"""stage 00: 建工作副本 + 剥 build/cache + git init。

历史上有 bash 版 stages/00_prepare.sh，已被本 Python 实现完全取代并删除。

行为：
  1) WORK_DIR 已存在则保留（便于 --from-stage 续跑）；否则：
     - 源是目录 → cp -r
     - 源是 .zip → unzip 到 WORK_DIR；如 zip 多套了一层目录则展平
  2) 删 build/cache 产物（防 grep / read 污染 LLM 上下文）
     - Node 系：node_modules / .next / dist / build / out / .turbo / .cache /
       .parcel-cache / .nuxt / .svelte-kit / .vite / coverage（顶层）
     - Python 系：__pycache__ / .pytest_cache / .mypy_cache / .ruff_cache /
       .venv / venv / .tox / *.egg-info / *.pyc（任意深度，但排除 node_modules）
     - 通用：.git / tmp / logs / .DS_Store
  3) 写 STATE_DIR/files-after-strip.txt 用于后续 diff
  4) git init + 首次 commit baseline
"""

from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

from .. import config, git, log, prompt_util

# 顶层硬删（不递归）—— Node 产物
_NODE_TOP_LEVEL = (
    "node_modules", ".next", "dist", "build", "out",
    ".turbo", ".cache", ".parcel-cache",
    ".nuxt", ".svelte-kit", ".vite", "coverage",
)

# 任意深度递归删 —— Python 产物
_PYTHON_DIRS = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", ".tox",
}

# 通用顶层硬删
_GENERIC_TOP_LEVEL = (".git", "tmp", "logs")


def _copy_or_unzip(src: Path, dst: Path) -> None:
    """根据源类型创建工作副本。"""
    if src.is_dir():
        log.log("cp -r 创建副本")
        # symlinks=False 与 bash cp -r 默认行为一致；ignore_dangling=True 避免坏链报错
        shutil.copytree(src, dst, symlinks=False, ignore_dangling_symlinks=True)
        return

    if src.is_file() and src.suffix == ".zip":
        log.log("解压 zip 创建副本")
        dst.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(src) as zf:
            zf.extractall(dst)
        # 如 zip 内套了一层目录，自动展平（仅当解出后 dst 下只有一个目录）
        items = list(dst.iterdir())
        if len(items) == 1 and items[0].is_dir():
            inner = items[0]
            log.log(f"zip 含外层目录 {inner.name}，展平")
            for child in inner.iterdir():
                shutil.move(str(child), str(dst / child.name))
            inner.rmdir()
        return

    log.die(f"源工程类型不支持：{src}")


def _strip_top_level(work_dir: Path, names: tuple[str, ...]) -> None:
    """硬删 work_dir 顶层指定名字的目录或文件。"""
    for name in names:
        p = work_dir / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            try:
                p.unlink()
            except OSError:
                pass


def _strip_python_artifacts(work_dir: Path) -> None:
    """递归删 __pycache__ / .pytest_cache / venv 等；排除 node_modules 子树。"""
    # os.walk topdown=True 时可以原地修改 dirnames 来剪枝
    for root, dirnames, filenames in os.walk(work_dir, topdown=True):
        # 剪枝：不下钻 node_modules
        dirnames[:] = [d for d in dirnames if d != "node_modules"]
        # 删匹配的目录
        kept = []
        for d in dirnames:
            if d in _PYTHON_DIRS or d.endswith(".egg-info"):
                shutil.rmtree(Path(root) / d, ignore_errors=True)
            else:
                kept.append(d)
        dirnames[:] = kept
        # 删 .pyc 和 .DS_Store
        for f in filenames:
            if f.endswith(".pyc") or f == ".DS_Store":
                try:
                    (Path(root) / f).unlink()
                except OSError:
                    pass


def _snapshot_files(work_dir: Path, out_file: Path) -> int:
    """生成"剥离后清单"snapshot；返回文件数。"""
    files: list[str] = []
    for root, dirnames, filenames in os.walk(work_dir, topdown=True):
        # 跳过 .guard-transform 内部目录（与 bash 版 -not -path 一致）
        dirnames[:] = [d for d in dirnames if d != ".guard-transform"]
        rel_root = Path(root).relative_to(work_dir)
        for f in filenames:
            rel = rel_root / f
            files.append(f"./{rel}" if str(rel_root) != "." else f"./{f}")
    files.sort()
    out_file.write_text("\n".join(files) + ("\n" if files else ""))
    return len(files)


# 历史上 _read_choice_with_timeout / _is_non_interactive_env 定义在本文件，
# 现统一抽到 guardx.prompt_util 供 git.py 等其他模块共用；这里保留同名别名
# 是为了避免其他地方有人 from . import _read_choice_with_timeout 的隐式依赖。
_read_choice_with_timeout = prompt_util.read_choice_with_timeout
_is_non_interactive_env = prompt_util.is_non_interactive


def _prepare_work_dir(cfg: config.Config) -> None:
    """按 cfg.fresh_copy_mode 决定如何处理已存在的工作副本目录。

    模式语义：
      - "reuse"  → 直接使用副本中现有内容（不重新 copy，保留你在副本里的所有改动）
      - "recopy" → 删掉副本目录 → 从源工程重新 copy 一份（丢弃所有副本中的改动）
      - "ask"    → 仅在 tty + 非 non-interactive 时弹问；否则等同 reuse
    """
    # 副本目录不存在：直接 copy，与历史行为完全一致
    if not cfg.work_dir.is_dir():
        _copy_or_unzip(cfg.source_project, cfg.work_dir)
        return

    mode = getattr(cfg, "fresh_copy_mode", "ask") or "ask"

    # ask 模式 + 非交互环境 / 非 tty → 自动降级为 reuse（向后兼容历史行为）
    if mode == "ask":
        if _is_non_interactive_env() or not sys.stdin.isatty() or not sys.stderr.isatty():
            log.log("[fresh-copy] 非交互环境，自动选择「使用现有副本」（如需重新 copy 请显式传 --recopy 或 GUARD_FRESH_COPY_MODE=recopy）")
            mode = "reuse"

    # ask 模式 + 交互环境 → 弹直白的选择菜单（30s 超时按 1）
    if mode == "ask":
        work_name = cfg.work_dir.name
        src_name = cfg.source_project.name
        prompt = (
            f"\n{log.C_BLD}发现工作副本目录已存在：{log.C_RST}{cfg.work_dir}\n"
            f"  {log.C_GRN}[1]{log.C_RST} 使用 {work_name} 中现有的内容进行转写"
            f"（保留你在该副本中已做的所有修改，不重新 copy 源码）\n"
            f"  {log.C_YEL}[2]{log.C_RST} 清空 {work_name}，重新从源工程 {src_name} 复制一份"
            f"（丢弃副本中所有改动，从干净源码开始）\n"
            f"  {log.C_RED}[q]{log.C_RST} 退出，不做任何修改\n"
            f"\n请输入 1 / 2 / q（30 秒超时按 1）: "
        )
        ans = _read_choice_with_timeout(prompt, timeout_s=30, default="1")
        if ans in ("1", "", "reuse", "use", "y", "yes"):
            mode = "reuse"
        elif ans in ("2", "recopy", "fresh", "new"):
            mode = "recopy"
        elif ans in ("q", "quit", "exit", "n", "no"):
            log.die("用户取消操作（在工作副本选择菜单选了退出）")
        else:
            log.warn(f"未识别的输入 '{ans}'，默认按「1（使用现有副本）」继续")
            mode = "reuse"

    # 落到实际行为
    if mode == "recopy":
        log.warn(f"[fresh-copy] 清空旧工作副本：{cfg.work_dir}")
        shutil.rmtree(cfg.work_dir, ignore_errors=True)
        if cfg.work_dir.exists():
            # 极端情况：rmtree 没清干净（权限 / busy 文件）
            log.die(f"无法清空工作副本目录 {cfg.work_dir}；请手动删除后重试")
        _copy_or_unzip(cfg.source_project, cfg.work_dir)
    else:
        log.log(f"[fresh-copy] 使用现有工作副本 {cfg.work_dir} 的内容继续转写")


def run(cfg: config.Config) -> int:
    log.log(f"源工程    : {cfg.source_project}")
    log.log(f"工作副本  : {cfg.work_dir}")

    # 1. 副本：按 fresh_copy_mode 决定怎么处理已存在的工作副本目录
    #   reuse  → 静默使用其中现有内容（保留你在副本里的手改；--from-stage 续跑场景必备）
    #   recopy → 删除副本目录 + 从源工程重新 copy 一份（丢弃所有副本中的改动）
    #   ask    → 仅当 stdin 是 tty 且非 server profile 时弹问；否则等同 reuse
    _prepare_work_dir(cfg)

    # 2. 剥 build / cache
    log.log("剥离 build / cache 产物（防 grep / read 污染）")
    _strip_top_level(cfg.work_dir, _NODE_TOP_LEVEL)
    _strip_python_artifacts(cfg.work_dir)
    _strip_top_level(cfg.work_dir, _GENERIC_TOP_LEVEL)

    # 3. 用户上传清单 snapshot
    out = cfg.state_dir / "files-after-strip.txt"
    n = _snapshot_files(cfg.work_dir, out)
    log.log(f"副本含 {n} 个源码文件")

    # 4. git init 跟踪 LLM 改动
    git.ensure_repo(cfg.work_dir)
    log.log("git 初始化完成")

    log.ok("stage 00 完成")
    return 0
