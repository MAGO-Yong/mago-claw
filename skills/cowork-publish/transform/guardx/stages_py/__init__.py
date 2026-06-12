"""Python 实现的 stage（阶段 3+）。

设计：
  - 模块名规则：bash stage `00_prepare` → Python 模块 `stage_00_prepare`
    （Python 模块名不能数字开头）
  - 每个模块导出 `def run(cfg: Config) -> int`，返回 0=成功，非 0=失败
  - pipeline.py 优先调 Python 实现；缺哪个 fallback 到 `bash stages/<name>.sh`
  - 这样可以**逐个 stage 迁移**，不必一次推全
  - 已迁完的 stage（00/10）的 bash 版已经从 stages/ 目录删除

注意：所有 stage 都不应自己 init log / checklist，
那些由 cli._setup_runtime 在主入口完成。
"""

from __future__ import annotations

import importlib
from typing import Callable, Optional

from .. import config as _config

# bash stage name → Python 模块名（去掉 stages_py/ 前缀）
PYTHON_STAGES: dict[str, str] = {
    "00_prepare": "stage_00_prepare",
    "10_detect_stack": "stage_10_detect_stack",
    "20_rewrite_loop": "stage_20_rewrite_loop",
    "30_render_scripts": "stage_30_render_scripts",
    "40_build": "stage_40_build",
    "50_smoke_test": "stage_50_smoke_test",
    "60_package": "stage_60_package",
    "70_report": "stage_70_report",
}

StageRunner = Callable[[_config.Config], int]


def get_runner(stage_name: str) -> Optional[StageRunner]:
    """返回 Python 版 runner，若没有 Python 实现则 None。"""
    mod_name = PYTHON_STAGES.get(stage_name)
    if mod_name is None:
        return None
    # 安全说明：mod_name 来自上面 PYTHON_STAGES 的硬编码白名单（不是用户输入），
    # 故 importlib.import_module 不存在动态加载任意模块的风险；SAST 报警可豁免。
    try:
        mod = importlib.import_module(f".{mod_name}", package=__name__)
    except ImportError:
        return None
    fn = getattr(mod, "run", None)
    if not callable(fn):
        return None
    return fn  # type: ignore[return-value]
