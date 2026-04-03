#!/usr/bin/env python3
"""
xray-cli auth login 的 Python 实现，与 Go 版本功能完全对齐。
用于 Agent Skill 调用。
"""

import os
import sys
import json
import time
import base64
import platform
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any
from urllib import request, error


# ============ Configuration ============

CLIENT_ID = "xray-cli"
VALID_ENVS = ["dev", "sit", "prod"]

SSO_ENDPOINTS = {
    "dev": {
        "device_auth": "http://localhost:8080/api/headless/auth/device/authorization",
        "token": "http://localhost:8080/api/headless/auth/token",
    },
    "sit": {
        "device_auth": "https://xray.devops.sit.xiaohongshu.com/api/headless/auth/device/authorization",
        "token": "https://xray.devops.sit.xiaohongshu.com/api/headless/auth/token",
    },
    "prod": {
        "device_auth": "https://xray.devops.xiaohongshu.com/api/headless/auth/device/authorization",
        "token": "https://xray.devops.xiaohongshu.com/api/token",
    },
}


# ============ Data Classes ============


@dataclass
class DeviceCodeResponse:
    """Device Authorization Endpoint 响应"""

    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


@dataclass
class TokenResponse:
    """Token Endpoint 成功响应"""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


@dataclass
class JWTPayload:
    """JWT Payload 解析结果"""

    sub: str
    name: str
    uuid: str
    type: str
    iat: int
    exp: int


@dataclass
class Credentials:
    """凭证数据"""

    access_token: str
    refresh_token: str
    expires_at: int


# ============ JWT Utils ============


def parse_jwt_payload(token: str) -> JWTPayload:
    """解析 JWT 的 payload 部分（不验签，仅解码）"""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(f"invalid JWT format: expected 3 parts, got {len(parts)}")

    # Base64 URL-safe decode
    payload_b64 = parts[1]
    # Add padding if needed
    padding_needed = 4 - len(payload_b64) % 4
    if padding_needed != 4:
        payload_b64 += "=" * padding_needed

    try:
        payload_data = base64.urlsafe_b64decode(payload_b64)
        payload_json = json.loads(payload_data)
    except Exception as e:
        raise ValueError(f"failed to decode JWT payload: {e}")

    return JWTPayload(
        sub=payload_json.get("sub", ""),
        name=payload_json.get("name", ""),
        uuid=payload_json.get("uuid", ""),
        type=payload_json.get("type", ""),
        iat=payload_json.get("iat", 0),
        exp=payload_json.get("exp", 0),
    )


# ============ Path Utils ============


def get_config_dir() -> Path:
    """获取 xray-cli 配置根目录路径（~/.config/xray-cli）"""
    if platform.system() == "Darwin":
        base = Path.home() / ".config" / ".xray-cli"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "xray-cli"


def get_credentials_path(env: str) -> Path:
    """获取指定环境的 credentials.json 完整路径"""
    return get_config_dir() / env / "credentials.json"


# ============ Credential Persistence ============


def save_credentials(path: Path, cred: Credentials) -> None:
    """将 credentials 写入 path，文件权限 0600（原子写入，避免 TOCTOU）"""
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    data = {
        "access_token": cred.access_token,
        "refresh_token": cred.refresh_token,
        "expires_at": cred.expires_at,
    }
    content = json.dumps(data, indent=2).encode("utf-8")
    # 用 O_CREAT | O_WRONLY | O_TRUNC + mode=0o600 原子创建/覆盖文件，
    # 全程不存在 0644 权限窗口（不同于 write_text + chmod 的两步操作）
    fd = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(fd, content)
    finally:
        os.close(fd)


def load_credentials(path: Path) -> Optional[Credentials]:
    """从 path 读取并解析 credentials"""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return Credentials(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
        )
    except (json.JSONDecodeError, KeyError):
        return None


def delete_credentials(path: Path) -> None:
    """删除 credentials 文件。若文件不存在，静默返回。"""
    if path.exists():
        path.unlink()


# ============ Browser Utils ============


def has_display() -> bool:
    """检测当前环境是否有可用的桌面显示环境"""
    system = platform.system()
    if system == "Darwin":
        return True
    elif system == "Linux":
        return (
            os.environ.get("DISPLAY") is not None or os.environ.get("WAYLAND_DISPLAY") is not None
        )
    return False


def open_browser(url: str) -> bool:
    """尝试在默认浏览器中打开 url，返回是否成功启动"""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        elif system == "Linux":
            if has_display():
                subprocess.Popen(
                    ["xdg-open", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
    except Exception:
        print(
            "  (Could not open browser automatically; please open the URL manually)",
            file=sys.stderr,
        )
    return False


# ============ HTTP Utils ============


def http_post_json(url: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """发送 POST 请求，返回 JSON 响应。

    HTTP 4xx/5xx 会直接抛出异常，不会与正常 200 响应混淆。
    调用方无需判断返回值是否代表错误。
    """
    req = request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        # 读取错误响应体以提供更多上下文，但始终抛异常，不返回 dict
        try:
            error_body = e.read().decode("utf-8")
            raise Exception(f"HTTP {e.code} {e.reason}: {error_body}")
        except Exception as inner:
            # 如果读 body 本身失败，直接抛原始错误
            if "HTTP" in str(inner):
                raise
            raise Exception(f"HTTP {e.code}: {e.reason}")
    except error.URLError as e:
        raise Exception(f"network error: {e.reason}; please check your internal network connection")
    except Exception as e:
        raise Exception(f"request failed: {e}")


# ============ Device Flow Client ============


class DeviceFlowClient:
    """OAuth 2.0 Device Authorization Grant 客户端"""

    def __init__(self, device_auth_endpoint: str, token_endpoint: str, client_id: str):
        self.device_auth_endpoint = device_auth_endpoint
        self.token_endpoint = token_endpoint
        self.client_id = client_id

    def request_device_code(self) -> DeviceCodeResponse:
        """请求 device code"""
        resp = http_post_json(self.device_auth_endpoint, {"client_id": self.client_id})

        if not resp.get("success", False):
            msg = resp.get("message", "unknown error")
            raise Exception(f"device authorization failed: {msg}")

        data = resp.get("data", {})
        return DeviceCodeResponse(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_uri=data["verification_uri"],
            expires_in=data["expires_in"],
            interval=data.get("interval", 5),
        )

    def request_token(self, device_code: str) -> tuple[Optional[TokenResponse], Optional[str]]:
        """
        请求 token，返回 (TokenResponse, error_code)
        error_code 可能是: authorization_pending, slow_down, expired_token, access_denied
        """
        resp = http_post_json(
            self.token_endpoint,
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": self.client_id,
            },
        )

        if resp.get("success", False):
            data = resp.get("data", {})
            return (
                TokenResponse(
                    access_token=data["access_token"],
                    refresh_token=data["refresh_token"],
                    token_type=data.get("token_type", "Bearer"),
                    expires_in=data["expires_in"],
                ),
                None,
            )

        # Handle error
        msg = resp.get("message", "")
        if msg == "authorization_pending":
            return None, "authorization_pending"
        elif msg == "slow_down":
            return None, "slow_down"
        elif msg == "expired_token":
            return None, "expired_token"
        elif msg == "access_denied":
            return None, "access_denied"
        else:
            raise Exception(f"token endpoint error: {resp.get('code', 'unknown')} - {msg}")

    def poll_token(self, device_code: str, interval_seconds: int, expires_in: int) -> TokenResponse:
        """
        轮询 Token Endpoint 直到授权完成或出错。

        策略：先请求一次，拿到结果后再决定是否 sleep。
        sleep 前检查是否已超时，避免在授权码即将过期时多等一个 interval。
        """
        start_time = time.time()
        interval = interval_seconds

        while True:
            token_resp, err_code = self.request_token(device_code)

            if token_resp is not None:
                return token_resp

            if err_code == "expired_token":
                raise Exception("authorization code expired, please run login again")
            elif err_code == "access_denied":
                raise Exception("authorization denied by user")
            elif err_code == "slow_down":
                interval += 5
            elif err_code != "authorization_pending":
                raise Exception(f"unexpected error from token endpoint: {err_code}")

            # 在 sleep 前估算"sleep 完后"的总耗时，采用保守策略：
            # 若 sleep 完毕时已达到或超过过期时间，则不再等待，直接报超时。
            # （宁可早报一次超时，也不在 token 几乎失效时再多等一个 interval）
            elapsed = time.time() - start_time
            if elapsed + interval >= expires_in:
                raise Exception("authorization code expired, please run login again")

            time.sleep(interval)


# ============ Main Login Flow ============


def login(env: str = "sit", auto_open_browser: bool = True) -> Credentials:
    """
    执行完整的登录流程

    Args:
        env: 环境标识 (dev, sit, prod)
        auto_open_browser: 是否尝试自动打开浏览器

    Returns:
        Credentials: 登录凭证

    Raises:
        Exception: 登录失败时抛出
    """
    if env not in VALID_ENVS:
        raise ValueError(f"invalid env '{env}'; must be one of {VALID_ENVS}")

    # Setup client
    endpoints = SSO_ENDPOINTS[env]
    client = DeviceFlowClient(
        device_auth_endpoint=endpoints["device_auth"],
        token_endpoint=endpoints["token"],
        client_id=CLIENT_ID,
    )

    # Step 1: 请求 device code
    device_resp = client.request_device_code()

    # Step 2: 打印提示信息
    vurl = f"{device_resp.verification_uri}?user_code={device_resp.user_code}&source=xray-cli"
    print()
    print(f"  Environment: {env}")
    print("  Open this URL in your browser:")
    print(f"  {vurl}", flush=True)  # flush 确保重定向到文件时 URL 立即可读
    print(f"  (Code expires in {device_resp.expires_in // 60} minutes)")
    print()

    # Step 3: 尝试自动打开浏览器
    if auto_open_browser and has_display():
        open_browser(vurl)

    # Step 4: 轮询等待用户完成授权
    token_resp = client.poll_token(
        device_resp.device_code,
        device_resp.interval,
        device_resp.expires_in,
    )

    # Step 5: 解析 JWT payload 获取用户信息
    payload = parse_jwt_payload(token_resp.access_token)

    # Step 6: 持久化 credentials
    cred = Credentials(
        access_token=token_resp.access_token,
        refresh_token=token_resp.refresh_token,
        expires_at=payload.exp,
    )
    cred_path = get_credentials_path(env)
    save_credentials(cred_path, cred)
    print(f"  auth file has write in {cred_path}")
    print(f"  Logged in as {payload.sub} ({env})")
    print()

    return cred


# ============ Logout ============


def logout(env: str) -> None:
    """删除指定环境的本地凭证，完成登出。"""
    if env not in VALID_ENVS:
        raise ValueError(f"invalid env '{env}'; must be one of {VALID_ENVS}")
    cred_path = get_credentials_path(env)
    delete_credentials(cred_path)
    print(f"  Logged out ({env}): credentials removed from {cred_path}")


# ============ CLI Entry ============


def main():
    """CLI 入口

    用法：
      auth.py [login] [sit|prod|dev]   — 登录（默认子命令）
      auth.py logout  [sit|prod|dev]   — 删除本地凭证（登出）
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Xray CLI 鉴权工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 auth.py               # 登录 SIT（默认）
  python3 auth.py prod          # 登录生产环境
  python3 auth.py logout        # 登出 SIT
  python3 auth.py logout prod   # 登出生产环境

环境变量：
  XRAY_ENV=prod python3 auth.py  # 通过环境变量指定环境
""",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="login",
        choices=["login", "logout"] + VALID_ENVS,
        help="子命令（login/logout）或直接传环境名（sit/prod/dev）",
    )
    parser.add_argument(
        "env_positional",
        nargs="?",
        default=None,
        metavar="ENV",
        help="目标环境：sit（默认）、prod、dev",
    )

    args = parser.parse_args()

    # 兼容旧用法：auth.py prod（第一个参数直接是 env 名）
    if args.command in VALID_ENVS:
        cmd = "login"
        env = args.command
    else:
        cmd = args.command  # "login" 或 "logout"
        env = args.env_positional or os.environ.get("XRAY_ENV", "sit")

    try:
        if cmd == "logout":
            logout(env)
        else:
            login(env=env)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
