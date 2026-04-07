#!/usr/bin/env python3
"""
索引切换状态检查工具

用法:
  python3 check_switch.py <dataSourceName> [tableName]

示例:
  python3 check_switch.py dssm_beauty_recall
  python3 check_switch.py dssm_beauty_recall dssm_beauty_recall_v2
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

API_BASE  = "https://autobots.devops.xiaohongshu.com"
CST       = timezone(timedelta(hours=8))
SEP       = "─" * 60
SEP2      = "┄" * 60

# .redInfo 默认路径，可通过环境变量覆盖
_WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE", str(Path.home() / ".openclaw/workspace"))
_RED_INFO  = Path(os.environ.get("RED_INFO_PATH", f"{_WORKSPACE}/.redInfo"))


# ── HTTP ──────────────────────────────────────────────

def get_cookie() -> str:
    """直接从 .redInfo 读取 SSO token，无需 subprocess / shell=True。"""
    if not _RED_INFO.exists():
        raise RuntimeError(f"未找到登录态文件 {_RED_INFO}，请先完成 SSO 登录")
    try:
        info = json.loads(_RED_INFO.read_text())
    except Exception as e:
        raise RuntimeError(f"读取 {_RED_INFO} 失败: {e}")
    token = info.get("token")
    exp   = info.get("exp", 0)
    if not token:
        raise RuntimeError(f"{_RED_INFO} 中未找到 token，请重新登录")
    if exp and time.time() * 1000 > exp:
        raise RuntimeError(f"SSO token 已过期（exp={exp}），请重新登录")
    return f"common-internal-access-token-prod={token}"


def curl_get(url: str, cookie: str) -> dict:
    r = subprocess.run(["curl", "-s", "-b", cookie, url],
                       capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout)


# ── 时间工具 ───────────────────────────────────────────

def parse_cst(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=CST)
        except ValueError:
            continue
    return None


def vid_to_time(version: str) -> datetime | None:
    """versionId（取 # 前部分）本身是秒级时间戳"""
    try:
        ts = int(version.split("#")[0])
        return datetime.fromtimestamp(ts, tz=CST)
    except (ValueError, IndexError):
        return None


def vid_only(version: str) -> str:
    """只取 versionId 部分，去掉 #incVersionId"""
    return version.split("#")[0]


def hours_between(t1: datetime | None, t2: datetime | None) -> float | None:
    if t1 is None or t2 is None:
        return None
    return (t1 - t2).total_seconds() / 3600


def fmt_hours(h: float | None) -> str:
    if h is None:
        return "N/A"
    return f"{h:.1f}h"


def fmt_time(t: datetime | None) -> str:
    return t.strftime("%Y-%m-%d %H:%M:%S") if t else "N/A"


# ── 数据版本（build/version/info）────────────────────

def fetch_data_versions(ds_name: str, cookie: str) -> list:
    url = f"{API_BASE}/api/build/version/info?dataSourceName={ds_name}"
    return curl_get(url, cookie).get("data", [])


def get_data_version_info(versions: list) -> tuple[str, datetime | None, timedelta | None]:
    """
    返回:
      latest_version  最新数据版本字符串 (YYYYMMDDHHmmss)
      latest_time     版本号解析的时间
      interval        相邻版本平均间隔
    """
    records = []
    for v in versions:
        if not v.get("isDone"):
            continue
        t = parse_cst(v.get("version", ""))
        if t:
            records.append((v["version"], t))
    if not records:
        return "", None, None
    latest_version, latest_time = records[0]
    if len(records) >= 2:
        diffs = [(records[i][1] - records[i+1][1]) for i in range(min(4, len(records)-1))]
        interval = sum(diffs, timedelta()) / len(diffs)
    else:
        interval = None
    return latest_version, latest_time, interval


# ── 构建版本（index/history/v2）──────────────────────

def fetch_build_history(ds_name: str, table_name: str, cookie: str) -> list:
    url = f"{API_BASE}/api/index/history/v2?dataSourceName={ds_name}&tableName={table_name}"
    return curl_get(url, cookie).get("data", [])


def get_build_info(history: list) -> tuple[str, str, datetime | None, dict]:
    """
    返回:
      build_version      最新构建版本 versionId#incVersionId
      build_data_ver     该构建对应的数据版本 (sourceData)
      build_time         构建完成时间 (CST)
      vid_to_source_map  versionId(str) -> sourceData 时间，供 zone 反查
    """
    if not history:
        return "", "", None, {}
    item  = history[0]
    infos = item.get("incIndexInfos") or []
    # 外层 incVersionId 是全量标记(-1)，真正最新版本在 incIndexInfos[0].incVersionId
    latest_inc = infos[0]["incVersionId"] if infos else item["incVersionId"]
    build_version  = f"{item['versionId']}#{latest_inc}"
    build_data_ver = infos[0].get("sourceData", "") if infos else item.get("sourceData", "")
    build_time     = parse_cst(infos[0].get("createTime", "")) if infos else None

    # versionId -> sourceData 时间（只保留第一条，通常是全量版本）
    vid_to_source_map = {}
    for h in history:
        vid = str(h["versionId"])
        sd  = h.get("sourceData", "")
        if sd and vid not in vid_to_source_map:
            vid_to_source_map[vid] = parse_cst(sd)

    return build_version, build_data_ver, build_time, vid_to_source_map


# ── 部署列表（deployment/list）───────────────────────

def fetch_deployments(ds_name: str, table_name: str, cookie: str) -> list:
    url = f"{API_BASE}/api/data/table/deployment/list?dataSourceName={ds_name}&tableName={table_name}"
    return curl_get(url, cookie).get("data", [])


# ── 全局告警（Step 0 + Step C）───────────────────────

def check_global(latest_data_ver: str, latest_data_time: datetime | None,
                 build_data_ver: str, gap: timedelta, now: datetime) -> list:
    alerts = []
    gap_h  = gap.total_seconds() / 3600

    # Step 0: 上游数据版本停止更新
    data_age_h = hours_between(now, latest_data_time)
    if data_age_h is not None and data_age_h > gap_h:
        alerts.append({
            "type": "data_stale",
            "msg":  f"上游数据停止更新：最新数据版本({latest_data_ver}) 距今 {data_age_h:.1f}h（阈值 {gap_h:.1f}h）",
        })

    # Step C: 索引构建延迟（最新数据 vs 最新构建使用的数据）
    build_data_time  = parse_cst(build_data_ver)
    data_to_build_h  = hours_between(latest_data_time, build_data_time)
    if data_to_build_h is not None and data_to_build_h > gap_h:
        alerts.append({
            "type": "build_stale",
            "msg":  f"索引构建延迟：最新数据版本({latest_data_ver}) 领先最新构建数据版本({build_data_ver}) {data_to_build_h:.1f}h（阈值 {gap_h:.1f}h）",
        })

    return alerts


# ── zone 级分析（Step A + B + D）─────────────────────

def analyze_zone(item: dict,
                 build_version: str, build_data_ver: str,
                 vid_to_source_map: dict,
                 gap: timedelta, now: datetime) -> dict:
    unit     = item.get("unit", "unknown")
    cur_vid  = item.get("currentVersion", "")
    tgt_vid  = item.get("targetVersion", "")
    progress = item.get("progress", "")
    start_t  = parse_cst(item.get("startSwitchTime", ""))
    gap_h    = gap.total_seconds() / 3600
    alerts   = []

    # 全量 versionId 和增量 incVersionId（整数）
    tgt_full_vid   = int(vid_only(tgt_vid))   if tgt_vid   else 0
    tgt_inc_vid    = int(tgt_vid.split("#")[1])   if "#" in tgt_vid   else -1
    cur_full_vid   = int(vid_only(cur_vid))   if cur_vid   else 0
    cur_inc_vid    = int(cur_vid.split("#")[1])   if "#" in cur_vid   else -1
    build_full_vid = int(vid_only(build_version)) if build_version else 0
    build_inc_vid  = int(build_version.split("#")[1]) if "#" in build_version else -1

    # 全量版本时间（只用 versionId 转时间戳，不用 sourceData）
    cur_time   = vid_to_time(cur_vid)
    tgt_time   = vid_to_time(tgt_vid)
    build_time_vid = datetime.fromtimestamp(build_full_vid, tz=CST)

    # Step A: tgt 是否落后于 build（全量版本落后，或同全量但增量落后）
    if tgt_full_vid < build_full_vid or (tgt_full_vid == build_full_vid and tgt_inc_vid < build_inc_vid):

        # Step B: 构建下发延迟
        build_to_tgt_h = hours_between(build_time_vid, tgt_time)  # 全量版本时间差（同全量时为0）
        inc_diff = build_inc_vid - tgt_inc_vid if tgt_full_vid == build_full_vid else None
        # 跨全量：用时间差判断；同全量：只要 inc 落后就告警
        is_delayed = (inc_diff is not None and inc_diff > 0) or (build_to_tgt_h is not None and build_to_tgt_h > gap_h)
        if is_delayed:
            if inc_diff is not None:
                # 同全量版本，只差增量
                msg = f"构建下发延迟：build({build_version}) 领先 target({tgt_vid}) {inc_diff} 个增量版本"
            else:
                # 跨全量版本
                msg = f"构建下发延迟：build({build_version}) 领先 target({tgt_vid}) {build_to_tgt_h:.1f}h（阈值 {gap_h:.1f}h）"
            alerts.append({"type": "build_delay", "msg": msg})

    # Step D: 切换进度（zone 级）
    prog_done, prog_total = 0, 0
    if "/" in str(progress):
        try:
            prog_done, prog_total = map(int, str(progress).split("/"))
        except ValueError:
            pass
    switching = (cur_vid != tgt_vid) or (prog_total > 0 and prog_done < prog_total)
    switch_elapsed = None
    if switching and start_t:
        switch_elapsed = now - start_t
        if switch_elapsed > gap:
            alerts.append({
                "type": "switch_stuck",
                "msg":  f"切换卡住：已耗时 {switch_elapsed.total_seconds()/60:.0f} 分钟（阈值 {gap_h*60:.0f} 分钟）",
            })

    # ── 始终输出的 gap 明细（只用全量版本时间）──
    cur_to_now_h = hours_between(now, cur_time)

    # build 领先 cur：全量时间差 + 增量序号差
    build_ahead_cur_h   = hours_between(build_time_vid, cur_time)
    build_ahead_cur_inc = (build_inc_vid - cur_inc_vid) if cur_full_vid == build_full_vid else None

    # build 领先 tgt：全量时间差 + 增量序号差
    build_ahead_tgt_h   = hours_between(build_time_vid, tgt_time)
    build_ahead_tgt_inc = (build_inc_vid - tgt_inc_vid) if tgt_full_vid == build_full_vid else None

    return {
        "unit":               unit,
        "cur_vid":            cur_vid,
        "tgt_vid":            tgt_vid,
        "build_ver":          build_version,
        "build_data_ver":     build_data_ver,
        "progress":           progress,
        "switching":          switching,
        "switch_elapsed":     switch_elapsed,
        "start_t":            item.get("startSwitchTime", ""),
        "finish_t":           item.get("finishSwitchTime", ""),
        "cur_to_now_h":       cur_to_now_h,
        "build_ahead_cur_h":  build_ahead_cur_h,
        "build_ahead_cur_inc": build_ahead_cur_inc,
        "build_ahead_tgt_h":  build_ahead_tgt_h,
        "build_ahead_tgt_inc": build_ahead_tgt_inc,
        "alerts":             alerts,
    }


# ── 输出 ──────────────────────────────────────────────

def fmt_switch_status(z: dict) -> str:
    """返回 zone 切换状态文字，不含主观判断。"""
    if z["switching"]:
        elapsed = f"{z['switch_elapsed'].total_seconds()/60:.0f}min" if z["switch_elapsed"] else "未知"
        return f"切换中  progress={z['progress']}  耗时={elapsed}"
    return "已完成"


def format_output(ds_name: str,
                  latest_data_ver: str, latest_data_time: datetime | None,
                  build_version: str, build_data_ver: str, build_time: datetime | None,
                  interval: timedelta | None, gap: timedelta,
                  global_alerts: list, zones: list, now: datetime) -> str:
    lines = []
    gap_h = gap.total_seconds() / 3600

    g_types   = {a["type"] for a in global_alerts}
    z_types   = {a["type"] for z in zones for a in z["alerts"]}
    all_types = g_types | z_types

    # ══════════════════════════════════════════════════
    # 上层：通用信息（纯客观，无判断）
    # ══════════════════════════════════════════════════
    lines.append(SEP)
    lines.append(f"  【基本信息】")
    lines.append(f"  索引表:         {ds_name}")
    lines.append(f"  检查时间:       {fmt_time(now)} (CST)")
    lines.append(SEP2)
    lines.append(f"  最新构建版本:   {build_version}")
    lines.append(f"  构建对应数据:   {build_data_ver}  (构建完成 {fmt_time(build_time)})")
    lines.append(f"  上游最新数据:   {latest_data_ver}  (版本时间 {fmt_time(latest_data_time)})")
    lines.append(SEP)

    # ══════════════════════════════════════════════════
    # 中层：每个 zone 的切换明细（纯客观，无判断）
    # ══════════════════════════════════════════════════
    lines.append(f"  【Zone 切换明细】（共 {len(zones)} 个 zone）")
    lines.append("")
    col_w = max(len(z["unit"]) for z in zones) + 2
    lines.append(f"  {'zone':<{col_w}}  {'当前版本':<22}  {'目标版本':<22}  {'切换状态'}")
    lines.append(f"  {'-'*col_w}  {'-'*22}  {'-'*22}  {'-'*30}")
    for z in zones:
        cur = z["cur_vid"] or "—"
        tgt = z["tgt_vid"] or "—"
        status = fmt_switch_status(z)
        lines.append(f"  {z['unit']:<{col_w}}  {cur:<22}  {tgt:<22}  {status}")
    lines.append(SEP)

    # ══════════════════════════════════════════════════
    # 下层：结论与建议
    # ══════════════════════════════════════════════════
    lines.append(f"  【结论与建议】")
    lines.append("")

    if not all_types:
        lines.append("  ✅ 一切正常，无异常。")
    else:
        if "data_stale" in all_types:
            a = next(x for x in global_alerts if x["type"] == "data_stale")
            lines.append(f"  ⚠️  上游数据停止更新")
            lines.append(f"      {a['msg']}")
            lines.append(f"      建议：检查上游数据产出任务是否正常运行。")
            lines.append("")
        if "build_stale" in all_types:
            a = next(x for x in global_alerts if x["type"] == "build_stale")
            lines.append(f"  ⚠️  索引构建延迟")
            lines.append(f"      {a['msg']}")
            lines.append(f"      建议：检查索引构建任务是否正常运行。")
            lines.append("")
        if "build_delay" in all_types:
            bd_zones = [z for z in zones if any(a["type"] == "build_delay" for a in z["alerts"])]
            lines.append(f"  ⚠️  构建下发延迟（zone: {', '.join(z['unit'] for z in bd_zones)}）")
            for z in bd_zones:
                a = next(x for x in z["alerts"] if x["type"] == "build_delay")
                lines.append(f"      [{z['unit']}] {a['msg']}")
            lines.append(f"      建议：检查调度/下发流程是否正常。")
            lines.append("")
        if "switch_stuck" in all_types:
            sk_zones = [z for z in zones if any(a["type"] == "switch_stuck" for a in z["alerts"])]
            lines.append(f"  🔴 切换卡住（zone: {', '.join(z['unit'] for z in sk_zones)}）")
            for z in sk_zones:
                a = next(x for x in z["alerts"] if x["type"] == "switch_stuck")
                lines.append(f"      [{z['unit']}] {a['msg']}")
            lines.append(f"      建议：检查对应服务的 shard 加载状态。")
            lines.append("")

    lines.append(SEP)
    return "\n".join(lines)


# ── 接口错误提示 ──────────────────────────────────────

def api_error(ds_name: str, api_name: str, detail: str, suggestion: str):
    print(f"❌ 接口查询失败：{api_name}")
    print(f"   表名:     {ds_name}")
    print(f"   原因:     {detail}")
    print(f"   建议:     {suggestion}")
    sys.exit(1)


# ── main ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ds_name    = sys.argv[1]
    table_name = sys.argv[2] if len(sys.argv) > 2 else ds_name
    now        = datetime.now(CST)
    cookie     = get_cookie()

    # 1. 数据版本 → 推算 GAP
    data_versions = fetch_data_versions(ds_name, cookie)
    if not data_versions:
        api_error(ds_name, "build/version/info",
                  "未返回数据版本记录，dataSourceName 可能不存在或尚未有数据产出。",
                  "确认 dataSourceName 是否正确；若表名与 dataSourceName 不同，请手动传入 tableName。")
    latest_data_ver, latest_data_time, interval = get_data_version_info(data_versions)
    gap = interval * 2 if interval else timedelta(hours=2)

    # 2. 构建版本
    history = fetch_build_history(ds_name, table_name, cookie)
    if not history:
        api_error(ds_name, "index/history/v2",
                  "未返回构建历史记录，表可能尚未触发过构建，或 tableName 与 dataSourceName 不匹配。",
                  "确认 tableName 是否正确；可尝试 `python3 check_switch.py <dataSourceName> <tableName>` 分开传入。")
    build_version, build_data_ver, build_time, vid_to_source_map = get_build_info(history)

    # 3. 部署列表
    deployments = fetch_deployments(ds_name, table_name, cookie)
    if not deployments:
        api_error(ds_name, "data/table/deployment/list",
                  "未返回部署信息，表可能尚未部署到任何 zone，或 tableName 不正确。",
                  "确认 tableName 是否正确；若表刚上线，可能尚未有 zone 部署记录。")

    # 4. 全局告警（Step 0 + C，只算一次）
    global_alerts = check_global(latest_data_ver, latest_data_time, build_data_ver, gap, now)

    # 5. zone 级分析（Step A + B + D）
    zones = [
        analyze_zone(d, build_version, build_data_ver, vid_to_source_map, gap, now)
        for d in deployments
    ]

    # 6. 输出
    print(format_output(ds_name, latest_data_ver, latest_data_time,
                        build_version, build_data_ver, build_time,
                        interval, gap, global_alerts, zones, now))


if __name__ == "__main__":
    main()
