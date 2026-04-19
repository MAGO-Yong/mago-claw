#!/usr/bin/env python3
"""
skill-evaluator: 评估题目生成器
用法:
  python3 generate_questions.py --skill-path <path_to_SKILL.md> [--context <business_context_json>]
输出: JSON 数组，包含评估题目
"""

import argparse
import json
import sys
import os
import re

def read_skill_md(skill_path):
    """读取 SKILL.md 文件"""
    if os.path.isdir(skill_path):
        md_path = os.path.join(skill_path, "SKILL.md")
    elif skill_path.endswith("SKILL.md"):
        md_path = skill_path
    else:
        md_path = os.path.join(skill_path, "SKILL.md")

    if not os.path.exists(md_path):
        print(json.dumps({"error": f"SKILL.md not found at {md_path}"}))
        sys.exit(1)

    with open(md_path, "r", encoding="utf-8") as f:
        return f.read()

def parse_skill_info(content):
    """从 SKILL.md 提取关键信息"""
    info = {
        "name": "",
        "description": "",
        "triggers": [],
        "inputs": [],
        "outputs": [],
        "boundaries": [],
        "evaluation_block": ""
    }

    # 提取 YAML frontmatter
    fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        name_m = re.search(r'^name:\s*(.+)$', fm, re.MULTILINE)
        if name_m:
            info["name"] = name_m.group(1).strip()
        desc_m = re.search(r'^description:\s*[>|]?\n?(.*?)(?=\n\w|\Z)', fm, re.DOTALL | re.MULTILINE)
        if desc_m:
            info["description"] = desc_m.group(1).strip()[:1000]

    # 提取 ## Evaluation 块（如果有）
    eval_m = re.search(r'## Evaluation\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if eval_m:
        info["evaluation_block"] = eval_m.group(1).strip()

    # 提取边界/限制
    boundary_m = re.search(r'(边界|限制|不支持|known_boundary|boundary)(.*?)(?=\n## |\Z)', content, re.DOTALL | re.IGNORECASE)
    if boundary_m:
        info["boundaries"] = boundary_m.group(2).strip()[:500]

    return info

def build_question_prompt(skill_info, context=None, mode="zero-config"):
    """构建题目生成的 Prompt"""
    n_questions = 10 if mode == "zero-config" else 15

    prompt = f"""你是一个 AI Agent 质量评估专家。请为以下 SKILL 生成评估题目。

## SKILL 基本信息
- 名称：{skill_info['name']}
- 功能描述：{skill_info['description']}
"""
    if skill_info.get("evaluation_block"):
        prompt += f"\n## SKILL 自定义评估标准\n{skill_info['evaluation_block']}\n"

    if context:
        prompt += f"\n## 业务上下文（用户提供）\n{context}\n"

    prompt += f"""
## 题目生成要求

请生成 {n_questions} 道评估题目，分布如下：
- 标准场景（S）：{n_questions // 2} 题 — 完整入参，直接调用，考察基础准确性
- 边界场景（B）：{n_questions // 4} 题 — 缺少参数、格式异常、超出能力范围的处理
- 组合场景（C）：{n_questions // 4} 题 — 需要多步推理或与其他 Skill 协作

{'有业务上下文时，S 类题目应使用真实的业务数据（服务名、事件ID等）' if context else '没有业务上下文时，使用合理的占位数据（如：服务名=test-service）'}

## 输出格式（严格 JSON 数组，不加任何其他文字）

[
  {{
    "id": "Q1",
    "type": "S",
    "query": "用户实际会说的话（自然语言）",
    "expected_skills": ["预期会调用的 skill 名称"],
    "expected_behavior": "预期的执行路径描述",
    "success_criteria": "判断这道题成功的具体标准",
    "known_boundary": false
  }},
  ...
]

注意：
1. query 必须是用户真实会说的自然语言，不是技术描述
2. success_criteria 要具体可判断，不要写"回答正确"这种模糊标准
3. B 类题目的 known_boundary 设为 true
4. 确保题目覆盖 SKILL 的核心能力，不要出超出 SKILL 能力范围的 S 类题目
"""
    return prompt

def main():
    parser = argparse.ArgumentParser(description="生成 SKILL 评估题目")
    parser.add_argument("--skill-path", required=True, help="SKILL 目录路径或 SKILL.md 文件路径")
    parser.add_argument("--context", default=None, help="业务上下文 JSON 字符串")
    parser.add_argument("--mode", default="zero-config", choices=["zero-config", "enhanced"], help="评估模式")
    args = parser.parse_args()

    content = read_skill_md(args.skill_path)
    skill_info = parse_skill_info(content)

    context = None
    if args.context:
        try:
            context = json.loads(args.context) if args.context.startswith("{") else args.context
        except:
            context = args.context

    prompt = build_question_prompt(skill_info, context, args.mode)

    # 输出结构化信息供 Agent 使用
    output = {
        "skill_name": skill_info["name"],
        "skill_description": skill_info["description"][:500],
        "has_evaluation_block": bool(skill_info["evaluation_block"]),
        "mode": args.mode,
        "generation_prompt": prompt,
        "instruction": (
            "请使用上方的 generation_prompt 调用 LLM 生成题目，"
            "将生成的 JSON 数组保存到 /tmp/eval_questions.json，"
            "然后继续执行 Phase 2（分批 spawn sub-agent 执行）。"
        )
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
