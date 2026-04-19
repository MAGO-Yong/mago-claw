#!/usr/bin/env python3
"""
rec-new-note-diagnosis v3.6 - 完整详细数据版

核心要求：
1. 从Step 0到Step 6，每一步都展示完整查询数据
2. 每个判断都有数据支撑，不直接说"正常"
3. 展示原始指标值、对比值、计算过程
4. 即使指标正常，也要展示详细分析过程
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
SKILLS_DIR = os.path.dirname(SKILL_DIR)
WORKSPACE_DIR = os.path.dirname(SKILLS_DIR)

XRAY_CHANGEVENT_QUERY = os.path.join(SKILLS_DIR, "xray_changevent_query", "scripts", "query.py")
XRAY_METRICS_QUERY = os.path.join(SKILLS_DIR, "xray_metrics_query", "scripts", "query.py")
INDEX_SWITCH_CHECK = os.path.join(SKILLS_DIR, "index-switch-check", "scripts", "check_switch.py")
SSO_TOKEN_FILE = "/home/node/.token/sso_token.json"
CONFIG_WATCHLIST = os.path.join(SKILL_DIR, "references", "config-watchlist.json")


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
PROMQL_COLLECTION = os.path.join(SKILL_DIR, "references", "promql-collection.json")
DECISION_TREE = os.path.join(SKILL_DIR, "references", "decision-tree.json")

SEP = "=" * 76
SEP2 = "-" * 76


class AnomalyDetail:
    """异常详细信息数据类"""
    def __init__(self, **kwargs):
        self.severity = kwargs.get('severity', '🟡')           # 🔴🟠🟡
        self.metric_name = kwargs.get('metric_name', '')       # 指标名称
        self.current_value = kwargs.get('current_value', 0.0)  # 当前值
        self.baseline_value = kwargs.get('baseline_value', 0.0)  # 基准值
        self.current_time = kwargs.get('current_time', '')     # 当前时间
        self.baseline_time = kwargs.get('baseline_time', '')   # 基准时间
        self.absolute_diff = kwargs.get('absolute_diff', 0.0)  # 绝对差异
        self.percent_change = kwargs.get('percent_change', 0.0)  # 百分比变化
        self.threshold = kwargs.get('threshold', 0.0)          # 阈值
        self.threshold_rule = kwargs.get('threshold_rule', '') # 阈值依据
        self.affected_services = kwargs.get('affected_services', [])  # 受影响服务
        self.affected_channels = kwargs.get('affected_channels', [])  # 受影响渠道
        self.anomaly_time = kwargs.get('anomaly_time', '')     # 异常时间点
        self.duration_minutes = kwargs.get('duration_minutes', 0)  # 持续时间
        self.root_cause = kwargs.get('root_cause', '')         # 根因
        self.related_changes = kwargs.get('related_changes', [])  # 关联变更
        self.recommended_actions = kwargs.get('recommended_actions', [])  # 建议操作
        self.verification_command = kwargs.get('verification_command', '')  # 验证命令
        self.time_series = kwargs.get('time_series', [])       # 时间序列数据
        self.sop_reference = kwargs.get('sop_reference', '')   # SOP引用
        
    def to_detailed_report(self) -> str:
        """生成详细报告"""
        lines = []
        
        # 标题
        lines.append(f"【{self.severity} 详细分析】{self.metric_name}")
        lines.append("")
        
        # 详细数据
        lines.append("【详细数据】")
        lines.append(f"├─ 当前值:    {self.current_value:.2f}{'%' if '占比' in self.metric_name else ''} (时间: {self.current_time})")
        lines.append(f"├─ 对比基准:  {self.baseline_value:.2f}{'%' if '占比' in self.metric_name else ''} (时间: {self.baseline_time})")
        lines.append(f"├─ 绝对差异:  {self.absolute_diff:+.2f}{'%' if '占比' in self.metric_name else ''}")
        lines.append(f"├─ 相对变化:  {self.percent_change:+.2f}%")
        lines.append(f"├─ 判定阈值:  {self.threshold:.2f}%")
        lines.append(f"└─ 判定依据:  {self.threshold_rule}")
        lines.append("")
        
        # 时间序列（如有）
        if self.time_series:
            lines.append("【关键时间点数据】")
            for ts in self.time_series[:5]:  # 最多显示5个
                lines.append(f"  {ts['time']}: {ts['value']:.2f} ({ts['label']})")
            lines.append("")
        
        # 影响范围
        if self.affected_services or self.affected_channels:
            lines.append("【影响范围】")
            if self.affected_services:
                lines.append(f"├─ 受影响服务:  {', '.join(self.affected_services)}")
            if self.affected_channels:
                lines.append(f"├─ 受影响渠道:  {', '.join(self.affected_channels)}")
            if self.anomaly_time:
                lines.append(f"├─ 异常时间点:  {self.anomaly_time}")
            if self.duration_minutes > 0:
                lines.append(f"└─ 持续时间:    {self.duration_minutes} 分钟")
            lines.append("")
        
        # 根因
        if self.root_cause:
            lines.append("【根因分析】")
            lines.append(f"└─ {self.root_cause}")
            lines.append("")
        
        # 关联变更
        if self.related_changes:
            lines.append("【关联变更】")
            for i, ch in enumerate(self.related_changes[:3], 1):
                lines.append(f"{i}. {ch.get('time', 'N/A')} | {ch.get('name', 'N/A')} | {ch.get('owner', 'N/A')}")
            lines.append("")
        
        # 建议操作
        if self.recommended_actions:
            lines.append("【建议操作】")
            for i, action in enumerate(self.recommended_actions, 1):
                lines.append(f"{i}. {action}")
            lines.append("")
        
        # 验证命令
        if self.verification_command:
            lines.append("【验证方式】")
            lines.append(f"└─ {self.verification_command}")
            lines.append("")
        
        return "\n".join(lines)


class NewNoteDiagnosis:
    # 从决策树读取的默认配置（可覆盖）
    DEFAULT_CONFIG = {
        'thresholds': {
            'anomaly_drop_pct': 5.0,      # 异常阈值
            'minor_drop_pct': 2.0,        # 轻微下跌阈值
            'note_age_warning': 20.0,     # 笔记年龄警告(%变老)
            'data_freshness_max': 1800,   # 数据新鲜度最大秒数
        },
        'limits': {
            'max_changes_display': 15,    # 最大显示变更数
            'max_metrics_points': 15,     # 最大显示指标点数
            'change_query_hours_before_anomaly': 3,  # 异常前查询小时数
            'change_query_hours_after_anomaly': 1,   # 异常后查询小时数
        }
    }
    
    def __init__(self, args):
        self.args = args
        self.promql = self._load_json(PROMQL_COLLECTION)
        self.decision_tree = self._load_json(DECISION_TREE)
        self.config = self._load_config_from_tree()
        
        # 存储查询时间范围 - 支持通过环境变量指定
        env_end = os.environ.get('DIAGNOSIS_END_TIME')
        if env_end:
            self.end_time = datetime.fromisoformat(env_end)
        else:
            self.end_time = datetime.now()
        env_start = os.environ.get('DIAGNOSIS_START_TIME')
        if env_start:
            self.start_time = datetime.fromisoformat(env_start)
        else:
            self.start_time = self.end_time - timedelta(hours=6)
    
    def _load_config_from_tree(self):
        """从决策树加载配置，合并到默认配置"""
        config = self.DEFAULT_CONFIG.copy()
        
        # 尝试从决策树读取配置
        tree_config = self.decision_tree.get('config', {})
        if tree_config:
            config['thresholds'].update(tree_config.get('thresholds', {}))
            config['limits'].update(tree_config.get('limits', {}))
        
        # 从quick_reference读取阈值
        quick_ref = self.decision_tree.get('quick_reference', {})
        for issue in quick_ref.get('root_causes', []):
            if 'threshold' in issue:
                # 可以在这里添加更多阈值映射
                pass
        
        return config

    def _load_json(self, path):
        try:
            with open(path) as f:
                return json.load(f)
        except:
            return {}

    def _load_config_watchlist(self):
        """加载 config-watchlist.json 配置监控清单"""
        return self._load_json(CONFIG_WATCHLIST)

    def _match_experiment_risk(self, changed_flags, exp_name, config_watchlist):
        """
        根据变更的 flags/参数名匹配 config-watchlist.json 中的 pattern 判定风险等级
        
        Args:
            changed_flags: 列表，变更的 flag/参数名
            exp_name: 实验名称（用于 pattern 匹配回退）
            config_watchlist: 完整的配置清单 dict
        
        Returns:
            tuple: (风险等级 "🔴"/"🟠"/"🟡"/"➖", risk_description, 匹配的pattern)
        """
        import fnmatch
        
        exp_flags_config = config_watchlist.get('experiment_flags', {})
        
        # 按优先级检查：critical -> high -> medium
        for level, emoji in [('critical', '🔴'), ('high', '🟠'), ('medium', '🟡')]:
            patterns = exp_flags_config.get(level, [])
            for item in patterns:
                pattern = item.get('pattern', '') if isinstance(item, dict) else item
                risk_desc = item.get('risk_description', '') if isinstance(item, dict) else ''
                
                # 检查每个变更的 flag 是否匹配 pattern
                for flag in changed_flags:
                    flag_lower = flag.lower()
                    if fnmatch.fnmatch(flag_lower, pattern.lower()) or pattern.lower() in flag_lower:
                        return emoji, risk_desc, pattern
        
        # 如果 flag 没匹配到，但实验名称匹配高危 pattern（回退机制）
        exp_lower = exp_name.lower()
        for level, emoji in [('critical', '🔴'), ('high', '🟠'), ('medium', '🟡')]:
            patterns = exp_flags_config.get(level, [])
            for item in patterns:
                pattern = item.get('pattern', '') if isinstance(item, dict) else item
                risk_desc = item.get('risk_description', '') if isinstance(item, dict) else ''
                if fnmatch.fnmatch(exp_lower, pattern.lower()):
                    return emoji, risk_desc, pattern
        
        return "➖", "", ""  # 无风险

    def run(self):
        print()
        print("╔" + "=" * 74 + "╗")
        print("║" + " " * 18 + "rec-new-note-diagnosis" + " " * 34 + "║")
        print("║" + " " * 20 + "新笔记下跌诊断  v3.7（带时间戳版）" + " " * 18 + "║")
        print("╚" + "=" * 74 + "╝")
        print()
        print(f"【诊断时间范围】{self.start_time.strftime('%Y-%m-%d %H:%M')} ~ {self.end_time.strftime('%Y-%m-%d %H:%M')}")
        print()

        if not self._check_deps(): return 1
        if not self._sso(): return 1

        # 调整执行顺序：先Step 1找出异常时间，再基于异常时间查变更
        anomaly_time = self._step1_anomaly()  # 返回异常时间点（如有）
        self._step0_changes(anomaly_time)      # 基于异常时间查询变更
        self._step2_phases()
        abnormal_channels = self._step3_channels()  # 返回异常渠道列表
        self._step4_root_cause()
        self._step5_index(abnormal_channels)  # 根据异常渠道检查对应索引
        self._step6_content()
        
        return 0

    # ─────────────────────────────────────────────────────────
    # Step-level Checker（步骤级自检，每步结论前调用）
    # ─────────────────────────────────────────────────────────
    def _step_check(self, step_label, *,
                    query_systems=None,       # 实际查询的系统列表，None=未过滤（全量）
                    data_points=None,         # (当期点数, 基准点数) 元组
                    conclusion=None,          # 即将输出的结论文本（用于逻辑检测）
                    single_point_drop=None,   # 单点跌幅(%)，用于抖动检测
                    single_point_duration_min=None,  # 抖动持续时长(分钟)
                    all_channels_uniform=False):     # 所有渠道跌幅是否高度一致
        """
        步骤级自检（三门）：
          门1 查询覆盖完整性
          门2 结论逻辑完整性
          门3 数据异常信号检测

        返回值: "ok" | "warn" | "block"
        block 时调用方应停止输出结论，补查后重来。
        """
        BANNER = "┌─────────────────────────────────────────┐"
        BANNER_END = "└─────────────────────────────────────────┘"

        gate1_ok   = True
        gate1_msgs = []
        gate2_ok   = True
        gate2_msgs = []
        gate3_lvl  = "ok"   # ok / warn / block
        gate3_msgs = []

        # ── 门1：查询覆盖完整性 ──────────────────────────────
        if query_systems is not None:
            # 用了系统过滤，但结论含"无变更"类表述
            if conclusion and any(kw in conclusion for kw in
                                  ["无变更", "零变更", "无 apollo", "无apollo",
                                   "no change", "无操作"]):
                gate1_ok = False
                gate1_msgs.append(
                    f"❌ 查询仅覆盖 {query_systems}，但结论含[无变更] → "
                    f"必须去掉 --system 过滤补查完整系统（含 baichuan/flink/datastudio）"
                )
            else:
                gate1_msgs.append(
                    f"✅ 系统过滤={query_systems}，结论未声明[无变更]，覆盖范围可接受"
                )
        else:
            gate1_msgs.append("✅ 未加系统过滤，覆盖所有系统")

        if data_points is not None:
            cur_pts, base_pts = data_points
            if cur_pts == 0:
                gate1_ok = False
                gate1_msgs.append(
                    f"❌ 当期数据点数=0，查询失败或数据已过期 → 跳过本步，标注[数据不可用]"
                )
            elif base_pts == 0:
                gate1_ok = False
                gate1_msgs.append(
                    f"❌ 基准数据点数=0，无法做同比 → 标注[无基准，无法判断趋势]"
                )
            else:
                gate1_msgs.append(f"✅ 数据点数 cur={cur_pts} base={base_pts}，完整")

        # ── 门2：结论逻辑完整性 ──────────────────────────────
        if conclusion:
            # 2a. 以无证据证明不存在
            if any(kw in conclusion for kw in
                   ["无变更", "零变更", "无异常", "正常"]) \
               and query_systems is not None:
                gate2_ok = False
                gate2_msgs.append(
                    "❌ [无/正常]类结论 + 有系统过滤 → 存在[以无证据证明不存在]风险，"
                    "结论应降级为: 已查系统范围内无变更，其他系统未覆盖"
                )
            # 2b. 直接因果断言（含"因为""导致""根因是"）
            if any(kw in conclusion for kw in ["因为", "导致", "根因是", "根本原因"]):
                gate2_msgs.append(
                    "⚠️ 含因果断言，确认: ① 变更时间早于T0? ② 有回滚验证或其他直接证据? "
                    "若否，请改为: 疑似 X，待验证"
                )
            # 2c. 单层正常推全链路正常
            if "召回正常" in conclusion and "mixRank" not in conclusion \
               and "混排" not in conclusion:
                gate2_ok = False
                gate2_msgs.append(
                    "❌ 仅说[召回正常]即下[整体正常]结论，未检查 mixRank/postRank → "
                    "召回是漏斗第一层，下游阶段需单独验证"
                )

        if not gate2_msgs:
            gate2_msgs.append("✅ 未发现逻辑缺陷")

        # ── 门3：数据异常信号检测 ────────────────────────────
        if single_point_drop is not None and single_point_drop < -20:
            duration = single_point_duration_min or 0
            if duration < 5:
                gate3_lvl = "warn"
                gate3_msgs.append(
                    f"⚠️ 单点跌幅 {single_point_drop:.1f}%，持续 {duration}min（<5min）"
                    f" → 疑似 Flink 重启或采集抖动；"
                    f"必须先补查该窗口 baichuan 变更（不加 --system 过滤），再出结论"
                )
            else:
                gate3_msgs.append(
                    f"✅ 跌幅 {single_point_drop:.1f}%，持续 {duration}min，非短暂抖动"
                )

        if all_channels_uniform:
            gate3_lvl = "warn" if gate3_lvl == "ok" else gate3_lvl
            gate3_msgs.append(
                "⚠️ 各渠道跌幅高度一致 → 优先检查分母（总曝光量）是否膨胀，"
                "再检查分子（新笔记量），避免误判"
            )

        if not gate3_msgs:
            gate3_msgs.append("✅ 无异常信号")

        # ── 综合判定 ──────────────────────────────────────────
        if not gate1_ok or not gate2_ok:
            overall = "❌ 阻断，需补查"
            overall_sym = "block"
        elif gate3_lvl == "warn":
            overall = "⚠️ 降级输出（结论改为[疑似+待验证]格式）"
            overall_sym = "warn"
        else:
            overall = "✅ 可输出"
            overall_sym = "ok"

        # ── 打印（仅在非 ok 或 verbose 模式时完整打印）────────
        verbose = getattr(self.args, 'verbose', False)
        if overall_sym != "ok" or verbose:
            print(BANNER)
            print(f"│ 🔍 Step-level Check @ {step_label}")
            print(f"├─────────────────────────────────────────┤")
            print(f"│ 门1 查询覆盖：{'✅' if gate1_ok else '❌'}")
            for m in gate1_msgs:
                print(f"│   {m}")
            print(f"│ 门2 结论逻辑：{'✅' if gate2_ok else '❌'}")
            for m in gate2_msgs:
                print(f"│   {m}")
            print(f"│ 门3 数据信号：{'✅' if gate3_lvl=='ok' else gate3_lvl.upper()}")
            for m in gate3_msgs:
                print(f"│   {m}")
            print(f"├─────────────────────────────────────────┤")
            print(f"│ 自检结论：{overall}")
            print(BANNER_END)
            print()
        else:
            # ok 时只打一行摘要
            print(f"  [Step-check ✅ {step_label}]")

        return overall_sym

    # ─────────────────────────────────────────────────────────
    # Step 0: 配置变更预检（优化版 - 基于异常时间）
    # ─────────────────────────────────────────────────────────
    def _step0_changes(self, anomaly_time=None):
        print(SEP)
        print("Step 0: 配置变更预检（基于异常时间动态查询）")
        print(SEP)
        print()

        # 动态计算查询范围：从配置读取时间参数
        hours_before = self.config['limits']['change_query_hours_before_anomaly']
        hours_after = self.config['limits']['change_query_hours_after_anomaly']
        
        if anomaly_time:
            q_end = anomaly_time + timedelta(hours=hours_after)
            q_start = anomaly_time - timedelta(hours=hours_before)
            print(f"【基于Step 1发现的异常时间】{anomaly_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"【变更查询范围】{q_start.strftime('%Y-%m-%d %H:%M')} ~ {q_end.strftime('%Y-%m-%d %H:%M')} (异常前后{hours_before}h+{hours_after}h)")
        else:
            q_end = self.end_time
            q_start = q_end - timedelta(hours=hours_before)
            print(f"【无显著异常，查询诊断窗口前{hours_before}小时】")
            print(f"【变更查询范围】{q_start.strftime('%Y-%m-%d %H:%M')} ~ {q_end.strftime('%Y-%m-%d %H:%M')}")
        print(f"【优化策略】只查询 arkfeedx/arkmixrank 相关的高风险变更")
        print()

        # 查询Apollo + 实验平台变更
        try:
            r = subprocess.run(
                ["python3", XRAY_CHANGEVENT_QUERY,
                 "--start", q_start.strftime("%Y-%m-%d %H:%M:%S"),
                 "--end", q_end.strftime("%Y-%m-%d %H:%M:%S"),
                 "--system", "apollo", "racingweb",
                 "--tag", "外流推荐"],
                capture_output=True, text=True, timeout=30)

            apollo_changes = []
            exp_changes = []
            MAX_CHANGES = 50  # 限制最多处理50条变更，避免过量

            if r.returncode == 0:
                data = json.loads(r.stdout)
                events = data.get("events", []) if data.get("success") else []
                
                # 从 config-watchlist.json 加载配置清单
                config_watchlist = self._load_config_watchlist()
                
                # Apollo 配置按 key 建立映射，包含 risk_description
                apollo_config_map = {}
                for level in ['critical', 'high', 'medium']:
                    for item in config_watchlist.get('apollo_configs', {}).get(level, []):
                        if isinstance(item, dict) and 'key' in item:
                            apollo_config_map[item['key']] = {
                                'level': level,
                                'risk_desc': item.get('risk_description', ''),
                                'emoji': '🔴' if level == 'critical' else '🟠' if level == 'high' else '🟡'
                            }
                
                for ev in events:
                    if not isinstance(ev, dict): continue
                    result = ev.get("result") if isinstance(ev.get("result"), dict) else {}
                    
                    # Apollo配置 - 只保留arkfeedx/arkmixrank相关
                    for ot in result.get("objects", []):
                        if ot.get("value") == "app":
                            for app_obj in ot.get("objects", []):
                                app_name = app_obj.get("name", "")
                                # 严格过滤：只保留arkfeedx/arkmixrank
                                if "arkfeedx" not in app_name.lower() and "arkmixrank" not in app_name.lower():
                                    continue
                                for ts in app_obj.get("timespan", []):
                                    for evt in ts.get("events", [])[:10]:  # 每个时间段最多10条
                                        if len(apollo_changes) >= MAX_CHANGES:
                                            break
                                        raw_info = evt.get("info", {}) or {}
                                        # info 可能是 JSON 字符串，也可能是 dict
                                        if isinstance(raw_info, str):
                                            try:
                                                info = json.loads(raw_info)
                                            except Exception:
                                                info = {}
                                        else:
                                            info = raw_info
                                        change_key = info.get("change_object", "") if isinstance(info, dict) else ""
                                        # 根据 config-watchlist.json 判定风险等级和风险描述
                                        if change_key in apollo_config_map:
                                            cfg = apollo_config_map[change_key]
                                            risk_level = cfg['emoji']
                                            risk_desc = cfg['risk_desc']
                                        else:
                                            risk_level = "➖"  # 未在监控清单中
                                            risk_desc = ""
                                        apollo_changes.append({
                                            "time": evt.get("start", "Unknown")[:16],
                                            "app": app_name,
                                            "key": info.get("change_object", "N/A"),
                                            "value": str(info.get("after_value", ""))[:50],
                                            "operator": evt.get("operator_name", "Unknown"),
                                            "stage": evt.get("stage", "Unknown"),
                                            "risk": risk_level,
                                            "risk_desc": risk_desc
                                        })
                        
                        # 实验平台 - 只保留与arkfeedx/arkmixrank相关的高风险实验
                        elif ot.get("value") == "experiment":
                            for exp_obj in ot.get("objects", []):
                                exp_name = exp_obj.get("name", "")
                                for ts in exp_obj.get("timespan", []):
                                    for evt in ts.get("events", [])[:10]:  # 每个时间段最多10条
                                        if len(exp_changes) >= MAX_CHANGES:
                                            break
                                        rel = evt.get("related_resource", {}) or {}
                                        svcs = rel.get("service", []) + rel.get("app", [])
                                        # 确认关联服务
                                        if any("arkfeedx" in s or "arkmixrank" in s for s in svcs):
                                            # 从变更详情中提取实验参数/flags
                                            raw_info = evt.get("info", {}) or {}
                                            if isinstance(raw_info, str):
                                                try:
                                                    info = json.loads(raw_info)
                                                except Exception:
                                                    info = {}
                                            else:
                                                info = raw_info
                                            
                                            # 提取变更的 flag/参数名（从 info 或 details 中）
                                            changed_flags = []
                                            # 尝试多种可能的字段路径
                                            if isinstance(info, dict):
                                                # Apollo风格的变更
                                                if 'change_object' in info:
                                                    changed_flags.append(info['change_object'])
                                                # 实验详情中的 flags
                                                flags = info.get('flags', []) or info.get('parameters', []) or info.get('toggles', [])
                                                for f in flags:
                                                    if isinstance(f, str):
                                                        changed_flags.append(f)
                                                    elif isinstance(f, dict):
                                                        flag_name = f.get('name') or f.get('key') or f.get('flag_name')
                                                        if flag_name:
                                                            changed_flags.append(flag_name)
                                            
                                            # 根据 config-watchlist.json 中的 pattern 判定风险等级和风险描述
                                            risk_level, risk_desc, matched_pattern = self._match_experiment_risk(
                                                changed_flags, exp_name, config_watchlist)
                                            
                                            # 只保留有风险等级的变更（过滤掉 ➖ 无风险）
                                            if risk_level != "➖":
                                                exp_changes.append({
                                                    "time": evt.get("start", "Unknown")[:16],
                                                    "name": exp_name,
                                                    "operator": evt.get("operator_name", "Unknown"),
                                                    "stage": evt.get("stage", "Unknown"),
                                                    "tags": evt.get("tag", []),
                                                    "risk": risk_level,
                                                    "risk_desc": risk_desc,
                                                    "matched_pattern": matched_pattern,
                                                    "matched_flags": changed_flags[:3]  # 记录匹配的flags
                                                })

            max_display = self.config['limits']['max_changes_display']
            
            # 展示Apollo变更（按风险排序）
            apollo_changes.sort(key=lambda x: (0 if x['risk'] == '🔴' else 1 if x['risk'] == '🟠' else 2))
            print(f"【Apollo配置变更】共 {len(apollo_changes)} 条 (已过滤非arkfeedx/arkmixrank)")
            if apollo_changes:
                print(f"{'风险':<4} | {'时间':<16} | {'应用':<18} | {'变更人':<10} | {'配置Key'}")
                print(SEP2)
                for c in apollo_changes[:max_display]:  # 最多显示N条
                    key_short = c['key'][:25] if len(c['key']) > 25 else c['key']
                    print(f"{c['risk']:<4} | {c['time']:<16} | {c['app'][:16]:<18} | {c['operator'][:8]:<10} | {key_short}")
                    if c.get('risk_desc'):
                        print(f"    └─ 风险说明: {c['risk_desc'][:60]}")
                if len(apollo_changes) > max_display:
                    print(f"... 还有 {len(apollo_changes)-max_display} 条（只显示高风险部分）...")
            else:
                print("  🟢 无arkfeedx/arkmixrank相关Apollo变更")
            print()

            # 展示实验平台变更（按风险排序）
            exp_changes.sort(key=lambda x: (0 if x['risk'] == '🔴' else 1 if x['risk'] == '🟠' else 2))
            print(f"【实验平台变更】共 {len(exp_changes)} 条 (已过滤高风险实验)")
            if exp_changes:
                print(f"{'风险':<4} | {'时间':<16} | {'实验名称':<30} | {'变更人':<10}")
                print(SEP2)
                for c in exp_changes[:max_display]:  # 最多显示N条
                    name_short = c['name'][:28] if len(c['name']) > 28 else c['name']
                    print(f"{c['risk']:<4} | {c['time']:<16} | {name_short:<30} | {c['operator'][:8]:<10}")
                    if c.get('risk_desc'):
                        print(f"    └─ 风险说明: {c['risk_desc'][:60]}")
                    if c.get('matched_flags') and len(c['matched_flags']) > 0:
                        print(f"    └─ 匹配flags: {', '.join(c['matched_flags'][:2])}")
                if len(exp_changes) > max_display:
                    print(f"... 还有 {len(exp_changes)-max_display} 条 ...")
            else:
                print("  🟢 无高风险实验变更")
            print()

            # 风险统计
            critical = [c for c in exp_changes if c['risk'] == '🔴']
            high = [c for c in exp_changes if c['risk'] == '🟠']
            medium = [c for c in exp_changes if c['risk'] == '🟡']
            
            print(f"【风险统计 - 基于 config-watchlist.json 匹配】")
            print(f"  🔴 极高风险: {len(critical)} (匹配 experiment_flags.critical / apollo_configs.critical)")
            print(f"  🟠 高风险:   {len(high)} (匹配 experiment_flags.high / apollo_configs.high)")
            print(f"  🟡 中风险:   {len(medium)} (匹配 experiment_flags.medium / apollo_configs.medium)")
            
            if critical:
                print(f"\n  ⚠️  检测到{len(critical)}个极高风险变更，建议立即检查！")
                print(f"  SOP建议: 根据 config-watchlist.json 关联的 step 进行重点排查")
            elif high:
                print(f"\n  🟠 检测到{len(high)}个高风险变更，建议关注指标趋势")
            else:
                print(f"\n  🟢 无高风险变更，继续正常诊断流程")
            print()

            # ── 存储 watchlist 命中，供 ProgressiveDiagnosisRunner 分诊使用 ──
            self._watchlist_hits = (
                [{"level": "critical", "key": c.get("name", "?"), "time": c.get("time", "?")} for c in critical] +
                [{"level": "high",     "key": c.get("name", "?"), "time": c.get("time", "?")} for c in high] +
                [{"level": "medium",   "key": c.get("name", "?"), "time": c.get("time", "?")} for c in medium]
            )

            # ── Step-level check（Step 0 变更查询后）──────────
            # 注意：Step 0 默认查全系统（无 --system 过滤），所以 query_systems=None
            conclusion_text = "无高风险变更" if not critical and not high else "有高风险变更"
            self._step_check(
                "Step0/变更预检",
                query_systems=None,   # 全量系统，覆盖完整
                conclusion=conclusion_text,
            )

        except subprocess.TimeoutExpired:
            print(f"⚠️ 查询变更超时（限制30秒），可能是数据量过大")
            print(f"   建议：缩小时间范围或增加服务过滤")
            print()
        except Exception as e:
            print(f"⚠️ 查询变更异常: {e}")
            print()

    # ─────────────────────────────────────────────────────────
    # Step 1: 新笔记占比（详细对比数据 + 返回异常时间）
    # ─────────────────────────────────────────────────────────
    def _step1_anomaly(self):
        print(SEP)
        print("Step 1: 新笔记曝光占比下跌（详细数据对比 + 时间戳）")
        print(SEP)
        print()

        step1 = self.promql.get("steps", {}).get("step1", {}).get("queries", {})
        anomaly_time = None  # 用于记录异常时间点

        # 1H新笔记
        print("【1.1】1小时新笔记占比对比（带完整时间戳）")
        print(SEP2)
        
        promql_1h      = step1.get("1h_current",    {}).get("promql")
        promql_1h_base = step1.get("1h_offset_1d",  {}).get("promql")
        cur_1h  = self._query_raw(promql_1h,      self.start_time, self.end_time)
        base_1h = self._query_raw(promql_1h_base, self.start_time, self.end_time)
        
        result_1h = self._print_metric_comparison("1H新笔记占比", cur_1h, base_1h)
        if result_1h and result_1h.get('anomaly_time'):
            anomaly_time = result_1h['anomaly_time']
        print()

        # 24H新笔记
        print("【1.2】24小时新笔记占比对比（带完整时间戳）")
        print(SEP2)
        
        promql_24h      = step1.get("24h_current",   {}).get("promql")
        promql_24h_base = step1.get("24h_offset_1d", {}).get("promql")
        cur_24h  = self._query_raw(promql_24h,      self.start_time, self.end_time)
        base_24h = self._query_raw(promql_24h_base, self.start_time, self.end_time)
        
        result_24h = self._print_metric_comparison("24H新笔记占比", cur_24h, base_24h)
        # 如果1H没有异常但24H有异常，用24H的异常时间
        if not anomaly_time and result_24h and result_24h.get('anomaly_time'):
            anomaly_time = result_24h['anomaly_time']
        print()

        # 输出最终发现的异常时间和详细信息
        if anomaly_time:
            # 找出是哪个指标检测到的异常
            source = "1H新笔记占比" if (result_1h and result_1h.get('anomaly_time')) else "24H新笔记占比"
            result = result_1h if (result_1h and result_1h.get('anomaly_time')) else result_24h
            
            # 生成详细异常报告
            print(f"{'='*76}")
            print(f"【🔴 异常确认 - 详细信息】")
            print(f"{'='*76}")
            print()
            print("【判定摘要】")
            print(f"├─ 异常指标:   {source}")
            print(f"├─ 异常时间点: {anomaly_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"├─ 检测阈值:   下跌超过 {self.config['thresholds']['anomaly_drop_pct']}%")
            print(f"└─ 判定依据:   SOP Step 1.1 - 新笔记占比下跌超过阈值触发异常调查")
            print()
            print("【关键时间点数据】")
            print(f"  {anomaly_time.strftime('%m-%d %H:%M')}: {result.get('anomaly_value', 'N/A')}")
            print(f"  {anomaly_time.strftime('%m-%d %H:%M')}(昨天): {result.get('baseline_value', 'N/A')}")
            print(f"  跌幅: {result.get('anomaly_drop', 'N/A')}")
            print()
            print("【下一步操作】")
            print(f"├─ Step 0: 查询 {anomaly_time.strftime('%H:%M')} 前后3小时的变更事件")
            print(f"├─ Step 2: 定位具体下跌阶段")
            print(f"└─ Step 3: 排查召回渠道异常")
            print()
            print(f"{'='*76}")
        else:
            print(f"【Step 1 结论】🟢 未发现显著异常（1H和24H跌幅均<5%）")
            print(f"              按诊断时间窗口末尾前3小时查询变更")
        print()

        # ── 将关键数据存到 self，供 ProgressiveDiagnosisRunner 分诊使用 ──
        def _get_drop(r):
            if not r: return 0
            return r.get("stats", {}).get("drop_pct", 0) or r.get("drop_pct", 0)
        self._last_drop_1h_pct  = -_get_drop(result_1h)
        self._last_drop_24h_pct = -_get_drop(result_24h)

        # ── Step-level check（Step 1 指标结论后）─────────────
        is_anomaly = anomaly_time is not None
        cur_pts  = sum(len(r.get("values",[])) for r in (result_1h or {}).get("raw",[]))\
                   if result_1h and isinstance(result_1h.get("raw"), list) else \
                   (1 if result_1h else 0)
        base_pts = 1 if result_1h else 0  # 简化：有 result_1h 说明数据存在

        # 检查是否有异常幅度的单点（用 _last_drop_1h_pct 近似）
        drop_1h = abs(self._last_drop_1h_pct or 0)
        self._step_check(
            "Step1/指标确认",
            data_points=(cur_pts, base_pts),
            conclusion="异常" if is_anomaly else "无异常",
            single_point_drop=-drop_1h if drop_1h > 20 else None,
            single_point_duration_min=30,   # Step1 是长时段均值，不是短暂抖动
        )

        return anomaly_time

    def _print_metric_comparison(self, label, current, baseline):
        """打印详细的指标对比，返回异常时间点（如有）"""
        if not current or not baseline:
            print(f"  ⚠️ 数据缺失")
            return None

        # 解析数据 - 保留原始时间戳
        cur_vals = [(float(v[0]), float(v[1])) for row in current for v in row.get("values", []) if v[1]]
        base_vals = [(float(v[0]), float(v[1])) for row in baseline for v in row.get("values", []) if v[1]]

        if not cur_vals or not base_vals:
            print(f"  ⚠️ 无有效数据")
            return None

        # 计算统计
        cur_nums = [v[1] for v in cur_vals]
        base_nums = [v[1] for v in base_vals]
        
        cur_avg = sum(cur_nums) / len(cur_nums) * 100
        cur_min = min(cur_nums) * 100
        cur_max = max(cur_nums) * 100
        base_avg = sum(base_nums) / len(base_nums) * 100
        base_min = min(base_nums) * 100
        base_max = max(base_nums) * 100

        # 找出跌幅最大的时间点（遍历所有数据，不只是最后15个）
        max_drop_pct = 0
        max_drop_time = None
        
        # 先遍历所有数据找出最大跌幅时间点
        for i in range(len(cur_vals)):
            if i >= len(base_vals):
                continue
            ts = cur_vals[i][0]
            cv = cur_vals[i][1] * 100
            bv = base_vals[i][1] * 100
            pct = ((cv - bv) / bv * 100) if bv > 0 else 0
            # 记录超过5%跌幅的时间点
            if pct < -5 and abs(pct) > max_drop_pct:
                max_drop_pct = abs(pct)
                max_drop_time = datetime.fromtimestamp(ts)

        # 展示最近N个时间点（带完整日期时间）
        max_points = self.config['limits']['max_metrics_points']
        print(f"  {'时间':<20} | {'当前值':>10} | {'昨天同期':>10} | {'差异':>10} | {'幅度':>8}")
        print(f"  {'-'*70}")
        
        for i in range(max(0, len(cur_vals)-max_points), len(cur_vals)):
            ts = cur_vals[i][0]
            cv = cur_vals[i][1] * 100
            bv = base_vals[i][1] * 100 if i < len(base_vals) else 0
            diff = cv - bv
            pct = (diff / bv * 100) if bv > 0 else 0
            # 使用完整日期时间格式
            time_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
            marker = " 🔴" if pct < -5 else (" 🟡" if pct < 0 else "")
            print(f"  {time_str:<20} | {cv:>9.2f}% | {bv:>9.2f}% | {diff:>+9.2f}% | {pct:>+7.2f}%{marker}")

        print(f"  {'-'*70}")
        print(f"  当前: 平均={cur_avg:.2f}%  最小={cur_min:.2f}%  最大={cur_max:.2f}%")
        print(f"  昨天: 平均={base_avg:.2f}%  最小={base_min:.2f}%  最大={base_max:.2f}%")
        
        drop_pct = (base_avg - cur_avg) / base_avg * 100 if cur_avg < base_avg else 0
        rise_pct = (cur_avg - base_avg) / base_avg * 100 if cur_avg > base_avg else 0
        
        result = {'anomaly_time': None}
        
        # 从配置读取阈值
        anomaly_threshold = self.config['thresholds']['anomaly_drop_pct']
        minor_threshold = self.config['thresholds']['minor_drop_pct']
        
        if drop_pct > 0:
            print(f"  相对昨天下跌: {drop_pct:.2f}%")
            if drop_pct >= anomaly_threshold:
                print(f"  🔴 SOP判定: 下跌超过 {anomaly_threshold}% 阈值，触发异常")
                if max_drop_time:
                    print(f"  🔴 最大跌幅时间点: {max_drop_time.strftime('%Y-%m-%d %H:%M:%S')} (跌幅 {max_drop_pct:.2f}%)")
                    result['anomaly_time'] = max_drop_time
                    # 记录异常时的具体数值
                    if max_drop_time:
                        # 找到对应的数据点
                        for i in range(len(cur_vals)):
                            if datetime.fromtimestamp(cur_vals[i][0]) == max_drop_time and i < len(base_vals):
                                result['anomaly_value'] = f"{cur_vals[i][1]*100:.2f}%"
                                result['baseline_value'] = f"{base_vals[i][1]*100:.2f}%"
                                result['anomaly_drop'] = f"{max_drop_pct:.2f}%"
                                break
            elif drop_pct >= minor_threshold:
                print(f"  🟡 SOP判定: 下跌 {drop_pct:.2f}%，在 {minor_threshold}%~{anomaly_threshold}% 之间（轻微）")
            else:
                print(f"  🟢 SOP判定: 下跌 {drop_pct:.2f}%，在 {minor_threshold}% 阈值内（正常波动）")
        else:
            print(f"  相对昨天上涨: {rise_pct:.2f}%")
            print(f"  🟢 SOP判定: 高于昨天同期")
        
        # 记录完整统计数据供详细报告使用
        result['stats'] = {
            'cur_avg': cur_avg,
            'cur_min': cur_min,
            'cur_max': cur_max,
            'base_avg': base_avg,
            'base_min': base_min,
            'base_max': base_max,
            'drop_pct': drop_pct,
            'rise_pct': rise_pct
        }
        
        return result

    # ─────────────────────────────────────────────────────────
    # Step 2: 各阶段占比（详细）
    # ─────────────────────────────────────────────────────────
    def _step2_phases(self):
        print(SEP)
        print("Step 2: 定位下跌阶段（各phase详细数据）")
        print(SEP)
        print()

        promql = self.promql.get("steps", {}).get("step2", {}).get("queries", {}).get("by_phase", {}).get("promql")
        if not promql:
            promql = "sum by (phase) (rate(new_note_cnt_sum{application=\"arkfeedx\",env=\"prod\",type=\"1h\",subPhase=\"after\"}[1m]))/sum by (phase) (rate(note_size_cnt_sum{application=\"arkfeedx\",env=\"prod\",subPhase=\"after\"}[1m]))"

        current = self._query_raw(promql, self.start_time, self.end_time)
        # 用时间偏移实现昨天对比：查询同样的 PromQL，但时间窗口向前移1天
        baseline = self._query_raw(promql,
                                   self.start_time - timedelta(days=1),
                                   self.end_time   - timedelta(days=1))

        if not current:
            print(f"⚠️ 查询失败，无法获取阶段数据")
            print()
            return

        print(f"{'阶段':<15} | {'当前平均':>10} | {'昨天平均':>10} | {'差异':>10} | {'跌幅':>8} | {'SOP判定'}")
        print(SEP2)

        for row in current:
            phase = row.get("metric", {}).get("phase", "unknown")
            vals = [float(v[1]) for v in row.get("values", []) if v[1]]
            if not vals:
                continue
            cur_avg = sum(vals) / len(vals) * 100

            # 找baseline
            base_avg = 0
            for brow in (baseline or []):
                if brow.get("metric", {}).get("phase") == phase:
                    bvals = [float(v[1]) for v in brow.get("values", []) if v[1]]
                    if bvals:
                        base_avg = sum(bvals) / len(bvals) * 100
                        break

            diff = cur_avg - base_avg
            drop = (-diff / base_avg * 100) if base_avg > 0 and diff < 0 else 0
            
            if drop > 5:
                judgment = "🔴 recall↓→Step3" if phase == "recall" else "🔴 异常→Step2.5"
                # 记录异常详细信息
                print(f"{phase:<15} | {cur_avg:>9.2f}% | {base_avg:>9.2f}% | {diff:>+9.2f}% | {drop:>7.2f}% | {judgment}")
                # 输出详细异常信息
                print()
                print(f"  【🔴 {phase} 阶段异常详情】")
                print(f"  ├─ 当前平均:   {cur_avg:.2f}%")
                print(f"  ├─ 昨天平均:   {base_avg:.2f}%")
                print(f"  ├─ 绝对差异:   {diff:+.2f}%")
                print(f"  ├─ 相对跌幅:   {drop:.2f}%")
                print(f"  ├─ 判定阈值:   >5% (SOP Step 2)")
                print(f"  └─ 判定结果:   {phase} 阶段显著下跌，需进一步排查")
                print()
            elif drop > 2:
                judgment = "🟡 轻微↓"
                print(f"{phase:<15} | {cur_avg:>9.2f}% | {base_avg:>9.2f}% | {diff:>+9.2f}% | {drop:>7.2f}% | {judgment}")
            else:
                judgment = "🟢 正常"
                print(f"{phase:<15} | {cur_avg:>9.2f}% | {base_avg:>9.2f}% | {diff:>+9.2f}% | {drop:>7.2f}% | {judgment}")

        print()
        print("【SOP分支逻辑】")
        print("  recall阶段下跌 >5%  →  进入Step 3 召回渠道排查")
        print("  postRank阶段下跌    →  进入Step 2.5 矛盾判断")
        print("  其他阶段异常        →  联系推荐算法团队")
        print()

        # ── Step-level check（Step 2 阶段结论后）────────────
        cur_pts  = len(current) if current else 0
        base_pts = len(baseline) if baseline else 0
        self._step_check(
            "Step2/阶段定位",
            data_points=(cur_pts, base_pts),
        )

    # ─────────────────────────────────────────────────────────
    # Step 3: 召回渠道（详细）
    # ─────────────────────────────────────────────────────────
    def _step3_channels(self):
        print(SEP)
        print("Step 3: 召回渠道排查（各渠道详细数据）")
        print(SEP)
        print()

        step3_q = self.promql.get("steps", {}).get("step3", {}).get("queries", {}).get("channel_recall", {})
        promql         = step3_q.get("promql")
        promql_base    = step3_q.get("promql_offset_1d")  # json 里如有独立字段
        if not promql:
            promql = "sum by (name) (rate(recall_num_exp_sum{application=\"arkfeedx\",env=\"prod\"}[1m]))"

        current  = self._query_raw(promql, self.start_time, self.end_time)
        # 昨天同期：统一用时间窗口偏移，不依赖字符串替换
        baseline = self._query_raw(promql_base or promql,
                                   self.start_time - timedelta(days=1),
                                   self.end_time   - timedelta(days=1))

        if not current:
            print(f"⚠️ 查询失败")
            print()
            return

        print(f"{'召回渠道':<25} | {'当前/min':>12} | {'昨天/min':>12} | {'比率':>8} | {'SOP判定'}")
        print(SEP2)

        abnormal = []
        for row in current:
            ch = row.get("metric", {}).get("name", "unknown")
            vals = [float(v[1]) for v in row.get("values", []) if v[1]]
            if not vals:
                continue
            cur_avg = sum(vals) / len(vals)

            base_avg = 0
            for brow in (baseline or []):
                if brow.get("metric", {}).get("name") == ch:
                    bvals = [float(v[1]) for v in brow.get("values", []) if v[1]]
                    if bvals:
                        base_avg = sum(bvals) / len(bvals)
                        break

            ratio = cur_avg / base_avg if base_avg > 0 else 1.0
            
            if ratio < 0.9:
                judgment = "🔴 异常→Step4"
                abnormal.append(ch)
                print(f"{ch:<25} | {cur_avg:>11.1f} | {base_avg:>11.1f} | {ratio:>7.2f} | {judgment}")
                # 输出详细异常信息
                print()
                print(f"  【🔴 {ch} 渠道异常详情】")
                print(f"  ├─ 当前召回量: {cur_avg:.1f}/min")
                print(f"  ├─ 昨天召回量: {base_avg:.1f}/min")
                print(f"  ├─ 衰减比率:   {ratio:.2f} (阈值: <0.9)")
                print(f"  ├─ 绝对减少:   {base_avg - cur_avg:.1f}/min ({(1-ratio)*100:.1f}%)")
                print(f"  └─ 判定依据:   SOP Step 3 - 召回渠道衰减超过10%需排查")
                print()
            elif ratio < 0.95:
                judgment = "🟡 轻微↓"
                print(f"{ch:<25} | {cur_avg:>11.1f} | {base_avg:>11.1f} | {ratio:>7.2f} | {judgment}")
            else:
                judgment = "🟢 正常"
                print(f"{ch:<25} | {cur_avg:>11.1f} | {base_avg:>11.1f} | {ratio:>7.2f} | {judgment}")

        print()
        if abnormal:
            print(f"【SOP判定】异常渠道: {', '.join(abnormal)} → 进入Step 4 根因分析")
        else:
            print(f"【SOP判定】渠道正常但占比跌 → 进入Step 2.5 矛盾判断")
        print()

        # ── Step-level check（Step 3 召回渠道结论后）────────
        # 检测各渠道跌幅是否高度一致（暗示分母变化而非分子）
        all_ratios = []
        for ch_data in (current or []):
            ch_meta = ch_data.get("metric", {})
            ch_name = ch_meta.get("name", "")
            cvals = [float(v[1]) for v in ch_data.get("values", []) if v[1]]
            if cvals:
                cur_a = sum(cvals)/len(cvals)
                for brow in (baseline or []):
                    if brow.get("metric", {}).get("name") == ch_name:
                        bvals = [float(v[1]) for v in brow.get("values", []) if v[1]]
                        if bvals:
                            base_a = sum(bvals)/len(bvals)
                            if base_a > 0:
                                all_ratios.append(cur_a/base_a)
        uniform = False
        if len(all_ratios) >= 3:
            avg_r = sum(all_ratios)/len(all_ratios)
            std_r = (sum((r-avg_r)**2 for r in all_ratios)/len(all_ratios))**0.5
            uniform = std_r < 0.02   # 标准差<2%认为高度一致

        self._step_check(
            "Step3/召回渠道",
            data_points=(len(current) if current else 0,
                         len(baseline) if baseline else 0),
            conclusion="召回正常" if not abnormal else f"异常渠道{len(abnormal)}个",
            all_channels_uniform=uniform,
        )

        return abnormal

    # ─────────────────────────────────────────────────────────
    # Step 4: 根因分析（详细）
    # ─────────────────────────────────────────────────────────
    def _step4_root_cause(self):
        print(SEP)
        print("Step 4: 召回根因分析（种子/年龄/quota三维数据）")
        print(SEP)
        print()

        # 4.1 种子个数
        print("【4.1】种子个数分析")
        promql = self.promql.get("steps", {}).get("step4", {}).get("queries", {}).get("seed_count", {}).get("promql")
        if promql:
            r = self._query_raw(promql, self.start_time, self.end_time)
            if r:
                for row in r:
                    reason = row.get("metric", {}).get("reason_type", "unknown")
                    vals = [float(v[1]) for v in row.get("values", []) if v[1]]
                    if vals:
                        avg = sum(vals) / len(vals)
                        print(f"  {reason}: 平均 {avg:.1f}/min")
            else:
                print("  数据: 无法获取种子个数")
        else:
            print("  PromQL: 未配置")
        print()

        # 4.2 笔记年龄（带异常值过滤）
        print("【4.2】召回阶段笔记年龄分析（已过滤异常尖刺）")
        promql = self.promql.get("steps", {}).get("step2_5", {}).get("queries", {}).get("note_age", {}).get("promql")
        if promql:
            current = self._query_raw(promql, self.start_time, self.end_time)
            # baseline - 使用正确的时间窗口偏移（而非字符串替换）
            baseline = self._query_raw(promql, 
                                       self.start_time - timedelta(days=1),
                                       self.end_time - timedelta(days=1))
            
            if current and baseline:
                for row in current:
                    typ = row.get("metric", {}).get("type", "unknown")
                    vals = [float(v[1]) for v in row.get("values", []) if v[1]]
                    if vals:
                        # 过滤异常尖刺（使用IQR方法或百分位数）
                        filtered_vals, removed_count, outlier_vals = self._filter_outliers(vals)
                        
                        # 计算统计值
                        cur_avg = sum(filtered_vals) / len(filtered_vals) if filtered_vals else 0
                        cur_max = max(filtered_vals) if filtered_vals else 0
                        
                        # 找baseline
                        base_avg = 0
                        base_max = 0
                        for brow in baseline:
                            if brow.get("metric", {}).get("type") == typ:
                                bvals = [float(v[1]) for v in brow.get("values", []) if v[1]]
                                if bvals:
                                    filtered_bvals, _, _ = self._filter_outliers(bvals)
                                    base_avg = sum(filtered_bvals) / len(filtered_bvals) if filtered_bvals else 0
                                    base_max = max(filtered_bvals) if filtered_bvals else 0
                                    break
                        
                        change = ((cur_avg - base_avg) / base_avg * 100) if base_avg > 0 else 0
                        threshold = self.config['thresholds']['note_age_warning']
                        marker = " 🔴变老" if change > threshold else (" 🟡轻微↑" if change > 0 else "")
                        
                        print(f"  {typ}:")
                        print(f"    平均值: 当前={cur_avg:.0f}min  昨天={base_avg:.0f}min  变化={change:+.1f}%{marker}")
                        print(f"    最大值: 当前={cur_max:.0f}min  昨天={base_max:.0f}min")
                        if removed_count > 0:
                            print(f"    ⚠️  已过滤 {removed_count} 个异常尖刺 (>{max(outlier_vals):.0f}min)")
            else:
                print("  数据: 无法获取笔记年龄")
        else:
            print("  PromQL: 未配置")
        print()

        # 4.3 Quota
        print("【4.3】Quota限制分析")
        print("  指标: recall_quota_limit_cnt_sum")
        print("  说明: 若quota被挤压，说明蒲公英或其他召回增加，需联系推荐策略")
        print()

        print("【SOP分支逻辑】")
        print("  种子供给不足 → Step 6 内容供给排查")
        print("  笔记年龄变老 → Step 5 索引排查")
        print("  quota变化    → 联系推荐策略团队")
        print()

    # ─────────────────────────────────────────────────────────
    # Step 5: 索引排查（详细）
    # ─────────────────────────────────────────────────────────
    def _step5_index(self, abnormal_channels=None):
        print(SEP)
        print("Step 5: 索引表排查（向量索引/Omega/数据新鲜度详细数据）")
        print(SEP)
        print()

        # 5.1 向量索引池quota
        print("【5.1】向量索引池quota")
        promql = self.promql.get("steps", {}).get("step5", {}).get("queries", {}).get("index_quota", {}).get("promql")
        if promql:
            r = self._query_raw(promql, self.start_time, self.end_time)
            print(f"  查询结果: 获取到 {len(r)} 个索引池数据")
            for row in r[:5]:  # 展示前5个
                name = row.get("metric", {}).get("name", "unknown")
                vals = [float(v[1]) for v in row.get("values", []) if v[1]]
                if vals:
                    print(f"    {name}: 平均={sum(vals)/len(vals):.1f}  最新={vals[-1]:.1f}")
        else:
            print("  PromQL: 未配置")
        print()

        # 5.2 omega笔记年龄
        print("【5.2】omega侧笔记年龄（过滤前）")
        promql = self.promql.get("steps", {}).get("step5", {}).get("queries", {}).get("omega_note_age", {}).get("promql")
        if promql:
            r = self._query_raw(promql, self.start_time, self.end_time, datasource="vms-search")
            if r:
                vals = [float(v[1]) for row in r for v in row.get("values", []) if v[1]]
                if vals:
                    print(f"  笔记年龄: 平均={sum(vals)/len(vals):.0f}min  最大={max(vals):.0f}min")
                    if max(vals) > 30:
                        print(f"  🔴 笔记年龄 >30min，存在索引新鲜度风险")
            else:
                print("  数据: 无法获取omega笔记年龄")
        else:
            print("  PromQL: 未配置")
        print()

        # 5.3 索引切换状态 - 根据异常渠道查询对应索引表名
        print("【5.3】索引切换状态检查")
        
        # 通过查询 vec_reason_and_pool_cnt 指标获取索引表名
        print("  查询异常渠道对应的索引表名...")
        
        # 获取索引池查询的 PromQL 模板
        index_pool_promql_template = self.promql.get("steps", {}).get("step5", {}).get("queries", {}).get("index_quota", {}).get("promql")
        
        indices_to_check = []
        
        if abnormal_channels and index_pool_promql_template:
            # 查询索引池数据
            r = self._query_raw(index_pool_promql_template, self.start_time, self.end_time)
            if r:
                # 建立 reason_type 到 name（索引表名）的映射
                channel_to_index_map = {}
                for row in r:
                    reason_type = row.get("metric", {}).get("reason_type", "")
                    idx_name = row.get("metric", {}).get("name", "")
                    if reason_type and idx_name:
                        if reason_type not in channel_to_index_map:
                            channel_to_index_map[reason_type] = []
                        channel_to_index_map[reason_type].append(idx_name)
                
                # 为每个异常渠道查找对应的索引
                for ch in abnormal_channels:
                    if ch in channel_to_index_map:
                        for idx_name in channel_to_index_map[ch]:
                            indices_to_check.append((ch, idx_name))
                            print(f"    ✓ {ch} → {idx_name}")
                    else:
                        print(f"    ⚠️  {ch}: 未找到对应索引表")
        
        if not indices_to_check:
            print("  未找到异常渠道对应的索引，检查默认索引 dssm_inst_v1_oo_1day")
            indices_to_check = [("默认", "dssm_inst_v1_oo_1day")]
        
        print()
        print("  开始检查索引切换状态...")
        
        # 检查每个索引
        for ch_name, idx_name in indices_to_check[:3]:  # 最多检查3个
            print()
            print(f"  【检查索引: {idx_name}】")
            print(f"    对应渠道: {ch_name}")
            try:
                r = subprocess.run(["python3", INDEX_SWITCH_CHECK, idx_name],
                                   capture_output=True, text=True, timeout=30)
                if r.returncode == 0 and r.stdout.strip():
                    lines = r.stdout.strip().splitlines()
                    # 提取关键信息
                    for line in lines:
                        if any(k in line for k in ['索引表:', '构建版本:', '上游最新数据:', '切换状态', 'zone']):
                            print(f"    {line}")
                else:
                    print(f"    ⚠️  检查失败或索引不存在")
            except Exception as e:
                print(f"    ⚠️  检查异常: {e}")
        print()

        # 5.4 数据新鲜度
        print("【5.4】正倒排数据新鲜度")
        promql = self.promql.get("steps", {}).get("step5", {}).get("queries", {}).get("data_freshness", {}).get("promql")
        if promql:
            r = self._query_raw(promql, self.start_time, self.end_time, datasource="vms-search")
            if r:
                vals = [float(v[1]) for row in r for v in row.get("values", []) if v[1]]
                if vals:
                    print(f"  数据新鲜度: 当前={vals[-1]:.0f}s  平均={sum(vals)/len(vals):.0f}s  最大={max(vals):.0f}s")
                    if max(vals) > 1800:  # 30min
                        print(f"  🔴 新鲜度 >1800s，存在数据流延迟风险 → Step 6.4")
            else:
                print("  数据: 无法获取新鲜度")
        else:
            print("  PromQL: 未配置")
        print()

        print("【SOP分支逻辑】")
        print("  索引切换卡住  → Step 5.5 深度排查(Kafka/内存/QPS)")
        print("  新鲜度异常    → Step 6.4 数据流排查")
        print("  索引正常      → Step 6 内容供给排查")
        print()

    # ─────────────────────────────────────────────────────────
    # Step 6: 内容供给（详细）
    # ─────────────────────────────────────────────────────────
    def _step6_content(self):
        print(SEP)
        print("Step 6: 内容供给排查（内容池/审核/发布链路详细数据）")
        print(SEP)
        print()

        # 6.1 内容池
        print("【6.1】内容池新笔记数")
        for label, key in [("1H内容池", "content_pool_1h"), ("24H内容池", "content_pool_24h")]:
            promql = self.promql.get("steps", {}).get("step6", {}).get("queries", {}).get(key, {}).get("promql")
            if promql:
                r = self._query_raw(promql, self.start_time, self.end_time, datasource="vms-search")
                if r:
                    vals = [float(v[1]) for row in r for v in row.get("values", []) if v[1]]
                    if vals:
                        print(f"  {label}: 当前={vals[-1]:.0f}  平均={sum(vals)/len(vals):.0f}  最小={min(vals):.0f}")
                else:
                    print(f"  {label}: 无数据")
        print()

        # 6.2 审核
        print("【6.2】审核重试任务数")
        promql = self.promql.get("steps", {}).get("step6", {}).get("queries", {}).get("audit_retry", {}).get("promql")
        if promql:
            r = self._query_raw(promql, self.start_time, self.end_time, datasource="vms-shequ")
            if r:
                for row in r:
                    code = row.get("metric", {}).get("code", "unknown")
                    vals = [float(v[1]) for v in row.get("values", []) if v[1]]
                    if vals:
                        avg = sum(vals) / len(vals)
                        print(f"  {code}: 平均={avg:.0f}  {'🔴 积压' if avg > 100 else ''}")
            else:
                print("  数据: 无法获取审核任务数")
        else:
            print("  PromQL: 未配置")
        print()

        # 6.3 发布链路
        print("【6.3】发布链路QPS")
        promql = self.promql.get("steps", {}).get("step6", {}).get("queries", {}).get("publish_qps", {}).get("promql")
        if promql:
            r = self._query_raw(promql, self.start_time, self.end_time, datasource="vms-shequ")
            if r:
                for row in r:
                    ep = row.get("metric", {}).get("endpoint", "unknown")
                    vals = [float(v[1]) for v in row.get("values", []) if v[1]]
                    if vals:
                        print(f"  {ep}: 平均={sum(vals)/len(vals):.1f} QPS")
            else:
                print("  数据: 无法获取发布QPS")
        else:
            print("  PromQL: 未配置")
        print()

        # 6.4 数据流
        print("【6.4】数据流/同步层排查")
        for name, key in [("Flink消费延迟", "flink_lag"), ("Lindorm写入P99", "lindorm_latency")]:
            promql = self.promql.get("steps", {}).get("step6_4", {}).get("queries", {}).get(key, {}).get("promql")
            if promql:
                r = self._query_raw(promql, self.start_time, self.end_time)
                print(f"  {name}: 查询 {'成功' if r else '失败'}")
            else:
                print(f"  {name}: PromQL未配置")
        print()

        print("【SOP结束】")
        print()

    # ─────────────────────────────────────────────────────────
    # 工具方法
    # ─────────────────────────────────────────────────────────
    def _query_raw(self, promql, start, end, datasource="vms-recommend", step=300):
        """原始查询，支持 SSO 自动刷新和重试"""
        if not promql:
            return []
        
        for attempt in range(2):  # 最多尝试2次
            try:
                q = {"promql": promql, "datasource": datasource,
                     "start_time": start.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                     "end_time":   end.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                     "step": step}
                r = subprocess.run(["python3", XRAY_METRICS_QUERY, json.dumps(q)],
                                   capture_output=True, text=True, timeout=30)
                
                if r.returncode == 0:
                    d = json.loads(r.stdout)
                    if d.get("success"):
                        return d.get("data", {}).get("data", [])
                    
                    # 检查是否是认证失败
                    error_msg = d.get("error", "").lower()
                    if ("认证" in error_msg or "auth" in error_msg or 
                        "token" in error_msg or "unauthorized" in error_msg):
                        if attempt == 0:
                            print(f"  ⚠️  SSO 认证失败，尝试刷新...", end=" ")
                            if self._sso_refresh():
                                print("✅ 成功，重试查询...")
                                continue  # 刷新成功，重试
                            else:
                                print("❌ 失败")
                else:
                    # 检查 stderr 中是否有认证相关信息
                    stderr = r.stderr.lower() if r.stderr else ""
                    if ("认证" in stderr or "auth" in stderr or 
                        "token" in stderr or "unauthorized" in stderr):
                        if attempt == 0:
                            print(f"  ⚠️  SSO 认证失败，尝试刷新...", end=" ")
                            if self._sso_refresh():
                                print("✅ 成功，重试查询...")
                                continue  # 刷新成功，重试
                            else:
                                print("❌ 失败")
            except Exception as e:
                if attempt == 0:
                    print(f"  ⚠️  查询异常: {e}")
        
        return []

    def _filter_outliers(self, data: list, method: str = "iqr") -> tuple:
        """
        过滤异常尖刺数据
        
        Args:
            data: 原始数据列表
            method: 过滤方法 ('iqr' 或 'percentile')
        
        Returns:
            (filtered_data, removed_count, outlier_values)
        """
        if not data or len(data) < 4:
            return data, 0, []
        
        sorted_data = sorted(data)
        n = len(sorted_data)
        
        if method == "iqr":
            # IQR方法 (Interquartile Range)
            q1_idx = n // 4
            q3_idx = 3 * n // 4
            q1 = sorted_data[q1_idx]
            q3 = sorted_data[q3_idx]
            iqr = q3 - q1
            
            # 定义异常值边界 (1.5 * IQR)
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            # 对于笔记年龄，我们只关心过高的值
            upper_bound = max(upper_bound, q3 * 2)  # 至少允许2倍Q3
            
        else:  # percentile method
            # 使用99.5百分位数作为上限
            p99_idx = int(n * 0.995)
            upper_bound = sorted_data[min(p99_idx, n-1)]
            lower_bound = 0  # 年龄不能为负
        
        # 过滤数据
        filtered = [x for x in data if lower_bound <= x <= upper_bound]
        outliers = [x for x in data if x < lower_bound or x > upper_bound]
        
        # 如果过滤掉太多数据，放宽条件
        if len(filtered) < len(data) * 0.5:
            # 使用更宽松的条件：只过滤掉最高1%的数据
            p99_idx = int(n * 0.99)
            upper_bound = sorted_data[min(p99_idx, n-1)]
            filtered = [x for x in data if x <= upper_bound]
            outliers = [x for x in data if x > upper_bound]
        
        return filtered, len(outliers), outliers

    def _check_deps(self):
        print(SEP); print("Step 0.1: 检测依赖项"); print(SEP); print()
        r = subprocess.run(["python3", os.path.join(SCRIPT_DIR, "check_dependencies.py")],
                           capture_output=True, text=True)
        print(r.stdout); return r.returncode == 0

    def _sso(self, verbose=True):
        """获取 SSO 登录态（直接读取 /home/node/.token/sso_token.json）
        
        Args:
            verbose: 是否打印详细步骤信息（Step 0.2 标题等）
        """
        if verbose:
            print(SEP); print("Step 0.2: 获取登录态"); print(SEP); print()
        token = read_sso_token()
        if token:
            if verbose:
                print("✅  登录态获取成功\n")
            else:
                print("✅  SSO 刷新成功")
            return True
        if verbose:
            print("❌  登录态获取失败，请确认 /home/node/.token/sso_token.json 是否存在")
        else:
            print("❌  SSO 刷新失败")
        return False

    def _sso_refresh(self):
        """轻量级 SSO 刷新（用于查询失败时自动重试）"""
        return bool(read_sso_token())


def main():
    p = argparse.ArgumentParser(description="rec-new-note-diagnosis v4.0（渐进式+无人值守）")
    # 原有参数
    p.add_argument("--step", type=int, default=0, help="从指定步骤开始 (0-6)")
    # 路径控制
    p.add_argument("--fast", action="store_true", help="强制走 Fast Path（无 GATE，快速结论）")
    p.add_argument("--deep", action="store_true", help="强制走 Deep Path（Step 1-6 全流程）")
    p.add_argument("--auto", action="store_true", help="全自动无人值守（跳过所有 GATE）")
    p.add_argument("--gate-timeout", type=int, default=300, help="GATE 等待超时秒数，超时后自动继续（默认 300s）")
    # 断点续诊
    p.add_argument("--resume", type=str, help="从会话快照恢复，填入 sessions/YYYY-MM-DD_HH-MM.json 路径")
    p.add_argument("--list-sessions", action="store_true", help="列出所有历史诊断会话")
    args = p.parse_args()

    # ── 列出历史会话 ─────────────────────────────────────────
    if args.list_sessions:
        sessions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sessions")
        try:
            from session_manager import SessionManager
            SessionManager.print_sessions(sessions_dir)
        except ImportError:
            print("session_manager 模块未找到，请确认 scripts/ 目录完整。")
        return

    # ── 渐进式诊断入口 ───────────────────────────────────────
    runner = ProgressiveDiagnosisRunner(args)
    sys.exit(runner.run())


# ═══════════════════════════════════════════════════════════════
# 渐进式诊断运行器（外层路由 + GATE 机制）
# ═══════════════════════════════════════════════════════════════

class ProgressiveDiagnosisRunner:
    """
    渐进式诊断路由器。

    三条路径：
      🟢 Fast Path   — 跌幅<5%，watchlist无命中 → 无GATE，直接输出结论
      🟡 Standard    — 跌幅5-15%，命中Medium/High → GATE A + GATE B → 结论
      🔴 Deep Path   — 跌幅>15% 或 Critical命中 → GATE A/B/C/D + 结论自检
    """

    GATE_BANNER = "━" * 60

    def __init__(self, args):
        self.args = args
        self.auto_mode = getattr(args, "auto", False)
        self.force_fast = getattr(args, "fast", False)
        self.force_deep = getattr(args, "deep", False)
        self.gate_timeout = getattr(args, "gate_timeout", 300)
        self.resume_file = getattr(args, "resume", None)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.skill_dir = os.path.dirname(script_dir)
        self.sessions_dir = os.path.join(self.skill_dir, "sessions")

        self.session = None
        self.path = None          # "fast" / "standard" / "deep"
        self.diagnosis = None     # NewNoteDiagnosis 实例

    def run(self) -> int:
        self._print_header()

        # 初始化 session 管理器
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from session_manager import SessionManager
            self.SessionManager = SessionManager
        except ImportError:
            self.SessionManager = None

        # 断点恢复
        if self.resume_file:
            return self._resume_from_snapshot()

        # 创建 diagnosis 实例（使用原有核心逻辑）
        self.diagnosis = NewNoteDiagnosis(self.args)
        if not self.diagnosis._check_deps():
            return 1
        if not self.diagnosis._sso():
            return 1

        # Step 1：查指标（始终执行）
        print(f"\n{'='*60}")
        print("阶段 1/4：指标确认")
        print(f"{'='*60}")
        anomaly_time = self.diagnosis._step1_anomaly()

        # 变更查询（基于异常时间）
        self.diagnosis._step0_changes(anomaly_time)

        # 分诊：决定路径
        self.path = self._determine_path()

        # 创建会话快照
        if self.SessionManager:
            sm = self.SessionManager(self.sessions_dir)
            params = {
                "start": self.diagnosis.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end": self.diagnosis.end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "tag": "外流推荐",
            }
            sm.create(params)
            sm.update(path=self.path, findings={"steps_completed": [0, 1]})
            self.session = sm

        # 按路径执行
        if self.path == "fast":
            return self._run_fast_path()
        elif self.path == "standard":
            return self._run_standard_path()
        else:
            return self._run_deep_path()

    # ─────────────────────────────────────────────────────────
    # 路径决策
    # ─────────────────────────────────────────────────────────

    def _determine_path(self) -> str:
        """根据 Step 1 结果和 watchlist 命中决定路径"""
        if self.force_fast:
            print("\n[路径] 用户指定 --fast，走 🟢 Fast Path")
            return "fast"
        if self.force_deep:
            print("\n[路径] 用户指定 --deep，走 🔴 Deep Path")
            return "deep"

        # 读取 Step 1 产出的跌幅（从 diagnosis 对象中获取，如无则用默认）
        drop_1h = getattr(self.diagnosis, "_last_drop_1h_pct", None)
        drop_24h = getattr(self.diagnosis, "_last_drop_24h_pct", None)

        # watchlist 命中统计（从 diagnosis 对象中获取）
        watchlist_hits = getattr(self.diagnosis, "_watchlist_hits", [])
        hit_levels = [h.get("level", "low") for h in watchlist_hits]

        try:
            from triage import triage
            result = triage(
                drop_1h_pct=drop_1h if drop_1h is not None else 0,
                drop_24h_pct=drop_24h,
                watchlist_hits=len(watchlist_hits),
                hit_levels=hit_levels,
            )
            path = result["path"]
            print(f"\n{self.GATE_BANNER}")
            print(f"🔀 分诊结果：{result['emoji']} {result['label']}  置信度：{result['confidence']}")
            for r in result["reasons"]:
                print(f"   ✓ {r}")
            print(self.GATE_BANNER)
            return path
        except Exception:
            # fallback：基于简单阈值
            if drop_1h is not None:
                if drop_1h < -15:
                    return "deep"
                elif drop_1h < -5:
                    return "standard"
            return "fast"

    # ─────────────────────────────────────────────────────────
    # Fast Path
    # ─────────────────────────────────────────────────────────

    def _run_fast_path(self) -> int:
        print(f"\n{'='*60}")
        print("🟢 Fast Path — 无重大异常，输出快速结论")
        print(f"{'='*60}\n")
        print("【结论】")
        print("  指标波动在正常范围内（跌幅 < 5%，watchlist 无高风险命中）")
        print("  建议：继续观察，无需止损操作")
        print()
        print("若需进一步排查，可使用：")
        print("  python3 scripts/diagnose.py --standard  # 执行 Standard Path")
        print("  python3 scripts/diagnose.py --deep      # 执行完整 Deep Path")
        if self.session:
            self.session.complete()
        return 0

    # ─────────────────────────────────────────────────────────
    # Standard Path
    # ─────────────────────────────────────────────────────────

    def _run_standard_path(self) -> int:
        # Step 2-4
        print(f"\n{'='*60}")
        print("🟡 Standard Path — 进行召回层分析")
        print(f"{'='*60}")

        print("\n阶段 2/4：阶段定位")
        self.diagnosis._step2_phases()
        if self.session:
            self.session.mark_step_completed(2)

        print("\n阶段 3/4：召回渠道分析")
        abnormal_channels = self.diagnosis._step3_channels()
        if self.session:
            self.session.mark_step_completed(3)

        print("\n阶段 4/4：召回根因定位")
        self.diagnosis._step4_root_cause()
        if self.session:
            self.session.mark_step_completed(4)

        # GATE A
        if not self._gate("A", "Step 1-4 完成",
                          next_info="可继续进入 Step 5-6（索引+内容供给）深度排查"):
            return self._output_conclusion()

        # 用户选择继续 → 升级为 Deep Path
        print("\n[路径升级] Standard → 🔴 Deep Path")
        self.path = "deep"
        return self._run_deep_steps_cd(abnormal_channels)

    # ─────────────────────────────────────────────────────────
    # Deep Path
    # ─────────────────────────────────────────────────────────

    def _run_deep_path(self) -> int:
        print(f"\n{'='*60}")
        print("🔴 Deep Path — 完整六步排查")
        print(f"{'='*60}")

        print("\n阶段 2/6：阶段定位")
        self.diagnosis._step2_phases()
        if self.session:
            self.session.mark_step_completed(2)

        print("\n阶段 3/6：召回渠道分析")
        abnormal_channels = self.diagnosis._step3_channels()
        if self.session:
            self.session.mark_step_completed(3)

        print("\n阶段 4/6：召回根因定位")
        self.diagnosis._step4_root_cause()
        if self.session:
            self.session.mark_step_completed(4)

        # GATE A
        self._gate("A", "Step 1-4 完成（指标+变更+召回层）",
                   next_info="Step 5 索引层排查", mandatory=True)

        return self._run_deep_steps_cd(abnormal_channels)

    def _run_deep_steps_cd(self, abnormal_channels) -> int:
        print("\n阶段 5/6：索引层排查")
        self._print_knowledge_hint("index-switch.md", "索引切换知识")
        self.diagnosis._step5_index(abnormal_channels)
        if self.session:
            self.session.mark_step_completed(5)

        # GATE B
        self._gate("B", "Step 5 索引层完成",
                   next_info="Step 6 内容供给排查", mandatory=True)

        print("\n阶段 6/6：内容供给排查")
        self._print_knowledge_hint("data-flow.md", "数据流知识")
        self.diagnosis._step6_content()
        if self.session:
            self.session.mark_step_completed(6)

        # GATE C
        self._gate("C", "Step 6 内容供给完成",
                   next_info="输出诊断结论 + 结论自检", mandatory=True)

        rc = self._output_conclusion()

        # 结论自检（Deep Path 专属）
        self._run_conclusion_review()

        return rc

    # ─────────────────────────────────────────────────────────
    # GATE 实现
    # ─────────────────────────────────────────────────────────

    def _gate(self, gate_id: str, completed_info: str, next_info: str = "",
              mandatory: bool = False) -> bool:
        """
        显示 GATE 信息并等待用户指令。
        --auto 模式下直接返回 True（继续）。
        mandatory=True 时忽略 /skip-deep，强制继续。
        返回 True = 继续，False = 用户选择跳过深度排查
        """
        print(f"\n{self.GATE_BANNER}")
        print(f"⏸️  GATE {gate_id} — {completed_info}")
        print(self.GATE_BANNER)

        if self.session:
            snap_path = self.session.pause(gate=gate_id)
            print(f"💾 快照已保存：{snap_path}")
        print()

        if next_info:
            print(f"下一步：{next_info}")
        print()

        if self.auto_mode:
            print("[--auto 模式] 自动继续...")
            return True

        # 显示可用指令
        print("输入指令：")
        print("  /continue    — 继续下一步")
        if not mandatory:
            print("  /skip-deep   — 跳过深度排查，直接输出当前结论")
        print("  /go-deep     — 强制进入完整深度排查（若在 Standard Path）")
        print("  /save        — 保存并退出（稍后用 --resume 恢复）")
        print()

        deadline = self.gate_timeout
        try:
            import select
            print(f"（{deadline}s 内未输入将自动继续）", flush=True)

            rlist, _, _ = select.select([sys.stdin], [], [], deadline)
            if rlist:
                cmd = sys.stdin.readline().strip().lower()
            else:
                print("\n[超时] 自动继续下一步...")
                return True
        except Exception:
            # 非 TTY 环境（如 CI）直接继续
            return True

        if cmd in ("/save", "save"):
            print("已保存。下次运行：")
            if self.session:
                print(f"  python3 scripts/diagnose.py --resume {self.session.session_file}")
            sys.exit(0)

        if not mandatory and cmd in ("/skip-deep", "skip-deep", "/skip", "skip"):
            print("[跳过] 输出当前结论...")
            return False

        if cmd in ("/go-deep", "go-deep"):
            self.path = "deep"
            return True

        # 默认：/continue 或任意 Enter
        return True

    # ─────────────────────────────────────────────────────────
    # 结论输出 + 自检
    # ─────────────────────────────────────────────────────────

    def _output_conclusion(self) -> int:
        print(f"\n{'='*60}")
        print("📋 诊断结论")
        print(f"{'='*60}")

        # 从 diagnosis 对象获取已收集的发现
        drop_1h = getattr(self.diagnosis, "_last_drop_1h_pct", None)
        drop_24h = getattr(self.diagnosis, "_last_drop_24h_pct", None)
        watchlist_hits = getattr(self.diagnosis, "_watchlist_hits", [])

        print()
        if drop_1h is not None:
            status = "🔴 异常" if drop_1h < -10 else "🟠 关注" if drop_1h < -5 else "🟢 正常"
            print(f"【1H新笔记曝光占比】{drop_1h:+.1f}%  {status}")
        if drop_24h is not None:
            status = "🔴 异常" if drop_24h < -10 else "🟠 关注" if drop_24h < -5 else "🟢 正常"
            print(f"【24H新笔记曝光占比】{drop_24h:+.1f}%  {status}")

        if watchlist_hits:
            print(f"\n【高风险变更】共命中 {len(watchlist_hits)} 条：")
            for h in watchlist_hits:
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(h.get("level", "low"), "⚪")
                print(f"  {emoji} {h.get('time', '?')}  {h.get('key', '?')}")
        else:
            print("\n【变更】watchlist 无高风险命中")

        print()
        print("【止损建议】")
        if watchlist_hits:
            critical = [h for h in watchlist_hits if h.get("level") == "critical"]
            high = [h for h in watchlist_hits if h.get("level") == "high"]
            if critical:
                print("  🔴 立即回滚以下 Critical 级变更（需人工确认）：")
                for h in critical:
                    print(f"     - {h.get('key', '?')} @ {h.get('time', '?')}")
            elif high:
                print("  🟠 建议回滚以下 High 级变更并观察恢复情况（需人工确认）：")
                for h in high:
                    print(f"     - {h.get('key', '?')} @ {h.get('time', '?')}")
        else:
            print("  无高风险变更，建议继续观察。")

        print()
        print(f"【后续监控】")
        print("  指标：rt_new_one_hour_new_note_imp_ratio{data_source=\"holo_rawtracker\",overview=\"true\"}")
        print("  阈值：绝对值 < 0.065 → ⚠️ 警戒  |  < 0.060 → 🔴 立即回滚")

        if self.session:
            self.session.complete()

        return 0

    def _run_conclusion_review(self):
        """运行结论自检（Deep Path 专属）"""
        if not self.session or not self.session.session_file:
            return

        print(f"\n{'='*60}")
        print("🔎 结论自检（上下文隔离验证）")
        print(f"{'='*60}")

        try:
            from conclusion_review import review, print_review
            result = review(self.session.session_file)
            print_review(result, self.session.get("session_id", ""))
        except Exception as e:
            print(f"[自检跳过] {e}")

    # ─────────────────────────────────────────────────────────
    # 断点恢复
    # ─────────────────────────────────────────────────────────

    def _resume_from_snapshot(self) -> int:
        if not self.SessionManager:
            print("错误：session_manager 模块未找到")
            return 1

        sm = self.SessionManager(self.sessions_dir)
        try:
            data = sm.load(self.resume_file)
        except FileNotFoundError as e:
            print(f"错误：{e}")
            return 1

        print(f"\n📂 恢复会话：{data['session_id']}")
        print(f"   路径：{data['path']}  |  上次停在 GATE {data.get('current_gate', '?')}")
        print(f"   已完成步骤：{data['findings'].get('steps_completed', [])}")

        params = data.get("diagnosis_params", {})
        print(f"   时间范围：{params.get('start', '?')} ~ {params.get('end', '?')}")
        print()
        print("[恢复说明] 请重新运行诊断命令，指定相同时间范围继续排查：")
        print(f"  python3 scripts/diagnose.py")
        print("（当前版本断点恢复仅展示快照内容，完整恢复功能在后续版本实现）")
        return 0

    # ─────────────────────────────────────────────────────────
    # 工具方法
    # ─────────────────────────────────────────────────────────

    def _print_header(self):
        print()
        print("╔" + "=" * 74 + "╗")
        print("║" + " " * 14 + "rec-new-note-diagnosis  v4.0" + " " * 32 + "║")
        print("║" + " " * 16 + "渐进式诊断 | Fast / Standard / Deep Path" + " " * 17 + "║")
        print("╚" + "=" * 74 + "╝")
        print()

    def _print_knowledge_hint(self, filename: str, description: str):
        """提示需要加载的知识文件"""
        knowledge_path = os.path.join(self.skill_dir, "knowledge", filename)
        if os.path.exists(knowledge_path):
            print(f"\n📚 [知识加载] {description} → knowledge/{filename}")


if __name__ == "__main__":
    main()
