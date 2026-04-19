#!/usr/bin/env python3
# ⚠️ DEPRECATED（2026-04-10）
# 历史兼容文件，依赖旧渲染架构（report_data_models / report_generator）。
# 当前所有路径已改为 AI 直接生成 HTML + publish_report.py 发布。
# 新路径禁止调用本脚本。保留仅供旧数据格式兼容场景参考。
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
    parser.add_argument('--path', default='', help='诊断路径字母，如 D / F / C2（用于文件命名）')
    parser.add_argument('--output', default='', help='输出文件路径（不传则按命名规范自动生成）')
    
    # 报告类型
    parser.add_argument('--limited', action='store_true', help='生成受限分析报告')
    parser.add_argument('--manual', action='store_true', help='生成人工分析报告')
    
    # 输入数据
    parser.add_argument('--input', help='JSON 数据文件路径')
    parser.add_argument('--gap-json', help='数据缺口 JSON 文件（受限报告用）')
    parser.add_argument('--events-json', help='事件列表 JSON 文件')
    
    args = parser.parse_args()
    
    # 确定报告类型
    if args.limited:
        report_type = ReportType.LIMITED
    elif args.manual:
        report_type = ReportType.MANUAL
    else:
        report_type = ReportType.COMPLETE
    
    # P0-2：命名规范 —— {cluster}_{path}_{date}.html
    if not args.output:
        date_str = datetime.now().strftime("%Y%m%d")
        path_seg = f"path-{args.path}" if args.path else "report"
        cluster_slug = args.cluster.replace("_", "-")
        args.output = f"{cluster_slug}_{path_seg}_{date_str}.html"

    # 加载或构建报告数据
    if args.input:
        # 从完整 JSON 加载，并将嵌套 dict 转换为对应 dataclass
        from report_data_models import (
            SummaryCard, TimelineData, TimelinePoint, TimelineEvent,
            TableStatsEntry, TableStats, IndexStats, ExplainResult,
            ImpactAssessment, AppendixData, SlowQuerySummary
        )
        data_dict = load_json(args.input)

        # 转换 summary_card
        if isinstance(data_dict.get("summary_card"), dict):
            data_dict["summary_card"] = SummaryCard(**data_dict["summary_card"])

        # 转换 timeline
        if isinstance(data_dict.get("timeline"), dict):
            td = data_dict["timeline"]
            points = [TimelinePoint(**p) for p in td.get("points", [])]
            events = [TimelineEvent(**e) for e in td.get("events", [])]
            data_dict["timeline"] = TimelineData(points=points, events=events)

        # 转换 table_stats_list
        if isinstance(data_dict.get("table_stats_list"), list):
            entries = []
            for entry in data_dict["table_stats_list"]:
                ts = TableStats(**entry["table_stats"]) if isinstance(entry.get("table_stats"), dict) else entry.get("table_stats")
                idx = [IndexStats(**i) for i in entry.get("index_stats", [])]
                exp = [ExplainResult(**e) for e in entry.get("explain_results", [])]
                entries.append(TableStatsEntry(
                    table_stats=ts,
                    index_stats=idx,
                    explain_results=exp,
                    sql_template=entry.get("sql_template", "")
                ))
            data_dict["table_stats_list"] = entries

        # 转换 impact
        if isinstance(data_dict.get("impact"), dict):
            data_dict["impact"] = ImpactAssessment(**data_dict["impact"])

        # 转换 appendix
        if isinstance(data_dict.get("appendix"), dict):
            data_dict["appendix"] = AppendixData(**data_dict["appendix"])

        # 转换 slow_query_summary
        if isinstance(data_dict.get("slow_query_summary"), dict):
            # SlowQuerySummary 可能字段不完全对应，过滤掉多余字段
            import dataclasses
            sq_fields = {f.name for f in dataclasses.fields(SlowQuerySummary)}
            sq_dict = {k: v for k, v in data_dict["slow_query_summary"].items() if k in sq_fields}
            data_dict["slow_query_summary"] = SlowQuerySummary(**sq_dict)

        # report_type 枚举转换
        if isinstance(data_dict.get("report_type"), str):
            data_dict["report_type"] = ReportType(data_dict["report_type"])

        report_data = ReportData(**data_dict)
    else:
        # 构建基础报告数据
        report_data = ReportData(
            cluster_name=args.cluster,
            node_name=args.node,
            fault_time=args.fault_time,
            analysis_period=args.period,
            report_type=report_type,
            path=args.path,
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
    output_path, missing = generator.generate(report_data, args.output)
    if missing:
        print(f"[report-check] ⚠️ 缺少章节: {missing}")

    print(f"✅ 报告已生成: {output_path}")
    print(f"   类型: {report_type.value}")
    print(f"   集群: {args.cluster}")
    print(f"   节点: {args.node or 'N/A'}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
