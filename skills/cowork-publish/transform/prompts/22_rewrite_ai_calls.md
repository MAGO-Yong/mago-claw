# 任务：把所有文本 LLM 调用迁到 Runway Bedrock

（系统约束已在上面前置注入；以下是本次原子任务）

## 你的唯一目标

把工程里所有**文本对话模型**调用统一改成走 Runway Bedrock InvokeModel。

**不要动**图像 / 视频 / 语音 / Embedding / vision-only 模型相关代码——保留原样。

## 端点 / 协议

| 项 | 值 |
|---|---|
| 非流式 | `POST {ai.base_url}/bedrock_runtime/model/invoke` |
| 流式 | `POST {ai.base_url}/bedrock_runtime/model/invoke-with-response-stream`（**换 URL，不是请求体加 stream:true**） |
| 鉴权 | `token: <api_key>` header（同时附 `api-key:` 兼容旧版） |
| 请求体 | Anthropic Messages 格式：`anthropic_version: "bedrock-2023-05-31"` + `max_tokens` + `messages` |
| `system` | **顶级字段**，不要塞 messages |
| `model` | **不要传**（由 api-key 在网关侧绑定） |
| `temperature` | **不要传**（Opus 4.x 已废弃，传了会被包成 200 OK 业务错） |
| `max_tokens` | 中文 JSON 输出至少 8000；启用 thinking 至少 16000 |

## 配置读取

`ai.properties` 格式（平台注入）：
```
ai.base_url=https://runway.devops.rednote.life/openai
ai.api_key=<在 Runway 平台申请>
```

读取代码：
- key 必须带 `ai.` 前缀（`props["ai.base_url"]` / `props["ai.api_key"]`）
- `base_url` 已含 `/openai`，**不要再拼** `/openai/`（双前缀 → 404）
- Next.js standalone：`process.chdir(__dirname)` 把 cwd 切到 `.next/standalone/`，`path.resolve(cwd, 'ai.properties')` 永远 404；要搜多个候选路径

## 必须的防御代码

### 1. 200 OK 业务错（必加）

Runway 把上游错误包成 200 OK + `{"Code":..., "Error":"..."}`：

```js
const data = await r.json();
if (data?.Code || data?.Error) {
  throw new Error(`upstream business error: ${data.Error || data.Code}`);
}
// 再正常解析 content
```

### 2. 响应解析

- 非流式：`content[].text` 拼接（过滤 `block.type === "text"`）；`usage.input_tokens` / `usage.output_tokens`
- 流式：每行 `{"chunk":{"bytes":"<b64>"}}` → base64 解码 → Anthropic 事件 JSON（关注 `content_block_delta.delta.type === "text_delta"`）

## 必须删的

- `package.json` 移除：`openai` / `anthropic` / `@anthropic-ai/sdk` / `zhipuai` / langchain 文本 provider
- `requirements.txt` 移除：上述同名包
- 移除直连 `/v1/chat/completions` / `/v1/messages` / `/v1/responses` / Vertex `/google/...` 等 endpoint

## 多用途 SDK 处理

`google-generativeai` / `dashscope` 等同时支持文本 + 图像/视频的 SDK：
- 工程**仅文本** → 删 SDK
- 工程**还有非文本调用** → 保留 SDK，**只把文本调用点迁过来**

## 验证（语义验证较弱，外层只做依赖清单 grep）

请你最后输出一段 **AI 调用覆盖范围声明**：
- 已迁移：列出每个调用点的旧 endpoint / SDK → 新 Runway Bedrock 路径
- 未替换：列出每个图像/视频/语音/embedding 的调用点 + 模型类型 + 走的原生 endpoint
