#!/usr/bin/env python3
"""
get_system_lock_status.py — System lock 专项采集脚本

用途：
  专门用于路径 B2（连接堆积）中的 System lock 诊断。
  采集活跃会话中 State='System lock' 的详情，识别热点分表、
  AUTO-INC 锁风险、持锁 SQL 模板，辅助判断子路径。

认证：DMS_AI_TOKEN（通过 DMS-AI-Token header），走 ai-api/v1

调用方式：
  python3 scripts/atomic/get_system_lock_status.py \\
      --ip <master_ip> --port <master_port> \\
      --cluster sns_user_extra \\
      [--output output/ --run_id my_run]

输出 JSON（含 _analysis 字段）：
  {
    "system_lock_count": 6,
    "sleep_count": 110,
    "row_lock_count": 0,
    "total_active": 125,
    "subtype": "autoinc",        # autoinc / sleep_leak / row_lock / mixed / normal
    "autoinc_risk": true,        # INSERT IGNORE/REPLACE/INSERT...SELECT 触发
    "hot_tables": ["user_location_1d0", "user_location_1d3"],
    "system_lock_sqls": [...],   # System lock SQL 去重列表
    "sleep_leak_count": 0,       # Sleep time > 3600s 的连接数
    "risks": [...]
  }

历史教训（2026-04-01）：
  sns_user_extra lshm-db-user-9：
  - INSERT IGNORE INTO user_location_1d? 6条并发 System lock
  - innodb_autoinc_lock_mode=1 下 INSERT IGNORE 属于 bulk insert，持表级 AUTO-INC 锁
  - get_active_sessions.py 的 state_dist 返回空字符串，本脚本作为专项补充
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from common.dms_client import (
    AI_TOKEN, CLAW_TOKEN, BASE_URL, AI_V1_PREFIX,
    _AI_HEADERS, _http_post, call_with_fallback,
)

# System lock 触发风险 SQL 关键词（AUTO-INC 锁高危语句）
AUTOINC_RISK_PATTERNS = [
    re.compile(r'^\s*INSERT\s+IGNORE\b', re.IGNORECASE),
    re.compile(r'^\s*INSERT\s+.*\s+SELECT\b', re.IGNORECASE),
    re.compile(r'^\s*REPLACE\s+INTO\b', re.IGNORECASE),
    re.compile(r'^\s*LOAD\s+DATA\b', re.IGNORECASE),
]

# 连接泄漏判定：Sleep 时间超过此秒数视为泄漏
SLEEP_LEAK_THRESHOLD = 3600


def extract_table_name(sql: str) -> str | None:
    """从 INSERT/REPLACE SQL 中提取分表名"""
    sql_clean = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL).strip()
    # INSERT IGNORE INTO `db`.`table_name`
    m = re.search(r'(?:INTO|TABLE)\s+[`"]?(\w+)[`"]?\.?[`"]?(\w+)[`"]?', sql_clean, re.IGNORECASE)
    if m:
        return m.group(2) if m.group(2) else m.group(1)
    return None


def is_autoinc_risk_sql(sql: str) -> bool:
    """判断 SQL 是否是 AUTO-INC 锁高危语句"""
    sql_clean = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL).strip()
    return any(p.match(sql_clean) for p in AUTOINC_RISK_PATTERNS)


def normalize_sql(sql: str) -> str:
    """参数化 SQL，用于去重"""
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL).strip()
    sql = re.sub(r"'[^']*'", '?', sql)
    sql = re.sub(r'\b\d+\b', '?', sql)
    sql = re.sub(r'0x[0-9a-fA-F]+', '?', sql)
    return re.sub(r'\s+', ' ', sql).strip()[:200]


def analyze(ip: str, port: int, cluster: str = "") -> dict:
    """采集并分析 System lock 状态"""

    # 调用 v1 实时会话接口（节点级），兜底 open-claw
    payload_v1 = {"ip": ip, "port": str(port), "show_system_session": False}
    payload_old = {"ip": ip, "port": str(port), "filter": {"show_system_session": False}}
    try:
        resp = call_with_fallback(
            lambda: _http_post(f"{AI_V1_PREFIX}/mysql/session/get_cur_process_list", payload_v1, _AI_HEADERS),
            lambda: _http_post(f"{BASE_URL}/dms-api/v1/mysql/session-manage/get-cur-process-list", payload_old, {"dms-claw-token": CLAW_TOKEN}),
            "[get_system_lock_status]",
        )
    except Exception as e:
        return {"error": f"API 调用失败: {e}", "_analysis": {"subtype": "unknown", "risks": [f"❌ API 失败: {e}"]}}

    # 检查业务错误（HTTP 200 但实际失败）
    # v1 格式：errorMessage 非空表示失败
    # open-claw 格式：{"code": 0, "message": "ok", "data": {...}}，code != 0 才是失败
    if resp.get("errorMessage"):
        err = resp["errorMessage"]
        return {"error": f"业务错误: {err}", "_analysis": {"subtype": "unknown", "risks": [f"❌ 业务错误: {err}"]}}
    if resp.get("code", 0) != 0:
        err = f"code={resp.get('code')} {resp.get('message', '')}"
        return {"error": f"业务错误: {err}", "_analysis": {"subtype": "unknown", "risks": [f"❌ 业务错误: {err}"]}}

    data = resp.get("data") or {}
    all_sessions = data.get("connectionList") or []

    # ⚠️ 响应结构异常检测：all_sessions 为空时打印原始结构，避免静默返回假"正常"
    if not all_sessions:
        raw_keys = list(resp.keys()) if isinstance(resp, dict) else type(resp).__name__
        print(
            f"[get_system_lock_status] ⚠️  all_sessions 为空，响应顶层 keys={raw_keys}，"
            f"data 类型={type(data).__name__}，"
            f"可能响应结构已变更或集群无活跃连接",
            file=sys.stderr,
        )
        if isinstance(data, dict):
            print(f"[get_system_lock_status]    data keys={list(data.keys())}", file=sys.stderr)

    # 分组统计
    system_lock_sessions = []
    sleep_sessions = []
    row_lock_sessions = []
    other_sessions = []

    for s in all_sessions:
        state = str(s.get("State", s.get("state", ""))).strip()
        state_lower = state.lower()
        if "system lock" in state_lower:
            system_lock_sessions.append(s)
        elif state_lower == "sleep":
            sleep_sessions.append(s)
        elif "waiting for" in state_lower or "lock" in state_lower:
            row_lock_sessions.append(s)
        else:
            other_sessions.append(s)

    # System lock 详细分析
    hot_tables = {}
    system_lock_sqls_raw = []
    autoinc_risk = False

    for s in system_lock_sessions:
        sql = str(s.get("Info", s.get("info", s.get("sql", ""))))
        if sql and sql.upper() != "NULL":
            system_lock_sqls_raw.append(sql)
            tbl = extract_table_name(sql)
            if tbl:
                hot_tables[tbl] = hot_tables.get(tbl, 0) + 1
            if is_autoinc_risk_sql(sql):
                autoinc_risk = True

    # SQL 去重
    seen = {}
    for sql in system_lock_sqls_raw:
        norm = normalize_sql(sql)
        if norm not in seen:
            seen[norm] = {"template": norm, "count": 0, "autoinc_risk": is_autoinc_risk_sql(sql)}
        seen[norm]["count"] += 1
    system_lock_sqls = list(seen.values())

    # Sleep 泄漏检测
    sleep_leak_count = 0
    for s in sleep_sessions:
        time_val = s.get("Time", s.get("time", 0))
        try:
            if int(time_val) > SLEEP_LEAK_THRESHOLD:
                sleep_leak_count += 1
        except (ValueError, TypeError):
            pass

    # 判断子类型
    sl_count = len(system_lock_sessions)
    slp_count = len(sleep_sessions)
    rl_count = len(row_lock_sessions)
    total = len(all_sessions)

    if sl_count >= 3 and sl_count > rl_count:
        subtype = "autoinc" if autoinc_risk else "system_lock_other"
    elif rl_count >= 3 and rl_count > sl_count:
        subtype = "row_lock"
    elif sleep_leak_count >= 5:
        subtype = "sleep_leak"
    elif sl_count > 0 and rl_count > 0:
        subtype = "mixed"
    else:
        subtype = "normal"

    # 热点分表排序
    hot_tables_list = sorted(hot_tables.items(), key=lambda x: -x[1])

    # 风险提示
    risks = []
    if sl_count >= 10:
        risks.append(f"🔴 System lock 严重堆积（{sl_count}条），需立即处理")
    elif sl_count >= 3:
        risks.append(f"🟠 System lock 堆积（{sl_count}条），建议检查 innodb_autoinc_lock_mode")
    elif sl_count > 0:
        risks.append(f"🟡 System lock 少量（{sl_count}条），关注趋势")

    if autoinc_risk:
        risks.append("⚠️  检测到 INSERT IGNORE / REPLACE / INSERT...SELECT，innodb_autoinc_lock_mode ≠ 2 时持表级 AUTO-INC 锁")

    if hot_tables_list:
        top_tables = ", ".join(f"{t}({c}条)" for t, c in hot_tables_list[:3])
        risks.append(f"🔥 写入热点分表：{top_tables}")

    if sleep_leak_count >= 5:
        risks.append(f"🟠 Sleep 连接泄漏：{sleep_leak_count}条 time > {SLEEP_LEAK_THRESHOLD}s，建议调低 wait_timeout")

    if rl_count >= 3:
        risks.append(f"🟠 行锁/MDL 锁等待：{rl_count}条，建议查 INNODB STATUS 找持锁 trx")

    if not risks:
        risks.append("✅ 无明显 System lock / 连接泄漏风险")

    analysis = {
        "total_active": total,
        "system_lock_count": sl_count,
        "sleep_count": slp_count,
        "row_lock_count": rl_count,
        "sleep_leak_count": sleep_leak_count,
        "subtype": subtype,
        # 当 all_sessions 为空时，subtype=normal 可能是假"正常"，需区分
        "data_warning": (
            "⚠️  all_sessions 为空，subtype=normal 不代表集群正常，"
            "可能是 API 响应结构变更或解析失败，请人工确认（查看 stderr 日志）"
        ) if not all_sessions else None,
        "autoinc_risk": autoinc_risk,
        "hot_tables": [{"table": t, "count": c} for t, c in hot_tables_list],
        "system_lock_sqls": system_lock_sqls,
        "risks": risks,
        # 子路径建议
        "recommended_subpath": {
            "autoinc": "路径 B2-AutoInc：调整 innodb_autoinc_lock_mode=2，批量写入，分表限流",
            "row_lock": "路径 B2-RowLock：SHOW ENGINE INNODB STATUS 找持锁 trx，考虑 KILL 或等待",
            "sleep_leak": "路径 B2-Leak：调低 wait_timeout，KILL 存量 Sleep 连接，排查应用连接池",
            "mixed": "路径 B2-Mixed：优先处理 System lock（autoinc），同时排查行锁持锁者",
            "normal": "连接正常，建议重新确认告警触发时的快照",
            "system_lock_other": "路径 B2：System lock 非 AUTO-INC 触发，建议人工查 INNODB STATUS",
            "unknown": "数据不足，建议人工 SHOW PROCESSLIST 确认",
        }.get(subtype, "未知子类型，需人工确认"),
    }

    return {
        "cluster": cluster,
        "node": f"{ip}:{port}",
        "_analysis": analysis,
        "raw_session_count": total,
    }


def main():
    parser = argparse.ArgumentParser(description="System lock 专项采集")
    parser.add_argument("--ip", required=True, help="主库 IP")
    parser.add_argument("--port", required=True, type=int, help="主库端口")
    parser.add_argument("--cluster", default="", help="集群名称（仅用于输出标注）")
    parser.add_argument("--output", default=None)
    parser.add_argument("--run_id", default=None)
    args = parser.parse_args()

    if not (AI_TOKEN or CLAW_TOKEN):
        print(json.dumps({"error": "DMS_AI_TOKEN 或 DMS_CLAW_TOKEN 未配置"}))
        sys.exit(1)

    result = analyze(args.ip, args.port, args.cluster)

    if args.output and args.run_id:
        raw_dir = os.path.join(args.output, args.run_id, "raw")
        os.makedirs(raw_dir, exist_ok=True)
        out_path = os.path.join(raw_dir, "get_system_lock_status.json")
        with open(out_path, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
