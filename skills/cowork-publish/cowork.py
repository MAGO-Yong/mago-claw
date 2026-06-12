#!/usr/bin/env python3
"""
cowork-cli — 在小红书 Cowork 平台部署 + 发布"作品"

子命令：
  pack       打包源码为可部署 zip（按 Guard 规范）
  precheck   对源码或 zip 跑 13 项 Guard 红线检查
  upload     上传 zip 到 OSS（拿 fileId）
  deploy     上传 + 触发部署 + 等待 RUNNING（返回 deploymentId/appId/accessUrl）
  publish    完整一键：deploy + 上传封面 + save（创建/更新作品）
  list       列出我已发布的作品
  detail     查看作品详情
  delete     删除作品
  status     查部署状态
  redeploy   对已有 work 重新部署（保留 appId/alias）

全链路：
  1) GET edith/api/media/v1/upload/web/permit  → permit
  2) PUT permit.uploadAddr/permit.fileIds[0]   → 实际文件
  3) POST cowork/works/deploy  body={fileIdJson} → deploymentId
  4) 轮询 cowork/works/deployment/{id}/status   → appId / accessUrl
  5) POST cowork/works/save                    → workId
"""

import argparse
import datetime
import io
import json
import os
import random
import re
import string
import sys
import time
import uuid
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

try:
    import requests
except ImportError:
    sys.stderr.write("缺少 requests，请: pip install requests --break-system-packages\n")
    sys.exit(127)

# OpenClaw pod 出口走 forward proxy（MITM 自签证书），关闭校验。
# 本地跑可设 COWORK_VERIFY_SSL=1 启用校验。
_VERIFY_SSL = os.environ.get("COWORK_VERIFY_SSL", "0") == "1"
if not _VERIFY_SSL:
    try:
        from urllib3.exceptions import InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    except Exception:
        pass

# -----------------------------------------------------------------------------
# 版本号（单一真相源：SKILL.md frontmatter 的 version 字段）
# -----------------------------------------------------------------------------
def _read_skill_version() -> str:
    """从同目录 SKILL.md 的 YAML frontmatter 中读取 version 字段。
    找不到时 fallback 为 '0.0.0'。"""
    skill_md = Path(__file__).resolve().parent / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
        if text.startswith("---"):
            end = text.index("---", 3)
            for line in text[3:end].splitlines():
                if line.strip().startswith("version:"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "0.0.0"


__version__ = _read_skill_version()

# -----------------------------------------------------------------------------
# 常量
# -----------------------------------------------------------------------------
COWORK_HOST = "https://city.xiaohongshu.com"
COWORK_API = f"{COWORK_HOST}/oasis/api/oa-office/cowork"
EDITH_HOST = "https://edith.xiaohongshu.com"
COWORK_WEB = "https://cowork.xiaohongshu.com"

# alias 改完后，路由层（网关）需要约 5s 才会把新别名同步到生效状态。
# 在这之前把 /s/<new-alias>/ 或 /f/<new-alias>/ 返回给用户，用户打开会看到「不存在」。
# 所以设置/修改 alias 成功后统一等这么久再返回 URL（可用 COWORK_ALIAS_PROPAGATION_SEC 覆盖）。
ALIAS_PROPAGATION_SEC = float(os.environ.get("COWORK_ALIAS_PROPAGATION_SEC", "5"))

# Cowork 项目顶级约定：所有 cowork scaffold / transform / dev / publish 项目都应在这里。
# Plugin scan / agent system prompt 都遵这个约定，外部不扫避免误收。
COWORK_PROJECT_ROOT = Path(os.environ.get(
    "COWORK_PROJECT_ROOT",
    os.path.expanduser("~/.openclaw/workspace/cowork"),
))
LEGACY_PROJECT_ROOT = Path(os.path.expanduser("~/.openclaw/workspace/code"))


def _ensure_project_root() -> Path:
    COWORK_PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    return COWORK_PROJECT_ROOT


# 作品详情页 URL obfuscation，与 Cowork Web 前端 encodeWorkId 对齐：
#   obfuscated = (workId ^ 0x6e2d) >>> 0
#   encoded = base64url(ascii('5a3c' + hex(obfuscated))).rstrip('=')
# 例：workId=30999 → obfuscated=0x173a → '5a3c173a' → 'NWEzYzE3M2E'
# 注意：历史上曾误用 0xe2d，并从早期样本推断出 '5a3c6' 前缀；真实前缀是 '5a3c'，
#      `6` 属于 0x6e2d 混淆后 hex 的首位，并非固定前缀。
COWORK_APP_URL_XOR = 0x6e2d
COWORK_APP_URL_PREFIX = "5a3c"


def cowork_app_url(work_id) -> Optional[str]:
    """返回 cowork 作品详情页 URL：https://cowork.xiaohongshu.com/app/<encoded>。"""
    if work_id is None:
        return None
    try:
        n = int(work_id)
    except Exception:
        return None
    import base64 as _b64
    obf = n ^ COWORK_APP_URL_XOR
    raw = f"{COWORK_APP_URL_PREFIX}{obf:x}".encode("ascii")
    enc = _b64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{COWORK_WEB}/app/{enc}"

BIZ_NAME = "ep"
SCENE = "oa_attachments"

# Guard 规范：监听端口
GUARD_PORT = 3000

# 标签 enum（前端按钮 → 后端 key）。
#
# ⚠以 cowork 平台 web bundle (fe-static.xhscdn.com/.../index.*.js) 为准，共 9 个。
# 如有客户端（如 Coral Studio）需要复用同一份映射，请直接读取本字典，
# 不要在客户端再硬编码一份。
SCENE_TAGS = {
    "效率提升": "efficiency_improvement",
    "内容生成": "content_generation",
    "数据分析": "data_analysis",
    "研究洞察": "research_insight",
    "沟通协作": "communication_collaboration",
    "代码开发": "code_development",
    "设计创作": "design_creativity",
    "趣味创意": "fun_creativity",
    "其他": "other",
}

# 可见性
# Visibility 枚举名与 cowork 后端一致（8b8 会 Seal x Cowork 接口调整以后的新名字）。
# 旧名字：ALL / PARTIAL / SELF_ONLY
# 新名字：PUBLIC / DEPARTMENTS / SELF_ONLY
VISIBILITY = {
    "all": "PUBLIC",        # 全公司可见（旧 ALL）
    "partial": "DEPARTMENTS",  # 部分可见（旧 PARTIAL）
    "self": "SELF_ONLY",    # 仅自己可见
}
# 兼容：只要用户或者老 manifest 还传旧名字，自动 normalize 为新名字
VISIBILITY_LEGACY = {
    "ALL": "PUBLIC",
    "PARTIAL": "DEPARTMENTS",
    "SELF_ONLY": "SELF_ONLY",
    "PUBLIC": "PUBLIC",
    "DEPARTMENTS": "DEPARTMENTS",
}


def normalize_visibility(v: Optional[str]) -> str:
    if not v:
        return "SELF_ONLY"
    if v in VISIBILITY:
        return VISIBILITY[v]
    if v in VISIBILITY_LEGACY:
        return VISIBILITY_LEGACY[v]
    return v

WORK_TYPES = {
    "deploy": "COWORK_DEPLOY",   # zip 部署型
    "link": "EXTERNAL_LINK",     # 外链型（猜测，需要验证）
    "skill": "SKILL",            # skill 型
}


# -----------------------------------------------------------------------------
# 诊断日志（卷档）
# -----------------------------------------------------------------------------
# 问题背景：publish hang 后 gateway 可能整个死，拿不到调用肌肊。
# 在 cowork.py 内部把所有关键 stage 以 append-only 写入固定路径，
# 卸下后可以用 `cat /tmp/cowork-publish-*.log` 拿到完整河流。
#
# 存放路径：/tmp/cowork-publish-YYYYMMDD-HHMMSS-PID.log
# 调用点：dlog("event", **fields)
import tempfile as _tf  # noqa: F401  (kept for backward compat if any caller uses)

_DIAG_LOG_PATH: "str | None" = None


def _diag_log_path() -> str:
    """Lazy-init 卷档路径。进程内使用同一个文件，便于事后拼接该进程所有事件。"""
    global _DIAG_LOG_PATH
    if _DIAG_LOG_PATH is None:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        _DIAG_LOG_PATH = f"/tmp/cowork-publish-{ts}-{os.getpid()}.log"
        # 首次写入 process-level metadata，下次出问题能拿到环境
        try:
            argv = " ".join(sys.argv)
            with open(_DIAG_LOG_PATH, "a") as f:
                f.write(
                    json.dumps(
                        {
                            "event": "process.started",
                            "ts": datetime.datetime.now().isoformat(),
                            "pid": os.getpid(),
                            "ppid": os.getppid(),
                            "argv": argv,
                            "cwd": os.getcwd(),
                            "python": sys.version.split()[0],
                            "platform": sys.platform,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception:
            pass
    return _DIAG_LOG_PATH


def dlog(event: str, **fields) -> None:
    """写一条诊断日志。不报错，不 block。应用场景：
    - 任何潜在长耗时子过程前后（npm ci / OSS upload / HTTP request 等）
    - 任何会 fail 的关键点（precheck / pack / deploy / save）
    """
    try:
        rec = {
            "event": event,
            "ts": datetime.datetime.now().isoformat(),
            "pid": os.getpid(),
            **fields,
        }
        with open(_diag_log_path(), "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            f.flush()  # 避免 hang 后丢最后一条
    except Exception:
        # 诊断日志决不能影响主流程
        pass


# -----------------------------------------------------------------------------
# 工具
# -----------------------------------------------------------------------------
def err(msg, code=1):
    dlog("err", msg=msg, code=code)
    sys.stderr.write(f"✗ {msg}\n")
    sys.stderr.flush()  # 立即输出，避免被块缓冲、用户看着像卡住
    sys.exit(code)


def ok(msg):
    dlog("ok", msg=msg)
    sys.stderr.write(f"✓ {msg}\n")
    sys.stderr.flush()


def info(msg):
    dlog("info", msg=msg)
    sys.stderr.write(f"  {msg}\n")
    sys.stderr.flush()


def wait_alias_propagation(new_alias: Optional[str] = None, seconds: Optional[float] = None) -> None:
    """alias 设置/修改成功后，等待路由层把新别名同步到生效状态再返回 URL。

    后端 save / set-alias 返回成功 ≠ 新别名立刻可访问——网关同步约需 5s。在这之前
    把 /s/<new-alias>/ 给用户，用户打开会看到「页面不存在」。这里统一等待并给一句
    友好的等待文案，避免用户拿到一个暂时打不开的链接。

    seconds 默认取 ALIAS_PROPAGATION_SEC（环境变量 COWORK_ALIAS_PROPAGATION_SEC 可覆盖）；
    设为 0 / 负数则跳过等待。
    """
    wait = ALIAS_PROPAGATION_SEC if seconds is None else seconds
    if wait <= 0:
        return
    tip = f"⏳ 别名已设置{f'（{new_alias}）' if new_alias else ''}，正在等待 ~{int(round(wait))}s 让访问链接全网生效…"
    dlog("alias.propagation.wait", alias=new_alias, seconds=wait)
    info(tip)
    time.sleep(wait)
    info("✅ 链接已生效，现在可以直接打开访问了")


def load_cookies() -> dict:
    """
    从环境取 cookie（运行在 OpenClaw pod 里默认是带 SSO 的）。
    Pod 出口走 forward proxy，会自动注入 cookie；本地跑则需要 COWORK_COOKIE。
    """
    raw = os.environ.get("COWORK_COOKIE", "").strip()
    if not raw:
        return {}
    out = {}
    for part in raw.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            out[k] = v
    return out


def session() -> requests.Session:
    s = requests.Session()
    s.verify = _VERIFY_SSL
    cookies = load_cookies()
    if cookies:
        s.cookies.update(cookies)
    s.headers.update({
        "Accept": "application/json, text/plain, */*",
        "User-Agent": f"cowork-cli/{__version__} (+OpenClaw)",
        "Referer": "https://cowork.xiaohongshu.com/",
        "Origin": "https://cowork.xiaohongshu.com",
    })
    return s


# api_call 默认超时：连接 10s + 读写 60s。背后接口遇到问题时请不要让
# cowork.py 子进程永远等。在 kw 中传 timeout= 可覆盖。
DEFAULT_API_TIMEOUT = (10, 60)

def api_call(method: str, path: str, **kw):
    """统一调 cowork oasis API，拿 data。"""
    s = kw.pop("session", None) or session()
    kw.setdefault("timeout", DEFAULT_API_TIMEOUT)
    url = path if path.startswith("http") else f"{COWORK_API}{path}"
    dlog("http.req", method=method, url=url, timeout=kw.get("timeout"))
    _t0 = time.time()
    try:
        r = s.request(method, url, **kw)
    except Exception as e:
        dlog("http.exc", method=method, url=url, dur_s=round(time.time()-_t0, 2), exc=type(e).__name__, msg=str(e)[:300])
        raise
    dlog("http.res", method=method, url=url, status=r.status_code, dur_s=round(time.time()-_t0, 2), body_len=len(r.text))
    if r.status_code >= 400:
        err(f"{method} {path} -> {r.status_code}\n{r.text[:600]}")
    try:
        j = r.json()
    except Exception:
        err(f"{method} {path} non-JSON: {r.text[:300]}")
    if not j.get("success", True):
        err(f"{method} {path} fail: {j.get('errorMsg') or j.get('alertMsg') or r.text[:300]}")
    return j.get("data")


# -----------------------------------------------------------------------------
# §1 上传：permit → PUT → fileId
# -----------------------------------------------------------------------------
def get_permit(file_format: str, file_count: int = 1, s=None) -> dict:
    """
    GET edith.xhs/api/media/v1/upload/web/permit
    返回 uploadTempPermits[0]：{cloudType, fileIds, token, uploadAddr, expireTime, uploadId, qos, bucket}
    """
    s = s or session()
    # 模拟前端，user_id__rand。user_id 拿不到也 OK（随便填，主要是去重）
    t = f"{int(time.time()*1000)}__{random.randint(100000, 9999999)}"
    params = {
        "bizName": BIZ_NAME,
        "scene": SCENE,
        "fileCount": file_count,
        "biz_name": BIZ_NAME,
        "file_format": file_format,
        "file_count": file_count,
        "version": 1,
        "subsystem": "web_resource",
        "_t": t,
    }
    url = f"{EDITH_HOST}/api/media/v1/upload/web/permit?{urlencode(params)}"
    # 严格超时：防 OSS permit 接口挂起后永远等，会让 plugin spawn 不退出。
    r = s.get(url, timeout=20)
    r.raise_for_status()
    j = r.json()
    if not j.get("success"):
        err(f"permit fail: {j}")
    data = j.get("data") or {}
    permits = data.get("uploadTempPermits") or []
    if not permits:
        result = data.get("result") or {}
        err(f"no permit returned: {result.get('message') or data}")
    return permits[0]


def ros_put(permit: dict, body: bytes, content_type: str, s=None) -> str:
    """
    将文件 PUT 到 ROS。返回 fileId（permit.fileIds[0]）。
    猜测：走 ros-upload.xiaohongshu.com，header 带 X-Cos-Security-Token 或 Authorization=permit.token。
    需要真实抓 PUT 才能 100% 确认；这里实现两种回退。
    """
    s = s or session()
    file_id = permit["fileIds"][0]
    addr = permit["uploadAddr"]
    token = permit["token"]
    if not addr.startswith("http"):
        addr = "https://" + addr
    # 尝试方案 A: PUT /<fileId>
    put_url = f"{addr}/{file_id}"
    # ROS 通常用 X-Cos-Security-Token (兼容腾讯 COS) 或 Authorization
    headers = {
        "Content-Type": content_type,
        "X-Cos-Security-Token": token,
        "Authorization": token,
    }
    # OSS upload 严格超时：连接 10s + 传输 300s（理论上 100MB zip 在内网也足够）。
    # 不加 timeout 会让 requests 永远等 → cowork.py 子进程不退出 → plugin spawn Promise 不 resolve。
    UPLOAD_TIMEOUT = (10, 300)
    r = s.put(put_url, data=body, headers=headers, timeout=UPLOAD_TIMEOUT)
    if r.status_code >= 400:
        # 方案 B: 试一下 POST 表单上传（少数对象存储用 multipart）
        files = {"file": (Path(file_id).name, body, content_type)}
        r = s.post(addr, files=files, data={"token": token, "key": file_id}, timeout=UPLOAD_TIMEOUT)
        if r.status_code >= 400:
            err(f"ROS upload fail: PUT {put_url} -> {r.status_code}\n{r.text[:600]}")
    return file_id


def upload_file(path: str, mime_type: Optional[str] = None, s=None) -> dict:
    """
    高层 API：上传单个文件，返回 {fileId, business, scene, name, mimeType, url}
    """
    p = Path(path)
    if not p.exists():
        err(f"file not found: {path}")
    ext = p.suffix.lstrip(".").lower()
    if not mime_type:
        mime_type = {
            "zip": "application/zip",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
        }.get(ext, "application/octet-stream")
    s = s or session()
    _size = p.stat().st_size
    _size_h = f"{_size/1024/1024:.1f}MB" if _size >= 1024*1024 else f"{_size/1024:.0f}KB"
    info(f"⇡ 申请上传凭证({ext}) ...")
    dlog("upload.permit.start", ext=ext, file=str(p), size_bytes=_size)
    _t0 = time.time()
    permit = get_permit(ext, s=s)
    dlog("upload.permit.ok", dur_s=round(time.time()-_t0, 2), upload_addr=permit.get("uploadAddr"))
    info(f"⇡ 上传 {p.name}（{_size_h}）中，请稍候 ...")
    dlog("upload.put.start", file=p.name, size_bytes=_size, upload_addr=permit.get("uploadAddr"))
    _t0 = time.time()
    file_id = ros_put(permit, p.read_bytes(), mime_type, s=s)
    _dur = round(time.time()-_t0, 1)
    info(f"⇡ 上传完成（{_size_h}, 耗时 {_dur}s）")
    dlog("upload.put.ok", file=p.name, dur_s=_dur, file_id=file_id)
    return {
        "fileId": file_id,
        "business": BIZ_NAME,
        "scene": SCENE,
        "name": p.name,
        "mimeType": mime_type,
        # URL 是预签名 preview, save 时需要
        "url": "",
    }


# -----------------------------------------------------------------------------
# §2 部署：deploy + 轮询 status
# -----------------------------------------------------------------------------
def deploy_zip(
    zip_fileid: str,
    zip_name: str = "app.zip",
    work_id: Optional[int] = None,
    deployment_id: Optional[int] = None,
    ext_platform_id: Optional[str] = None,
    deploy_source: str = "SEAL",
    s=None,
) -> dict:
    """
    POST cowork/community/works/deploy
    body: {
        fileIdJson: "<json string>",
        deploymentId?: <int>,           # 重新部署且作品尚未发布时传——复用同一台机器/部署记录
        workId?: <int>,                 # 编辑已发布作品的重新部署时传
        extPlatformId?: "cw_proj_xxx",  # Seal 侧项目唯一 ID（新建部署时存入）
        deploySource?: "SEAL" | "COWORK" | "OMNI"  # 平台源，Seal 链路固定 SEAL
    }

    三种入口（deploymentId / workId 二选一或都不传）：
      - 首次部署（新建作品）：都不传，仅 fileIdJson → 创建一条新部署记录
      - 新建作品重新部署：传 deploymentId → **复用该部署记录（同一台机器重试，不新建僵尸机器）**
      - 编辑已发布作品：传 workId → 找该作品的部署记录复用
    返回: {deploymentId, deploymentStatus, appId, alias, workId, ...}
    """
    s = s or session()
    file_id_json = json.dumps({
        "fileId": zip_fileid,
        "business": BIZ_NAME,
        "scene": SCENE,
        "name": zip_name,
    }, ensure_ascii=False)
    body = {
        "fileIdJson": file_id_json,
        "deploySource": deploy_source,
    }
    if deployment_id is not None:
        body["deploymentId"] = int(deployment_id)
    if work_id is not None:
        body["workId"] = int(work_id)
    if ext_platform_id:
        body["extPlatformId"] = ext_platform_id
    return api_call(
        "POST",
        "/community/works/deploy",
        json=body,
        session=s,
    )


def deploy_zip_reuse_or_new(
    zip_fileid: str,
    zip_name: str = "app.zip",
    *,
    reuse_deployment_id: Optional[int] = None,
    ext_platform_id: Optional[str] = None,
    deploy_source: str = "SEAL",
    s=None,
) -> dict:
    """首发/重试用：优先复用 reuse_deployment_id 的机器；该记录已失效则自动降级为新建部署。

    解决「首发 deploy 失败 → 修代码重试时不带 ID → 后端每次新开机器，遗留一堆失败僵尸机」。
    复用前先 deployment_status 探活：
      - 记录存在 → 带 deploymentId deploy，复用同一台机器重试
      - 记录不存在（机器久未关联作品被平台清理）→ 自动降级为不带 ID 的新建部署
    返回结构同 deploy_zip，并附加 _reused（bool）/ _reuseFallback（被迫降级时为 True）。
    """
    s = s or session()
    use_id = None
    fallback = False
    if reuse_deployment_id is not None:
        try:
            st = deployment_status(int(reuse_deployment_id), s=s) or {}
            if st.get("deploymentId") or st.get("deploymentStatus"):
                use_id = int(reuse_deployment_id)
                info(f"♻️  复用历史部署机器 deploymentId={use_id}（避免新开机器）")
            else:
                fallback = True
        except SystemExit:
            # 探活失败（多为「部署记录不存在」——机器久未关联作品被清理）→ 降级新建
            fallback = True
        if fallback:
            info(f"ℹ️  历史 deploymentId={reuse_deployment_id} 已失效（机器可能被平台清理），"
                 "本次降级为新建部署")
    d = deploy_zip(
        zip_fileid, zip_name=zip_name,
        deployment_id=use_id,
        ext_platform_id=ext_platform_id,
        deploy_source=deploy_source,
        s=s,
    )
    if isinstance(d, dict):
        d["_reused"] = use_id is not None
        d["_reuseFallback"] = fallback
    return d


# -----------------------------------------------------------------------------
# §2.5 静态资源挂载（纯前端应用走轻量挂载，不占独立 Pod、不轮询）
# -----------------------------------------------------------------------------
# 部署类型（作品 workDeployType）：
#   APP_DEPLOY      应用部署（独立 Pod，走 deploy_zip + wait_deploy，历史链路）
#   STATIC_RESOURCE 静态资源挂载（纯前端，走 static_deploy，同步返回 MOUNT_SUCCESS）
WORK_DEPLOY_TYPE_APP = "APP_DEPLOY"
WORK_DEPLOY_TYPE_STATIC = "STATIC_RESOURCE"

# 哨兵：区分「参数未传（省略字段）」与「显式传 None（透传 null）」。
_UNSET = object()


def _file_id_json(zip_fileid: str, zip_name: str = "app.zip") -> str:
    """构造 deploy / static-deploy / detect 接口共用的 fileIdJson 字符串。"""
    return json.dumps({
        "fileId": zip_fileid,
        "business": BIZ_NAME,
        "scene": SCENE,
        "name": zip_name,
    }, ensure_ascii=False)


def detect_code_package_type(file_id_json: str, s=None) -> dict:
    """POST /community/works/detect-code-package-type

    服务端解包检测 zip 类型，返回:
      { "type": "STATIC_RESOURCE" | "APP_DEPLOY_CONVERTED" | "APP_DEPLOY_NOT_CONVERTED",
        "reason": "<判定原因>" }

    判定（服务端权威，与本地规则可能略有出入，以服务端为准）：
      STATIC_RESOURCE          所有扩展名在静态白名单内 + 不含构建/后端文件 + 根目录有 index.html
      APP_DEPLOY_CONVERTED     根目录同时有 health.sh / install.sh / start.sh（已转写）
      APP_DEPLOY_NOT_CONVERTED 以上都不满足

    用途：publish / redeploy 内部 pack 后调一次，按 type 自动分流静态 vs 应用部署；
    reason 用于失败诊断（告诉 agent 为什么不是静态包）。
    """
    s = s or session()
    # 该接口 body 直接是 fileIdJson 字符串（不是包一层 {fileIdJson: ...}），见接口文档
    return api_call(
        "POST",
        "/community/works/detect-code-package-type",
        json=file_id_json,
        session=s,
    )


def static_deploy(
    zip_fileid: str,
    zip_name: str = "app.zip",
    *,
    static_resource_id: Optional[int] = None,
    work_id: Optional[int] = None,
    ext_platform_id: Optional[str] = None,
    deploy_source: str = "SEAL",
    s=None,
) -> dict:
    """POST /community/works/static-deploy —— 纯前端静态资源挂载（同步，不轮询）。

    三种入口：
      - 新增部署：static_resource_id 和 work_id 都不传
      - 更新（按 staticResourceId）：传 static_resource_id
      - 更新（按 workId，编辑已发布作品重部署）：传 work_id

    返回 StaticResourceStatusDTO（同步，挂载完才返回）:
      { staticResourceId, workId, appId(sr_前缀), status(INIT/MOUNT_SUCCESS/MOUNT_FAILED),
        alias, accessUrl, rawAccessUrl, errorMessage, deploySource, extPlatformId }

    与 deploy_zip 的本质区别：静态挂载是同步的——返回时已经是终态（MOUNT_SUCCESS/FAILED），
    不需要 wait_deploy 轮询。
    """
    s = s or session()
    body = {
        "fileIdJson": _file_id_json(zip_fileid, zip_name),
        "deploySource": deploy_source,
    }
    if static_resource_id is not None:
        body["staticResourceId"] = int(static_resource_id)
    if work_id is not None:
        body["workId"] = int(work_id)
    if ext_platform_id:
        body["extPlatformId"] = ext_platform_id
    return api_call(
        "POST",
        "/community/works/static-deploy",
        json=body,
        session=s,
    )


def deployment_status(deployment_id: int, s=None) -> dict:
    return api_call("GET", f"/community/works/deployment/{deployment_id}/status", session=s)


DEFAULT_DEPLOY_TIMEOUT_S = 600  # 10 分钟；cowork 团队文档说“数分钟”起步。
DEPLOY_GRACE_EXTRA_S = 180      # 首发超时后宽限续轮询，尽力等到 RUNNING 再 save 作品。


def _emit_progress(deployment_id: int, status: str, *, extra: dict = None) -> None:
    """Plugin / 上游可 stream parse 的阶段提示行。

    格式: PROGRESS:{...json...}  (单行，走 stdout）
    输出后立即 flush，避免被 piped 调用方明提意外 buffer。
    """
    payload = {"deploymentId": deployment_id, "status": status, "ts": int(time.time() * 1000)}
    if extra:
        payload.update(extra)
    try:
        sys.stdout.write("PROGRESS:" + json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except Exception:
        pass


def wait_deploy(deployment_id: int, timeout_s: int = DEFAULT_DEPLOY_TIMEOUT_S,
                s=None, *, on_progress=None) -> dict:
    """轮询直到 RUNNING / FAILED / 超时。

    状态机：UPLOADING → INSTALLING → STARTING → RUNNING
    返回值（与之前不同：不再 hard err）：
      - RUNNING → dict 原样返 + ok=True
      - FAILED  → dict + ok=False + failed=True（上游负责拋错/提示用户）
      - 超时   → dict + ok=False + timedOut=True（保留 deploymentId / status）

    原因：hard err 丢掉 deploymentId，上游无法后续用 status 继续轮询。
    """
    s = s or session()
    _t_start = time.time()
    deadline = _t_start + timeout_s
    last = None
    last_dict = {}
    _last_heartbeat = _t_start
    while time.time() < deadline:
        d = deployment_status(deployment_id, s=s) or {}
        last_dict = d
        st = d.get("deploymentStatus")
        now = time.time()
        if st != last:
            info(f"⌛ deployment#{deployment_id} {st}")
            _emit_progress(deployment_id, st, extra={k: d.get(k) for k in ("accessUrl", "appId", "alias", "workId") if d.get(k)})
            if on_progress:
                try:
                    on_progress(d)
                except Exception:
                    pass
            last = st
            _last_heartbeat = now
        elif now - _last_heartbeat >= 15:
            # 状态长时间不变时也打个心跳，让用户知道仍在进行、没卡死。
            info(f"⌛ 仍在 {st or '部署'} ...（已等 {int(now - _t_start)}s）")
            _last_heartbeat = now
        if st == "RUNNING":
            d["ok"] = True
            return d
        if st == "FAILED":
            d["ok"] = False
            d["failed"] = True
            d.setdefault("errorMessage", d.get("errorMessage") or "(no error msg)")
            return d
        time.sleep(2)
    # 超时：不报错，返回结构化“still-deploying”。
    last_dict["ok"] = False
    last_dict["timedOut"] = True
    last_dict.setdefault("deploymentId", deployment_id)
    last_dict.setdefault("deploymentStatus", last)
    last_dict["message"] = (
        f"部署仍在进行中（已等 {timeout_s}s, 最后状态={last}）。"
        f"可用 `cowork.py status {deployment_id}` 继续查询。"
    )
    return last_dict


# -----------------------------------------------------------------------------
# §3 保存作品（save）
# -----------------------------------------------------------------------------
def save_work(
    *,
    name: str,
    one_line_intro: str,
    description: str,
    cover: dict,                 # upload_file() 返回的 dict（图片）
    deployment_id=_UNSET,        # 应用部署通道 ID；显式传 None=透传 null；不传=省略（后端不动）
    static_resource_id=_UNSET,   # 静态资源通道 ID；显式传 None=透传 null；不传=省略
    work_deploy_type: Optional[str] = None,    # APP_DEPLOY / STATIC_RESOURCE；按本次走的通道传准
    deployment_alias: Optional[str] = None,    # 旧字段名，向后兼容；新代码用 alias
    alias: Optional[str] = None,               # 访问别名（同时同步到应用 / 静态记录）
    scene_tags: Optional[list] = None,    # ["efficiency_improvement", ...]
    version: str = "1.0",
    visibility: str = "SELF_ONLY",         # PUBLIC / DEPARTMENTS / SELF_ONLY
    visible_user_ids: Optional[list] = None,
    visible_department_ids: Optional[list] = None,
    links: Optional[list] = None,          # [{title, url}]
    notify_on_publish: bool = False,
    work_type: str = "SEAL_DEPLOY",  # Seal 链路固定 SEAL_DEPLOY（COWORK_DEPLOY 是原 cowork web 链路）
    extra_images: Optional[list] = None,   # 额外图片（同 cover 结构，type 为 "other"）
    work_id: Optional[int] = None,         # 已存在的 work id（更新模式）
    display_in_community: Optional[bool] = None,  # SEAL_DEPLOY 固定 False，其他类型 True
    s=None,
) -> int:
    """
    POST cowork/community/works/save
    返回 workId（int）

    通道字段（deployment_id / static_resource_id）三态语义（关键）：
      - 不传该参数（默认 _UNSET）= body 省略该字段 = 后端复用已关联记录、不改动
      - 显式传 None = body 写 null = 透传清空意图（详情接口查出来另一通道恒 null，原样透传）
      - 传具体值 = 写该 ID
    更新作品本质是「作品 ↔ 部署资源关联」，与「更新部署/静态资源（实际部署代码）」解耦。
    推荐用法：调 detail 查出 deploymentId / staticResourceId（互斥，生效通道有值、另一通道 null），
    原样回填本函数（有就传值、null 就透传 null），不要本地拼凑或维护跨通道 ID。
    work_deploy_type 决定作品链接走哪条通道（STATIC_RESOURCE / APP_DEPLOY），按本次实际通道传准。
    """
    s = s or session()
    # normalize visibility 枚举（兼容旧名字）
    visibility = normalize_visibility(visibility)
    images = []
    if cover:
        c = dict(cover)
        c["type"] = "cover"
        images.append(c)
    if extra_images:
        for img in extra_images:
            d = dict(img)
            d.setdefault("type", "other")
            images.append(d)
    # display_in_community 默认根据 work_type 注入
    if display_in_community is None:
        display_in_community = (work_type != "SEAL_DEPLOY")
    body = {
        "name": name,
        "imagesJson": json.dumps(images, ensure_ascii=False),
        "sceneTagsJson": json.dumps(scene_tags or [], ensure_ascii=False),
        "version": version,
        "visibilityScope": visibility,
        "oneLineIntro": one_line_intro or "",
        "description": description or "",
        "linksJson": json.dumps(links or [], ensure_ascii=False),
        "notifyOnPublish": bool(notify_on_publish),
        "workType": work_type,
        "displayInCommunity": bool(display_in_community),
    }
    # 通道 ID 三态：_UNSET 省略 / None 透传 null / 有值传值。
    if deployment_id is not _UNSET:
        body["deploymentId"] = int(deployment_id) if deployment_id is not None else None
    if static_resource_id is not _UNSET:
        body["staticResourceId"] = int(static_resource_id) if static_resource_id is not None else None
    if work_deploy_type:
        body["workDeployType"] = work_deploy_type
    # alias：新字段 alias 优先；兼容旧 deployment_alias 传参
    _alias = alias if alias is not None else deployment_alias
    if _alias:
        body["alias"] = _alias
    if work_id:
        body["id"] = work_id
    if visible_user_ids:
        body["visibleUserIds"] = visible_user_ids
    if visible_department_ids:
        body["visibleDepartmentIds"] = visible_department_ids
    return api_call("POST", "/community/works/save", json=body, session=s)


# -----------------------------------------------------------------------------
# §3.5 单独设/改 alias
# -----------------------------------------------------------------------------
#
# 文档 4.3：PUT /community/works/deployment/{deploymentId}/alias
# - 需登录，仅部署创建人可操作
# - 部署状态必须 RUNNING
# - alias 全局唯一
# - **支持多次修改**，新 alias 覆盖旧的
# - alias 格式：3-32 位小写/数字/连字符，不能以连字符头尾，不能连续两个连字符
# ⚠️ 仅应用部署可用（用 deploymentId）；静态作品无 deploymentId。统一改别名走 save(alias=)，
#    本函数保留作「应用部署快速改别名」的补充入口，cmd_set_alias 已改走 save 不再调它。
ALIAS_REGEX = re.compile(r"^[a-z0-9](?:[a-z0-9]|-(?!-))*[a-z0-9]$")


def set_deployment_alias(deployment_id: int, alias: str, s=None) -> None:
    """PUT cowork/community/works/deployment/<id>/alias body={alias}（应用部署专用补充入口）

    日常改别名请用 save(alias=)（应用/静态统一）。本函数仅在已知是应用部署、想走快速
    通道时用。服务端校验失败会报 4xx：别名被占用、格式不合、部署未 RUNNING、非创建人。
    """
    if not (3 <= len(alias) <= 32) or not ALIAS_REGEX.match(alias):
        err(f"别名不合法：{alias} (需 3-32 位小写字母/数字/-，不能以 - 开头/结尾，不能 --)")
    return api_call(
        "PUT",
        f"/community/works/deployment/{deployment_id}/alias",
        json={"alias": alias},
        session=s,
    )


# -----------------------------------------------------------------------------
# §4 打包 & 预检
# -----------------------------------------------------------------------------
GUARD_REQUIRED = ["install.sh", "start.sh", "health.sh"]

# Cowork 平台在用户 db.properties 文件中只会注入这 6 个 key。
# 任何其他 key（如 db.url / db.driver / db.schema / db.pool_size）都是不安全的幻想——
# 笨蛋模型会生成「请用户到管理面处配置 PG host/port」这种鬼话。
DB_PROPS_ALLOWED_KEYS = {"db.type", "db.host", "db.port", "db.username", "db.password", "db.database"}

# 允许的"build 产物"（zip 必须含）
GUARD_BUILD_HINTS = [
    ".next/standalone",
    "dist",
    "build",
    "out",
]

# SSO 红线：Hard Rule #4——所有项目必须接 SSO，索「Decrypted-Userinfo」
# header 引用。以下任一命中即认为接入了：
#   - python: Header(..., alias="Decrypted-Userinfo") / request.headers["decrypted-userinfo"]
#   - js/ts: req.headers['decrypted-userinfo'] / get("decrypted-userinfo")
#   - 模板内置 helper 名：_parse_sso_user / parse_sso_user / getUser/getCurrentUser
# 逻辑用‍‍正则匹配粗粒度：只要字面出现 "Decrypted-Userinfo" / "decrypted-userinfo" /
# "decrypted_userinfo" / "decryptedUserinfo" / 模板 helper 名其一，都认为过。
SSO_TOKEN_PATTERNS = [
    r"[Dd]ecrypted[-_]?[Uu]serinfo",      # header name 所有大小写变体
    r"decryptedUserinfo",                  # camelCase
    r"_parse_sso_user\b",                  # 模板内置 helper
    r"parse_sso_user\b",                   # 同上 no-prefix
    r"parseSsoUser\b",                     # camelCase
]
# SSO bypass 后门模式：扫到任一即拒绝。这些是“生产跳 SSO”后门的常见 cargo-cult：
#   - if APP_ENV == "sit" / SIT: return mock_user
#   - if DEV_SSO_BYPASS / SKIP_SSO / NO_AUTH == "1": return ...
#   - if NODE_ENV != "production" / process.env.NODE_ENV !== 'production'
#   - sit-dev / dev-sso / mock-sso 这类魔法值
SSO_BACKDOOR_PATTERNS = [
    # 环境变量 + sit / dev / mock 魔法值
    r"APP_ENV[\s\)\]]*[=!]=\s*['\"](?:sit|dev|development|local)['\"]",
    r"NODE_ENV[\s\)\]]*[=!]=[=]?\s*['\"](?:sit|dev|development|local)['\"]",
    r"NODE_ENV[\s\)\]]*[=!]==?\s*['\"]production['\"]",   # !== 'production' 同样问题
    # 开关名明显表示 bypass SSO
    r"DEV_SSO_BYPASS", r"SKIP_SSO", r"NO_AUTH", r"DISABLE_SSO", r"BYPASS_AUTH",
    # 魔法用户 ID / mock user
    r"['\"]sit-dev['\"]", r"['\"]dev-user['\"]", r"['\"]mock-user['\"]",
    # sso-email 这种自造 header 后门
    r"['\"]sso-email['\"]",
    # “userId” 字段紧接” anon/dev/mock/guest”类魔法值——这只在伪造用户时才会写
    r"['\"]userId['\"]\s*:\s*['\"](?:anon|anonymous|guest|demo|visitor|fake|mock)",
    # "if not user" + 紧跟 user = {...} 赋值 —— 纯 Python，不能跨行 grep，用下面 特征函数扫
]

# 跨行插件扫描模式：取“401 拦被改成 fallback”类代码
SSO_FALLBACK_REGEX = re.compile(
    r"if\s+not\s+user\s*:\s*\n\s*(?:#.*\n\s*)*user\s*=\s*[{(\[].*['\"](?:email|userId|name)['\"]",
    re.MULTILINE,
)
SSO_FALLBACK_REGEX_JS = re.compile(
    r"if\s*\(\s*!\s*user\s*\)\s*\{\s*\n\s*(?://.*\n\s*)*user\s*=\s*\{",
    re.MULTILINE,
)
# 扫描范围后缀
SSO_SCAN_EXTS = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
# 扫描时跳过的路径段
SSO_SCAN_SKIP_DIRS = ("node_modules", ".venv", "venv", "__pycache__",
                      "dist", ".next", ".turbo", ".cache", "build", "out",
                      ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache")
# 纯前端 SPA（无后端）体现：项目中根本没 .py / 后端脚本，只有前端文件。
# 这种容器中给它们临时略过 SSO 红线（后续改进：走 cookie / 最小后端代理）。
# 识别依据：同时满足「有 vite/SPA 项目特征」 & 「什么后端脚本都没」。


# 纯 SPA marker：模板生成的 server.cjs 会带 `@cowork-spa-host`。
# 过 SSO precheck 时，项目任一代码文件中出现该 marker，则跳过后端 SSO 检查。
# 业务加了后端 API 后会人工删 marker + 接 SSO。
SSO_SPA_MARKER = "@cowork-spa-host"


def _is_pure_spa(src_dir: str) -> bool:
    """项目是否为纯前端 SPA（跳过 SSO 红线）。识别依据：文件出现 marker。"""
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in SSO_SCAN_SKIP_DIRS]
        for f in files:
            if not f.endswith(SSO_SCAN_EXTS) and not f.endswith((".cjs", ".mjs")):
                continue
            try:
                text = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if SSO_SPA_MARKER in text:
                return True
    return False


def _scan_sso_backdoor(src_dir: str) -> list[tuple[str, str]]:
    """扫描 SSO bypass 后门。返回「(文件路径, 命中行)」列表。空列表 → 通过。"""
    patterns = [re.compile(p) for p in SSO_BACKDOOR_PATTERNS]
    hits: list[tuple[str, str]] = []
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in SSO_SCAN_SKIP_DIRS]
        for f in files:
            if not f.endswith(SSO_SCAN_EXTS):
                continue
            try:
                text = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            rel = os.path.relpath(os.path.join(root, f), src_dir)
            # 1. 关键字扫
            for p in patterns:
                m = p.search(text)
                if m:
                    hits.append((rel, m.group(0)))
                    break
            else:
                # 2. 跨行 fallback 模式扫（401 拦被改成 anon fallback）
                m = SSO_FALLBACK_REGEX.search(text) or SSO_FALLBACK_REGEX_JS.search(text)
                if m:
                    snippet = m.group(0).split("\n", 1)[0].strip()[:80]
                    hits.append((rel, f"SSO fallback 模式：{snippet}..."))
    return hits


def _check_sso_compliance(src_dir: str) -> Optional[str]:
    """红线：后端场景必须看到 SSO 接入代码（Decrypted-Userinfo 引用）。

    返回 None 为通过；返回错误信息为错。同时检查 SSO bypass 后门。
    """
    # 1. SSO bypass 后门检查——优先报，即使是 SPA 也不能含后门
    backdoors = _scan_sso_backdoor(src_dir)
    if backdoors:
        lines = ["❌ [Hard Rule #4] 检测到 SSO bypass 后门（生产环境跳 SSO 是严重安全问题）："]
        for path, snippet in backdoors[:10]:
            lines.append(f"   {path}：{snippet}")
        if len(backdoors) > 10:
            lines.append(f"   … 还有 {len(backdoors) - 10} 处")
        lines.append("   本地调试请用浏览器插件（ModHeader / Header Editor）手动注入 Decrypted-Userinfo header，不要在代码里留 env bypass。")
        return "\n".join(lines)
    if _is_pure_spa(src_dir):
        # 模板标记为纯 SPA 项目——跳过（后续考虑加 cookie 鉴权）
        return None
    patterns = [re.compile(p) for p in SSO_TOKEN_PATTERNS]
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in SSO_SCAN_SKIP_DIRS]
        for f in files:
            if not f.endswith(SSO_SCAN_EXTS):
                continue
            try:
                text = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            for p in patterns:
                if p.search(text):
                    return None  # 命中任一 → 认为接入了
    return (
        "❌ [Hard Rule #4] 未发现 SSO 接入代码（未索到 `Decrypted-Userinfo` header 引用 / 未调 "
        "`_parse_sso_user`）。公司安全规范要求所有 Cowork 项目（含 demo / 只读 dashboard / 抽奖工具）"
        "都必须解析 SSO。即使业务不需要识别身份，也要用 SSO 拦未登录请求。可参考 "
        "`references/sso.md` 或模板中已有的 `_parse_sso_user` helper。"
    )


# 不允许出现的 build 触发字眼
GUARD_INSTALL_BLACKLIST = [
    "npm run build", "yarn build", "pnpm build", "vite build",
    "tsc ", "next build", "nuxt build", "webpack ",
    "playwright install", "puppeteer browsers install",
    "pip install -i https://pypi.org",
    "npm install --registry https://registry.npmjs.org",
    "apt-get", "yum install", "curl http",
]


def precheck_zip(zip_path: str) -> list:
    """
    对一个 zip 跑硬检查，返回 issue 列表（空就通过）。
    必须裸文件：install.sh / start.sh / health.sh 在根目录
    install.sh 不能跑 build / 装公网依赖
    start.sh 末行 exec + 端口 3000
    """
    issues = []
    if not os.path.exists(zip_path):
        return [f"zip not found: {zip_path}"]
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        # 1) 必须文件
        for must in GUARD_REQUIRED:
            if must not in names:
                # 也可能在某个子目录下
                under = [n for n in names if n.endswith("/" + must) or n == must]
                if under and under[0] != must:
                    issues.append(f"❌ {must} 在子目录 {under[0]}, Guard 要求**裸根**")
                elif not under:
                    issues.append(f"❌ 缺少必需脚本: {must}")
        # 2) install.sh / start.sh 内容审查
        for must in GUARD_REQUIRED:
            if must not in names:
                continue
            try:
                content = z.read(must).decode("utf-8", "replace")
            except Exception:
                continue
            if must == "install.sh":
                for blk in GUARD_INSTALL_BLACKLIST:
                    if blk in content:
                        issues.append(f"❌ install.sh 含禁止操作: `{blk}`")
                if ("pip install" in content or "pip3 install" in content) and "pypi.devops.xiaohongshu.com" not in content:
                    issues.append("❌ install.sh 跳 pip install 但未指内网镜像 "
                                  "`-i http://pypi.devops.xiaohongshu.com/simple/`。Guard pod 无公网。")
            if must == "start.sh":
                # 末行 exec
                lines = [l.strip() for l in content.strip().splitlines() if l.strip() and not l.strip().startswith("#")]
                if lines and not lines[-1].startswith("exec "):
                    issues.append("⚠️ start.sh 末行非 `exec`，PM2 daemon 会失控")
                if "3000" not in content and "$APP_PORT" not in content and "${APP_PORT" not in content:
                    issues.append("⚠️ start.sh 未明确监听 3000 端口（Guard upstream 默认 3000）")
                if "0.0.0.0" not in content:
                    issues.append("⚠️ start.sh 未明确 bind 0.0.0.0（127.0.0.1 会无法外部访问）")
                if 'cd "$(dirname "$0")"' not in content and "cd $(dirname $0)" not in content:
                    issues.append("⚠️ start.sh 开头没有 `cd \"$(dirname \"$0\")\"`，"
                                  "Guard cwd 不保证是项目目录。")
        # 3) build 产物提示（前端栈）
        has_pkg_json = any(n == "package.json" or n.endswith("/package.json") for n in names)
        if has_pkg_json:
            has_build = any(any(h in n for h in GUARD_BUILD_HINTS) for n in names)
            if not has_build:
                issues.append("⚠️ 检测到 package.json 但没 .next/standalone / dist / build/out，确认 build 产物已打入")
        # 4) 公网域名扫描（仅 install.sh）
        if "install.sh" in names:
            content = z.read("install.sh").decode("utf-8", "replace")
            urls = re.findall(r"https?://[\w\.-]+", content)
            for u in urls:
                if any(allow in u for allow in [".xiaohongshu.com", "npmmirror.com"]):
                    continue
                issues.append(f"❌ install.sh 含公网 URL（Pod 无公网）: {u}")
        # 5) SSO 红线（Hard Rule #4）——扫 zip 里的后端文件
        sso_err = _check_sso_compliance_zip(z, names)
        if sso_err:
            issues.append(sso_err)
    return issues


def _check_sso_compliance_zip(z: "zipfile.ZipFile", names: list) -> Optional[str]:
    """zip 版本的 SSO 检查。

    SPA 识别依赖任何代码文件中出现 SSO_SPA_MARKER（`@cowork-spa-host`）。
    先扫 bypass 后门（出现即拒，不依赖 SPA marker），再扫 SSO 接入。
    """
    scan_names = []
    for n in names:
        if any(d in n.split("/") for d in SSO_SCAN_SKIP_DIRS):
            continue
        if n.endswith(SSO_SCAN_EXTS) or n.endswith((".cjs", ".mjs")):
            scan_names.append(n)
    # 1. 后门扫
    backdoor_patterns = [re.compile(p) for p in SSO_BACKDOOR_PATTERNS]
    backdoor_hits: list[tuple[str, str]] = []
    for n in scan_names:
        try:
            text = z.read(n).decode("utf-8", "replace")
        except Exception:
            continue
        matched = False
        for p in backdoor_patterns:
            m = p.search(text)
            if m:
                backdoor_hits.append((n, m.group(0)))
                matched = True
                break
        if not matched:
            m = SSO_FALLBACK_REGEX.search(text) or SSO_FALLBACK_REGEX_JS.search(text)
            if m:
                snippet = m.group(0).split("\n", 1)[0].strip()[:80]
                backdoor_hits.append((n, f"SSO fallback 模式：{snippet}..."))
    if backdoor_hits:
        lines = ["❌ [Hard Rule #4] zip 中检测到 SSO bypass 后门（生产环境跳 SSO 是严重安全问题）："]
        for path, snippet in backdoor_hits[:10]:
            lines.append(f"   {path}：{snippet}")
        if len(backdoor_hits) > 10:
            lines.append(f"   … 还有 {len(backdoor_hits) - 10} 处")
        lines.append("   本地调试请用浏览器插件（ModHeader / Header Editor）手动注入 Decrypted-Userinfo header。")
        return "\n".join(lines)
    # 2. SPA marker
    for n in scan_names:
        try:
            text = z.read(n).decode("utf-8", "replace")
        except Exception:
            continue
        if SSO_SPA_MARKER in text:
            return None
    # 3. SSO 接入扫
    patterns = [re.compile(p) for p in SSO_TOKEN_PATTERNS]
    for n in scan_names:
        try:
            text = z.read(n).decode("utf-8", "replace")
        except Exception:
            continue
        for p in patterns:
            if p.search(text):
                return None
    return (
        "❌ [Hard Rule #4] 未发现 SSO 接入代码（未索到 `Decrypted-Userinfo` header 引用 / 未调 "
        "`_parse_sso_user`）。公司安全规范要求所有 Cowork 项目（含 demo / 只读 dashboard / 抽奖工具）"
        "都必须解析 SSO。即使业务不需要识别身份，也要用 SSO 拦未登录请求。可参考 "
        "`references/sso.md` 或模板中已有的 `_parse_sso_user` helper。"
    )


def pack_dir(src: str, out: str = None, in_place: bool = False, keep: list = None,
             keep_copy: bool = False) -> str:
    """
    把源目录打成 zip：
    - 默认走副本 <src>-guard/，剥 build 缓存 + 打 zip
    - --in-place: 不建副本，直接 zip 当前
    """
    src = os.path.abspath(src.rstrip("/"))
    if not os.path.isdir(src):
        err(f"not a dir: {src}")
    out = out or f"{src.rstrip('/')}.zip"

    if not in_place:
        import shutil
        copy_dir = src + "-guard"
        if os.path.exists(copy_dir):
            shutil.rmtree(copy_dir)
        info(f"📋 cp -r {src} {copy_dir}")
        shutil.copytree(src, copy_dir, symlinks=True, ignore_dangling_symlinks=True)
        # 副本不是一个独立的 cowork 项目，别让本地 / plugin scan 把它当独立项目。
        # 还顺便删一下 session/dev、runtime cache 之类临时状态。
        for stale in (MANIFEST_FILENAME, ".cowork"):
            stale_path = Path(copy_dir) / stale
            if stale_path.exists():
                try:
                    stale_path.unlink()
                except Exception:
                    pass
        # ⚡️ 在剪之前跳进副本跑一下 prepack 钩子
        # vite-spa / nextjs-standalone install.sh 不跑 build，依赖 dist/ / .next/standalone/
        # 在 zip 里。在这里自动跑完，避免用户忘了手跑。
        #
        # 优先级：prepack.sh > scripts.cowork:prepack > scripts.build (仅 vite/next)
        import subprocess as _sp
        prepack_sh = Path(copy_dir) / "prepack.sh"
        pkg_json_path = Path(copy_dir) / "package.json"
        ran_prebuild = False
        if prepack_sh.exists():
            # 旧版 prepack.sh 没有 dist cache check（无条件 npm ci + build），
            # 在 react/koa monorepo 工程上跑 30-90s，会触发 OpenClaw
            # pi-agent waitForIdle 30s cleanup bug (#8643)。
            # 检测到旧版就主动 warn 让用户重新 scaffold（或换新 prepack.sh）。
            try:
                _prepack_body = prepack_sh.read_text()
            except Exception:
                _prepack_body = ""
            if ("fast path" not in _prepack_body) and ("dist 已是最新" not in _prepack_body):
                sys.stderr.write(
                    "⚠️  prepack.sh 为旧版模板（无 dist 缓存复用逻辑）。\n"
                    "    每次 pack 都会重跑 npm ci + build（30-90s），\n"
                    "    可能触发 OpenClaw 30s cleanup（#8643）导致 publish hang。\n"
                    "    建议走 cowork.py transform 重新渲染模板，或手动使用最新 prepack.sh。\n"
                )
            info(f"⚡️ prepack: bash prepack.sh")
            dlog("prepack.start", script="bash prepack.sh", cwd=str(copy_dir))
            _t0 = time.time()
            try:
                # ✅ timeout=600s (10min)：prepack 超圣 → 者 杬認超时，不再永远 hang。
                _sp.run(["bash", "prepack.sh"], cwd=copy_dir, check=True, timeout=600)
                ran_prebuild = True
                dlog("prepack.ok", dur_s=round(time.time()-_t0, 2))
            except _sp.TimeoutExpired as e:
                dlog("prepack.timeout", dur_s=round(time.time()-_t0, 2), timeout=e.timeout)
                err(f"prepack.sh timeout after {e.timeout}s; 可能是 npm ci / build 在 hang。请手动 cd {copy_dir} 跳过后重试。")
            except _sp.CalledProcessError as e:
                dlog("prepack.fail", dur_s=round(time.time()-_t0, 2), exit=e.returncode)
                err(f"prepack.sh failed: {e}")
        elif pkg_json_path.exists():
            try:
                pkg = json.loads(pkg_json_path.read_text())
            except Exception:
                pkg = {}
            scripts = (pkg.get("scripts") or {})
            deps_text = (json.dumps(pkg.get("dependencies") or {})
                         + json.dumps(pkg.get("devDependencies") or {}))
            if ("vite" in deps_text) or ("next" in deps_text):
                script_name = "cowork:prepack" if "cowork:prepack" in scripts else (
                    "build" if "build" in scripts else None)
                if script_name:
                    # === fast path: dist / .next/standalone 已存在且不旧于源码,直接复用 ===
                    # 避免重跑 30-120s 的 npm ci + build,绕 OpenClaw 30s cleanup bug (#8643)
                    dist_index = Path(copy_dir) / "dist" / "index.html"
                    next_server = Path(copy_dir) / ".next" / "standalone" / "server.js"
                    artifact = dist_index if dist_index.exists() else (
                        next_server if next_server.exists() else None)
                    skip_build = False
                    if artifact is not None:
                        artifact_mtime = artifact.stat().st_mtime
                        # 检查源码是否比 artifact 新
                        stale = False
                        for src_pattern in ["src", "app", "pages", "components", "lib",
                                            "package.json", "package-lock.json",
                                            "vite.config.ts", "vite.config.js",
                                            "vite.config.mts", "vite.config.mjs",
                                            "next.config.js", "next.config.mjs", "next.config.ts",
                                            "tsconfig.json", "tsconfig.app.json",
                                            "index.html"]:
                            src_path = Path(copy_dir) / src_pattern
                            if not src_path.exists():
                                continue
                            if src_path.is_file():
                                if src_path.stat().st_mtime > artifact_mtime:
                                    stale = True
                                    break
                            else:
                                # 目录: 递归找比 artifact 新的文件
                                for root, _, files in os.walk(src_path):
                                    for fn in files:
                                        try:
                                            if (Path(root) / fn).stat().st_mtime > artifact_mtime:
                                                stale = True
                                                break
                                        except OSError:
                                            pass
                                    if stale:
                                        break
                            if stale:
                                break
                        if not stale:
                            info(f"⚡️ prepack: ✅ {artifact.name} 已是最新,跳过 npm ci + build")
                            skip_build = True
                            ran_prebuild = True
                    if not skip_build:
                        info(f"⚡️ prepack: npm ci && npm run {script_name}")
                        # ✅ timeout=480s (8min)：npm ci 最多 8min，build 最多 8min。
                        # 避免 杬認 永远 hang 谁 cowork.py 进程主容 (kp pi-embedded-runner timeout #8643)
                        try:
                            dlog("prepack.fallback.npm-ci.start", cwd=str(copy_dir))
                            _t0 = time.time()
                            _sp.run(["npm", "ci"], cwd=copy_dir, check=True, timeout=480)
                            dlog("prepack.fallback.npm-ci.ok", dur_s=round(time.time()-_t0, 2))
                            dlog("prepack.fallback.npm-run.start", script=script_name)
                            _t0 = time.time()
                            _sp.run(["npm", "run", script_name], cwd=copy_dir, check=True, timeout=480)
                            dlog("prepack.fallback.npm-run.ok", dur_s=round(time.time()-_t0, 2))
                            ran_prebuild = True
                        except _sp.TimeoutExpired as e:
                            dlog("prepack.fallback.timeout", cmd=str(e.cmd), timeout=e.timeout)
                            err(f"npm prebuild timeout after {e.timeout}s (cmd: {e.cmd})")
                        except _sp.CalledProcessError as e:
                            dlog("prepack.fallback.fail", exit=e.returncode)
                            err(f"npm prebuild failed: {e}")
                        except FileNotFoundError:
                            dlog("prepack.fallback.no-npm")
                            err("npm 不在 PATH，无法跑 prebuild。请安装 Node.js。")
        if ran_prebuild:
            # vite 默认 outDir=dist; next standalone 输出在 .next/standalone/
            keep = list(keep or [])
            for d in ("dist", ".next", "public"):
                if d not in keep:
                    keep.append(d)

        # 剥
        STRIP_DIRS = [".next", "dist", "build", "out", ".turbo", ".cache",
                      ".parcel-cache", ".nuxt", ".svelte-kit", ".vite", "coverage",
                      ".git", "node_modules", "__pycache__", ".pytest_cache",
                      ".mypy_cache", ".ruff_cache", ".venv", "venv", ".tox", "vendor",
                      "tmp", "logs", ".cowork"]
        # “keep” 优先级高于 STRIP：包含 SPA build 的生产产物（如 Vite dist/）
        # 可以 1）命令行 --keep dist build 显式传；
        #     2）在 .cowork.json 中写 {"pack":{"keep":["dist"]}} 永久化
        keep_dirs = set(keep or [])
        manifest_path = Path(src) / '.cowork.json'
        if manifest_path.exists():
            try:
                mf = json.loads(manifest_path.read_text())
                for d in (mf.get('pack') or {}).get('keep') or []:
                    keep_dirs.add(d)
            except Exception:
                pass
        if keep_dirs:
            info(f"📎 keep dirs (not stripped): {sorted(keep_dirs)}")
        # 如果某个顶层 keep_dir 在当前 root 路径中已经出现，则其子树上的一切 STRIP_DIRS 子目录
        # 都不应该被剥。例如 .next 是 keep 后 .next/standalone/node_modules 不能被干掉。
        keep_subtree_anchors = {os.path.join(copy_dir, d) for d in keep_dirs}

        def _is_inside_keep(p: str) -> bool:
            for anchor in keep_subtree_anchors:
                if p == anchor or p.startswith(anchor + os.sep):
                    return True
            return False

        for root, dirs, files in os.walk(copy_dir, topdown=True):
            # 排除掉子目录
            for d in list(dirs):
                if d in keep_dirs:
                    continue
                full = os.path.join(root, d)
                if _is_inside_keep(full):
                    # 在 keep 子树里的 STRIP_DIRS 不刪（典型：.next/standalone/node_modules）
                    continue
                if d in STRIP_DIRS or d.endswith(".egg-info"):
                    full = os.path.join(root, d)
                    info(f"🧹 rm {os.path.relpath(full, copy_dir)}")
                    shutil.rmtree(full, ignore_errors=True)
                    dirs.remove(d)
            for fn in files:
                if fn.endswith(".pyc") or fn == ".DS_Store":
                    try:
                        os.remove(os.path.join(root, fn))
                    except Exception:
                        pass
        target = copy_dir
    else:
        target = src

    # zip：根目录裸文件（Guard 要求）
    info(f"📦 zip {out}")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(target):
            for f in files:
                full = os.path.join(root, f)
                arc = os.path.relpath(full, target)
                z.write(full, arc)
    sz = os.path.getsize(out)
    ok(f"packed {out} ({sz/1024:.1f} KB)")

    # 默认清理副本。zip 已出，<src>-guard/ 是中间产物，不清理会被
    # 后续流程误认为项目（用户 link source / file picker 都有可能误选）。
    # 仅在 in_place=False 且 未设 keep_copy 时清。
    if not in_place and not keep_copy:
        import shutil
        try:
            shutil.rmtree(target)
            info(f"🧹 cleaned copy: {target}")
        except Exception as e:
            info(f"⚠️ failed to clean copy {target}: {e}")
    return out


# -----------------------------------------------------------------------------
# §5 高层命令
# -----------------------------------------------------------------------------
def cmd_pack(args):
    dlog("cmd.pack.start", src=args.src, out=args.out, skip_precheck=args.skip_precheck,
         in_place=getattr(args, 'in_place', False))
    _t0 = time.time()
    out = pack_dir(args.src, out=args.out, in_place=args.in_place,
                   keep=getattr(args, 'keep', None),
                   keep_copy=getattr(args, 'keep_copy', False))
    dlog("cmd.pack.zip-done", dur_s=round(time.time()-_t0, 2), zip=out,
         zip_size=Path(out).stat().st_size if Path(out).exists() else None)
    if not args.skip_precheck:
        dlog("cmd.pack.precheck.start")
        issues = precheck_zip(out)
        if issues:
            sys.stderr.write("\n=== precheck issues ===\n")
            for i in issues:
                sys.stderr.write(i + "\n")
            if any(i.startswith("❌") for i in issues):
                dlog("cmd.pack.precheck.fail", issues=len(issues))
                err("precheck FAIL (上面有 ❌)，先修复再发布")
        else:
            dlog("cmd.pack.precheck.ok")
            ok("precheck pass")
    dlog("cmd.pack.done", dur_s=round(time.time()-_t0, 2), zip=out)
    print(out)


def precheck_dir(src_dir: str) -> list:
    """对源码目录跑 Guard 红线检查（link source 场景使用）。

    实现点：复用 precheck_zip 的逻辑，充当临时只读 zip 路径
    是类似的。但目录检查几个重点：
      - install.sh / start.sh / health.sh 是否裸在根
      - install.sh 是否含禁止 build / 公网 URL
      - start.sh 是否末行 exec + 0.0.0.0:3000
      - 前端栈 build 产物提示
    """
    issues = []
    if not os.path.isdir(src_dir):
        return [f"❌ 不是目录: {src_dir}"]
    for must in GUARD_REQUIRED:
        target = os.path.join(src_dir, must)
        if not os.path.exists(target):
            # 子目录检查
            found_sub = []
            for root, _, files in os.walk(src_dir):
                if must in files and root != src_dir:
                    found_sub.append(os.path.relpath(os.path.join(root, must), src_dir))
                    break
            if found_sub:
                issues.append(f"❌ {must} 在子目录 {found_sub[0]}, Guard 要求**裸根**")
            else:
                issues.append(f"❌ 缺少必需脚本: {must}")
            continue
        try:
            content = open(target).read()
        except Exception:
            continue
        if must == "install.sh":
            for blk in GUARD_INSTALL_BLACKLIST:
                if blk in content:
                    issues.append(f"❌ install.sh 含禁止操作: `{blk}`")
            urls = re.findall(r"https?://[\w\.-]+", content)
            for u in urls:
                if any(allow in u for allow in [".xiaohongshu.com", "npmmirror.com"]):
                    continue
                issues.append(f"❌ install.sh 含公网 URL（Pod 无公网）: {u}")
            # Guard pod 无公网：pip / npm install 必须走内网镜像
            if ("pip install" in content or "pip3 install" in content) and "pypi.devops.xiaohongshu.com" not in content:
                issues.append("❌ install.sh 跳 pip install 但未指内网镜像 "
                              "`-i http://pypi.devops.xiaohongshu.com/simple/`。Guard pod 无公网，"
                              "部署会在 install 阶段挂死。")
            if ("npm install" in content or "npm ci" in content) and not os.path.exists(os.path.join(src_dir, ".npmrc")):
                issues.append("❌ install.sh 跳 npm install/ci 但项目根没 .npmrc 配内网 registry。"
                              "请在项目根加 .npmrc 指内网镜像。")
        if must == "start.sh":
            lines = [l.strip() for l in content.strip().splitlines() if l.strip() and not l.strip().startswith("#")]
            if lines and not lines[-1].startswith("exec "):
                issues.append("⚠️ start.sh 末行非 `exec`，PM2 daemon 会失控")
            if "3000" not in content and "$APP_PORT" not in content and "${APP_PORT" not in content:
                issues.append("⚠️ start.sh 未明确监听 3000 端口（Guard upstream 默认 3000）")
            if "0.0.0.0" not in content:
                issues.append("⚠️ start.sh 未明确 bind 0.0.0.0（127.0.0.1 会无法外部访问）")
            # Guard 调度器的 cwd 不保证是项目目录，不切差会找不到入口文件
            if 'cd "$(dirname "$0")"' not in content and "cd $(dirname $0)" not in content:
                issues.append("⚠️ start.sh 开头没有 `cd \"$(dirname \"$0\")\"`，"
                              "Guard cwd 不保证是项目目录，uvicorn/node 可能找不到入口。")
    pkg = os.path.join(src_dir, "package.json")
    if os.path.isfile(pkg):
        has_build = any(
            os.path.exists(os.path.join(src_dir, h)) or os.path.exists(os.path.join(src_dir, h.lstrip(".")))
            for h in GUARD_BUILD_HINTS
        )
        if not has_build:
            issues.append("⚠️ 检测到 package.json 但没 .next/standalone / dist / build/out，确认 build 产物已打入")
    # SSO 红线检查（Hard Rule #4）
    sso_err = _check_sso_compliance(src_dir)
    if sso_err:
        issues.append(sso_err)
    # db.properties 文件本身 key 越权检查（防模型让用户去管理面配 PG）
    issues.extend(_check_db_properties_keys(src_dir))
    # transform/verifiers 真硬校验（AI 走 Runway / SSO 解析对 / 代码中 db.* 引用越权）
    issues.extend(_run_transform_verifiers(src_dir))
    return issues


def _check_db_properties_keys(src_dir: str) -> list:
    """检 db.properties 文件是否含平台不注入的额外 key。

    背景：Cowork 平台只注入 6 个标准 key（DB_PROPS_ALLOWED_KEYS）。模型常让用户加
    db.url / db.driver / db.schema / db.pool_size / db.timezone 等，带着「用户去管理面
    配一下」的谎言发布 → 部署后什么都读不到。用 cowork.py precheck 硬拦住。

    只打包之前检推荐的位置：根目录 / backend/ / app/ / src/ 下的 db.properties。
    """
    issues = []
    candidates = []
    p = Path(src_dir)
    for rel in ("db.properties", "backend/db.properties", "app/db.properties", "src/db.properties"):
        f = p / rel
        if f.is_file():
            candidates.append(f)
    for f in candidates:
        try:
            lines = f.read_text(errors="replace").splitlines()
        except Exception:
            continue
        extra = []
        for ln in lines:
            s = ln.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key = s.split("=", 1)[0].strip()
            if not key.startswith("db."):
                continue
            if key not in DB_PROPS_ALLOWED_KEYS:
                extra.append(key)
        if extra:
            extras_str = ", ".join(sorted(set(extra)))
            issues.append(
                f"❌ {f.relative_to(p)} 含平台不注入的 key: {extras_str}\n"
                f"  Cowork 只注入 6 个标准 key：db.type / db.host / db.port / db.username / db.password / db.database\n"
                f"  不要让用户去管理面配额外 key——用以上 6 个 key 拼出需要的东西（如 "
                f"jdbc URL = ${{db.type}}://${{db.host}}:${{db.port}}/${{db.database}}），"
                f"其他都在代码里写默认值。"
            )
    return issues


# -----------------------------------------------------------------------------
# transform/ 子目录：复用改写流程的真 verifier（shell），不再写阉割版
# -----------------------------------------------------------------------------
TRANSFORM_DIR = Path(__file__).parent / "transform"
VERIFIERS_DIR = TRANSFORM_DIR / "verifiers"

# precheck 需要调的核心 verifier。其它（如 verify_zip_layout、verify_install_no_internet）
# precheck_dir 已经用内置逻辑覆盖，这里只补 cowork.py 没做的硬校验。
_CORE_VERIFIERS = [
    ("verify_db_props_keys.sh", "❌ db.properties key 越权或不规范（笨蛋模型可能让用户去管理页面配 PG）"),
    ("verify_ai_calls.sh", "❌ AI 调用未走 Runway 网关（禁止直接调 anthropic/openai/google SDK）"),
    ("verify_sso_correct.sh", "❌ SSO 接入实现不符合规范（必须 latin-1 → JSON 两步，无 base64）"),
]


def _run_transform_verifiers(src_dir: str) -> list:
    """调 transform/verifiers/ 下的真 shell verifier，作为 precheck 硬卡层。

    设计：
    - verifier 是 cowork-app 改写流程沉淀的 28 个硬校验脚本，比 cowork.py 内置检查精细
    - 只在本机有 transform/verifiers/ 时跑（merge 后默认有）
    - 找不到 verifier 静默跳过——保证旧 skill 安装也能用
    - verifier 非零退出 → 转成 ❌ issue（fatal，会让 precheck 失败）
    """
    import subprocess  # cowork.py 约定：按需 import、不污染顶层
    issues = []
    if not VERIFIERS_DIR.is_dir():
        return issues
    for script, hint in _CORE_VERIFIERS:
        sh = VERIFIERS_DIR / script
        if not sh.is_file():
            continue
        try:
            r = subprocess.run(
                ["bash", str(sh), src_dir],
                capture_output=True, text=True, timeout=60,
            )
        except Exception as e:
            # verifier 自身炸了（非业务问题）→ warning，不阻塞
            issues.append(f"⚠️ verifier {script} 执行异常: {e}")
            continue
        if r.returncode != 0:
            out = (r.stdout + r.stderr).strip()
            # 保留最后 30 行细节给 agent 看
            tail = "\n".join(out.splitlines()[-30:]) if out else "(no output)"
            issues.append(f"{hint}\n  verifier: {script}\n  详情:\n{tail}")
    return issues


def cmd_transform(args):
    """thin wrapper: 把现有工程改写为 Cowork Guard 子应用规范。

    实际逻辑全在 transform/transform.sh（前 cowork-app skill），cowork.py 不重复实现。
    """
    import subprocess
    sh = TRANSFORM_DIR / "transform.sh"
    if not sh.is_file():
        err(f"transform.sh 不存在: {sh}\n请确认 cowork-publish skill 已包含 transform/ 子目录")
    src = os.path.abspath(args.srcDir)
    if not os.path.isdir(src):
        err(f"srcDir 不存在或不是目录: {src}")
    extra = list(args.extra or [])
    cmd = ["bash", str(sh), src] + extra
    info(f"调用 transform: {' '.join(cmd)}")
    try:
        r = subprocess.run(cmd, check=False)
        sys.exit(r.returncode)
    except KeyboardInterrupt:
        sys.exit(130)


def cmd_precheck(args):
    target = args.target
    if os.path.isdir(target):
        issues = precheck_dir(target)
        kind = "dir"
    elif os.path.isfile(target):
        issues = precheck_zip(target)
        kind = "zip"
    else:
        err(f"路径不存在: {target}")
    if not issues:
        ok(f"precheck pass ({kind})")
        if args.json:
            print(json.dumps({"ok": True, "target": target, "kind": kind, "issues": []}, ensure_ascii=False))
        return
    if args.json:
        print(json.dumps({
            "ok": not any(i.startswith("❌") for i in issues),
            "target": target,
            "kind": kind,
            "issues": issues,
        }, ensure_ascii=False, indent=2))
    else:
        for i in issues:
            print(i)
    if any(i.startswith("❌") for i in issues):
        sys.exit(2)


# -----------------------------------------------------------------------------
# §4.6 suggest-publish-metadata：首发表单预填
# -----------------------------------------------------------------------------
_STOPWORDS = set("""a an and the to for of in on with is are be will can use using app project
一个 上 下 中 是 在 和 与 有 为 到 仅 只 进行 可以 使用 项目 应用 cowork seal todo demo""".split())

_TAG_HINTS = {
    "efficiency_improvement": ["效率", "todo", "待办", "管理", "任务", "workflow", "调度"],
    "content_generation": ["文案", "生成", "写作", "summary", "总结", "创作"],
    "data_analysis": ["报表", "看板", "统计", "dashboard", "分析", "表格"],
    "research_insight": ["调研", "趋势", "insight", "研究"],
    "communication_collaboration": ["协作", "分组", "团队", "聊天", "讨论", "问卷", "报名"],
    "code_development": ["代码", "fastapi", "vite", "react", "vue", "htmx", "sdk", "接口", "api"],
    "design_creativity": ["设计", "原型", "figma", "品牌", "创意", "logo", "插画", "配色", "主题"],
    "fun_creativity": [
        # 娱乐/小游戏
        "贪吃蛇", "俄罗斯", "2048", "扫雷", "路饮", "随机", "抽礼", "抽奖", "转盘",
        # 率社/玄学
        "抽签", "塔罗", "占卜", "黄历", "八字", "运势", "星座", "mbti", "职业性格",
        # 创意小工具
        "菜谱", "饮品", "诗", "俳句", "昂米", "段子", "梵高", "棵高", "表情包",
        # 文案
        "趣味", "好玩", "轻松", "摇一摇",
    ],
}


def _read_text_safe(path: Path, limit: int = 4096) -> str:
    try:
        return path.read_text(errors="replace")[:limit]
    except Exception:
        return ""


def _collect_corpus(src_dir: str) -> dict:
    """扫描 src_dir 取几个“必读文件”的内容，不递归遭整个工程。"""
    p = Path(src_dir)
    corpus = {"readme": "", "package": None, "html_titles": [], "py_routes": [], "description": ""}
    # README*
    for name in ("README.md", "README.MD", "Readme.md", "readme.md", "README.rst", "README.txt"):
        f = p / name
        if f.exists():
            corpus["readme"] = _read_text_safe(f, 6000)
            break
    # package.json
    pkg = p / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text())
            corpus["package"] = {
                "name": data.get("name"),
                "description": data.get("description"),
                "keywords": data.get("keywords") or [],
            }
        except Exception:
            pass
    # 任意 HTML 的 <title>
    for html in list(p.glob("index.html"))[:1] + list((p / "templates").glob("*.html") if (p / "templates").is_dir() else [])[:5]:
        text = _read_text_safe(html, 4000)
        m = re.search(r"<title>(.+?)</title>", text, re.I | re.S)
        if m:
            corpus["html_titles"].append(m.group(1).strip())
    # Python 路由
    for py in list(p.glob("app.py"))[:1] + list(p.glob("main.py"))[:1]:
        text = _read_text_safe(py, 6000)
        for m in re.finditer(r"@(?:app|router)\.(?:get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]", text):
            route = m.group(1)
            if route not in corpus["py_routes"]:
                corpus["py_routes"].append(route)
            if len(corpus["py_routes"]) >= 8:
                break
    # README 首段作为 description 兑底
    if corpus["readme"]:
        # 取第一个非标题段落
        paras = [p.strip() for p in corpus["readme"].split("\n\n") if p.strip() and not p.strip().startswith("#")]
        if paras:
            corpus["description"] = paras[0][:400]
    elif corpus["package"] and corpus["package"].get("description"):
        corpus["description"] = corpus["package"]["description"][:400]
    return corpus


def _infer_intro(corpus: dict, fallback_name: str) -> str:
    if corpus["description"]:
        first = corpus["description"].split("\n")[0].strip().rstrip("。")
        return first[:60] if len(first) > 60 else first
    if corpus["html_titles"]:
        return corpus["html_titles"][0][:60]
    return f"{fallback_name} — 用 Cowork 快速发布的小工具"


def _infer_tags(corpus: dict, fallback_name: str) -> list:
    blob = " ".join([
        corpus.get("readme", ""),
        corpus.get("description", ""),
        " ".join(corpus.get("html_titles", [])),
        " ".join(corpus.get("py_routes", [])),
        ((corpus.get("package") or {}).get("description") or ""),
        " ".join((corpus.get("package") or {}).get("keywords") or []),
        fallback_name,
    ]).lower()
    tags = []
    for tag, hints in _TAG_HINTS.items():
        if any(h.lower() in blob for h in hints):
            tags.append(tag)
        if len(tags) >= 5:
            break
    return tags or ["efficiency_improvement"]


def _suggest_publish_metadata(project_id: str = None, src_dir: str = None) -> dict:
    """纯本地推断，不调 LLM；plugin / Studio 可在之后补 LLM。

    返回字段：projectId / srcDir / title / intro / description / alias / tags /
    visibility / coverPath / coverHint。cover 不生成（需 puppeteer/playwright），
    如果上一次发布过且 manifest 里存了 coverPath 则优先复用；否则 coverPath
    为 None，Studio 表单允许用户现场挑。
    """
    # 优先从 manifest 拿项目。
    manifest = {}
    if src_dir:
        manifest = _load_manifest(src_dir)
    elif project_id:
        # 扫完整 workspace，按 manifest.id 反查 src_dir
        from pathlib import Path as _P
        for root in (COWORK_PROJECT_ROOT, LEGACY_PROJECT_ROOT):
            if not root.exists():
                continue
            for child in root.iterdir():
                mp = child / MANIFEST_FILENAME
                if not mp.exists():
                    continue
                try:
                    m = json.loads(mp.read_text())
                except Exception:
                    continue
                if m.get("id") == project_id:
                    manifest = m
                    src_dir = m.get("srcDir")
                    break
    if not src_dir:
        err(f"cannot resolve srcDir for project (projectId={project_id})")
    if not manifest:
        manifest = _load_manifest(src_dir)
    if not manifest:
        err(f"no .cowork.json under {src_dir}; not a cowork project")

    name = manifest.get("name") or Path(src_dir).name
    corpus = _collect_corpus(src_dir)

    # scaffold/transform 时用户写的一句话需求描述优先级最高（比 README 首段更贴合意图）。
    manifest_desc = (manifest.get("description") or "").strip()
    if manifest_desc:
        corpus["description"] = manifest_desc[:400]

    # 标题预填：manifest.name > html title > srcDir basename
    title = name
    if corpus["html_titles"]:
        title = corpus["html_titles"][0]

    intro = _infer_intro(corpus, name)

    description = corpus.get("description") or intro

    # alias 预填：manifest.plannedAlias > slugify(name)，遵循 3-32 小写/数字/-
    alias = manifest.get("plannedAlias") or _slugify(name)

    tags = _infer_tags(corpus, name)

    visibility = (manifest.get("cowork") or {}).get("visibility") or "SELF_ONLY"

    # cover 复用：manifest 里上次 publish 如果记过本地路径，进一步默认
    cover_path = manifest.get("coverPath") or None
    cover_hint = None
    if cover_path:
        cover_hint = "reused-from-manifest"

    return {
        "projectId": manifest.get("id"),
        "srcDir": src_dir,
        "title": title,
        "intro": intro,
        "description": description,
        "alias": alias,
        "tags": tags,
        "visibility": visibility,
        "coverPath": cover_path,
        "coverHint": cover_hint,
        "signals": {
            "hasReadme": bool(corpus["readme"]),
            "hasPackageJson": bool(corpus["package"]),
            "htmlTitleCount": len(corpus["html_titles"]),
            "pyRouteCount": len(corpus["py_routes"]),
        },
    }


def cmd_suggest_publish_metadata(args):
    src_dir = None
    if args.src:
        src_dir = os.path.abspath(args.src)
    result = _suggest_publish_metadata(
        project_id=args.project_id if args.project_id else None,
        src_dir=src_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _resolve_manifest_by_project_or_slug(key: str = None, src_dir: str = None) -> dict:
    if src_dir:
        m = _load_manifest(os.path.abspath(src_dir))
        if m:
            return m
    if not key:
        err('project id / slug / --src is required')
    for root in (COWORK_PROJECT_ROOT, LEGACY_PROJECT_ROOT):
        if not root.exists():
            continue
        for child in root.iterdir():
            mp = child / MANIFEST_FILENAME
            if not mp.exists():
                continue
            try:
                m = json.loads(mp.read_text())
            except Exception:
                continue
            slug = _slugify(m.get('name') or m.get('id'))
            if key in (m.get('id'), slug, m.get('name')):
                return m
    # 再从 memory root link 文件反查
    candidate = MEMORY_ROOT / (key if key.endswith('.md') else f'{key}.md')
    if candidate.exists() or candidate.is_symlink():
        fm, _body = _parse_frontmatter(_read_text(candidate))
        if fm.get('srcDir'):
            m = _load_manifest(fm['srcDir'])
            if m:
                return m
            return {'id': fm.get('projectId'), 'name': fm.get('name'), 'srcDir': fm.get('srcDir')}
    err(f'project not found: {key}')


def cmd_memory(args):
    if args.memory_action == 'list':
        _memory_index_refresh()
        print(_read_text(MEMORY_INDEX))
        return

    manifest = _resolve_manifest_by_project_or_slug(args.project, src_dir=getattr(args, 'src', None))
    if args.memory_action == 'show':
        p = _project_memory_path(manifest.get('srcDir'))
        if not p.exists():
            _memory_init(manifest)
        print(_read_text(p))
        return

    if args.memory_action == 'append':
        content = args.content
        if args.file:
            content = _read_text(Path(args.file))
        if not content:
            # stdin 支持管道
            if not sys.stdin.isatty():
                content = sys.stdin.read()
        if not content:
            err('append requires --content, --file, or stdin')
        # 多行内容缩进到 section 下；首行前加 bullet，后续保持原样。
        lines = content.strip().splitlines()
        if len(lines) == 1:
            line = f"- {time.strftime('%Y-%m-%d %H:%M')} — {lines[0]}"
        else:
            line = f"- {time.strftime('%Y-%m-%d %H:%M')} —\n" + '\n'.join(f"  {ln}" for ln in lines)
        _memory_append(manifest, section=args.section, line=line)
        ok(f"appended to {_project_memory_path(manifest.get('srcDir'))}#{args.section}")
        return


# -----------------------------------------------------------------------------
# §4.5 本地项目元信息（.cowork.json manifest）
# -----------------------------------------------------------------------------
def _now_ms() -> int:
    return int(time.time() * 1000)


COWORK_PROJECT_SCHEMA = 'cowork-project/v1'
MANIFEST_FILENAME = '.cowork.json'


def _manifest_path(src_dir: str) -> Path:
    return Path(src_dir) / MANIFEST_FILENAME


def _load_manifest(src_dir: str) -> dict:
    p = _manifest_path(src_dir)
    if not p.exists():
        return {}
    try:
        m = json.loads(p.read_text())
        return m if isinstance(m, dict) else {}
    except Exception:
        return {}


def _save_manifest(src_dir: str, manifest: dict) -> None:
    p = _manifest_path(src_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    tmp.replace(p)


def _new_project_id() -> str:
    return 'cw_proj_' + ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10))


def _ensure_manifest(src_dir: str, *, name: str | None = None, stack: str | None = None,
                    created_by: str = 'cowork-cli', chat_session_id: str | None = None) -> dict:
    """读取 / 创建项目 manifest；返回 manifest dict。"""
    m = _load_manifest(src_dir)
    now = _now_ms()
    if not m or m.get('schema') != COWORK_PROJECT_SCHEMA:
        m = {
            'schema': COWORK_PROJECT_SCHEMA,
            'id': _new_project_id(),
            'name': name or Path(src_dir).name,
            'srcDir': os.path.abspath(src_dir),
            'createdAt': now,
            'updatedAt': now,
            'createdBy': created_by,
            'stack': stack,
            'guardCompliant': True,
        }
    else:
        m['updatedAt'] = now
        if name and not m.get('name'):
            m['name'] = name
        if stack and not m.get('stack'):
            m['stack'] = stack
        m.setdefault('srcDir', os.path.abspath(src_dir))
        m.setdefault('createdBy', created_by)
        m.setdefault('guardCompliant', True)
    if chat_session_id:
        m['chatSessionId'] = chat_session_id
    _save_manifest(src_dir, m)
    return m


# -----------------------------------------------------------------------------
# §4.7 项目 memory：~/memory/cowork-memory/<slug>.md 集中 + .cowork/memory.md 主体
# -----------------------------------------------------------------------------
MEMORY_ROOT = Path(os.environ.get("COWORK_MEMORY_ROOT", os.path.expanduser("~/.openclaw/workspace/memory/cowork-memory")))
MEMORY_INDEX = MEMORY_ROOT / "INDEX.md"


def _project_memory_path(src_dir: str) -> Path:
    """项目内 memory.md 真主体。"""
    return Path(src_dir) / ".cowork" / "memory.md"


def _memory_link_path(slug: str) -> Path:
    return MEMORY_ROOT / f"{slug}.md"


def _read_text(p: Path) -> str:
    try:
        return p.read_text()
    except Exception:
        return ""


def _write_text(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(content)
    tmp.replace(p)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """返回 (frontmatter_dict, body_md)。不依赖 PyYAML，只支持简单 key: value。"""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5:]
    fm = {}
    for line in raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            val = v.strip()
            # _render_frontmatter 会把含 ':' 的 URL json.dumps；读回来时还原，避免重复转义。
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                try:
                    val = json.loads(val)
                except Exception:
                    val = val.strip('"').strip("'")
            fm[k.strip()] = val
    return fm, body


def _render_frontmatter(fm: dict) -> str:
    lines = ["---"]
    for k, v in fm.items():
        if v is None or v == "":
            continue
        # 含特殊字符加引号
        sv = str(v)
        if any(c in sv for c in ":#\n"):
            sv = json.dumps(sv, ensure_ascii=False)
        lines.append(f"{k}: {sv}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _ensure_memory_link(slug: str, src_dir: str) -> Path:
    """创建集中索引的 symlink；同 slug 冲突时后缀 -2 -3。"""
    target = _project_memory_path(src_dir).resolve()
    link = _memory_link_path(slug)
    counter = 1
    while link.exists() or link.is_symlink():
        # 如果已是指同一个 target，复用
        try:
            if link.is_symlink() and Path(os.readlink(link)).resolve() == target:
                return link
        except OSError:
            pass
        counter += 1
        link = _memory_link_path(f"{slug}-{counter}")
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(str(target), str(link))
    except OSError:
        # 某些 fs 不打 symlink（如 SMB 挂载），降级拷贝
        link.write_text(_read_text(target))
    return link


def _memory_render_initial(manifest: dict, *, user_prompt: str = None,
                           project_summary: str = None) -> str:
    fm = {
        "projectId": manifest.get("id"),
        "name": manifest.get("name"),
        "slug": _slugify(manifest.get("name") or manifest.get("id")),
        "srcDir": manifest.get("srcDir"),
        "stack": manifest.get("stack") or "",
        "createdAt": time.strftime("%Y-%m-%d", time.localtime((manifest.get("createdAt") or _now_ms()) / 1000)),
        "workId": (manifest.get("cowork") or {}).get("workId", ""),
        "alias": (manifest.get("cowork") or {}).get("alias", ""),
        "accessUrl": (manifest.get("cowork") or {}).get("accessUrl", ""),
        "visibility": (manifest.get("cowork") or {}).get("visibility", ""),
    }
    body_lines = [
        f"# {manifest.get('name') or manifest.get('id')}\n",
        "## 项目简介",
        (project_summary or "<!-- scaffold 时写入，可被用户/agent 编辑 -->"),
        "",
        "## 用户原始需求",
    ]
    if user_prompt:
        for line in user_prompt.strip().splitlines():
            body_lines.append(f"> {line}")
    else:
        body_lines.append("<!-- 用户首次创建时描述 -->")
    body_lines += [
        "",
        "## 关键决策",
        "<!-- agent 在 chat 收尾时追加 -->",
        "",
        "## 发布历史",
        "<!-- publish / redeploy 自动追加 -->",
        "",
        "## 元信息变更",
        "<!-- update_metadata 自动追加 -->",
        "",
        "## 已知问题 / TODO",
        "<!-- agent / 用户追加 -->",
        "",
    ]
    return _render_frontmatter(fm) + "\n" + "\n".join(body_lines)


def _memory_update_frontmatter(text: str, updates: dict) -> str:
    fm, body = _parse_frontmatter(text)
    fm.update({k: v for k, v in updates.items() if v is not None})
    return _render_frontmatter(fm) + "\n" + body.lstrip("\n")


def _memory_append_section(text: str, section: str, line: str) -> str:
    """在指定二级标题下追加一行；如 section 不存在则文末新增。"""
    fm, body = _parse_frontmatter(text)
    header = f"## {section}"
    lines = body.splitlines()
    try:
        idx = next(i for i, ln in enumerate(lines) if ln.strip() == header)
    except StopIteration:
        lines += ["", header, line, ""]
    else:
        # 找到下一个 "## "，在之前插入
        insert_at = len(lines)
        for j in range(idx + 1, len(lines)):
            if lines[j].startswith("## "):
                insert_at = j
                break
        # 垃圾行清理：跳过 <!-- ... --> 占位行
        block = lines[idx + 1: insert_at]
        clean_block = [ln for ln in block if not (ln.strip().startswith("<!--") and ln.strip().endswith("-->"))]
        if clean_block != block:
            # 去占位行
            lines = lines[: idx + 1] + clean_block + lines[insert_at:]
            insert_at = idx + 1 + len(clean_block)
        # 追加新行，保证前后有空行
        prefix = lines[: insert_at]
        suffix = lines[insert_at:]
        if prefix and prefix[-1].strip() != "":
            lines = prefix + [line, ""] + suffix
        else:
            lines = prefix + [line] + suffix
    return _render_frontmatter(fm) + "\n" + "\n".join(lines).lstrip("\n")


def _memory_init(manifest: dict, *, user_prompt: str = None,
                 project_summary: str = None) -> Path:
    src_dir = manifest.get("srcDir")
    mem = _project_memory_path(src_dir)
    if not mem.exists():
        _write_text(mem, _memory_render_initial(manifest, user_prompt=user_prompt, project_summary=project_summary))
    slug = _slugify(manifest.get("name") or manifest.get("id"))
    _ensure_memory_link(slug, src_dir)
    _memory_index_refresh()
    return mem


def _memory_append(manifest: dict, *, section: str, line: str,
                   frontmatter_updates: dict = None) -> None:
    """在项目 memory 中追加一行。如主体不存在先初始化。"""
    src_dir = manifest.get("srcDir")
    mem = _project_memory_path(src_dir)
    if not mem.exists():
        _memory_init(manifest)
    text = _read_text(mem)
    text = _memory_append_section(text, section, line)
    if frontmatter_updates:
        text = _memory_update_frontmatter(text, frontmatter_updates)
    _write_text(mem, text)
    _memory_index_refresh()


def _memory_index_refresh() -> None:
    """扫 ~/memory/cowork-memory/*.md （主体或 symlink）生成 INDEX.md。"""
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
    rows = []
    for f in sorted(MEMORY_ROOT.glob("*.md")):
        if f.name == "INDEX.md":
            continue
        text = _read_text(f)
        fm, _ = _parse_frontmatter(text)
        rows.append({
            "file": f.name,
            "name": fm.get("name") or f.stem,
            "projectId": fm.get("projectId", "-"),
            "accessUrl": fm.get("accessUrl", ""),
            "workId": fm.get("workId", ""),
        })
    lines = [
        "# Cowork 项目 Memory 索引",
        "",
        f"更新于：{time.strftime('%Y-%m-%d %H:%M:%S')}\u3000共 {len(rows)} 个项目",
        "",
        "| 项目 | Project ID | Work ID | 访问地址 | 文件 |",
        "|------|-----------|---------|----------|------|",
    ]
    for r in rows:
        url = f"[{r['accessUrl']}]({r['accessUrl']})" if r["accessUrl"] else "-"
        lines.append(f"| {r['name']} | `{r['projectId']}` | {r['workId'] or '-'} | {url} | [{r['file']}](./{r['file']}) |")
    _write_text(MEMORY_INDEX, "\n".join(lines) + "\n")


def _memory_archive(manifest: dict) -> None:
    """标记归档，保留历史，不删文件。"""
    src_dir = manifest.get("srcDir")
    if not src_dir:
        return
    mem = _project_memory_path(src_dir)
    if not mem.exists():
        return
    text = _read_text(mem)
    text = _memory_update_frontmatter(text, {"archived": "true", "archivedAt": time.strftime("%Y-%m-%d")})
    text = _memory_append_section(text, "元信息变更", f"- {time.strftime('%Y-%m-%d %H:%M')} — 作品被删除 / 归档")
    _write_text(mem, text)
    _memory_index_refresh()


def _slugify(s: str) -> str:
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s.lower()).strip('-')
    return s[:32] or 'mini-tool'


def cmd_upload(args):
    info_ = upload_file(args.file)
    print(json.dumps(info_, ensure_ascii=False, indent=2))


def cmd_deploy(args):
    dlog("cmd.deploy.start", zip=args.zip, no_wait=args.no_wait, timeout=getattr(args, 'timeout', None))
    s = session()
    # 上传 zip
    if args.zip.endswith(".zip"):
        meta = upload_file(args.zip, mime_type="application/zip", s=s)
    else:
        err("deploy requires a .zip")
    info("🚀 trigger deploy ...")
    dlog("cmd.deploy.trigger.start", file_id=meta["fileId"])
    _t0 = time.time()
    d = deploy_zip(meta["fileId"], zip_name=meta["name"], s=s)
    deployment_id = d["deploymentId"]
    dlog("cmd.deploy.trigger.ok", deployment_id=deployment_id, dur_s=round(time.time()-_t0, 2))
    if args.no_wait:
        info(f"⏭  --no-wait：仅触发 deploy，不轮询 (deploymentId={deployment_id})")
        d.setdefault("deploymentId", deployment_id)
        d["ok"] = True
        d["waiting"] = False
        dlog("cmd.deploy.done", mode="no-wait", deployment_id=deployment_id)
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return
    info(f"⏳ deploymentId={deployment_id}, waiting (timeout {args.timeout}s) ...")
    res = wait_deploy(deployment_id, timeout_s=args.timeout, s=s)
    if res.get("ok"):
        ok(f"deployed: {res.get('accessUrl')}  (appId={res.get('appId')})")
    elif res.get("failed"):
        info(f"⚠️ deploy FAILED: {res.get('errorMessage', '')[:300]}")
    elif res.get("timedOut"):
        info(f"⏱️  {res.get('message', '')}")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res.get("failed"):
        sys.exit(2)
    # 超时不作为 fatal：上游拿到 timedOut=True 可继续轮询


def _scene_tag_keys(tags) -> list:
    """中文标签名 / enum key → enum key 列表（publish / static 共用）。"""
    out = []
    for t in (tags or []):
        if t in SCENE_TAGS:
            out.append(SCENE_TAGS[t])
        elif t in SCENE_TAGS.values():
            out.append(t)
        else:
            info(f"⚠️ 未知标签 {t}, 跳过")
    return out


def _fetch_work_detail(work_id, s=None) -> dict:
    """查作品详情 GET /community/works/{id}。

    返回 WorksDetailDTO，含后端算好的统一字段：
      accessUrl（当前生效访问 URL，直接用，别本地拼）/ alias / workDeployType
      + 生效通道详情（deployment* 或 staticResource*，互斥，另一通道恒 null）

    容错：本函数只用于「拿后端算好的展示值」，是锦上添花。详情接口偶发失败时**绝不能**
    让已成功的部署/save 流程整体失败——失败返回 {}，调用方用本地兜底值（deploy 返回的
    URL）即可。所以这里吞掉 api_call 抛出的 SystemExit / 异常。
    """
    s = s or session()
    try:
        return api_call("GET", f"/community/works/{int(work_id)}", session=s) or {}
    except SystemExit:
        info(f"⚠️ 查作品详情失败（workId={work_id}），用本地兜底 accessUrl")
        return {}
    except Exception as e:
        info(f"⚠️ 查作品详情异常（workId={work_id}）：{e}；用本地兜底")
        return {}


def _infer_src_dir(zip_path, anchor: Optional[str] = None) -> Optional[str]:
    """从 zip 路径反推源码目录。

    publish 只拿到 zip，但 manifest 同步 / transform 提示需要源码目录。约定 pack 产物
    通常是 同名/ 或 同名-guard/ 在 zip 同级。anchor 给定时（如 'install.sh' / 'index.html'）
    要求该锚点文件存在才认；不给则只要目录存在即认（用于 transform 提示这种宽松场景）。
    """
    try:
        zp = Path(zip_path).resolve()
    except Exception:
        return None
    for c in (zp.with_suffix(''), zp.parent / (zp.stem + '-guard')):
        if c.is_dir() and (anchor is None or (c / anchor).exists()):
            return str(c)
    return None


def _publish_static(args, *, zip_meta, cover, ext_platform_id, s):
    """纯前端静态资源挂载发布分支（由 cmd_publish 在 detect 判为 STATIC_RESOURCE 后调用）。

    与应用部署的区别：
      - static_deploy 同步返回（MOUNT_SUCCESS/FAILED），不 wait_deploy 轮询
      - save_work 传 static_resource_id + work_deploy_type=STATIC_RESOURCE
      - 访问 URL 由后端按通道算好（详情 accessUrl，形如 /f/<alias or sr_appId>/），不本地拼
      - 不依赖三件套（纯前端无 install.sh）
    """
    info("🚀 static-deploy（纯前端静态资源挂载，同步）...")
    res = static_deploy(
        zip_meta["fileId"], zip_name=zip_meta["name"],
        ext_platform_id=ext_platform_id,
        deploy_source="SEAL",
        s=s,
    )
    status = res.get("status")
    if status != "MOUNT_SUCCESS":
        info(f"⚠️ static mount FAILED: status={status} {res.get('errorMessage', '')[:300]}")
        info("  💡 静态挂载失败多为打包不合规：根目录须有 index.html、用相对路径、"
             "不得含 install.sh/package.json/node_modules 等黑名单文件。"
             "打包规范见 references/pure-frontend.md")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(2)
    static_resource_id = res.get("staticResourceId")
    app_id = res.get("appId")
    # static_deploy 同步返回已带 accessUrl/rawAccessUrl（后端算好），直接用，不本地拼。
    raw_access_url = res.get("rawAccessUrl")
    mount_url = res.get("accessUrl")
    ok(f"mounted → {mount_url}")

    tag_keys = _scene_tag_keys(args.tags)
    visibility = normalize_visibility(args.visibility)
    links = [{"title": args.title, "url": mount_url}] if mount_url else None
    info("📝 save work（STATIC_RESOURCE）...")
    work_id = save_work(
        name=args.title,
        one_line_intro=args.intro or "",
        description=args.desc or "",
        cover=cover,
        static_resource_id=static_resource_id,
        work_deploy_type=WORK_DEPLOY_TYPE_STATIC,
        alias=args.alias,
        scene_tags=tag_keys,
        version=args.version,
        visibility=visibility,
        links=links,
        notify_on_publish=args.notify,
        work_type="SEAL_DEPLOY",
        display_in_community=False,
        s=s,
    )
    ok(f"published(static): workId={work_id}")

    # 查详情拿后端算好的权威 accessUrl / alias（兜底用 static_deploy 同步返回值）。
    detail = _fetch_work_detail(work_id, s=s) if str(work_id).isdigit() else {}
    final_url = detail.get("accessUrl") or mount_url
    eff_alias = detail.get("alias") or args.alias
    eff_app_id = detail.get("staticResourceAppId") or app_id

    # 推断 srcDir 写 manifest。纯前端无 install.sh，用 index.html 作为锚点。
    src_dir = _infer_src_dir(args.zip, anchor='index.html')
    if src_dir:
        try:
            manifest = _ensure_manifest(src_dir)
            _wid = int(work_id) if isinstance(work_id, (int, str)) and str(work_id).isdigit() else work_id
            manifest['cowork'] = {
                'workId': _wid,
                'workDeployType': detail.get("workDeployType") or WORK_DEPLOY_TYPE_STATIC,
                'staticResourceId': static_resource_id,
                'staticAppId': eff_app_id,
                'alias': eff_alias,
                'accessUrl': final_url,
                'coworkAppUrl': cowork_app_url(_wid) if isinstance(_wid, int) else None,
                'rawAccessUrl': raw_access_url,
                'publishedAt': _now_ms(),
                'visibility': visibility,
            }
            _save_manifest(src_dir, manifest)
            _memory_append(
                manifest,
                section='发布历史',
                line=f"- **v{args.version}** — {time.strftime('%Y-%m-%d %H:%M')} — 首发到 Cowork（静态挂载），alias=`{eff_alias or eff_app_id}`，workId={work_id}，staticResourceId={static_resource_id}",
                frontmatter_updates={
                    'workId': work_id,
                    'alias': eff_alias or eff_app_id,
                    'accessUrl': final_url,
                    'visibility': visibility,
                },
            )
            info(f"updated manifest: {src_dir}/.cowork.json")
        except Exception as e:
            info(f"⚠️ manifest update skipped: {e}")

    _wid = int(work_id) if isinstance(work_id, (int, str)) and str(work_id).isdigit() else work_id
    # 指定了自定义 alias 时，路由层需 ~5s 才把 /f/<alias>/ 同步生效，先等再返回 URL。
    if getattr(args, 'alias', None):
        wait_alias_propagation(eff_alias)
    print(json.dumps({
        "workId": work_id,
        "appId": eff_app_id,
        "workDeployType": detail.get("workDeployType") or WORK_DEPLOY_TYPE_STATIC,
        "staticResourceId": static_resource_id,
        "accessUrl": final_url,
        "rawAccessUrl": raw_access_url,
        "coworkAppUrl": cowork_app_url(_wid) if isinstance(_wid, int) else None,
    }, ensure_ascii=False, indent=2))


def cmd_publish(args):
    dlog("cmd.publish.start", zip=args.zip, title=args.title, alias=getattr(args, 'alias', None),
         work_id=getattr(args, 'work_id', None), visibility=getattr(args, 'visibility', None))
    _t_pub = time.time()
    s = session()
    # 0.-1) 防重复建作品：若传入源码目录且其 .cowork.json 已记录 workId，说明已发布过，
    #       publish 会再建一个新作品（浪费资源 + split-brain）。自动转更新链路 redeploy，
    #       复用已有作品的两通道关联（含跨类型升级）。--force 可强制走首发。
    if os.path.isdir(args.zip) and not getattr(args, 'force', False):
        _existing = _load_manifest(os.path.abspath(args.zip.rstrip('/')))
        _existing_wid = (_existing or {}).get('cowork', {}).get('workId') if _existing else None
        if _existing_wid:
            info(f"↪️  检测到已发布作品 workId={_existing_wid}，自动转 redeploy（更新链路，避免重复建作品）")
            _ra = argparse.Namespace(
                work_id=int(_existing_wid), src=os.path.abspath(args.zip.rstrip('/')),
                zip=None, version=getattr(args, 'version', None), bump=getattr(args, 'bump', None),
                keep=getattr(args, 'keep', None), force=getattr(args, 'force', False),
                no_wait=getattr(args, 'no_wait', False), timeout=getattr(args, 'timeout', DEFAULT_DEPLOY_TIMEOUT_S),
            )
            return cmd_redeploy(_ra)
    # 0.0) 如果传进来的是源码目录（不是 zip），自动先 pack 成 zip。
    #      这让 agent 的心智模型简化为「scaffold → 改代码 → publish <srcDir>」一条龙，
    #      不必先手动 pack。pack_dir 内部已含 prepack（vite/next build）+ keep。
    #      Guard precheck（三件套）挪到 detect 判为应用部署之后才跑——纯前端静态包没有三件套。
    if os.path.isdir(args.zip):
        info(f"📦 publish: 检测到源码目录，先 pack → {args.zip}")
        args.zip = pack_dir(args.zip, in_place=False, keep=getattr(args, 'keep', None))
    # 1) 上传 zip（detect / deploy / static-deploy 都需要 fileId）
    info("⇡ uploading zip ...")
    zip_meta = upload_file(args.zip, mime_type="application/zip", s=s)
    # 2) 上传封面图
    info("⇡ uploading cover ...")
    cover = upload_file(args.cover, s=s)
    # extPlatformId：Seal 链路传 .cowork.json id，便于后端跨部署记录关联
    ext_platform_id = getattr(args, 'ext_platform_id', None)
    if not ext_platform_id:
        zp = Path(args.zip).resolve()
        for c in (zp.with_suffix(''), zp.parent / (zp.stem + '-guard')):
            mf = c / MANIFEST_FILENAME
            if mf.exists():
                try:
                    ext_platform_id = json.loads(mf.read_text()).get("id")
                    if ext_platform_id:
                        break
                except Exception:
                    pass
    # 2.5) detect 代码包类型 → 自动分流静态资源挂载 vs 应用部署
    #      STATIC_RESOURCE          纯前端 → _publish_static（同步挂载，不需三件套 / 不轮询）
    #      APP_DEPLOY_CONVERTED     已转写 → 应用部署（precheck + deploy + wait）
    #      APP_DEPLOY_NOT_CONVERTED 不符合规范 → 直接拦截，提示先 transform（不浪费一次 deploy）
    try:
        det = detect_code_package_type(_file_id_json(zip_meta["fileId"], zip_meta["name"]), s=s)
        pkg_type = (det or {}).get("type")
        det_reason = (det or {}).get("reason", "")
    except SystemExit:
        # detect 接口不可用时不阻断：回退到应用部署旧链路（precheck 兜底）
        pkg_type, det_reason = None, "(detect 接口不可用，回退应用部署)"
    info(f"🔎 detect: type={pkg_type or '?'} — {det_reason}")
    if pkg_type == "STATIC_RESOURCE":
        _publish_static(args, zip_meta=zip_meta, cover=cover, ext_platform_id=ext_platform_id, s=s)
        return
    if pkg_type == "APP_DEPLOY_NOT_CONVERTED" and not args.force:
        _src_hint = _infer_src_dir(args.zip) or args.zip
        err(
            "代码包不符合 Cowork/Guard 子应用规范，未转写，禁止直接部署。\n"
            f"  原因：{det_reason or '缺少 install.sh/start.sh/health.sh 或存在违规依赖'}\n"
            f"  请先转写：python3 cowork.py transform {_src_hint}\n"
            "  转写完成后会自动重新发布；或确认无误用 --force 跳过本检查。"
        )
    # —— 应用部署分支（APP_DEPLOY_CONVERTED / detect 不可用回退）——
    # Guard precheck（三件套等），仅对应用部署有意义；静态分支上面已 return
    issues = precheck_zip(args.zip)
    blockers = [i for i in issues if i.startswith("❌")]
    if blockers and not args.force:
        for i in issues:
            sys.stderr.write(i + "\n")
        err("precheck FAIL；--force 跳过")
    # 复用机器：--deployment-id 显式优先；否则读源码目录 manifest 的 pendingDeploymentId
    # （上次首发 deploy 失败留下的）。避免每次失败重试都新开机器、遗留僵尸机。
    _pub_src_dir = _infer_src_dir(args.zip, anchor='install.sh')
    reuse_dep_id = getattr(args, 'deployment_id', None)
    if reuse_dep_id is None and _pub_src_dir:
        reuse_dep_id = (_load_manifest(_pub_src_dir).get('cowork', {}) or {}).get('pendingDeploymentId')
    info("🚀 deploy ...")
    d = deploy_zip_reuse_or_new(
        zip_meta["fileId"], zip_name=zip_meta["name"],
        reuse_deployment_id=reuse_dep_id,
        ext_platform_id=ext_platform_id,
        deploy_source="SEAL",
        s=s,
    )
    deployment_id = d["deploymentId"]
    info(f"⏳ 部署中（deploymentId={deployment_id}），平台正在 install→start→health，预计数分钟，请稍候 ...")
    res = wait_deploy(deployment_id, timeout_s=args.timeout, s=s)
    if res.get("failed"):
        info(f"⚠️ deploy FAILED: {res.get('errorMessage', '')[:300]}")
        # 记下 deploymentId 到 manifest，修复后重新 publish 同一目录会自动复用这台机器重试，
        # 不再新开机器。机器若已被平台清理，下次复用探活失败会自动降级新建。
        if _pub_src_dir:
            try:
                _m = _ensure_manifest(_pub_src_dir)
                _m.setdefault('cowork', {})
                _m['cowork']['pendingDeploymentId'] = deployment_id
                _save_manifest(_pub_src_dir, _m)
                info(f"📌 已记录 deploymentId={deployment_id} 到 .cowork.json；"
                     "修复代码后重新 publish 同一目录会自动复用这台机器重试（不新开机器）")
            except Exception as e:
                info(f"⚠️ 记录 pendingDeploymentId 失败: {e}")
        res["deploymentId"] = deployment_id
        res["pendingDeploymentId"] = deployment_id
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(2)
    if res.get("timedOut"):
        # 超时不直接放弃 save——首发的目标是「部署成功后必须建作品」。
        # 先宽限续轮询一段（多数是后端慢/本地窗口短），拿到 RUNNING 就继续往下 save。
        info(f"⏱️  {res.get('message', '')}")
        info("⏳ 宽限续轮询，尽力等到 RUNNING 后再 save 作品 ...")
        res = wait_deploy(deployment_id, timeout_s=DEPLOY_GRACE_EXTRA_S, s=s)
        if res.get("failed"):
            info(f"⚠️ deploy FAILED: {res.get('errorMessage', '')[:300]}")
            print(json.dumps(res, ensure_ascii=False, indent=2))
            sys.exit(2)
        if res.get("timedOut") or not res.get("appId"):
            # 实在等不到 RUNNING：返回 pending，让上游/用户后续用 save-after-deploy 补建作品。
            info("⚠️ 仍未 RUNNING——返回 deploymentId，部署完成后请用 "
                 "`cowork.py save-after-deploy --deployment-id <id> ...` 补建作品")
            res.setdefault("action", "poll-then-save")
            res["_pendingSave"] = {
                "title": args.title, "intro": args.intro, "desc": args.desc,
                "alias": args.alias, "tags": args.tags, "visibility": args.visibility,
                "notify": args.notify, "version": args.version,
            }
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return
    app_id = res["appId"]
    access_url = res["accessUrl"]
    ok(f"deployed → {access_url}")
    # 4) save 作品
    tag_keys = []
    for t in (args.tags or []):
        if t in SCENE_TAGS:
            tag_keys.append(SCENE_TAGS[t])
        elif t in SCENE_TAGS.values():
            tag_keys.append(t)
        else:
            info(f"⚠️ 未知标签 {t}, 跳过")
    visibility = normalize_visibility(args.visibility)
    # 首发时作品尚未建，links 暂用 deploy 返回的 raw accessUrl；save 后查详情拿权威 accessUrl。
    links = [{"title": args.title, "url": access_url}]
    info("📝 save work ...")
    try:
        work_id = save_work(
            name=args.title,
            one_line_intro=args.intro or "",
            description=args.desc or "",
            cover=cover,
            deployment_id=deployment_id,
            deployment_alias=args.alias,
            scene_tags=tag_keys,
            version=args.version,
            visibility=visibility,
            links=links,
            notify_on_publish=args.notify,
            work_type="SEAL_DEPLOY",  # Seal 链路固定
            work_deploy_type=WORK_DEPLOY_TYPE_APP,  # 应用部署通道
            display_in_community=False,  # Seal 链路固定 False
            s=s,
        )
    except SystemExit:
        # save 失败最常见是 alias 撞名——多半是「想升级已有作品却走了新建 publish」。
        # 给出纠偏指引：升级应对原作品 redeploy，而非用同名 alias 新建。
        if args.alias:
            info(
                f"✗ 创建作品失败（alias=`{args.alias}` 可能已被占用）。\n"
                "  ⚠️ 如果你本意是【升级已有作品】（如把之前的静态页加后端），"
                "**不应该新建 publish**，而应对原作品 `cowork.py redeploy <原workId>`——\n"
                "     同一作品支持静态↔应用类型来回切换，会复用原 alias、不会撞名。\n"
                "     用 `cowork.py list-projects` 找回原 workId；确认是全新作品则换个 --alias 再发。"
            )
        raise
    ok(f"published: workId={work_id}")

    # 查详情拿后端算好的权威 accessUrl / alias，不本地拼 /s/。
    detail = _fetch_work_detail(work_id, s=s) if str(work_id).isdigit() else {}
    final_url = detail.get("accessUrl") or access_url
    eff_alias = detail.get("alias") or args.alias

    # 推断 srcDir：CLI 只拿到 zip，约定 同名/ 或 同名-guard/ 在 zip 同级，以 install.sh 为锚点。
    src_dir = _infer_src_dir(args.zip, anchor='install.sh')
    if src_dir:
        try:
            manifest = _ensure_manifest(src_dir)
            _work_id_int = int(work_id) if isinstance(work_id, (int, str)) and str(work_id).isdigit() else work_id
            _prev_cowork = manifest.get('cowork') if isinstance(manifest.get('cowork'), dict) else {}
            manifest['cowork'] = {
                **{k: v for k, v in _prev_cowork.items() if k != 'pendingDeploymentId'},  # 成功了，清掉失败遗留的 pendingDeploymentId
                'workId': _work_id_int,
                'workDeployType': detail.get("workDeployType") or WORK_DEPLOY_TYPE_APP,
                'appId': app_id,
                'alias': eff_alias,
                'accessUrl': final_url,
                'coworkAppUrl': cowork_app_url(_work_id_int) if isinstance(_work_id_int, int) else None,
                'rawAccessUrl': access_url,
                'deploymentId': deployment_id,
                'deploymentStatus': 'RUNNING',
                'publishedAt': _now_ms(),
                'visibility': visibility,
            }
            _save_manifest(src_dir, manifest)
            _memory_append(
                manifest,
                section='发布历史',
                line=f"- **v{args.version}** — {time.strftime('%Y-%m-%d %H:%M')} — 首发到 Cowork，alias=`{eff_alias or app_id}`，workId={work_id}，deploymentId={deployment_id}",
                frontmatter_updates={
                    'workId': work_id,
                    'alias': eff_alias or app_id,
                    'accessUrl': final_url,
                    'visibility': visibility,
                },
            )
            info(f"updated manifest: {src_dir}/.cowork.json")
        except Exception as e:
            info(f"⚠️ manifest update skipped: {e}")

    _work_id_int = int(work_id) if isinstance(work_id, (int, str)) and str(work_id).isdigit() else work_id
    # 指定了自定义 alias 时，路由层需 ~5s 才把 /s/<alias>/ 同步生效，先等再返回 URL。
    # 走自动 appId（未指定 --alias）的不需要等，appId 后端即时生效。
    if getattr(args, 'alias', None):
        wait_alias_propagation(eff_alias)
    print(json.dumps({
        "workId": work_id,
        "appId": app_id,
        "workDeployType": detail.get("workDeployType") or WORK_DEPLOY_TYPE_APP,
        "accessUrl": final_url,
        "rawAccessUrl": access_url,
        "deploymentId": deployment_id,
        "coworkAppUrl": cowork_app_url(_work_id_int) if isinstance(_work_id_int, int) else None,
    }, ensure_ascii=False, indent=2))


def cmd_status(args):
    d = deployment_status(args.deployment_id)
    print(json.dumps(d, ensure_ascii=False, indent=2))


def cmd_save_after_deploy(args):
    """后续 save_work 动作拆出来：适用于上游（publish.ts）自己管理 deploy poll 后，
    在拿到 RUNNING 的 deploymentId 后调本命令完成 cover upload + save_work + manifest 回写。

    设计动机：OpenClaw runtime 有3 0s idle cleanup bug（参考 issue #8643），
    plugin spawn cowork.py 超过 30s 会被误杀。cmd_publish 完整走一趟 上传zip+upload
    cover+deploy+wait+save 可能超 1 分钟，会被 cleanup。拆后 plugin 可以拆成：
      1. cowork.py deploy <zip> --no-wait  (上传+触发，拿 deploymentId，5-15s)
      2. cowork.py status <id> 轮询多次（每次几百毫秒，在 plugin 内间隔 2-5s）
      3. cowork.py save-after-deploy --deployment-id <id> --cover ... --title ... （<30s）
    任意一步都 ≤ 25s，不触发 OpenClaw cleanup。
    """
    s = session()

    dlog("cmd.save-after-deploy.start", deployment_id=args.deployment_id, title=args.title,
         alias=getattr(args, 'alias', None))
    _t_save = time.time()
    # 1) 从 deploymentId 拿 RUNNING 状态里的 appId / accessUrl（不再 wait，上游应该已确认状态是 RUNNING）
    d = deployment_status(args.deployment_id, s=s) or {}
    st = d.get("deploymentStatus")
    if st != "RUNNING":
        dlog("cmd.save-after-deploy.bad-status", got=st)
        err(f"save-after-deploy: deploymentId={args.deployment_id} 状态为 {st}，要求 RUNNING。请先所有状态 RUNNING 后再 save。")
    app_id = d.get("appId")
    raw_access_url = d.get("accessUrl")
    if not app_id:
        err(f"save-after-deploy: deployment={args.deployment_id} RUNNING 但未返 appId，不能 save")

    # 2) 上传封面图
    info("⇡ uploading cover ...")
    cover = upload_file(args.cover, s=s)

    # 3) 标签 enum 转换（同 cmd_publish）
    tag_keys = []
    for t in (args.tags or []):
        if t in SCENE_TAGS:
            tag_keys.append(SCENE_TAGS[t])
        elif t in SCENE_TAGS.values():
            tag_keys.append(t)
        else:
            info(f"⚠️ 未知标签 {t}, 跳过")
    visibility = normalize_visibility(args.visibility)
    # 首发时作品未建，links 暂用 deployment 的 raw accessUrl；save 后查详情拿权威 accessUrl。
    links = [{"title": args.title, "url": raw_access_url}] if raw_access_url else None

    # 4) save
    info("📝 save work ...")
    work_id = save_work(
        name=args.title,
        one_line_intro=args.intro or "",
        description=args.desc or "",
        cover=cover,
        deployment_id=args.deployment_id,
        deployment_alias=args.alias,
        work_deploy_type=WORK_DEPLOY_TYPE_APP,
        scene_tags=tag_keys,
        version=args.version,
        visibility=visibility,
        links=links,
        notify_on_publish=args.notify,
        work_type="SEAL_DEPLOY",
        display_in_community=False,
        s=s,
    )
    ok(f"published: workId={work_id}")

    # 查详情拿后端算好的权威 accessUrl / alias，不本地拼 /s/。
    detail = _fetch_work_detail(work_id, s=s) if str(work_id).isdigit() else {}
    final_url = detail.get("accessUrl") or raw_access_url or f"{COWORK_WEB}/s/{args.alias or app_id}"
    eff_alias = detail.get("alias") or args.alias

    # 5) 推断 srcDir + 写 manifest + memory（同 cmd_publish 尾段，但优先用显式传的 --src-dir）
    src_dir = getattr(args, 'src_dir', None) or None
    if not src_dir:
        # 备 fallback：从 zip 推 srcDir（如果上游传了 --zip）
        if getattr(args, 'zip', None):
            zip_path = Path(args.zip).resolve()
            for c in (zip_path.with_suffix(''), zip_path.parent / (zip_path.stem + '-guard')):
                if c.is_dir() and (c / 'install.sh').exists():
                    src_dir = str(c)
                    break
    if src_dir:
        try:
            manifest = _ensure_manifest(src_dir)
            _work_id_int = int(work_id) if isinstance(work_id, (int, str)) and str(work_id).isdigit() else work_id
            manifest['cowork'] = {
                'workId': _work_id_int,
                'workDeployType': detail.get("workDeployType") or WORK_DEPLOY_TYPE_APP,
                'appId': app_id,
                'alias': eff_alias,
                'accessUrl': final_url,
                'coworkAppUrl': cowork_app_url(_work_id_int) if isinstance(_work_id_int, int) else None,
                'rawAccessUrl': raw_access_url,
                'deploymentId': args.deployment_id,
                'deploymentStatus': 'RUNNING',
                'publishedAt': _now_ms(),
                'visibility': visibility,
            }
            _save_manifest(src_dir, manifest)
            _memory_append(
                manifest,
                section='发布历史',
                line=f"- **v{args.version}** — {time.strftime('%Y-%m-%d %H:%M')} — 首发到 Cowork，alias=`{eff_alias or app_id}`，workId={work_id}，deploymentId={args.deployment_id}",
                frontmatter_updates={
                    'workId': work_id,
                    'alias': eff_alias or app_id,
                    'accessUrl': final_url,
                    'visibility': visibility,
                },
            )
            info(f"updated manifest: {src_dir}/.cowork.json")
        except Exception as e:
            info(f"⚠️ manifest update skipped: {e}")

    _work_id_int = int(work_id) if isinstance(work_id, (int, str)) and str(work_id).isdigit() else work_id
    # 指定了自定义 alias 时，路由层需 ~5s 才把 /s/<alias>/ 同步生效，先等再返回 URL。
    if getattr(args, 'alias', None):
        wait_alias_propagation(eff_alias)
    print(json.dumps({
        "workId": work_id,
        "appId": app_id,
        "workDeployType": detail.get("workDeployType") or WORK_DEPLOY_TYPE_APP,
        "accessUrl": final_url,
        "rawAccessUrl": raw_access_url,
        "deploymentId": args.deployment_id,
        "coworkAppUrl": cowork_app_url(_work_id_int) if isinstance(_work_id_int, int) else None,
    }, ensure_ascii=False, indent=2))


def cmd_list(args):
    """
    GET community/user-profile/works?email=<self>&tab=recent
    """
    email = (
        args.email
        or os.environ.get("COWORK_EMAIL")
        or os.environ.get("XHS_USER_EMAIL")
        or os.environ.get("USER_EMAIL")
    )
    if not email:
        try:
            cur = api_call("GET", "/employee/userCurrent")
            if isinstance(cur, dict):
                email = cur.get("email") or cur.get("workEmail")
            elif isinstance(cur, list) and cur:
                email = cur[0].get("email") or cur[0].get("workEmail")
        except Exception:
            pass
    if not email:
        # 不能 hard fail：上层（Coral Studio / plugin）依赖本命令汇总远端作品，
        # 但 desktop fallback / pod 环境未必能拿到当前邮箱。
        # 输出空数组 + stderr 提示，上层只是少拿到 cowork-only，不会整个 Studio 坏掉。
        sys.stderr.write(
            "⚠️ cowork list: 未提供 --email 且无法从 SSO context 推断。\n"
            "  请传 --email <you@xiaohongshu.com> 或设 COWORK_EMAIL 环境变量。\n"
            "  本次返回空数组。\n"
        )
        print("[]")
        return
    url = f"/community/user-profile/works?email={email}&tab={args.tab or 'recent'}"
    data = api_call("GET", url)
    items = data if isinstance(data, list) else (data.get('items') if isinstance(data, dict) else None) or []

    # 默认 enriched：list 接口缺少 deployment* 字段，每项补一次 detail。
    # 设 --raw 可跳过（仅在只要轻量列表时使用）。
    if not getattr(args, 'raw', False):
        s = session()
        for it in items:
            wid = it.get('id')
            if not wid:
                continue
            try:
                detail = api_call('GET', f'/community/works/{wid}', session=s)
                if isinstance(detail, dict):
                    for k in (
                        'deploymentId', 'deploymentAppId', 'deploymentAlias',
                        'deploymentAccessUrl', 'deploymentRawAccessUrl',
                        'deploymentRealPath', 'deploymentStatus',
                        'description', 'linksJson', 'attachmentFile',
                    ):
                        if detail.get(k) is not None and it.get(k) is None:
                            it[k] = detail[k]
            except SystemExit:
                # api_call 失败会 sys.exit；enrich 是 best-effort 不该中断。
                continue
            except Exception:
                continue

    # 汇总后统一加 coworkAppUrl（详情页，Studio 跳转用）。
    for it in items:
        if it.get('id') is not None and not it.get('coworkAppUrl'):
            u = cowork_app_url(it.get('id'))
            if u:
                it['coworkAppUrl'] = u

    print(json.dumps(items, ensure_ascii=False, indent=2))


def cmd_list_my_apps(args):
    """
    GET community/works/my/apps?includeDeployment=true
    走 SSO session，不需 email。一次拉完拿部署信息，比旧 list 快很多。
    返回 List<WorksCardDTO> raw——上层（TS server-method）负责合本地 manifest。
    """
    params = {"includeDeployment": "true"}
    work_type = getattr(args, "work_type", None)
    if work_type:
        params["workType"] = work_type
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    data = api_call("GET", f"/community/works/my/apps?{qs}")
    items = data if isinstance(data, list) else (data.get('items') if isinstance(data, dict) else None) or []

    # 统一补 coworkAppUrl（详情页，Studio 跳转用）。
    for it in items:
        if it.get('id') is not None and not it.get('coworkAppUrl'):
            u = cowork_app_url(it.get('id'))
            if u:
                it['coworkAppUrl'] = u

    print(json.dumps(items, ensure_ascii=False, indent=2))


# -----------------------------------------------------------------------------
# list-projects —— 本地 manifest + 远端作品 merge，输出带 3 状态 chip 的项目列表
# -----------------------------------------------------------------------------
#
# 这是从原 plugin TS（project-registry.ts + list-projects.ts）1:1 移植的逻辑。
# 与 list-my-apps（只拉远端、只能看到已发布作品）的本质区别：
#   list-projects 会扫本地 .cowork.json，因此能列出「本地 scaffold 了但还没
#   publish 的草稿」（local-only），这是 agent / Studio 最关心的状态。
#
# 3 个状态 chip（2026-05-29 帝江拍板，不要 running/stopped）：
#   - published    本地 manifest 有 workId 且远端存在
#   - local-only   本地 manifest 有但远端没有（从未发布 / 远端被删）
#   - cowork-only  远端有但本地无 manifest
# 排序：published > local-only > cowork-only，同类按 updatedAt 倒序。

def _lp_safe_number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if v == int(v) else None
    if isinstance(v, str) and re.fullmatch(r"-?\d+", v):
        return int(v)
    return None


def _lp_visibility_from_scope(scope):
    if not scope:
        return None
    s = str(scope).upper()
    if s in ("PUBLIC", "ALL"):
        return "ALL"
    if s in ("DEPARTMENTS", "PARTIAL"):
        return "PARTIAL"
    if s in ("SELF_ONLY", "SELF"):
        return "SELF_ONLY"
    return None


def _lp_read_manifest(manifest_path: Path):
    """读 + 校验一个 .cowork.json；非法返 None。等价 TS readManifest()。"""
    try:
        raw = manifest_path.read_text()
    except Exception:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    if obj.get("schema") != COWORK_PROJECT_SCHEMA:
        return None
    if not (isinstance(obj.get("id"), str)
            and isinstance(obj.get("name"), str)
            and isinstance(obj.get("srcDir"), str)):
        return None
    return obj


def _lp_scan_manifests(code_root: Path):
    """扫一个根目录的直接子目录里的 .cowork.json。等价 TS scanManifests()。

    去重：同一 manifest.id 出现多次时，优先保留 srcDir 与项目目录自指的那份。
    """
    if not code_root.exists():
        return []
    try:
        entries = list(code_root.iterdir())
    except Exception:
        return []
    hits = []  # (manifest, projDir)
    for child in entries:
        if not child.is_dir():
            continue
        m = _lp_read_manifest(child / MANIFEST_FILENAME)
        if m:
            hits.append((m, child))
    by_id = {}
    for m, proj_dir in hits:
        mid = m["id"]
        existing = by_id.get(mid)
        if existing is None:
            by_id[mid] = (m, proj_dir)
            continue
        ex_m, ex_dir = existing
        existing_self = Path(ex_m["srcDir"]).resolve() == Path(ex_dir).resolve()
        candidate_self = Path(m["srcDir"]).resolve() == Path(proj_dir).resolve()
        if candidate_self and not existing_self:
            by_id[mid] = (m, proj_dir)
    return [v[0] for v in by_id.values()]


def _lp_list_local_projects():
    """扫本地两个根，按 manifest.id 去重，返回半成品 studio project。
    等价 TS listCoworkProjects() + toStudioProject()。"""
    roots = [COWORK_PROJECT_ROOT, LEGACY_PROJECT_ROOT]
    all_manifests = []
    for root in roots:
        all_manifests.extend(_lp_scan_manifests(root))
    # 跨 root 再按 id 去重：updatedAt 新的赢
    dedup = {}
    for m in all_manifests:
        existing = dedup.get(m["id"])
        if existing is None:
            dedup[m["id"]] = m
            continue
        if (m.get("updatedAt") or 0) > (existing.get("updatedAt") or 0):
            dedup[m["id"]] = m
    projects = []
    for m in dedup.values():
        cowork = m.get("cowork") if isinstance(m.get("cowork"), dict) else None
        status = ["published"] if (cowork and cowork.get("workId") is not None) else ["local-only"]
        proj = {
            "id": m["id"],
            "name": m["name"],
            "title": (cowork or {}).get("alias") or m["name"],
            "srcDir": m["srcDir"],
            "stack": m.get("stack"),
            "chatSessionId": m.get("chatSessionId"),
            "guardCompliant": m.get("guardCompliant"),
            "intro": m.get("description"),
            "createdAt": m.get("createdAt"),
            "updatedAt": m.get("updatedAt"),
            "cowork": ({
                "workId": cowork.get("workId"),
                "appId": cowork.get("appId"),
                "alias": cowork.get("alias"),
                "accessUrl": cowork.get("accessUrl"),
                "coworkAppUrl": cowork.get("coworkAppUrl"),
                "deploymentId": cowork.get("deploymentId"),
                "deploymentStatus": cowork.get("deploymentStatus"),
                "publishedAt": cowork.get("publishedAt"),
                "visibility": cowork.get("visibility"),
                "version": cowork.get("version"),
            } if cowork else None),
            "status": status,
        }
        projects.append(proj)
    return projects


def _lp_fetch_my_apps():
    """拉远端我的作品（含部署信息）。失败降级返 []，等价 TS fetchMyApps()。"""
    try:
        data = api_call("GET", "/community/works/my/apps?includeDeployment=true")
    except SystemExit:
        return []
    except Exception:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items") or []
    return []


def _lp_extract_deployment(raw: dict):
    """兼容嵌套 deployment.* 与打平 deployment* 两种布局。等价 TS extractDeployment()。"""
    d = raw.get("deployment") if isinstance(raw.get("deployment"), dict) else {}
    return {
        "deploymentId": _lp_safe_number(d.get("deploymentId")) or _lp_safe_number(raw.get("deploymentId")) or 0,
        "appId": d.get("appId") or raw.get("deploymentAppId") or "",
        "alias": d.get("alias") or raw.get("deploymentAlias") or None,
        "accessUrl": d.get("accessUrl") or raw.get("deploymentAccessUrl") or None,
        "rawAccessUrl": d.get("rawAccessUrl") or raw.get("deploymentRawAccessUrl") or None,
        "deploymentStatus": d.get("deploymentStatus") or raw.get("deploymentStatus") or None,
    }


def _lp_parse_tags(raw: dict):
    """远端 sceneTagsJson(enum) → 中文 label。等价 TS parseTagsField()。"""
    render = raw.get("sceneTagsRenderName")
    if isinstance(render, list):
        arr = [x for x in render if isinstance(x, str) and x]
        if arr:
            return arr
    for c in (raw.get("tags"), raw.get("sceneTagsJson"), raw.get("keywordsJson")):
        arr = None
        if isinstance(c, list):
            arr = [x for x in c if isinstance(x, str)]
        elif isinstance(c, str) and c.strip().startswith("["):
            try:
                parsed = json.loads(c)
                if isinstance(parsed, list):
                    arr = [x for x in parsed if isinstance(x, str)]
            except Exception:
                arr = None
        if arr:
            # SCENE_TAGS 是 {中文: enum}，这里需要 enum → 中文反查
            label_by_enum = {v: k for k, v in SCENE_TAGS.items()}
            return [label_by_enum.get(x, x) for x in arr]
    return None


def _lp_map_remote_cowork(raw: dict, work_id: int):
    dep = _lp_extract_deployment(raw)
    return {
        "workId": work_id,
        "appId": dep["appId"],
        "alias": dep["alias"],
        "accessUrl": dep["accessUrl"] or dep["rawAccessUrl"] or "",
        "coworkAppUrl": cowork_app_url(work_id),
        "deploymentId": dep["deploymentId"],
        "deploymentStatus": dep["deploymentStatus"],
        "visibility": _lp_visibility_from_scope(raw.get("visibilityScope")),
        "publishedAt": raw.get("updatedAt") if raw.get("updatedAt") is not None else raw.get("createdAt"),
        "version": raw.get("version"),
    }


def _lp_remote_to_studio(raw: dict):
    work_id = _lp_safe_number(raw.get("id")) if raw.get("id") is not None else _lp_safe_number(raw.get("workId"))
    if work_id is None:
        return None
    dep = _lp_extract_deployment(raw)
    return {
        "id": f"cowork-only:{work_id}",
        "name": raw.get("name") or dep["alias"] or f"Work {work_id}",
        "title": dep["alias"] or raw.get("name"),
        "intro": raw.get("oneLineIntro"),
        "description": raw.get("description"),
        "tags": _lp_parse_tags(raw),
        "updatedAt": raw.get("updatedAt") if raw.get("updatedAt") is not None else raw.get("createdAt"),
        "cowork": _lp_map_remote_cowork(raw, work_id),
        "status": ["cowork-only"],
    }


def _lp_first(*vs):
    for v in vs:
        if isinstance(v, str) and v:
            return v
    return None


def cmd_list_projects(args):
    """本地 manifest + 远端作品 merge，输出带 3 状态 chip 的项目列表。

    输出 JSON: { projects: [...], refreshedAt: <ms> }
    """
    local_projects = _lp_list_local_projects()
    remote_works = _lp_fetch_my_apps()

    remote_by_wid = {}
    for r in remote_works:
        wid = _lp_safe_number(r.get("id")) if r.get("id") is not None else _lp_safe_number(r.get("workId"))
        if wid is not None:
            remote_by_wid[wid] = r

    local_wids = set()
    merged = []
    # 第一遍：本地 manifest，重算 status，published 时用远端字段兜底
    for proj in local_projects:
        new_status = []
        cowork = proj.get("cowork") or {}
        wid = cowork.get("workId")
        if wid is not None:
            local_wids.add(wid)
            remote = remote_by_wid.get(wid)
            if remote:
                new_status.append("published")
                proj = {
                    **proj,
                    "title": _lp_first(remote.get("name"), remote.get("deploymentAlias"), proj.get("title")),
                    "intro": _lp_first(remote.get("oneLineIntro"), proj.get("intro")),
                    "description": _lp_first(remote.get("description"), proj.get("description")),
                    "tags": _lp_parse_tags(remote) or proj.get("tags"),
                    "updatedAt": remote.get("updatedAt") if remote.get("updatedAt") is not None
                                 else (remote.get("createdAt") if remote.get("createdAt") is not None else proj.get("updatedAt")),
                    "cowork": {**(proj.get("cowork") or {}), **_lp_map_remote_cowork(remote, wid)},
                }
            else:
                new_status.append("local-only")
        else:
            new_status.append("local-only")
        merged.append({**proj, "status": new_status})

    # 第二遍：远端 workId 没出现在本地 → cowork-only
    for wid, raw in remote_by_wid.items():
        if wid in local_wids:
            continue
        studio = _lp_remote_to_studio(raw)
        if studio:
            merged.append(studio)

    # 排序：published > local-only > cowork-only，同类按 updatedAt 倒序
    def rank(p):
        st = p.get("status") or []
        if "published" in st:
            return 0
        if "local-only" in st:
            return 1
        if "cowork-only" in st:
            return 2
        return 3

    def updated_key(p):
        return p.get("updatedAt") or (p.get("cowork") or {}).get("publishedAt") or 0

    merged.sort(key=lambda p: (rank(p), -(updated_key(p) or 0)))

    print(json.dumps({"projects": merged, "refreshedAt": _now_ms()},
                     ensure_ascii=False, indent=2))


def cmd_detail(args):
    data = api_call("GET", f"/community/works/{args.id}")
    if isinstance(data, dict) and data.get('id') is not None and not data.get('coworkAppUrl'):
        u = cowork_app_url(data.get('id'))
        if u:
            data['coworkAppUrl'] = u
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_link(args):
    """把一个本地代码目录 link 到已发布的 cowork 作品上。

    使用场景（低频不规则）：
      - 多端开发： A 机首发 workId=100，B 机 git clone 后 link
      - 重装系统 / 项目从别处 cp 来 / 手动 rm 了 .cowork.json

    步骤：
      1. precheck srcDir——不合规拒绝，让用户先走 transform
      2. 检查 srcDir 是否已有 .cowork.json：
         - 已有且 workId 相同 → 幂等返回
         - 已有但 workId 不同 → 拒绝（避免静默覆盖原 manifest）
      3. 检查该 workId 是否已被别的目录 link（避免 split-brain）
      4. 拉远端 detail 拿 alias / accessUrl / visibility
      5. 写 manifest：workId / alias / accessUrl / coworkAppUrl / deploymentId / visibility 全入 cowork 块
    """
    work_id = int(args.work_id)
    src_dir = os.path.abspath(args.src_dir)
    if not os.path.isdir(src_dir):
        err(f"srcDir 不是目录: {src_dir}")

    # Step 1: precheck——不合规拒绝。直调函数级 precheck_dir 拿 issues，避免 cmd_precheck 里 sys.exit。
    info(f"⏳ precheck {src_dir}…")
    issues = precheck_dir(src_dir)
    fatal_issues = [i for i in issues if i.startswith("❌")]
    if fatal_issues:
        err_msg = (
            "precheck 不过。不能 link——请先走 `python3 cowork.py transform "
            + src_dir
            + "` 改写为 Guard 子应用。\nprecheck issues:\n"
            + "\n".join(fatal_issues[:20])
        )
        err(err_msg)

    # Step 2: 检查已存在 manifest
    manifest_path = Path(src_dir) / MANIFEST_FILENAME
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text())
        except Exception:
            existing = None
        existing_wid = (existing or {}).get("cowork", {}).get("workId") if existing else None
        if existing_wid == work_id:
            info(f"幂等：{manifest_path} 已是 workId={work_id}的 manifest")
            print(json.dumps({
                "ok": True,
                "projectId": existing.get("id"),
                "srcDir": src_dir,
                "manifestPath": str(manifest_path),
                "workId": work_id,
                "accessUrl": (existing.get("cowork") or {}).get("accessUrl", ""),
                "alreadyLinked": True,
            }, ensure_ascii=False, indent=2))
            return
        if existing_wid is not None:
            err(
                f"srcDir 已经 link 到 workId={existing_wid}，不能改 link 到 workId={work_id}。\n"
                f"如要切换 link，先手动 rm {manifest_path}"
            )

    # Step 3: 检查该 workId 已被别的目录 link——避免 split-brain
    for manifests_root in (COWORK_PROJECT_ROOT, LEGACY_PROJECT_ROOT):
        if not manifests_root.exists():
            continue
        for child in manifests_root.iterdir():
            mf = child / MANIFEST_FILENAME
            if not mf.exists():
                continue
            try:
                m = json.loads(mf.read_text())
            except Exception:
                continue
            other_wid = (m.get("cowork") or {}).get("workId")
            other_src = m.get("srcDir")
            if other_wid == work_id and other_src and Path(other_src).resolve() != Path(src_dir).resolve():
                err(
                    f"workId={work_id} 已 link 到其他目录: {other_src}\n"
                    f"不能同时 link 到两个目录（会出现 redeploy 走哪个 srcDir 不确定的 split-brain）。\n"
                    f"如要迁移到 {src_dir}，先 rm {mf}"
                )

    # Step 4: 拉远端 detail
    info(f"⏳ 拉远端 detail workId={work_id}…")
    detail = api_call("GET", f"/community/works/{work_id}")
    if not detail or not isinstance(detail, dict):
        err(f"远端未找到 workId={work_id} 的作品。")

    alias = detail.get("deploymentAlias") or detail.get("alias")
    deployment_id = detail.get("deploymentId") or 0
    deployment_app_id = detail.get("deploymentAppId") or ""
    access_url = (
        detail.get("deploymentAccessUrl")
        or detail.get("deploymentRawAccessUrl")
        or (f"{COWORK_WEB}/s/{alias}" if alias else "")
    )
    if not access_url:
        err(f"work {work_id} 详情缺 accessUrl/alias/appId，无法 link。")
    visibility = detail.get("visibility") or detail.get("visibilityScope") or "SELF_ONLY"
    if visibility == "PUBLIC":
        visibility = "ALL"
    elif visibility == "DEPARTMENTS":
        visibility = "PARTIAL"

    # Step 5: 写 manifest
    now = _now_ms()
    name = detail.get("name") or detail.get("title") or alias or Path(src_dir).name
    manifest = {
        "schema": COWORK_PROJECT_SCHEMA,
        "id": _new_project_id(),
        "name": name,
        "srcDir": src_dir,
        "createdAt": now,
        "updatedAt": now,
        "createdBy": "cowork-cli-link",
        "guardCompliant": True,
        "cowork": {
            "workId": work_id,
            "appId": deployment_app_id,
            "alias": alias,
            "accessUrl": access_url,
            "coworkAppUrl": cowork_app_url(work_id),
            "deploymentId": deployment_id,
            "deploymentStatus": detail.get("deploymentStatus"),
            "visibility": visibility,
            "publishedAt": detail.get("updatedAt") or detail.get("createdAt") or now,
            "version": detail.get("version") or "1.0",
            "intro": detail.get("oneLineIntro"),
            "desc": detail.get("description"),
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    ok(f"linked → {manifest_path}")
    print(json.dumps({
        "ok": True,
        "projectId": manifest["id"],
        "srcDir": src_dir,
        "manifestPath": str(manifest_path),
        "workId": work_id,
        "accessUrl": access_url,
    }, ensure_ascii=False, indent=2))


def cmd_set_visibility(args):
    """
    UI 专用的可见性设置——不过 cmd_update 的 agent guard。

    “放大可见范围不能动”是给 agent 设的防误操作，但 UI 是用户主动点击选范围，没该限制。
    本函数只改 visibility / visibleUserIds / visibleDepartmentIds 三个字段，其他字段沿用远端原值，
    避免需要重传封面/imagesJson/links 等东西。

    根据接口文档 4.可见性校验规则：
      PUBLIC      → 名单传了会被后端忽略，提前清掉
      DEPARTMENTS → visibleUserIds / visibleDepartmentIds 至少一个非空
      SELF_ONLY   → 两个名单都不能传
    """
    work_id_arg = args.work_id
    visibility = normalize_visibility(args.visibility)
    visible_user_ids = args.visible_user_ids
    visible_department_ids = args.visible_department_ids

    # 名单与范围联动校验——提前拦住，避免 4xx
    if visibility == "DEPARTMENTS":
        if not visible_user_ids and not visible_department_ids:
            err("DEPARTMENTS 可见需要至少一个部门或一个人员")
    elif visibility == "SELF_ONLY":
        if visible_user_ids or visible_department_ids:
            err("SELF_ONLY 仅自己可见不可传名单")
        visible_user_ids = None
        visible_department_ids = None
    elif visibility == "PUBLIC":
        # 后端会忽略，提前清掉以免误导
        visible_user_ids = None
        visible_department_ids = None

    s = session()
    work = api_call("GET", f"/community/works/{work_id_arg}", session=s)
    if not work:
        err(f"work not found: {work_id_arg}")

    # 复用远端原值，只改可见性三字段
    existing_images = []
    try:
        existing_images = json.loads(work.get("imagesJson") or "[]") or []
    except Exception:
        existing_images = []
    existing_cover = next((img for img in existing_images if img.get("type") == "cover"), None)
    existing_extras = [img for img in existing_images if img.get("type") != "cover"]
    cover = {k: v for k, v in existing_cover.items() if k != "type"} if existing_cover else None

    try:
        scene_tags = json.loads(work.get("sceneTagsJson") or "[]")
    except Exception:
        scene_tags = []
    try:
        existing_links = json.loads(work.get("linksJson") or "[]")
    except Exception:
        existing_links = []

    save_work(
        name=work.get("name") or "",
        one_line_intro=work.get("oneLineIntro") or "",
        description=work.get("description") or "",
        cover=cover,
        # 通道 ID 按详情原样透传（互斥），只改可见性，不动部署关联。
        deployment_id=work.get("deploymentId"),
        static_resource_id=work.get("staticResourceId"),
        deployment_alias=work.get("alias") or work.get("deploymentAlias"),
        scene_tags=scene_tags,
        version=work.get("version") or "1.0",
        visibility=visibility,
        visible_user_ids=visible_user_ids,
        visible_department_ids=visible_department_ids,
        links=existing_links,
        notify_on_publish=False,
        work_type=work.get("workType") or "COWORK_DEPLOY",
        extra_images=existing_extras or None,
        work_id=int(work_id_arg),
        s=s,
    )

    out = {
        "ok": True,
        "workId": int(work_id_arg),
        "visibility": visibility,
    }
    if visible_user_ids:
        out["visibleUserIds"] = visible_user_ids
    if visible_department_ids:
        out["visibleDepartmentIds"] = visible_department_ids
    print(json.dumps(out, ensure_ascii=False, indent=2))


REDCITY_SEARCH_URL = "https://redcity.xiaohongshu.com/searchgateway/api/search/integrated/search"
EHR_FIND_USER_URL = "https://city.xiaohongshu.com/oasis/api/ehr/common/commonController/findUserInfoByValue"


def _redcity_session():
    """复用 session() 的 SSO cookie，但 base URL 不同。"""
    return session()


def cmd_search_users(args):
    """员工搜索——GET ehr/findUserInfoByValue。
    返回字段精简成 UI 需要的 schema。给 cowork.search_users RPC 用。
    """
    keyword = (args.keyword or "").strip()
    if not keyword:
        print(json.dumps({"users": []}, ensure_ascii=False))
        return
    s = _redcity_session()
    try:
        resp = s.get(
            EHR_FIND_USER_URL,
            params={"value": keyword, "isIncludingLeaving": "false"},
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json() or {}
    except Exception as e:
        err(f"search_users failed: {e}")
        return
    raw = body.get("data") or []
    users = []
    for u in raw:
        if not isinstance(u, dict):
            continue
        users.append({
            "userId": str(u.get("userID") or ""),
            "name": u.get("showName") or u.get("userName") or "",
            "redName": u.get("redName"),
            "email": u.get("email"),
            "redEmail": u.get("redEmail"),
            "departmentId": u.get("departmentId"),
            "departmentPath": u.get("departmentNamesPath") or [],
            "avatarUrl": u.get("avatarUrl"),
        })
    print(json.dumps({"users": users}, ensure_ascii=False, indent=2))


def cmd_search_contacts(args):
    """部门 + 人员混合搜索——POST redcity searchgateway integrated/search。
    返回字段精简成 UI 需要的 schema。给 cowork.search_contacts RPC 用。
    """
    keyword = (args.keyword or "").strip()
    if not keyword:
        print(json.dumps({"users": [], "departments": [], "chats": []}, ensure_ascii=False))
        return
    types = args.types or "account,department"

    s = _redcity_session()
    payload = {
        "query": keyword,
        "paramsMap": {
            "queryDataTypes": types,
            "chatBizStatus": "1",
            "chatStatus": "1",
            "tagSyncStatus": "finished_sync|sync_ing",
            "includeAccountType": "1,2,5,6,11,14,16",
        },
    }
    try:
        resp = s.post(REDCITY_SEARCH_URL, json=payload, timeout=15)
        resp.raise_for_status()
        body = resp.json() or {}
    except Exception as e:
        err(f"search_contacts failed: {e}")
        return

    records = (body.get("data") or {}).get("itemRecords") or []
    out = {"users": [], "departments": [], "chats": []}
    for rec in records:
        items = rec.get("items") or []
        for it in items:
            ext = it.get("extInfo") or {}
            if "departmentNamePath" in ext and "departmentId" in ext and not ext.get("email"):
                # 部门
                out["departments"].append({
                    "departmentId": str(ext.get("departmentId")),
                    "name": it.get("title") or ext.get("department") or "",
                    "path": (ext.get("departmentNamePath") or "").split(",") if isinstance(ext.get("departmentNamePath"), str) else (ext.get("departmentNamePath") or []),
                    "departmentLevel": ext.get("departmentLevel"),
                    "parentDepartmentId": ext.get("parentDepartmentId"),
                })
            elif ext.get("email") or ext.get("userId"):
                # 人员——返 userId（数字字符串），visibleUserIds 接收这个。
                out["users"].append({
                    "userId": str(ext.get("userId") or ""),
                    "accountId": ext.get("accountId") or it.get("bizId"),  # = email
                    "email": ext.get("email") or it.get("bizId"),
                    "redEmail": ext.get("redEmail"),
                    "name": ext.get("redNameAndFirstName") or ext.get("fullName") or it.get("title") or "",
                    "redName": ext.get("redName"),
                    "departmentId": str(ext.get("departmentId") or ""),
                    "departmentPath": (ext.get("departmentNamePath") or "").split(",") if isinstance(ext.get("departmentNamePath"), str) else (ext.get("departmentNamePath") or []),
                    "avatarUrl": ext.get("avatarUrl") or it.get("avatarUrl"),
                })
            elif "chatId" in ext or it.get("title"):
                # 群聊
                out["chats"].append({
                    "chatId": str(ext.get("chatId") or it.get("bizId") or ""),
                    "name": it.get("title") or "",
                    "avatarUrl": it.get("avatarUrl"),
                    "memberCount": ext.get("memberCount"),
                })
    print(json.dumps(out, ensure_ascii=False, indent=2))


# ============================================================
# resolve-department-names：按 ID 反查部门名字 + 路径。
#
# **为什么这么设计**：
# EHR 端 getDepartmentName 接口不支持按 ID 反查，只能一次拉全树。但部门信息
# 属于安全敏感数据，plugin 不应缓存全树。权衡后的方案：
#
#   1. 每次 RPC 实时拉全树（~200KB / 80-200ms）
#   2. 进内存过滤出 client 请求的 N 个 ID
#   3. 计算 path
#   4. 返 N 条（不返全树）。全树随函数栈释放 GC，不入进程内 cache
#
# 这样 plugin 保持严格无状态，client 也不会拿到全公司组织结构。
# ============================================================

def _fetch_department_tree():
    """拉全公司部门树。**不缓存**，每次调都走真接口。"""
    s = session()
    url = (
        "https://city.xiaohongshu.com/oasis/api/ehr/org/"
        "departmentManageController/getDepartmentName?needChildren=true"
    )
    r = s.get(url, timeout=20)
    r.raise_for_status()
    body = r.json() if r.content else {}
    data = body.get("data") or []
    if not isinstance(data, list):
        raise SystemExit(f"resolve-department-names: unexpected response shape: {body!r}")
    return data


def cmd_resolve_department_names(args):
    requested = list(dict.fromkeys(  # 去重保顺
        (s.strip() for s in (args.ids or []) if s and s.strip())
    ))
    if not requested:
        print(json.dumps({"departments": []}, ensure_ascii=False, indent=2))
        return

    raw = _fetch_department_tree()

    # 建临时 by_id 索引（这个 dict 随函数返回 GC，不进缓存）
    by_id = {}
    for d in raw:
        did = d.get("id")
        if did is None:
            continue
        did_str = str(did)
        by_id[did_str] = {
            "name": d.get("departmentName") or "",
            "parentId": str(d.get("parentId")) if d.get("parentId") is not None else None,
        }

    def compute_path(node_id, _seen=None):
        if _seen is None:
            _seen = set()
        if node_id in _seen:
            return []
        _seen.add(node_id)
        node = by_id.get(node_id)
        if not node:
            return []
        parent_id = node["parentId"]
        if not parent_id or parent_id == node_id or parent_id not in by_id:
            return [node["name"]]
        return compute_path(parent_id, _seen) + [node["name"]]

    out = []
    for did in requested:
        node = by_id.get(did)
        if node:
            out.append({
                "id": did,
                "name": node["name"],
                "path": compute_path(did),
            })
        else:
            out.append({
                "id": did,
                "name": None,
                "path": [],
            })

    print(json.dumps({"departments": out}, ensure_ascii=False, indent=2))


def cmd_delete(args):
    if not args.yes:
        sys.stderr.write(f"⚠️ 将删除 work {args.id}，加 --yes 确认\n")
        sys.exit(1)
    # 先找本地 manifest，删除后标记 memory archived（不删历史）。
    manifest_to_archive = None
    try:
        for manifests_root in (COWORK_PROJECT_ROOT, LEGACY_PROJECT_ROOT):
            if not manifests_root.exists():
                continue
            for child in manifests_root.iterdir():
                mp = child / MANIFEST_FILENAME
                if not mp.exists():
                    continue
                try:
                    m = json.loads(mp.read_text())
                except Exception:
                    continue
                if (m.get('cowork') or {}).get('workId') == int(args.id):
                    manifest_to_archive = m
                    break
            if manifest_to_archive:
                break
    except Exception:
        pass
    api_call("POST", "/community/works/delete", json={"id": int(args.id)})
    if manifest_to_archive:
        _memory_archive(manifest_to_archive)
    ok(f"deleted work {args.id}")


def cmd_set_alias(args):
    """为已发布作品设置/修改别名（统一入口，应用部署 + 静态资源都支持）。

    走 save 接口的 alias 字段——后端按部署类型统一改别名（应用走 deployment、静态走
    static-resource），CLI 不分类型、不拼 URL。改完查详情拿后端算好的 accessUrl。

    （历史的 PUT /deployment/{deploymentId}/alias 仅应用部署可用，静态作品无 deploymentId，
    故不再用它；该接口保留作快速改别名的补充入口，set_deployment_alias() 仍在但本命令不调。）
    """
    if not (3 <= len(args.alias) <= 32) or not ALIAS_REGEX.match(args.alias):
        err(f"别名不合法：{args.alias} (需 3-32 位小写字母/数字/-，不能以 - 开头/结尾，不能 --)")
    s = session()
    work_id = int(args.work_id)
    work = api_call("GET", f"/community/works/{work_id}", session=s)
    if not work:
        err(f"work not found: {work_id}")
    cur_alias = work.get("alias") or work.get("deploymentAlias") or work.get("staticResourceAlias")
    cowork_app_link = cowork_app_url(work_id)
    if cur_alias == args.alias:
        info(f"alias 未变（当前 {cur_alias}），跳过")
        result = {
            "workId": work_id,
            "alias": cur_alias,
            "accessUrl": work.get("accessUrl"),
            "coworkAppUrl": cowork_app_link,
            "changed": False,
        }
    else:
        # 走 save 统一改别名：复用远端字段，只覆盖 alias；通道 ID 按详情原样透传（互斥）。
        existing_images = _json_loads_safe(work.get("imagesJson"), []) or []
        cover = next((img for img in existing_images if img.get("type") == "cover"), None)
        extras = [img for img in existing_images if img.get("type") != "cover"]
        if cover:
            cover = {k: v for k, v in cover.items() if k != "type"}
        _vis = normalize_visibility(work.get("visibilityScope") or "SELF_ONLY")
        _vusers = work.get("visibleUserIds") if _vis == "DEPARTMENTS" else None
        _vdepts = work.get("visibleDepartmentIds") if _vis == "DEPARTMENTS" else None
        save_work(
            name=work.get("name") or "",
            one_line_intro=work.get("oneLineIntro") or "",
            description=work.get("description") or "",
            cover=cover,
            deployment_id=work.get("deploymentId"),
            static_resource_id=work.get("staticResourceId"),
            alias=args.alias,
            scene_tags=_json_loads_safe(work.get("sceneTagsJson"), []) or [],
            version=work.get("version") or "1.0",
            visibility=_vis,
            visible_user_ids=_vusers,
            visible_department_ids=_vdepts,
            links=_json_loads_safe(work.get("linksJson"), []) or [],
            notify_on_publish=False,
            work_type=work.get("workType") or "COWORK_DEPLOY",
            extra_images=extras or None,
            work_id=work_id,
            s=s,
        )
        # 改完查详情拿后端算好的 accessUrl / alias（按生效通道，应用 /s/、静态 /f/）。
        detail = _fetch_work_detail(work_id, s=s)
        eff_alias = detail.get("alias") or args.alias
        access_url = detail.get("accessUrl")
        ok(f"alias {cur_alias or '(null)'} → {eff_alias}")
        # alias 改完后路由层需 ~5s 才生效，先等再返回 URL，避免用户拿到暂时打不开的链接
        wait_alias_propagation(eff_alias)
        result = {
            "workId": work_id,
            "alias": eff_alias,
            "accessUrl": access_url,
            "coworkAppUrl": cowork_app_link,
            "changed": True,
            "previousAlias": cur_alias,
        }
        # 同步本地 manifest + memory
        synced_src_dir: Optional[str] = None
        synced_manifest: Optional[dict] = None
        try:
            for manifests_root in (COWORK_PROJECT_ROOT, LEGACY_PROJECT_ROOT):
                if not manifests_root.exists():
                    continue
                for child in manifests_root.iterdir():
                    mf = child / MANIFEST_FILENAME
                    if not mf.exists():
                        continue
                    try:
                        m = json.loads(mf.read_text())
                    except Exception:
                        continue
                    c = m.get("cowork") or {}
                    if c.get("workId") == work_id:
                        c["alias"] = eff_alias
                        c["accessUrl"] = access_url
                        m["cowork"] = c
                        mf.write_text(json.dumps(m, ensure_ascii=False, indent=2))
                        result["manifestUpdated"] = str(child)
                        synced_src_dir = str(child)
                        # 补 srcDir 让 _memory_append 使用
                        synced_manifest = dict(m)
                        synced_manifest["srcDir"] = str(child)
                        break
                if synced_src_dir:
                    break
        except Exception as e:
            info(f"⚠️ sync manifest failed: {e}")

        # 同步 .cowork/memory.md：frontmatter 换 alias / accessUrl + 在「部署历史」加一行
        if synced_manifest:
            try:
                _memory_append(
                    synced_manifest,
                    section="部署历史",
                    line=(
                        f"- **alias 变更** — {time.strftime('%Y-%m-%d %H:%M')} — "
                        f"`{cur_alias or '(null)'}` → `{eff_alias}`，"
                        f"新 URL {access_url}"
                    ),
                    frontmatter_updates={
                        "alias": eff_alias,
                        "accessUrl": access_url,
                    },
                )
                result["memoryUpdated"] = True
            except Exception as e:
                info(f"⚠️ sync memory.md failed: {e}")
    if getattr(args, 'json', False):
        print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_update(args):
    """仅更新作品元信息（标题 / 简介 / 封面 / alias / 可见范围 / 标签），不重新部署。

    部分更新：未传的 flag 保留远端原值。
    --cover 未传时不调 ROS 上传，复用远端已有 cover fileId。
    """
    work_id_arg = args.work_id
    has_change = any([
        args.title is not None,
        args.intro is not None,
        args.desc is not None,
        args.alias is not None,
        args.cover is not None,
        args.visibility is not None,
        args.tags is not None,
    ])
    if not has_change:
        print(json.dumps({
            "ok": True,
            "noChange": True,
            "workId": int(work_id_arg) if str(work_id_arg).isdigit() else work_id_arg,
        }, ensure_ascii=False, indent=2))
        return

    s = session()
    work = api_call("GET", f"/community/works/{work_id_arg}", session=s)
    if not work:
        err(f"work not found: {work_id_arg}")

    # 封面：传了才传 ROS；否则复用现有 cover dict。
    existing_images = []
    try:
        existing_images = json.loads(work.get("imagesJson") or "[]") or []
    except Exception:
        existing_images = []
    existing_cover = next((img for img in existing_images if img.get("type") == "cover"), None)
    existing_extras = [img for img in existing_images if img.get("type") != "cover"]

    if args.cover is not None:
        info("⇡ uploading new cover ...")
        cover = upload_file(args.cover, s=s)
    elif existing_cover:
        # 复用远端 cover dict（保留 fileId / url 等）
        cover = {k: v for k, v in existing_cover.items() if k != "type"}
    else:
        cover = None  # 远端原本就没封面的谜之 case

    # tags：中文名 → enum key，与 publish 保持一致。
    if args.tags is not None:
        tag_keys = []
        for t in args.tags:
            if t in SCENE_TAGS:
                tag_keys.append(SCENE_TAGS[t])
            elif t in SCENE_TAGS.values():
                tag_keys.append(t)
            else:
                info(f"⚠️ unknown tag {t}, skipped")
        scene_tags = tag_keys
    else:
        try:
            scene_tags = json.loads(work.get("sceneTagsJson") or "[]")
        except Exception:
            scene_tags = []

    # visibility： CLI 简写 → enum，同时兼容旧名 ALL/PARTIAL。
    # 「放大」（备 -> all / partial）由 CLI 提前拦住，引导去 Cowork Studio Web 端。
    if args.visibility is not None:
        visibility = normalize_visibility(args.visibility)
        if visibility in ("PUBLIC", "DEPARTMENTS"):
            err(
                "放大可见范围（全公司 PUBLIC / 部分可见 DEPARTMENTS）的操作在 CLI / agent 处一律拒绝。"
                "\n原因：一次手抖会把内部工具面向全公司，且内网没有授权接口让 agent 查 departmentId/userId。"
                "\n请去 https://cowork.xiaohongshu.com/ 找到该作品，在「Edit Metadata」里手动选择部门/人员。"
            )
    else:
        visibility = normalize_visibility(work.get("visibilityScope") or "SELF_ONLY")

    new_alias = args.alias if args.alias is not None else work.get("alias") or work.get("deploymentAlias")

    # links：如果 alias 变了，同步更新默认链接；否则保留原 links。
    # URL 用后端算好的 accessUrl（已按生效通道，应用 /s/、静态 /f/），不本地拼。
    try:
        existing_links = json.loads(work.get("linksJson") or "[]")
    except Exception:
        existing_links = []
    if args.alias is not None or args.title is not None:
        title_for_link = args.title if args.title is not None else (work.get("name") or "")
        access_url = work.get("accessUrl") or f"{COWORK_WEB}/s/{new_alias or work.get('deploymentAppId') or ''}"
        existing_links = [{"title": title_for_link, "url": access_url}]

    body_name = args.title if args.title is not None else work.get("name")
    body_intro = args.intro if args.intro is not None else (work.get("oneLineIntro") or "")
    body_desc = args.desc if args.desc is not None else (work.get("description") or "")

    # visibility 与名单的联动校验（后端文档 4.可见性校验规则）：
    #   PUBLIC      → 名单传了会被忽略
    #   DEPARTMENTS → visibleUserIds / visibleDepartmentIds 至少一个非空
    #   SELF_ONLY   → 名单都不能传，传了后端报错
    # 错误提前在 CLI 抦住比发到服务端被 4xx 友好。
    visible_user_ids = args.visible_user_ids
    visible_department_ids = args.visible_department_ids
    if visibility == "DEPARTMENTS":
        if not visible_user_ids and not visible_department_ids:
            # 保留远端原有名单（部分可见只改别的字段场景）。
            # 后端 detail 返的字段名是 visibleUserIds / visibleDepartmentIds（数组），
            # 老版本可能过 *Json 名字传 JSON 字符串——两者都兼容。
            existing_users = work.get("visibleUserIds")
            existing_depts = work.get("visibleDepartmentIds")
            if existing_users is None:
                existing_users = _json_loads_safe(work.get("visibleUserIdsJson"), [])
            if existing_depts is None:
                existing_depts = _json_loads_safe(work.get("visibleDepartmentIdsJson"), [])
            if isinstance(existing_users, list) and existing_users:
                visible_user_ids = existing_users
            if isinstance(existing_depts, list) and existing_depts:
                visible_department_ids = existing_depts
        if not visible_user_ids and not visible_department_ids:
            err("DEPARTMENTS 可见需要至少一个部门或一个人员，请同时传 --visible-departments / --visible-users")
    elif visibility == "SELF_ONLY":
        if visible_user_ids or visible_department_ids:
            err("SELF_ONLY 仅自己可见不可传名单（--visible-users / --visible-departments）")
        visible_user_ids = None
        visible_department_ids = None
    elif visibility == "PUBLIC":
        # 名单会被后端忽略，清掉以免误导
        visible_user_ids = None
        visible_department_ids = None

    new_work_id = save_work(
        name=body_name,
        one_line_intro=body_intro,
        description=body_desc,
        cover=cover,
        # 通道 ID 按详情原样透传（互斥，生效通道有值、另一通道 null），不改类型。
        deployment_id=work.get("deploymentId"),
        static_resource_id=work.get("staticResourceId"),
        deployment_alias=new_alias,
        scene_tags=scene_tags,
        version=work.get("version") or "1.0",
        visibility=visibility,
        visible_user_ids=visible_user_ids,
        visible_department_ids=visible_department_ids,
        links=existing_links,
        notify_on_publish=False,
        work_type=work.get("workType") or "COWORK_DEPLOY",
        extra_images=existing_extras or None,
        work_id=int(work_id_arg),
        s=s,
    )

    app_id = work.get("deploymentAppId") or work.get("staticResourceAppId")
    # 改完查详情拿后端算好的 accessUrl（alias 改了后端会重算）。
    _ud = _fetch_work_detail(work_id_arg, s=s) if str(work_id_arg).isdigit() else {}
    access_url = _ud.get("accessUrl") or work.get("accessUrl") or f"{COWORK_WEB}/s/{new_alias or app_id or ''}"
    new_alias = _ud.get("alias") or new_alias

    # 同步本地 manifest（如果有 srcDir 能索到）。
    synced_manifest = None
    try:
        for manifests_root in (COWORK_PROJECT_ROOT, LEGACY_PROJECT_ROOT):
            if not manifests_root.exists():
                continue
            for child in manifests_root.iterdir():
                mp = child / MANIFEST_FILENAME
                if not mp.exists():
                    continue
                try:
                    m = json.loads(mp.read_text())
                except Exception:
                    continue
                if (m.get('cowork') or {}).get('workId') == int(work_id_arg):
                    m['cowork'].update({
                        'alias': new_alias,
                        'accessUrl': access_url,
                        'coworkAppUrl': cowork_app_url(int(work_id_arg)),
                        'visibility': visibility,
                    })
                    m['updatedAt'] = _now_ms()
                    _save_manifest(str(child), m)
                    synced_manifest = m
                    info(f"updated manifest: {mp}")
                    break
            if synced_manifest:
                break
    except Exception as e:
        info(f"⚠️ manifest sync skipped: {e}")

    if synced_manifest:
        changed = []
        if args.title is not None:
            changed.append('title')
        if args.intro is not None:
            changed.append('intro')
        if args.desc is not None:
            changed.append('description')
        if args.alias is not None:
            changed.append('alias')
        if args.cover is not None:
            changed.append('cover')
        if args.visibility is not None:
            changed.append('visibility')
        if args.tags is not None:
            changed.append('tags')
        _memory_append(
            synced_manifest,
            section='元信息变更',
            line=f"- {time.strftime('%Y-%m-%d %H:%M')} — 更新作品元信息：{', '.join(changed) or 'metadata'}",
            frontmatter_updates={
                'workId': new_work_id,
                'alias': new_alias,
                'accessUrl': access_url,
                'visibility': visibility,
            },
        )

    ok(f"updated workId={new_work_id}")
    # 仅当本次改了 alias 时，路由层需 ~5s 才把新 URL 同步生效，先等再返回 URL。
    if args.alias is not None:
        wait_alias_propagation(new_alias)
    _norm_work_id = int(new_work_id) if isinstance(new_work_id, (int, str)) and str(new_work_id).isdigit() else new_work_id
    print(json.dumps({
        "ok": True,
        "workId": _norm_work_id,
        "appId": app_id,
        "alias": new_alias,
        "accessUrl": access_url,
        "coworkAppUrl": cowork_app_url(_norm_work_id) if isinstance(_norm_work_id, int) else None,
    }, ensure_ascii=False, indent=2))


def _workspace_code_roots() -> list[Path]:
    """redeploy 反查 srcDir 时扫描的项目根。

    历史 bug（2026-06 修）：旧实现写死返回 ['/home/node/.openclaw/workspace/code']，
    既写死了 pod 专属路径（本地环境不存在），又只扫 legacy 的 code/——
    而 scaffold / transform / dev 实际把项目建在 cowork/（COWORK_PROJECT_ROOT）。
    结果：cowork/ 里的项目 redeploy 不带 --src 时反查不到 manifest → extPlatformId
    丢失 → 后端把 redeploy 当成全新部署 → 每次重部署都新建一台机器。

    修复：默认与全仓其他「项目根」逻辑（delete / update / link / suggest /
    list-projects）保持一致，扫 COWORK_PROJECT_ROOT(cowork/) + LEGACY_PROJECT_ROOT(code/)。
    仍保留 COWORK_CODE_ROOTS / COWORK_CODE_ROOT 环境变量作为显式覆盖入口。
    """
    raw = os.environ.get('COWORK_CODE_ROOTS') or os.environ.get('COWORK_CODE_ROOT')
    if raw:
        return [Path(x).expanduser() for x in raw.split(':') if x.strip()]
    return [COWORK_PROJECT_ROOT, LEGACY_PROJECT_ROOT]


def _find_manifest_by_work_id(work_id: str | int) -> tuple[str, dict] | tuple[None, None]:
    """Find a project manifest by cowork.workId under known code roots."""
    target = str(work_id)
    for root in _workspace_code_roots():
        if not root.exists():
            continue
        for mp in root.glob('*/' + MANIFEST_FILENAME):
            try:
                m = json.loads(mp.read_text())
            except Exception:
                continue
            cw = m.get('cowork') or {}
            if str(cw.get('workId')) == target:
                return str(mp.parent), m
    return None, None


def _bump_version(current: str | None, bump: str = 'patch') -> str:
    cur = (current or '1.0').strip() or '1.0'
    # Keep only numeric dot parts for bumping; fallback to 1.0 when non-semver-ish.
    if not re.match(r'^\d+(\.\d+){0,2}$', cur):
        cur = '1.0'
    parts = [int(x) for x in cur.split('.')]
    while len(parts) < 3:
        parts.append(0)
    major, minor, patch = parts[:3]
    if bump == 'major':
        major += 1
        minor = 0
        patch = 0
        return f'{major}.0'
    if bump == 'minor':
        minor += 1
        patch = 0
        return f'{major}.{minor}'
    patch += 1
    return f'{major}.{minor}.{patch}'


def _sha256_file(path: str | Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return 'sha256:' + h.hexdigest()


def _json_loads_safe(value, default):
    try:
        if value is None:
            return default
        return json.loads(value)
    except Exception:
        return default


def _redeploy_static(args, *, src_dir, manifest, work, work_id_arg, zip_meta, zip_hash, s):
    """纯前端静态作品的 redeploy 分支（detect 判为 STATIC_RESOURCE 时）。

    带 workId 调 static_deploy（后端按 workId 找到已有静态记录，原 app_id 重新挂载 +
    清缓存），同步返回；再补 save 写版本号；最后同步 manifest。
    """
    info("🚀 static-deploy（纯前端，更新挂载，同步）...")
    ext_platform_id = (manifest or {}).get("id")
    res = static_deploy(
        zip_meta["fileId"], zip_name=zip_meta["name"],
        work_id=int(work_id_arg),
        ext_platform_id=ext_platform_id,
        deploy_source="SEAL",
        s=s,
    )
    if res.get("status") != "MOUNT_SUCCESS":
        info(f"⚠️ static mount FAILED: status={res.get('status')} {res.get('errorMessage', '')[:300]}")
        info("  💡 静态挂载失败多为打包不合规：根目录须有 index.html、用相对路径、"
             "不得含 install.sh/package.json/node_modules 等黑名单文件。"
             "打包规范见 references/pure-frontend.md")
        res["workId"] = int(work_id_arg)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(2)
    static_resource_id = res.get("staticResourceId")
    app_id = res.get("appId")
    alias = res.get("alias") or (manifest or {}).get('cowork', {}).get('alias')
    final_url = res.get("accessUrl") or f"{COWORK_WEB}/f/{alias or app_id}/"
    raw_access_url = res.get("rawAccessUrl") or f"{COWORK_WEB}/f/{app_id}/"
    ok(f"redeployed(static) → {final_url}")

    # 跨类型升级提示：原作品若是应用部署，本次改走静态挂载。两通道共存由后端自管
    # （最后成功部署的通道生效），CLI 不维护跨通道 ID——save 时按详情原样透传即可。
    type_switched = work.get("workDeployType") == WORK_DEPLOY_TYPE_APP
    if type_switched:
        info("🔀 作品类型升级：应用部署 → 静态挂载（链接将切到静态挂载，应用部署记录后端保留）")

    current_version = work.get("version") or (manifest or {}).get('cowork', {}).get('version') or "1.0"
    next_version = args.version or _bump_version(current_version, args.bump or 'patch')
    # 触发条件：版本变 OR 跨类型升级（类型变了必须 save 一次更新 workDeployType）。
    if next_version != current_version or type_switched:
        try:
            existing_images = _json_loads_safe(work.get("imagesJson"), []) or []
            cover = next((img for img in existing_images if img.get("type") == "cover"), None)
            extras = [img for img in existing_images if img.get("type") != "cover"]
            if cover:
                cover = {k: v for k, v in cover.items() if k != "type"}
            _vis = normalize_visibility(work.get("visibilityScope") or work.get("visibility") or "SELF_ONLY")
            _vusers = work.get("visibleUserIds") if _vis == "DEPARTMENTS" else None
            _vdepts = work.get("visibleDepartmentIds") if _vis == "DEPARTMENTS" else None
            if isinstance(_vusers, str):
                _vusers = _json_loads_safe(_vusers, []) or []
            if isinstance(_vdepts, str):
                _vdepts = _json_loads_safe(_vdepts, []) or []
            save_work(
                name=work.get("name"),
                one_line_intro=work.get("oneLineIntro") or "",
                description=work.get("description") or "",
                cover=cover,
                # 本次主通道是静态挂载，用新 staticResourceId；应用通道按详情原样透传。
                static_resource_id=static_resource_id,
                deployment_id=work.get("deploymentId"),
                work_deploy_type=WORK_DEPLOY_TYPE_STATIC,
                alias=alias,
                scene_tags=_json_loads_safe(work.get("sceneTagsJson"), []) or [],
                version=next_version,
                visibility=_vis,
                visible_user_ids=_vusers,
                visible_department_ids=_vdepts,
                links=_json_loads_safe(work.get("linksJson"), []) or [],
                notify_on_publish=False,
                work_type=work.get("workType") or "SEAL_DEPLOY",
                extra_images=extras or None,
                work_id=int(work_id_arg),
                s=s,
            )
        except Exception as e:
            info(f"⚠️ version bump save failed: {e}")

    new_work_id = int(work_id_arg)

    # 关联完成后查详情拿后端算好的权威 accessUrl / alias / workDeployType，不本地拼 URL。
    detail = _fetch_work_detail(work_id_arg, s=s)
    access_url = detail.get("accessUrl") or final_url
    eff_alias = detail.get("alias") or alias
    eff_app_id = detail.get("staticResourceAppId") or app_id
    eff_raw_url = detail.get("staticResourceRawAccessUrl") or raw_access_url
    try:
        m = _ensure_manifest(src_dir, name=(manifest or {}).get('name') or work.get('name'))
        m['cowork'] = {
            **((m.get('cowork') or {}) if isinstance(m.get('cowork'), dict) else {}),
            'workId': new_work_id,
            'workDeployType': detail.get("workDeployType") or WORK_DEPLOY_TYPE_STATIC,
            'staticResourceId': static_resource_id,
            'staticAppId': eff_app_id,
            'alias': eff_alias,
            'accessUrl': access_url,
            'coworkAppUrl': cowork_app_url(new_work_id),
            'rawAccessUrl': eff_raw_url,
            'publishedAt': _now_ms(),
            'visibility': detail.get("visibilityScope") or work.get("visibilityScope") or "SELF_ONLY",
            'version': next_version,
            'lastZipHash': zip_hash,
        }
        m['updatedAt'] = _now_ms()
        _save_manifest(src_dir, m)
        _memory_append(
            m,
            section='发布历史',
            line=f"- **v{next_version}** — {time.strftime('%Y-%m-%d %H:%M')} — redeploy 到 Cowork（静态挂载），alias=`{eff_alias or eff_app_id}`，staticResourceId={static_resource_id}",
            frontmatter_updates={
                'workId': new_work_id,
                'alias': eff_alias or eff_app_id,
                'accessUrl': access_url,
                'visibility': detail.get("visibilityScope") or work.get("visibilityScope") or "SELF_ONLY",
            },
        )
        info(f"updated manifest: {src_dir}/.cowork.json")
    except Exception as e:
        info(f"⚠️ manifest update skipped: {e}")

    print(json.dumps({
        "ok": True,
        "workId": new_work_id,
        "workDeployType": detail.get("workDeployType") or WORK_DEPLOY_TYPE_STATIC,
        "staticResourceId": static_resource_id,
        "appId": eff_app_id,
        "alias": eff_alias,
        "accessUrl": access_url,                                  # 部署链接（/f/）
        "rawAccessUrl": eff_raw_url,
        "coworkAppUrl": cowork_app_url(new_work_id),              # 作品详情页链接 /app/<id>
        "version": next_version,
        "lastZipHash": zip_hash,
    }, ensure_ascii=False, indent=2))


def cmd_redeploy(args):
    """对已有 Cowork work 重新部署当前本地代码，保留元信息，递增版本。"""
    s = session()
    work_id_arg = args.work_id

    # Resolve source directory. Preferred: explicit --src. Fallback: .cowork.json by workId.
    manifest = None
    src_dir = args.src
    if src_dir:
        src_dir = os.path.abspath(src_dir.rstrip('/'))
        manifest = _load_manifest(src_dir)
    else:
        src_dir, manifest = _find_manifest_by_work_id(work_id_arg)
    if not src_dir:
        err(f"cannot resolve srcDir for workId={work_id_arg}; pass --src <dir> or ensure .cowork.json has cowork.workId")
    if not os.path.isdir(src_dir):
        err(f"srcDir not found: {src_dir}")

    # Remote work remains the source of truth for metadata.
    work = api_call("GET", f"/community/works/{work_id_arg}", session=s)
    if not work:
        err(f"work not found: {work_id_arg}")
    alias = work.get("deploymentAlias") or (manifest or {}).get('cowork', {}).get('alias')
    app_id = work.get("deploymentAppId") or (manifest or {}).get('cowork', {}).get('appId')
    info(f"current alias={alias}, appId={app_id}, srcDir={src_dir}")

    # Pack from source directory. pack_dir honors .cowork.json pack.keep.
    zip_path = args.zip or f"{src_dir.rstrip('/')}.zip"
    zip_path = pack_dir(src_dir, out=zip_path, in_place=False, keep=getattr(args, 'keep', None))
    zip_hash = _sha256_file(zip_path)
    meta = upload_file(zip_path, mime_type="application/zip", s=s)

    # detect 分流：纯前端走静态挂载更新；已转写走应用部署；未转写直接拦截提示 transform
    try:
        det = detect_code_package_type(_file_id_json(meta["fileId"], meta["name"]), s=s)
        pkg_type = (det or {}).get("type")
        det_reason = (det or {}).get("reason", "")
    except SystemExit:
        pkg_type, det_reason = None, "(detect 接口不可用，回退应用部署)"
    info(f"🔎 detect: type={pkg_type or '?'} — {det_reason}")
    if pkg_type == "STATIC_RESOURCE":
        if getattr(args, 'no_wait', False):
            info("ℹ️  静态资源挂载为同步部署，--no-wait 不适用，已忽略")
        _redeploy_static(args, src_dir=src_dir, manifest=manifest, work=work,
                         work_id_arg=work_id_arg, zip_meta=meta, zip_hash=zip_hash, s=s)
        return
    if pkg_type == "APP_DEPLOY_NOT_CONVERTED" and not args.force:
        err(
            "代码包不符合 Cowork/Guard 子应用规范，未转写，禁止直接部署。\n"
            f"  原因：{det_reason or '缺少 install.sh/start.sh/health.sh 或存在违规依赖'}\n"
            f"  请先转写：python3 cowork.py transform {src_dir}\n"
            "  转写完成后重新发布；或确认无误用 --force 跳过本检查。"
        )

    # —— 应用部署分支（APP_DEPLOY_CONVERTED / detect 不可用回退）——
    # 跨类型升级提示：原作品若是静态挂载，本次改走应用部署。两通道共存由后端自管
    # （最后成功部署的通道生效），CLI 不维护跨通道 ID——save 时按详情原样透传即可。
    type_switched = work.get("workDeployType") == WORK_DEPLOY_TYPE_STATIC
    if type_switched:
        info("🔀 作品类型升级：静态挂载 → 应用部署（链接将切到应用部署，静态记录后端保留）")

    issues = precheck_zip(zip_path)
    if any(i.startswith("❌") for i in issues) and not args.force:
        for i in issues:
            sys.stderr.write(i + "\n")
        err("precheck FAIL；--force 跳过")
    for i in issues:
        if i.startswith("⚠️"):
            info(i)

    # 关键：deploy 带 workId，后端会把新 deployment 绑到该 work，
    # 复用现有 alias。不需要再调 save（alias 不变、元信息不变）。
    ext_platform_id = (manifest or {}).get("id")
    d = deploy_zip(
        meta["fileId"], zip_name=meta["name"],
        work_id=int(work_id_arg),
        ext_platform_id=ext_platform_id,
        deploy_source="SEAL",
        s=s,
    )
    if args.no_wait:
        info(f"⏭  --no-wait：仅触发 redeploy，不轮询 (deploymentId={d.get('deploymentId')})")
        d["ok"] = True
        d["waiting"] = False
        d["workId"] = int(work_id_arg)
        d["coworkAppUrl"] = cowork_app_url(int(work_id_arg))
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return
    info(f"⏳ 重新部署中（deploymentId={d['deploymentId']}），平台正在 install→start→health，请稍候 ...")
    res = wait_deploy(d["deploymentId"], timeout_s=args.timeout, s=s)
    if res.get("failed"):
        info(f"⚠️ redeploy FAILED: {res.get('errorMessage', '')[:300]}")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(2)
    if res.get("timedOut"):
        info(f"⏱️  {res.get('message', '')}")
        res["workId"] = int(work_id_arg)
        res["coworkAppUrl"] = cowork_app_url(int(work_id_arg))
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    ok(f"redeployed → {res.get('accessUrl')}")

    current_version = work.get("version") or (manifest or {}).get('cowork', {}).get('version') or "1.0"
    next_version = args.version or _bump_version(current_version, args.bump or 'patch')

    # save 作品↔资源关联（与上面 deploy 实际部署解耦）。
    # 触发条件：版本变 OR 跨类型升级（类型变了必须 save 一次更新 workDeployType，
    # 否则作品类型停留在旧通道、与实际 accessUrl 不一致）。
    if next_version != current_version or type_switched:
        try:
            existing_images = _json_loads_safe(work.get("imagesJson"), []) or []
            cover = next((img for img in existing_images if img.get("type") == "cover"), None)
            extras = [img for img in existing_images if img.get("type") != "cover"]
            if cover:
                cover = {k: v for k, v in cover.items() if k != "type"}
            # 保留远端可见性 + 名单，避免 redeploy 把 PARTIAL 项目打回 SELF_ONLY或清空名单
            _vis = normalize_visibility(work.get("visibilityScope") or work.get("visibility") or "SELF_ONLY")
            _vusers = work.get("visibleUserIds") if _vis == "DEPARTMENTS" else None
            _vdepts = work.get("visibleDepartmentIds") if _vis == "DEPARTMENTS" else None
            if isinstance(_vusers, str):
                _vusers = _json_loads_safe(_vusers, []) or []
            if isinstance(_vdepts, str):
                _vdepts = _json_loads_safe(_vdepts, []) or []
            save_work(
                name=work.get("name"),
                one_line_intro=work.get("oneLineIntro") or "",
                description=work.get("description") or "",
                cover=cover,
                # 本次主通道是应用部署，用新 deploymentId；静态通道按详情原样透传
                # （详情互斥：另一通道恒 null，透传 None 即可，不本地维护）。
                deployment_id=res["deploymentId"],
                static_resource_id=work.get("staticResourceId"),
                deployment_alias=alias,
                work_deploy_type=WORK_DEPLOY_TYPE_APP,
                scene_tags=_json_loads_safe(work.get("sceneTagsJson"), []) or [],
                version=next_version,
                visibility=_vis,
                visible_user_ids=_vusers,
                visible_department_ids=_vdepts,
                links=_json_loads_safe(work.get("linksJson"), []) or [],
                notify_on_publish=False,
                work_type=work.get("workType") or "COWORK_DEPLOY",
                extra_images=extras or None,
                work_id=int(work_id_arg),
                s=s,
            )
        except Exception as e:
            info(f"⚠️ version bump save failed: {e}")

    new_work_id = int(work_id_arg)

    # 关联完成后查一次详情，拿后端算好的权威 accessUrl / alias / workDeployType，不本地拼 URL。
    detail = _fetch_work_detail(work_id_arg, s=s)
    access_url = detail.get("accessUrl") or res.get("accessUrl")
    eff_alias = detail.get("alias") or alias
    eff_app_id = detail.get("deploymentAppId") or res.get("appId") or app_id
    raw_access_url = detail.get("deploymentRawAccessUrl") or res.get("rawAccessUrl") or res.get("accessUrl")
    ok(f"redeployed → {access_url}")

    # Sync manifest.
    try:
        m = _ensure_manifest(src_dir, name=(manifest or {}).get('name') or work.get('name'))
        _new_work_id_int = int(new_work_id) if isinstance(new_work_id, (int, str)) and str(new_work_id).isdigit() else new_work_id
        m['cowork'] = {
            **((m.get('cowork') or {}) if isinstance(m.get('cowork'), dict) else {}),
            'workId': _new_work_id_int,
            'workDeployType': detail.get("workDeployType") or WORK_DEPLOY_TYPE_APP,
            'appId': eff_app_id,
            'alias': eff_alias,
            'accessUrl': access_url,
            'coworkAppUrl': cowork_app_url(_new_work_id_int) if isinstance(_new_work_id_int, int) else None,
            'rawAccessUrl': raw_access_url,
            'deploymentId': res['deploymentId'],
            'deploymentStatus': 'RUNNING',
            'publishedAt': _now_ms(),
            'visibility': detail.get("visibilityScope") or work.get("visibilityScope") or "SELF_ONLY",
            'version': next_version,
            'lastZipHash': zip_hash,
        }
        m['updatedAt'] = _now_ms()
        _save_manifest(src_dir, m)
        _memory_append(
            m,
            section='发布历史',
            line=f"- **v{next_version}** — {time.strftime('%Y-%m-%d %H:%M')} — redeploy 到 Cowork，alias=`{eff_alias or eff_app_id}`，deploymentId={res['deploymentId']}",
            frontmatter_updates={
                'workId': new_work_id,
                'alias': eff_alias or eff_app_id,
                'accessUrl': access_url,
                'visibility': detail.get("visibilityScope") or work.get("visibilityScope") or "SELF_ONLY",
            },
        )
        info(f"updated manifest: {src_dir}/.cowork.json")
    except Exception as e:
        info(f"⚠️ manifest update skipped: {e}")

    output = {
        "ok": True,
        "workId": int(new_work_id) if isinstance(new_work_id, (int, str)) and str(new_work_id).isdigit() else new_work_id,
        "deploymentId": res["deploymentId"],
        "appId": eff_app_id,
        "alias": eff_alias,
        "workDeployType": detail.get("workDeployType") or WORK_DEPLOY_TYPE_APP,
        "accessUrl": access_url,                                          # 部署链接（/s/ 或 /f/）
        "rawAccessUrl": raw_access_url,
        "coworkAppUrl": cowork_app_url(_new_work_id_int) if isinstance(_new_work_id_int, int) else None,  # 作品详情页链接 /app/<id>
        "version": next_version,
        "lastZipHash": zip_hash,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# -----------------------------------------------------------------------------
# scaffold —— 从内置模板生成 Cowork 合规项目骨架
# -----------------------------------------------------------------------------
#
# 设计要点：
#   1. 模板就在本仓库 templates/<name>/ 下（与 transform/profiles 同名同语义）。
#   2. 默认输出目录 ~/.openclaw/workspace/cowork/<slug>/，与 SKILL 「项目目录约定」对齐；
#      仅 power-user 可用 --target-dir 指定其他路径。
#   3. 不覆盖已有非空目录；空目录可复用。
#   4. copy 后强制 chmod +x install.sh / start.sh / health.sh（zipfile / fs.copy
#      在某些 FS 上会丢 mode bits）。
#   5. 写 .cowork.json 用 _ensure_manifest()；额外补 pack.keep（前端构建产物保留清单），
#      方便后续 publish 打包时不被剥掉。

SCAFFOLD_TEMPLATES = (
    "fastapi-only",
    "koa-monorepo",
    "nextjs-fullstack",
    "react-fastapi-monorepo",
)


def _scaffold_templates_root() -> Path:
    """templates/ 与 cowork.py 同级（skill 仓库 / workspace skill 落盘后都成立）。"""
    return Path(__file__).resolve().parent / "templates"


def _scaffold_pack_keep(template: str) -> list:
    """pack 阶段必须保留的产物目录（前端模板）。"""
    if template == "nextjs-fullstack":
        return [".next", "public"]
    if template in ("react-fastapi-monorepo", "koa-monorepo"):
        return ["frontend/dist"]
    return []


def _scaffold_copytree(src: Path, dst: Path) -> None:
    """与 shutil.copytree(dirs_exist_ok=True) 等价，但显式保留 mode bits（含 +x）。"""
    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        s = entry
        d = dst / entry.name
        if s.is_dir():
            _scaffold_copytree(s, d)
        elif s.is_file():
            data = s.read_bytes()
            d.write_bytes(data)
            try:
                d.chmod(s.stat().st_mode)
            except Exception:
                pass


def cmd_scaffold(args):
    """`cowork.py scaffold <name> --template fastapi-only [--target-dir ...]`

    从 templates/<template>/ 生成 Guard 合规 cowork 项目骨架，写 .cowork.json。
    输出 JSON：{ projectId, srcDir, template, manifestPath }。

    与 SKILL Creation Hard Rule #1 / #2 / #7 配合：scaffold 完不自动 publish，
    agent 负责后续 read templates-ref/<template>.md → 改业务代码 → cowork.py publish。
    """
    name = (args.name or "").strip()
    if not name:
        err("scaffold: name 必填")
    template = args.template or "fastapi-only"
    if template not in SCAFFOLD_TEMPLATES:
        err(f"scaffold: 不支持的 template '{template}'，可选: {', '.join(SCAFFOLD_TEMPLATES)}")

    slug = _slugify(name)
    target_dir = args.target_dir
    if target_dir:
        src_dir = Path(target_dir).expanduser().resolve()
    else:
        _ensure_project_root()
        src_dir = (COWORK_PROJECT_ROOT / slug).resolve()

    # 不覆盖已有非空目录
    if src_dir.exists():
        try:
            entries = list(src_dir.iterdir())
        except OSError:
            entries = []
        if entries:
            err(f"scaffold: targetDir 已存在且非空: {src_dir}")

    templates_root = _scaffold_templates_root()
    template_dir = templates_root / template
    if not template_dir.is_dir():
        err(f"scaffold: 模板未找到: {template_dir}")

    _scaffold_copytree(template_dir, src_dir)

    # fs.copyFile 在某些 FS 会丢 +x；显式恢复执行位
    for sh in ("install.sh", "start.sh", "health.sh"):
        p = src_dir / sh
        if p.exists():
            try:
                p.chmod(p.stat().st_mode | 0o111)
            except OSError:
                pass

    # 写 manifest（schema/projectId/createdAt 都由 _ensure_manifest 兜底）
    manifest = _ensure_manifest(
        str(src_dir),
        name=slug,
        stack=template,
        created_by="cowork-cli",
        chat_session_id=getattr(args, "chat_session_id", None),
    )
    # 补 4 模板的 pack 预设（pack.keep：打包时保留的前端构建产物）
    pack_keep = _scaffold_pack_keep(template)
    if pack_keep:
        manifest["pack"] = {"keep": pack_keep}
    # 一句话需求描述：写进 manifest，后续 suggest-publish-metadata 据此生成发布文案
    description = (getattr(args, "description", None) or "").strip()
    extra_dirty = False
    if description:
        manifest["description"] = description
        extra_dirty = True
    if pack_keep or extra_dirty:
        _save_manifest(str(src_dir), manifest)

    output = {
        "projectId": manifest.get("id"),
        "srcDir": str(src_dir),
        "template": template,
        "manifestPath": str(src_dir / ".cowork.json"),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(prog="cowork", description="cowork-cli — 部署 + 发布作品到 cowork")
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("pack", help="把源码打成 Guard zip")
    p1.add_argument("src", help="源目录")
    p1.add_argument("-o", "--out", help="输出 zip 路径（默认 <src>.zip）")
    p1.add_argument("--in-place", action="store_true", help="不建副本，直接 zip 原目录")
    p1.add_argument("--keep-copy", action="store_true", help="保留 <src>-guard/ 副本（默认 pack 后自动删除，避免污染项目列表）")
    p1.add_argument("--skip-precheck", action="store_true")
    p1.add_argument("--keep", nargs="*", default=None,
                    help="不要剥掉的目录名（如 SPA build 产物 dist build）")
    p1.set_defaults(func=cmd_pack)

    p2 = sub.add_parser("precheck", help="对源码目录或 zip 跑 Guard 红线检查（自动识别）")
    p2.add_argument("target", help="目录路径 or zip 文件")
    p2.add_argument("--json", action="store_true", help="结构化输出给上游 plugin / IPC 使用")
    p2.set_defaults(func=cmd_precheck)

    pt = sub.add_parser("transform", help="把现有工程改写为 Cowork Guard 子应用（调 transform/transform.sh）")
    pt.add_argument("srcDir", help="源工程目录")
    # REMAINDER：把 srcDir 之后的所有参数（含 --skip-llm / --resume / --from-stage NN 等
    # 以 - 开头的）原样透传给 transform.sh，不被 cowork.py 顶层 parser 拦截。
    pt.add_argument("extra", nargs=argparse.REMAINDER,
                    help="额外参数透传给 transform.sh（如 --skip-llm / --resume / --from-stage NN）")
    pt.set_defaults(func=cmd_transform)

    p3 = sub.add_parser("upload", help="上传任意文件到 OSS，返回 fileId")
    p3.add_argument("file")
    p3.set_defaults(func=cmd_upload)

    p4 = sub.add_parser("deploy", help="上传 zip + 部署 + 等 RUNNING")
    p4.add_argument("zip")
    p4.add_argument("--timeout", type=int, default=DEFAULT_DEPLOY_TIMEOUT_S,
                    help=f"轮询最长等待秒数，默认 {DEFAULT_DEPLOY_TIMEOUT_S}s；超时不报错返结构化 timedOut")
    p4.add_argument("--no-wait", dest="no_wait", action="store_true",
                    help="仅触发 deploy 不轮询，返回 deploymentId。上游可后续调 status 查询")
    p4.set_defaults(func=cmd_deploy)

    p5 = sub.add_parser("publish", help="完整发布：deploy + 上传封面 + save")
    p5.add_argument("zip", help="部署 zip")
    p5.add_argument("--cover", required=True, help="封面图（jpg/png/gif）")
    p5.add_argument("--title", required=True)
    p5.add_argument("--intro", help="一句话简介")
    p5.add_argument("--desc", help="详细描述（支持多行）")
    p5.add_argument("--alias", help="自定义后缀，3-32 位小写字母/数字/-")
    p5.add_argument("--version", default="1.0")
    # 首发 visibility 锁死仅 self：防用户/agent 误发到全公司 / 部门。
    # 后续放开需要用户去 Cowork Studio Web 端手动操作。
    p5.add_argument("--visibility", default="self", choices=["self", "SELF_ONLY"],
                    help="首发仅支持 self（仅自己可见）。释放为 partial / all 请发后去 Cowork Studio 手动调")
    p5.add_argument("--ext-platform-id", dest='ext_platform_id',
                    help="外部平台项目 ID（Seal projectId cw_proj_xxx）。不传则从 zip 同级 .cowork.json id 自动读。")
    p5.add_argument("--tags", nargs="*", help="场景标签（中文 or enum key）")
    p5.add_argument("--notify", action="store_true", help="发布时通知关注者")
    p5.add_argument("--timeout", type=int, default=DEFAULT_DEPLOY_TIMEOUT_S,
                    help=f"轮询最长等待秒数，默认 {DEFAULT_DEPLOY_TIMEOUT_S}s")
    p5.add_argument("--force", action="store_true", help="precheck 失败也强行发")
    p5.add_argument("--deployment-id", dest="deployment_id", type=int, default=None,
                    help="复用上次失败的部署机器重试（首发失败后修代码重发用）；"
                         "不传则自动读 .cowork.json 的 pendingDeploymentId。记录已失效会自动降级新建")
    p5.add_argument("--keep", nargs="*", default=None,
                    help="传源码目录时 pack 阶段不要剥掉的目录名（如 SPA build 产物 dist build）")
    p5.set_defaults(func=cmd_publish)

    psug = sub.add_parser(
        "suggest-publish-metadata",
        help="为 Studio 首发表单生成预填字段（标题/简介/描述/alias/tags）",
    )
    psug.add_argument("project_id", nargs="?", help="项目身份 cw_proj_xxxxx；不传则必须 --src")
    psug.add_argument("--src", help="代码目录；与 project_id 二选一")
    psug.add_argument("--json", action="store_true", help="兼容 wrapper；实际不论传不传都 JSON 输出")
    psug.set_defaults(func=cmd_suggest_publish_metadata)

    pmem = sub.add_parser("memory", help="查看/追加 Cowork 项目 memory")
    memsub = pmem.add_subparsers(dest="memory_action", required=True)
    pmem_list = memsub.add_parser("list", help="刷新并输出 Cowork memory INDEX")
    pmem_list.set_defaults(func=cmd_memory)
    pmem_show = memsub.add_parser("show", help="显示项目 memory.md")
    pmem_show.add_argument("project", help="projectId / slug / name")
    pmem_show.add_argument("--src", help="直接指定 srcDir")
    pmem_show.set_defaults(func=cmd_memory)
    pmem_append = memsub.add_parser("append", help="向项目 memory 的指定 section 追加内容")
    pmem_append.add_argument("project", help="projectId / slug / name")
    pmem_append.add_argument("--src", help="直接指定 srcDir")
    pmem_append.add_argument("--section", default="关键决策", help="二级标题 section，默认 关键决策")
    pmem_append.add_argument("--content", help="追加内容；也可用 --file 或 stdin")
    pmem_append.add_argument("--file", help="从文件读取追加内容")
    pmem_append.set_defaults(func=cmd_memory)

    p6 = sub.add_parser("status", help="查 deploymentId 状态")
    p6.add_argument("deployment_id", type=int)
    p6.set_defaults(func=cmd_status)

    psad = sub.add_parser(
        "save-after-deploy",
        help="deploy 后单独走 save（upload cover + save_work + manifest 写回）。publish.ts 三段式发布中的 step-3",
    )
    psad.add_argument("--deployment-id", dest="deployment_id", type=int, required=True)
    psad.add_argument("--cover", required=True, help="封面图路径")
    psad.add_argument("--title", required=True)
    psad.add_argument("--intro", default="")
    psad.add_argument("--desc", default="")
    psad.add_argument("--alias", help="自定义后缀")
    psad.add_argument("--version", default="1.0")
    psad.add_argument("--visibility", default="self", choices=["self", "SELF_ONLY"],
                      help="首发仅支持 self")
    psad.add_argument("--tags", nargs="*", help="场景标签（中文 or enum key）")
    psad.add_argument("--notify", action="store_true")
    psad.add_argument("--src-dir", dest="src_dir", help="项目 srcDir（可选，不传则从 zip 位置推断）")
    psad.add_argument("--zip", help="部署过的 zip 路径（可选，仅用于 fallback 推 srcDir）")
    psad.set_defaults(func=cmd_save_after_deploy)

    p7 = sub.add_parser("list", help="列我发的作品（旧接口 enriched；新代码请用 list-my-apps）")
    p7.add_argument("--email")
    p7.add_argument("--tab", default="recent", choices=["recent", "all"])
    p7.add_argument("--raw", action="store_true", help="不补 deployment 字段，仅返回 list 原始响应")
    p7.set_defaults(func=cmd_list)

    p7b = sub.add_parser("list-my-apps", help="走 SSO session 拉我的作品（含部署信息，不需 email）")
    p7b.add_argument("--work-type", dest="work_type",
                     choices=["EXTERNAL_RESOURCE", "COWORK_DEPLOY", "SEAL_DEPLOY"],
                     help="不传返回全部")
    p7b.set_defaults(func=cmd_list_my_apps)

    p7c = sub.add_parser(
        "list-projects",
        help="列出本地所有 Cowork 项目（含未发布草稿）+ 远端作品，merge 后带 3 状态 chip",
    )
    p7c.set_defaults(func=cmd_list_projects)

    p8 = sub.add_parser("detail", help="查 work 详情")
    p8.add_argument("id", type=int)
    p8.set_defaults(func=cmd_detail)

    plink = sub.add_parser("link",
                           help="把本地代码目录 link 到已发布的 cowork 作品（多端开发/重装恢复场景）")
    plink.add_argument("work_id", help="要 link 的作品 workId")
    plink.add_argument("src_dir", help="本地代码目录绝对路径（必须已通过 Guard precheck）")
    plink.set_defaults(func=cmd_link)

    p9 = sub.add_parser("delete", help="删 work")
    p9.add_argument("id")
    p9.add_argument("--yes", action="store_true")
    p9.set_defaults(func=cmd_delete)

    palias = sub.add_parser("set-alias", help="设置/修改已发布作品的 alias（走 save，应用/静态统一）")
    palias.add_argument("work_id", help="作品 workId")
    palias.add_argument("alias", help="新 alias（3-32 位小写字母/数字/-，不能连字符头尾/两连）")
    palias.add_argument("--json", action="store_true", help="输出 JSON")
    palias.set_defaults(func=cmd_set_alias)

    pvis = sub.add_parser("set-visibility",
                          help="设置作品可见性（UI 专用，不走 cmd_update 的 agent guard）")
    pvis.add_argument("work_id", help="作品 workId")
    pvis.add_argument("--visibility", required=True,
                      choices=["self", "partial", "all", "SELF_ONLY", "DEPARTMENTS", "PARTIAL", "PUBLIC", "ALL"],
                      help="可见范围")
    pvis.add_argument("--visible-users", dest="visible_user_ids", nargs="*", default=None,
                      help="可见人员 userId 列表（partial 时使用）")
    pvis.add_argument("--visible-departments", dest="visible_department_ids", nargs="*", default=None,
                      help="可见部门 departmentId 列表（partial 时使用）")
    pvis.set_defaults(func=cmd_set_visibility)

    psu = sub.add_parser("search-users",
                         help="员工搜索（UI 专用，依赖 EHR findUserInfoByValue）")
    psu.add_argument("keyword", help="薯名/姓名/邮箱/工号")
    psu.set_defaults(func=cmd_search_users)

    psc = sub.add_parser("search-contacts",
                         help="部门+人员+群聊混合搜索（UI 专用，走 redcity 综合搜索网关）")
    psc.add_argument("keyword", help="搜索关键词")
    psc.add_argument("--types", default="account,department",
                     help="搜索类型，逗号分隔：account/department/chat/tag（默认 account,department）")
    psc.set_defaults(func=cmd_search_contacts)

    prdn = sub.add_parser(
        "resolve-department-names",
        help="按 ID 反查部门名字+路径（UI 专用，不缓存、只返请求的 N 个）"
    )
    prdn.add_argument("ids", nargs="+", help="部门 ID 列表（空格分隔）")
    prdn.set_defaults(func=cmd_resolve_department_names)

    pu = sub.add_parser("update", help="仅更新作品元信息（标题/简介/封面/alias/可见范围/标签），不重新部署")
    pu.add_argument("work_id", help="作品 workId")
    pu.add_argument("--title", default=None)
    pu.add_argument("--intro", default=None)
    pu.add_argument("--desc", default=None)
    pu.add_argument("--alias", default=None, help="3-32 位小写字母/数字/-")
    pu.add_argument("--cover", default=None, help="封面图；不传就复用远端")
    # “放大可见范围”（self → all / partial）在 CLI 中一律拒绝，引导用户去 Cowork Studio Web 端。
    # 原因：一次手抖就能把内部工具面向全公司，危险太高；且内网没给普通员工查 departmentId/userId 的接口。
    # 只保留 self（可以“下架”/ 缩小可见范围，安全）。
    pu.add_argument("--visibility", default=None, choices=["self", "SELF_ONLY"],
                    help="仅允许改为 self（仅自己可见 / 缩小可见范围）。放大为 partial/all 请去 Cowork Studio Web 端手动操作。")
    pu.add_argument("--visible-users", dest="visible_user_ids", nargs="*", default=None,
                    help="[禁用] 跳 Cowork Studio Web 端设置")
    pu.add_argument("--visible-departments", dest="visible_department_ids", nargs="*", default=None,
                    help="[禁用] 跳 Cowork Studio Web 端设置")
    pu.add_argument("--tags", nargs="*", default=None, help="场景标签（中文 or enum key）")
    pu.set_defaults(func=cmd_update)

    psc2 = sub.add_parser("scaffold", help="从内置模板生成 Cowork 合规项目骨架（4 个 profile，写 .cowork.json）")
    psc2.add_argument("name", help="项目名（slug 化后作为目录名）")
    psc2.add_argument("--template", default="fastapi-only",
                      choices=list(SCAFFOLD_TEMPLATES),
                      help="模板 profile（默认 fastapi-only）")
    psc2.add_argument("--target-dir", dest="target_dir",
                      help="目标目录（默认 ~/.openclaw/workspace/cowork/<slug>/）；非空目录会拒绝")
    psc2.add_argument("--description", dest="description",
                      help="一句话需求描述（写进 .cowork.json，供后续 suggest-publish-metadata 生成发布文案）")
    psc2.add_argument("--chat-session-id", dest="chat_session_id",
                      help="绑定 Coral chat session id（可选）")
    psc2.set_defaults(func=cmd_scaffold)

    p10 = sub.add_parser("redeploy", help="对已有 work 重新打包并部署当前本地代码（保留元信息/alias，自增版本）")
    p10.add_argument("work_id", help="Cowork workId")
    p10.add_argument("--src", help="源码目录；不传则按 workId 从 .cowork.json 反查")
    p10.add_argument("--zip", help="临时 zip 输出路径；默认 <src>.zip")
    p10.add_argument("--version", help="显式指定版本号；不传则按 --bump 自增")
    p10.add_argument("--bump", choices=["major", "minor", "patch"], default="patch",
                     help="未显式指定 --version 时的版本自增策略，默认 patch")
    p10.add_argument("--timeout", type=int, default=DEFAULT_DEPLOY_TIMEOUT_S,
                     help=f"轮询最长等待秒数，默认 {DEFAULT_DEPLOY_TIMEOUT_S}s")
    p10.add_argument("--no-wait", dest="no_wait", action="store_true",
                     help="仅触发 redeploy 不轮询，返回 deploymentId")
    p10.add_argument("--force", action="store_true")
    p10.add_argument("--json", action="store_true", help="兼容 wrapper；redeploy 成功时始终输出 JSON")
    p10.add_argument("--keep", nargs="*", default=None,
                     help="pack 时不要剥掉的目录名（如 SPA build 产物 dist build）")
    p10.set_defaults(func=cmd_redeploy)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
