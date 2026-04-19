#!/usr/bin/env python3
"""
获取创建工作项初始信息（有权限的空间列表及子类型列表）

Usage:
    python3 get_create_workitem_init_info.py

环境变量：
    XHS_USER_EMAIL  当前用户邮箱（必须）
"""

import json
import os
import ssl
import urllib.request

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

BASE_URL = "https://pingcode2.devops.xiaohongshu.com"


def main():
    user_email = os.environ.get("XHS_USER_EMAIL")
    if not user_email:
        raise EnvironmentError("环境变量 XHS_USER_EMAIL 未设置")

    url = f"{BASE_URL}/redpingcode/openapi/mcp/work_item/create/init/info"
    body = json.dumps({"userEmail": user_email, "excludePublicSpaces": True}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
        result = json.loads(resp.read())

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
