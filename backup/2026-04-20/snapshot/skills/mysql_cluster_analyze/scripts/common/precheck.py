#!/usr/bin/env python3
"""
precheck.py — Layer 2 前置依赖检查

检查 Token 是否已配置（优先 DMS_AI_TOKEN，兜底 DMS_CLAW_TOKEN），
并验证 DMS 服务可达。

用法：
  python3 precheck.py          # 独立运行，AI 在 Layer 2 开始前调用
"""

import os
import sys
import urllib.request
from pathlib import Path

DMS_HEALTH_URL = "https://dms.devops.xiaohongshu.com/dms-api/v1/base/health-check"
AI_TOKEN_KEY = "DMS_AI_TOKEN"
CLAW_TOKEN_KEY = "DMS_CLAW_TOKEN"


def _load_from_env_file(key: str) -> str:
    """从 workspace .env 文件加载指定 key。"""
    env_file = Path(__file__).parents[3] / '.env'
    if not env_file.exists():
        return ''
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith(f'{key}=') and not line.startswith('#'):
            return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


def check_dms_token() -> bool:
    """
    检查 Token 是否已配置：优先 DMS_AI_TOKEN，兜底 DMS_CLAW_TOKEN。
    两者至少有一个才可继续执行。
    """
    ai_token = os.environ.get(AI_TOKEN_KEY, '').strip() or _load_from_env_file(AI_TOKEN_KEY)
    claw_token = os.environ.get(CLAW_TOKEN_KEY, '').strip() or _load_from_env_file(CLAW_TOKEN_KEY)

    if ai_token:
        print(f"[precheck] ✅ {AI_TOKEN_KEY} 已配置（长度={len(ai_token)}）")
        if claw_token:
            print(f"[precheck] ✅ {CLAW_TOKEN_KEY} 已配置（兜底，长度={len(claw_token)}）")
        else:
            print(f"[precheck] ⚠️  {CLAW_TOKEN_KEY} 未配置（v1 接口异常时无法兜底）", file=sys.stderr)
        return True

    if claw_token:
        print(f"[precheck] ⚠️  {AI_TOKEN_KEY} 未配置，将使用 {CLAW_TOKEN_KEY} 兜底（长度={len(claw_token)}）", file=sys.stderr)
        print(f"[precheck] ✅ {CLAW_TOKEN_KEY} 已配置（长度={len(claw_token)}）")
        return True

    print(
        f"[precheck] ❌ 未找到 {AI_TOKEN_KEY} 或 {CLAW_TOKEN_KEY}\n"
        f"  请在环境变量或 workspace/.env 中至少配置一个：\n"
        f"  {AI_TOKEN_KEY}=<your-dms-ai-token>       # 推荐，走 ai-api/v1\n"
        f"  {CLAW_TOKEN_KEY}=<your-dms-claw-token>   # 备用，走 open-claw",
        file=sys.stderr,
    )
    return False


def check_dms_reachable() -> bool:
    """
    检查 DMS 服务是否可达（访问 health-check 接口）。
    返回 True 表示可达，False 表示不可达（仅警告，不阻断流程）。
    """
    try:
        req = urllib.request.Request(DMS_HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status < 500:
                print(f"[precheck] ✅ DMS 服务可达（status={resp.status}）")
                return True
    except Exception as e:
        print(f"[precheck] ⚠️  DMS 服务连通性检查失败：{e}（将在上传时重试）", file=sys.stderr)
    return True  # 网络不可达只警告，不阻断（沙箱环境可能受限）


if __name__ == "__main__":
    ok = check_dms_token() and check_dms_reachable()
    sys.exit(0 if ok else 1)
