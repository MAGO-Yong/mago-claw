#!/usr/bin/env python3
"""
会话快照管理器 - 支持断点续诊

用法：
    from session_manager import SessionManager
    sm = SessionManager(sessions_dir)
    
    # 创建新会话
    sm.create(params={...})
    
    # 更新状态
    sm.update(current_gate="A", next_step=3, findings={...})
    
    # 保存（暂停）
    sm.pause()
    
    # 加载已有会话
    sm.load("sessions/2026-04-02_10-36.json")
    
    # 列出所有会话
    SessionManager.list_sessions(sessions_dir)
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path


CST = timezone(timedelta(hours=8))


class SessionManager:
    def __init__(self, sessions_dir: str):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(exist_ok=True)
        self._data = {}
        self._session_file = None

    def create(self, params: dict) -> str:
        """创建新的会话快照，返回会话ID"""
        now = datetime.now(tz=CST)
        session_id = now.strftime("%Y-%m-%d_%H-%M")
        self._session_file = self.sessions_dir / f"{session_id}.json"

        self._data = {
            "session_id": session_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "path": "unknown",        # fast / standard / deep
            "current_gate": None,     # A / B / C / D / None
            "next_step": 1,           # 下一步要执行的 step
            "diagnosis_params": params,
            "findings": {
                "t0": None,
                "anomaly_type": None,  # 急跌 / 阴跌 / 混合
                "baseline_set": None,  # "-1d" / "-7d,-14d" 等
                "drop_1h_pct": None,
                "drop_24h_pct": None,
                "watchlist_hits": [],
                "steps_completed": [],
            },
            "status": "running",      # running / paused_at_gate / completed
        }
        self._save()
        return session_id

    def load(self, session_file: str) -> dict:
        """从快照文件加载会话"""
        path = Path(session_file)
        if not path.exists():
            raise FileNotFoundError(f"Session file not found: {session_file}")
        with open(path) as f:
            self._data = json.load(f)
        self._session_file = path
        return self._data

    def update(self, **kwargs):
        """更新会话状态，支持嵌套字段"""
        now = datetime.now(tz=CST)
        self._data["updated_at"] = now.isoformat()

        for key, value in kwargs.items():
            if key == "findings" and isinstance(value, dict):
                self._data["findings"].update(value)
            else:
                self._data[key] = value
        self._save()

    def add_watchlist_hit(self, level: str, key: str, time: str, description: str = ""):
        """追加 watchlist 命中记录"""
        hit = {"level": level, "key": key, "time": time, "description": description}
        self._data["findings"]["watchlist_hits"].append(hit)
        self._data["updated_at"] = datetime.now(tz=CST).isoformat()
        self._save()

    def mark_step_completed(self, step: int):
        """标记某个 step 已完成"""
        steps = self._data["findings"].get("steps_completed", [])
        if step not in steps:
            steps.append(step)
            self._data["findings"]["steps_completed"] = steps
        self._data["updated_at"] = datetime.now(tz=CST).isoformat()
        self._save()

    def pause(self, gate: str = None):
        """暂停诊断，保存快照"""
        self._data["status"] = "paused_at_gate"
        if gate:
            self._data["current_gate"] = gate
        self._data["updated_at"] = datetime.now(tz=CST).isoformat()
        self._save()
        return str(self._session_file)

    def complete(self):
        """标记诊断完成"""
        self._data["status"] = "completed"
        self._data["updated_at"] = datetime.now(tz=CST).isoformat()
        self._save()

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def get_findings(self, key: str, default=None):
        return self._data.get("findings", {}).get(key, default)

    @property
    def data(self) -> dict:
        return self._data

    @property
    def session_file(self) -> str:
        return str(self._session_file) if self._session_file else None

    def _save(self):
        if self._session_file:
            with open(self._session_file, "w") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def list_sessions(sessions_dir: str) -> list:
        """列出所有历史会话，按时间倒序"""
        dir_path = Path(sessions_dir)
        if not dir_path.exists():
            return []

        sessions = []
        for f in sorted(dir_path.glob("*.json"), reverse=True):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                sessions.append({
                    "file": str(f),
                    "session_id": data.get("session_id", f.stem),
                    "status": data.get("status", "unknown"),
                    "path": data.get("path", "unknown"),
                    "current_gate": data.get("current_gate"),
                    "next_step": data.get("next_step"),
                    "created_at": data.get("created_at", ""),
                    "params": data.get("diagnosis_params", {}),
                    "drop_1h_pct": data.get("findings", {}).get("drop_1h_pct"),
                })
            except Exception:
                pass
        return sessions

    @staticmethod
    def print_sessions(sessions_dir: str):
        """打印历史会话列表"""
        sessions = SessionManager.list_sessions(sessions_dir)
        if not sessions:
            print("没有历史诊断会话。")
            return

        print(f"\n{'='*60}")
        print("历史诊断会话")
        print(f"{'='*60}")
        for s in sessions:
            status_emoji = {"running": "🔄", "paused_at_gate": "⏸️", "completed": "✅"}.get(s["status"], "❓")
            print(f"\n{status_emoji} [{s['session_id']}]  路径：{s['path']}  GATE：{s['current_gate']}")
            params = s["params"]
            print(f"   时间范围：{params.get('start', '?')} ~ {params.get('end', '?')}")
            if s["drop_1h_pct"] is not None:
                print(f"   1H跌幅：{s['drop_1h_pct']:+.1f}%")
            print(f"   文件：{s['file']}")
        print()
