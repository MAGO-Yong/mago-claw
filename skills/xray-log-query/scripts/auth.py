#!/usr/bin/env python3
"""
XRay API 鉴权模块
提供 ticket 生成能力，供各查询脚本复用。

Ticket 生成规则（来自 XRay OpenAPI 文档）：
  Base64(app & token & timestamp_ms)

Token 获取优先级：
  1. 环境变量 XRAY_AUTH_TOKEN
  2. 交互式终端输入

App 来源：
  1. 环境变量 XRAY_APP
  2. 默认值 "xray"
"""

import base64
import os
import sys
import time

APP: str = os.environ.get("XRAY_APP", "xray")


def get_token() -> str:
    """
    获取 XRay API Token。
    优先从环境变量 XRAY_AUTH_TOKEN 读取，若未设置则提示用户交互式输入。
    """
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


def build_ticket() -> str:
    """
    生成 xray_ticket 请求头值（含毫秒时间戳，每次调用实时生成，不可复用）。
    生成规则：Base64(app & token & timestamp_ms)
    """
    ts = int(time.time() * 1000)
    raw = f"{APP}&{get_token()}&{ts}"
    return base64.b64encode(raw.encode()).decode()
