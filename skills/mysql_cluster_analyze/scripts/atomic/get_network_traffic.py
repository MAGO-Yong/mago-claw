#!/usr/bin/env python3
"""
get_network_traffic.py — 查询集群网络流量监控指标

接口：POST /dms-api/ai-api/v1/grafana/fetch_data_by_pql
认证：DMS_AI_TOKEN（通过 DMS-AI-Token header），走 ai-api/v1

说明：
  查询集群网络带宽使用情况（network_in / network_out），用于带宽告警诊断（路径 F）。
  通过分析流量时序判断：是 DTS 迁移导致的预期高负载，还是业务大查询/大结果集异常。

  双数据源自动回退：
  1. 优先查 vms-db（cluster_name 标签，DMS 管控节点）
  2. 若 vms-db 无数据（0 series）且提供了 --vm_ip，自动回退到 vms-vm（instance 标签，覆盖所有云主机）
  适用场景：vms-db 未覆盖的节点（如非 DMS 管控机、备份恢复时的临时机器）

指标说明：
  network_in  — 入方向流量（Mbps，由 node_network_receive_bytes_total 换算）
  network_out — 出方向流量（Mbps，由 node_network_transmit_bytes_total 换算）

用法：
  python3 get_network_traffic.py \\
      --cluster <cluster_name> \\
      --start "2026-03-26 14:00:00" \\
      --end "2026-03-26 15:00:00" \\
      [--vm_ip <master_ip>]   # 提供后，vms-db 无数据时自动回退 vms-vm
      [--output <dir>] [--run_id <id>]
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parents[1]))
from common.dms_client import (
    AI_TOKEN, CLAW_TOKEN, BASE_URL, AI_V1_PREFIX, OPEN_CLAW_PREFIX,
    _AI_HEADERS, _http_post, call_with_fallback,
)


_CST = timezone(timedelta(hours=8))


def to_utc_ts(dt_str: str) -> int:
    """将 'YYYY-MM-DD HH:MM:SS'（北京时间 UTC+8）转为 UTC Unix 秒时间戳。"""
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        raise ValueError(
            f"[get_network_traffic] 时间格式错误（期望 'YYYY-MM-DD HH:MM:SS'）: {e}"
        )
    dt_cst = dt.replace(tzinfo=_CST)
    return int(dt_cst.timestamp())


def _query_pql(pql: str, start_ts: int, end_ts: int, step: int = 30, datasource: str = "vms-db") -> list:
    """执行单条 PromQL 查询，返回 series 列表。"""
    payload = {
        "app": "pangu",
        "pql": pql,
        "start": start_ts,
        "end": end_ts,
        "step": step,
        "datasource": datasource,
    }
    result = call_with_fallback(
        lambda: _http_post(f"{AI_V1_PREFIX}/grafana/fetch_data_by_pql", payload, _AI_HEADERS, timeout=20),
        lambda: _http_post(f"{OPEN_CLAW_PREFIX}/grafana/fetch-data-by-pql", payload, {"dms-claw-token": CLAW_TOKEN}, timeout=20),
        "[get_network_traffic]",
    )
    # grafana v1 响应结构：{data: {success: bool, data: {success: bool, data: [...]}}}
    outer = result.get("data") or {}
    if not outer.get("success"):
        raise RuntimeError(f"[get_network_traffic] 查询失败: {outer.get('message') or result}")
    return outer.get("data", {}).get("data") or []


def _extract_values(series_list: list) -> list:
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


def _has_data(series_list: list) -> bool:
    """判断 series 是否有有效数据点。"""
    return any(
        point.get("value") is not None
        for s in series_list
        for point in s.get("values", [])
    )


def fetch_network_metrics(cluster_name: str, start: str, end: str, vm_ip: str = None) -> dict:
    """
    通过 Grafana PromQL 查询集群网络流量（RX / TX），转换为 Mbps。

    策略：
    1. 先用 vms-db（cluster_name 标签）查询
    2. 若 vms-db 返回 0 有效数据点 且提供了 vm_ip，自动回退 vms-vm（instance=~"{vm_ip}:.*"）
    """
    start_ts = to_utc_ts(start)
    end_ts = to_utc_ts(end)

    datasource_used = "vms-db"

    # ---- vms-db 查询（cluster_name 标签，DMS 管控节点）----
    pql_rx = (
        f'sum(irate(node_network_receive_bytes_total'
        f'{{cluster_name=~"{cluster_name}", device!~"lo"}}[1m])) * 8 / 1000000'
    )
    pql_tx = (
        f'sum(irate(node_network_transmit_bytes_total'
        f'{{cluster_name=~"{cluster_name}", device!~"lo"}}[1m])) * 8 / 1000000'
    )

    try:
        rx_series = _query_pql(pql_rx, start_ts, end_ts, datasource="vms-db")
        tx_series = _query_pql(pql_tx, start_ts, end_ts, datasource="vms-db")
    except Exception as e:
        raise RuntimeError(f"[get_network_traffic] vms-db 请求失败：{e}")

    # ---- 检查是否有数据，若无且提供了 vm_ip，回退 vms-vm ----
    if not _has_data(rx_series) and not _has_data(tx_series) and vm_ip:
        print(
            f"[get_network_traffic] vms-db 无数据（cluster_name=~\"{cluster_name}\"），"
            f"回退 vms-vm（instance=~\"{vm_ip}:.*\"）",
            file=sys.stderr,
        )
        datasource_used = "vms-vm"
        # vms-vm 使用 instance=~"{IP}:.*" 过滤（node_exporter 标签格式）
        pql_rx = (
            f'sum(irate(node_network_receive_bytes_total'
            f'{{instance=~"{vm_ip}:.*", device!~"lo"}}[1m])) * 8 / 1000000'
        )
        pql_tx = (
            f'sum(irate(node_network_transmit_bytes_total'
            f'{{instance=~"{vm_ip}:.*", device!~"lo"}}[1m])) * 8 / 1000000'
        )
        try:
            rx_series = _query_pql(pql_rx, start_ts, end_ts, datasource="vms-vm")
            tx_series = _query_pql(pql_tx, start_ts, end_ts, datasource="vms-vm")
        except Exception as e:
            raise RuntimeError(f"[get_network_traffic] vms-vm 请求失败：{e}")

    return {
        "cluster": cluster_name,
        "vm_ip": vm_ip,
        "datasource_used": datasource_used,
        "time_range": {"start": start, "end": end},
        "data": {
            "network_in_mbps": _extract_values(rx_series),
            "network_out_mbps": _extract_values(tx_series),
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

    if not in_vals and not out_vals:
        summary["interpretation"] = (
            "无有效数据点。vms-db 和 vms-vm 均无数据，请确认 --vm_ip 是否正确"
            if data.get("vm_ip") else
            "vms-db 无数据。若告警节点不在 DMS 管控范围，请传入 --vm_ip 触发 vms-vm 回退"
        )
        return summary

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
    parser.add_argument(
        "--vm_ip", default="",
        help="告警节点 IP（如 10.65.1.166）。提供后，若 vms-db 无数据则自动回退 vms-vm",
    )
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    args = parser.parse_args()

    if not (AI_TOKEN or CLAW_TOKEN):
        print("[get_network_traffic] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    try:
        result = fetch_network_metrics(args.cluster, args.start, args.end, vm_ip=args.vm_ip or None)
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
    ds = result.get("datasource_used", "vms-db")
    print(
        f"[get_network_traffic] datasource={ds}  "
        f"峰值入流量={s['peak_in_mbps']} Mbps  峰值出流量={s['peak_out_mbps']} Mbps  "
        f"模式={s['pattern']}  高位={s['is_high']}",
        file=sys.stderr,
    )
    if s["interpretation"]:
        print(f"[get_network_traffic] 解读：{s['interpretation']}", file=sys.stderr)


if __name__ == "__main__":
    main()
