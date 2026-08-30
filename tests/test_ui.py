"""
Task 5 - UI 红色警告框模块测试（Step 1 红灯阶段）。
"""
import pytest

from danger_guard.core import ui


def test_warning_box_contains_all_passed_message_lines(fake_tty):
    """warning_box 输出应包含所有传入的 message_lines 和默认提示语。"""
    lines = [
        "即将删除 /home/user/documents 目录",
        "影响 1,200 个文件，总计约 4.2 GB",
        "此操作不可逆！",
    ]
    result = ui.warning_box(
        title="⚠ 高风险操作 WARNING",
        message_lines=lines,
        risk_level=3,
        border_color="red",
    )
    # 检查所有消息行都出现在结果中（关键字即可，放宽空格要求）
    for ln in lines:
        assert ln in result
    # 检查默认提示语
    assert "Ctrl+C" in result
    assert "跳过" in result
    # 检查边框元素
    assert "┌" in result
    assert "└" in result
    assert "│" in result


def test_warning_box_respects_no_color_env(fake_tty, monkeypatch):
    """设置 NO_COLOR=1 后，warning_box 输出不应包含 ANSI 转义序列 \x1b[。"""
    monkeypatch.setenv("NO_COLOR", "1")
    lines = ["测试消息 Test message"]
    result = ui.warning_box(
        title="⚠ 高风险操作 WARNING",
        message_lines=lines,
        risk_level=3,
        border_color="red",
    )
    # 核心断言：不含 \x1b[ 前缀的颜色码
    assert "\x1b[" not in result, f"输出包含 ANSI 颜色码：{result!r}"


def test_preview_summary_renders_sample_items(fake_tty):
    """preview_summary 应渲染统计信息和前 N 个样本条目。"""
    samples = [
        "/data/logs/app1.log",
        "/data/logs/app2.log",
        "/data/tmp/old_cache.dat",
        "/data/tmp/session.db",
    ]
    result = ui.preview_summary(
        header="预删除预览",
        affected_count=4,
        total_size_bytes=1024 * 1024 * 5,  # 5 MB
        target_scope="/data",
        sample_items=samples,
        risk_level=3,
    )
    # 关键字段
    assert "预删除预览" in result
    assert "4" in result  # affected_count
    assert "/data" in result  # target_scope
    # 样本条目（至少前几个关键字出现）
    assert "app1.log" in result
    assert "app2.log" in result
    assert "old_cache.dat" in result
    # 人类可读大小（5 MB 左右）
    assert "MB" in result or "KB" in result or "B" in result
