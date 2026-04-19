#!/usr/bin/env python3
"""
错慢请求采样 MessageId 批量查询脚本

根据服务名、接口 type/name、时间范围，批量获取采样 messageId 列表。

接口: GET https://xray-ai.devops.xiaohongshu.com/open/skill/application/r/t/sample/batchIds

type 参数速查:
  Service        - RPC 接口（服务端被调用），name 示例: UserService.getUserById
  Http           - HTTP 接口，name 示例: /api/v1/user/info
  Call           - RPC 客户端调用，name 示例: UserService.getUserById
  Redis.<集群名> - Redis 操作，name 示例: GET / SET
  SQL.<操作类型> - MySQL 操作，name 示例: user.select（操作类型如 Conn/shopping_cart/Sequence 等）

用法示例:
  python3 sample.py \\
    --app your-service \\
    --type Service --name UserService.getUserById \\
    --start 1700000000 --end 1700003600 \\
    --sample-type fail \\
    --limit 10
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://xray-ai.devops.xiaohongshu.com"


def do_get(url: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[ERROR] HTTP {e.code}: {e.reason}", file=sys.stderr)
        print(f"[ERROR] 响应体: {body[:500]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 请求失败: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="错慢请求采样 MessageId — GET /open/skill/application/r/t/sample/batchIds"
    )
    parser.add_argument("--app", required=True, help="服务 appkey")
    parser.add_argument(
        "--type",
        required=True,
        dest="type",
        help="Transaction 类型（Service/Http/Call/SQL.<操作类型>/Redis.<集群名> 等）",
    )
    parser.add_argument("--name", default=None, help="接口名称（可选，为空时查该 type 下聚合）")
    parser.add_argument("--ip", default="All", help="机器 IP，默认 All")
    parser.add_argument("--zone", default="All", help="机房，默认 All（全机房）")
    parser.add_argument("--start", required=True, type=int, help="开始时间（秒级时间戳）")
    parser.add_argument("--end", required=True, type=int, help="结束时间（秒级时间戳）")
    parser.add_argument(
        "--sample-type",
        required=True,
        choices=["fail", "longest", "success"],
        help="采样类型: fail（批量失败请求）/ longest（耗时最长）/ success（最新成功）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="最大返回条数（仅 fail 类型有效，默认 10）",
    )
    args = parser.parse_args()

    params = [
        f"app={urllib.parse.quote(args.app)}",
        f"ip={urllib.parse.quote(args.ip)}",
        f"startTime={args.start}",
        f"endTime={args.end}",
        f"type={urllib.parse.quote(args.type)}",
        f"sampleType={urllib.parse.quote(args.sample_type)}",
        f"limit={args.limit}",
    ]
    if args.name:
        params.append(f"name={urllib.parse.quote(args.name)}")
    params.append(f"zone={urllib.parse.quote(args.zone)}")

    url = f"{BASE_URL}/open/skill/application/r/t/sample/batchIds?" + "&".join(params)
    print(
        f"[INFO] 调用 /sample/batchIds: app={args.app}, type={args.type}, name={args.name}, sampleType={args.sample_type}, limit={args.limit}",
        file=sys.stderr,
    )
    resp = do_get(url)

    success = resp.get("success", False)
    if not success:
        print(
            f"[WARN] 接口返回 success=false, message={resp.get('message', '')}",
            file=sys.stderr,
        )

    message_ids = resp.get("data") or []
    if not message_ids:
        print("## 结果\n\n未获取到采样 messageId（该时段内无对应类型的采样记录）")
        return

    print(f"## 采样 MessageId 列表（共 {len(message_ids)} 条）\n")
    for i, mid in enumerate(message_ids, 1):
        print(f"{i}. `{mid}`")

    print("\n可使用以下命令查询 Logview（以第一条为例）：\n")
    print("```bash")
    print(f"python3 logview.py --message-id {message_ids[0]}")
    print("```")


if __name__ == "__main__":
    main()
