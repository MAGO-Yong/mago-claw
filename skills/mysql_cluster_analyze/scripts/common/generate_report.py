#!/usr/bin/env python3
"""
快速报告生成入口
支持从 JSON 数据文件生成报告

用法：
    # 从 JSON 文件生成
    python3 generate_report.py --input data.json --output report.html
    
    # 生成受限报告（数据不足场景）
    python3 generate_report.py \
        --cluster fls_product \
        --node qsh5-db-fls-product-122 \
        --fault-time "2025-03-23 00:01:00" \
        --limited \
        --gap-json gaps.json \
        --output report.html
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from report_data_models import ReportData, ReportType, DataGap
from report_generator import ReportGenerator, generate_limited_report


def load_json(path: str) -> dict:
    """加载 JSON 文件"""
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description='MySQL 故障诊断报告生成器')
    
    # 基本参数
    parser.add_argument('--cluster', required=True, help='集群名称')
    parser.add_argument('--node', default='', help='节点名称')
    parser.add_argument('--fault-time', default='', help='故障时间')
    parser.add_argument('--period', default='', help='分析时段')
    parser.add_argument('--output', required=True, help='输出文件路径')
    
    # 报告类型
    parser.add_argument('--limited', action='store_true', help='生成受限分析报告')
    parser.add_argument('--manual', action='store_true', help='生成人工分析报告')
    
    # 输入数据
    parser.add_argument('--input', help='JSON 数据文件路径')
    parser.add_argument('--gap-json', help='数据缺口 JSON 文件（受限报告用）')
    parser.add_argument('--events-json', help='事件列表 JSON 文件')
    parser.add_argument('--conclusions-json', help='结论 JSON 文件')
    
    args = parser.parse_args()
    
    # 确定报告类型
    if args.limited:
        report_type = ReportType.LIMITED
    elif args.manual:
        report_type = ReportType.MANUAL
    else:
        report_type = ReportType.COMPLETE
    
    # 加载或构建报告数据
    if args.input:
        # 从完整 JSON 加载
        data_dict = load_json(args.input)
        report_data = ReportData(**data_dict)
    else:
        # 构建基础报告数据
        report_data = ReportData(
            cluster_name=args.cluster,
            node_name=args.node,
            fault_time=args.fault_time,
            analysis_period=args.period,
            report_type=report_type,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # 加载数据缺口（受限报告）
        if args.gap_json and Path(args.gap_json).is_file():
            try:
                gaps_data = load_json(args.gap_json)
                report_data.data_gaps = [DataGap(**g) for g in gaps_data]
                report_data.data_source_note = "部分历史数据无法获取"
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"⚠️ 无法加载数据缺口文件: {e}", file=sys.stderr)
        
        # TODO: 加载事件列表和结论
    
    # 生成报告
    generator = ReportGenerator()
    output_path = generator.generate(report_data, args.output)
    
    print(f"✅ 报告已生成: {output_path}")
    print(f"   类型: {report_type.value}")
    print(f"   集群: {args.cluster}")
    print(f"   节点: {args.node or 'N/A'}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
