#!/usr/bin/env python3
"""
XRay 变更事件时间线查询脚本
查询 XRay 变更事件时间线接口（/api/change/event_timeline），支持按时间范围、系统、标签、环境、变更类型、服务等多维度过滤。

用法：
    python3 query.py --start "2026-03-23 19:00:00" --end "2026-03-23 20:00:00"
    python3 query.py --start "now-1h" --end "now"
    python3 query.py --start "now-2h" --system apollo racingweb --tag 外流推荐
    python3 query.py --start "now-1h" --service arkfeedx-1-default arkmixrank-77-default --event-type human

必填参数：
    --start         开始时间（支持 "now-1h"、"now-30m"、"2026-03-23 19:00:00"、Unix 时间戳）

可选参数：
    --end           结束时间（默认 now）
    --system        变更系统，可多选（如 apollo racingweb），默认不限制
    --tag           变更标签，可多选（如 外流推荐），默认不限制
    --custom-tag    自定义标签，可多选，默认为空
    --env           环境，可多选（默认 prod）
    --event-type    事件类型，可多选（如 human system），默认 human
    --service       服务名，可多选，默认不限制
    --experiment    实验过滤，可多选（默认 all）
    --app           应用过滤，可多选（默认 all）
    --db            数据库过滤，可多选（默认 all）
    --preplan       预案过滤，可多选（默认 all）
    --domain        域名过滤，可多选（默认 all）
    --strategy      策略过滤，可多选（默认 all）
    --index         索引过滤，可多选（默认 all）
    --model         模型过滤，可多选（默认 all）
    --job-id        任务ID过滤，可多选（默认 all）
    --other         其他过滤，可多选（默认 all）
"""

import sys
import os
import json
import re
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ────────────────────────────────────────────────
# 常量
# ────────────────────────────────────────────────
API_URL = "https://xray.devops.xiaohongshu.com/api/change/event_timeline"
TIMEOUT = 60

# .redInfo 默认路径，可通过环境变量覆盖
_WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE", str(Path.home() / ".openclaw/workspace"))
_RED_INFO  = Path(os.environ.get("RED_INFO_PATH", f"{_WORKSPACE}/.redInfo"))


def get_cookie() -> str:
    """从 .redInfo 文件读取 SSO token，构造 cookie 字符串。

    不做客户端 exp 预校验，直接使用 token。
    若 token 真正失效，API 会返回 401/403，届时再提示用户重新登录。
    """
    if not _RED_INFO.exists():
        raise RuntimeError(f"未找到登录态文件 {_RED_INFO}，请先完成 SSO 登录")
    try:
        info = json.loads(_RED_INFO.read_text())
    except Exception as e:
        raise RuntimeError(f"读取 {_RED_INFO} 失败: {e}")
    token = info.get("token")
    if not token:
        raise RuntimeError(f"{_RED_INFO} 中未找到 token，请先完成 SSO 登录")
    return f"common-internal-access-token-prod={token}"


# ────────────────────────────────────────────────
# 时间解析
# ────────────────────────────────────────────────
def parse_time(value: str) -> str:
    """解析时间字符串，返回 'YYYY-MM-DD HH:MM:SS' 格式（东八区）。"""
    value = value.strip()
    now = datetime.now(tz=timezone(timedelta(hours=8)))

    # 相对时间：now / now-Xs / now-Xm / now-Xh / now-Xd
    if value == "now":
        return now.strftime("%Y-%m-%d %H:%M:%S")
    m = re.match(r"^now-(\d+)([smhd])$", value)
    if m:
        amount, unit = int(m.group(1)), m.group(2)
        delta = timedelta(seconds=amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit])
        return (now - delta).strftime("%Y-%m-%d %H:%M:%S")

    # Unix 时间戳（秒/毫秒）
    if re.match(r"^\d{10}$", value):
        dt = datetime.fromtimestamp(int(value), tz=timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if re.match(r"^\d{13}$", value):
        dt = datetime.fromtimestamp(int(value) / 1000, tz=timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    # 标准格式
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    raise ValueError(f"无法解析时间格式: {value}")


# ────────────────────────────────────────────────
# HTTP 请求
# ────────────────────────────────────────────────
def _extract_events(obj, result: list):
    """递归提取所有变更事件节点（含 event_cn_name + start 字段的 dict）。"""
    if isinstance(obj, list):
        for item in obj:
            _extract_events(item, result)
    elif isinstance(obj, dict):
        if "event_cn_name" in obj and "start" in obj and "system_name" in obj:
            result.append(obj)
        else:
            for v in obj.values():
                _extract_events(v, result)


def do_post(url: str, payload: dict, cookie: str) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("Cookie", cookie)
    req.add_header("UserName", "codewiz")
    req.add_header("User-Agent",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")
    req.add_header("DNT", "1")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise RuntimeError(f"SSO token 已失效（HTTP {e.code}），请重新登录以刷新 {_RED_INFO}")
        raise RuntimeError(f"HTTP错误: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"请求失败: {e.reason}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"响应非 JSON: {raw[:300]}")


# ────────────────────────────────────────────────
# 参数构建
# ────────────────────────────────────────────────
def build_payload(args: argparse.Namespace, start_str: str, end_str: str) -> dict:
    # system_name 为空数组时 = 查询所有系统（接口行为）
    system_name = args.system  # [] 表示不限制系统

    service = args.service if args.service else []

    resource = {
        "service":    service,
        "experiment": args.experiment,
        "app":        args.app,
        "db":         args.db,
        "preplan":    args.preplan,
        "domain":     args.domain,
        "strategy":   args.strategy,
        "index":      args.index,
        "model":      args.model,
        "job_id":     args.job_id,
        "other":      args.other,
    }

    return {
        "start":       start_str,
        "end":         end_str,
        "system_name": system_name,
        "tag":         args.tag,
        "custom_tag":  args.custom_tag,
        "env":         args.env,
        "event_type":  args.event_type,
        "resource":    resource,
    }


# ────────────────────────────────────────────────
# 主流程
# ────────────────────────────────────────────────
def main():
    # 1. 认证
    try:
        cookie = get_cookie()
    except RuntimeError as e:
        _fail(str(e))

    # 2. 参数
    parser = argparse.ArgumentParser(description="XRay 变更事件时间线查询")
    parser.add_argument("--start",       required=True,
                        help="开始时间，如 'now-1h' / 'now-30m' / '2026-03-23 19:00:00'")
    parser.add_argument("--end",         default="now",
                        help="结束时间（默认 now）")
    parser.add_argument("--system",      nargs="*", default=[],
                        help="变更系统，可多选，如 apollo racingweb（默认不限）")
    parser.add_argument("--tag",         nargs="*", default=[],
                        help="变更标签，可多选，如 外流推荐（默认不限）")
    parser.add_argument("--custom-tag",  nargs="*", default=[],
                        dest="custom_tag",
                        help="自定义标签，可多选（默认为空）")
    parser.add_argument("--env",         nargs="*", default=["prod"],
                        help="环境，可多选（默认 prod）")
    parser.add_argument("--event-type",  nargs="*", default=["human"],
                        dest="event_type",
                        help="事件类型，可多选（默认 human）")
    parser.add_argument("--service",     nargs="*", default=[],
                        help="服务名，可多选（默认不限）")
    parser.add_argument("--experiment",  nargs="*", default=["all"])
    parser.add_argument("--app",         nargs="*", default=["all"])
    parser.add_argument("--db",          nargs="*", default=["all"])
    parser.add_argument("--preplan",     nargs="*", default=["all"])
    parser.add_argument("--domain",      nargs="*", default=["all"])
    parser.add_argument("--strategy",    nargs="*", default=["all"])
    parser.add_argument("--index",       nargs="*", default=["all"])
    parser.add_argument("--model",       nargs="*", default=["all"])
    parser.add_argument("--job-id",      nargs="*", default=["all"],
                        dest="job_id")
    parser.add_argument("--other",       nargs="*", default=["all"])
    args = parser.parse_args()

    # 3. 时间
    try:
        start_str = parse_time(args.start)
        end_str   = parse_time(args.end)
    except ValueError as e:
        _fail(str(e))

    # 4. 构建 payload
    payload = build_payload(args, start_str, end_str)

    # 5. 请求
    try:
        resp = do_post(API_URL, payload, cookie)
    except RuntimeError as e:
        _fail(str(e))

    # 6. 解析响应
    # 接口返回结构：{"code":0, "data": {"count": N, "services": [...]}}
    # services 是按服务分组的，每个 service 下有 timespan -> events 嵌套
    if isinstance(resp, list):
        # 极少数情况直接返回事件列表
        events = resp
    elif isinstance(resp, dict):
        code = resp.get("code", resp.get("status", 0))
        if code not in (0, 200, None):
            _fail(f"接口返回错误: code={code}, msg={resp.get('msg', resp.get('message', '未知'))}")
        # 接口实际返回字段可能是 "result" 或 "data"
        data = resp.get("result", resp.get("data", {}))
        if isinstance(data, list):
            # data 直接是列表
            events = data
        elif isinstance(data, dict):
            # 接口有两套返回结构：
            # 1. 指定 system 时：data.services[].timespan[].events[]
            # 2. 不指定 system 时：data.objects（嵌套结构）需递归遍历
            # 统一用递归提取所有包含 event_cn_name + start 字段的节点
            events = []
            _extract_events(data, events)
        else:
            events = []
    else:
        _fail(f"未知响应格式: {str(resp)[:200]}")

    # 7. 格式化 events：解析 info 字段，提取变更详情
    formatted_events = []
    for ev in sorted(events, key=lambda x: x.get("start", "")):
        raw_info = ev.get("info", "") or ""
        try:
            info_obj = json.loads(raw_info) if raw_info else {}
        except Exception:
            info_obj = {}

        change_object = info_obj.get("change_object", "")
        before_raw    = info_obj.get("before_value", "")
        after_raw     = info_obj.get("after_value", "")

        # info_obj 解析失败时（如 after_value 内含截断的嵌套 JSON），
        # 用正则从原始字符串中提取 change_object
        if not change_object and raw_info:
            import re as _re
            m = _re.search(r'"change_object"\s*:\s*"([^"]+)"', raw_info)
            if m:
                change_object = m.group(1)

        # after_value：从原始字符串中提取三层嵌套的真正值
        # 结构：info -> after_value(层1字符串) -> {key: 层2字符串} -> 真正dict
        if not after_raw and raw_info and change_object:
            import re as _re
            m = _re.search(r'"after_value"\s*:\s*("(?:[^"\\]|\\.)*")', raw_info)
            if m:
                try:
                    after_raw = json.loads(m.group(1))
                except Exception:
                    after_raw = ""

        def _try_parse(v):
            """尝试将字符串解析为 JSON，失败则原样返回。"""
            if not isinstance(v, str):
                return v
            try:
                return json.loads(v)
            except Exception:
                return v

        def _deep_parse(obj, depth=0):
            """递归展开对象中所有字符串值（最多4层）。"""
            if depth >= 4:
                return obj
            if isinstance(obj, dict):
                for k, v in list(obj.items()):
                    if isinstance(v, str):
                        parsed = _try_parse(v)
                        if isinstance(parsed, (dict, list)):
                            obj[k] = _deep_parse(parsed, depth + 1)
                    elif isinstance(v, (dict, list)):
                        obj[k] = _deep_parse(v, depth + 1)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, (dict, list)):
                        obj[i] = _deep_parse(item, depth + 1)
            return obj

        def _parse_nested(s):
            """将 apollo 多层嵌套 JSON 字符串完整解开为 Python 对象。"""
            if not s:
                return None
            obj = _try_parse(s)
            if isinstance(obj, (dict, list)):
                return _deep_parse(obj)
            return obj

        before_parsed = _parse_nested(before_raw)
        after_parsed  = _parse_nested(after_raw)

        # apollo 特殊处理：after_value 结构为 {change_key: 真正的值}
        # 将真正的值提升出来，丢弃外层包装
        if change_object and isinstance(after_parsed, dict) and change_object in after_parsed:
            after_parsed = after_parsed[change_object]
        if change_object and isinstance(before_parsed, dict) and change_object in before_parsed:
            before_parsed = before_parsed[change_object]

        # racingweb 实验参数变更：提取 parasChangeEvents
        paras_changes = []
        if after_parsed and isinstance(after_parsed, dict):
            pce = after_parsed.get("parasChangeEvents", [])
            if pce:
                for item in pce:
                    paras_changes.append({
                        "varId":        item.get("varId", ""),
                        "after_params": item.get("flagValueMap", {}),
                    })
        if before_parsed and isinstance(before_parsed, dict) and paras_changes:
            pce_before = before_parsed.get("parasChangeEvents", [])
            for i, item in enumerate(pce_before):
                if i < len(paras_changes):
                    paras_changes[i]["before_params"] = item.get("flagValueMap", {})

        entry = {
            "time":          ev.get("start", ""),
            "system":        ev.get("system_name", ""),
            "operator":      ev.get("operator_name", ""),
            "resource_name": ev.get("resource_name", ""),
            "action":        ev.get("event_cn_name", ""),
            "env":           ev.get("env", ""),
            "link":          ev.get("link", ""),
        }

        # apollo 变更：展示 change_object + before/after
        if change_object:
            entry["change_object"] = change_object
        if before_parsed:
            entry["before_value"] = before_parsed
        if after_parsed:
            entry["after_value"] = after_parsed

        # racingweb 实验变更：展示参数 diff
        if paras_changes:
            entry["param_changes"] = paras_changes

        # 保留原始 info 作为 fallback
        # 注意：不截断原始 info，截断会破坏 JSON 完整性导致后续解析失败
        # 改为：先尝试解析，解析成功则存 dict，解析失败才存截断字符串
        if raw_info and not change_object and not paras_changes:
            try:
                entry["info_raw"] = json.loads(raw_info)
            except Exception:
                entry["info_raw"] = raw_info[:2000]

        formatted_events.append(entry)

    # 8. 输出
    result = {
        "success": True,
        "query": {
            "start":      start_str,
            "end":        end_str,
            "system":     args.system,
            "tag":        args.tag,
            "custom_tag": args.custom_tag,
            "env":        args.env,
            "event_type": args.event_type,
            "service":    args.service,
        },
        "count":  len(formatted_events),
        "events": formatted_events,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _fail(msg: str):
    print(json.dumps({"success": False, "error": msg}, ensure_ascii=False))
    sys.exit(1)


if __name__ == "__main__":
    main()
