"""guardx CLI 入口：argparse（不依赖 typer），子命令对齐 bash 版。

子命令：
    transform <source>   主流程，对应 bash 版 transform.sh
    detect    <source>   只跑 stage 10（栈识别），输出 stack.json
    verify    <work>     只跑 verifiers/*.sh，对照工作副本
    clean     <source>   删除 work_dir + state_dir（危险，需 -y）

参数与 bash 版 transform.sh 完全对齐：
    --from-stage NN / --skip-llm / --resume / --reset / -y / --yes
    --no-autofix / --autofix-max N / --no-strict
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import sys
from pathlib import Path

from . import __version__, checklist, config, git, log, process


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="guardx",
        description="guard-transform Python edition (Stage 2 PoC)",
    )
    p.add_argument("--version", action="version", version=f"guardx {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    # ---- transform ----
    t = sub.add_parser("transform", help="跑完整 0~70 stage 流水线")
    t.add_argument("source", help="源工程路径（目录或 .zip）")
    _add_pipeline_args(t)
    t.set_defaults(func=cmd_transform)

    # ---- detect ----
    d = sub.add_parser("detect", help="只跑 stage 10：识别技术栈，写 stack.json")
    d.add_argument("source", help="源工程路径")
    _add_pipeline_args(d)
    d.set_defaults(func=cmd_detect)

    # ---- verify ----
    v = sub.add_parser("verify", help="跑 verifiers/*.sh 验证已生成的工作副本")
    v.add_argument("source", help="源工程路径（用于推导 work_dir）")
    v.set_defaults(func=cmd_verify)

    # ---- logs ----
    lg = sub.add_parser("logs", help="实时查看 transform 日志（tail -f）")
    lg.add_argument("source", help="源工程路径（用于推导 state_dir）")
    lg.add_argument("-n", "--lines", type=int, default=50,
                    help="显示最近 N 行（默认 50）")
    lg.add_argument("-f", "--follow", action="store_true", default=True,
                    help="持续跟踪输出（默认开启，Ctrl+C 退出）")
    lg.add_argument("--no-follow", dest="follow", action="store_false",
                    help="只显示最近 N 行，不持续跟踪")
    lg.set_defaults(func=cmd_logs)

    # ---- stop ----
    stop_p = sub.add_parser("stop", help="停止后台运行的 guardx 进程")
    stop_p.add_argument("source", help="源工程路径（用于推导 state_dir + pidfile）")
    stop_p.set_defaults(func=cmd_stop)

    # ---- status ----
    stat_p = sub.add_parser(
        "status",
        help="轮询友好的状态输出（status + 自上次以来的增量日志），适合外部自动化每 N 秒调用",
    )
    stat_p.add_argument("source", help="源工程路径（用于推导 state_dir）")
    stat_p.add_argument(
        "-n", "--tail", type=int, default=50,
        help="首次轮询（offset 文件不存在时）显示的最近行数（默认 50）",
    )
    stat_p.add_argument(
        "--reset-offset", action="store_true",
        help="重置增量游标：下次调用回退到首次模式显示最近 N 行",
    )
    stat_p.set_defaults(func=cmd_status)

    # ---- clean ----
    c = sub.add_parser("clean", help="删除 work_dir + state_dir（危险）")
    c.add_argument("source", help="源工程路径")
    c.add_argument("-y", "--yes", action="store_true", help="跳过确认")
    c.set_defaults(func=cmd_clean)

    return p


def _add_pipeline_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--from-stage", type=int, default=0,
                   help="从指定 stage 续跑（0/10/20/30/40/50/60/70）")
    p.add_argument("--skip-llm", action="store_true",
                   help="跳过所有 LLM 调用（同 SKIP_LLM=1）")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--resume", dest="resume_mode", action="store_const",
                   const="resume", help="发现 checklist 时直接跳过已完成步骤，不询问")
    g.add_argument("--reset", dest="resume_mode", action="store_const",
                   const="reset", help="清空 checklist 重新开始，不询问")
    g.add_argument("-y", "--yes", dest="resume_mode", action="store_const",
                   const="resume", help="同 --resume（兼容 CI；同时把 --reuse-copy 也设为默认）")
    p.set_defaults(resume_mode="ask")

    # 工作副本目录已存在时怎么处理（独立于 checklist 的 --resume / --reset；后者只管进度文件）
    # 历史上 stage 00 在 work_dir 存在时**默认静默复用**，本地交互场景常导致用户
    # 修改源工程后再次跑流水线却没生效（因为复用的是上次 copy 出来的旧副本）。
    # 加这个互斥组让本地交互模式可以弹问 "用已有副本 / 删掉重新 copy 一份"，
    # 默认 ask；非 tty / -y / 服务端 profile 自动等同 reuse 保持向后兼容。
    g2 = p.add_mutually_exclusive_group()
    g2.add_argument("--reuse-copy", dest="fresh_copy_mode", action="store_const",
                    const="reuse",
                    help="工作副本目录已存在则直接使用其内容跑转写（不重新从源工程 copy；保留你在副本中的手改）")
    g2.add_argument("--recopy", dest="fresh_copy_mode", action="store_const",
                    const="recopy",
                    help="工作副本目录已存在则先清空、再从源工程重新 copy 一份（丢弃副本中的所有改动）")
    p.set_defaults(fresh_copy_mode="ask")

    p.add_argument("--no-autofix", dest="autofix", action="store_false",
                   help="禁用 build/verify 失败时的 LLM 自动修复")
    p.add_argument("--autofix-max", type=int, default=5,
                   help="每个失败任务最多调 LLM 修复次数（默认 5；实测 1-3 次大多已成或已陷入死循环）")
    p.add_argument("--no-strict", dest="strict", action="store_false",
                   help="verifier autofix 仍失败时不 die（带伤继续）")


# ----------------------------- 命令实现 -----------------------------


def _log_llm_config(cfg: config.Config) -> None:
    """打印当前 LLM 后端 / 模型路由 / 超时等信息，并提示如何覆盖。

    打印位置：cmd_transform 入口（_setup_runtime 之后），与其他启动 banner 同时输出，
    确保用户在流水线真正开始前就能看到本次运行使用的模型；如果走的是 codewiz skill
    集成路径，default_env.sh 在本进程之前已完成回显（提示 LLM 后端 + 模型默认值），
    这里再补一份完整四件套（后端/strong 模型/fast 模型/超时心跳）+ 覆盖方法。

    模型分级路由（详见 llm.py LLMConfig.model_id）：
      - strong profile：stage 20 rewrite_loop 跨文件改写 → 默认 opus-4-7
      - fast   profile：其他 stage 的 autofix / 局部小修 → 默认 sonnet-4-6

    实现注意：
      - GUARD_LLM 默认 claude（与 LLMConfig 默认一致）；codewiz skill 安装后默认 codewiz；
      - GUARD_LLM_MODEL 若设置则一刀切覆盖所有 profile（向后兼容旧用法）；
      - GUARD_LLM_MODEL_STRONG / GUARD_LLM_MODEL_FAST 可分别覆盖；
      - 不做任何环境改写，仅 read-only 打印。
    """
    # 实例化两个 profile 让 model_id() 解析出最终生效值
    # 注意：这里 import 局部化，避免在 cli 顶层引入 llm 模块的额外副作用
    from . import llm as _llm
    strong_id = _llm.LLMConfig.for_profile("strong").model_id() or "<后端默认>"
    fast_id = _llm.LLMConfig.for_profile("fast").model_id() or "<后端默认>"

    backend = cfg.llm_backend
    override = os.environ.get("GUARD_LLM_MODEL")
    timeout = os.environ.get("GUARD_LLM_TIMEOUT", "600")
    heartbeat = os.environ.get("GUARD_LLM_HEARTBEAT", "30")

    log.log(f"LLM 后端  : {backend}（SKIP_LLM={int(cfg.skip_llm)}）")
    if override:
        # 用户设了 GUARD_LLM_MODEL → 所有 profile 都走这个，分级失效
        log.log(f"LLM 模型  : {override}（GUARD_LLM_MODEL 一刀切，分级路由失效）")
    else:
        log.log(f"LLM 模型  : strong={strong_id}  ← stage 20 跨文件改写")
        log.log(f"            fast  ={fast_id}  ← 其他 stage 的 autofix / 局部修复")
    log.log(f"LLM 超时  : {timeout}s | 心跳: {heartbeat}s")
    # 覆盖方法说明：让用户知道这些值并非硬编码
    log.log(
        "覆盖方法  : export GUARD_LLM=<backend>  "
        "GUARD_LLM_MODEL_STRONG='<id>'  GUARD_LLM_MODEL_FAST='<id>'"
    )
    log.log(
        "            （或 GUARD_LLM_MODEL='<id>' 一刀切；GUARD_LLM_TIMEOUT=<sec>）"
    )
    log.log(
        "            或编辑 $GUARD_TRANSFORM_HOME/default_env.sh 永久修改默认值"
    )


def _env_bool(name: str, default: bool) -> bool:
    """读取 0/1/true/false/yes/no 环境变量；未设置返回 default。"""
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v.strip().lower() not in ("0", "false", "no", "off")


def _build_config(args: argparse.Namespace) -> config.Config:
    # 命令行参数优先；未显式给出时（即沿用 argparse 默认值），允许环境变量兜底，
    # 以兼容 bash 时代约定：SKIP_LLM / GUARD_AUTOFIX / GUARD_AUTOFIX_MAX / GUARD_STRICT。
    skip_llm = getattr(args, "skip_llm", False) or _env_bool("SKIP_LLM", False)
    autofix = getattr(args, "autofix", True) and _env_bool("GUARD_AUTOFIX", True)
    autofix_max = getattr(args, "autofix_max", 5)
    try:
        env_max = os.environ.get("GUARD_AUTOFIX_MAX")
        if env_max:
            autofix_max = int(env_max)
    except ValueError:
        pass
    strict = getattr(args, "strict", True) and _env_bool("GUARD_STRICT", True)

    # fresh_copy_mode：CLI > env(GUARD_FRESH_COPY_MODE) > "ask"
    # `-y` 历史语义是"全自动 / 兼容 CI"，应当一并把 fresh_copy_mode 拉到 reuse；
    # 同时让 GUARD_NONINTERACTIVE / GUARD_PROFILE=server 场景也默认 reuse。
    fresh_copy_mode = getattr(args, "fresh_copy_mode", "ask") or "ask"
    env_fcm = os.environ.get("GUARD_FRESH_COPY_MODE", "").strip().lower()
    if fresh_copy_mode == "ask" and env_fcm in ("reuse", "recopy", "ask"):
        fresh_copy_mode = env_fcm
    if fresh_copy_mode == "ask":
        # `-y` → resume_mode 已被强设为 "resume"，认为用户要全自动；与 CI / server profile 对齐
        resume_mode_now = getattr(args, "resume_mode", "ask") or "ask"
        if resume_mode_now == "resume" or _env_bool("GUARD_NONINTERACTIVE", False):
            fresh_copy_mode = "reuse"

    return config.Config.from_args(
        args.source,
        from_stage=getattr(args, "from_stage", 0),
        skip_llm=skip_llm,
        resume_mode=getattr(args, "resume_mode", "ask") or "ask",
        autofix=autofix,
        autofix_max=autofix_max,
        strict=strict,
        fresh_copy_mode=fresh_copy_mode,
    )


def _setup_runtime(cfg: config.Config) -> None:
    """初始化日志 + checklist + 信号处理；所有命令共用。"""
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    log.init(cfg.state_dir / "transform.log")
    checklist.init(cfg.state_dir)

    # 后台模式（--bg）兜底：注册 atexit，确保 python 正常退出（含 SystemExit/die）
    # 时一定能写出 guardx.done，给外部轮询作为「已结束」信号。
    # bin/guardx 的守护 bash 子 shell 是主要写入方，这里只是 belt-and-suspenders，
    # 防止某些边缘情形（守护 shell 被杀但 python 还活着）下 done 文件迟到。
    if os.environ.get("GUARDX_BG_MODE") == "1":
        import atexit
        done_file = cfg.state_dir / "guardx.done"

        def _mark_done() -> None:
            try:
                done_file.touch(exist_ok=True)
            except Exception:
                pass

        atexit.register(_mark_done)

    def _on_signal(signum: int) -> None:
        log.fail(f"收到 SIG{signal.Signals(signum).name}，正在终止所有子进程...")
        # process.run 自身会在 KeyboardInterrupt 时整树杀，这里只兜底退出
        sys.exit(130)

    process.setup_signal_handlers(_on_signal)


def cmd_transform(args: argparse.Namespace) -> int:
    cfg = _build_config(args)
    _setup_runtime(cfg)
    log.section("guard-transform 开始")
    log.log(f"源工程    : {cfg.source_project}")
    log.log(f"工作副本  : {cfg.work_dir}")
    log.log(f"状态目录  : {cfg.state_dir}")
    _log_llm_config(cfg)
    log.log(f"起始 stage: {cfg.from_stage}")
    log.log(f"续跑模式  : {cfg.resume_mode}")
    log.log(
        f"AI autofix: GUARD_AUTOFIX={int(cfg.autofix)} "
        f"max={cfg.autofix_max} strict={int(cfg.strict)}"
    )

    checklist.resume_or_reset(cfg.resume_mode)

    from . import pipeline  # 延迟导入，避免循环
    rc = pipeline.run(cfg)
    if rc == 0:
        log.section("guard-transform 全部成功")
        log.log(f"交付 zip : {cfg.zip_path}")
        log.log(f"交付报告 : {cfg.state_dir}/report.md")
    return rc


def cmd_detect(args: argparse.Namespace) -> int:
    """快捷入口：只跑 stage 00/10。"""
    args.from_stage = 0
    cfg = _build_config(args)
    _setup_runtime(cfg)
    log.section("guard-transform detect (stage 00 + 10)")
    checklist.resume_or_reset(cfg.resume_mode)
    from . import pipeline
    return pipeline.run(cfg, only_stages=("00_prepare", "10_detect_stack"))


def cmd_verify(args: argparse.Namespace) -> int:
    cfg = config.Config.from_args(args.source)
    _setup_runtime(cfg)
    log.section("guard-transform verify")
    if not cfg.work_dir.is_dir():
        log.die(f"工作副本不存在: {cfg.work_dir}（先跑 transform）")
    home = config.home_dir()
    verifiers = sorted((home / "verifiers").glob("verify_*.sh"))
    if not verifiers:
        log.warn("未发现 verifiers/verify_*.sh")
        return 0
    fails = 0
    for v in verifiers:
        out = cfg.state_dir / f"verify-{v.stem}.log"
        r = process.run(
            ["bash", str(v), str(cfg.work_dir)],
            log_path=out,
            heartbeat_sec=0,
            timeout=300,
        )
        if r.ok:
            log.ok(v.stem)
        else:
            log.fail(f"{v.stem} (详见 {out})")
            fails += 1
    return 0 if fails == 0 else 1


def _bg_status(state_dir: Path) -> tuple[str, int | None, int | None]:
    """检测后台进程状态。

    返回 (status, pid, exit_code)，其中 status ∈ {"running", "done", "none"}：
      - "done" : guardx.done 已落盘（守护 shell 或 atexit 写入），任务结束
      - "running" : pidfile 存在 且 进程存活 且 非 zombie
      - "none"  : 没有 pidfile（前台模式 / 未启动）

    检测 zombie 是必要的：容器内若 PID 1 不是 init，python 退出后会变 defunct，
    `kill -0 pid` 仍返回 0，纯靠 kill 探活会误判「进程还在跑」。
    """
    done_file = state_dir / "guardx.done"
    exitcode_file = state_dir / "guardx.exitcode"
    pidfile = state_dir / "guardx.pid"

    ec: int | None = None
    if exitcode_file.is_file():
        try:
            ec = int(exitcode_file.read_text().strip())
        except (ValueError, OSError):
            pass

    if done_file.is_file():
        return ("done", None, ec)

    if not pidfile.is_file():
        return ("none", None, ec)

    try:
        pid = int(pidfile.read_text().strip())
    except (ValueError, OSError):
        return ("done", None, ec)

    # kill -0 检测
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return ("done", pid, ec)

    # 检测 zombie：/proc/<pid>/status 的 State 字段以 Z 开头
    proc_status = Path(f"/proc/{pid}/status")
    if proc_status.is_file():
        try:
            for line in proc_status.read_text().splitlines():
                if line.startswith("State:"):
                    if "Z" in line.split(":", 1)[1].strip()[:2]:
                        return ("done", pid, ec)
                    break
        except OSError:
            pass

    return ("running", pid, ec)


def cmd_logs(args: argparse.Namespace) -> int:
    """实时查看 transform 日志。"""
    import subprocess as _sp
    cfg = config.Config.from_args(args.source)
    logfile = cfg.state_dir / "transform.log"
    if not logfile.is_file():
        print(f"[guardx] 日志文件不存在: {logfile}", file=sys.stderr)
        print(f"[guardx] 请先启动 transform：guardx --bg transform {args.source}", file=sys.stderr)
        return 1

    # 显示进程状态
    status, pid, ec = _bg_status(cfg.state_dir)
    if status == "running":
        print(f"[guardx] 后台进程运行中 (PID={pid})", file=sys.stderr)
    elif status == "done":
        ec_str = f", exit={ec}" if ec is not None else ""
        print(f"[guardx] 后台进程已结束{ec_str}", file=sys.stderr)
    else:
        print(f"[guardx] 无后台进程记录（可能是前台模式）", file=sys.stderr)

    print(f"[guardx] 日志文件: {logfile}", file=sys.stderr)
    print(f"[guardx] {'按 Ctrl+C 退出跟踪' if args.follow else ''}", file=sys.stderr)
    print("---", file=sys.stderr)

    # 使用 tail 查看日志
    # 进程已结束时强制关闭 -f，避免外部调用方（如 openclaw）被无限阻塞
    follow = args.follow and status == "running"
    tail_cmd = ["tail", f"-n{args.lines}"]
    if follow:
        tail_cmd.append("-f")
    tail_cmd.append(str(logfile))

    try:
        return _sp.call(tail_cmd)
    except KeyboardInterrupt:
        return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """停止后台运行的 guardx 进程。"""
    cfg = config.Config.from_args(args.source)
    pidfile = cfg.state_dir / "guardx.pid"
    donefile = cfg.state_dir / "guardx.done"

    # done 文件存在直接当作已结束
    if donefile.is_file() and not pidfile.is_file():
        print(f"[guardx] 后台进程已自行结束（guardx.done 已存在）", file=sys.stderr)
        return 0

    if not pidfile.is_file():
        print(f"[guardx] 未找到 PID 文件: {pidfile}", file=sys.stderr)
        print(f"[guardx] 可能未以 --bg 模式启动", file=sys.stderr)
        return 1

    try:
        pid = int(pidfile.read_text().strip())
    except (ValueError, OSError) as e:
        print(f"[guardx] 读取 PID 文件失败: {e}", file=sys.stderr)
        return 1

    # 检测进程状态（含 zombie）
    status, _, _ = _bg_status(cfg.state_dir)
    if status == "done":
        print(f"[guardx] 进程 {pid} 已结束（zombie 或已退出）", file=sys.stderr)
        pidfile.unlink(missing_ok=True)
        donefile.touch(exist_ok=True)
        return 0

    print(f"[guardx] 正在停止进程 {pid}...", file=sys.stderr)
    try:
        os.kill(pid, signal.SIGTERM)
        # 等待最多 5 秒
        import time
        for _ in range(50):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                print(f"[guardx] 进程 {pid} 已停止", file=sys.stderr)
                pidfile.unlink(missing_ok=True)
                donefile.touch(exist_ok=True)
                return 0
        # 5 秒后还活着，SIGKILL
        print(f"[guardx] 进程未响应 SIGTERM，强制 SIGKILL...", file=sys.stderr)
        os.kill(pid, signal.SIGKILL)
        pidfile.unlink(missing_ok=True)
        donefile.touch(exist_ok=True)
        print(f"[guardx] 进程 {pid} 已强制停止", file=sys.stderr)
    except ProcessLookupError:
        print(f"[guardx] 进程 {pid} 已停止", file=sys.stderr)
        pidfile.unlink(missing_ok=True)
        donefile.touch(exist_ok=True)
    except PermissionError:
        print(f"[guardx] 无权限停止进程 {pid}", file=sys.stderr)
        return 1
    return 0


def _fmt_duration(seconds: float) -> str:
    """把秒数格式化成 1h23m45s / 2m15s / 45s，方便人/agent 读取。"""
    if seconds < 0:
        seconds = 0
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h > 0:
        return f"{h}h{m:02d}m{sec:02d}s"
    if m > 0:
        return f"{m}m{sec:02d}s"
    return f"{sec}s"


def cmd_status(args: argparse.Namespace) -> int:
    """轮询友好的状态输出：状态行 + 活体证明 + 自上次调用以来的增量日志。

    专为外部自动化（openclaw、CI 心跳脚本等）每 N 秒一次的心跳轮询设计。
    输出固定格式（全部到 stdout，便于 pipeline 抓取）：
        ===STATUS=== RUNNING                (或 DONE exit=N)
        ===META=== elapsed=2m15s pid=12345 log_age=12s log_size=4823 poll=#3
        ===LOG=== (首次/增量 X bytes/无新输出，已静默 12s)
        <增量日志正文>

    维护两个 state 文件：
      - state_dir/.guardx_status_offset : 上次读取的字节位置（避免重复刷屏）
      - state_dir/.guardx_status_meta   : 轮询计数 + 首次轮询墙钟（便于 elapsed 显示）

    关键设计：即使无新日志，===META=== 也始终给出 elapsed / log_age 等活体证明，
    让上游 agent（如 openclaw）能在前端持续输出"心跳 #N: 仍在运行 X 分钟"等可见提示，
    避免出现"看不到增量 → 误以为 agent 假死 → 停止上报"的恶性循环。
    """
    import json
    import time

    cfg = config.Config.from_args(args.source)
    state = cfg.state_dir
    if not state.is_dir():
        print(f"===STATUS=== UNKNOWN (state_dir 不存在: {state})")
        return 1

    logfile = state / "transform.log"
    offset_file = state / ".guardx_status_offset"
    meta_file = state / ".guardx_status_meta"
    pidfile = state / "guardx.pid"
    donefile = state / "guardx.done"

    if args.reset_offset:
        offset_file.unlink(missing_ok=True)
        meta_file.unlink(missing_ok=True)

    now = time.time()

    # ---- 状态行 ----
    status, pid, ec = _bg_status(state)
    if status == "done":
        print(f"===STATUS=== DONE exit={ec if ec is not None else '?'}")
    elif status == "running":
        print(f"===STATUS=== RUNNING")
    else:
        print(f"===STATUS=== NONE (无 pid/done 记录，可能未以 --bg 启动或已被清理)")

    # ---- 维护轮询元数据（poll 计数 + 起始时间）----
    meta: dict = {}
    if meta_file.is_file():
        try:
            meta = json.loads(meta_file.read_text() or "{}")
        except (json.JSONDecodeError, OSError):
            meta = {}
    if not meta.get("first_poll_ts"):
        # 优先用 pidfile mtime 作为任务起点（更接近真实启动时刻），fallback 到 now
        try:
            meta["first_poll_ts"] = pidfile.stat().st_mtime if pidfile.is_file() else now
        except OSError:
            meta["first_poll_ts"] = now
    meta["poll_count"] = int(meta.get("poll_count", 0)) + 1
    meta["last_poll_ts"] = now

    first_poll_ts = float(meta["first_poll_ts"])
    poll_count = int(meta["poll_count"])
    elapsed = now - first_poll_ts

    # ---- 活体证明 META 行 ----
    meta_parts = [f"elapsed={_fmt_duration(elapsed)}"]
    if pid is not None:
        meta_parts.append(f"pid={pid}")
    if logfile.is_file():
        try:
            log_stat = logfile.stat()
            log_age = now - log_stat.st_mtime
            meta_parts.append(f"log_age={_fmt_duration(log_age)}")
            meta_parts.append(f"log_size={log_stat.st_size}")
        except OSError:
            pass
    if status == "done" and donefile.is_file():
        try:
            done_age = now - donefile.stat().st_mtime
            meta_parts.append(f"done_age={_fmt_duration(done_age)}")
        except OSError:
            pass
    meta_parts.append(f"poll=#{poll_count}")
    print(f"===META=== {' '.join(meta_parts)}")

    # 写回 meta 文件（best effort）
    try:
        meta_file.write_text(json.dumps(meta))
    except OSError:
        pass

    # ---- 增量日志 ----
    if not logfile.is_file():
        print("===LOG=== (日志文件暂未生成)")
        return 0

    try:
        cur_size = logfile.stat().st_size
        log_mtime = logfile.stat().st_mtime
    except OSError as e:
        print(f"===LOG=== (无法 stat 日志: {e})")
        return 0

    last_offset = 0
    has_offset = offset_file.is_file()
    if has_offset:
        try:
            last_offset = int(offset_file.read_text().strip() or "0")
        except (ValueError, OSError):
            last_offset = 0

    # 首次 / 文件被截断 → 显示最近 N 行
    if not has_offset or cur_size < last_offset:
        reason = "首次轮询" if not has_offset else "日志被截断，重置"
        print(f"===LOG=== ({reason}，显示最近 {args.tail} 行)")
        try:
            with logfile.open("r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            for line in lines[-args.tail:]:
                sys.stdout.write(line)
            if lines and not lines[-1].endswith("\n"):
                sys.stdout.write("\n")
        except OSError as e:
            print(f"(读取失败: {e})")
        try:
            offset_file.write_text(str(cur_size))
        except OSError:
            pass
        return 0

    # 无新输出
    if cur_size == last_offset:
        silent_for = _fmt_duration(now - log_mtime)
        print(f"===LOG=== (无新日志输出，已静默 {silent_for})")
        return 0

    # 增量
    delta = cur_size - last_offset
    print(f"===LOG=== (增量 {delta} bytes)")
    try:
        with logfile.open("rb") as f:
            f.seek(last_offset)
            new_bytes = f.read()
        sys.stdout.write(new_bytes.decode("utf-8", errors="replace"))
        if new_bytes and not new_bytes.endswith(b"\n"):
            sys.stdout.write("\n")
    except OSError as e:
        print(f"(读取失败: {e})")
        return 0

    try:
        offset_file.write_text(str(cur_size))
    except OSError:
        pass
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    cfg = config.Config.from_args(args.source)
    targets = [cfg.work_dir, cfg.state_dir]
    log.warn("即将删除以下目录：")
    for t in targets:
        log.log(f"  {t}{'  (不存在)' if not t.exists() else ''}")
    if not args.yes:
        log.die("加 -y 确认删除")
    for t in targets:
        if t.exists():
            shutil.rmtree(t)
            log.ok(f"已删除 {t}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    # 环境预检：所有子命令跑前确保 git 可用。
    # - 没装 git + 非交互 → log.die（友好报错，含安装命令）
    # - 没装 git + 交互  → 弹问是否自动安装（30s 超时按否）
    # 装了 / GUARD_SKIP_GIT_CHECK=1 → no-op，零开销
    # 放这里而非 _setup_runtime 的原因：clean / logs / status / stop 这些
    # 不依赖 git 的命令也走 _setup_runtime，但完全不该被 git 缺失阻塞；
    # main 这里只在真正会调用 git 的子命令前预检。
    if getattr(args, "command", None) in ("transform", "detect"):
        try:
            git.ensure_installed()
        except SystemExit as e:
            return int(e.code) if isinstance(e.code, int) else 1
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        log.fail("用户中断")
        return 130
    except FileNotFoundError as e:
        log.fail(str(e))
        return 1
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1


if __name__ == "__main__":
    sys.exit(main())
