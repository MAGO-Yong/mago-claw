#!/usr/bin/env python3
"""Convert LangChain Deep Agents translated markdown files to styled HTML."""

import re
import os
import markdown

MARKDOWN_DIR = "/home/node/.openclaw/workspace/langchain-deepagents"
HTML_DIR = "/home/node/.openclaw/workspace/langchain-deepagents-html"

os.makedirs(HTML_DIR, exist_ok=True)

# CSS template for all HTML files
CSS = """
<style>
  :root {
    --bg: #ffffff;
    --text: #1a1a2e;
    --code-bg: #1e1e2e;
    --code-text: #cdd6f4;
    --link: #2563eb;
    --border: #e2e8f0;
    --thead-bg: #f8fafc;
    --stripe-bg: #f8fafc;
    --h1-color: #0f172a;
    --h2-color: #1e293b;
    --blockquote-bg: #f0f9ff;
    --blockquote-border: #3b82f6;
    --note-bg: #fefce8;
    --note-border: #eab308;
    --warning-bg: #fef2f2;
    --warning-border: #ef4444;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f172a;
      --text: #e2e8f0;
      --code-bg: #1e1e2e;
      --code-text: #cdd6f4;
      --link: #60a5fa;
      --border: #334155;
      --thead-bg: #1e293b;
      --stripe-bg: #1e293b;
      --h1-color: #f8fafc;
      --h2-color: #e2e8f0;
      --blockquote-bg: #1e293b;
      --blockquote-border: #3b82f6;
      --note-bg: #422006;
      --note-border: #eab308;
      --warning-bg: #450a0a;
      --warning-border: #ef4444;
    }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    line-height: 1.7;
    color: var(--text);
    background: var(--bg);
    max-width: 900px;
    margin: 0 auto;
    padding: 40px 20px 80px;
  }
  h1 { font-size: 2.2em; font-weight: 700; color: var(--h1-color); margin: 0 0 8px; padding-top: 20px; }
  h2 { font-size: 1.6em; font-weight: 600; color: var(--h2-color); margin: 40px 0 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
  h3 { font-size: 1.3em; font-weight: 600; color: var(--h2-color); margin: 30px 0 12px; }
  h4 { font-size: 1.1em; font-weight: 600; margin: 24px 0 8px; }
  p { margin: 12px 0; }
  a { color: var(--link); text-decoration: none; }
  a:hover { text-decoration: underline; }
  ul, ol { margin: 12px 0; padding-left: 24px; }
  li { margin: 4px 0; }
  li > ul, li > ol { margin: 4px 0; }
  code {
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
    background: var(--code-bg);
    color: var(--code-text);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
  }
  pre {
    background: var(--code-bg);
    color: var(--code-text);
    padding: 16px 20px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 16px 0;
    font-size: 0.88em;
    line-height: 1.5;
  }
  pre code {
    background: none;
    padding: 0;
    color: inherit;
    font-size: inherit;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 0.95em;
  }
  th {
    background: var(--thead-bg);
    font-weight: 600;
    text-align: left;
    padding: 10px 14px;
    border: 1px solid var(--border);
  }
  td {
    padding: 10px 14px;
    border: 1px solid var(--border);
    vertical-align: top;
  }
  tr:nth-child(even) { background: var(--stripe-bg); }
  blockquote {
    border-left: 4px solid var(--blockquote-border);
    background: var(--blockquote-bg);
    padding: 12px 16px;
    margin: 16px 0;
    border-radius: 0 8px 8px 0;
  }
  blockquote blockquote { margin: 8px 0; }
  hr { border: none; border-top: 2px solid var(--border); margin: 32px 0; }
  .original-link {
    font-size: 0.9em;
    color: #64748b;
    margin-bottom: 24px;
  }
  /* Syntax highlighting approximation */
  pre code .comment { color: #6a9955; }
  pre code .keyword { color: #c678dd; }
  pre code .string { color: #98c379; }
  pre code .function { color: #61afef; }
  pre code .number { color: #d19a66; }
  pre code .class-name { color: #e5c07b; }
</style>
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  {css}
</head>
<body>
{content}
</body>
</html>"""


def clean_markdown(text):
    """Clean up non-standard markdown attributes from LangChain docs."""
    # Remove theme={} attributes from code blocks
    text = re.sub(r'```(\w*)\s+theme=\{[^}]*\}', r'```\1', text)
    # Remove icon/size attributes
    text = re.sub(r'\s+icon="[^"]*"', '', text)
    text = re.sub(r'\s+size=\{\d+\}', '', text)
    # Remove theme attributes from Accordion/Tab/etc.
    text = re.sub(r'\s+theme=\{[^}]*\}', '', text)
    # Remove expandable attributes
    text = re.sub(r'\s+expandable', '', text)
    # Remove title attributes from code blocks that contain theme
    text = re.sub(r'```(\w*)\s+title="([^"]*)"\s+theme=\{[^}]*\}', r'```\1  \n<!-- title: \2 -->', text)
    text = re.sub(r'```(\w*)\s+title="([^"]*)"', r'```\1  \n<!-- title: \2 -->', text)
    # Clean up HTML-like custom components - convert to simple text
    text = re.sub(r'<Icon[^>]*/>', '', text)
    # Remove <Note>, <Tip>, <Warning>, <Accordion>, <Tabs>, <Tab>, <CardGroup>, <Card>, <ParamField>, <CodeGroup>, <AccordionGroup>, <Step>, <Steps> tags but keep their content
    for tag in ['Note', 'Tip', 'Warning', 'Accordion', 'Tab', 'Card', 'ParamField', 'CodeGroup', 'Step']:
        text = re.sub(rf'<{tag}[^>]*>', '', text)
        text = re.sub(rf'</{tag}>', '', text)
    # Keep AccordionGroup, CardGroup, Tabs, Steps as section markers
    for tag in ['AccordionGroup', 'CardGroup', 'Tabs', 'Steps']:
        text = re.sub(rf'<{tag}[^>]*>', '\n', text)
        text = re.sub(rf'</{tag}>', '\n', text)
    # Remove remaining unknown HTML-like tags but keep content
    text = re.sub(r'<[^/][^>]*>', '', text)  # opening tags
    text = re.sub(r'</[^>]*>', '', text)  # closing tags
    return text


def get_title(text):
    """Extract the first H1 title from markdown."""
    match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "LangChain Deep Agents Documentation"


files = [
    "quickstart.md",
    "customization.md",
    "models.md",
    "backends.md",
    "sandboxes.md",
    "permissions.md",
    "human-in-the-loop.md",
    "skills.md",
    "context-engineering.md",
    "cli-overview.md",
    "acp.md",
]

for md_file in files:
    src = os.path.join(MARKDOWN_DIR, md_file)
    if not os.path.exists(src):
        print(f"SKIP: {md_file} not found")
        continue

    with open(src, 'r', encoding='utf-8') as f:
        text = f.read()

    title = get_title(text)
    cleaned = clean_markdown(text)

    # Convert markdown to HTML
    md = markdown.Markdown(extensions=[
        'tables',
        'fenced_code',
        'codehilite',
        'toc',
        'nl2br',
    ])
    html_content = md.convert(cleaned)

    # Wrap in HTML template
    full_html = HTML_TEMPLATE.format(
        title=title,
        css=CSS,
        content=html_content
    )

    # Write HTML file
    html_name = md_file.replace('.md', '.html')
    out_path = os.path.join(HTML_DIR, html_name)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

    print(f"OK: {html_name} ({len(full_html)} bytes)")

print(f"\nDone! Generated {len(files)} HTML files in {HTML_DIR}")
