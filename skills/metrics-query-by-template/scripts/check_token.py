#!/usr/bin/env python3
"""
检查并配置XRay API Token
"""
import json
import os
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".xray-skills" / ".config"
TOKEN_FILE = CONFIG_DIR / "token.json"

# 固定配置
SOURCE = "skill"

def check_token():
    """检查token是否已配置"""
    if not TOKEN_FILE.exists():
        return False, "Token未配置"

    try:
        with open(TOKEN_FILE, 'r') as f:
            config = json.load(f)

        if 'token' not in config or not config['token']:
            return False, "Token为空"

        return True, config
    except Exception as e:
        return False, f"读取token失败: {e}"

def configure_token():
    """引导用户配置token"""
    print("=== XRay API Token 配置 ===")
    print()
    print("首次使用需要配置API Token")
    print("Token申请地址: https://xray.devops.xiaohongshu.com/config/token")
    print()

    token = input("请输入你的API Token: ").strip()

    if not token:
        print("✗ Token不能为空")
        sys.exit(1)

    # 保存配置
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config = {
        "token": token,
        "source": SOURCE,
        "created_at": int(os.times().elapsed * 1000)
    }

    with open(TOKEN_FILE, 'w') as f:
        json.dump(config, f, indent=2)

    # 设置文件权限为600
    TOKEN_FILE.chmod(0o600)

    print()
    print("✓ Token配置成功！")
    print(f"  Token: {token[:8]}...")
    print()
    print("提示: 所有xray-skills都会使用这个token")

    return config

def main():
    """主函数"""
    is_configured, result = check_token()

    if is_configured:
        print("✓ Token已配置")
        print(f"  来源: {SOURCE}")
        sys.exit(0)
    else:
        print(f"✗ {result}")
        print()
        config = configure_token()
        sys.exit(0)

if __name__ == "__main__":
    main()
