#!/usr/bin/env bash
# 验证 start.sh 的启动命令显式收敛 stderr → stdout
#
# 动机：
#   Guard runner 监听子进程 stderr 来判定异常；很多框架默认把正常 INFO 启动日志
#   （"Server listening on..."、"Worker booted"、"Started in 3.2s"）打到 stderr，
#   导致 Guard 误判子应用启动失败 → 触发不必要的 retry / restart / 告警。
#
# 平台范围：产物只支持 Python / Node 后端；输入工程不限语言（Java / Rust / Go / .NET 等由 stage 20 重写为 Python/Node）
#
# ============================================================
# 框架日志默认目的地速查表（Python / Node 主流）
# ============================================================
# Python:
#   gunicorn       : INFO 启动日志默认走 stderr（gunicorn.error logger）
#                    ⚠️  --error-logfile -  中 `-` = stderr（反直觉，常见坑）
#                    ⚠️  --access-logfile - 中 `-` = stdout（同字面含义相反！）
#                    ⚠️  --error-logfile /dev/stdout 在 Pod 里会触发
#                       OSError(6, 'No such device or address')——容器中
#                       /dev/stdout → /proc/self/fd/1，并不总是绑定可写。
#                       唯一稳妥方案：shell 级 `2>&1`（在 exec 前执行）
#   hypercorn      : 同 gunicorn，--error-logfile - 也是 stderr，
#                    --error-logfile /dev/stdout 同样在 Pod 里不可靠
#   uvicorn        : 全部日志默认 stderr，无 --*-logfile 参数，只能 2>&1
#   daphne         : INFO 默认 stderr；--access-log - 是 stdout（无 - 反直觉）
#   granian        : 默认 stderr，无反直觉参数
#   waitress       : 跟随 Python logging（默认 stderr），无自有 logfile flag
#   celery/rq      : 默认 stderr
#   flask run / app.run() / python -m http.server :
#                    dev server 不应进生产，由 verify_no_dev_artifacts 兜底
#   logging 模块默认 handler stream=sys.stderr —— 这是上游一切默认 stderr 的根源
#
# Node:
#   语言级行为：
#     console.log / console.info  → stdout
#     console.warn / console.error / console.debug → stderr
#   框架默认目的地：
#     Next.js / Nuxt   : 启动 INFO 多走 stderr（用了 console.error/warn 输出）
#     NestJS           : 自带 Logger 默认走 stdout ✓
#     Express / Koa    : 无内置请求日志，看用户中间件
#     Fastify          : 内置 pino，默认走 stdout ✓
#     winston / pino / bunyan : 主流 logger 默认走 stdout ✓
#
# ============================================================
# 设计立场：不为任何框架做"默认走 stdout"的豁免；唯一接受 shell 级 `2>&1`
# ============================================================
#   即使是 NestJS / fastify / winston / pino 这种"默认就走 stdout"的工具，
#   verifier 也仍要求 exec 行显式 2>&1。原因：
#     1) 用户可能改了 transport 配置改走 stderr，verifier 静态无法感知
#     2) 业务代码里任何一处 console.error / logger.error 都会污染 stderr
#     3) 第三方依赖里的 deprecation warning 也走 stderr
#   "宁可重复保险（2>&1 是幂等的），不能漏过"。
#
#   为什么不接受 `--error-logfile /dev/stdout` / `--log-file /dev/stdout`？
#     真实事故：在 Guard Pod 中曾出现
#       Error: '/dev/stdout' isn't writable [OSError(6, 'No such device or address')]
#     根因：/dev/stdout 是 /proc/self/fd/1 的符号链接；某些 runc/containerd
#     启动方式下 fd 1 没绑定到可写的 pty/pipe，进程级 open("/dev/stdout") 直接失败。
#     而 shell 级 `2>&1` 完全发生在 exec 之前，由 shell 把 fd 2 dup 到 fd 1 上，
#     再 exec 业务进程——业务进程根本不需要"open /dev/stdout"，因此没有这个隐患。
#
# ============================================================
# 合法形式（任一满足）
# ============================================================
#   1) exec ... 2>&1                                       # 最常用，bash 重定向合并
#   2) exec ... > file 2>&1                                # 重定向到文件并合并
#   3) exec ... &> file                                    # bash 合并重定向语法糖
#   4) exec ... 2>&1 | tee ...                             # 合并后 tee
#
# ============================================================
# 不合法（FAIL）示例
# ============================================================
#   exec gunicorn -w 4 -b 0.0.0.0:3000 app:app
#   exec uvicorn app:app --host 0.0.0.0 --port 3000
#   exec node dist/server.js
#   exec gunicorn --error-logfile - app:app
#     ↑ 注意！gunicorn / hypercorn 的 --error-logfile - 中 `-` 表示 stderr
#       完全没收敛；这是它们最常见的踩坑写法
#   exec gunicorn --error-logfile /dev/stdout app:app
#     ↑ 看似对，但 Pod 里 /dev/stdout 不一定可写，gunicorn 启动时会
#       OSError(6, 'No such device or address') —— 必须用 shell 级 2>&1
#
# Skip 条件：start.sh 不存在（由 verify_entry_scripts.sh 兜底）
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

if [ ! -f start.sh ]; then
    echo "[OK] 无 start.sh，skip（由 verify_entry_scripts.sh 兜底）"
    exit 0
fi

# ---- 收集所有 exec 启动行（非注释）----
EXEC_LINES=$(grep -nE '^[[:space:]]*exec[[:space:]]+' start.sh \
    | grep -vE '^[[:space:]]*[0-9]+:[[:space:]]*#' || true)

if [ -z "$EXEC_LINES" ]; then
    echo "[FAIL] start.sh 找不到 exec 启动行" >&2
    echo "    Guard 子应用规范：start.sh 末尾必须用 exec 启动业务进程（前台运行）" >&2
    echo "    （exec 行也是本 verifier 校验 stderr 收敛的对象）" >&2
    echo "    当前 start.sh（首 30 行）：" >&2
    head -30 start.sh | sed 's/^/      /' >&2
    echo "[HINT] 目标文件 start.sh：把末行业务启动命令前加 \`exec\`，并在命令末尾追加 \`2>&1\`（合并 stderr 到 stdout）。示例：\`exec uvicorn main:app --host 0.0.0.0 --port 3000 2>&1\` 或 \`exec node dist/server.js 2>&1\`" >&2
    exit 1
fi

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# ---- 逐行检查 ----
while IFS= read -r raw_line; do
    [ -z "$raw_line" ] && continue
    # 注意：避免使用 LINENO（bash 内置变量，赋值后会被立刻覆盖回脚本真实行号）
    LNUM=$(echo "$raw_line" | cut -d: -f1)
    CMD=$(echo "$raw_line" | cut -d: -f2-)

    # 命中以下任一形式即合法（仅接受 shell 级 stderr 重定向）
    #   - bash 重定向：2>&1 / &> / >& / 2> /path/file
    # 注意：刻意 *不* 接受 --error-logfile /dev/stdout 等进程内方案。
    # 真实事故：Pod 里 /dev/stdout（→ /proc/self/fd/1）不一定可写，
    # gunicorn 启动时会 OSError(6, 'No such device or address')。
    # 唯一稳妥方案：shell 级 2>&1（在 exec 之前完成 fd dup）。
    if echo "$CMD" | grep -qE \
        '2>&1|&>[[:space:]]+|>&[[:space:]]+|2>[[:space:]]*[^&[:space:]]+'; then
        continue
    fi

    # 已知的"看似对、实际是 Pod 杀手"反模式：显式标记原因
    if echo "$CMD" | grep -qE -- '--(error-logfile|log-file)[[:space:]=]+/dev/stdout([[:space:]]|$)'; then
        report "start.sh 第 $LNUM 行使用 \`--error-logfile /dev/stdout\` —— 在 Guard Pod 中会触发 OSError(6, 'No such device or address') 启动失败"
        echo "    命令: $(echo "$CMD" | sed 's/^[[:space:]]*//')" >&2
        echo "    根因: 容器里 /dev/stdout → /proc/self/fd/1，某些 runc 启动方式 fd 1 未绑定可写设备" >&2
        echo "    修复: 删掉 \`--error-logfile /dev/stdout\` 或 \`--log-file /dev/stdout\`，改用 exec 行末尾 \`2>&1\`（shell 级重定向，发生在 exec 之前，永远生效）" >&2
        continue
    fi

    # ---- 未命中合法形式：给出框架特定的修复建议 ----
    SUGGESTION=""
    if echo "$CMD" | grep -qE '\bgunicorn\b'; then
        # 注意：gunicorn 的 --error-logfile - 中 - = stderr（不是 stdout），不能这样修
        # 也不能用 --error-logfile /dev/stdout：Pod 中 /dev/stdout 不一定可写，会 OSError(6) 启动失败
        # 唯一稳妥方案：bash 末尾 2>&1（在 exec 前完成 fd dup）
        SUGGESTION="检测到 gunicorn（INFO \"Booting worker\" 走 error logger，默认 stderr）：在末尾加 \`2>&1\`。⚠️ 不要写 \`--error-logfile -\`（\`-\` = stderr）；也不要写 \`--error-logfile /dev/stdout\`（Pod 里 /dev/stdout 不一定可写，会 OSError(6) 启动失败）"
    elif echo "$CMD" | grep -qE '\buvicorn\b'; then
        SUGGESTION="检测到 uvicorn（默认所有日志走 stderr，无 --error-logfile 参数）：只能在末尾加 \`2>&1\`"
    elif echo "$CMD" | grep -qE '\bhypercorn\b'; then
        # hypercorn 与 gunicorn 同样的 - 反直觉坑 + 同样的 /dev/stdout Pod 不可写问题
        SUGGESTION="检测到 hypercorn（INFO 启动日志走 error logger，默认 stderr）：在末尾加 \`2>&1\`。⚠️ 与 gunicorn 同样的坑：\`--error-logfile -\` 中 \`-\` = stderr；\`--error-logfile /dev/stdout\` 在 Pod 里会 OSError(6) 启动失败"
    elif echo "$CMD" | grep -qE '\bdaphne\b|\bgranian\b|\bwaitress-serve\b'; then
        SUGGESTION="检测到 ASGI/WSGI server（默认日志走 stderr）：在末尾加 \`2>&1\` 把 stderr 合并到 stdout"
    elif echo "$CMD" | grep -qE '\bnode\b|/node_modules/\.bin/|\bnpm[[:space:]]+(run[[:space:]]+)?start\b|\byarn[[:space:]]+start\b|\bpnpm[[:space:]]+(run[[:space:]]+)?start\b|\bbun\b|\bdeno\b'; then
        SUGGESTION="检测到 Node.js（console.error/warn 走 stderr）：在末尾加 \`2>&1\`"
    elif echo "$CMD" | grep -qE '\bpython[0-9.]*\b|\bcelery\b|\brq[[:space:]]'; then
        SUGGESTION="检测到 Python（logging 默认 handler stream=sys.stderr）：在末尾加 \`2>&1\`"
    else
        SUGGESTION="在 exec 命令末尾加 \`2>&1\` 把 stderr 合并到 stdout"
    fi

    report "start.sh 第 $LNUM 行 exec 启动命令未显式收敛 stderr → Guard 会把正常 INFO 启动日志误判为异常"
    echo "    命令: $(echo "$CMD" | sed 's/^[[:space:]]*//')" >&2
    echo "    建议: $SUGGESTION" >&2
    echo "[HINT] 目标文件 start.sh 第 ${LNUM} 行：在该 exec 行末尾追加 \`2>&1\`（最简且最稳：shell 级 fd dup，发生在 exec 之前）。⚠️ 不要用 \`--error-logfile -\`（\`-\` = stderr，不收敛）或 \`--error-logfile /dev/stdout\`（Pod 里 /dev/stdout 不一定可写，会 OSError(6) 启动失败）" >&2
done <<< "$EXEC_LINES"

if [ "$fail" -gt 0 ]; then
    echo "" >&2
    echo "[FAIL] $fail 处 exec 启动命令缺 stderr 收敛" >&2
    echo "    Guard 子应用规范：runner 监听 stderr 判定异常，正常启动日志必须统一走 stdout" >&2
    echo "    最简修复：在 exec 整条命令末尾追加 \`2>&1\`" >&2
    exit 1
fi

echo "[OK] start.sh 所有 exec 启动命令均已显式收敛 stderr → stdout"
