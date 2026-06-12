# 任务：生成项目简述（project_brief.md）

（系统约束已在上面前置注入；以下是本次原子任务）

## 你的唯一目标

读取当前工程的源码，生成一份**精简的项目简述文件** `project_brief.md`，写到当前工作目录根下。

这份文件会被后续所有 LLM 改写任务（stage 20）自动拼入 prompt 前缀，**目的是让后续 LLM 不必从头 Glob/Read 全仓就能快速定位关键文件**，从而减少工具调用轮次和 token 消耗。

## 你必须做的事

1. 用 `Glob` / `Read` 扫描工程结构，重点读：
   - 根目录 `package.json` / `requirements.txt` / `pyproject.toml`（依赖清单）
   - monorepo 子目录的同名文件（`backend/`、`frontend/`、`server/`、`api/` 等）
   - 主入口文件（`src/index.ts` / `main.py` / `app.py` / `server.js` 等）
   - 配置文件（`.env.example` / `config/` 目录下的文件）
   - 数据库相关文件（`prisma/schema.prisma` / `models/` / `db/` / `migrations/`）
   - 中间件 / 路由文件（`middleware/` / `routes/` / `app/api/` 等）
   - AI 调用相关文件（含图像生成调用点）

2. 输出 `project_brief.md`，**严格按下面格式**，不要多写无关内容：

```markdown
# 项目简述（由 stage 10 自动生成，供后续 LLM 改写任务参考）

## 基本信息
- 语言/框架：<lang> / <framework>
- 工程结构：<单仓 | monorepo>
- 后端入口：<相对路径，如 backend/src/index.ts>
- 前端目录：<相对路径，如 frontend/，无则填"无">

## 关键文件索引（后续改写任务直接 Read 这些文件）
- 依赖声明：<package.json 或 requirements.txt 的相对路径>
- 主入口：<相对路径>
- DB 连接/初始化：<相对路径，如 src/db/index.ts，无则填"无">
- 文本 AI 调用：<相对路径列表，如 src/service/llm.ts，无则填"无">
- 图像 AI 调用：<相对路径列表，如 src/service/image.ts，无则填"无">
- SSO/认证中间件：<相对路径，无则填"无">
- 环境变量配置：<.env.example 或 config/ 相对路径>

## 技术栈信号（补充 shell 静态扫描可能漏掉的）
- has_db：<0|1>（理由：<一句话，如"src/db/index.ts 里有 new Pool(...)"，或"requirements.txt 有 psycopg2"，或"无 DB 相关代码">）
- has_ai：<0|1>（理由：<一句话，has_ai_text 或 has_ai_image 任一为 1 则填 1>）
- has_ai_text：<0|1>（理由：<一句话>）
  判断规则——以下任一条件满足即填 1：
  · 依赖里有文本对话 SDK（openai / anthropic / @anthropic-ai/sdk / zhipuai / langchain 等）
  · 代码里有文本 LLM 调用（chat completions / messages / bedrock_runtime / anthropic_version 等）
  · 代码里有 Runway Bedrock 调用（bedrock_runtime/model/invoke）
- has_ai_image：<0|1>（理由：<一句话>）
  判断规则——以下任一条件满足即填 1：
  · 依赖里有图像生成 SDK（openai 图像分支 / dashscope 万相 / stability_sdk / replicate / @google/genai / zhipuai 图像 / midjourney 代理等）
  · 代码里有图像生成调用（openai.images.create / ImageSynthesis.call / generateContent 含 responseModalities IMAGE / replicate.run 图像 model / nova-canvas / DALL·E / Flux / SD 等）
  · 代码里有 Runway Google GenerateContent 图像调用（/google/v1:generateContent）
  注意：纯 vision-only 理解（输入图、输出文本，如 OCR / VQA）不算图像生成，填 0
- has_sso：<0|1>（理由：<一句话>）
  判断规则——以下任一条件满足即填 1，**即使当前用 mock 实现也算**：
  · 已接入 Decrypted-Userinfo header（平台 SSO 标准方式）
  · 后端存在获取当前用户的 API 路由或函数（如 /api/me、/api/user/me、getCurrentUser、get_current_user、req.user、request.user、ctx.user、g.user 等）
  · 前端存在展示当前用户信息的 hook / 组件 / store（如 useUser、useCurrentUser、useAuth、useSession、userStore、authStore、user.name、user.avatar、user.nickname 等）
  理由示例："src/routes/user.ts 有 /api/me 路由（当前返回 mock 数据）"、"frontend/hooks/useUser.ts 展示用户头像（mock）"、"无任何用户身份相关代码"
- has_external_infra：<0|1>（理由：<一句话，如"package.json 有 ioredis"，或"无">）

## 图像 AI 调用详情（has_ai_image=1 时必填，否则填"无图像生成调用"）
- 原始方案：<原工程使用的图像生成方案，如 DALL·E 3 / 万相 / Stable Diffusion / Flux / Replicate / Midjourney 等>
- 调用文件：<相对路径列表>
- 调用方式：<SDK 名称 + 关键方法，如 openai.images.create / dashscope.ImageSynthesis.call>
- 厂商特殊参数：<原工程使用的厂商特有参数，如 DALL·E 的 style:vivid / SD 的 negative_prompt / 万相的 seed 等，改写时需丢弃>
- 图片落库方式：<原工程如何处理生成的图片，如"直接返回 URL"/"写本地磁盘"/"返回 base64"等>
- 改写注意：<针对本工程图像调用的特殊注意事项，如"图片编辑场景有多张参考图"/"有异步生成轮询逻辑"等>

## 改写注意事项（针对本工程的特殊情况）
<列出 1-5 条后续 LLM 改写时需要特别注意的点，没有就写"无特殊情况"。例如：>
- DB 连接在 src/db/pool.ts 里用了 f-string 拼 URL，需要改成结构化 API
- 文本 AI 调用分散在 3 个 service 文件里，需要逐一替换
- 图像生成用了 DALL·E 的 style:vivid 参数，改写时需丢弃（Gemini 不支持）
- 前端 Next.js standalone 模式，ai.properties 路径需要特殊处理
```

## 约束

- **不要**修改任何源码文件，只写 `project_brief.md`
- **不要**写超过 100 行——这是给 LLM 看的索引，不是给人看的文档
- 技术栈信号里的 `has_*` 字段：**只能填 0 或 1**，不能填"可能"/"不确定"
- 如果某个字段真的无法判断（如工程极度混乱），填 0 并在理由里说明"无法判断"
- 文件路径全部用**相对于工作目录根**的路径
- `has_ai_image=0` 时，"图像 AI 调用详情"一节填"无图像生成调用"即可，不要展开
- `has_ai_text` 和 `has_ai_image` 是独立字段，可以同时为 1（工程同时有文本和图像 AI 调用）
