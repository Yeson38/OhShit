"""dd hook 测试：参数解析 / 预览 / 执行调度。"""
import os
import pytest
from pathlib import Path
from unittest import mock

def test_dd_parse_args_separated_kv_tokens():
    from danger_guard.hooks import get_hook
    h = get_hook("dd")()
    parsed = h.parse_args(["if=/dev/zero", "of=/tmp/out.img", "bs=4M", "count=100", "conv=noerror,sync"])
    assert parsed.dd_if == "/dev/zero"
    assert parsed.dd_of == "/tmp/out.img"
    assert parsed.bs == "4M"
    assert parsed.count == "100"
    assert "noerror" in parsed.conv.split(",")

def test_dd_parse_args_mixed_with_flag_skipped():
    from danger_guard.hooks import get_hook
    h = get_hook("dd")()
    # dd 偶尔会带全局参数：--version / --help / status=progress
    parsed = h.parse_args(["if=/dev/sda", "of=/dev/null", "status=progress", "bs=1M"])
    assert parsed.dd_if == "/dev/sda"
    assert parsed.dd_of == "/dev/null"
    assert parsed.status == "progress"

def test_dd_parse_args_block_size_numeric_multiplier():
    from danger_guard.hooks.dd_hook import _parse_bytesize
    assert _parse_bytesize("512") == 512
    assert _parse_bytesize("4K") == 4 * 1024
    assert _parse_bytesize("4M") == 4 * 1024**2
    assert _parse_bytesize("2G") == 2 * 1024**3
    assert _parse_bytesize("") == 0

def test_dd_estimate_size_count_times_bs():
    from danger_guard.hooks import get_hook
    h = get_hook("dd")()
    parsed = h.parse_args(["if=/dev/zero", "of=/tmp/f.img", "bs=1M", "count=100"])
    preview = h.preview(parsed)
    assert preview.total_size_bytes == 100 * 1024**2
    assert preview.affected_count == 1   # 一个"文件对象"

def test_dd_preview_target_scope_shows_if_of():
    from danger_guard.hooks import get_hook
    h = get_hook("dd")()
    parsed = h.parse_args(["if=/dev/sda", "of=/dev/sdb", "bs=1M"])
    pr = h.preview(parsed)
    assert "/dev/sda" in pr.target_scope
    assert "/dev/sdb" in pr.target_scope

def test_dd_block_device_detection_triggers_risk_3(tmp_workspace):
    from danger_guard.hooks import get_hook
    h = get_hook("dd")()
    # 直接 patch _is_block_device 返回 True
    with mock.patch.object(type(h), "_is_block_device", return_value=True):
        parsed = h.parse_args(["if=/dev/zero", "of=/dev/sda", "bs=1M", "count=10"])
        pr = h.preview(parsed)
        assert pr.risk_level == 3
        assert any("块设备" in w or "block device" in w.lower() for w in pr.extra_warnings)

def test_dd_dry_run_execute_zero(tmp_workspace):
    from danger_guard.hooks import get_hook
    h = get_hook("dd")()
    parsed = h.parse_args(["if=/dev/zero", "of=/tmp/o.img", "bs=1K", "count=1"])
    r = h.execute(parsed, dry_run=True)
    assert r.exit_code == 0
    assert r.success is True

def test_dd_parse_count_missing_then_zero_size_but_count_preserved():
    # 如果用户没写 count= 或 seek= 或 skip=，dd 读到 EOF，估算 size = 0 但 target_scope 正常
    from danger_guard.hooks import get_hook
    h = get_hook("dd")()
    parsed = h.parse_args(["if=/dev/random", "of=/tmp/a.bin", "bs=1K"])
    pr = h.preview(parsed)
    assert pr.affected_count == 1
