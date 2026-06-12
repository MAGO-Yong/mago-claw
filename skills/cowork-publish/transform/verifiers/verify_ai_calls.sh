#!/usr/bin/env bash
# 验证：文本 LLM 调用走 Runway Bedrock，无残留 SDK / endpoint / 错字段
# 详见 transform_prompt.md § 五 + § 十 checklist 第 2151-2168 行
#
# 检查项（仅当工程含 AI 信号时严格执行）：
#   1) 不能有 OpenAI Chat Completions / Anthropic Messages 原生 endpoint
#   2) 不能有纯文本 SDK 残留（openai chat / anthropic / @anthropic-ai/sdk / zhipuai / langchain 文本 provider）
#   3) Runway 调用请求体不能传 model / temperature 字段
#   4) system 必须是顶级字段（不能塞 messages 数组）
#   5) 必须有 200 OK 业务错检查（data.Code || data.Error 拦截）
#   6) 不能用 OpenAI SSE 格式（data: {...}\n\ndata: [DONE]）解析 Runway 流式
#   7) 不能用 OpenAI 响应字段 choices[0].message.content 解析 Runway 非流式
#   8) base_url 已含 /openai 前缀，不能再拼 /openai/

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

EXCLUDE='(node_modules|\.next/|dist/|build/|\.guard-transform|\.venv|venv/|__pycache__|\.test\.|\.spec\.|/test/|/tests/|__tests__|\.d\.ts$|README|CHANGELOG)'

# ---- 先决条件：是否调了文本 LLM？----
USES_TEXT_AI=0
# 标志 1：依赖里出现纯文本 SDK / Runway endpoint 字面量 / Anthropic Messages 协议关键词
for f in package.json apps/*/package.json packages/*/package.json backend/package.json; do
  [ -f "$f" ] || continue
  if grep -qE '"(openai|@anthropic-ai/sdk|anthropic|zhipuai|langchain|@langchain/)' "$f" 2>/dev/null; then
    USES_TEXT_AI=1; break
  fi
done
for f in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
  [ -f "$f" ] || continue
  if grep -qiE '^[[:space:]]*(openai|anthropic|zhipuai|langchain|llama-index)([><=!~ ]|$)' "$f" 2>/dev/null; then
    USES_TEXT_AI=1; break
  fi
done
# 标志 2：代码里有 Runway / Bedrock / anthropic_version / ai.properties 关键词
if grep -rqIE 'bedrock_runtime|anthropic_version|ai\.base_url|ai\.api_key|ai\.properties' . 2>/dev/null \
     --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
     --include='*.py' --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next \
     --exclude-dir=dist --exclude-dir=build --exclude-dir=.venv --exclude-dir=__pycache__; then
  USES_TEXT_AI=1
fi

if [ "$USES_TEXT_AI" = "0" ]; then
  echo "[OK] 工程未调用文本 LLM（跳过）"
  exit 0
fi

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# ---- 1. 残留纯文本 SDK 依赖 ----
BANNED_NODE_AI='"(openai|@anthropic-ai/sdk|anthropic|zhipuai|@langchain/openai|@langchain/anthropic)"'
for pkg in package.json apps/*/package.json packages/*/package.json backend/package.json; do
  [ -f "$pkg" ] || continue
  hits=$(grep -nE "$BANNED_NODE_AI" "$pkg" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    report "$pkg 含纯文本 LLM SDK（应整体迁到 Runway HTTP 调用）:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
done

BANNED_PY_AI='^[[:space:]]*(openai|anthropic|zhipuai|langchain-openai|langchain-anthropic)([><=!~ ]|$)'
for req in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
  [ -f "$req" ] || continue
  hits=$(grep -niE "$BANNED_PY_AI" "$req" 2>/dev/null | grep -vE '^\s*#' || true)
  if [ -n "$hits" ]; then
    report "$req 含纯文本 LLM SDK:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
done

# ---- 2. 残留原生 endpoint（OpenAI / Anthropic / Vertex）----
# Runway 网关上这些 path 根本不存在
ENDPOINT_HITS=$(grep -rnIE \
  '/v1/chat/completions|/v1/messages|/v1/responses|/v1:rawPredict|/v1:streamRawPredict|api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis\.com' \
  --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
  --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | head -10 || true)
if [ -n "$ENDPOINT_HITS" ]; then
  report "残留 OpenAI / Anthropic / Vertex 原生 endpoint（Runway 网关上不存在，会拿 404）:"
  echo "$ENDPOINT_HITS" | sed 's/^/    /' >&2
fi

# ---- 3. 残留 OpenAI 响应字段解析 ----
hits=$(grep -rnIE 'choices\[0\]\.message\.content|choices\[0\]\.delta\.content|usage\.prompt_tokens|usage\.completion_tokens' \
  --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
  --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | head -5 || true)
if [ -n "$hits" ]; then
  report "残留 OpenAI 响应字段（Runway Bedrock 用 content[].text + usage.input_tokens）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# ---- 4. 残留 OpenAI SSE 解析（data: {...}\n\ndata: [DONE]）----
hits=$(grep -rnIE 'data:\s*\[DONE\]|"data:\s"|data: ' \
  --include='*.ts' --include='*.js' --include='*.mjs' --include='*.cjs' --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | grep -iE 'split|parse|stream|chunk' \
  | head -5 || true)
if [ -n "$hits" ]; then
  report "残留 OpenAI SSE 解析模式（Runway 流式是 base64 包裹的 chunk.bytes，不是 OpenAI SSE）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# ---- 5. 调用 invoke endpoint 的请求体含 model / temperature 字段 ----
# 只检查"明显是构造 Runway 请求体"的代码块
INVOKE_FILES=$(grep -rlIE 'bedrock_runtime/model/invoke|anthropic_version' . 2>/dev/null \
               --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
               --include='*.py' --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next \
               --exclude-dir=dist --exclude-dir=build --exclude-dir=.venv --exclude-dir=__pycache__ || true)

for f in $INVOKE_FILES; do
  # model 字段（不是 modelId / model_name 等其它字段；只查独立的 "model": ）
  if grep -nE '["'"'"']model["'"'"']\s*:' "$f" 2>/dev/null | grep -vE 'modelI[dD]|model_id|model_name|model_type|model_version' | head -3 | grep -q .; then
    HIT=$(grep -nE '["'"'"']model["'"'"']\s*:' "$f" 2>/dev/null | grep -vE 'modelI[dD]|model_id|model_name|model_type|model_version' | head -3)
    report "$f 调用 Runway invoke 时传了 \"model\" 字段（模型由 api-key 在网关侧绑定，不要传）:"
    echo "$HIT" | sed 's/^/    /' >&2
  fi
  # temperature 字段（Opus 4.x 已废弃）
  if grep -nE '["'"'"']temperature["'"'"']\s*:' "$f" 2>/dev/null | head -3 | grep -q .; then
    HIT=$(grep -nE '["'"'"']temperature["'"'"']\s*:' "$f" 2>/dev/null | head -3)
    report "$f 调用 Runway invoke 时传了 \"temperature\" 字段（Opus 4.x / Claude 4 已废弃，会被包成 200 OK 业务错）:"
    echo "$HIT" | sed 's/^/    /' >&2
  fi
done

# ---- 6. 必须有 200 OK 业务错检查 ----
if [ -n "$INVOKE_FILES" ]; then
  MISSING_BIZ_ERR=""
  for f in $INVOKE_FILES; do
    # data.Code || data.Error / data["Code"] / .get("Code") / data.get("Error") 都算
    if ! grep -qE '\.Code\b|\["Code"\]|\.get\(["'"'"']Code["'"'"']\)|\.Error\b|\["Error"\]|\.get\(["'"'"']Error["'"'"']\)' "$f" 2>/dev/null; then
      MISSING_BIZ_ERR="$MISSING_BIZ_ERR $f"
    fi
  done
  if [ -n "$MISSING_BIZ_ERR" ]; then
    report "下列文件调 Runway invoke 但缺 200 OK 业务错检查（data.Code / data.Error）:"
    for f in $MISSING_BIZ_ERR; do echo "    $f" >&2; done
    echo "    必加：if (data.Code || data.Error) throw new Error(...)" >&2
  fi
fi

# ---- 7. base_url 不能再拼 /openai/ ----
hits=$(grep -rnIE '\$\{[^}]*base_?url[^}]*\}/openai/|\+\s*["'"'"']/openai/|\.base_url\s*\+\s*["'"'"']/openai' \
  --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
  --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | head -5 || true)
if [ -n "$hits" ]; then
  report "ai.base_url 已含 /openai 前缀，重复拼会双前缀 404:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# ---- 8. ai.properties key 必须带 ai. 前缀 ----
# 反例：props["base_url"] 而不是 props["ai.base_url"]
hits=$(grep -rnIE '(props|properties|config)\[\s*["'"'"'](base_url|api_key)["'"'"']\s*\]' \
  --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
  --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | grep -vE 'ai\.base_url|ai\.api_key' \
  | head -5 || true)
if [ -n "$hits" ]; then
  report "读 ai.properties 缺 ai. 前缀（应 props[\"ai.base_url\"] / props[\"ai.api_key\"]）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项 AI 调用违反 - 详见 transform_prompt.md § 五" >&2
  exit 1
fi
echo "[OK] AI 调用符合 Runway Bedrock 协议"
