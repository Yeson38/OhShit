# danger_guard/executors/posix_exec.py
"""
POSIX 平台（Linux / macOS）原生命令执行器。
使用绝对路径绕过 alias / function 递归。
"""
import os
import shutil
import subprocess
import sys
from typing import List, Dict, Optional
from danger_guard.hooks.base import HookExecutionResult


# ------------- 可执行文件绝对路径解析 -------------

def _resolve_executable(names: List[str]) -> str:
    """尝试在常见系统路径下查找可执行文件，找到第一个存在的返回绝对路径。"""
    # 先试 /bin /usr/bin /sbin /usr/sbin（传统位置）
    search_dirs = ["/bin", "/usr/bin", "/sbin", "/usr/sbin", "/usr/local/bin"]
    for d in search_dirs:
        for name in names:
            p = os.path.join(d, name)
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
    # 兜底：交给 shutil.which（它会走 $PATH，可能找到用户别名路径，但因绝对路径仍不会触发 alias）
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    # 最终兜底：返回标准路径（调用方会收到 FileNotFoundError，这是期望行为）
    return os.path.join("/bin", names[0])


# 可执行文件绝对路径（模块加载时解析一次）
RM_PATH = _resolve_executable(["rm"])
DD_PATH = _resolve_executable(["dd"])


# ------------- rm -------------

def build_rm_command(parsed: Dict) -> List[str]:
    """
    根据 rm Hook 的 parse_args() 结构化结果，构建可执行命令行列表。
    :param parsed: {"paths": List[str], "recursive": bool, "force": bool,
                     "verbose": bool, "interactive": bool, "extra_flags": List[str]}
    """
    cmd: List[str] = [RM_PATH]
    # 先加 flag（单独拆成 -r -f 等，便于测试断言 + 兼容各种 shell 风格）
    if parsed.get("recursive"):
        cmd.append("-r")
    if parsed.get("force"):
        cmd.append("-f")
    if parsed.get("verbose"):
        cmd.append("-v")
    if parsed.get("interactive"):
        cmd.append("-i")
    # 其他任意 flag（保留用户传入的 --preserve-root 等）
    cmd.extend(parsed.get("extra_flags") or [])
    # 最后加目标路径
    cmd.extend(parsed.get("paths") or [])
    return cmd


def exec_rm(parsed: Dict, dry_run: bool = False) -> HookExecutionResult:
    cmd = build_rm_command(parsed)
    if dry_run:
        print("[ohshit dry-run]  " + " ".join(cmd), file=sys.stderr)
        return HookExecutionResult(success=True, exit_code=0, message=None)
    try:
        completed = subprocess.run(cmd, check=False)
        code = completed.returncode
        return HookExecutionResult(
            success=(code == 0),
            exit_code=code,
            message=None,
        )
    except FileNotFoundError as e:
        return HookExecutionResult(
            success=False, exit_code=127,
            message=f"找不到原生命令 {RM_PATH}: {e}. 请检查系统安装。"
        )
    except OSError as e:
        return HookExecutionResult(
            success=False, exit_code=1,
            message=f"执行 rm 失败: {e}"
        )


# ------------- dd -------------

def build_dd_command(parsed: Dict) -> List[str]:
    """
    根据 dd Hook 的 parse_args() 结构化结果构建命令行。
    :param parsed: {"if": str, "of": str, "bs": str, "count": str,
                     "conv": str, "status": str,
                     "skip": str, "seek": str, "ibs": str, "obs": str,
                     "iflag": str, "oflag": str,
                     "extra_flags": List[str]}
    """
    cmd: List[str] = [DD_PATH]
    for key in ("if", "of", "bs", "count", "conv", "status",
                "skip", "seek", "ibs", "obs", "iflag", "oflag"):
        val = parsed.get(key, "")
        if val:
            cmd.append(f"{key}={val}")
    cmd.extend(parsed.get("extra_flags") or [])
    return cmd


def exec_dd(parsed: Dict, dry_run: bool = False) -> HookExecutionResult:
    cmd = build_dd_command(parsed)
    if dry_run:
        print("[ohshit dry-run]  " + " ".join(cmd), file=sys.stderr)
        return HookExecutionResult(success=True, exit_code=0, message=None)
    try:
        completed = subprocess.run(cmd, check=False)
        code = completed.returncode
        return HookExecutionResult(success=(code == 0), exit_code=code, message=None)
    except FileNotFoundError as e:
        return HookExecutionResult(
            success=False, exit_code=127,
            message=f"找不到原生命令 {DD_PATH}: {e}"
        )
    except OSError as e:
        return HookExecutionResult(
            success=False, exit_code=1,
            message=f"执行 dd 失败: {e}"
        )


__all__ = [
    "RM_PATH", "DD_PATH",
    "build_rm_command", "exec_rm",
    "build_dd_command", "exec_dd",
]
