#!/bin/bash
# CodeSearch CLI - 小红书内部代码搜索工具
# 基于 Zoekt 搜索引擎,支持搜索全公司所有代码仓库主分支代码

set -e

# API 配置
API_URL="http://codewiz.devops.xiaohongshu.com/v1/cs/api/search"

# 默认参数
PAGE=1
PAGE_SIZE=20
CONTEXT_LINES=2

usage() {
    cat <<EOF
CodeSearch - 小红书代码搜索工具

用法:
    $(basename "$0") <query> [OPTIONS]

参数:
    query                 搜索查询语句 (支持 Zoekt 语法)

选项:
    -p, --page           页码 (默认: 1)
    -s, --page-size      每页结果数, 1-100 (默认: 20)
    -c, --context        匹配行周围的上下文行数 (默认: 2)
    -h, --help          显示帮助信息

搜索语法示例:
    基础搜索:
        "function_name"              # 搜索关键词
        "exact phrase"               # 精确匹配短语
        sym:GitResponse              # 搜索符号(方法名/类名)

    字段过滤:
        file:"main.go"               # 按文件名搜索
        lang:python                  # 按编程语言过滤
        repo:ee/backend              # 按仓库名过滤
        content:"error handling"     # 搜索文件内容

    高级搜索:
        case:yes content:"Foo"       # 大小写敏感
        regex:foo.*bar               # 正则表达式
        lang:go -file:test           # 排除测试文件
        repo:"p1" or repo:"p2"       # 多仓库搜索

使用示例:
    $(basename "$0") "sym:GetUserInfo lang:java"
    $(basename "$0") 'content:"error" lang:go' -p 2 -s 50
    $(basename "$0") 'file:"*.proto"' -c 5
    $(basename "$0") 'regex:/def\s+\w+\s*\(/ lang:python'

EOF
    exit 0
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--page)
            PAGE="$2"
            shift 2
            ;;
        -s|--page-size)
            PAGE_SIZE="$2"
            shift 2
            ;;
        -c|--context)
            CONTEXT_LINES="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        -*)
            echo "错误: 未知选项 $1"
            echo "使用 -h 查看帮助信息"
            exit 1
            ;;
        *)
            QUERY="$1"
            shift
            ;;
    esac
done

# 检查必需参数
if [[ -z "$QUERY" ]]; then
    echo "错误: 缺少搜索查询语句"
    echo ""
    usage
fi

# 验证参数
if ! [[ "$PAGE" =~ ^[0-9]+$ ]] || [[ "$PAGE" -lt 1 ]]; then
    echo "错误: 页码必须是大于 0 的整数 (当前值: $PAGE)"
    exit 1
fi

if ! [[ "$PAGE_SIZE" =~ ^[0-9]+$ ]] || [[ "$PAGE_SIZE" -lt 1 ]] || [[ "$PAGE_SIZE" -gt 100 ]]; then
    echo "错误: 每页结果数必须是 1-100 之间的整数 (当前值: $PAGE_SIZE)"
    exit 1
fi

if ! [[ "$CONTEXT_LINES" =~ ^[0-9]+$ ]]; then
    echo "错误: 上下文行数必须是非负整数 (当前值: $CONTEXT_LINES)"
    exit 1
fi

# 构建请求 payload (使用 jq 安全构建 JSON,避免注入攻击)
PAYLOAD=$(jq -n \
    --arg query "$QUERY" \
    --argjson page "$PAGE" \
    --argjson pageSize "$PAGE_SIZE" \
    --argjson contextLines "$CONTEXT_LINES" \
    '{
        opts: {
            NumContextLines: $contextLines
        },
        q: $query,
        page: $page,
        pageSize: $pageSize
    }'
)

# 执行搜索请求
# 注意: 代理会自动添加认证信息,无需手动设置 token
response=$(curl -s -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -H "Accept: */*" \
    -d "$PAYLOAD")

# 检查响应
if [[ -z "$response" ]]; then
    echo "错误: API 返回空响应"
    exit 1
fi

# 检查 API 响应状态
success=$(echo "$response" | grep -o '"success":[a-z]*' | head -1 | sed 's/"success"://' || echo "false")
if [[ "$success" != "true" ]]; then
    error_msg=$(echo "$response" | grep -o '"msg":"[^"]*"' | sed 's/"msg":"//;s/"//' || echo "未知错误")
    echo "错误: $error_msg"
    exit 1
fi

# 提取统计信息 (从嵌套的 data 对象中提取)
total=$(echo "$response" | grep -o '"total":[0-9]*' | head -1 | sed 's/"total"://' || echo "0")
hasNext=$(echo "$response" | grep -o '"hasNext":[a-z]*' | head -1 | sed 's/"hasNext"://' || echo "false")
hasPrevious=$(echo "$response" | grep -o '"hasPrevious":[a-z]*' | head -1 | sed 's/"hasPrevious"://' || echo "false")

# 输出搜索结果摘要
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 搜索结果摘要"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "查询: $QUERY"
echo "匹配文件数: $total"
echo "当前页: $PAGE (每页 $PAGE_SIZE 条)"
echo "上一页: $hasPrevious | 下一页: $hasNext"
echo ""

# 如果没有结果,提示用户
if [[ "$total" == "0" ]]; then
    echo "未找到匹配结果"
    echo ""
    echo "提示:"
    echo "  - 尝试使用更通用的搜索词"
    echo "  - 使用 Zoekt 语法进行精确搜索"
    echo "  - 查看帮助: $(basename "$0") -h"
    exit 0
fi

# 输出文件列表和链接
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 匹配文件"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 解析并显示文件信息
echo "$response" | python3 -c "
import sys
import json

try:
    response = json.load(sys.stdin)
    # API 返回嵌套结构: {success, code, msg, data: {files, total, ...}}
    data = response.get('data', {})
    files = data.get('files', [])

    for idx, file_info in enumerate(files[:20], 1):
        repo = file_info.get('repository', 'N/A')
        file_name = file_info.get('fileName', 'N/A')
        project_id = file_info.get('projectId', '')
        line_matches = file_info.get('lineMatches', [])

        print(f'{idx}. {repo}/{file_name}')

        # 显示匹配的代码行
        if line_matches:
            for match in line_matches[:3]:  # 只显示前3个匹配
                line_num = match.get('lineNumber', 0)
                line_content = match.get('line', '').strip()
                if line_content:
                    print(f'   L{line_num}: {line_content[:100]}')

        # 生成 CodeWiz 链接
        if project_id and file_name:
            link = f'https://codewiz.devops.xiaohongshu.com/projects/{project_id}/code?treePath={file_name}&treeType=blob'
            print(f'   🔗 {link}')

        print()

except json.JSONDecodeError as e:
    print(f'JSON 解析错误: {e}', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'处理错误: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null || {
    # Python 解析失败时的降级方案
    echo "警告: 无法解析响应格式,输出原始 JSON"
    echo "$response" | head -50
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 输出完整 JSON (用于调试和进一步处理)
if [[ "${DEBUG:-}" == "1" ]]; then
    echo "完整响应 (DEBUG=1):"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
fi
