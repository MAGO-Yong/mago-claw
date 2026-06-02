#!/usr/bin/env bash
# 验证：图像生成调用走 Runway Google GenerateContent（Gemini Nano Banana），无残留 SDK / endpoint / 错字段
# 详见 transform_prompt.md § 五.5 + § 十 checklist "AI 图像生成"组
#
# 检查项（仅当工程含图像生成信号时严格执行）：
#   1) 不能有原图像生成 SDK 残留（openai 图像分支 / dashscope 万相 / stability_sdk / replicate 图像 / @google/genai 图像 / zhipuai 图像 / midjourney 代理）
#   2) 不能有原图像 endpoint 直连（api.openai.com/v1/images / generativelanguage.googleapis.com / api.stability.ai 等）
#   3) 图像调用请求体必须含 responseModalities: ["TEXT","IMAGE"]
#   4) 图像调用请求体不能传 model 字段
#   5) maxOutputTokens 不能是 1024（图像 base64 必截断）
#   6) 必须有 200 OK 业务错检查（data.Code || data.Error）
#   7) 必须有 finishReason 检查（非 STOP/MAX_TOKENS 时抛错）
#   8) 图像配置从 ai.image_base_url / ai.image_api_key 读，不能 fallback 到文本字段
#   9) 鉴权用 api-key: header，不能用 token: 或 Authorization: Bearer

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

EXCLUDE='(node_modules|\.next/|dist/|build/|\.guard-transform|\.venv|venv/|__pycache__|\.test\.|\.spec\.|/test/|/tests/|__tests__|\.d\.ts$|README|CHANGELOG)'

# ---- 先决条件：是否有图像生成信号？----
USES_IMAGE_AI=0

# 标志 1：依赖里出现图像生成 SDK
for f in package.json apps/*/package.json packages/*/package.json backend/package.json; do
  [ -f "$f" ] || continue
  if grep -qE '"(openai|@google/genai|google-genai|stability-sdk|replicate|dashscope|zhipuai|midjourney)"' "$f" 2>/dev/null; then
    USES_IMAGE_AI=1; break
  fi
done
for f in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
  [ -f "$f" ] || continue
  if grep -qiE '^[[:space:]]*(openai|google-generativeai|google-genai|stability[_-]sdk|replicate|dashscope|zhipuai)([><=!~ ]|$)' "$f" 2>/dev/null; then
    USES_IMAGE_AI=1; break
  fi
done

# 标志 2：代码里有图像生成调用关键词
if grep -rqIE 'images\.(create|generate|edit)|ImageSynthesis\.call|generateContent|image_generation|imagegeneration|nova.canvas|text.to.image|image.synthesis|inlineData|responseModalities|ai\.image_base_url|ai\.image_api_key' . 2>/dev/null \
     --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
     --include='*.py' --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next \
     --exclude-dir=dist --exclude-dir=build --exclude-dir=.venv --exclude-dir=__pycache__; then
  USES_IMAGE_AI=1
fi

if [ "$USES_IMAGE_AI" = "0" ]; then
  echo "[OK] 工程未调用图像生成模型（跳过）"
  exit 0
fi

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# ---- 1. 残留图像生成 SDK 依赖 ----
# 注：openai / dashscope / replicate / google-generativeai 可能同时被文本/视频/语音用，
# 这里只检查"图像专用 SDK"；多用途 SDK 的图像调用点由检查项 2 覆盖
BANNED_IMAGE_NODE='"(stability-sdk|@stability-ai/sdk|midjourney|@midjourney/|nova-canvas)"'
for pkg in package.json apps/*/package.json packages/*/package.json backend/package.json; do
  [ -f "$pkg" ] || continue
  hits=$(grep -nE "$BANNED_IMAGE_NODE" "$pkg" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    report "$pkg 含图像专用 SDK（应整体迁到 Runway Google GenerateContent）:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
done

BANNED_IMAGE_PY='^[[:space:]]*(stability[_-]sdk|stability-sdk)([><=!~ ]|$)'
for req in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
  [ -f "$req" ] || continue
  hits=$(grep -niE "$BANNED_IMAGE_PY" "$req" 2>/dev/null | grep -vE '^\s*#' || true)
  if [ -n "$hits" ]; then
    report "$req 含图像专用 SDK:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
done

# ---- 2. 残留原生图像 endpoint ----
IMAGE_ENDPOINT_HITS=$(grep -rnIE \
  'api\.openai\.com/v1/images|v1/images/generations|v1/images/edits|generativelanguage\.googleapis\.com|aiplatform\.googleapis\.com|api\.stability\.ai|dashscope\.aliyuncs\.com.*image-synthesis|open\.bigmodel\.cn.*images' \
  --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
  --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | head -10 || true)
if [ -n "$IMAGE_ENDPOINT_HITS" ]; then
  report "残留原图像生成 endpoint（应改为 Runway Google GenerateContent）:"
  echo "$IMAGE_ENDPOINT_HITS" | sed 's/^/    /' >&2
fi

# ---- 3. 图像调用走了文本通路（bedrock_runtime）----
# 图像必须走 /google/v1:generateContent，不能走 /bedrock_runtime/model/invoke
IMAGE_FILES=$(grep -rlIE 'google/v1:generateContent|ai\.image_base_url|ai\.image_api_key|responseModalities.*IMAGE|inlineData' . 2>/dev/null \
               --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
               --include='*.py' --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next \
               --exclude-dir=dist --exclude-dir=build --exclude-dir=.venv --exclude-dir=__pycache__ || true)

# ---- 4. 图像调用请求体含 model 字段 ----
for f in $IMAGE_FILES; do
  if grep -nE '["'"'"']model["'"'"']\s*:' "$f" 2>/dev/null \
     | grep -vE 'modelI[dD]|model_id|model_name|model_type|model_version' | head -3 | grep -q .; then
    HIT=$(grep -nE '["'"'"']model["'"'"']\s*:' "$f" 2>/dev/null \
          | grep -vE 'modelI[dD]|model_id|model_name|model_type|model_version' | head -3)
    report "$f 图像调用传了 \"model\" 字段（模型由 api-key 在网关侧绑定，不要传）:"
    echo "$HIT" | sed 's/^/    /' >&2
  fi
done

# ---- 5. 缺 responseModalities: ["TEXT","IMAGE"] ----
if [ -n "$IMAGE_FILES" ]; then
  MISSING_MODALITIES=""
  for f in $IMAGE_FILES; do
    if ! grep -qE 'responseModalities|response_modalities' "$f" 2>/dev/null; then
      MISSING_MODALITIES="$MISSING_MODALITIES $f"
    fi
  done
  if [ -n "$MISSING_MODALITIES" ]; then
    report "下列文件调图像生成但缺 responseModalities（漏了 Gemini 默认只回文本，parts 里没有 inlineData）:"
    for f in $MISSING_MODALITIES; do echo "    $f" >&2; done
    echo '    必加：generationConfig.responseModalities: ["TEXT","IMAGE"]' >&2
  fi
fi

# ---- 6. maxOutputTokens 是 1024（图像 base64 必截断）----
if [ -n "$IMAGE_FILES" ]; then
  for f in $IMAGE_FILES; do
    if grep -nE 'maxOutputTokens\s*[=:]\s*1024\b|max_output_tokens\s*[=:]\s*1024\b' "$f" 2>/dev/null | head -3 | grep -q .; then
      HIT=$(grep -nE 'maxOutputTokens\s*[=:]\s*1024\b|max_output_tokens\s*[=:]\s*1024\b' "$f" 2>/dev/null | head -3)
      report "$f 图像调用 maxOutputTokens=1024（图像 base64 必截断，32768 起步）:"
      echo "$HIT" | sed 's/^/    /' >&2
    fi
  done
fi

# ---- 7. 必须有 200 OK 业务错检查 ----
if [ -n "$IMAGE_FILES" ]; then
  MISSING_BIZ_ERR=""
  for f in $IMAGE_FILES; do
    if ! grep -qE '\.Code\b|\["Code"\]|\.get\(["'"'"']Code["'"'"']\)|\.Error\b|\["Error"\]|\.get\(["'"'"']Error["'"'"']\)' "$f" 2>/dev/null; then
      MISSING_BIZ_ERR="$MISSING_BIZ_ERR $f"
    fi
  done
  if [ -n "$MISSING_BIZ_ERR" ]; then
    report "下列文件调图像生成但缺 200 OK 业务错检查（data.Code / data.Error）:"
    for f in $MISSING_BIZ_ERR; do echo "    $f" >&2; done
    echo "    必加：if (data.Code || data.Error) throw new Error(...)" >&2
  fi
fi

# ---- 8. 必须有 finishReason 检查 ----
if [ -n "$IMAGE_FILES" ]; then
  MISSING_FINISH=""
  for f in $IMAGE_FILES; do
    if ! grep -qE 'finishReason|finish_reason' "$f" 2>/dev/null; then
      MISSING_FINISH="$MISSING_FINISH $f"
    fi
  done
  if [ -n "$MISSING_FINISH" ]; then
    report "下列文件调图像生成但缺 finishReason 检查（SAFETY/RECITATION/PROHIBITED_CONTENT 等拒绝会以 200 返）:"
    for f in $MISSING_FINISH; do echo "    $f" >&2; done
    echo '    必加：if (reason && reason !== "STOP" && reason !== "MAX_TOKENS") throw ...' >&2
  fi
fi

# ---- 9. 图像配置不能 fallback 到文本字段 ----
FALLBACK_HITS=$(grep -rnIE \
  'image_api_key\s*\|\|\s*api_key|image_base_url\s*\|\|\s*base_url|image_api_key.*or.*api_key|image_base_url.*or.*base_url|get\(['"'"'"](ai\.image_api_key|ai\.image_base_url)['"'"'"]\s*,\s*[^)]+\)' \
  --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
  --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | head -5 || true)
if [ -n "$FALLBACK_HITS" ]; then
  report "图像配置 fallback 到文本字段（禁止：平台独立计配额，缺 ai.image_* 时必须 503）:"
  echo "$FALLBACK_HITS" | sed 's/^/    /' >&2
fi

# ---- 10. 鉴权 header 不能用 token: 或 Authorization: Bearer（图像走 api-key:）----
if [ -n "$IMAGE_FILES" ]; then
  for f in $IMAGE_FILES; do
    # 只检查"明显是图像调用"的文件里是否用了文本通路的 token: header
    if grep -nE '"token"\s*:\s*|token:\s*api_?key|"token":\s*image' "$f" 2>/dev/null \
       | grep -vE '(//|#)' | head -3 | grep -q .; then
      HIT=$(grep -nE '"token"\s*:\s*|token:\s*api_?key' "$f" 2>/dev/null | grep -vE '(//|#)' | head -3)
      report "$f 图像调用用了文本通路的 token: header（图像走 api-key:，两条链路不互通）:"
      echo "$HIT" | sed 's/^/    /' >&2
    fi
  done
fi

# ---- 11. ai.image_base_url 不能再拼 /openai/ ----
hits=$(grep -rnIE '\$\{[^}]*image_base_?url[^}]*\}/openai/|\+\s*["'"'"']/openai/|image_base_url\s*\+\s*["'"'"']/openai' \
  --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
  --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | head -5 || true)
if [ -n "$hits" ]; then
  report "ai.image_base_url 已含 /openai 前缀，重复拼会双前缀 404:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# ---- 12. ai.properties key 必须带 ai. 前缀 ----
hits=$(grep -rnIE '(props|properties|config)\[\s*["'"'"'](image_base_url|image_api_key)["'"'"']\s*\]' \
  --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' --include='*.mjs' --include='*.cjs' \
  --include='*.py' . 2>/dev/null \
  | grep -vE "$EXCLUDE" \
  | grep -vE 'ai\.image_base_url|ai\.image_api_key' \
  | head -5 || true)
if [ -n "$hits" ]; then
  report "读 ai.properties 图像字段缺 ai. 前缀（应 props[\"ai.image_base_url\"] / props[\"ai.image_api_key\"]）:"
  echo "$hits" | sed 's/^/    /' >&2
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项图像 AI 调用违规 - 详见 transform_prompt.md § 五.5" >&2
  exit 1
fi
echo "[OK] 图像 AI 调用符合 Runway Google GenerateContent 协议"
