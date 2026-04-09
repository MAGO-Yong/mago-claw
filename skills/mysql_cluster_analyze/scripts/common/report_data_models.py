#!/usr/bin/env python3
"""
报告数据模型定义
统一 Layer 1 和 Layer 2 的数据结构
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class ReportType(Enum):
    """报告类型"""
    COMPLETE = "complete"    # 完整诊断
    MANUAL = "manual"        # 人工编排
    LIMITED = "limited"      # 受限分析


class EventType(Enum):
    """事件类型"""
    LOCK_SURGE = "lock_surge"      # 锁积压爆发
    LOCK_RELEASE = "lock_release"  # 锁释放
    SLOW_QUERY_SPIKE = "slow_query_spike"  # 慢查询爆发
    CPU_HIGH = "cpu_high"
    DISK_FULL = "disk_full"
    REPLICATION_LAG = "replication_lag"


@dataclass
class SlowLogEvent:
    """慢查询事件"""
    timestamp: str
    query_count: int
    total_time: float
    max_time: float
    sql_fingerprint: str = ""
    client: str = ""
    db: str = ""


@dataclass
class ConnectionEvent:
    """连接数事件"""
    timestamp: str
    count: int
    event_type: str = "normal"  # surge, drop, normal
    notes: str = ""


@dataclass
class LockEvent:
    """锁积压事件"""
    start_time: str
    end_time: Optional[str] = None
    duration_minutes: float = 0.0
    peak_connections: int = 0
    affected_tables: List[str] = field(default_factory=list)
    trigger_note: str = ""


@dataclass
class DataGap:
    """数据缺口说明"""
    item: str
    expected_source: str
    actual_status: str
    alternative: str


@dataclass
class ReportData:
    """报告数据容器"""
    # 基本信息
    cluster_name: str
    node_name: str = ""
    fault_time: str = ""
    analysis_period: str = ""
    report_type: ReportType = ReportType.COMPLETE
    
    # 事件列表
    slow_log_events: List[SlowLogEvent] = field(default_factory=list)
    connection_events: List[ConnectionEvent] = field(default_factory=list)
    lock_events: List[LockEvent] = field(default_factory=list)
    
    # 数据完整性
    data_sources: Dict[str, bool] = field(default_factory=dict)
    data_gaps: List[DataGap] = field(default_factory=list)
    
    # 结论
    root_cause_summary: str = ""
    root_cause_primary: str = ""
    root_cause_secondary: str = ""
    recommendations: List[Dict[str, str]] = field(default_factory=list)
    
    # 元数据
    generated_at: str = ""
    data_source_note: str = ""
