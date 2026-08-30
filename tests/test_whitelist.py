"""
Task 5 - Whitelist 模块测试（Step 1 红灯阶段）。
"""
import os
import tempfile
from pathlib import Path

import pytest

from danger_guard.core import whitelist


def test_default_whitelist_entries():
    """默认白名单必须包含 /tmp/*、/var/tmp/*、~/.cache/*、/dev/null。"""
    items = whitelist.load_default_items()
    assert "/tmp/*" in items or "/tmp" in items
    assert "/var/tmp/*" in items or "/var/tmp" in items
    cache_pattern = os.path.expanduser("~") + "/.cache/*"
    assert any(cache_pattern in x for x in items) or any(".cache" in x for x in items)
    assert "/dev/null" in items


def test_is_whitelisted_path_all_temporary():
    """临时目录下的所有路径都应被判定为白名单。"""
    assert whitelist.is_whitelisted_path("/tmp/foo.txt") is True
    assert whitelist.is_whitelisted_path("/tmp/bar/baz.log") is True
    assert whitelist.is_whitelisted_path("/var/tmp/something") is True


def test_is_whitelisted_path_nested_under_whitelist():
    """白名单目录的嵌套子路径也应放行。"""
    wl = ["/tmp/safe_dir/*"]
    assert whitelist.is_whitelisted_path("/tmp/safe_dir/a/b/c.txt", whitelist=wl) is True
    assert whitelist.is_whitelisted_path("/tmp/safe_dir/", whitelist=wl) is True


def test_user_whitelist_file_expand_homedir():
    """用户白名单文件里的 ~ 应该正确展开。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("~/my_safe_dir/*\n")
        fpath = f.name
    try:
        items = whitelist.load_user_whitelist(fpath)
        expanded = os.path.expanduser("~/my_safe_dir/*")
        assert any(expanded in x or x.startswith(os.path.expanduser("~")) for x in items)
        wl = items
        target = os.path.expanduser("~/my_safe_dir/secret.txt")
        assert whitelist.is_whitelisted_path(target, whitelist=wl) is True
    finally:
        os.unlink(fpath)


def test_user_whitelist_file_with_comments():
    """# 开头的注释和空行应该被跳过；行尾内联 ' # comment' 也应被剥离。"""
    content = """# 这是全行行首注释
/tmp/safe_item

/home/user/docs  # 行尾内联注释
/var/data # 另一个注释
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        fpath = f.name
    try:
        items = whitelist.load_user_whitelist(fpath)
        # 注释行和空行不应计入
        assert len(items) == 3
        assert "#" not in items[0] and "#" not in items[1] and "#" not in items[2]
        assert "/tmp/safe_item" in items or items[0] == "/tmp/safe_item"
        assert any("home/user/docs" in x for x in items)
        assert any("var/data" in x for x in items)
    finally:
        os.unlink(fpath)


def test_load_user_whitelist_missing_file_returns_empty():
    """不存在的用户白名单文件应返回空列表，不抛异常。"""
    missing = "/this/path/definitely/does/not/exist_12345_whitelist.txt"
    result = whitelist.load_user_whitelist(missing)
    assert result == []
