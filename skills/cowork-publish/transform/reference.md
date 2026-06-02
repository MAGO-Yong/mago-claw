# cowork-app skill 参考索引

> 本文件是 Seal IDE skill 规范里的 `reference.md` —— **按需加载**的详细参考。
> 不必一开始就读，等 SKILL.md 把意图分发后，按下表对应跳转到具体子文档。

## 文档地图

| 子能力 | 何时读 | 文档 | 主要内容 |
| --- | --- | --- | --- |
| **项目转写** | 用户说"改成 / 转写成 cowork 子应用"、想跑 8 stage 流水线 | [`transform.md`](transform.md) | 完整 detect → LLM 改写 → 模板渲染 → build → 烟测 → 打包 → 报告流程、如何覆盖默认值、续跑、栈不识别的兜底 |
| **项目打包** | 用户手改完 `<src>-guard/` 后想重新打包、只想做"合规体检 + zip" | [`package.md`](package.md) | `cowork-package-verify` 用法、verify fail 三选一分流、前端构建产物 mtime 检查、最终 zip 产出位置 |
| **失败诊断** | 任一 stage 报错、不知道根因 | [`troubleshooting.md`](troubleshooting.md) | 按 stage 编号查根因 + 修复建议 + 续跑命令 |
| **使用示例** | 想看完整对话样例（安装 / Next.js / FastAPI / monorepo / 续跑） | [`examples.md`](examples.md) | 端到端的对话脚本，按典型场景索引 |

## 关键脚本（位于 `scripts/`）

> 所有脚本由 Seal 云端执行（zip 解压后），路径用 `$GUARD_TRANSFORM_HOME` 引用。
> `$GUARD_TRANSFORM_HOME` 由 [`scripts/default_env.sh`](scripts/default_env.sh) 自动推导 = scripts/ 自身。

| 脚本 | 作用 | 典型用法 |
| --- | --- | --- |
| [`scripts/transform.sh`](scripts/transform.sh) | 8 stage 流水线主入口 | `"$GUARD_TRANSFORM_HOME/transform.sh" <src> [-y] [--from-stage N]` |
| [`scripts/bin/guardx`](scripts/bin/guardx) | Python 入口（transform.sh 内部调起） | 一般不直接用；调试时 `"$GUARD_TRANSFORM_HOME/bin/guardx" verify <src>` |
| [`scripts/bin/cowork-package-verify`](scripts/bin/cowork-package-verify) | 打包前合规体检 | `"$GUARD_TRANSFORM_HOME/bin/cowork-package-verify" <src>` |
| [`scripts/bin/cowork-login-check`](scripts/bin/cowork-login-check) | LLM 后端登录预检 | `transform.sh` 启动时自动调；也可独立跑做诊断 |
| [`scripts/default_env.sh`](scripts/default_env.sh) | 默认环境变量（GUARD_LLM 等） | `source "$GUARD_TRANSFORM_HOME/default_env.sh"` |
| [`scripts/choose-model.sh`](scripts/choose-model.sh) | 交互式换模型（仅 macOS） | `"$GUARD_TRANSFORM_HOME/choose-model.sh"` —— Seal 云端 Linux 跑不起来，请改用 `--show` 或编辑 default_env.sh |

## 关键环境变量速查

> 完整版见 [`scripts/default_env.sh`](scripts/default_env.sh) 顶部注释；这里只列最常用的 6 个。

| 变量 | 默认值 | 作用 |
| --- | --- | --- |
| `GUARD_LLM` | `seal` | LLM 后端（CLI=`codewiz-cc`）。可选 `seal` / `claude` / `codewiz` / `qwen-code` / `codex` / `gemini` / `mock` |
| `GUARD_LLM_MODEL` | (空) | 一刀切模型 id；留空才能让分级路由生效 |
| `GUARD_LLM_MODEL_STRONG` | `claude-4.6-sonnet-google` | stage 20 跨文件大改写用的模型（非 thinking）。**seal 后端可用**：`claude-4.6-sonnet-google` |
| `GUARD_LLM_MODEL_FAST` | `claude-4.6-sonnet-google` | stage 10 brief / autofix 局部小修用的模型（非 thinking）。**seal 后端可用**：`claude-4.6-sonnet-google` / `claude-4.5-haiku-google` |
| `GUARD_PROFILE` | (空) | 一键预设：`server` 展开为「非交互 + LLM 自动修复 + 关重量级 smoke」 |
| `GUARD_RUN_MODE` | macOS=`interactive`，其它=`non-interactive` | 是否询问用户。`GUARD_INTERACTIVE=1` / `GUARD_NONINTERACTIVE=1` 可强制覆盖 |

## 覆盖优先级（从高到低）

1. **用户预先 `export`** 的同名变量（最高优先）
2. `GUARD_PROFILE=<name>` 预设展开（一键填一批服务端 / CI 场景的合理值）
3. 内置默认值（最低，仅作兜底）

实现细节：`default_env.sh` 全部用 `${VAR:=default}` 语义 —— "未设置或空才填"，已 `export` 的值永远赢。

## 关键边界（绝对不要做）

详见各子文档"危险操作"小节；这里只列**跨子能力共用**的 6 条红线：

1. ❌ 不要把 transform 内部的 8 stage 自己用 `codewiz-cc` 跑一遍 —— guard-transform 是确定性 Python pipeline
2. ❌ 不要修改 `scripts/prompts/*.md` / `scripts/verifiers/*.sh` / `scripts/templates/*.tpl` 来"绕过"失败
3. ❌ 不要伪造 stdout
4. ❌ 副本路径不要落在源工程目录下
5. ❌ 不要忽略 AI 模型覆盖范围声明（transform 跑完后 `report.md` 里这段必须给用户看）
6. ❌ 转写完成后不要继续把"再改一下 / 再打个 zip"解析到原工程路径 —— 必须切到 `<src>-guard/` 副本

## 设计哲学（深读）

- 完整设计文档：[`scripts/README.md`](scripts/README.md)
- 调用链路图、Python 重构架构、LLM CLI 抽象层都在这里
- Guard 子应用规范（2575 行权威定义）在源仓库 `transform_prompt.origin.md`，本 skill 不携带
