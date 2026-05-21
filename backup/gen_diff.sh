#!/bin/bash
set -e
cd /home/node/.openclaw/workspace

diff_date="2026-05-22"
prev_date="2026-05-21"
out="backup/2026-05-22/diff.md"

{
echo "# 每日备份差异报告 - ${diff_date}"
echo ""
echo "生成时间: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "对比基准: backup/core/ (${prev_date}) vs backup/snapshot/ (今日)"
echo ""
echo "---"
echo ""
} > "$out"

for f in MEMORY.md SOUL.md AGENTS.md ROUTING.md TOOLS.md USER.md IDENTITY.md HEARTBEAT.md; do
  curr="backup/snapshot/$f"
  prev="backup/core/$f"

  if [ -f "$curr" ] && [ -f "$prev" ]; then
    if diff "$prev" "$curr" > /dev/null 2>&1; then
      echo "**${f}**: 无变化" >> "$out"
    else
      size_prev=$(wc -c < "$prev")
      size_curr=$(wc -c < "$curr")
      lines_changed=$(diff "$prev" "$curr" | grep -c '^[<>]' || true)
      echo "" >> "$out"
      echo "**${f}**: 有变更 (大小: ${size_prev}B -> ${size_curr}B, ${lines_changed} 行差异)" >> "$out"
      echo "" >> "$out"
      echo '```diff' >> "$out"
      diff -u "$prev" "$curr" | head -80 >> "$out"
      echo '```' >> "$out"
      echo "" >> "$out"
    fi
  elif [ -f "$curr" ] && [ ! -f "$prev" ]; then
    sz=$(wc -c < "$curr")
    echo "**${f}**: 新增文件 (${sz}B)" >> "$out"
  fi
done

echo "" >> "$out"
echo "---" >> "$out"
echo "" >> "$out"
echo "### memory/ 目录" >> "$out"
echo "" >> "$out"
total_mem=$(find memory/ -name "*.md" 2>/dev/null | wc -l)
echo "总计 ${total_mem} 个文件" >> "$out"
echo "最近修改:" >> "$out"
ls -lt memory/*.md 2>/dev/null | head -3 | while read -r line; do
  fname=$(echo "$line" | awk '{print $NF}')
  fsize=$(wc -c < "$fname")
  fdate=$(stat -c %y "$fname" | cut -d' ' -f1)
  echo "- ${fname} (${fsize}B, ${fdate})" >> "$out"
done

echo "" >> "$out"
echo "### agents/ 目录" >> "$out"
echo "" >> "$out"
find agents/ -maxdepth 2 -type f | sort | while read -r fpath; do
  fsize=$(wc -c < "$fpath")
  echo "- ${fpath} (${fsize}B)" >> "$out"
done

# Copy to snapshot and backup root
cp "$out" backup/snapshot/diff.md
cp "$out" backup/diff.md

echo "=== DIFF GENERATED ==="
cat "$out"
