# 由 guard-transform 渲染生成
# 双路 registry：@xhs/* 走内部 / 其余走 npmmirror（公网镜像）
#
# 注意：值必须裸写（不带引号），否则 verify_install_no_internet.sh 的正则
# `^registry[[:space:]]*=[[:space:]]*https?://` 会因 `=` 后紧跟 `"` 而误判
# 为"未指向内部源"——历史踩过的坑，请勿改回 `registry = "..."` 形式。
@xhs:registry=http://npm.devops.xiaohongshu.com:7001
registry=http://registry.npmmirror.com
