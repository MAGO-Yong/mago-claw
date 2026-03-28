#!/usr/bin/env python3
"""
Xray 日志聚类查询脚本 - /cluster-logs 接口
用途：将指定时间范围内的日志按内容模板聚类（Drain 算法），返回各聚类模板和数量。
      仅支持 application 表（tid=33）。

注意：聚类功能依赖离线训练，如果某服务未训练过则返回空列表，调用方需做好兜底处理。

用法：
  python query_cluster_logs.py --query "subApplication:my-service" \
                                --st 1700000000 --et 1700003600 \
                                [--compare-st 1699996400 --compare-et 1700000000]

输出：JSON 格式，包含 templates 聚类列表。
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse
from typing import Optional

import auth

BASE_URL = "https://xray.devops.xiaohongshu.com/logging/api/v1/tables/33/cluster-logs"


def query_cluster_logs(
    query: str,
    st: int,
    et: int,
    compare_st: Optional[int] = None,
    compare_et: Optional[int] = None,
) -> dict:
    """
    调用 /cluster-logs 接口。

    Args:
        query:      Lucene 语法查询条件（必须含 subApplication 等必要字段）
        st:         开始时间，Unix 秒
        et:         结束时间，Unix 秒
        compare_st: 对比时间段开始，Unix 秒（与 compare_et 同时传才生效）
        compare_et: 对比时间段结束，Unix 秒

    Returns:
        接口原始 JSON 响应（dict）。
        data.templates 可能为空数组（聚类未训练或无数据），调用方必须处理此情况。
    """
    params: dict = {
        "query": query,
        "st": str(st),
        "et": str(et),
    }
    if compare_st is not None and compare_et is not None:
        params["compareST"] = str(compare_st)
        params["compareET"] = str(compare_et)

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
        description="查询 Xray 日志聚类（/cluster-logs 接口）"
    )
    parser.add_argument("--query", required=True, help="Lucene 查询条件")
    parser.add_argument("--st", required=True, type=int, help="开始时间 Unix 秒")
    parser.add_argument("--et", required=True, type=int, help="结束时间 Unix 秒")
    parser.add_argument(
        "--compare-st", type=int, default=None, help="对比时间段开始 Unix 秒（可选）"
    )
    parser.add_argument(
        "--compare-et", type=int, default=None, help="对比时间段结束 Unix 秒（可选）"
    )
    args = parser.parse_args()

    result = query_cluster_logs(
        query=args.query,
        st=args.st,
        et=args.et,
        compare_st=args.compare_st,
        compare_et=args.compare_et,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("code") != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
