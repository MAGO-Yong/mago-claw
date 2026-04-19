#!/usr/bin/env python3
"""
test_report.py — 基于已有 raw 数据，生成 AI 报告上下文说明。

用法：
    python3 scripts/test/test_report.py --run_id <run_id>
    python3 scripts/test/test_report.py --run_id <run_id> --path B

脚本不生成 HTML，不调 DMS API。
它只做：
  1. 定位 raw 目录（自动处理路径嵌套 bug）
  2. 读 run_meta.json 拿已有元数据
  3. 列 raw 文件清单 + 每个文件的关键字段摘要（单行）
  4. 推断诊断路径（从文件名特征 / run_meta 推断）
  5. 打印给 AI 的上下文说明（AI 读后直接接管生成报告）
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent  # skills/mysql_cluster_analyze/
OUTPUT_DIR = BASE / "output"
DOCS_DIR = BASE / "docs"


# ─── 路径推断 ───────────────────────────────────────────────

def find_raw_dir(run_id: str) -> Path | None:
    """
    自动找 raw 目录，兼容正常结构和嵌套结构（脚本 bug 遗留）。
    正常：output/{run_id}/{run_id}/raw/
    嵌套：output/{run_id}/{run_id}/raw/{run_id}/raw/{run_id}/raw/...
    返回包含 .json 文件最多的那个目录。
    """
    root = OUTPUT_DIR / run_id
    if not root.exists():
        return None

    candidates = list(root.rglob("raw"))
    if not candidates:
        return None

    # 取包含 .json 文件最多的 raw 目录（嵌套时取最深有数据的那层）
    best = max(candidates, key=lambda p: len(list(p.glob("*.json"))))
    return best if list(best.glob("*.json")) else None


def infer_path(raw_dir: Path, run_meta: dict, explicit_path: str | None) -> str:
    """推断诊断路径（B / B2 / A / C1 / C2 / D / E / F / G）"""
    if explicit_path:
        return explicit_path.upper()

    # 从 run_meta 的 main_report_url 推断
    url = run_meta.get("main_report_url", "")
    for pat, p in [("path-B2", "B2"), ("path-B", "B"), ("path-A", "A"),
                   ("path-C1", "C1"), ("path-C2", "C2"), ("path-D", "D"),
                   ("path-E", "E"), ("path-F", "F"), ("path-G", "G"),
                   ("B2", "B2"), ("conn_alert", "B2"), ("cpu_high", "B"),
                   ("slow_sql", "A"), ("repl_delay", "C1")]:
        if pat in url:
            return p

    # 从 raw 文件名特征推断
    files = {f.name for f in raw_dir.glob("*.json")}
    if "get_system_lock_status.json" in files:
        # 读 subtype 区分 B vs B2
        try:
            d = json.loads((raw_dir / "get_system_lock_status.json").read_text())
            subtype = d.get("_analysis", {}).get("subtype", "")
            if subtype == "row_lock":
                return "B2"
        except Exception:
            pass
    if any("xray_metrics" in f for f in files):
        return "B"
    if "get_raw_slow_log.json" in files:
        return "A"

    return "UNKNOWN"


# ─── 文件摘要 ────────────────────────────────────────────────

def summarize_file(path: Path) -> str:
    """读 JSON 文件，提取单行关键摘要。"""
    try:
        raw = path.read_text(encoding="utf-8")
        d = json.loads(raw)
    except Exception as e:
        return f"[读取失败: {e}]"

    name = path.name

    # threads_running
    if "threads_running" in name:
        try:
            series = d.get("series", [])
            max_val = max(
                pt["value"] for s in series for pt in s.get("data_points", [])
            )
            nodes = len(series)
            return f"{nodes} 个节点，全窗口 max threads_running = {max_val}"
        except Exception:
            pass

    # row_lock_waits（原始是 counter 累计值，_summary 里有 rate）
    if "row_lock" in name:
        try:
            series = d.get("series", [])
            if series:
                summary = series[0].get("_summary", {})
                max_rate = summary.get("max_rate")
                if max_rate is not None:
                    return f"max row_lock_waits_rate = {max_rate:.2f}/s（来自 _summary）"
                # 兜底：展示原始 counter 最大值
                max_val = max(pt["value"] for s in series for pt in s.get("data_points", []))
                return f"max counter = {max_val:.0f}（原始累计值，非速率）"
        except Exception:
            pass

    # threads_connected
    if "threads_connected" in name:
        try:
            series = d.get("series", [])
            max_val = max(
                pt["value"] for s in series for pt in s.get("data_points", [])
            )
            return f"max threads_connected = {int(max_val)}"
        except Exception:
            pass

    # dirty_bytes / pages_free / wait_free / handler_commit / pages_flushed
    if any(k in name for k in ["dirty_bytes", "pages_free", "wait_free", "handler_commit", "pages_flushed"]):
        try:
            series = d.get("series", [])
            if series:
                vals = [pt["value"] for s in series for pt in s.get("data_points", [])]
                return f"min={min(vals):.0f}, max={max(vals):.0f}, points={len(vals)}"
            return "无有效 series"
        except Exception:
            pass

    # get_slow_log_list / phase0
    if "slow_log_list" in name:
        try:
            # phase0 文件有 _phase0_summary，非 phase0 文件在 ctx 或直接 data
            p0 = d.get("_phase0_summary")
            if p0:
                total = p0.get("total", "?")
                level = p0.get("level", "?")
                by_type = p0.get("by_type", {})
                biz = by_type.get("business", {}).get("count", "?")
                dts = by_type.get("dts", {}).get("count", "?")
                return f"total={total}, level={level}, business={biz}, dts={dts}"
            # 非 phase0：从 data.total 读
            data = d.get("data", {})
            if isinstance(data, dict):
                total = data.get("total", "?")
                items = data.get("data", [])
                dbs = [item.get("dbName", "?") for item in items[:3]]
                return f"total={total}, 前3库={dbs}"
            return f"total={data if isinstance(data, int) else '?'}"
        except Exception:
            pass

    # get_raw_slow_log
    if "raw_slow_log" in name:
        try:
            data = d.get("data", {})
            timeline = data.get("timeline", [])
            details = data.get("details", [])
            top_sql = data.get("top_sql", [])
            return f"timeline={len(timeline)}点, details={len(details)}条, top_sql={len(top_sql)}条"
        except Exception:
            pass

    # get_db_connectors
    if "db_connectors" in name:
        try:
            nodes = d.get("data", [])
            roles = {}
            for n in nodes:
                r = n.get("role", "unknown")
                roles[r] = roles.get(r, 0) + 1
            cluster_type = d.get("_meta", {}).get("cluster_type", "?")
            return f"{len(nodes)} 个节点，类型={cluster_type}，{roles}"
        except Exception:
            pass

    # get_active_sessions
    if "active_sessions" in name:
        try:
            analysis = d.get("_analysis", {})
            total = analysis.get("total_active", "?")
            risks = analysis.get("risks", [])
            return f"total_active={total}, risks={risks}"
        except Exception:
            pass

    # get_system_lock_status
    if "system_lock" in name:
        try:
            analysis = d.get("_analysis", {})
            subtype = analysis.get("subtype", "?")
            top_sql = analysis.get("top_sql", [])
            return f"subtype={subtype}, top_sql条数={len(top_sql)}"
        except Exception:
            pass

    # get_slave_status
    if "slave_status" in name:
        try:
            data = d.get("data", {})
            delay = data.get("seconds_behind_master", data.get("Seconds_Behind_Master", "?"))
            vm = d.get("_analysis", {}).get("vm_name", "?")
            return f"vm_name={vm}, seconds_behind={delay}"
        except Exception:
            pass

    # analysis_conclusions
    if "analysis_conclusions" in name:
        try:
            keys = list(d.keys()) if isinstance(d, dict) else []
            return f"字段: {keys}"
        except Exception:
            pass

    # report_input
    if "report_input" in name:
        try:
            keys = list(d.keys()) if isinstance(d, dict) else []
            return f"字段: {keys}"
        except Exception:
            pass

    # 兜底
    size = len(raw)
    return f"{size} bytes，顶层 keys: {list(d.keys())[:6] if isinstance(d, dict) else type(d).__name__}"


# ─── 主逻辑 ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MySQL 集群诊断报告回归测试工具")
    parser.add_argument("--run_id", required=True, help="run_id，如 xray_cat_20260407_205700")
    parser.add_argument("--path", default=None, help="诊断路径（B/B2/A/C1...），不填自动推断")
    args = parser.parse_args()

    run_id = args.run_id
    out_root = OUTPUT_DIR / run_id

    if not out_root.exists():
        print(f"[ERROR] 找不到 output/{run_id}，请确认 run_id 正确", file=sys.stderr)
        sys.exit(1)

    # 1. 读 run_meta
    run_meta_path = out_root / "run_meta.json"
    run_meta = {}
    if run_meta_path.exists():
        try:
            run_meta = json.loads(run_meta_path.read_text())
        except Exception:
            pass

    # 2. 找 raw 目录
    raw_dir = find_raw_dir(run_id)

    # 3. 推断路径
    diagnosis_path = infer_path(raw_dir, run_meta, args.path) if raw_dir else (args.path or "UNKNOWN")

    # 4. 列文件 + 摘要
    files_info = []
    if raw_dir:
        for f in sorted(raw_dir.glob("*.json")):
            summary = summarize_file(f)
            files_info.append((f.name, str(f.relative_to(BASE)), summary))

    # 5. 规范文档路径
    spec_doc = f"docs/path-{diagnosis_path}.md"
    spec_path = DOCS_DIR / f"path-{diagnosis_path}.md"
    spec_exists = spec_path.exists()

    # ─── 输出 ──────────────────────────────────────────────
    sep = "═" * 60
    print(f"""
{sep}
🧪 TEST REPORT MODE — mysql_cluster_analyze
{sep}
run_id        : {run_id}
diagnosis_path: {diagnosis_path}
out_root      : output/{run_id}/
raw_dir       : {str(raw_dir.relative_to(BASE)) if raw_dir else '未找到'}
spec_doc      : {spec_doc} {"✅" if spec_exists else "❌ 不存在"}
existing_report: {run_meta.get("main_report_url", "（尚未生成）")}
{sep}

📂 RAW 文件清单（{len(files_info)} 个文件）：
""")

    for fname, fpath, summary in files_info:
        print(f"  {fname}")
        print(f"    路径  : {fpath}")
        print(f"    摘要  : {summary}")
        print()

    print(f"""{sep}
📋 AI 接管指令（复制以下内容给 AI）：
{sep}

你现在处于 **TEST REPORT MODE**。

任务：基于以下已有 raw 数据，跳过诊断 SOP，直接生成路径 {diagnosis_path} 的诊断报告 HTML。

**run_id**：{run_id}
**raw 目录**：{str(raw_dir.relative_to(BASE)) if raw_dir else '未找到'}
**规范文档**：{spec_doc}

执行步骤：
1. read {spec_doc}（读报告生成规范，重点看报告章节要求）
2. 逐一 read 上方 raw 文件（优先读关键文件：slow_log / xray_metrics / lock_status / connectors）
3. 基于 raw 数据 + 规范，直接生成完整 HTML 报告
4. 在报告 footer 加注：[TEST MODE · run_id: {run_id}]
5. 生成后调用 python3 scripts/common/publish_report.py 上传 CDN

⚠️  不调任何 DMS API，不走诊断 SOP，直接出报告。
{sep}
""")


if __name__ == "__main__":
    main()
