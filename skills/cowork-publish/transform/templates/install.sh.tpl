#!/usr/bin/env bash
# install.sh - Pod 解压后跑一次
# 由 guard-transform 模板渲染生成；shebang / set / 镜像参数已写死，请勿手改
set -eo pipefail
cd "$(dirname "$0")"

# monorepo 后端子目录（空字符串表示单仓，pip/npm 直接在顶层执行）
BACKEND_DIR="${TPL_BACKEND_DIR}"

echo "[install] step: start (backend_dir='${BACKEND_DIR}')"

# 切到 backend 目录的 helper：单仓时是 no-op
_cd_backend() {
  if [ -n "$BACKEND_DIR" ] && [ -d "$BACKEND_DIR" ]; then
    cd "$BACKEND_DIR"
  fi
}

if [ "${TPL_HAS_PYTHON_DEPS}" = "1" ]; then
  (
    _cd_backend
    if [ -f requirements.txt ]; then
      # Linux 上使用 venv 隔离，避免 pip 全局安装污染系统
      if [ "$(uname)" = "Linux" ]; then
        echo "[install] step: create venv + pip install (venv 隔离, 内部镜像) in $(pwd)"
        python3 -m venv .venv
        . .venv/bin/activate
        pip install --no-cache-dir -r requirements.txt \
          -i http://pypi.devops.xiaohongshu.com/simple/ \
          --trusted-host pypi.devops.xiaohongshu.com 2>&1
        deactivate
      else
        echo "[install] step: pip install (内部镜像) in $(pwd)"
        python -m pip install --no-cache-dir -r requirements.txt \
          -i http://pypi.devops.xiaohongshu.com/simple/ \
          --trusted-host pypi.devops.xiaohongshu.com 2>&1
      fi
    fi
  )
fi

if [ "${TPL_HAS_NODE_DEPS}" = "1" ]; then
  (
    _cd_backend
    # Next.js standalone 通常自带 node_modules，可跳过
    if [ -f package.json ] && [ ! -f .next/standalone/server.js ]; then
      echo "[install] step: npm ci --omit=dev in $(pwd)"
      # .npmrc 已打进 zip，自动走内部双路 registry
      npm ci --omit=dev 2>&1
    fi
  )
fi

# ── 纯前端 SPA 托管 runtime（仅 server.cjs 依赖的 serve-handler）─────────────
# 设计：业务 package.json 通常只声明 build 期 devDependencies（vite/react/...），
# 生产 Pod 不需要这些。我们把托管层依赖（serve-handler）隔离到 .guard-runtime/
# 子目录，单独装一个 package.json，避免：
#   1) 改业务 package.json（破坏 package-lock 一致性，npm ci 失败）
#   2) 在业务根目录跑 npm install（重新解析全部 deps，浪费 + 可能拉公网）
# server.cjs 通过 require('.guard-runtime/node_modules/serve-handler') 引用
if [ "${TPL_NEEDS_STATIC_RUNTIME}" = "1" ]; then
  echo "[install] step: setup .guard-runtime/ for static serving (serve-handler)"
  mkdir -p .guard-runtime
  # 不存在则写一份最小 package.json；存在则保留（支持后续手动加钉版本）
  if [ ! -f .guard-runtime/package.json ]; then
    cat > .guard-runtime/package.json <<'JSON'
{
  "name": "guard-static-runtime",
  "version": "1.0.0",
  "private": true,
  "description": "guard-transform 渲染的纯前端托管 runtime，仅含 server.cjs 所需依赖",
  "dependencies": {
    "serve-handler": "^6.1.5"
  }
}
JSON
  fi
  (
    cd .guard-runtime
    # 继承上级 .npmrc（双路内部镜像）；无 lock 走 npm install
    if [ -f package-lock.json ]; then
      npm ci --omit=dev 2>&1
    else
      npm install --no-audit --prefer-offline --omit=dev 2>&1
    fi
  )
fi

if [ "${TPL_NEEDS_DB_INIT}" = "1" ]; then
  (
    _cd_backend
    # Linux 上 Python 脚本需激活 venv（install 阶段已创建）
    if [ "$(uname)" = "Linux" ] && [ -f .venv/bin/activate ]; then
      . .venv/bin/activate
    fi
    echo "[install] step: db init (DDL + DML) in $(pwd)"
    if [ -f app/init_db.py ]; then
      python -m app.init_db 2>&1
    elif [ -f init_db.py ]; then
      python init_db.py 2>&1
    elif [ -f dist/init_db.js ]; then
      node dist/init_db.js 2>&1
    elif [ -f init_db.js ]; then
      node init_db.js 2>&1
    fi

    if [ -f app/seed_db.py ]; then
      echo "[install] step: db seed"
      python -m app.seed_db 2>&1
    elif [ -f dist/seed_db.js ]; then
      echo "[install] step: db seed"
      node dist/seed_db.js 2>&1
    fi
  )
fi

echo "[install] done"
