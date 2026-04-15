#!/usr/bin/env python3
"""
根据筛选条件查询工作项

Usage:
    python search_workitem_by_condition.py --filter-condition '<JSON>'

环境变量：
    XHS_USER_EMAIL  当前用户邮箱（必须）

Example:
    python search_workitem_by_condition.py \
        --filter-condition '{"createBy": ["user@example.com"], "createTime": ["DAYS_AGO_7", "TODAY"], "workItemType": "TASK"}'
"""

import argparse
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

    parser = argparse.ArgumentParser()
    parser.add_argument("--filter-condition", required=True)
    args = parser.parse_args()

    url = f"{BASE_URL}/redpingcode/openapi/mcp/search/work_item/by_filter"
    body = json.dumps({
        "userEmail": user_email,
        "filterCondition": json.loads(args.filter_condition),
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
        result = json.loads(resp.read())

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
