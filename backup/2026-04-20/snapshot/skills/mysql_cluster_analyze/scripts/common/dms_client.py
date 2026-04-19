#!/usr/bin/env python3
"""
dms_client.py — DMS API 统一调用客户端（含 v1 → open-claw 兜底）

设计：
  - 优先调用 ai-api/v1（使用 DMS_AI_TOKEN）
  - 若 v1 发生网络/HTTP 异常，自动回退到 open-claw（使用 DMS_CLAW_TOKEN）
  - 若 v1 返回业务错误（HTTP 200 + errorMessage 字段），不回退，直接透传

环境变量：
  DMS_BASE_URL   — DMS 基础地址，默认 https://dms.devops.xiaohongshu.com
  DMS_AI_TOKEN   — ai-api/v1 Token（DMS-AI-Token header）
  DMS_CLAW_TOKEN — open-claw Token（dms-claw-token header）

ai-api/v1 响应格式：
  成功：{"data": ...}
  失败：{"errorMessage": "..."}

open-claw 响应格式：
  {"code": 0, "data": ..., "message": "ok"}

规范化：v1 成功响应会注入 "code": 0，使调用方无需区分来源。
"""

import json
import logging
import os
import ssl
import sys
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get("DMS_BASE_URL", "https://dms.devops.xiaohongshu.com").rstrip("/")
AI_TOKEN = os.environ.get("DMS_AI_TOKEN", "")
CLAW_TOKEN = os.environ.get("DMS_CLAW_TOKEN", "")

AI_V1_PREFIX = BASE_URL + "/dms-api/ai-api/v1"
OPEN_CLAW_PREFIX = BASE_URL + "/dms-api/open-claw"

# ai-api/v1 必填 AI 元信息 Header（固定值，识别调用来源）
_AI_HEADERS = {
    "DMS-AI-Token": AI_TOKEN,
    "X-AI-Agent-Id": "mysql-cluster-analyze",
    "X-AI-Session-Id": "local-script",
    "X-AI-Intent": "atomic-script-call",
    "X-AI-Version": "1.0",
}


def _make_ssl_ctx(url: str) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if "beta" in url or os.environ.get("DMS_SKIP_SSL_VERIFY"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _http_get(url: str, headers: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=_make_ssl_ctx(url)) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post(url: str, payload: dict, headers: dict, timeout: int = 60) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_make_ssl_ctx(url)) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _normalize_v1(result: dict) -> dict:
    """v1 成功响应注入 code=0，兼容调用方 result.get('code') == 0 判断。"""
    if "errorMessage" not in result:
        result.setdefault("code", 0)
    return result


def call_with_fallback(v1_fn, old_fn, label: str) -> dict:
    """
    执行带兜底的 API 调用：

      1. 优先执行 v1_fn()（ai-api/v1）
         - 成功 → 注入 code=0，返回
         - 业务错误（HTTP 200 + errorMessage）→ 不兜底，直接返回
         - 网络/HTTP 异常 → 进入步骤 2

      2. 兜底执行 old_fn()（open-claw）
         - 成功或失败均直接返回

    Args:
        v1_fn:  无参可调用，返回 v1 响应 dict；失败时抛异常
        old_fn: 无参可调用，返回 open-claw 响应 dict；失败时抛异常
        label:  日志标签，如 "[explain_sql]"
    """
    if AI_TOKEN:
        try:
            result = v1_fn()
            if "errorMessage" in result:
                # 业务错误，不兜底
                logger.warning("%s v1 业务错误（不兜底）: %s", label, result.get("errorMessage"))
                print(f"{label} v1 业务错误（不兜底）: {result.get('errorMessage')}", file=sys.stderr)
                return result
            print(f"{label} v1 调用成功", file=sys.stderr)
            return _normalize_v1(result)
        except Exception as e:
            print(f"{label} v1 调用异常，回退 open-claw: {e}", file=sys.stderr)
    else:
        print(f"{label} 未设置 DMS_AI_TOKEN，直接使用 open-claw", file=sys.stderr)

    if not CLAW_TOKEN:
        raise RuntimeError(f"{label} DMS_CLAW_TOKEN 未设置，无法兜底")

    result = old_fn()
    print(f"{label} open-claw 调用成功（兜底）", file=sys.stderr)
    return result
