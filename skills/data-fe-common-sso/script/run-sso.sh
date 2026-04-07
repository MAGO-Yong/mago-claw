#!/bin/bash
# mock SSO - 直接读取 .redInfo 里的 token 并输出
WORKSPACE="${1:-$HOME/.openclaw/workspace}"
TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.redInfo'))['token'])" 2>/dev/null)
if [ -n "$TOKEN" ]; then
    echo "common-internal-access-token-prod=$TOKEN"
    exit 0
else
    echo "❌ .redInfo 中未找到 token" >&2
    exit 1
fi
