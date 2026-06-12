"""guardx：guard-transform 的 Python 编排核心（阶段 2 渐进迁移）

历史背景：
    guard-transform 初版是 ~3000 行 bash（详见 ../README.md）。
    bash 在跨平台、信号处理、可测试性、数据驱动编排上达到瓶颈，
    阶段 2 把"编排骨架"迁到 Python（pure stdlib，零依赖），
    把 verifiers/prompts/templates 三类资产保留为外部文件 / 子进程调用。

模块边界：
    cli         — 命令行入口（argparse），子命令 transform/detect/verify/clean
    config      — 路径常量、env 读取、解析 SOURCE_PROJECT → WORK_DIR/STATE_DIR
    log         — 统一日志：stderr 着色 + transform.log 落盘
    process     — subprocess 包装：timeout / kill_tree / tee / heartbeat
    checklist   — TSV 持久化（与 bash 版完全兼容）+ 续跑判定
    git         — 工作副本里跑 git 的 helper
    llm         — LLM CLI 抽象层（claude/qwen/codex/gemini/codewiz/mock）
    pipeline    — stage 编排循环（含 autofix retry）；当前仍委托 bash stages
"""

__version__ = "0.1.0-stage2"
