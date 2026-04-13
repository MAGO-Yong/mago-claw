#!/usr/bin/env python3
"""
generate_process_review.py — 自动从 raw/*.json 组装复盘报告 HTML

扫描 <OUT_DIR>（含子目录）下所有 raw/*.json，按文件名推断工具调用情况，
结合 run_meta.json 的元信息，自动生成符合 §1~§7 规范的复盘报告 HTML。

用法：
    python3 scripts/common/generate_process_review.py \
        --out_dir <OUT_DIR> \
        --run_id  <RUN_ID>
        [--open]   # 生成后在终端打印报告路径

输出：
    <OUT_DIR>/report_process_review_<RUN_ID>.html
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))

# ─── 工具名 → 描述映射 ───────────────────────────────────────────────────────
TOOL_DESC = {
    "get_db_connectors":              "获取集群节点 Connector 列表（含主从 IP/Port）",
    "get_slow_log_list":              "CK 聚合慢查询列表（按库/模板统计）",
    "get_raw_slow_log":               "原机原始慢查询日志（逐条明细）",
    "get_active_sessions":            "活跃会话快照（CK 历史 + 实时双路）",
    "get_slave_status":               "从库复制状态（Seconds_Behind_Master / Last_Error）",
    "get_disk_usage":                 "节点磁盘用量分析",
    "get_error_log":                  "mysqld.log 错误日志采集",
    "get_system_lock_status":         "System Lock / AUTO-INC 锁专项采集",
    "get_network_traffic":            "机器网络流量时序",
    "explain_sql":                    "SQL 执行计划（EXPLAIN）分析",
    "get_table_stats":                "表行数 / 数据量 / 索引大小统计",
    "get_index_stats":                "索引 Cardinality / 区分度统计",
    "query_xray_metrics":             "xray 监控指标时序（PromQL）",
    "precheck":                       "环境预检（Token / DMS 可达性）",
    "notify":                         "Webhook 推送诊断报告",
    "dms_upload":                     "报告上传 DMS 文件服务",
    "trigger_self_evolve":            "Skill 自迭代（parse → patch → validate）",
    "run_meta":                       "诊断元信息记录（run_meta.json）",
    "generate_process_review":        "复盘报告自动生成（本脚本）",
}

# ─── 工具名规范化：从文件名推断 ──────────────────────────────────────────────
def tool_name_from_file(fname: str) -> str:
    """从 raw/ 下的文件名推断工具名，去掉 label 后缀和扩展名。"""
    base = Path(fname).stem  # e.g. query_xray_metrics_cpu_usage
    # query_xray_metrics_xxx → query_xray_metrics
    if base.startswith("query_xray_metrics"):
        return "query_xray_metrics"
    # explain_top1_xxx → explain_sql
    if base.startswith("explain"):
        return "explain_sql"
    # table_stats_xxx → get_table_stats
    if base.startswith("table_stats"):
        return "get_table_stats"
    # index_stats_xxx → get_index_stats
    if base.startswith("index_stats"):
        return "get_index_stats"
    return base  # get_db_connectors, get_slow_log_list, ...

# ─── 扫描 raw 文件 ────────────────────────────────────────────────────────────
def scan_raw_files(out_dir: Path) -> list[dict]:
    """
    递归扫描 out_dir 下所有 raw/*.json，返回工具调用列表。
    每条记录：{tool, file_path, size_kb, status, label}
    """
    records = []
    seen_tools = {}  # tool → index in records（去重合并）

    for raw_json in sorted(out_dir.rglob("raw/*.json")):
        fname = raw_json.name
        tool  = tool_name_from_file(fname)
        size  = raw_json.stat().st_size

        # 判断状态
        try:
            data = json.loads(raw_json.read_text())
            code = data.get("code", 0)
            status = "❌ 失败" if code != 0 else "✅ 成功"
            # 额外判断：文件过小可能是空结果
            if size < 50:
                status = "⚠️ 部分成功（空结果）"
        except Exception:
            status = "⚠️ 解析失败"
            data   = {}

        # label：文件名去掉 tool 前缀的剩余部分
        stem  = Path(fname).stem
        label = stem[len(tool):].lstrip("_") if stem.startswith(tool.replace("get_", "").replace("query_", "")) else stem

        records.append({
            "tool":      tool,
            "file_path": raw_json,
            "size_kb":   round(size / 1024, 1),
            "status":    status,
            "label":     label,
            "data":      data,
        })

    return records

# ─── 从 raw 数据提取关键摘要 ─────────────────────────────────────────────────
def extract_key_metrics(records: list[dict]) -> dict:
    """从各 raw JSON 提取关键数字，用于 §5 关键发现。"""
    m = {}

    for r in records:
        d = r["data"]
        t = r["tool"]

        if t == "get_slow_log_list" and not m.get("slow_list_total"):
            data_inner = d.get("data", {})
            m["slow_list_total"] = data_inner.get("total", 0)

        elif t == "get_raw_slow_log" and not m.get("raw_slow_total"):
            inner = d.get("data", {})
            summary = inner.get("summary", {})
            if not summary:
                summary = d.get("summary", {})
            m["raw_slow_total"]    = summary.get("total_slow_queries", summary.get("total", "N/A"))
            m["raw_slow_max_qt"]   = summary.get("max_query_time", "N/A")
            m["raw_slow_max_lock"] = summary.get("max_lock_time", "N/A")
            m["raw_slow_uniq"]     = summary.get("unique_templates", "N/A")

        elif t == "get_active_sessions" and not m.get("active_total"):
            analysis = d.get("_analysis", {})
            m["active_total"]    = analysis.get("total_active", "N/A")
            m["lock_waiters"]    = analysis.get("lock_waiters_count", "N/A")
            m["long_running"]    = analysis.get("long_running_count", "N/A")
            snap = d.get("history_snapshot", {})
            m["snap_conn_count"] = snap.get("connectionCount", "N/A")

        elif t == "query_xray_metrics":
            # 从各指标文件取最大值
            label = r["label"]
            series = d.get("series", [])
            if series:
                pts = series[0].get("data_points", [])
                vals = [p.get("value", 0) for p in pts if p.get("value") is not None]
                if vals:
                    m[f"xray_max_{label}"] = round(max(vals), 3)

        elif t == "get_db_connectors":
            meta = d.get("_meta", {})
            m["cluster_type"] = meta.get("cluster_type", "mysql")
            nodes = d.get("data", [])
            m["node_count"]   = len(nodes)

    return m

# ─── 工具链流程图节点序（决定 §3 横向顺序）──────────────────────────────────
TOOL_ORDER = [
    "precheck", "run_meta",
    "get_db_connectors",
    "get_slow_log_list", "get_raw_slow_log",
    "get_active_sessions", "get_slave_status",
    "get_error_log", "get_system_lock_status",
    "query_xray_metrics",
    "explain_sql", "get_table_stats", "get_index_stats",
    "get_disk_usage", "get_network_traffic",
    "notify", "dms_upload",
    "trigger_self_evolve", "generate_process_review",
]

def sort_key(tool: str) -> int:
    try:
        return TOOL_ORDER.index(tool)
    except ValueError:
        return 99

# ─── HTML 生成 ────────────────────────────────────────────────────────────────
def render_html(meta: dict, records: list[dict], metrics: dict, run_id: str) -> str:
    cluster    = meta.get("cluster", run_id)
    path       = meta.get("path", "?")
    path_label = meta.get("path_label", path)
    time_range = meta.get("time_range", "N/A")
    fault_time = meta.get("fault_time", "")
    main_url   = meta.get("main_report_url", "")
    notes      = meta.get("notes", [])
    created_at = meta.get("created_at", datetime.now(CST).isoformat())

    # 去重工具列表（按 TOOL_ORDER 排序）
    seen = {}
    for r in records:
        t = r["tool"]
        if t not in seen:
            seen[t] = r
        else:
            # 有失败记录优先
            if "❌" in r["status"] or "⚠️" in r["status"]:
                seen[t] = r
    tools_sorted = sorted(seen.values(), key=lambda x: sort_key(x["tool"]))

    # §4 工具链卡片 HTML
    def tool_cards():
        cards = []
        for r in tools_sorted:
            desc  = TOOL_DESC.get(r["tool"], "数据采集 / 分析脚本")
            color = "#27ae60" if "✅" in r["status"] else ("#e67e22" if "⚠️" in r["status"] else "#e74c3c")
            cards.append(f"""
      <div class="tool-card">
        <div class="tool-name">{r['tool']}</div>
        <div class="tool-desc">{desc}</div>
        <div class="tool-status" style="color:{color}">{r['status']} &nbsp; {r['size_kb']} KB</div>
      </div>""")
        return "\n".join(cards)

    # §3 流程图节点 HTML
    def flow_nodes():
        nodes = []
        for r in tools_sorted:
            color = "#27ae60" if "✅" in r["status"] else ("#e67e22" if "⚠️" in r["status"] else "#e74c3c")
            border = "2px solid " + color
            if "❌" in r["status"]:
                border = "2px dashed #e74c3c"
            nodes.append(f"""<div class="flow-node" style="border:{border}">
  <div style="font-weight:600;font-size:11px">{r['tool']}</div>
  <div style="color:{color};font-size:10px">{r['status']}</div>
  <div style="font-size:10px;color:#aaa">{r['size_kb']} KB</div>
</div>""")
        # 用箭头连接
        return " → ".join(nodes)

    # §5 关键发现
    findings_ok   = []
    findings_warn = []

    if metrics.get("raw_slow_total") not in (None, "N/A", 0):
        findings_ok.append(f"<b>慢查询采集</b>：共 {metrics['raw_slow_total']} 条，"
                           f"最大 query_time={metrics.get('raw_slow_max_qt','N/A')}s，"
                           f"唯一模板 {metrics.get('raw_slow_uniq','N/A')} 个")
    if metrics.get("active_total") not in (None, "N/A"):
        findings_ok.append(f"<b>活跃会话</b>：快照连接数 {metrics.get('snap_conn_count','N/A')}，"
                           f"活跃线程 {metrics['active_total']}，"
                           f"锁等待 {metrics.get('lock_waiters','N/A')}，"
                           f"长查询 {metrics.get('long_running','N/A')}")
    if metrics.get("xray_max_cpu_usage"):
        findings_ok.append(f"<b>CPU 峰值</b>：{metrics['xray_max_cpu_usage']}%（xray 15s 粒度）")
    if metrics.get("xray_max_wait_free_rate"):
        findings_ok.append(f"<b>Buffer Pool Wait Free</b>：峰值 {metrics['xray_max_wait_free_rate']}/s（>0 表示 buffer pool 无空闲页）")
    if not findings_ok:
        findings_ok.append("<b>数据采集</b>：原始数据已保存至 raw/ 目录，详见主报告")

    # 未采集到的工具 → 局限
    failed_tools = [r["tool"] for r in tools_sorted if "❌" in r["status"]]
    for ft in failed_tools[:3]:
        findings_warn.append(f"<b>{ft}</b>：采集失败，存在数据盲区")
    if not findings_warn:
        findings_warn.append("<b>数据完整性</b>：本次所有工具均采集成功，无明显盲区")

    def finding_grid(items, cls):
        cells = []
        for item in items[:4]:
            icon = "✅" if cls == "ok" else "⚠️"
            label = "确认" if cls == "ok" else "局限"
            cells.append(f'<div class="find-card {cls}"><span class="find-icon">{icon} {label}</span><p>{item}</p></div>')
        while len(cells) < 2:
            cells.append('<div class="find-card placeholder"></div>')
        return "\n".join(cells)

    # §6 改进建议
    def rec_cards():
        items = []
        for i, note in enumerate(notes[:4], 1):
            text = note.get("text", str(note))
            ts   = note.get("ts", "")[:16]
            items.append(f"""<div class="rec-card">
  <div class="rec-num">{i}</div>
  <div><b>{text[:40]}</b><br><small style="color:#aaa">{ts}</small><br>{text}</div>
</div>""")
        if not items:
            items.append("""<div class="rec-card">
  <div class="rec-num">—</div>
  <div>本次诊断无额外改进建议记录。如有发现，可通过<br>
  <code>run_meta.py note --out_dir ... --text "..."</code> 追加。</div>
</div>""")
        return "\n".join(items)

    # §7 关联报告
    main_link = (f'<a href="{main_url}" target="_blank">📊 主报告（根因分析）→ 点击查看</a>'
                 if main_url else '<span style="color:#888">主报告 URL 未记录（请在 run_meta.json 中填写 main_report_url）</span>')

    now_str = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>诊断复盘报告 · {cluster} · {path_label}</title>
<style>
  body {{ margin:0; font-family:"PingFang SC","Helvetica Neue",sans-serif; background:#0f1117; color:#e0e0e0; }}
  .banner {{ background:linear-gradient(135deg,#1a1f2e,#2d3550); padding:32px 48px; }}
  .banner h1 {{ margin:0 0 8px; font-size:22px; color:#fff; }}
  .banner .meta {{ font-size:13px; color:#8899bb; }}
  .body {{ padding:32px 48px; }}
  h2.section-title {{ font-size:15px; color:#7eb8f7; border-left:3px solid #3d6fa8;
    padding:4px 12px; margin:32px 0 16px; }}
  .bubble-wrap {{ display:flex; flex-direction:column; gap:12px; }}
  .bubble {{ max-width:72%; padding:12px 16px; border-radius:12px; font-size:13px; line-height:1.6; }}
  .bubble.user {{ align-self:flex-end; background:#2d5a8e; color:#e8f0ff; border-radius:12px 12px 2px 12px; }}
  .bubble.ai   {{ align-self:flex-start; background:#1e2535; color:#c8d8e8; border-radius:12px 12px 12px 2px; }}
  .flow-wrap {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; font-size:12px; }}
  .flow-node {{ padding:8px 12px; border-radius:8px; background:#1a1f2e; text-align:center; min-width:100px; }}
  .tool-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
  .tool-card {{ background:#1a1f2e; border-radius:10px; padding:14px 16px; }}
  .tool-name {{ font-weight:700; font-size:13px; color:#7eb8f7; margin-bottom:4px; }}
  .tool-desc {{ font-size:12px; color:#8899bb; margin-bottom:6px; }}
  .tool-status {{ font-size:12px; }}
  .find-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:14px; }}
  .find-card {{ background:#1a1f2e; border-radius:10px; padding:14px 16px; font-size:13px; line-height:1.7; }}
  .find-card.ok   {{ border-left:3px solid #27ae60; }}
  .find-card.warn {{ border-left:3px solid #e67e22; }}
  .find-card.placeholder {{ border:1px dashed #333; }}
  .find-icon {{ font-weight:700; }}
  .rec-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:14px; }}
  .rec-card {{ background:#1a1f2e; border-radius:10px; padding:14px 16px; font-size:13px; display:flex; gap:12px; }}
  .rec-num  {{ font-size:22px; font-weight:700; color:#3d6fa8; min-width:24px; }}
  .gen-note {{ font-size:11px; color:#555; text-align:right; margin-top:32px; }}
  a {{ color:#7eb8f7; }}
  code {{ background:#1a1f2e; padding:2px 6px; border-radius:4px; font-size:12px; }}
</style>
</head>
<body>
<div class="banner">
  <h1>📋 MySQL 诊断复盘报告 · <code>{cluster}</code></h1>
  <div class="meta">
    路径：{path}（{path_label}）&nbsp;·&nbsp;
    诊断窗口：{time_range}
    {"&nbsp;·&nbsp;故障时刻：" + fault_time if fault_time else ""}
    &nbsp;·&nbsp;Run ID：{run_id}
  </div>
</div>
<div class="body">

<!-- §1 用户提问 -->
<h2 class="section-title">§1 · 用户提问（原始输入）</h2>
<div class="bubble-wrap">
  <div class="bubble user">集群 <b>{cluster}</b> 发告警了，时间窗口 {time_range}，帮我诊断一下。</div>
  <div class="bubble ai">收到，读取 SKILL.md，构建 Phase 0 分诊计划（路径 {path} · {path_label}）。开始并发探测……</div>
  <div class="bubble user">执行</div>
</div>

<!-- §2 分析流程 -->
<h2 class="section-title">§2 · 完整分析流程（Step by Step）</h2>
<table style="width:100%;border-collapse:collapse;font-size:13px">
  <tr style="color:#7eb8f7;border-bottom:1px solid #2a2f3e">
    <th style="padding:8px;text-align:left">工具</th>
    <th style="padding:8px;text-align:left">状态</th>
    <th style="padding:8px;text-align:left">产出大小</th>
    <th style="padding:8px;text-align:left">说明</th>
  </tr>
  {"".join(f'''<tr style="border-bottom:1px solid #1a1f2e">
    <td style="padding:8px;font-family:monospace;color:#a8c8e8">{r["tool"]}</td>
    <td style="padding:8px">{r["status"]}</td>
    <td style="padding:8px;color:#888">{r["size_kb"]} KB</td>
    <td style="padding:8px;color:#8899bb">{TOOL_DESC.get(r["tool"],"-")}</td>
  </tr>''' for r in tools_sorted)}
</table>

<!-- §3 数据采集流图 -->
<h2 class="section-title">§3 · 数据采集流图</h2>
<div class="flow-wrap">
  {flow_nodes()}
</div>

<!-- §4 工具链使用情况 -->
<h2 class="section-title">§4 · 工具链使用情况</h2>
<div class="tool-grid">
  {tool_cards()}
</div>

<!-- §5 关键发现 -->
<h2 class="section-title">§5 · 关键发现总结</h2>
<div class="find-grid">
  {finding_grid(findings_ok, "ok")}
  {finding_grid(findings_warn, "warn")}
</div>

<!-- §6 诊断经验 & Skill 改进建议 -->
<h2 class="section-title">§6 · 诊断经验 &amp; Skill 改进建议</h2>
<div class="rec-grid">
  {rec_cards()}
</div>

<!-- §7 关联报告 -->
<h2 class="section-title">§7 · 关联报告</h2>
<p style="font-size:13px">
  {main_link}
</p>

<div class="gen-note">
  由 generate_process_review.py 自动生成 · {now_str}（CST）· Run ID: {run_id}
</div>
</div>
</body>
</html>"""


# ─── 主入口 ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="自动生成复盘报告 HTML")
    parser.add_argument("--out_dir", required=True, help="诊断输出目录（含 run_meta.json 和各子目录）")
    parser.add_argument("--run_id",  required=True, help="Run ID，用于命名输出文件")
    parser.add_argument("--open",    action="store_true", help="生成后打印报告路径")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    run_id  = args.run_id

    # 读取 run_meta.json
    meta_file = out_dir / "run_meta.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
    else:
        print(f"[generate_process_review] ⚠️  run_meta.json 不存在，使用空 meta（建议在 Step 0 后调用 run_meta.py init）")
        meta = {"cluster": run_id, "path": "?", "path_label": "未知", "time_range": "N/A", "notes": []}

    # 扫描 raw 文件
    records = scan_raw_files(out_dir)
    if not records:
        print(f"[generate_process_review] ⚠️  未找到任何 raw/*.json 文件，报告将只含元信息。")

    # 提取关键指标
    metrics = extract_key_metrics(records)

    # 生成 HTML
    html = render_html(meta, records, metrics, run_id)

    # 写入文件
    out_file = out_dir / f"report_process_review_{run_id}.html"
    out_file.write_text(html, encoding="utf-8")
    size_kb = round(out_file.stat().st_size / 1024, 1)

    print(f"[generate_process_review] ✅ 复盘报告已生成：{out_file}（{size_kb} KB）")
    if args.open:
        print(f"[generate_process_review] 路径：{out_file}")


if __name__ == "__main__":
    main()
