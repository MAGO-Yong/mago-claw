#!/usr/bin/env python3
"""
统一报告生成器
支持 Layer 1 人工编排和 Layer 2 自动诊断
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from report_data_models import (
    ReportData, ReportType, SlowLogEvent, ConnectionEvent,
    LockEvent, DataGap
)


# 内置基础模板（当外部模板不可用时使用）
BASE_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ report_title }}</title>
<style>
{{ base_css }}
</style>
</head>
<body>
<div class="container">
{{ header_section }}
{{ content_section }}
{{ footer_section }}
</div>
</body>
</html>'''

# Header 配置：报告类型 -> (badge, background)
HEADER_CONFIG = {
    ReportType.COMPLETE: ("✅ 完整诊断", "linear-gradient(135deg, #1e3a5f, #2d6a9f)"),
    ReportType.MANUAL: ("🔧 人工分析", "linear-gradient(135deg, #1e8449, #27ae60)"),
    ReportType.LIMITED: ("⚠️ 受限分析", "linear-gradient(135deg, #8e44ad, #9b59b6)"),
}

BASE_CSS = '''
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 24px; background: #f5f7fa; color: #1a1a2e; line-height: 1.6; }
.container { max-width: 960px; margin: 0 auto; }
.header { color: white; padding: 24px 32px; border-radius: 12px; margin-bottom: 20px; }
.header h1 { margin: 0 0 8px; font-size: 20px; }
.header .badge { display: inline-block; background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 20px; font-size: 12px; margin-bottom: 8px; }
.header .sub { font-size: 13px; opacity: 0.9; }
.section { background: white; border-radius: 10px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.section-title { font-size: 15px; font-weight: 700; color: #1e3a5f; margin: 0 0 14px; padding-bottom: 8px; border-bottom: 2px solid #e8f0fe; }
.alert-box { border-left: 4px solid; padding: 12px 16px; border-radius: 0 8px 8px 0; margin: 12px 0; font-size: 13px; }
.alert-orange { border-color: #e67e22; background: #fef9f0; color: #784212; }
.alert-blue { border-color: #3498db; background: #eaf4fd; color: #1a5276; }
.alert-red { border-color: #e74c3c; background: #fdf0ef; color: #922b21; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #f0f4ff; color: #1e3a5f; padding: 10px 12px; text-align: left; font-weight: 600; }
td { padding: 9px 12px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
.gap-row td { background: #fff5f5; color: #c0392b; }
code { background: #f0f4ff; color: #1a5276; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 12px; }
.footer { text-align: center; font-size: 12px; color: #9aa5be; padding: 20px 0; }
.kv-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.kv-card { background: #f8faff; border: 1px solid #e2eaf8; border-radius: 8px; padding: 14px; }
.kv-label { font-size: 12px; color: #6b7a99; margin-bottom: 4px; }
.kv-value { font-size: 18px; font-weight: 700; color: #1e3a5f; }
'''


class ReportGenerator:
    """统一报告生成器"""
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        初始化报告生成器
        
        Args:
            template_dir: 模板目录路径，None 则使用内置模板
        """
        self.template_dir = template_dir
        if template_dir and Path(template_dir).exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(template_dir),
                autoescape=select_autoescape(['html', 'xml'])
            )
        else:
            self.jinja_env = None
    
    def generate(self, report_data: ReportData, output_path: str) -> str:
        """
        生成 HTML 报告
        
        Args:
            report_data: 报告数据对象
            output_path: 输出文件路径
            
        Returns:
            生成的 HTML 文件路径
        """
        html = self._render(report_data)
        Path(output_path).write_text(html, encoding='utf-8')
        return output_path
    
    def _render(self, data: ReportData) -> str:
        """渲染 HTML"""
        # 渲染 header
        header_html = self._render_header(data)
        
        # 渲染各部分
        content_html = self._render_content(data)
        footer_html = self._render_footer(data)
        
        # 组装完整 HTML
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MySQL 故障诊断报告 - {data.cluster_name}</title>
<style>
{BASE_CSS}
</style>
</head>
<body>
<div class="container">
{header_html}
{content_html}
{footer_html}
</div>
</body>
</html>'''
    
    def _render_header(self, data: ReportData) -> str:
        """渲染 header，根据报告类型选择样式"""
        badge, background = HEADER_CONFIG.get(
            data.report_type,
            ("📊 诊断报告", "linear-gradient(135deg, #666, #999)")
        )
        return f'''
<div class="header" style="background: {background};">
  <div class="badge">{badge}</div>
  <h1>🔍 MySQL 故障诊断报告</h1>
  <div class="sub">{data.cluster_name} · {data.node_name} · {data.analysis_period}</div>
</div>
'''
    
    def _render_content(self, data: ReportData) -> str:
        """渲染内容区"""
        sections = []
        
        # 数据缺口声明（LIMITED 类型必显）
        if data.report_type == ReportType.LIMITED or data.data_gaps:
            sections.append(self._render_data_gaps(data))
        
        # 基本信息
        sections.append(self._render_basic_info(data))
        
        # 事件列表
        if data.lock_events:
            sections.append(self._render_lock_events(data))
        
        if data.slow_log_events:
            sections.append(self._render_slow_log_events(data))
        
        if data.connection_events:
            sections.append(self._render_connection_events(data))
        
        # 根因分析
        if data.root_cause_summary:
            sections.append(self._render_root_cause(data))
        
        # 改进建议
        if data.recommendations:
            sections.append(self._render_recommendations(data))
        
        return '\n'.join(sections)
    
    def _render_data_gaps(self, data: ReportData) -> str:
        """渲染数据缺口说明"""
        if not data.data_gaps:
            return ''
        
        rows = ''
        for gap in data.data_gaps:
            rows += f'''
    <tr class="gap-row">
      <td>{gap.item}</td>
      <td>{gap.expected_source}</td>
      <td>❌ {gap.actual_status}</td>
      <td>{gap.alternative}</td>
    </tr>'''
        
        return f'''
<div class="section">
  <div class="section-title">⚠️ 数据完整性声明</div>
  <div class="alert-orange">
    <strong>本次分析受限：{data.data_source_note or '部分历史数据无法获取'}</strong>
  </div>
  <table style="margin-top: 12px;">
    <tr><th>数据项</th><th>预期来源</th><th>实际状态</th><th>替代方案</th></tr>
    {rows}
  </table>
</div>
'''
    
    def _render_basic_info(self, data: ReportData) -> str:
        """渲染基本信息"""
        return f'''
<div class="section">
  <div class="section-title">📋 基本信息</div>
  <div class="kv-grid">
    <div class="kv-card">
      <div class="kv-label">集群名称</div>
      <div class="kv-value">{data.cluster_name}</div>
    </div>
    <div class="kv-card">
      <div class="kv-label">目标节点</div>
      <div class="kv-value">{data.node_name or 'N/A'}</div>
    </div>
    <div class="kv-card">
      <div class="kv-label">故障时间</div>
      <div class="kv-value">{data.fault_time or 'N/A'}</div>
    </div>
    <div class="kv-card">
      <div class="kv-label">报告类型</div>
      <div class="kv-value">{data.report_type.value}</div>
    </div>
  </div>
</div>
'''
    
    def _render_lock_events(self, data: ReportData) -> str:
        """渲染锁积压事件"""
        rows = ''
        for event in data.lock_events:
            duration = f"{event.duration_minutes:.1f}分钟" if event.duration_minutes else "未知"
            rows += f'''
    <tr>
      <td>{event.start_time}</td>
      <td>{event.end_time or '未释放'}</td>
      <td>{duration}</td>
      <td>{event.peak_connections}</td>
      <td>{', '.join(event.affected_tables[:3])}</td>
    </tr>'''
        
        return f'''
<div class="section">
  <div class="section-title">🔒 锁积压事件</div>
  <table>
    <tr><th>开始时间</th><th>结束时间</th><th>持锁时长</th><th>峰值连接</th><th>涉及表</th></tr>
    {rows}
  </table>
</div>
'''
    
    def _render_slow_log_events(self, data: ReportData) -> str:
        """渲染慢查询事件"""
        rows = ''
        for event in data.slow_log_events[:10]:
            rows += f'''
    <tr>
      <td>{event.timestamp}</td>
      <td>{event.query_count}</td>
      <td>{event.total_time:.0f}s</td>
      <td>{event.max_time:.1f}s</td>
      <td>{event.client[:30]}</td>
    </tr>'''
        
        return f'''
<div class="section">
  <div class="section-title">📊 慢查询事件</div>
  <table>
    <tr><th>时间</th><th>条数</th><th>总耗时</th><th>最大耗时</th><th>来源</th></tr>
    {rows}
  </table>
</div>
'''
    
    def _render_connection_events(self, data: ReportData) -> str:
        """渲染连接数事件"""
        rows = ''
        for event in data.connection_events[:20]:
            badge = {
                'surge': '🚨',
                'drop': '⬇️',
                'normal': ''
            }.get(event.event_type, '')
            rows += f'''
    <tr>
      <td>{event.timestamp}</td>
      <td>{event.count}</td>
      <td>{badge} {event.event_type}</td>
      <td>{event.notes}</td>
    </tr>'''
        
        return f'''
<div class="section">
  <div class="section-title">📈 连接数变化</div>
  <table>
    <tr><th>时间</th><th>连接数</th><th>事件类型</th><th>备注</th></tr>
    {rows}
  </table>
</div>
'''
    
    def _render_root_cause(self, data: ReportData) -> str:
        """渲染根因分析"""
        primary = f"<p><strong>主因：</strong>{data.root_cause_primary}</p>" if data.root_cause_primary else ""
        secondary = f"<p><strong>次因：</strong>{data.root_cause_secondary}</p>" if data.root_cause_secondary else ""
        
        return f'''
<div class="section">
  <div class="section-title">💡 根因分析</div>
  <div class="alert-blue">
    {data.root_cause_summary}
  </div>
  {primary}
  {secondary}
</div>
'''
    
    def _render_recommendations(self, data: ReportData) -> str:
        """渲染改进建议"""
        items = ''
        for rec in data.recommendations:
            priority = rec.get('priority', 'P2')
            item = rec.get('item', '')
            items += f'''
    <li><code>{priority}</code> {item}</li>'''
        
        return f'''
<div class="section">
  <div class="section-title">🛠️ 改进建议</div>
  <ul style="line-height: 1.8;">
    {items}
  </ul>
</div>
'''
    
    def _render_footer(self, data: ReportData) -> str:
        """渲染 footer"""
        type_desc = {
            ReportType.COMPLETE: '完整诊断',
            ReportType.MANUAL: '人工分析',
            ReportType.LIMITED: '受限分析'
        }.get(data.report_type, '诊断报告')
        
        return f'''
<div class="footer">
  报告类型：{type_desc} · 生成时间：{data.generated_at}<br>
  集群：{data.cluster_name} · 节点：{data.node_name or 'N/A'}
</div>
'''


# 便捷函数
def generate_limited_report(
    cluster: str,
    node: str,
    fault_time: str,
    data_gaps: List[Dict[str, str]],
    output_path: str
) -> str:
    """
    快速生成受限分析报告
    
    示例：
        generate_limited_report(
            cluster="fls_product",
            node="qsh5-db-fls-product-122",
            fault_time="2025-03-23 00:01:00",
            data_gaps=[
                {"item": "慢查询列表", "expected_source": "CK", "actual_status": "已归档", "alternative": "联系DBA"},
            ],
            output_path="/tmp/report.html"
        )
    """
    from datetime import datetime
    
    gaps = [DataGap(**g) for g in data_gaps]
    
    report_data = ReportData(
        cluster_name=cluster,
        node_name=node,
        fault_time=fault_time,
        report_type=ReportType.LIMITED,
        data_gaps=gaps,
        data_source_note="部分历史数据已归档，无法获取",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    generator = ReportGenerator()
    return generator.generate(report_data, output_path)


if __name__ == "__main__":
    # 示例：生成受限报告
    generate_limited_report(
        cluster="fls_product",
        node="qsh5-db-fls-product-122",
        fault_time="2025-03-23 00:01:00",
        data_gaps=[
            {"item": "慢查询列表", "expected_source": "CK 聚合统计", "actual_status": "已归档", "alternative": "联系 DBA 查询原始慢日志"},
            {"item": "连接数快照", "expected_source": "CK 10s 快照", "actual_status": "已归档", "alternative": "Grafana 历史曲线"},
        ],
        output_path="/tmp/test_limited_report.html"
    )
    print("已生成测试报告: /tmp/test_limited_report.html")
