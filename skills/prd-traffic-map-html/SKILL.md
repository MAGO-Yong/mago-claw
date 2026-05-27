---
name: prd-traffic-map-html
version: 2.0.0
description: Use when the user gives a PRD/REDoc document or an existing traffic-map HTML and wants Codex to extract, draw, review, or iteratively edit a user-visible traffic/topology map with evidence drawers, screenshots, and PRD-backed node hierarchy.
---

# PRD Traffic Map HTML

## Role

Turn product PRDs into an editable traffic map skeleton, usually as a standalone HTML topology graph. The map should help PMs, R&D, QA, and stability owners discuss user-visible flow, key modules, landing pages, and future QPS / success-rate observation points.

This skill is for product traffic-map collaboration, not service dependency topology. Prefer user-visible pages, modules, and landing surfaces over internal implementation states.

This package has two parts:

1. **Collaboration protocol**: rules for how to read a PRD, choose nodes, arrange hierarchy, use evidence drawers, respond to user corrections, and validate the topology.
2. **World Cup V1 baseline**: the current `26 世界杯中心页` topology, source PRD conclusions, evidence image links, and HTML template. Anyone continuing that map should start from this V1 baseline and optimize it incrementally, not redraw from zero.

For a request that mentions `世界杯`, `26 世界杯中心页`, `worldcup-center-flow-map.html`, or the REDoc shortcut `a9150c0b65f863943f937552f2db1657`, load the baseline spec and HTML first:

```text
examples/worldcup-center-map-spec.md
templates/worldcup-center-flow-map.html
```

Then apply user feedback as a patch on top of the baseline. Only start from zero when the user explicitly asks to discard the baseline.

## When To Use

Use this skill when the user asks things like:

- "给这个 PRD 画个流量地图 / 流程图 / 拓扑图"
- "基于产品文档生成 HTML 流程图"
- "这个地图层级不对，帮我继续改"
- "把节点对应的截图和产品描述放进去"
- "我要和别人一起协作绘制这个地图"

If a REDoc link is provided, also use the `redoc` / `hi-docs` skill to fetch the document. If an existing local HTML is provided or visible in the in-app browser, edit that file directly.

If the task is about continuing the World Cup center-page map, first read `examples/worldcup-center-map-spec.md` and reuse `templates/worldcup-center-flow-map.html` or the user's current working copy. Do not regenerate a blank topology from the PRD.

## Package Artifacts

The skill package must be treated as a reusable baseline bundle:

```text
SKILL.md
  Collaboration protocol, drawing rules, validation rules, and iteration behavior.

examples/worldcup-center-map-spec.md
  World Cup V1 baseline: PRD source, product conclusions, node hierarchy, modeling decisions,
  preserved user corrections, evidence images, and latest validation facts.

templates/worldcup-center-flow-map.html
  World Cup V1 baseline HTML: current topology, styles, drawer interaction, evidence details,
  and edge definitions.
```

When handed to another collaborator, this means:

- use `SKILL.md` to understand how to modify and review the map;
- use the example spec to understand why the current nodes and hierarchy exist;
- use the HTML template as the starting graph;
- preserve prior decisions unless new PRD/user evidence supersedes them;
- document any new correction back into the spec when it should affect future collaborators.

## OpenClaw Runtime Contract

Installing this skill into OpenClaw gives the agent the method, baseline, and template. It does not by itself guarantee that OpenClaw can write local files, open a browser, or render HTML. To make the result reliably visual, every OpenClaw run must follow this output contract.

### Install-Time Behavior (MANDATORY)

Immediately after installing this skill, the agent MUST:

1. Copy the baseline HTML to the canvas documents directory:
   ```bash
   mkdir -p ~/.openclaw/canvas/documents
   cp <skill_dir>/templates/worldcup-center-flow-map.html ~/.openclaw/canvas/documents/worldcup-center-flow-map.html
   ```
2. Start a local HTTP server to serve the canvas documents directory (if not already running):
   ```bash
   python3 -m http.server 8765 --directory ~/.openclaw/canvas/documents &
   sleep 1
   ```
   Note: This environment runs a local HTTP server on port 8765 by default. If `localhost:3000` or similar is refused, always fall back to starting `python3 -m http.server 8765`. Do NOT conclude "no HTTP service available" without first trying to start one.
3. Open the HTML in the browser and take a full-page screenshot:
   ```
   browser open http://127.0.0.1:8765/worldcup-center-flow-map.html
   browser screenshot fullPage=true
   ```
4. Show the screenshot to the user and briefly describe the map structure (node count, layer count, color legend).
5. Then invite the user to continue editing.

Do NOT skip straight to "here is an embed" without a real screenshot. The user must see the actual rendered map before any further interaction.

### Required Output Priority

When the user asks to draw, optimize, or continue the map, produce the highest-capability artifact available:

1. **Standalone interactive HTML file**  
   Preferred. Use `templates/worldcup-center-flow-map.html` as the V1 starting point for World Cup work. Save a complete `.html` artifact if the runtime supports files/artifacts.

2. **Complete standalone HTML code block**  
   If OpenClaw cannot write a file but can answer in chat, output the full HTML document in one fenced `html` block. It must be directly copyable and runnable in a browser.

3. **Mermaid topology plus node evidence table**  
   If HTML is not feasible, output a Mermaid `flowchart TD` or `flowchart LR` diagram, plus a compact table of node evidence and screenshot links.

4. **Structured JSON spec**  
   Last fallback. Output `{ nodes, edges, details, layoutRules }` so another agent can render it later.

Do not stop at prose. A valid run must produce at least one renderable or machine-renderable artifact.

### OpenClaw Minimum Capability Expectations

For best results, OpenClaw should allow at least one of:

- creating or editing a text artifact/file;
- returning a long code block without truncation;
- rendering Mermaid;
- attaching an HTML artifact.

If none are available, the skill should explicitly say the runtime cannot draw directly and then output the structured JSON spec.

### HTTP Rendering — Always Try Before Giving Up

This environment does NOT have a persistent HTTP server on `localhost:3000`. The correct approach every time:

```bash
# 1. Check if port 8765 is already listening
python3 -c "import socket; s=socket.socket(); s.connect(('127.0.0.1', 8765))" 2>/dev/null && echo alive || echo dead
# 2. If dead, start it
python3 -m http.server 8765 --directory ~/.openclaw/canvas/documents &
sleep 1
```

Do NOT tell the user "no HTTP server" without running the above. Do NOT try `localhost:3000` (it will always fail in this environment).

### Prompt To Use In OpenClaw

Use this wording when invoking the skill in OpenClaw:

```text
使用 prd-traffic-map-html Skill。请基于 Skill 里的 World Cup V1 baseline
继续优化世界杯中心页流量地图，不要从 0-1 重画。
优先输出可直接打开的 standalone HTML 交互页面；如果不能落文件，
就输出完整 HTML；如果 HTML 不可行，再输出 Mermaid + 节点证据表。
每次修改后说明节点数、边数、层级变化、是否有断边/缺失详情/重叠风险。
```

### Artifact Acceptance Criteria

The produced visualization is acceptable only if:

- it contains the current V1 baseline nodes unless the user explicitly removes them;
- it applies the user's requested edit incrementally;
- same-level nodes are visually on one row;
- every node has evidence text;
- every edge endpoint exists;
- HTML output includes CSS, nodes, edges, drawer/details data, and JavaScript in one document;
- Mermaid output includes all meaningful nodes and edges, not only a summary;
- it reports any runtime limitation clearly.

## Source Discipline

1. Read the PRD before drawing. Do not infer core routes only from a screenshot.
2. Treat PRD statements, architecture images, and module tables as primary evidence.
3. Distinguish:
   - true traffic entry points;
   - center-page modules;
   - module landing pages;
   - interaction states;
   - backend/material/config concepts.
4. Only draw user-visible pages, modules, or landing functions as nodes by default.
5. Put interaction states in the evidence drawer unless the user explicitly wants them as nodes.
6. If a node is uncertain, mark the drawer text as "待确认" instead of presenting it as fact.

## REDoc Fetch Pattern

For internal REDoc links, use `hi-docs`. On this user's machine, prefer the Node 24 wrapper because normal frontend work may pin the shell to Node 18:

```bash
/Users/mahengyang/.codex/bin/hi-node24 docs:get --shortcut-id <shortcutId> --mode common
```

If the wrapper does not exist, check `hi docs --help` and use the current recommended `hi` command. Do not change the global Node version just to read docs.

Save derived artifacts under:

```text
~/Documents/Codex CLI/CC-generate/
```

## Drawing Workflow

1. **Extract entry routes**
   - Search for words such as `入口`, `Tab`, `中心页`, `能不能看见`, `feed`, `push`, `NNS`, `承接`, `访问`.
   - Do not assume Home Feed is an entry just because the PRD mentions feed. Confirm whether it is an initial entrance, a distribution/recall channel, or a module inside the center page.
   - When evidence is mixed, prefer the PRD section that explicitly defines entry capability over later mentions of recall, push, feed, or internal modules.

2. **Extract main venue structure**
   - Identify the center page / main venue node.
   - Separate stable peer modules from phase-specific modules.
   - If the PRD says architecture is basically consistent across phases and only a top region changes, draw the stable modules as peers and only branch the changing top region.
   - Do not create an abstract "通用固定能力区" if the user-visible modules can be shown directly as peer nodes. Abstract grouping is allowed only when it reduces clutter without hiding real product surfaces.

3. **Extract module drilldowns**
   - For each user-visible module, decide whether it has one more landing level.
   - Examples: content module -> detail page / search result / circle page / publisher; live card -> live room / schedule / replay / reservation button.
   - If several peer modules all have landing pages, draw a second peer row under them instead of showing only one module's landing page.

4. **Avoid over-modeling**
   - Do not draw pure state transitions such as "authorization success", "closed/skipped", "selected", "not started" unless they are product surfaces the user wants to monitor.
   - Fold material types such as `official live`, `ops live`, `ops note` into drawer descriptions when they are not independent visible entry modules.
   - If the node label sounds like an action/state rather than a visible product surface, challenge it before drawing. Examples: `Push 授权`, `中断路径`, `运营直播`, `发布链路`.

5. **Build or edit HTML**
   - Use the existing topology HTML if present.
   - Keep same-level nodes on one row; do not wrap a single logical layer into multiple rows.
   - For each node, include `QPS -` and `成功率 -` placeholders.
   - Add a right-side evidence drawer shown on hover, containing PRD description and screenshot.
   - Do not add a left metrics panel unless the user asks for it.

6. **Iterate with user corrections**
   - Treat user screenshots and annotations as layout/product feedback.
   - When the user says "这几个是一个层级", put them on the same row.
   - When the user says "可以下钻一层", add the next landing row.
   - When the user says "这不是入口/不是节点", remove or fold it into drawer evidence.
   - When the user points at two nodes sticking together, fix both the concrete overlap and the validation heuristic that missed it.
   - When the user questions "这个截图对吗", re-read the PRD section and downgrade uncertain evidence instead of defending the current drawing.

7. **Validate**
   - Run a static script that checks:
     - every node has detail evidence;
     - every edge points to an existing node;
     - no extra detail objects are left behind;
     - approximate card boxes do not overlap;
     - requested same-level rows share the same `top`.
   - If Browser can open or reload the local file safely, verify visually. If `file://` access is blocked by browser policy, say so and rely on static validation plus user refresh.

## HTML Conventions

- Use one standalone HTML file for easy sharing.
- Nodes are absolute-positioned cards on a grid background.
- Edges are generated from a JS `edges` array.
- Drawer evidence is a JS `details` object keyed by `data-id`.
- The drawer appears only on hover unless the user asks for click persistence.
- Use restrained colors:
  - blue: app / entry / main venue;
  - orange: preheat / appointment / fission path;
  - green: formal live / content consumption path;
  - purple: configurable fixed modules / king slots.
- Avoid nested cards, large decorative sections, and explanatory in-app instructions.

## User-Learned Arrangement Rules

These rules came from real collaboration on the World Cup center-page map. Apply them proactively in future PRD traffic maps.

### Node Selection

- Draw the map around **user-visible functions and pages**, not every interaction action.
- Keep internal states and interaction requirements in drawer evidence unless the user asks to monitor them as separate nodes.
- If a concept is only a material/config type inside a visible module, do not draw it as a peer node. Put it in the parent node drawer.
- If two labels refer to the same product surface, merge them. For example, `世界杯中心页` and `世界杯主会场` should be one node when the PRD uses them as the same venue.

### Entry And Recall

- Initial entry must be backed by an explicit PRD entry section.
- Do not promote downstream recall channels to initial entry. `Home Feed`, `Push`, `NNS`, `全局底 Bar`, or `Mainfeed 推流` may be recall/承接/触达 paths rather than first-level entry.
- If the user asks whether the start is correct, immediately re-check the PRD source and adjust the map instead of relying on the current drawing.

### Hierarchy

- Same business layer means same visual row. Do not wrap same-level nodes into a 2x2 block or mix one next-level node into the parent row.
- A group can branch into multiple peer children. If a user says "这些都可以下钻一层", add one next row with one landing node per parent where possible.
- If a child is specifically the next step of one module, align it under that module. Example: `赛事热点 -> 搜索结果页`.
- If a child is one step deeper than a sibling, move it to the next row. Example: `邀好友预约 -> 分享海报`.

### Phase Modeling

- If a PRD says only a certain area changes between preheat and formal states, isolate the phase split to that area.
- Do not duplicate stable modules under both preheat and formal sections unless they truly differ by phase.
- Avoid abstract "通用固定能力" containers when stable modules can be peers under the venue.

### Layout

- Lay out from top to bottom for user journey, and left to right for peer modules.
- Same-level peer nodes must be in one row, even if the canvas needs to be wider.
- Reserve vertical space using the real rendered card height, including `依据` text, not only the base card height.
- After adding drawer refs or longer labels, rerun overlap validation with an approximate card height of at least 126px.
- If the right drawer covers the graph, that is acceptable for hover inspection, but the underlying topology should remain readable when no node is hovered.

### Evidence Drawer

- Use the drawer for screenshots and PRD text so the graph stays clean.
- Show the drawer only while hovering a node unless the user asks for persistent selection.
- Each drawer should explain why the node exists and what it drills into. It should also mention if the node is a modeling decision rather than an explicit PRD title.
- The drawer should carry uncertainties and source distinctions, for example "PRD describes this as material type, so it is folded into the live-card node."

### Validation

- Validate both graph structure and collaboration intent:
  - every node has a detail entry;
  - every edge endpoint exists;
  - there are no stale details for removed nodes;
  - no cards overlap using realistic card height;
  - each user-declared peer group has a single row;
  - each user-declared child group is one row below the parent group;
  - removed concepts such as `Home Feed` are actually gone from nodes, details, and edges.
- Browser visual verification is preferred, but if local `file://` browsing is blocked by policy, clearly report that and rely on static validation plus user refresh.

## Validation Script Pattern

Use a script like this after each meaningful edit. Adjust the `target` path and expected same-level groups.

```bash
node - <<'NODE'
const fs = require('fs');
const target = '/absolute/path/to/traffic-map.html';
const html = fs.readFileSync(target, 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');
new Function(scripts);
const nodes = [...html.matchAll(/<section class="node[^\"]*" data-id="([^\"]+)" style="left: ([0-9]+)px; top: ([0-9]+)px;"/g)]
  .map(m => ({ id: m[1], x: +m[2], y: +m[3] }));
const detailKeys = [...html.matchAll(/^\s{6}(["']?)([a-zA-Z0-9-]+)\1: \{/gm)].map(m => m[2]);
const edgeText = html.match(/const edges = \[([\s\S]*?)\];/)[1];
const edges = [...edgeText.matchAll(/\["([^"]+)", "([^"]+)", "([^"]*)"\]/g)].map(m => [m[1], m[2], m[3]]);
const width = id => (['center', 'app', 'preheat-hero', 'formal-hero'].includes(id) ? 184 : (['stage-area', 'content-floor', 'live-card'].includes(id) ? 164 : 150));
const approxHeight = 126;
const overlaps = [];
for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
  const a = nodes[i], b = nodes[j], aw = width(a.id), bw = width(b.id);
  if (!(a.x + aw < b.x || b.x + bw < a.x || a.y + approxHeight < b.y || b.y + approxHeight < a.y)) overlaps.push([a.id, b.id]);
}
const missingEdgeNodes = [...new Set(edges.flatMap(([a, b]) => [a, b]).filter(id => !nodes.some(n => n.id === id)))];
console.log(JSON.stringify({
  nodes: nodes.length,
  edges: edges.length,
  missingDetails: nodes.map(n => n.id).filter(id => !detailKeys.includes(id)),
  extraDetails: detailKeys.filter(id => !nodes.some(n => n.id === id)),
  overlaps,
  missingEdgeNodes
}, null, 2));
NODE
```

## World Cup Center Page Example

The current example is stored in:

```text
examples/worldcup-center-map-spec.md
templates/worldcup-center-flow-map.html
```

Use it as a concrete reference for continuing the `26 世界杯中心页` map. Do not blindly reuse its content for unrelated PRDs.

Key conclusion from the PRD:

- Initial entry is `用户进入小红书 App -> 世界杯 Tab -> 世界杯中心页/主会场`.
- `Home Feed` should not be drawn as a parallel initial entry for this PRD. In the source document, feed appears as center-page/internal distribution or appointment success recall, not as the top-level entrance.
- The center page architecture is mostly stable across preheat and formal periods; the top phase region changes.
- Stable peer modules include activity backpack, my team, page share, 4 king slots, and dynamic content floor.
- The content floor currently drills one level: `比赛看点 -> 笔记详情页`, `大家都在发 -> 发布模板/发布器`, `热门球迷圈 -> 圈子详情/聚合页`, `赛事热点 -> 搜索结果页`.

## Final Response Pattern

When finishing an edit, answer with:

- the changed local HTML path;
- the product-level change in one or two sentences;
- validation result: node count, edge count, missing details, broken edges, overlap status;
- whether browser visual verification was completed or blocked.
