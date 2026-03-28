#!/usr/bin/env python3
"""
Xray 日志详情查询脚本 - /logs 接口
用途：查询具体的日志条目列表。建议先调用 query_charts.py 为本接口预热缓存。

用法：
  python query_logs.py --query "subApplication:my-service AND level:error" \
                        --st 1700000000 --et 1700003600 \
                        [--page 1] [--page-size 20] \
                        [--order desc] [--search-trace-app]

输出：JSON 格式，包含 logs 数组、count、cost 等字段。
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse

import auth

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
        headers={"xray_ticket": auth.build_ticket()},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main():
    parser = argparse.ArgumentParser(description="查询 Xray 日志详情（/logs 接口）")
    parser.add_argument("--query", required=True, help="Lucene 查询条件")
    parser.add_argument("--st", required=True, type=int, help="开始时间 Unix 秒")
    parser.add_argument("--et", required=True, type=int, help="结束时间 Unix 秒")
    parser.add_argument("--page", type=int, default=1, help="页码，默认 1")
    parser.add_argument("--page-size", type=int, default=20, help="每页条数，默认 20")
    parser.add_argument(
        "--order", choices=["asc", "desc"], default="desc", help="排序方向，默认 desc"
    )
    parser.add_argument(
        "--search-trace-app",
        action="store_true",
        help="按 TraceId 查询时加上，自动关联涉及的服务",
    )
    args = parser.parse_args()

    result = query_logs(
        query=args.query,
        st=args.st,
        et=args.et,
        page=args.page,
        page_size=args.page_size,
        order=args.order,
        search_trace_app=args.search_trace_app,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("code") != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
