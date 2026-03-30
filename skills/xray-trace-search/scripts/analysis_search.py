#!/usr/bin/env python3
"""
XRay 异常 Span 批量查询脚本
调用 /analysisSearch 接口，查询指定服务+接口在某时间段内的异常 Span，
输出精简 Span 列表、traceId 列表及 8 维度聚合分析。

用法：
    python3 analysis_search.py \
        --app xray-server \
        --start 1711339200 \
        --end 1711342800 \
        [--endpoint "Http./api/trace/search"] \
        [--error-names "TimeoutException,IOException"] \
        [--limit 500]
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

API_URL = "https://xray.devops.xiaohongshu.com/api/trace/analysisSearch"
AUTH_HEADER = "pass"
TOP_N = 10  # Span 列表展示条数


def parse_args():
    parser = argparse.ArgumentParser(description="XRay 异常 Span 批量查询")
    parser.add_argument("--app", required=True, help="服务名（必填）")
    parser.add_argument(
        "--start", required=True, type=int, help="开始时间（秒级 Unix 时间戳，必填）"
    )
    parser.add_argument("--end", required=True, type=int, help="结束时间（秒级 Unix 时间戳，必填）")
    parser.add_argument(
        "--endpoint",
        default=None,
        help="接口，格式 transactionType.transactionName（选填）",
    )
    parser.add_argument(
        "--error-names",
        default=None,
        help="异常类型过滤，逗号分隔（选填），如 TimeoutException,IOException",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="返回条数上限，默认 500，最大 1000（选填）",
    )
    return parser.parse_args()


def build_payload(args):
    payload = {
        "app": args.app,
        "start": args.start,
        "end": args.end,
        "limit": min(args.limit, 1000),
    }
    if args.endpoint:
        payload["endpoint"] = args.endpoint
    if args.error_names:
        payload["errorNames"] = [e.strip() for e in args.error_names.split(",") if e.strip()]
    return payload


def call_api(payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "xray_ticket": AUTH_HEADER,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[ERROR] HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERROR] 网络错误: {e.reason}", file=sys.stderr)
        sys.exit(1)


def fmt_dist(dist, top=10):
    """格式化分布 Map，取前 top 条，按 count 降序（API 已排序）。"""
    if not dist:
        return "  (无数据)"
    lines = []
    for i, (k, v) in enumerate(dist.items()):
        if i >= top:
            lines.append(f"  ... (共 {len(dist)} 项)")
            break
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def print_results(resp):
    if not resp.get("success"):
        print(
            f"[ERROR] 接口返回失败: code={resp.get('code')}, msg={resp.get('message')}",
            file=sys.stderr,
        )
        sys.exit(1)

    data = resp.get("data", {})
    total = data.get("total", 0)
    spans = data.get("spans", [])
    trace_ids = data.get("traceIds", [])
    agg = data.get("aggregation", {})

    # --- 1. 概览 ---
    print("=" * 60)
    print("【概览】")
    print(f"  命中异常 Span 总数 : {total}")
    print(f"  返回 Span 数       : {len(spans)}")
    print(f"  去重 traceId 数    : {len(trace_ids)}")

    # --- 2. 8 维度聚合分析 ---
    print("\n【8 维度聚合分析】")

    sections = [
        ("异常类型分布", "errorTypeDistribution"),
        ("接口分布", "spanNameDistribution"),
        ("Pod 分布", "podDistribution"),
        ("本端机房分布", "zoneDistribution"),
        ("下游机房分布", "downstreamZoneDistribution"),
        ("下游集群分布", "downstreamIpDistribution"),
        ("入口分布", "entryDistribution"),
    ]
    for label, key in sections:
        val = agg.get(key)
        if val:
            print(f"\n  [{label}]")
            print(fmt_dist(val))

    cross_zone = agg.get("crossZoneRatio")
    if cross_zone is not None:
        print(f"\n  [跨机房占比] {cross_zone:.2f}%")

    # --- 3. 异常 Span 列表摘要（前 TOP_N 条）---
    print(f"\n【异常 Span 列表（前 {TOP_N} 条）】")
    for i, span in enumerate(spans[:TOP_N]):
        ts = span.get("startTimestamp", "")
        errs = ", ".join(span.get("errorTypes") or []) or "(无 errorTypes)"
        print(
            f"  [{i + 1}] traceId={span.get('traceId')} | "
            f"duration={span.get('durationMs')}ms | "
            f"type={span.get('spanType')} | "
            f"pod={span.get('podName')} | "
            f"zone={span.get('zone')} | "
            f"errors={errs}"
        )

    # --- 4. traceId 列表 ---
    print(f"\n【去重 traceId 列表（共 {len(trace_ids)} 条）】")
    for tid in trace_ids:
        print(f"  {tid}")

    if trace_ids:
        print("\n提示：可将 traceId 传入 xray-logview-analyzer 做单链路深度分析。")

    print("=" * 60)


def main():
    args = parse_args()
    payload = build_payload(args)

    print(f"[INFO] 查询参数: {json.dumps(payload, ensure_ascii=False)}")
    resp = call_api(payload)
    print_results(resp)


if __name__ == "__main__":
    main()
