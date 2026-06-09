# 日志排查

1. 运行 `qs logs <pod/trial_id> -n 200`，**设置 Bash timeout（如 30000ms）避免挂起**
2. 分析日志，重点关注：OOM、CUDA error、Traceback、NCCL timeout、segfault
3. 如需深入排查，提示用户 `! qs exec <pod> -it` 进入容器

> `qs logs` 对存活 pod 会持续流式输出，必须设置 timeout。pod 已终止时拉取历史日志，有限输出不会挂起。
