# guard-transform 故障排查 (Seal IDE 版，按 stage 编号)

本文档按 8 个 stage 的失败现象给出根因定位 + 修复路径。读到 `.guard-transform-<name>-guard/transform.log` 末尾报错时按此表 routing。

> **共用约定**：所有过程产物在源工程同级的 `.guard-transform-<name>-guard/` 目录里；`<work>` 指改写副本目录（同名加 `-guard` 后缀）；`<state>` 指上述 `.guard-transform-*-guard/` 状态目录。

---

## skill 构建 / 上传问题

| 现象 | 根因 | 修复 |
|---|---|---|
| `bash build.sh` 报 `guard-transform 工具不完整：缺少 ...` | build.sh 没在 `skills/seal/` 目录下，或 `core/` 同级目录缺失 | 确保用源仓库内的脚本：`bash <repo>/skills/seal/build.sh`，并确认 `<repo>/core/` 完整 |
| 上传 zip 后 Seal IDE 没识别 skill | zip 包结构不对 / SKILL.md 缺失 | 重新跑 `bash <repo>/skills/seal/build.sh`，用 `unzip -l <repo>/skills/seal/dist/cowork-app-latest.zip` 检查包内有 `cowork-app/SKILL.md` |
| 上传 zip 后 transform 跑起来报"找不到 prompts/..." | 旧 zip 缓存 / zip 没包含 `core/` 实现层 | 手动清理 `<repo>/skills/seal/dist/` 目录（或单独删旧 zip 文件），再 `bash <repo>/skills/seal/build.sh` 重 build 重传 |
| 在 Seal IDE 里跑 transform 报 `command not found: codewiz-cc` | seal backend 依赖 codewiz-cc CLI，但宿主里没装 | 让用户在 Seal IDE 里确认 codewiz-cc 已就绪，或改用其他 backend（见 SKILL.md） |

---

## stage 00 - prepare（准备工作副本）

| 现象 | 根因 | 修复 |
|---|---|---|
| `[FAIL] 源目录不存在` | 路径写错 / 相对路径未生效 | 用绝对路径，且确认拼写 |
| `[FAIL] 权限不足` | 父目录不可写（如 `/opt/...`） | 先 `chmod` 或换到用户可写的路径 |
| `[FAIL] 副本已存在但不是 git repo` | 上次中断留下的脏目录 | `bin/guardx clean <src> -y` 后重跑 |

---

## stage 10 - detect（栈识别）

| 现象 | 根因 | 修复 |
|---|---|---|
| `framework: unknown` | 检测规则没覆盖（`detect_rules.json`） | 看 `<state>/stack.json`，手动改 framework 字段 + `--from-stage 20` 续跑 |
| 识别错（如把 monorepo 识成单仓） | profile 评分模糊 | 同上：直接改 stack.json 后跳过 detect 续跑 |
| `[FAIL] no profile matched` | 当前栈不在内置 profile 里 | 在 `profiles/` 下加 profile，或挑最接近的 profile 在 stack.json 里硬写 |

---

## stage 20 - rewrite（LLM 改写）⚡ 最容易出问题

| 现象 | 根因 | 修复 |
|---|---|---|
| `claude: command not found` | claude CLI 未装 / nvm 切了 node 版本 | `npm i -g @anthropic-ai/claude-cli`，或 `nvm use` 回原 node 版本 |
| `claude` 鉴权失败 / 401 | OAuth token 过期 | `claude login` 重新登录 |
| `claude` 超时 / 长时间无心跳 | 模型慢或网络抖动 | seal skill 默认已 1800s 超时；如仍不够：`export GUARD_LLM_TIMEOUT=3600 GUARD_LLM_HEARTBEAT=300; source $GUARD_TRANSFORM_HOME/default_env.sh; transform.sh --resume` |
| LLM 没改文件 | tool denied / 权限交互被拒 | `cat <state>/llm-*.log` 看具体被拒哪个 tool；transform.sh 已默认带 `--dangerously-skip-permissions` |
| LLM 改了但漏改关键文件 | prompt 第 N 段不准 | 看 `<state>/_retry-*.md`，找漏的部分；自动 retry 已 ≤3 次。**用户**可主动换更强后端再续跑（**agent 不会替你切**，避免悄悄换模型）：`export GUARD_LLM=codewiz GUARD_LLM_MODEL='codewiz/Claude-4.6-opus(thinking)'` → `source $GUARD_TRANSFORM_HOME/default_env.sh` → `transform.sh <src> --resume` |
| LLM 反复同样的错 | autofix 死循环 | `--autofix-max 3` 限次或 `--no-autofix` 直接看原错 |
| 想跳过 LLM 调试流水线骨架 | — | `--skip-llm`；或显式覆盖默认 `export GUARD_LLM=mock; SKIP_LLM=1 transform.sh ...` |

诊断命令：
```bash
# 看本轮 LLM 真正读到的 prompt
ls -lt <state>/_retry-*.md | head
# 看 LLM 真改了哪些文件
cat <state>/llm-*.log
# 看改写历史（每次 LLM 调用都自动 git commit）
cd <work> && git log --oneline
cd <work> && git show <commit>
```

---

## stage 30 - render（模板渲染）

| 现象 | 根因 | 修复 |
|---|---|---|
| 缺端口 / start.sh 没有 `0.0.0.0:3000` | 模板渲染脚本 bug 或 stack.json 没标对端口 | `cat <work>/start.sh`；改完模板后 `--from-stage 30 --resume` |
| db.properties 字段不全 | 工程类型没识别为 has_db | 改 `<state>/stack.json` 的 `has_db: true` 后 `--from-stage 30` |
| Decrypted-Userinfo 中间件未注入 | profile 没标 `needs_sso: true` | 同上改 stack.json |

---

## stage 40 - build（构建）

| 现象 | 根因 | 修复 |
|---|---|---|
| `npm install` 失败 / 拉不到包 | 网络 / 私有源 token 过期 | 进 `<work>` 手工跑 `npm install` 复现，按真实报错处理 |
| `npm run build` TypeScript 报错 | LLM 改写引入了类型错误 | 看 `<state>/build-*.log`；可 `--autofix-max 20 --resume` 让 LLM 自愈 |
| `pip install` 失败 | requirements 与 base image 冲突 | 同上，先复现具体冲突 |

诊断命令：
```bash
cd <work> && npm install && npm run build      # 复现 Node 工程
cd <work> && pip install -r requirements.txt   # 复现 Python 工程
```

---

## stage 50 - smoke_test（烟测 + 18+ verifier）

| 现象 | 根因 | 修复 |
|---|---|---|
| `verify_port_3000` 失败 | 应用未起在 0.0.0.0:3000 | 复跑：`cd <work>; bash $GUARD_TRANSFORM_HOME/verifiers/verify_port_3000.sh .` |
| `verify_db_properties` 失败 | 6 个标准 key 缺失 | 看 `<work>/conf/db.properties`，对照 README 的 PG 配置规范补齐 |
| `verify_health_endpoint` 超时 | 应用启动慢或 health 路径不对 | 看 `<state>/smoke-*.log`；调整 health 路径或加大超时 |
| `verify_no_url_absolute` 拦到 HTML `href="/foo"` | ⚠️ **verifier 旧版 bug**：与规范 `prompts/23_fix_paths.md §2` 冲突——规范明确说 HTML 里 `<a href="/foo">` 保留 `/`，由 router 注入前缀。verifier 已修复为只拦 `href="http://..."` / `href="//host/..."` 这两类真违规 | 升级到本仓库新版 `verifiers/verify_no_url_absolute.sh` 即可；若仍复现说明你的 skill 安装目录是旧版，需 `bash <repo>/skills/seal/build.sh` 后在 Seal IDE 里重传 zip 重装 |
| `verify_no_url_absolute` 拦到 `href="http://..."` / `src="//cdn..."` | 真违规：协议头硬编 / 内部 host 硬编 | 改 `<work>` 副本里对应的 HTML 模板，去掉 `http://` 协议头，保留裸路径 `/foo`；router 会自动注入正确的前缀和协议 |
| 单个 verifier 偶发失败 | 端口被占等环境问题 | `--resume` 重跑；持续失败请按上面的复跑命令本地执行看真错 |
| 全部 verifier 都失败 | 副本根本没起来 | `cd <work>; bash start.sh` 手工启动看输出 |

**带伤通过**（仅调试用，正式产出不要用）：
```bash
GUARD_STRICT=0 transform.sh <src> --resume    # 或 --no-strict
```

---

## stage 60 - package（打 zip）

| 现象 | 根因 | 修复 |
|---|---|---|
| zip 体积超大 | node_modules / dist 未被 ignore | 检查 `<work>/.guardignore`（如有）；补排除规则后 `--from-stage 60` |
| 缺关键文件 | 打包白名单错 | 看打包阶段 stdout，确认包含的根级条目 |

---

## stage 70 - report（生成 report.md）

stage 70 几乎不会失败。如果它报错通常是磁盘满或权限问题。

---

## 跨 stage 通用诊断

| 想看什么 | 怎么看 |
|---|---|
| 跑到哪一步了 | `tail -f <state>/transform.log` |
| 每个 stage 的耗时 | `cat <state>/checklist.tsv` |
| LLM 用量 / 调用次数 | `cat <state>/llm-*.log \| grep -c '^==='` |
| 某个 verifier 单独再跑 | `cd <work>; bash $GUARD_TRANSFORM_HOME/verifiers/verify_xxx.sh .` |
| 整个工程从头再来 | `bin/guardx clean <src> -y && transform.sh <src>` |
| 不调 LLM 看流水线骨架 | `transform.sh <src> --skip-llm` |

---

## 还是搞不定？升级 routing

按下面顺序试（**前 3 步保持当前 claude 模型；只有第 4 步是用户主动换后端**）：

1. **加大 autofix**：`--autofix-max 20 --resume`（claude CLI 当前是哪个模型就一直用那个）
2. **去 transform 工具仓库提 issue**：带上：
   - `<state>/transform.log` 末尾 100 行
   - `<state>/stack.json`
   - 失败 stage 对应的 `<state>/<stage>-*.log`
3. **手工接管**：进 `<work>` 自己改完、自己 build；然后跑 `bin/guardx verify <src>` 单独验证 → 跑 `--from-stage 60` 直接打包
4. **用户主动换更强后端 / 模型**（覆盖 default_env.sh 的 claude 默认；**agent 不会替你做这一步**）：
   ```bash
   export GUARD_LLM=codewiz
   export GUARD_LLM_MODEL='codewiz/Claude-4.6-opus(thinking)'
   source "$GUARD_TRANSFORM_HOME/default_env.sh"   # 用户值优先
   "$GUARD_TRANSFORM_HOME/transform.sh" <src> --resume
   ```

> **不要做**：
> - 不要用 `apply_diff` 直接改 `<work>` 副本里 LLM 改写的文件，会跟下次 `--resume` 冲突
> - 不要自己手动删除 `.guard-transform-*-guard/` 目录，状态丢了 `--resume` 也救不回来；用 `bin/guardx clean` 让工具自己清
> - 不要长期开 `--no-strict` / `GUARD_STRICT=0`，那只是把错误降级为 warn，问题还在
