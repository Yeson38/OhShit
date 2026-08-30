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
        # 实际上仍会进入 7 步，只是会在"force"分支跳过验证（Step 6 force）
        rc = run_pipeline("rm", ["-f", "/tmp/xyzabc_does_not_exist.log"], dry_run=True)
    assert rc == 0
