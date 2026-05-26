#!/usr/bin/env python3
"""
alipayservice 成功率下跌告警诊断 Skill
输入：event_id
输出：JSON 诊断报告
"""

import sys
import json
import subprocess
import datetime
import os

SKILL_NAME = "alipayservice-success-rate-diagnosis"
APP = "alipayservice"
EXCEPTION_LIST = [
    "java.lang.Exception",
    "java.lang.RuntimeException",
    "java.util.concurrent.TimeoutException",
    "com.xiaohongshu.exception.XhsException",
]


def run_xray(args: list[str]) -> tuple[bool, dict | str]:
    """执行 xray-cli 命令，返回 (success, data)"""
    cmd = ["xray-cli"] + args + ["--output-format", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return False, "timeout after 60s"
    except json.JSONDecodeError as e:
        return False, f"json parse error: {e} | stdout: {result.stdout[:200]}"
    except Exception as e:
        return False, str(e)


def parse_time(time_str: str) -> datetime.datetime:
    """解析 ISO 时间字符串"""
    return datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))


def format_time(dt: datetime.datetime) -> str:
    """格式化为 xray-cli 接受的本地时间字符串"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"status": "blocked", "reason": "missing event_id argument"}, ensure_ascii=False))
        sys.exit(1)

    event_id = sys.argv[1]
    report = {
        "skill": SKILL_NAME,
        "event_id": event_id,
        "trigger_time": None,
        "restore_time": None,
        "duration_minutes": None,
        "analysis": {
            "error_spans": {"status": "unknown", "total": 0, "top_errors": []},
            "exceptions": {"status": "unknown", "top_exceptions": []},
        },
        "dependency_gaps": [
            {
                "name": "RPC拓扑指标",
                "reason": "alipayservice 中间件版本不满足 trace topology service 查询要求（需 ≥ 3.3.31.3-RELEASE）",
                "manual_url": f"https://xray.devops.xiaohongshu.com/d/topology?app={APP}",
            },
            {
                "name": "变更查询",
                "reason": "xray-cli 暂无变更查询原子能力",
                "manual_url": f"https://xray.devops.xiaohongshu.com/event/search?app={APP}",
            },
        ],
        "conclusion": "unknown",
        "suggested_actions": [],
    }

    # Step 1: 获取告警事件基本信息
    ok, data = run_xray(["alarm", "event", "get", event_id])
    if not ok:
        report["conclusion"] = "blocked"
        report["error"] = f"alarm event get failed: {data}"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(1)

    basic = data.get("basic", {})
    trigger_time_str = basic.get("trigger_time")
    restore_time_str = basic.get("restore_time")

    report["trigger_time"] = trigger_time_str
    report["restore_time"] = restore_time_str

    # 计算时间窗口
    try:
        trigger_dt = parse_time(trigger_time_str)
        start_dt = trigger_dt - datetime.timedelta(minutes=5)

        if restore_time_str:
            end_dt = parse_time(restore_time_str) + datetime.timedelta(minutes=2)
            duration = (parse_time(restore_time_str) - trigger_dt).seconds // 60
        else:
            end_dt = trigger_dt + datetime.timedelta(minutes=30)
            duration = None

        report["duration_minutes"] = duration
        start_str = format_time(start_dt)
        end_str = format_time(end_dt)
    except Exception as e:
        report["conclusion"] = "blocked"
        report["error"] = f"time parse failed: {e}"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(1)

    # Step 2a: trace search error
    ok, data = run_xray([
        "trace", "search",
        "--app", APP,
        "--mode", "error",
        "--start", start_str,
        "--end", end_str,
    ])
    if not ok:
        report["analysis"]["error_spans"] = {"status": "unknown", "error": str(data)}
    else:
        total = data.get("total", 0)
        spans = data.get("spans", [])
        agg = data.get("aggregation", {})

        if total == 0:
            report["analysis"]["error_spans"] = {"status": "none", "total": 0, "top_errors": []}
        else:
            # 提取 Top5 错误
            top_errors = []
            # 尝试从 aggregation 或 spans 提取
            error_groups = agg.get("errors") or agg.get("error_clusters") or []
            if error_groups:
                for eg in sorted(error_groups, key=lambda x: x.get("count", 0), reverse=True)[:5]:
                    top_errors.append({
                        "error": eg.get("error_name") or eg.get("name") or eg.get("exception"),
                        "count": eg.get("count") or eg.get("total"),
                    })
            else:
                # 从 spans 聚合
                counter = {}
                for s in spans:
                    key = s.get("error_name") or s.get("exception") or s.get("error") or "unknown"
                    counter[key] = counter.get(key, 0) + 1
                for k, v in sorted(counter.items(), key=lambda x: -x[1])[:5]:
                    top_errors.append({"error": k, "count": v})

            report["analysis"]["error_spans"] = {
                "status": "found",
                "total": total,
                "top_errors": top_errors,
            }

    # Step 2b: trace exception
    ok, data = run_xray([
        "trace", "exception",
        "--app", APP,
        "--exceptions", ",".join(EXCEPTION_LIST),
        "--start", start_str,
        "--end", end_str,
    ])
    if not ok:
        report["analysis"]["exceptions"] = {"status": "unknown", "error": str(data)}
    else:
        exceptions = data.get("exceptions", [])
        if not exceptions:
            report["analysis"]["exceptions"] = {"status": "none", "top_exceptions": []}
        else:
            top_exceptions = []
            # 按总 count 降序取 Top3
            exc_with_count = []
            for exc in exceptions:
                total_count = sum(s.get("count", 0) for s in exc.get("tags", []))
                exc_with_count.append((exc["exception"], total_count, exc.get("tags", [])))

            for exc_name, count, tags in sorted(exc_with_count, key=lambda x: -x[1])[:3]:
                top_stack = ""
                if tags:
                    top_stack = "\n".join(tags[0].get("stack", "").split("\n")[:5])
                top_exceptions.append({
                    "exception": exc_name,
                    "count": count,
                    "top_stack_preview": top_stack,
                })

            report["analysis"]["exceptions"] = {
                "status": "found",
                "top_exceptions": top_exceptions,
            }

    # 判定 conclusion
    error_status = report["analysis"]["error_spans"]["status"]
    exc_status = report["analysis"]["exceptions"]["status"]

    has_error = (error_status == "found") or (exc_status == "found")
    has_unknown = (error_status == "unknown") or (exc_status == "unknown")

    if has_error:
        report["conclusion"] = "error_found"
        report["suggested_actions"].append("服务存在异常报错，建议结合堆栈定位根因，并查看 RPC 拓扑和变更（见 dependency_gaps）")
    elif has_unknown:
        report["conclusion"] = "dependency_gap_required"
        report["suggested_actions"].append("部分自动分析失败，请手动补充 RPC 拓扑和变更查询")
    else:
        report["conclusion"] = "auto_cleared"
        report["suggested_actions"].append("自动分析未发现报错，建议人工确认 RPC 上下游指标和变更（见 dependency_gaps）")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
