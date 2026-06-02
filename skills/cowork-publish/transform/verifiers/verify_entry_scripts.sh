#!/usr/bin/env bash
# 入口脚本可运行性体检
#
# 检查对象：install.sh / start.sh / health.sh（三个 Pod 启动入口脚本）
#
# 体检项：
#   1) 第一行是合法 shebang（#!/bin/bash 或 #!/usr/bin/env bash 等）
#   2) 文件有 +x 可执行权限位
#   3) 无 UTF-8 BOM（BOM 在 #! 之前会让 kernel 找不到 shebang）
#   4) 无 CRLF 行尾（Windows 行尾让 bash 报 bad interpreter: bash\r）
#   5) install.sh / start.sh 必须 set -eo pipefail（fail-loud；health.sh 短脚本豁免）
#   6) bash -n 语法检查通过（提前发现语法错，不用等 Pod 真跑）
#   7) install.sh 不能执行 npm/yarn/pnpm build / next build / vite build / tsc
#      （build 必须在 stage 40 阶段完成，install.sh 只能拷贝 + 解依赖 + 灌种子）
#   8) start.sh 末尾必须用 exec 启动业务进程（不能 & 后台 + 退出）
#      原因：bash 进程退出会让 Pod 健康检查认为容器死了
#   9) health.sh 必须包含 127.0.0.1:3000/health 字面量探测（端口/host 必须显式写）
#      原因：平台调 health.sh 判活，路径不是 /health 或端口写错都会立刻烂
#
# 任何一项不通过 → exit 1
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }
hint()   { printf '[HINT] %s\n' "$*" >&2; }

# bash -n 报错文本要先落到临时文件再读出来；用 mktemp 拿真正唯一名称，
# trap EXIT/INT/TERM 时用 python unlink 清理（避免脚本里出现 shell 删除字面量）。
_TMP_SHEBANG_ERR="$(mktemp -t shebang-err.XXXXXX)"
_cleanup_tmp() {
    python3 - "$_TMP_SHEBANG_ERR" <<'PY' 2>/dev/null || true
import os, sys
for p in sys.argv[1:]:
    try: os.unlink(p)
    except OSError: pass
PY
}
trap _cleanup_tmp EXIT INT TERM

for f in install.sh start.sh health.sh; do
  if [ ! -f "$f" ]; then
    report "$f 不存在"
    hint "目标文件 $f：在工程根目录新建 $f，加 shebang \`#!/usr/bin/env bash\` + \`set -eo pipefail\`，并 chmod +x；start.sh 末行须 \`exec\` 启动业务进程并监听 0.0.0.0:3000，health.sh 须 curl 127.0.0.1:3000/health"
    continue
  fi

  # shebang
  if ! head -1 "$f" | grep -qE '^#!(/bin/sh|/bin/bash|/usr/bin/env (bash|sh))$'; then
    report "$f 第一行 shebang 不合法: $(head -1 "$f")"
    hint "目标文件 $f：把第一行改为 \`#!/usr/bin/env bash\`（必须是文件第 1 行，前面不能有空行、注释或 BOM）"
  fi

  # 可执行权限
  if [ ! -x "$f" ]; then
    report "$f 缺可执行权限位"
    hint "目标文件 $f：执行 \`chmod +x $f\` 加上可执行位（git 仓库内可 \`git update-index --chmod=+x $f\` 持久化）"
  fi

  # BOM
  if head -c 3 "$f" | xxd 2>/dev/null | grep -q 'efbb bf'; then
    report "$f 含 UTF-8 BOM (会让 shebang 失效)"
    hint "目标文件 $f：去掉文件开头的 UTF-8 BOM，例如 \`sed -i '1s/^\\xEF\\xBB\\xBF//' $f\`（或用编辑器另存为 UTF-8 无 BOM）"
  fi

  # CRLF
  if file "$f" 2>/dev/null | grep -q 'CRLF'; then
    report "$f 含 CRLF 行尾 (Pod 上 sh 解释会报 \\r 错)"
    hint "目标文件 $f：转 LF 行尾，例如 \`sed -i 's/\\r$//' $f\`（或 \`dos2unix $f\`）"
  fi

  # set -eo pipefail（install.sh / start.sh 必须；health.sh 短脚本豁免）
  case "$f" in
    install.sh|start.sh)
      if ! grep -qE '^set -e' "$f"; then
        report "$f 缺 set -e（fail loud 强制要求）"
        hint "目标文件 $f：在 shebang 下一行新增 \`set -eo pipefail\`（任何中间命令失败必须立刻退出，避免静默成功）"
      fi
      if ! grep -qE 'pipefail' "$f"; then
        report "$f 建议 set -eo pipefail（含 pipe 时 -e 不够）"
        hint "目标文件 $f：把已有的 \`set -e\` 改为 \`set -eo pipefail\`（让管道中任一段失败也算整条失败）"
      fi
      ;;
  esac

  # bash 语法检查
  if ! bash -n "$f" 2> "$_TMP_SHEBANG_ERR"; then
    report "$f 语法错: $(cat "$_TMP_SHEBANG_ERR")"
    hint "目标文件 $f：按上面 \`bash -n\` 报错信息修复语法（常见：未闭合的引号 / heredoc 未关 / if-fi 不匹配）；本地用 \`bash -n $f\` 复跑验证"
  fi
done

# ---- 7. install.sh 不能跑 build（Pod 资源不足会 OOM 重启） ----
if [ -f install.sh ]; then
  # 排除注释行 / heredoc 内容；只看实际命令行
  BUILD_HITS=$(grep -nE '^[[:space:]]*(npm|yarn|pnpm|bun|cnpm)[[:space:]]+(run[[:space:]]+)?build\b|^[[:space:]]*(npx[[:space:]]+)?(next|vite|tsc|webpack|rollup|esbuild|parcel|nuxt|astro|svelte-kit)[[:space:]]+build\b' \
    install.sh 2>/dev/null | grep -vE '^\s*[0-9]+:#' || true)
  if [ -n "$BUILD_HITS" ]; then
    report "install.sh 含 build 命令（严禁！Pod 容器通常 1C2G，前端 build 会 OOM → 无限重启）:"
    echo "$BUILD_HITS" | sed 's/^/    /' >&2
    hint "目标文件 install.sh：删除所有 \`npm/yarn/pnpm/bun run build\` 和 \`next/vite/tsc/webpack/rollup/esbuild/parcel/nuxt/astro/svelte-kit build\` 命令；前端构建必须在 stage 40 本地完成，install.sh 只允许 cp / 解压 / pip / npm install（无 build）"
  fi
fi

# ---- 8. start.sh 末行必须 exec ----
if [ -f start.sh ]; then
  # 取出最后一条非注释非空行
  LAST_LINE=$(grep -nvE '^[[:space:]]*(#|$)' start.sh | tail -1 || true)
  if [ -n "$LAST_LINE" ]; then
    LAST_LINENO=$(echo "$LAST_LINE" | cut -d: -f1)
    LAST_CMD=$(echo "$LAST_LINE" | cut -d: -f2-)
    # 末行必须 exec ...（除了 fi/done/} 这种结构控制行）
    if ! echo "$LAST_CMD" | grep -qE '^[[:space:]]*(exec[[:space:]]|\}|done[[:space:]]*$|fi[[:space:]]*$|esac[[:space:]]*$)'; then
      report "start.sh 最后一条命令不是 exec（第 $LAST_LINENO 行: $LAST_CMD）；后台启动会让 bash 退出 → Pod 误判容器死亡"
      hint "目标文件 start.sh 第 $LAST_LINENO 行：在业务启动命令前加 \`exec\`，例如 \`exec uvicorn main:app --host 0.0.0.0 --port 3000\` 或 \`exec node server.js\`（必须前台运行，bash 退出 = Pod 死亡）"
    fi
    # 末行不应以 & 结尾（后台运行）
    if echo "$LAST_CMD" | grep -qE '&[[:space:]]*$'; then
      report "start.sh 最后一条命令以 & 结尾（后台运行；必须前台 exec）：$LAST_CMD"
      hint "目标文件 start.sh 第 $LAST_LINENO 行：去掉行尾 \`&\` 并在命令前加 \`exec\`，让业务进程接管 PID 1，前台运行（Pod 探活依赖此前台进程）"
    fi
  fi
fi

# ---- 9. health.sh 基础格式检查（path 一致性交给 verify_health_consistency.sh） ----
# 注意：path 不再强制 /health，应用可能用 /api/health / /healthz / /actuator/health 等；
#      探测路径与业务路由的双向一致性由 verify_health_consistency.sh 负责
if [ -f health.sh ]; then
  # 必须出现 127.0.0.1:3000 或 localhost:3000 作为探测目标的 host:port（无论后续 path 是什么）
  # 也允许 nc / </dev/tcp/.../3000 这种 TCP 探活；进程/ping 探测会被 verify_health_consistency 标记
  if ! grep -qE '(127\.0\.0\.1|localhost)[:/[:space:]]*3000\b|/dev/tcp/(127\.0\.0\.1|localhost)/3000\b|\bnc\s+(-[a-zA-Z]+\s+)*(127\.0\.0\.1|localhost)\s+3000\b' health.sh; then
    # 如果只是没识别到 host:port，且 health.sh 用了 ping/进程检查也算合法形式，留给 verify_health_consistency 决策
    if ! grep -qE '\bping\b|\bpgrep\b|\bpidof\b' health.sh; then
      report "health.sh 找不到对 127.0.0.1:3000 / localhost:3000 的探测（端口必须 3000；path 由业务决定，由 verify_health_consistency 负责一致性校验）"
      echo "    当前内容（首 5 行）:" >&2
      head -5 health.sh | sed 's/^/      /' >&2
      hint "目标文件 health.sh：用一条 \`curl -fsS http://127.0.0.1:3000/health\` 做探测（host 固定 127.0.0.1，端口固定 3000，path 由 verify_health_consistency 决定；最简模板：\`#!/usr/bin/env bash\\nexec curl -fsS http://127.0.0.1:3000/health\`）"
    fi
  fi
  # 不能用 0.0.0.0 当探测目标
  if grep -qE 'curl[^|]*0\.0\.0\.0' health.sh; then
    report "health.sh 用 0.0.0.0 当探测目标（应该用 127.0.0.1，0.0.0.0 仅用于 listen）"
    hint "目标文件 health.sh：把 curl 目标里的 \`0.0.0.0\` 全部替换为 \`127.0.0.1\`（0.0.0.0 是 listen 地址、不是合法的请求目标 IP）"
  fi
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项 shebang/语法问题" >&2
  exit 1
fi
echo "[OK] shebang / 权限 / 语法检查通过"
