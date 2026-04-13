#!/usr/bin/env python3
"""
检测 rec-new-note-diagnosis 的依赖 skills

用法：
    python3 check_dependencies.py
    
返回：
    0 - 所有依赖已安装
    1 - 有依赖缺失
"""

import os
import sys

# 必需的依赖 skills
REQUIRED_SKILLS = [
    {
        "name": "xray_changevent_query",
        "description": "查询 XRay 变更事件（Apollo配置+实验变更）",
        "install_cmd": "openclaw skill install xray_changevent_query",
        "path": "skills/xray_changevent_query",
        "script": "scripts/query.py",
        "required": True
    },
    {
        "name": "xray_metrics_query", 
        "description": "查询 XRay 监控指标（Prometheus/VictoriaMetrics）",
        "install_cmd": "openclaw skill install xray_metrics_query",
        "path": "skills/xray_metrics_query",
        "script": "scripts/query.py",
        "required": True
    },
    {
        "name": "index-switch-check",
        "description": "检查索引切换状态（RIS/Omega）",
        "install_cmd": "openclaw skill install index-switch-check",
        "path": "skills/index-switch-check",
        "script": "scripts/check_switch.py",
        "required": True
    },
]

# SSO 登录态：直接读取全局 token 文件，无需安装 data-fe-common-sso
# Token 路径：/home/node/.token/sso_token.json（由 OpenClaw 自动维护）

# 可选依赖
OPTIONAL_SKILLS = [
    {
        "name": "hi-redoc-curd",
        "description": "上传文档到 Redoc",
        "install_cmd": "openclaw skill install hi-redoc-curd",
        "path": "skills/hi-redoc-curd",
        "script": "scripts/hi-redoc-curd.sh",
        "required": False
    }
]


def get_workspace_dir():
    """获取 workspace 目录"""
    # 当前脚本路径：skills/rec-new-note-diagnosis/scripts/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 上级目录：skills/rec-new-note-diagnosis/
    skill_dir = os.path.dirname(script_dir)
    # 上上级目录：skills/
    skills_dir = os.path.dirname(skill_dir)
    # 再上上级：workspace/
    workspace_dir = os.path.dirname(skills_dir)
    return workspace_dir


def check_skill_installed(skill):
    """检查 skill 是否安装"""
    workspace = get_workspace_dir()
    skill_path = os.path.join(workspace, skill["path"])
    script_path = os.path.join(skill_path, skill["script"])
    
    return os.path.exists(skill_path) and os.path.exists(script_path)


def print_separator():
    print("-" * 60)


def install_skills(skills, dry_run=False):
    """安装 skills 列表"""
    import subprocess
    
    if not skills:
        return True
    
    skill_names = " ".join([s["name"] for s in skills])
    cmd = f"openclaw skill install {skill_names}"
    
    print(f"\n🔧 执行安装命令：{cmd}")
    
    if dry_run:
        print("（dry-run 模式，未实际执行）")
        return True
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print("✅ 安装成功！")
            return True
        else:
            print(f"❌ 安装失败：{result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ 安装超时（>5 分钟）")
        return False
    except Exception as e:
        print(f"❌ 安装异常：{e}")
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="检测 rec-new-note-diagnosis 的依赖 skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 check_dependencies.py              # 仅检查依赖
  python3 check_dependencies.py --install    # 检查并安装缺失的依赖
  python3 check_dependencies.py --dry-run    # 预览将安装的 skills
        """
    )
    parser.add_argument("--install", action="store_true",
                        help="自动安装缺失的依赖")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览将安装的 skills，不实际执行")
    parser.add_argument("--all", action="store_true",
                        help="安装所有依赖（包括可选）")
    
    args = parser.parse_args()
    
    print_separator()
    print("🔍 检测 rec-new-note-diagnosis 依赖项")
    print_separator()
    print()
    
    missing_required = []
    missing_optional = []
    
    # 检查必需依赖
    print("📦 必需依赖：")
    for skill in REQUIRED_SKILLS:
        installed = check_skill_installed(skill)
        status = "✅" if installed else "❌"
        print(f"  {status} {skill['name']}")
        print(f"     说明：{skill['description']}")
        
        if not installed:
            missing_required.append(skill)
    
    print()
    
    # 检查可选依赖
    print("📦 可选依赖：")
    for skill in OPTIONAL_SKILLS:
        installed = check_skill_installed(skill)
        status = "✅" if installed else "⚠️ "
        print(f"  {status} {skill['name']}")
        print(f"     说明：{skill['description']}")
        
        if not installed:
            missing_optional.append(skill)
    
    print()
    print_separator()
    
    # 输出结果
    if missing_required:
        print("❌ 缺少必需的 skill 依赖：")
        print()
        for i, skill in enumerate(missing_required, 1):
            print(f"{i}. {skill['name']}")
            print(f"   说明：{skill['description']}")
            print(f"   安装命令：{skill['install_cmd']}")
            print()
        
        if args.install or args.dry_run:
            print("💡 准备安装缺失的依赖...")
            success = install_skills(missing_required, dry_run=args.dry_run)
            if success and not args.dry_run:
                print("\n✅ 依赖安装完成！重新运行诊断脚本即可使用。")
                print("   python3 skills/rec-homefeed-newnote-diagnosis/scripts/diagnose.py")
            return 0 if success else 1
        else:
            print("💡 快速安装所有依赖：")
            print()
            print("openclaw skill install xray_changevent_query xray_metrics_query index-switch-check")
            print()
            print("或使用自动安装：")
            print("python3 scripts/check_dependencies.py --install")
            print()
            return 1
    
    if missing_optional:
        print("⚠️  可选依赖未安装（不影响核心功能）：")
        for skill in missing_optional:
            print(f"  - {skill['name']}: {skill['install_cmd']}")
        print()
        
        if args.all and (args.install or args.dry_run):
            print("💡 准备安装可选依赖...")
            install_skills(missing_optional, dry_run=args.dry_run)
    
    print("✅ 所有必需依赖已安装，可以正常使用 rec-new-note-diagnosis。")
    print()
    print("使用示例：")
    print("  python3 skills/rec-homefeed-newnote-diagnosis/scripts/diagnose.py")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
