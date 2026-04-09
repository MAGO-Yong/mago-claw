#!/usr/bin/env python3
"""
get_active_sessions.py — 查询活跃连接与线程堆积（双路采集）

两路数据源：
  1. CK 历史快照（故障时刻）：
       POST /dms-api/ai-api/v1/mysql/session/get_his_process_count_list   ← 优先
       POST /dms-api/ai-api/v1/mysql/session/get_his_process_group_and_detail ← 优先
           → 获取 vm_name 在告警时刻前后的采集时间点列表，取距故障时刻最近的时间点，拿明细 + SQL 聚合

  2. 实时采集（当前时刻）：
       POST /dms-api/ai-api/v1/mysql/session/get_cur_process_list         ← 优先
           → 直连 MySQL 查当前活跃会话（注意：故障可能已缓解）

  各接口均自动降级到 open-claw（/dms-api/v1/mysql/session-manage/...）。

认证：优先 DMS_AI_TOKEN（ai-api/v1），兜底 DMS_CLAW_TOKEN（open-claw）

时区说明：
  fault_time 须与 CK 存储时区一致。DMS CK 存储的是北京时间（CST, UTC+8），
  因此 fault_time 应传北京时间，例如 "2026-04-01 10:00:00"（北京时间）。
  若 Agent 运行在 UTC 机器上，collect_time（datetime.now()）会是 UTC，
  与 fault_time 存在 8 小时偏差——请确保运行环境时区设置为 Asia/Shanghai，
  或在调用方做换算后再传入 fault_time。

用法：
  python3 get_active_sessions.py \
      --cluster <cluster_name> \
      --vm_name <vm_name> \
      --ip      <ip> \
      --port    <port> \
      [--fault_time "2026-04-01 10:00:00"]   # 故障时刻（北京时间），CK 快照选点依据
      [--min_time 0]                           # 实时采集：只看运行超过 N 秒的线程
      [--output <dir>] [--run_id <id>]

输出结构：
  {
    "history_snapshot": {
      "snapshot_time": "2026-04-01 10:00:00",  # CK 里实际采集到的最近时间点（完整日期时间）
      "note": "CK 历史快照，存档时刻 2026-04-01 10:00:00（故障时刻 10:00:00）",
      "connectionList": [...],                  # 原始明细列表
      "processGroupList": [...],                # SQL 指纹聚合
      "connectionCount": N
    },
    "realtime": {
      "collect_time": "2026-04-01 10:05:00",  # 实际采集时刻
      "note": "实时采集，故障可能已缓解，仅供参考",
      "connectionList": [...],
      "connectionCount": N
    },
    "_analysis": { ... }                      # 风险评估（优先基于实时数据；实时失败时降级用历史快照）
  }
"""

import argparse
import json
import sys
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

# 统一客户端（支持 DMS_AI_TOKEN 优先 + DMS_CLAW_TOKEN 兜底）
sys.path.insert(0, str(Path(__file__).parents[1]))
from common.dms_client import (
    AI_TOKEN, CLAW_TOKEN, BASE_URL, AI_V1_PREFIX,
    _AI_HEADERS, _http_post, call_with_fallback,
)

TOKEN = CLAW_TOKEN  # open-claw 兜底用

# 持锁者的典型 State
LOCK_HOLDER_STATES = {
    "updating", "deleting", "executing", "locked", "",
    "update", "delete", "insert", "replace",
}

# 系统账号，用于客户端二次过滤（当 API show_system_session=False 不生效时兜底）
SYSTEM_USERS = {"backuser", "mhauser", "root", "ro_query", "event_scheduler",
                "monitor", "repl", "system user", "tencentroot"}


def _post_old(path: str, payload: dict) -> dict:
    """open-claw 兜底 POST 封装。"""
    return _http_post(f"{BASE_URL}{path}", payload, {"dms-claw-token": TOKEN})


# ─── CK 历史快照 ──────────────────────────────────────────────────────────────

def fetch_ck_time_points(vm_name: str, fault_time: str) -> list[str]:
    """
    查询 CK 里 vm_name 在故障时刻前后 30 分钟内有数据的时间点列表。
    返回格式：["2026-04-01 09:58:00", "2026-04-01 10:00:00", ...]（北京时间字符串）

    注意：fault_time 须为北京时间，与 CK 存储时区一致。
    """
    try:
        fault_dt = datetime.strptime(fault_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise RuntimeError(f"fault_time 格式错误，期望 'YYYY-MM-DD HH:MM:SS'，实际：{fault_time}")

    start_time = (fault_dt - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    end_time = (fault_dt + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "vm_name": vm_name,
        "start_time": start_time,
        "end_time": end_time,
        "show_system_session": False,
    }
    payload_old = {
        "vm_name": vm_name,
        "start_time": start_time,
        "end_time": end_time,
        "filter": {"show_system_session": False},
    }

    result = call_with_fallback(
        lambda: _http_post(f"{AI_V1_PREFIX}/mysql/session/get_his_process_count_list", payload, _AI_HEADERS),
        lambda: _post_old("/dms-api/v1/mysql/session-manage/get-his-process-count-list", payload_old),
        "[get_active_sessions/ck_count]",
    )
    code = result.get("code", -1)
    if code != 0:
        raise RuntimeError(f"get-his-process-count-list 返回 code={code}: {result.get('message', '')}")

    data = result.get("data") or []
    # data 是 [{create_time: "...", count: N}, ...] 按时间升序
    time_points = []
    for item in data:
        ct = item.get("create_time") or item.get("createTime") or ""
        if ct:
            # 统一转成字符串格式
            time_points.append(str(ct)[:19])  # 截取到秒
    return time_points


def pick_closest_before(time_points: list[str], fault_time: str) -> str | None:
    """
    从时间点列表中，选出最接近且 <= fault_time 的那个时间点。
    若不存在 <= fault_time 的点，返回 None（由调用方决定降级策略）。
    """
    fault_dt = datetime.strptime(fault_time, "%Y-%m-%d %H:%M:%S")
    best = None
    best_dt = None
    for tp in time_points:
        try:
            tp_dt = datetime.strptime(tp[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if tp_dt <= fault_dt:
            if best_dt is None or tp_dt > best_dt:
                best = tp
                best_dt = tp_dt
    return best


def fetch_ck_snapshot(vm_name: str, select_time: str) -> dict:
    """
    用指定时间点查 CK 明细 + SQL 聚合。
    """
    payload = {"vm_name": vm_name, "select_time": select_time, "show_system_session": False}
    payload_old = {"vm_name": vm_name, "select_time": select_time, "filter": {"show_system_session": False}}

    result = call_with_fallback(
        lambda: _http_post(f"{AI_V1_PREFIX}/mysql/session/get_his_process_group_and_detail", payload, _AI_HEADERS),
        lambda: _post_old("/dms-api/v1/mysql/session-manage/get-his-process-group-and-detail-list", payload_old),
        "[get_active_sessions/ck_snapshot]",
    )
    code = result.get("code", -1)
    if code != 0:
        raise RuntimeError(f"get-his-process-group-and-detail-list 返回 code={code}: {result.get('message', '')}")
    return result.get("data") or {}


def collect_history_snapshot(vm_name: str, fault_time: str) -> dict:
    """完整的 CK 历史快照采集流程：选点 → 查明细。"""
    time_points = fetch_ck_time_points(vm_name, fault_time)
    if not time_points:
        return {
            "snapshot_time": None,
            "note": f"CK 历史快照：故障时刻 {fault_time} 前后 30 分钟内无采集数据",
            "connectionList": [],
            "processGroupList": [],
            "connectionCount": 0,
        }

    select_time = pick_closest_before(time_points, fault_time)
    if not select_time:
        # 找不到 <= fault_time 的点：所有时间点都晚于故障时刻，取最早的一个
        # 注意：该快照反映的是故障之后的状态，note 中明确标注，避免误导
        select_time = time_points[0]
        after_fault_note = True
    else:
        after_fault_note = False

    snapshot_data = fetch_ck_snapshot(vm_name, select_time)
    connection_list = snapshot_data.get("connectionList") or []
    process_group_list = snapshot_data.get("processGroupList") or []
    count = snapshot_data.get("connectionCount") or len(connection_list)

    # 保留完整日期时间，避免跨天时仅显示 HH:MM:SS 产生歧义
    snapshot_label = select_time[:19] if len(select_time) >= 19 else select_time
    fault_label = fault_time[:19]

    if after_fault_note:
        note = (
            f"CK 历史快照：未找到故障时刻前的采集点，"
            f"使用最近时间点 {snapshot_label}（晚于故障时刻 {fault_label}，数据反映故障后状态）"
        )
    else:
        note = f"CK 历史快照，存档时刻 {snapshot_label}（故障时刻 {fault_label}）"

    return {
        "snapshot_time": select_time,
        "snapshot_label": snapshot_label,
        "note": note,
        "connectionList": connection_list,
        "processGroupList": process_group_list,
        "connectionCount": count,
    }


# ─── 实时采集 ─────────────────────────────────────────────────────────────────

def fetch_realtime(ip: str, port: int) -> dict:
    """调用 get-cur-process-list 接口拿当前活跃会话。"""
    payload = {"ip": ip, "port": str(port), "show_system_session": False}
    payload_old = {"ip": ip, "port": str(port), "filter": {"show_system_session": False}}

    result = call_with_fallback(
        lambda: _http_post(f"{AI_V1_PREFIX}/mysql/session/get_cur_process_list", payload, _AI_HEADERS),
        lambda: _post_old("/dms-api/v1/mysql/session-manage/get-cur-process-list", payload_old),
        "[get_active_sessions/realtime]",
    )
    code = result.get("code", -1)
    if code != 0:
        raise RuntimeError(f"get-cur-process-list 返回 code={code}: {result.get('message', '')}")
    return result.get("data") or {}


def collect_realtime(ip: str, port: int) -> dict:
    """实时采集，标注采集时刻。"""
    collect_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = fetch_realtime(ip, port)
    connection_list = data.get("connectionList") or []
    count = data.get("connectionCount") or len(connection_list)
    return {
        "collect_time": collect_time,
        "note": f"实时采集（{collect_time}），故障可能已缓解，仅供参考",
        "connectionList": connection_list,
        "connectionCount": count,
    }


# ─── 分析（优先基于实时数据；实时失败时降级用历史快照）────────────────────────────

def _get_field(s: dict, *keys, default=None):
    for k in keys:
        if k in s:
            return s[k]
    return default


def _is_system_user(s: dict) -> bool:
    """客户端二次过滤系统账号（当 API show_system_session=False 不生效时兜底）。"""
    user = (_get_field(s, "user", "User") or "").lower()
    return user in SYSTEM_USERS


def analyze(sessions: list, min_time: int = 0) -> dict:
    """分析线程分布，识别堆积模式。兼容大小写字段名。客户端二次过滤系统账号。"""
    # 先过滤系统账号，再按 min_time 筛选
    business_sessions = [s for s in sessions if not _is_system_user(s)]
    filtered = [s for s in business_sessions
                if (_get_field(s, "time", "Time", default=0) or 0) >= min_time]
    total = len(filtered)

    def get_state(s): return (_get_field(s, "state", "State") or "").strip()
    def get_time(s): return _get_field(s, "time", "Time", default=0) or 0
    def get_command(s): return _get_field(s, "command", "Command") or ""

    state_dist = Counter(get_state(s) for s in filtered)
    long_running = [s for s in filtered if get_time(s) > 30]

    lock_holders = [
        s for s in filtered
        if get_time(s) > 10
        and get_state(s).lower() in LOCK_HOLDER_STATES
        and "Sleep" not in get_command(s)
    ]
    lock_waiters = [
        s for s in filtered
        if "lock" in get_state(s).lower() or get_state(s) == "Locked"
    ]
    relay_waiters = [
        s for s in filtered
        if "relay" in get_state(s).lower()
    ]

    risks = []
    if len(long_running) > 5:
        risks.append(f"🔴 发现 {len(long_running)} 个运行超过 30s 的线程，线程池可能趋于饱和")
    if lock_waiters:
        risks.append(f"🔴 发现 {len(lock_waiters)} 个锁等待线程，存在锁竞争")
    if relay_waiters:
        risks.append(f"🟠 发现 {len(relay_waiters)} 个 Waiting for relay log 线程，疑似主从延迟")
    if total > 50:
        risks.append(f"🟠 活跃线程总数 {total}，建议关注连接数上限")
    if not risks:
        risks.append("✅ 活跃连接无明显异常")

    return {
        "total_active": total,
        "state_distribution": dict(state_dist.most_common(10)),
        "long_running_count": len(long_running),
        "lock_holders_count": len(lock_holders),
        "lock_waiters_count": len(lock_waiters),
        "relay_waiters_count": len(relay_waiters),
        "top_long_running": sorted(long_running, key=lambda x: -get_time(x))[:5],
        "risks": risks,
    }


def analyze_from_process_group(process_group_list: list) -> dict:
    """
    实时采集失败时的降级分析：基于 history_snapshot.processGroupList 做简要风险评估。
    processGroupList 是 SQL 指纹聚合，字段与 connectionList 不同，只能做粗粒度分析。
    """
    risks = []
    if not process_group_list:
        risks.append("⚠️  实时采集失败且历史快照无 processGroupList，无法分析")
        return {"source": "history_snapshot_fallback", "risks": risks}

    total = sum(pg.get("total_num", 0) or pg.get("totalNum", 0) for pg in process_group_list)
    max_time = max(
        (pg.get("max_execute_time", 0) or pg.get("maxExecuteTime", 0) for pg in process_group_list),
        default=0,
    )

    if max_time > 30:
        risks.append(f"🔴 历史快照中最长执行时间 {max_time}s，存在慢查询（降级分析，基于 CK 历史快照）")
    if total > 50:
        risks.append(f"🟠 历史快照活跃线程聚合总数 {total}（降级分析，基于 CK 历史快照）")
    if not risks:
        risks.append("✅ 历史快照无明显异常（降级分析，实时采集失败）")

    return {
        "source": "history_snapshot_fallback",
        "total_active_approx": total,
        "max_execute_time": max_time,
        "risks": risks,
    }


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="查询活跃连接（双路：CK历史快照 + 实时采集）")
    parser.add_argument("--cluster", required=True, help="集群名称")
    parser.add_argument("--vm_name", required=True, help="节点 vm_name（主库），用于 CK 历史快照")
    parser.add_argument("--ip", required=True, help="节点 IP，用于实时采集")
    parser.add_argument("--port", type=int, required=True, help="节点 Port（整数），用于实时采集")
    parser.add_argument("--fault_time", default="", help="故障时刻（北京时间），格式 'YYYY-MM-DD HH:MM:SS'，CK快照选点依据，不传则不采集历史快照")
    parser.add_argument("--min_time", type=int, default=0, help="实时采集：只看运行超过 N 秒的线程")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    args = parser.parse_args()

    if not AI_TOKEN and not TOKEN:
        print("[get_active_sessions] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    result = {"cluster": args.cluster, "vm_name": args.vm_name}
    has_error = False

    # ── 路1：CK 历史快照 ──
    if args.fault_time:
        print(f"[get_active_sessions] 采集 CK 历史快照，故障时刻：{args.fault_time}", file=sys.stderr)
        try:
            history = collect_history_snapshot(args.vm_name, args.fault_time)
            result["history_snapshot"] = history
            print(f"  CK快照时间点    : {history.get('snapshot_time', '无数据')}", file=sys.stderr)
            print(f"  CK快照连接数    : {history.get('connectionCount', 0)}", file=sys.stderr)
        except RuntimeError as e:
            print(f"[get_active_sessions] ⚠️  CK历史快照采集失败：{e}", file=sys.stderr)
            result["history_snapshot"] = {
                "snapshot_time": None,
                "note": f"CK历史快照采集失败：{e}",
                "connectionList": [],
                "processGroupList": [],
                "connectionCount": 0,
            }
            has_error = True
    else:
        result["history_snapshot"] = {
            "snapshot_time": None,
            "note": "未传 fault_time，跳过 CK 历史快照采集",
            "connectionList": [],
            "processGroupList": [],
            "connectionCount": 0,
        }

    # ── 路2：实时采集 ──
    print(f"[get_active_sessions] 采集实时会话，{args.ip}:{args.port}", file=sys.stderr)
    try:
        realtime = collect_realtime(args.ip, args.port)
        result["realtime"] = realtime
        analysis = analyze(realtime["connectionList"], args.min_time)
        result["_analysis"] = analysis

        print(f"  采集时刻         : {realtime['collect_time']}", file=sys.stderr)
        print(f"  活跃线程总数     : {analysis['total_active']}", file=sys.stderr)
        print(f"  运行 >30s 线程   : {analysis['long_running_count']}", file=sys.stderr)
        print(f"  锁等待线程       : {analysis['lock_waiters_count']}", file=sys.stderr)
        print(f"  持锁者（写操作） : {analysis['lock_holders_count']}", file=sys.stderr)
        print(f"  relay log 等待   : {analysis['relay_waiters_count']}", file=sys.stderr)
        print(f"  State 分布       : {analysis['state_distribution']}", file=sys.stderr)
        print("  风险评估：", file=sys.stderr)
        for r in analysis["risks"]:
            print(f"    {r}", file=sys.stderr)
    except RuntimeError as e:
        print(f"[get_active_sessions] ⚠️  实时采集失败：{e}", file=sys.stderr)
        result["realtime"] = {
            "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": f"实时采集失败：{e}",
            "connectionList": [],
            "connectionCount": 0,
        }
        # 降级：基于历史快照做粗粒度分析
        history_pg = result.get("history_snapshot", {}).get("processGroupList") or []
        result["_analysis"] = analyze_from_process_group(history_pg)
        has_error = True

    output_str = json.dumps(result, ensure_ascii=False, indent=2, default=str)

    if args.output and args.run_id:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        out_file = raw_dir / "get_active_sessions.json"
        out_file.write_text(output_str, encoding="utf-8")
        print(f"[get_active_sessions] ✅ 已写入 {out_file}", file=sys.stderr)

    print(output_str)
    sys.exit(1 if has_error else 0)


if __name__ == "__main__":
    main()
