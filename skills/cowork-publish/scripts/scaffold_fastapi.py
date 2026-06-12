#!/usr/bin/env python3
"""
快速生成一个符合 Guard 规范的 FastAPI 最小 demo。
用法：
    python3 scaffold_fastapi.py <target_dir>

会生成：
    <target>/install.sh
    <target>/start.sh
    <target>/health.sh
    <target>/app.py
"""
import os, sys, stat

TPL = {
    "install.sh": """#!/bin/sh
set -e
pip install -i http://pypi.devops.xiaohongshu.com/simple/ \\
            --trusted-host pypi.devops.xiaohongshu.com \\
            fastapi==0.115.0 'uvicorn[standard]==0.30.6'
""",
    "start.sh": """#!/bin/sh
cd "$(dirname "$0")"
exec uvicorn app:app --host 0.0.0.0 --port 3000
""",
    "health.sh": """#!/bin/sh
curl -fsS http://127.0.0.1:3000/health > /dev/null && exit 0 || exit 1
""",
    "app.py": '''from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html>
<html><head><meta charset="utf-8"><title>Hello Cowork</title></head>
<body><h1>Hello from Cowork Guard!</h1>
<p>see also <a href="api/ping">api/ping</a></p>
</body></html>
"""

@app.get("/api/ping")
def ping():
    return {"pong": True}

@app.get("/health")
def health():
    return {"ok": True}
''',
}


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    target = os.path.abspath(sys.argv[1])
    os.makedirs(target, exist_ok=True)
    for name, body in TPL.items():
        path = os.path.join(target, name)
        with open(path, "w") as f:
            f.write(body)
        if name.endswith(".sh"):
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  wrote {path}")
    print(f"\n✓ scaffold ready at {target}")
    print(f"  next: python3 cowork.py pack {target}")
    print(f"        python3 cowork.py publish {target}.zip --cover <png> --title <name>")


if __name__ == "__main__":
    main()
