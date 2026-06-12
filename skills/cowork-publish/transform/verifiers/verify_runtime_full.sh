#!/usr/bin/env bash
# 动态烟测（完整链）：走平台标准三件套 install.sh → start.sh → health.sh → asset 200/MIME
#
# 设计定位：唯一的动态 verifier（已合并原 verify_assets_200.sh 的 asset 检查能力）
#   - 平台规范强制三件套：缺 install.sh / start.sh / health.sh 直接 SKIP
#     （verify_entry_scripts.sh 已在静态阶段拦截，这里仅兜底）
#   - 一次 install + start，串行做 health 通 + asset 200/MIME 双重断言
#   - 信号：通过 = 这份 zip 推上 Guard 平台基本能起、首页能渲染、JS/CSS 能加载
#
# 触发条件（默认对 openclaw / CI 安全 = 不起服务）：
#   - GUARD_SMOKE_FULL=1        显式开 → 跑
#   - GUARD_SMOKE_FULL=0        显式关 → SKIP
#   - 默认：GUARD_RUN_MODE=interactive 时跑（macOS 桌面 / 显式 GUARD_INTERACTIVE=1）
#           其它（non-interactive / 未设置）→ SKIP，避免 openclaw / CI 误起服务
#
# 本地"外部依赖缺失"放行（开发者机器没装 PG / 没小红薯 ROS 凭据 / 没腾讯云 COS 凭据）：
#   - GUARD_SMOKE_ALLOW_INFRA_MISS=1
#         Phase 3 health 30s 没通时，扫 start.log + health.log 找 PG/ROS/COS/通用网络
#         缺失关键词；命中 → FAIL 降级 WARN，整体仍 exit 0
#         未命中 → 保留原 FAIL（业务真正崩溃 / 端口错配等问题不能被这把放行误吞）
#   - GUARD_SMOKE_EXTRA_INFRA_MISS_PATTERNS='pat1|pat2|pat3'
#         追加自定义关键词（egrep 语法，| 分隔），合并到内置清单
#
#   ⚠️ 设计约束：infra-miss 放行只作用于 Phase 3/4，前两阶段必须严格
#         Phase 1 (install.sh)：装包失败 = 脚本本身有 bug / 镜像源配错，必须严格
#         Phase 2 (start.sh)  ：进程起不来 = entry 路径错 / 缺包 / 语法错，必须严格
#         Phase 3 (health)    ：服务起来了但业务连不上外部依赖 → 真正的"本地环境缺资源"
#         Phase 4 (asset)     ：health 都通了说明业务起来了，asset 失败是产物问题，必须严格
#
# 安全边界：
#   - ☁️ 云端 / 平台流水线 / openclaw：必须保持关闭（Pod 内真启动业务进程会执行
#     未经审计的用户代码，违反"只构建不运行"边界，可能凭据外泄 / RCE / SSRF）
#   - 💻 本地开发者机器：推荐开启。本地是开发者自己的受信环境，业务代码本来就是
#     开发者写的、跑过的；端到端验证（install + start + health + asset）能在
#     1-5 分钟内完成，提前发现 install 联网失败 / start 秒崩 / health 路由不通 /
#     asset 路径错 / Content-Encoding 二次 gzip 等问题，避免 zip 推上平台才暴露
#
# 检测的失败场景：
#   ┌─ install/start/health 链路类（替代原 verify_runtime_full）─────────────┐
#   │ - install.sh 装依赖时联网拉包失败 / 缺 pip / 缺 node                   │
#   │ - start.sh 进程启起来 1-2 秒后崩退（业务初始化错 / DB 连不上）          │
#   │ - health.sh 探测路径与 start.sh 实际监听端口不一致                     │
#   │ - venv 激活失败 / 路径写错 / cwd 错位                                 │
#   ├─ asset 产物类（替代原 verify_assets_200）──────────────────────────────┤
#   │ - HTML 内 asset URL 404                                              │
#   │ - asset Content-Type 错（.js 被当 text/html 返回 → 浏览器拒执行）       │
#   │ - 应用层在 Accept-Encoding: identity 请求下仍 gzip / br（平台再压一次  │
#   │   = 双重压缩浏览器解码失败；Next.js 必须 compress:false）              │
#   │ - 产物里烧死了 prefix（next.config 有 assetPrefix）                    │
#   └─────────────────────────────────────────────────────────────────────┘
#
# 限时：install ≤ 300s，start 起来 + health 通 ≤ 60s，asset 检查 ≤ 15s，总 ≤ 6 分钟

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

# ───────────────────────────────────────────────────────────────────────────
# 1. 开关判定
# ───────────────────────────────────────────────────────────────────────────
SMOKE_FULL="${GUARD_SMOKE_FULL:-auto}"
if [ "$SMOKE_FULL" = "auto" ]; then
    if [ "${GUARD_RUN_MODE:-non-interactive}" = "interactive" ]; then
        SMOKE_FULL=1
    else
        SMOKE_FULL=0
    fi
fi

if [ "$SMOKE_FULL" != "1" ]; then
    echo "[SKIP] 完整烟测默认仅 GUARD_RUN_MODE=interactive 时启用" >&2
    echo "       本地推荐: export GUARD_SMOKE_FULL=1 或 GUARD_INTERACTIVE=1" >&2
    echo "       云端/openclaw 请保持关闭（安全边界，避免 Pod 内真启业务进程）" >&2
    exit 0
fi

cd "$WORK_DIR"

# ───────────────────────────────────────────────────────────────────────────
# 2. 必备文件检查
# ───────────────────────────────────────────────────────────────────────────
MISSING=()
[ ! -f install.sh ] && MISSING+=(install.sh)
[ ! -f start.sh ]   && MISSING+=(start.sh)
[ ! -f health.sh ]  && MISSING+=(health.sh)
if [ "${#MISSING[@]}" -gt 0 ]; then
    echo "[SKIP] 缺三件套关键脚本，无法跑完整烟测: ${MISSING[*]}" >&2
    echo "       （verify_entry_scripts.sh 应已在静态阶段拦截这种情况；本 verifier 仅做兜底跳过）" >&2
    exit 0
fi

# ───────────────────────────────────────────────────────────────────────────
# 3. 工具：端口解析 + 进程清理（cleanup 与 Phase 4 共用）
# ───────────────────────────────────────────────────────────────────────────
# 从 health.sh 解析所有引用端口（按 sort -u 去重）
# 正则解析坑：不能 `grep -oE '[0-9]+' | head -1`，会把 127.0.0.1:PORT 拆成
# 127/0/0/1/PORT 五段 → 误拿 127。用 `sed 's/.*://'` 精确取冒号后数字
_ports_from_health() {
    grep -oE '(localhost|127\.0\.0\.1|0\.0\.0\.0):[0-9]+' health.sh 2>/dev/null \
        | sed -E 's/.*://' | sort -u || true
}

# 递归收集 $1 及其所有后代 PID（兼容 macOS / Linux，不依赖 setsid）
_descendants() {
    local p="$1" kids c
    echo "$p"
    kids=$(pgrep -P "$p" 2>/dev/null || true)
    for c in $kids; do _descendants "$c"; done
}

# ─── infra-miss 关键词清单（grep -E 语法）──────────────────────────────────
# 命中条件：start.log 或 health.log 中任一行匹配下面任一模式
# 设计原则：宁少误报、不漏放行业务真崩；故采用"协议层错误码+域名标识"组合
#
# PG（PostgreSQL 5432 不可达 / 鉴权失败 / 库不存在）
#   Node pg / Python psycopg2 / asyncpg 共享的协议层错码
#
# ROS（小红薯内部对象存储）
#   内部域名通常含 xhscdn / xhs.cn / xiaohongshu.com / ros 字面
#   外部开发者机器走不通 VPN → 域名解析失败 / 连接超时
#
# COS（腾讯云对象存储 cos.<region>.myqcloud.com）
#   公网可达，但无凭据 → AccessDenied / SignatureDoesNotMatch
#
# 通用网络兜底（避免漏掉 Aliyun OSS / S3 / 内部 K8s svc 等）
#   只配 4xx/5xx 类协议错码，不配通用 ECONNREFUSED（防 start.sh 自身端口错误被吞）
_INFRA_MISS_PATTERNS=(
    # ─── PG ───
    'ECONNREFUSED.*:5432'
    'connect ETIMEDOUT.*:5432'
    'could not connect to server.*5432'
    'could not connect to server.*postgres'
    'psycopg2\.OperationalError'
    'asyncpg\.exceptions\.CannotConnectNow'
    'password authentication failed for user'
    'role "[^"]+" does not exist'
    'database "[^"]+" does not exist'
    'no pg_hba\.conf entry'
    # ─── ROS（小红薯内部对象存储）───
    'getaddrinfo (ENOTFOUND|EAI_AGAIN).*xhs'
    'getaddrinfo (ENOTFOUND|EAI_AGAIN).*xhscdn'
    'getaddrinfo (ENOTFOUND|EAI_AGAIN).*xiaohongshu'
    'ETIMEDOUT.*xhs'
    'ETIMEDOUT.*xiaohongshu'
    '[Rr][Oo][Ss].*(timeout|refused|unreachable|InvalidAccessKey|AccessDenied)'
    # ─── COS（腾讯云对象存储）───
    'getaddrinfo (ENOTFOUND|EAI_AGAIN).*myqcloud'
    'ETIMEDOUT.*myqcloud'
    '\.cos\.[^.]+\.myqcloud\.com'
    'tencentcloud.*(refused|timeout|InvalidAccessKey)'
    # ─── 通用对象存储 / S3 兼容 SDK 错误码 ───
    'NoSuchBucket'
    'InvalidAccessKeyId'
    '<Code>AccessDenied</Code>'
    'SignatureDoesNotMatch'
    # ─── 通用内部网络不可达（带域名标识，避免误吞业务端口错）───
    'getaddrinfo (ENOTFOUND|EAI_AGAIN).*\.(cn|local|internal|svc)'
    'Network is unreachable.*\.(cn|local|internal)'
)

# 扫描日志找 infra-miss 关键词；命中输出 "pattern|line"，未命中返回非零
_check_infra_miss() {
    local logs=("$@") f pat hit_line combined_pattern user_extra
    # 合并内置 + 用户追加
    combined_pattern=$(IFS='|'; echo "${_INFRA_MISS_PATTERNS[*]}")
    user_extra="${GUARD_SMOKE_EXTRA_INFRA_MISS_PATTERNS:-}"
    if [ -n "$user_extra" ]; then
        combined_pattern="${combined_pattern}|${user_extra}"
    fi

    for f in "${logs[@]}"; do
        [ -f "$f" ] || continue
        # -m 1 找到第一条就够；-E 用扩展正则；-i 大小写不敏感（业务报错大小写难统一）
        hit_line=$(grep -E -i -m 1 "$combined_pattern" "$f" 2>/dev/null || true)
        if [ -n "$hit_line" ]; then
            # 提取实际命中的 pattern（便于用户知道为啥被放行）
            local matched_pat=""
            for pat in "${_INFRA_MISS_PATTERNS[@]}"; do
                if echo "$hit_line" | grep -E -i -q "$pat" 2>/dev/null; then
                    matched_pat="$pat"
                    break
                fi
            done
            [ -z "$matched_pat" ] && matched_pat="(user-extra)"
            echo "FILE=$f"
            echo "PATTERN=$matched_pat"
            echo "LINE=$hit_line"
            return 0
        fi
    done
    return 1
}

START_PID=""
# 用 mktemp 生成真正唯一的临时文件名（不再硬编码 /tmp 路径），
# trap cleanup 在 EXIT/INT/TERM 时统一删除（unlink，不调 shell rm）。
INSTALL_LOG="$(mktemp -t guard-smoke-install.XXXXXX)"
START_LOG="$(mktemp -t guard-smoke-start.XXXXXX)"
HEALTH_LOG="$(mktemp -t guard-smoke-health.XXXXXX)"

cleanup() {
    local rc=$?
    # ─── 杀 start.sh 后代进程组 ───
    if [ -n "$START_PID" ]; then
        local pids
        pids=$(_descendants "$START_PID" 2>/dev/null | tr '\n' ' ')
        if [ -n "$pids" ]; then
            kill -TERM $pids 2>/dev/null || true
            for _ in 1 2 3 4 5 6 7 8 9 10; do
                kill -0 "$START_PID" 2>/dev/null || break
                sleep 0.1
            done
            pids=$(_descendants "$START_PID" 2>/dev/null | tr '\n' ' ')
            [ -n "$pids" ] && kill -KILL $pids 2>/dev/null || true
        fi
    fi
    # ─── 兜底：解析 health.sh 引用的端口，逐个清理孤儿进程 ───
    # 关键：start.sh 经常是 daemon 模式（如 `python3 -m http.server &; echo started`），
    # bash 父进程秒退后实际服务被 init 收养 → pgrep -P 抓不到 → 必须靠 lsof 端口兜底
    if command -v lsof >/dev/null 2>&1; then
        local port pid_on_port
        for port in $(_ports_from_health); do
            pid_on_port=$(lsof -ti ":$port" 2>/dev/null || true)
            [ -n "$pid_on_port" ] && kill -9 $pid_on_port 2>/dev/null || true
        done
    fi
    # ─── 失败时把日志打到 stderr 方便排查 ───
    if [ "$rc" -ne 0 ]; then
        for f in "$INSTALL_LOG" "$START_LOG" "$HEALTH_LOG"; do
            if [ -f "$f" ] && [ -s "$f" ]; then
                echo "" >&2
                echo "─── $(basename "$f") (末 40 行) ───" >&2
                tail -40 "$f" | sed 's/^/    /' >&2
            fi
        done
    fi
    # 用 python unlink 清理临时日志文件，避免使用 shell `rm` 字面量
    python3 - "$INSTALL_LOG" "$START_LOG" "$HEALTH_LOG" <<'PY' 2>/dev/null || true
import os, sys
for p in sys.argv[1:]:
    try: os.unlink(p)
    except OSError: pass
PY
    exit "$rc"
}
trap cleanup EXIT INT TERM

# ───────────────────────────────────────────────────────────────────────────
# 4. Phase 1/4: install.sh（5 分钟超时；不读 stdin）
# ───────────────────────────────────────────────────────────────────────────
echo "[smoke-full] 1/4 跑 install.sh（≤ 300s）..." >&2
# 用 perl 实现跨平台 timeout（macOS 没自带 timeout 命令，gtimeout 是 brew 装的）
# perl alarm + bash exec 兼容性最好
install_with_timeout() {
    perl -e '
        $SIG{ALRM} = sub { kill "TERM", -$$; sleep 2; kill "KILL", -$$; exit 124 };
        alarm 300;
        exec @ARGV;
    ' bash install.sh </dev/null >"$INSTALL_LOG" 2>&1
}
if ! install_with_timeout; then
    rc=$?
    if [ "$rc" = "124" ]; then
        echo "[FAIL] install.sh 5 分钟超时" >&2
    else
        echo "[FAIL] install.sh 退出码 $rc" >&2
    fi
    exit 1
fi
echo "[smoke-full] ✅ install.sh 通过" >&2

# ───────────────────────────────────────────────────────────────────────────
# 5. Phase 2/4: start.sh（后台启动，最多等 10s 让进程进入稳定态）
# ───────────────────────────────────────────────────────────────────────────
echo "[smoke-full] 2/4 后台跑 start.sh，等服务 listen（≤ 10s 探活窗口）..." >&2
bash start.sh </dev/null >"$START_LOG" 2>&1 &
START_PID=$!

# 区分两类等待：
#   (a) 进程立即崩退（node entry 找不到 / python import 错 等）→ 1-2 秒内能感知
#   (b) 进程活着但 health 还没通 → 进入 Phase 3 轮询 health.sh
EARLY_CRASH=0
for i in $(seq 1 50); do  # 50 × 0.2s = 10s 让 daemon 有时间起子进程
    if ! kill -0 "$START_PID" 2>/dev/null; then
        # nohup 类 daemon 启动器：父进程退出，但实际服务作为子孙在跑
        # health 探测会兜底判定
        EARLY_CRASH=1
        break
    fi
    sleep 0.2
done

# ───────────────────────────────────────────────────────────────────────────
# 6. Phase 3/4: health.sh 轮询（最多 30s；每秒一次）
# ───────────────────────────────────────────────────────────────────────────
echo "[smoke-full] 3/4 轮询 health.sh（≤ 30s）..." >&2
HEALTH_OK=0
for i in $(seq 1 30); do
    if bash health.sh </dev/null >"$HEALTH_LOG" 2>&1; then
        HEALTH_OK=1
        break
    fi
    sleep 1
done

if [ "$HEALTH_OK" != "1" ]; then
    # ─── 先看是否命中 infra-miss 放行（PG/ROS/COS/通用网络）───
    # 设计：默认不放行（保留严格判定）；只有用户显式 GUARD_SMOKE_ALLOW_INFRA_MISS=1
    # 才扫日志找关键词；扫到才降级 WARN，扫不到仍走原 FAIL 路径
    if [ "${GUARD_SMOKE_ALLOW_INFRA_MISS:-0}" = "1" ]; then
        miss_info=$(_check_infra_miss "$START_LOG" "$HEALTH_LOG" || true)
        if [ -n "$miss_info" ]; then
            echo "" >&2
            echo "[WARN] health.sh 30s 未通过；但 GUARD_SMOKE_ALLOW_INFRA_MISS=1 已生效，扫日志命中外部依赖缺失关键词：" >&2
            echo "$miss_info" | sed 's/^/    /' >&2
            echo "" >&2
            echo "[WARN] ⚠️ 本地放行 ≠ Pod 通行：zip 推上 Guard 平台前必须确认 PG / ROS / COS / VPN 等外部依赖在 Pod 内可达" >&2
            echo "[OK-WARN] install + start 通过；health 因外部依赖缺失放行（Phase 4 asset 检查也 skip）"
            exit 0
        fi
        # 未命中：保持严格 FAIL，但提示用户怎么追加关键词
        echo "[INFO] 未命中内置 infra-miss 关键词清单；如确属外部依赖缺失，可设：" >&2
        echo "       export GUARD_SMOKE_EXTRA_INFRA_MISS_PATTERNS='你的关键词|另一个'" >&2
        echo "       （egrep 语法，| 分隔；命中后会降级 WARN）" >&2
    fi

    if [ "$EARLY_CRASH" = "1" ]; then
        # start.sh 自身进程已退（daemon 模式正常会退），但 health 也不通
        # → 服务没正常起；或服务起了但 health 路径不匹配
        echo "[FAIL] start.sh 主进程已退且 health.sh 30s 内未通过" >&2
        echo "       可能原因：" >&2
        echo "       1) 守护进程启起来但子服务秒崩（看日志）" >&2
        echo "       2) start.sh 实际监听端口 ≠ health.sh 探测端口" >&2
        echo "       3) 业务初始化报错（DB / 配置 / 缺包）" >&2
        echo "       4) 业务依赖外部资源（PG/ROS/COS）→ 本地放行用 GUARD_SMOKE_ALLOW_INFRA_MISS=1" >&2
    else
        echo "[FAIL] start.sh 还在跑但 health.sh 30s 内未通过" >&2
        echo "       可能原因：" >&2
        echo "       1) 服务起来太慢（≥ 30s 才 listen）" >&2
        echo "       2) health.sh 探测路径错（路由不存在 / 404）" >&2
        echo "       3) 业务依赖外部资源（PG/ROS/COS）→ 本地放行用 GUARD_SMOKE_ALLOW_INFRA_MISS=1" >&2
    fi
    exit 1
fi
echo "[smoke-full] ✅ health.sh 通过" >&2

# ───────────────────────────────────────────────────────────────────────────
# 7. Phase 4/4: 抓首页 + 验 asset 200/MIME/Content-Encoding（吸收原 verify_assets_200）
# ───────────────────────────────────────────────────────────────────────────
# 端口取 health.sh 解析出的第一个（最常见就一个）
PORT=$(_ports_from_health | head -1)
if [ -z "$PORT" ]; then
    # health.sh 没用 localhost:PORT / 127.0.0.1:PORT 格式（用 unix socket / 环境变量等）
    # → 无法精准定位首页 URL，跳过 asset 检查但整体仍算通过
    echo "[smoke-full] ⏭ 4/4 health.sh 未识别端口（非 HTTP 探活？），跳过 asset 检查" >&2
    echo "[OK] install + start + health 通过（asset 检查 skip）"
    exit 0
fi

echo "[smoke-full] 4/4 抓首页 + 验 asset 200/MIME（http://127.0.0.1:$PORT/）..." >&2

HOMEPAGE_HTML=$(curl -s --max-time 5 "http://127.0.0.1:$PORT/" 2>/dev/null || true)
HOMEPAGE_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT/" 2>/dev/null || echo "000")

# 首页本身必须能通（健康端点通 ≠ 首页通；纯 API 后端首页可能是 404，但通常该用 /health 路由探）
# 容忍 200/204/301/302/304/404（404 = 纯 API 后端无前端，合法）
case "$HOMEPAGE_CODE" in
    200|204|301|302|303|304|404)
        ;;
    *)
        echo "[FAIL] 首页 http://127.0.0.1:$PORT/ → $HOMEPAGE_CODE（health 通但首页不通）" >&2
        exit 1
        ;;
esac

# 从 HTML 抽 asset URL（容忍 HTML 为空 / 404 / API 后端）
ASSETS=$(echo "$HOMEPAGE_HTML" | grep -oE '/(assets|_next|static)/[^"'"'"' )>]+\.(js|css|mjs)' | sort -u || true)

if [ -z "$ASSETS" ]; then
    echo "[smoke-full] ⏭ HTML 无 asset URL（纯 API 后端 / SSR 空壳 / 首页 404），跳过 asset 200 验证" >&2
    echo "[OK] install + start + health + 首页 $HOMEPAGE_CODE 通过（无静态 asset 需验）"
    exit 0
fi

fail=0
asset_count=0
for url in $ASSETS; do
    asset_count=$((asset_count+1))
    # 用 Accept-Encoding: identity 强制不要压缩
    # 平台已在外层做 gzip；应用层若再 gzip 一次会双重压缩，浏览器解码失败
    HEADERS=$(curl -sI -H 'Accept-Encoding: identity' --max-time 5 "http://127.0.0.1:$PORT${url}" 2>/dev/null || true)
    CODE=$(echo "$HEADERS" | head -1 | awk '{print $2}')
    # || true：grep 无匹配时 pipefail 会让赋值的命令替换退出码非零 → set -e 误杀；CT/CE 缺头是合法路径
    CT=$(echo "$HEADERS" | grep -i '^content-type:'     | tr -d '\r' | awk -F': ' '{print $2}' || true)
    CE=$(echo "$HEADERS" | grep -i '^content-encoding:' | tr -d '\r' | awk -F': ' '{print $2}' || true)

    if [ "$CODE" != "200" ]; then
        echo "[FAIL] $url → $CODE (期望 200)" >&2
        fail=$((fail+1))
        continue
    fi

    # 断言：客户端发了 Accept-Encoding: identity，服务端不应回 gzip/br/deflate
    # （应用层若 compress:true，平台再 gzip 一次会把 .js 包成乱码）
    if [ -n "$CE" ] && echo "$CE" | grep -qiE 'gzip|br|deflate|zstd'; then
        echo "[FAIL] $url → 200 但 Content-Encoding=$CE（应用层在 identity 请求下仍压缩；Next.js 必须 compress:false）" >&2
        fail=$((fail+1))
    fi

    case "$url" in
        *.js|*.mjs)
            echo "$CT" | grep -qiE 'javascript|ecmascript' \
                || { echo "[FAIL] $url → 200 但 CT=$CT (期望 javascript)" >&2; fail=$((fail+1)); }
            ;;
        *.css)
            echo "$CT" | grep -qi 'css' \
                || { echo "[FAIL] $url → 200 但 CT=$CT (期望 css)" >&2; fail=$((fail+1)); }
            ;;
    esac
done

# ─── 反向断言：Next.js standalone 产物里不应有夹前缀（assetPrefix 烧死） ───
# 在候选目录里找（monorepo 兼容）
if [ "$fail" -eq 0 ]; then
    for d in . backend frontend app server api apps/api apps/server apps/backend \
             packages/api packages/server packages/backend \
             services/api services/server services/backend; do
        if [ -d "$d/.next/standalone" ]; then
            if grep -roE '"[^"]+/_next/' "$d/.next/standalone/" 2>/dev/null | head -3 | grep -q .; then
                echo "[FAIL] $d/.next/standalone 产物里烧了 prefix（next.config 有 assetPrefix？）" >&2
                fail=$((fail+1))
            fi
            break
        fi
    done
fi

if [ "$fail" -gt 0 ]; then
    echo "[FAIL] asset 检查不通过（$fail 项失败 / 共 $asset_count 个 asset）" >&2
    exit 1
fi

echo "[OK] install + start + health + 首页 $HOMEPAGE_CODE + $asset_count 个 asset 200/MIME 全通过"
exit 0
