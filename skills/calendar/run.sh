#!/usr/bin/env bash

set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  TARGET="$(readlink "$SOURCE")"
  if [[ "$TARGET" != /* ]]; then
    TARGET="$DIR/$TARGET"
  fi
  SOURCE="$TARGET"
done

SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
CLI_BIN="$SCRIPT_DIR/build/cli.js"

NEED_INSTALL=0
if [ ! -d "$SCRIPT_DIR/node_modules" ]; then
  NEED_INSTALL=1
elif [ "$SCRIPT_DIR/package-lock.json" -nt "$SCRIPT_DIR/node_modules/.package-lock.json" ]; then
  NEED_INSTALL=1
fi

if [ "$NEED_INSTALL" -eq 1 ]; then
  echo "正在安装依赖，请稍候..." >&2
  ( cd "$SCRIPT_DIR" && npm ci --ignore-scripts )
fi

NEED_BUILD=0
if [ ! -f "$CLI_BIN" ]; then
  NEED_BUILD=1
elif [ "$SCRIPT_DIR/package.json" -nt "$CLI_BIN" ]; then
  NEED_BUILD=1
fi

if [ "$NEED_BUILD" -eq 1 ]; then
  echo "正在编译，请稍候..." >&2
  ( cd "$SCRIPT_DIR" && npm run build )
fi

exec node "$CLI_BIN" "$@"
