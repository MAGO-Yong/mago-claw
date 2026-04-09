#!/usr/bin/env python3
"""
get_disk_usage.py — 查询集群各节点磁盘用量（空间分析）

通过 DMS 空间分析接口获取集群磁盘容量趋势信息。

接口（优先 ai-api/v1，兜底 open-claw /dms-api/v1）：
  GET /dms-api/ai-api/v1/mysql/data_analyse/vm_space_metric       ← 优先（DMS_AI_TOKEN）
  GET /dms-api/v1/mysql/data-analyse/vm-space-metric              ← 兜底（DMS_CLAW_TOKEN）
      params: cluster_name, vm_name, start_time, end_time

  GET /dms-api/ai-api/v1/mysql/data_analyse/cluster_space_metric  ← 优先（DMS_AI_TOKEN）
  GET /dms-api/v1/mysql/data-analyse/cluster-space-metric         ← 兜底（DMS_CLAW_TOKEN）
      params: cluster_name, start_time, end_time

认证：优先 DMS_AI_TOKEN（ai-api/v1），兜底 DMS_CLAW_TOKEN（open-claw）

用法：
  # 查询全集群（最近 1 小时）
  python3 get_disk_usage.py --cluster sns_note_new_ae

  # 查询指定节点
  python3 get_disk_usage.py --cluster sns_note_new_ae --vm_name lusse11a-db-sns-note-new-ae-9rb4f-3

  # 指定时间范围（格式：YYYY-MM-DD HH:MM:SS）
  python3 get_disk_usage.py --cluster sns_note_new_ae \\
      --start_time "2026-03-26 14:00:00" --end_time "2026-03-26 15:00:00"
"""

import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from common.dms_client import (
    AI_TOKEN, CLAW_TOKEN, BASE_URL, AI_V1_PREFIX,
    _AI_HEADERS, _http_get, call_with_fallback,
)

TOKEN = CLAW_TOKEN  # open-claw 兜底用

MANUAL_GUIDE = """[get_disk_usage] ⚠️  DMS API 查询失败，请使用以下方式人工确认：

方式 1：DMS 控制台
  集群管理 → {cluster} → 空间分析 → 容量趋势图

方式 2：SSH 到目标节点
  df -h /data                   # 总体用量
  du -sh /data/mysql            # 数据文件
  du -sh /data/binlog           # binlog
  du -sh /data/relaylog         # relay log（从库）
  du -sh /data/mysql/slow.log   # 慢日志

方式 3：MySQL 查数据文件大小（不含 binlog/relay log）
  SELECT table_schema, ROUND(SUM(data_length+index_length)/1024/1024/1024,2) AS size_gb
  FROM information_schema.tables
  GROUP BY table_schema ORDER BY size_gb DESC;

磁盘告警处置阈值：
  > 95%  → 🔴 P0 立即扩容或清理
  85~95% → 🟠 P1 本日内处理
  75~85% → 🟡 P2 本周内制定计划
"""


def _fetch_v1(v1_path: str, old_path: str, params: dict, label: str) -> dict:
    """发起 GET 请求，v1 优先，open-claw 兜底。失败时抛出 RuntimeError。"""
    qs = urllib.parse.urlencode(params)
    return call_with_fallback(
        lambda: _http_get(f"{AI_V1_PREFIX}{v1_path}?{qs}", _AI_HEADERS),
        lambda: _http_get(f"{BASE_URL}/dms-api/v1{old_path}?{qs}", {"dms-claw-token": TOKEN}),
        label,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cluster", required=True)
    ap.add_argument("--vm_name", default=None, help="指定节点 vm_name（可选，不填则查全集群）")
    ap.add_argument("--start_time", default=None, help="开始时间，格式 YYYY-MM-DD HH:MM:SS")
    ap.add_argument("--end_time", default=None, help="结束时间，格式 YYYY-MM-DD HH:MM:SS")
    ap.add_argument("--output", default=None)
    ap.add_argument("--run_id", default="run")
    args = ap.parse_args()

    if not AI_TOKEN and not TOKEN:
        print("[get_disk_usage] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    # 默认时间范围：最近 1 小时
    now = datetime.now()
    end_time = args.end_time or now.strftime("%Y-%m-%d %H:%M:%S")
    start_time = args.start_time or (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    # 选择接口：有 vm_name 用单节点接口，否则用全集群接口
    if args.vm_name:
        v1_path = "/mysql/data_analyse/vm_space_metric"
        old_path = "/mysql/data-analyse/vm-space-metric"
        params = {
            "cluster_name": args.cluster,
            "vm_name": args.vm_name,
            "start_time": start_time,
            "end_time": end_time,
        }
        label = "[get_disk_usage/vm]"
    else:
        v1_path = "/mysql/data_analyse/cluster_space_metric"
        old_path = "/mysql/data-analyse/cluster-space-metric"
        params = {
            "cluster_name": args.cluster,
            "start_time": start_time,
            "end_time": end_time,
        }
        label = "[get_disk_usage/cluster]"

    try:
        data = _fetch_v1(v1_path, old_path, params, label)
    except RuntimeError as e:
        print(f"[get_disk_usage] ⚠️  接口请求失败：{e}", file=sys.stderr)
        print(MANUAL_GUIDE.format(cluster=args.cluster))
        result = {
            "code": -1,
            "data": {"status": "api_failed", "manual_guide": True},
            "_summary": {"status": "api_failed"},
        }
        _write_output(args, json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    if data.get("code") != 0:
        print(f"[get_disk_usage] ⚠️  API 返回异常 code={data.get('code')}: {data.get('message')}", file=sys.stderr)
        print(MANUAL_GUIDE.format(cluster=args.cluster))
        result = {**data, "_summary": {"status": "api_error", "message": data.get("message")}}
        _write_output(args, json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    # 解析数据
    raw_data = data.get("data", {})
    metrics = raw_data if isinstance(raw_data, list) else raw_data.get("metrics", raw_data.get("list", []))

    summary = _analyze(args.cluster, args.vm_name, metrics)
    data["_summary"] = summary

    output_str = json.dumps(data, ensure_ascii=False, indent=2)

    # 打印人类可读摘要到 stderr
    print(f"[get_disk_usage] 集群：{args.cluster}", file=sys.stderr)
    if args.vm_name:
        print(f"  节点：{args.vm_name}", file=sys.stderr)
    print(f"  时间范围：{start_time} ~ {end_time}", file=sys.stderr)
    for line in summary.get("display_lines", []):
        print(f"  {line}", file=sys.stderr)

    _write_output(args, output_str)
    print(output_str)


def _analyze(cluster: str, vm_name: str | None, metrics: list) -> dict:
    """分析磁盘用量趋势，返回结构化摘要。"""
    if not metrics:
        return {"status": "no_data", "display_lines": ["⚠️  返回数据为空，无法分析"]}

    # 取最新一个时间点的用量数据（时序列表最后一项）
    latest = metrics[-1] if isinstance(metrics, list) else metrics
    used_pct = latest.get("diskUsedPercent") or latest.get("used_percent") or latest.get("usedPercent")
    total_gb = latest.get("diskTotalGB") or latest.get("total_gb") or latest.get("totalGB")
    used_gb = latest.get("diskUsedGB") or latest.get("used_gb") or latest.get("usedGB")

    risks = []
    display_lines = []

    if used_pct is not None:
        icon = "🔴" if used_pct > 95 else "🟠" if used_pct > 85 else "🟡" if used_pct > 75 else "🟢"
        display_lines.append(f"{icon} 磁盘使用率：{used_pct:.1f}%")
        if used_gb is not None and total_gb is not None:
            display_lines.append(f"  已用：{used_gb:.1f} GB / 总量：{total_gb:.1f} GB")
        if used_pct > 95:
            risks.append("🔴 P0：磁盘使用率超 95%，需立即扩容或清理")
        elif used_pct > 85:
            risks.append("🟠 P1：磁盘使用率超 85%，本日内处理")
        elif used_pct > 75:
            risks.append("🟡 P2：磁盘使用率超 75%，本周内制定计划")
    else:
        display_lines.append("⚠️  返回数据中无磁盘使用率字段，请查看原始 JSON")

    if risks:
        display_lines.append("风险：" + "；".join(risks))

    return {
        "status": "ok",
        "used_pct": used_pct,
        "total_gb": total_gb,
        "used_gb": used_gb,
        "risks": risks,
        "display_lines": display_lines,
    }


def _write_output(args, output_str: str):
    if args.output:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        out_path = raw_dir / "get_disk_usage.json"
        out_path.write_text(output_str, encoding="utf-8")
        print(f"[get_disk_usage] ✅ 已写入 {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
