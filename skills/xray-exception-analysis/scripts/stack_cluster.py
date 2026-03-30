#!/usr/bin/env python3
"""
异常堆栈聚类分析脚本

对指定服务、时间范围内的一批异常类型进行聚类分析，返回每种异常的堆栈分布
（按出现比例降序），并附带关联的 messageId 列表。

接口: POST https://xray.devops.xiaohongshu.com/openapi/application/r/p/stack/cluster

用法示例:
  python3 stack_cluster.py \\
    --app your-service \\
    --start 1700000000 --end 1700003600 \\
    --exceptions java.util.concurrent.TimeoutException java.net.SocketTimeoutException
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

BASE_URL = "https://xray.devops.xiaohongshu.com"


def make_headers() -> dict:
    return {
        "xray_ticket": "pass",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def do_post(url: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in make_headers().items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_str = e.read().decode("utf-8", errors="replace")
        print(f"[ERROR] HTTP {e.code}: {e.reason}", file=sys.stderr)
        print(f"[ERROR] 响应体: {body_str[:500]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 请求失败: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="异常堆栈聚类分析 — POST /openapi/application/r/p/stack/cluster"
    )
    parser.add_argument("--app", required=True, help="服务 appkey")
    parser.add_argument("--start", required=True, type=int, help="开始时间（秒级时间戳）")
    parser.add_argument("--end", required=True, type=int, help="结束时间（秒级时间戳）")
    parser.add_argument("--exceptions", required=True, nargs="+", help="异常类全名列表，空格分隔")
    args = parser.parse_args()

    url = f"{BASE_URL}/openapi/application/r/p/stack/cluster"
    body = {
        "app": args.app,
        "start": args.start,
        "end": args.end,
        "exceptions": args.exceptions,
    }

    print(
        f"[INFO] 调用 stack/cluster: app={args.app}, exceptions={args.exceptions}",
        file=sys.stderr,
    )
    resp = do_post(url, body)

    outer_code = resp.get("code", -1)
    if outer_code != 0:
        print(
            f"[WARN] 接口返回 code={outer_code}, msg={resp.get('msg', '')}",
            file=sys.stderr,
        )

    data = resp.get("data", {}) or {}
    exceptions = data.get("exceptions", [])

    if not exceptions:
        print("## 结果\n\n无聚类数据（该时间段内无异常堆栈记录）")
        return

    lines = ["## 异常堆栈聚类分析结果\n"]
    for exc in exceptions:
        exc_name = exc.get("exception", "?")
        tags = exc.get("tags", [])
        lines.append(f"### {exc_name}\n")
        if not tags:
            lines.append("_无聚类堆栈_\n")
            continue
        for i, tag in enumerate(tags, 1):
            count = tag.get("count", 0)
            ratio = tag.get("ratio", 0)
            stack = tag.get("stack", "")
            msg_ids = tag.get("messageIds", [])
            lines.append(f"**堆栈 #{i}** — 出现 {count} 次，占比 {ratio * 100:.1f}%\n")
            if stack:
                lines.append("```")
                lines.append(stack.strip())
                lines.append("```\n")
            else:
                lines.append("_（堆栈详情暂无）_\n")
            if msg_ids:
                lines.append(f"关联 messageId（共 {len(msg_ids)} 个）:")
                for mid in msg_ids[:5]:
                    lines.append(f"  - `{mid}`")
                if len(msg_ids) > 5:
                    lines.append(f"  - ... 共 {len(msg_ids)} 个")
            else:
                lines.append("_（无关联 messageId）_")
            lines.append("")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
