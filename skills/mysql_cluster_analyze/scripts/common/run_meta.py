#!/usr/bin/env python3
"""
run_meta.py — run_meta.json 的读写工具

run_meta.json 记录每次 Layer 2 诊断的元信息，供 generate_process_review.py 读取。
文件位置：<OUT_DIR>/run_meta.json

Schema:
{
    "cluster":          "redtao_antispam",
    "run_id":           "redtao_antispam_20260404_040000",
    "path":             "B",            // 诊断路径：A/B/B2/C1/C2/D/E/F/G
    "path_label":       "CPU 高",       // 路径中文描述
    "time_range":       "2026-04-04 04:00 ~ 04:30",  // 北京时间
    "fault_time":       "2026-04-04 04:15:00",        // 北京时间
    "main_report_url":  "https://...",  // Step 5 上传后填写
    "review_report_url":"https://...",  // Step 7 上传后填写
    "notes":            [],             // AI 在诊断过程中追加的改进建议
    "created_at":       "2026-04-04T04:00:00+08:00"
}

用法（CLI）：
    # 初始化（Step 0 之后调用）
    python3 scripts/common/run_meta.py init \
        --out_dir <OUT_DIR> \
        --cluster redtao_antispam \
        --run_id  redtao_antispam_20260404_040000 \
        --path    B \
        --time_range "2026-04-04 04:00 ~ 04:30" \
        [--fault_time "2026-04-04 04:15:00"]

    # 更新单个字段
    python3 scripts/common/run_meta.py set \
        --out_dir <OUT_DIR> \
        --key main_report_url \
        --value "https://..."

    # 追加 note（改进建议）
    python3 scripts/common/run_meta.py note \
        --out_dir <OUT_DIR> \
        --text "get_error_log 接口返回 404，建议平台补全"

    # 读取（打印 JSON）
    python3 scripts/common/run_meta.py get --out_dir <OUT_DIR>
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
META_FILENAME = "run_meta.json"

PATH_LABELS = {
    "A":  "慢查询",
    "B":  "CPU 高",
    "B2": "连接堆积",
    "C1": "主从延迟",
    "C":  "主从延迟",
    "C2": "复制中断",
    "D":  "磁盘满",
    "E":  "Crash",
    "F":  "机器带宽",
    "G":  "IOWait",
}


def meta_path(out_dir: str) -> Path:
    return Path(out_dir) / META_FILENAME


def load(out_dir: str) -> dict:
    p = meta_path(out_dir)
    if p.exists():
        return json.loads(p.read_text())
    return {}


def save(out_dir: str, data: dict) -> None:
    p = meta_path(out_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_init(args):
    path_label = PATH_LABELS.get(args.path, args.path)
    data = {
        "cluster":           args.cluster,
        "run_id":            args.run_id,
        "path":              args.path,
        "path_label":        path_label,
        "time_range":        args.time_range,
        "fault_time":        getattr(args, "fault_time", ""),
        "main_report_url":   "",
        "review_report_url": "",
        "notes":             [],
        "created_at":        datetime.now(CST).isoformat(),
    }
    save(args.out_dir, data)
    print(f"[run_meta] ✅ 初始化完成：{meta_path(args.out_dir)}")
    print(f"  cluster={data['cluster']}  path={data['path']}({path_label})  run_id={data['run_id']}")


def cmd_set(args):
    data = load(args.out_dir)
    data[args.key] = args.value
    save(args.out_dir, data)
    print(f"[run_meta] ✅ 已更新 {args.key}={args.value}")


def cmd_note(args):
    data = load(args.out_dir)
    if "notes" not in data:
        data["notes"] = []
    entry = {
        "text": args.text,
        "ts": datetime.now(CST).isoformat(),
    }
    data["notes"].append(entry)
    save(args.out_dir, data)
    print(f"[run_meta] ✅ note 已追加：{args.text[:60]}")


def cmd_get(args):
    data = load(args.out_dir)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="run_meta.json 读写工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # init
    p_init = sub.add_parser("init", help="初始化 run_meta.json")
    p_init.add_argument("--out_dir",    required=True)
    p_init.add_argument("--cluster",    required=True)
    p_init.add_argument("--run_id",     required=True)
    p_init.add_argument("--path",       required=True, help="诊断路径：A/B/B2/C1/C2/D/E/F/G")
    p_init.add_argument("--time_range", required=True, help="北京时间范围，如 '2026-04-04 04:00 ~ 04:30'")
    p_init.add_argument("--fault_time", default="",   help="故障时刻（北京时间）")

    # set
    p_set = sub.add_parser("set", help="更新单个字段")
    p_set.add_argument("--out_dir", required=True)
    p_set.add_argument("--key",     required=True)
    p_set.add_argument("--value",   required=True)

    # note
    p_note = sub.add_parser("note", help="追加改进建议")
    p_note.add_argument("--out_dir", required=True)
    p_note.add_argument("--text",    required=True)

    # get
    p_get = sub.add_parser("get", help="打印 run_meta.json")
    p_get.add_argument("--out_dir", required=True)

    args = parser.parse_args()
    {"init": cmd_init, "set": cmd_set, "note": cmd_note, "get": cmd_get}[args.cmd](args)


if __name__ == "__main__":
    main()
