#!/usr/bin/env python3
"""
explain_sql.py — 执行 EXPLAIN 分析 SQL 执行计划

接口（优先）：POST /dms-api/ai-api/v1/mysql/meta_data/explain_sql
接口（兜底）：POST /dms-api/open-claw/meta-data/mysql/explain-sql
认证：DMS_AI_TOKEN（v1） / DMS_CLAW_TOKEN（open-claw）

用法：
  python3 explain_sql.py \
      --cluster <cluster_name> --db <db_name> \
      --sql "SELECT * FROM t WHERE id=1" \
      --connector "normal:10.0.0.1:3306" \
      [--output <dir>] [--run_id <id>] [--label <label>]
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
from common.dms_client import (
    AI_V1_PREFIX, OPEN_CLAW_PREFIX, CLAW_TOKEN,
    _AI_HEADERS, _http_post, call_with_fallback,
)

TOKEN = CLAW_TOKEN

# EXPLAIN type 风险等级（越靠后越差）
_TYPE_RISK = ["system", "const", "eq_ref", "ref", "range", "index", "ALL"]


def fetch_explain(cluster_name: str, db_name: str, sql: str, connector: str = "") -> dict:
    payload: dict = {"cluster_name": cluster_name, "db_name": db_name, "sql": sql}
    if connector:
        payload["connector"] = connector

    def _v1():
        return _http_post(
            f"{AI_V1_PREFIX}/mysql/meta_data/explain_sql",
            payload,
            _AI_HEADERS,
            timeout=30,
        )

    def _old():
        return _http_post(
            f"{OPEN_CLAW_PREFIX}/meta-data/mysql/explain-sql",
            payload,
            {"dms-claw-token": TOKEN},
            timeout=30,
        )

    try:
        return call_with_fallback(_v1, _old, "[explain_sql]")
    except Exception as e:
        raise RuntimeError(f"[explain_sql] 请求失败：{e}")


def flag_issues(rows: list[dict]) -> list[str]:
    """检测 EXPLAIN 结果中的风险项"""
    issues = []
    for row in rows:
        table = row.get("table", "?")
        scan_type = row.get("type", "")
        key = row.get("key")
        extra = row.get("Extra", "") or ""
        est_rows = row.get("rows", 0)

        if scan_type == "ALL":
            issues.append(f"⚠️  表 `{table}` 全表扫描（type=ALL），估算扫描行数 {est_rows:,}")
        elif scan_type == "index":
            issues.append(f"⚠️  表 `{table}` 全索引扫描（type=index），效率较低")

        if not key:
            issues.append(f"⚠️  表 `{table}` 未使用任何索引")

        if "Using filesort" in extra:
            issues.append(f"⚠️  表 `{table}` 存在文件排序（Using filesort）")
        if "Using temporary" in extra:
            issues.append(f"⚠️  表 `{table}` 使用临时表（Using temporary）")

    return issues


def main():
    parser = argparse.ArgumentParser(description="执行 EXPLAIN 分析")
    parser.add_argument("--cluster", required=True, help="集群名称")
    parser.add_argument("--db", required=True, help="数据库名称")
    parser.add_argument("--sql", required=True, help="要 EXPLAIN 的 SQL")
    parser.add_argument("--connector", default="", help="连接器，格式：normal:ip:port")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    parser.add_argument("--label", default="explain", help="输出文件名标签，默认 explain")
    args = parser.parse_args()

    from common.dms_client import AI_TOKEN
    if not AI_TOKEN and not TOKEN:
        print("[explain_sql] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    try:
        result = fetch_explain(args.cluster, args.db, args.sql, args.connector)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    output_str = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output and args.run_id:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        safe_label = re.sub(r"[^a-zA-Z0-9_-]", "_", args.label)
        out_file = raw_dir / f"explain_{safe_label}.json"
        out_file.write_text(output_str, encoding="utf-8")
        print(f"[explain_sql] ✅ 已写入 {out_file}", file=sys.stderr)

    print(output_str)

    # 打印风险检测结果到 stderr
    rows = result.get("data", [])
    if isinstance(rows, list):
        issues = flag_issues(rows)
        if issues:
            print("[explain_sql] 风险检测：", file=sys.stderr)
            for issue in issues:
                print(f"  {issue}", file=sys.stderr)
        else:
            print("[explain_sql] ✅ 未发现明显风险", file=sys.stderr)


if __name__ == "__main__":
    main()
