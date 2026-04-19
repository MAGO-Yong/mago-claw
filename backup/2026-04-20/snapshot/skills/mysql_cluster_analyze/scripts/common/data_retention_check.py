#!/usr/bin/env python3
"""
data_retention_check.py — 数据保留期前置检查

避免查询已归档数据浪费时间，自动降级为受限报告

用法：
    from data_retention_check import check_retention, RetentionStatus
    
    status = check_retention("2025-03-23 00:01:00")
    if status == RetentionStatus.EXPIRED:
        # 直接生成受限报告，不查询 CK
        pass
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import NamedTuple


# 各类数据的保留期（天）
RETENTION_CONFIG = {
    "ck_slow_log": 7,           # CK 慢查询统计
    "ck_connection_snapshot": 7, # CK 连接数快照
    "ck_raw_slow_log": 3,      # CK 原始慢日志
    "dms_realtime_session": 1, # DMS 实时会话
}


class RetentionStatus(Enum):
    """保留期状态"""
    AVAILABLE = "available"     # 数据可用
    WARNING = "warning"           # 即将过期（3天内）
    EXPIRED = "expired"           # 已过期


class RetentionCheckResult(NamedTuple):
    """检查结果"""
    status: RetentionStatus
    fault_time: datetime
    days_ago: int
    available_sources: list      # 仍可用的数据源
    expired_sources: list         # 已过期数据源
    gaps: list                    # 数据缺口说明


def check_retention(fault_time_str: str) -> RetentionCheckResult:
    """
    检查故障时间的数据保留期
    
    Args:
        fault_time_str: 故障时间，格式 "YYYY-MM-DD HH:MM:SS"
        
    Returns:
        RetentionCheckResult
    """
    try:
        fault_time = datetime.strptime(fault_time_str, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        raise ValueError(f"时间格式错误: {fault_time_str}，请使用 'YYYY-MM-DD HH:MM:SS' 格式") from e
    now = datetime.now()
    delta = now - fault_time
    days_ago = delta.days
    
    # 判断状态
    if days_ago > 7:
        status = RetentionStatus.EXPIRED
    elif days_ago > 4:
        status = RetentionStatus.WARNING
    else:
        status = RetentionStatus.AVAILABLE
    
    # 分析各数据源
    available_sources = []
    expired_sources = []
    gaps = []
    
    for source, retention_days in RETENTION_CONFIG.items():
        if days_ago <= retention_days:
            available_sources.append(source)
        else:
            expired_sources.append(source)
            gaps.append({
                "item": source.replace("_", " ").upper(),
                "expected_source": f"CK ({retention_days}d retention)",
                "actual_status": f"已归档（{days_ago}天前）",
                "alternative": get_alternative(source)
            })
    
    return RetentionCheckResult(
        status=status,
        fault_time=fault_time,
        days_ago=days_ago,
        available_sources=available_sources,
        expired_sources=expired_sources,
        gaps=gaps
    )


def get_alternative(source: str) -> str:
    """获取替代方案"""
    alternatives = {
        "ck_slow_log": "联系 DBA 查询原始慢日志文件",
        "ck_connection_snapshot": "Grafana 历史监控曲线",
        "ck_raw_slow_log": "DMS Agent 慢日志文件",
        "dms_realtime_session": "无法回溯，需现场复现",
    }
    return alternatives.get(source, "联系 DBA 协助")


def should_generate_limited_report(fault_time_str: str) -> bool:
    """
    快速判断是否应该生成受限报告
    
    使用：在 Phase 0 快速检查，避免无效查询
    """
    result = check_retention(fault_time_str)
    return result.status == RetentionStatus.EXPIRED


if __name__ == "__main__":
    # 测试
    test_times = [
        "2025-03-23 00:01:00",  # fls_product 故障时间
        "2026-04-02 04:00:00",  # redtao_antispam 故障时间
        "2026-04-02 15:00:00",  # 今天（应该可用）
    ]
    
    for t in test_times:
        result = check_retention(t)
        print(f"\n故障时间: {t}")
        print(f"  距今: {result.days_ago} 天")
        print(f"  状态: {result.status.value}")
        print(f"  可用数据源: {len(result.available_sources)} 个")
        print(f"  过期数据源: {len(result.expired_sources)} 个")
        if result.gaps:
            print(f"  数据缺口:")
            for gap in result.gaps:
                print(f"    - {gap['item']}: {gap['alternative']}")
