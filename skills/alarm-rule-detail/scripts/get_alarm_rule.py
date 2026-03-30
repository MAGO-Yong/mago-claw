#!/usr/bin/env python3
import json
import sys
import urllib.error
import urllib.request

API_URL = "http://xray.devops.xiaohongshu.com/openapi/alarm/rule/detail"
API_SIT_URL = "http://xray.devops.sit.xiaohongshu.com/openapi/alarm/rule/detail"
TICKET = "pass"


def fetch_rule(rule_id: int, bind_id: int | None = None) -> dict:
    url = f"{API_URL}?id={rule_id}&source=rule"
    if bind_id is not None:
        url += f"&bindId={bind_id}"
    req = urllib.request.Request(url, headers={"xray_ticket": TICKET})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def summarize_sub_conditions(sub_conditions: list) -> str:
    parts = []
    for sc in sub_conditions:
        parts.append(
            f"{sc['minute']}min内{sc['type']}{sc['operator']}{sc['text']}命中{sc['hit']}次"
        )
    return "；".join(parts) if parts else "无子条件"


def summarize_condition(cond: dict) -> str:
    time_ranges = "、".join(
        f"{tr['startTime']}-{tr['endTime']}" for tr in cond.get("timeRanges", [])
    )
    sub = summarize_sub_conditions(cond.get("subConditions") or [])
    return f"时间段:{time_ranges} | {sub}"


def summarize_conditions(conditions: list) -> list:
    result = []
    for c in conditions:
        metric = c.get("metric", {})
        metric_str = metric.get("value", "未知指标")
        unit = metric.get("unit") or ""

        dimensions = c.get("dimensions", [])
        dim_parts = []
        for d in dimensions:
            excludes = d.get("excludes", [])
            values = d.get("values", [])
            dim_str = f"{d.get('name', '')}={','.join(values)}"
            if excludes:
                dim_str += f"(排除:{','.join(excludes)})"
            dim_parts.append(dim_str)

        funcs = c.get("funcs", [])
        group_by = next((f["groupBys"] for f in funcs if f.get("name") == "groupBy"), [])

        cond_summaries = [summarize_condition(cc) for cc in c.get("conditions", [])]

        result.append(
            {
                "metric": metric_str + (f"({unit})" if unit else ""),
                "dimensions": dim_parts,
                "groupBy": group_by,
                "conditions": cond_summaries,
            }
        )
    return result


def extract_rule(data: dict) -> dict:
    attr = data.get("attribute") or {}

    return {
        "id": data["id"],
        "name": data["name"],
        "status": data.get("status") == 1,
        "level": data.get("level"),
        "datasourceType": data.get("datasourceType"),
        "alarmTarget": data.get("alarmTarget"),
        "alarmTargetType": data.get("alarmTargetType"),
        "step": attr.get("step"),
        "pending": attr.get("pending"),
        "recover": attr.get("recover"),
        "silentTime": attr.get("silentTime"),
        "conditions": summarize_conditions(data.get("conditions") or []),
    }


def main():
    if len(sys.argv) != 2:
        print("用法: python get_alarm_rule.py <rule_id>", file=sys.stderr)
        print("       rule_id 格式: <id> 或 <ruleId>_<bindId> (如: 5_16)", file=sys.stderr)
        sys.exit(1)

    rule_arg = sys.argv[1]
    bind_id = None

    if "_" in rule_arg:
        parts = rule_arg.split("_")
        if len(parts) != 2:
            print(
                f"错误: rule_id 格式不正确，应为 <id> 或 <ruleId>_<bindId>，收到 '{rule_arg}'",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            rule_id = int(parts[0])
            bind_id = int(parts[1])
        except ValueError:
            print(f"错误: rule_id 和 bind_id 必须为整数，收到 '{rule_arg}'", file=sys.stderr)
            sys.exit(1)
        if rule_id <= 0 or bind_id <= 0:
            print(f"错误: rule_id 和 bind_id 必须为正整数，收到 '{rule_arg}'", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            rule_id = int(rule_arg)
        except ValueError:
            print(f"错误: rule_id 必须为整数，收到 '{rule_arg}'", file=sys.stderr)
            sys.exit(1)
        if rule_id <= 0:
            print(f"错误: rule_id 必须为正整数，收到 '{rule_arg}'", file=sys.stderr)
            sys.exit(1)

    try:
        resp = fetch_rule(rule_id, bind_id)
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
