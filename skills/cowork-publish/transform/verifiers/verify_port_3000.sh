#!/usr/bin/env bash
# 验证子应用端口契约：
#   - 不允许端口字面量硬编码（例如 --port 3000 / app.listen(3000) / "port": 3000）
#   - start.sh 必须使用 `APP_PORT="${APP_PORT:-3000}"` 兜底默认值语法，
#     业务启动命令必须以 `${APP_PORT}` 引用（蓝绿期 / 多实例下平台会注入 APP_PORT=3001）
#   - 业务代码读 env 必须 APP_PORT，不能裸 PORT
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# -- 1. uvicorn / gunicorn --port 字面量数字（必须改成 ${APP_PORT}）--
hits=$(grep -rnE '(uvicorn|gunicorn|hypercorn|sanic).*--port[ =]+[0-9]+' \
  --include='*.sh' --include='*.py' --include='*.toml' --include='*.cfg' \
  . 2>/dev/null | grep -v node_modules | grep -v '\.guard-transform' || true)
if [ -n "$hits" ]; then
  report "uvicorn/gunicorn 启动端口被硬编码为字面量数字（必须改用 \${APP_PORT}）:"
  echo "$hits" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面 grep 列出的 start.sh / *.py / *.toml。把 \`--port <N>\` 改为 \`--port \${APP_PORT}\`，并在 start.sh 顶部 \`export APP_PORT=\"\${APP_PORT:-3000}\"\`；host 同步改为 \`--host 0.0.0.0\`（平台 Pod 默认暴露 3000，蓝绿期会注入其它端口；host 必须 0.0.0.0）" >&2
fi

# -- 2. start.sh 必须满足端口环境变量契约 --
if [ -f start.sh ]; then
  # 2a. 必须使用 ${APP_PORT:-3000} 兜底默认值语法，不能裸 APP_PORT=3000 硬编码
  if ! grep -qE 'APP_PORT[="]*\$\{APP_PORT:-3000\}' start.sh; then
    report "start.sh 未使用 \`APP_PORT=\"\${APP_PORT:-3000}\"\` 兜底默认值语法"
    echo "[HINT] 目标文件 start.sh：必须用形如 \`export APP_PORT=\"\${APP_PORT:-3000}\"\` 的兜底语法（默认 3000，外部注入可覆盖）。直接 \`export APP_PORT=3000\` 会覆盖蓝绿期平台注入的 APP_PORT=3001，导致新版本永远探不通健康检查。" >&2
  fi

  # 2b. exec 启动行的端口必须引用 ${APP_PORT}（不是字面量数字）
  exec_line=$(grep -nE '^[[:space:]]*exec ' start.sh | head -1 || true)
  if [ -n "$exec_line" ]; then
    line_text=$(echo "$exec_line" | cut -d: -f2-)
    # 同时检查 --port / -p / :端口号 / --bind X:port 模式里是否含字面量
    if echo "$line_text" | grep -qE '(--port[= ]+[0-9]+|[[:space:]]-p[= ]+[0-9]+|--bind[= ]+[^[:space:]]*:[0-9]+|\.listen\([[:space:]]*[0-9]+)'; then
      report "start.sh exec 启动行端口被硬编码为字面量（必须改用 \${APP_PORT}）:"
      echo "  $exec_line" | sed 's/^/    /' >&2
      echo "[HINT] 目标文件 start.sh：把 exec 行的 \`--port 3000\` / \`-p 3000\` / \`--bind 0.0.0.0:3000\` 改为 \`--port \${APP_PORT}\` / \`-p \${APP_PORT}\` / \`--bind 0.0.0.0:\${APP_PORT}\`；端口的唯一 source of truth 是顶部的 \`export APP_PORT=\"\${APP_PORT:-3000}\"\`。" >&2
    fi
  fi
fi

# -- 3. Node：app.listen / server.listen 非 3000 --
hits=$(grep -rnE '\.(listen|bind)\(\s*([0-9]{4,5})' \
  --include='*.js' --include='*.ts' --include='*.mjs' --include='*.cjs' \
  src/ app/ backend/ apps/ . 2>/dev/null \
  | grep -vE '\b3000\b' \
  | grep -vE '(node_modules|\.next/|dist/|build/|\.guard-transform)' \
  | head -10 || true)
if [ -n "$hits" ]; then
  report "Node 入口 listen/bind 用了非 3000 端口:"
  echo "$hits" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面 grep 列出的 *.js / *.ts。把 \`.listen(<N>)\` / \`.bind(<N>)\` 的端口字面量改为 \`3000\`，host 用 \`'0.0.0.0'\`（如 \`app.listen(3000, '0.0.0.0')\`）" >&2
fi

# -- 4. process.env.PORT || 8000 / .PORT ?? 8000 这类 fallback --
hits=$(grep -rnE 'process\.env\.(APP_)?PORT[^|?&\)]*[\|\?]{1,2}\s*[\x27"]?([0-9]+)' \
  --include='*.js' --include='*.ts' --include='*.mjs' --include='*.cjs' \
  . 2>/dev/null \
  | grep -vE '[\|\?]{1,2}\s*[\x27"]?3000\b' \
  | grep -vE '(node_modules|\.next/|dist/|build/|\.guard-transform)' \
  | head -10 || true)
if [ -n "$hits" ]; then
  report "process.env.PORT fallback 默认值不是 3000:"
  echo "$hits" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面 grep 列出的 *.js / *.ts。把 \`process.env.APP_PORT || <N>\` / \`?? <N>\` 中的默认值改为 \`3000\`（env 名也要带 APP_ 前缀）" >&2
fi

# -- 5. Python os.environ.get("PORT", "8000") 这类 --
hits=$(grep -rnE 'environ(\.get|\[)\s*\(?[\x27"]?(APP_)?PORT[\x27"]?\s*[,\)\]]?\s*[\x27"]?([0-9]+)' \
  --include='*.py' . 2>/dev/null \
  | grep -vE '\b3000\b' \
  | grep -vE '(\.venv|__pycache__|\.guard-transform)' \
  | head -10 || true)
if [ -n "$hits" ]; then
  report "Python environ PORT fallback 不是 3000:"
  echo "$hits" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面 grep 列出的 *.py。把 \`os.environ.get('APP_PORT', <N>)\` 中的默认值改为 \`'3000'\`（key 加 APP_ 前缀，值用字符串 '3000'）" >&2
fi

# -- 6. yaml/json/toml 配置文件里的 port: 8000 / "port": 8080 --
hits=$(grep -rnE '^\s*[\x27"]?port[\x27"]?\s*[:=]\s*([0-9]{4})' \
  --include='*.yaml' --include='*.yml' --include='*.json' --include='*.toml' \
  --include='*.ini' --include='*.cfg' \
  . 2>/dev/null \
  | grep -vE ':\s*[\x27"]?3000\b' \
  | grep -vE '(node_modules|\.guard-transform|package-lock|tsconfig)' \
  | head -10 || true)
if [ -n "$hits" ]; then
  report "配置文件含非 3000 端口:"
  echo "$hits" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面 grep 列出的 yaml/json/toml/ini/cfg。把 port 值改为 3000（如 \`port: 3000\`）" >&2
fi

# -- 7. 监听 host 必须是 0.0.0.0（不是 127.0.0.1 / localhost）--
if [ -f start.sh ]; then
  if grep -qE '\b(127\.0\.0\.1|localhost)\b' start.sh; then
    report "start.sh 含 127.0.0.1 / localhost，应监听 0.0.0.0"
    echo "[HINT] 目标文件 start.sh：把所有 \`--host 127.0.0.1\` / \`--host localhost\` 改为 \`--host 0.0.0.0\`（127.0.0.1 不接受 Pod 外部流量，平台健康检查会失败）" >&2
  fi
fi

# -- 8. Node 入口里读 process.env.HOST / process.env.HOSTNAME 必须用 APP_ 前缀 --
# Next.js standalone server.js 默认读 HOSTNAME；业务代码再读 HOST/HOSTNAME 不带前缀
# 会与平台注入的系统 env 冲突；所有业务 env 必须 APP_ 前缀（详见 § 一 / § 七.5）
hits=$(grep -rnE 'process\.env\.(HOST|HOSTNAME|PORT)\b' \
  --include='*.js' --include='*.ts' --include='*.mjs' --include='*.cjs' \
  src/ app/ apps/ backend/ api/ server/ pages/ . 2>/dev/null \
  | grep -vE '(node_modules|\.next/|dist/|build/|\.guard-transform|\.test\.|\.spec\.)' \
  | grep -vE '/test/|/tests/|__tests__' \
  | grep -vE 'process\.env\.APP_' \
  | head -10 || true)
if [ -n "$hits" ]; then
  # 排除 Next.js standalone 自己的 server.js 入口（它必须读 HOSTNAME / PORT）
  hits=$(echo "$hits" | grep -vE '\.next/standalone/server\.js' || true)
  if [ -n "$hits" ]; then
    report "业务代码读裸 process.env.HOST/HOSTNAME/PORT（必须用 APP_HOST / APP_PORT 前缀）:"
    echo "$hits" | sed 's/^/    /' >&2
    echo "[HINT] 目标文件：上面 grep 列出的 *.js / *.ts。把 \`process.env.HOST\` → \`process.env.APP_HOST\`、\`process.env.HOSTNAME\` → \`process.env.APP_HOST\`、\`process.env.PORT\` → \`process.env.APP_PORT\`（业务 env 全部带 APP_ 前缀，否则会被平台系统 env 覆盖）" >&2
  fi
fi

# -- 9. Python 业务代码里 os.environ.get("HOST"/"HOSTNAME"/"PORT") --
hits=$(grep -rnE "os\.(environ\.get|environ\[|getenv)\s*\(?\s*[\"'](HOST|HOSTNAME|PORT)[\"']" \
  --include='*.py' \
  src/ app/ apps/ backend/ api/ server/ . 2>/dev/null \
  | grep -vE '(\.venv|__pycache__|\.guard-transform|\.test\.|\.spec\.|/test/|/tests/)' \
  | head -10 || true)
if [ -n "$hits" ]; then
  report "Python 业务代码读裸 HOST/HOSTNAME/PORT env（必须用 APP_HOST / APP_PORT 前缀）:"
  echo "$hits" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面 grep 列出的 *.py。把 \`os.environ.get('HOST'/'HOSTNAME')\` → \`os.environ.get('APP_HOST')\`、\`os.environ.get('PORT')\` → \`os.environ.get('APP_PORT')\`（业务 env 全部带 APP_ 前缀）" >&2
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项端口约束违反" >&2
  exit 1
fi
echo "[OK] 端口 3000 + host 0.0.0.0 + APP_ 前缀约束通过"
