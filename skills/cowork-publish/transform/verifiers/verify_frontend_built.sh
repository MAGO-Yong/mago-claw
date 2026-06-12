#!/usr/bin/env bash
# 验证：前端工程已经构建（产物已落盘到 dist/build/.next/out/...）。
#
# ★★★ 重要：不允许在 install.sh 中执行前端 build ★★★
# Pod 部署容器资源有限（通常 1C2G），前端 build（webpack/vite/next build）内存开销巨大，
# 在 install.sh 中构建会导致容器 OOM 被 kill → 无限重启。
# 所有前端构建必须在本地 stage 40 完成，产物打进 zip 交付。
#
# 设计动机（必读）：
#   1. install.sh 在 Pod 内跑，**网络受限 + 资源受限**（通常 1C2G，无法 build）
#   2. guard-transform 的设计原则：
#        ★ 唯一正确做法：本地（stage 40）跑前端 build，把 dist/build/.next 等产物打进 zip
#          install.sh 在云端只装 *运行时* 依赖（pip / `npm ci --omit=dev`），不再 build
#        ✗ 禁止：在 install.sh 里加 `npm run build`
#          原因：Pod 内存不足会 OOM → 容器反复重启 → 部署失败
#
# 拦截目标：
#   场景 1：前端缺产物 + install.sh 无 build → 白屏 / 404
#   场景 2：前端缺产物 + install.sh 有 build → OOM 重启（本 verifier 强制拦截）
#
# Skip 条件：
#   - 工程整体不像前端（没有任何前端框架依赖）
#   - 后端为 Next.js standalone（.next/standalone/server.js 已存在，已是构建产物）
#   - .next 已包含 BUILD_ID 等构建标记
#
# 失败时给 LLM autofix 的修复路径（唯一方案：本地构建）：
#   - 直接在 work_dir 跑 npm install + npm run build（verifier autofix 阶段，LLM 有 Bash 工具）
#   - 或修 stack.json 的 frontend_dir 让用户 --from-stage 40 重跑

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

export GVFB_WORK_DIR="$(pwd)"

exec python3 - <<'PY'
"""verify_frontend_built 内嵌脚本。

判定流程：
  1) 在候选目录扫 package.json，识别"前端工程目录"
  2) 对每个前端目录检查构建产物是否存在
  3) 如果全缺 → 进一步看 install.sh 是否有 build 命令兜底
  4) 都没有 → fail，输出明确两条修复方向
"""
import json
import os
import re
import sys
from pathlib import Path

WORK = Path(os.environ["GVFB_WORK_DIR"]).resolve()

# 候选前端目录（顺序无关，全扫一遍）
_CAND_DIRS = [
    ".",
    "frontend", "client", "web", "ui",
    "app", "apps/web", "apps/frontend", "apps/ui", "apps/client", "apps/app",
    "packages/web", "packages/frontend", "packages/ui", "packages/client", "packages/app",
]

# 前端框架检测（package.json 中出现任一即视为前端）
# 注意：用包名严格匹配，避免误判 react-native 等非 web 场景（仍归前端，但产物路径不同）
_FE_FRAMEWORK_KEYS = (
    '"react"', '"react-dom"',
    '"vue"', '"@vue/cli-service"', '"nuxt"', '"nuxt3"',
    '"next"',
    '"vite"',
    '"svelte"', '"@sveltejs/kit"',
    '"@angular/core"',
    '"preact"', '"solid-js"',
    '"@remix-run/react"', '"@remix-run/dev"',
    '"astro"',
)

# 构建产物候选（任一存在视为该目录已构建）
# key: 描述性名字（用于错误信息），value: 相对前端目录的产物探针路径
_BUILD_PROBES = (
    ("dist/index.html",                "Vite / Vue CLI / Rollup SPA"),
    ("dist/index.htm",                 "Vite SPA（极少数 .htm）"),
    ("dist/server/entry.mjs",          "Astro SSR"),
    ("build/index.html",               "Create React App / 旧版 Vue CLI"),
    (".next/BUILD_ID",                 "Next.js（产物已构建）"),
    (".next/standalone/server.js",     "Next.js standalone"),
    ("out/index.html",                 "Next.js export"),
    (".svelte-kit/output/server/index.js", "SvelteKit"),
    (".output/server/index.mjs",       "Nuxt 3"),
    ("dist/spa/index.html",            "Quasar SPA"),
)

# install.sh 中的 build 兜底命令正则（行级匹配，跳过纯注释行）
# 匹配：npm/yarn/pnpm/cnpm/bun [run] build / build:xxx
_INSTALL_SH_BUILD_RE = re.compile(
    r"\b(?:npm|yarn|pnpm|cnpm|bun)\s+(?:run\s+)?build(?:[:\w\-]*)?\b"
)


def _read(p: Path) -> str:
    try:
        return p.read_text(errors="replace")
    except OSError:
        return ""


def _is_frontend_pkg(pkg_path: Path) -> tuple[bool, list[str]]:
    """package.json 是否声明前端框架；返回 (is_frontend, hits)。"""
    text = _read(pkg_path)
    if not text:
        return False, []
    hits = [k.strip('"') for k in _FE_FRAMEWORK_KEYS if k in text]
    if not hits:
        return False, []
    # 必须含 build script 才视为"应当被构建"的前端
    # （某些 monorepo 子包只是组件库，无 build script，跳过）
    try:
        data = json.loads(text)
        scripts = data.get("scripts") or {}
        if not isinstance(scripts, dict):
            return False, hits
        # 含 build 或任一 build:xxx 即可
        has_build = any(
            k == "build" or k.startswith("build:")
            for k in scripts
            if isinstance(k, str)
        )
        if not has_build:
            return False, hits
    except (json.JSONDecodeError, ValueError):
        # JSON 解析失败 → 退化用文本匹配
        if '"build"' not in text:
            return False, hits
    return True, hits


def _has_built_artifacts(fe_dir: Path) -> tuple[bool, list[str]]:
    """检查任一构建产物是否存在；返回 (built, matched_probes)。"""
    matched: list[str] = []
    for probe, label in _BUILD_PROBES:
        if (fe_dir / probe).exists():
            matched.append(f"{probe} ({label})")
    return (len(matched) > 0), matched


def _install_sh_has_build() -> tuple[bool, list[str]]:
    """install.sh 中是否含 npm/yarn/pnpm build 命令；返回 (found, lines)。"""
    install_sh = WORK / "install.sh"
    if not install_sh.is_file():
        return False, []
    matched: list[str] = []
    for lineno, raw in enumerate(_read(install_sh).splitlines(), start=1):
        # 跳过纯注释 / 空行
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # 跳过行内注释后的部分
        no_comment = re.sub(r"#.*$", "", raw)
        if _INSTALL_SH_BUILD_RE.search(no_comment):
            matched.append(f"install.sh:{lineno}: {stripped}")
    return (len(matched) > 0), matched


# ---------- 主流程 ----------
fe_dirs: list[tuple[Path, list[str]]] = []  # [(目录, 命中的框架关键字列表)]
seen: set[Path] = set()

for rel in _CAND_DIRS:
    d = (WORK / rel).resolve()
    if d in seen or not d.is_dir():
        continue
    seen.add(d)
    pkg = d / "package.json"
    if not pkg.is_file():
        continue
    is_fe, hits = _is_frontend_pkg(pkg)
    if is_fe:
        fe_dirs.append((d, hits))

if not fe_dirs:
    print("[OK] 未识别到前端工程（无候选目录的 package.json 含 react/vue/next/vite 等框架 + build script），skip")
    sys.exit(0)

# 对每个前端目录检查产物
missing: list[tuple[Path, list[str]]] = []  # [(目录, 命中的框架)]
built: list[tuple[Path, list[str]]] = []    # [(目录, 命中的产物)]

for fe_dir, hits in fe_dirs:
    has_built, probes = _has_built_artifacts(fe_dir)
    rel = fe_dir.relative_to(WORK).as_posix() or "."
    if has_built:
        built.append((fe_dir, probes))
        print(f"[OK] {rel}: 检测到构建产物 → {', '.join(probes)}")
    else:
        missing.append((fe_dir, hits))

if not missing:
    print(f"[OK] 全部 {len(fe_dirs)} 个前端目录均已构建")
    sys.exit(0)

# 有前端目录缺产物 → 检查 install.sh 是否错误地包含了 build（必须移除）
sh_has_build, sh_lines = _install_sh_has_build()
if sh_has_build:
    print("[FAIL] 前端构建产物缺失，且 install.sh 中包含 build 命令（禁止）", file=sys.stderr)
    print("", file=sys.stderr)
    print("★ install.sh 中的 build 命令必须移除 ★", file=sys.stderr)
    print("  原因：Pod 部署容器资源有限（通常 1C2G），前端 build（webpack/vite/next build）", file=sys.stderr)
    print("  内存开销巨大，在 install.sh 中构建会导致容器 OOM → 无限重启 → 部署失败", file=sys.stderr)
    print("", file=sys.stderr)
    print("  当前 install.sh 中检测到的 build 命令（必须删除）：", file=sys.stderr)
    for line in sh_lines:
        print(f"    {line}", file=sys.stderr)
    print("", file=sys.stderr)
    print("  正确做法：在本地完成前端构建，产物打进 zip 交付（见下方修复路径）", file=sys.stderr)
    print("", file=sys.stderr)

# fail：产物缺失（不论 install.sh 是否有 build，都要求本地构建）
if not sh_has_build:
    print("[FAIL] 前端构建产物缺失；云端部署后会缺前端文件（白屏 / 404）", file=sys.stderr)
    print("", file=sys.stderr)

print("缺产物的前端目录：", file=sys.stderr)
for fe_dir, hits in missing:
    rel = fe_dir.relative_to(WORK).as_posix() or "."
    print(f"  - {rel}/  框架: {', '.join(hits)}", file=sys.stderr)
    print(f"    （已扫但都不存在: {', '.join(p for p, _ in _BUILD_PROBES)}）", file=sys.stderr)
print("", file=sys.stderr)

print("修复路径（唯一方案：本地构建）：", file=sys.stderr)
print("", file=sys.stderr)
print("  ★ 本地构建（与 guard-transform 设计一致，stage 40 阶段完成）", file=sys.stderr)
print("    在每个缺产物的前端目录跑：", file=sys.stderr)
for fe_dir, _ in missing:
    rel = fe_dir.relative_to(WORK).as_posix() or "."
    cd_part = "" if rel == "." else f'cd "{rel}" && '
    print(f"      ({cd_part}npm install && npm run build)", file=sys.stderr)
print("    构建完成后产物（dist/build/.next 等）会被 stage 60 一并打进 zip。", file=sys.stderr)
print("", file=sys.stderr)
print("    根因排查：通常是 stack.json 的 frontend_dir 字段未识别正确，导致 stage 40 漏跑前端 build；", file=sys.stderr)
print("    可同时修 .guard-transform-*-guard/stack.json 的 frontend_dir，下次跑 transform 时 stage 40 自动构建。", file=sys.stderr)
if sh_has_build:
    print("", file=sys.stderr)
    print("  ✗ 同时请从 install.sh 中删除以下 build 命令（禁止在 Pod 内 build，会 OOM）：", file=sys.stderr)
    for line in sh_lines:
        print(f"      {line}", file=sys.stderr)
print("", file=sys.stderr)
sys.exit(1)
PY
