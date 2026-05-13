# XRay AI 评估前端样式升级 — 交接文档（精简版）

> 2026-05-13 21:00 (Asia/Shanghai)

---

## 一、背景：我们怎么识别问题的

1. **访问真实页面截图**：`https://xray.devops.xiaohongshu.com/aiobservation/aievaluation?projectId=cmht3lmqy0001vj07an15cq8n&agentId=observability`
   - 探索了全部 5 个 TAB（数据集/自动评估/评估实验/评估器/LLM配置）
   - 点进各列表详情、打开创建抽屉、编辑抽屉、数据项查看抽屉，逐一截图

2. **对照 NEX 设计**：`https://nex.devops.xiaohongshu.com/workspaces/workspace-mxujpzdz`
   - NEX 是公司内部新设计语言标准（Linear/Vercel 极简风格）
   - XRay AI 评估页面是旧风格，对比鲜明

3. **结论**：XRay AI 评估模块整体视觉风格偏旧，表格密集、色彩杂乱、层级不清晰，需要对标 NEX 风格升级

---

## 二、新设计方案

先做了完整高保真 HTML Prototype，覆盖所有 TAB 的所有子页面/抽屉，用户验收后再改真实代码。

**Prototype 文件**：`http://10.40.12.135:8080/xray-ai-eval-v2.html`（可直接访问预览）

**设计语言规范（NEX 风格）**：
- 主色：`#2563eb`
- 表头：`#f9fafb` 灰底，11px 字号，letter-spacing
- 行 hover：`#f8faff` 极淡蓝
- 边框：`#f3f4f6`（比原来更淡）
- 圆角：容器 8px，按钮/输入框 6px
- 主文字：`#111827`，次文字：`#6b7280`
- 操作列靠右，搜索框和按钮同行
- 详情页用面包屑导航，不用页内返回按钮

---

## 三、代码库信息

**clone 命令**：
```bash
git clone https://oauth2:wR1kiSrhwy1jZzZhcQYr@code.devops.xiaohongshu.com/fe/tech-platform/xray.git
```

**GitLab Token**：`wR1kiSrhwy1jZzZhcQYr`

**AI 评估模块路径**：
```
packages/xray-main/src/pages/aIApplicationEvaluation/
```

**技术栈**：Vue 3 + TypeScript + `@xhs/delight`（内部 UI 库，封装 AntD 3.x）+ Stylus

**npm registry**（内网）：`http://npm.devops.xiaohongshu.com:7001/`

---

## 四、修改需求

### 核心约束
1. **只改 `<style>` 块**，`<template>` 和 `<script>` 一行不动
2. 不改任何接口调用、state 管理、路由逻辑
3. 纯 UI 逻辑（不涉及接口，如 LLM/HTTP 切换 toggle 展示）可以加
4. 分批进行：数据集 → 自动评估 → 评估实验 → 评估器 → LLM 配置

### 待改文件（按批次）

**第一批：数据集 TAB**（已完成，可跳过）
- `dataset.vue`
- `datasetDetail.vue`
- `components/NavHeader.vue`
- `components/DatasetItem.vue`
- `components/UpdateDataset.vue`

**第二批：自动评估 TAB**
- `autoEvaluation.vue` — 列表（列：名称/数据类型/执行周期/状态toggle/时间范围/创建时间/更新时间/操作）
- `autoEvaluationDetail.vue` — 详情（只有"执行历史" TAB）
- `components/CreateAutoEvaluationTask.vue` — 4步创建流程
- `components/CreateLinkBackflow.vue`、`LinkBackflow.vue`、`LinkBackflowRunRecord.vue`

**第三批：评估实验 TAB**
- `evaluationExperiment.vue`
- `autoEvaluationExperimentDetail.vue`
- `components/ExperimentDetail.vue`、`ExperimentDetailInfo.vue`、`ExperimentAnalysis.vue`
- `components/AutoEvaluationExperimentDetailInfo.vue`
- `components/CreateDatasetRelatedExperiment.vue`、`DatasetRelatedExperiment.vue`

**第四批：评估器 TAB**
- `evaluator.vue` — 卡片列表（3列网格）
- `components/CreateEvaluator.vue`
- `components/CreateCustomEvaluator.vue`

**第五批：LLM 配置 TAB**
- `llmConfig.vue`
- `components/CreateLlmConfig.vue`

**其他组件（随批次处理）**
- `components/DatasetItemDetail.vue`
- `components/AddDatasetItem.vue`
- `components/AddToDataset.vue`

### 验收方式
在本地 xray 项目根目录：
```bash
pnpm dev:main
# 访问 http://local.xiaohongshu.com:1391
# 导航到 AI 评估页面对应 TAB 验收
```
