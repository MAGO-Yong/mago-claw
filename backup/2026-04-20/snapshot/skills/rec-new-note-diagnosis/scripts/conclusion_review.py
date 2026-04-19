#!/usr/bin/env python3
"""
结论自检脚本 - 独立验证诊断结论的合理性

用法：
    python3 scripts/conclusion_review.py --session sessions/2026-04-02_10-36.json

输入：session 快照文件（包含诊断过程中收集的所有 findings）
输出：PASS / FAIL + 问题列表
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta


CST = timezone(timedelta(hours=8))


def parse_time(time_str: str):
    """尝试解析各种时间格式"""
    if not time_str:
        return None
    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M",
        "%H:%M:%S",
        "%H:%M",
    ]:
        try:
            t = datetime.strptime(time_str, fmt)
            if t.tzinfo is None:
                t = t.replace(tzinfo=CST)
            return t
        except ValueError:
            continue
    return None


def check_evidence_completeness(findings: dict) -> tuple:
    """检查证据完整性"""
    issues = []
    passed = True

    # 必须有 T0
    if not findings.get("t0"):
        issues.append("❌ 缺少 T0 时刻（异常起始时间点）")
        passed = False

    # 必须有跌幅数据
    if findings.get("drop_1h_pct") is None:
        issues.append("❌ 缺少 1H跌幅数值")
        passed = False

    # 必须有基准集
    if not findings.get("baseline_set"):
        issues.append("⚠️ 未记录置信基准集（-1d/-7d/-14d）")

    # 止损建议是否有链接
    mitigation = findings.get("mitigation", {})
    if mitigation:
        if not mitigation.get("link"):
            issues.append("⚠️ 止损建议缺少操作链接（racing/redcloud URL）")
        if not mitigation.get("expected_recovery"):
            issues.append("⚠️ 止损建议缺少预期恢复效果描述")

    return passed, issues


def check_timing(findings: dict) -> tuple:
    """检查时序合理性"""
    issues = []
    passed = True

    t0_str = findings.get("t0")
    t0 = parse_time(t0_str)
    anomaly_type = findings.get("anomaly_type", "")

    hits = findings.get("watchlist_hits", [])
    for hit in hits:
        change_time_str = hit.get("time", "")
        change_time = parse_time(change_time_str)

        if t0 and change_time:
            delta_minutes = (t0 - change_time).total_seconds() / 60

            if delta_minutes < 0:
                issues.append(
                    f"❌ 变更 [{hit.get('key', '?')}]（{change_time_str}）晚于 T0（{t0_str}），"
                    f"时差 {abs(delta_minutes):.0f}分钟，该变更不可能是根因"
                )
                passed = False
            elif delta_minutes < 5 and anomaly_type == "急跌":
                issues.append(
                    f"⚠️ 变更 [{hit.get('key', '?')}]（{change_time_str}）与 T0 时差仅 {delta_minutes:.0f}分钟，"
                    f"急跌场景下时差过短，请确认变更生效时间"
                )
            elif delta_minutes > 180 and anomaly_type == "急跌":
                issues.append(
                    f"⚠️ 变更 [{hit.get('key', '?')}]（{change_time_str}）距 T0 超过 3 小时，"
                    f"急跌场景下相关性较弱，建议重新评估"
                )

    return passed, issues


def check_contradiction(findings: dict) -> tuple:
    """检查结论内部矛盾"""
    issues = []
    passed = True

    drop_1h = findings.get("drop_1h_pct")
    drop_24h = findings.get("drop_24h_pct")
    root_cause = findings.get("root_cause", "")
    mitigation_target = findings.get("mitigation", {}).get("target", "")

    # 1H/24H 方向矛盾
    if drop_1h is not None and drop_24h is not None:
        if drop_1h < -10 and drop_24h > 5:
            issues.append(
                f"⚠️ 1H跌幅 {drop_1h:+.1f}% 但 24H上涨 {drop_24h:+.1f}%，"
                "结论应说明两者背离的原因"
            )
        elif drop_24h < -10 and drop_1h > 5:
            issues.append(
                f"⚠️ 24H跌幅 {drop_24h:+.1f}% 但 1H正常 {drop_1h:+.1f}%，"
                "建议重点排查历史数据消耗，而非实时发布侧"
            )

    # 根因和止损目标不一致
    if root_cause and mitigation_target:
        if root_cause and mitigation_target and root_cause != mitigation_target:
            # 简单检查：如果根因提到的关键词在止损目标中不存在
            root_words = set(root_cause.lower().split())
            target_words = set(mitigation_target.lower().split())
            if not root_words.intersection(target_words) and len(root_words) > 2:
                issues.append(
                    f"⚠️ 根因分析（{root_cause[:50]}）与止损目标（{mitigation_target[:50]}）"
                    "关键词不重叠，请确认两者一致"
                )

    return passed, issues


def check_mitigation_completeness(findings: dict) -> tuple:
    """检查止损建议完整性"""
    issues = []
    passed = True

    mitigation = findings.get("mitigation")
    if not mitigation:
        # 如果有异常但没有止损建议，问题严重
        if findings.get("drop_1h_pct") and findings["drop_1h_pct"] < -10:
            issues.append("❌ 指标下跌超过 10% 但没有止损建议")
            passed = False
        return passed, issues

    if not mitigation.get("action"):
        issues.append("❌ 止损建议缺少具体操作描述")
        passed = False

    if not mitigation.get("link"):
        issues.append("⚠️ 止损建议缺少操作链接（racing/redcloud URL）")

    if not mitigation.get("verify_metric"):
        issues.append("⚠️ 止损建议缺少验证指标（止损后看哪个指标确认恢复）")

    return passed, issues


def review(session_file: str) -> dict:
    """执行完整的结论审查"""
    with open(session_file) as f:
        session = json.load(f)

    findings = session.get("findings", {})

    # 各维度检查
    pass1, issues1 = check_evidence_completeness(findings)
    pass2, issues2 = check_timing(findings)
    pass3, issues3 = check_contradiction(findings)
    pass4, issues4 = check_mitigation_completeness(findings)

    all_issues = issues1 + issues2 + issues3 + issues4
    critical_issues = [i for i in all_issues if i.startswith("❌")]
    warning_issues = [i for i in all_issues if i.startswith("⚠️")]

    overall_pass = not critical_issues

    if overall_pass and warning_issues:
        overall_label = "⚠️ PASS WITH CAVEATS"
    elif overall_pass:
        overall_label = "✅ PASS"
    else:
        overall_label = "❌ FAIL"

    return {
        "overall": overall_label,
        "passed": overall_pass,
        "dimension_results": {
            "证据完整性": {"pass": pass1, "issues": issues1},
            "时序合理性": {"pass": pass2, "issues": issues2},
            "矛盾检测": {"pass": pass3, "issues": issues3},
            "止损建议完整性": {"pass": pass4, "issues": issues4},
        },
        "all_issues": all_issues,
        "critical_count": len(critical_issues),
        "warning_count": len(warning_issues),
    }


def print_review(result: dict, session_id: str):
    SEP = "━" * 60
    print(f"\n{SEP}")
    print(f"🔎 结论审查报告 — {session_id}")
    print(SEP)
    print(f"总评：{result['overall']}")
    print()

    for dim_name, dim_result in result["dimension_results"].items():
        status = "✅ PASS" if dim_result["pass"] else "❌ FAIL"
        if dim_result["pass"] and any(i.startswith("⚠️") for i in dim_result["issues"]):
            status = "⚠️ 有告警"
        print(f"[{status}] {dim_name}")

    if result["all_issues"]:
        print("\n问题清单：")
        for i, issue in enumerate(result["all_issues"], 1):
            print(f"  {i}. {issue}")
    else:
        print("\n未发现问题。")

    print()
    if result["passed"]:
        print("结论可信，建议按止损方案执行（需人工确认）。")
    else:
        print("结论存在重大问题，建议重新排查后再执行止损。")
    print(SEP)


def main():
    parser = argparse.ArgumentParser(description="诊断结论自检")
    parser.add_argument("--session", required=True, help="session 快照文件路径")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    if not Path(args.session).exists():
        print(f"错误：文件不存在 {args.session}", file=sys.stderr)
        sys.exit(1)

    session_id = Path(args.session).stem
    result = review(args.session)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_review(result, session_id)

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
