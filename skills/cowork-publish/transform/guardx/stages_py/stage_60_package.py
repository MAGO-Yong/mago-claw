"""stage 60: 打 zip + 顶层结构断言。

排除规则与 bash 版严格对齐（同时覆盖顶层和子目录，monorepo 必须的）。
打包后断言 zip 顶层必须直接含 install.sh / start.sh / health.sh，
否则说明多套了一层目录（cd 错位常见 bug）。
"""

from __future__ import annotations

import fnmatch
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path

from .. import config, log

# 排除模式（fnmatch 风格）；与 bash zip -x 严格对齐
# 每个 pattern 都对应"任意层级"的匹配：
#   - "node_modules/*" → 任何 node_modules 目录下的文件
#   - "*/node_modules/*" → 子目录下的 node_modules
#   - 顶层文件如 ".env" 也排除
#
# 注：下面这一行 "*credentials*"/"*secret*"/"*token*"/"*.pem"/"*.key"/"id_rsa*"
# 是【打包排除清单】里的敏感文件名 glob —— 用途是把工作副本里**可能误存在的**敏感
# 文件挡在 zip 之外（防止误打包上传），不是读取或访问任何凭据。SAST 扫描器误把这
# 几个保护性 pattern 当成"读凭据"，请按白名单处理。
_EXCLUDE_PATTERNS = (
    "*.git*",
    "node_modules", "node_modules/*", "*/node_modules", "*/node_modules/*",
    ".next/cache", ".next/cache/*", "*/.next/cache", "*/.next/cache/*",
    ".turbo", ".turbo/*", "*/.turbo", "*/.turbo/*",
    ".parcel-cache", ".parcel-cache/*", "*/.parcel-cache", "*/.parcel-cache/*",
    ".venv", ".venv/*", "*/.venv", "*/.venv/*",
    "__pycache__", "__pycache__/*", "*/__pycache__", "*/__pycache__/*",
    "*.pyc",
    ".env", ".env.*", ".envrc", "*/.env", "*/.env.*",
    "db.properties", "ai.properties", "*.example",
    "build.sh",
    "docker-compose*.yml", "Dockerfile*",
    "README*.md", "CHANGELOG*.md", "CONTRIBUTING*.md", "LICENSE*",
    "*credentials*", "*secret*", "*token*", "*.pem", "*.key", "id_rsa*",
    "Makefile", "justfile", "Taskfile.yml",
    ".DS_Store", "*/.DS_Store",
    ".idea", ".idea/*", "*/.idea", "*/.idea/*",
    ".vscode", ".vscode/*", "*/.vscode", "*/.vscode/*",
    "docs", "docs/*", "*/docs", "*/docs/*",
    "wiki", "wiki/*", "*/wiki", "*/wiki/*",
    "tsconfig.tsbuildinfo", "*/tsconfig.tsbuildinfo",
)

# .guard-transform-* 也要排（落地的状态目录，可能在副本旁）
_INTERNAL_DIR_PREFIX = ".guard-transform"


def _is_excluded(rel_path: str) -> bool:
    """rel_path 是 './' 风格的相对路径（不含 './' 前缀）。"""
    parts = rel_path.split("/")
    # 任意路径段命中模式即排除
    for pat in _EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_path, pat):
            return True
        # 也对每个目录段做匹配（覆盖 "node_modules/" 这类目录排除）
        for seg in parts:
            if fnmatch.fnmatch(seg, pat):
                return True
    return False


def _chmod_x_top_sh(work_dir: Path) -> None:
    for f in work_dir.glob("*.sh"):
        try:
            st = f.stat()
            f.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass


def _strip_pre_zip(work_dir: Path) -> None:
    """zip 前清理：.git + 任何 .guard-transform-* 子目录。"""
    git_dir = work_dir / ".git"
    if git_dir.is_dir():
        shutil.rmtree(git_dir, ignore_errors=True)
    for root, dirnames, _ in os.walk(work_dir, topdown=True):
        # 原地修改 dirnames 实现 "深度遍历但删后剪枝"
        to_remove = [d for d in dirnames if d.startswith(_INTERNAL_DIR_PREFIX)]
        for d in to_remove:
            shutil.rmtree(Path(root) / d, ignore_errors=True)
        dirnames[:] = [d for d in dirnames if not d.startswith(_INTERNAL_DIR_PREFIX)]


def _walk_for_zip(work_dir: Path) -> list[Path]:
    """收集所有要打进 zip 的文件（绝对路径）。"""
    out: list[Path] = []
    for root, dirnames, filenames in os.walk(work_dir, topdown=True):
        # 剪枝：被排除的目录直接不下钻（性能 + 防意外吃 node_modules 几十万文件）
        rel_root = Path(root).relative_to(work_dir).as_posix()
        kept_dirs: list[str] = []
        for d in dirnames:
            rel = d if rel_root == "." else f"{rel_root}/{d}"
            if _is_excluded(rel) or _is_excluded(d):
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for f in filenames:
            rel = f if rel_root == "." else f"{rel_root}/{f}"
            if _is_excluded(rel):
                continue
            out.append(Path(root) / f)
    out.sort()
    return out


def _make_zip(work_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    files = _walk_for_zip(work_dir)
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        for fp in files:
            arcname = fp.relative_to(work_dir).as_posix()
            zf.write(fp, arcname=arcname)


def _list_top_level(zip_path: Path) -> set[str]:
    """zip 顶层条目集合（仅取首个路径段）。"""
    top: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name:
                continue
            seg = name.split("/", 1)[0]
            top.add(seg)
    return top


# 禁止打进 zip 的"敏感/平台注入"文件名（任意层级出现都拦截）
# 详见 transform_prompt.md § 二 + § 五（db.properties / ai.properties 由平台运行时注入到
# 与 install.sh 同级的顶层目录，不能由项目自带；.env 会让运维误以为可改）
_ZIP_BANNED_NAMES = (
    "db.properties",
    "ai.properties",
    ".env",
    ".env.development",
    ".env.production",
    ".env.local",
    ".env.test",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
)


def _assert_no_banned_in_zip(zip_path: Path) -> list[str]:
    """返回 zip 内出现的禁打文件路径列表（任意层级，含子目录）。"""
    banned_set = {n.lower() for n in _ZIP_BANNED_NAMES}
    found: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            base = name.rsplit("/", 1)[-1].lower()
            # 精确文件名匹配
            if base in banned_set:
                found.append(name)
                continue
            # .env.* 模糊（覆盖 .env.staging 等）
            if base.startswith(".env."):
                found.append(name)
                continue
            # Dockerfile.* 模糊
            if base.startswith("dockerfile."):
                found.append(name)
                continue
            # docker-compose.*.yml 模糊
            if base.startswith("docker-compose.") and (base.endswith(".yml") or base.endswith(".yaml")):
                found.append(name)
                continue
    return found


def run(cfg: config.Config) -> int:
    work_dir = cfg.work_dir

    # 统一 chmod
    _chmod_x_top_sh(work_dir)

    # 删 .git + .guard-transform-* 子目录
    _strip_pre_zip(work_dir)

    # zip 文件名带 MMDDhhmm 时间戳后缀，每次跑 transform 都产出独立产物
    # （cfg.zip_path 在 Config 实例化时一次性确定，stage 60 / stage 70 / cli banner 引用同值）
    zip_path = cfg.zip_path
    log.log(f"打包 zip: {zip_path}")
    log.log(f"  时间戳后缀: {cfg.zip_timestamp}（可用 GUARD_ZIP_TIMESTAMP=MMDDhhmm 指定）")
    _make_zip(work_dir, zip_path)

    # ---- 关键断言 1：zip 顶层结构 ----
    # 默认要求顶层直接含 install.sh / start.sh / health.sh；
    # 纯前端项目（stack.frontend_only=1）改为要求构建产物里有 index.html
    # （dist/index.html / build/index.html / out/index.html / 顶层 index.html 任一）。
    log.log("断言 zip 顶层结构")
    top = _list_top_level(zip_path)

    frontend_only = False
    stack_path = cfg.state_dir / "stack.json"
    if stack_path.is_file():
        try:
            stack = json.loads(stack_path.read_text())
            frontend_only = str(stack.get("frontend_only", "")) == "1"
        except (OSError, json.JSONDecodeError):
            pass

    if frontend_only:
        # 找 index.html：dist/build/out/顶层 任一存在即可
        index_candidates = ("dist/index.html", "build/index.html", "out/index.html", "index.html")
        with zipfile.ZipFile(zip_path) as zf:
            zip_names = set(zf.namelist())
        if not any(c in zip_names for c in index_candidates):
            log.die(
                "frontend_only 项目 zip 内未找到 index.html "
                f"（已扫: {', '.join(index_candidates)}）；"
                "确认 stage 40 已成功 build，产物落到 dist/ 或 build/"
            )
        log.ok("zip 含构建产物 index.html (frontend_only)")
    else:
        for f in ("install.sh", "start.sh", "health.sh"):
            if f not in top:
                log.die(f"zip 顶层缺 {f}（多套了一层目录？请检查 cd 进副本再打）")
        log.ok("zip 顶层结构正确")

    # ---- 关键断言 2：zip 内不能含 db.properties / ai.properties / .env / Dockerfile ----
    # 这些要么由平台运行时注入（db/ai.properties），要么是开发期残留（.env / Dockerfile）
    # 详见 transform_prompt.md § 二 + § 五
    log.log("断言 zip 不含敏感 / 平台注入 / 开发期残留文件")
    banned_in_zip = _assert_no_banned_in_zip(zip_path)
    if banned_in_zip:
        msg_lines = ["zip 内含禁止打包的文件（必须由 stage 30 / 60 排除）:"]
        for p in banned_in_zip[:20]:
            msg_lines.append(f"  - {p}")
        if len(banned_in_zip) > 20:
            msg_lines.append(f"  ...（共 {len(banned_in_zip)} 项）")
        msg_lines.append(
            "  说明：db.properties/ai.properties 由平台注入到与 install.sh 同级的顶层目录，"
            ".env/Dockerfile 是开发期残留"
        )
        log.die("\n".join(msg_lines))
    log.ok("zip 不含禁打文件")

    # ---- 关键断言 3：zip 内不能含任何嵌套 venv（任意目录名）----
    # 设计理由：
    #   _EXCLUDE_PATTERNS 里的 ".venv"/".venv/*" 只能挡名字叫 .venv 的目录，
    #   用户手写 build.sh 完全可能 `python3 -m venv venv` / `python3 -m venv myenv` /
    #   `python3 -m virtualenv .my-py-env`，绕过名字白名单 → venv 落进 zip → 上线后
    #   `.venv/bin/gunicorn` 形态的 shebang ENOENT 重现（详见 verify_no_venv_creation.sh）。
    #
    #   此处用 venv 自身的"指纹文件"做判定，名字无关：
    #     - `pyvenv.cfg`：CPython `venv` 模块在 venv 根目录强制创建的元数据文件，
    #                     存在 = 这一定是个 venv（无论目录叫什么）
    #     - `*/bin/python*` 当前先不查 ELF 头，仅 pyvenv.cfg 已足够覆盖 venv 模块产物；
    #       virtualenv CLI 也写 pyvenv.cfg（兼容 PEP 405），同样能命中。
    #
    #   touch 此 assert 只在 zip 已生成后扫一次条目名，不读文件内容，零额外 IO。
    log.log("断言 zip 不含嵌套 venv（pyvenv.cfg 指纹）")
    venv_hits: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            if name.rsplit("/", 1)[-1] == "pyvenv.cfg":
                venv_hits.append(name)
    if venv_hits:
        msg_lines = ["zip 内发现嵌套 venv（pyvenv.cfg 文件）:"]
        for p in venv_hits[:10]:
            venv_root = p.rsplit("/", 1)[0] if "/" in p else "(zip 顶层)"
            msg_lines.append(f"  - {p}  ← venv root: {venv_root}")
        if len(venv_hits) > 10:
            msg_lines.append(f"  ...（共 {len(venv_hits)} 个）")
        msg_lines.append("")
        msg_lines.append(
            "  根因：业务 .sh 在工程内创建了嵌套 venv（python -m venv 或 virtualenv），"
            "_EXCLUDE_PATTERNS 仅按名字过滤 .venv/，非 .venv 名字的 venv 会被打进 zip。"
        )
        msg_lines.append(
            "  后果：guard-rust 启动时会 `fs::rename` 工程目录，但 venv 内 console_script "
            "(gunicorn/uvicorn 等) 的 shebang 写死创建时刻的绝对路径，rename 后 execve "
            "ENOENT，bash 报 `cannot execute: required file not found`。"
        )
        msg_lines.append(
            "  修复：参见 verify_no_venv_creation.sh —— 删掉所有 `python -m venv ...` / "
            "`virtualenv ...`，依赖 Pod 镜像的 /opt/venv 全局 venv，install.sh 直接 "
            "`python3 -m pip install`，start.sh 直接 `exec python3 -m gunicorn ...`。"
        )
        log.die("\n".join(msg_lines))
    log.ok("zip 不含嵌套 venv")

    # ---- 大小检查 ----
    size = zip_path.stat().st_size
    size_mb = size // (1024 * 1024)
    log.log(f"zip 大小: {size_mb} MB")
    if size_mb > 200:
        log.warn("zip > 200 MB；常见原因：未排 node_modules / 大模型权重未排")

    log.ok("stage 60 完成")
    return 0
