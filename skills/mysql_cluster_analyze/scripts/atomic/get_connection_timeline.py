#!/usr/bin/env python3
"""
get_connection_timeline.py — 连接数时序快速查询

一键输出连接数时序图（ASCII 可视化），自动识别锁积压模式

用法：
  python3 get_connection_timeline.py \
      --cluster redtao_antispam \
      --node qsh8-db-redtao-antispam-u5trt-11 \
      --start "2026-04-02 04:00:00" \
      --end "2026-04-02 05:00:00" \
      [--detect-locks]  # 自动检测锁积压事件
      [--threshold-drop 10]  # 锁获取阈值（连接数低于此值）
      [--threshold-surge 100]  # 积压爆发阈值（连接数高于此值）

输出：
  - ASCII 时序图
  - 锁积压事件列表（如有）
  - 统计摘要
"""

import argparse
import json
import sys
import urllib.parse
from datetime import datetime
from typing import List, Optional
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from common.dms_client import (
    AI_TOKEN, CLAW_TOKEN, BASE_URL, AI_V1_PREFIX,
    _AI_HEADERS, _http_post, call_with_fallback,
)

TOKEN = CLAW_TOKEN  # open-claw 兜底用

# 默认阈值
DEFAULT_THRESHOLD_DROP = 10       # 锁获取：连接数低于此值
DEFAULT_THRESHOLD_PREV = 20       # 锁获取：前一点连接数高于此值
DEFAULT_THRESHOLD_SURGE = 100     # 积压爆发：连接数高于此值
DEFAULT_MAX_LOOKAHEAD = 50        # 往前查找峰值的最大点数
DEFAULT_MAX_LOOKAHEAD_RELEASE = 20  # 往后查找释放点的最大点数

ConnectionEvent = namedtuple('ConnectionEvent', ['timestamp', 'count'])
LockSurge = namedtuple('LockSurge', ['start', 'end', 'duration_min', 'peak'])


def parse_timestamp(ts: str) -> Optional[datetime]:
    """
    解析时间戳，支持多种格式
    
    Args:
        ts: 时间字符串
        
    Returns:
        datetime 对象，解析失败返回 None
    """
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    
    # 截取前 19 个字符（去掉毫秒和时区）
    ts_clean = ts[:19] if len(ts) > 19 else ts
    
    for fmt in formats:
        try:
            return datetime.strptime(ts_clean, fmt)
        except ValueError:
            continue
    
    # 尝试 ISO 格式
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except:
        pass
    
    return None


def _call_count_list(vm_name: str, start_time: str, end_time: str) -> dict:
    """调用 get_his_process_count_list，v1 优先，open-claw 兜底。"""
    payload = {
        "vm_name": vm_name,
        "start_time": start_time,
        "end_time": end_time,
        "show_system_session": False,
    }
    payload_old = {
        "vm_name": vm_name,
        "start_time": start_time,
        "end_time": end_time,
        "filter": {"show_system_session": False},
    }
    return call_with_fallback(
        lambda: _http_post(f"{AI_V1_PREFIX}/mysql/session/get_his_process_count_list", payload, _AI_HEADERS),
        lambda: _http_post(f"{BASE_URL}/dms-api/v1/mysql/session-manage/get-his-process-count-list", payload_old, {"dms-claw-token": TOKEN}),
        "[get_connection_timeline]",
    )


def get_connection_timeline(vm_name: str, start: str, end: str) -> List[ConnectionEvent]:
    """
    获取连接数时序
    
    Args:
        vm_name: 虚拟机名称
        start: 开始时间
        end: 结束时间
        
    Returns:
        连接数事件列表，失败返回空列表
    """
    try:
        result = _call_count_list(vm_name, start, end)
    except Exception as e:
        print(f"  ⚠️ API 错误: {e}", file=sys.stderr)
        return []

    if result.get("code", -1) != 0:
        print(f"  ⚠️ API 返回 code={result.get('code')}: {result.get('message', '')}", file=sys.stderr)
        return []

    events = []
    for item in result.get('data', []):
        ct = item.get('create_time') or item.get('createTime') or ''
        count = item.get('count', 0)
        if ct:
            events.append(ConnectionEvent(timestamp=ct, count=count))
    return events


def detect_lock_surges(
    events: List[ConnectionEvent],
    threshold_drop: int = DEFAULT_THRESHOLD_DROP,
    threshold_prev: int = DEFAULT_THRESHOLD_PREV,
    threshold_surge: int = DEFAULT_THRESHOLD_SURGE,
    max_lookahead: int = DEFAULT_MAX_LOOKAHEAD,
    max_lookahead_release: int = DEFAULT_MAX_LOOKAHEAD_RELEASE
) -> List[LockSurge]:
    """
    自动检测锁积压模式：骤降→暴涨
    
    算法：
    1. 找骤降：count < threshold_drop，前一点 count > threshold_prev
    2. 找暴涨：在骤降后 count > threshold_surge
    3. 找释放：暴涨后 count < threshold_drop
    
    Args:
        events: 连接数事件列表
        threshold_drop: 锁获取/释放的连接数阈值
        threshold_prev: 前一时刻连接数阈值
        threshold_surge: 积压爆发阈值
        max_lookahead: 往前查找峰值的最大点数
        max_lookahead_release: 往后查找释放点的最大点数
        
    Returns:
        锁积压事件列表
    """
    surges = []
    i = 0
    
    while i < len(events) - 1:
        # 找骤降点（锁获取）
        if i > 0 and events[i].count < threshold_drop and events[i-1].count > threshold_prev:
            lock_start = events[i]
            
            # 往后找暴涨点
            peak = None
            peak_idx = i
            for j in range(i+1, min(i+max_lookahead, len(events))):
                if events[j].count > threshold_surge:
                    if peak is None or events[j].count > peak.count:
                        peak = events[j]
                        peak_idx = j
            
            if peak:
                # 找释放点（锁释放后连接数骤降）
                release = None
                for j in range(peak_idx+1, min(peak_idx+max_lookahead_release, len(events))):
                    if events[j].count < threshold_drop:
                        release = events[j]
                        break
                
                # 计算持锁时长
                start_dt = parse_timestamp(lock_start.timestamp)
                if release and start_dt:
                    end_dt = parse_timestamp(release.timestamp)
                    if end_dt:
                        duration = (end_dt - start_dt).total_seconds() / 60
                    else:
                        duration = None
                else:
                    duration = None
                
                surges.append(LockSurge(
                    start=lock_start.timestamp,
                    end=release.timestamp if release else "未释放",
                    duration_min=duration,
                    peak=peak.count
                ))
                
                i = peak_idx + 1
                continue
        
        i += 1
    
    return surges


def print_timeline(events: List[ConnectionEvent], surges: List[LockSurge]):
    """
    打印 ASCII 时序图
    
    Args:
        events: 连接数事件列表
        surges: 锁积压事件列表
    """
    if not events:
        print("  无数据")
        return
    
    max_count = max(e.count for e in events)
    bar_width = 40
    
    print(f"\n{'时间':19s} {'连接数':>8s} {'可视化':{bar_width}s} 事件")
    print("-" * (19 + 1 + 8 + 1 + bar_width + 10))
    
    # 标记锁积压时段
    surge_periods = set()
    for surge in surges:
        start_dt = parse_timestamp(surge.start)
        if start_dt is None:
            continue
        if surge.end != "未释放":
            end_dt = parse_timestamp(surge.end)
            if end_dt is None:
                continue
            for e in events:
                e_dt = parse_timestamp(e.timestamp)
                if e_dt and start_dt <= e_dt <= end_dt:
                    surge_periods.add(e.timestamp)
    
    # 打印时序
    prev_count = None
    for i, e in enumerate(events):
        # 计算趋势
        if prev_count is not None:
            delta = e.count - prev_count
            if delta > 50:
                trend = "🚨"
            elif delta > 20:
                trend = "↑"
            elif delta < -20:
                trend = "⬇️"
            else:
                trend = ""
        else:
            trend = ""
        
        # 标记锁积压时段
        marker = "🔒" if e.timestamp in surge_periods else "  "
        
        # 计算进度条
        if max_count > 0:
            bar_len = int(e.count / max_count * bar_width)
        else:
            bar_len = 0
        
        if e.timestamp in surge_periods:
            bar = "█" * bar_len
        else:
            bar = "░" * bar_len
        
        print(f"{e.timestamp}  {e.count:>8d} {bar:{bar_width}s} {trend}{marker}")
        prev_count = e.count


def print_statistics(events: List[ConnectionEvent], surges: List[LockSurge]):
    """
    打印统计摘要
    
    Args:
        events: 连接数事件列表
        surges: 锁积压事件列表
    """
    if not events:
        return
    
    counts = [e.count for e in events]
    print(f"\n{'='*60}")
    print("📊 统计摘要")
    print(f"{'='*60}")
    print(f"  采样点数:     {len(events)}")
    print(f"  时间跨度:     {events[0].timestamp} ~ {events[-1].timestamp}")
    print(f"  平均连接数:   {sum(counts)/len(counts):.1f}")
    print(f"  最小连接数:   {min(counts)}")
    print(f"  最大连接数:   {max(counts)} ⭐")
    
    # 计算波动
    deltas = [counts[i] - counts[i-1] for i in range(1, len(counts))]
    surge_deltas = [d for d in deltas if d > 50]
    drop_deltas = [d for d in deltas if d < -50]
    
    print(f"  暴涨次数(>50): {len(surge_deltas)}")
    print(f"  骤降次数(<-50): {len(drop_deltas)}")
    
    print(f"\n{'='*60}")
    print("🔒 锁积压事件检测")
    print(f"{'='*60}")
    
    if surges:
        for i, surge in enumerate(surges, 1):
            print(f"\n  事件 #{i}:")
            print(f"    持锁开始:    {surge.start}")
            print(f"    锁释放:      {surge.end}")
            if surge.duration_min:
                print(f"    持锁时长:    {surge.duration_min:.1f} 分钟")
            print(f"    积压峰值:    {surge.peak} 连接")
    else:
        print("  未检测到明显锁积压模式（骤降→暴涨）")


def main():
    parser = argparse.ArgumentParser(
        description='连接数时序快速查询',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基础查询
  python3 get_connection_timeline.py \\
      --node qsh8-db-redtao-antispam-u5trt-11 \\
      --start "2026-04-02 04:00:00" \\
      --end "2026-04-02 05:00:00"

  # 启用锁积压检测
  python3 get_connection_timeline.py \\
      --node qsh8-db-redtao-antispam-u5trt-11 \\
      --start "2026-04-02 04:00:00" \\
      --end "2026-04-02 05:00:00" \\
      --detect-locks

  # 自定义阈值
  python3 get_connection_timeline.py \\
      --node qsh8-db-redtao-antispam-u5trt-11 \\
      --start "2026-04-02 04:00:00" \\
      --end "2026-04-02 05:00:00" \\
      --detect-locks \\
      --threshold-drop 5 \\
      --threshold-surge 200
"""
    )
    
    # 基本参数
    parser.add_argument('--cluster', help='集群名称（用于展示）')
    parser.add_argument('--node', required=True, help='节点 VM 名称')
    parser.add_argument('--start', required=True, help='开始时间（YYYY-MM-DD HH:MM:SS）')
    parser.add_argument('--end', required=True, help='结束时间（YYYY-MM-DD HH:MM:SS）')
    
    # 功能开关
    parser.add_argument('--detect-locks', action='store_true', help='自动检测锁积压事件')
    
    # 阈值参数
    parser.add_argument(
        '--threshold-drop', 
        type=int, 
        default=DEFAULT_THRESHOLD_DROP,
        help=f'锁获取/释放的连接数阈值（默认：{DEFAULT_THRESHOLD_DROP}）'
    )
    parser.add_argument(
        '--threshold-prev', 
        type=int, 
        default=DEFAULT_THRESHOLD_PREV,
        help=f'前一时刻连接数阈值（默认：{DEFAULT_THRESHOLD_PREV}）'
    )
    parser.add_argument(
        '--threshold-surge', 
        type=int, 
        default=DEFAULT_THRESHOLD_SURGE,
        help=f'积压爆发阈值（默认：{DEFAULT_THRESHOLD_SURGE}）'
    )
    
    # 输出
    parser.add_argument('--output-json', help='输出 JSON 文件路径（可选）')
    
    args = parser.parse_args()

    if not AI_TOKEN and not TOKEN:
        print("[get_connection_timeline] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 连接数时序分析")
    print(f"   节点: {args.node}")
    if args.cluster:
        print(f"   集群: {args.cluster}")
    print(f"   时间: {args.start} ~ {args.end}")
    if args.detect_locks:
        print(f"   锁检测阈值: drop<{args.threshold_drop}, surge>{args.threshold_surge}")
    
    # 获取数据
    events = get_connection_timeline(args.node, args.start, args.end)
    
    if not events:
        print("\n❌ 该时间窗口无 CK 连接数快照数据")
        print("   可能原因：")
        print("   - 超过 7 天保留期，数据已归档")
        print("   - 该时段节点未产生快照")
        print("   - API 调用失败（见上方错误信息）")
        return 1
    
    print(f"   获取到 {len(events)} 个时间点")
    
    # 检测锁积压
    surges = []
    if args.detect_locks:
        surges = detect_lock_surges(
            events,
            threshold_drop=args.threshold_drop,
            threshold_prev=args.threshold_prev,
            threshold_surge=args.threshold_surge
        )
    
    # 打印时序图
    print_timeline(events, surges)
    
    # 打印统计
    print_statistics(events, surges)
    
    # 输出 JSON（可选）
    if args.output_json:
        data = {
            "node": args.node,
            "cluster": args.cluster,
            "start": args.start,
            "end": args.end,
            "events": [{"timestamp": e.timestamp, "count": e.count} for e in events],
            "lock_surges": [
                {
                    "start": s.start,
                    "end": s.end,
                    "duration_min": s.duration_min,
                    "peak": s.peak
                } for s in surges
            ]
        }
        with open(args.output_json, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n💾 数据已保存: {args.output_json}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())