"""统一日志：stderr 输出（带颜色，仅当 stderr 是 tty）+ 同步落盘到 LOG_FILE。

设计动机：
    - bash 版日志在 lib/common.sh 用 ANSI 转义自己渲染颜色，stderr/file 双写。
    - Python 版保持完全一致的视觉风格 + 文件格式，方便 bash 与 python 混用阶段
      产出同一份 transform.log。

后台模式（GUARDX_BG_MODE=1）：
    - stdout/stderr 已被 bin/guardx --bg 重定向到 transform.log
    - 此时 _BG_MODE=True，日志不再额外写 _LOG_FILE（避免双写同一文件）
    - stderr.isatty() 为 False，无 ANSI 颜色（落盘清洁）
    - 用户通过 `guardx logs <source>` 或 `tail -f STATE_DIR/transform.log` 查看
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---- 后台模式检测 ----
_BG_MODE = os.environ.get("GUARDX_BG_MODE", "0") == "1"

# ---- ANSI ----
_TTY = sys.stderr.isatty()
C_RED = "\033[31m" if _TTY else ""
C_GRN = "\033[32m" if _TTY else ""
C_YEL = "\033[33m" if _TTY else ""
C_CYN = "\033[36m" if _TTY else ""
C_BLD = "\033[1m" if _TTY else ""
C_RST = "\033[0m" if _TTY else ""

_LOG_FILE: Optional[Path] = None


def init(log_file: Path) -> None:
    """在 stage 启动时调一次；后续 log()/ok()/warn()/fail() 都会双写。

    后台模式下 stdout/stderr 已被重定向到 transform.log，
    此时 _LOG_FILE 仍设置（用于其他模块获取路径），但 _write 不再额外追加写入
    （避免 nohup 重定向和 open('a') 竞争同一文件）。
    """
    global _LOG_FILE
    _LOG_FILE = log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    if not _BG_MODE:
        # 前台模式：清空旧内容（日志从头开始）
        log_file.write_text("")


def _write(prefix_color: str, prefix: str, msg: str, with_ts: bool = True) -> None:
    if with_ts:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sys.stderr.write(f"{C_CYN}[{ts}]{C_RST} {prefix_color}{prefix}{C_RST} {msg}\n")
        line = f"[{ts}] {prefix} {msg}\n"
    else:
        sys.stderr.write(f"{prefix_color}{prefix}{C_RST} {msg}\n")
        line = f"{prefix} {msg}\n"
    sys.stderr.flush()
    # 后台模式下 stderr 已重定向到日志文件，无需额外写入
    if _LOG_FILE is not None and not _BG_MODE:
        try:
            with _LOG_FILE.open("a") as f:
                f.write(line)
        except OSError:
            pass  # 日志写失败不应破坏主流程


def log(msg: str) -> None:
    _write("", "", msg)


def ok(msg: str) -> None:
    _write(C_GRN, "[OK]", msg, with_ts=False)


def warn(msg: str) -> None:
    _write(C_YEL, "[WARN]", msg, with_ts=False)


def fail(msg: str) -> None:
    _write(C_RED, "[FAIL]", msg, with_ts=False)


def die(msg: str, code: int = 1) -> None:
    fail(msg)
    sys.exit(code)


def section(title: str) -> None:
    """阶段开头的醒目分割。"""
    sys.stderr.write(f"\n{C_BLD}{C_CYN}===  {title}  ==={C_RST}\n")
    sys.stderr.flush()
    if _LOG_FILE is not None:
        try:
            with _LOG_FILE.open("a") as f:
                f.write(f"\n=== {title} ===\n")
        except OSError:
            pass
