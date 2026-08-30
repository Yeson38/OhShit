# tests/test_executors_posix.py
import pytest
from unittest import mock
from danger_guard.executors.posix_exec import (
    build_rm_command,
    build_dd_command,
    exec_rm,
    exec_dd,
    HookExecutionResult,
)


def test_build_rm_command_basic():
    parsed = {"paths": ["/tmp/a.txt", "/tmp/b"], "recursive": True, "force": True,
              "verbose": False, "interactive": False, "extra_flags": []}
    cmd = build_rm_command(parsed)
    # 必须是绝对路径 /bin/rm 或 /usr/bin/rm，不能只是 "rm"（防止 alias 递归）
    assert cmd[0].startswith("/") and cmd[0].endswith("/rm")
    assert "-r" in cmd or "-R" in cmd or "--recursive" in cmd
    assert "-f" in cmd or "--force" in cmd
    assert "/tmp/a.txt" in cmd
    assert "/tmp/b" in cmd


def test_build_rm_command_non_recursive_simple():
    parsed = {"paths": ["file.txt"], "recursive": False, "force": False,
              "verbose": False, "interactive": False, "extra_flags": ["-v"]}
    cmd = build_rm_command(parsed)
    assert cmd[0].startswith("/")
    assert "-r" not in " ".join(cmd).lower()  # 不传 recursive 就不该有 -r
    assert "-f" not in cmd


def test_build_dd_command_basic():
    parsed = {"if": "/dev/zero", "of": "/tmp/out.img", "bs": "4M",
              "count": "100", "conv": "", "status": "progress", "extra_flags": []}
    cmd = build_dd_command(parsed)
    assert cmd[0].startswith("/") and cmd[0].endswith("/dd")
    assert "if=/dev/zero" in cmd
    assert "of=/tmp/out.img" in cmd
    assert "bs=4M" in cmd
    assert "count=100" in cmd


def test_build_dd_command_skips_empty_fields():
    parsed = {"if": "/tmp/in", "of": "/tmp/out", "bs": "", "count": "",
              "conv": "", "status": "", "extra_flags": []}
    cmd = build_dd_command(parsed)
    assert not any(arg.startswith("bs=") and arg == "bs=" for arg in cmd)
    assert not any(arg.startswith("count=") and arg == "count=" for arg in cmd)
    assert "if=/tmp/in" in cmd and "of=/tmp/out" in cmd


def test_exec_rm_dry_run_no_subprocess_call():
    """dry_run 模式不得调用 subprocess。"""
    with mock.patch('subprocess.run') as run_mock:
        parsed = {"paths": ["/tmp/xxx"], "recursive": False, "force": False,
                  "verbose": False, "interactive": False, "extra_flags": []}
        result = exec_rm(parsed, dry_run=True)
        assert result.success is True
        assert result.exit_code == 0
        run_mock.assert_not_called()
