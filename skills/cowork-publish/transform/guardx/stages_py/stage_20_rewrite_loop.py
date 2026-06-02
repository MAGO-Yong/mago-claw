"""stage 20: 调度 LLM 做"语义改写"（翻译自 stages/20_rewrite_loop.sh）。

子任务（按 stack.json 条件触发）：
  20:remove_external_infra    has_external_infra=1 时跑（含 redis/mq/s3/es）；强 verifier
  20:rewrite_ai_calls         has_ai_text=1 时跑；强 verifier（verify_ai_calls.sh），失败 die
                              （文本对话 → Runway Bedrock InvokeModel）
  20:rewrite_image_calls      has_ai_image=1 时跑；强 verifier（verify_image_calls.sh），失败 die
                              （图像生成 → Runway Google GenerateContent / Gemini Nano Banana）
  20:rewrite_sso              has_sso=1 时跑；强 verifier（verify_sso_correct.sh）
  20:fix_paths                总是跑；强 verifier，失败 warn 不 die（最终烟测会拦）

向后兼容：旧 stack.json 没有 has_ai_text / has_ai_image 时，回退用 has_ai（仅触发文本改写）。
新代码请在 stage 10 输出两个细分字段。

设计哲学：本 stage **只**调 LLM 处理"非机械"问题。
机械改写（端口、shebang、镜像、.npmrc）一律走 stage 30 模板渲染。
"""

from __future__ import annotations

import json
from pathlib import Path

from .. import checklist, config, git, llm, log


def _stack_get(state_dir: Path, key: str) -> str:
    """从 STATE_DIR/stack.json 读字段；失败返回空串。"""
    try:
        data = json.loads((state_dir / "stack.json").read_text())
    except (OSError, json.JSONDecodeError):
        log.die("stack.json 不存在或损坏，未跑 stage 10？")
    val = data.get(key, "")
    return "" if val is None else str(val)


def run(cfg: config.Config) -> int:
    home = config.home_dir()
    prompts_dir = home / "prompts"
    verifiers_dir = home / "verifiers"

    has_redis = _stack_get(cfg.state_dir, "has_redis")
    has_external_infra = _stack_get(cfg.state_dir, "has_external_infra")
    # 向后兼容：旧 stack.json 没有 has_external_infra 时，回退用 has_redis
    if not has_external_infra:
        has_external_infra = has_redis
    has_ai = _stack_get(cfg.state_dir, "has_ai")
    has_ai_text = _stack_get(cfg.state_dir, "has_ai_text")
    has_ai_image = _stack_get(cfg.state_dir, "has_ai_image")
    # 向后兼容：旧 stack.json 没有 has_ai_text / has_ai_image 时，回退用 has_ai 触发文本改写
    # （旧字段没有图像信号，has_ai_image 默认 0；保守起见不跑图像改写避免误改）
    if not has_ai_text and not has_ai_image and has_ai == "1":
        has_ai_text = "1"
    has_sso = _stack_get(cfg.state_dir, "has_sso")
    has_static_spa = _stack_get(cfg.state_dir, "has_static_spa")
    framework = _stack_get(cfg.state_dir, "framework")

    log.log(
        f"改写计划：has_external_infra={has_external_infra} "
        f"(redis={has_redis}), has_ai_text={has_ai_text}, has_ai_image={has_ai_image}, "
        f"has_sso={has_sso}, framework={framework}"
    )

    # stage 20 是整个 pipeline 唯一真正需要"深度思考"的环节：
    # 跨文件迁 Redis→PG、改 SDK→Runway Bedrock、改造 SSO 等
    # 都要求 LLM 理解上下文 + 给出一致改写。这里显式用 strong profile（默认 opus-4-7）。
    # 其他 stage 的 verifier/build autofix 在 verifier.py 默认走 fast (sonnet-4-6)。
    llm_cfg = llm.LLMConfig.for_profile("strong")

    # ---- task 1: 移除外部基础设施反模式（Redis/MQ/S3/ES）----
    if has_external_infra == "1":
        with checklist.substep("20:remove_external_infra") as do:
            if do:
                ok = llm.call_with_verify(
                    prompts_dir / "20_remove_external_infra.md",
                    verifiers_dir / "verify_no_external_infra.sh",
                    cfg.work_dir,
                    cfg.state_dir,
                    max_retry=3,
                    cfg=llm_cfg,
                )
                if not ok:
                    log.die("task 20:remove_external_infra 失败 - 重试已耗尽")
                git.commit_step(
                    cfg.work_dir,
                    "rewrite: remove external infra (redis/mq/s3/es → pg)",
                )
    else:
        checklist.skip("20:remove_external_infra", "has_external_infra=0")

    # ---- task 2: 文本 AI 调用迁 Runway Bedrock InvokeModel（带强 verifier）----
    if has_ai_text == "1":
        with checklist.substep("20:rewrite_ai_calls") as do:
            if do:
                ok = llm.call_with_verify(
                    prompts_dir / "22_rewrite_ai_calls.md",
                    verifiers_dir / "verify_ai_calls.sh",
                    cfg.work_dir,
                    cfg.state_dir,
                    max_retry=3,
                    cfg=llm_cfg,
                )
                if ok:
                    git.commit_step(
                        cfg.work_dir, "rewrite: text AI calls -> Runway Bedrock"
                    )
                else:
                    log.die(
                        "task 20:rewrite_ai_calls 失败 - 重试已耗尽 "
                        "（详见 transform_prompt.md § 五）"
                    )
    else:
        checklist.skip("20:rewrite_ai_calls", "has_ai_text=0")

    # ---- task 2.5: 图像 AI 调用迁 Runway Google GenerateContent（带强 verifier）----
    # 文本和图像是两条独立链路（独立 endpoint / 独立 api-key / 独立配额），可以同时存在。
    # 改写 prompt 见 prompts/22_rewrite_image_calls.md（覆盖 DALL·E / SD / 万相 / Flux 等）。
    if has_ai_image == "1":
        with checklist.substep("20:rewrite_image_calls") as do:
            if do:
                img_prompt = prompts_dir / "22_rewrite_image_calls.md"
                img_verifier = verifiers_dir / "verify_image_calls.sh"
                if not img_prompt.is_file() or not img_verifier.is_file():
                    log.warn(
                        "22_rewrite_image_calls.md 或 verify_image_calls.sh 缺失，"
                        "跳过图像 AI 子任务（请重装 skill 或 git pull 同步最新版本）"
                    )
                else:
                    ok = llm.call_with_verify(
                        img_prompt,
                        img_verifier,
                        cfg.work_dir,
                        cfg.state_dir,
                        max_retry=3,
                        cfg=llm_cfg,
                    )
                    if ok:
                        git.commit_step(
                            cfg.work_dir,
                            "rewrite: image AI calls -> Runway Google GenerateContent",
                        )
                    else:
                        log.die(
                            "task 20:rewrite_image_calls 失败 - 重试已耗尽 "
                            "（详见 transform_prompt.md § 五.5）"
                        )
    else:
        checklist.skip("20:rewrite_image_calls", "has_ai_image=0")

    # ---- task 3: SSO 改造（Decrypted-Userinfo header + auto-provision）----
    if has_sso == "1":
        with checklist.substep("20:rewrite_sso") as do:
            if do:
                sso_prompt = prompts_dir / "21_rewrite_sso.md"
                sso_verifier = verifiers_dir / "verify_sso_correct.sh"
                if not sso_prompt.is_file() or not sso_verifier.is_file():
                    log.warn(
                        "21_rewrite_sso.md 或 verify_sso_correct.sh 缺失，"
                        "跳过 SSO 子任务"
                    )
                else:
                    ok = llm.call_with_verify(
                        sso_prompt,
                        sso_verifier,
                        cfg.work_dir,
                        cfg.state_dir,
                        max_retry=3,
                        cfg=llm_cfg,
                    )
                    if ok:
                        git.commit_step(
                            cfg.work_dir,
                            "rewrite: SSO -> Decrypted-Userinfo header + auto-provision",
                        )
                    else:
                        log.die(
                            "task 20:rewrite_sso 失败 - 重试已耗尽 "
                            "（详见 transform_prompt.md § 六）"
                        )
    else:
        checklist.skip("20:rewrite_sso", "has_sso=0")

    # ---- task 4: URL 裸路径修复 ----
    with checklist.substep("20:fix_paths") as do:
        if do:
            ok = llm.call_with_verify(
                prompts_dir / "23_fix_paths.md",
                verifiers_dir / "verify_no_url_absolute.sh",
                cfg.work_dir,
                cfg.state_dir,
                max_retry=3,
                cfg=llm_cfg,
            )
            if ok:
                git.commit_step(
                    cfg.work_dir,
                    "rewrite: paths -> relative; remove assetPrefix/basePath",
                )
            else:
                log.warn("路径改写未完全通过；继续后续 stage（最终烟测会拦截）")

    log.ok("stage 20 完成")
    return 0
