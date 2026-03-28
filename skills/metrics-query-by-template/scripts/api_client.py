#!/usr/bin/env python3
import argparse, base64, json, sys, time, requests
from pathlib import Path

CONFIG_DIR = Path.home() / ".xray-skills" / ".config"
TOKEN_FILE = CONFIG_DIR / "token.json"

def load_config():
    if not TOKEN_FILE.exists():
        print("错误: Token未配置", file=sys.stderr)
        sys.exit(1)
    with open(TOKEN_FILE, 'r') as f:
        return json.load(f)

def generate_ticket(token, source):
    timestamp = int(time.time() * 1000)
    return base64.b64encode(f"{source}&{token}&{timestamp}".encode()).decode()

def call_api(config, arguments):
    ticket = generate_ticket(config['token'], config['source'])
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
    parser.add_argument('--app', required=True, help='服务名称')
    parser.add_argument('--start', required=True, help='开始时间')
    parser.add_argument('--end', required=True, help='结束时间')
    parser.add_argument('--metric-ids', required=True, help='指标ID列表，逗号分隔')
    parser.add_argument('--scope', default='CLUSTER', help='查询范围')
    parser.add_argument('--group-bys', help='分组维度，逗号分隔')
    args = parser.parse_args()

    config = load_config()

    # 解析metricIds
    metric_ids = [m.strip() for m in args.metric_ids.split(',')]

    arguments = {
        "app": args.app,
        "start": args.start,
        "end": args.end,
        "metricIds": metric_ids,
        "scope": args.scope
    }

    # 解析groupBys
    if args.group_bys:
        arguments["groupBys"] = [g.strip() for g in args.group_bys.split(',')]

    result = call_api(config, arguments)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
