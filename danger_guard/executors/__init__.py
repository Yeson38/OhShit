# danger_guard/executors/__init__.py
"""
系统原生命令执行层。
设计原则：
1. 绝对不经过 Shell alias，POSIX 用可执行文件绝对路径（/bin/rm），
   Windows 用 powershell -NoProfile（避免 $PROFILE 注入 alias）。
2. 永远不调用 "ohshit" / "rm" / "dd" 等裸名，防止触发自身别名造成无限递归。
3. 所有执行器支持 dry_run=True 模式（只打印不执行，用于集成测试）。
"""
from typing import Dict
import danger_guard.config as config

# 统一调度入口（方便 Hook 不知道自己跑在哪）
def dispatch_exec(command_family: str, parsed: Dict, dry_run: bool = False):
    """
    按当前系统类型调度到对应执行器。
    command_family: "rm" 或 "dd"
    """
    sys_name = config.detect_system()
    if sys_name == "Windows":
        from . import windows_exec
        if command_family == "rm":
            return windows_exec.exec_remove_item(parsed, dry_run)
        elif command_family == "dd":
            return windows_exec.exec_dd(parsed, dry_run)
    else:
        from . import posix_exec
        if command_family == "rm":
            return posix_exec.exec_rm(parsed, dry_run)
        elif command_family == "dd":
            return posix_exec.exec_dd(parsed, dry_run)
    raise ValueError(f"未知命令族: {command_family}")

__all__ = ["posix_exec", "windows_exec", "dispatch_exec"]
