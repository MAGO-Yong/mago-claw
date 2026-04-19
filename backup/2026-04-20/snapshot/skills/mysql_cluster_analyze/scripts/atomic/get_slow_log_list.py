#!/usr/bin/env python3
"""
get_slow_log_list.py — 从 ClickHouse 查询慢日志聚合列表

接口：GET /dms-api/v1/mysql/slow-query/slow-log-list
说明：从 CK 聚合表查询慢日志模板，按库/SQL模板聚合，支持分页。
      适用于快速定位哪个库/哪类 SQL 慢，时间范围不受限制。
      与 get-raw-slow-log（原机 SSH）互补：
        - 本接口：CK 聚合，快速宏观定位，无需 SSH
        - get-raw-slow-log：原机精确采集，≤10分钟窗口，需 SSH

Phase 0 专用模式（--phase0）：
  自动执行"全库分组聚合"，不传 db_name，取 page_size=200，
  按 DB 分组统计总量，并自动分类 SQL 类型（business / info_schema / dts），
  输出 _phase0_summary 字段供推理矩阵使用。

环境变量：
  DMS_BASE_URL   — DMS 基础地址，默认 https://dms.devops.xiaohongshu.com
  DMS_CLAW_TOKEN — open-claw token（必填）

用法：
  # 常规用法
  python3 get_slow_log_list.py \\
      --cluster <cluster_name> \\
      --start "2026-03-25 00:00:00" --end "2026-03-25 01:00:00" \\
      [--db <db_name>] [--page 1] [--page_size 20] \\
      [--output <dir>] [--run_id <id>]

  # Phase 0 分诊模式（推荐在 Phase 0 探测 A 中使用）
  python3 get_slow_log_list.py \\
      --cluster <cluster_name> \\
      --start "2026-03-26 14:00:00" --end "2026-03-26 15:03:32" \\
      --phase0 \\
      [--output <dir>] [--run_id <id>]
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
    AI_TOKEN, BASE_URL, AI_V1_PREFIX, CLAW_TOKEN,
    _AI_HEADERS, _http_get, call_with_fallback,
)

TOKEN = CLAW_TOKEN

# DTS Checksum SQL 特征（bit_xor + crc32 + concat_ws）
DTS_PATTERN = re.compile(r"bit_xor|crc32|concat_ws", re.IGNORECASE)
# information_schema 特征
INFO_SCHEMA_PATTERN = re.compile(r"information_schema", re.IGNORECASE)


def classify_sql(db_name: str, sql_template: str) -> str:
    """
    分类 SQL 类型：
      dts         — DTS Checksum（bit_xor/crc32/concat_ws）
      info_schema — 对 information_schema 库的查询（通常为 ORM/监控系统噪声）
      business    — 业务 SQL
    """
    if db_name == "information_schema" or INFO_SCHEMA_PATTERN.search(sql_template or ""):
        return "info_schema"
    if DTS_PATTERN.search(sql_template or ""):
        return "dts"
    return "business"


def fetch_slow_log_list(
    cluster_name: str,
    start_time: str,
    end_time: str,
    db_name: str = "",
    keyword: str = "",
    current_page: int = 1,
    page_size: int = 20,
    slow_log_count_sort: str = "desc",
) -> dict:
    params = {
        "cluster_name": cluster_name,
        "start_time": start_time,
        "end_time": end_time,
        "current_page": current_page,
        "page_size": page_size,
        "slow_log_count_sort": slow_log_count_sort,
    }
    if db_name:
        params["db_name"] = db_name
    if keyword:
        params["keyword"] = keyword

    qs = urllib.parse.urlencode(params)

    def _v1():
        return _http_get(
            f"{AI_V1_PREFIX}/mysql/slow_query/slow_log_list?{qs}",
            _AI_HEADERS,
            timeout=30,
        )

    def _old():
        return _http_get(
            f"{BASE_URL}/dms-api/v1/mysql/slow-query/slow-log-list?{qs}",
            {"dms-claw-token": TOKEN, "Content-Type": "application/json"},
            timeout=30,
        )

    try:
        return call_with_fallback(_v1, _old, "[get_slow_log_list]")
    except Exception as e:
        raise RuntimeError(f"[get_slow_log_list] 请求失败：{e}")


def build_phase0_summary(items: list, total: int) -> dict:
    """
    Phase 0 专用：对慢查询列表做量化分析 + SQL 分类。

    返回结构：
    {
      "total": 102231,          # 全部慢查询总量
      "level": "severe",        # none / light / moderate / severe
      "by_type": {
        "business":    {"count": 6,      "top_dbs": ["cat"]},
        "info_schema": {"count": 102225, "top_dbs": ["information_schema"]},
        "dts":         {"count": 0,      "top_dbs": []},
      },
      "business_ratio": 0.0,    # 业务SQL占比（0~1）
      "noise_dominated": True,  # info_schema > 90% → 背景噪声主导
      "dts_dominated": False,
      "top_items": [...],       # 前5条（按 count 降序）
      "risks": [...],           # 推理结论列表
    }
    """
    by_type: dict = {
        "business":    {"count": 0, "top_dbs": []},
        "info_schema": {"count": 0, "top_dbs": []},
        "dts":         {"count": 0, "top_dbs": []},
    }
    db_counts: dict = {}

    for item in items:
        db = item.get("dbName") or item.get("db_name") or ""
        sql = item.get("sqlTemplate") or item.get("sql_template") or item.get("digest") or ""
        cnt = item.get("count") or item.get("slowLogCount") or item.get("countSum") or 1

        sql_type = classify_sql(db, sql)
        by_type[sql_type]["count"] += cnt
        if db and db not in by_type[sql_type]["top_dbs"]:
            by_type[sql_type]["top_dbs"].append(db)

        db_counts[db] = db_counts.get(db, 0) + cnt

    # 如果 API 返回了 total，用 total；否则用 items 累加
    real_total = total if total and total > 0 else sum(
        by_type[t]["count"] for t in by_type
    )

    business_count = by_type["business"]["count"]
    info_count = by_type["info_schema"]["count"]
    dts_count = by_type["dts"]["count"]
    business_ratio = business_count / real_total if real_total > 0 else 0.0
    noise_dominated = (info_count / real_total > 0.9) if real_total > 0 else False
    dts_dominated = (dts_count / real_total > 0.5) if real_total > 0 else False

    # 量级分级
    if real_total == 0:
        level = "none"
    elif real_total < 100:
        level = "light"
    elif real_total < 10000:
        level = "moderate"
    else:
        level = "severe"

    # 推理风险
    risks = []
    if level == "none":
        risks.append("✅ CK 无慢查询记录，排除慢 SQL 为主因")
    elif level == "light":
        risks.append(f"🟡 慢查询量级轻微（{real_total} 条），告警可能已自愈")
    elif noise_dominated:
        risks.append(
            f"⚠️  慢查询以 information_schema 为主（{info_count}/{real_total} 条，"
            f"{info_count/real_total*100:.0f}%），大概率为 ORM/监控系统背景噪声，"
            "非本次告警直接根因，需结合原机慢日志确认业务 SQL 情况"
        )
    elif dts_dominated:
        risks.append(
            f"🔵 慢查询以 DTS Checksum 为主（{dts_count}/{real_total} 条），"
            "通常为 DTS 数据一致性校验，属运维操作非业务 SQL 问题"
        )
    else:
        risks.append(
            f"🔴 发现 {real_total} 条慢查询（业务 SQL {business_count} 条，"
            f"占比 {business_ratio*100:.0f}%），慢 SQL 为主因"
        )

    # top_dbs（全局，按量降序）
    top_dbs = sorted(db_counts.items(), key=lambda x: -x[1])[:5]

    return {
        "total": real_total,
        "level": level,
        "by_type": by_type,
        "business_ratio": round(business_ratio, 4),
        "noise_dominated": noise_dominated,
        "dts_dominated": dts_dominated,
        "top_dbs": [{"db": k, "count": v} for k, v in top_dbs],
        "top_items": sorted(items, key=lambda x: -(
            x.get("count") or x.get("slowLogCount") or x.get("countSum") or 0
        ))[:5],
        "risks": risks,
    }


def main():
    parser = argparse.ArgumentParser(description="从 CK 查询慢日志聚合列表")
    parser.add_argument("--cluster", required=True, help="集群名称")
    parser.add_argument("--start", required=True, help="开始时间，格式：2026-03-25 00:00:00（本地时间）")
    parser.add_argument("--end", required=True, help="结束时间，格式：2026-03-25 01:00:00（本地时间）")
    parser.add_argument("--db", default="", help="数据库名称（可选，过滤）")
    parser.add_argument("--keyword", default="", help="关键词过滤（库名或集群名）")
    parser.add_argument("--page", type=int, default=1, help="页码，默认 1")
    parser.add_argument("--page_size", type=int, default=20, help="每页条数，默认 20")
    parser.add_argument("--sort", default="desc", help="按慢查询数排序：desc/asc，默认 desc")
    parser.add_argument("--phase0", action="store_true",
                        help="Phase 0 分诊模式：全库聚合 + SQL 分类 + 量化推理")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    args = parser.parse_args()

    if not AI_TOKEN and not TOKEN:
        print("[get_slow_log_list] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    # Phase 0 模式：强制全库、大 page_size
    if args.phase0:
        page_size = 200
        db_name = ""
    else:
        page_size = args.page_size
        db_name = args.db

    try:
        result = fetch_slow_log_list(
            cluster_name=args.cluster,
            start_time=args.start,
            end_time=args.end,
            db_name=db_name,
            keyword=args.keyword,
            current_page=args.page,
            page_size=page_size,
            slow_log_count_sort=args.sort,
        )
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    data = result.get("data", {})
    total = data.get("total", 0)
    items = data.get("data", [])

    # Phase 0 模式：附加分类摘要
    if args.phase0:
        phase0_summary = build_phase0_summary(items, total)
        result["_phase0_summary"] = phase0_summary

        # 打印 Phase 0 摘要到 stderr
        s = phase0_summary
        print(f"[get_slow_log_list] Phase 0 探测 A 结果 · 集群：{args.cluster}", file=sys.stderr)
        print(f"  总慢查询数    : {s['total']} 条（量级：{s['level']}）", file=sys.stderr)
        print(f"  业务 SQL      : {s['by_type']['business']['count']} 条", file=sys.stderr)
        print(f"  info_schema   : {s['by_type']['info_schema']['count']} 条", file=sys.stderr)
        print(f"  DTS Checksum  : {s['by_type']['dts']['count']} 条", file=sys.stderr)
        print(f"  噪声主导      : {'是' if s['noise_dominated'] else '否'}", file=sys.stderr)
        print(f"  DTS 主导      : {'是' if s['dts_dominated'] else '否'}", file=sys.stderr)
        print(f"  TOP DB        : {s['top_dbs']}", file=sys.stderr)
        print("  推理：", file=sys.stderr)
        for r in s["risks"]:
            print(f"    {r}", file=sys.stderr)
    else:
        print(f"[get_slow_log_list] 总计 {total} 条，本页 {len(items)} 条", file=sys.stderr)

    output_str = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output and args.run_id:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        fname = "get_slow_log_list_phase0.json" if args.phase0 else "get_slow_log_list.json"
        out_file = raw_dir / fname
        out_file.write_text(output_str, encoding="utf-8")
        print(f"[get_slow_log_list] ✅ 已写入 {out_file}", file=sys.stderr)

    print(output_str)


if __name__ == "__main__":
    main()
