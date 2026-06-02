#!/usr/bin/env bash
# 验证 install.sh 不触发任何公网调用
set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"

cd "$WORK_DIR"

[ -f install.sh ] || { echo "[FAIL] install.sh 不存在" >&2; exit 1; }

fail=0
report() { printf '[FAIL] %s\n' "$*" >&2; fail=$((fail+1)); }

# 允许的内部镜像域
ALLOWED='(xiaohongshu\.com|npmmirror\.com|rednote\.life)'

# 1. 提取所有 https?:// URL
EXT=$(grep -oE 'https?://[a-zA-Z0-9.-]+' install.sh 2>/dev/null \
  | grep -vE "//[^/]*${ALLOWED}" | sort -u || true)
if [ -n "$EXT" ]; then
  report "install.sh 引用公网域名（Pod 无公网，必失败）:"
  echo "$EXT" | sed 's/^/    /' >&2
  echo "[HINT] 目标文件 install.sh：把公网域替换为内部镜像（pip 用 http://pypi.devops.xiaohongshu.com/simple/；npm 用 https://artifacts.devops.xiaohongshu.com/artifactory/api/npm/npm/ 或 .npmrc 配置）" >&2
fi

# 2. 高危公网工具
hits=$(grep -nE '(playwright|puppeteer|@cypress/run)\s+(install|browsers\s+install)' install.sh 2>/dev/null || true)
if [ -n "$hits" ]; then
  report "install.sh 触发浏览器二进制公网下载:"
  echo "$hits" | sed 's/^/    /' >&2
fi

# 3. apt-get / yum / brew
if grep -qE '\b(apt-get|apt|yum|brew|dnf|pacman)\s+(install|update|upgrade)\b' install.sh; then
  report "install.sh 含 OS 包管理器调用（Pod 镜像封闭，装不进）"
  echo "[HINT] 目标文件 install.sh：删除 apt-get/yum/brew 等 OS 包管理器命令；Pod 镜像只有 Python 3 + Node.js + PostgreSQL，业务不能装系统包" >&2
fi

# 4. curl | sh / wget | bash
if grep -qE '(curl|wget)[^|]*\|\s*(sh|bash)' install.sh; then
  report "install.sh 含 curl ... | sh 模式（公网 + 不安全）"
fi

# 5. git clone https://（先抓所有 git clone https，再过滤白名单域）
if grep -oE 'git[[:space:]]+clone[[:space:]]+https://[a-zA-Z0-9.-]+' install.sh 2>/dev/null \
     | grep -vE "$ALLOWED" | grep -q .; then
  report "install.sh 含 git clone 公网仓库"
fi

# 6. pip 必须带内部镜像
if grep -qE '\bpip\s+install' install.sh; then
  if ! grep -qE '\-i\s+http://pypi\.devops\.xiaohongshu\.com' install.sh; then
    report "install.sh 调 pip install 但未指定内部镜像 -i http://pypi.devops.xiaohongshu.com/simple/"
    echo "[HINT] 目标文件 install.sh：所有 pip install 行追加 \`-i http://pypi.devops.xiaohongshu.com/simple/ --trusted-host pypi.devops.xiaohongshu.com\`" >&2
  fi
fi

# 7. npm install 必须用内部 registry（公网 npm registry 在 Pod 上不通）
# 检查策略：install.sh 含 npm/yarn/pnpm install 时，必须或者
#   (a) 同时含 --registry=http://...xiaohongshu.com / npmmirror.com
#   (b) 工程根目录有 .npmrc 指向内部 registry
if grep -qE '\b(npm|yarn|pnpm|cnpm)[[:space:]]+(install|i|ci|add)\b' install.sh; then
  HAS_REG_FLAG=$(grep -nE -- '--registry[= ]https?://[^ ]+' install.sh 2>/dev/null || true)
  HAS_INTERNAL_REG=$(grep -nE -- '--registry[= ]https?://[^ ]*(xiaohongshu\.com|npmmirror\.com|rednote\.life)' install.sh 2>/dev/null || true)

  if [ -n "$HAS_REG_FLAG" ] && [ -z "$HAS_INTERNAL_REG" ]; then
    report "install.sh 含 npm install --registry=公网域（Pod 无公网，必失败）:"
    echo "$HAS_REG_FLAG" | sed 's/^/    /' >&2
  elif [ -z "$HAS_REG_FLAG" ]; then
    # 没显式 --registry：检查 .npmrc
    NPMRC_OK=0
    for f in .npmrc backend/.npmrc frontend/.npmrc apps/*/.npmrc packages/*/.npmrc; do
      [ -f "$f" ] || continue
      if grep -qE '^registry[[:space:]]*=[[:space:]]*https?://[^[:space:]]*(xiaohongshu\.com|npmmirror\.com|rednote\.life)' "$f" 2>/dev/null; then
        NPMRC_OK=1
        break
      fi
    done
    if [ "$NPMRC_OK" = "0" ]; then
      report "install.sh 调 npm/yarn install 但未指定内部 registry，且 .npmrc 未指向内部源（默认会去 https://registry.npmjs.org/，公网必失败）"
      echo "[HINT] 目标文件 .npmrc（工程根目录新建/编辑）：写入一行 \`registry=https://artifacts.devops.xiaohongshu.com/artifactory/api/npm/npm/\`；或在 install.sh 的 npm install 命令上追加 \`--registry=<同上>\`" >&2
    fi
  fi
fi

# 8. .npmrc 不能写公网 registry
for f in .npmrc backend/.npmrc frontend/.npmrc apps/*/.npmrc packages/*/.npmrc; do
  [ -f "$f" ] || continue
  hits=$(grep -nE '^registry[[:space:]]*=[[:space:]]*https?://(registry\.npmjs\.org|registry\.yarnpkg\.com|npm\.pkg\.github\.com|registry\.npmmirror\.com\.cn)' "$f" 2>/dev/null || true)
  # registry.npmjs.org 等公网域名
  hits2=$(grep -nE '^registry[[:space:]]*=[[:space:]]*https?://[^[:space:]]+' "$f" 2>/dev/null \
    | grep -vE '(xiaohongshu\.com|npmmirror\.com|rednote\.life)' || true)
  if [ -n "$hits2" ]; then
    report "$f 含公网 registry（Pod 无公网，必失败）:"
    echo "$hits2" | sed 's/^/    /' >&2
    echo "[HINT] 目标文件 $f：把 registry 行替换为 \`registry=https://artifacts.devops.xiaohongshu.com/artifactory/api/npm/npm/\`" >&2
  fi
done

# 9. requirements.txt 不能含 git+https://github.com/ 等公网仓库
for req in requirements.txt backend/requirements.txt apps/*/requirements.txt; do
  [ -f "$req" ] || continue
  hits=$(grep -nE '^[[:space:]]*(git\+|hg\+|bzr\+|svn\+)?https?://' "$req" 2>/dev/null \
    | grep -vE '(xiaohongshu\.com|npmmirror\.com|rednote\.life)' \
    | grep -vE '^\s*[0-9]+:#' || true)
  if [ -n "$hits" ]; then
    report "$req 含公网 URL 依赖（Pod 装不下来）:"
    echo "$hits" | sed 's/^/    /' >&2
  fi
done

if [ "$fail" -gt 0 ]; then
  echo "[FAIL] $fail 项公网调用风险" >&2
  exit 1
fi
echo "[OK] install.sh 无公网调用"
