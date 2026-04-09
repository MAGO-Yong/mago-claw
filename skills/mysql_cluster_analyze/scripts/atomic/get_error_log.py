#!/usr/bin/env python3
"""
get_error_log.py — 采集原机 error log (mysqld.log)

接口（优先）：POST /dms-api/ai-api/v1/mysql/meta_data/get_error_log
接口（兜底）：POST /dms-api/open-claw/meta-data/mysql/get-error-log
认证：DMS_AI_TOKEN（v1） / DMS_CLAW_TOKEN（open-claw）

注意：start_time / end_time 为北京时间，时间窗口 ≤ 60 分钟

用法：
  python3 get_error_log.py \
      --hostname qsh8-db-redtao-antispam-u5trt-11 \
      --start "2026-04-02 04:25:00" \
      --end   "2026-04-02 04:35:00" \
      [--level_filter "Error,Warning"] \
      [--keyword "page_cleaner"] \
      [--output <dir>] [--run_id <id>]
"""

import argparse
import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime as _dt
from pathlib import Path

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
from common.dms_client import (
    AI_TOKEN, AI_V1_PREFIX, OPEN_CLAW_PREFIX, CLAW_TOKEN,
    _AI_HEADERS, _http_post, call_with_fallback,
)

TOKEN = CLAW_TOKEN


def fetch_error_log(
    hostname: str,
    start_time: str,
    end_time: str,
    level_filter: list = None,
    keyword: str = "",
) -> dict:
    payload = {
        "hostname": hostname,
        "start_time": start_time,
        "end_time": end_time,
    }
    if level_filter:
        payload["level_filter"] = level_filter
    if keyword:
        payload["keyword"] = keyword

    def _v1():
        return _http_post(
            f"{AI_V1_PREFIX}/mysql/meta_data/get_error_log",
            payload,
            _AI_HEADERS,
            timeout=60,
        )

    def _old():
        return _http_post(
            f"{OPEN_CLAW_PREFIX}/meta-data/mysql/get-error-log",
            payload,
            {"dms-claw-token": TOKEN},
            timeout=60,
        )

    try:
        return call_with_fallback(_v1, _old, "[get_error_log]")
    except Exception as e:
        raise RuntimeError(f"[get_error_log] 请求失败：{e}")


def main():
    parser = argparse.ArgumentParser(description="采集原机 error log (mysqld.log)")
    parser.add_argument("--hostname", required=True, help="实例 hostname（vm_name 或 IP）")
    parser.add_argument("--start", required=True, help="开始时间（北京时间），格式：2026-04-02 04:25:00")
    parser.add_argument("--end", required=True, help="结束时间（北京时间），格式：2026-04-02 04:35:00")
    parser.add_argument("--level_filter", default="", help="日志级别过滤，逗号分隔，如 Error,Warning")
    parser.add_argument("--keyword", default="", help="关键词过滤（不区分大小写）")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    args = parser.parse_args()

    if not AI_TOKEN and not TOKEN:
        print("[get_error_log] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    level_filter = [lv.strip() for lv in args.level_filter.split(",") if lv.strip()] if args.level_filter else None

    # 校验时间窗口 ≤ 60 分钟
    try:
        _start = _dt.strptime(args.start, "%Y-%m-%d %H:%M:%S")
        _end = _dt.strptime(args.end, "%Y-%m-%d %H:%M:%S")
        _delta = (_end - _start).total_seconds()
        if _delta > 3600:
            print(f"[get_error_log] ⚠️ 时间窗口 {_delta/60:.0f} 分钟，超过 60 分钟限制，可能被截断", file=sys.stderr)
        if _delta <= 0:
            print(f"[get_error_log] ❌ end 必须晚于 start", file=sys.stderr)
            sys.exit(1)
    except ValueError:
        pass  # 时间格式异常交由 API 返回错误

    try:
        result = fetch_error_log(
            args.hostname, args.start, args.end,
            level_filter, args.keyword,
        )
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    # 检查 API 响应错误（兼容 v1 errorMessage 和 open-claw code）
    if result.get("errorMessage"):
        print(f"[get_error_log] ❌ API 返回错误：{result['errorMessage']}", file=sys.stderr)
        sys.exit(1)
    api_code = result.get("code")
    if api_code is not None and api_code != 0:
        msg = result.get("message", "未知错误")
        print(f"[get_error_log] ❌ API 返回错误（code={api_code}）：{msg}", file=sys.stderr)
        sys.exit(1)

    output_str = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output and not args.run_id:
        print("[get_error_log] ⚠️ 指定了 --output 但未指定 --run_id，结果不会落盘", file=sys.stderr)

    if args.output and args.run_id:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        out_file = raw_dir / "get_error_log.json"
        out_file.write_text(output_str, encoding="utf-8")
        print(f"[get_error_log] ✅ 已写入 {out_file}", file=sys.stderr)

    print(output_str)

    # 打印摘要到 stderr
    data = result.get("data", {})
    summary = data.get("summary", {})
    total = summary.get("total_lines", "?")
    errors = summary.get("error_count", 0)
    warnings = summary.get("warning_count", 0)
    keywords = summary.get("critical_keywords_found", [])
    print(f"[get_error_log] 总行数：{total}，Error：{errors}，Warning：{warnings}", file=sys.stderr)
    if keywords:
        print(f"[get_error_log] 关键词命中：{', '.join(keywords)}", file=sys.stderr)


if __name__ == "__main__":
    main()
