#!/usr/bin/env python3
"""
查询 Xray 告警事件记录。

支持按 app、时间范围、接收人、接收群等维度过滤，返回格式化后的告警事件列表。

示例：
  %(prog)s --apps victoriametrics --start "2026-03-26 09:00:00" --end "2026-03-26 21:00:00"
  %(prog)s --apps "victoriametrics,xrayaiagent" --receive-users "foo@xiaohongshu.com"
  %(prog)s --apps victoriametrics --start "2026-03-26 09:00:00" --end "2026-03-26 21:00:00" --page 2 --page-size 50
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://xray.devops.xiaohongshu.com/api/ac/event"
ST_ID = "xray_overview"
ST_SECRET = "3dd67e04c899313aae19bc99c0a5c551"


def format_duration(seconds: int) -> str:
    """将秒数转换为人类可读格式，如 '2小时5分30秒'。"""
    if seconds is None:
        return None
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}秒"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}分{secs}秒" if secs else f"{minutes}分"
    hours, mins = divmod(minutes, 60)
    parts = [f"{hours}小时"]
    if mins:
        parts.append(f"{mins}分")
    if secs:
        parts.append(f"{secs}秒")
    return "".join(parts)


def fetch(params: dict) -> dict:
    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    url = f"{API_URL}?{query_string}"
    req = urllib.request.Request(
        url,
        headers={
            "x_authorization_st_id": ST_ID,
            "x_authorization_st_secret": ST_SECRET,
        },
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


def format_event(e: dict) -> dict:
    return {
        "id": e.get("id"),
        "rule_id": e.get("rule_id"),
        "rule_name": e.get("e_name"),
        "app": e.get("app"),
        "level": f"P{e.get('level')}" if e.get("level") is not None else None,
        "trigger_time": e.get("trigger_time"),
        "restore_time": e.get("restore_time"),
        "duration": format_duration(e.get("duration")),
        "reacted": e.get("reacted"),
        "receive_users": e.get("receive_users") or [],
        "receive_user_names": e.get("receive_user_names") or [],
        "receive_chats": e.get("receive_chats") or [],
        "receive_chat_names": e.get("receive_chat_names") or [],
    }


def main():
    parser = argparse.ArgumentParser(
        description="查询 Xray 告警事件记录。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            '  %(prog)s --apps base.obs.victoriametrics --start "2026-03-26 09:00:00" --end "2026-03-26 21:00:00"\n'
            '  %(prog)s --apps "base.obs.xrayaiagent,base.obs.victoriametrics" --receive-users "foo@xiaohongshu.com"\n'
            "  %(prog)s --apps base.obs.victoriametrics --page 2 --page-size 50\n"
            "\n"
            "输出字段：id / rule_id / rule_name / app / level / trigger_time / restore_time / duration / "
            "reacted / receive_users / receive_user_names / receive_chats / receive_chat_names"
        ),
    )
    parser.add_argument(
        "--apps",
        metavar="APPS",
        default="",
        help=(
            "app 名称，格式为服务树路径（如 base.obs.xrayaiagent），"
            "多个用英文逗号分隔（如 base.obs.xrayaiagent,base.obs.victoriametrics）"
        ),
    )
    parser.add_argument(
        "--start",
        metavar="DATETIME",
        default="",
        help='查询起始时间，格式 "YYYY-MM-DD HH:MM:SS"',
    )
    parser.add_argument(
        "--end",
        metavar="DATETIME",
        default="",
        help='查询结束时间，格式 "YYYY-MM-DD HH:MM:SS"',
    )
    parser.add_argument(
        "--receive-users",
        metavar="EMAILS",
        default="",
        help="接收人邮箱，多个用英文逗号分隔（如 foo@xiaohongshu.com,bar@xiaohongshu.com）",
    )
    parser.add_argument(
        "--receive-chats",
        metavar="CHAT_IDS",
        default="",
        help="接收群 ID，多个用英文逗号分隔（如 CHAT123,CHAT456）",
    )
    parser.add_argument(
        "--page", type=int, default=1, metavar="N", help="页码，从 1 开始（默认：1）"
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=20,
        metavar="N",
        help="每页条数（默认：20）",
    )
    args = parser.parse_args()

    if args.page < 1:
        parser.error("--page 必须 >= 1")
    if args.page_size < 1:
        parser.error("--page-size 必须 >= 1")

    filter_args = [
        args.apps,
        args.start,
        args.end,
        args.receive_users,
        args.receive_chats,
    ]
    if not any(filter_args):
        parser.error(
            "至少需要指定一个过滤条件：--apps、--start、--end、--receive-users、--receive-chats\n"
            '  示例：--apps base.obs.xrayaiagent --start "2026-03-26 09:00:00" --end "2026-03-26 21:00:00"'
        )

    if args.apps:
        bad = [a.strip() for a in args.apps.split(",") if a.strip().count(".") < 2]
        if bad:
            parser.error(
                f"--apps 格式不正确：{', '.join(bad)}\n"
                "  app 须为服务树完整路径，格式：<产品线>.<业务线>.<app>（如 base.obs.xrayaiagent）\n"
                "  多个 app 用英文逗号分隔：base.obs.xrayaiagent,base.obs.victoriametrics"
            )

    params = {
        "page": args.page,
        "page_size": args.page_size,
        "pdls": "",
        "bizs": "",
        "apps": args.apps,
        "trigger_time_gt": args.start,
        "trigger_time_lt": args.end,
        "source": "",
        "alert_level": "",
        "mark": "",
        "tags": "",
        "receive_users": args.receive_users,
        "receive_chats": args.receive_chats,
        "platform": "",
    }

    resp = fetch(params)

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

    total = data.get("total", 0)
    rows = [format_event(e) for e in data.get("rows") or []]

    result = {
        "query": {
            "apps": args.apps or "(不限)",
            "time_range": {
                "start": args.start or "(不限)",
                "end": args.end or "(不限)",
            },
            "receive_users": args.receive_users or "(不限)",
            "receive_chats": args.receive_chats or "(不限)",
        },
        "pagination": {
            "page": data.get("page"),
            "page_size": data.get("page_size"),
            "total_page": data.get("total_page"),
            "total_events": total,
        },
        "events": rows,
    }

    if total == 0:
        result["message"] = "未找到符合条件的告警事件，请确认过滤条件是否正确"

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
