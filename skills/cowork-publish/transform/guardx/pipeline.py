"""pipeline 编排：8 个 stage 全部 Python 实现，**进程内调用**。

历史上有 bash stages/*.sh 实现，已在阶段 6/7 全部翻 Python 并删除。
保留 GUARDX_FORCE_BASH=1 兼容开关——会在 stage 入口给友好错并退出。

阶段 stage 命名：00_prepare / 10_detect_stack / ... / 70_report
"""

from __future__ import annotations

import time
from typing import Iterable, Optional

from . import checklist, config, log, stages_py

STAGES: tuple[str, ...] = (
    "00_prepare",
    "10_detect_stack",
    "20_rewrite_loop",
    "30_render_scripts",
    "40_build",
    "50_smoke_test",
    "60_package",
    "70_report",
)


def _stage_num(stage: str) -> int:
    """'40_build' → 40。"""
    return int(stage.split("_", 1)[0])


# 允许通过环境变量强制走 bash 实现（调试 / 灰度），不改代码即可回滚
def _force_bash() -> bool:
    import os
    return os.environ.get("GUARDX_FORCE_BASH", "0") == "1"


def _run_python_stage(stage: str, cfg: config.Config) -> int:
    """跑 Python 版 stage；返回 returncode（异常→1）。"""
    runner = stages_py.get_runner(stage)
    if runner is None:
        return -1  # sentinel: 没有 Python 实现
    log.log(f"  [python] stages_py.{stages_py.PYTHON_STAGES[stage]}.run()")
    try:
        return int(runner(cfg) or 0)
    except SystemExit as e:
        # log.die / sys.exit 抛 SystemExit；视作 fail
        return e.code if isinstance(e.code, int) and e.code != 0 else 1
    except KeyboardInterrupt:
        raise
    except Exception as e:  # noqa: BLE001
        log.fail(f"Python stage {stage} 抛出异常: {type(e).__name__}: {e}")
        import traceback
        for line in traceback.format_exc().splitlines():
            log.log(f"    {line}")
        return 1


def _run_bash_stage(stage: str, cfg: config.Config) -> int:
    """已无 bash 实现；保留函数仅供 GUARDX_FORCE_BASH=1 路径报友好错。"""
    log.fail(
        f"stage {stage} 已 100% Python 化（阶段 6/7），"
        f"GUARDX_FORCE_BASH=1 已无效——请直接 unset 该环境变量"
    )
    return 1


def run(
    cfg: config.Config,
    *,
    only_stages: Optional[Iterable[str]] = None,
) -> int:
    """串行跑 stage 流水线。

    Args:
        cfg: 已 _setup_runtime 过的 Config（log/checklist 已 init）
        only_stages: 仅跑这些 stage（例如 detect 命令只要 00/10）；None=全部

    Returns:
        0 表示全部成功，非 0 表示某 stage 失败。
    """
    stages = tuple(only_stages) if only_stages else STAGES
    force_bash = _force_bash()
    if force_bash:
        log.warn("GUARDX_FORCE_BASH=1，所有 stage 强制走 bash 实现（忽略 stages_py/）")

    # `--from-stage NN` 隐含语义：重置 NN 及之后所有 stage / substep 的 checklist。
    # 否则用户场景"跑完一次 transform 后用 --from-stage 60 -y 重打包"会直接命中
    # checklist 缓存秒退（stage 60 状态还是 ok → is_done True → continue），不产
    # 出新 zip；同理 --from-stage 50 也不会重跑 verifier，导致 verify_frontend_built
    # 等校验失效。reset 后下面的 is_done 检查就会按预期返回 False，stage 真正重跑。
    if cfg.from_stage > 0:
        cleared = checklist.reset_from_stage(cfg.from_stage)
        if cleared:
            log.log(
                f"--from-stage {cfg.from_stage} 隐含重置 checklist "
                f"({len(cleared)} 项): {', '.join(cleared)}"
            )

    for stage in stages:
        # --from-stage 跳过
        if _stage_num(stage) < cfg.from_stage:
            log.log(f"[skip] stage {stage}（< --from-stage {cfg.from_stage}）")
            continue

        # checklist 缓存命中
        if checklist.is_done(stage):
            log.ok(f"stage {stage} 已完成（checklist 缓存命中），跳过")
            continue

        log.log(f"{log.C_BLD}▶ stage: {stage}{log.C_RST}")
        checklist.set(stage, "running")

        t0 = time.monotonic()
        # 优先 Python 实现，缺则 fallback bash
        rc = -1 if force_bash else _run_python_stage(stage, cfg)
        if rc == -1:
            rc = _run_bash_stage(stage, cfg)
        cost = int(time.monotonic() - t0)

        if rc == 0:
            checklist.set(stage, "ok", f"{cost}s")
            log.ok(f"stage {stage} 完成 (耗时 {cost}s)")
        else:
            checklist.set(stage, "fail", f"rc={rc}")
            log.fail(f"stage {stage} 失败 (rc={rc})")
            return rc

    return 0
