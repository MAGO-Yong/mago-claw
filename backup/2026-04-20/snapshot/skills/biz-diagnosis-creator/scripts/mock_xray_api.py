#!/usr/bin/env python3
"""
Mock X-Ray 大盘/图表 API + 原子 Skill 列表查询
用于本地测试 biz-diagnosis-creator 交互效果

用法：
  python3 mock_xray_api.py dashboards --service ark0 --keyword 新笔记
  python3 mock_xray_api.py panels --dashboard_id ark_notefeed_monitor --keyword 占比
  python3 mock_xray_api.py skills --data_type metrics
  python3 mock_xray_api.py skills --list
"""

import json
import sys
import argparse

# ─── Mock 数据 ────────────────────────────────────────────────────────────────

MOCK_DASHBOARDS = [
    {
        "id": "ark_notefeed_monitor",
        "name": "ark-notefeed业务监控",
        "service": "ark0",
        "url": "https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong",
        "tags": ["推荐", "内流", "新笔记", "召回", "排序"],
        "panels": [
            {
                "id": "779",
                "name": "新笔记占比_笔记年龄1_24hr",
                "description": "分stage统计新笔记（1-24hr）占比，支持与7日前对比",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum by (stage) (rate(lownv_waterfall_total{application=~\"$appid\", env=~\"$env\", type=\"age\", tag=\"(1hr,24hr]\"}[1m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=779"
            },
            {
                "id": "1103",
                "name": "召回阶段_分渠道新笔记量",
                "description": "按召回渠道统计新笔记召回量，可用于定位哪个渠道突变",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum by (type) (rate(recall_newnote_waterfall_total{application=~\"$appid\", env=~\"$env\", name=\"day\"}[1m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1103"
            },
            {
                "id": "1000",
                "name": "召回多队列分渠道数量",
                "description": "召回阶段各多队列的笔记量，用于判断是否有突变",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum by (name, queue)(rate(recall_multiqueue_total{application=~\"$appid\"}[1m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1000"
            },
            {
                "id": "1042",
                "name": "粗排多队列分渠道数量",
                "description": "粗排阶段各多队列笔记量",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum by (name, queue)(rate(firstrank_multiqueue_total{application=~\"$appid\"}[1m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1042"
            },
            {
                "id": "683",
                "name": "正排完整率",
                "description": "统计笔记正排数据完整率，过低说明正排索引有问题",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "1-(sum by(xhs_zone)(rate(note_profile_stat_sum{application=\"$appid\", name=~\"missing|invalid\"}[1m])) / sum by(xhs_zone)(rate(note_profile_stat_count{application=\"$appid\", name=~\"missing|invalid\"}[1m]))) / (sum by(xhs_zone)(rate(note_profile_stat_sum{application=\"$appid\", name=~\"total\"}[1m])) / sum by(xhs_zone)(rate(note_profile_stat_count{application=\"$appid\", name=~\"total\"}[1m])))",
                "url": "https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=683"
            },
            {
                "id": "824",
                "name": "正排字段异常率",
                "description": "特征粒度的正排字段异常占比，排查新笔记时过滤 name=~\"notecreate.*\"",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum by (name)(rate(vf_note_info_check_total{application=\"$appid\", name!=\"all\"}[1m])) / sum(rate(vf_note_info_check_total{application=\"$appid\", name=\"all\"}[1m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=824"
            },
            {
                "id": "1132",
                "name": "粗排模型打分均值",
                "description": "粗排各模型打分均值趋势，突变说明模型异常",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "avg by (model)(rate(firstrank_model_score_sum{application=~\"$appid\"}[1m])) / avg by (model)(rate(firstrank_model_score_count{application=~\"$appid\"}[1m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1132"
            },
            {
                "id": "1085",
                "name": "精排模型打分均值",
                "description": "精排各模型打分均值趋势",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "avg by (model)(rate(finalrank_model_score_sum{application=~\"$appid\"}[1m])) / avg by (model)(rate(finalrank_model_score_count{application=~\"$appid\"}[1m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1085"
            },
            {
                "id": "1059",
                "name": "排序降级QPS",
                "description": "粗排/精排降级QPS，分first_rank和final_rank",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum by (rank_type)(rate(rank_downgrade_total{application=~\"$appid\"}[1m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/7ck8fwr4k/ark-notefeedye-wu-jian-kong?viewpanel=1059"
            }
        ]
    },
    {
        "id": "ark_overview",
        "name": "ark综合大盘",
        "service": "ark0",
        "url": "https://monitor.devops.xiaohongshu.com/d/rxobcm87k/ark",
        "tags": ["推荐", "空结果", "成功率", "QPS", "CPU"],
        "panels": [
            {
                "id": "5",
                "name": "场景空结果率",
                "description": "按场景统计空结果率，严重告警场景",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum by (scene_id)(rate(ark_empty_result_total{application=~\"$appid\"}[1m])) / sum by (scene_id)(rate(ark_request_total{application=~\"$appid\"}[1m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/rxobcm87k/ark?viewpanel=5"
            },
            {
                "id": "156",
                "name": "服务QPS（周同比）",
                "description": "服务整体QPS，支持与上周同期对比",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum(rate(api_request_count{application=~\"$appid\"}[1m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/rxobcm87k/ark?viewpanel=156"
            },
            {
                "id": "109",
                "name": "集群CPU利用率（分Zone）",
                "description": "按机房统计CPU利用率",
                "data_type": "metrics",
                "datasource": "vms-infra",
                "pql": "avg by (zone)(rate(container_cpu_usage_seconds_total{pod_name=~\"$appid-.*\"}[2m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/rxobcm87k/ark?viewpanel=109"
            }
        ]
    },
    {
        "id": "bifrost_send_monitor",
        "name": "消息发送链路大盘",
        "service": "bifrostimsend",
        "url": "https://monitor.devops.xiaohongshu.com/d/fld_fobik/xiao-xi-fa-song-lian-lu-da-pan",
        "tags": ["IM", "消息", "发送", "成功率", "MQ"],
        "panels": [
            {
                "id": "send_success_rate",
                "name": "私信发送成功率（分source/类型）",
                "description": "按source和消息类型统计私信发送成功率",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum(increase(msgunifiedmetricsreporter_total{stage=\"downward\",event=\"start\",type=\"default\"}[2m])) by (content_type, source) / sum(increase(msgunifiedmetricsreporter_total{stage=\"entry\", event=\"start\"}[2m])) by (content_type, source)",
                "url": "https://monitor.devops.xiaohongshu.com/d/fld_fobik/xiao-xi-fa-song-lian-lu-da-pan?viewpanel=send_success_rate"
            },
            {
                "id": "mq_backlog",
                "name": "异步MQ积压情况",
                "description": "消息发送链路MQ消费积压监控",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum(rocketmq_consumer_delay{phycluster=~\"default\", topic=~\"bifrostim-send-message-async-v2\"}) by (topic, group)",
                "url": "https://monitor.devops.xiaohongshu.com/d/fld_fobik/xiao-xi-fa-song-lian-lu-da-pan?viewpanel=mq_backlog"
            },
            {
                "id": "biz_error",
                "name": "业务异常量（分错误码）",
                "description": "发送链路业务异常量，按错误码分类",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum(rate(bizerrorreporter_total{env=~\"$env\"}[1m])) by (source)",
                "url": "https://monitor.devops.xiaohongshu.com/d/fld_fobik/xiao-xi-fa-song-lian-lu-da-pan?viewpanel=biz_error"
            },
            {
                "id": "downstream_success",
                "name": "下游服务调用成功率",
                "description": "发送链路对下游服务的调用成功率",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum by (servicename,endpoint)(increase(thrift_calls_count{application=\"bifrostimsend\", success=\"true\"}[1m])) / sum by (servicename,endpoint)(increase(thrift_calls_count{application=\"bifrostimsend\"}[1m]))",
                "url": "https://monitor.devops.xiaohongshu.com/d/fld_fobik/xiao-xi-fa-song-lian-lu-da-pan?viewpanel=downstream_success"
            },
            {
                "id": "longconn_traffic",
                "name": "长连接入口流量（私信/群聊）",
                "description": "来自长连的私信和群聊上行流量",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum by (source, endpoint)(rate(api_request_count{application=\"bifrostimsend\", cluster=~\"bifrostimsend-service-default\", endpoint=\"sendimmsg\"}[1m])[1m])",
                "url": "https://monitor.devops.xiaohongshu.com/d/fld_fobik/xiao-xi-fa-song-lian-lu-da-pan?viewpanel=longconn_traffic"
            }
        ]
    },
    {
        "id": "arkfeedx_perf",
        "name": "推荐外流性能大盘",
        "service": "arkfeedx",
        "url": "https://monitor.devops.xiaohongshu.com/d/arkfeedx_perf/tui-jian-wai-liu",
        "tags": ["外流", "推荐", "RT", "CPU", "劣化", "generate"],
        "panels": [
            {
                "id": "generate_qps",
                "name": "Generate QPS（分Zone）",
                "description": "推荐中控服务generate类型QPS，按机房",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum(rate(ark_processor_rt_seconds_count{perf_test=\"0\", name=\"common.dag.dagproc$generate\", application=\"arkfeedx\", cluster=~\"arkfeedx-1-default\", env=~\"prod\"}[1m])) by (zone)",
                "url": "https://monitor.devops.xiaohongshu.com/d/arkfeedx_perf/tui-jian-wai-liu?viewpanel=generate_qps"
            },
            {
                "id": "generate_rt",
                "name": "Generate 平均RT（ms）",
                "description": "推荐中控服务generate平均响应时间，毫秒",
                "data_type": "metrics",
                "datasource": "vms-recommend",
                "pql": "sum(rate(ark_processor_rt_seconds_sum{perf_test=\"0\", name=~\"common.dag.dagproc\\\\$generate\", application=\"arkfeedx\", cluster=~\"arkfeedx-1-default\", env=~\"prod\", zone!~\"alsh1|alsh1-gray\"}[2m])) / sum(rate(ark_processor_rt_seconds_count{perf_test=\"0\", name=~\"common.dag.dagproc\\\\$generate\", application=\"arkfeedx\", env=~\"prod\"}[2m])) * 1000",
                "url": "https://monitor.devops.xiaohongshu.com/d/arkfeedx_perf/tui-jian-wai-liu?viewpanel=generate_rt"
            },
            {
                "id": "cpu_utilization",
                "name": "CPU利用率（分Zone）",
                "description": "arkfeedx服务CPU利用率，按机房",
                "data_type": "metrics",
                "datasource": "vms-infra",
                "pql": "(avg(rate(container_cpu_usage_seconds_total{pod_name=~\"(arkfeedx-qcnj2-rec-c2-.*|arkfeedx-alhz1-rec-c2-.*|arkfeedx-rcsh1-idc-rec-c2-.*)\",container_name=~\"rec-arkfeedx\"}[2m])) / avg(kube_pod_container_resource_limits_cpu_cores{pod_name=~\"(arkfeedx-.*)\",container_name=~\"rec-arkfeedx\"}[2m])) * 100",
                "url": "https://monitor.devops.xiaohongshu.com/d/arkfeedx_perf/tui-jian-wai-liu?viewpanel=cpu_utilization"
            }
        ]
    }
]

MOCK_ATOMIC_SKILLS = [
    {
        "id": "metrics-compare",
        "name": "指标环比/同比对比",
        "description": "查询指标当前值与历史值（1d/7d/1h前）的对比，输出变化率和趋势判断",
        "data_types": ["metrics"],
        "use_cases": ["周同比下跌检测", "趋势突变识别", "日常巡检对比"],
        "input_params": ["pql", "datasource", "offset", "threshold"],
        "doc_url": "https://xray.devops.xiaohongshu.com/skills/metrics-compare"
    },
    {
        "id": "metrics-breakdown",
        "name": "指标分维度下钻",
        "description": "按指定维度（zone/source/type等）分组查询指标，识别突变的子维度",
        "data_types": ["metrics"],
        "use_cases": ["召回渠道分析", "分source成功率", "按机房定位"],
        "input_params": ["pql", "datasource", "group_by", "top_n"],
        "doc_url": "https://xray.devops.xiaohongshu.com/skills/metrics-breakdown"
    },
    {
        "id": "metrics-threshold",
        "name": "指标阈值检测",
        "description": "检测指标是否超过/低于阈值，支持绝对值和百分比阈值",
        "data_types": ["metrics"],
        "use_cases": ["完整率检测", "成功率低于95%", "空结果率检测"],
        "input_params": ["pql", "datasource", "threshold", "direction"],
        "doc_url": "https://xray.devops.xiaohongshu.com/skills/metrics-threshold"
    },
    {
        "id": "metrics-correlation",
        "name": "指标相关性分析",
        "description": "分析两个指标之间的相关性，建立量化关系模型（如QPS-RT关系）",
        "data_types": ["metrics"],
        "use_cases": ["QPS与RT关系建模", "流量与CPU关系", "劣化根因量化"],
        "input_params": ["pql_x", "pql_y", "datasource", "time_range"],
        "doc_url": "https://xray.devops.xiaohongshu.com/skills/metrics-correlation"
    },
    {
        "id": "log-query",
        "name": "日志查询",
        "description": "按条件查询日志，支持关键词、时间范围、服务过滤",
        "data_types": ["logs"],
        "use_cases": ["错误日志查询", "特定请求追踪", "异常关键词检索"],
        "input_params": ["service", "keyword", "time_range", "level"],
        "doc_url": "https://xray.devops.xiaohongshu.com/skills/log-query"
    },
    {
        "id": "log-cluster",
        "name": "日志聚类分析",
        "description": "对日志进行聚类，识别高频错误模式，输出Top错误及占比",
        "data_types": ["logs"],
        "use_cases": ["错误模式识别", "异常聚类", "新增错误发现"],
        "input_params": ["service", "time_range", "filter", "top_n"],
        "doc_url": "https://xray.devops.xiaohongshu.com/skills/log-cluster"
    },
    {
        "id": "trace-query",
        "name": "链路追踪查询",
        "description": "查询指定服务的链路数据，支持按TraceID、服务名、耗时过滤",
        "data_types": ["trace"],
        "use_cases": ["慢请求定位", "链路完整性检查", "下游依赖耗时分析"],
        "input_params": ["service", "time_range", "min_duration", "status"],
        "doc_url": "https://xray.devops.xiaohongshu.com/skills/trace-query"
    },
    {
        "id": "change-query",
        "name": "变更记录查询",
        "description": "查询指定时间范围内的变更事件（发布、配置变更、实验变更等）",
        "data_types": ["change"],
        "use_cases": ["告警关联变更", "问题时间点变更查找", "回滚决策支持"],
        "input_params": ["service", "time_range", "change_type"],
        "doc_url": "https://xray.devops.xiaohongshu.com/skills/change-query"
    },
    {
        "id": "alert-context",
        "name": "告警上下文获取",
        "description": "根据告警ID获取告警详情、触发时间、关联规则和历史告警记录",
        "data_types": ["alert"],
        "use_cases": ["告警触发点确认", "历史告警频率分析", "告警规则查看"],
        "input_params": ["alert_id", "rule_id"],
        "doc_url": "https://xray.devops.xiaohongshu.com/skills/alert-context"
    },
    {
        "id": "topology-query",
        "name": "服务拓扑查询",
        "description": "查询服务的上下游依赖拓扑，支持成功率和QPS展示",
        "data_types": ["topology"],
        "use_cases": ["下游依赖识别", "链路全貌查看", "影响范围评估"],
        "input_params": ["service", "time_range", "depth"],
        "doc_url": "https://xray.devops.xiaohongshu.com/skills/topology-query"
    },
    {
        "id": "metrics-multi-compare",
        "name": "多指标并行对比",
        "description": "同时查询多个指标并行对比，输出统一的变化分析报告",
        "data_types": ["metrics"],
        "use_cases": ["并行排查多个阶段", "多维度同时检测", "批量指标巡检"],
        "input_params": ["pql_list", "datasource", "offset"],
        "doc_url": "https://xray.devops.xiaohongshu.com/skills/metrics-multi-compare"
    }
]

# ─── API 函数 ─────────────────────────────────────────────────────────────────

def search_dashboards(service=None, keyword=None):
    """搜索大盘列表"""
    results = []
    for dash in MOCK_DASHBOARDS:
        if service and dash["service"] != service:
            continue
        if keyword:
            kw = keyword.lower()
            hit = (kw in dash["name"].lower() or
                   any(kw in t.lower() for t in dash["tags"]))
            if not hit:
                continue
        results.append({
            "id": dash["id"],
            "name": dash["name"],
            "service": dash["service"],
            "url": dash["url"],
            "tags": dash["tags"],
            "panel_count": len(dash["panels"])
        })
    return results


def search_panels(dashboard_id=None, keyword=None, data_type=None):
    """搜索图表（panel）"""
    results = []
    for dash in MOCK_DASHBOARDS:
        if dashboard_id and dash["id"] != dashboard_id:
            continue
        for panel in dash["panels"]:
            if data_type and panel["data_type"] != data_type:
                continue
            if keyword:
                kw = keyword.lower()
                hit = (kw in panel["name"].lower() or
                       kw in panel["description"].lower())
                if not hit:
                    continue
            results.append({
                "dashboard_id": dash["id"],
                "dashboard_name": dash["name"],
                "panel_id": panel["id"],
                "panel_name": panel["name"],
                "description": panel["description"],
                "data_type": panel["data_type"],
                "datasource": panel["datasource"],
                "pql": panel["pql"],
                "url": panel["url"]
            })
    return results


def list_atomic_skills(data_type=None):
    """列出原子 Skill"""
    if data_type:
        return [s for s in MOCK_ATOMIC_SKILLS if data_type in s["data_types"]]
    return MOCK_ATOMIC_SKILLS


def match_skill_for_panel(panel_data_type, use_case_hint=None):
    """根据图表数据类型和使用场景，推荐最匹配的原子 Skill"""
    candidates = [s for s in MOCK_ATOMIC_SKILLS if panel_data_type in s["data_types"]]
    if not use_case_hint or not candidates:
        return candidates[:2]  # 默认返回前两个
    # 简单关键词匹配
    hint = use_case_hint.lower()
    scored = []
    for skill in candidates:
        score = sum(1 for uc in skill["use_cases"] if any(w in uc for w in hint.split()))
        scored.append((score, skill))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:2]]


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Mock X-Ray API")
    subparsers = parser.add_subparsers(dest="cmd")

    # dashboards
    p_dash = subparsers.add_parser("dashboards", help="搜索大盘")
    p_dash.add_argument("--service", help="服务名，如 ark0")
    p_dash.add_argument("--keyword", help="关键词")

    # panels
    p_panel = subparsers.add_parser("panels", help="搜索图表")
    p_panel.add_argument("--dashboard_id", help="大盘ID")
    p_panel.add_argument("--keyword", help="关键词")
    p_panel.add_argument("--data_type", help="数据类型: metrics/logs/trace")

    # skills
    p_skill = subparsers.add_parser("skills", help="查询原子Skill")
    p_skill.add_argument("--data_type", help="数据类型过滤")
    p_skill.add_argument("--list", action="store_true", help="列出所有")
    p_skill.add_argument("--match_panel", help="图表数据类型，用于匹配推荐")
    p_skill.add_argument("--use_case", help="使用场景关键词（配合--match_panel）")

    args = parser.parse_args()

    if args.cmd == "dashboards":
        result = search_dashboards(service=args.service, keyword=args.keyword)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.cmd == "panels":
        result = search_panels(
            dashboard_id=args.dashboard_id,
            keyword=args.keyword,
            data_type=args.data_type
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.cmd == "skills":
        if args.match_panel:
            result = match_skill_for_panel(args.match_panel, args.use_case)
        else:
            result = list_atomic_skills(data_type=args.data_type)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
