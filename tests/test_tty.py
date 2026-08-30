"""
Task 5 - TTY 检测模块测试（Step 1 红灯阶段）。
"""
import os
import sys

import pytest

from danger_guard.core import tty


def test_is_interactive_tty_true_in_tty_fixture(fake_tty):
    """fake_tty fixture 下 is_interactive_tty 应返回 True。"""
    assert tty.is_interactive_tty() is True


def test_is_interactive_tty_false_in_pipe_fixture(fake_pipe):
    """fake_pipe fixture 下 is_interactive_tty 应返回 False。"""
    assert tty.is_interactive_tty() is False


def test_env_force_override_ignores_tty(fake_pipe, monkeypatch):
    """设置 FORCE 环境变量后，即使是管道模式，is_force_overridden 也应为 True。"""
    monkeypatch.setenv("DANGER_FORCE", "1")
    assert tty.is_force_overridden(cli_force_flag=False) is True
    # should_run_checks 在 override 时返回 False（跳过校验）
    assert tty.should_run_checks(cli_force_flag=False) is False


def test_cli_flag_override_regardless_of_tty(fake_pipe, monkeypatch):
    """cli_force_flag=True 时，不管 TTY 还是环境变量，都视为强制覆盖。"""
    # 确保没有环境变量覆盖
    monkeypatch.delenv("DANGER_FORCE", raising=False)
    assert tty.is_force_overridden(cli_force_flag=True) is True
    assert tty.should_run_checks(cli_force_flag=True) is False


def test_pipe_without_override_bypasses_all_checks(fake_pipe, monkeypatch):
    """纯管道（非交互）模式且无覆盖时，should_run_checks 返回 False（自动跳过）。"""
    monkeypatch.delenv("DANGER_FORCE", raising=False)
    # 非交互 TTY
    assert tty.is_interactive_tty() is False
    # 没有任何覆盖
    assert tty.is_force_overridden(cli_force_flag=False) is False
    # 所以应该跳过校验
    assert tty.should_run_checks(cli_force_flag=False) is False
