#!/usr/bin/env python3
"""
错慢请求采样 MessageId 查询脚本

根据服务名、接口 type/name、时间范围，获取一个具有代表性的采样 messageId。

接口: GET https://xray.devops.xiaohongshu.com/openapi/application/r/t/sample

type 参数速查:
  Service   - RPC 接口（服务端被调用），name 示例: UserService.getUserById
  URL       - HTTP 接口，name 示例: /api/v1/user/info
  Call      - RPC 客户端调用，name 示例: UserService.getUserById
  Redis.<集群名> - Redis 操作，name 示例: GET / SET
  SQL       - MySQL 操作，name 示例: user.select

用法示例:
  python3 sample.py \\
    --app your-service \\
    --type Service --name UserService.getUserById \\
    --start 1700000000 --end 1700003600 \\
    --sample-type fail
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://xray.devops.xiaohongshu.com"


def make_headers() -> dict:
    return {
        "xray_ticket": "pass",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def do_get(url: str) -> dict:
    req = urllib.request.Request(url)
    for k, v in make_headers().items():
        req.add_header(k, v)
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
        description="错慢请求采样 MessageId — GET /openapi/application/r/t/sample"
    )
    parser.add_argument("--app", required=True, help="服务 appkey")
    parser.add_argument(
        "--type",
        required=True,
        dest="type",
        help="Transaction 类型（Service/URL/Call/SQL/Redis.<集群名> 等）",
    )
    parser.add_argument("--name", default=None, help="接口名称（可选，为空时查该 type 下聚合）")
    parser.add_argument("--ip", default="ALL", help="机器 IP，默认 ALL")
    parser.add_argument("--zone", default=None, help="机房（可选）")
    parser.add_argument("--start", required=True, type=int, help="开始时间（秒级时间戳）")
    parser.add_argument("--end", required=True, type=int, help="结束时间（秒级时间戳）")
    parser.add_argument(
        "--sample-type",
        required=True,
        choices=["fail", "longest", "success"],
        help="采样类型: fail（随机失败请求）/ longest（耗时最长）/ success（最新成功）",
    )
    args = parser.parse_args()

    params = [
        f"app={urllib.parse.quote(args.app)}",
        f"ip={urllib.parse.quote(args.ip)}",
        f"startTime={args.start}",
        f"endTime={args.end}",
        f"type={urllib.parse.quote(args.type)}",
        f"sampleType={urllib.parse.quote(args.sample_type)}",
    ]
    if args.name:
        params.append(f"name={urllib.parse.quote(args.name)}")
    if args.zone:
        params.append(f"zone={urllib.parse.quote(args.zone)}")

    url = f"{BASE_URL}/openapi/application/r/t/sample?" + "&".join(params)
    print(
        f"[INFO] 调用 /sample: app={args.app}, type={args.type}, name={args.name}, sampleType={args.sample_type}",
        file=sys.stderr,
    )
    resp = do_get(url)

    outer_code = resp.get("code", -1)
    if outer_code != 0:
        print(
            f"[WARN] 接口返回 code={outer_code}, msg={resp.get('msg', '')}",
            file=sys.stderr,
        )

    message_id = resp.get("data")
    if not message_id:
        print("## 结果\n\n未获取到采样 messageId（该时段内无对应类型的采样记录）")
        return

    print(f"## 采样 MessageId\n\n`{message_id}`\n")
    print("可使用以下命令查询 Logview：\n")
    print("```bash")
    print(f"python3 logview.py --message-id {message_id}")
    print("```")


if __name__ == "__main__":
    main()
