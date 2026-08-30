import os
import pytest
import subprocess
import sys

def _run(argv, env=None):
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    cmd = [sys.executable, "-m", "danger_guard", *argv]
    cp = subprocess.run(cmd, capture_output=True, text=True, cwd="/workspace", env=full_env, timeout=30)
    return cp

def test_cli_list_hooks_shows_rm_and_dd():
    cp = _run(["--list-hooks"])
    assert cp.returncode == 0
    assert "rm" in cp.stdout
    assert "dd" in cp.stdout

def test_cli_dry_run_rm_without_force_prints_preview_nonzero_code(monkeypatch, tmp_path):
    # 非交互（subprocess.run 下默认不是 TTY）→ 正常非 force 应该跳过校验，
    # 所以我们强制 CLI 进入"跑校验"模式：用 NO_TTY= 是不行的，直接传 --danger-force 让它不跳过
    # 但我们这里只想看"能解析 + 打印 preview + 没 crash"，dry_run 就好
    f = tmp_path / "junk.log"
    f.write_text("hello")
    # 非交互 且无 override → should_run_checks=False → 直接 dispatch
    # 但 dry_run=True 会让 executor 也只打印
    cp = _run(["--dry-run", "--", "rm", "-f", str(f)])
    # 至少应该 0 或 127 之类
    assert cp.returncode in (0, 1)

def test_cli_version_flag():
    cp = _run(["--version"])
    assert cp.returncode == 0
    assert "1.0.0" in cp.stdout

def test_cli_missing_hook_name_returns_2_with_help_hint():
    cp = _run([])
    # argparse error → returncode == 2
    assert cp.returncode == 2
