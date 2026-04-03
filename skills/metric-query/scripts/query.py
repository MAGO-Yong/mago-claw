#!/usr/bin/env python3
"""
统一指标查询客户端
支持三种查询模式: system（模板指标）、pql（PromQL）、cat（Cat 指标）
"""

import argparse
import json
import sys

import requests

BASE_URL = "http://xray-ai.devops.xiaohongshu.com/open/skill/metric/proxy"
TIMEOUT = 120


def call_api(mode, payload):
    url = f"{BASE_URL}/{mode}"
    print(f"请求: POST {url}", file=sys.stderr)
    print(f"参数: {json.dumps(payload, ensure_ascii=False, indent=2)}", file=sys.stderr)
    print(file=sys.stderr)

    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"错误: HTTP {resp.status_code} — {resp.text[:500]}", file=sys.stderr)
            sys.exit(1)
        return resp.json()
    except requests.RequestException as e:
        print(f"请求异常: {e}", file=sys.stderr)
        sys.exit(1)


def build_system_payload(args):
    if not args.metric_names:
        print("错误: system 模式必须提供 --metric-names", file=sys.stderr)
        sys.exit(1)
    if not args.app:
        print("错误: system 模式必须提供 --app", file=sys.stderr)
        sys.exit(1)

    payload = {
        "app": args.app,
        "start": args.start,
        "end": args.end,
        "metricNames": [m.strip() for m in args.metric_names.split(",")],
    }
    if args.view:
        payload["view"] = args.view
    if args.group_bys:
        payload["groupBys"] = [g.strip() for g in args.group_bys.split(",")]
    return payload


def build_pql_payload(args):
    if not args.pql:
        print("错误: pql 模式必须提供 --pql", file=sys.stderr)
        sys.exit(1)

    payload = {
        "pql": args.pql,
        "start": args.start,
        "end": args.end,
    }
    if args.app:
        payload["app"] = args.app
    if args.datasource:
        payload["datasource"] = args.datasource
    return payload


def build_cat_payload(args):
    if not args.app:
        print("错误: cat 模式必须提供 --app", file=sys.stderr)
        sys.exit(1)

    payload = {
        "app": args.app,
        "start": args.start,
        "end": args.end,
    }
    if args.theme:
        payload["theme"] = args.theme
    if args.metric:
        payload["metric"] = args.metric
    if args.type:
        payload["type"] = args.type
    if args.types:
        payload["types"] = [t.strip() for t in args.types.split(",")]
    if args.names:
        payload["names"] = [n.strip() for n in args.names.split(",")]
    if args.zones:
        payload["zones"] = [z.strip() for z in args.zones.split(",")]
    if args.ips:
        payload["ips"] = [i.strip() for i in args.ips.split(",")]
    if args.step:
        payload["step"] = args.step
    return payload


BUILDERS = {
    "system": build_system_payload,
    "pql": build_pql_payload,
    "cat": build_cat_payload,
}


def main():
    parser = argparse.ArgumentParser(description="统一指标查询")
    parser.add_argument("--mode", required=True, choices=["system", "pql", "cat"], help="查询模式")

    # 公共参数
    parser.add_argument("--app", help="服务名称")
    parser.add_argument("--start", required=True, help="开始时间 yyyy-MM-dd HH:mm:ss")
    parser.add_argument("--end", required=True, help="结束时间 yyyy-MM-dd HH:mm:ss")

    # system 模式
    parser.add_argument("--metric-names", help="指标名称列表，逗号分隔 (system 模式)")
    parser.add_argument("--view", help="查询视角: cluster/zone/container (system 模式)")
    parser.add_argument("--group-bys", help="分组维度，逗号分隔 (system 模式)")

    # pql 模式
    parser.add_argument("--pql", help="PromQL 表达式 (pql 模式)")
    parser.add_argument("--datasource", help="VMS 数据源名称 (pql 模式)")

    # cat 模式
    parser.add_argument("--theme", help="Cat 主题: transaction/event/problem (cat 模式)")
    parser.add_argument("--metric", help="Cat 指标: qps/avg/tp99/count/... (cat 模式)")
    parser.add_argument("--type", help="Cat 类型，单选: Call/Service/Http/URL (cat 模式)")
    parser.add_argument("--types", help="Cat 类型，多选，逗号分隔，与 --type 互斥 (cat 模式)")
    parser.add_argument("--names", help="接口名称列表，逗号分隔 (cat 模式)")
    parser.add_argument("--zones", help="机房列表，逗号分隔 (cat 模式)")
    parser.add_argument("--ips", help="IP 列表，逗号分隔 (cat 模式)")
    parser.add_argument("--step", type=int, help="步长(秒) (cat 模式)")

    args = parser.parse_args()

    builder = BUILDERS[args.mode]
    payload = builder(args)
    result = call_api(args.mode, payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
