"""
pytest 公共 fixture。
提供：临时目录工厂、fake_isatty（模拟 TTY）、patch_stdin（模拟用户输入）。
"""
import io
import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional
from unittest import mock

import pytest


@pytest.fixture
def tmp_workspace() -> Path:
    """创建一个有内容的临时测试目录，测试完毕自动删除。
    目录结构：
        tmp_workspace/
        ├── report_final_v3.docx (100 bytes)
        ├── thesis_backup.pdf (200 bytes)
        ├── customer_db.sql (4096 bytes)
        ├── notes/
        │   ├── idea1.txt
        │   └── idea2.txt
        └── .hidden_secret (50 bytes, 隐藏文件)
    """
    tmp = Path(tempfile.mkdtemp(prefix="ohshit_test_"))
    # 文件 + 内容（填充非空字节确保大小真实）
    (tmp / "report_final_v3.docx").write_bytes(b"A" * 100)
    (tmp / "thesis_backup.pdf").write_bytes(b"B" * 200)
    (tmp / "customer_db.sql").write_bytes(b"C" * 4096)
    (tmp / "notes").mkdir()
    (tmp / "notes" / "idea1.txt").write_text("first idea\n")
    (tmp / "notes" / "idea2.txt").write_text("second idea\n")
    (tmp / ".hidden_secret").write_bytes(b"H" * 50)
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def fake_tty(monkeypatch):
    """让 sys.stdin / sys.stdout 假装是 TTY（交互模式）。"""
    def _fake_isatty(*args, **kwargs):
        return True
    monkeypatch.setattr(sys.stdin, 'isatty', _fake_isatty)
    monkeypatch.setattr(sys.stdout, 'isatty', _fake_isatty)
    monkeypatch.setattr(sys.stderr, 'isatty', _fake_isatty)
    yield


@pytest.fixture
def fake_pipe(monkeypatch):
    """让 sys.stdin 假装是管道（非交互模式，模拟脚本/cron）。"""
    def _not_a_tty(*args, **kwargs):
        return False
    monkeypatch.setattr(sys.stdin, 'isatty', _not_a_tty)
    monkeypatch.setattr(sys.stdout, 'isatty', _not_a_tty)
    monkeypatch.setattr(sys.stderr, 'isatty', _not_a_tty)
    yield


class _StdinSimulator:
    """帮助 monkeypatch input() / sys.stdin 模拟多轮用户输入。"""
    def __init__(self, lines: List[str]):
        self._buffer = lines[:]
        self._index = 0

    def readline(self) -> str:
        if self._index >= len(self._buffer):
            return ""  # EOF
        line = self._buffer[self._index]
        self._index += 1
        return line + "\n"


def patch_user_input(monkeypatch, inputs: List[str]) -> _StdinSimulator:
    """替换 sys.stdin 为指定输入序列。
    例：patch_user_input(monkeypatch, ["hello", "DELETE"]) 会让 input() 依次返回 "hello" 再 "DELETE"
    """
    sim = _StdinSimulator(inputs)
    monkeypatch.setattr('sys.stdin', sim)
    return sim
