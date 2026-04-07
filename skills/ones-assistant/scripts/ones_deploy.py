#!/usr/bin/env python3
"""
ones_deploy.py — ones 发布平台 Agent Tool 调用封装

所有 tool 通过 ones 开放接口调用：
  POST https://ones.devops.xiaohongshu.com/api/v1/x/a/tools/{tool_name}
  Body: { "arguments": { ...参数 } }

Cookie 和 Agent-Platform 由框架层自动注入，本脚本无需携带。
发布环境安全校验由 ones 后端负责，本脚本仅做文字提示。

子命令体系:
  list-tools                       列出所有可用 tool
  my-apps                          查询当前用户有权限的应用列表
  my-services                      查询当前用户有权限的服务列表
  app-info <app>                   查询应用详情（含服务列表）
  service-info <service>           查询服务的部署组信息
  images <service>                 查询服务可用镜像版本
  changeflows <service>            查询服务下的发布流程模板及部署组
  check <service> <wgs...>         校验部署组发布前状态
  my-changeflows                   查询我的发布流程列表（最近 7 天）
  my-changeflows-by-app <app>      查询我在某应用下的发布流程
  deploy-info <name>               根据发布流程实例名查询详情
  pod-info <service> <wg>          查询部署组下的工作负载及 Pod 信息
  deploy-history <service> <wg>    查询指定部署组的发布历史
  deploy <service> ...             创建发布流程（含交互式确认）
  diagnose <name>                  诊断发布流程运行状态
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from typing import Any


BASE_URL = "https://ones.devops.xiaohongshu.com"
TOOLS_API = f"{BASE_URL}/api/v1/x/a/tools"


# ──────────────────────────────────────────────
# 基础 HTTP 调用
# ──────────────────────────────────────────────

def call_tool(tool_name: str, arguments: dict) -> Any:
    """
    调用 ones agent tool 接口。
    Cookie 和 Agent-Platform 由框架自动注入，无需手动传入。

    Returns:
        接口返回的 data 字段内容

    Raises:
        RuntimeError: HTTP 错误或业务错误
    """
    url = f"{TOOLS_API}/{tool_name}"
    payload = json.dumps({"arguments": arguments}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} [{tool_name}]: {raw[:300]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error [{tool_name}]: {e.reason}")

    if not body.get("success", True):
        raise RuntimeError(
            f"Tool '{tool_name}' error: {body.get('error') or body.get('message') or body}"
        )

    return body.get("data")


def list_all_tools() -> list:
    """GET /api/v1/x/a/tools — 列出所有可用 tool。"""
    req = urllib.request.Request(f"{TOOLS_API}", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ──────────────────────────────────────────────
# 输出工具
# ──────────────────────────────────────────────

def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_info(msg: str) -> None:
    print(f"[INFO] {msg}", file=sys.stderr)


def print_error(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)


def print_warning(msg: str) -> None:
    print(f"[WARN] {msg}", file=sys.stderr)


# ──────────────────────────────────────────────
# 子命令实现
# ──────────────────────────────────────────────

def cmd_list_tools(args) -> int:
    """列出所有可用 tool。"""
    try:
        tools = list_all_tools()
        print_json(tools)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_my_apps(args) -> int:
    """查询当前用户有权限的应用列表。"""
    try:
        data = call_tool("get_applications_with_permission_by_user", {})
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_my_services(args) -> int:
    """查询当前用户有权限的服务列表。"""
    try:
        data = call_tool("get_services_with_permission_by_user", {})
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_app_info(args) -> int:
    """查询应用详情（含服务及部署组列表）。"""
    try:
        data = call_tool("get_application_info_with_services", {"appName": args.app})
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_service_info(args) -> int:
    """查询服务的部署组信息（zone、name、env）。"""
    try:
        arguments: dict = {"service": args.service}
        if args.application:
            arguments["application"] = args.application
        data = call_tool("get_service_info", arguments)
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_images(args) -> int:
    """查询服务可用的镜像版本列表。"""
    try:
        data = call_tool(
            "get_service_image_repo_info",
            {"applicationChildName": args.service},
        )
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_changeflows(args) -> int:
    """查询服务下的发布流程模板及部署组。"""
    try:
        data = call_tool(
            "get_changeflows_with_workload_groups_by_service",
            {"applicationChildName": args.service},
        )
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_check(args) -> int:
    """校验部署组发布前状态（canDeploy / deploying / requireApproval / firstDeploy）。"""
    try:
        data = call_tool(
            "check_workload_groups_for_changeflow",
            {
                "applicationChildName": args.service,
                "workloadGroups": args.workload_groups,
            },
        )
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_my_changeflows(args) -> int:
    """查询当前用户最近 7 天的发布流程列表。"""
    try:
        data = call_tool("list_changeflow_by_user", {})
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_my_changeflows_by_app(args) -> int:
    """查询当前用户在指定应用下的发布流程列表。"""
    try:
        data = call_tool("list_changeflow_by_user_and_app", {"appName": args.app})
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_deploy_info(args) -> int:
    """根据发布流程实例名查询完整发布详情。"""
    try:
        data = call_tool(
            "get_deploy_info_by_changeflow_name",
            {"changeflowName": args.name},
        )
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_pod_info(args) -> int:
    """查询部署组下的工作负载及 Pod 信息。"""
    try:
        data = call_tool(
            "get_workload_group_workloads",
            {"service": args.service, "workloadGroupName": args.workload_group},
        )
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_deploy_history(args) -> int:
    """查询指定部署组的发布历史。"""
    try:
        arguments: dict = {
            "applicationChildName": args.service,
            "workloadGroupName": args.workload_group,
        }
        if args.image_tag:
            arguments["imageTag"] = args.image_tag
        data = call_tool(
            "get_deploy_history_by_workload_group_and_image_tag",
            arguments,
        )
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_diagnose(args) -> int:
    """诊断发布流程运行状态（含 Pod 状态和日志，用于发布卡住或异常时的排查）。"""
    try:
        data = call_tool(
            "check_step_pipelinerun_running_stages_status",
            {"changeflowName": args.name},
        )
        print_json(data)
    except Exception as e:
        print_error(str(e))
        return 1
    return 0


def cmd_deploy(args) -> int:
    """
    创建发布流程实例（含交互式确认）。

    完整发布流程：
    1. 校验部署组发布前状态（check_workload_groups_for_changeflow）
    2. 展示发布参数，用户确认（--yes 可跳过）
    3. create_deploy_with_watch：创建并开启值守
    4. 输出发布流程实例信息（含链接，由 ones 后端返回）

    注意：ones 后端会对发布环境做安全校验，线上环境发布需要通过 ones 平台审批流程。
    """
    service: str = args.service
    changeflow_info_name: str = args.changeflow
    workload_groups: list = args.workload_groups
    repo_tag: str = args.tag
    description: str = args.description or ""
    skip_confirm: bool = args.yes

    # ── 步骤 1: 校验部署组状态 ──
    print_info("正在校验部署组发布前状态...")
    try:
        check_result = call_tool(
            "check_workload_groups_for_changeflow",
            {
                "applicationChildName": service,
                "workloadGroups": workload_groups,
            },
        )
        if isinstance(check_result, dict):
            if check_result.get("deploying"):
                print_warning("检测到部署组正在发布中，新发布将排队等待")
            if check_result.get("requireApproval"):
                print_warning("该发布需要审批，请关注 ones 审批进度")
            if check_result.get("firstDeploy"):
                print_info("首次发布，ones 会自动初始化部署组配置")
        print_info(f"校验结果: {json.dumps(check_result, ensure_ascii=False)}")
    except Exception as e:
        print_warning(f"发布前校验异常（不阻断发布，ones 后端仍会做校验）: {e}")

    # ── 步骤 2: 展示发布参数，用户确认 ──
    print("\n" + "=" * 55)
    print("待发布参数：")
    print(f"  服务名:       {service}")
    print(f"  发布模板:     {changeflow_info_name}")
    print(f"  部署组:       {', '.join(workload_groups)}")
    print(f"  镜像 Tag:     {repo_tag}")
    if description:
        print(f"  发布描述:     {description}")
    print("=" * 55)
    print_info("注意：ones 后端会对发布环境做安全校验，线上发布需审批。")

    if not skip_confirm:
        try:
            ans = input("确认发布以上内容？[y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = ""
        if ans not in ("y", "yes"):
            print_info("用户取消发布")
            return 0

    # ── 步骤 3: 创建发布 ──
    print_info("正在创建发布流程，开启值守...")
    arguments: dict = {
        "applicationChildName": service,
        "changeflowInfoName": changeflow_info_name,
        "workloadGroups": workload_groups,
        "repoTag": repo_tag,
    }
    if description:
        arguments["description"] = description

    try:
        result = call_tool("create_deploy_with_watch", arguments)
    except Exception as e:
        print_error(f"创建发布失败: {e}")
        return 1

    # ── 步骤 4: 输出结果 ──
    print_json(result)
    print_info("发布流程已创建，值守已开启。可用 deploy-info 子命令查询发布进度。")
    return 0


# ──────────────────────────────────────────────
# 命令行解析
# ──────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ones_deploy.py",
        description="ones 发布平台 Agent Tool 调用封装",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查询当前用户有权限的服务列表
  python ones_deploy.py my-services

  # 查询服务下的发布流程模板和部署组
  python ones_deploy.py changeflows <service>

  # 查询可用镜像 tag
  python ones_deploy.py images <service>

  # 校验部署组发布前状态
  python ones_deploy.py check <service> sit.svc sit.svc.staging

  # 触发发布（交互确认）
  python ones_deploy.py deploy <service> \\
    --changeflow <changeflowInfoName> \\
    --workload-groups sit.svc sit.svc.staging \\
    --tag <imageTag>

  # 查询发布详情
  python ones_deploy.py deploy-info <changeflowName>

  # 诊断卡住的发布
  python ones_deploy.py diagnose <changeflowName>
        """,
    )

    sub = parser.add_subparsers(dest="subcommand", help="子命令")

    # list-tools
    sub.add_parser("list-tools", help="列出所有可用 tool")

    # my-apps
    sub.add_parser("my-apps", help="查询当前用户有权限的应用列表")

    # my-services
    sub.add_parser("my-services", help="查询当前用户有权限的服务列表")

    # app-info
    p_app = sub.add_parser("app-info", help="查询应用详情（含服务及部署组）")
    p_app.add_argument("app", help="应用名（appName）")

    # service-info
    p_svc = sub.add_parser("service-info", help="查询服务的部署组信息")
    p_svc.add_argument("service", help="服务名（service）")
    p_svc.add_argument("--application", default="", help="应用名（可选，自动推断）")

    # images
    p_img = sub.add_parser("images", help="查询服务可用的镜像版本列表")
    p_img.add_argument("service", help="服务名（applicationChildName）")

    # changeflows
    p_cf = sub.add_parser("changeflows", help="查询服务下的发布流程模板及部署组")
    p_cf.add_argument("service", help="服务名（applicationChildName）")

    # check
    p_chk = sub.add_parser("check", help="校验部署组发布前状态")
    p_chk.add_argument("service", help="服务名（applicationChildName）")
    p_chk.add_argument(
        "workload_groups", nargs="+", metavar="workload-group",
        help="部署组列表（可多个，如 sit.svc sit.svc.staging）",
    )

    # my-changeflows
    sub.add_parser("my-changeflows", help="查询我最近 7 天的发布流程列表")

    # my-changeflows-by-app
    p_cfapp = sub.add_parser("my-changeflows-by-app", help="查询我在指定应用下的发布流程")
    p_cfapp.add_argument("app", help="应用名（appName）")

    # deploy-info
    p_di = sub.add_parser("deploy-info", help="根据发布流程实例名查询详情")
    p_di.add_argument("name", help="发布流程实例名（changeflowName）")

    # pod-info
    p_pod = sub.add_parser("pod-info", help="查询部署组下的工作负载及 Pod 信息")
    p_pod.add_argument("service", help="服务名")
    p_pod.add_argument("workload_group", metavar="workload-group", help="部署组名")

    # deploy-history
    p_hist = sub.add_parser("deploy-history", help="查询指定部署组的发布历史")
    p_hist.add_argument("service", help="服务名（applicationChildName）")
    p_hist.add_argument("workload_group", metavar="workload-group", help="部署组名")
    p_hist.add_argument(
        "--image-tag", dest="image_tag", default="",
        help="镜像 tag（可选，用于过滤特定版本的发布历史）",
    )

    # diagnose
    p_diag = sub.add_parser("diagnose", help="诊断发布流程运行状态（发布卡住时使用）")
    p_diag.add_argument("name", help="发布流程实例名（changeflowName）")

    # deploy
    p_dep = sub.add_parser("deploy", help="创建发布流程（含交互确认，ones 后端负责环境安全校验）")
    p_dep.add_argument("service", help="服务名（applicationChildName）")
    p_dep.add_argument(
        "--changeflow", required=True,
        help="发布流程模板名（changeflowInfoName），可通过 changeflows 子命令查询",
    )
    p_dep.add_argument(
        "--workload-groups", dest="workload_groups", nargs="+", required=True,
        metavar="wg",
        help="部署组列表（可多个），如 sit.svc sit.svc.staging",
    )
    p_dep.add_argument("--tag", required=True, help="镜像 tag（repoTag），可通过 images 子命令查询")
    p_dep.add_argument("--description", default="", help="发布描述（可选）")
    p_dep.add_argument("--yes", "-y", action="store_true", help="跳过交互确认，直接发布")

    return parser


SUBCOMMAND_MAP = {
    "list-tools": cmd_list_tools,
    "my-apps": cmd_my_apps,
    "my-services": cmd_my_services,
    "app-info": cmd_app_info,
    "service-info": cmd_service_info,
    "images": cmd_images,
    "changeflows": cmd_changeflows,
    "check": cmd_check,
    "my-changeflows": cmd_my_changeflows,
    "my-changeflows-by-app": cmd_my_changeflows_by_app,
    "deploy-info": cmd_deploy_info,
    "pod-info": cmd_pod_info,
    "deploy-history": cmd_deploy_history,
    "diagnose": cmd_diagnose,
    "deploy": cmd_deploy,
}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        return 0

    handler = SUBCOMMAND_MAP.get(args.subcommand)
    if not handler:
        print_error(f"未知子命令: {args.subcommand}")
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
