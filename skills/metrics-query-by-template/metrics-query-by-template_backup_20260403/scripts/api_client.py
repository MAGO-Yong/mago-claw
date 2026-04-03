#!/usr/bin/env python3
import argparse, base64, json, sys, time, requests, os

SOURCE = "skill"


def get_token():
    """
    获取 XRay API Token。
    优先从环境变量 XRAY_AUTH_TOKEN 读取，若未设置则提示用户交互式输入。
    """
    token = os.environ.get("XRAY_AUTH_TOKEN", "").strip()
    if token:
        return token
    print(
        "[metrics-query-by-template] 未检测到环境变量 XRAY_AUTH_TOKEN，请输入 XRay Token：",
        file=sys.stderr,
    )
    token = input("XRAY_AUTH_TOKEN> ").strip()
    if not token:
        print("[metrics-query-by-template] Token 不能为空，已退出。", file=sys.stderr)
        sys.exit(1)
    return token


def generate_ticket(token, source):
    timestamp = int(time.time() * 1000)
    return base64.b64encode(f"{source}&{token}&{timestamp}".encode()).decode()


def call_api(arguments):
    token = get_token()
    ticket = generate_ticket(token, SOURCE)
    url = "https://xray-ai.devops.xiaohongshu.com/skill/metrics_query_by_template"
    headers = {"xray_ticket": ticket, "Content-Type": "application/json"}

    print(f"正在调用API: {url}", file=sys.stderr)
    print(f"参数: {json.dumps(arguments, ensure_ascii=False, indent=2)}", file=sys.stderr)
    print(file=sys.stderr)

    try:
        response = requests.post(url, json=arguments, headers=headers, timeout=120)
        if response.status_code != 200:
            print(f"错误: API调用失败 (HTTP {response.status_code})", file=sys.stderr)
            sys.exit(1)
        return response.json()
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, help="服务名称")
    parser.add_argument("--start", required=True, help="开始时间")
    parser.add_argument("--end", required=True, help="结束时间")
    parser.add_argument("--metric-ids", required=True, help="指标ID列表，逗号分隔")
    parser.add_argument("--scope", default="CLUSTER", help="查询范围")
    parser.add_argument("--group-bys", help="分组维度，逗号分隔")
    args = parser.parse_args()

    # 解析metricIds
    metric_ids = [m.strip() for m in args.metric_ids.split(",")]

    arguments = {
        "app": args.app,
        "start": args.start,
        "end": args.end,
        "metricIds": metric_ids,
        "scope": args.scope,
    }

    # 解析groupBys
    if args.group_bys:
        arguments["groupBys"] = [g.strip() for g in args.group_bys.split(",")]

    result = call_api(arguments)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
