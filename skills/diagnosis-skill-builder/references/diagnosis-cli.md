# diagnosis-cli 原子能力

这份文档登记 `diagnosis-skill-builder` 当前允许生成的告警 Skill 使用的 `diagnosis-cli` 只读原子能力。

`diagnosis-cli` 用于封装三方平台或诊断语义下的小型原子能力。它不是 `xray-cli` 的替代品，也不是任意 shell 出口。没有写在本文档里的 `diagnosis-cli` 子命令，生成的告警 Skill 运行时不得依赖。

## 安装

创建和验证阶段可用 npm 安装：

```bash
npm install -g @xray/diagnosis-cli --registry http://npm.devops.xiaohongshu.com:7001/
```

安装只属于创建和验证阶段。生成后的告警 Skill 运行时不得执行安装、升级或交互式修复。

## 预检

```bash
diagnosis-cli --version
diagnosis-cli change query <app> --help
```

如果目标运行环境里缺少 `diagnosis-cli`，或 `change query` 不可用，生成的告警 Skill 应把对应取证节点标为 `blocked` / `dependency_gap`，不要伪装成已自动取证。

## 变更事件查询

当前唯一登记的 `diagnosis-cli` 原子能力是变更事件查询：

```bash
diagnosis-cli change query <app> \
  --start "<YYYY-MM-DD HH:mm:ss>" \
  --end "<YYYY-MM-DD HH:mm:ss>" \
  --output-format json
```

示例：

```bash
diagnosis-cli change query xrayaiagent \
  --start "2026-05-29 00:00:00" \
  --end "2026-06-01 00:00:00" \
  --output-format json
```

用途：

- 查询指定 app 在给定时间窗内的变更事件。
- 用于判断告警前后是否存在发布、配置、实验、Switch、Autobots 等相关变更证据。
- 只能作为证据来源之一，不能单独把“有变更”解释成确定根因。

参数约束：

- `<app>` 必填，优先来自告警 payload、服务树、用户给定 app 或 Skill 输入契约。
- `--start` / `--end` 必须使用明确时间，不要在生成后的通用 Skill 中硬编码示例时间。
- 时间格式优先使用 `YYYY-MM-DD HH:mm:ss`，按 `Asia/Shanghai` 表达。
- 可选过滤参数只有在场景明确需要时才使用，例如 `--system-name`、`--service`、`--change-env`、`--operator`、`--content`。
- 自动化消费必须使用 `--output-format json`。

失败策略：

- 空结果：报告“该时间窗未查到变更事件”，不要推出确定性无关结论。
- 返回非 0：报告命令失败、stderr 和 returncode，状态标为 `blocked` 或 `unknown`。
- 超时：报告 timeout，并建议缩小时间窗或增加过滤条件。
- 鉴权失败：报告 `blocked`，不要要求运行时交互登录。
- 字段缺失：保留原始命令和摘要，把缺失字段列入未知项。

## 不允许

- 不允许直接调用变更平台 HTTP API、`curl` 或浏览器状态绕过 `diagnosis-cli`。
- 不允许把未登记的 `diagnosis-cli` 子命令写进生成后的告警 Skill。
- 不允许在运行时执行 `npm install`、写全局 PATH、修改认证文件或等待人工登录。
- 不允许把 text 输出作为机器消费合同。
