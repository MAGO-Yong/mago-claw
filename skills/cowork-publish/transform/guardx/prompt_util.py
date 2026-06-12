"""交互式弹问公共工具。

历史上 ``_read_choice_with_timeout`` / ``_is_non_interactive_env`` 散落在
``stages_py/stage_00_prepare.py`` 里只服务于"工作副本已存在"那一处弹问；
当 ``git.py`` 也需要"无 git 时弹问是否自动安装"时，把它们抽出来共用，
避免在 git.py 里再写一份语义略有偏差的"非交互判定"。

非交互判定与 SKILL.md / install.sh 的 ``default_env.sh`` 对齐：
  - ``GUARD_NONINTERACTIVE=1``      → 非交互
  - ``GUARD_RUN_MODE=non-interactive`` → 非交互
  - stdin / stderr 任一非 tty       → 非交互
"""

from __future__ import annotations

import os
import sys


def is_non_interactive() -> bool:
    """判定当前是否处于"不该弹问"的环境。

    返回 True 时，调用方应当走"安全默认值"分支，不要 ``input()``，
    否则在 CI / 后台进程 / agent runtime 等场景会永久阻塞。
    """
    if os.environ.get("GUARD_NONINTERACTIVE") == "1":
        return True
    if os.environ.get("GUARD_RUN_MODE") == "non-interactive":
        return True
    # 任一端不是 tty 都视为非交互（pipe 进来的 stdin 也算）
    try:
        if not sys.stdin.isatty() or not sys.stderr.isatty():
            return True
    except (AttributeError, ValueError):
        # 极端环境（如 pytest capfd / 嵌入式 Python）下 isatty 可能抛
        return True
    return False


def read_choice_with_timeout(prompt: str, timeout_s: int, default: str) -> str:
    """tty 上写 ``prompt`` 到 stderr 并等 ``timeout_s`` 秒输入；超时返回 ``default``。

    与 ``stage_00_prepare._read_choice_with_timeout`` 行为完全一致，从那里抽出来
    复用。``select`` 不可用的罕见环境（如 Windows + 无 pywin32）会退化为阻塞读。
    """
    import select
    sys.stderr.write(prompt)
    sys.stderr.flush()
    try:
        rlist, _, _ = select.select([sys.stdin], [], [], timeout_s)
        if rlist:
            line = sys.stdin.readline()
            return (line or "").strip().lower()
        # 超时：补一行换行让终端整洁，提示用户超时已用默认
        sys.stderr.write("\n")
        sys.stderr.flush()
        return default
    except Exception:
        # select 不可用 → 阻塞 read，不带超时
        try:
            return (sys.stdin.readline() or "").strip().lower()
        except Exception:
            return default
