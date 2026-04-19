#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://xray-ai.devops.xiaohongshu.com/open/skill/alarm/analysis/node"

# path 格式: xhs.<prdLine>.<bizLine>.<app>.<service>
LEVEL_NAMES = ["prdLine", "bizLine", "app", "service"]


def fetch(service: str) -> dict:
    url = f"{API_URL}?{urllib.parse.urlencode({'service': service})}"
    req = urllib.request.Request(
        url,
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"请求失败: HTTP {e.code} {e.reason}\n{body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"请求失败: {e.reason}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"响应非 JSON: {raw[:200]}", file=sys.stderr)
        sys.exit(1)


def parse_node(node: dict) -> dict:
    path: str = node.get("path") or ""
    if not path:
        print(f"节点 path 字段为空: {node}", file=sys.stderr)
        sys.exit(1)

    parts_without_root = path.split(".")[1:]
    if not parts_without_root:
        print(f"节点 path 格式异常（无法解析层级）: {path!r}", file=sys.stderr)
        sys.exit(1)

    full_path = ".".join(parts_without_root)
    levels: dict = {}
    for i, name in enumerate(LEVEL_NAMES):
        levels[name] = parts_without_root[i] if i < len(parts_without_root) else None

    return {
        "name": node.get("name"),
        "full_path": full_path,
        **levels,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "查询 Xray 服务树节点信息，解析节点的完整服务树路径及各层级归属。\n"
            "服务树层级：prdLine（产品线）> bizLine（业务线）> app > service"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  %(prog)s --service xrayaiagent-service-diagnosis\n"
            "  %(prog)s --service xrayaiagent\n"
            "\n"
            "输出字段：name / full_path / prdLine / bizLine / app / service"
        ),
    )
    parser.add_argument(
        "--service",
        metavar="NAME",
        required=True,
        help="服务或 app 名称（如 xrayaiagent-service-diagnosis）",
    )
    args = parser.parse_args()

    resp = fetch(args.service)

    if not resp.get("success"):
        print(f"API 返回失败: {resp.get('message')}", file=sys.stderr)
        sys.exit(1)

    nodes = resp.get("data", {}).get("node") or []
    if not nodes:
        print(f"未找到服务节点: {args.service}", file=sys.stderr)
        sys.exit(1)

    result = [parse_node(n) for n in nodes]
    output = result[0] if len(result) == 1 else result
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
