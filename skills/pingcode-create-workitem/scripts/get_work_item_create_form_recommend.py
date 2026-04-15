#!/usr/bin/env python3
"""
获取创建工作项推荐表单（含字段值推荐逻辑）

Usage:
    python3 get_work_item_create_form_recommend.py <workSpaceId> <subTypeCode> [parentId]

Arguments:
    workSpaceId   空间ID（必填）
    subTypeCode   工作项子类型code（必填），如：TASK_SUBTYPE_PRODUCT、BUG_SUBTYPE_DEFAULT、SUBTASK_SUBTYPE_SERVER 等
    parentId      父需求ID（可选），创建子任务时传入

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

    if len(sys.argv) < 3:
        raise ValueError("请传入 workSpaceId 和 subTypeCode，例如：python3 get_work_item_create_form_recommend.py 60 TASK_SUBTYPE_PRODUCT")

    work_space_id = int(sys.argv[1])
    sub_type_code = sys.argv[2]
    parent_id = int(sys.argv[3]) if len(sys.argv) > 3 else None

    url = f"{BASE_URL}/redpingcode/openapi/mcp/work_item/recommend_create_form"
    payload = {
        "userEmail": user_email,
        "workSpaceId": work_space_id,
        "subTypeCode": sub_type_code,
    }
    if parent_id is not None:
        payload["parentId"] = parent_id
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
        result = json.loads(resp.read())

    if isinstance(result.get("data"), dict):
        result["data"].pop("userList", None)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
