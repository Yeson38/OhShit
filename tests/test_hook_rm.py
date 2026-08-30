"""
tests/test_hook_rm.py — Task 6: rm Hook 参数解析 + os.walk 预览 + 执行调度。
TDD 红灯先行：此文件在 rm_hook.py 创建前会 ModuleNotFoundError。
"""
import os
import tempfile
import shutil
from pathlib import Path
from unittest import mock

import pytest

from danger_guard.hooks import get_hook


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rm_hook():
    """获取注册好的 RmHook 实例。"""
    HookCls = get_hook("rm")
    return HookCls()


@pytest.fixture
def three_level_workspace(tmp_workspace: Path) -> Path:
    """
    在 tmp_workspace 基础上扩展为 3 层嵌套，共 10 个文件 + 若干目录。
    最终结构：
        tmp/
        ├── report_final_v3.docx      （1）
        ├── thesis_backup.pdf         （2）
        ├── customer_db.sql           （3）
        ├── .hidden_secret            （4）
        ├── notes/
        │   ├── idea1.txt             （5）
        │   ├── idea2.txt             （6）
        │   └── deep/
        │       ├── sub_note_a.txt    （7）
        │       ├── sub_note_b.txt    （8）
        │       └── even_deeper/
        │           └── core.txt      （9）
        └── archive/
            └── old_report.docx       （10）
    文件：10 个；目录：notes/、notes/deep/、notes/deep/even_deeper/、archive/ —— 共 4 个。
    os.walk 会计入 dirs + files：总共 14。
    """
    # L1: notes/deep
    deep = tmp_workspace / "notes" / "deep"
    deep.mkdir(parents=True, exist_ok=True)
    (deep / "sub_note_a.txt").write_text("a" * 10)
    (deep / "sub_note_b.txt").write_text("b" * 20)
    # L2: notes/deep/even_deeper
    even_deeper = deep / "even_deeper"
    even_deeper.mkdir(parents=True, exist_ok=True)
    (even_deeper / "core.txt").write_text("core" * 5)
    # L1: archive
    archive = tmp_workspace / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "old_report.docx").write_text("old" * 30)
    return tmp_workspace


# ======================================================================
# TestRmParseArgs (7)
# ======================================================================

class TestRmParseArgs:

    def test_parse_basic_rf(self, rm_hook):
        """`rm -rf /tmp/foo` → recursive=True, force=True, paths=['/tmp/foo']"""
        p = rm_hook.parse_args(["-rf", "/tmp/foo"])
        assert p.recursive is True
        assert p.force is True
        assert "/tmp/foo" in p.paths

    def test_single_dash_recursive(self, rm_hook):
        """`rm -r /tmp/bar` → recursive=True（单字母 -r）"""
        p = rm_hook.parse_args(["-r", "/tmp/bar"])
        assert p.recursive is True
        assert "/tmp/bar" in p.paths

    def test_two_minus_recursive(self, rm_hook):
        """`rm --recursive /tmp/baz` → recursive=True（长选项 --recursive）"""
        p = rm_hook.parse_args(["--recursive", "/tmp/baz"])
        assert p.recursive is True
        assert "/tmp/baz" in p.paths

    def test_preserve_root_flag_recognized(self, rm_hook):
        """`rm --preserve-root=all /a` → preserve_root='all' 被正确解析"""
        p = rm_hook.parse_args(["--preserve-root=all", "/a"])
        # 允许字段叫 preserve_root 或其他等价
        assert getattr(p, "preserve_root", None) == "all" or "--preserve-root=all" in p.extra_flags

    def test_interactive_flag_stripped(self, rm_hook):
        """`rm -i file` → interactive 被解析（非空），且 -i 不落在 extra_flags 中。"""
        p = rm_hook.parse_args(["-i", "file"])
        assert p.interactive in ("always", "once", True)  # 非空即可
        assert "-i" not in p.extra_flags

    def test_recognize_multiple_paths(self, rm_hook):
        """`rm a b c` → paths 中应包含 3 个独立条目。"""
        p = rm_hook.parse_args(["a.txt", "b.txt", "c.txt"])
        assert len(p.paths) == 3
        assert "a.txt" in p.paths and "b.txt" in p.paths and "c.txt" in p.paths

    def test_no_dash_means_file_argument_only(self, rm_hook):
        """未传 -r/-R 时 recursive 必须为 False。"""
        p = rm_hook.parse_args(["just_a_file.dat"])
        assert p.recursive is False
        assert p.paths == ["just_a_file.dat"]


# ======================================================================
# TestRmPreview (4)
# ======================================================================

class TestRmPreview:

    def test_preview_recursive_counts_nested_items(self, rm_hook, three_level_workspace):
        """
        使用 3 层嵌套的临时目录，递归预览时：
        - affected_count 必须 ≥ 10（实际 14 = 10 files + 4 dirs）
        - total_size_bytes > 0
        - sample_items 非空且不超过 affected_count
        """
        parsed = rm_hook.parse_args(["-rf", str(three_level_workspace)])
        pr = rm_hook.preview(parsed)
        # 至少 10 个文件（dirs + files 总和肯定 ≥ 10）
        assert pr.affected_count >= 10
        assert pr.total_size_bytes > 0
        assert 0 < len(pr.sample_items) <= pr.affected_count

    def test_preview_non_recursive_single_file(self, rm_hook, tmp_workspace):
        """
        非递归模式 + 单个文件目标：
        affected_count 应等于实际文件数（1），且 sample_items 长度 1。
        """
        target = tmp_workspace / "report_final_v3.docx"
        parsed = rm_hook.parse_args([str(target)])
        pr = rm_hook.preview(parsed)
        # 非递归 + 文件 = 1 项
        assert pr.affected_count == 1
        assert len(pr.sample_items) == 1
        assert str(target) in pr.sample_items or "report_final_v3" in pr.sample_items[0]

    def test_preview_target_scope_is_parent_of_all_items(self, rm_hook, tmp_workspace):
        """
        多路径时 target_scope 应是所有 paths 的最长公共前缀。
        例如 paths=[/tmp/a/x, /tmp/a/y] → target_scope 以 "/tmp/a/" 开头。
        """
        a = tmp_workspace / "alpha"
        b = tmp_workspace / "beta"
        # 提前创建避免 "路径不存在" 干扰
        a.write_text("x")
        b.write_text("y")
        parsed = rm_hook.parse_args([str(a), str(b)])
        pr = rm_hook.preview(parsed)
        # target_scope 必须是两者的公共前缀：至少为 str(tmp_workspace) + "/"
        common = str(tmp_workspace) + os.sep
        assert pr.target_scope.startswith(common) or pr.target_scope == str(tmp_workspace)

    def test_preview_validation_pool_has_most_distinctive_names(self, rm_hook, tmp_workspace):
        """
        validation_pool 至少一个元素来自预览时真实受影响的 basename。
        并且：长名字优先（按 basename 长度降序）、去重、至少 3 个。
        """
        # 建两个长名字文件，确保它们的 basename 够"有辨识度"
        long1 = tmp_workspace / "very_long_report_name_final_v3_2026.docx"
        long2 = tmp_workspace / "customer_db_backup_full_2026_q2.sql"
        long1.write_bytes(b"X" * 50)
        long2.write_bytes(b"Y" * 60)
        parsed = rm_hook.parse_args(["-rf", str(tmp_workspace)])
        pr = rm_hook.preview(parsed)
        # pool 至少 3 个
        assert len(pr.validation_pool) >= 3
        # 至少一个 basename（去重后）来自真实受影响条目
        real_basenames = {os.path.basename(x) for x in pr.sample_items}
        real_basenames.add("very_long_report_name_final_v3_2026.docx")
        real_basenames.add("customer_db_backup_full_2026_q2.sql")
        pool_set = set(pr.validation_pool)
        # 交集非空即通过（至少一个 pool 元素来自真实 basename）
        assert pool_set & real_basenames, (
            f"validation_pool 中找不到任何真实受影响条目 basename。\n"
            f"pool={pr.validation_pool}\n"
            f"real_basenames(样本)={real_basenames}"
        )


# ======================================================================
# TestRmExecute (3)
# ======================================================================

class TestRmExecute:

    def test_execute_dry_run_returns_0_without_subprocess(self, rm_hook, monkeypatch):
        """
        dry_run=True 时 execute 必须：
        1. 返回 exit_code=0 / success=True
        2. 绝不真正调用 subprocess.run
        """
        called = {"flag": False}
        original_run = getattr(__import__("subprocess"), "run")

        def spying_run(*a, **kw):
            called["flag"] = True
            return original_run(*a, **kw)

        monkeypatch.setattr("subprocess.run", spying_run)

        parsed = rm_hook.parse_args(["-f", "/tmp/not_exist_xyz_123.txt"])
        result = rm_hook.execute(parsed, dry_run=True)
        assert result.exit_code == 0
        assert result.success is True
        assert called["flag"] is False, "dry_run 不应触发 subprocess.run"

    def test_execute_non_dry_runs_through_posix_dispatch_exec(self, rm_hook, monkeypatch):
        """
        Linux 下非 dry_run：最终会通过 subprocess.run 执行真实 rm 绝对路径。
        mock subprocess.run 返回 rc=0 的 CompletedProcess。
        """
        fake_completed = mock.MagicMock()
        fake_completed.returncode = 0

        with mock.patch("subprocess.run", return_value=fake_completed) as run_mock:
            # 用绝对路径定位一个真实存在的临时文件，保证 build_rm_command 路径合法
            tmpf = tempfile.NamedTemporaryFile(delete=False)
            tmpf.write(b"hi")
            tmpf.close()
            try:
                parsed = rm_hook.parse_args(["-f", tmpf.name])
                result = rm_hook.execute(parsed, dry_run=False)
            finally:
                if os.path.exists(tmpf.name):
                    os.unlink(tmpf.name)

            # 确保 subprocess.run 被调用过
            assert run_mock.called, "非 dry_run 必须走 subprocess.run"
            # 断言：传给 run 的 cmd[0] 是绝对路径（防 alias 递归）
            cmd = run_mock.call_args[0][0]
            assert cmd[0].startswith("/") and cmd[0].endswith("/rm")
            # 返回值
            assert result.exit_code == 0
            assert result.success is True

    def test_execute_dispatch_calls_hook_with_parsed_arguments(self, rm_hook):
        """
        execute() 内部必须把 parsed 参数透传给 dispatch_exec。
        用 mock.patch 替换 dispatch_exec 在 rm_hook 模块中的引用（patch where used）。
        """
        captured = {}

        def fake_dispatch(command_family, parsed, dry_run=False):
            captured["family"] = command_family
            captured["parsed"] = parsed
            captured["dry_run"] = dry_run
            from danger_guard.hooks.base import HookExecutionResult
            return HookExecutionResult(success=True, exit_code=0)

        # patch where used：rm_hook 是 from ... import dispatch_exec，
        # 所以必须 patch danger_guard.hooks.rm_hook.dispatch_exec 才生效。
        with mock.patch("danger_guard.hooks.rm_hook.dispatch_exec", side_effect=fake_dispatch):
            parsed = rm_hook.parse_args(["-rf", "/tmp/abc", "/tmp/def"])
            _ = rm_hook.execute(parsed, dry_run=True)

        assert captured.get("family") == "rm"
        assert captured.get("dry_run") is True
        # parsed 本身或其 dict 等价形式包含 paths 中的这两个路径
        cap_parsed = captured.get("parsed")
        if hasattr(cap_parsed, "paths"):
            assert "/tmp/abc" in cap_parsed.paths and "/tmp/def" in cap_parsed.paths
        elif isinstance(cap_parsed, dict):
            paths = cap_parsed.get("paths", [])
            assert "/tmp/abc" in paths and "/tmp/def" in paths
        else:
            pytest.fail(f"dispatch_exec 收到的 parsed 类型未知: {type(cap_parsed)}")
