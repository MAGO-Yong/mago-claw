# Cowork Dev Session Protocol

用于 Coral Chat 侧的小工具调试窗口绑定 URL → 代码目录。

## 方案 A：URL 自带项目签名

`cowork.py dev start <src>` 返回：

```text
http://10.40.121.204:<port>/?__cw=<toolSessionId>
MINI_TOOL_OPEN:{"url":"...","sessionId":"cw_xxxxxxxx"}
```

`__cw` 是唯一绑定 ID。Coral 独立浏览器窗口只要拿到这个 ID，就可以反查该页面对应的代码目录。

## 状态文件

```text
~/.openclaw/workspace/.cowork-dev/sessions.json
```

结构：

```json
{
  "cw_4bnbcmtc": {
    "id": "cw_4bnbcmtc",
    "srcDir": "/tmp/cw-demo",
    "port": 8901,
    "pid": 53179,
    "url": "http://10.40.121.204:8901/?__cw=cw_4bnbcmtc",
    "chatSessionId": null,
    "title": "cw-demo",
    "alias": "cw-demo",
    "coverPath": null,
    "logPath": "/home/node/.openclaw/workspace/.cowork-dev/cw_4bnbcmtc.log",
    "createdAt": 1779111577673,
    "updatedAt": 1779111577673
  }
}
```

## CLI

```bash
# 启动，自动分配 8901-8999 端口
python3 cowork.py dev start ./my-app --title "我的工具" --alias my-tool

# JSON 输出，供 Coral/Electron IPC 调
python3 cowork.py dev start ./my-app --json
python3 cowork.py dev list --json

# 同 src 默认复用已有 alive session
python3 cowork.py dev start ./my-app

# 强制新建
python3 cowork.py dev start ./my-app --new

# 停止
python3 cowork.py dev stop cw_xxxxxxxx
```

## 默认启动命令推断

| 项目特征 | 命令 |
|----------|------|
| `package.json` 且有 `scripts.dev` | `PORT=<port> npm run dev -- --host 0.0.0.0 --port <port>` |
| `app.py` | `uvicorn app:app --host 0.0.0.0 --port <port> --reload` |
| `main.py` | `uvicorn main:app --host 0.0.0.0 --port <port> --reload` |
| `index.html` | `python3 -m http.server <port> --bind 0.0.0.0` |

不符合时用 `--cmd`。

## Coral 使用建议

- Agent 回复 `MINI_TOOL_OPEN:{...}` 后，Chat UI 剥离该 directive，并调用 `miniTool.openWindow({url, chatSessionId})`
- 独立窗口初始化时保存 `toolSessionId`，即使用户导航导致 query 丢失，也以 initial id 为准
- 发布按钮点击时：
  1. `dev list --json` 查 session
  2. 取 `srcDir` → `cowork.py pack <srcDir>`
  3. `cowork.py publish <zip> --cover ... --title ... --alias ...`
