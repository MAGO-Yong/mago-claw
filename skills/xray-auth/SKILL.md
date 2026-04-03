---
name: xray-auth
description:
  管理 Xray 平台的登录鉴权，提供两项能力：（1）引导用户通过浏览器完成 OAuth 2.0 Device Flow
  登录并保存凭证；（2）为其他 skill 脚本提供非交互式 Token 获取接口（自动 refresh）。 当用户说"登录
  xray"、"xray auth"、"xray 鉴权"，或其他 skill 需要 XRAY_AUTH_TOKEN 时触发。
metadata:
  category: auth
  platform: xray
  trigger: login/token/auth/credentials
  input: [env]
  output: [access_token, credentials_file]
  impl: python-script
---

# Xray 鉴权（xray-auth）

> `{SKILL_DIR}` 为本 skill 所在目录的绝对路径，执行脚本时必须使用绝对路径。

## 概述

本 skill 提供两个脚本：

| 脚本                               | 场景                          | 交互性                                    |
| ---------------------------------- | ----------------------------- | ----------------------------------------- |
| `{SKILL_DIR}/scripts/auth.py`      | 用户首次登录或 token 彻底失效 | **交互式**（需用户打开浏览器授权）        |
| `{SKILL_DIR}/scripts/get_token.py` | 其他 skill 获取有效 token     | **非交互式**（自动读取/刷新，失败则报错） |

凭证保存路径：`~/.config/.xray-cli/xray-cli/<env>/credentials.json`（权限 0600）

## 支持的环境

| 环境   | 说明                                |
| ------ | ----------------------------------- |
| `sit`  | SIT 测试环境（**默认**）            |
| `prod` | 生产环境                            |
| `dev`  | 本地开发环境（需本地启动 SSO 服务） |

---

## 工作流程

### 场景一：用户登录

当用户说"登录 xray"、"xray
auth"或其他 skill 报告需要登录时，**必须后台启动脚本**，不得前台阻塞等待授权完成。

**第一步：后台启动，将 stdout+stderr 统一重定向到日志文件**

```bash
# 登录 SIT（默认）
python3 -u {SKILL_DIR}/scripts/auth.py > /tmp/xray.out 2>&1 &
AUTH_PID=$!

# 登录生产环境
python3 -u {SKILL_DIR}/scripts/auth.py prod > /tmp/xray.out 2>&1 &
AUTH_PID=$!
```

**第二步：等待授权 URL 出现，提取并展示给用户**

脚本启动后约 2 秒内会将授权 URL 写入日志，读取并提取：

```bash
sleep 2 && cat /tmp/xray.out
```

从输出中找到形如 `https://xray.devops.*.xiaohongshu.com/headless/activate?user_code=...`
的链接，**将完整 URL 展示给用户**，并告知：

> 请在浏览器中打开以下链接完成授权（链接 5 分钟内有效）： `<URL>` 完成后请告诉我，我将验证登录结果。

**第三步：用户确认后，检查登录结果**

```bash
# 等待后台进程结束（最多 60 秒）
wait $AUTH_PID
# 查看完整日志
cat /tmp/xray.out
```

日志末尾出现 `Logged in as ...` 表示登录成功；若进程已退出但未见成功信息，提示用户重新执行第一步。

**日志输出示例（/tmp/xray.out）：**

```
  Environment: sit
  Open this URL in your browser:
  https://xray.devops.sit.xiaohongshu.com/headless/activate?user_code=ABCD-1234&source=xray-cli
  (Code expires in 5 minutes)

  auth file has write in /Users/xxx/.config/.xray-cli/xray-cli/sit/credentials.json
  Logged in as user@xiaohongshu.com (sit)
```

**登录流程说明：**

1. 脚本向 SSO 请求 Device Code，打印授权 URL（写入 `/tmp/xray.out`）
2. 在有桌面环境的机器上自动打开浏览器（macOS / Linux with DISPLAY）
3. 用户在浏览器中完成登录授权
4. 脚本轮询 SSO Token 端点，获取 access_token 和 refresh_token
5. 凭证写入 `~/.config/.xray-cli/xray-cli/<env>/credentials.json`

### 场景二：其他 skill 获取 Token

当其他 skill 需要调用 Xray API 时，通过 `get_token.py` 获取有效的 access_token：

```bash
# 获取 access_token 字符串（最常用）
TOKEN=$(python3 {SKILL_DIR}/scripts/get_token.py --env sit)
export XRAY_AUTH_TOKEN=$TOKEN

# 获取完整 credentials JSON（含 refresh_token 和过期时间）
python3 {SKILL_DIR}/scripts/get_token.py --env sit --output json

# 通过环境变量指定 env（适合 CI/CD）
XRAY_ENV=prod python3 {SKILL_DIR}/scripts/get_token.py
```

**Token 自动刷新逻辑：**

```
读取 credentials.json
        │
        ▼
  access_token 有效？ ──是──→ 直接输出 token（退出码 0）
        │
       否
        │
        ▼
  用 refresh_token 请求新 token
        │
     ┌──┴──┐
   成功   失败
    │       │
    ▼       ▼
  保存新   输出错误（stderr）
  credentials  退出码 1
  输出 token   提示用户重新登录
 （退出码 0）
```

**提前 30 秒判定过期**，避免 token 在实际使用时刚好失效。

> **注意：** `get_token.py` 使用 `fcntl.flock`
> 实现并发安全刷新，该模块仅支持 macOS 和 Linux，不支持 Windows。

**退出码说明：**

| 退出码 | 含义                            |
| ------ | ------------------------------- |
| `0`    | 成功，token 已输出到 stdout     |
| `1`    | 需要重新登录，错误信息在 stderr |

---

## 其他 Skill 集成方式

以 `xray-log-query` 为例，在 Python 脚本中接入 xray-auth 的推荐写法：

```python
import subprocess, sys

def get_xray_token(xray_auth_skill_dir: str, env: str = "sit") -> str:
    """获取有效的 Xray access_token，失败时抛出 SystemExit。"""
    result = subprocess.run(
        [sys.executable, f"{xray_auth_skill_dir}/scripts/get_token.py", "--env", env],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()
```

> 注意：根据本仓库约定，所有调用必须通过 Python 脚本执行，不应使用 shell 管道拼装。

---

## 错误处理

| 错误情况                                    | 处理方式                                |
| ------------------------------------------- | --------------------------------------- |
| `credentials.json` 不存在                   | 退出码 1，提示运行 `auth.py` 登录       |
| `access_token` 过期，refresh 成功           | 自动更新文件，输出新 token，退出码 0    |
| `access_token` 过期，refresh 失败           | 退出码 1，提示重新登录                  |
| 网络不通                                    | 退出码 1，提示检查内网连接              |
| `auth.py` 等待超时（授权码 5 分钟内未使用） | 脚本报错，重新运行即可                  |
| 用户在浏览器中拒绝授权                      | 脚本报错 "authorization denied by user" |
| 浏览器无法自动打开                          | stderr 提示手动打开 URL，登录流程不中断 |

---

## 快速参考

```bash
# 登录（交互式）
python3 {SKILL_DIR}/scripts/auth.py [sit|prod|dev]

# 登出（删除本地凭证）
python3 {SKILL_DIR}/scripts/auth.py logout [sit|prod|dev]

# 获取 token（非交互式）
python3 {SKILL_DIR}/scripts/get_token.py [--env sit|prod|dev] [--output token|json]

# 查看帮助
python3 {SKILL_DIR}/scripts/auth.py --help
python3 {SKILL_DIR}/scripts/get_token.py --help
```
