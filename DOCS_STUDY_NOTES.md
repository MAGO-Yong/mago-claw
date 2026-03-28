# 产品文档结构学习笔记

**学习来源**：Langfuse官方文档 (langfuse.com/docs/evaluation)

## Langfuse文档结构分析

### 第一层：入口 - Overview Page
```
标题：Evaluation of LLM Applications

核心价值主张（1-2句）：
- Evals give you a repeatable check of your LLM application's behavior
- You replace guesswork with data
- Help catch regressions before shipping

导向：
- "新手？先看Core Concepts"
- 快速链接到关键操作路径
```

**特点**：
- ✅ 简洁明确的价值陈述
- ✅ 直接指向新手学习路径
- ✅ 提供多条操作路径（各取所需）

---

### 第二层：概念 - Core Concepts Page

#### 2.1 首先建立思维模型：The Evaluation Loop

**用实例讲解流程**：
```
例子：客服聊天机器人

1. 修改prompt（使语气不正式）
   ↓
2. 离线评估：在测试数据集上运行实验 (Offline)
   ↓
3. 查看评分和输出
   ↓
4. 继续优化prompt
   ↓
5. 满意后部署
   ↓
6. 监控生产环境 (Online)
   ↓
7. 发现法语查询问题
   ↓
8. 添加法语案例到数据集
   ↓
9. 继续迭代
```

**特点**：
- ✅ 用完整场景而非抽象概念
- ✅ 展示离线→上线→反馈→迭代的完整循环
- ✅ 说明为什么需要这样做

#### 2.2 然后是方法 - Evaluation Methods

**用表格对比，而非长文章**：
| 方法 | 是什么 | 何时用 |
|------|------|--------|
| LLM-as-Judge | 用LLM评估 | 主观判断（语气、准确性等） |
| UI手工评分 | 手动添加评分 | 快速spot check |
| 注释队列 | 人工审核工作流 | 标注ground truth |
| API/SDK评分 | 程序化添加评分 | 自定义评估管道 |

**特点**：
- ✅ 一目了然的对比
- ✅ "何时用"帮助快速决策

#### 2.3 最后是对象模型 - Experiments

**先定义关键对象**：
| 对象 | 定义 |
|------|------|
| Dataset | 测试用例的集合 |
| Dataset Item | 单个测试用例 |
| Task | 要测试的应用代码 |
| Evaluation Method | 评分函数 |
| Score | 评估输出 |
| Experiment Run | 一次完整执行 |

**然后解释它们如何协作**：
```
Dataset → Dataset Items → Task Function → Outputs → 
Evaluation Method → Scores → Compare Results
```

**特点**：
- ✅ 先定义术语
- ✅ 再解释关系
- ✅ 包含流程图视觉化
- ✅ 说明两种运行方式（UI vs SDK）

---

### 第三层：操作 - How-To Guides

**单个明确的任务**：
- Create a Dataset
- Run an Experiment
- Set up LLM-as-a-Judge
- 等等

**特点**：
- ✅ 每个页面一个具体任务
- ✅ 有明确的开始和结束
- ✅ 包含代码示例

---

## 关键学到的结构模式

### 信息层次
```
Level 1: Overview
  ↓ 价值 + 引导
Level 2: Concepts
  ↓ 思维模型 + 方法对比 + 对象定义
Level 3: How-To Guides
  ↓ 具体操作步骤
```

### 表现形式优先级
1. **实例/故事** > 抽象定义
2. **表格对比** > 长段文字
3. **流程图** > 顺序描述
4. **术语定义表** > 段落解释

### 从新手角度的逻辑
```
我是谁？ (Overview - 你在哪儿)
  ↓
我要干什么？ (Concepts - 思维模型)
  ↓
有什么方法？ (Methods - 对比选择)
  ↓
怎么操作？ (How-To - 具体步骤)
```

---

## 对你项目的启示

基于Langfuse的学习，你的AI应用评估文档应该：

1. **不要一开始就讲名词**
   - ❌ 错误：先讲"链路"、"SPAN"、"评估器"
   - ✅ 正确：先讲"为什么需要评估"和"大致流程"

2. **用完整的使用场景而非编造案例**
   - ✅ 使用真实的任务流程（你之前给的配置截图）
   - ✅ 展示真实的数据（593条链路、9984条实验结果）

3. **对比表格很强大**
   - ✅ 在线 vs 离线模式
   - ✅ LLM评估器 vs HTTP评估器
   - ✅ 不同场景的方法选择

4. **先定义对象模型，再解释如何协作**
   - ✅ 分别定义：评估器、评估任务、实验
   - ✅ 然后用流程图展示关系

5. **把"两种模式"明确作为核心概念讲解**
   - ✅ 在线链路模式（实时监控）
   - ✅ 离线数据模式（AB测试/验证）
   - ✅ 说明各自的优缺点和适用场景

---

## 下一步建议

等你学习完COZE和其他文档后，我们可以：

1. 先给出**结构框架**（有具体的目录和每部分的内容概要）
2. 基于**你的真实数据**补充内容
3. 用**表格和流程图**替代长文章
4. **不编造任何案例**，只用真实的配置流程

---

**我已经准备好等待，而不是盲目输出了。** 🙏
