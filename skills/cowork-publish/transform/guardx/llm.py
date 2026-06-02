"""LLM CLI 抽象层（翻译自 lib/llm.sh）。

支持 7 个后端：claude / qwen-code / codex / gemini / codewiz / seal / mock
通过 GUARD_LLM 环境变量选择，默认 claude。

seal 后端说明：
  - seal 是小红书内部 IDE，其内置 CLI 名为 `codewiz-cc`
  - `codewiz-cc` 本身是 Claude Code 的 fork，CLI 参数与 `claude` 完全兼容
  - 因此 seal backend 复用 claude 的全部 argv 构造逻辑，仅把可执行文件名替换为 codewiz-cc

关键不变量（与 bash 版完全一致）：
  1) stdin 必须 DEVNULL，否则 LLM CLI 探测 tty 会挂死
  2) 单次调用必须有"工作目录边界"（cwd 或 --dir 参数）
  3) timeout 兜底（GUARD_LLM_TIMEOUT 秒，默认 600）；命中时整树杀
  4) heartbeat 周期性输出"还活着"，防长任务被误判假死
  5) 失败必须返回非 0；调用方负责 git commit + verifier

bash 版 350 行，Python 版 ~200 行——所有"_bash_timeout / _kill_descendants /
_start_heartbeat / _tty_prefix_setup / declare -a TTY_PRE / PIPESTATUS"等
跨平台 + set -u + 数组兼容性踩坑全部消失（process.run 一手搞定）。
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import log, process

SUPPORTED_BACKENDS = ("claude", "qwen-code", "codex", "gemini", "codewiz", "seal", "mock")

# seal 后端实际调用的 CLI 名（Claude Code 的 fork，参数兼容）
_SEAL_CLI = "codewiz-cc"

# ---- 模型分级路由：strong（复杂改写）/ fast（局部 autofix）----
# 服务端可选模型（截至 2025-Q2 平台清单）：
#   - claude-opus-4-6   ($5/$25 per Mtok)  深度思考，质量最高，速度慢
#   - claude-sonnet-4-6 ($3/$15 per Mtok)  日常任务，质量接近 Opus，速度快 2-3x
#   - claude-haiku-4-5  ($1/$5  per Mtok)  快速回答，适合分类/格式化
#
# 默认分级策略：
#   strong → opus-4-6 （仅 stage 20 rewrite_loop 跨文件大改造时用）
#   fast   → sonnet-4-6（其他所有 stage：30/40/50 autofix、verify_start_sh_llm 等）
#
# 覆盖优先级（高 → 低）：
#   1) GUARD_LLM_MODEL          一刀切覆盖所有 profile（向后兼容旧用法；
#                               install.sh 默认留空，让分级路由真正生效）
#   2) GUARD_LLM_MODEL_STRONG   覆盖 strong profile
#      GUARD_LLM_MODEL_FAST     覆盖 fast   profile
#   3) 内置默认（_DEFAULT_MODEL_STRONG / _DEFAULT_MODEL_FAST）
_DEFAULT_MODEL_STRONG = "claude-opus-4-6"
_DEFAULT_MODEL_FAST = "claude-sonnet-4-6"
_VALID_PROFILES = ("strong", "fast")


@dataclass
class LLMConfig:
    """LLM 后端配置；默认从环境变量读取（与 bash 版同名）。

    profile 字段决定该次调用走哪个模型：
      - "fast"   （默认）：autofix / 局部小修 → sonnet-4-6
      - "strong" :  stage 20 跨文件改写       → opus-4-7
    """

    backend: str = field(default_factory=lambda: os.environ.get("GUARD_LLM", "claude"))
    timeout: int = field(default_factory=lambda: int(os.environ.get("GUARD_LLM_TIMEOUT", "600")))
    heartbeat: int = field(default_factory=lambda: int(os.environ.get("GUARD_LLM_HEARTBEAT", "30")))
    tty: bool = field(default_factory=lambda: os.environ.get("GUARD_LLM_TTY", "0") == "1")
    # 兼容字段：GUARD_LLM_MODEL 一旦设置就一刀切覆盖 profile 路由（向后兼容）
    model: Optional[str] = field(default_factory=lambda: os.environ.get("GUARD_LLM_MODEL") or None)
    # 新增字段：分级 profile（默认 fast；stage_20 显式传 strong）
    profile: str = "fast"
    skip_llm: bool = field(default_factory=lambda: os.environ.get("SKIP_LLM", "0") == "1")
    home: Path = field(
        default_factory=lambda: Path(
            os.environ.get(
                "GUARD_TRANSFORM_HOME",
                str(Path(__file__).resolve().parent.parent),
            )
        )
    )

    def __post_init__(self) -> None:
        if self.backend not in SUPPORTED_BACKENDS:
            log.die(f"未知 GUARD_LLM 后端: {self.backend}（支持: {', '.join(SUPPORTED_BACKENDS)}）")
        if self.profile not in _VALID_PROFILES:
            log.die(f"未知 LLMConfig.profile: {self.profile}（支持: {', '.join(_VALID_PROFILES)}）")

    @classmethod
    def for_profile(cls, profile: str, **overrides) -> "LLMConfig":
        """便捷构造：LLMConfig.for_profile('strong') / LLMConfig.for_profile('fast')。

        支持透传 timeout 等 dataclass 字段覆盖，例如：
            LLMConfig.for_profile('fast', timeout=1800)  # detect 子任务用更长超时
        """
        return cls(profile=profile, **overrides)

    def model_id(self) -> Optional[str]:
        """返回当前 profile 应使用的模型 id；None 表示让后端 CLI 走自身默认。

        优先级：GUARD_LLM_MODEL（一刀切）→ profile 专属 env → 内置默认。
        """
        if self.model:
            # 用户显式指定 GUARD_LLM_MODEL，profile 路由失效
            return self.model
        if self.profile == "strong":
            return os.environ.get("GUARD_LLM_MODEL_STRONG") or _DEFAULT_MODEL_STRONG
        # profile == "fast"
        return os.environ.get("GUARD_LLM_MODEL_FAST") or _DEFAULT_MODEL_FAST

    def available(self) -> bool:
        """探测当前后端 CLI 是否可用。mock 永远 True。

        seal 后端实际依赖 codewiz-cc 二进制（Claude Code fork）。
        """
        if self.backend == "mock":
            return True
        if self.backend == "seal":
            return shutil.which(_SEAL_CLI) is not None
        return shutil.which(self.backend) is not None


def _tty_prefix(cfg: LLMConfig) -> list[str]:
    """GUARD_LLM_TTY=1 时返回 ['script', '-q', '/dev/null'] 前缀（仅 macOS）。

    Linux 的 util-linux script 用法不同（必须 -c "cmd" 拼字符串），暂不支持。
    """
    if not cfg.tty:
        return []
    if shutil.which("script") is None:
        return []
    import platform

    if platform.system() == "Darwin":
        return ["script", "-q", "/dev/null"]
    log.warn("GUARD_LLM_TTY=1 在 Linux 上暂不支持（util-linux script 用法不同），已忽略")
    return []


def _compose_prompt(task_prompt: Path, state_dir: Path, home: Path) -> Path:
    """把 prompts/00_system.md + project_brief.md 拼到 task prompt 前；返回合成后的临时文件。

    动机：codewiz/claude 的 --dir 锁在 work_dir，LLM 读不到 guard-transform
    仓库内的文件，必须把 system prompt 物理拼接进 task prompt 才能让 LLM 看到。

    拼接顺序：
      [00_system.md]
      ---
      [project_brief.md]（若存在且当前 task 不是生成 brief 本身）
      ---
      [task_prompt]

    project_brief.md 由 stage 10 末尾生成，落盘到 state_dir/project_brief.md。
    生成 brief 本身的那次调用（task_prompt.stem == "10_project_brief"）跳过拼接，
    避免循环依赖（brief 还没生成）。
    """
    sys_prompt = home / "prompts" / "00_system.md"
    if not sys_prompt.exists():
        return task_prompt
    composed = state_dir / f"_composed-{task_prompt.stem}.md"

    # 拼接 project_brief.md（跳过生成 brief 本身的那次调用）
    brief_section = ""
    if task_prompt.stem != "10_project_brief":
        brief_path = state_dir / "project_brief.md"
        if brief_path.is_file():
            brief_section = (
                "\n\n---\n\n"
                "## 项目简述（stage 10 自动生成，供参考）\n\n"
                + brief_path.read_text().rstrip("\n")
            )

    composed.write_text(
        sys_prompt.read_text() + brief_section + "\n\n---\n\n" + task_prompt.read_text()
    )
    return composed


def _build_argv(cfg: LLMConfig, prompt_file: Path, work_dir: Path, extra: list[str]) -> tuple[list[str], Optional[Path]]:
    """根据 backend 构造 argv 列表，返回 (argv, cwd)。

    cwd=None 表示 backend 自己管目录（如 codewiz --dir）；
    其他都需要让 process.run(cwd=work_dir) 切目录。
    """
    pre = _tty_prefix(cfg)
    prompt_text = prompt_file.read_text()

    # 让所有支持的后端都享受 profile 路由（claude / codewiz 都能 --model 直传）
    mid = cfg.model_id()

    if cfg.backend in ("claude", "seal"):
        # seal CLI（codewiz-cc）是 Claude Code 的 fork，参数集完全兼容 claude，
        # 因此共用同一段 argv 构造，仅替换可执行文件名。
        cli_name = "claude" if cfg.backend == "claude" else _SEAL_CLI
        argv = pre + [
            cli_name, "-p", prompt_text,
            "--output-format", "text",
            # bypassPermissions：guard-transform 内部的 LLM 调用需要修改用户的工作副本，
            # 必须跳过权限确认（stdin=DEVNULL 场景下等确认会永久 hang）。
            # allowedTools 限定可用工具范围，防止 LLM 越界操作。
            "--permission-mode", "bypassPermissions",
            "--allowedTools", "Read,Write,Edit,Glob,Grep,Bash",
            "--max-turns", "20",
        ]
        # profile 路由：strong → opus-4-7，fast → sonnet-4-6（默认）
        # 关键修复：原版只对 codewiz 透传 model，claude 后端会一直走服务端默认（Opus 4.7），
        # 导致 fast profile 失效、autofix 全在 Opus 上烧 token + 触发深度思考变慢。
        if mid:
            argv += ["--model", mid]
        argv += extra
        return argv, work_dir
    if cfg.backend == "qwen-code":
        argv = pre + ["qwen-code", "--prompt-file", str(prompt_file), "--yes"] + extra
        return argv, work_dir
    if cfg.backend == "codex":
        argv = pre + ["codex", "exec", "--skip-git-repo-check", prompt_text] + extra
        return argv, work_dir
    if cfg.backend == "gemini":
        argv = pre + ["gemini", "--prompt", prompt_text, "--yolo"] + extra
        return argv, work_dir
    if cfg.backend == "codewiz":
        argv = pre + [
            "codewiz", "run",
            "--dir", str(work_dir),
            "--dangerously-skip-permissions",
        ]
        if mid:
            argv += ["--model", mid]
        argv += [prompt_text] + extra
        return argv, None  # codewiz 自己 --dir，不必 cwd
    raise RuntimeError(f"unreachable: backend={cfg.backend}")


def call(
    prompt_file: Path,
    work_dir: Path,
    state_dir: Path,
    *extra: str,
    cfg: Optional[LLMConfig] = None,
    log_label: str = "",
) -> process.RunResult:
    """单次 LLM 调用。

    Args:
        prompt_file: prompt md 文件
        work_dir: LLM 操作的工作目录（边界）
        state_dir: 日志/合成 prompt 落盘位置
        extra: 透传给 backend CLI 的额外参数
        cfg: 配置；默认 LLMConfig() 从环境变量读
        log_label: 用于日志前缀和文件名（如 stage 名）

    Returns:
        RunResult: returncode=0 即成功；returncode=124 即 timeout
    """
    cfg = cfg or LLMConfig()

    if not prompt_file.is_file():
        log.fail(f"prompt 文件不存在: {prompt_file}")
        return process.RunResult(returncode=1, log_path=None)
    if not work_dir.is_dir():
        log.fail(f"工作目录不存在: {work_dir}")
        return process.RunResult(returncode=1, log_path=None)

    if cfg.skip_llm:
        log.warn(f"SKIP_LLM=1，跳过 LLM 调用: {prompt_file}")
        return process.RunResult(returncode=0, log_path=None)

    if not cfg.available():
        log.fail(
            f"LLM 后端 '{cfg.backend}' CLI 未安装；"
            "export GUARD_LLM=mock 可走空操作模式"
        )
        return process.RunResult(returncode=1, log_path=None)

    # 自动拼 system prompt
    composed = _compose_prompt(prompt_file, state_dir, cfg.home)

    # mock backend 直接返回（不实际调用）
    if cfg.backend == "mock":
        out_path = state_dir / f"llm-{composed.stem}-{int(time.time())}.log"
        out_path.write_text(f"[mock-llm] would have run: {composed} in {work_dir}\n")
        log.log(f"[mock-llm] would have run: {composed} in {work_dir}")
        return process.RunResult(returncode=0, log_path=out_path)

    out_path = state_dir / f"llm-{composed.stem}-{int(time.time())}.log"
    # 显示实际生效模型 id 便于排查（profile 路由结果一目了然）
    _model_hint = cfg.model_id() or "<后端默认>"
    log.log(
        f"  LLM 调用 backend={cfg.backend}, profile={cfg.profile}, "
        f"model={_model_hint}, timeout={cfg.timeout}s, log={out_path}"
    )
    log.log(
        f"  提示：实时输出已转发到当前终端；每 {cfg.heartbeat}s 一次 heartbeat；"
        "CTRL+C 2s 内退出，当前 stage 会标 fail 可 --resume"
    )
    if cfg.tty and _tty_prefix(cfg):
        log.log(
            "  GUARD_LLM_TTY=1: 已为 LLM CLI 制造伪 tty"
            "（按行 flush + spinner，输出可能含 ^M）"
        )

    argv, cwd = _build_argv(cfg, composed, work_dir, list(extra))
    result = process.run(
        argv,
        cwd=cwd,
        timeout=cfg.timeout if cfg.timeout > 0 else None,
        log_path=out_path,
        heartbeat_sec=cfg.heartbeat,
        label=log_label or cfg.backend,
    )

    if result.timed_out:
        log.fail(
            f"{cfg.backend} 超时（>{cfg.timeout}s）；"
            "调高 GUARD_LLM_TIMEOUT 或检查 CLI 鉴权 / 网络"
        )
    return result


def call_with_verify(
    prompt_file: Path,
    verifier: Path,
    work_dir: Path,
    state_dir: Path,
    *,
    max_retry: int = 3,
    cfg: Optional[LLMConfig] = None,
) -> bool:
    """调 LLM 改代码 → 跑 verifier → 失败把 verifier stderr 喂回去重试。

    返回 True 表示某轮 verifier 通过；False 表示 max_retry 用尽仍失败。
    """
    cfg = cfg or LLMConfig()
    last_err = ""
    for n in range(1, max_retry + 1):
        log.log(f"LLM 调用 [{n}/{max_retry}]: {prompt_file.name}")

        actual_prompt = prompt_file
        if last_err:
            actual_prompt = state_dir / f"_retry-{prompt_file.name}"
            actual_prompt.write_text(
                prompt_file.read_text()
                + "\n\n---\n## 上一次的 verifier 失败信息（请修正）\n\n```\n"
                + last_err
                + "\n```\n"
            )

        r = call(actual_prompt, work_dir, state_dir, cfg=cfg)
        if not r.ok:
            log.warn(f"LLM 调用失败（第 {n} 次）")

        # 跑 verifier，捕获 stderr 用于下一轮反馈
        verify_log = state_dir / "_verify-stderr"
        rv = process.run(
            ["bash", str(verifier), str(work_dir)],
            log_path=verify_log,
            heartbeat_sec=0,
            timeout=300,
        )
        if rv.ok:
            log.ok(f"verifier 通过：{verifier.name}")
            return True

        try:
            last_err = verify_log.read_text()
        except OSError:
            last_err = "(无法读取 verifier 日志)"
        log.warn(f"verifier 失败（第 {n} 次）：{verifier.name}")
        # 缩进打印日志，与 bash 版一致
        for line in last_err.splitlines():
            log.log(f"    {line}")

    log.fail(f"LLM 改写后 {max_retry} 次 verifier 仍失败：{verifier.name}")
    return False
