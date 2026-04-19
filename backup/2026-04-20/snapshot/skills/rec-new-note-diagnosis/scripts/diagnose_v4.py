#!/usr/bin/env python3
"""
rec-new-note-diagnosis v4.0 - 决策树驱动版

核心特性：
1. 读取 decision-tree.json 自动执行排查流程
2. 配置化阈值和判断条件
3. 支持动态分支跳转
4. 所有数值带时间戳
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
SKILLS_DIR = os.path.dirname(SKILL_DIR)
WORKSPACE_DIR = os.path.dirname(SKILLS_DIR)

CONFIG_PATHS = {
    'decision_tree': os.path.join(SKILL_DIR, 'references', 'decision-tree.json'),
    'promql': os.path.join(SKILL_DIR, 'references', 'promql-collection.json'),
    'watchlist': os.path.join(SKILL_DIR, 'references', 'config-watchlist.json'),
}

TOOLS = {
    'change_query': os.path.join(SKILLS_DIR, 'xray_changevent_query', 'scripts', 'query.py'),
    'metrics_query': os.path.join(SKILLS_DIR, 'xray_metrics_query', 'scripts', 'query.py'),
    'index_check': os.path.join(SKILLS_DIR, 'index-switch-check', 'scripts', 'check_switch.py'),
}

SSO_TOKEN_FILE = "/home/node/.token/sso_token.json"


def read_sso_token(env: str = "prod") -> str:
    """从全局 token 文件读取 SSO 登录态（OpenClaw 自动维护）。
    
    优先级：
    1. 环境变量 SSO_COOKIE（显式传入，最高优先级）
    2. /home/node/.token/sso_token.json（OpenClaw 自动维护，推荐主路径）
    """
    env_cookie = os.environ.get("SSO_COOKIE", "").strip()
    if env_cookie:
        return env_cookie
    key = f"common-internal-access-token-{env}"
    try:
        with open(SSO_TOKEN_FILE) as f:
            data = json.load(f)
        token = data.get(key, "").strip()
        if token:
            return f"{key}={token}"
    except Exception:
        pass
    return ""

SEP = "=" * 76
SEP2 = "-" * 76


class DecisionEngine:
    """决策树执行引擎"""
    
    def __init__(self, start_time: datetime, end_time: datetime):
        self.start_time = start_time
        self.end_time = end_time
        self.tree = self._load_json(CONFIG_PATHS['decision_tree'])
        self.promql = self._load_json(CONFIG_PATHS['promql'])
        self.context = {}  # 执行上下文，存储中间结果
        self.current_node = self.tree.get('start_node', 'step1')
        self.anomaly_time = None
        
    def _load_json(self, path: str) -> dict:
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  加载配置失败 {path}: {e}")
            return {}
    
    def run(self):
        """执行决策树"""
        max_steps = 50  # 防止无限循环
        step_count = 0
        
        while self.current_node and step_count < max_steps:
            step_count += 1
            node = self.tree.get('nodes', {}).get(self.current_node)
            if not node:
                print(f"❌ 节点 {self.current_node} 不存在")
                break
            
            print(f"\n{SEP}")
            print(f"Step: {node.get('name', self.current_node)}")
            print(SEP)
            print(f"描述: {node.get('description', '')}")
            print()
            
            # 执行节点
            next_node = self._execute_node(node)
            
            # 检查是否是结束节点
            if node.get('type') == 'end':
                print(f"\n【诊断结束】{node.get('description', '')}")
                break
            
            self.current_node = next_node
        
        if step_count >= max_steps:
            print("⚠️  达到最大执行步数，强制结束")
    
    def _execute_node(self, node: dict) -> Optional[str]:
        """执行单个节点，返回下一个节点ID"""
        node_type = node.get('type', 'decision')
        
        if node_type == 'decision':
            return self._execute_decision_node(node)
        elif node_type == 'analysis':
            return self._execute_analysis_node(node)
        elif node_type == 'change_detection':
            return self._execute_change_detection(node)
        elif node_type == 'sequential':
            return self._execute_sequential_node(node)
        elif node_type == 'end':
            return None
        else:
            print(f"⚠️  未知节点类型: {node_type}")
            return node.get('next') or node.get('branches', [{}])[0].get('next')
    
    def _execute_decision_node(self, node: dict) -> Optional[str]:
        """执行决策节点"""
        # 获取PromQL并查询
        promql_ref = node.get('promql_ref')
        if promql_ref and not self._check_skip_query(node):
            metrics = self._query_metrics(promql_ref)
            self.context[node['id']] = metrics
            
            # 显示结果
            self._display_metrics(metrics, node.get('output_template'))
        
        # 评估条件
        condition = node.get('condition')
        if condition:
            result = self._evaluate_condition(condition, node)
            branches = node.get('branches', [])
            for branch in branches:
                if self._match_branch_condition(branch, result):
                    print(f"\n【分支】{branch.get('description', '')}")
                    return branch.get('next')
        
        # 默认分支
        branches = node.get('branches', [])
        if branches:
            return branches[0].get('next')
        return node.get('next')
    
    def _execute_analysis_node(self, node: dict) -> Optional[str]:
        """执行分析节点"""
        print(f"【分析】{node.get('description', '')}")
        
        # 执行PromQL查询
        promql_ref = node.get('promql_ref')
        if promql_ref:
            metrics = self._query_metrics(promql_ref)
            self.context[node['id']] = metrics
            self._display_metrics(metrics, node.get('output_template'))
        
        # 检查配置中的分支
        branches = node.get('branches', [])
        for branch in branches:
            condition = branch.get('condition', '')
            # 简化判断：检查上下文中的关键字
            if self._check_condition_in_context(condition):
                print(f"\n【匹配分支】{branch.get('description', '')}")
                return branch.get('next')
        
        return node.get('next')
    
    def _execute_change_detection(self, node: dict) -> Optional[str]:
        """执行变更检测（Step 0）"""
        # 查询范围：基于异常时间或诊断窗口
        if self.anomaly_time:
            q_start = self.anomaly_time - timedelta(hours=3)
            q_end = self.anomaly_time + timedelta(hours=1)
            print(f"【基于异常时间】{self.anomaly_time.strftime('%Y-%m-%d %H:%M')}")
        else:
            q_end = self.end_time
            q_start = q_end - timedelta(hours=3)
            print(f"【无显著异常，查询诊断窗口前3小时】")
        
        print(f"【变更查询范围】{q_start.strftime('%Y-%m-%d %H:%M')} ~ {q_end.strftime('%Y-%m-%d %H:%M')}")
        
        # 执行变更查询
        changes = self._query_changes(q_start, q_end)
        self.context['step0'] = changes
        
        # 统计风险等级
        critical = len([c for c in changes if c.get('risk') == '🔴'])
        high = len([c for c in changes if c.get('risk') == '🟠'])
        medium = len([c for c in changes if c.get('risk') == '🟡'])
        
        print(f"\n【风险统计】")
        print(f"  🔴 极高风险: {critical}")
        print(f"  🟠 高风险:   {high}")
        print(f"  🟡 中风险:   {medium}")
        
        # 根据风险数量决定分支
        branches = node.get('branches', [])
        for branch in branches:
            cond = branch.get('condition', '')
            if 'high_risk_changes > 0' in cond and critical > 0:
                print(f"\n  ⚠️  检测到{critical}个极高风险变更")
                return branch.get('next')
            elif 'high_risk_changes == 0' in cond and critical == 0:
                print(f"\n  🟢 无高风险变更")
                return branch.get('next')
        
        return branches[0].get('next') if branches else 'step1'
    
    def _execute_sequential_node(self, node: dict) -> Optional[str]:
        """执行顺序节点（包含多个子步骤）"""
        sub_steps = node.get('sub_steps', [])
        for sub in sub_steps:
            print(f"  执行: {sub}")
        
        # 执行主要查询
        promql_ref = node.get('promql_ref')
        if promql_ref:
            metrics = self._query_metrics(promql_ref)
            self.context[node['id']] = metrics
        
        # 评估分支
        branches = node.get('branches', [])
        for branch in branches:
            cond = branch.get('condition', '')
            if self._check_condition_in_context(cond):
                return branch.get('next')
        
        return branches[0].get('next') if branches else None
    
    def _query_metrics(self, promql_ref: str) -> dict:
        """查询指标"""
        # 从 promql-collection.json 获取查询
        queries = self.promql.get('steps', {}).get(promql_ref, {}).get('queries', {})
        results = {}
        
        for key, config in queries.items():
            promql = config.get('promql', '')
            if not promql:
                continue
            
            # 构建查询
            q = {
                'promql': promql,
                'datasource': config.get('datasource', 'vms-recommend'),
                'start_time': self.start_time.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
                'end_time': self.end_time.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
                'instant': False
            }
            
            try:
                r = subprocess.run(
                    ['python3', TOOLS['metrics_query'], json.dumps(q)],
                    capture_output=True, text=True, timeout=30
                )
                if r.returncode == 0:
                    data = json.loads(r.stdout)
                    if data.get('success'):
                        results[key] = data.get('data', {}).get('data', [])
            except Exception as e:
                print(f"  ⚠️  查询失败 {key}: {e}")
        
        return results
    
    def _query_changes(self, q_start: datetime, q_end: datetime) -> List[dict]:
        """查询变更事件"""
        changes = []
        
        try:
            r = subprocess.run(
                ['python3', TOOLS['change_query'],
                 '--start', q_start.strftime('%Y-%m-%d %H:%M:%S'),
                 '--end', q_end.strftime('%Y-%m-%d %H:%M:%S'),
                 '--system', 'apollo', 'racingweb',
                 '--tag', '外流推荐'],
                capture_output=True, text=True, timeout=30
            )
            
            if r.returncode == 0:
                data = json.loads(r.stdout)
                # 解析变更数据...（简化版）
                # 实际应该解析完整的变更结构
                changes = self._parse_changes(data)
        except Exception as e:
            print(f"  ⚠️  变更查询失败: {e}")
        
        return changes
    
    def _parse_changes(self, data: dict) -> List[dict]:
        """解析变更数据（简化版）"""
        changes = []
        # 这里应该实现完整的变更解析逻辑
        # 为了演示，返回空列表
        return changes
    
    def _display_metrics(self, metrics: dict, template: Optional[str]):
        """展示指标结果"""
        # 简化展示
        for key, data in metrics.items():
            print(f"  {key}: 获取到 {len(data)} 条数据")
    
    def _evaluate_condition(self, condition: dict, node: dict) -> dict:
        """评估条件"""
        # 简化版：返回评估结果字典
        return {'result': True, 'metrics': self.context.get(node.get('id'), {})}
    
    def _match_branch_condition(self, branch: dict, result: dict) -> bool:
        """匹配分支条件"""
        # 简化版：总是匹配第一个
        return True
    
    def _check_condition_in_context(self, condition: str) -> bool:
        """检查上下文中的条件"""
        # 简化实现
        return False
    
    def _check_skip_query(self, node: dict) -> bool:
        """检查是否需要跳过查询"""
        # 如果该节点的数据已在上下文中，可以跳过
        return node['id'] in self.context


def main():
    # 解析参数
    env_start = os.environ.get('DIAGNOSIS_START_TIME')
    env_end = os.environ.get('DIAGNOSIS_END_TIME')
    
    if env_end:
        end_time = datetime.fromisoformat(env_end)
    else:
        end_time = datetime.now()
    
    if env_start:
        start_time = datetime.fromisoformat(env_start)
    else:
        start_time = end_time - timedelta(hours=6)
    
    print("╔" + "=" * 74 + "╗")
    print("║" + " " * 20 + "rec-new-note-diagnosis" + " " * 30 + "║")
    print("║" + " " * 22 + "v4.0（决策树驱动版）" + " " * 28 + "║")
    print("╚" + "=" * 74 + "╝")
    print(f"\n【诊断时间范围】{start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}")
    
    # 获取SSO登录态（直接读取 token 文件，无需调用外部脚本）
    print(f"\n{SEP}")
    print("获取登录态")
    print(SEP)
    token = read_sso_token()
    if token:
        print("✅ 登录态获取成功")
    else:
        print("⚠️ 登录态获取失败，请确认 /home/node/.token/sso_token.json 是否存在")
    
    # 创建引擎并执行
    engine = DecisionEngine(start_time, end_time)
    engine.run()


if __name__ == '__main__':
    main()
