"""profile 数据驱动：把"按项目类型路由 templates / build 命令 / smoke endpoints"
从 stage 脚本里抽出来到 profiles/*.json，**新增项目类型 = 新建 1 个 json**。

设计原则：
  - **pure stdlib**：用 json（不引 pyyaml / tomllib），任何环境都能跑
  - 字段尽量扁平、自描述；避免 jinja-like 复杂语法
  - 变量插值用 ${name}，从 stack.json 字段 + profile.vars 字典解析

Profile JSON Schema（参考）::

    {
      "name": "react-fastapi-monorepo",         // 必填，唯一标识
      "description": "React/Vite SPA + FastAPI backend (monorepo)",
      "priority": 100,                          // 数字越小越优先匹配
      "match": {                                // 所有字段必须满足
        "lang": "python",                       //   scalar = stack[lang] == "python"
        "framework": ["fastapi", "flask"],      //   list   = stack[framework] in [...]
        "has_static_spa": 1
      },
      "scripts": {                              // stage 30 渲染入口脚本的模板
        "install": "templates/install_react_fastapi.sh",
        "start":   "templates/start_react_fastapi.sh",
        "health":  "templates/health_default.sh"
      },
      "build": {                                // stage 40 build 命令（按顺序）
        "frontend": "cd ${frontend_dir} && npm install --no-audit && npm run build",
        "backend":  "cd ${backend_dir} && pip install -r requirements.txt"
      },
      "smoke_test": {                           // stage 50 烟测端点
        "port": "8000",
        "endpoints": ["/", "/api/health"],
        "wait_seconds": 5
      },
      "vars": {                                 // 给变量插值额外补默认值
        "PORT": "8000"
      }
    }

匹配语义：
  - match 中每个字段必须满足（partial match，未在 match 中出现的字段不约束）
  - scalar 值 → stack[key] == value
  - list   值 → stack[key] in value

匹配优先级：
  - profile.priority 数字越小越先；同 priority 按 name 字典序
  - 第一个匹配的 profile 胜出（避免歧义）
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import log


@dataclass
class Profile:
    name: str
    description: str = ""
    priority: int = 100
    match: dict[str, Any] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)
    build: dict[str, str] = field(default_factory=dict)
    smoke_test: dict[str, Any] = field(default_factory=dict)
    vars: dict[str, str] = field(default_factory=dict)
    source_path: Optional[Path] = None  # 文件来源（debug 用）

    @classmethod
    def from_dict(cls, data: dict[str, Any], source_path: Optional[Path] = None) -> "Profile":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            priority=int(data.get("priority", 100)),
            match=data.get("match", {}),
            scripts=data.get("scripts", {}),
            build=data.get("build", {}),
            smoke_test=data.get("smoke_test", {}),
            vars=data.get("vars", {}),
            source_path=source_path,
        )

    def matches(self, stack: dict[str, Any]) -> bool:
        """该 profile 是否匹配给定的 stack。"""
        for key, expected in self.match.items():
            actual = stack.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            else:
                if actual != expected:
                    return False
        return True

    def render(self, stack: dict[str, Any]) -> "Profile":
        """对 scripts/build/smoke_test/vars 内的 ${var} 插值后返回新 Profile。

        变量来源（按优先级）：
          1. profile.vars 自身（user-provided default）
          2. stack.json 所有字段（lang / framework / backend_dir / frontend_dir 等）
          3. 大写别名：${BACKEND_DIR} = stack[backend_dir]
        """
        ctx: dict[str, str] = {}
        ctx.update(self.vars)
        for k, v in stack.items():
            ctx[k] = str(v)
            ctx[k.upper()] = str(v)

        def _interp(s: Any) -> Any:
            if isinstance(s, str):
                return _PATTERN.sub(lambda m: ctx.get(m.group(1), m.group(0)), s)
            if isinstance(s, list):
                return [_interp(x) for x in s]
            if isinstance(s, dict):
                return {k: _interp(v) for k, v in s.items()}
            return s

        return Profile(
            name=self.name,
            description=self.description,
            priority=self.priority,
            match=self.match,
            scripts=_interp(self.scripts),
            build=_interp(self.build),
            smoke_test=_interp(self.smoke_test),
            vars=_interp(self.vars),
            source_path=self.source_path,
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "name": self.name,
                "description": self.description,
                "priority": self.priority,
                "match": self.match,
                "scripts": self.scripts,
                "build": self.build,
                "smoke_test": self.smoke_test,
                "vars": self.vars,
            },
            indent=2,
            ensure_ascii=False,
        )


_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z_0-9]*)\}")


def load_all(profiles_dir: Path) -> list[Profile]:
    """读取 profiles/*.json，按 (priority, name) 排序。"""
    if not profiles_dir.is_dir():
        return []
    out: list[Profile] = []
    for p in sorted(profiles_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text())
            out.append(Profile.from_dict(data, source_path=p))
        except (OSError, json.JSONDecodeError, KeyError) as e:
            log.warn(f"profile 解析失败: {p} ({type(e).__name__}: {e})")
    out.sort(key=lambda x: (x.priority, x.name))
    return out


def match(stack: dict[str, Any], profiles: list[Profile]) -> Optional[Profile]:
    """返回首个匹配的 profile（已按 priority 排）；都不匹配返回 None。"""
    for p in profiles:
        if p.matches(stack):
            return p
    return None


def detect_and_save(stack: dict[str, Any], profiles_dir: Path, out_path: Path) -> Optional[Profile]:
    """组合 load_all + match + 渲染 + 落盘到 STATE_DIR/profile.json。"""
    profiles = load_all(profiles_dir)
    if not profiles:
        log.warn(f"profiles 目录为空: {profiles_dir}")
        return None

    matched = match(stack, profiles)
    if matched is None:
        log.warn(
            "未匹配到 profile（已加载 "
            + ", ".join(p.name for p in profiles)
            + "）；后续 stage 将走 fallback 行为"
        )
        return None

    rendered = matched.render(stack)
    out_path.write_text(rendered.to_json() + "\n")
    log.ok(f"profile 命中: {matched.name}（{matched.description}）→ {out_path}")
    return rendered
