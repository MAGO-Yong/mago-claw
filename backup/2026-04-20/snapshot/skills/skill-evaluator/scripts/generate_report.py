#!/usr/bin/env python3
"""
skill-evaluator: 评估报告生成器
用法:
  python3 generate_report.py --results <results_json_file> --skill-name <name>
输出: Markdown 格式的评估报告
"""

import argparse
import json
import sys
from datetime import datetime
from collections import defaultdict

def calc_aggregate_scores(results):
    """计算各维度的聚合分数"""
    dims = [
        "intent_recognition", "skill_selection", "reasoning_process",
        "result_completeness", "result_accuracy", "delivery_quality", "response_speed"
    ]
    dim_scores = defaultdict(list)
    totals = []
    verdicts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    all_bad_patterns = []
    all_suggestions = []

    for r in results:
        scores = r.get("scores", {})
        for dim in dims:
            if dim in scores:
                dim_scores[dim].append(scores[dim])
        if "total" in r:
            totals.append(r["total"])
        verdict = r.get("verdict", "WARN")
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
        all_bad_patterns.extend(r.get("bad_patterns", []))
        all_suggestions.extend(r.get("optimization_suggestions", []))

    # 去重并统计频次
    pattern_counts = defaultdict(int)
    for p in all_bad_patterns:
        pattern_counts[p] += 1

    # 去重建议
    seen_suggestions = set()
    unique_suggestions = []
    for s in all_suggestions:
        if s not in seen_suggestions:
            seen_suggestions.add(s)
            unique_suggestions.append(s)

    avg_scores = {}
    for dim in dims:
        if dim_scores[dim]:
            avg_scores[dim] = round(sum(dim_scores[dim]) / len(dim_scores[dim]), 2)

    avg_total = round(sum(totals) / len(totals), 2) if totals else 0
    # 归一化到 5 分（总分 6 分）
    normalized = round(avg_total / 6 * 5, 2) if avg_total > 0 else 0

    return {
        "dim_scores": avg_scores,
        "avg_total": avg_total,
        "normalized_5": normalized,
        "verdicts": verdicts,
        "bad_patterns": dict(sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)),
        "suggestions": unique_suggestions
    }

def classify_suggestions(suggestions):
    """按优先级分类建议"""
    p0, p1, p2 = [], [], []
    for s in suggestions:
        s_lower = s.lower()
        if "p0" in s_lower or "立即" in s or "严重" in s or "阻塞" in s:
            p0.append(s.replace("P0", "").replace("（P0）", "").replace("[P0]", "").strip())
        elif "p1" in s_lower or "近期" in s or "重要" in s:
            p1.append(s.replace("P1", "").replace("（P1）", "").replace("[P1]", "").strip())
        else:
            p2.append(s.replace("P2", "").replace("（P2）", "").replace("[P2]", "").strip())
    return p0, p1, p2

def overall_verdict(verdicts, normalized):
    """计算整体判定"""
    total = sum(verdicts.values())
    fail_rate = verdicts.get("FAIL", 0) / total if total > 0 else 0
    if fail_rate > 0.3 or normalized < 3.0:
        return "FAIL ❌"
    elif fail_rate > 0.1 or normalized < 4.0:
        return "WARN ⚠️"
    else:
        return "PASS ✅"

def generate_report(results, skill_name, mode="zero-config"):
    """生成 Markdown 评估报告"""
    agg = calc_aggregate_scores(results)
    p0, p1, p2 = classify_suggestions(agg["suggestions"])
    verdict_str = overall_verdict(agg["verdicts"], agg["normalized_5"])

    dim_labels = {
        "intent_recognition": "意图识别",
        "skill_selection": "Skill 选择",
        "reasoning_process": "推理过程",
        "result_completeness": "结果完整性",
        "result_accuracy": "结果准确性",
        "delivery_quality": "交付体验",
        "response_speed": "响应速度"
    }
    dim_max = {
        "intent_recognition": 1.0,
        "skill_selection": 1.0,
        "reasoning_process": 1.0,
        "result_completeness": 1.0,
        "result_accuracy": 1.0,
        "delivery_quality": 0.5,
        "response_speed": 0.5
    }

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# {skill_name} 评估报告",
        f"",
        f"**评估时间**：{now}  ",
        f"**评估模式**：{'零配置模式' if mode == 'zero-config' else '精评模式（含业务上下文）'}  ",
        f"**题目数量**：{len(results)} 题  ",
        f"",
        f"---",
        f"",
        f"## 综合评分",
        f"",
        f"| 维度 | 得分 | 满分 |",
        f"|------|------|------|",
    ]

    for dim, label in dim_labels.items():
        score = agg["dim_scores"].get(dim, 0)
        max_s = dim_max[dim]
        lines.append(f"| {label} | {score} | {max_s} |")

    lines += [
        f"| **综合（归一化）** | **{agg['normalized_5']} / 5.0** | 5.0 |",
        f"",
        f"**整体判定**：{verdict_str}",
        f"",
        f"---",
        f"",
        f"## 问题分布",
        f"",
        f"- ✅ PASS：{agg['verdicts'].get('PASS', 0)} 题",
        f"- ⚠️ WARN：{agg['verdicts'].get('WARN', 0)} 题",
        f"- ❌ FAIL：{agg['verdicts'].get('FAIL', 0)} 题",
        f"",
        f"---",
        f"",
        f"## Bad Patterns（系统性问题）",
        f"",
    ]

    if agg["bad_patterns"]:
        lines += ["| 问题 | 出现频次 |", "|------|---------|"]
        for pattern, count in agg["bad_patterns"].items():
            lines.append(f"| {pattern} | {count} 题 |")
    else:
        lines.append("*未发现系统性问题 ✅*")

    lines += [
        f"",
        f"---",
        f"",
        f"## 优化建议",
        f"",
    ]

    if p0:
        lines.append("### P0（立即修复）")
        for s in p0:
            lines.append(f"- {s}")
        lines.append("")

    if p1:
        lines.append("### P1（近期优化）")
        for s in p1:
            lines.append(f"- {s}")
        lines.append("")

    if p2:
        lines.append("### P2（长期改进）")
        for s in p2:
            lines.append(f"- {s}")
        lines.append("")

    if not p0 and not p1 and not p2:
        lines.append("*暂无优化建议*\n")

    lines += [
        f"---",
        f"",
        f"## 各题详情",
        f"",
        f"| 题目 | 类型 | 得分 | 判定 | 主要问题 |",
        f"|------|------|------|------|---------|",
    ]

    for r in results:
        qid = r.get("question_id", "?")
        qtype = r.get("type", "S")
        score = r.get("normalized_5", r.get("total", 0))
        v = r.get("verdict", "WARN")
        verdict_icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(v, "⚠️")
        patterns = r.get("bad_patterns", [])
        main_issue = patterns[0] if patterns else "无"
        lines.append(f"| {qid} | {qtype} | {score}/5.0 | {verdict_icon} {v} | {main_issue} |")

    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="生成 SKILL 评估报告")
    parser.add_argument("--results", required=True, help="评估结果 JSON 文件路径")
    parser.add_argument("--skill-name", required=True, help="SKILL 名称")
    parser.add_argument("--mode", default="zero-config", choices=["zero-config", "enhanced"])
    parser.add_argument("--output", default=None, help="输出文件路径（默认输出到 stdout）")
    args = parser.parse_args()

    try:
        with open(args.results, "r", encoding="utf-8") as f:
            results = json.load(f)
    except Exception as e:
        print(json.dumps({"error": f"Failed to read results: {e}"}))
        sys.exit(1)

    report = generate_report(results, args.skill_name, args.mode)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(json.dumps({"status": "ok", "output": args.output, "lines": len(report.splitlines())}))
    else:
        print(report)

if __name__ == "__main__":
    main()
