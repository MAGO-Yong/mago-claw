"""进度持久化 + 续跑。

**严格兼容 bash 版** (lib/common.sh)：同一份 checklist.tsv 可被两边交替读写。

文件格式：
    路径: $STATE_DIR/checklist.tsv
    每行: task_id<TAB>status<TAB>timestamp<TAB>note
    status 取值: pending / running / ok / fail / skip

"覆盖" 语义：set(task_id, ...) 时**不重写整张表**，而是
  1) 用 grep -v 模式删除该 task_id 的所有旧行
  2) append 一行新状态
这样即便文件被并发追加（bash 子进程也在写），也只丢"同 task 的旧条目"。

读取时同样以"最后一行"为准（`get` → tail -1），与 bash 版语义对齐。
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Literal, Optional

from . import log

Status = Literal["pending", "running", "ok", "fail", "skip"]

# 进程级缓存：避免每次 set 都需要外部传 STATE_DIR
_FILE: Optional[Path] = None


def init(state_dir: Path) -> None:
    """阶段开始前调一次。state_dir 即 bash 版的 STATE_DIR。"""
    global _FILE
    state_dir.mkdir(parents=True, exist_ok=True)
    _FILE = state_dir / "checklist.tsv"


def _file() -> Path:
    if _FILE is None:
        raise RuntimeError("checklist.init(state_dir) 还未调用")
    return _FILE


def reset() -> None:
    """清空 checklist。"""
    f = _file()
    f.write_text("")
    log.log(f"checklist 初始化: {f}")


def set(task_id: str, status: Status, note: str = "") -> None:  # noqa: A001
    """覆盖某 task 的状态。bash-compatible：grep -v 删旧 + append 新。"""
    f = _file()
    if not f.exists():
        f.touch()

    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    new_line = f"{task_id}\t{status}\t{ts}\t{note}\n"

    # 删旧条目（同 task_id）+ append 新行
    if f.stat().st_size > 0:
        try:
            kept = [
                line
                for line in f.read_text().splitlines(keepends=True)
                if not line.startswith(f"{task_id}\t")
            ]
            tmp = f.with_suffix(f.suffix + ".tmp")
            tmp.write_text("".join(kept))
            os.replace(tmp, f)
        except OSError:
            pass  # 写失败不应破坏主流程

    try:
        with f.open("a") as fp:
            fp.write(new_line)
    except OSError:
        pass


def get(task_id: str) -> Status:
    """返回该 task 的当前状态；不存在记为 pending。"""
    f = _file()
    if not f.exists() or f.stat().st_size == 0:
        return "pending"
    last: Optional[str] = None
    try:
        for line in f.read_text().splitlines():
            if line.startswith(f"{task_id}\t"):
                last = line
    except OSError:
        return "pending"
    if last is None:
        return "pending"
    parts = last.split("\t")
    if len(parts) < 2:
        return "pending"
    s = parts[1].strip()
    if s in ("pending", "running", "ok", "fail", "skip"):
        return s  # type: ignore[return-value]
    return "pending"


def is_done(task_id: str) -> bool:
    """ok 或 skip 都算"无需重跑"。"""
    return get(task_id) in ("ok", "skip")


def _task_stage_num(task_id: str) -> Optional[int]:
    """从 task_id 抽取 stage 编号；既兼容 stage 主行 (`60_package`) 又兼容
    substep 行 (`20:remove_external_infra`)；不可解析的返回 None。"""
    head = task_id.split(":", 1)[0].split("_", 1)[0]
    try:
        return int(head)
    except ValueError:
        return None


def reset_from_stage(stage_num: int) -> list[str]:
    """重置所有 stage 编号 >= stage_num 的 task 状态为 pending。

    覆盖两类 task：
      - stage 主行：`60_package` / `50_smoke_test` / ...（pipeline.run 用）
      - substep 行：`20:remove_external_infra` / `20:fix_paths` / ...
        （stage_20_rewrite_loop 内部 with_substep 用）

    设计动机：
      - `--from-stage NN` 旧语义只控 pipeline 起始迭代点，**不动 checklist**；
        遇到 NN 已 ok → step()/run() is_done 命中缓存直接 yield False / continue，
        导致用户期望"重打包"却命令秒退、没产出新 zip / verifier 没重跑（前端
        构建产物缺失等回归 bug 漏检）。
      - 让 `--from-stage NN` 隐含 reset 后所有 NN 起 stage 真正会被重新执行。

    返回被重置的 task_id 列表（按 checklist 内出现顺序），便于上游打日志。
    pending 状态不动（也不计入返回），避免噪音。
    """
    cleared: list[str] = []
    note = f"--from-stage {stage_num} 重置"
    # 先把全部 rows 物化，再逐个写 set；set 会原子重写文件，迭代器读旧文件相对安全
    for tid, status, _ts, _note in list(_iter_rows()):
        if status == "pending":
            continue
        n = _task_stage_num(tid)
        if n is None or n < stage_num:
            continue
        set(tid, "pending", note)
        cleared.append(tid)
    return cleared


def skip(task_id: str, reason: str = "not applicable") -> None:
    set(task_id, "skip", reason)
    log.ok(f"subtask {task_id} 跳过：{reason}")


def _iter_rows() -> Iterable[tuple[str, str, str, str]]:
    f = _file()
    if not f.exists() or f.stat().st_size == 0:
        return
    for line in f.read_text().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        # 容忍少列（bash 版有时 note 为空）
        while len(parts) < 4:
            parts.append("")
        yield parts[0], parts[1], parts[2], parts[3]


def show() -> None:
    """彩色打印整张表到 stderr。"""
    rows = list(_iter_rows())
    if not rows:
        log.log("checklist 为空")
        return

    sys.stderr.write(
        f"\n  {'TASK':<50} {'STATUS':<10} {'TIMESTAMP':<20} NOTE\n"
    )
    sys.stderr.write(
        f"  {'----':<50} {'------':<10} {'---------':<20} ----\n"
    )
    color_map = {
        "ok": log.C_GRN,
        "fail": log.C_RED,
        "running": log.C_YEL,
        "skip": log.C_CYN,
    }
    for task, status, ts, note in rows:
        c = color_map.get(status, "")
        sys.stderr.write(
            f"  {task:<50} {c}{status:<10}{log.C_RST} {ts:<20} {note}\n"
        )
    sys.stderr.write("\n")
    sys.stderr.flush()


def to_md() -> str:
    """生成给 report.md 用的 markdown 表。"""
    lines = [
        "| Task | Status | Timestamp | Note |",
        "|---|---|---|---|",
    ]
    rows = list(_iter_rows())
    if not rows:
        lines.append("| _(空)_ | | | |")
        return "\n".join(lines) + "\n"

    icon_map = {
        "ok": "✅ ok",
        "fail": "❌ fail",
        "running": "🟡 running",
        "skip": "⏭ skip",
    }
    for task, status, ts, note in rows:
        icon = icon_map.get(status, f"⏳ {status}")
        lines.append(f"| `{task}` | {icon} | {ts} | {note} |")
    return "\n".join(lines) + "\n"


# ---- resume ----
ResumeMode = Literal["ask", "resume", "reset"]


def resume_or_reset(mode: ResumeMode = "ask") -> None:
    """启动时调；按 mode 决定如何处理已有 checklist。

    与 bash 版语义对齐：
      - 文件不存在 / 空 → 初始化即可
      - mode=resume → 直接续跑
      - mode=reset  → 清空重跑
      - mode=ask    → 非 tty 自动 continue；tty 弹交互（60s 超时按 continue）
    """
    f = _file()
    if not f.exists() or f.stat().st_size == 0:
        reset()
        return

    log.log(f"{log.C_BLD}发现上次的 checklist 进度：{log.C_RST}")
    show()

    if mode == "resume":
        log.log("RESUME_MODE=resume，跳过已完成步骤")
        return
    if mode == "reset":
        log.log("RESUME_MODE=reset，清空 checklist 重新开始")
        reset()
        return

    # ask
    if not sys.stdin.isatty():
        log.log("[non-interactive] stdin 非 tty，自动 continue（如需重置请显式传 --reset）")
        return

    sys.stderr.write(
        f"{log.C_BLD}发现上次进度，请选择: "
        f"{log.C_GRN}[c]{log.C_RST}ontinue / "
        f"{log.C_YEL}[r]{log.C_RST}eset / "
        f"{log.C_RED}[q]{log.C_RST}uit ? {log.C_RST}"
    )
    sys.stderr.flush()

    # 60s 超时，超时按 continue
    choice = _read_with_timeout(60)
    choice = (choice or "").strip().lower()
    if choice in ("", "c", "continue"):
        log.log("[continue] 续跑，跳过已完成步骤")
        return
    if choice in ("r", "reset"):
        log.log("[reset] 用户选择重置 checklist")
        reset()
        return
    log.die(f"用户取消（输入: {choice}）。CI 场景请用 --resume 或 --reset。")


def _read_with_timeout(timeout_sec: float) -> Optional[str]:
    """用 select 实现 stdin readline 带超时；不依赖第三方。"""
    import select

    try:
        ready, _, _ = select.select([sys.stdin], [], [], timeout_sec)
    except OSError:
        return None
    if sys.stdin in ready:
        return sys.stdin.readline()
    return None


# ---- with_step / with_substep ----
# 与 bash 版语义一致，但用 Python 异常+返回码取代 trap+wait+SIGINT 技巧。
# Python 版 SIGINT 由 process.setup_signal_handlers 在主入口统一处理，这里
# 不需要 _run_intr 那种 "& wait $!" 兜底。

import time as _time
from contextlib import contextmanager


@contextmanager
def step(name: str):
    """with_step 的 Python 版，用 contextmanager 写法。

    用法:
        with checklist.step("00_prepare") as do:
            if do:
                run_stage_00()
        # do == False 表示 "已完成，被跳过，with body 仍会执行但通常包 if"
        # 失败时（with body 抛异常）会标 fail 并 raise。
    """
    if is_done(name):
        log.ok(f"stage {name} 已完成（checklist 缓存命中），跳过")
        yield False
        return

    log.log(f"{log.C_BLD}▶ stage: {name}{log.C_RST}")
    set(name, "running")
    t0 = _time.monotonic()
    try:
        yield True
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 1
        set(name, "fail", f"rc={rc}")
        raise
    except KeyboardInterrupt:
        set(name, "fail", "interrupted")
        raise
    except Exception as e:  # noqa: BLE001
        set(name, "fail", f"{type(e).__name__}: {e}")
        raise
    cost = int(_time.monotonic() - t0)
    set(name, "ok", f"{cost}s")
    log.ok(f"stage {name} 完成 (耗时 {cost}s)")


@contextmanager
def substep(task_id: str):
    """with_substep 版本：失败不抛 die，只标 fail 后继续 raise 让外层决定。"""
    if is_done(task_id):
        log.ok(f"subtask {task_id} 已完成（checklist 缓存命中），跳过")
        yield False
        return

    log.log(f"  ▶ subtask: {task_id}")
    set(task_id, "running")
    t0 = _time.monotonic()
    try:
        yield True
    except KeyboardInterrupt:
        set(task_id, "fail", "interrupted")
        raise
    except Exception as e:  # noqa: BLE001
        set(task_id, "fail", f"{type(e).__name__}: {e}")
        log.fail(f"subtask {task_id} 失败：{e}")
        raise
    cost = int(_time.monotonic() - t0)
    set(task_id, "ok", f"{cost}s")
    log.ok(f"subtask {task_id} 完成 (耗时 {cost}s)")
