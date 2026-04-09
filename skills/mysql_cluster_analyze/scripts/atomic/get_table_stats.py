#!/usr/bin/env python3
"""
get_table_stats.py — 查询表基础统计信息

接口（优先）：GET /dms-api/ai-api/v1/mysql/meta_data/get_table_stats
接口（兜底）：GET /dms-api/open-claw/meta-data/mysql/get-table-stats
认证：DMS_AI_TOKEN（v1） / DMS_CLAW_TOKEN（open-claw）

返回：table_rows、data_length、index_length、update_time 等

用法：
  python3 get_table_stats.py \
      --cluster <cluster_name> --db <db_name> --table <table_name> \
      --connector "normal:10.0.0.1:3306" \
      [--output <dir>] [--run_id <id>]
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
from common.dms_client import (
    AI_TOKEN, AI_V1_PREFIX, OPEN_CLAW_PREFIX, CLAW_TOKEN,
    _AI_HEADERS, _http_get, call_with_fallback,
)

TOKEN = CLAW_TOKEN


def fetch_table_stats(
    cluster_name: str,
    db_name: str,
    table_name: str,
    connector: str = "",
    node_role: str = "slave",
) -> dict:
    params: dict = {
        "cluster_name": cluster_name,
        "db_name": db_name,
        "table_name": table_name,
        "node_role": node_role,
    }
    if connector:
        params["connector"] = connector

    qs = urllib.parse.urlencode(params)

    def _v1():
        return _http_get(
            f"{AI_V1_PREFIX}/mysql/meta_data/get_table_stats?{qs}",
            _AI_HEADERS,
            timeout=15,
        )

    def _old():
        return _http_get(
            f"{OPEN_CLAW_PREFIX}/meta-data/mysql/get-table-stats?{qs}",
            {"dms-claw-token": TOKEN},
            timeout=15,
        )

    try:
        return call_with_fallback(_v1, _old, "[get_table_stats]")
    except Exception as e:
        raise RuntimeError(f"[get_table_stats] 请求失败：{e}")


def main():
    parser = argparse.ArgumentParser(description="查询表基础统计信息")
    parser.add_argument("--cluster", required=True, help="集群名称")
    parser.add_argument("--db", required=True, help="数据库名称")
    parser.add_argument("--table", required=True, help="表名")
    parser.add_argument("--connector", default="", help="连接器，格式：normal:ip:port")
    parser.add_argument("--node_role", default="slave", help="节点角色，默认 slave")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    args = parser.parse_args()

    if not AI_TOKEN and not TOKEN:
        print("[get_table_stats] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    try:
        result = fetch_table_stats(
            args.cluster, args.db, args.table, args.connector, args.node_role
        )
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    output_str = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output and args.run_id:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        out_file = raw_dir / f"table_stats_{args.table}.json"
        out_file.write_text(output_str, encoding="utf-8")
        print(f"[get_table_stats] ✅ 已写入 {out_file}", file=sys.stderr)

    print(output_str)

    # 打印关键指标到 stderr
    data = result.get("data", [])
    if data:
        row = data[0] if isinstance(data, list) else data
        table_rows = row.get("table_rows", "?")
        data_mb = round(int(row.get("data_length", 0)) / 1024 / 1024, 1)
        print(f"[get_table_stats] table_rows={table_rows:,}  data={data_mb}MB", file=sys.stderr)


if __name__ == "__main__":
    main()
