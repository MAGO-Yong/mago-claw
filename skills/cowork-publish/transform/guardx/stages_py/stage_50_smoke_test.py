"""stage 50: 跑全部 verifiers（不可绕过、不可伪造）。

任一 verifier 失败 → 整个 stage 失败 → 不允许进入 60_package。
GUARD_STRICT=0 可让流水线带伤继续（仅给调试用）。

产出：STATE_DIR/smoke-fingerprint.txt，stage 70 报告引用。
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

from .. import config, git, log, verifier

# 静态 verifier（不需要起服务）
# 顺序：基础脚本/端口/env 命名 → 外部基础设施/文件 DB → 公网/迁移工具 →
#       DB props/SQL → URL/CSS 路径 → AI/SSO → 静态资源/开发期残留
_STATIC_VERIFIERS = (
    "verify_entry_scripts.sh",
    "verify_health_consistency.sh",    # health.sh 探测路径 ↔ 业务路由 双向一致（纯规则）
    "verify_port_3000.sh",
    "verify_app_factory.sh",
    "verify_start_artifacts.sh",       # 跨语言产物存在性（纯规则）
    "verify_frontend_built.sh",        # 前端 dist/build/.next 等产物已落盘（云端缺前端文件白屏拦截）
    "verify_startup_log_stream.sh",    # start.sh exec 行必须 2>&1 显式收敛 stderr（避免 Guard 误判）
    "verify_subprocess_lifecycle.sh",  # 业务 spawn 子服务：父子进程组生命周期（detached/start_new_session 反例 fail；缺信号桥接 warn）
    "verify_app_env_naming.sh",
    "verify_no_external_infra.sh",
    "verify_no_file_db.sh",
    "verify_install_no_internet.sh",
    "verify_python_requirements.sh",
    "verify_venv_activation.sh",       # 非根 start.sh 调用 venv-installed Python CLI 必须激活 venv 或用绝对路径（避免 `exec: gunicorn: not found`）
    "verify_no_migrations_tool.sh",
    "verify_db_props_keys.sh",
    "verify_db_url_safe.sh",
    "verify_seed_idempotent.sh",
    "verify_no_url_absolute.sh",
    "verify_css_no_abs_url.sh",
    "verify_ai_calls.sh",          # 文本 LLM 通路（Runway Bedrock）；无文本 AI 信号自动 skip
    "verify_image_calls.sh",       # 图像生成通路（Runway Google GenerateContent）；无图像 AI 信号自动 skip
    "verify_sso_correct.sh",
    "verify_static_antipattern.sh",
    "verify_no_dev_artifacts.sh",
    "verify_start_sh_llm.sh",          # LLM 综合 review（默认 skip，GUARD_LLM_VERIFY=1 启用）
)

# 动态 verifier（唯一）：走平台标准三件套 install.sh + start.sh + health.sh + asset 200/MIME
# 最贴近 Guard Pod 实际运行环境，串行验证：
#   - install 链路（联网拉包 / 缺 pip-node / venv 激活）
#   - start  链路（进程秒崩 / 端口绑定 / 启动器报错）
#   - health 链路（探测路径 ≠ 实际监听端口）
#   - asset  产物（URL 200 / MIME 正确 / 应用层不二次 gzip / Next standalone 不烧 prefix）
_DYNAMIC_VERIFIER = "verify_runtime_full.sh"


def _git_short_sha(work_dir: Path) -> str:
    if not (work_dir / ".git").is_dir():
        return "none"
    r = git.gx("rev-parse", "--short", "HEAD", cwd=work_dir)
    if r.returncode != 0:
        return "none"
    return (r.stdout or "").strip() or "none"


def run(cfg: config.Config) -> int:
    home = config.home_dir()
    vdir = home / "verifiers"

    fail_count = 0

    for vname in _STATIC_VERIFIERS:
        if not verifier.run_with_autofix(vdir / vname, cfg):
            fail_count += 1

    # ─── 动态 verifier 门控策略 ───
    # 默认按 GUARD_RUN_MODE 自动判定：
    #   - GUARD_RUN_MODE=interactive（macOS 桌面） → 默认开，本地秒发现起不来
    #   - 其它（non-interactive / openclaw / CI / 云端）→ 默认 skip
    #     避免在 Pod 内真启业务进程（违反"只构建不运行"安全边界，
    #     可能凭据外泄 / RCE / SSRF）
    # GUARD_SMOKE_FULL=0/1 可显式覆盖
    log.log(
        "▶ 动态烟测：verify_runtime_full "
        "(interactive 默认开 / 其它默认 skip，GUARD_SMOKE_FULL=0/1 覆盖)"
    )
    if not verifier.run_with_autofix(vdir / _DYNAMIC_VERIFIER, cfg):
        fail_count += 1

    if fail_count > 0:
        if cfg.strict:
            log.die(
                f"{fail_count} 个 verifier 经 autofix 仍失败，"
                f"详见 {cfg.state_dir}/verify-*.log"
                "（设 GUARD_STRICT=0 可让流水线带伤继续到 60_package）"
            )
        log.warn(f"{fail_count} 个 verifier 仍失败，但 GUARD_STRICT=0，继续执行")

    # ---- 写 fingerprint ----
    ts = time.time_ns()
    host = socket.gethostname()
    sha = _git_short_sha(cfg.work_dir)
    fp = f"ts={ts} host={host} work={cfg.work_dir} sha={sha}"
    (cfg.state_dir / "smoke-fingerprint.txt").write_text(fp + "\n")
    log.log(f"fingerprint: {fp}")

    log.ok("stage 50 全部通过")
    return 0
