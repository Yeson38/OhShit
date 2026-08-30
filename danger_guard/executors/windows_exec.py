# danger_guard/executors/windows_exec.py
"""
Windows 平台原生命令执行器。
- 删除走 PowerShell Remove-Item（必须加 -NoProfile 防 $PROFILE 中 Set-Alias 递归）
- dd 走 Git Bash 自带 dd.exe 或其他用户自行安装的 dd 可执行文件，找不到报错
"""
import os
import shutil
import subprocess
import sys
from typing import List, Dict
from danger_guard.hooks.base import HookExecutionResult


def _powershell_path() -> str:
    return shutil.which("powershell") or shutil.which("pwsh") or "powershell.exe"


def _escape_pwsh_arg(s: str) -> str:
    """把字符串转义成 PowerShell 单引号参数（单引号用 '' 转义）。"""
    return "'" + s.replace("'", "''") + "'"


# ========== Remove-Item (替代 rm) ==========

def build_remove_item_script(parsed: Dict) -> str:
    """
    生成 PowerShell Remove-Item 脚本字符串（单文件执行）。
    :param parsed: {"paths": List[str], "recursive": bool, "force": bool,
                     "verbose": bool, "interactive": bool, "extra_flags": List[str]}
    """
    ps_flags: List[str] = []
    if parsed.get("recursive"):
        ps_flags.append("-Recurse")
    if parsed.get("force"):
        ps_flags.append("-Force")
    if parsed.get("verbose"):
        ps_flags.append("-Verbose")
    # PowerShell 的 -Confirm 默认 False，interactive=True 时显式加
    if parsed.get("interactive"):
        ps_flags.append("-Confirm")

    paths = parsed.get("paths") or []
    # 对每个路径独立执行，避免通配符解析问题
    lines = []
    for p in paths:
        escaped = _escape_pwsh_arg(p)
        lines.append(f"Remove-Item -Path {escaped} {' '.join(ps_flags)} -ErrorAction Stop")
    return "\n".join(lines)


def exec_remove_item(parsed: Dict, dry_run: bool = False) -> HookExecutionResult:
    script = build_remove_item_script(parsed)
    cmd = [_powershell_path(), "-NoProfile", "-NonInteractive",
           "-NoLogo", "-Command", script]
    if dry_run:
        print("[ohshit dry-run]  " + " ".join(cmd), file=sys.stderr)
        return HookExecutionResult(success=True, exit_code=0, message=None)
    try:
        completed = subprocess.run(cmd, check=False)
        code = completed.returncode
        return HookExecutionResult(success=(code == 0), exit_code=code, message=None)
    except FileNotFoundError as e:
        return HookExecutionResult(success=False, exit_code=127,
                                   message=f"找不到 PowerShell: {e}")
    except OSError as e:
        return HookExecutionResult(success=False, exit_code=1,
                                   message=f"执行 Remove-Item 失败: {e}")


# ========== dd on Windows ==========

def _resolve_dd_on_windows() -> str:
    """在 Windows 上找 dd 可执行文件（Git Bash / Cygwin / WSL / 手动安装）。"""
    candidates = [
        # Git Bash 常见安装位置
        r"C:\Program Files\Git\usr\bin\dd.exe",
        r"C:\Program Files (x86)\Git\usr\bin\dd.exe",
        # 用户 PATH
        shutil.which("dd") or "",
        # WSL 下的 dd
        "",
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    # 最终兜底：如果用户 PATH 里有就返回"dd"（尽管风险较高）
    return shutil.which("dd") or "dd.exe"


def build_dd_command(parsed: Dict) -> List[str]:
    """与 POSIX 版本 build_dd_command 逻辑相同，但使用 Windows 可执行路径。"""
    cmd = [_resolve_dd_on_windows()]
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
    # 兜底检查：如果 exe 路径不存在，直接报友好错误（dd 不是 Windows 预装，用户大概率没有）
    if not os.path.isfile(cmd[0]) and shutil.which(cmd[0]) is None:
        return HookExecutionResult(
            success=False, exit_code=127,
            message=(
                f"在 Windows 上未找到 dd 可执行文件（期望位置: {cmd[0]}）。"
                " 请安装 Git for Windows（自带 /usr/bin/dd.exe）或手动指定 dd 路径。"
            )
        )
    try:
        completed = subprocess.run(cmd, check=False)
        return HookExecutionResult(
            success=(completed.returncode == 0),
            exit_code=completed.returncode,
            message=None,
        )
    except OSError as e:
        return HookExecutionResult(success=False, exit_code=1,
                                   message=f"执行 dd 失败: {e}")


__all__ = [
    "build_remove_item_script", "exec_remove_item",
    "build_dd_command", "exec_dd",
]
