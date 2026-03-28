#!/usr/bin/env python3
import sys
import json
import urllib.request
import urllib.error

API_URL = "http://xray.devops.xiaohongshu.com/openapi/alarm/pql/rule/detail"
API_SIT_URL = "http://xray.devops.sit.xiaohongshu.com/openapi/alarm/pql/rule/detail"
TICKET = "pass"


def fetch_rule(rule_id: int) -> dict:
    url = f"{API_URL}?id={rule_id}"
    req = urllib.request.Request(url, headers={"xray_ticket": TICKET})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def summarize_rule_config(rule_cfg: dict) -> str:
    mode_str = {0: "简单模式", 1: "高级模式"}.get(rule_cfg.get("mode"), "未知模式")
    parts = []
    for r in rule_cfg.get("rules", []):
        sub: dict = r["subRule"]
        tr: dict = r["timeRange"]
        parts.append(
            f"{tr['startTime']}-{tr['endTime']} "
            f"{sub['count']}次中命中{sub['hit']}次触发{sub['level']}告警"
            f"，间隔{sub['interval']}s"
        )
    return f"{mode_str}：{'；'.join(parts) if parts else '无规则'}"


def extract_rule(data: dict) -> dict:
    metric = data["metricConfig"]

    return {
        "id": data["id"],
        "name": data["name"],
        "status": data.get("status") == 1,
        "bizLine": data["bizLine"],
        "prdLine": data["prdLine"],
        "app": data["app"],
        "datasource": data["datasource"],
        "datasourceId": data["datasourceId"],
        "expression": metric["expression"],
        "step": metric["step"],
        "offset": metric["offset"],
        "ruleConfig": summarize_rule_config(data["ruleConfig"]),
    }


def main():
    if len(sys.argv) != 2:
        print("用法: python get_alarm_pql_rule.py <rule_id>", file=sys.stderr)
        sys.exit(1)

    try:
        rule_id = int(sys.argv[1])
    except ValueError:
        print(f"错误: rule_id 必须为整数，收到 '{sys.argv[1]}'", file=sys.stderr)
        sys.exit(1)

    try:
        resp = fetch_rule(rule_id)
    except urllib.error.URLError as e:
        print(f"请求失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not resp.get("success"):
        print(f"API 返回失败: {resp.get('message')}", file=sys.stderr)
        sys.exit(1)

    data = resp.get("data")
    if not data:
        print("API 返回数据为空", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(extract_rule(data), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
