"""subprocess 包装：timeout / 整树杀 / 实时 tee / heartbeat。

继承 bash 版 lib/llm.sh 的所有"踩坑修复"，但用 stdlib 的 signal+select 实现，
比 bash 干净 5 倍：
  - bash 版要写 _bash_timeout（macOS 没 GNU timeout 时纯 bash fallback）+
    _kill_descendants（递归 pkill -P）+ _start_heartbeat（subshell + trap）。
  - Python 版用 subprocess.Popen + os.killpg + threading.Timer 一气呵成。

关键不变量（与 bash 版对齐）：
  1) stdin 必须显式关掉 (DEVNULL)，否则某些 LLM CLI 探测 tty 时挂死
  2) 子进程要起独立 process group (preexec_fn=os.setsid)，方便 killpg 整树杀
  3) timeout 到了先 SIGTERM，等 2s 仍存活再 SIGKILL
  4) 长任务每 N 秒打一行 heartbeat 防"假死"误判
  5) 输出实时 tee 到日志文件 + stderr，而非全部缓存
"""

from __future__ import annotations

import os
import select
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import log


@dataclass
class RunResult:
    returncode: int
    log_path: Optional[Path]
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _kill_tree(pid: int, sig: int = signal.SIGTERM) -> None:
    """递归杀 pid 及其所有子孙。优先用进程组（killpg），fallback 用 ps -o pid 遍历。"""
    try:
        # 如果 pid 是进程组 leader，killpg 一击 → 整组接收信号
        os.killpg(os.getpgid(pid), sig)
    except (ProcessLookupError, PermissionError):
        return
    except OSError:
        # fallback：手动遍历子进程
        try:
            out = subprocess.check_output(
                ["pgrep", "-P", str(pid)], text=True
            )
            for child in out.split():
                _kill_tree(int(child), sig)
            os.kill(pid, sig)
        except (subprocess.CalledProcessError, ProcessLookupError):
            pass


def _dump_hang_diagnostics(pid: int, prefix: str = "", reason: str = "timeout") -> None:
    """诊断 hang：dump 进程树 + 进程状态 + 网络连接，写入日志便于事后分析。

    适用场景：
      - LLM CLI（如 claude）超过 timeout 仍未返回 → 杀进程前先记现场
      - 长时间无新输出（silent hang）→ heartbeat 时主动诊断

    Linux 优先用 /proc 文件系统读 wchan/status（无须额外工具）；
    macOS / 容器内可能 /proc 不可用，仅靠 ps/pgrep 输出。
    所有命令均带 timeout=3s 兜底，避免诊断本身把流程卡死。
    """
    log.warn(f"{prefix}=== 诊断 dump 开始 (root pid={pid}, reason={reason}) ===")

    # 1. 进程树（root pid 及所有子孙）
    pids = [pid]
    try:
        def _find_children(p: int, acc: list[int], depth: int = 0) -> None:
            if depth > 10:
                return
            try:
                out = subprocess.check_output(
                    ["pgrep", "-P", str(p)], text=True, timeout=3,
                ).strip()
                for child_s in out.split():
                    try:
                        child = int(child_s)
                        acc.append(child)
                        _find_children(child, acc, depth + 1)
                    except ValueError:
                        pass
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                    FileNotFoundError, OSError):
                pass
        _find_children(pid, pids)
    except Exception as e:
        log.warn(f"{prefix}  pgrep 失败: {e}")

    log.warn(f"{prefix}  进程树 pids: {pids}")

    # 2. ps -o 详细信息（cmd / state / etime / wchan）
    try:
        ps_args = ["ps", "-o", "pid,ppid,stat,etime,pcpu,pmem,wchan,args"]
        for p in pids:
            ps_args += ["-p", str(p)]
        out = subprocess.check_output(ps_args, text=True, timeout=3)
        for line in out.splitlines():
            log.warn(f"{prefix}  ps | {line}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError, OSError) as e:
        log.warn(f"{prefix}  ps 失败: {e}")

    # 3. /proc/<pid>/status 的 State + /proc/<pid>/wchan（仅 Linux）
    for p in pids:
        status_file = Path(f"/proc/{p}/status")
        wchan_file = Path(f"/proc/{p}/wchan")
        try:
            if status_file.is_file():
                for line in status_file.read_text().splitlines():
                    if line.startswith(("Name:", "State:", "Threads:", "VmRSS:")):
                        log.warn(f"{prefix}  /proc/{p}/status | {line}")
            if wchan_file.is_file():
                wchan = wchan_file.read_text().strip()
                log.warn(f"{prefix}  /proc/{p}/wchan = {wchan or '<无>'}")
        except OSError:
            pass

    # 4. 网络连接：只看目标进程树的 fd，避免把无关 node/python 的连接也带出来
    # 优先 lsof -p（精准指定 pid），fallback ss/netstat + 按 pid grep
    # 用 bytes 模式 + errors='replace' 防工具输出含非 UTF-8 字节
    pids_csv = ",".join(str(p) for p in pids)
    pid_strs = {str(p) for p in pids}

    def _grep_by_pid(text: str) -> list[str]:
        """从 ss/netstat -p 输出里挑出 pid=<我们的 pid> 的行"""
        kept = []
        for ln in text.splitlines():
            for p in pid_strs:
                if f"pid={p}" in ln or f"pid={p}," in ln:
                    kept.append(ln)
                    break
        return kept

    network_tools = [
        # lsof -p 直接按 PID 过滤（最精准）
        (["lsof", "-p", pids_csv, "-P", "-n"], lambda t: [
            ln for ln in t.splitlines() if "TCP" in ln or "UDP" in ln
        ]),
        # ss -tnp 列所有连接，按 pid 过滤
        (["ss", "-tnp"], _grep_by_pid),
        # netstat -tnp 同上
        (["netstat", "-tnp"], _grep_by_pid),
    ]
    for tool, filter_fn in network_tools:
        try:
            out_bytes = subprocess.check_output(
                tool, timeout=3, stderr=subprocess.DEVNULL,
            )
            out = out_bytes.decode("utf-8", errors="replace")
            kept = filter_fn(out)
            if kept:
                log.warn(f"{prefix}  {tool[0]} (限定本进程树) 网络连接:")
                for ln in kept[:30]:
                    log.warn(f"{prefix}    {ln}")
            else:
                log.warn(f"{prefix}  {tool[0]} 本进程树无活动网络连接")
            break  # 第一个可用工具就够了
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError, OSError):
            continue

    log.warn(f"{prefix}=== 诊断 dump 结束 ===")


def run(
    cmd: Sequence[str] | str,
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    timeout: Optional[int] = None,
    log_path: Optional[Path] = None,
    heartbeat_sec: int = 30,
    shell: bool = False,
    label: str = "",
) -> RunResult:
    """跑一个子进程，实时 tee 输出到 log_path + stderr，heartbeat 防假死。

    Args:
        cmd: 命令列表（推荐）或字符串 + shell=True
        cwd: 工作目录
        env: 环境变量；None 表示继承
        timeout: 秒；None 表示不限时
        log_path: tee 目标；None 表示只输出到 stderr
        heartbeat_sec: 多久打一次心跳；0 禁用
        shell: 是否走 shell（cmd 必须是 str）
        label: 显示用前缀，区分多个并行任务

    Returns:
        RunResult: returncode + timed_out 标志
    """
    # 准备日志文件
    log_fp = None
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fp = log_path.open("w")

    prefix = f"[{label}] " if label else ""
    log.log(f"{prefix}exec: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    if log_path:
        log.log(f"{prefix}log:  {log_path}")

    # 启动子进程
    #   start_new_session=True 等价 preexec_fn=os.setsid（更安全，3.2+）
    #   stdin=DEVNULL：关键，防 LLM CLI 探测 tty 挂死
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,  # 关键：不缓冲，实时拿到子进程输出
        shell=shell,
        start_new_session=True,
    )

    # heartbeat 线程（仅在长任务）
    # 同时检测「silent hang」：若 silent_dump_sec 秒无新输出，dump 诊断（每轮只 dump 一次）
    stop_hb = threading.Event()
    last_output_ts = time.monotonic()
    _last_output_lock = threading.Lock()
    silent_dumped = [False]  # 用 list 闭包共享可变状态
    # silent_dump_sec：默认 5 倍心跳间隔，至少 180s；触发后只 dump 一次（per run）
    silent_dump_sec = max(180, heartbeat_sec * 5) if heartbeat_sec > 0 else 0

    def _get_last_output_age() -> float:
        with _last_output_lock:
            return time.monotonic() - last_output_ts

    if heartbeat_sec > 0:
        def _heartbeat():
            elapsed = 0
            while not stop_hb.wait(heartbeat_sec):
                elapsed += heartbeat_sec
                silent_age = int(_get_last_output_age())
                log.log(
                    f"{prefix}[heartbeat] 已运行 {elapsed}s "
                    f"(timeout={timeout or '无限'}s, pid={proc.pid}, "
                    f"silent={silent_age}s)"
                )
                # silent hang：长时间无新输出 → 主动诊断（仅 dump 一次，避免刷屏）
                if (silent_dump_sec > 0
                        and silent_age >= silent_dump_sec
                        and not silent_dumped[0]):
                    silent_dumped[0] = True
                    log.warn(
                        f"{prefix}子进程已 {silent_age}s 无新输出，疑似 hang，"
                        f"主动 dump 诊断信息"
                    )
                    try:
                        _dump_hang_diagnostics(
                            proc.pid, prefix=prefix, reason=f"silent_{silent_age}s",
                        )
                    except Exception as e:
                        log.warn(f"{prefix}诊断 dump 失败: {e}")
        threading.Thread(target=_heartbeat, daemon=True).start()

    # tee 输出 + 监控 timeout
    deadline = time.monotonic() + timeout if timeout else None
    timed_out = False
    try:
        assert proc.stdout is not None
        while True:
            # select 实现非阻塞读 + timeout 检查
            remaining = (deadline - time.monotonic()) if deadline else 1.0
            if remaining is not None and remaining <= 0:
                timed_out = True
                log.fail(f"{prefix}timeout {timeout}s 到期，正在杀进程组...")
                # 杀进程前先 dump 现场（用户最关心：claude 当时在等什么）
                try:
                    _dump_hang_diagnostics(
                        proc.pid, prefix=prefix, reason=f"timeout_{timeout}s",
                    )
                except Exception as e:
                    log.warn(f"{prefix}诊断 dump 失败: {e}")
                _kill_tree(proc.pid, signal.SIGTERM)
                # 给子进程 2 秒优雅退出
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    _kill_tree(proc.pid, signal.SIGKILL)
                break

            wait_for = min(1.0, remaining) if remaining else 1.0
            ready, _, _ = select.select([proc.stdout], [], [], wait_for)
            if proc.stdout in ready:
                chunk = os.read(proc.stdout.fileno(), 4096)
                if not chunk:
                    # EOF，子进程已结束输出
                    break
                # 标记最近一次有新输出的时间戳（供 heartbeat 检测 silent hang）
                with _last_output_lock:
                    last_output_ts = time.monotonic()
                # 实时双写
                try:
                    sys.stderr.buffer.write(chunk)
                    sys.stderr.buffer.flush()
                except (BrokenPipeError, ValueError):
                    pass
                if log_fp:
                    try:
                        log_fp.write(chunk.decode("utf-8", errors="replace"))
                        log_fp.flush()
                    except (BrokenPipeError, ValueError):
                        pass
            elif proc.poll() is not None:
                # 没有数据可读且子进程已退出
                break
    except KeyboardInterrupt:
        log.fail(f"{prefix}收到 KeyboardInterrupt，杀进程组")
        _kill_tree(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _kill_tree(proc.pid, signal.SIGKILL)
        raise
    finally:
        stop_hb.set()
        if log_fp:
            log_fp.close()

    # 等子进程真的结束（拿 returncode）
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid, signal.SIGKILL)
        proc.wait()

    rc = 124 if timed_out else (proc.returncode or 0)
    return RunResult(returncode=rc, log_path=log_path, timed_out=timed_out)


def setup_signal_handlers(on_interrupt: Callable[[int], None]) -> None:
    """主进程安装 SIGINT/SIGTERM handler，把信号变成 on_interrupt(signum) 调用。

    on_interrupt 应该负责：
      1) 标记当前 stage 为 fail（checklist）
      2) 杀所有子进程
      3) sys.exit(130)
    """
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, _frame: on_interrupt(s))
