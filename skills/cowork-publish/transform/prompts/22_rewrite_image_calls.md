# 任务：把所有图像生成调用迁到 Runway Google GenerateContent（Gemini Nano Banana）

（系统约束已在上面前置注入；以下是本次原子任务）

## 你的唯一目标

把工程里所有**图像生成 / 编辑能力调用点**，无论原工程用什么模型 / SDK / 厂商，**一律改写为 Gemini Nano Banana 系**，统一走 Runway 网关 Google GenerateContent 协议。

**不要动**视频 / 语音 / Embedding / 纯 vision-only 理解（输入图、输出文本）相关代码——保留原样。

## 判别口径（看能力，不看模型名）

**必须迁移**（输出是新图）：
- 文本 → 图（text-to-image）
- 图 + 文本 → 图（编辑、修复、超分、风格迁移、背景替换、消除、放大、上色）
- 多张参考图合成 1 张

**不在迁移范围**（保留原样，相关 SDK 不删）：
- 视频生成（Sora / Runway Gen / 可灵 / Veo / Pika）
- 语音 / TTS / ASR（Whisper / ElevenLabs / Polly）
- Embedding / Rerank / 向量检索专用模型
- 纯 vision-only 理解（输入图、**输出文本而非新图**，如 OCR / 检测 / 分类 / VQA）

## 端点 / 协议

| 项 | 值 |
|---|---|
| endpoint | `POST {ai.image_base_url}/google/v1:generateContent` |
| 鉴权 header | `api-key: <ai.image_api_key>`（**不是** `Authorization: Bearer`；**不是**文本通路的 `token:`） |
| 请求体必填 | `contents`（含 `role` + `parts`）、`generationConfig.responseModalities: ["TEXT","IMAGE"]` |
| `maxOutputTokens` | **32768 起步**（图像 base64 必截断，不照搬文本侧 1024） |
| `safetySettings` | 四类（`HARM_CATEGORY_HATE_SPEECH` / `HARM_CATEGORY_DANGEROUS_CONTENT` / `HARM_CATEGORY_SEXUALLY_EXPLICIT` / `HARM_CATEGORY_HARASSMENT`）全填 `OFF` |
| `model` | **不传**——模型由 api-key 在网关侧绑定；URL 路径里**不带** `<model>:` 段 |
| 输入图片上限 | 单次最多 14 张组合到 1 张输出（Pro） |
| 响应 | `candidates[0].content.parts[]`：`{text: "..."}` 或 `{inlineData: {mimeType, data: "<base64>"}}` 混排 |

## 配置读取

`ai.properties` 格式（平台注入，图像字段独立）：
```
ai.base_url=https://runway.devops.rednote.life/openai
ai.api_key=<文本模型 key>
ai.image_base_url=https://runway.devops.rednote.life/openai
ai.image_api_key=<图像模型 key>
```

读取规则：
- key 必须带 `ai.` 前缀（`props["ai.image_base_url"]` / `props["ai.image_api_key"]`）
- `ai.image_base_url` 已含 `/openai`，**不要再拼** `/openai/`（双前缀 → 404）
- **严格独立读取**：图像调用**禁止** fallback 到 `ai.base_url` / `ai.api_key`；缺 `ai.image_*` 时 `is_image_enabled()` 返 False、`/api/image/*` 返 503
- Next.js standalone：同 § 五，用 `findPropertiesFile('ai.properties')` 搜多个候选路径

## 必须的防御代码

### 1. Runway 伪 200 错误（必加）

```python
if isinstance(data, dict) and (data.get("Code") or data.get("Error")):
    raise RuntimeError(f"upstream business error: {data.get('Error') or data.get('Code')}")
```

```js
if (result?.Code || result?.Error) {
  throw new Error(`upstream business error: ${result.Error || result.Code}`);
}
```

### 2. Gemini 自身拒绝（必加）

```python
cand = (data.get("candidates") or [{}])[0]
reason = cand.get("finishReason")
if reason and reason not in ("STOP", "MAX_TOKENS"):
    raise RuntimeError(f"image generation refused: finishReason={reason}")
parts = (cand.get("content") or {}).get("parts") or []
images = [p["inlineData"] for p in parts if "inlineData" in p]
if not images:
    raise RuntimeError("image generation returned no inlineData")
```

```js
const cand = (data.candidates || [])[0] || {};
const reason = cand.finishReason;
if (reason && reason !== "STOP" && reason !== "MAX_TOKENS") {
  throw new Error(`image generation refused: finishReason=${reason}`);
}
const images = (cand.content?.parts || []).filter(p => p.inlineData?.data);
if (!images.length) throw new Error("image generation returned no inlineData");
```

### 3. 响应解析

取图从 `candidates[0].content.parts[].inlineData.{mimeType, data}` 解 base64（**不是** OpenAI 风格的 `data[0].b64_json`，**不是** `data[0].url`）。

## 调用示例（Python httpx）

```python
import base64, httpx

props          = _load_properties("./ai.properties")
image_base_url = props["ai.image_base_url"].rstrip("/")
image_api_key  = props["ai.image_api_key"]

IMAGE_URL = f"{image_base_url}/google/v1:generateContent"
HEADERS   = {"api-key": image_api_key, "Content-Type": "application/json"}

SAFETY_OFF = [
    {"category": c, "threshold": "OFF"}
    for c in ("HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_DANGEROUS_CONTENT",
              "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_HARASSMENT")
]

# 文本 → 图
def generate_image(prompt: str, aspect_ratio: str = "1:1", image_size: str = "1K") -> bytes:
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 1,
            "maxOutputTokens": 32768,
            "responseModalities": ["TEXT", "IMAGE"],
            "topP": 0.95,
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": image_size,
                "imageOutputOptions": {"mimeType": "image/png"},
            },
        },
        "safetySettings": SAFETY_OFF,
    }
    r = httpx.post(IMAGE_URL, headers=HEADERS, json=body, timeout=180)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and (data.get("Code") or data.get("Error")):
        raise RuntimeError(f"upstream business error: {data.get('Error') or data.get('Code')}")
    cand = (data.get("candidates") or [{}])[0]
    reason = cand.get("finishReason")
    if reason and reason not in ("STOP", "MAX_TOKENS"):
        raise RuntimeError(f"image generation refused: finishReason={reason}")
    for p in (cand.get("content") or {}).get("parts") or []:
        inline = p.get("inlineData")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError("image generation returned no inlineData")

# 图 + 文本 → 图（编辑；多张参考图最多 14 张）
def edit_image(prompt: str, reference_images: list[tuple[str, bytes]]) -> bytes:
    parts = []
    for mime, content in reference_images[:14]:
        parts.append({"inlineData": {"mimeType": mime,
                                     "data": base64.b64encode(content).decode("ascii")}})
    parts.append({"text": prompt})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 1,
            "maxOutputTokens": 32768,
            "responseModalities": ["TEXT", "IMAGE"],
            "topP": 0.95,
        },
        "safetySettings": SAFETY_OFF,
    }
    r = httpx.post(IMAGE_URL, headers=HEADERS, json=body, timeout=180)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and (data.get("Code") or data.get("Error")):
        raise RuntimeError(f"upstream business error: {data.get('Error') or data.get('Code')}")
    cand = (data.get("candidates") or [{}])[0]
    for p in (cand.get("content") or {}).get("parts") or []:
        inline = p.get("inlineData")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError("edit returned no inlineData")
```

## 调用示例（Node fetch）

```js
const props = Object.fromEntries(
  fs.readFileSync("./ai.properties", "utf-8").split("\n")
    .filter(l => l && !l.startsWith("#"))
    .map(l => { const i = l.indexOf("="); return [l.slice(0, i).trim(), l.slice(i + 1).trim()]; })
);
const imageBaseUrl = props["ai.image_base_url"].replace(/\/$/, "");
const imageApiKey  = props["ai.image_api_key"];
const IMAGE_URL    = `${imageBaseUrl}/google/v1:generateContent`;
const HEADERS = { "api-key": imageApiKey, "Content-Type": "application/json" };

const SAFETY_OFF = [
  "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_DANGEROUS_CONTENT",
  "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_HARASSMENT",
].map(category => ({ category, threshold: "OFF" }));

function checkBusinessError(data) {
  if (data && (data.Code || data.Error)) {
    throw new Error(`upstream business error: ${data.Error || data.Code}`);
  }
}

function extractImage(data) {
  const cand = (data.candidates || [])[0] || {};
  const reason = cand.finishReason;
  if (reason && reason !== "STOP" && reason !== "MAX_TOKENS") {
    throw new Error(`image generation refused: finishReason=${reason}`);
  }
  for (const p of (cand.content?.parts) || []) {
    if (p.inlineData?.data) return Buffer.from(p.inlineData.data, "base64");
  }
  throw new Error("image generation returned no inlineData");
}

export async function generateImage(prompt, { aspectRatio = "1:1", imageSize = "1K" } = {}) {
  const r = await fetch(IMAGE_URL, {
    method: "POST", headers: HEADERS,
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 1, maxOutputTokens: 32768, topP: 0.95,
        responseModalities: ["TEXT", "IMAGE"],
        imageConfig: { aspectRatio, imageSize, imageOutputOptions: { mimeType: "image/png" } },
      },
      safetySettings: SAFETY_OFF,
    }),
  });
  const data = await r.json();
  checkBusinessError(data);
  return extractImage(data);
}

export async function editImage(prompt, referenceImages /* [{mime, bytes}] */) {
  const parts = referenceImages.slice(0, 14).map(({ mime, bytes }) => ({
    inlineData: { mimeType: mime, data: Buffer.from(bytes).toString("base64") },
  }));
  parts.push({ text: prompt });
  const r = await fetch(IMAGE_URL, {
    method: "POST", headers: HEADERS,
    body: JSON.stringify({
      contents: [{ role: "user", parts }],
      generationConfig: {
        temperature: 1, maxOutputTokens: 32768, topP: 0.95,
        responseModalities: ["TEXT", "IMAGE"],
      },
      safetySettings: SAFETY_OFF,
    }),
  });
  const data = await r.json();
  checkBusinessError(data);
  return extractImage(data);
}
```

## 必须删的

- `package.json` 移除（仅图像用途时）：`openai`（图像分支）/ `@google/genai` / `google-genai` / `stability_sdk` / `stability-sdk` / `replicate`（仅图像）/ `dashscope`（仅万相）/ `zhipuai`（仅图像）/ Midjourney 代理客户端包
- `requirements.txt` 移除（仅图像用途时）：`openai`（图像分支）/ `google-generativeai`（仅图像）/ `stability_sdk` / `replicate`（仅图像）/ `dashscope`（仅万相）/ `zhipuai`（仅图像）
- 移除原图像 endpoint 直连：`api.openai.com/v1/images/generations` / `generativelanguage.googleapis.com/.../<model>:generateContent` / `*-aiplatform.googleapis.com/.../<model>:generateContent` / `dashscope.aliyuncs.com/.../image-synthesis` / `api.stability.ai` 等

## 多用途 SDK 处理

`google-generativeai` / `dashscope` / `replicate` 等同时支持图像 + 视频/语音/文本的 SDK：
- 工程**仅图像** → 删 SDK
- 工程**还有非图像调用**（视频 / 语音 / 文本 / vision-only 理解）→ 保留 SDK，**只把图像调用点改 Runway 直调**

## 厂商特殊参数处理

以下厂商特有参数 Gemini 不支持，**直接丢弃**，不要试图映射：
- DALL·E：`style: "vivid"` / `style: "natural"` / `quality: "hd"` / `size: "1024x1024"`
- Stable Diffusion：`negative_prompt` / `cfg_scale` / `steps` / `sampler`
- 通义万相：`seed` / `style` / `n`（多图）
- Flux：`guidance` / `num_inference_steps`
- Midjourney：`--ar` / `--v` / `--style` 等参数

用自然语言在 prompt 里描述风格 / 反向意图，效果差异可接受。

## 图片产物落库

生成 / 编辑得到的图片是**业务数据**，按 § 四走 PG Large Object：
- `attachments` 表存 `mime` / `size_bytes` / `sha256` / `owner_id` / `content_oid` 元数据
- 返回前端是 `{ id, downloadUrl: "./api/attachments/<id>" }`（**不**直接吐 base64 给前端做持久化）
- 一次性预览允许返 dataURL，但**不入库 = 刷新即丢**，需告知用户

## 验证（语义验证较弱，外层只做依赖清单 grep）

请你最后输出一段 **AI 图像调用覆盖范围声明**：
- 已迁移：列出每个调用点的原 SDK / endpoint → 新 Runway Google GenerateContent 路径；显式列出丢弃的厂商特殊参数
- 未替换：列出每个视频 / 语音 / embedding / vision-only 理解的调用点 + 模型类型 + 走的原生 endpoint / SDK，显式标注"按当前策略保留原工程实现"
