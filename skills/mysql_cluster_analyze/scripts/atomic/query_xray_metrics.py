#!/usr/bin/env python3
"""
query_xray_metrics.py — 执行任意 PromQL 查询，返回完整时序数据

复用现有 DMS 接口：POST /dms-api/open-claw/grafana/fetch-data-by-pql
与 mysql_monitor.py 的区别：
  - 独立 CLI 脚本（非 Python 类方法）
  - 支持任意 PromQL
  - 返回完整时序（非仅最后一个点）
  - 默认 step=15（更高精度）
  - 时间输入为北京时间字符串（自动转 Unix timestamp）
  - 支持 vmname 客户端过滤
  - 提供摘要统计（min, max, avg, data_points）

认证：DMS_CLAW_TOKEN

用法：
  python3 query_xray_metrics.py \
      --pql 'mysql_global_status_innodb_buffer_pool_wait_free{cluster_name="redtao_antispam"}' \
      --start "2026-04-02 04:15:00" \
      --end   "2026-04-02 04:45:00" \
      [--step 15] \
      [--vmname "qsh8-db-redtao-antispam-u5trt-11"] \
      [--datasource vms-db] \
      [--output <dir>] [--run_id <id>] [--label wait_free]
"""

import argparse
import calendar
import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
from common.dms_client import (
    AI_TOKEN, AI_V1_PREFIX, OPEN_CLAW_PREFIX, CLAW_TOKEN,
    _AI_HEADERS, _http_post, call_with_fallback,
)

TOKEN = CLAW_TOKEN


def _beijing_to_unix(dt_str: str) -> int:
    """将北京时间字符串转为 Unix timestamp（北京时间 = UTC+8）。"""
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            dt = datetime.strptime(dt_str, fmt)
            # 北京时间 = UTC+8，转换为 UTC 后再转 timestamp
            utc_ts = calendar.timegm(dt.timetuple()) - 8 * 3600
            return utc_ts
        except ValueError:
            continue
    raise ValueError(f"无法解析时间：{dt_str}，请使用格式 YYYY-MM-DD HH:MM:SS")


def _unix_to_beijing(ts: int) -> str:
    """将 Unix timestamp 转为北京时间字符串。"""
    dt = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8)))
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def query_promql(
    pql: str,
    start_ts: int,
    end_ts: int,
    step: int = 15,
    datasource: str = "vms-db",
) -> dict:
    """执行 PromQL 查询，返回原始 API 响应。"""
    payload = {
        "app": "pangu",
        "pql": pql,
        "start": start_ts,
        "end": end_ts,
        "step": step,
        "datasource": datasource,
    }

    def _v1():
        return _http_post(
            f"{AI_V1_PREFIX}/grafana/fetch_data_by_pql",
            payload,
            _AI_HEADERS,
            timeout=60,
        )

    def _old():
        return _http_post(
            f"{OPEN_CLAW_PREFIX}/grafana/fetch-data-by-pql",
            payload,
            {"dms-claw-token": TOKEN},
            timeout=60,
        )

    try:
        return call_with_fallback(_v1, _old, "[query_xray_metrics]")
    except Exception as e:
        raise RuntimeError(f"[query_xray_metrics] 请求失败：{e}")


def _process_series(series_list: list, vmname_filter: str = "") -> list:
    """
    处理 API 返回的时序数据列表，可选按 vmname 过滤。
    每个 series 包含 metric（标签）和 values（时间序列）。
    """
    results = []
    for series in series_list:
        metric = series.get('metric', {})

        # vmname 过滤
        if vmname_filter:
            vm = metric.get('vmname', '') or metric.get('instance', '')
            if vmname_filter not in vm:
                continue

        values = series.get('values', [])
        # 转换 values 为更友好的格式
        data_points = []
        numeric_values = []
        for v in values:
            ts = v.get('timestamp') or v.get('time')
            val = v.get('value')
            try:
                ts_int = int(ts) if ts is not None else 0
                val_float = float(val) if val is not None else None
            except (ValueError, TypeError):
                ts_int = 0
                val_float = None

            point = {
                'timestamp': ts_int,
                'time_beijing': _unix_to_beijing(ts_int) if ts_int else '',
                'value': val_float,
            }
            data_points.append(point)
            if val_float is not None:
                numeric_values.append(val_float)

        # 计算摘要统计
        summary = {}
        if numeric_values:
            summary = {
                'min': round(min(numeric_values), 6),
                'max': round(max(numeric_values), 6),
                'avg': round(sum(numeric_values) / len(numeric_values), 6),
                'data_points': len(numeric_values),
            }

        results.append({
            'metric': metric,
            'data_points': data_points,
            '_summary': summary,
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="执行任意 PromQL 查询，返回完整时序数据")
    parser.add_argument("--pql", required=True, help="PromQL 查询表达式")
    parser.add_argument("--start", required=True, help="开始时间（北京时间），格式：2026-04-02 04:15:00")
    parser.add_argument("--end", required=True, help="结束时间（北京时间），格式：2026-04-02 04:45:00")
    parser.add_argument("--step", type=int, default=15, help="采样间隔（秒），默认 15")
    parser.add_argument("--vmname", default="", help="按 vmname 过滤结果（客户端过滤，支持子串匹配）")
    parser.add_argument("--datasource", default="vms-db", help="数据源，默认 vms-db")
    parser.add_argument("--label", default="", help="输出文件名标签，如 wait_free")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    args = parser.parse_args()

    if not AI_TOKEN and not TOKEN:
        print("[query_xray_metrics] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    if args.step < 5:
        print(f"[query_xray_metrics] ⚠️ --step={args.step} 过小（建议 ≥5s），可能导致数据点过多或被 API 限流", file=sys.stderr)

    if args.output and not args.run_id:
        print("[query_xray_metrics] ⚠️ 指定了 --output 但未指定 --run_id，结果不会落盘", file=sys.stderr)

    try:
        start_ts = _beijing_to_unix(args.start)
        end_ts = _beijing_to_unix(args.end)
    except ValueError as e:
        print(f"[query_xray_metrics] ❌ {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"[query_xray_metrics] PQL: {args.pql[:80]}{'...' if len(args.pql) > 80 else ''}\n"
        f"  时间范围：{args.start} ~ {args.end}（step={args.step}s）\n"
        f"  Unix: {start_ts} ~ {end_ts}",
        file=sys.stderr,
    )

    try:
        raw_result = query_promql(args.pql, start_ts, end_ts, args.step, args.datasource)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # 检查 API 返回码
    if raw_result.get('code') != 0:
        msg = raw_result.get('message', '未知错误')
        print(f"[query_xray_metrics] ❌ API 返回错误：{msg}", file=sys.stderr)
        sys.exit(1)

    # 提取时序数据（API 响应结构：{data: {data: {data: [...]}}}）
    outer_data = raw_result.get('data')
    if not isinstance(outer_data, dict):
        print(f"[query_xray_metrics] ⚠️ API 响应结构异常：'data' 非 dict，type={type(outer_data).__name__}", file=sys.stderr)
        outer_data = {}
    mid_data = outer_data.get('data')
    if not isinstance(mid_data, dict):
        print(f"[query_xray_metrics] ⚠️ API 响应结构异常：'data.data' 非 dict，type={type(mid_data).__name__}", file=sys.stderr)
        mid_data = {}
    series_list = mid_data.get('data', [])
    if not isinstance(series_list, list):
        print(f"[query_xray_metrics] ⚠️ API 响应结构异常：'data.data.data' 非 list，type={type(series_list).__name__}", file=sys.stderr)
        series_list = []
    processed = _process_series(series_list, args.vmname)

    result = {
        "pql": args.pql,
        "start_time": args.start,
        "end_time": args.end,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "step": args.step,
        "datasource": args.datasource,
        "vmname_filter": args.vmname or "(none)",
        "total_series": len(series_list),
        "filtered_series": len(processed),
        "series": processed,
    }

    output_str = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output and args.run_id:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        file_label = f"_{args.label}" if args.label else ""
        out_file = raw_dir / f"query_xray_metrics{file_label}.json"
        out_file.write_text(output_str, encoding="utf-8")
        print(f"[query_xray_metrics] ✅ 已写入 {out_file}", file=sys.stderr)

    print(output_str)

    # 打印摘要到 stderr
    print(f"[query_xray_metrics] 返回 {len(series_list)} 个 series，过滤后 {len(processed)} 个", file=sys.stderr)
    for i, s in enumerate(processed[:3]):
        sm = s.get('_summary', {})
        metric_label = s.get('metric', {}).get('vmname', '') or s.get('metric', {}).get('instance', '') or f'series_{i}'
        if sm:
            print(
                f"  [{metric_label}] min={sm.get('min', '?')}, max={sm.get('max', '?')}, avg={sm.get('avg', '?')}, points={sm.get('data_points', '?')}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
