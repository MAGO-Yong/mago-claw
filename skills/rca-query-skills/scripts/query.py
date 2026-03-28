#!/usr/bin/env python3
"""
RCA 故障查询脚本

用法:
    python query.py '<JSON参数>'

参数说明（所有字段可选）:
    title           string      标题关键词
    level           string[]    故障级别: P0/P1/P2/P3/P4/Notice
    scene           string[]    故障场景
    business_line   string[]    业务线
    case_type       string[]    案例类型: 服务端/前端/数据问题/非技术
    rca_review_status string[]  RCA状态: 已复盘/未复盘
    case_status     string      故障状态: fixed/unfix
    start           string      创建时间起始: YYYY-MM-DD HH:MM:SS (如 2026-03-11 00:00:00)
    end             string      创建时间结束: YYYY-MM-DD HH:MM:SS (如 2026-03-13 23:59:59)
    pageNo          int         页码 (默认 1)
    pageSize        int         每页数量 (默认 20)

输出: JSON 到 stdout
    成功: {"success": true, "total": N, "pageNo": N, "pageSize": N, "list": [...]}
    失败: {"success": false, "error": "错误信息"}
"""

import json
import sys
import urllib.request
import urllib.error

API_URL = "https://rca.devops.xiaohongshu.com/api/case/search"
TIMEOUT = 15

# 数组类型字段
ARRAY_FIELDS = {
    "feedback_label", "level", "scene", "business_line",
    "case_type", "rca_review_status", "mttr",
}


def build_request_body(params: dict) -> dict:
    """将用户参数合并到默认请求体"""
    body = {
        "feedback_label": [],
        "level": [],
        "scene": [],
        "business_line": [],
        "case_type": [],
        "rca_review_status": [],
        "title": "",
        "mttr": [],
        "type": 1,
        "pageNo": params.get("pageNo", 1),
        "pageSize": params.get("pageSize", 20),
    }

    for key, value in params.items():
        if key in ("pageNo", "pageSize"):
            continue
        if key in ARRAY_FIELDS:
            body[key] = value if isinstance(value, list) else [value]
        else:
            body[key] = value

    return body


def query_rca(params: dict) -> dict:
    """调用 RCA API，返回解析后的响应"""
    body = build_request_body(params)
    data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Cookie": "a1=19c54da136ec4k87oyjr2rq0ppqr5vi5f04nuhqja30000427947; webId=f9b12138888ace1c7de08b245ca46134; timeslogin=945d05a1-4b4d-43cd-8ffa-6b70abcfc614; porch_beaker_session_id=867c1aa3a3064300c002c53a4ad038b4b26a7affgAJ9cQAoWAMAAABfaWRxAVggAAAAZTM1YjdjODc3ODAyNGU1Nzk3NWQ5ZDk0ZDIyMjYyMTVxAlgOAAAAX2FjY2Vzc2VkX3RpbWVxA0ogi4VpWAoAAABleHBpcmVkX2F0cQRKIDL8aVgNAAAAcG9yY2gtdXNlci1pZHEFWBgAAAA2NjhiNGEwYTEyMDAwMDAwMDAwMDAwMDJxBlgQAAAAcG9yY2gtYXV0aC10b2tlbnEHWEEAAABjNWE2ZDBhMDdiMmQ0ZjAxYWYwN2FmNDI0MmJlMzZiMi1lY2IwZDRhOGI0OWM2NTRlMmYzNjJiMTc3MDM1OTQxOXEIWA4AAABfY3JlYXRpb25fdGltZXEJSiCLhWl1Lg==; redpass_did=2D0F79F9-8838-5E5C-8444-7C6D5F49DE01; e-sso-user-id=668b4a0a1200000000000002; access-token-xray-nj.devops.xiaohongshu.com=internal.xray.AT-c02ba64faeca42c4b745146f9dd6424b-e35f8c15de7f7f338718c71770950108; common-internal-access-token-prod=AT-c02ba64faeca42c4b745146f9dd6424b-e35f8c15de7f7f338718c71770950108; portal-guide=done; sit_porch_beaker_session_id=7ba2e3c80f67c94b6d7a453b775f039b90fe196agAJ9cQAoWAMAAABfaWRxAVggAAAAMzczN2ExY2FjYzJhNDVjMmI3NDMxNjZkMDkyYmVkZWRxAlgOAAAAX2FjY2Vzc2VkX3RpbWVxA0ofOa5pWAoAAABleHBpcmVkX2F0cQRKH+AkalgNAAAAcG9yY2gtdXNlci1pZHEFWBgAAAA2NjhiNGEwYjFkMDAwMDAwMDAwMDAwMDFxBlgQAAAAcG9yY2gtYXV0aC10b2tlbnEHWEEAAAA0YzJhYzM5YzEzMzU0YzQzODhjZWJlMzVmYzQ4N2FmMC1lY2QyOGUyYzJmYWY0OGFlYmIyNzIwYjgxZDk4NGM3N3EIWA4AAABfY3JlYXRpb25fdGltZXEJSh85rml1Lg==; x-user-id-sit=668b4a0b1d00000000000001; _porch_uuid=835559117951910; e-sso-user-id-sit=668b4a0b1d00000000000001; access-token-xray.devops.sit.xiaohongshu.com=internal.xray.AT-8d46052c7b864753ba935c93b55d8c10-ac5352a529481f82f28ed61773025568; x-user-id=668b4a0b1d00000000000001; x-user-id-xray.devops.sit.xiaohongshu.com=668b4a0b1d00000000000001; common-internal-access-token-sit=AT-8d46052c7b864753ba935c93b55d8c10-ac5352a529481f82f28ed61773025568; abRequestId=f9b12138888ace1c7de08b245ca46134; webBuild=5.14.2; loadts=1773058727101; web_session=030037ae9deed3afc02eebfcd62e4a38638b4a; xsecappid=itspc; x-user-lang-prod=zh_cn; gid=yjSd8Jq8fjifyjS24f0yq8xAKdS4TYWlvVFJ4V0FA8UUAIq8F2h3278884JWj4W8J4DD48K2; websectiga=3fff3a6f9f07284b62c0f2ebf91a3b10193175c06e4f71492b60e056edcdebb2",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"查询失败，状态码：{e.code}")
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if "timed out" in reason:
            raise RuntimeError("网络请求超时，请稍后重试")
        raise RuntimeError(f"无法连接到 RCA 平台：{reason}")
    except json.JSONDecodeError:
        raise RuntimeError("响应数据格式异常，请联系平台管理员")


def main():
    # 解析命令行参数
    params = {}
    if len(sys.argv) > 1:
        try:
            params = json.loads(sys.argv[1])
        except json.JSONDecodeError as e:
            print(json.dumps({"success": False, "error": f"参数解析失败：{e}"}))
            sys.exit(1)

    try:
        resp = query_rca(params)
    except RuntimeError as e:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)

    # 提取关键字段
    if not resp.get("success", False):
        err = resp.get("err_msg") or resp.get("error") or "未知错误"
        print(json.dumps({"success": False, "error": err}, ensure_ascii=False))
        sys.exit(1)

    data = resp.get("data", {})
    result = {
        "success": True,
        "total": data.get("total", 0),
        "pageNo": data.get("pageNum", params.get("pageNo", 1)),
        "pageSize": data.get("pageSize", params.get("pageSize", 20)),
        "list": data.get("list", []),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
