# 场景参考：创建项目周例会文档

> 最后验证：2026-04-15，基于 PL技术项目 0415→0422 周会文档完整跑通

## 触发

「帮我建周会文档」「创建本周项目周会」「准备周会」「建0XXX周会文档」

---

## 核心原则

- ⛔ **绝对不用 `write-doc` 或 `create-doc` 新建**：YDoc 格式会丢失，表格内容错位/崩溃
- ⛔ **不用 `/docgateway/api/menu/create` + `copyFromShortcutId`**：只创建空壳，不复制内容
- ✅ **唯一正确方案**：浏览器「创建副本」克隆 → `pmo weekly --new-id` 一键处理

---

## 完整 SOP（Step by Step）

### Step 1：dry-run 确认上一期

```bash
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ \
  npx --yes @xhs/pmo-cli@latest weekly "项目名" --date MMDD --dry-run
```

输出：确认识别的上一期文档标题、shortcutId、例会目录 ID。

---

### Step 2：浏览器创建副本

在已登录的 docs.xiaohongshu.com 页面（打开上一期文档后），执行：

```javascript
// 1. 触发目录项 ··· 按钮
const links = document.querySelectorAll('a');
for (const a of links) {
  if (a.href.includes('<上一期shortcutId>')) {
    const parent = a.closest('li') || a.parentElement;
    const btn = parent && parent.querySelector('button,._btn_7csdl_23');
    if (btn) { btn.click(); break; }
  }
}

// 2. 点「创建副本」菜单项
const spans = document.querySelectorAll('span,div,li');
for (const el of spans) {
  if (el.children.length < 3 && el.textContent.trim() === '创建副本') {
    el.click(); break;
  }
}

// 3. 等待跳转后获取新文档 ID
// window.location.href → https://docs.xiaohongshu.com/doc/<新ID>
```

等待约 8-10 秒页面跳转，从 URL 取新文档 ID。

---

### Step 3：pmo weekly 一键处理

```bash
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ \
  npx --yes @xhs/pmo-cli@latest weekly "项目名" --date MMDD --new-id <新文档ID>
```

**自动完成：**
| 步骤 | 内容 |
|------|------|
| 改标题 | 文档标题改为「MMDD {项目}周会」 |
| Todo 清空 | 状态列含完成语义（已完成/done/closed/🟢）的行：清空所有内容（含 mention embed）+ **删除行骨架**（不留空白行）|
| 进展大盘清空 | 健康度列不含完成语义的行：整列清空进展列（含 image/card/link/mention）；健康度已完成的行**保留不动** |
| 移顶 | 文档移到上一期文档之前 |

> **说明**：`pmo weekly` 内部使用 `hi-cli docs:get` 读取文档 Markdown，解析 Todo 表格和进展大盘表格，通过 `hi-cli docs:edit`（target/replace 模式）逐行清空已完成的 Todo 行内容、清空进展大盘进展列内容。

测试阶段（跳过移顶）：
```bash
... weekly "项目名" --date MMDD --new-id <新文档ID> --skip-move
```

---

### Step 4：更新会邀（可选）

```bash
cd ~/.openclaw/workspace/skills/hi-calendar
PATH="$PWD/node_modules/.bin:$PATH" bash run.sh edit-conference "<SCHEDULE_ID>" \
  --document-shortcut-ids "<新文档ID>" \
  --no-notify-creator \
  --no-notify-origin
```

> ⚠️ `hi-calendar` skill 已 patch：`conferenceReserveCheck` 对周期会议会误报，已在 `src/cli.ts` 中改为 try/catch 跳过。

---

### Step 5：询问是否发群通知

完成后输出文档链接，**询问用户**是否需要发群通知：

```
文档已就绪：https://docs.xiaohongshu.com/doc/<新文档ID>
要发群通知让大家更新进展列吗？
```

用户确认后：

```bash
NPM_CONFIG_REGISTRY=http://npm.devops.xiaohongshu.com:7001/ \
  npx --yes @xhs/pmo-cli@latest send msg "项目名" \
  "📋 **本周周会文档已就绪，请大家会前更新！**

[MMDD {项目}周会](https://docs.xiaohongshu.com/doc/<新文档ID>)

**请各位负责人：**
- ✍️ 在**进展管理/进展大盘**部分填写本周进展及风险总结
- ⚠️ 有风险或特殊议题请在对应风险/议题区域单独更新

请会前2小时内更新完毕，感谢～" \
  --mention-all
```

---

## 常见坑 & 解法

| 问题 | 原因 | 解法 |
|------|------|------|
| `pmo weekly` 找不到上一期文档 | 周会文档标题不含 MMDD 格式，或文档在目录根层而非子目录 | 已修复（`fix/custom-weekly-doc-lookup`）：增加 `\b\d{4}\b` 正则 + 根目录 fallback |
| Todo 已完成行未清空 | target/replace 匹配失败 | 确认 Markdown 表格行格式与 `docs:get` 返回一致；hash 版本校验失败时需重新 get |
| 浏览器「创建副本」按钮找不到 | hover 未触发或 ref 定位失败 | 用 JS evaluate 方式：找 `a[href*=shortcutId]` → 找 `._btn_7csdl_23` → 点击 → 找 `创建副本` SPAN |
| 副本创建后页面未跳转 | RedDoc 异步处理，需等 8-10 秒 | `sleep 9` 后再取 URL |
| 会邀更新报错「重复性日程」 | `conferenceReserveCheck` 误报 | hi-calendar skill 已 patch，无需处理 |

---

## 技术实现说明

### `pmo weekly` 内部流程

1. `pmo weekly --dry-run`：调用 `pmo tree` 识别上一期文档 shortcutId 和例会目录 ID
2. 浏览器克隆副本后，`pmo weekly --new-id <id>`：
   - `hi-cli docs:get --mode blocks` 定位 title blockId，用 `docs:edit --ops edit` 改标题
   - `hi-cli docs:get`（Markdown 模式）读取文档内容，解析 Part 1 Todo 表格和 Part 3 进展大盘表格
   - 逐行识别已完成 Todo 行（状态列含完成语义）和需清空的进展列，用 `docs:edit --target/--replace` 逐条替换
3. 移顶：POST `/docgateway/api/menu/moveShortcut`

### hi-cli docs:edit 使用规则

| 模式 | 用于 | 注意 |
|------|------|------|
| `--ops edit` | 替换指定 block 全部内容（改标题） | 需先通过 `docs:get --mode blocks` 获取 blockId 和 hash |
| `--target/--replace` | 按原文匹配替换（清空表格行内容） | target 须与文档 Markdown 精确匹配；每次编辑后 hash 更新需重新获取 |
