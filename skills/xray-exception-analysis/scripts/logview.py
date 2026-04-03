#!/usr/bin/env python3
"""
Logview 调用链详情查询脚本

根据 CAT messageId 查询完整的请求调用链（消息树），输出原始 JSON 供分析。

接口: GET https://xray-ai.devops.xiaohongshu.com/open/skill/application/r/logview/{messageId}/json

messageId 格式: Domain-index-timestamp-seq
  例如: MyApp-0-1700000000-0

data.code 含义:
  200  - 成功
  1003 - 数据缺失（在保留期内未找到）
  1004 - 数据已过期归档

用法示例:
  python3 logview.py --message-id MyApp-0-1700000000-0
"""

import argparse
import json
import sys
import urllib.error
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
        description="Logview 调用链详情查询 — GET /open/skill/application/r/logview/{messageId}/json"
    )
    parser.add_argument("--message-id", required=True, help="CAT messageId")
    args = parser.parse_args()

    url = f"{BASE_URL}/open/skill/application/r/logview/{args.message_id}/json"
    print(f"[INFO] 调用 logview: messageId={args.message_id}", file=sys.stderr)
    resp = do_get(url)

    outer_code = resp.get("code", -1)
    if outer_code != 0:
        print(
            f"[WARN] 接口返回 code={outer_code}, msg={resp.get('msg', '')}",
            file=sys.stderr,
        )

    # 输出完整 JSON 供 Codewiz 分析
    print(json.dumps(resp, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
