#!/usr/bin/env python3
import argparse
import datetime
import json
import sys
import urllib.error
import urllib.request

API_URL = "https://xray.devops.xiaohongshu.com/openapi/alarm/pql/rule/all/v1"
TICKET = "pass"


def fetch(filter_key: str, filter_val: str, page: int, size: int) -> dict:
    body = json.dumps({"type": -1, "page": page, "size": size, filter_key: filter_val}).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Content-Type": "application/json", "xray_ticket": TICKET},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"请求失败: HTTP {e.code} {e.reason}\n{body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"请求失败: {e.reason}", file=sys.stderr)
        sys.exit(1)


def format_rule(r: dict) -> dict:
    modify_ts = r.get("modifyTime")
    return {
        "ruleId": r["id"],
        "type": "pql",
        "name": r["name"],
        "alarmTarget": r.get("app"),
        "level": r.get("level"),
        "status": "启用" if r.get("status") == 1 else "停用",
        "modifyTime": (
            datetime.datetime.fromtimestamp(modify_ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
            if modify_ts
            else None
        ),
        "modifier": r.get("modifier"),
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "搜索 Xray PQL 告警规则列表（基于 PromQL 表达式的指标告警）。\n"
            "按服务树维度过滤，返回分页结果及分页元信息。\n"
            "服务树层级：prdLine > bizLine > app > service\n"
            "--app 同时支持传入 service 名称（如 xrayaiagent-service-diagnosis）。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  %(prog)s --app xrayaiagent-service-diagnosis\n"
            "  %(prog)s --app xrayaiagent-service-diagnosis --page 2 --size 50\n"
            "  %(prog)s --prdLine fulishe --size 100\n"
            "  %(prog)s --bizLine usergrowth\n"
            "\n"
            "输出字段：ruleId / type(固定为pql) / name / alarmTarget / level / status / modifyTime / modifier\n"
            "分页元信息：total / page / total_page / page_size"
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--app",
        metavar="NAME",
        help="按 app 或 service 名称过滤（如 xrayaiagent-service-diagnosis）",
    )
    group.add_argument("--prdLine", metavar="NAME", help="按产品线过滤（如 fulishe、community）")
    group.add_argument("--bizLine", metavar="NAME", help="按业务线过滤（如 usergrowth、deal）")
    parser.add_argument(
        "--page", type=int, default=1, metavar="N", help="页码，从 1 开始（默认：1）"
    )
    parser.add_argument("--size", type=int, default=20, metavar="N", help="每页条数（默认：20）")
    args = parser.parse_args()

    if args.page < 1:
        parser.error("--page 必须 >= 1")
    if args.size < 1:
        parser.error("--size 必须 >= 1")

    if args.app:
        filter_key, filter_val = "app", args.app
    elif args.prdLine:
        filter_key, filter_val = "prdLine", args.prdLine
    elif args.bizLine:
        filter_key, filter_val = "bizLine", args.bizLine
    else:
        parser.error("请指定 --app、--prdLine 或 --bizLine 之一")

    resp = fetch(filter_key, filter_val, args.page, args.size)

    if not resp.get("success"):
        print(f"API 返回失败: {resp.get('message')}", file=sys.stderr)
        sys.exit(1)

    data = resp.get("data")
    if data is None:
        print("API 返回数据为空", file=sys.stderr)
        sys.exit(1)

    result = {
        "total": data.get("total"),
        "page": data.get("page"),
        "total_page": data.get("total_page"),
        "page_size": data.get("page_size"),
        "rows": [format_rule(r) for r in data.get("rows") or []],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
