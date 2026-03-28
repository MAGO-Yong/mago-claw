#!/bin/bash
# 每周成长报告生成脚本
# 运行时间：每周日 20:00 Asia/Shanghai

WORKSPACE="/home/node/.openclaw/workspace"
WEEK=$(date +%Y-W%V)
REPORT_FILE="$WORKSPACE/memory/weekly/$WEEK-growth-report.md"

echo "[weekly] 开始生成成长报告 $WEEK"

# 收集本周 memory 日记文件
WEEK_START=$(date -d "last monday" +%Y-%m-%d 2>/dev/null || date -v-mon +%Y-%m-%d)
echo "本周起始：$WEEK_START"

# 列出本周修改的记忆文件
RECENT_MEMORIES=$(find "$WORKSPACE/memory" -name "*.md" -newer "$WORKSPACE/memory/$WEEK_START.md" 2>/dev/null | head -20)

cat > "$REPORT_FILE" << EOF
# 成长报告 $WEEK

> 生成时间：$(date '+%Y-%m-%d %H:%M')
> 覆盖范围：$WEEK_START 至 $(date +%Y-%m-%d)

## 本周活跃记忆文件
$RECENT_MEMORIES

## 待 Agent 填写
<!-- 以下内容由 Agent 在下次会话时基于本周记忆补全 -->

### 本周重要事件


### 新增执行规则/偏好


### 错误与纠正


### 核心洞察


### 下周待跟进

EOF

echo "[weekly] 报告文件已生成：$REPORT_FILE"

# git push
cd "$WORKSPACE"
git add -A
git commit -m "weekly report: $WEEK"
git push origin main 2>&1

echo "[weekly] 成长报告推送完成"
