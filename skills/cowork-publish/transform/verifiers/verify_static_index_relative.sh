#!/usr/bin/env bash
# 验证：纯前端项目构建产物 index.html 中的静态资源引用必须是相对路径。
#
# 平台模式：纯前端子应用仅托管静态产物（dist/index.html 等），
# 平台运行时会把它们挂在某个不固定的 URL 前缀下（如 /apps/<id>/）。
# 这意味着 index.html 里若用 "/" 或 "//" 开头的资源 URL 会指向 Pod 根路径
# 或其它域名，加载到 404 / CORS 错误，前端白屏。
#
# 唯一正确做法：构建工具配置 base="./"（Vite）或 publicPath="./"（Webpack 等），
# 让产物里的 <script src=...> / <link href=...> / <img src=...> 都用 "./"
# 这种相对当前文档的路径形式。
#
# 检查项：
#   1) index.html 必须存在（dist/index.html / build/index.html / out/index.html / 顶层）
#   2) 资源属性（script/link/img/source/iframe/video/audio 的 src/href）：
#      - 不得以 "/" 开头（绝对根路径）
#      - 不得以 "//" 开头（协议相对，会跨域）
#      - 允许：./xxx / xxx / 完整 http(s):// URL（外部 CDN，warn）
#
# 执行条件：
#   - stack.frontend_only=1，或
#   - work_dir 下存在 dist/index.html / build/index.html / out/index.html 之一

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

# 找 index.html 候选；按优先级取第一个存在的
INDEX_HTML=""
for cand in dist/index.html build/index.html out/index.html index.html; do
  if [ -f "$cand" ]; then
    INDEX_HTML="$cand"
    break
  fi
done

# 决定是否执行
FRONTEND_ONLY=0
if [ -n "${STATE_DIR:-}" ] && [ -f "$STATE_DIR/stack.json" ]; then
  if grep -q '"frontend_only"[[:space:]]*:[[:space:]]*1' "$STATE_DIR/stack.json"; then
    FRONTEND_ONLY=1
  fi
fi

if [ "$FRONTEND_ONLY" = "0" ] && [ -z "$INDEX_HTML" ]; then
  echo "[OK] 非 frontend_only 且未发现 dist/build/out/index.html，skip"
  exit 0
fi

if [ -z "$INDEX_HTML" ]; then
  echo "[FAIL] frontend_only 项目找不到 index.html（已扫: dist/index.html build/index.html out/index.html index.html）" >&2
  echo "[HINT] 确认 stage 40 已成功 build；产物应该落在 dist/ 或 build/ 下" >&2
  exit 1
fi

echo "[INFO] 检查 $INDEX_HTML 资源引用相对路径合规性"

export GVSI_INDEX="$INDEX_HTML"

exec python3 - <<'PY'
"""扫 index.html 中的资源属性，要求路径不以 `/` 或 `//` 开头。

只看 src= / href= 这两类属性；忽略 data-/aria-/style 内联值（它们不直接触发资源加载，
或由 verify_css_no_abs_url 等其他 verifier 单独处理）。

正则匹配 HTML 里 src="..." / src='...' / href="..." / href='...'，
路径直接以 / 开头（不允许）或 // 开头（不允许）即报错。

允许：
  ./...   ../...     —— 相对当前文档
  data:   blob:      —— inline 数据
  http://  https://  —— 完整外部 URL（warn）
  #anchor / mailto:/javascript:/  —— 非资源 URL，跳过
  ?query  —— 同源查询，跳过
"""
import os
import re
import sys

p = os.environ["GVSI_INDEX"]
try:
    with open(p, encoding="utf-8", errors="replace") as f:
        text = f.read()
except OSError as e:
    print(f"[FAIL] 读 {p} 失败: {e}", file=sys.stderr)
    sys.exit(1)

# 抓取 src="..." / src='...' / href="..." / href='...'
attr_re = re.compile(
    r"""\b(?P<attr>src|href)\s*=\s*(?P<q>['"])(?P<val>[^'"]*)(?P=q)""",
    re.IGNORECASE,
)

bad = []  # (line_no, attr, value, reason)
warn_external = []
total = 0

for m in attr_re.finditer(text):
    total += 1
    val = m.group("val").strip()
    if not val:
        continue
    # 跳过非资源 URL
    if val.startswith(("#", "mailto:", "tel:", "javascript:", "data:", "blob:", "?")):
        continue
    # 协议相对（//cdn.example.com/...）
    if val.startswith("//"):
        line = text[: m.start()].count("\n") + 1
        bad.append((line, m.group("attr"), val, "以 // 开头（协议相对路径，跨域加载）"))
        continue
    # 绝对根路径（/static/...）
    if val.startswith("/"):
        line = text[: m.start()].count("\n") + 1
        bad.append((line, m.group("attr"), val, "以 / 开头（绝对根路径，平台 URL 前缀不固定会 404）"))
        continue
    # 完整外部 URL
    if val.startswith(("http://", "https://")):
        warn_external.append((m.group("attr"), val))
        continue

if warn_external:
    print(f"[INFO] 发现 {len(warn_external)} 处外部 URL 资源引用（CDN 等，请确认网络可达）：")
    for attr, val in warn_external[:5]:
        print(f"    {attr}={val}")
    if len(warn_external) > 5:
        print(f"    ...（共 {len(warn_external)} 处）")

if not bad:
    print(f"[OK] {p} 共扫描 {total} 处 src/href 属性，资源引用均为相对路径")
    sys.exit(0)

print(f"[FAIL] {p} 发现 {len(bad)} 处绝对路径资源引用（必须改为相对路径 ./xxx）：", file=sys.stderr)
for line, attr, val, reason in bad[:20]:
    print(f"    第 {line} 行: {attr}=\"{val}\"  ← {reason}", file=sys.stderr)
if len(bad) > 20:
    print(f"    ...（共 {len(bad)} 处）", file=sys.stderr)

print("", file=sys.stderr)
print("[HINT] 修复方法（按构建工具）：", file=sys.stderr)
print("  - Vite: 在 vite.config.ts 里设 `base: './'`（默认 '/' 会让产物用绝对路径）", file=sys.stderr)
print("  - Webpack/CRA: 在 package.json 设 `\"homepage\": \".\"`，或 webpack.config 的 `output.publicPath = './'`", file=sys.stderr)
print("  - Rollup: `output.format = 'es'` + 入口 HTML 引用用 './'", file=sys.stderr)
print("  - Parcel: `--public-url ./` 或 package.json `\"targets\": { ... \"publicUrl\": \"./\" }`", file=sys.stderr)
print("  改完后重新 build，让 dist/index.html 里的 <script src> / <link href> 都以 './' 开头", file=sys.stderr)
sys.exit(1)
PY
