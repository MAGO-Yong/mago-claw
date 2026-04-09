#!/usr/bin/env python3
"""
MySQL/MyHub 监控查询工具

使用 DMS API 查询 MySQL 和 MyHub 集群监控指标。
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

sys.path.insert(0, str(Path(__file__).parent))
from common.dms_client import (
    AI_TOKEN, CLAW_TOKEN, AI_V1_PREFIX, OPEN_CLAW_PREFIX,
    _AI_HEADERS, _http_post, call_with_fallback,
)

_CLAW_TOKEN = CLAW_TOKEN


class MySQLMonitor:
    """MySQL/MyHub 监控查询类"""

    def __init__(self, openclaw_token: str = "", timeout: int = 30):
        """
        初始化

        Args:
            openclaw_token: dms-claw-token 认证 token（可选，不传则自动从环境变量读取）
            timeout: 请求超时时间 (秒)
        """
        self.datasource = "vms-db"
        # 兼容旧调用方式（显式传 token）；不传则用 dms_client 的全局 token
        self._claw_token = openclaw_token or _CLAW_TOKEN
        self.timeout = timeout
    
    # ==================== 工具方法 ====================
    
    def _query_promql(
        self,
        pql: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
        step: int = 30
    ) -> List[Dict]:
        """
        执行 PromQL 查询 (内部方法)，ai-api/v1 优先，open-claw 兜底。

        Returns:
            查询结果数据
        """
        now = int(time.time())
        end = end or now
        start = start or (end - 900)  # 默认 15 分钟

        payload = {
            "app": "pangu",
            "pql": pql,
            "start": start,
            "end": end,
            "step": step,
            "datasource": self.datasource,
        }
        claw_headers = {"dms-claw-token": self._claw_token}

        result = call_with_fallback(
            lambda: _http_post(f"{AI_V1_PREFIX}/grafana/fetch_data_by_pql", payload, _AI_HEADERS, timeout=self.timeout),
            lambda: _http_post(f"{OPEN_CLAW_PREFIX}/grafana/fetch-data-by-pql", payload, claw_headers, timeout=self.timeout),
            "[mysql_monitor]",
        )

        if result.get('code') != 0:
            raise Exception(f"查询失败: {result.get('message')}")

        return result.get('data', {}).get('data', {}).get('data', [])
    
    def find_clusters_by_db(self, db_name: str, db_type: str = "mysql") -> List[Dict]:
        """
        根据数据库名查找所属集群
        
        Args:
            db_name: 数据库名
            db_type: 类型 ("mysql" 或 "myhub")
        
        Returns:
            集群列表,每项包含 cluster_name 等信息
        """
        # 通过查询包含该 DB 的指标来发现集群
        if db_type == "mysql":
            pql = f'mysql_global_status_threads_connected{{db=~".*{db_name}.*"}}'
        else:  # myhub
            pql = f'myhub_backend_conns{{db=~".*{db_name}.*"}}'
        
        data = self._query_promql(pql)
        
        clusters = {}
        for series in data:
            metric = series.get('metric', {})
            cluster_name = metric.get('cluster_name')
            if cluster_name and cluster_name not in clusters:
                clusters[cluster_name] = {
                    'cluster_name': cluster_name,
                    'zone': metric.get('xhs_zone'),
                    'shard': metric.get('shardname'),
                    'db_type': db_type
                }
        
        return list(clusters.values())
    
    # ==================== MySQL 指标查询 ====================
    
    def query_mysql_connections(self, cluster_name: str) -> int:
        """查询 MySQL 连接数"""
        pql = f'max_over_time(mysql_global_status_threads_connected{{cluster_name=~"{cluster_name}"}}[15s])'
        data = self._query_promql(pql)
        
        total = 0
        for series in data:
            values = series.get('values', [])
            if values:
                total += int(float(values[-1].get('value', 0)))
        return total
    
    def query_mysql_active_threads(self, cluster_name: str) -> int:
        """查询 MySQL 活跃线程数"""
        pql = f'max_over_time(mysql_global_status_threads_running{{cluster_name=~"{cluster_name}"}}[5m])'
        data = self._query_promql(pql)
        
        total = 0
        for series in data:
            values = series.get('values', [])
            if values:
                total += int(float(values[-1].get('value', 0)))
        return total
    
    def query_mysql_qps(self, cluster_name: str) -> Dict[str, float]:
        """
        查询 MySQL QPS (分类型)
        
        Returns:
            {"select": ..., "insert": ..., "update": ..., "delete": ..., "total": ...}
        """
        commands = ['select', 'insert', 'update', 'delete']
        result = {}
        
        for cmd in commands:
            pql = f'sum(rate(mysql_global_status_commands_total{{cluster_name=~"{cluster_name}", command="{cmd}"}}[1m]))'
            data = self._query_promql(pql)
            
            if data and len(data) > 0:
                values = data[0].get('values', [])
                if values:
                    result[cmd] = float(values[-1].get('value', 0))
                else:
                    result[cmd] = 0.0
            else:
                result[cmd] = 0.0
        
        result['total'] = sum(result.values())
        return result
    
    def query_mysql_slow_queries(self, cluster_name: str) -> float:
        """查询慢查询速率"""
        pql = f'sum(rate(mysql_global_status_slow_queries{{cluster_name=~"{cluster_name}"}}[1m]))'
        data = self._query_promql(pql)
        
        if data and len(data) > 0:
            values = data[0].get('values', [])
            if values:
                return float(values[-1].get('value', 0))
        return 0.0
    
    def query_mysql_innodb_cache_hit(self, cluster_name: str) -> float:
        """查询 InnoDB 缓存命中率"""
        pql = f'1-(sum(mysql_global_status_innodb_buffer_pool_reads{{cluster_name=~"{cluster_name}"}}) / sum(mysql_global_status_innodb_buffer_pool_read_requests{{cluster_name=~"{cluster_name}"}}))' 
        data = self._query_promql(pql)
        
        if data and len(data) > 0:
            values = data[0].get('values', [])
            if values:
                return float(values[-1].get('value', 0))
        return 0.0
    
    # ==================== System 指标查询 ====================
    
    def query_cpu_usage(self, cluster_name: str) -> float:
        """查询 CPU 使用率"""
        pql = f'(1 - avg(rate(node_cpu_seconds_total{{cluster_name=~"{cluster_name}", mode="idle"}}[5m])) by (vmname, xhs_zone))*100'
        data = self._query_promql(pql)
        
        if data:
            # 返回平均值
            total = sum(float(s['values'][-1]['value']) for s in data if s.get('values'))
            count = len([s for s in data if s.get('values')])
            return total / count if count > 0 else 0.0
        return 0.0
    
    def query_memory_usage(self, cluster_name: str) -> float:
        """查询内存使用率"""
        pql = f'avg((1 - node_memory_MemAvailable_bytes{{cluster_name=~"{cluster_name}"}}/node_memory_MemTotal_bytes{{cluster_name=~"{cluster_name}"}}) * 100)'
        data = self._query_promql(pql)
        
        if data and len(data) > 0:
            values = data[0].get('values', [])
            if values:
                return float(values[-1].get('value', 0))
        return 0.0
    
    def query_disk_usage(self, cluster_name: str) -> Dict[str, float]:
        """查询磁盘使用率"""
        pql = f'avg((node_filesystem_size_bytes{{cluster_name=~"{cluster_name}",fstype=~"ext.*|xfs",mountpoint!~".*pod.*"}}-node_filesystem_free_bytes{{cluster_name=~"{cluster_name}",fstype=~"ext.*|xfs",mountpoint!~".*pod.*"}}) *100/(node_filesystem_avail_bytes{{cluster_name=~"{cluster_name}",fstype=~"ext.*|xfs",mountpoint!~".*pod.*"}}+(node_filesystem_size_bytes{{cluster_name=~"{cluster_name}",fstype=~"ext.*|xfs",mountpoint!~".*pod.*"}}-node_filesystem_free_bytes{{cluster_name=~"{cluster_name}",fstype=~"ext.*|xfs",mountpoint!~".*pod.*"}})))'
        data = self._query_promql(pql)
        
        avg_usage = 0.0
        if data and len(data) > 0:
            values = data[0].get('values', [])
            if values:
                avg_usage = float(values[-1].get('value', 0))
        
        return {"average_usage": avg_usage}
    
    def query_network_traffic(self, cluster_name: str) -> Dict[str, float]:
        """查询网络流量"""
        # 接收
        pql_rx = f'sum(irate(node_network_receive_bytes_total{{cluster_name=~"{cluster_name}", device!~"lo"}}[1m]))'
        data_rx = self._query_promql(pql_rx)
        
        rx = 0.0
        if data_rx and len(data_rx) > 0:
            values = data_rx[0].get('values', [])
            if values:
                rx = float(values[-1].get('value', 0))
        
        # 发送
        pql_tx = f'sum(irate(node_network_transmit_bytes_total{{cluster_name=~"{cluster_name}", device!~"lo"}}[1m]))'
        data_tx = self._query_promql(pql_tx)
        
        tx = 0.0
        if data_tx and len(data_tx) > 0:
            values = data_tx[0].get('values', [])
            if values:
                tx = float(values[-1].get('value', 0))
        
        return {
            "receive_bps": rx,
            "transmit_bps": tx,
            "total_bps": rx + tx
        }
    
    # ==================== MyHub 指标查询 ====================
    
    def convert_cluster_to_proxycluster(self, cluster_name: str) -> str:
        """
        将集群名转换为 proxycluster 格式
        
        将下划线转为横线
        例如: sns_userauth -> sns-userauth
        """
        return cluster_name.replace('_', '-')
    
    def query_myhub_connections(self, cluster_name: str) -> int:
        """查询 MyHub 连接数"""
        proxycluster = self.convert_cluster_to_proxycluster(cluster_name)
        pql = f'sum(myhub_backend_conns{{proxycluster="{proxycluster}"}})'
        data = self._query_promql(pql)
        
        if data and len(data) > 0:
            values = data[0].get('values', [])
            if values:
                return int(float(values[-1].get('value', 0)))
        return 0
    
    def query_myhub_qps(self, cluster_name: str) -> float:
        """查询 MyHub QPS"""
        proxycluster = self.convert_cluster_to_proxycluster(cluster_name)
        pql = f'sum(rate(myhub_query_total{{proxycluster="{proxycluster}"}}[1m]))'
        data = self._query_promql(pql)
        
        if data and len(data) > 0:
            values = data[0].get('values', [])
            if values:
                return float(values[-1].get('value', 0))
        return 0.0
    
    # ==================== 综合查询 ====================
    
    def get_mysql_cluster_overview(self, cluster_name: str) -> Dict[str, Any]:
        """
        获取 MySQL 集群完整概览
        
        Args:
            cluster_name: MySQL 集群名称
        
        Returns:
            集群概览字典
        """
        overview = {
            "cluster_name": cluster_name,
            "cluster_type": "mysql",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            
            "mysql": {},
            "system": {}
        }
        
        # MySQL 指标
        try:
            overview["mysql"]["connections"] = self.query_mysql_connections(cluster_name)
        except Exception as e:
            overview["mysql"]["connections"] = f"Error: {e}"
        
        try:
            overview["mysql"]["active_threads"] = self.query_mysql_active_threads(cluster_name)
        except Exception as e:
            overview["mysql"]["active_threads"] = f"Error: {e}"
        
        try:
            overview["mysql"]["qps"] = self.query_mysql_qps(cluster_name)
        except Exception as e:
            overview["mysql"]["qps"] = {"error": str(e)}
        
        try:
            overview["mysql"]["slow_queries"] = self.query_mysql_slow_queries(cluster_name)
        except Exception as e:
            overview["mysql"]["slow_queries"] = f"Error: {e}"
        
        try:
            overview["mysql"]["innodb_cache_hit"] = self.query_mysql_innodb_cache_hit(cluster_name)
        except Exception as e:
            overview["mysql"]["innodb_cache_hit"] = f"Error: {e}"
        
        # System 指标
        try:
            overview["system"]["cpu_usage"] = self.query_cpu_usage(cluster_name)
        except Exception as e:
            overview["system"]["cpu_usage"] = f"Error: {e}"
        
        try:
            overview["system"]["memory_usage"] = self.query_memory_usage(cluster_name)
        except Exception as e:
            overview["system"]["memory_usage"] = f"Error: {e}"
        
        try:
            overview["system"]["disk_usage"] = self.query_disk_usage(cluster_name)
        except Exception as e:
            overview["system"]["disk_usage"] = {"error": str(e)}
        
        try:
            overview["system"]["network"] = self.query_network_traffic(cluster_name)
        except Exception as e:
            overview["system"]["network"] = {"error": str(e)}
        
        return overview
    
    def get_myhub_cluster_overview(self, cluster_name: str) -> Dict[str, Any]:
        """
        获取 MyHub 集群概览
        
        Args:
            cluster_name: MyHub 集群名称 (将自动转换为 proxycluster 格式)
        
        Returns:
            集群概览字典
        """
        proxycluster = self.convert_cluster_to_proxycluster(cluster_name)
        
        overview = {
            "cluster_name": cluster_name,
            "proxycluster": proxycluster,
            "cluster_type": "myhub",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            
            "myhub": {}
        }
        
        try:
            overview["myhub"]["connections"] = self.query_myhub_connections(cluster_name)
        except Exception as e:
            overview["myhub"]["connections"] = f"Error: {e}"
        
        try:
            overview["myhub"]["qps"] = self.query_myhub_qps(cluster_name)
        except Exception as e:
            overview["myhub"]["qps"] = f"Error: {e}"
        
        return overview


# ==================== 命令行工具 ====================

def main():
    """命令行工具入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="MySQL/MyHub 监控查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查询 MySQL 集群
  %(prog)s --cluster sns_userauth --type mysql --token $DMS_CLAW_TOKEN
  
  # 查询 MyHub 集群
  %(prog)s --cluster sns_userauth --type myhub --token $DMS_CLAW_TOKEN
  
  # 根据 DB 名查找集群
  %(prog)s --db userauth --find-cluster --token $DMS_CLAW_TOKEN
  
  # 也可省略 --token，自动读取 DMS_CLAW_TOKEN 环境变量
  %(prog)s --cluster sns_userauth
        """
    )
    
    parser.add_argument("--cluster", help="集群名称")
    parser.add_argument("--type", choices=["mysql", "myhub"], default="mysql", help="集群类型")
    parser.add_argument("--db", help="数据库名 (用于查找集群)")
    parser.add_argument("--find-cluster", action="store_true", help="根据 DB 名查找集群")
    parser.add_argument("--token", default="", help="dms-claw-token Token（可选，不传则自动读取 DMS_AI_TOKEN / DMS_CLAW_TOKEN 环境变量）")
    parser.add_argument("--output", "-o", help="输出文件路径 (JSON 格式)")

    args = parser.parse_args()

    if not args.token and not AI_TOKEN and not CLAW_TOKEN:
        parser.error("必须提供 --token 或设置 DMS_AI_TOKEN / DMS_CLAW_TOKEN 环境变量")

    # 初始化
    monitor = MySQLMonitor(args.token)
    
    try:
        # 查找集群
        if args.find_cluster:
            if not args.db:
                print("❌ 使用 --find-cluster 时必须提供 --db")
                return 1
            
            print(f"查找包含数据库 '{args.db}' 的集群...")
            clusters = monitor.find_clusters_by_db(args.db, args.type)
            
            if not clusters:
                print(f"未找到包含 '{args.db}' 的 {args.type} 集群")
                return 1
            
            print(f"\n找到 {len(clusters)} 个集群:")
            for i, c in enumerate(clusters, 1):
                print(f"  {i}. {c['cluster_name']} (zone: {c['zone']}, shard: {c['shard']})")
            
            return 0
        
        # 查询集群
        if not args.cluster:
            print("❌ 必须提供 --cluster 或使用 --find-cluster")
            return 1
        
        print(f"查询 {args.type.upper()} 集群: {args.cluster}")
        print("=" * 80)
        
        if args.type == "mysql":
            overview = monitor.get_mysql_cluster_overview(args.cluster)
            
            # 显示结果
            print("\nMySQL 指标:")
            print(f"  连接数: {overview['mysql'].get('connections', 'N/A')}")
            print(f"  活跃线程: {overview['mysql'].get('active_threads', 'N/A')}")
            
            qps = overview['mysql'].get('qps', {})
            if isinstance(qps, dict) and 'total' in qps:
                print(f"  总 QPS: {qps['total']:,.2f}")
                print(f"    - Select: {qps.get('select', 0):,.2f}")
                print(f"    - Insert: {qps.get('insert', 0):,.2f}")
                print(f"    - Update: {qps.get('update', 0):,.2f}")
                print(f"    - Delete: {qps.get('delete', 0):,.2f}")
            
            print(f"  慢查询: {overview['mysql'].get('slow_queries', 'N/A')}")
            
            cache_hit = overview['mysql'].get('innodb_cache_hit')
            if isinstance(cache_hit, float):
                print(f"  InnoDB 缓存命中率: {cache_hit*100:.2f}%")
            
            print("\nSystem 指标:")
            cpu = overview['system'].get('cpu_usage')
            if isinstance(cpu, float):
                print(f"  CPU 使用率: {cpu:.2f}%")
            
            mem = overview['system'].get('memory_usage')
            if isinstance(mem, float):
                print(f"  内存使用率: {mem:.2f}%")
            
            disk = overview['system'].get('disk_usage', {})
            if isinstance(disk, dict):
                print(f"  磁盘使用率: {disk.get('average_usage', 0):.2f}%")
            
            net = overview['system'].get('network', {})
            if isinstance(net, dict):
                print(f"  网络流量: RX {net.get('receive_bps', 0)/1024/1024:.2f} MB/s, TX {net.get('transmit_bps', 0)/1024/1024:.2f} MB/s")
        
        else:  # myhub
            overview = monitor.get_myhub_cluster_overview(args.cluster)
            
            print(f"\nProxyCluster: {overview['proxycluster']}")
            print("\nMyHub 指标:")
            print(f"  连接数: {overview['myhub'].get('connections', 'N/A')}")
            print(f"  QPS: {overview['myhub'].get('qps', 'N/A'):,.2f}")
        
        print()
        
        # 保存结果
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(overview, f, indent=2, ensure_ascii=False)
            print(f"结果已保存到: {args.output}")
            print()
    
    except Exception as e:
        print(f"\n❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
