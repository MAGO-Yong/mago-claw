#!/usr/bin/env python3
"""
非交互式 Token 获取工具，供其他 skill 脚本调用。

功能：
  1. 读取本地已保存的 credentials.json
  2. 若 access_token 仍有效 → 直接输出
  3. 若 access_token 过期但 refresh_token 仍有效 → 自动用 refresh_token 换取新 token
  4. 若均无效 → 退出码 1，提示用户重新登录

用法：
  python3 get_token.py [--env sit] [--output token|json]

输出：
  --output token (默认)  : 仅输出 access_token 字符串（适合直接赋值给变量）
  --output json          : 输出完整 credentials JSON（含 access_token / refresh_token / expires_at）

退出码：
  0  成功，token 已输出到 stdout
  1  需要重新登录（token 不存在或无法刷新），错误信息输出到 stderr
"""

import sys
import os
import json
import time
import fcntl
import argparse
from pathlib import Path

# ------------------------------------------------------------------
# 复用 auth.py 中的路径/数据结构工具（避免重复代码）
# ------------------------------------------------------------------

# 将 auth.py 所在目录加入 path，便于 import
_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))

from auth import (
    get_credentials_path,
    save_credentials,
    load_credentials,
    parse_jwt_payload,
    http_post_json,
    SSO_ENDPOINTS,
    CLIENT_ID,
    Credentials,
)


# ============ Token Refresh ============


def refresh_access_token(env: str, refresh_token: str) -> Credentials:
    """
    使用 refresh_token 从 SSO 获取新的 access_token。
    复用 /token 端点，grant_type=refresh_token（RFC 6749 标准）。

    Raises:
        Exception: 刷新失败时抛出，调用方负责捕获并提示重新登录。
    """
    endpoints = SSO_ENDPOINTS[env]
    token_endpoint = endpoints["token"]

    resp = http_post_json(
        token_endpoint,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
        },
    )

    if not resp.get("success", False):
        msg = resp.get("message", "unknown error")
        raise Exception(f"refresh token failed: {msg}")

    data = resp.get("data", {})
    access_token = data.get("access_token")
    new_refresh_token = data.get("refresh_token", refresh_token)  # 部分 SSO 不轮换 refresh_token

    if not access_token:
        raise Exception("refresh token response missing access_token")

    # 解析新 token 的有效期；解析失败说明 SSO 返回了无效 token，直接报错，
    # 不能用 fallback 有效期缓存一个坏 token（会导致下游持续失败 1 小时）
    try:
        payload = parse_jwt_payload(access_token)
        expires_at = payload.exp
    except Exception as e:
        raise Exception(f"refreshed token is invalid (JWT parse failed: {e}); please login again")

    return Credentials(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_at=expires_at,
    )


# ============ Main Logic ============

# 提前 30 秒视为过期，避免边界情况下 token 在使用时恰好失效
_EXPIRY_BUFFER_SECONDS = 30


def get_token(env: str) -> Credentials:
    """
    获取当前有效的 Credentials。

    优先返回本地缓存；过期时使用文件锁（fcntl.flock）保证同一时刻只有一个进程
    执行 refresh，避免并发场景下多次无效刷新或 credentials.json 写入冲突。
    无法续期时以 SystemExit(1) 退出，调用方负责引导用户重新登录。

    Raises:
        SystemExit(1): 需要重新登录
    """
    cred_path = get_credentials_path(env)
    lock_path = cred_path.parent / ".refresh.lock"

    # 先不加锁，快速检查 token 是否仍然有效
    cred = load_credentials(cred_path)
    if cred is None:
        _die(
            f"No credentials found for env '{env}'. "
            f"Please run the xray-auth login script first:\n"
            f"  python3 {_SCRIPT_DIR}/auth.py {env}"
        )

    now = int(time.time())
    if cred.expires_at - _EXPIRY_BUFFER_SECONDS > now:
        return cred

    # token 已过期，加排他锁后再刷新，防止并发竞争
    cred_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            # 加锁后重新读取凭证：可能其他进程已经刷新完毕
            cred = load_credentials(cred_path)
            if cred is None:
                _die(
                    f"No credentials found for env '{env}'. "
                    f"Please run the xray-auth login script first:\n"
                    f"  python3 {_SCRIPT_DIR}/auth.py {env}"
                )
            now = int(time.time())
            if cred.expires_at - _EXPIRY_BUFFER_SECONDS > now:
                # 其他进程已刷新，直接返回新 token
                return cred

            print(
                "[xray-auth] access_token expired, refreshing via refresh_token ...",
                file=sys.stderr,
            )
            try:
                new_cred = refresh_access_token(env, cred.refresh_token)
                save_credentials(cred_path, new_cred)
                print("[xray-auth] token refreshed successfully.", file=sys.stderr)
                return new_cred
            except Exception as e:
                _die(
                    f"Token refresh failed ({e}). "
                    f"Please login again:\n"
                    f"  python3 {_SCRIPT_DIR}/auth.py {env}"
                )
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _die(message: str) -> None:
    """输出错误到 stderr 并以退出码 1 终止。"""
    print(f"[xray-auth] ERROR: {message}", file=sys.stderr)
    sys.exit(1)


# ============ CLI Entry ============


def main():
    parser = argparse.ArgumentParser(
        description="获取当前有效的 Xray auth token（自动 refresh）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 直接获取 access_token（适合赋值给 XRAY_AUTH_TOKEN）
  TOKEN=$(python3 get_token.py --env sit)
  export XRAY_AUTH_TOKEN=$TOKEN

  # 获取完整 credentials JSON
  python3 get_token.py --env prod --output json

退出码：
  0  成功
  1  token 不存在或无法刷新，需要重新登录
""",
    )
    parser.add_argument(
        "--env",
        default=os.environ.get("XRAY_ENV", "sit"),
        choices=["dev", "sit", "prod"],
        help="目标环境（默认 sit，或读取 XRAY_ENV 环境变量）",
    )
    parser.add_argument(
        "--output",
        default="token",
        choices=["token", "json"],
        help="输出格式：token（仅 access_token，默认）或 json（完整 credentials）",
    )

    args = parser.parse_args()

    cred = get_token(args.env)

    if args.output == "json":
        print(
            json.dumps(
                {
                    "access_token": cred.access_token,
                    "refresh_token": cred.refresh_token,
                    "expires_at": cred.expires_at,
                },
                indent=2,
            )
        )
    else:
        print(cred.access_token)


if __name__ == "__main__":
    main()
