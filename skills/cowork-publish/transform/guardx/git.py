"""git 薄封装：与 bash 版 lib/common.sh 的 gx / ensure_git_repo / git_commit_step 对齐。

故意不引第三方（GitPython / dulwich）：guard-transform 只用到最基本的
init / add -A / commit / diff，subprocess 已经够；少一份依赖更省事。

关于"运行环境没装 git"的处理（与 ``ensure_installed`` 协作）：
  - ``gx()`` 捕获 ``FileNotFoundError`` 转成 rc=127 的伪 CompletedProcess，
    避免外部调用栈直接崩。
  - ``ensure_installed()`` 由 cli 主入口在所有 stage 跑之前调一次：
      * 已装 → no-op
      * 没装 + 非交互 → ``log.die`` 直接友好失败
      * 没装 + 交互  → 弹问"是否自动安装"（30s 超时按否），按平台选包管理器
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import log, prompt_util


def gx(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    """在 cwd 下执行 ``git <args>``，返回 CompletedProcess（不抛异常）。

    无 git 时（``FileNotFoundError``）返回伪 CompletedProcess(rc=127)，
    调用方按返回值判断即可，不需要再 try。这样 ``commit_step()`` 在无 git
    场景会自然返回 False 而非栈崩，``ensure_repo()`` 则会触发显式 die。
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        # 伪造一个 rc=127（与 shell "command not found" 语义对齐）+ stderr 提示
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=127,
            stdout="",
            stderr="git: command not found (PATH 中未找到 git；请先安装 git)",
        )


def ensure_repo(work_dir: Path) -> None:
    """确保 work_dir 是 git 仓库；不是就 init + 首次 commit。

    若运行环境没装 git，gx() 会返回 rc=127；这里 ``log.die`` 显式失败而非
    悄悄继续（首次 init 失败后续所有 commit_step 都会无声失败 → 没法回溯）。
    正常情况下 cli 主入口已调过 ``ensure_installed()`` 提前拦截，所以走到
    这里说明用户拒绝了自动安装但仍想继续——必须 die 出去。
    """
    if (work_dir / ".git").is_dir():
        return
    r = gx("init", "-q", cwd=work_dir)
    if r.returncode == 127:
        log.die(
            "无法初始化 git 仓库：未在 PATH 找到 git。\n"
            "      guard-transform 用 git 在 stage 之间打快照（init / add / commit / diff）\n"
            "      以便失败时定位是哪个 stage 引入的问题。\n"
            "      请先安装 git：macOS `brew install git` / Debian `apt-get install git`\n"
            "                / RHEL `yum install git` / Alpine `apk add git`"
        )
    gx("config", "user.email", "guard-transform@local", cwd=work_dir)
    gx("config", "user.name", "guard-transform", cwd=work_dir)
    gx("add", "-A", cwd=work_dir)
    # 允许空 commit 失败（如目录里啥都没）
    gx("commit", "-q", "-m", "baseline (after prepare)", cwd=work_dir)


def commit_step(work_dir: Path, msg: str) -> bool:
    """有 staged 改动就 commit，没有就 no-op。返回是否真的 commit 了。

    无 git 时所有 gx() 都返回 rc=127，``diff --cached --quiet`` 会被识别为
    "没有差异"（rc=0 走 False，rc!=0 走 commit；rc=127 走 commit 分支，
    commit 也会返回 127 → 走最末的 warn 分支不死）。这给了"没 git 也能跑
    完后续 stage（只是丢失了 commit 回溯）"的降级路径，是否启用这个降级
    路径由调用方决定（autofix 的 D2 逻辑会借此自然走 abort）。
    """
    add_r = gx("add", "-A", cwd=work_dir)
    if add_r.returncode == 127:
        # 无 git → 静默降级为 no-op（false）。不打 warn 是因为 autofix 的 D2
        # 会基于这个 False 连续 2 次后 abort，warn 出来会刷屏。
        # 真正的 die 由 ensure_repo / ensure_installed 在更早的入口负责。
        return False
    diff = gx("diff", "--cached", "--quiet", cwd=work_dir)
    if diff.returncode == 0:
        # quiet 模式 returncode=0 表示**没有**差异
        return False
    r = gx("commit", "-q", "-m", msg, cwd=work_dir)
    if r.returncode == 0:
        log.ok(f"git commit: {msg}")
        return True
    log.warn(f"git commit 失败: {msg} (rc={r.returncode}) {r.stderr.strip()}")
    return False


# ---------------------------------------------------------------------------
# 环境预检：在 cli 主入口跑所有 stage 之前调一次，避免到 stage 00 才崩
# ---------------------------------------------------------------------------

# 各平台包管理器 + 安装命令；按"装得最多 / 检测最便宜"顺序排
# 注意：用 sudo 而非 sudo -n（-n 在没缓存的环境会直接报错；裸 sudo 让用户能输密码）
_INSTALL_RECIPES: tuple[tuple[str, str, list[str]], ...] = (
    # (检测命令, 人类可读描述, 安装命令 argv)
    ("apt-get", "Debian / Ubuntu (apt-get)", ["sudo", "apt-get", "install", "-y", "git"]),
    ("dnf",     "Fedora / RHEL 8+ (dnf)",   ["sudo", "dnf",     "install", "-y", "git"]),
    ("yum",     "RHEL 7 / CentOS (yum)",    ["sudo", "yum",     "install", "-y", "git"]),
    ("apk",     "Alpine (apk)",              ["sudo", "apk", "add", "--no-cache", "git"]),
    ("pacman",  "Arch (pacman)",             ["sudo", "pacman", "-S", "--noconfirm", "git"]),
    ("zypper",  "openSUSE (zypper)",         ["sudo", "zypper", "install", "-y", "git"]),
    ("brew",    "macOS (Homebrew)",          ["brew", "install", "git"]),  # brew 自己处理权限，不要 sudo
)


def _pick_install_recipe() -> tuple[str, list[str]] | None:
    """按 PATH 中存在的包管理器挑一条安装命令。找不到返回 None。"""
    for binary, desc, cmd in _INSTALL_RECIPES:
        if shutil.which(binary):
            return desc, cmd
    return None


def _try_auto_install() -> bool:
    """根据当前系统选包管理器尝试安装 git。安装后再次 ``which('git')`` 校验。

    任何一步失败都返回 False，让调用方决定是 die 还是降级。
    """
    recipe = _pick_install_recipe()
    if recipe is None:
        log.fail("未识别到任何受支持的包管理器（apt-get / dnf / yum / apk / pacman / zypper / brew）")
        log.log("      请手动安装 git 后重试：https://git-scm.com/downloads")
        return False

    desc, cmd = recipe
    log.warn(f"[git-install] 检测到 {desc}，将执行：{' '.join(cmd)}")
    log.log("              （sudo 可能会要求输入密码；按 Ctrl+C 可中止）")
    try:
        # 不捕获 stdout/stderr，让包管理器的进度直接打到终端，便于看下载进度 + 输密码
        rc = subprocess.call(cmd)
    except FileNotFoundError as e:
        log.fail(f"[git-install] 执行失败：{e}")
        return False
    except KeyboardInterrupt:
        log.fail("[git-install] 用户中断安装")
        return False

    if rc != 0:
        log.fail(f"[git-install] 包管理器退出 rc={rc}，安装可能失败")
        return False

    # 安装后立即重新探测 PATH（包管理器可能把 git 放到 /usr/local/bin 等非典型路径）
    if shutil.which("git") is None:
        log.fail("[git-install] 安装命令返回成功，但 PATH 仍找不到 git；请检查 shell 重启或手动 `hash -r`")
        return False

    log.ok(f"[git-install] git 安装成功：{shutil.which('git')}")
    return True


def ensure_installed() -> None:
    """启动时一次性预检；按交互/非交互走不同分支。

    设计意图：把"环境没装 git"这个错误**前置**到 stage 跑之前，给用户友好提示
    （含安装命令、平台特定建议），而不是等到 stage 00 ``git init`` 崩在栈里、
    或者更糟——stage 00 静默跑过去到 stage 20 才发现所有 commit_step 都是 no-op。

    GUARD_SKIP_GIT_CHECK=1 可跳过本预检（罕见场景：用户自定义了 git 包装脚本
    但没放进 PATH，希望 guardx 直接相信 git 可用）。
    """
    if os.environ.get("GUARD_SKIP_GIT_CHECK") == "1":
        return
    if shutil.which("git") is not None:
        return  # 装了就 no-op，零开销

    log.fail("未在 PATH 找到 git；guard-transform 依赖 git 做 stage 间快照（init / add / commit / diff）")

    if prompt_util.is_non_interactive():
        log.die(
            "当前为非交互环境（CI / 后台进程 / 非 tty），无法弹问是否自动安装。\n"
            "      请先安装 git 后重试：\n"
            "        macOS  : brew install git\n"
            "        Debian : sudo apt-get install -y git\n"
            "        RHEL   : sudo yum install -y git\n"
            "        Alpine : sudo apk add --no-cache git\n"
            "      或设置 GUARD_SKIP_GIT_CHECK=1 跳过本预检（仅当你确信 git 可用但 PATH 探测不到时）"
        )

    # 交互模式：弹问是否自动安装；30s 超时按 n（保守，不主动改用户系统）
    recipe = _pick_install_recipe()
    if recipe is None:
        log.die(
            "未识别到任何受支持的包管理器（apt-get / dnf / yum / apk / pacman / zypper / brew）。\n"
            "      请手动安装 git 后重试：https://git-scm.com/downloads"
        )

    desc, cmd = recipe
    prompt = (
        f"\n{log.C_BLD}是否尝试自动安装 git？{log.C_RST}\n"
        f"  将执行：{log.C_YEL}{' '.join(cmd)}{log.C_RST}\n"
        f"  平台：  {desc}\n"
        f"  {log.C_GRN}[y]{log.C_RST} 是，立即安装（可能要输 sudo 密码）\n"
        f"  {log.C_RED}[n]{log.C_RST} 否，中止 guardx（默认；我自己装）\n"
        f"\n请输入 y / n（30 秒超时按 n）: "
    )
    ans = prompt_util.read_choice_with_timeout(prompt, timeout_s=30, default="n")
    if ans not in ("y", "yes"):
        log.die(
            "用户取消自动安装。请手动安装 git 后重试：\n"
            f"        {' '.join(cmd)}\n"
            "      或参考 https://git-scm.com/downloads"
        )

    if not _try_auto_install():
        log.die("git 自动安装失败；请按上面提示手动安装后重试")
