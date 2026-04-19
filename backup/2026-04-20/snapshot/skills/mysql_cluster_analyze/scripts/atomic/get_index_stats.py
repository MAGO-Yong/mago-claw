#!/usr/bin/env python3
"""
get_index_stats.py — 查询索引统计与区分度

接口（优先）：GET /dms-api/ai-api/v1/mysql/meta_data/get_index_stats
接口（兜底）：GET /dms-api/open-claw/meta-data/mysql/get-index-stats
认证：DMS_AI_TOKEN（v1） / DMS_CLAW_TOKEN（open-claw）

返回：索引名、列名、cardinality 等，结合 table_rows 可计算区分度

用法：
  python3 get_index_stats.py \
      --cluster <cluster_name> --db <db_name> --table <table_name> \
      --connector "normal:10.0.0.1:3306" \
      [--index <index_name>] [--output <dir>] [--run_id <id>]
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


def fetch_index_stats(
    cluster_name: str,
    db_name: str,
    table_name: str,
    connector: str = "",
    index_name: str = "",
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
    if index_name:
        params["index_name"] = index_name

    qs = urllib.parse.urlencode(params)

    def _v1():
        return _http_get(
            f"{AI_V1_PREFIX}/mysql/meta_data/get_index_stats?{qs}",
            _AI_HEADERS,
            timeout=15,
        )

    def _old():
        return _http_get(
            f"{OPEN_CLAW_PREFIX}/meta-data/mysql/get-index-stats?{qs}",
            {"dms-claw-token": TOKEN},
            timeout=15,
        )

    try:
        return call_with_fallback(_v1, _old, "[get_index_stats]")
    except Exception as e:
        raise RuntimeError(f"[get_index_stats] 请求失败：{e}")


def calc_selectivity(index_data: list[dict], table_rows: int) -> list[dict]:
    """计算各索引区分度 = cardinality / table_rows"""
    results = []
    for row in index_data:
        cardinality = int(row.get("cardinality", 0) or 0)
        selectivity = round(cardinality / table_rows, 4) if table_rows > 0 else None
        risk = ""
        if selectivity is not None:
            if selectivity < 0.01:
                risk = "⚠️ 极低区分度（可能数据倾斜）"
            elif selectivity < 0.1:
                risk = "⚠️ 低区分度"
        results.append({**row, "selectivity": selectivity, "risk": risk})
    return results


def main():
    parser = argparse.ArgumentParser(description="查询索引统计与区分度")
    parser.add_argument("--cluster", required=True, help="集群名称")
    parser.add_argument("--db", required=True, help="数据库名称")
    parser.add_argument("--table", required=True, help="表名")
    parser.add_argument("--connector", default="", help="连接器，格式：normal:ip:port")
    parser.add_argument("--index", default="", help="索引名（可选，不传返回所有索引）")
    parser.add_argument("--node_role", default="slave", help="节点角色，默认 slave")
    parser.add_argument("--table_rows", type=int, default=0, help="表总行数（用于计算区分度）")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    args = parser.parse_args()

    if not AI_TOKEN and not TOKEN:
        print("[get_index_stats] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    try:
        result = fetch_index_stats(
            args.cluster, args.db, args.table,
            args.connector, args.index, args.node_role,
        )
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # 若传了 table_rows，附加区分度计算
    if args.table_rows > 0:
        data = result.get("data", [])
        if isinstance(data, list):
            result["data"] = calc_selectivity(data, args.table_rows)

    output_str = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output and args.run_id:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        out_file = raw_dir / f"index_stats_{args.table}.json"
        out_file.write_text(output_str, encoding="utf-8")
        print(f"[get_index_stats] ✅ 已写入 {out_file}", file=sys.stderr)

    print(output_str)

    # 打印风险项到 stderr
    data = result.get("data", [])
    if isinstance(data, list):
        risks = [r for r in data if r.get("risk")]
        if risks:
            print("[get_index_stats] 风险检测：", file=sys.stderr)
            for r in risks:
                print(
                    f"  {r['risk']} 索引={r.get('index_name')} "
                    f"列={r.get('column_name')} "
                    f"区分度={r.get('selectivity')}",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    main()
