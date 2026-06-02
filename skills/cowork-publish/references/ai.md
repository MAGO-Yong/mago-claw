# AI 调用（Runway 网关）

> **何时读**：**加任何 AI 调用前必读**。**禁止直接调 anthropic/openai/google SDK**——必须走 Runway 网关。文本走 Bedrock（Anthropic Messages 协议）；图像走 Google GenerateContent（Gemini Nano Banana）。注意 Runway 返 200 OK 但 finishReason=SAFETY 是真失败。
>
> 本文从官方 `ai-demo-platform-guard-transform-skill/subapp-spec/CLAUDE.md` 拆分而来。

## 7. AI 调用（Runway 网关）

### 7.1 `ai.properties` 格式（最多 4 个 key）

**文件位置**（同 `db.properties`）：

- **物理路径**：**与 `install.sh` 完全同级**，即 `<zip 解压根>/ai.properties`（**不是** `conf/ai.properties`）
- **平台运行时注入**：你不在 zip 里带，不 commit 到 git，已被 `.gitignore` 屏蔽
- **业务读取**：相对路径 `"ai.properties"`（start.sh 已 `cd "$(dirname "$0")"`）
- **没用 AI**：平台可不注入这个文件，业务代码加载时要容错（文件不存在 = 没启用 AI 功能）

文件内容：

```properties
# 文本（必填，调 LLM 才需要）
ai.base_url=https://runway-internal.xxx
ai.api_key=xxx-text-key

# 图像（仅图像生成时填；与文本完全独立计配额，禁止 fallback）
ai.image_base_url=https://runway-internal.xxx
ai.image_api_key=xxx-image-key
```

**严禁** `ai.image_api_key or ai.api_key` 这种 fallback（verifier `verify_image_calls.sh` 会扫）。缺图像 key 时应返回 503，不要拿文本 key 凑数。

### 7.2 文本：Runway Bedrock（Anthropic Messages 协议）

```python
# ✅ 标准请求
import httpx

resp = httpx.post(
    f"{ai_base_url}/bedrock_runtime/model/invoke",
    headers={
        "token": ai_api_key,          # ⚠️ 是 token: 不是 Authorization: Bearer
        "Content-Type": "application/json",
    },
    json={
        "anthropic_version": "bedrock-2023-05-31",   # ⚠️ 固定值
        "max_tokens": 4096,
        "messages": [
            {"role": "user", "content": "你好"}
        ],
        # ❌ 不要传 model（模型由 api_key 在网关侧绑定）
        # ❌ 不要传 temperature / top_p（网关不接受）
    },
    timeout=60,
)
data = resp.json()

# ⚠️ Runway 是 200 OK 返业务错，必须显式检查
if data.get("Code") or data.get("Error"):
    raise RuntimeError(f"AI call failed: {data}")

text = data["content"][0]["text"]
```

```javascript
// ✅ Node fetch
const resp = await fetch(`${aiBaseUrl}/bedrock_runtime/model/invoke`, {
  method: 'POST',
  headers: {
    'token': aiApiKey,                 // ⚠️ token: 不是 Authorization
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    anthropic_version: 'bedrock-2023-05-31',
    max_tokens: 4096,
    messages: [{ role: 'user', content: 'hello' }],
    // ❌ 不传 model / temperature
  }),
})
const data = await resp.json()
if (data.Code || data.Error) throw new Error(`AI failed: ${JSON.stringify(data)}`)
const text = data.content[0].text
```

**禁项**（verifier `verify_ai_calls.sh` 会扫）：

- ❌ 用 `openai` / `@anthropic-ai/sdk` / `langchain` / `litellm` 等 SDK 直连（必须走 Runway 网关）
- ❌ 直连 `api.openai.com` / `api.anthropic.com` / `generativelanguage.googleapis.com`
- ❌ 用 `Authorization: Bearer xxx`（Runway 用 `token: xxx`）
- ❌ 请求体传 `model` / `temperature` / `top_p`
- ❌ 漏 `anthropic_version: "bedrock-2023-05-31"`
- ❌ 漏 `if (data.Code || data.Error) throw`（200 OK 业务错没人发现）

### 7.3 图像：Runway Google GenerateContent（Gemini Nano Banana）

```python
# ✅ 图像生成（注意：与文本是不同 endpoint、不同 header、不同协议）
resp = httpx.post(
    f"{ai_image_base_url}/google/v1:generateContent",
    headers={
        "api-key": ai_image_api_key,   # ⚠️ 图像是 api-key: 不是 token:
        "Content-Type": "application/json",
    },
    json={
        "contents": [{
            "role": "user",
            "parts": [{"text": "一只猫"}],
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],   # ⚠️ 必须，否则只返文本
            "maxOutputTokens": 32768,                  # ⚠️ 不能是 1024（base64 必截断）
        },
        # ❌ 不要传 model
    },
    timeout=120,
)
data = resp.json()
if data.get("Code") or data.get("Error"):
    raise RuntimeError(f"image gen failed: {data}")

# ⚠️ 必须检查 finishReason（SAFETY/RECITATION/PROHIBITED_CONTENT 也以 200 返）
candidate = data["candidates"][0]
reason = candidate.get("finishReason")
if reason and reason not in ("STOP", "MAX_TOKENS"):
    raise RuntimeError(f"image gen rejected: {reason}")

# 抽 base64
for part in candidate["content"]["parts"]:
    if "inlineData" in part:
        b64 = part["inlineData"]["data"]
        # → 落 PG LO
```

**图像调用专属禁项**：

- ❌ header 用 `token:`（文本通路，与图像不互通）
- ❌ 缺 `responseModalities: ["TEXT","IMAGE"]`（Gemini 默认只返文本）
- ❌ `maxOutputTokens: 1024`（图像 base64 至少几十 KB）
- ❌ 缺 `finishReason` 检查
- ❌ 用 `stability-sdk` / `dashscope` / `replicate` / `midjourney` 等图像 SDK
- ❌ `image_base_url` 已含 `/openai` 时再拼 `/openai/`（双前缀 404）
- ❌ 读 props 时 key 缺 `ai.` 前缀（必须 `props["ai.image_base_url"]`）

### 7.4 配置加载示例

```python
def load_ai():
    props = {}
    with open("ai.properties") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            k, _, v = line.partition("=")
            props[k.strip()] = v.strip()
    return props

ai = load_ai()
TEXT_BASE = ai["ai.base_url"]
TEXT_KEY  = ai["ai.api_key"]
IMG_BASE  = ai.get("ai.image_base_url")  # 可能没配
IMG_KEY   = ai.get("ai.image_api_key")
if image_feature_enabled and not (IMG_BASE and IMG_KEY):
    raise RuntimeError("image AI not configured; 503")  # ❌ 不要 fallback 到 TEXT_*
```

---
