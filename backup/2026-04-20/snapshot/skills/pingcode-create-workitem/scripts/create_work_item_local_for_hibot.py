#!/usr/bin/env python3
"""
创建工作项（需求/缺陷/子任务），用于 HiBot 创建工作项。

Usage:
    python3 create_work_item_local_for_hibot.py <workSpaceId> <subTypeId> <workItemTypeKey> <subTypeCode> <formData JSON> [parentId]

Arguments:
    workSpaceId     空间ID（必填）
    subTypeId       工作项子类型ID（必填）
    workItemTypeKey 工作项类型，如：task、bug、subtask（必填）
    subTypeCode     子类型编码（必填），用于获取用户列表做用户名转 email
    formData        表单数据，JSON 字符串（必填），如：'{"name":"优化登录","owner":"普兰","businessLine":"0000000065"}'
    parentId        父工作项ID（可选），创建子任务时必填

Example:
    python3 create_work_item_local_for_hibot.py 60 194 task TASK_SUBTYPE_TECHNOLOGY '{"name":"优化登录","owner":"普兰","businessLine":"0000000065"}'

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

# 用户类型字段
USER_FIELD_TYPES = {"USER", "MULTI_USER", "ROLE_MULTI_USER"}


def _is_email(s: str) -> bool:
    return isinstance(s, str) and "@" in s and "." in s


def _find_best_match_email(user_name: str, user_list: list, name_to_email: dict) -> str:
    """根据用户名模糊匹配 email，逻辑与 TypeScript 端保持一致。"""
    if not user_name or not isinstance(user_name, str):
        return ""
    trimmed = user_name.strip()
    if _is_email(trimmed):
        return trimmed
    # 精确匹配
    if trimmed in name_to_email:
        return name_to_email[trimmed]
    # 模糊匹配：包含关系
    for user in user_list:
        value = user.get("value", "")
        key = user.get("key", "")
        if value and key:
            if trimmed in value or value in trimmed:
                return key
    return ""


def _fetch_form_config(user_email: str, work_space_id: int, sub_type_code: str):
    """调用表单推荐接口，获取 formFieldList 和 userList。"""
    url = f"{BASE_URL}/redpingcode/openapi/mcp/work_item/recommend_create_form"
    body = json.dumps({
        "userEmail": user_email,
        "workSpaceId": work_space_id,
        "subTypeCode": sub_type_code,
        "includeUserList": True,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
        result = json.loads(resp.read())

    data = result.get("data")
    if not data:
        return None, None
    return data.get("formFieldList"), data.get("userList")


def _resolve_user_fields(form_data: dict, form_field_list: list, user_list: list) -> dict | None:
    """
    将 formData 中用户类型字段的用户名转换为 email。
    如果 owner 字段无法匹配，返回错误 dict；否则返回 None 表示成功。
    """
    name_to_email: dict[str, str] = {}
    for user in user_list:
        key = user.get("key", "")
        value = user.get("value", "")
        if key and value:
            name_to_email[value] = key

    for field in form_field_list:
        if field.get("fieldType") not in USER_FIELD_TYPES:
            continue

        field_key = field.get("fieldKey", "")
        is_owner = field_key == "owner"
        field_value = form_data.get(field_key)

        # owner 必填校验
        if is_owner and (field_value is None or field_value == ""):
            return {"success": False, "code": 400, "msg": "负责人不能为空", "data": "负责人不能为空"}

        if field_value is None:
            continue

        if isinstance(field_value, list):
            form_data[field_key] = [
                email for name in field_value
                if (email := _find_best_match_email(name, user_list, name_to_email))
            ]
        elif isinstance(field_value, str):
            matched = _find_best_match_email(field_value, user_list, name_to_email)
            if is_owner and not matched:
                return {
                    "success": False,
                    "code": 4000,
                    "msg": "负责人不存在",
                    "data": f'"{field_value}"在系统中不存在或没有权限',
                }
            form_data[field_key] = matched

    return None  # 成功


def main():
    user_email = os.environ.get("XHS_USER_EMAIL")
    if not user_email:
        raise EnvironmentError("环境变量 XHS_USER_EMAIL 未设置")

    if len(sys.argv) < 6:
        raise ValueError(
            "用法: python3 create_work_item_local_for_hibot.py <workSpaceId> <subTypeId> <workItemTypeKey> <subTypeCode> <formData JSON> [parentId]"
        )

    work_space_id = int(sys.argv[1])
    sub_type_id = int(sys.argv[2])
    work_item_type_key = sys.argv[3]
    sub_type_code = sys.argv[4]
    form_data = json.loads(sys.argv[5])
    parent_id = int(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] else None

    # ---- 用户名 → email 转换（与 TypeScript 端逻辑对齐）----
    form_field_list, user_list = _fetch_form_config(user_email, work_space_id, sub_type_code)
    if form_field_list and user_list:
        err = _resolve_user_fields(form_data, form_field_list, user_list)
        if err:
            print(json.dumps(err, ensure_ascii=False, indent=2))
            return

    # ---- 调用创建接口 ----
    url = f"{BASE_URL}/redpingcode/openapi/mcp/work_item/create/local_for_hibot"
    body_obj = {
        "userEmail": user_email,
        "workSpaceId": work_space_id,
        "subTypeId": sub_type_id,
        "workItemTypeKey": work_item_type_key,
        "formData": form_data,
        "parentId": parent_id,
        "source": "HI",
    }
    body = json.dumps(body_obj).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
        result = json.loads(resp.read())

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
