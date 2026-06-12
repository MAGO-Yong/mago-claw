#!/usr/bin/env bash
# 验证：package.json 与 package-lock.json 同步。
#
# 拦截目标：
#   云端 install.sh 里跑 `npm ci --omit=dev`，要求 lock 与 package.json 完全一致。
#   开发机改了 package.json 没重新生成 lock 时，Pod 上会直接挂：
#       npm error `npm ci` can only install packages when your package.json
#       and package-lock.json or npm-shrinkwrap.json are in sync.
#       npm error Invalid: lock file's picomatch@2.3.2 does not satisfy picomatch@4.0.4
#   本 verifier 在打包前就把这种漂移拦下来。
#
# 检查方式（纯文本对比，不调 npm，无网络/无 node 依赖）：
#   1. 找所有候选 Node 目录（同 verify_frontend_built 的目录列表 + 后端 backend/server）
#   2. 对每个含 package.json + package-lock.json 的目录：
#       a. 读 package.json 的 dependencies / devDependencies / optionalDependencies / peerDependencies
#       b. 读 package-lock.json (lockfileVersion 2/3) 的 packages[""].dependencies/...
#       c. 两者键集合 + 每个键的 range 字符串必须严格相等
#       d. 对每个声明的依赖，packages["node_modules/<name>"] 必须存在且 version 符合 range
#   3. 不一致 → fail，列出差异 + 修复命令
#
# Skip 条件：
#   - 目录无 package.json
#   - 目录无 package-lock.json（用户走 yarn.lock / pnpm-lock.yaml，本 verifier 不管）
#   - lockfileVersion < 2（npm 6 / 老格式，packages 字段不存在；这种工程不该用 npm ci）

set -eo pipefail
WORK_DIR="${1:?usage: $0 <work_dir>}"
cd "$WORK_DIR"

export GVNL_WORK_DIR="$(pwd)"

exec python3 - <<'PY'
"""verify_npm_lock_sync 内嵌脚本。

判定：在每个候选 Node 目录里把 package.json 与 package-lock.json 的顶层依赖
（packages[""]）做严格 key+range 对比，再对每个声明的依赖检查 lock 中的解析
版本是否落在 range 内（用本地实现的最小子集 semver 判定）。
"""
import json
import os
import re
import sys
from pathlib import Path

WORK = Path(os.environ["GVNL_WORK_DIR"]).resolve()

# 候选目录：与 verify_frontend_built 一致 + 常见后端目录
_CAND_DIRS = [
    ".",
    "frontend", "client", "web", "ui",
    "backend", "server", "api",
    "app", "apps/web", "apps/frontend", "apps/ui", "apps/client", "apps/app",
    "apps/backend", "apps/server", "apps/api",
    "packages/web", "packages/frontend", "packages/ui", "packages/client", "packages/app",
    "packages/backend", "packages/server", "packages/api",
]

_DEP_FIELDS = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(errors="replace"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


# --------- 极简 semver 子集判定（覆盖 ^X.Y.Z / ~X.Y.Z / X.Y.Z / X / >=X.Y.Z 等常见 range） ---
# 不实现完整 spec：URL / git / file: / npm: alias 直接放过（不参与 range 判定）。
_NUM = r"(\d+)\.(\d+)\.(\d+)"
_PARSE_RE = re.compile(r"^\s*([\^~><=]*)?\s*v?" + _NUM + r"(?:[-+][\w.\-]+)?\s*$")


def _parse_ver(v: str):
    m = re.match(r"^v?" + _NUM + r"(?:[-+][\w.\-]+)?$", v.strip())
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def _range_satisfied(range_str: str, ver: str) -> bool:
    """返回 lock 解析出的 ver 是否满足 package.json 的 range_str。

    无法解析的 range / ver 一律返回 True（保守通过，避免误报；npm ci 自己最后会再检查）。
    """
    if not range_str or not ver:
        return True
    rs = range_str.strip()
    # URL / 文件 / git / npm: alias / workspace: / "*" / "" → 不判定
    if any(rs.startswith(p) for p in ("http", "git", "file:", "npm:", "workspace:", "link:", "portal:")):
        return True
    if rs in ("*", "x", "X", "latest", ""):
        return True
    parsed = _parse_ver(ver)
    if not parsed:
        return True
    # 拆 OR （||）和 AND（空格）；只要任一 AND 组合全过 → 通过
    for or_part in re.split(r"\s*\|\|\s*", rs):
        ok = True
        for tok in or_part.strip().split():
            if not _check_token(tok, parsed):
                ok = False
                break
        if ok:
            return True
    return False


def _check_token(tok: str, ver: tuple) -> bool:
    m = _PARSE_RE.match(tok)
    if not m:
        # hyphen range / pre-release / 复杂表达，保守通过
        return True
    op = (m.group(1) or "").strip()
    rmajor, rminor, rpatch = int(m.group(2)), int(m.group(3)), int(m.group(4))
    vmajor, vminor, vpatch = ver
    if op == "" or op == "=" or op == "==":
        return ver == (rmajor, rminor, rpatch)
    if op == "^":
        # ^1.2.3 -> >=1.2.3 <2.0.0；^0.2.3 -> >=0.2.3 <0.3.0；^0.0.3 -> ==0.0.3
        if rmajor > 0:
            return ver >= (rmajor, rminor, rpatch) and vmajor == rmajor
        if rminor > 0:
            return ver >= (rmajor, rminor, rpatch) and (vmajor, vminor) == (rmajor, rminor)
        return ver == (rmajor, rminor, rpatch)
    if op == "~":
        # ~1.2.3 -> >=1.2.3 <1.3.0
        return ver >= (rmajor, rminor, rpatch) and (vmajor, vminor) == (rmajor, rminor)
    if op == ">=":
        return ver >= (rmajor, rminor, rpatch)
    if op == ">":
        return ver > (rmajor, rminor, rpatch)
    if op == "<=":
        return ver <= (rmajor, rminor, rpatch)
    if op == "<":
        return ver < (rmajor, rminor, rpatch)
    return True


def _check_dir(d: Path):
    """检查单个 Node 目录；返回 (status, errors)
    status: "ok" / "fail" / "skip"
    errors: list[str]
    """
    pj = d / "package.json"
    pl = d / "package-lock.json"
    if not pj.is_file():
        return "skip", []
    if not pl.is_file():
        return "skip", []  # 走 yarn / pnpm / 无 lock，不归本 verifier 管
    pj_data = _read_json(pj)
    pl_data = _read_json(pl)
    if pj_data is None or pl_data is None:
        return "fail", [f"无法解析 {pj.relative_to(WORK)} 或 {pl.relative_to(WORK)}（JSON 损坏）"]

    lock_ver = pl_data.get("lockfileVersion")
    if not isinstance(lock_ver, int) or lock_ver < 2:
        return "skip", []  # npm 6 旧格式，packages[""] 不存在；不应配 npm ci

    pkgs = pl_data.get("packages") or {}
    if not isinstance(pkgs, dict):
        return "fail", ["package-lock.json 缺少顶层 packages 字段"]
    root = pkgs.get("") or {}

    errors = []

    # 1. 顶层 deps/devDeps/... 严格对齐
    for fld in _DEP_FIELDS:
        pj_fld = pj_data.get(fld) or {}
        rt_fld = root.get(fld) or {}
        if not isinstance(pj_fld, dict):
            pj_fld = {}
        if not isinstance(rt_fld, dict):
            rt_fld = {}
        only_in_pj = sorted(set(pj_fld) - set(rt_fld))
        only_in_lock = sorted(set(rt_fld) - set(pj_fld))
        for k in only_in_pj:
            errors.append(f"{fld}: lock 缺少 `{k}@{pj_fld[k]}`（package.json 已声明）")
        for k in only_in_lock:
            errors.append(f"{fld}: lock 多了 `{k}@{rt_fld[k]}`（package.json 未声明）")
        for k in sorted(set(pj_fld) & set(rt_fld)):
            if pj_fld[k] != rt_fld[k]:
                errors.append(
                    f"{fld}: range 不一致 `{k}`: package.json=`{pj_fld[k]}` vs lock=`{rt_fld[k]}`"
                )

    # 2. 每个声明的依赖必须在 lock 中有对应解析项，且 version 满足 range
    seen = set()
    for fld in _DEP_FIELDS:
        pj_fld = pj_data.get(fld) or {}
        if not isinstance(pj_fld, dict):
            continue
        for name, range_str in pj_fld.items():
            if name in seen:
                continue
            seen.add(name)
            entry = pkgs.get(f"node_modules/{name}")
            if not entry:
                # 已被上面"only_in_pj"覆盖（缺顶层声明），跳过避免重复报
                continue
            ver = entry.get("version") if isinstance(entry, dict) else None
            if ver and not _range_satisfied(range_str, ver):
                errors.append(
                    f"resolved 不满足 range: `{name}` package.json=`{range_str}` "
                    f"但 lock 解析为 `{ver}`"
                )

    if errors:
        return "fail", errors
    return "ok", []


# ---------- 主流程 ----------
checked = []
failed = []

seen_dirs = set()
for rel in _CAND_DIRS:
    d = (WORK / rel).resolve()
    if d in seen_dirs or not d.is_dir():
        continue
    seen_dirs.add(d)
    status, errs = _check_dir(d)
    rel_d = d.relative_to(WORK).as_posix() or "."
    if status == "skip":
        continue
    checked.append(rel_d)
    if status == "fail":
        failed.append((rel_d, errs))

if not checked:
    print("[OK] 未发现含 package-lock.json 的 Node 目录，skip")
    sys.exit(0)

if not failed:
    print(f"[OK] 检查 {len(checked)} 个 Node 目录的 package.json ↔ package-lock.json 一致性: {', '.join(checked)}")
    sys.exit(0)

# fail 输出
print("[FAIL] package.json 与 package-lock.json 漂移；云端 `npm ci --omit=dev` 会直接报错并部署失败", file=sys.stderr)
print("", file=sys.stderr)
print("典型云端报错：", file=sys.stderr)
print("  npm error `npm ci` can only install packages when your package.json", file=sys.stderr)
print("  and package-lock.json or npm-shrinkwrap.json are in sync.", file=sys.stderr)
print("  npm error Invalid: lock file's <pkg>@<a> does not satisfy <pkg>@<b>", file=sys.stderr)
print("", file=sys.stderr)
print("漂移详情：", file=sys.stderr)
for rel_d, errs in failed:
    print(f"  目录 {rel_d}/", file=sys.stderr)
    for e in errs:
        print(f"    - {e}", file=sys.stderr)
print("", file=sys.stderr)
print("修复路径：", file=sys.stderr)
print("  在每个有问题的目录里重新生成 lock 并提交：", file=sys.stderr)
for rel_d, _ in failed:
    cd_part = "" if rel_d == "." else f'cd "{rel_d}" && '
    print(f"    ({cd_part}npm install --package-lock-only --no-audit)", file=sys.stderr)
print("    然后 git add package-lock.json && git commit", file=sys.stderr)
print("", file=sys.stderr)
print("  说明：`--package-lock-only` 只更新 lock 不动 node_modules，速度快；", file=sys.stderr)
print("        若需要本地实际验证可用 `npm install` 全量装一次。", file=sys.stderr)
print("", file=sys.stderr)
print("  注意：不要用 `npm install --no-package-lock` 或删除 lock 来绕过——", file=sys.stderr)
print("        云端 install.sh 走 `npm ci --omit=dev`，**必须**有一致的 lock。", file=sys.stderr)
sys.exit(1)
PY
