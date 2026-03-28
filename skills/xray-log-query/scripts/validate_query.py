#!/usr/bin/env python3
"""
Xray 日志查询参数前置校验脚本
用途：在实际调用 /logs 或 /charts 接口前，本地校验参数合法性，尽早发现问题，
      避免将明显错误的请求发到服务端浪费配额/并发资源。

校验规则来源于项目源码（internal/ 层）：
  - ReqQueryBinder（pkg/model/view/base.go）
  - service/base/log/logs.go
  - service/base/charts/charts.go
  - middlewares/auth.go（PermissionChecker 逻辑说明）
  - pkg/utils/query_check.go（CheckIllegalSelect）

用法：
  python validate_query.py --query "subApplication:my-service AND level:error" \\
                            --st 1700000000 --et 1700003600

  # 校验通过：exit code 0，输出 {"valid": true}
  # 校验失败：exit code 1，输出 {"valid": false, "errors": [...]}

可作为管道前置步骤：
  python validate_query.py --query "..." --st ... --et ... && \\
    python query_charts.py --query "..." --st ... --et ...
"""

import argparse
import json
import re
import sys
import time
from typing import List, Tuple

# ── 常量（与服务端保持一致） ──────────────────────────────────────────────────

# application 表默认最大查询时间跨度（天），与 Apollo max_query_time_range_day 默认值一致
MAX_QUERY_RANGE_DAYS = 5

# 默认分页参数
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 10000

# application 表（tid=33）强制必须包含的字段之一
REQUIRED_FIELDS = [
    "subApplication",
    "xrayTraceId",
    "_pod_name_",
    "traceId",
    "ID",
    "catMsgId",
    "catRootId",
    "userId",
]

# 禁止在 query 中通过管道注入 SELECT（来源：pkg/utils/query_check.go）
SELECT_INJECT_RE = re.compile(r"(?i)\|\s*SELECT\s")

# xrayTraceId 格式：32 位十六进制
TRACE_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$")

# orderKeywords 合法值
VALID_ORDER = {"asc", "desc"}


# ── 核心校验函数 ──────────────────────────────────────────────────────────────


def validate(
    query: str,
    st: int,
    et: int,
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
    order: str = "desc",
    max_range_days: int = MAX_QUERY_RANGE_DAYS,
) -> Tuple[bool, List[str]]:
    """
    对 logs/charts 公共参数做前置校验。

    Args:
        query:          Lucene 查询条件字符串
        st:             开始时间，Unix 秒
        et:             结束时间，Unix 秒
        page:           页码
        page_size:      每页条数
        order:          排序方向 asc/desc
        max_range_days: 最大查询时间跨度（天），默认 5

    Returns:
        (is_valid, errors)
        is_valid: True 表示全部通过
        errors:   失败时的错误说明列表
    """
    errors: List[str] = []

    # ── 1. query 非空 ─────────────────────────────────────────────────────────
    if not query or not query.strip():
        errors.append("query 不能为空")
        # query 为空时后续字段相关校验无意义，提前返回
        return False, errors

    # ── 2. query 禁止 | SELECT 注入（来源：CheckIllegalSelect） ──────────────
    if SELECT_INJECT_RE.search(query):
        errors.append(
            "query 中不允许通过 '| SELECT' 语法注入 SELECT 语句，"
            "如需分析请使用 XQL 管道语法（仅限 count 等分析接口）"
        )

    # ── 3. application 表必填字段约束 ─────────────────────────────────────────
    # 从 query 中提取所有出现的字段名（形如 fieldName: 或 fieldName.sub:）
    used_fields = set(re.findall(r"([a-zA-Z_][a-zA-Z0-9_.]*)\s*:", query))
    has_required = any(f in used_fields for f in REQUIRED_FIELDS)
    if not has_required:
        errors.append(
            f"query 必须包含以下字段之一：{', '.join(REQUIRED_FIELDS)}。"
            "推荐使用 subApplication:<服务名> 作为基础条件"
        )

    # ── 4. xrayTraceId 格式校验（如果 query 中含有 xrayTraceId） ─────────────
    trace_matches = re.findall(r"xrayTraceId\s*:\s*([^\s\)AND]+)", query)
    for trace_id in trace_matches:
        trace_id = trace_id.strip().strip("'\"")
        if trace_id and not TRACE_ID_RE.match(trace_id):
            errors.append(
                f"xrayTraceId 格式错误：'{trace_id}' 应为 32 位十六进制字符串"
            )

    # ── 5. 时间参数校验 ───────────────────────────────────────────────────────
    now = int(time.time())

    if st < 0 or et < 0:
        errors.append("st 和 et 必须为非负整数（Unix 秒）")
    else:
        if st == 0 and et == 0:
            # 服务端会自动取最近 15 分钟，此处给出提示而非报错
            pass  # 合法，服务端兜底

        elif et < st:
            errors.append(f"结束时间 et({et}) 必须大于开始时间 st({st})")
        else:
            interval_seconds = et - st
            max_seconds = max_range_days * 24 * 3600
            if interval_seconds > max_seconds:
                errors.append(
                    f"查询时间跨度 {interval_seconds // 3600:.1f} 小时超出上限 "
                    f"{max_range_days} 天（{max_seconds // 3600} 小时）。"
                    "请缩小时间范围或联系管理员调整 max_query_time_range_day 配置"
                )

        # 未来时间警告（et 超过当前时间 5 分钟以上）
        if et > now + 300:
            errors.append(
                f"结束时间 et({et}) 超过当前时间 {(et - now) // 60} 分钟，"
                "可能导致查询结果为空"
            )

    # ── 6. 分页参数校验 ───────────────────────────────────────────────────────
    if page < 1:
        errors.append(f"page 必须 >= 1，当前值：{page}（服务端会自动修正为 1）")

    if page_size < 1:
        errors.append(
            f"pageSize 必须 >= 1，当前值：{page_size}（服务端会自动修正为 20）"
        )
    elif page_size > MAX_PAGE_SIZE:
        errors.append(
            f"pageSize({page_size}) 超出最大值 {MAX_PAGE_SIZE}，请减小 pageSize"
        )

    # ── 7. orderKeywords 校验 ─────────────────────────────────────────────────
    if order.lower() not in VALID_ORDER:
        errors.append(
            f"order '{order}' 不合法，必须为 'asc' 或 'desc'（服务端会强制转为 DESC）"
        )

    return len(errors) == 0, errors


# ── CLI 入口 ──────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Xray 日志查询参数前置校验（logs/charts 通用）",
        epilog=(
            "示例：\n"
            "  python validate_query.py \\\n"
            '    --query "subApplication:my-service AND level:error" \\\n'
            "    --st 1700000000 --et 1700003600\n\n"
            '校验通过：exit 0，输出 {"valid": true}\n'
            '校验失败：exit 1，输出 {"valid": false, "errors": [...]}'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--query", required=True, help="Lucene XQL 查询条件")
    parser.add_argument("--st", required=True, type=int, help="开始时间 Unix 秒")
    parser.add_argument("--et", required=True, type=int, help="结束时间 Unix 秒")
    parser.add_argument(
        "--page", type=int, default=DEFAULT_PAGE, help=f"页码，默认 {DEFAULT_PAGE}"
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"每页条数，默认 {DEFAULT_PAGE_SIZE}",
    )
    parser.add_argument("--order", default="desc", help="排序方向 asc/desc，默认 desc")
    parser.add_argument(
        "--max-range-days",
        type=int,
        default=MAX_QUERY_RANGE_DAYS,
        help=f"最大查询时间跨度（天），默认 {MAX_QUERY_RANGE_DAYS}，与 Apollo max_query_time_range_day 保持一致",
    )
    args = parser.parse_args()

    valid, errors = validate(
        query=args.query,
        st=args.st,
        et=args.et,
        page=args.page,
        page_size=args.page_size,
        order=args.order,
        max_range_days=args.max_range_days,
    )

    if valid:
        print(json.dumps({"valid": True}, ensure_ascii=False))
        sys.exit(0)
    else:
        print(
            json.dumps({"valid": False, "errors": errors}, ensure_ascii=False, indent=2)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
