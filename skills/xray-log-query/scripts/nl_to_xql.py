#!/usr/bin/env python3
"""
自然语言 → Xray XQL 查询语句转换脚本
用途：将用户的自然语言描述转换为符合 Xray application 表约束的 XQL 查询参数，
      输出 JSON，供后续脚本（validate_query.py / query_charts.py / query_logs.py）直接使用。

XQL 语法规则（来源：Redoc 文档《日志查询语法》）：
  - 键值检索：field:value（精确匹配，性能最高）
  - 短语检索：field:"value"（包含该 token）
  - 模糊检索：field:"*value*"（通配符，性能较差）
  - 数值检索：field:>400、field:>=200
  - 多值检索：field:v1,v2（等同于 OR）
  - 逻辑组合：AND / OR / NOT / ()
  - 结构化字段：ext.uid:12345
  - 管道分析：query | SELECT ...（本脚本仅生成检索部分，不生成 SELECT）

application 表约束（服务端强制，来源：内部项目校验代码）：
  - query 必须含 subApplication / xrayTraceId / _pod_name_ /
    traceId / ID / catMsgId / catRootId / userId 之一

转换策略（基于规则匹配 + LLM，无需网络即可运行基础规则模式）：

  模式 A（规则模式，无需 LLM）：
    从自然语言中识别常见模式并直接映射：
      "xxx 服务"           → subApplication:xxx
      "error/错误"         → level:error
      "warn/告警"          → level:warn
      "traceId:xxx"        → xrayTraceId:xxx
      "pod xxx"            → _pod_name_:xxx
      "userId/uid xxx"     → ext.uid:xxx
      "关键词 xxx"         → msg:"xxx"
      "最近 N 分钟/小时"   → st/et 时间范围

  模式 B（LLM 模式，需配置 API Key）：
    当规则模式置信度不足时，调用大模型生成精确 XQL。
    通过环境变量或 --llm-api-key 参数配置。

用法：
  # 规则模式（默认）
  python nl_to_xql.py --text "查一下 my-service 最近 1 小时的 error 日志"

  # LLM 模式
  python nl_to_xql.py --text "..." --llm-api-key sk-xxx [--llm-base-url https://...]

  # 管道用法（直接传给下游脚本）
  python nl_to_xql.py --text "my-service 最近 error" | \\
    python -c "import json,sys; p=json.load(sys.stdin); \\
      print(p['query'], p['st'], p['et'])"

输出 JSON 格式：
  {
    "query": "subApplication:my-service AND level:error",
    "st": 1700000000,
    "et": 1700003600,
    "search_trace_app": false,
    "mode": "rule",          // rule | llm
    "confidence": "high",    // high | medium | low
    "explanation": "识别到服务名 my-service，时间范围最近 1 小时，日志级别 error"
  }
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from typing import Optional, Tuple


# ── 时间解析 ──────────────────────────────────────────────────────────────────

_TIME_PATTERNS = [
    # 最近 N 分钟
    (re.compile(r"最近\s*(\d+)\s*分钟"), lambda m: int(m.group(1)) * 60),
    # 最近 N 小时
    (re.compile(r"最近\s*(\d+)\s*(小时|h|hour)"), lambda m: int(m.group(1)) * 3600),
    # 最近 N 天
    (re.compile(r"最近\s*(\d+)\s*(天|d|day)"), lambda m: int(m.group(1)) * 86400),
    # last N minutes
    (re.compile(r"last\s+(\d+)\s*min", re.I), lambda m: int(m.group(1)) * 60),
    # last N hours
    (re.compile(r"last\s+(\d+)\s*h", re.I), lambda m: int(m.group(1)) * 3600),
    # past N hours / past N minutes
    (re.compile(r"past\s+(\d+)\s*hour", re.I), lambda m: int(m.group(1)) * 3600),
    (re.compile(r"past\s+(\d+)\s*min", re.I), lambda m: int(m.group(1)) * 60),
    # 1h / 30m 简写
    (re.compile(r"\b(\d+)\s*h\b", re.I), lambda m: int(m.group(1)) * 3600),
    (re.compile(r"\b(\d+)\s*m\b"), lambda m: int(m.group(1)) * 60),
]

_DEFAULT_RANGE_SECONDS = 3600  # 未识别时间时默认最近 1 小时


def _parse_time_range(text: str) -> Tuple[int, int]:
    """从自然语言中提取时间范围，返回 (st, et) Unix 秒。"""
    now = int(time.time())
    for pattern, calc in _TIME_PATTERNS:
        m = pattern.search(text)
        if m:
            seconds = calc(m)
            return now - seconds, now
    return now - _DEFAULT_RANGE_SECONDS, now


# ── 字段识别 ──────────────────────────────────────────────────────────────────

_LEVEL_MAP = {
    "error": "error",
    "错误": "error",
    "err": "error",
    "warn": "warn",
    "warning": "warn",
    "告警": "warn",
    "info": "info",
    "信息": "info",
    "debug": "debug",
    "调试": "debug",
}

_TRACE_ID_RE = re.compile(r"\b([0-9a-fA-F]{32})\b")
_TRACE_FIELD_RE = re.compile(
    r"(?:xrayTraceId|traceId|trace[_\s]?id)\s*[=:]\s*([0-9a-fA-F]{32})", re.I
)
_POD_RE = re.compile(r"(?:pod|_pod_name_)\s*[=:]?\s*([\w\-]+)", re.I)
_UID_RE = re.compile(r"(?:userId|uid|用户[Ii][Dd]?)\s*[=:]\s*(\d+)", re.I)
_MSG_KEYWORD_RE = re.compile(
    r'(?:关键词|keyword|包含|msg|message)\s*[=:]?\s*["\']?([^\s"\'，,]+)["\']?', re.I
)
# 通过显式前缀关键字匹配服务名（精确模式）
_SERVICE_RE = re.compile(r"(?:subApplication|app)\s*[=:]\s*([\w\-\.]+)", re.I)
# "xxx 服务" 后缀模式：xxx 必须看起来像服务名（含连字符/点，且不是纯中文时间词）
_SERVICE_SUFFIX_RE = re.compile(r"([\w][\w\-\.]*[\w])\s*(?:服务|service)")
# 句首或空白后紧跟着的英文服务名（形如 my-service、user.center 等，至少含一个连字符或点）
_SERVICE_PLAIN_RE = re.compile(r"(?:^|[\s，,。！!？?])([\w][\w]*[-\.][\w][\w\-\.]*)")
# 需要从服务名候选中排除的时间/停用词
_SERVICE_STOPWORDS = {
    "最近",
    "最新",
    "今天",
    "昨天",
    "上周",
    "这个",
    "那个",
    "所有",
    "全部",
    "帮我",
    "查看",
    "查询",
    "分析",
    "排查",
    "last",
    "recent",
    "latest",
    "all",
    "any",
}


def _parse_rule(text: str) -> dict:
    """规则模式：从文本中提取字段，构建 XQL。"""
    conditions = []
    confidence_score = 0
    explanation_parts = []
    search_trace_app = False

    # 1. TraceId
    trace_id = None
    m = _TRACE_FIELD_RE.search(text)
    if m:
        trace_id = m.group(1)
    else:
        m = _TRACE_ID_RE.search(text)
        if m:
            trace_id = m.group(1)
    if trace_id:
        conditions.append(f"xrayTraceId:{trace_id}")
        search_trace_app = True
        confidence_score += 40
        explanation_parts.append(f"识别到 TraceId: {trace_id}")

    # 2. 服务名
    # 先用预处理文本去掉时间短语，避免"最近"被误识别为服务名
    text_for_service = re.sub(
        r"最近\s*\d+\s*(?:分钟|小时|天|min|hour|h|d|day)",
        "",
        text,
        flags=re.I,
    )
    service = None
    m = _SERVICE_RE.search(text_for_service)
    if m:
        candidate = m.group(1)
        if candidate.lower() not in _SERVICE_STOPWORDS:
            service = candidate
    if not service:
        m = _SERVICE_SUFFIX_RE.search(text_for_service)
        if m:
            candidate = m.group(1)
            if candidate.lower() not in _SERVICE_STOPWORDS:
                service = candidate
    # 尝试匹配句中英文服务名（含连字符/点，形如 my-service / user.center）
    if not service:
        for m in _SERVICE_PLAIN_RE.finditer(text_for_service):
            candidate = m.group(1)
            if candidate.lower() not in _SERVICE_STOPWORDS:
                service = candidate
                break
    if service and not trace_id:
        conditions.append(f"subApplication:{service}")
        confidence_score += 40
        explanation_parts.append(f"识别到服务名: {service}")
    elif service and trace_id:
        # 有 traceId 时 subApplication 作为补充（可选）
        explanation_parts.append(f"附带服务名: {service}（traceId 模式下可选）")

    # 3. 日志级别
    for kw, level in _LEVEL_MAP.items():
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.I):
            conditions.append(f"level:{level}")
            confidence_score += 10
            explanation_parts.append(f"识别到日志级别: {level}")
            break

    # 4. Pod 名称
    m = _POD_RE.search(text)
    if m:
        pod = m.group(1)
        conditions.append(f"_pod_name_:{pod}")
        if not trace_id and not service:
            confidence_score += 40
        explanation_parts.append(f"识别到 Pod: {pod}")

    # 5. userId / uid
    m = _UID_RE.search(text)
    if m:
        uid = m.group(1)
        conditions.append(f"ext.uid:{uid}")
        if not trace_id and not service:
            confidence_score += 30
        explanation_parts.append(f"识别到用户 ID: {uid}")

    # 6. 消息关键词
    m = _MSG_KEYWORD_RE.search(text)
    if m:
        keyword = m.group(1)
        conditions.append(f'msg:"{keyword}"')
        confidence_score += 5
        explanation_parts.append(f"识别到消息关键词: {keyword}")

    # 7. 如果没有任何必要字段，降低置信度
    has_required = any(
        c.startswith(
            (
                "subApplication:",
                "xrayTraceId:",
                "_pod_name_:",
                "traceId:",
                "userId:",
                "ext.uid:",
            )
        )
        for c in conditions
    )
    if not has_required:
        confidence_score = max(0, confidence_score - 30)

    # 组合 query
    query = " AND ".join(conditions) if conditions else ""

    # 置信度评级
    if confidence_score >= 50:
        confidence = "high"
    elif confidence_score >= 20:
        confidence = "medium"
    else:
        confidence = "low"

    st, et = _parse_time_range(text)
    explanation_parts.append(
        f"时间范围：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st))} ~ "
        f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(et))}"
    )

    return {
        "query": query,
        "st": st,
        "et": et,
        "search_trace_app": search_trace_app,
        "mode": "rule",
        "confidence": confidence,
        "explanation": "；".join(explanation_parts)
        if explanation_parts
        else "未能识别有效字段",
    }


# ── LLM 模式 ──────────────────────────────────────────────────────────────────

_LLM_SYSTEM_PROMPT = """你是 Xray 日志平台的 XQL 查询专家。
请将用户的自然语言描述转换为 Xray XQL 查询参数，以 JSON 格式输出，不要包含任何其他内容。

XQL 语法规则：
- 键值精确匹配：field:value（value 不含空格时）
- 短语检索：field:"value"（检索包含该 token 的日志）
- 模糊检索：field:"*value*"（通配符）
- 数值比较：field:>400 / field:>=200 / field:<500
- 多值 OR：field:v1,v2
- 逻辑组合：AND / OR / NOT / ()
- 结构化字段：ext.uid:12345
- 不要生成 | SELECT 语法

application 表必须包含以下字段之一（否则报错）：
subApplication（推荐）/ xrayTraceId / _pod_name_ / traceId / ID / catMsgId / catRootId / userId

时间参数：st 和 et 为 Unix 秒（当前时间戳参考：{now}）。

输出 JSON 格式（严格遵守，不要有多余字段）：
{{
  "query": "XQL 查询语句",
  "st": 开始时间Unix秒,
  "et": 结束时间Unix秒,
  "search_trace_app": true/false（仅当 query 含 xrayTraceId 时为 true）,
  "confidence": "high/medium/low",
  "explanation": "简要说明识别逻辑"
}}"""


def _parse_llm(text: str, api_key: str, base_url: str, model: str) -> dict:
    """LLM 模式：调用大模型生成 XQL。"""
    now = int(time.time())
    system_prompt = _LLM_SYSTEM_PROMPT.format(now=now)

    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.0,
            "max_tokens": 512,
        }
    ).encode()

    url = base_url.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read().decode())
    except Exception as e:
        raise RuntimeError(f"LLM API 调用失败：{e}") from e

    content = resp_data["choices"][0]["message"]["content"].strip()

    # 从响应中提取 JSON（模型有时会包裹在 ```json ... ``` 中）
    json_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content)
    if json_match:
        content = json_match.group(1)

    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM 返回内容无法解析为 JSON：{content!r}") from e

    result["mode"] = "llm"
    return result


# ── CLI 入口 ──────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="将自然语言转换为 Xray XQL 查询参数",
        epilog=(
            "示例：\n"
            '  python nl_to_xql.py --text "查一下 my-service 最近 1 小时的 error 日志"\n'
            '  python nl_to_xql.py --text "这个 traceId a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4 的日志"\n'
            '  python nl_to_xql.py --text "..." --llm-api-key sk-xxx\n\n'
            "管道用法：\n"
            "  python nl_to_xql.py --text '...' | \\\n"
            '    python -c "\n'
            "      import json,sys,subprocess\n"
            "      p=json.load(sys.stdin)\n"
            "      subprocess.run(['python','validate_query.py',\n"
            "        '--query',p['query'],'--st',str(p['st']),'--et',str(p['et'])])\n"
            '    "'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--text", required=True, help="自然语言查询描述")
    parser.add_argument(
        "--llm-api-key",
        default=os.environ.get("LLM_API_KEY", ""),
        help="LLM API Key（也可通过环境变量 LLM_API_KEY 设置）",
    )
    parser.add_argument(
        "--llm-base-url",
        default=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        help="LLM API Base URL，默认 https://api.openai.com/v1（也可通过 LLM_BASE_URL 设置）",
    )
    parser.add_argument(
        "--llm-model",
        default=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        help="LLM 模型名，默认 gpt-4o-mini（也可通过 LLM_MODEL 设置）",
    )
    parser.add_argument(
        "--force-rule",
        action="store_true",
        help="强制使用规则模式，即使配置了 LLM API Key",
    )
    args = parser.parse_args()

    use_llm = bool(args.llm_api_key) and not args.force_rule

    if use_llm:
        try:
            result = _parse_llm(
                text=args.text,
                api_key=args.llm_api_key,
                base_url=args.llm_base_url,
                model=args.llm_model,
            )
        except RuntimeError as e:
            # LLM 失败时降级到规则模式
            sys.stderr.write(f"[warn] LLM 模式失败，降级到规则模式：{e}\n")
            result = _parse_rule(args.text)
            result["llm_fallback"] = True
    else:
        result = _parse_rule(args.text)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 置信度 low 时以非零退出，提示调用方人工确认
    if result.get("confidence") == "low":
        sys.stderr.write(
            "[warn] 置信度较低，建议人工确认 query 是否符合预期，"
            "或使用 --llm-api-key 启用 LLM 模式以获得更准确的结果\n"
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
