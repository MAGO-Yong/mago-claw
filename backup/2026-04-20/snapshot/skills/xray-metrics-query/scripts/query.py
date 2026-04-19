#!/usr/bin/env python3
"""
XRay 指标查询脚本 - 查询 Prometheus/VictoriaMetrics 指标数据

用法:
    python3 query.py '<JSON参数>'

参数说明（JSON格式）:
    promql       string   Prometheus 查询语句 (PromQL)
    datasource   string   数据源名称（如 vms-infra, vms-recommend）
    start_time   string   开始时间（相对时间/时间戳/ISO格式）
    end_time     string   结束时间/查询时间点
    instant      bool     查询类型：true=即时查询，false=范围查询（默认false）

示例:
    python3 query.py '{"promql":"up","datasource":"vms-infra","start_time":"now-1h","end_time":"now"}'

输出: JSON 到 stdout
    成功: {"success": true, "query_type": "range", "data": {...}}
    失败: {"success": false, "error": "错误信息"}
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    import httpx
except ImportError:
    print(json.dumps({
        "success": False,
        "error": "缺少依赖",
        "detail": "请安装 httpx: pip3 install httpx"
    }, ensure_ascii=False))
    sys.exit(1)


# XRay API 配置
XRAY_API_URL_INSTANT = "https://xray.devops.xiaohongshu.com/api/application/metric/explore/query"
XRAY_API_URL_RANGE = "https://xray.devops.xiaohongshu.com/api/application/metric/explore/query_range"

# .redInfo 默认路径，可通过环境变量覆盖
_WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE", str(Path.home() / ".openclaw/workspace"))
_RED_INFO  = Path(os.environ.get("RED_INFO_PATH", f"{_WORKSPACE}/.redInfo"))


def get_cookies() -> str:
    """从 .redInfo 文件读取 SSO token，构造 cookie 字符串。

    不做客户端 exp 预校验，直接使用 token。
    若 token 真正失效，API 会返回 401/403，届时再提示用户重新登录。
    （本地 exp 字段有时滞，提前校验可能误判仍有效的 token 为过期）
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


def parse_time(time_str: str) -> int:
    """将时间字符串转换为时间戳（毫秒）"""
    # 相对时间: now, now-1h, now-30m, now-1d
    if time_str == "now":
        return int(datetime.now().timestamp() * 1000)
    
    if time_str.startswith("now-"):
        match = re.match(r"now-(\d+)([smhd])", time_str)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            current_ts = int(datetime.now().timestamp() * 1000)
            
            multipliers = {
                "s": 1000,
                "m": 60 * 1000,
                "h": 3600 * 1000,
                "d": 86400 * 1000
            }
            return current_ts - value * multipliers.get(unit, 0)
    
    # 时间戳（秒或毫秒）
    try:
        ts = int(time_str)
        # 如果是秒级时间戳（小于10位数），转换为毫秒
        if ts < 10000000000:
            ts *= 1000
        return ts
    except ValueError:
        pass
    
    # ISO 格式或标准日期时间格式
    try:
        # 处理 ISO 8601 格式
        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        return int(dt.timestamp() * 1000)
    except ValueError:
        pass
    
    # 默认返回当前时间
    return int(datetime.now().timestamp() * 1000)


def format_metric_result(data: dict, is_instant: bool = False) -> str:
    """格式化指标查询结果为可读文本"""
    if not data or data.get("status") != "success":
        return "查询返回空数据或状态异常"
    
    result_data = data.get("data", {})
    result_type = result_data.get("resultType", "")
    results = result_data.get("result", [])
    
    if not results:
        return "查询结果为空"
    
    lines = [f"结果类型: {result_type}", f"结果数量: {len(results)} 条", ""]
    
    for idx, item in enumerate(results, 1):
        metric = item.get("metric", {})
        
        # 格式化标签
        labels = ", ".join(f"{k}={v}" for k, v in metric.items())
        lines.append(f"[{idx}] {{{labels}}}")
        
        if is_instant or result_type == "vector":
            # 即时查询结果
            value = item.get("value", [])
            if len(value) == 2:
                timestamp, val = value
                dt = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"    时间: {dt}")
                lines.append(f"    值: {val}")
        else:
            # 范围查询结果
            values = item.get("values", [])
            if values:
                lines.append(f"    数据点数: {len(values)}")
                # 显示前3个和最后1个数据点
                sample_count = min(3, len(values))
                for i in range(sample_count):
                    timestamp, val = values[i]
                    dt = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    lines.append(f"    [{i+1}] {dt}: {val}")
                
                if len(values) > sample_count:
                    lines.append(f"    ... (共 {len(values)} 个数据点)")
                    # 显示最后一个
                    timestamp, val = values[-1]
                    dt = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    lines.append(f"    [最后] {dt}: {val}")
        
        lines.append("")
    
    return "\n".join(lines)


def query_xray_metrics(
    promql: str,
    datasource: str,
    start_time: str,
    end_time: str,
    instant: bool = False
) -> dict:
    """查询 XRay 指标数据"""
    
    # 获取认证信息
    try:
        cookies = get_cookies()
    except RuntimeError as e:
        return {
            "success": False,
            "error": "认证配置错误",
            "detail": str(e)
        }
    
    # 转换时间参数
    end_timestamp = parse_time(end_time)
    start_timestamp = parse_time(start_time)
    
    # 构建请求头
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "origin": "https://xray.devops.xiaohongshu.com",
        "referer": "https://xray.devops.xiaohongshu.com/metric/explore",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "cookie": cookies
    }
    
    # 根据查询类型选择 API 端点和构建请求体
    if instant:
        api_url = XRAY_API_URL_INSTANT
        payload = {
            "pql": promql,
            "datasource": datasource,
            "time": end_timestamp,
            "type": 0
        }
    else:
        api_url = XRAY_API_URL_RANGE
        payload = {
            "pql": promql,
            "datasource": datasource,
            "start": int(start_timestamp / 1000),
            "end": int(end_timestamp / 1000),
            "type": 0
        }
    
    # 发送请求
    try:
        with httpx.Client(timeout=30.0, verify=False) as client:
            response = client.post(
                api_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # 格式化输出
            formatted_text = format_metric_result(result, is_instant=instant)
            
            return {
                "success": True,
                "query_type": "instant" if instant else "range",
                "query": {
                    "promql": promql,
                    "datasource": datasource,
                    "start_time": start_time,
                    "end_time": end_time,
                    "start_timestamp": start_timestamp,
                    "end_timestamp": end_timestamp
                },
                "data": result,
                "formatted": formatted_text
            }
    
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code in (401, 403):
            return {
                "success": False,
                "error": f"SSO token 已失效（HTTP {status_code}），请重新登录以刷新 {_RED_INFO}",
            }
        return {
            "success": False,
            "error": f"HTTP错误: {status_code}",
            "detail": e.response.text if hasattr(e.response, 'text') else str(e)
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "请求超时",
            "detail": "XRay API 响应超时，请稍后重试或缩小查询时间范围"
        }
    except Exception as e:
        return {
            "success": False,
            "error": "查询失败",
            "detail": str(e)
        }


def main():
    # 解析命令行参数
    if len(sys.argv) < 2:
        print(json.dumps({
            "success": False,
            "error": "缺少参数",
            "detail": "用法: python3 query.py '<JSON参数>'"
        }, ensure_ascii=False))
        sys.exit(1)
    
    try:
        params = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({
            "success": False,
            "error": "参数解析失败",
            "detail": str(e)
        }, ensure_ascii=False))
        sys.exit(1)
    
    # 验证必填参数
    required_params = ["promql", "datasource", "start_time", "end_time"]
    missing = [p for p in required_params if p not in params]
    if missing:
        print(json.dumps({
            "success": False,
            "error": "缺少必填参数",
            "detail": f"缺少: {', '.join(missing)}"
        }, ensure_ascii=False))
        sys.exit(1)
    
    # 执行查询
    result = query_xray_metrics(
        promql=params["promql"],
        datasource=params["datasource"],
        start_time=params["start_time"],
        end_time=params["end_time"],
        instant=params.get("instant", False)
    )
    
    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
