# guard-transform 典型场景示例（Seal IDE 版）

本文档给出几种常见的 Seal IDE 调用本 skill 的完整对话样例，帮助你（codewiz-cc agent）在面对类似输入时知道该怎么响应。

---

## 场景 0：用户首次加载/构建 skill（zip 上传模式）

**用户**：构建 `~/Workspace/ai-platform/ai-demo-platform-guard-transform-skill` 的 seal skill。

**你应该**：

1. 验证路径下存在 `skills/seal/build.sh`：
   ```bash
   test -f ~/Workspace/ai-platform/ai-demo-platform-guard-transform-skill/skills/seal/build.sh && echo OK
   ```
2. 跑构建脚本：
   ```bash
   bash ~/Workspace/ai-platform/ai-demo-platform-guard-transform-skill/skills/seal/build.sh
   ```
3. 构建脚本最后会打印：
   ```
   [OK] zip 构建完成
        产物          : skills/seal/dist/cowork-app-<ts>.zip
        symlink       : skills/seal/dist/cowork-app-latest.zip
        ...
   ```
4. 给用户报告：
   > 已构建 guard-transform seal skill zip：`skills/seal/dist/cowork-app-latest.zip`。
   >
   > 下一步：
   > 1. 在 Seal IDE 里点 **Skills → 上传 zip**，选这个文件
   > 2. 上传完成后在 codewiz-cc 会话里说"把这个工程改成 CoWork 子应用"即可自动触发
   >
   > 默认 LLM 后端：`seal`（复用 codewiz-cc CLI），默认模型 `claude-4.6-sonnet-google`，如需切换见 SKILL.md。

**如果用户给的是仓库根目录之外的路径**（如只给了 `~/Workspace/ai-platform`）：

→ 自动拼上 `/ai-demo-platform-guard-transform-skill/skills/seal/build.sh` 即可，不用问用户。

**如果路径不存在或没找到 build.sh**：

> 在 `<path>` 下找不到 `skills/seal/build.sh`。请确认路径是否指向了 `ai-demo-platform-guard-transform-skill` 仓库根目录。

---

## 场景 1：第一次跑 transform（Next.js 全栈工程）

**用户**：帮我把 `~/code/my-nextjs-app` 改成 Guard 子应用部署 zip。

**你应该**：

1. 读 `~/.claude/skills/cowork-app/.guard_transform_home` 拿到 `$GUARD_TRANSFORM_HOME`
2. 跑 `python3 --version && command -v claude` 确认前置 OK
3. 先跑 detect：
   ```bash
   "$GUARD_TRANSFORM_HOME/bin/guardx" detect ~/code/my-nextjs-app
   ```
4. 读 `.guard-transform-my-nextjs-app-guard/stack.json`，告诉用户："识别到 Next.js 全栈，匹配 nextjs-fullstack profile，has_db=true，has_ai=false。是否继续？"
5. 用户确认后 source 默认环境（默认 claude 后端，可覆盖；详见 SKILL.md Step 2）+ 跑 transform：
   ```bash
   source "$GUARD_TRANSFORM_HOME/default_env.sh"
   "$GUARD_TRANSFORM_HOME/transform.sh" ~/code/my-nextjs-app
   ```
6. 跑完后读 `.guard-transform-my-nextjs-app-guard/report.md`，把 stage 状态 + AI 覆盖范围 + zip 路径告诉用户

---

## 场景 2：续跑（上次卡在 stage 50）

**用户**：上次跑到一半失败了，现在继续。

**你应该**：

1. 用 `list_files` 找当前目录下 `.guard-transform-*-guard/` 状态目录
2. 读 `<state_dir>/checklist.tsv` 看上次跑到哪一步
3. 给用户报告："上次 stage 50 (smoke_test) 失败，已完成的有 00/10/20/30/40。现在用 --resume 续跑会跳过这 5 个步骤。"
4. 跑：
   ```bash
   source "$GUARD_TRANSFORM_HOME/default_env.sh"
   "$GUARD_TRANSFORM_HOME/transform.sh" <源工程绝对路径> --resume
   ```

如果用户想从特定 stage 重跑：

```bash
source "$GUARD_TRANSFORM_HOME/default_env.sh"
"$GUARD_TRANSFORM_HOME/transform.sh" <src> --from-stage 50
```

---

## 场景 3：识别错栈，需要换 profile

**用户**：跑 detect 识别成 fastapi-only，但我这是 React + FastAPI monorepo。

**你应该**：

1. 让用户确认 monorepo 结构：`list_files` 看顶层是否有 `frontend/` `backend/` 之类目录
2. 检查 `$GUARD_TRANSFORM_HOME/profiles/` 下的 profile 选项
3. 告诉用户：
   > 我看到你的 monorepo 应该匹配 `react-fastapi-monorepo` profile。当前自动识别失败可能是 `is_monorepo` 信号不足。
   >
   > 临时方案：手动改 `.guard-transform-<名字>-guard/stack.json`，把 `framework` 改成 `react-spa`、加 `backend_framework: fastapi` `is_monorepo: true`，然后跑 `--from-stage 20` 跳过识别阶段。
   >
   > 长期方案：改 profile 匹配规则或 `detect_rules.json`，但这是工具升级，需要单独评审。

---

## 场景 4：纯验证已改写的工程

**用户**：我手动改了一份 work 副本，帮我跑 verifier 集合验证。

**你应该**：

1. 不要走完整 transform，直接跑：
   ```bash
   "$GUARD_TRANSFORM_HOME/bin/guardx" verify <源工程绝对路径>
   ```
2. 这个命令只跑 18+ 个 shell verifier，约 30 秒，不调 LLM、不改文件
3. 把 ok / fail 列表给用户，failed 的指向对应日志文件

---

## 场景 5：失败后 routing

**用户**：跑完了报错 stage 40 build 失败。

**你应该**：

1. 读 `.guard-transform-<名字>-guard/transform.log` 末尾确认是 stage 40
2. 读 `.guard-transform-<名字>-guard/build-*.log`（具体名字看日志里提示）
3. 通常是依赖问题，给用户 2 个选项（**始终保持 claude 当前模型，不要主动建议切后端**）：
   - 选项 A：手动进 `<work>` 目录跑 `npm install && npm run build` 复现，看具体报错
   - 选项 B：调高 autofix 次数：`--autofix-max 20 --resume`
4. 如果用户**主动**说"换更强模型再试"，告诉他："本 skill 默认锁 claude CLI 当前模型，要切后端请按 [`SKILL.md` Step 2 方式 1](SKILL.md#如何覆盖默认值) 自己 export 后再调起 skill；agent 不会替你切，避免悄悄换模型导致产物前后不一致。"

**不要**：

- 不要自己 `apply_diff` 去改 `<work>` 副本里的源码
- 不要直接加 `--no-strict` 跳过——那只是把错误降级为 warn，问题还在
- 不要为了"提升成功率"自动 `export GUARD_LLM=codewiz` / `export GUARD_LLM_MODEL=...` 切换底层模型——claude skill 的契约是"以 claude CLI 当前模型为准"，autofix 重试也跑同模型

---

## 场景 6：用户想跳过 LLM 自检流水线

**用户**：我先跑一下流水线骨架看看不调 LLM 能不能走通。

**你应该**：

```bash
# mock 模式：显式覆盖 default_env.sh 的 claude 默认（用户值优先）
export GUARD_LLM=mock
SKIP_LLM=1 "$GUARD_TRANSFORM_HOME/transform.sh" <合法样本路径>
```

或更简洁（不用动 GUARD_LLM）：

```bash
source "$GUARD_TRANSFORM_HOME/default_env.sh"
"$GUARD_TRANSFORM_HOME/transform.sh" <src> --skip-llm
```

跑完告诉用户："骨架走通，stage 20 LLM 调用被跳过，需要真改写时去掉 --skip-llm 重跑。"

---

## 场景 7：告诉用户清理状态目录

**用户**：磁盘空间不够了，帮我清理。

**你应该**：

1. 用 `list_files` 找当前目录所有 `.guard-transform-*-guard/` 目录
2. 列出每个目录的占用情况（如果方便）
3. 用 guard-transform 自带的 clean 命令：
   ```bash
   "$GUARD_TRANSFORM_HOME/bin/guardx" clean <源工程绝对路径> -y
   ```
   会删 `<work_dir>` + `<state_dir>`

**不要**自己直接删目录，让工具自己清理避免误删 state 之外的东西。

---

## 场景 8：用户想升级或卸载 skill

**用户**：guard-transform 工具更新了，我刚 git pull 过，帮我重新构建 zip。

**你应该**：

```bash
# 找到源仓库路径（用户给过的或从 git remote 推断）
bash <repo>/skills/seal/build.sh
# 提示用户在 Seal IDE Skills 面板里重新上传新 zip
```

**用户**：我不用了，删掉吧。

**你应该**：

> 在 Seal IDE 的 **Skills** 面板里删除 cowork-app skill 即可（zip 模式不在本地写文件，所以不需要清理任何目录）。
> 仓库内的 `skills/seal/dist/` 是本地构建产物，删除该目录可省空间。

---

## 场景 9：非交互模式（默认模式 — Linux / 容器 / CI / 远程 ssh）

**场景**：本 skill **默认就是非交互模式**——只要不是 macOS 桌面，且用户没显式 `export GUARD_INTERACTIVE=1`，全部按这个流程跑。典型情况：

- Claude 在 GitLab CI / Jenkins / GitHub Actions 上被脚本调起
- Linux 构建机 / Docker 容器里跑
- 通过 ssh 接到远程 Linux 服务器跑
- macOS 桌面但用户显式 `export GUARD_NONINTERACTIVE=1` 想完全不被打扰

**核心原则**：**不询问任何决策，按推荐方案自动执行；连续失败 3 次后 abort 让调用方介入**。详见 [`SKILL.md` 运行模式判定](SKILL.md#运行模式判定交互-vs-非交互)⚠️-必读 章节。

### 完整流程

**用户（可能是 CI 脚本，也可能是 Linux 上的开发者）**：把 `/builds/my-app` 改成 Guard subapp。

**你应该**：

1. **判定运行模式**（默认非交互，仅 macOS 或显式 `GUARD_INTERACTIVE=1` 才交互）：
   ```bash
   if [ "${GUARD_NONINTERACTIVE:-0}" = "1" ]; then
       GUARD_RUN_MODE=non-interactive
   elif [ "${GUARD_INTERACTIVE:-0}" = "1" ]; then
       GUARD_RUN_MODE=interactive
   elif [ "$(uname -s)" = "Darwin" ]; then
       GUARD_RUN_MODE=interactive
   else
       GUARD_RUN_MODE=non-interactive
   fi
   echo "[guard-skill] 运行模式: $GUARD_RUN_MODE"
   ```
   → 在 Linux 上 `uname -s` = `Linux` → 非交互模式（默认）

2. **跑 detect**，读 `stack.json` **直接进入 transform，不再问"是否继续"**：
   ```bash
   "$GUARD_TRANSFORM_HOME/bin/guardx" detect /builds/my-app
   # 把识别结果写到 stdout 让调用方/CI 日志留痕，但不阻塞
   cat /builds/.guard-transform-my-app-guard/stack.json
   ```

3. **跑 transform，强制带 `-y`**（防止 transform.sh 内部读 stdin 卡死）：
   ```bash
   source "$GUARD_TRANSFORM_HOME/default_env.sh"
   "$GUARD_TRANSFORM_HOME/transform.sh" /builds/my-app -y
   ```

4. **失败时按非交互 routing 自动重试 ≤2 次后 abort，全程锁同一 claude 模型**（参考 [`SKILL.md` Step 5 非交互分支](SKILL.md#非交互模式服务端--ci--不要询问用户按下面优先级自动执行)）：
   - 第 1 次失败 → `transform.sh /builds/my-app --resume --autofix-max 20`
   - 第 2 次失败 → **同模型再 resume 一次**：`transform.sh /builds/my-app --resume --autofix-max 20`（**不切 codewiz、不换 opus**，claude CLI 当前是 4.7 就一直 4.7）
   - 第 3 次仍失败 → 输出 `transform.log` 末尾 200 行到 stderr，**退出非零**让调用方决策（是否人工换更强后端、加 fallback profile 等）

5. **成功后输出机器可读路径**（让调用方/CI 抓产物）：
   ```bash
   ZIP=$(ls -t /builds/my-app-guard-*.zip 2>/dev/null | head -1)
   REPORT=/builds/.guard-transform-my-app-guard/report.md
   echo "GUARD_OUTPUT_ZIP=$ZIP"
   echo "GUARD_OUTPUT_REPORT=$REPORT"
   ```

### 反例：非交互模式**绝对不要做**

| 反例 | 为什么不行 |
|---|---|
| detect 后输出"是否继续？"等用户回答 | 没人回答，命令卡死 |
| 跑 `transform.sh /builds/my-app`（不带 `-y`） | 已存在 checklist 时会读 stdin 询问 continue/reset，没 tty 直接读到 EOF abort |
| 失败后输出"想我做哪个？1/2/3" | 没人选，等同 fail |
| 失败 3 次后**自动**加 `GUARD_STRICT=0` 强行打包 | 会让带伤产物上线；严重违反规则 |
| 失败 3 次后**自动**加 `--skip-llm` 绕过 LLM 改写 | 产出未改造的副本，部署即翻车 |
| `claude` 鉴权 401 后还在重试 | 浪费 LLM 配额；应立即 abort 让运维改 token |
| 在 Linux 上想"用户体验更友好"主动改成 interactive 询问 | 违反默认非交互策略；用户想交互会自己 export GUARD_INTERACTIVE=1 |
| 第 1 次失败后**自动**切到 codewiz / opus / 其它后端"试试看" | claude skill 的契约就是"以 claude CLI 当前模型为准"；偷偷换会让 stage 20 的 LLM 改写跨模型不一致，autofix 重试也跑同模型 |

### CI 调用方接产物的最小示例

```bash
#!/usr/bin/env bash
# .gitlab-ci.yml 里的某个 job —— 注意默认就是非交互，不需要再额外 export 任何标志
set -e
# 让 Claude 跑本 skill（具体客户端 CLI 因平台而异）
output=$(claude-cli run-skill guard-transform --prompt "把 /builds/$CI_PROJECT_NAME 改成 Guard subapp")
zip_path=$(echo "$output" | grep '^GUARD_OUTPUT_ZIP=' | cut -d= -f2)
[ -f "$zip_path" ] || { echo "guard-transform 未产出 zip"; exit 1; }
# 上传到 artifact 仓 / 推送到 Guard 平台
curl -F "file=@$zip_path" https://guard.example.com/api/upload
```

### 在 macOS 桌面想要非交互（开发者本机长任务）

```bash
export GUARD_NONINTERACTIVE=1
# 之后所有 transform 调用都按非交互流程走，不打断开发者
```

---

## 触发关键词速查

下表是 description 里包含的高优先级触发词，看到就用本 skill：

| 中文 | 英文 |
|---|---|
| guard 子应用 / 子应用规范 | guard subapp |
| cowork guard | cowork guard |
| 转写成 / 改造成 / 转成 guard | convert to guard |
| 部署到 guard / guard 平台 | deploy to guard / guard platform |
| guard zip / 子应用 zip | guard zip / subapp zip |
| 跑 transform.sh / guardx | run transform / guardx |
| 8 个 stage / 8-stage 流水线 | 8-stage pipeline |
| 加载 / 安装 guard-transform skill | load / install guard-transform skill |
