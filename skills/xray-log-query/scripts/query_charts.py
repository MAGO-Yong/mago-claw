#!/usr/bin/env python3
"""
Xray 日志数量分布查询脚本 - /charts 接口
用途：获取指定时间范围内的日志数量柱状图，同时为 /logs 预热缓存。

用法：
  python query_charts.py --query "subApplication:my-service AND level:error" \
                          --st 1700000000 --et 1700003600 \
                          [--page-size 20]

输出：JSON 格式，包含 histograms 柱状图数据和 count 总数。
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse

import auth

BASE_URL = "https://xray.devops.xiaohongshu.com/logging/api/v1/tables/33/charts"


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
        "query": query,
        "st": str(st),
        "et": str(et),
        "pageSize": str(page_size),
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"xray_ticket": auth.build_ticket()},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main():
    parser = argparse.ArgumentParser(
        description="查询 Xray 日志数量分布（/charts 接口）"
    )
    parser.add_argument("--query", required=True, help="Lucene 查询条件")
    parser.add_argument("--st", required=True, type=int, help="开始时间 Unix 秒")
    parser.add_argument("--et", required=True, type=int, help="结束时间 Unix 秒")
    parser.add_argument("--page-size", type=int, default=20, help="每页条数，默认 20")
    args = parser.parse_args()

    result = query_charts(
        query=args.query,
        st=args.st,
        et=args.et,
        page_size=args.page_size,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("code") != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
