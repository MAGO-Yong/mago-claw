#!/bin/bash
# Sync skills from SealWorkspace to Claude Code skill directories via symlinks.
#
# Usage:
#   sync.sh [SOURCE_DIR]
#
# SOURCE_DIR defaults to ~/SealWorkspace/$USER/skills
# Destinations: ~/.codewiz/skills and ~/.claude/skills
#
# Skips entries that are real directories (non-symlink) in the destination.

SRC="${1:-$HOME/SealWorkspace/$USER/skills}"

if [ ! -d "$SRC" ]; then
    echo "错误：源目录不存在：$SRC"
    echo "用法：sync.sh [SOURCE_DIR]"
    exit 1
fi

DESTINATIONS=("$HOME/.codewiz/skills" "$HOME/.claude/skills")

total_created=0
total_skipped=0
skipped_names=()

for DST in "${DESTINATIONS[@]}"; do
    [ ! -d "$DST" ] && mkdir -p "$DST"
    echo "→ 同步到 $DST"
    for skill_dir in "$SRC"/*/; do
        [ ! -d "$skill_dir" ] && continue
        name=$(basename "$skill_dir")
        target="$DST/$name"

        if [ -d "$target" ] && [ ! -L "$target" ]; then
            already_noted=0
            for s in "${skipped_names[@]}"; do [[ "$s" == "$name" ]] && already_noted=1; done
            [[ $already_noted -eq 0 ]] && skipped_names+=("$name")
            total_skipped=$((total_skipped + 1))
            continue
        fi

        [ -L "$target" ] && rm "$target"
        ln -s "$skill_dir" "$target"
        total_created=$((total_created + 1))
    done
done

echo ""
echo "完成。共创建 $total_created 个软链接，源目录：$SRC"

if [ ${#skipped_names[@]} -gt 0 ]; then
    echo ""
    echo "跳过的（目标已是真实目录，共 ${#skipped_names[@]} 个）："
    for n in "${skipped_names[@]}"; do
        echo "  - $n"
    done
fi
