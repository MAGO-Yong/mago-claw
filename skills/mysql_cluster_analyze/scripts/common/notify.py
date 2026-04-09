#!/usr/bin/env python3
"""
notify.py — redcity webhook 推送封装

将诊断报告链接及摘要通过 webhook 机器人推送到群。
初期使用 markdown 格式，后续可迭代为卡片格式。

调用方式：
  python3 notify.py --cluster my_cluster --time_range "2026-03-25 14:00 ~ 14:10" \
      --cdn_url https://... --top_sqls "SELECT ...|1.23s" "UPDATE ...|0.89s"
  from common.notify import send_report

──────────────────────────────────────────────────────────
Webhook 地址配置（三层优先级，高优先级覆盖低优先级）：

  1. 命令行参数  --webhook_url <url>          （最高优先级，临时覆盖）
  2. 环境变量    DMS_WEBHOOK_URL=<url>         （推荐：在 .env 或部署环境中设置）
  3. 代码默认值  DEFAULT_WEBHOOK_URL           （兜底，需要换群时改这里）

推荐做法：在 ~/.openclaw/workspace/.env 中添加：
  DMS_WEBHOOK_URL=https://redcity-open.xiaohongshu.com/api/robot/webhook/send?key=xxx
──────────────────────────────────────────────────────────
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime
from typing import Optional


# 默认 webhook 地址（兜底值，优先级最低）
# 换群时修改此处，或通过环境变量 DMS_WEBHOOK_URL 覆盖
DEFAULT_WEBHOOK_URL = (
    "https://redcity-open.xiaohongshu.com/api/robot/webhook/send"
    "?key=d9bf1a35-bbf6-4dc2-9c4d-7d0ebb401f40"
)


def _resolve_webhook_url(cli_url: Optional[str] = None) -> str:
    """
    解析最终使用的 webhook 地址，优先级：
    1. 命令行参数 --webhook_url
    2. 环境变量 DMS_WEBHOOK_URL
    3. DEFAULT_WEBHOOK_URL（代码内默认值）
    """
    if cli_url:
        return cli_url
    env_url = os.environ.get("DMS_WEBHOOK_URL", "").strip()
    if env_url:
        return env_url
    return DEFAULT_WEBHOOK_URL


def send_report(
    cluster_name: str,
    time_range: str,
    cdn_url: str,
    top_sqls: Optional[list[dict]] = None,
    webhook_url: Optional[str] = None,
) -> bool:
    """
    推送诊断报告到群。

    Args:
        cluster_name: 集群名称
        time_range:   诊断时间范围，如 "2026-03-25 14:00 ~ 14:10"
        cdn_url:      HTML 报告的 CDN 公网 URL
        top_sqls:     TOP 慢 SQL 列表，每项包含 sql_template / avg_query_time / query_count
                      最多取前 3 条展示

    Returns:
        True 表示推送成功，False 表示失败
    """
    top_sqls = top_sqls or []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    url = _resolve_webhook_url(webhook_url)
    print(f"[notify] 推送目标：{url.split('?')[0]}?key=***")

    # ── 构造 markdown 内容 ──────────────────────────────────────
    # hi markdown 支持语法（子集）：
    #   - 换行：真实 \n，json.dumps 会自动序列化
    #   - 颜色：<font color="info|comment|warning">  (绿/灰/橙红)
    #   - 加粗：**text**   斜体：*text*
    #   - 引用：> text（每行单独加 >，不能空行嵌套）
    #   - 行内代码：`code`
    #   - 链接：[text](url)
    #   - 标题：# ## 等（渲染为加粗）
    #   - 不支持：表格、代码块、多级引用、分割线 ---
    # ────────────────────────────────────────────────────────────

    # ── 聚合摘要数字（从 top_sqls 中提取） ──
    max_qt     = top_sqls[0].get("avg_query_time", "?") if top_sqls else "?"
    total_cnt  = sum(
        int(s.get("query_count", 0)) for s in top_sqls
        if str(s.get("query_count", "?")).isdigit()
    )
    total_str  = str(total_cnt) if total_cnt > 0 else "?"

    # ── 第一块：报告头 ──
    parts = [
        f"## 🔍 MySQL 慢查询诊断报告 · `{cluster_name}`",
        f"> **诊断窗口**：{time_range}",
        f"> **最长耗时**：<font color=\"warning\">**{max_qt}**</font>　"
        f"**慢查总数**：<font color=\"warning\">**{total_str} 条**</font>",
        f"> **生成时间**：<font color=\"comment\">{now}</font>",
        f"> 📄 完整报告 → [**点击查看详细分析**]({cdn_url})",
    ]

    # ── 第二块：TOP SQL ──
    if top_sqls:
        parts.append("")
        parts.append("**🐢 TOP 慢 SQL — 需立即关注**")
        for i, sql in enumerate(top_sqls[:3], 1):
            template   = sql.get("sql_template", "N/A")
            avg_time   = sql.get("avg_query_time", "?")
            count      = sql.get("query_count", "?")
            rows_exam  = sql.get("rows_examined", "")
            amplify    = sql.get("scan_amplify", "")
            table      = sql.get("table_name", "")

            short_sql = template[:55] + "…" if len(template) > 55 else template

            # 指标行
            detail_parts = [f"耗时 **{avg_time}**"]
            if str(count) not in ("?", "0", ""):
                detail_parts.append(f"执行 **{count} 次**")
            if rows_exam:
                detail_parts.append(f"扫描 **{rows_exam} 行**")
            if amplify:
                detail_parts.append(f"放大 <font color=\"warning\">**{amplify}x**</font>")
            if table:
                detail_parts.append(f"表：`{table}`")

            # SQL 行和指标行都放进引用块，保持视觉对齐
            parts.append(f"> **{i}. ** <font color=\"warning\">{short_sql}</font>")
            parts.append("> " + "　".join(detail_parts))

    # 用真正的换行符连接，json.dumps 序列化时会自动转成 \n
    content = "\n".join(parts)

    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read().decode("utf-8")
            resp_json = json.loads(resp_body)
            if resp_json.get("code") == 0 or resp_json.get("errcode") == 0:
                print(f"[notify] ✅ 推送成功")
                return True
            else:
                print(f"[notify] ❌ 推送失败，响应：{resp_body}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"[notify] ❌ 推送异常：{e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="推送诊断报告到群")
    parser.add_argument("--cluster",     required=True, help="集群名称")
    parser.add_argument("--time_range",  required=True, help="诊断时间范围")
    parser.add_argument("--cdn_url",     required=True, help="报告 CDN URL")
    parser.add_argument(
        "--top_sqls",
        nargs="*",
        default=[],
        help="TOP SQL，格式：<sql_template>|<avg_time>|<count>，可传多个",
    )
    parser.add_argument(
        "--webhook_url",
        default=None,
        help=(
            "Webhook 地址（可选，优先级最高）。"
            "不传则读取环境变量 DMS_WEBHOOK_URL，再不存在则用代码内默认值。"
        ),
    )
    args = parser.parse_args()

    # 解析 top_sqls 参数
    sqls = []
    for item in args.top_sqls:
        parts = item.split("|")
        if len(parts) >= 2:
            sqls.append({
                "sql_template":   parts[0],
                "avg_query_time": parts[1],
                "query_count":    parts[2] if len(parts) > 2 else "?",
            })

    ok = send_report(args.cluster, args.time_range, args.cdn_url, sqls, args.webhook_url)
    sys.exit(0 if ok else 1)
