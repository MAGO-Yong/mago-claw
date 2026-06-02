#!/usr/bin/env bash
# 验证：交付物里没有开发期残留（Dockerfile / Makefile / docker-compose / .env / .example）
# 详见 transform_prompt.md § 七 + § 十 checklist
#
# 关键事实：
#   - 平台用 install.sh / start.sh / health.sh，不读 Dockerfile / Makefile
#   - .env / .env.example 留下来会让运维误以为该改它（实际只读 db.properties / ai.properties）
#   - docker-compose.yml 留下来会暗示需要外部基础设施
#
# 这些文件应在 stage 30 渲染交付脚本时就清掉，本 verifier 是安全网。

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# ---- 1. Docker 残留（顶层）----
DOCKER_FILES=$(find . -maxdepth 2 -type f \
  \( -name 'Dockerfile' -o -name 'Dockerfile.*' \
     -o -name 'docker-compose.yml' -o -name 'docker-compose.yaml' \
     -o -name 'docker-compose.*.yml' -o -name 'docker-compose.*.yaml' \
     -o -name '.dockerignore' \) \
  -not -path '*/node_modules/*' -not -path '*/.git/*' \
  -not -path '*/.guard-transform/*' 2>/dev/null | head -20 || true)
if [ -n "$DOCKER_FILES" ]; then
  report "交付物含 Docker 文件（平台不用 Docker 交付，应在 stage 30 删除）:"
  echo "$DOCKER_FILES" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面列出的 Dockerfile* / docker-compose*.yml / .dockerignore。直接 \`rm\` 删除（平台用 install.sh + start.sh + health.sh 三件套，不会读 Docker 配置；保留只会误导运维）" >&2
fi

# ---- 2. Makefile 残留 ----
MAKE_FILES=$(find . -maxdepth 2 -type f \
  \( -name 'Makefile' -o -name 'makefile' -o -name 'GNUmakefile' \) \
  -not -path '*/node_modules/*' -not -path '*/.git/*' \
  -not -path '*/.guard-transform/*' 2>/dev/null | head -10 || true)
if [ -n "$MAKE_FILES" ]; then
  report "交付物含 Makefile（平台用 install.sh/start.sh/health.sh）:"
  echo "$MAKE_FILES" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面列出的 Makefile / makefile / GNUmakefile。直接 \`rm\` 删除；如有需要的命令把它们搬进 install.sh / start.sh（平台不会执行 make）" >&2
fi

# ---- 3. .env / .env.example 残留 ----
# 注意：.env.development 或 .env.production 等被前端框架内置识别的，由 stage 30 单独处理
ENV_FILES=$(find . -maxdepth 3 -type f \
  \( -name '.env' -o -name '.env.*' -o -name '.envrc' \) \
  -not -path '*/node_modules/*' -not -path '*/.git/*' \
  -not -path '*/.guard-transform/*' -not -path '*/.next/*' \
  -not -path '*/dist/*' -not -path '*/build/*' 2>/dev/null | head -20 || true)
if [ -n "$ENV_FILES" ]; then
  report "交付物含 .env* 文件（平台只读 conf/db.properties + conf/ai.properties，.env 会让运维误改）:"
  echo "$ENV_FILES" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面列出的 .env / .env.* / .envrc。直接 \`rm\` 删除，并把代码中所有 dotenv.config() / load_dotenv() / require('dotenv') import 一并删掉（平台已注入 env，不需要 dotenv 加载；保留 .env 会让运维误以为该改它）" >&2
fi

# ---- 4. docker-compose / kubernetes / helm 配置 ----
K8S_FILES=$(find . -maxdepth 3 -type f \
  \( -name 'kustomization.yaml' -o -name 'kustomization.yml' \
     -o -name 'Chart.yaml' -o -name 'values.yaml' -o -name 'values.yml' \
     -o -name 'skaffold.yaml' -o -name 'skaffold.yml' \) \
  -not -path '*/node_modules/*' -not -path '*/.git/*' \
  -not -path '*/.guard-transform/*' 2>/dev/null | head -10 || true)
if [ -n "$K8S_FILES" ]; then
  report "交付物含 K8s/Helm/Kustomize 配置（平台不用，应删除）:"
  echo "$K8S_FILES" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面列出的 kustomization.yaml / Chart.yaml / values.yaml / skaffold.yaml 直接 \`rm\` 删除（平台自有 Pod 编排，业务不需要也不会读这些）" >&2
fi

# ---- 5. CI 配置文件（项目级）----
CI_DIRS=$(find . -maxdepth 2 -type d \
  \( -name '.github' -o -name '.gitlab' -o -name '.circleci' \
     -o -name '.drone.yml' -o -name '.travis.yml' \) \
  -not -path '*/node_modules/*' 2>/dev/null | head -10 || true)
if [ -n "$CI_DIRS" ]; then
  report "交付物含 CI 配置（应在 stage 30 删除）:"
  echo "$CI_DIRS" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件：上面列出的 .github / .gitlab / .circleci 等目录或 .travis.yml / .drone.yml 文件。直接删除整个目录或文件即可（CI 配置只对原仓库有意义，子应用交付物不需要）" >&2
fi

# ---- 6. tsconfig.json 等开发期 build 配置（仅在源码已被 build 后还存在算冗余）----
# 该项设为 INFO，不算 fail：因为 tsx/ts-node 启动确实需要 tsconfig
TSCONFIG_TOP=$(find . -maxdepth 2 -type f \
  \( -name 'tsconfig*.json' -o -name '.eslintrc*' -o -name '.prettierrc*' \
     -o -name 'jest.config.*' -o -name 'vitest.config.*' \) \
  -not -path '*/node_modules/*' -not -path '*/.git/*' \
  -not -path '*/.guard-transform/*' -not -path '*/dist/*' -not -path '*/build/*' \
  2>/dev/null | head -10 || true)
if [ -n "$TSCONFIG_TOP" ]; then
  echo "[INFO] 检测到顶层开发期配置（如 tsconfig.json 是运行时必需则忽略）:" >&2
  echo "$TSCONFIG_TOP" | sed 's/^/    /' >&2
fi

# ---- 7. README 不算残留，但 CONTRIBUTING / CHANGELOG 等开发文档应清理 ----
DEV_DOCS=$(find . -maxdepth 2 -type f \
  \( -iname 'CONTRIBUTING*' -o -iname 'CHANGELOG*' -o -iname 'CODE_OF_CONDUCT*' \
     -o -iname 'SECURITY.md' -o -iname 'AUTHORS*' \) \
  -not -path '*/node_modules/*' 2>/dev/null | head -10 || true)
if [ -n "$DEV_DOCS" ]; then
  echo "[INFO] 检测到开发期文档（建议清理但不强制）:" >&2
  echo "$DEV_DOCS" | sed 's/^/    /' >&2
fi

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 类开发期残留 - 详见 transform_prompt.md § 七" >&2
  exit 1
fi
echo "[OK] 无开发期残留"
