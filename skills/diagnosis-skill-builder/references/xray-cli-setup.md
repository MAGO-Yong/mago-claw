# xray-cli 准备

这份文档只用于告警 Skill 创建和验证阶段。安装、升级和登录不应写进生成后的告警 Skill 运行时逻辑。

## 预检

```bash
xray-cli --version
xray-cli auth status
```

`xray-cli` 版本必须是 `v0.0.31` 或以上。

## 安装或升级

优先全局安装指定版本：

```bash
npm install -g @xray/xray-cli@0.0.31 --registry http://npm.devops.xiaohongshu.com:7001/
```

如果全局安装遇到权限问题，安装到用户目录：

```bash
mkdir -p ~/.npm-global
npm install -g @xray/xray-cli@0.0.31 --prefix ~/.npm-global --registry http://npm.devops.xiaohongshu.com:7001/
```

用户目录安装后，先检查 `~/.bash_profile` 是否已有 PATH 块。没有时再追加，避免重复写入：

```bash
if ! grep -q "## xray-cli start" ~/.bash_profile 2>/dev/null; then
  cat >> ~/.bash_profile <<'EOF'
## xray-cli start
export PATH="$HOME/.npm-global/bin:$PATH"
## xray-cli end
EOF
fi
```

## 认证

验证阶段需要 `xray-cli auth status` 成功。认证失败时先完成开发环境登录，再执行 upload/test。

生成后的告警 Skill 运行时不得执行交互式登录，也不得把认证失败伪装成正常诊断结果；应输出 `blocked`。
