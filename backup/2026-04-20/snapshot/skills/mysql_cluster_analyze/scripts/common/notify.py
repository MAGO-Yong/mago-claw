#!/usr/bin/env python3
"""
notify.py — redcity webhook 推送封装

将诊断报告链接及摘要通过 webhook 机器人推送到群。
初期使用 markdown 格式，后续可迭代为卡片格式。

⚠️ 调用约束（方案A文档层）：
  --dms_url 必须传 DMS 内网 URL（由 dms_upload.py 上传后返回）
  严禁直接传 CDN 链接（https://fe-static.xhscdn.com/...），传入会立即报错退出。
  正确流程：generate_report → dms_upload → notify(dms_url=<DMS URL>)

调用方式：
  python3 notify.py --cluster my_cluster --time_range "2026-03-25 14:00 ~ 14:10" \
      --dms_url https://dms.devops.xiaohongshu.com/... --top_sqls "SELECT ...|1.23s"
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


# ── CDN 链接黑名单（方案B校验层）──
# 传入以下前缀的 URL 时直接报错退出，必须先调用 dms_upload.py 上传
_CDN_PREFIXES = (
    "https://fe-static.xhscdn.com",
    "http://fe-static.xhscdn.com",
)


def _validate_dms_url(url: str) -> None:
    """
    校验 dms_url 不是 CDN 链接。
    命中 CDN 前缀则打印错误并 sys.exit(1)。
    """
    for prefix in _CDN_PREFIXES:
        if url.startswith(prefix):
            print(
                f"[notify] ❌ 拒绝 CDN 链接：{url[:60]}...\n"
                f"[notify]    请先调用 dms_upload.py 上传报告，再将返回的 DMS URL 传入 --dms_url",
                file=sys.stderr,
            )
            sys.exit(1)


def send_report(
    cluster_name: str,
    time_range: str,
    dms_url: str,
    top_sqls: Optional[list[dict]] = None,
    webhook_url: Optional[str] = None,
    # 通用诊断摘要字段（均有默认值，向后兼容）
    path: str = "",
    path_label: str = "",
    severity: str = "",
    root_cause: str = "",
    p0_action: str = "",
) -> bool:
    """
    推送诊断报告到群。

    Args:
        cluster_name: 集群名称
        time_range:   诊断时间范围，如 "2026-03-25 14:00 ~ 14:10"
        dms_url:      HTML 报告的 DMS 内网 URL（必须由 dms_upload.py 上传后获取，禁止传 CDN 链接）
        top_sqls:     TOP 慢 SQL 列表（路径A专用），最多取前3条展示
        path:         诊断路径字母，如 "D" / "F" / "C2"
        path_label:   路径描述，如 "磁盘满" / "机器带宽" / "复制中断"
        severity:     严重程度，如 "P0" / "P1" / "P2"
        root_cause:   一句话根因
        p0_action:    P0 建议（最重要的一条）

    Returns:
        True 表示推送成功，False 表示失败
    """
    # ── 方案B：CDN 链接校验 ──
    _validate_dms_url(dms_url)
    top_sqls = top_sqls or []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    url = _resolve_webhook_url(webhook_url)
    print(f"[notify] 推送目标：{url.split('?')[0]}?key=***")

    # ── 判断使用通用模板还是慢查询专用模板 ──
    use_generic = bool(path or path_label or severity or root_cause)

    cdn_url = dms_url  # 内部变量名保持兼容，实际传入的是 DMS URL

    if use_generic:
        # ── 通用结构化 Webhook 消息 ──
        sev_color = {"P0": "warning", "P1": "warning", "P2": "info", "P3": "comment"}.get(severity.upper(), "info")
        path_str = f"路径 {path} · {path_label}" if path and path_label else (path_label or path or "诊断")
        title_icon = {"P0": "🚨", "P1": "⚠️", "P2": "🔍", "P3": "✅"}.get(severity.upper(), "🔍")

        parts = [
            f"## {title_icon} MySQL {path_str}诊断报告 · `{cluster_name}`",
        ]
        if severity:
            parts.append(f"> **严重程度**：<font color=\"{sev_color}\">**{severity}**</font>")
        parts.append(f"> **诊断窗口**：{time_range}")
        if root_cause:
            parts.append(f"> **根因**：{root_cause}")
        if p0_action:
            parts.append(f"> **P0 建议**：<font color=\"warning\">{p0_action}</font>")
        parts.append(f"> **生成时间**：<font color=\"comment\">{now}</font>")
        parts.append(f"> 📄 完整报告 → [**点击查看详细分析**]({cdn_url})")

    else:
        # ── 慢查询专用模板（旧逻辑，向后兼容）──
        max_qt    = top_sqls[0].get("avg_query_time", "?") if top_sqls else "?"
        total_cnt = sum(
            int(s.get("query_count", 0)) for s in top_sqls
            if str(s.get("query_count", "?")).isdigit()
        )
        total_str = str(total_cnt) if total_cnt > 0 else "?"

        parts = [
            f"## 🔍 MySQL 慢查询诊断报告 · `{cluster_name}`",
            f"> **诊断窗口**：{time_range}",
            f"> **最长耗时**：<font color=\"warning\">**{max_qt}**</font>　"
            f"**慢查总数**：<font color=\"warning\">**{total_str} 条**</font>",
            f"> **生成时间**：<font color=\"comment\">{now}</font>",
            f"> 📄 完整报告 → [**点击查看详细分析**]({cdn_url})",
        ]

        if top_sqls:
            parts.append("")
            parts.append("**🐢 TOP 慢 SQL — 需立即关注**")
            for i, sql in enumerate(top_sqls[:3], 1):
                template  = sql.get("sql_template", "N/A")
                avg_time  = sql.get("avg_query_time", "?")
                count     = sql.get("query_count", "?")
                rows_exam = sql.get("rows_examined", "")
                amplify   = sql.get("scan_amplify", "")
                table     = sql.get("table_name", "")

                short_sql = template[:55] + "…" if len(template) > 55 else template
                detail_parts = [f"耗时 **{avg_time}**"]
                if str(count) not in ("?", "0", ""):
                    detail_parts.append(f"执行 **{count} 次**")
                if rows_exam:
                    detail_parts.append(f"扫描 **{rows_exam} 行**")
                if amplify:
                    detail_parts.append(f"放大 <font color=\"warning\">**{amplify}x**</font>")
                if table:
                    detail_parts.append(f"表：`{table}`")

                parts.append(f"> **{i}. ** <font color=\"warning\">{short_sql}</font>")
                parts.append("> " + "　".join(detail_parts))

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
    parser.add_argument("--dms_url",     required=True,
                        help="报告 DMS URL（必须由 dms_upload.py 上传后获取，禁止传 CDN 链接）")
    parser.add_argument("--top_sqls",    nargs="*", default=[],
                        help="TOP SQL，格式：<sql_template>|<avg_time>|<count>，可传多个")
    parser.add_argument("--webhook_url", default=None,
                        help="Webhook 地址（可选，优先级最高）")
    # 通用摘要字段（新增，均有默认值，向后兼容）
    parser.add_argument("--path",        default="", help="诊断路径字母，如 D / F / C2")
    parser.add_argument("--path_label",  default="", help="路径描述，如 磁盘满 / 机器带宽")
    parser.add_argument("--severity",    default="", help="严重程度，如 P0 / P1 / P2")
    parser.add_argument("--root_cause",  default="", help="一句话根因")
    parser.add_argument("--p0_action",   default="", help="P0 建议（最重要的一条）")
    args = parser.parse_args()

    sqls = []
    for item in args.top_sqls:
        parts = item.split("|")
        if len(parts) >= 2:
            sqls.append({
                "sql_template":   parts[0],
                "avg_query_time": parts[1],
                "query_count":    parts[2] if len(parts) > 2 else "?",
            })

    ok = send_report(
        args.cluster, args.time_range, args.dms_url, sqls, args.webhook_url,
        path=args.path, path_label=args.path_label, severity=args.severity,
        root_cause=args.root_cause, p0_action=args.p0_action,
    )
    sys.exit(0 if ok else 1)
