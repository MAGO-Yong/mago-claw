#!/usr/bin/env python3
"""
查询 Xray 告警事件详情。

根据事件 ID 获取告警事件的完整信息，包括基本字段、操作记录、告警详情。

示例：
  %(prog)s 171238413
  %(prog)s 171238413 --show-link
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://xray-ai.devops.xiaohongshu.com/open/skill/xray-proxy/ac/event"


def fetch(event_id: int) -> dict:
    url = f"{API_URL}/{event_id}"
    req = urllib.request.Request(
        url,
        method="GET",
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


def aggregate_alarm_details(ops: list, show_link: bool) -> dict:
    alarm_ops = [op for op in ops if op.get("type") == 0]

    if not alarm_ops:
        return {}

    machines = set()
    current_values = []
    trigger_rules = set()
    first_trigger_time = None
    last_restore_time = None
    links = {}

    first_op = alarm_ops[0]
    content = first_op.get("content", {})
    name = content.get("名称")
    metric = content.get("监控项")

    for op in alarm_ops:
        content = op.get("content", {})
        machine = content.get("机器")
        if machine:
            machines.add(machine)

        current_value = content.get("当前值")
        if current_value:
            current_values.append(
                {
                    "machine": machine,
                    "value": current_value,
                    "trigger_time": op.get("create_time"),
                    "restore_time": op.get("restore_time"),
                }
            )

        rule = content.get("触发规则")
        if rule:
            trigger_rules.update(rule if isinstance(rule, list) else [rule])

        if op.get("create_time"):
            if not first_trigger_time or op["create_time"] < first_trigger_time:
                first_trigger_time = op["create_time"]
        if op.get("restore_time"):
            if not last_restore_time or op["restore_time"] > last_restore_time:
                last_restore_time = op["restore_time"]

        if not links and op.get("link"):
            links = op["link"]

    result = {
        "name": name,
        "metric": metric,
        "trigger_rules": list(trigger_rules),
        "affected_machines": sorted(machines),
        "machine_count": len(machines),
        "first_trigger_time": first_trigger_time,
        "last_restore_time": last_restore_time,
        "sample_values": current_values[:10],
        "total_samples": len(current_values),
    }

    if show_link:
        result["links"] = links

    return result


def format_event_detail(data: dict, show_link: bool) -> dict:
    event = data.get("event", {})
    ops = event.get("ops", [])

    basic = {
        "source": event.get("source"),
        "prdline": event.get("product_line"),
        "bizline": event.get("biz"),
        "app": event.get("app"),
        "name": event.get("e_name"),
        "rule_id": event.get("rule_id"),
        "level": f"P{event['level']}" if event.get("level") is not None else None,
        "trigger_time": event.get("trigger_time"),
        "operate_time": event.get("operate_time"),
        "restore_time": event.get("restore_time"),
    }

    operation_records = []
    for op in ops:
        if op.get("type") == 10:
            record = {
                "operator": op.get("op"),
                "user_name": op.get("user_name"),
                "trigger_time": op.get("trigger_time"),
                "create_time": op.get("create_time"),
            }
            if show_link:
                record["links"] = op.get("link", {})
            operation_records.append(record)

    alarm_details = aggregate_alarm_details(ops, show_link)

    return {
        "basic": basic,
        "operations": operation_records,
        "alarm_details": alarm_details,
    }


def main():
    parser = argparse.ArgumentParser(
        description="查询 Xray 告警事件详情。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  %(prog)s 171238413\n"
            "  %(prog)s 171238413 --show-link\n"
            "\n"
            "输出字段：\n"
            "  - basic: 基本信息（source/prdline/bizline/app/name/rule_id/level/trigger_time/operate_time/restore_time）\n"
            "  - operations: 操作记录\n"
            "  - alarm_details: 告警详情（聚合信息、受影响机器、当前值等）\n"
            "\n"
            "选项：\n"
            "  --show-link: 输出中包含快捷链接字段（默认不包含）"
        ),
    )
    parser.add_argument(
        "event_id",
        type=int,
        metavar="EVENT_ID",
        help="告警事件 ID",
    )
    parser.add_argument(
        "--show-link",
        action="store_true",
        help="输出中包含快捷链接字段",
    )
    args = parser.parse_args()

    resp = fetch(args.event_id)

    if resp.get("code") != 200:
        print(
            f"API 返回失败: code={resp.get('code')} msg={resp.get('msg')}",
            file=sys.stderr,
        )
        sys.exit(1)

    data = resp.get("data")
    if data is None:
        print("API 返回数据为空", file=sys.stderr)
        sys.exit(1)

    result = format_event_detail(data, args.show_link)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
