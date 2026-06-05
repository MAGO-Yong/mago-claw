# Hi 消息发送参考

> 所有消息发送优先使用 `pmo send` 命令。HTTP 接口说明仅供参考（pmo CLI 内部调用方式）。

## pmo CLI 快速发送

```bash
# 发群聊消息（通过项目名自动获取 chatId）
pmo send msg "消息内容" --project "项目名"

# 直接指定 chatId
pmo send msg "消息内容" --chat-id "CHAT7xxx"

# @全体
pmo send msg "消息内容" --project "项目名" --mention-all

# 发私聊
pmo send msg "消息内容" --to "user@xiaohongshu.com"
pmo send msg "消息内容" --to "薯名(真名)"

# 截图并发送
pmo send screenshot "https://example.com" --project "项目名" --caption "截图说明"
pmo send screenshot "https://example.com" --chat-id "CHAT7xxx"
pmo send screenshot "https://example.com" --to "user@xiaohongshu.com"
```

## operator-id 获取规则

发送时需在 Header 传 `operator-id`（发送者邮箱）：
1. 优先从 `USER.md` 读取 `@xiaohongshu.com` 邮箱
2. 不可用时回退为 `projectConfig.createdBy`
3. 两者都不可用时，提示用户补充

## @策略

| 场景 | 做法 |
|------|------|
| 正文 @ 有真名的人 | `薯名(真名)`，后端自动转换 |
| 正文 @ 只有薯名 | `<薯名>` |
| 正文 @ 邮箱 | `<@email>` |
| 额外 @ 正文未提及的人 | `mentionList: ["a@xhs.com"]` |
| @ 所有人 | `mentionAll: true` |

⚠️ 正文已有 `<@email>` 时，**不传 mentionList**，否则重复 @

## 私聊消息必须加署名

```
{消息内容}

—— {USER.md 中的用户名}
```

群聊无需署名。

## 消息内容规范

**所有发送到 Hi 群/私聊的消息，内容必须全程使用 Markdown 格式**，Hi 支持完整 Markdown 渲染。

| 元素 | 正确写法 | 错误写法 |
|------|---------|---------|
| 加粗 | `**重要内容**` | 重要内容（无格式） |
| 列表 | `- 条目` 或 `1. 条目` | 纯文本堆砌 |
| 链接 | `[链接文字](URL)` | 裸 URL（Hi 不解析） |
| 标题 | `**标题**`（Hi 不支持 # 标题） | `# 标题` |
| 代码 | \`inline\` 或 \`\`\`块\`\`\` | 直接贴代码 |

### 链接格式（最常见错误）
```
✅ 正确：[0415 PL技术项目周会](https://docs.xiaohongshu.com/doc/xxx)
❌ 错误：https://docs.xiaohongshu.com/doc/xxx
```

生成消息内容时，先在脑内过一遍：**所有链接是否已转成 `[文字](URL)`？所有重点是否已加粗？**

## 消息格式模板

**催更 Todo（群聊）：**
```
✅ 以下 **{项目名}** 未完成的待办项，请负责人及时更新

1. {Todo描述}，截止日期:{DDL}，薯名A(张三)
2. {Todo描述}，截止日期:无，<薯名B>

[相关文档链接]({URL})
```

**催更例会文档（群聊）：**
```
PMO BP发现 薯名A(张三) <薯名B> 还没更新[例会文档]({URL})呢🙂，请记得会前更新好哦～
```

**催更排除规则（必须遵守）：**
- 进展健康度已标"已完成" → 不催
- 里程碑全部未打勾且最早节点时间未到 → 不催
- 只催：健康度为空 **且** 至少有一个里程碑节点已打勾或时间已过

## 群消息查询

通过 browser evaluate 在 aipmo 域下调用：

```javascript
const resp = await fetch('/api/hi/group/query', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({chatId: 'CHAT7xxx', limit: 100})
});
const data = await resp.json();
// data.data.messages — 消息数组
// data.data.hasNext — 是否还有更多
```

消息字段：`messageId`、`senderEmail`、`content`、`messageType`（1=文本，9=富文本，1111=图片，1113=表情反应）、`sendTime`（东八区 LocalDateTime）、`recalled`

过滤最近 N 小时：
```javascript
const cutoff = Date.now() - N * 3600 * 1000;
const recent = data.data.messages.filter(m => {
  if (m.recalled || [1111, 1113].includes(m.messageType)) return false;
  return new Date(m.sendTime + '+08:00').getTime() >= cutoff;
});
```

## 撤回群聊消息

```javascript
await fetch('/api/hi/group/recall', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({chatId: 'CHAT7xxx', messageId: '<messageId>'})
});
```

## 截图发送说明

- 凭证自动从 `~/.openclaw/hi_config.json` 的 `project_shu` 读取
- 默认每段高度 1500px，自动找空白行分割，不从表格中间截断
- 最后一段底部补白边确保等宽
