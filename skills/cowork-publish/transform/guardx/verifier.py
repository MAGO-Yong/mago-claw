"""verifier 跑测 + AI 自愈封装（翻译自 lib/common.sh 的 run_verifier /
run_verifier_with_autofix / run_with_autofix）。

verifier 本身仍是 bash 脚本（设计哲学要求"独立可验证 + 不依赖 guard-transform 内部状态"），
本文件提供：
  - run(verifier, work_dir, state_dir): 跑一次 verifier，输出落 verify-<name>.log
  - run_with_autofix(verifier, ...): 失败时调 LLM 修，最多 max_attempts 次
  - run_cmd_with_autofix(...): 包装一个**任意构建命令**，失败时同样调 LLM 修

与 bash 版的语义不变量：
  1. verifier 是 `bash <script> <work_dir>` 调用约定
  2. 输出路径形如 STATE_DIR/verify-<basename>.log（autofix 重跑覆盖同一文件）
  3. autofix prompt 用 prompts/50_fix_verify_failure.md / prompts/40_fix_build_error.md 作前缀
  4. LLM 输出含 `^CANNOT_FIX:` 时立刻放弃（避免无限烧 token）
  5. 每次 autofix 成功后 `git_commit_step "autofix: ..."` 留可追踪痕迹
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional, Sequence

from . import config, git, llm, log, process

_CANNOT_FIX_RE = re.compile(r"^CANNOT_FIX:", re.MULTILINE)


def run(verifier: Path, work_dir: Path, state_dir: Path) -> bool:
    """跑一次 verifier，成功 True / 失败 False。

    日志固定写到 STATE_DIR/verify-<name>.log（与 bash 版一致，stage 70 会扫这里）。
    失败时把日志缩进打到 stderr 方便排查。
    """
    name = verifier.stem
    out = state_dir / f"verify-{name}.log"
    out.parent.mkdir(parents=True, exist_ok=True)

    # 直接 capture（verifier 通常 < 30s，不需要 tee 实时输出）
    res = subprocess.run(
        ["bash", str(verifier), str(work_dir)],
        capture_output=True,
        text=True,
    )
    out.write_text((res.stdout or "") + (res.stderr or ""))
    if res.returncode == 0:
        log.ok(name)
        return True

    log.fail(f"{name} (详见 {out})")
    for line in (res.stdout + res.stderr).splitlines():
        log.log(f"    {line}")
    return False


# 关键行抽取：用于 _extract_key_lines 把 verifier stderr 里的修复指引置顶。
# 规则：
#   [HINT] ... —— verifier 显式给的"目标文件 + 怎么改"提示（最高优先级）
#   [FAIL] ... —— verifier 的失败结论行（描述根因）
# 这两类行会被抽出来放在 prompt 顶部，LLM 第一眼就看到修复方向，
# 避免 LLM 从 200 行 log 里再扫一遍 → 省 LLM 输出 token + 减少试错轮次。
_KEY_LINE_RE = re.compile(r"^\s*\[(HINT|FAIL)\]\s*(.+)$")


def _extract_key_lines(log_text: str, *, max_lines: int = 30) -> list[str]:
    """从 verify_log 抽出 [HINT] / [FAIL] 行，按出现顺序去重保留前 max_lines 条。

    去重原因：verifier 在 stderr / stdout 都打一遍 FAIL 是常见模式；
    autofix 阶段重复行只会加噪声不会加信息。
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in log_text.splitlines():
        m = _KEY_LINE_RE.match(raw)
        if not m:
            continue
        norm = raw.strip()
        if norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
        if len(out) >= max_lines:
            break
    return out


def _build_autofix_prompt(
    base_prompt: Path,
    *,
    name: str,
    verifier_path: Path,
    verify_log_path: Path,
    stack_json_path: Optional[Path],
    attempt: int,
) -> str:
    """拼 verifier autofix 用的 prompt 文本（不落盘，调用方决定写哪）。"""
    parts: list[str] = [base_prompt.read_text()]
    parts.append("\n\n---\n## 当前失败的 verifier 信息\n")
    parts.append(f"\n**VERIFIER_NAME**: `{name}`\n")

    # 取最后 200 行用作 VERIFY_LOG；同时从全文抽 [HINT] / [FAIL] 关键行置顶
    try:
        log_text = verify_log_path.read_text()
        lines = log_text.splitlines()
        tail = "\n".join(lines[-200:])
    except OSError:
        log_text = ""
        tail = "(verify log unreadable)"

    key_lines = _extract_key_lines(log_text)
    if key_lines:
        parts.append(
            "\n**KEY_HINTS** (verifier 直接抽出的失败结论 + 修复建议，**优先看这块**)：\n\n```\n"
            + "\n".join(key_lines)
            + "\n```\n"
        )

    parts.append(f"\n**VERIFIER_SCRIPT** (`{verifier_path}`):\n\n```bash\n{verifier_path.read_text()}```\n")
    parts.append(f"\n**VERIFY_LOG** (最后 200 行):\n\n```\n{tail}\n```\n")

    if stack_json_path and stack_json_path.is_file():
        parts.append(f"\n**STACK_INFO**:\n\n```json\n{stack_json_path.read_text()}```\n")

    if attempt > 1:
        parts.append(f"\n**ATTEMPT**: {attempt}（前面已尝试 {attempt-1} 次仍失败，请换思路）\n")

    return "".join(parts)


def run_with_autofix(
    verifier: Path,
    cfg: config.Config,
    *,
    max_attempts: Optional[int] = None,
    llm_cfg: Optional[llm.LLMConfig] = None,
) -> bool:
    """跑 verifier；失败 → LLM 修 → 重跑，最多 max_attempts 次。

    Args:
        verifier: verifier 脚本路径
        cfg: guardx Config（提供 work_dir / state_dir / autofix / autofix_max）
        max_attempts: 覆盖 cfg.autofix_max
        llm_cfg: 覆盖默认 LLMConfig
    """
    if run(verifier, cfg.work_dir, cfg.state_dir):
        return True

    if not cfg.autofix:
        return False

    # autofix 都是局部小修（如改 .npmrc 引号、给 exec 加 2>&1），
    # 默认走 fast profile（sonnet-4-6），避免烧 opus-4-7 的深度思考成本
    if llm_cfg is None:
        llm_cfg = llm.LLMConfig.for_profile("fast")

    max_attempts = max_attempts if max_attempts is not None else cfg.autofix_max
    name = verifier.stem
    out = cfg.state_dir / f"verify-{name}.log"

    base_prompt = config.home_dir() / "prompts" / "50_fix_verify_failure.md"
    if not base_prompt.is_file():
        log.warn(f"[autofix] 缺 {base_prompt}，跳过 autofix")
        return False

    stack_json = cfg.state_dir / "stack.json"
    # 连续 N 次 LLM 跑完没产生任何 git diff（既没 CANNOT_FIX 也没改文件） →
    # 视为已陷入死循环，提前 abort 省 token。阈值 2：偶发一次空跑（如 LLM
    # 工具调用失败但 wrapper 报 ok）不算，连续 2 次空跑才退出。
    NO_DIFF_ABORT_THRESHOLD = 2
    no_diff_streak = 0

    for attempt in range(1, max_attempts + 1):
        log.warn(f"[autofix] verifier={name} 第 {attempt}/{max_attempts} 次 LLM 修复...")

        fix_prompt = cfg.state_dir / f"_autofix-verify-{name}-{attempt}.md"
        fix_prompt.write_text(
            _build_autofix_prompt(
                base_prompt,
                name=name,
                verifier_path=verifier,
                verify_log_path=out,
                stack_json_path=stack_json if stack_json.is_file() else None,
                attempt=attempt,
            )
        )

        r = llm.call(fix_prompt, cfg.work_dir, cfg.state_dir, cfg=llm_cfg)
        if not r.ok:
            log.warn(f"[autofix] LLM 调用失败（第 {attempt} 次）")
            continue

        # 检测 LLM 是否输出 CANNOT_FIX
        if r.log_path and r.log_path.is_file():
            try:
                if _CANNOT_FIX_RE.search(r.log_path.read_text()):
                    log.warn("[autofix] LLM 显式声明无法修复")
                    return False
            except OSError:
                pass

        # 留 commit 方便回溯；commit_step 返回 False 表示本次 LLM 没改任何文件
        committed = git.commit_step(cfg.work_dir, f"autofix: {name} (attempt {attempt})")
        if not committed:
            no_diff_streak += 1
            log.warn(
                f"[autofix] {name} 第 {attempt} 次 LLM 跑完未产生任何 git diff "
                f"（连续 {no_diff_streak}/{NO_DIFF_ABORT_THRESHOLD}）"
            )
            if no_diff_streak >= NO_DIFF_ABORT_THRESHOLD:
                log.fail(
                    f"[autofix] {name} 连续 {NO_DIFF_ABORT_THRESHOLD} 次 LLM 无改动，"
                    f"提前 abort 省 token（剩余 {max_attempts - attempt} 次未跑）"
                )
                return False
            # 没改文件就没必要重跑 verifier；直接进入下一轮 LLM
            continue
        no_diff_streak = 0

        if run(verifier, cfg.work_dir, cfg.state_dir):
            log.ok(f"[autofix] {name} 修复成功（第 {attempt} 次）")
            return True

        log.fail(f"[autofix] {name} 第 {attempt} 次修复后仍失败")

    log.fail(f"[autofix] {name} 经 {max_attempts} 次 LLM 修复仍失败，放弃")
    return False


def _build_cmd_autofix_prompt(
    base_prompt: Path,
    *,
    task_name: str,
    cwd_hint: str,
    cmd: Sequence[str],
    log_path: Path,
    work_dir: Path,
    attempt: int,
) -> str:
    """拼 build/cmd autofix 用的 prompt 文本。"""
    parts: list[str] = [base_prompt.read_text()]
    parts.append("\n\n---\n## 失败信息\n")
    parts.append(f"\n**TASK_NAME**: `{task_name}`\n")
    parts.append(f"\n**BUILD_DIR**: `{cwd_hint}`\n")
    parts.append("\n**FAILED_COMMAND**:\n\n```\n" + " ".join(cmd) + "\n```\n")

    try:
        log_text = log_path.read_text()
        lines = log_text.splitlines()
        tail = "\n".join(lines[-200:])
    except OSError:
        log_text = ""
        tail = "(build log unreadable)"

    # 与 _build_autofix_prompt 一致：若 build log 含 [HINT] / [FAIL]，置顶给 LLM
    key_lines = _extract_key_lines(log_text)
    if key_lines:
        parts.append(
            "\n**KEY_HINTS** (从 build log 抽出的关键失败 / 修复建议)：\n\n```\n"
            + "\n".join(key_lines)
            + "\n```\n"
        )

    parts.append(f"\n**BUILD_LOG** (最后 200 行):\n\n```\n{tail}\n```\n")

    pkg_json = work_dir / cwd_hint / "package.json"
    if pkg_json.is_file():
        parts.append(f"\n**PACKAGE_JSON** (`{cwd_hint}/package.json`):\n\n```json\n{pkg_json.read_text()}```\n")

    req_txt = work_dir / cwd_hint / "requirements.txt"
    if req_txt.is_file():
        parts.append(f"\n**REQUIREMENTS** (`{cwd_hint}/requirements.txt`):\n\n```\n{req_txt.read_text()}```\n")

    parts.append(f"\n**ATTEMPT**: {attempt}\n")
    return "".join(parts)


def run_cmd_with_autofix(
    task_name: str,
    prompt_relative: str,
    cwd_hint: str,
    cmd: Sequence[str],
    cfg: config.Config,
    *,
    max_attempts: Optional[int] = None,
    llm_cfg: Optional[llm.LLMConfig] = None,
) -> bool:
    """跑 cmd（list），失败时调 LLM 修后重跑。给 stage 40 build 用。

    Args:
        task_name: 子任务名（用于日志和 commit message）
        prompt_relative: prompts 目录下的相对路径（如 "40_fix_build_error.md"）
        cwd_hint: 业务目录提示（喂给 LLM 看的）
        cmd: 命令 list（直接 subprocess，无 shell）
    """
    out = cfg.state_dir / f"autofix-{task_name}.log"

    def _run_once() -> int:
        return process.run(
            list(cmd),
            cwd=cfg.work_dir,
            log_path=out,
            heartbeat_sec=int(cfg.export_env().get("GUARD_LLM_HEARTBEAT", "30") or "30"),
            timeout=None,  # 让外层 stage 决定，build 可能很慢
            label=task_name,
        ).returncode

    if _run_once() == 0:
        return True

    if not cfg.autofix:
        log.fail(f"[{task_name}] 失败且 autofix=off，不自动修复")
        return False

    # build 错误修复（npm install / next build / pip install 失败等）也走 fast profile，
    # 这类错误通常是依赖缺失 / lock 文件冲突，定位明确，无需 opus 级推理
    if llm_cfg is None:
        llm_cfg = llm.LLMConfig.for_profile("fast")

    max_attempts = max_attempts if max_attempts is not None else cfg.autofix_max
    base_prompt = config.home_dir() / "prompts" / prompt_relative
    if not base_prompt.is_file():
        log.warn(f"[autofix] 缺 {base_prompt}，跳过 autofix")
        return False

    # 连续 N 次 LLM 无 diff 提前 abort（同 run_with_autofix 策略）
    NO_DIFF_ABORT_THRESHOLD = 2
    no_diff_streak = 0

    for attempt in range(1, max_attempts + 1):
        log.warn(f"[autofix] task={task_name} 第 {attempt}/{max_attempts} 次 LLM 修复...")

        fix_prompt = cfg.state_dir / f"_autofix-{task_name}-{attempt}.md"
        fix_prompt.write_text(
            _build_cmd_autofix_prompt(
                base_prompt,
                task_name=task_name,
                cwd_hint=cwd_hint,
                cmd=cmd,
                log_path=out,
                work_dir=cfg.work_dir,
                attempt=attempt,
            )
        )

        r = llm.call(fix_prompt, cfg.work_dir, cfg.state_dir, cfg=llm_cfg)
        if not r.ok:
            log.warn(f"[autofix] LLM 调用失败（第 {attempt} 次）")
            continue

        if r.log_path and r.log_path.is_file():
            try:
                if _CANNOT_FIX_RE.search(r.log_path.read_text()):
                    log.warn("[autofix] LLM 声明无法修复")
                    return False
            except OSError:
                pass

        committed = git.commit_step(cfg.work_dir, f"autofix: {task_name} (attempt {attempt})")
        if not committed:
            no_diff_streak += 1
            log.warn(
                f"[autofix] {task_name} 第 {attempt} 次 LLM 跑完未产生任何 git diff "
                f"（连续 {no_diff_streak}/{NO_DIFF_ABORT_THRESHOLD}）"
            )
            if no_diff_streak >= NO_DIFF_ABORT_THRESHOLD:
                log.fail(
                    f"[autofix] {task_name} 连续 {NO_DIFF_ABORT_THRESHOLD} 次 LLM 无改动，"
                    f"提前 abort 省 token（剩余 {max_attempts - attempt} 次未跑）"
                )
                return False
            continue
        no_diff_streak = 0

        if _run_once() == 0:
            log.ok(f"[autofix] {task_name} 修复成功（第 {attempt} 次）")
            return True
        log.fail(f"[autofix] {task_name} 第 {attempt} 次修复后仍失败")

    log.fail(f"[autofix] {task_name} 经 {max_attempts} 次 LLM 修复仍失败，放弃")
    return False
