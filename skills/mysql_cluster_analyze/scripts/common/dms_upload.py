#!/usr/bin/env python3
"""
dms_upload.py — 上传 AI 报告到 DMS 内部文件服务

将本地 HTML 文件上传到 DMS，通过 COS 持久存储，返回公开访问 URL。

上传接口：POST https://dms.devops.xiaohongshu.com/dms-api/v1/ai-files/upload
访问 URL：https://dms.devops.xiaohongshu.com/dms-api/v1/ai-files/<file_name>

文件命名规范（由调用方保证）：
  <集群名>-<分析开始时间yyyymmddHHMMSS>-<故障类型>.html
  示例：risk_venom-20260326200213-replication_lag.html

鉴权：上传接口固定使用 dms-claw-token header，token 值优先取 DMS_AI_TOKEN，兜底 DMS_CLAW_TOKEN。
      注意：DMS-AI-Token 仅允许访问 /dms-api/ai-api/v1/ 路径，而上传接口在 /dms-api/v1/，
            因此两种 token 都通过 dms-claw-token header 传入（上传接口两者均认）。

调用方式：
  python3 dms_upload.py /path/to/report.html [--file-name custom_name.html]
  from common.dms_upload import upload_file
"""

import argparse
import os
import sys
from enum import Enum
from pathlib import Path


# ── 常量 ────────────────────────────────────────────────────────────────────

DMS_BASE_URL = "https://dms.devops.xiaohongshu.com"
UPLOAD_ENDPOINT = f"{DMS_BASE_URL}/dms-api/v1/ai-files/upload"
ACCESS_URL_TEMPLATE = f"{DMS_BASE_URL}/dms-api/v1/ai-files/{{file_name}}"

# 鉴权 token：优先 DMS_AI_TOKEN，兜底 DMS_CLAW_TOKEN
_AI_TOKEN_KEY   = "DMS_AI_TOKEN"
_CLAW_TOKEN_KEY = "DMS_CLAW_TOKEN"


class FaultType(str, Enum):
    """故障类型枚举，用于文件命名"""
    REPLICATION_LAG  = "replication_lag"   # 主从复制延迟
    CPU_HIGH         = "cpu_high"           # CPU 使用率过高
    SLOW_QUERY       = "slow_query"         # 慢查询
    DISK_FULL        = "disk_full"          # 磁盘容量告警
    CONN_SPIKE       = "conn_spike"         # 连接数突增
    PROCESS_DOWN     = "process_down"       # 进程 Down
    NET_BANDWIDTH    = "net_bandwidth"      # 网络带宽超限
    SEMI_SYNC        = "semi_sync"          # 半同步状态异常
    DTS_LAG          = "dts_lag"            # DTS 同步延迟
    UNKNOWN          = "unknown"            # 未知/通用


# ── 核心函数 ─────────────────────────────────────────────────────────────────

def build_file_name(cluster: str, start_time_str: str, fault_type: FaultType | str) -> str:
    """
    构造标准化文件名。

    Args:
        cluster:        集群名，如 risk_venom
        start_time_str: AI 开始分析的时间，格式 yyyymmddHHMMSS，如 20260326200213
        fault_type:     故障类型，FaultType 枚举或字符串

    Returns:
        文件名，如 risk_venom-20260326200213-replication_lag.html
    """
    # 集群名中的特殊字符替换为下划线（防止影响文件名解析）
    safe_cluster = cluster.replace('/', '_').replace('\\', '_')
    fault_str = fault_type.value if isinstance(fault_type, FaultType) else str(fault_type)
    return f"{safe_cluster}-{start_time_str}-{fault_str}.html"


def _load_env_file() -> dict:
    """从 workspace .env 文件加载 key=value 对（仅作兜底）。"""
    # .env 固定在 ~/.openclaw/workspace/.env
    env_file = Path.home() / '.openclaw' / 'workspace' / '.env'
    result: dict = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _get_token() -> str:
    """
    获取上传所用的 token 值（固定通过 dms-claw-token header 传入）。

    优先顺序：DMS_AI_TOKEN → DMS_CLAW_TOKEN
    两种 token 均通过 dms-claw-token header 传入——上传接口在 /dms-api/v1/ 路径，
    DMS-AI-Token header 仅限 /dms-api/ai-api/v1/ 路径，因此不直接使用。

    Returns:
        token 值字符串
    """
    env_file_cache: dict | None = None

    def _read(key: str) -> str:
        nonlocal env_file_cache
        val = os.environ.get(key, '').strip()
        if not val:
            if env_file_cache is None:
                env_file_cache = _load_env_file()
            val = env_file_cache.get(key, '').strip()
        return val

    token = _read(_AI_TOKEN_KEY) or _read(_CLAW_TOKEN_KEY)
    if token:
        return token

    raise RuntimeError(
        f"[dms_upload] 未找到 {_AI_TOKEN_KEY} 或 {_CLAW_TOKEN_KEY}，\n"
        f"  请在环境变量或 .env 中配置其中之一：\n"
        f"  export {_AI_TOKEN_KEY}=<your-dms-ai-token>\n"
        f"  export {_CLAW_TOKEN_KEY}=<your-dms-claw-token>"
    )


def upload_file(file_path: str, file_name: str | None = None) -> str:
    """
    上传单个文件到 DMS 文件服务。

    Args:
        file_path: 本地文件绝对路径
        file_name: 上传后的文件名（可选）。
                   未传则使用 file_path 的原始文件名。
                   推荐通过 build_file_name() 构造规范名称。

    Returns:
        文件公开访问 URL，如：
        https://dms.devops.xiaohongshu.com/dms-api/v1/ai-files/risk_venom-20260326200213-replication_lag.html

    Raises:
        FileNotFoundError: 本地文件不存在
        RuntimeError: 上传失败（含详细错误信息）
    """
    import urllib.request
    import urllib.parse

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"[dms_upload] 文件不存在：{file_path}")

    final_name = file_name or path.name
    token = _get_token()

    print(f"[dms_upload] 开始上传：{path.name} → {final_name}")

    # ── 构造 multipart/form-data ─────────────────────────────────
    boundary = "----DmsUploadBoundary7Ma4YWxkTrZu0gW"
    file_content = path.read_bytes()

    # RFC 2046 multipart body
    body_parts = [
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file_name"\r\n\r\n'
        f"{final_name}\r\n",
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{final_name}"\r\n'
        f"Content-Type: text/html; charset=utf-8\r\n\r\n",
    ]
    body = (
        "".join(body_parts).encode("utf-8")
        + file_content
        + f"\r\n--{boundary}--\r\n".encode("utf-8")
    )

    req = urllib.request.Request(
        UPLOAD_ENDPOINT,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "dms-claw-token": token,
        },
        method="POST",
    )

    try:
        import json as _json
        import urllib.error as _uerr
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
            resp_json = _json.loads(resp_body)
    except _uerr.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"[dms_upload] HTTP {e.code} 上传失败：{body_text[:300]}")
    except Exception as e:
        raise RuntimeError(f"[dms_upload] 请求失败：{e}")

    # ── 解析响应 ─────────────────────────────────────────────────
    # DMS 上传接口成功响应：{"code": 0, "data": {"url": "..."}}
    code = resp_json.get("code", -1)
    if code != 0:
        msg = resp_json.get("message") or resp_json.get("userMessage") or str(resp_json)
        raise RuntimeError(f"[dms_upload] 上传失败 code={code}：{msg}")

    data = resp_json.get("data") or {}
    url = None
    if isinstance(data, dict):
        url = data.get("url")
    elif isinstance(data, str) and data.startswith("http"):
        url = data

    if not url:
        # 兜底：自己拼接访问 URL（服务端文件名与请求一致）
        encoded = urllib.parse.quote(final_name, safe='-_.~')
        url = ACCESS_URL_TEMPLATE.format(file_name=encoded)
        print(f"[dms_upload] ⚠️  响应中未含 url 字段，使用构造 URL：{url}")
        print(f"[dms_upload]    原始响应：{resp_json}")

    print(f"[dms_upload] ✅ 上传完成：{url}")
    return url


# ── CLI 入口 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="上传 AI 报告 HTML 到 DMS 文件服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 直接上传，使用原始文件名
  python3 dms_upload.py /tmp/report.html

  # 指定规范文件名
  python3 dms_upload.py /tmp/report.html --file-name risk_venom-20260326200213-replication_lag.html

  # 通过 build_file_name 构造文件名（在 Python 代码中）
  from common.dms_upload import build_file_name, FaultType, upload_file
  name = build_file_name("risk_venom", "20260326200213", FaultType.REPLICATION_LAG)
  url  = upload_file("/tmp/report.html", name)
        """,
    )
    parser.add_argument("file_path", help="本地 HTML 文件路径")
    parser.add_argument(
        "--file-name",
        default=None,
        help="上传后的文件名（不传则使用原始文件名）",
    )
    args = parser.parse_args()

    try:
        result_url = upload_file(args.file_path, args.file_name)
        print(result_url)
    except (FileNotFoundError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
