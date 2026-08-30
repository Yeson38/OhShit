import pytest, os
from unittest import mock

def test_detect_command_rm_from_leading_rm_token():
    from danger_guard.core.engine import detect_command
    name, rest = detect_command(["rm", "-rf", "/tmp/a"])
    assert name == "rm"
    assert rest == ["-rf", "/tmp/a"]

def test_detect_command_native_commands_mapping():
    # 即便第一个 token 是 "/bin/rm" 也应识别为 rm hook
    from danger_guard.core.engine import detect_command
    name, rest = detect_command(["/bin/rm", "/tmp/foo"])
    assert name == "rm"

def test_detect_command_honours_positional_arg():
    from danger_guard.core.engine import detect_command
    # argv[0] 是我们的 CLI wrapper（dang / danger / ohshit），通过子命令 detect
    name, rest = detect_command(["dd", "if=/dev/zero", "of=/tmp/out.img", "bs=1M"])
    assert name == "dd"

def test_whitelist_bypass_returns_exit_code_0_without_validation(tmp_workspace):
    # 让 target 是 "/tmp/this-is-whitelisted-by-default-path-xxxx"
    from danger_guard.core.engine import run_pipeline
    fake_file = os.path.join(tmp_workspace, "a.bin")
    with open(fake_file, "w") as f:
        f.write("x")
    # 不跑真正的验证：用 whitelist 里的路径，bypass 应 return 0（whitelisted）
    # 但 /tmp 是 whitelist，所以用真正的 /tmp 下文件：
    # 但 tmp_workspace fixture 不一定在 /tmp，所以直接 monkeypatch whitelist
    from danger_guard.core import whitelist as wl
    with mock.patch.object(wl, "is_whitelisted_path", return_value=True):
        rc = run_pipeline("rm", ["-f", fake_file], dry_run=True)
    assert rc == 0

def test_bypass_for_non_interactive_pipe_no_validation(tmp_workspace):
    # 非交互 + 不 override → should_run_checks=False，管道模式直接 dispatch 到执行层
    from danger_guard.core.engine import run_pipeline
    from danger_guard.core import tty as tty_m
    with mock.patch.object(tty_m, "should_run_checks", return_value=False):
        with mock.patch("danger_guard.executors.posix_exec.subprocess.run") as run_m:
            from subprocess import CompletedProcess
            run_m.return_value = CompletedProcess([], returncode=0)
            f = os.path.join(tmp_workspace, "x.log")
            open(f, "w").write("a")
            rc = run_pipeline("rm", ["-f", f], dry_run=False)
    assert rc == 0

def test_tty_force_override_invokes_validation_and_passes_with_mocked_approval(tmp_workspace):
    """如果环境变量 DANGER_FORCE=1，应该跳过验证但仍执行命令"""
    from danger_guard.core.engine import run_pipeline
    from danger_guard.core import tty as tty_m
    with mock.patch.object(tty_m, "is_force_overridden", return_value=True), \
         mock.patch.object(tty_m, "should_run_checks", return_value=True):
        rc = run_pipeline("rm", ["-f", "/tmp/xyzabc_does_not_exist.log"], dry_run=True)
    assert rc == 0


def test_ctrl_c_during_validation_returns_rc130_no_stacktrace(tmp_workspace, capsys):
    """Step 6 验证阶段 Ctrl+C 不得堆栈；engine 应打印红色"✅ 已取消"，返回 rc=130。"""
    from danger_guard.core.engine import run_pipeline
    from danger_guard.core import tty as tty_m
    import danger_guard.core.engine as engine_m
    def _raise_kbi(*a, **kw):
        # engine 中调用 run_validation_loop 是 "from validator import run_validation_loop"，
        # 必须 patch 该 import 后的名字（engine.run_validation_loop），才会真正在 Step 6 触发。
        raise KeyboardInterrupt()
    tgt_dir = os.path.join(tmp_workspace, "kbi_target")
    os.makedirs(tgt_dir, exist_ok=True)
    with open(os.path.join(tgt_dir, "x.log"), "w") as f:
        f.write("hi")
    from danger_guard.core import whitelist as wl
    with mock.patch.object(tty_m, "is_force_overridden", return_value=False), \
         mock.patch.object(tty_m, "should_run_checks", return_value=True), \
         mock.patch.object(wl, "is_whitelisted_path", return_value=False), \
         mock.patch.object(engine_m, "run_validation_loop", _raise_kbi):
        rc = run_pipeline("rm", ["-rf", tgt_dir], dry_run=True)
    out = capsys.readouterr().out
    assert rc == 130, f"Ctrl+C 必须返回 shell 标准 rc=130，实际 {rc}（path={tgt_dir}）"
    assert any(kw in out for kw in ("已取消", "Ctrl+C", "中断", "取消")), f"out: {out[:500]}"
    assert "Traceback" not in out
    assert "KeyboardInterrupt" not in out


def test_ctrl_c_on_entry_main_returns_rc130():
    """顶层 __main__.main 也必须兜底 KBI 不堆栈，返回 rc=130。"""
    from danger_guard import __main__ as entry
    with mock.patch.object(entry, "run_pipeline") as rp:
        rp.side_effect = KeyboardInterrupt()
        rc = entry.main(["--dry-run", "--", "rm", "-f", "/tmp/x.log"])
    assert rc == 130, f"entry main 必须把 KBI 转为 rc=130，实际 {rc}"
