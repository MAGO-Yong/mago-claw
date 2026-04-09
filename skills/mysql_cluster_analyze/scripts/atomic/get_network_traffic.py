#!/usr/bin/env python3
"""
get_network_traffic.py — 查询集群网络流量监控指标

接口：POST /dms-api/ai-api/v1/grafana/fetch_data_by_pql
认证：DMS_AI_TOKEN（通过 DMS-AI-Token header），走 ai-api/v1

说明：
  查询集群网络带宽使用情况（network_in / network_out），用于带宽告警诊断（路径 F）。
  通过分析流量时序判断：是 DTS 迁移导致的预期高负载，还是业务大查询/大结果集异常。

指标说明：
  network_in  — 入方向流量（Mbps，由 node_network_receive_bytes_total 换算）
  network_out — 出方向流量（Mbps，由 node_network_transmit_bytes_total 换算）

用法：
  python3 get_network_traffic.py \\
      --cluster <cluster_name> \\
      --start "2026-03-26 14:00:00" \\
      --end "2026-03-26 15:00:00" \\
      [--output <dir>] [--run_id <id>]
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parents[1]))
from common.dms_client import AI_TOKEN, CLAW_TOKEN, AI_V1_PREFIX, _AI_HEADERS, _http_post


_CST = timezone(timedelta(hours=8))


def to_utc_ts(dt_str: str) -> int:
    """将 'YYYY-MM-DD HH:MM:SS'（北京时间 UTC+8）转为 UTC Unix 秒时间戳。"""
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        raise ValueError(
            f"[get_network_traffic] 时间格式错误（期望 'YYYY-MM-DD HH:MM:SS'）: {e}"
        )
    # 明确指定为北京时间（UTC+8），timestamp() 自动转 UTC
    dt_cst = dt.replace(tzinfo=_CST)
    return int(dt_cst.timestamp())


def _query_pql(pql: str, start_ts: int, end_ts: int, step: int = 30) -> list:
    """执行单条 PromQL 查询，返回 series 列表。"""
    payload = {
        "app": "pangu",
        "pql": pql,
        "start": start_ts,
        "end": end_ts,
        "step": step,
        "datasource": "vms-db",
    }
    result = _http_post(f"{AI_V1_PREFIX}/grafana/fetch_data_by_pql", payload, _AI_HEADERS, timeout=20)
    # grafana v1 响应结构：{data: {success: bool, data: {success: bool, data: [...]}}}
    outer = result.get("data") or {}
    if not outer.get("success"):
        raise RuntimeError(f"[get_network_traffic] 查询失败: {outer.get('message') or result}")
    return outer.get("data", {}).get("data") or []


def fetch_network_metrics(cluster_name: str, start: str, end: str) -> dict:
    """通过 Grafana PromQL 查询集群网络流量（RX / TX），转换为 Mbps。"""
    start_ts = to_utc_ts(start)
    end_ts = to_utc_ts(end)

    # bytes/s → Mbps：× 8 / 1_000_000
    pql_rx = (
        f'sum(irate(node_network_receive_bytes_total'
        f'{{cluster_name=~"{cluster_name}", device!~"lo"}}[1m])) * 8 / 1000000'
    )
    pql_tx = (
        f'sum(irate(node_network_transmit_bytes_total'
        f'{{cluster_name=~"{cluster_name}", device!~"lo"}}[1m])) * 8 / 1000000'
    )

    try:
        rx_series = _query_pql(pql_rx, start_ts, end_ts)
        tx_series = _query_pql(pql_tx, start_ts, end_ts)
    except Exception as e:
        raise RuntimeError(f"[get_network_traffic] 请求失败：{e}")

    def extract_values(series_list: list) -> list[float]:
        """从 grafana series 格式提取所有数值点。"""
        vals = []
        for s in series_list:
            for point in s.get("values", []):
                v = point.get("value")
                if v is not None:
                    try:
                        vals.append(float(v))
                    except (TypeError, ValueError):
                        pass
        return vals

    return {
        "cluster": cluster_name,
        "time_range": {"start": start, "end": end},
        "data": {
            "network_in_mbps": extract_values(rx_series),
            "network_out_mbps": extract_values(tx_series),
        },
    }


def analyze_traffic(data: dict) -> dict:
    """
    分析流量数据，输出摘要：
    - peak_in / peak_out：入/出方向峰值（Mbps）
    - avg_in / avg_out：平均值（Mbps）
    - is_high：是否超过 500 Mbps 告警阈值
    - pattern：突发型 or 持续型
    """
    summary = {
        "peak_in_mbps": None,
        "peak_out_mbps": None,
        "avg_in_mbps": None,
        "avg_out_mbps": None,
        "is_high": False,
        "pattern": "unknown",
        "interpretation": "",
    }

    metrics = data.get("data", {})
    if not metrics:
        summary["interpretation"] = "无流量数据，可能接口返回格式不同，请查看原始响应"
        return summary

    in_vals = [v for v in metrics.get("network_in_mbps", []) if v is not None]
    out_vals = [v for v in metrics.get("network_out_mbps", []) if v is not None]

    if in_vals:
        summary["peak_in_mbps"] = round(max(in_vals), 2)
        summary["avg_in_mbps"] = round(sum(in_vals) / len(in_vals), 2)
    if out_vals:
        summary["peak_out_mbps"] = round(max(out_vals), 2)
        summary["avg_out_mbps"] = round(sum(out_vals) / len(out_vals), 2)

    peak = max(
        summary["peak_in_mbps"] or 0,
        summary["peak_out_mbps"] or 0,
    )
    summary["is_high"] = peak > 500

    # 判断突发型 vs 持续型
    if in_vals and len(in_vals) > 3:
        avg = sum(in_vals) / len(in_vals)
        variance = sum((v - avg) ** 2 for v in in_vals) / len(in_vals)
        cv = (variance ** 0.5) / avg if avg > 0 else 0
        summary["pattern"] = "burst" if cv > 0.5 else "sustained"

    # 解读
    if summary["pattern"] == "sustained" and summary["is_high"]:
        summary["interpretation"] = (
            "流量持续高位 → 可能是 DTS 迁移任务或大规模数据导入/导出，"
            "建议检查 processlist 确认是否有 DTS binlog 拉取线程"
        )
    elif summary["pattern"] == "burst" and summary["is_high"]:
        summary["interpretation"] = (
            "流量突发型高峰 → 可能是业务大查询（大结果集）或批量操作，"
            "建议查慢日志确认触发时刻的 SQL"
        )
    elif not summary["is_high"]:
        summary["interpretation"] = "流量未超过高位阈值，带宽告警可能已自愈或阈值设置较低"

    return summary


def main():
    parser = argparse.ArgumentParser(description="查询网络流量监控指标（带宽诊断）")
    parser.add_argument("--cluster", required=True, help="集群名称")
    parser.add_argument("--start", required=True, help="开始时间，格式：YYYY-MM-DD HH:MM:SS（北京时间）")
    parser.add_argument("--end", required=True, help="结束时间，格式：YYYY-MM-DD HH:MM:SS（北京时间）")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    args = parser.parse_args()

    if not (AI_TOKEN or CLAW_TOKEN):
        print("[get_network_traffic] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    try:
        result = fetch_network_metrics(args.cluster, args.start, args.end)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    summary = analyze_traffic(result)
    result["_network_summary"] = summary

    output_str = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output and args.run_id:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        out_file = raw_dir / "network_traffic.json"
        out_file.write_text(output_str, encoding="utf-8")
        print(f"[get_network_traffic] ✅ 已写入 {out_file}", file=sys.stderr)

    print(output_str)

    # 打印摘要到 stderr
    s = summary
    print(
        f"[get_network_traffic] 峰值入流量={s['peak_in_mbps']} Mbps  峰值出流量={s['peak_out_mbps']} Mbps  "
        f"模式={s['pattern']}  高位={s['is_high']}",
        file=sys.stderr,
    )
    if s["interpretation"]:
        print(f"[get_network_traffic] 解读：{s['interpretation']}", file=sys.stderr)


if __name__ == "__main__":
    main()
