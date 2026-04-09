#!/usr/bin/env python3
"""
get_raw_slow_log.py — 采集原机慢查询日志

接口（优先）：POST /dms-api/ai-api/v1/mysql/meta_data/get_raw_slow_log
接口（兜底）：POST /dms-api/open-claw/meta-data/mysql/get-raw-slow-log
认证：DMS_AI_TOKEN（v1） / DMS_CLAW_TOKEN（open-claw）

注意：start_time / end_time 为 UTC 时间，时间窗口 ≤ 10 分钟

用法：
  python3 get_raw_slow_log.py \
      --cluster <cluster_name> --hostname <vm_name> \
      --start "2026-03-25 06:00:00" --end "2026-03-25 06:10:00" \
      [--db <db_name>] [--min_query_time 1.0] [--limit 200] \
      [--output <dir>] [--run_id <id>]
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
from common.dms_client import (
    AI_TOKEN, AI_V1_PREFIX, OPEN_CLAW_PREFIX, CLAW_TOKEN,
    _AI_HEADERS, _http_post, call_with_fallback,
)

TOKEN = CLAW_TOKEN


def fetch_slow_log(
    cluster_name: str,
    hostname: str,
    start_time: str,
    end_time: str,
    db_name: str = "",
    min_query_time: float = 1.0,
    limit: int = 200,
) -> dict:
    payload = {
        "cluster_name": cluster_name,
        "hostname": hostname,
        "start_time": start_time,
        "end_time": end_time,
        "min_query_time": min_query_time,
        "limit": limit,
    }
    if db_name:
        payload["db_name"] = db_name

    def _v1():
        return _http_post(
            f"{AI_V1_PREFIX}/mysql/meta_data/get_raw_slow_log",
            payload,
            _AI_HEADERS,
            timeout=60,
        )

    def _old():
        return _http_post(
            f"{OPEN_CLAW_PREFIX}/meta-data/mysql/get-raw-slow-log",
            payload,
            {"dms-claw-token": TOKEN},
            timeout=60,
        )

    try:
        return call_with_fallback(_v1, _old, "[get_raw_slow_log]")
    except Exception as e:
        raise RuntimeError(f"[get_raw_slow_log] 请求失败：{e}")


def main():
    parser = argparse.ArgumentParser(description="采集原机慢查询日志")
    parser.add_argument("--cluster", required=True, help="集群名称")
    parser.add_argument("--hostname", required=True, help="实例 hostname（vm_name）")
    parser.add_argument("--start", required=True, help="开始时间 UTC，格式：2026-03-25 06:00:00")
    parser.add_argument("--end", required=True, help="结束时间 UTC，格式：2026-03-25 06:10:00")
    parser.add_argument("--db", default="", help="数据库名称（可选，过滤）")
    parser.add_argument("--min_query_time", type=float, default=1.0, help="最小慢查询时间（秒），默认 1.0")
    parser.add_argument("--limit", type=int, default=200, help="明细条数上限，默认 200")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    args = parser.parse_args()

    if not AI_TOKEN and not TOKEN:
        print("[get_raw_slow_log] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    try:
        result = fetch_slow_log(
            args.cluster, args.hostname, args.start, args.end,
            args.db, args.min_query_time, args.limit,
        )
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    output_str = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output and args.run_id:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        out_file = raw_dir / "get_raw_slow_log.json"
        out_file.write_text(output_str, encoding="utf-8")
        print(f"[get_raw_slow_log] ✅ 已写入 {out_file}", file=sys.stderr)

    print(output_str)

    # 打印摘要到 stderr
    data = result.get("data", {})
    summary = data.get("summary", {})
    total = summary.get("total_slow_queries", "?")
    print(f"[get_raw_slow_log] 慢查询总数：{total}", file=sys.stderr)


if __name__ == "__main__":
    main()
