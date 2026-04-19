#!/usr/bin/env python3
"""
get_db_connectors.py — 获取数据库连接器列表

接口：GET /dms-api/open-claw/meta-data/mysql/get-db-connectors
认证：DMS_CLAW_TOKEN

用法：
  # 只传集群名（自动识别类型，自动选 db_name）
  python3 get_db_connectors.py --cluster redtao_tns

  # 手动指定 db_name（覆盖自动推断）
  python3 get_db_connectors.py --cluster redtao_tns --db redtao_tns_p00000

  # 包含主库
  python3 get_db_connectors.py --cluster sns_user_extra --include_master

自动推断逻辑：
  1. 调用 cluster/search 判断 connectType（精确匹配集群名）
  2. connectType=redhub → 调用 get-db-list 枚举物理分片库，取第一个 _p 分片作为 connector_db
  3. connectType=mysql  → 使用 cluster_name 本身作为 db_name
  4. 调用失败时降级为 db_name='mysql'（通用兜底）

输出附加字段（_meta）：
  cluster_type    — mysql / redhub / unknown
  connector_db    — 仅用于获取 connector 的代表分片（不代表分析范围）
  logical_db      — 逻辑库名
  shards          — 分库分表时的所有物理分片库名列表（空列表=普通集群）
  analysis_shards — 后续 get-table-stats/get-index-stats 需遍历的分片列表
                    分库分表集群 = shards 全集；普通集群 = [connector_db]
  shard_warning   — 分库分表集群时的强提示（非空表示必须遍历 analysis_shards）

  ⚠️  connector_db 仅用于定位节点 IP，不等于分析范围。
      分库分表集群必须遍历 analysis_shards 全部分片做 table-stats/index-stats，
      否则会漏掉数据量差异悬殊的分片（历史案例：rows_examined 差 3000 倍）。

历史教训（2026-03-27 redtao_tns）：
  只采集 5fpli-2 漏掉了 5fpli-3，而 5fpli-3 上的 SQL rows_examined=11,922,717
  （是 5fpli-2 的 3000 倍）。诊断多分片集群必须遍历所有从库节点。
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from pathlib import Path

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
from common.dms_client import (
    AI_TOKEN, BASE_URL as DMS_BASE, AI_V1_PREFIX, OPEN_CLAW_PREFIX, CLAW_TOKEN,
    _AI_HEADERS, _http_get, call_with_fallback,
)

OPEN_CLAW_BASE = OPEN_CLAW_PREFIX
V1_BASE = DMS_BASE + "/dms-api/v1"
TOKEN = CLAW_TOKEN

# 物理分片库名正则：必须以 _p + 5位数字 结尾，避免误匹配 _pipeline / _performance 等
_SHARD_RE = re.compile(r'_p\d{5}$')


# ──────────────────────────────────────────────
# 基础 HTTP 工具
# ──────────────────────────────────────────────

def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"dms-claw-token": TOKEN})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ──────────────────────────────────────────────
# Step 1：判断集群类型（精确匹配）
# ──────────────────────────────────────────────

def detect_cluster_type(cluster_name: str) -> dict:
    """
    返回：{
      "cluster_type": "mysql" | "redhub" | "unknown",
      "cluster_id": ...,
    }

    使用精确匹配（name == cluster_name），避免模糊搜索取到相似名集群。
    """
    try:
        url = f"{V1_BASE}/mysql/base/cluster/search?{urllib.parse.urlencode({'key_word': cluster_name})}"
        d = _get(url)
        candidates = d.get("data", [])
        # 优先精确匹配
        for c in candidates:
            if c.get("name") == cluster_name or c.get("clusterName") == cluster_name:
                ct = str(c.get("connectType", "")).lower()
                return {
                    "cluster_type": ct if ct else "mysql",
                    "cluster_id": c.get("id"),
                }
        # 无精确匹配时取第一条并打印警告
        if candidates:
            c = candidates[0]
            ct = str(c.get("connectType", "")).lower()
            print(
                f"[get_db_connectors] ⚠️  未找到精确匹配集群 '{cluster_name}'，"
                f"取第一条结果 '{c.get('name', '?')}'（connectType={ct}）",
                file=sys.stderr,
            )
            return {"cluster_type": ct if ct else "mysql", "cluster_id": c.get("id")}
    except Exception as e:
        print(f"[get_db_connectors] ⚠️  cluster/search 失败，降级为 mysql 类型: {e}", file=sys.stderr)
    return {"cluster_type": "unknown", "cluster_id": None}


# ──────────────────────────────────────────────
# Step 2：获取库名列表
# ──────────────────────────────────────────────

def _get_real_db_names(cluster_name: str) -> list[str]:
    """普通集群：从 get-db-list 取真实库名列表（排除系统库）"""
    SYS_DBS = {"information_schema", "mysql", "performance_schema", "sys"}
    try:
        url = f"{V1_BASE}/mysql/base/get-db-list?{urllib.parse.urlencode({'cluster_name': cluster_name})}"
        d = _get(url)
        dbs = [db for db in d.get("data", []) if db.lower() not in SYS_DBS]
        return dbs
    except Exception as e:
        print(f"[get_db_connectors] ⚠️  get-db-list 失败: {e}", file=sys.stderr)
        return []


def list_shards(cluster_name: str) -> list[str]:
    """
    返回所有物理分片库名，如 ['redtao_tns_p00000', 'redtao_tns_p00001']

    使用严格正则 _p\\d{5}$ 匹配，避免误匹配 _pipeline / _performance 等业务库。
    """
    try:
        url = f"{V1_BASE}/mysql/base/get-db-list?{urllib.parse.urlencode({'cluster_name': cluster_name})}"
        d = _get(url)
        dbs = d.get("data", [])
        shards = sorted([db for db in dbs if _SHARD_RE.search(db)])
        return shards
    except Exception as e:
        print(f"[get_db_connectors] ⚠️  get-db-list 失败: {e}", file=sys.stderr)
        return []


# ──────────────────────────────────────────────
# Step 3：自动推断 connector_db 及分析分片列表
# ──────────────────────────────────────────────

def resolve_db_name(cluster_name: str, db_name_override: str | None) -> dict:
    """
    返回：{
      "connector_db":    str,       # 仅用于拉取 connector 的代表分片
      "cluster_type":   str,        # mysql / redhub / unknown / manual
      "shards":         list[str],  # 分库分表时的所有物理分片（空=普通集群）
      "analysis_shards": list[str], # 后续 table-stats/index-stats 需遍历的完整列表
      "logical_db":     str,        # 逻辑库名
    }

    关键语义区分：
      connector_db    → 只是定位节点用的"代表"，不代表分析范围
      analysis_shards → 分库分表集群必须全部遍历；普通集群等于 [connector_db]
    """
    if db_name_override:
        # 手动指定时：仍然探测集群类型，只覆盖 connector_db
        meta = detect_cluster_type(cluster_name)
        ct = meta["cluster_type"]
        if ct == "redhub":
            shards = list_shards(cluster_name)
        else:
            shards = []
        return {
            "connector_db": db_name_override,
            "cluster_type": ct,
            "shards": shards,
            "analysis_shards": shards if shards else [db_name_override],
            "logical_db": cluster_name,
        }

    meta = detect_cluster_type(cluster_name)
    ct = meta["cluster_type"]

    if ct == "redhub":
        shards = list_shards(cluster_name)
        if shards:
            connector_db = shards[0]   # 取第一个分片定位节点，仅此用途
            print(f"[get_db_connectors] redhub 集群，物理分片: {shards}", file=sys.stderr)
            print(f"[get_db_connectors] connector 代表分片={connector_db}（共 {len(shards)} 个分片）", file=sys.stderr)
        else:
            connector_db = cluster_name
            shards = []
            print(f"[get_db_connectors] ⚠️  未找到物理分片，降级使用 connector_db={connector_db}", file=sys.stderr)
        return {
            "connector_db": connector_db,
            "cluster_type": "redhub",
            "shards": shards,
            "analysis_shards": shards if shards else [connector_db],
            "logical_db": cluster_name,
        }
    else:
        db_name = cluster_name
        real_dbs = _get_real_db_names(cluster_name)
        if real_dbs:
            db_name = real_dbs[0]
            print(f"[get_db_connectors] 普通集群库名: {real_dbs[:5]}，使用 db_name={db_name}", file=sys.stderr)
        return {
            "connector_db": db_name,
            "cluster_type": ct,
            "shards": [],
            "analysis_shards": [db_name],
            "logical_db": cluster_name,
        }


# ──────────────────────────────────────────────
# Step 4：拉取 connector 列表
# ──────────────────────────────────────────────

def fetch_connectors(cluster_name: str, db_name: str, include_master: bool = False) -> dict:
    params = {"cluster_name": cluster_name, "db_name": db_name}
    if include_master:
        params["include_master"] = "true"
    qs = urllib.parse.urlencode(params)

    def _v1():
        return _http_get(
            f"{AI_V1_PREFIX}/mysql/meta_data/get_db_connectors?{qs}",
            _AI_HEADERS,
            timeout=15,
        )

    def _old():
        return _http_get(
            f"{OPEN_CLAW_BASE}/meta-data/mysql/get-db-connectors?{qs}",
            {"dms-claw-token": TOKEN},
            timeout=15,
        )

    try:
        return call_with_fallback(_v1, _old, "[get_db_connectors]")
    except Exception as e:
        raise RuntimeError(f"[get_db_connectors] 请求失败：{e}")


# ──────────────────────────────────────────────
# Fallback：instance/get-by-cluster（myhub 集群专用）
# ──────────────────────────────────────────────

def _fallback_instance_list(cluster_name: str, include_master: bool = False) -> dict | None:
    """
    当 get-db-connectors 接口返回 400（myhub 集群不支持）时，
    fallback 到 /mysql/base/instance/get-by-cluster，返回全量节点。

    white-screen-instance-list/get-by-cluster 仅返回白屏展示用的部分分片，
    本接口返回完整节点列表（含全部分片，如 ads_ad_core 返回 33 个节点）。

    shard 字段部分节点可能为空（lshn 前缀等跨机房节点），填充 "" 空字符串，不过滤。
    """
    try:
        url = f"{V1_BASE}/mysql/base/instance/get-by-cluster?{urllib.parse.urlencode({'db_cluster': cluster_name})}"
        d = _get(url)
        instances = d.get("data", [])
        if not instances:
            print(f"[get_db_connectors] ⚠️  instance/get-by-cluster 返回空列表", file=sys.stderr)
            return None

        # 格式化为 get-db-connectors 兼容结构
        nodes = []
        for inst in instances:
            role = (inst.get("role") or "slave").lower()
            if not include_master and role == "master":
                continue
            nodes.append({
                "role":      role,
                "vm_name":   inst.get("vmName", ""),
                "ip":        inst.get("ip", ""),
                "port":      inst.get("port", 3306),
                "shardName": inst.get("shardName") or "",  # 部分节点为空，填充 ""
            })

        total = len(instances)
        masters = sum(1 for i in instances if (i.get("role") or "").lower() == "master")
        slaves  = sum(1 for i in instances if (i.get("role") or "").lower() == "slave")
        print(
            f"[get_db_connectors] ✅ instance/get-by-cluster fallback 成功："
            f"共 {total} 个节点（master={masters}, slave={slaves}）",
            file=sys.stderr,
        )
        return {"data": nodes, "_fallback": "instance/get-by-cluster"}
    except Exception as e:
        print(f"[get_db_connectors] ❌ instance/get-by-cluster fallback 失败: {e}", file=sys.stderr)
        return None


# ──────────────────────────────────────────────
# 工具函数（供外部调用）
# ──────────────────────────────────────────────

def pick_slave_connector(data: dict) -> str:
    """取第一个 slave connector（兼容旧调用方）"""
    slaves = list_slave_connectors(data)
    if not slaves:
        raise RuntimeError("[get_db_connectors] 未找到 slave 实例")
    return slaves[0]


def list_slave_connectors(data: dict) -> list[str]:
    """
    返回所有 slave connectors：["normal:ip1:port1", ...]

    ⚠️ 诊断多分片集群时必须遍历所有从库，不能只取第一个。
    历史教训（2026-03-27 redtao_tns）：漏掉 5fpli-3，rows_examined 差 3000 倍。
    """
    connectors = data.get("data", [])
    slaves = [c for c in connectors if c.get("role") == "slave"]
    return [f"normal:{c['ip']}:{c['port']}" for c in slaves]


# ──────────────────────────────────────────────
# main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="获取数据库连接器列表（自动识别分库分表）")
    parser.add_argument("--cluster", required=True, help="集群名称")
    parser.add_argument("--db", default=None,
                        help="数据库名称（可选，不传则自动推断：redhub取第一个物理分片，普通集群取cluster_name）")
    parser.add_argument("--include_master", action="store_true", help="是否包含主库")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--run_id", default="", help="本次运行 ID")
    args = parser.parse_args()

    if not AI_TOKEN and not TOKEN:
        print("[get_db_connectors] ❌ 未设置 DMS_AI_TOKEN 或 DMS_CLAW_TOKEN", file=sys.stderr)
        sys.exit(1)

    # 自动推断（含分片列表）
    resolved = resolve_db_name(args.cluster, args.db)
    connector_db = resolved["connector_db"]

    # 拉取 connector
    try:
        result = fetch_connectors(args.cluster, connector_db, args.include_master)
    except RuntimeError as e:
        # 若失败且是自动推断的，尝试用 'mysql' 兜底
        if not args.db and connector_db != "mysql":
            print(f"[get_db_connectors] ⚠️  使用 {connector_db} 失败，降级尝试 db=mysql", file=sys.stderr)
            try:
                result = fetch_connectors(args.cluster, "mysql", args.include_master)
                resolved["connector_db"] = "mysql"
                resolved["analysis_shards"] = ["mysql"]
            except RuntimeError as e2:
                print(f"[get_db_connectors] ⚠️  db=mysql 也失败，尝试 instance/get-by-cluster fallback", file=sys.stderr)
                result = _fallback_instance_list(args.cluster, args.include_master)
                if result is None:
                    print(str(e2), file=sys.stderr)
                    sys.exit(1)
                resolved["connector_db"] = "mysql"
                resolved["analysis_shards"] = ["mysql"]
        else:
            print(f"[get_db_connectors] ⚠️  fetch_connectors 失败，尝试 instance/get-by-cluster fallback", file=sys.stderr)
            result = _fallback_instance_list(args.cluster, args.include_master)
            if result is None:
                print(str(e), file=sys.stderr)
                sys.exit(1)

    # ── 构建 _meta，明确区分 connector_db 和 analysis_shards ──
    shards = resolved["shards"]
    shard_warning = (
        f"分库分表集群（{len(shards)} 个分片）：connector_db={resolved['connector_db']} 仅用于定位节点，"
        f"get-table-stats / get-index-stats 必须遍历 analysis_shards 全部 {len(shards)} 个分片，"
        f"否则会漏掉数据量差异悬殊的分片（历史案例：rows_examined 差 3000 倍）"
    ) if shards else None

    result["_meta"] = {
        "cluster_type":    resolved["cluster_type"],
        # connector_db：仅用于拉取 connector（定位节点 IP），不等于分析范围
        "connector_db":    resolved["connector_db"],
        "logical_db":      resolved["logical_db"],
        # shards：所有物理分片库名
        "shards":          shards,
        # analysis_shards：后续 table-stats/index-stats 必须覆盖的完整分片列表
        #   分库分表集群 = shards 全集（必须逐一遍历）
        #   普通集群     = [connector_db]（单库，无需遍历）
        "analysis_shards": resolved["analysis_shards"],
        # shard_warning：非 None 时表示调用方必须遍历 analysis_shards
        "shard_warning":   shard_warning,
    }

    output_str = json.dumps(result, ensure_ascii=False, indent=2)

    # 写文件
    if args.output and args.run_id:
        raw_dir = Path(args.output) / args.run_id / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        out_file = raw_dir / "get_db_connectors.json"
        out_file.write_text(output_str, encoding="utf-8")
        print(f"[get_db_connectors] ✅ 已写入 {out_file}", file=sys.stderr)

    print(output_str)

    # ── stderr 摘要 ──
    try:
        slaves = list_slave_connectors(result)
        ct = resolved["cluster_type"]
        print(
            f"[get_db_connectors] 集群类型={ct}  connector_db={resolved['connector_db']}  slave={len(slaves)}个",
            file=sys.stderr,
        )
        for c in result.get("data", []):
            role = c.get("role", "?")
            vm   = c.get("vm_name", "?")
            ip   = c.get("ip", "?")
            port = c.get("port", "?")
            print(f"  [{role}] {vm}  {ip}:{port}", file=sys.stderr)

        if shards:
            print("", file=sys.stderr)
            print(f"[get_db_connectors] {'='*60}", file=sys.stderr)
            print(f"[get_db_connectors] ⚠️  分库分表集群，共 {len(shards)} 个物理分片", file=sys.stderr)
            print(f"[get_db_connectors]    connector_db（仅定位节点）: {resolved['connector_db']}", file=sys.stderr)
            print(f"[get_db_connectors]    analysis_shards（必须遍历）: {resolved['analysis_shards']}", file=sys.stderr)
            print(f"[get_db_connectors]    ❌ 直接用 connector_db 做 table-stats 只会看到一个分片！", file=sys.stderr)
            print(f"[get_db_connectors]    ✅ 后续请对 analysis_shards 每个分片分别调用 get-table-stats/get-index-stats", file=sys.stderr)
            print(f"[get_db_connectors] {'='*60}", file=sys.stderr)
        elif slaves:
            print(f"[get_db_connectors] ⚠️  诊断时请覆盖所有节点，勿只取第一个", file=sys.stderr)
    except Exception as e:
        print(f"[get_db_connectors] ⚠️  摘要输出失败: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
