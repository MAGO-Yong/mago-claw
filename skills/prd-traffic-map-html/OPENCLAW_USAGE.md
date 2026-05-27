# OpenClaw Usage

This skill is designed to make OpenClaw continue from the existing World Cup V1 traffic-map baseline instead of drawing from zero.

## What This Skill Can Do

If OpenClaw supports file/artifact creation, it can produce a standalone interactive HTML topology page.

If OpenClaw cannot create files, it should still output one of these visual artifacts:

1. complete standalone HTML code;
2. Mermaid topology plus node evidence table;
3. structured JSON spec for later rendering.

The agent should never answer only with prose when the user asks for a map or visualization.

## Recommended Prompt

```text
使用 prd-traffic-map-html Skill。请基于 Skill 里的 World Cup V1 baseline
继续优化世界杯中心页流量地图，不要从 0-1 重画。
优先输出可直接打开的 standalone HTML 交互页面；如果不能落文件，
就输出完整 HTML；如果 HTML 不可行，再输出 Mermaid + 节点证据表。
每次修改后说明节点数、边数、层级变化、是否有断边/缺失详情/重叠风险。
```

## Runtime Behavior

For World Cup center-page work, OpenClaw should first read:

```text
examples/worldcup-center-map-spec.md
templates/worldcup-center-flow-map.html
```

Then it should patch the V1 baseline according to the user's new feedback.

## Output Acceptance Checklist

- Starts from the V1 baseline unless the user explicitly says to discard it.
- Produces an actual visual artifact: HTML, Mermaid, or JSON spec.
- Keeps same-level nodes on one row.
- Keeps evidence/details for every node.
- Does not re-add removed top-level `Home Feed` unless new evidence requires it.
- Does not turn interaction states into topology nodes by default.
- Reports node count, edge count, broken edge status, missing detail status, and overlap risk.

## If OpenClaw Cannot Render HTML

Ask it to output this fallback:

```text
请输出 Mermaid flowchart TD，并附上 nodes/edges/details JSON。
不要只描述地图。
```
