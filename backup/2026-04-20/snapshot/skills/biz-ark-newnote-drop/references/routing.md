# 原子 Skill 路由表

| Step | 原子 Skill | 调用参数说明 | 文档 |
|------|-----------|------------|------|
| Step 1 | metrics-compare | offset=7d, group_by=stage | [查看](https://xray.devops.xiaohongshu.com/skills/metrics-compare) |
| Step 2 | metrics-breakdown | group_by=channel, top_n=10 | [查看](https://xray.devops.xiaohongshu.com/skills/metrics-breakdown) |
| Step 3 | metrics-multi-compare | pql_list=[召回多队列, 粗排多队列], group_by=queue | [查看](https://xray.devops.xiaohongshu.com/skills/metrics-multi-compare) |
| Step 4 | metrics-threshold | threshold=0.01, direction=below, group_by=zone | [查看](https://xray.devops.xiaohongshu.com/skills/metrics-threshold) |
| Step 5 | metrics-compare | filter=notecreate.*, group_by=name | [查看](https://xray.devops.xiaohongshu.com/skills/metrics-compare) |
| Step 6 | metrics-multi-compare | pql_list=[粗排打分, 精排打分], group_by=model | [查看](https://xray.devops.xiaohongshu.com/skills/metrics-multi-compare) |
| Step 7 | metrics-compare | offset=7d | [查看](https://xray.devops.xiaohongshu.com/skills/metrics-compare) |

## 执行关系说明

- **Step 1 与 Step 2-7**：全部并行启动，互不等待
- **Step 2 → Step 3 → Step 4 → Step 5 → Step 6 → Step 7**：串行执行
- **汇总节点**：等待 Step 1 和 Step 7 全部完成后，输出综合结论
