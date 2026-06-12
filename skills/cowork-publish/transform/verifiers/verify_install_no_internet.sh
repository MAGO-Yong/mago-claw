#!/usr/bin/env bash
# 验证 install.sh 不在脚本里硬编码任何包管理器源 / 公网下载危险动作
#
# 设计原则（2026-05 更新）：
#   - install.sh 内**不指定** pip / npm 源——交给 Pod 环境的 PIP_INDEX_URL /
#     .npmrc / NPM_CONFIG_REGISTRY 等运行时配置注入，避免把镜像 URL 写死在交付物里
#   - 仍然拦截肯定会失败 / 不安全的动作：apt-get/yum/brew、curl|sh、git clone https、
#     playwright/puppeteer browsers install、requirements.txt 里的 VCS URL 依赖
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

[ -f install.sh ] || { echo "[FAIL] install.sh 不存在" >&2; exit 1; }

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# 1. 高危公网工具（浏览器二进制下载）
hits=$(grep -nE '(playwright|puppeteer|@cypress/run)\s+(install|browsers\s+install)' install.sh 2>/dev/null || true)
if [ -n "$hits" ]; then
  report "install.sh 触发浏览器二进制公网下载:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# 2. apt-get / yum / brew
if grep -qE '\b(apt-get|apt|yum|brew|dnf|pacman)\s+(install|update|upgrade)\b' install.sh; then
  report "install.sh 含 OS 包管理器调用（Pod 镜像封闭，装不进）"
  echo "[HINT] 目标文件 install.sh：删除 apt-get/yum/brew 等 OS 包管理器命令；Pod 镜像只有 Python 3 + Node.js + PostgreSQL，业务不能装系统包" >&2
fi

# 3. curl | sh / wget | bash
if grep -qE '(curl|wget)[^|]*\|\s*(sh|bash)' install.sh; then
  report "install.sh 含 curl ... | sh 模式（公网 + 不安全）"
fi

# 4. git clone https：任何 git clone https 都不允许（业务依赖应通过 pip / npm 装，不该克隆源仓库）
if grep -qE 'git[[:space:]]+clone[[:space:]]+https?://' install.sh; then
  report "install.sh 含 git clone 命令（依赖请走 requirements.txt / package.json，不要在 install.sh 里克隆源仓库）"
fi

# 5. pip / npm 不应在 install.sh 里硬编码源（让运行时环境决定）
if grep -qE '\bpip[3]?[[:space:]]+install[^\n]*[[:space:]](-i|--index-url|--extra-index-url|--trusted-host)[[:space:]]' install.sh; then
  report "install.sh 在 pip install 行里硬编码了源参数（-i / --index-url / --trusted-host）"
  echo "[HINT] 目标文件 install.sh：删除 pip install 后面的 \`-i ...\` / \`--index-url ...\` / \`--trusted-host ...\`；如需走内部镜像，请在 Pod 启动环境用 PIP_INDEX_URL / PIP_TRUSTED_HOST 注入" >&2
fi
if grep -qE '\b(npm|yarn|pnpm|cnpm)[[:space:]]+(install|i|ci|add)[^\n]*--registry[= ]https?://' install.sh; then
  report "install.sh 在 npm install 行里硬编码了 --registry=<URL>"
  echo "[HINT] 目标文件 install.sh：删除 npm install 后面的 \`--registry=...\`；如需走内部 registry，请在工程根的 npm 配置文件或 Pod 环境的 NPM_CONFIG_REGISTRY 配置" >&2
fi

# 6. requirements.txt 不能含 VCS URL 依赖（git+https / hg+https / svn+https / bzr+https）
#    无论公网内网都不允许，避免 install.sh 跑时联网拉源
for req in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
  [ -f "$req" ] || continue
  hits=$(grep -nE '^[[:space:]]*(git\+|hg\+|bzr\+|svn\+)https?://' "$req" 2>/dev/null \
    | grep -vE '^\s*[0-9]+:#' || true)
  if [ -n "$hits" ]; then
    report "$req 含 VCS URL 依赖（git+https / hg+https 等；改用 PyPI 包名 + 版本号）:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
done

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项公网调用风险" >&2
  exit 1
fi
echo "[OK] install.sh 无公网调用 / 硬编码源问题"
