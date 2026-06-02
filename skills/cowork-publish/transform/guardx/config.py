"""运行时配置：源工程 → 工作副本 / 状态目录 路径派生 + 全局开关。

与 bash 版 transform.sh 命名完全对齐：
    SOURCE_PROJECT  → 用户传入的源（绝对化后存 source_abs）
    WORK_BASE       → 源所在目录
    WORK_NAME       → 基名 + "-guard"（去掉 .zip 后缀）
    WORK_DIR        → WORK_BASE / WORK_NAME       （工作副本，会被 LLM 改动）
    STATE_DIR       → WORK_BASE / .guard-transform-<WORK_NAME>  （checklist/log/产物）
"""

from __future__ import annotations

import datetime
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

ResumeMode = Literal["ask", "resume", "reset"]


def _make_zip_timestamp() -> str:
    """生成 zip 文件名后缀时间戳 MMDDhhmm（本地时区）。

    支持 GUARD_ZIP_TIMESTAMP 环境变量覆盖，便于 CI / 测试场景固化文件名做对比。
    格式校验：8 位数字（MMDDhhmm）；不合法时直接走默认，避免污染产物名。
    """
    override = os.environ.get("GUARD_ZIP_TIMESTAMP", "").strip()
    if override and re.fullmatch(r"\d{8}", override):
        return override
    return datetime.datetime.now().strftime("%m%d%H%M")


@dataclass
class Config:
    # 源 / 派生路径
    source_project: Path     # 用户传入的源（绝对路径）
    work_dir: Path            # 工作副本
    state_dir: Path           # 状态目录
    work_name: str            # WORK_DIR / 包名

    # 流程开关
    from_stage: int = 0
    skip_llm: bool = False
    resume_mode: ResumeMode = "ask"

    # 工作副本目录已存在时的处理策略（与 resume_mode 互补：resume 只管 checklist 进度文件）
    # - "ask"    本地交互模式 + tty 时弹问"用现有的 / 删掉重 copy"；其它情形等同 reuse
    # - "reuse"  直接使用副本目录现有内容跑转写（保留你在副本里的手改）
    # - "recopy" 清空副本目录 + 从源工程重新 copy 一份（丢弃所有改动）
    fresh_copy_mode: str = "ask"

    # autofix 开关
    # autofix_max 默认 5：实测大多数 autofix 第 1-3 次就成或就死循环；
    # 超过 5 次的成功率 < 5%，继续重试只是烧 token。需要更激进可通过
    # --autofix-max N / GUARD_AUTOFIX_MAX=N 覆盖。
    autofix: bool = True
    autofix_max: int = 5
    strict: bool = True

    # LLM 后端（透传给 llm.LLMConfig；这里只记录 + 供日志展示）
    llm_backend: str = "claude"

    # zip 产物时间戳（MMDDhhmm）；同一次 transform 调用内三处共用，
    # 保证 cli banner / stage 60 写文件 / stage 70 报告 指向同一个 zip。
    # default_factory 在每次实例化（即每次 transform 命令）时重新取当前时间。
    zip_timestamp: str = field(default_factory=_make_zip_timestamp)

    @classmethod
    def from_args(
        cls,
        source_project: str,
        *,
        from_stage: int = 0,
        skip_llm: bool = False,
        resume_mode: ResumeMode = "ask",
        autofix: bool = True,
        autofix_max: int = 5,
        strict: bool = True,
        fresh_copy_mode: str = "ask",
    ) -> "Config":
        src_path = Path(source_project).expanduser()
        if not src_path.exists():
            raise FileNotFoundError(f"源工程不存在: {source_project}")
        # 绝对化（与 bash 版 SOURCE_ABS 一致）。
        # Path.resolve() 已能正确处理 '.' / './' / '..' / 末尾带 /，
        # name 都是真实目录名（不会得到 '.'）。仍加一层兜底应对 '/'、空字符串等极端边界。
        source_abs = src_path.resolve()
        work_base = source_abs.parent
        base = source_abs.name
        if base.endswith(".zip"):
            base = base[:-4]
        # 防御性兜底：base 为空（如源是文件系统根 '/'）时，回退为通用名
        if not base or base in (".", ".."):
            base = "guard-output"
        work_name = f"{base}-guard"

        return cls(
            source_project=source_abs,
            work_dir=work_base / work_name,
            state_dir=work_base / f".guard-transform-{work_name}",
            work_name=work_name,
            from_stage=from_stage,
            skip_llm=skip_llm,
            resume_mode=resume_mode,
            autofix=autofix,
            autofix_max=autofix_max,
            strict=strict,
            fresh_copy_mode=fresh_copy_mode,
            llm_backend=os.environ.get("GUARD_LLM", "claude"),
        )

    @property
    def zip_path(self) -> Path:
        """交付 zip 路径：<work_base>/<work_name>-<MMDDhhmm>.zip。

        加 MMDDhhmm 后缀的目的：每次跑 transform 都生成新文件，避免覆盖上次产物，
        方便对比 / 回滚 / 提交多个版本到 Guard 平台做 A/B 验证。
        """
        return self.work_dir.parent / f"{self.work_name}-{self.zip_timestamp}.zip"

    def export_env(self) -> dict[str, str]:
        """生成给 bash stage 子进程用的环境变量。

        阶段 2 中 stage 仍是 bash 脚本，必须把这套变量塞回去，否则
        stages/*.sh 跑起来找不到 WORK_DIR / STATE_DIR / SKIP_LLM 等。
        """
        env = os.environ.copy()
        env["GUARD_TRANSFORM_HOME"] = str(home_dir())
        env["SOURCE_PROJECT"] = str(self.source_project)
        env["WORK_DIR"] = str(self.work_dir)
        env["STATE_DIR"] = str(self.state_dir)
        env["SKIP_LLM"] = "1" if self.skip_llm else "0"
        env["RESUME_MODE"] = self.resume_mode
        env["GUARD_FRESH_COPY_MODE"] = self.fresh_copy_mode
        env["GUARD_AUTOFIX"] = "1" if self.autofix else "0"
        env["GUARD_AUTOFIX_MAX"] = str(self.autofix_max)
        env["GUARD_STRICT"] = "1" if self.strict else "0"
        env["LOG_FILE"] = str(self.state_dir / "transform.log")
        # 让任何下游 bash stage（如有）也能拿到本次 zip 时间戳，避免重新生成不一致
        env["GUARD_ZIP_TIMESTAMP"] = self.zip_timestamp
        return env


def home_dir() -> Path:
    """guard-transform 仓库根目录（含 stages/ prompts/ verifiers/ 等）。

    优先用 GUARD_TRANSFORM_HOME 环境变量（bin/guardx shim 已设），
    否则用本文件所在目录的上一级（即 guardx/ 的父）。
    """
    env = os.environ.get("GUARD_TRANSFORM_HOME")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent
