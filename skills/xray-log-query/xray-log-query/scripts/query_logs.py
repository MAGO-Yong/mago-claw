#!/usr/bin/env python3
"""
Xray 日志详情查询脚本 - /logs 接口
用途：查询具体的日志条目列表。建议先调用 query_charts.py 为本接口预热缓存。

支持两种调用模式：

  模式 A（自然语言，一步到位）：
    python query_logs.py --text "查一下 my-service 最近 1 小时的 error 日志"
    自动完成：自然语言解析 → 参数校验 → logs 查询，输出合并结果。

  模式 B（直接传参）：
    python query_logs.py --query "subApplication:my-service AND level:error" \
                          --st 1700000000 --et 1700003600 \
                          [--page 1] [--page-size 20] \
                          [--order desc] [--search-trace-app]

输出：JSON 格式，包含 logs 数组、count、cost 等字段。
     --text 模式下额外包含 parse_result（nl_to_xql 解析结果）。
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.parse

_XRAY_APP: str = os.environ.get("XRAY_APP", "xray")


def _get_token() -> str:
    token = os.environ.get("XRAY_AUTH_TOKEN", "").strip()
    if token:
        return token
    print(
        "[xray-log-query] 未检测到环境变量 XRAY_AUTH_TOKEN，请输入 XRay Token：",
        file=sys.stderr,
    )
    token = input("XRAY_AUTH_TOKEN> ").strip()
    if not token:
        print("[xray-log-query] Token 不能为空，已退出。", file=sys.stderr)
        sys.exit(1)
    return token


def _build_ticket() -> str:
    ts = int(time.time() * 1000)
    raw = f"{_XRAY_APP}&{_get_token()}&{ts}"
    return base64.b64encode(raw.encode()).decode()


BASE_URL = "https://xray.devops.xiaohongshu.com/logging/api/v1/tables/33/logs"


def query_logs(
    query: str,
    st: int,
    et: int,
    page: int = 1,
    page_size: int = 20,
    order: str = "desc",
    search_trace_app: bool = False,
) -> dict:
    """
    调用 /logs 接口。

    Args:
        query:            Lucene 语法查询条件（必须含 subApplication 等必要字段）
        st:               开始时间，Unix 秒
        et:               结束时间，Unix 秒
        page:             页码，默认 1
        page_size:        每页条数，默认 20，最大 10000
        order:            排序，"asc" 或 "desc"（默认 "desc"）
        search_trace_app: 按 TraceId 查询时设为 True，自动关联涉及的服务

    Returns:
        接口原始 JSON 响应（dict）
    """
    params: dict = {
        "query": query,
        "st": str(st),
        "et": str(et),
        "page": str(page),
        "pageSize": str(page_size),
        "orderKeywords": order,
    }
    if search_trace_app:
        params["searchTraceApp"] = "true"

    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"xray_ticket": _build_ticket()},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main():
    parser = argparse.ArgumentParser(
        description="查询 Xray 日志详情（/logs 接口）",
        epilog=(
            "示例：\n"
            "  # 自然语言模式（一步到位）\n"
            '  python query_logs.py --text "查一下 my-service 最近 1 小时的 error 日志"\n\n'
            "  # 直接传参模式\n"
            '  python query_logs.py --query "subApplication:my-service AND level:error" \\\n'
            "    --st 1700000000 --et 1700003600 --page-size 20\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # 模式 A：自然语言
    parser.add_argument("--text", default=None, help="自然语言查询描述（与 --query 二选一）")
    parser.add_argument(
        "--llm-api-key",
        default=os.environ.get("LLM_API_KEY", ""),
        help="LLM API Key（--text 模式可选，启用 LLM 解析）",
    )
    parser.add_argument(
        "--llm-base-url",
        default=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        help="LLM API Base URL",
    )
    parser.add_argument(
        "--llm-model",
        default=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        help="LLM 模型名",
    )
    parser.add_argument(
        "--force-rule",
        action="store_true",
        help="--text 模式下强制使用规则解析，不调用 LLM",
    )
    # 模式 B：直接传参
    parser.add_argument("--query", default=None, help="Lucene 查询条件（与 --text 二选一）")
    parser.add_argument("--st", type=int, default=None, help="开始时间 Unix 秒")
    parser.add_argument("--et", type=int, default=None, help="结束时间 Unix 秒")
    # 通用参数
    parser.add_argument("--page", type=int, default=1, help="页码，默认 1")
    parser.add_argument("--page-size", type=int, default=20, help="每页条数，默认 20")
    parser.add_argument(
        "--order", choices=["asc", "desc"], default="desc", help="排序方向，默认 desc"
    )
    parser.add_argument(
        "--search-trace-app",
        action="store_true",
        help="按 TraceId 查询时加上，自动关联涉及的服务（--text 模式下自动根据解析结果设置）",
    )
    args = parser.parse_args()

    # ── 参数互斥校验 ──────────────────────────────────────────────────────────
    if args.text and args.query:
        print(
            json.dumps(
                {"error": "--text 和 --query 不能同时指定，请二选一"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)
    if not args.text and not args.query:
        print(
            json.dumps({"error": "必须指定 --text 或 --query 之一"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)

    parse_result = None
    search_trace_app = args.search_trace_app

    if args.text:
        # ── 模式 A：自然语言 → 解析 → 校验 → 查询 ────────────────────────────
        import nl_to_xql
        import validate_query

        use_llm = bool(args.llm_api_key) and not args.force_rule
        if use_llm:
            try:
                parse_result = nl_to_xql._parse_llm(
                    text=args.text,
                    api_key=args.llm_api_key,
                    base_url=args.llm_base_url,
                    model=args.llm_model,
                )
            except RuntimeError as e:
                sys.stderr.write(f"[warn] LLM 模式失败，降级到规则模式：{e}\n")
                parse_result = nl_to_xql._parse_rule(args.text)
                parse_result["llm_fallback"] = True
        else:
            parse_result = nl_to_xql._parse_rule(args.text)

        query = parse_result["query"]
        st = parse_result["st"]
        et = parse_result["et"]
        # 自动设置 search_trace_app
        if parse_result.get("search_trace_app"):
            search_trace_app = True

        if not query:
            output = {
                "error": "自然语言解析未能生成有效 query",
                "parse_result": parse_result,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            sys.exit(2)

        if parse_result.get("confidence") == "low":
            sys.stderr.write(
                "[warn] 置信度较低，建议人工确认 query 是否符合预期，"
                "或使用 --llm-api-key 启用 LLM 模式\n"
            )

        valid, errors = validate_query.validate(
            query=query,
            st=st,
            et=et,
            page=args.page,
            page_size=args.page_size,
            order=args.order,
        )
        if not valid:
            output = {
                "error": "参数校验失败",
                "validation_errors": errors,
                "parse_result": parse_result,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            sys.exit(1)

    else:
        # ── 模式 B：直接传参 ──────────────────────────────────────────────────
        if args.st is None or args.et is None:
            print(
                json.dumps(
                    {"error": "直接传参模式下 --st 和 --et 必须指定"},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        query = args.query
        st = args.st
        et = args.et

    # ── 调用 logs 接口 ────────────────────────────────────────────────────────
    result = query_logs(
        query=query,
        st=st,
        et=et,
        page=args.page,
        page_size=args.page_size,
        order=args.order,
        search_trace_app=search_trace_app,
    )

    if parse_result is not None:
        result["parse_result"] = parse_result

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("code") != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
