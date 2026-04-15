#!/usr/bin/env python3
"""
通用极简发布脚本 — AI 生成 HTML 后调用。

执行三步（不含任何分析或渲染逻辑）：
  1. dms_upload  — 上传 HTML 到 DMS，获得 dms_url
  2. run_meta    — 写入 main_report_url（或 --meta_key 指定的 key）
  3. send_report — 推送 webhook 通知

用法：
    python3 scripts/common/publish_report.py \\
        --html_path output/xxx/report.html \\
        --out_dir   output/xxx \\
        --cluster   ads_ad_core \\
        --time_range "09:54~10:04" \\
        --path B2 --path_label RowLock \\
        --severity P1 \\
        --root_cause "行锁堆积，row_lock_count=16" \\
        --p0_action "KILL 持锁连接，调低 innodb_lock_wait_timeout"

所有路径（B2-RowLock / B2-AutoInc / B2-Leak / 其他）共用此脚本。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dms_upload import upload_file
from notify import send_report
import run_meta as _run_meta


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 诊断报告通用发布脚本")

    parser.add_argument("--html_path",  required=True, help="AI 生成的 HTML 文件本地路径")
    parser.add_argument("--out_dir",    required=True, help="run_meta.json 所在目录（诊断输出根目录）")
    parser.add_argument("--cluster",    required=True, help="集群名，用于 notify 推送摘要")
    parser.add_argument("--time_range", required=True, help="诊断窗口，如 '09:54~10:04'")
    parser.add_argument("--file_name",  default=None,  help="DMS 上传文件名，默认取 html_path 的 basename")
    parser.add_argument("--path",       default="B2",      help="诊断路径字母，如 B2 / D / F（默认 B2）")
    parser.add_argument("--path_label", default="RowLock", help="路径描述，如 RowLock / AutoInc（默认 RowLock）")
    parser.add_argument("--severity",   default="P1",      help="故障等级 P0/P1/P2（默认 P1）")
    parser.add_argument("--root_cause", default="",        help="根因一句话，用于 notify 推送摘要")
    parser.add_argument("--p0_action",  default="",        help="P0 处置建议，用于 notify 推送摘要")
    parser.add_argument("--meta_key",   default="main_report_url",
                        help="写入 run_meta.json 的 key（默认 main_report_url；复盘报告传 review_report_url）")

    args = parser.parse_args()

    html_path = Path(args.html_path)
    out_dir   = args.out_dir
    file_name = args.file_name or html_path.name

    # ── Step 1: dms_upload ──────────────────────────────────────────
    if not html_path.exists():
        print(f"[publish_report] ❌ HTML 文件不存在: {html_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[publish_report] 上传 {html_path.name} → DMS ...")
    try:
        dms_url = upload_file(str(html_path), file_name)
    except Exception as e:
        print(f"[publish_report] ❌ dms_upload 失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not dms_url:
        print("[publish_report] ❌ dms_upload 返回空 URL", file=sys.stderr)
        sys.exit(1)

    print(f"[publish_report] ✅ 上传成功: {dms_url}")

    # ── Step 2: run_meta 写入 main_report_url ───────────────────────
    try:
        meta = _run_meta.load(out_dir)
        meta[args.meta_key] = dms_url
        _run_meta.save(out_dir, meta)
        print(f"[publish_report] ✅ run_meta.json 已写入 {args.meta_key}")
    except Exception as e:
        print(f"[publish_report] ❌ run_meta 写入失败: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Step 3: send_report (notify) ────────────────────────────────
    print(f"[publish_report] 推送 webhook 通知 ...")
    try:
        ok = send_report(
            cluster_name=args.cluster,
            time_range=args.time_range,
            dms_url=dms_url,
            path=args.path,
            path_label=args.path_label,
            severity=args.severity,
            root_cause=args.root_cause,
            p0_action=args.p0_action,
        )
    except Exception as e:
        print(f"[publish_report] ❌ send_report 异常: {e}", file=sys.stderr)
        sys.exit(1)

    if not ok:
        print("[publish_report] ❌ send_report 返回 False，推送失败", file=sys.stderr)
        sys.exit(1)

    print(f"[publish_report] ✅ 推送成功")
    print(f"[publish_report] 报告地址: {dms_url}")


if __name__ == "__main__":
    main()
