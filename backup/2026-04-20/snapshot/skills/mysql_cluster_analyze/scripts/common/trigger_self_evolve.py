#!/usr/bin/env python3
"""
trigger_self_evolve.py — 诊断完成后挂载 skill-self-evolve 的标准入口

执行流程：
  1. 检查复盘报告是否存在；若不存在，先调用 generate_process_review.py 生成
  2. 询问用户是否触发 skill 自迭代（--auto 跳过询问）
  3. 依次执行 parse → generate_patch → apply_patch → validate

用法：
    python3 scripts/common/trigger_self_evolve.py \
        --out_dir  <OUT_DIR> \
        --run_id   <RUN_ID> \
        [--skill_dir <target_skill_dir>] \
        [--auto]

    # 兼容旧接口（直接传复盘报告路径）
    python3 scripts/common/trigger_self_evolve.py \
        --report_path <path/to/report_process_review.html> \
        [--skill_dir ...] \
        [--auto]
"""

import argparse
import glob
import subprocess
import sys
import os
from pathlib import Path

SKILL_DIR        = Path(__file__).resolve().parents[2]          # mysql_cluster_analyze/
SELF_EVOLVE_DIR  = Path.home() / ".openclaw/workspace/skills/skill-self-evolve/scripts"
DEFAULT_TARGET   = SKILL_DIR


def run_step(cmd: list, desc: str) -> bool:
    """执行一个子步骤，打印输出，返回是否成功。"""
    print(f"[skill-self-evolve] ▶ {desc}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        print(f"[skill-self-evolve] ❌ {desc} 失败：{result.stderr.strip()}", file=sys.stderr)
        return False
    print(f"[skill-self-evolve] ✅ {desc} 完成")
    return True


def find_review_report(out_dir: Path, run_id: str) -> Path | None:
    """在 out_dir 下查找复盘报告文件。"""
    # 精确匹配
    exact = out_dir / f"report_process_review_{run_id}.html"
    if exact.exists():
        return exact
    # 模糊匹配
    matches = sorted(out_dir.glob("report_process_review_*.html"))
    return matches[0] if matches else None


def ensure_review_report(out_dir: Path, run_id: str, auto: bool) -> Path | None:
    """
    确保复盘报告存在。若不存在则：
    - 调用 generate_process_review.py 自动生成
    返回复盘报告路径，失败返回 None。
    """
    report = find_review_report(out_dir, run_id)
    if report:
        print(f"[trigger_self_evolve] ✅ 复盘报告已存在：{report.name}")
        return report

    # 缺失 → 尝试自动生成
    print(f"\n[trigger_self_evolve] ⚠️  未找到复盘报告（report_process_review_{run_id}.html）")
    print(f"[trigger_self_evolve] ▶ 自动调用 generate_process_review.py 生成...")

    gen_script = SKILL_DIR / "scripts/common/generate_process_review.py"
    ok = run_step(
        ["python3", str(gen_script), "--out_dir", str(out_dir), "--run_id", run_id],
        "生成复盘报告"
    )
    if not ok:
        print(f"[trigger_self_evolve] ❌ 复盘报告生成失败，跳过自迭代。", file=sys.stderr)
        return None

    report = find_review_report(out_dir, run_id)
    if not report:
        print(f"[trigger_self_evolve] ❌ 生成后仍未找到报告文件，跳过自迭代。", file=sys.stderr)
        return None

    print(f"[trigger_self_evolve] ✅ 复盘报告已生成：{report.name}")
    return report


def run_self_evolve(report_html: Path, skill_dir: Path) -> bool:
    """依次执行 parse → generate_patch → apply_patch → validate 四步。"""
    s = str(SELF_EVOLVE_DIR)
    steps = [
        (["python3", f"{s}/parse_review.py",
          "--input",  str(report_html),
          "--output", "/tmp/review_parsed.json"],
         "解析复盘报告"),
        (["python3", f"{s}/generate_patch.py",
          "--input",     "/tmp/review_parsed.json",
          "--skill-dir", str(skill_dir),
          "--output",    "/tmp/patch_plan.json"],
         "生成 patch 计划"),
        (["python3", f"{s}/apply_patch.py",
          "--plan",      "/tmp/patch_plan.json",
          "--skill-dir", str(skill_dir)],
         "执行 patch"),
        (["python3", f"{s}/validate_patch.py",
          "--skill-dir", str(skill_dir)],
         "验证改动"),
    ]
    for cmd, desc in steps:
        if not run_step(cmd, desc):
            return False

    # 打印 CHANGELOG 末尾
    changelog = skill_dir / "CHANGELOG.md"
    if changelog.exists():
        lines = changelog.read_text().splitlines()
        print("\n[skill-self-evolve] 📋 CHANGELOG 最新记录：")
        print("\n".join(lines[-20:]))
    return True


def main():
    parser = argparse.ArgumentParser(description="诊断完成后触发 skill-self-evolve 迭代")

    # 新接口（推荐）
    parser.add_argument("--out_dir",  help="诊断输出目录（OUT_DIR）")
    parser.add_argument("--run_id",   help="Run ID")

    # 旧接口（兼容）
    parser.add_argument("--report_path", help="复盘报告 HTML 路径（旧接口，优先 --out_dir）")

    parser.add_argument("--skill_dir", default=str(DEFAULT_TARGET),
                        help=f"要迭代的 skill 目录（默认：{DEFAULT_TARGET}）")
    parser.add_argument("--auto", action="store_true",
                        help="不询问用户确认，直接执行")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir)

    # ── 确定复盘报告路径 ──────────────────────────────────────────────────────
    if args.out_dir and args.run_id:
        out_dir = Path(args.out_dir)
        run_id  = args.run_id
        report  = ensure_review_report(out_dir, run_id, args.auto)
        if report is None:
            sys.exit(1)

    elif args.report_path:
        # 旧接口兼容
        report = Path(args.report_path)
        if not report.exists():
            print(f"[trigger_self_evolve] ⚠️  复盘报告文件不存在：{report}，跳过。", file=sys.stderr)
            sys.exit(0)
        # 尝试从路径推断 out_dir / run_id，用于缺失时生成
        out_dir = report.parent
        run_id  = report.stem.replace("report_process_review_", "")

    else:
        parser.error("必须提供 --out_dir + --run_id，或 --report_path")

    # ── 用户确认 ──────────────────────────────────────────────────────────────
    if not args.auto:
        print(f"\n🔄 诊断报告已就绪，是否触发 skill 自迭代？(y/N) ", end="", flush=True)
        try:
            ans = input().strip().lower()
        except EOFError:
            ans = "n"
        if ans not in ("y", "yes"):
            print("[trigger_self_evolve] 跳过自迭代。")
            sys.exit(0)

    # ── 执行自迭代 ────────────────────────────────────────────────────────────
    ok = run_self_evolve(report, skill_dir)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
