"""
token_counter.py — 从当前 OpenClaw session JSONL 统计 token 消耗

用法：
    from token_counter import get_tokens_since
    tokens = get_tokens_since(start_ts)  # start_ts: float unix timestamp（秒）

字段来源：
    ~/.openclaw/agents/main/sessions/<latest>.jsonl
    每条 assistant message 的 message.usage.totalTokens
"""

import json
import os
import glob
from typing import Optional


SESSION_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")


def get_current_session_jsonl() -> Optional[str]:
    """返回最近修改的 session JSONL 文件路径，找不到返回 None。"""
    pattern = os.path.join(SESSION_DIR, "*.jsonl")
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def get_tokens_since(start_ts: float) -> int:
    """
    统计 start_ts（unix timestamp，秒）之后所有 assistant message 的 totalTokens 之和。

    Args:
        start_ts: 诊断开始时间（time.time() 返回值）

    Returns:
        int，token 总消耗量；文件不存在或解析失败返回 0
    """
    session_file = get_current_session_jsonl()
    if not session_file:
        print("[token_counter] ⚠️ 未找到 session JSONL 文件，token_count 记为 0")
        return 0

    total = 0
    try:
        with open(session_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = r.get("message", {})
                if msg.get("role") != "assistant":
                    continue
                # message.timestamp 单位是毫秒
                msg_ts = msg.get("timestamp", 0) / 1000.0
                if msg_ts < start_ts:
                    continue
                usage = msg.get("usage", {})
                total += usage.get("totalTokens", 0)
    except Exception as e:
        print(f"[token_counter] ⚠️ 读取 session JSONL 失败：{e}，token_count 记为 0")
        return 0

    return total


if __name__ == "__main__":
    # 单测：统计全 session token
    import time
    tokens = get_tokens_since(0)
    print(f"[token_counter] 当前 session 全量 token: {tokens:,}")
    tokens_recent = get_tokens_since(time.time() - 60)
    print(f"[token_counter] 最近 60s token: {tokens_recent:,}")
