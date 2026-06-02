"""stage 30: 用模板渲染 install.sh / start.sh / health.sh / .npmrc。

完全机械——不交给 LLM。模板里的 shebang / set -eo pipefail / chmod / 镜像参数
都已写死，本 stage **只**负责把 ${TPL_xxx} 占位符替换为运行时变量。

替换语义（与 bash envsubst "$TPL_VARS" 严格对齐）：
  - 只替换以 `TPL_` 开头的变量，避免误吃模板里的 `$(pwd)` / `${BACKEND_DIR}` 等
    shell 自身变量；
  - 未定义的 TPL_xxx 替换为空串。

stage 完成后立刻跑 3 个基础 verifier 验证模板正确性，失败即按 strict / autofix 策略处理。
"""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path

from .. import config, git, log, verifier

# 仅替换 ${TPL_xxx}（白名单）；其他 ${...} 原样保留
_TPL_PATTERN = re.compile(r"\$\{(TPL_[A-Za-z_][A-Za-z_0-9]*)\}")


def _stack_get(state_dir: Path, key: str) -> str:
    try:
        data = json.loads((state_dir / "stack.json").read_text())
    except (OSError, json.JSONDecodeError):
        log.die("stack.json 不存在或损坏，未跑 stage 10？")
    val = data.get(key, "")
    return "" if val is None else str(val)


def _entry_to_module(entry: str, backend_dir: str) -> str:
    """entry 相对 backend_dir 转 module 路径。

    例：entry=backend/app/main.py, backend_dir=backend → app.main
    例：entry=app/main.py,         backend_dir=""      → app.main
    """
    e = entry
    if backend_dir and e.startswith(backend_dir + "/"):
        e = e[len(backend_dir) + 1 :]
    if e.endswith(".py"):
        e = e[:-3]
    return e.replace("/", ".")


def _build_tpl_vars(stack: dict) -> dict[str, str]:
    """根据 stack 派生所有 TPL_ 渲染变量。"""
    lang = str(stack.get("lang", ""))
    framework = str(stack.get("framework", ""))
    entry = str(stack.get("entry", ""))
    has_db = str(stack.get("has_db", ""))
    backend_dir = str(stack.get("backend_dir", "") or "")
    frontend_dir = str(stack.get("frontend_dir", "") or "")

    tpl: dict[str, str] = {
        "TPL_HAS_PYTHON_DEPS": "0",
        "TPL_HAS_NODE_DEPS": "0",
        "TPL_NEEDS_DB_INIT": "1" if has_db == "1" else "0",
        # 纯前端 SPA 专用：是否需要在 Pod 上单独建 .guard-runtime/ 装 serve-handler
        # （仅 framework=vite-spa 等纯静态 SPA 时为 "1"，对应渲染 server.cjs 入口）
        "TPL_NEEDS_STATIC_RUNTIME": "0",
        # 纯前端首选静态目录；server.cjs 启动时按 [TPL_STATIC_DIR, dist, build, out, public] 顺序探测
        "TPL_STATIC_DIR": "dist",
        "TPL_START_CMD": "",
        "TPL_VENV_ACTIVATE": "",
        "TPL_BACKEND_DIR": backend_dir,
        "TPL_FRONTEND_DIR": frontend_dir,
    }

    if lang == "python":
        tpl["TPL_HAS_PYTHON_DEPS"] = "1"
        # Linux 上 venv 路径（install.sh 在后端目录下创建 .venv）
        venv_path = f"{backend_dir}/.venv" if backend_dir else ".venv"
        # 注意：不再依赖 `source .venv/bin/activate` + exec 的组合。
        # 原因：exec 会替换当前 shell 进程，venv 激活只修改了当前 shell 的 PATH，
        # 但 exec 之后 shell 环境被替换，python3/gunicorn 解析走系统 PATH，
        # 导致 "No module named gunicorn" 等错误。
        # 修复：直接用 .venv/bin/python 绝对路径，完全绕开 venv 激活的不确定性；
        # 非 Linux（本地 macOS 开发）回退到系统 python3。
        tpl["TPL_VENV_ACTIVATE"] = (
            '# Linux 上用 .venv 绝对路径调用 python，避免 exec 替换 shell 后 PATH 失效\n'
            f'if [ "$(uname)" = "Linux" ] && [ -f "{venv_path}/bin/python" ]; then\n'
            f'  PYTHON="{venv_path}/bin/python"\n'
            'else\n'
            '  PYTHON="python3"\n'
            'fi'
        )
        # 统一注入 APP_PORT 字面量：
        #   ① verify_app_env_naming.sh 要求 start.sh 必须含 APP_PORT 引用
        #      （平台只允许业务读 APP_* 前缀 env；裸 PORT/HOSTNAME 平台不注入）
        #   ② verify_port_3000.sh 要求端口 **不得硬编码** ——
        #      必须使用 `APP_PORT="${APP_PORT:-3000}"` 默认值兜底语法，
        #      并在 exec 行用 `${APP_PORT}` 引用，使蓝绿期外部注入的
        #      APP_PORT=3001 不会被本行 export 覆盖。
        #   ③ exec 命令引用 ${APP_PORT} 让端口源于显式声明，未来想换端口只需
        #      改一处 export 即可
        if framework == "fastapi":
            mod = _entry_to_module(entry, backend_dir)
            # uvicorn 同样用 $PYTHON 绝对路径，与 flask/django 保持一致
            cmd = (
                'export APP_PORT="${APP_PORT:-3000}"\n'
                f'exec $PYTHON -m uvicorn {mod}:app --host 0.0.0.0 --port ${{APP_PORT}}'
            )
            if backend_dir:
                tpl["TPL_START_CMD"] = (
                    f'cd "$(dirname "$0")/{backend_dir}"\n{cmd}'
                )
            else:
                tpl["TPL_START_CMD"] = cmd
        elif framework == "flask":
            mod = _entry_to_module(entry, backend_dir)
            # 直接用 $PYTHON -m gunicorn，不依赖 PATH 里的 gunicorn 可执行文件
            cmd = (
                'export APP_PORT="${APP_PORT:-3000}"\n'
                f"exec $PYTHON -m gunicorn --bind 0.0.0.0:${{APP_PORT}} {mod}:app"
            )
            if backend_dir:
                tpl["TPL_START_CMD"] = (
                    f'cd "$(dirname "$0")/{backend_dir}"\n{cmd}'
                )
            else:
                tpl["TPL_START_CMD"] = cmd
        elif framework == "django":
            # 直接用 $PYTHON -m gunicorn，不依赖 PATH 里的 gunicorn 可执行文件
            cmd = (
                'export APP_PORT="${APP_PORT:-3000}"\n'
                "exec $PYTHON -m gunicorn --bind 0.0.0.0:${APP_PORT} wsgi:application"
            )
            if backend_dir:
                tpl["TPL_START_CMD"] = (
                    f'cd "$(dirname "$0")/{backend_dir}"\n{cmd}'
                )
            else:
                tpl["TPL_START_CMD"] = cmd
        else:
            tpl["TPL_START_CMD"] = (
                f"# TODO: Python 框架 {framework} 未识别，"
                "自行补齐启动命令并保证 listen 0.0.0.0:${APP_PORT}；"
                '记得 export APP_PORT="${APP_PORT:-3000}" 满足平台 env 命名规范并支持外部注入'
            )

    elif lang == "node":
        tpl["TPL_HAS_NODE_DEPS"] = "1"
        cd_node = ""
        if backend_dir:
            cd_node = f'cd "$(dirname "$0")/{backend_dir}"\n'

        if framework == "nextjs-standalone":
            # nextjs-standalone 入口 .next/standalone/server.js 由 Next 生成，
            # 读 HOSTNAME/PORT env；stage 40 会 sed 改写让它读 APP_HOSTNAME/APP_PORT
            # 端口走 ${APP_PORT:-3000} 兜底，蓝绿期外部 APP_PORT=3001 注入仍然生效
            tpl["TPL_START_CMD"] = (
                f'{cd_node}export APP_PORT="${{APP_PORT:-3000}}"\n'
                f"export APP_HOSTNAME=0.0.0.0 NODE_ENV=production\n"
                f"exec node .next/standalone/server.js"
            )
        elif framework == "nextjs":
            tpl["TPL_START_CMD"] = (
                f'{cd_node}export APP_PORT="${{APP_PORT:-3000}}"\n'
                f"exec npx next start -H 0.0.0.0 -p ${{APP_PORT}}"
            )
        elif framework == "vite-spa":
            # 纯前端 SPA：不装业务 deps（dist 已在 stage 40 build 完毕），
            # 改用模板渲染的 server.cjs（serve-handler lib）托管 dist + 自带 /health
            # 详见 templates/server.cjs.tpl 与 install.sh.tpl 的 TPL_NEEDS_STATIC_RUNTIME 分支
            tpl["TPL_HAS_NODE_DEPS"] = "0"
            tpl["TPL_NEEDS_STATIC_RUNTIME"] = "1"
            # 单仓 SPA dist 默认在根；monorepo 中如果识别到 frontend_dir 则优先
            if frontend_dir:
                tpl["TPL_STATIC_DIR"] = f"{frontend_dir}/dist"
            tpl["TPL_START_CMD"] = (
                'export APP_PORT="${APP_PORT:-3000}"\n'
                "export NODE_ENV=production\n"
                "exec node server.cjs"
            )
        elif framework == "node-backend":
            node_entry = entry or "src/server.js"
            if backend_dir and node_entry.startswith(backend_dir + "/"):
                node_entry = node_entry[len(backend_dir) + 1 :]
            # 同时 export APP_PORT 和 PORT：APP_PORT 满足 verify_app_env_naming，
            # PORT 兼容大量 Node 后端框架（Express / Koa / Fastify 等约定俗成读 PORT）
            # 都走 ${APP_PORT:-3000} 兜底语法：默认 3000，外部注入可覆盖
            if node_entry.endswith(".ts"):
                tail = node_entry[len("src/"):] if node_entry.startswith("src/") else node_entry
                dist_entry = "dist/" + tail[:-3] + ".js"
                tpl["TPL_START_CMD"] = (
                    f'{cd_node}export APP_PORT="${{APP_PORT:-3000}}"\n'
                    f'export PORT="${{APP_PORT}}" NODE_ENV=production\n'
                    f"exec node {dist_entry}"
                )
            else:
                tpl["TPL_START_CMD"] = (
                    f'{cd_node}export APP_PORT="${{APP_PORT:-3000}}"\n'
                    f'export PORT="${{APP_PORT}}" NODE_ENV=production\n'
                    f"exec node {node_entry}"
                )
        else:
            tpl["TPL_START_CMD"] = (
                f"# TODO: Node 框架 {framework} 未识别；"
                '记得 export APP_PORT="${APP_PORT:-3000}" 满足平台 env 命名规范并支持外部注入'
            )

    # ---- 统一后处理：给末行 exec 命令追加 ` 2>&1`，满足 verify_startup_log_stream.sh ----
    # 设计理由：
    #   verifiers/verify_startup_log_stream.sh 要求 start.sh 的 exec 启动行必须
    #   显式带 shell 级 stderr→stdout 重定向（2>&1 / &> / >&），否则 Guard runner
    #   在某些 Pod 环境下读不到子进程 stderr，会误判服务异常。
    #
    #   该 verifier 在 stage 50 跑；如果不在此处统一注入，每条新增框架分支
    #   都得手动记得带 2>&1，漏一处即 100% 失败 → 靠 autofix 烧 token 兜底。
    #
    #   逻辑：找到最后一行（rstrip 后），若以 `exec ` 开头且尚未含
    #   2>&1 / &> / >& 之类的合并重定向，就在末尾追加 ` 2>&1`。
    #   不影响 TODO 注释 fallback 与已带重定向的（如未来手写）的命令。
    _start = tpl.get("TPL_START_CMD", "")
    if _start:
        _lines = _start.rstrip("\n").split("\n")
        if _lines:
            _last = _lines[-1]
            if _last.lstrip().startswith("exec ") and not re.search(
                r"2>&1|&>\s|>&\s|2>\s*[^&\s]", _last
            ):
                _lines[-1] = _last + " 2>&1"
                tpl["TPL_START_CMD"] = "\n".join(_lines)

    return tpl


def _render(template_path: Path, out_path: Path, tpl_vars: dict[str, str], chmod_x: bool = True) -> None:
    """读模板 → 替换 ${TPL_xxx} → 写出；可选 chmod +x。"""
    text = template_path.read_text()

    def _sub(m: re.Match[str]) -> str:
        return tpl_vars.get(m.group(1), "")

    rendered = _TPL_PATTERN.sub(_sub, text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered)
    if chmod_x:
        st = out_path.stat()
        out_path.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    mode = oct(out_path.stat().st_mode)[-3:]
    log.log(f"渲染: {out_path} (mode={mode})")


def run(cfg: config.Config) -> int:
    home = config.home_dir()
    tpl_dir = home / "templates"

    # 读 stack
    stack_path = cfg.state_dir / "stack.json"
    if not stack_path.is_file():
        log.die("stack.json 不存在，未跑 stage 10？")
    stack = json.loads(stack_path.read_text())
    lang = str(stack.get("lang", ""))

    tpl_vars = _build_tpl_vars(stack)

    # 渲染 install.sh / start.sh / health.sh
    _render(tpl_dir / "install.sh.tpl", cfg.work_dir / "install.sh", tpl_vars)
    _render(tpl_dir / "start.sh.tpl", cfg.work_dir / "start.sh", tpl_vars)
    _render(tpl_dir / "health.sh.tpl", cfg.work_dir / "health.sh", tpl_vars)

    # .npmrc 仅 Node 工程
    if lang == "node":
        _render(tpl_dir / "npmrc.tpl", cfg.work_dir / ".npmrc", tpl_vars, chmod_x=False)
        log.log("渲染: .npmrc (Node)")

    # 纯前端 SPA：渲染 server.cjs（serve-handler lib 托管 + /health endpoint）
    # 不加可执行位（由 `node server.cjs` 解释执行）
    if tpl_vars.get("TPL_NEEDS_STATIC_RUNTIME") == "1":
        _render(
            tpl_dir / "server.cjs.tpl",
            cfg.work_dir / "server.cjs",
            tpl_vars,
            chmod_x=False,
        )
        log.log("渲染: server.cjs (纯前端 serve-handler 托管入口)")

    # 立即跑 3 个基础 verifier 验证模板正确性
    #
    # 设计权衡：stage 30 是确定性模板渲染，理想情况下 verifier 应全部通过。
    # 但模板 + verifier 的版本/规则可能存在边角不匹配（比如 .npmrc 引号格式 vs 正则），
    # 或源工程有特殊文件结构让模板渲染出非典型产物。这种情况下：
    #   - 简单 die 会让上层流水线（含 openclaw 等自动化 agent）卡在第 30 stage 直接退出，
    #     用户体验差且需要工具维护方介入。
    #   - 走 LLM autofix 让 LLM 直接修 work_dir 副本里的 install.sh / .npmrc /
    #     start.sh，是单次跑通的合理兜底——副本不会被本 stage 再次覆盖，
    #     LLM 改完即生效，下游 stage 40/50 仍会做严格校验。
    #
    # ⚠️ 副作用：如果根因是工具模板的 bug，autofix 仅治标。verifier 失败时会先
    # log.warn 提醒，autofix 成功后也会在 commit message 里留痕，便于维护方
    # 在事后日志里发现并修复模板。
    log.log("立即验证脚本基础正确性")
    verifiers_dir = home / "verifiers"
    fail_count = 0
    for vname in (
        "verify_entry_scripts.sh",
        "verify_port_3000.sh",
        "verify_install_no_internet.sh",
    ):
        vpath = verifiers_dir / vname
        # 先跑一次裸 verifier；通过则下一项
        if verifier.run(vpath, cfg.work_dir, cfg.state_dir):
            continue
        # 失败：根据 cfg.autofix 决定是否调 LLM 修
        if not cfg.autofix:
            fail_count += 1
            continue
        log.warn(
            f"[stage 30] {vname} 失败 —— 尝试 LLM autofix（如果根因是模板 bug，"
            f"请把 {cfg.state_dir}/verify-{vpath.stem}.log 反馈给 guard-transform 维护方）"
        )
        if verifier.run_with_autofix(vpath, cfg):
            log.ok(f"[stage 30] {vname} 经 autofix 修复成功")
        else:
            fail_count += 1

    if fail_count > 0:
        if cfg.strict:
            log.die(
                f"{fail_count} 个基础 verifier 经 autofix 仍失败，"
                f"请检查 {cfg.state_dir}/verify-*.log；"
                f"GUARD_STRICT=0 可让流水线带伤继续到下一 stage（仅调试用）"
            )
        log.warn(
            f"{fail_count} 个基础 verifier 仍失败，但 GUARD_STRICT=0，继续执行"
        )

    git.commit_step(
        cfg.work_dir, "render: install.sh / start.sh / health.sh / .npmrc"
    )

    log.ok("stage 30 完成")
    return 0
