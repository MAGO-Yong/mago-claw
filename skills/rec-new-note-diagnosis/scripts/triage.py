#!/usr/bin/env python3
"""
分诊脚本 - 根据指标数据快速决定诊断路径

用法：
    python3 scripts/triage.py --drop-1h -18.5 --drop-24h 1.5 --watchlist-hits 2 --hit-levels high,medium

输出：
    路径: 🔴 Deep Path
    原因: 1H跌幅 -18.5% 超过 15% 阈值，watchlist 命中 2条
    置信度: HIGH
"""

import argparse
import sys


def triage(
    drop_1h_pct: float,
    drop_24h_pct: float,
    watchlist_hits: int = 0,
    hit_levels: list = None,
    has_contradiction: bool = False,
    absolute_value: float = None,
    acute_drop_detected: bool = False,
) -> dict:
    """
    执行分诊，返回路径决策。

    参数：
        drop_1h_pct: 1H指标跌幅（负数为下跌，如 -18.5 表示跌18.5%）
        drop_24h_pct: 24H指标跌幅
        watchlist_hits: watchlist 命中数量
        hit_levels: 命中级别列表，如 ['critical', 'high', 'medium']
        has_contradiction: 是否存在矛盾判断（recall正常但指标跌）
        absolute_value: 1H指标绝对值（如 0.0523）
        acute_drop_detected: 是否检测到急跌信号（Step 1.3）

    返回：
        dict: {
            'path': 'fast' | 'standard' | 'deep',
            'emoji': '🟢' | '🟡' | '🔴',
            'label': 'Fast Path' | 'Standard Path' | 'Deep Path',
            'confidence': 'HIGH' | 'MEDIUM' | 'LOW',
            'reasons': [...],  # 触发原因列表
            'gates': ['A', 'B'] | ['A', 'B', 'C', 'D'] | [],
        }
    """
    if hit_levels is None:
        hit_levels = []

    hit_levels_lower = [l.lower() for l in hit_levels]
    has_critical = 'critical' in hit_levels_lower
    high_count = sum(1 for l in hit_levels_lower if l == 'high')
    medium_count = sum(1 for l in hit_levels_lower if l == 'medium')

    reasons = []
    path_scores = {"fast": 0, "standard": 0, "deep": 0}

    # ─── 评分规则 ────────────────────────────────────────────────

    # 1H 跌幅评分
    if drop_1h_pct <= -15:
        reasons.append(f"1H跌幅 {drop_1h_pct:+.1f}% 超过 15% 阈值")
        path_scores["deep"] += 3
    elif drop_1h_pct <= -5:
        reasons.append(f"1H跌幅 {drop_1h_pct:+.1f}% 在 5%-15% 范围内")
        path_scores["standard"] += 2
    else:
        path_scores["fast"] += 2

    # 24H 跌幅评分
    if drop_24h_pct is not None and drop_24h_pct <= -10:
        reasons.append(f"24H跌幅 {drop_24h_pct:+.1f}% 超过 10% — 1H+24H 同步下跌")
        path_scores["deep"] += 3
    elif drop_24h_pct is not None and drop_24h_pct <= -5:
        reasons.append(f"24H跌幅 {drop_24h_pct:+.1f}% 在 5%-10% 范围内")
        path_scores["standard"] += 1

    # watchlist 命中评分
    if has_critical:
        reasons.append(f"watchlist 命中 Critical 级变更")
        path_scores["deep"] += 4
    elif high_count >= 3:
        reasons.append(f"watchlist 命中 {high_count}条 High 级变更")
        path_scores["deep"] += 3
    elif high_count >= 1 or medium_count >= 2:
        hit_summary = []
        if high_count: hit_summary.append(f"{high_count}条 High")
        if medium_count: hit_summary.append(f"{medium_count}条 Medium")
        reasons.append(f"watchlist 命中 {', '.join(hit_summary)}")
        path_scores["standard"] += 2
    elif watchlist_hits == 0 and drop_1h_pct > -5:
        path_scores["fast"] += 3

    # 矛盾判断
    if has_contradiction:
        reasons.append("存在矛盾判断（recall正常但指标跌）")
        path_scores["deep"] += 3

    # 急跌信号
    if acute_drop_detected:
        reasons.append("检测到急跌信号（Step 1.3 触发）")
        path_scores["standard"] += 1

    # 绝对值红线
    if absolute_value is not None and absolute_value < 0.060:
        reasons.append(f"绝对值 {absolute_value:.4f} 跌破红线 0.060")
        path_scores["deep"] += 4
    elif absolute_value is not None and absolute_value < 0.065:
        reasons.append(f"绝对值 {absolute_value:.4f} 跌破警戒线 0.065")
        path_scores["deep"] += 2

    # ─── 路径决策 ─────────────────────────────────────────────────
    if path_scores["deep"] > 0:
        path = "deep"
    elif path_scores["standard"] > 0:
        path = "standard"
    else:
        path = "fast"

    # 置信度：看最高分和次高分的差距
    scores_sorted = sorted(path_scores.values(), reverse=True)
    confidence = "HIGH" if (scores_sorted[0] - scores_sorted[1]) >= 3 else "MEDIUM"
    if confidence == "MEDIUM" and path == "fast" and drop_1h_pct > -2:
        confidence = "HIGH"

    path_map = {
        "fast": ("🟢", "Fast Path", []),
        "standard": ("🟡", "Standard Path", ["A", "B"]),
        "deep": ("🔴", "Deep Path", ["A", "B", "C", "D"]),
    }
    emoji, label, gates = path_map[path]

    return {
        "path": path,
        "emoji": emoji,
        "label": label,
        "confidence": confidence,
        "reasons": reasons,
        "gates": gates,
        "scores": path_scores,
    }


def print_triage_result(result: dict, drop_1h_pct: float, drop_24h_pct: float):
    SEP = "━" * 60
    print(f"\n{SEP}")
    print("🔀 分诊结果")
    print(SEP)
    print(f"路径：{result['emoji']} {result['label']}")
    print(f"置信度：{result['confidence']}")
    print()
    print("触发原因：")
    for r in result["reasons"]:
        print(f"  ✓ {r}")
    print()
    if result["gates"]:
        print(f"GATE 检查点：{'→'.join(['GATE ' + g for g in result['gates']])}")
    else:
        print("GATE 检查点：无（自动完成）")
    print(SEP)
    print()


def main():
    parser = argparse.ArgumentParser(description="新笔记诊断分诊脚本")
    parser.add_argument("--drop-1h", type=float, required=True,
                        help="1H指标跌幅（负数，如 -18.5）")
    parser.add_argument("--drop-24h", type=float, default=None,
                        help="24H指标跌幅（负数）")
    parser.add_argument("--watchlist-hits", type=int, default=0,
                        help="watchlist命中总数")
    parser.add_argument("--hit-levels", type=str, default="",
                        help="命中级别，逗号分隔，如 critical,high,medium")
    parser.add_argument("--contradiction", action="store_true",
                        help="是否存在矛盾判断")
    parser.add_argument("--absolute-value", type=float, default=None,
                        help="1H指标绝对值，如 0.0523")
    parser.add_argument("--acute-drop", action="store_true",
                        help="是否检测到急跌信号")
    parser.add_argument("--json", action="store_true",
                        help="以 JSON 格式输出结果")
    args = parser.parse_args()

    hit_levels = [l.strip() for l in args.hit_levels.split(",") if l.strip()]

    result = triage(
        drop_1h_pct=args.drop_1h,
        drop_24h_pct=args.drop_24h,
        watchlist_hits=args.watchlist_hits,
        hit_levels=hit_levels,
        has_contradiction=args.contradiction,
        absolute_value=args.absolute_value,
        acute_drop_detected=args.acute_drop,
    )

    if args.json:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_triage_result(result, args.drop_1h, args.drop_24h)

    # exit code: 0=fast, 1=standard, 2=deep
    exit_codes = {"fast": 0, "standard": 1, "deep": 2}
    sys.exit(exit_codes[result["path"]])


if __name__ == "__main__":
    main()
