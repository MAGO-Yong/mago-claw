#!/usr/bin/env python3
"""
get_slave_status.py — 查询从库复制状态

接口（白名单已确认）：
  GET /dms-api/ai-api/v1/mysql/monitor/get_slave_state   ← 优先（DMS_AI_TOKEN）
  GET /dms-api/v1/mysql/operation/get-slave-state        ← 兜底（DMS_CLAW_TOKEN）

认证：优先 DMS_AI_TOKEN（ai-api/v1），兜底 DMS_CLAW_TOKEN（open-claw）

返回字段包括：ip, port, vmName, clusterName, role, sqlDelay, cpuUsage, ioWait 等。
注意：该接口返回 sqlDelay（主从延迟秒数），对应 SHOW SLAVE STATUS 中的 Seconds_Behind_Master。

若 DMS API 返回失败，降级输出人工排查 SQL 指引。

用法：
  python3 get_slave_status.py \
      --cluster <cluster_name> \
      --hostname <slave_vm_name> \
      [--output <dir>] [--run_id <id>]
"""

import argparse
import json
import sys
import urllib.parse
from pathlib import Path

# 统一客户端（支持 DMS_AI_TOKEN 优先 + DMS_CLAW_TOKEN 兜底）
sys.path.insert(0, str(Path(__file__).parents[1]))
from common.dms_client import (
    AI_TOKEN, CLAW_TOKEN, BASE_URL, AI_V1_PREFIX,
    _AI_HEADERS, _http_get, call_with_fallback,
)

TOKEN = CLAW_TOKEN  # open-claw 兜底用

MANUAL_GUIDE = """
[get_slave_status] ⚠️  DMS API 请求失败，请人工确认：

方式 1：DMS 控制台
  集群管理 → {cluster} → 选中从库节点 → 会话管理 → 执行以下 SQL

方式 2：直接执行 SQL
  SHOW SLAVE STATUS\\G

重点关注字段：
  Slave_IO_Running       : Yes（正常）/ No（IO线程停了）
  Slave_SQL_Running      : Yes（正常）/ No（SQL线程停了，复制中断）
  Seconds_Behind_Master  : 0（正常）/ >30（延迟告警）/ >300（紧急）
  Last_Error             : 空（正常）/ 非空（复制报错，需立即处理）
  Relay_Log_Space        : 稳定（正常）/ 持续增长（SQL线程消化慢）
  Master_Log_File        : 当前读取的主库 binlog 文件名
  Exec_Master_Log_Pos    : 当前回放位点

延迟类型判断：
  Slave_IO_Running=No  → binlog 拉取中断（网络/主库问题）
  Slave_SQL_Running=No → 回放中断（Last_Error 非空，SQL 执行报错）
  两者均 Yes 但延迟大  → 从库回放速度跟不上（慢 SQL / 大事务 / 硬件瓶颈）
"""


def fetch_slave_state(vmname: str) -> dict:
    """调用 get-slave-state 接口，v1 优先，open-claw 兜底。"""

    def _v1():
        qs = urllib.parse.urlencode({"vm_name": vmname})
        return _http_get(f"{AI_V1_PREFIX}/mysql/monitor/get_slave_state?{qs}", _AI_HEADERS)

    def _old():
        qs = urllib.parse.urlencode({"vmname": vmname})
        return _http_get(
            f"{BASE_URL}/dms-api/v1/mysql/operation/get-slave-state?{qs}",
            {"dms-claw-token": TOKEN},
        )

    return call_with_fallback(_v1, _old, "[get_slave_status]")


def analyze(data: dict) -> dict:
    """分析关键字段，输出风险摘要。"""
    # get-slave-state 返回 sqlDelay（整数秒）作为复制延迟
    sql_delay = data.get("sqlDelay")
    cpu_usage = data.get("cpuUsage")
    io_wait = data.get("ioWait")
    role = data.get("role", "unknown")

    result = {
        "vm_name": data.get("vmName", "?"),
        "cluster": data.get("clusterName", "?"),
        "role": role,
        "seconds_behind": sql_delay,
        "cpu_usage": cpu_usage,
        "io_wait": io_wait,
        "risks": [],
    }

    # seconds_behind 分析（None 说明接口未返回该字段）
    if sql_delay is None:
        result["risks"].append("🟡 sqlDelay 字段为空，无法判断主从延迟（节点可能是主库或刚启动）")
    elif sql_delay > 300:
        result["risks"].append(f"🔴 sqlDelay={sql_delay}s：严重主从延迟，需紧急处理")
    elif sql_delay > 30:
        result["risks"].append(f"🟠 sqlDelay={sql_delay}s：主从延迟告警")
    elif sql_delay > 0:
        result["risks"].append(f"🟡 sqlDelay={sql_delay}s：轻微延迟")

    # CPU & IO 辅助判断
    try:
        if cpu_usage is not None and float(cpu_usage) > 80:
            result["risks"].append(f"🟠 CPU 使用率 {cpu_usage}%，负载较高")
        if io_wait is not None and float(io_wait) > 30:
            result["risks"].append(f"🟠 IO Wait {io_wait}%，磁盘 IO 可能成为瓶颈")
    except (ValueError, TypeError):
        pass

    if not result["risks"]:
        result["risks"].append("✅ 从库状态正常（无延迟，CPU/IO 正常）")

    return result


def main():
    parser = argparse.ArgumentParser(description="查询从库复制状态")
    parser.add_argument("--cluster", required=True, help="集群名称（用于人工指引提示）")
    parser.add_argument("--hostname", required=True, help="从库 vm_name（如 qsh4-db-sns-cat-34）")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    args = parser.parse_args()

    if not AI_TOKEN and not TOKEN:
        print("[get_slave_status] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    try:
        result = fetch_slave_state(args.hostname)
        code = result.get("code", -1)
        if code != 0:
            raise RuntimeError(f"API 返回 code={code}: {result.get('message', '')}")
    except RuntimeError as e:
        print(f"[get_slave_status] ⚠️  请求失败：{e}", file=sys.stderr)
        print(MANUAL_GUIDE.format(cluster=args.cluster), file=sys.stderr)
        fallback = {
            "code": -1,
            "data": {"status": "api_failed", "manual_guide": True},
            "_analysis": {"risks": ["⚠️  API 不可用，请人工确认"]},
        }
        output_str = json.dumps(fallback, ensure_ascii=False, indent=2)
    else:
        data = result.get("data", {})
        analysis = analyze(data)
        result["_analysis"] = analysis
        output_str = json.dumps(result, ensure_ascii=False, indent=2)

        # 打印摘要到 stderr
        print(f"[get_slave_status] 集群：{args.cluster}  节点：{args.hostname}", file=sys.stderr)
        print(f"  角色            : {analysis['role']}", file=sys.stderr)
        print(f"  Seconds_Behind  : {analysis['seconds_behind']}", file=sys.stderr)
        print(f"  CPU 使用率      : {analysis['cpu_usage']}%", file=sys.stderr)
        print(f"  IO Wait         : {analysis['io_wait']}%", file=sys.stderr)
        print("  风险评估：", file=sys.stderr)
        for r in analysis["risks"]:
            print(f"    {r}", file=sys.stderr)

    if args.output and args.run_id:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        out_file = raw_dir / "get_slave_status.json"
        out_file.write_text(output_str, encoding="utf-8")
        print(f"[get_slave_status] ✅ 已写入 {out_file}", file=sys.stderr)

    print(output_str)


if __name__ == "__main__":
    main()
