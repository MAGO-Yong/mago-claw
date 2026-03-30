import argparse
import re
import sys
import time
import requests
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# 时间解析工具（内嵌，参考 xray-log-query/scripts/to_timestamp.py）
# ---------------------------------------------------------------------------

# 支持的 datetime 格式列表（按优先级顺序尝试）
_DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%Y%m%d%H%M%S",
    "%Y%m%d",
]

# 相对时间表达式：now[+-]<number><unit>
_RELATIVE_PATTERN = re.compile(
    r"^now\s*([+-])\s*(\d+)\s*(s|sec|m|min|h|hour|d|day)s?$",
    re.IGNORECASE,
)

_UNIT_SECONDS = {
    "s": 1,
    "sec": 1,
    "m": 60,
    "min": 60,
    "h": 3600,
    "hour": 3600,
    "d": 86400,
    "day": 86400,
}


def _parse_relative(text: str):
    """解析相对时间表达式，返回 Unix 秒；不匹配则返回 None。"""
    m = _RELATIVE_PATTERN.match(text.strip())
    if not m:
        return None
    sign, amount, unit = m.group(1), int(m.group(2)), m.group(3).lower()
    delta = amount * _UNIT_SECONDS[unit]
    now = int(time.time())
    return now + delta if sign == "+" else now - delta


def _parse_unix_ts(text: str):
    """
    识别纯数字时间戳，返回秒级值；
    13 位及以上（毫秒）自动除以 1000。不匹配则返回 None。
    """
    text = text.strip()
    if not re.fullmatch(r"\d+", text):
        return None
    ts = int(text)
    if ts > 9_999_999_999:  # 毫秒时间戳
        ts = ts // 1000
    return ts


def _parse_datetime_str(text: str):
    """逐一尝试已知格式解析 datetime 字符串，返回 Unix 秒（本地时区）；失败返回 None。"""
    text = text.strip()
    for fmt in _DATETIME_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return int(time.mktime(dt.timetuple()))
        except ValueError:
            continue
    return None


def to_unix_seconds(text: str) -> int:
    """
    将任意时间表示转换为 Unix 秒时间戳（本地时区）。

    支持：
      - "now"
      - 相对表达式："now-15m", "now-1h", "now+30m", "now-2d"
      - Unix 秒时间戳：1700000000
      - Unix 毫秒时间戳：1700000000000（自动识别）
      - 日期时间字符串："2024-03-25 14:00:00" / "2024-03-25T14:00:00" 等

    Returns:
        Unix 秒时间戳（int）

    Raises:
        ValueError: 无法识别的格式
    """
    text = text.strip()

    # 1. "now"
    if text.lower() == "now":
        return int(time.time())

    # 2. 相对表达式
    result = _parse_relative(text)
    if result is not None:
        return result

    # 3. 纯数字时间戳（秒或毫秒）
    result = _parse_unix_ts(text)
    if result is not None:
        return result

    # 4. datetime 字符串
    result = _parse_datetime_str(text)
    if result is not None:
        return result

    raise ValueError(
        f"无法识别的时间格式: {text!r}\n"
        "支持：now / now-15m / now-1h / 1700000000 / 1700000000000 / "
        '"2024-03-25 14:00:00" 等'
    )


def to_datetime_str(text: str) -> str:
    """
    将任意时间表示转换为 API 所需的 "YYYY-MM-DD HH:MM:SS" 格式字符串（本地时区）。

    Args:
        text: 任意时间表示（时间戳、相对时间、datetime 字符串）

    Returns:
        格式化后的 datetime 字符串，如 "2026-03-26 13:20:00"

    Raises:
        ValueError: 无法识别的格式
    """
    unix_ts = to_unix_seconds(text)
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(unix_ts))


# ---------------------------------------------------------------------------
# 主分析逻辑
# ---------------------------------------------------------------------------


def run_analysis(analysis_type, service, raw_start_time, raw_end_time):
    # Mapping of analysis type to corresponding API endpoint
    endpoints = {
        "problem": "/api/diagnosis/service/analysis/problem",
        "rpc": "/api/diagnosis/service/analysis/rpc",
    }

    if analysis_type not in endpoints:
        print(
            f"Error: Unsupported analysis type '{analysis_type}'. Supported: {list(endpoints.keys())}",
            file=sys.stderr,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # 时间转换：在调用接口前统一转为 "YYYY-MM-DD HH:MM:SS" 格式
    # ------------------------------------------------------------------
    try:
        start_time = to_datetime_str(raw_start_time)
        end_time = to_datetime_str(raw_end_time)
    except ValueError as e:
        print(f"[ERROR] 时间参数解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"[INFO] 时间范围: {raw_start_time!r} → {start_time}  |  {raw_end_time!r} → {end_time}",
        file=sys.stderr,
    )

    # ------------------------------------------------------------------
    # 校验时间顺序
    # ------------------------------------------------------------------
    start_ts = to_unix_seconds(raw_start_time)
    end_ts = to_unix_seconds(raw_end_time)
    if end_ts <= start_ts:
        print(
            f"[ERROR] 结束时间 ({end_time}) 不晚于开始时间 ({start_time})，请检查输入",
            file=sys.stderr,
        )
        sys.exit(1)

    url = f"https://xray-ai.devops.xiaohongshu.com{endpoints[analysis_type]}"
    headers = {
        "User-Agent": "Apipost client Runtime/+https://www.apipost.cn/",
        "Content-Type": "application/json",
    }
    data = {"service": service, "startTime": start_time, "endTime": end_time}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        # Return full JSON output for processing
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except requests.exceptions.RequestException as e:
        print(f"Error calling {analysis_type} API: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Xray Service Analysis Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
时间参数支持以下格式（--startTime / --endTime）：
  相对时间:   now-15m  now-1h  now-2d  now
  Unix 秒:    1700000000
  Unix 毫秒:  1700000000000  （自动识别并转换）
  日期时间:   "2026-03-26 13:20:00"  "2026-03-26T13:20:00"  "2026-03-26 13:20"

示例:
  python3 analyze_service.py --type problem --service my-service --startTime now-15m --endTime now
  python3 analyze_service.py --type service --service my-service --startTime 1700000000 --endTime 1700003600
  python3 analyze_service.py --type problem --service my-service --startTime "2026-03-26 13:00:00" --endTime "2026-03-26 13:30:00"
""",
    )
    parser.add_argument(
        "--type",
        choices=["problem", "rpc"],
        default="problem",
        help="Analysis type: problem or rpc",
    )
    parser.add_argument("--service", required=True, help="Service name")
    parser.add_argument(
        "--startTime",
        required=True,
        help='开始时间，支持: now-15m / Unix时间戳(秒或毫秒) / "2026-03-26 13:00:00"',
    )
    parser.add_argument(
        "--endTime",
        required=True,
        help='结束时间，支持: now / Unix时间戳(秒或毫秒) / "2026-03-26 13:30:00"',
    )

    args = parser.parse_args()
    run_analysis(args.type, args.service, args.startTime, args.endTime)
