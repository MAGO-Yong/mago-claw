#!/bin/bash
# 每日工作区备份脚本
# 运行时间：每日 02:00 Asia/Shanghai

WORKSPACE="/home/node/.openclaw/workspace"
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="$WORKSPACE/backup/$DATE"

echo "[backup] 开始备份 $DATE"

# 1. 创建当日备份目录
mkdir -p "$BACKUP_DIR/snapshot"

# 2. 快照核心文件
cp "$WORKSPACE/MEMORY.md" "$BACKUP_DIR/snapshot/" 2>/dev/null
cp "$WORKSPACE/SOUL.md" "$BACKUP_DIR/snapshot/" 2>/dev/null
cp "$WORKSPACE/AGENTS.md" "$BACKUP_DIR/snapshot/" 2>/dev/null
cp "$WORKSPACE/ROUTING.md" "$BACKUP_DIR/snapshot/" 2>/dev/null
cp -r "$WORKSPACE/memory/" "$BACKUP_DIR/snapshot/memory/" 2>/dev/null
cp -r "$WORKSPACE/agents/" "$BACKUP_DIR/snapshot/agents/" 2>/dev/null

# 3. 生成 diff（对比昨日）
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)
YESTERDAY_DIR="$WORKSPACE/backup/$YESTERDAY/snapshot"

if [ -d "$YESTERDAY_DIR" ]; then
    diff -rq --exclude="*.tmp" "$YESTERDAY_DIR" "$BACKUP_DIR/snapshot" > "$BACKUP_DIR/diff.md" 2>&1
    echo "[backup] diff 生成完成"
else
    echo "首次备份，无历史对比" > "$BACKUP_DIR/diff.md"
fi

# 4. 更新 core/ 目录（同步最新核心文件）
cp "$WORKSPACE/MEMORY.md" "$WORKSPACE/core/" 2>/dev/null
cp "$WORKSPACE/SOUL.md" "$WORKSPACE/core/" 2>/dev/null
cp "$WORKSPACE/AGENTS.md" "$WORKSPACE/core/" 2>/dev/null
cp "$WORKSPACE/ROUTING.md" "$WORKSPACE/core/" 2>/dev/null
cp "$WORKSPACE/TOOLS.md" "$WORKSPACE/core/" 2>/dev/null
cp "$WORKSPACE/USER.md" "$WORKSPACE/core/" 2>/dev/null

# 5. git commit & push
cd "$WORKSPACE"
git add -A
git commit -m "auto backup: $DATE" --allow-empty
git push origin main 2>&1

echo "[backup] 备份完成 $DATE"
