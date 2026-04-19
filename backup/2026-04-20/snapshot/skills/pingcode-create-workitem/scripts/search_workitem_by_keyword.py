#!/usr/bin/env python3
"""
模糊搜索工作项（通过ID或名称关键词）

Usage:
    python3 search_workitem_by_keyword.py <keyword>

环境变量：
    XHS_USER_EMAIL  当前用户邮箱（必须）
"""

import json
import os
import ssl
import sys
import urllib.request

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

BASE_URL = "https://pingcode2.devops.xiaohongshu.com"


def main():
    user_email = os.environ.get("XHS_USER_EMAIL")
    if not user_email:
        raise EnvironmentError("环境变量 XHS_USER_EMAIL 未设置")

    if len(sys.argv) < 2:
        raise ValueError("请传入搜索关键词，例如：python3 search_workitem_by_keyword.py 优化登录")

    keyword = sys.argv[1]

    url = f"{BASE_URL}/redpingcode/openapi/mcp/work_item/search"
    body = json.dumps({
        "userEmail": user_email,
        "workItemKeyWord": keyword,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
        result = json.loads(resp.read())

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
