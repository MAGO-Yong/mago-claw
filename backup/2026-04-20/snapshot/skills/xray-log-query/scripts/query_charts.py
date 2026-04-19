#!/usr/bin/env python3
"""
Xray 日志数量分布查询脚本 - /charts 接口
用途：获取指定时间范围内的日志数量柱状图，同时为 /logs 预热缓存。

支持两种调用模式：

  模式 A（自然语言，一步到位）：
    python query_charts.py --text "查一下 my-service 最近 1 小时的 error 日志"
    自动完成：自然语言解析 → 参数校验 → charts 查询，输出合并结果。

  模式 B（直接传参）：
    python query_charts.py --query "subApplication:my-service AND level:error" \
                            --st 1700000000 --et 1700003600 \
                            [--page-size 20]

输出：JSON 格式，包含 histograms 柱状图数据和 count 总数。
     --text 模式下额外包含 parse_result（nl_to_xql 解析结果）。
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse

BASE_URL = "https://xray-ai.devops.xiaohongshu.com/open/skill/log/api/v1/tables/charts"


def query_charts(query: str, st: int, et: int, page_size: int = 20) -> dict:
    """
    调用 /charts 接口。

    Args:
        query:     Lucene 语法查询条件（必须含 subApplication 等必要字段）
        st:        开始时间，Unix 秒
        et:        结束时间，Unix 秒
        page_size: 每页条数，默认 20

    Returns:
        接口原始 JSON 响应（dict）
    """
    params = {
        "table": "application",
        "query": query,
        "st": str(st),
        "et": str(et),
        "pageSize": str(page_size),
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main():
    parser = argparse.ArgumentParser(
        description="查询 Xray 日志数量分布（/charts 接口）",
        epilog=(
            "示例：\n"
            "  # 自然语言模式（一步到位）\n"
            '  python query_charts.py --text "查一下 my-service 最近 1 小时的 error 日志"\n\n'
            "  # 直接传参模式\n"
            '  python query_charts.py --query "subApplication:my-service AND level:error" \\\n'
            "    --st 1700000000 --et 1700003600\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # 模式 A：自然语言
    parser.add_argument("--text", default=None, help="自然语言查询描述（与 --query 二选一）")
    # 模式 A 可选：LLM 相关参数
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
    parser.add_argument("--page-size", type=int, default=20, help="每页条数，默认 20")
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

    if args.text:
        # ── 模式 A：自然语言 → 解析 → 校验 → 查询 ────────────────────────────
        import nl_to_xql
        import validate_query

        # Step 1: 自然语言解析
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

        # Step 2: 参数校验
        valid, errors = validate_query.validate(query=query, st=st, et=et, page_size=args.page_size)
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

    # ── Step 3: 调用 charts 接口 ──────────────────────────────────────────────
    result = query_charts(query=query, st=st, et=et, page_size=args.page_size)

    # --text 模式下将解析结果附加到输出
    if parse_result is not None:
        result["parse_result"] = parse_result

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("code") != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
