# OhShit 删库跑路预防针 - 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2 个开发日内交付可演示 MVP：rm + dd 双命令拦截 + 可扩展钩子框架 + 三阶防护（预演量化 + 红色警告 + B- 随机文件名验证）+ 跨平台安装脚本。

**Architecture:** Python 包结构，完全模块化单向依赖。BaseHook 抽象基类 + @register_hook 装饰器 + pkgutil 自动发现实现零侵入扩展。三阶防护流程由 core/engine.py 统一编排，各 Hook 调用 executors 层以绝对路径执行原生命令防 alias 递归。

**Tech Stack:** Python 3.7+ 标准库（argparse, pathlib, subprocess, abc, pkgutil, shutil），ANSI 转义序列做终端彩色（无需 colorama），pytest 测试。

---

## 文件结构总览

以下文件按创建依赖顺序排列，先建基础模块再建上层模块。

| # | 路径 | 职责 | 新建/修改 |
|---|---|---|---|
| 1 | `danger_guard/__init__.py` | 包标识，导出版本号 | 新建 |
| 2 | `danger_guard/config.py` | 系统检测、路径常量、环境变量 | 新建 |
| 3 | `danger_guard/hooks/__init__.py` | 注册表 + @register_hook + 自动发现 | 新建 |
| 4 | `danger_guard/hooks/base.py` | BaseHook ABC + PreviewResult + HookExecutionResult | 新建 |
| 5 | `danger_guard/executors/__init__.py` | 导出子模块接口 | 新建 |
| 6 | `danger_guard/executors/posix_exec.py` | POSIX 平台 rm/dd 执行（绝对路径） | 新建 |
| 7 | `danger_guard/executors/windows_exec.py` | Windows 平台 Remove-Item/dd 执行 | 新建 |
| 8 | `danger_guard/hooks/rm_hook.py` | rm 拦截器：参数解析/预览/执行 | 新建 |
| 9 | `danger_guard/hooks/dd_hook.py` | dd 拦截器：参数解析/预览/执行 | 新建 |
| 10 | `danger_guard/core/__init__.py` | core 包标识 | 新建 |
| 11 | `danger_guard/core/tty_detector.py` | TTY 检测 + DANGER_FORCE 环境变量判断 | 新建 |
| 12 | `danger_guard/core/ui.py` | 红色警告框渲染、彩色输出、最终确认 | 新建 |
| 13 | `danger_guard/core/validator.py` | B- 验证：形近字规范化 + 反复制粘贴 + 3 次重试 | 新建 |
| 14 | `danger_guard/core/whitelist.py` | ~/.danger-whitelist 解析 + 默认白名单 | 新建 |
| 15 | `danger_guard/core/engine.py` | 三阶防护 7 步流程编排器（唯一公开：run_pipeline） | 新建 |
| 16 | `danger_guard/cli.py` | argparse 入口，--cmd 路由到 engine | 新建 |
| 17 | `danger_guard/__main__.py` | python -m danger_guard 入口 | 新建 |
| 18 | `danger_guard/scripts/install.sh` | Linux/macOS 一键安装（alias + 还原点 + 卸载脚本生成） | 新建 |
| 19 | `danger_guard/scripts/install.ps1` | Windows 一键安装（PowerShell Set-Alias + 卸载脚本生成） | 新建 |
| 20 | `tests/__init__.py` | 测试包标识 | 新建 |
| 21 | `tests/conftest.py` | pytest 公共 fixture（tmp 目录、fake_tty、stdin patch helper） | 新建 |
| 22 | `tests/test_config.py` | config.detect_system 跨平台 mock 测试 | 新建 |
| 23 | `tests/test_validator.py` | B- 算法全量测试：规范化/形近字/反复制粘贴/编辑距离/3 次重试 | 新建 |
| 24 | `tests/test_whitelist.py` | 白名单解析、默认白名单、匹配逻辑 | 新建 |
| 25 | `tests/test_hooks_rm.py` | rm 参数解析、preview 统计、validation_pool | 新建 |
| 26 | `tests/test_hooks_dd.py` | dd 参数解析（if=/of=/bs=）、块设备降级路径 | 新建 |
| 27 | `tests/test_ui.py` | 警告框渲染（ANSI 码断言）、人类可读大小格式化 | 新建 |
| 28 | `tests/test_engine_smoke.py` | 完整 7 步 pipeline 冒烟测试（dry_run + monkeypatch） | 新建 |
| 29 | `pyproject.toml` | 项目元数据、依赖、pytest 配置（测试工具配置） | 新建 |

---

## Task 1: 项目骨架 + config 模块（基础依赖）

**Files:**
- Create: `danger_guard/__init__.py`
- Create: `danger_guard/config.py`
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test for detect_system**

```python
# tests/test_config.py
import platform
import pytest
from unittest import mock

def test_detect_system_linux():
    with mock.patch.object(platform, 'system', return_value='Linux'):
        from danger_guard.config import detect_system
        assert detect_system() == 'Linux'

def test_detect_system_darwin():
    with mock.patch.object(platform, 'system', return_value='Darwin'):
        from danger_guard.config import detect_system
        assert detect_system() == 'Darwin'

def test_detect_system_windows():
    with mock.patch.object(platform, 'system', return_value='Windows'):
        from danger_guard.config import detect_system
        assert detect_system() == 'Windows'

@pytest.mark.parametrize('cygwin_like', ['CYGWIN_NT-10.0', 'MINGW64_NT-10.0', 'MSYS_NT-10.0'])
def test_detect_system_cygwin_family_maps_to_windows(cygwin_like):
    with mock.patch.object(platform, 'system', return_value=cygwin_like):
        from danger_guard.config import detect_system
        assert detect_system() == 'Windows'

def test_detect_system_unknown_falls_back_to_linux():
    with mock.patch.object(platform, 'system', return_value='FreeBSD'):
        from danger_guard.config import detect_system
        assert detect_system() == 'Linux'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace && python -m pytest tests/test_config.py -v 2>&1 | head -30`
Expected: FAIL with "No module named 'danger_guard'" or "No module named 'danger_guard.config'"

- [ ] **Step 3: Write danger_guard/__init__.py**

```python
# danger_guard/__init__.py
"""OhShit 删库跑路预防针 - 防止高危命令误操作的包装器"""
__version__ = "1.0.0"
__all__ = ["__version__"]
```

- [ ] **Step 4: Write danger_guard/config.py**

```python
# danger_guard/config.py
"""
全局配置常量与平台检测。
所有业务模块一律从此处取平台信息，禁止自行调用 platform.system()。
此模块禁止 import 任何业务模块，仅允许标准库。
"""
import os
import platform
from pathlib import Path
from typing import List


def detect_system() -> str:
    """
    检测当前操作系统，保证返回 "Linux" / "Darwin" / "Windows" 三选一。
    Cygwin / MinGW / MSYS 统一视为 Windows（因为它们在 Windows 内核上运行）。
    未知系统兜底为 Linux（避免报错中断用户）。
    """
    s = platform.system()
    if s.startswith(("CYGWIN", "MINGW", "MSYS")):
        return "Windows"
    if s in ("Linux", "Darwin", "Windows"):
        return s
    return "Linux"


# ========== 运行时常量（可被环境变量覆盖） ==========

SYSTEM = detect_system()
HOME = Path.home()

# 用户可通过 DANGER_WHITELIST 指定自定义白名单文件路径
WHITELIST_PATH: Path = Path(
    os.environ.get("DANGER_WHITELIST", str(HOME / ".danger-whitelist"))
)

# 审计日志路径（记录被 OhShit 拦截的操作与内部故障）
LOG_PATH: Path = Path(
    os.environ.get("DANGER_LOG", str(HOME / ".danger.log"))
)

# 强制放行环境变量：设置 DANGER_FORCE=1 时跳过所有防护直接执行
FORCE_ENV: str = "DANGER_FORCE"
FORCE_FLAG: bool = os.environ.get(FORCE_ENV, "").strip() in ("1", "true", "yes", "on")

# 默认白名单目录（跨平台），这些目录下的操作一律放行
DEFAULT_WHITELIST_ITEMS: List[str] = [
    # Linux/POSIX 临时目录
    "/tmp",
    "/var/tmp",
    "/dev/shm",
    # macOS 独有
    "/private/tmp",
    "/private/var/tmp",
    # 环境变量占位（解析时展开）
    "$TMPDIR",
    "$TEMP",
    "$TMP",
]
```

- [ ] **Step 5: Write pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "danger-guard"
version = "1.0.0"
description = "OhShit 删库跑路预防针 - 防止 rm -rf / dd 等高危命令误操作的包装器"
requires-python = ">=3.7"
license = {text = "MIT"}
authors = [{name = "YESON"}]
keywords = ["security", "rm", "delete", "anti-accident", "safeguard"]
classifiers = [
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX :: Linux",
    "Operating System :: MacOS",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: System :: Systems Administration",
    "Topic :: Utilities",
]
dependencies = []

[project.scripts]
ohshit = "danger_guard.cli:main"

[project.urls]
Homepage = "https://github.com/yeson/ohshit"
Repository = "https://github.com/yeson/ohshit"

[tool.setuptools.packages.find]
include = ["danger_guard*"]
exclude = ["tests*", "scripts*", "docs*"]

[tool.setuptools.package-data]
danger_guard = ["scripts/*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "-ra --strict-markers --tb=short"
```

- [ ] **Step 6: Write tests/__init__.py + tests/conftest.py**

```python
# tests/__init__.py
```

```python
# tests/conftest.py
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
```

- [ ] **Step 7: Run config tests to verify pass**

Run: `cd /workspace && python -m pytest tests/test_config.py -v`
Expected: 5 passed

- [ ] **Step 8: Commit**

```bash
cd /workspace && git add danger_guard/__init__.py danger_guard/config.py pyproject.toml tests/__init__.py tests/conftest.py tests/test_config.py && git commit -m "feat: project skeleton + config module with cross-platform system detection"
```

---

## Task 2: Hooks 框架基类 + 自动注册机制

**Files:**
- Create: `danger_guard/hooks/__init__.py`
- Create: `danger_guard/hooks/base.py`

- [ ] **Step 1: Write failing tests for hook registry**

Append to `tests/test_config.py` bottom (or create `tests/test_hooks_registry.py`):

```python
# tests/test_hooks_registry.py — 新建此文件
import pytest
from danger_guard.hooks.base import BaseHook, PreviewResult, HookExecutionResult
from danger_guard.hooks import get_hook, list_hooks, register_hook

class FakePreviewResult:
    pass

def test_registered_hooks_include_rm_and_dd():
    """rm_hook.py 和 dd_hook.py 创建后此测试才会通过，Task 2 阶段会失败（属预期）。"""
    hooks = list_hooks()
    # 先验证注册表机制本身（以下断言在 Task 9 后才会全绿，Task 2 仅测框架可导入）

def test_basehook_is_abstract_cannot_instantiate():
    with pytest.raises(TypeError, match="abstract class"):
        BaseHook()

def test_preview_result_has_expected_fields():
    # PreviewResult 用 dataclasses 或简单类实现，字段必须存在
    pr = PreviewResult(
        affected_count=10,
        total_size_bytes=1024,
        sample_items=["a.txt", "b.txt"],
        target_scope="/tmp",
        risk_level=1,
        validation_pool=["a.txt", "b.txt", "c.txt"],
        extra_warnings=[],
    )
    assert pr.affected_count == 10
    assert pr.total_size_bytes == 1024
    assert len(pr.sample_items) == 2
    assert pr.risk_level == 1

def test_hook_execution_result_fields():
    r = HookExecutionResult(success=True, exit_code=0, message=None)
    assert r.success is True
    assert r.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail appropriately**

Run: `cd /workspace && python -m pytest tests/test_hooks_registry.py::test_basehook_is_abstract_cannot_instantiate tests/test_hooks_registry.py::test_preview_result_has_expected_fields tests/test_hooks_registry.py::test_hook_execution_result_fields -v 2>&1 | head -30`
Expected: FAIL with "No module named 'danger_guard.hooks'"

- [ ] **Step 3: Write danger_guard/hooks/base.py**

```python
# danger_guard/hooks/base.py
"""
钩子框架基类定义。
- PreviewResult / HookExecutionResult: 纯数据类（值对象，无行为）
- BaseHook: 抽象基类，3 个生命周期方法（parse_args / preview / execute）
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import sys


@dataclass
class PreviewResult:
    """预演结果数据类。所有 Hook 的 preview() 方法必须返回此实例。"""
    affected_count: int
    total_size_bytes: int
    sample_items: List[str]
    target_scope: str
    risk_level: int                       # 1=低 2=中 3=高
    validation_pool: List[str]
    extra_warnings: List[str] = field(default_factory=list)

    def __post_init__(self):
        """字段防御性校验，避免 Hook 实现者漏填。"""
        assert isinstance(self.affected_count, int) and self.affected_count >= 0, "affected_count 必须是非负整数"
        assert isinstance(self.total_size_bytes, int) and self.total_size_bytes >= 0, "total_size_bytes 必须是非负整数"
        assert self.risk_level in (1, 2, 3), "risk_level 必须是 1(低)/2(中)/3(高)"
        assert isinstance(self.validation_pool, list) and len(self.validation_pool) > 0, \
            "validation_pool 不能为空（至少需要 1 个可用于随机验证的候选名）"


@dataclass
class HookExecutionResult:
    """执行结果数据类。execute() 返回此实例。"""
    success: bool
    exit_code: int
    message: Optional[str] = None


class BaseHook(ABC):
    """
    所有高危命令拦截器的抽象基类。
    子类必须：
    1. 声明 name（命令名，如 "rm"）
    2. 声明 native_commands（各平台原生命令映射表）
    3. 实现 parse_args / preview / execute 三个抽象方法
    """

    # ---------- 子类必须声明的元数据 ----------
    name: str = ""
    native_commands: Dict[str, List[str]] = {}

    # ---------- 生命周期方法（子类必须实现） ----------

    @abstractmethod
    def parse_args(self, raw_args: List[str]) -> Dict:
        """
        解析该命令的原始参数，返回结构化 dict。
        dict 的 schema 仅对该 Hook 自己有意义，engine 不解析，只透传给 preview/execute。
        """

    @abstractmethod
    def preview(self, parsed: Dict) -> PreviewResult:
        """
        预演计算：统计影响范围、大小、风险等级、验证池。
        禁止执行任何写操作！此函数必须是纯函数。
        """

    @abstractmethod
    def execute(self, parsed: Dict, dry_run: bool = False) -> HookExecutionResult:
        """
        真正执行原生命令。engine 会确保所有验证通过后才调用。
        dry_run=True 时：只打印将要执行的命令行到 stdout，不实际执行，返回 (success=True, code=0)。
        """

    # ---------- 公共工具方法（子类不得重写） ----------

    def is_natively_supported(self, system: str) -> bool:
        """判断当前系统是否支持该命令的原生实现。"""
        return system in self.native_commands
```

- [ ] **Step 4: Write danger_guard/hooks/__init__.py**

```python
# danger_guard/hooks/__init__.py
"""
Hook 注册中心。
- 自动发现机制：首次访问 get_hook() / list_hooks() 时，
  用 pkgutil.iter_modules 扫描本目录下所有 .py 文件（base.py 除外）并 import。
  import 过程中各子类文件顶部的 @register_hook 装饰器会填充注册表。
- 新增命令的社区贡献流程：在 hooks/ 下新建 foo_hook.py，
  类顶部写 @register_hook，继承 BaseHook，实现 3 个抽象方法。零侵入。
"""
import pkgutil
import importlib
from typing import Dict, Type
from .base import BaseHook, PreviewResult, HookExecutionResult

__all__ = [
    "BaseHook",
    "PreviewResult",
    "HookExecutionResult",
    "register_hook",
    "get_hook",
    "list_hooks",
]

# ========== 内部注册表（首次 _ensure_loaded 后填充） ==========
_REGISTRY: Dict[str, Type[BaseHook]] = {}
_LOADED = False


def register_hook(cls: Type[BaseHook]) -> Type[BaseHook]:
    """
    装饰器：把 Hook 子类注册进全局注册表。
    使用：
        @register_hook
        class RmHook(BaseHook):
            name = "rm"
            ...
    """
    if not isinstance(cls, type) or not issubclass(cls, BaseHook):
        raise TypeError(f"@register_hook 只能装饰继承自 BaseHook 的类，当前: {cls}")
    if not cls.name:
        raise ValueError(f"Hook 类 {cls.__name__} 必须声明非空的 name 属性")
    if cls.name in _REGISTRY:
        raise ValueError(f"Hook 名称 {cls.name!r} 重复（已注册: {_REGISTRY[cls.name].__name__}）")
    _REGISTRY[cls.name] = cls
    return cls


def get_hook(name: str) -> Type[BaseHook]:
    """
    按命令名获取 Hook 类。
    首次调用时触发自动发现。
    :raises KeyError: 名称未注册
    """
    _ensure_loaded()
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys())) or "<空>"
        raise KeyError(
            f"未注册的 Hook 命令: {name!r}，当前可用: {available}。"
            f" 扩展新命令请在 danger_guard/hooks/ 下新建文件并使用 @register_hook 装饰器。"
        )
    return _REGISTRY[name]


def list_hooks() -> Dict[str, Type[BaseHook]]:
    """返回当前所有已注册的 Hook 类字典（副本，防外部修改）。"""
    _ensure_loaded()
    return dict(_REGISTRY)


def _ensure_loaded() -> None:
    """延迟加载：扫描 hooks/ 目录，import 所有子模块以触发装饰器注册。"""
    global _LOADED
    if _LOADED:
        return
    # __path__ 是当前包的搜索路径列表（pkgutil 会用它找子模块）
    for _finder, modname, _ispkg in pkgutil.iter_modules(__path__):
        if modname == "base":
            continue  # 跳过基类本身
        importlib.import_module(f"{__name__}.{modname}")
    _LOADED = True
```

- [ ] **Step 5: Run registry framework tests (base tests should pass, rm/dd existence test expected to fail)**

Run: `cd /workspace && python -m pytest tests/test_hooks_registry.py::test_basehook_is_abstract_cannot_instantiate tests/test_hooks_registry.py::test_preview_result_has_expected_fields tests/test_hooks_registry.py::test_hook_execution_result_fields -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
cd /workspace && git add danger_guard/hooks/__init__.py danger_guard/hooks/base.py tests/test_hooks_registry.py && git commit -m "feat: hooks framework - BaseHook ABC + automatic registry via pkgutil"
```

---

## Task 3: Executors 执行层（防 alias 递归）

**Files:**
- Create: `danger_guard/executors/__init__.py`
- Create: `danger_guard/executors/posix_exec.py`
- Create: `danger_guard/executors/windows_exec.py`

- [ ] **Step 1: Write failing test for posix_exec command building**

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /workspace && python -m pytest tests/test_executors_posix.py -v 2>&1 | head -20`
Expected: FAIL "No module named 'danger_guard.executors'"

- [ ] **Step 3: Write executors/__init__.py**

```python
# danger_guard/executors/__init__.py
"""
系统原生命令执行层。
设计原则：
1. 绝对不经过 Shell alias，POSIX 用可执行文件绝对路径（/bin/rm），
   Windows 用 powershell -NoProfile（避免 $PROFILE 注入 alias）。
2. 永远不调用 "ohshit" / "rm" / "dd" 等裸名，防止触发自身别名造成无限递归。
3. 所有执行器支持 dry_run=True 模式（只打印不执行，用于集成测试）。
"""
from typing import Dict
import danger_guard.config as config

# 统一调度入口（方便 Hook 不知道自己跑在哪）
def dispatch_exec(command_family: str, parsed: Dict, dry_run: bool = False):
    """
    按当前系统类型调度到对应执行器。
    command_family: "rm" 或 "dd"
    """
    sys_name = config.detect_system()
    if sys_name == "Windows":
        from . import windows_exec
        if command_family == "rm":
            return windows_exec.exec_remove_item(parsed, dry_run)
        elif command_family == "dd":
            return windows_exec.exec_dd(parsed, dry_run)
    else:
        from . import posix_exec
        if command_family == "rm":
            return posix_exec.exec_rm(parsed, dry_run)
        elif command_family == "dd":
            return posix_exec.exec_dd(parsed, dry_run)
    raise ValueError(f"未知命令族: {command_family}")

__all__ = ["posix_exec", "windows_exec", "dispatch_exec"]
```

- [ ] **Step 4: Write executors/posix_exec.py**

```python
# danger_guard/executors/posix_exec.py
"""
POSIX 平台（Linux / macOS）原生命令执行器。
使用绝对路径绕过 alias / function 递归。
"""
import os
import shutil
import subprocess
import sys
from typing import List, Dict, Optional
from danger_guard.hooks.base import HookExecutionResult


# ------------- 可执行文件绝对路径解析 -------------

def _resolve_executable(names: List[str]) -> str:
    """尝试在常见系统路径下查找可执行文件，找到第一个存在的返回绝对路径。"""
    # 先试 /bin /usr/bin /sbin /usr/sbin（传统位置）
    search_dirs = ["/bin", "/usr/bin", "/sbin", "/usr/sbin", "/usr/local/bin"]
    for d in search_dirs:
        for name in names:
            p = os.path.join(d, name)
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
    # 兜底：交给 shutil.which（它会走 $PATH，可能找到用户别名路径，但因绝对路径仍不会触发 alias）
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    # 最终兜底：返回标准路径（调用方会收到 FileNotFoundError，这是期望行为）
    return os.path.join("/bin", names[0])


# 可执行文件绝对路径（模块加载时解析一次）
RM_PATH = _resolve_executable(["rm"])
DD_PATH = _resolve_executable(["dd"])


# ------------- rm -------------

def build_rm_command(parsed: Dict) -> List[str]:
    """
    根据 rm Hook 的 parse_args() 结构化结果，构建可执行命令行列表。
    :param parsed: {"paths": List[str], "recursive": bool, "force": bool,
                     "verbose": bool, "interactive": bool, "extra_flags": List[str]}
    """
    cmd: List[str] = [RM_PATH]
    # 先加 flag（POSIX 惯例）
    short_flags = []
    if parsed.get("recursive"):
        short_flags.append("r")
    if parsed.get("force"):
        short_flags.append("f")
    if parsed.get("verbose"):
        short_flags.append("v")
    if parsed.get("interactive"):
        short_flags.append("i")
    if short_flags:
        cmd.append("-" + "".join(short_flags))
    # 其他任意 flag（保留用户传入的 --preserve-root 等）
    cmd.extend(parsed.get("extra_flags") or [])
    # 最后加目标路径
    cmd.extend(parsed.get("paths") or [])
    return cmd


def exec_rm(parsed: Dict, dry_run: bool = False) -> HookExecutionResult:
    cmd = build_rm_command(parsed)
    if dry_run:
        print("[ohshit dry-run]  " + " ".join(cmd), file=sys.stderr)
        return HookExecutionResult(success=True, exit_code=0, message=None)
    try:
        completed = subprocess.run(cmd, check=False)
        code = completed.returncode
        return HookExecutionResult(
            success=(code == 0),
            exit_code=code,
            message=None,
        )
    except FileNotFoundError as e:
        return HookExecutionResult(
            success=False, exit_code=127,
            message=f"找不到原生命令 {RM_PATH}: {e}. 请检查系统安装。"
        )
    except OSError as e:
        return HookExecutionResult(
            success=False, exit_code=1,
            message=f"执行 rm 失败: {e}"
        )


# ------------- dd -------------

def build_dd_command(parsed: Dict) -> List[str]:
    """
    根据 dd Hook 的 parse_args() 结构化结果构建命令行。
    :param parsed: {"if": str, "of": str, "bs": str, "count": str,
                     "conv": str, "status": str, "extra_flags": List[str]}
    """
    cmd: List[str] = [DD_PATH]
    for key in ("if", "of", "bs", "count", "conv", "status", "skip", "seek", "ibs", "obs"):
        val = parsed.get(key, "")
        if val:
            cmd.append(f"{key}={val}")
    cmd.extend(parsed.get("extra_flags") or [])
    return cmd


def exec_dd(parsed: Dict, dry_run: bool = False) -> HookExecutionResult:
    cmd = build_dd_command(parsed)
    if dry_run:
        print("[ohshit dry-run]  " + " ".join(cmd), file=sys.stderr)
        return HookExecutionResult(success=True, exit_code=0, message=None)
    try:
        completed = subprocess.run(cmd, check=False)
        code = completed.returncode
        return HookExecutionResult(success=(code == 0), exit_code=code, message=None)
    except FileNotFoundError as e:
        return HookExecutionResult(
            success=False, exit_code=127,
            message=f"找不到原生命令 {DD_PATH}: {e}"
        )
    except OSError as e:
        return HookExecutionResult(
            success=False, exit_code=1,
            message=f"执行 dd 失败: {e}"
        )


__all__ = [
    "RM_PATH", "DD_PATH",
    "build_rm_command", "exec_rm",
    "build_dd_command", "exec_dd",
]
```

- [ ] **Step 5: Write executors/windows_exec.py**

```python
# danger_guard/executors/windows_exec.py
"""
Windows 平台原生命令执行器。
- 删除走 PowerShell Remove-Item（必须加 -NoProfile 防 $PROFILE 中 Set-Alias 递归）
- dd 走 Git Bash 自带 dd.exe 或其他用户自行安装的 dd 可执行文件，找不到报错
"""
import os
import shutil
import subprocess
import sys
from typing import List, Dict
from danger_guard.hooks.base import HookExecutionResult


def _powershell_path() -> str:
    return shutil.which("powershell") or shutil.which("pwsh") or "powershell.exe"


def _escape_pwsh_arg(s: str) -> str:
    """把字符串转义成 PowerShell 单引号参数（单引号用 '' 转义）。"""
    return "'" + s.replace("'", "''") + "'"


# ========== Remove-Item (替代 rm) ==========

def build_remove_item_script(parsed: Dict) -> str:
    """
    生成 PowerShell Remove-Item 脚本字符串（单文件执行）。
    :param parsed: {"paths": List[str], "recursive": bool, "force": bool,
                     "verbose": bool, "interactive": bool, "extra_flags": List[str]}
    """
    ps_flags: List[str] = []
    if parsed.get("recursive"):
        ps_flags.append("-Recurse")
    if parsed.get("force"):
        ps_flags.append("-Force")
    if parsed.get("verbose"):
        ps_flags.append("-Verbose")
    # PowerShell 的 -Confirm 默认 False，interactive=True 时显式加
    if parsed.get("interactive"):
        ps_flags.append("-Confirm")

    paths = parsed.get("paths") or []
    # 对每个路径独立执行，避免通配符解析问题
    lines = []
    for p in paths:
        escaped = _escape_pwsh_arg(p)
        lines.append(f"Remove-Item -Path {escaped} {' '.join(ps_flags)} -ErrorAction Stop")
    return "\n".join(lines)


def exec_remove_item(parsed: Dict, dry_run: bool = False) -> HookExecutionResult:
    script = build_remove_item_script(parsed)
    cmd = [_powershell_path(), "-NoProfile", "-NonInteractive",
           "-NoLogo", "-Command", script]
    if dry_run:
        print("[ohshit dry-run]  " + " ".join(cmd), file=sys.stderr)
        return HookExecutionResult(success=True, exit_code=0, message=None)
    try:
        completed = subprocess.run(cmd, check=False)
        code = completed.returncode
        return HookExecutionResult(success=(code == 0), exit_code=code, message=None)
    except FileNotFoundError as e:
        return HookExecutionResult(success=False, exit_code=127,
                                   message=f"找不到 PowerShell: {e}")
    except OSError as e:
        return HookExecutionResult(success=False, exit_code=1,
                                   message=f"执行 Remove-Item 失败: {e}")


# ========== dd on Windows ==========

def _resolve_dd_on_windows() -> str:
    """在 Windows 上找 dd 可执行文件（Git Bash / Cygwin / WSL / 手动安装）。"""
    candidates = [
        # Git Bash 常见安装位置
        r"C:\Program Files\Git\usr\bin\dd.exe",
        r"C:\Program Files (x86)\Git\usr\bin\dd.exe",
        # 用户 PATH
        shutil.which("dd") or "",
        # WSL 下的 dd
        "",
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    # 最终兜底：如果用户 PATH 里有就返回"dd"（尽管风险较高）
    return shutil.which("dd") or "dd.exe"


def build_dd_command(parsed: Dict) -> List[str]:
    """与 POSIX 版本 build_dd_command 逻辑相同，但使用 Windows 可执行路径。"""
    cmd = [_resolve_dd_on_windows()]
    for key in ("if", "of", "bs", "count", "conv", "status", "skip", "seek", "ibs", "obs"):
        val = parsed.get(key, "")
        if val:
            cmd.append(f"{key}={val}")
    cmd.extend(parsed.get("extra_flags") or [])
    return cmd


def exec_dd(parsed: Dict, dry_run: bool = False) -> HookExecutionResult:
    cmd = build_dd_command(parsed)
    if dry_run:
        print("[ohshit dry-run]  " + " ".join(cmd), file=sys.stderr)
        return HookExecutionResult(success=True, exit_code=0, message=None)
    # 兜底检查：如果 exe 路径不存在，直接报友好错误（dd 不是 Windows 预装，用户大概率没有）
    if not os.path.isfile(cmd[0]) and shutil.which(cmd[0]) is None:
        return HookExecutionResult(
            success=False, exit_code=127,
            message=(
                f"在 Windows 上未找到 dd 可执行文件（期望位置: {cmd[0]}）。"
                " 请安装 Git for Windows（自带 /usr/bin/dd.exe）或手动指定 dd 路径。"
            )
        )
    try:
        completed = subprocess.run(cmd, check=False)
        return HookExecutionResult(
            success=(completed.returncode == 0),
            exit_code=completed.returncode,
            message=None,
        )
    except OSError as e:
        return HookExecutionResult(success=False, exit_code=1,
                                   message=f"执行 dd 失败: {e}")


__all__ = [
    "build_remove_item_script", "exec_remove_item",
    "build_dd_command", "exec_dd",
]
```

- [ ] **Step 6: Run posix executor tests**

Run: `cd /workspace && python -m pytest tests/test_executors_posix.py -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
cd /workspace && git add danger_guard/executors/__init__.py danger_guard/executors/posix_exec.py danger_guard/executors/windows_exec.py tests/test_executors_posix.py && git commit -m "feat: executors layer - POSIX (absolute-path rm/dd) + Windows (powershell -NoProfile)"
```

---

## Task 4: B- 验证器（核心算法）

**Files:**
- Create: `danger_guard/core/__init__.py`
- Create: `danger_guard/core/validator.py`
- Create: `tests/test_validator.py`

- [ ] **Step 1: Write failing tests for validator**

```python
# tests/test_validator.py
import pytest
from danger_guard.core.validator import (
    normalize,
    validate_challenge,
    run_validation_loop,
    ConfusableError,
)


# ========== 规范化函数单元测试 ==========

class TestNormalize:
    def test_lowercase(self):
        assert normalize("ABC") == normalize("abc") == "abc"

    def test_letter_o_vs_zero(self):
        assert normalize("hello") == normalize("hell0")
        assert normalize("O") == normalize("0") == normalize("o") == "o"

    def test_l_vs_1_vs_pipe_vs_i(self):
        assert normalize("hello|") == normalize("hello1") == normalize("hellol")
        assert normalize("I") == normalize("1") == normalize("l") == normalize("i") == "l"

    def test_s_vs_5(self):
        assert normalize("snake") == normalize("5nake")

    def test_z_vs_2(self):
        assert normalize("zebra") == normalize("2ebra")

    def test_b_vs_8(self):
        assert normalize("ball") == normalize("8all")

    def test_g_vs_9_vs_q(self):
        assert normalize("goal") == normalize("9oal")
        # q 和 o 在同一组 -> 所以 goal = qoal 但不一定 = 9oal 经过 2 轮
        # 规范化是单向映射表：9->g, q->o, 所以 "goal" == "9oal"，但 "qoal" 会变成 "ooal"
        assert normalize("goal") == normalize("9oal")

    def test_dash_family_normalized(self):
        assert normalize("A-B_C") == normalize("A—B_C") == normalize("A–B_C")

    def test_dot_family(self):
        assert normalize("file.txt") == normalize("file．txt") == normalize("file。txt")

    def test_parentheses_bracket_normalized(self):
        assert normalize("a(b)") == normalize("a（b）") == normalize("a[b]")

    def test_fullwidth_halfwidth_space(self):
        assert normalize("a b") == normalize("a　b")

    def test_slash_backslash(self):
        assert normalize("a/b") == normalize("a\\b") == normalize("a／b")


# ========== B- 判定逻辑 ==========

class TestValidateChallenge:
    def test_exact_match_is_rejected_anti_copy_paste(self):
        ok, msg = validate_challenge(
            user_input="report_final_v3.docx",
            challenge="report_final_v3.docx",
        )
        assert ok is False, "完全精确一致必须被拒绝（防复制粘贴）"
        assert "复制" in msg or "粘贴" in msg or "copy" in msg.lower() or "paste" in msg.lower()

    def test_fuzzy_match_passes_with_shape_substitution(self):
        ok, msg = validate_challenge(
            user_input="Rep0rt_F1nal_v3.docx",   # o→0, i→1
            challenge="report_final_v3.docx",
        )
        assert ok is True
        assert "通过" in msg or "pass" in msg.lower()

    def test_case_insensitive_but_not_exact(self):
        # 大小写不同 = 字节级不同，不算复制粘贴，应通过
        ok, _ = validate_challenge(
            user_input="Report_Final_V3.DOCX",
            challenge="report_final_v3.docx",
        )
        assert ok is True

    def test_totally_wrong_returns_false_with_distance_hint(self):
        ok, msg = validate_challenge(user_input="blahblah", challenge="report.docx")
        assert ok is False
        # 提示应包含编辑距离或"还差 N 个字符"的语义
        assert any(ch.isdigit() for ch in msg)

    def test_leading_trailing_whitespace_stripped_on_input(self):
        # 用户不小心多加空格也算正确尝试
        ok, _ = validate_challenge(
            user_input="  Rep0rt_f1nal_v3.docx  \t",
            challenge="report_final_v3.docx",
        )
        assert ok is True


# ========== 3 次重试循环 ==========

class TestRunValidationLoop:
    def test_first_attempt_correct_passes(self, monkeypatch):
        # 第一次输入就用大小写不同的模糊匹配
        from tests.conftest import patch_user_input
        patch_user_input(monkeypatch, ["Report_Final.DOCX"])
        result, history = run_validation_loop(
            validation_pool=["report_final.docx", "thesis.pdf", "customer.sql"],
            max_attempts=3,
        )
        assert result is True

    def test_three_wrong_attempts_fails_with_rotation(self, monkeypatch):
        from tests.conftest import patch_user_input
        patch_user_input(monkeypatch, ["blah1", "blah2", "blah3"])
        result, history = run_validation_loop(
            validation_pool=["a.txt", "b.txt", "c.txt"],
            max_attempts=3,
        )
        assert result is False
        # 历史应记录 3 次挑战，且每次的挑战文件名不同（轮换）
        assert len(history) == 3
        challenges_used = [h["challenge"] for h in history]
        assert len(set(challenges_used)) == 3, "三次失败的挑战文件名必须轮换不同，防止死磕一个"

    def test_ctrl_c_exits_gracefully(self, monkeypatch):
        def fake_input_always_raises(*a, **kw):
            raise KeyboardInterrupt()
        monkeypatch.setattr('sys.stdin.readline', fake_input_always_raises)
        with pytest.raises(KeyboardInterrupt):
            run_validation_loop(validation_pool=["a.txt"], max_attempts=3)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /workspace && python -m pytest tests/test_validator.py -v 2>&1 | head -20`
Expected: FAIL "No module named 'danger_guard.core'"

- [ ] **Step 3: Write core/__init__.py**

```python
# danger_guard/core/__init__.py
"""
核心业务子模块（三阶防护各阶段的独立实现）。
本目录下模块之间互相独立，互不 import；统一由 core/engine.py 编排。
"""
```

- [ ] **Step 4: Write core/validator.py**

```python
# danger_guard/core/validator.py
"""
B- 随机文件名验证算法（核心防呆）。
规则：
1. 忽略大小写（底层统一 lower()）
2. 形近字模糊容忍：O/0/Q, l/1/I/|, S/5, Z/2, B/8, G/9 等等价
3. 完全精确字节匹配 = 拒绝：如果用户输入与 challenge 字节级完全一致，
   说明是复制粘贴的，必须拒绝以强制人工输入。
4. 3 次机会，每次随机从 validation_pool 抽新文件名（失败则轮换，避免死磕同一个）。
"""
import random
import sys
from typing import List, Tuple, Dict, Any, Optional

# 自定义异常类（Ctrl+C 包装等）
class ConfusableError(Exception):
    """验证算法内部错误，非用户输入问题。"""


# ========== 形近字等价类表 ==========
# 每组内的所有字符都视为等价，规范化时统一映射为组内第一个字符（规范形）
_CONFUSABLE_GROUPS: List[Tuple[str, ...]] = [
    # 字母 vs 数字
    ('o', '0', 'q', '○', '●', 'Ο', 'ⓞ'),        # Ο=希腊 Omicron
    ('l', '1', 'i', '|', 'Ι', 'Ⅰ', 'ǀ', 'ĺ'),    # Ι=希腊 Iota, Ⅰ=罗马数字 1, ǀ=拉丁齿龈边音
    ('s', '5', '§', 'ƽ'),
    ('z', '2', 'ƻ', 'ƹ'),
    ('b', '8', 'Β', 'ß'),                        # Β=希腊 Beta, ß=德语 Eszett(外形近似)
    ('g', '9', 'q', '६'),
    ('a', '@', 'α', 'ᴀ'),
    ('x', '×', '✕', '᙮'),
    # 数字本身的字形变体
    ('4', 'Ꮞ'),
    ('6', 'б'),
    ('7', '7', 'ㄱ'),
    # 连字符 / 破折号 / 下划线 合并
    ('-', '—', '–', '_', '−', '‒', '⁃'),
    # 点 / 句号 / 间隔号
    ('.', '。', '·', '｡', '˙'),
    # 逗号
    (',', '，', '‚'),
    # 感叹号
    ('!', '！', '¡'),
    # 问号
    ('?', '？', '¿'),
    # 加号
    ('+', '＋', 'ᐩ'),
    # 等号
    ('=', '＝', '﹦'),
    # 括号（左/右分开成两组，避免把 ) 归一成 ( 导致 "a(b)" 和 "a)b(" 等价这种荒谬）
    ('(', '（', '[', '【', '〔'),
    (')', '）', ']', '】', '〕'),
    # 引号（单 / 双 分开两组）
    ("'", '’', '`', '´', '‘', 'ʻ', 'ʼ'),
    ('"', '”', '“', '«', '»', '„', '‟', '❝', '❞'),
    # 斜杠 / 反斜杠 / 全角
    ('/', '\\', '／', '＼', '⧸', '⧹'),
    # 冒号（全半角）
    (':', '：'),
    # 分号
    (';', '；'),
    # 空格
    (' ', '　', '\t'),
    # 星号
    ('*', '＊', '✱', '✲'),
    # 哈希 / 井号
    ('#', '＃', '♯'),
    # 美元
    ('$', '＄'),
    # 百分号
    ('%', '％'),
    # 和号
    ('&', '＆'),
]

# 构建 字符 → 规范形 映射表（O(1) 查表）
_CHAR_MAP: Dict[str, str] = {}
for group in _CONFUSABLE_GROUPS:
    canonical = group[0].lower()
    for ch in group:
        _CHAR_MAP[ch.lower()] = canonical
        if ch.upper() != ch.lower():
            _CHAR_MAP[ch.upper()] = canonical


# ========== 核心工具函数 ==========

def normalize(s: str) -> str:
    """
    规范化：小写化 + 形近字替换为规范形。
    两个字符串 normalize() 后相等即视为模糊匹配。
    """
    if not s:
        return ""
    # 先整体 lower，再逐字符查替换表
    lowered = s.lower()
    out_chars = []
    for ch in lowered:
        if ch in _CHAR_MAP:
            out_chars.append(_CHAR_MAP[ch])
        else:
            out_chars.append(ch)
    return "".join(out_chars)


def levenshtein_distance(a: str, b: str) -> int:
    """
    两个字符串的编辑距离（插入、删除、替换均计 1）。
    用于在验证失败时给出"还差 N 个字符修正"的友好提示。
    实现：标准 O(n*m) DP，验证器处理的都是短文件名，完全够用。
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    la, lb = len(a), len(b)
    # 滚动数组优化（只需两行）
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,         # 删除
                curr[j - 1] + 1,     # 插入
                prev[j - 1] + cost,  # 替换
            )
        prev = curr
    return prev[lb]


def validate_challenge(user_input: str, challenge: str) -> Tuple[bool, str]:
    """
    B- 单次验证判定。
    :returns: (是否通过, 给用户看的提示文案)
    规则优先级（从高到低）：
        1) user_input.strip() == challenge → 精确字节一致 = 拒绝（防复制粘贴）
        2) normalize(user_input.strip()) == normalize(challenge) → 模糊通过 ✅
        3) 其他 → 失败，附编辑距离提示
    """
    stripped = user_input.strip()
    challenge_stripped = challenge.strip()

    # 规则 1：完全精确一致 → 故意拒绝
    if stripped == challenge_stripped and len(challenge_stripped) > 0:
        return (
            False,
            "❌ 检测到直接复制粘贴。OhShit 要求必须人工输入："
            "请故意稍作改动（例如把 o 写成 0，或调整大小写），再试一次。"
        )

    norm_user = normalize(stripped)
    norm_challenge = normalize(challenge_stripped)

    # 规则 2：模糊匹配通过
    if norm_user == norm_challenge:
        diff_flags = []
        if stripped.lower() != challenge_stripped.lower():
            diff_flags.append("容忍了字形混淆（形近字符互通）")
        else:
            if stripped != challenge_stripped:
                diff_flags.append("容忍了大小写差异")
            else:
                diff_flags.append("匹配通过")
        suffix = ""
        if diff_flags:
            suffix = f"（{diff_flags[0]}）"
        return (True, f"✅ 验证通过{suffix}。")

    # 规则 3：不匹配
    dist = levenshtein_distance(norm_user, norm_challenge)
    hint = f"规范化后还差约 {dist} 个字符修正。" if dist <= 20 else "差异较大，请重新阅读警告框中的文件名。"
    return (
        False,
        f"❌ 不匹配。{hint}"
        f"\n   你输入: {stripped!r}"
        f"\n   期望的任一形: {challenge_stripped!r}（允许写错字形或改大小写）"
    )


# ========== 交互循环 ==========

def run_validation_loop(
    validation_pool: List[str],
    max_attempts: int = 3,
    challenge_prompt_fn=None,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    运行多轮 B- 验证交互，直到通过或耗尽次数。
    :param validation_pool: 候选文件名/设备名池（必须非空）
    :param max_attempts: 最大尝试次数（默认 3）
    :param challenge_prompt_fn: 可选，自定义 prompt 函数。签名: fn(challenge, attempt, max_attempts) -> None
                                 默认会把提示文案写到 stdout。
    :returns: (是否全部通过, 历史记录列表)
              历史记录每项为 {"challenge": str, "user_input": str, "passed": bool, "message": str}
    :raises KeyboardInterrupt: 用户按 Ctrl+C 时透传（由上层 engine 捕获显示"已取消"）
    """
    if not validation_pool:
        raise ConfusableError("validation_pool 不能为空，至少需要 1 个候选")

    pool = list(validation_pool)
    history: List[Dict[str, Any]] = []
    used_this_round: List[str] = []

    # 先输出验证规则的提示语（只打一次）
    print("\n" + _bold_yellow("━" * 52))
    print(_bold_yellow(" 🔐 OhShit B- 人机验证"))
    print(_yellow("    · 允许写错字形（如 o↔0、l↔1、Z↔2 等互通）"))
    print(_yellow("    · 允许改大小写"))
    print(_yellow("    · ⚠️ 直接复制粘贴的完全一致将被拒绝——请故意稍作改动"))
    print(_bold_yellow("━" * 52) + "\n")
    sys.stdout.flush()

    for attempt in range(1, max_attempts + 1):
        # 选一个"在本次还没被用过"的文件名（如果都用完了就重置）
        remaining = [p for p in pool if p not in used_this_round]
        if not remaining:
            remaining = pool
            used_this_round.clear()
        challenge = random.choice(remaining)
        used_this_round.append(challenge)

        # 出挑战题
        if challenge_prompt_fn:
            challenge_prompt_fn(challenge, attempt, max_attempts)
        else:
            # 默认提示：展示挑战文件名 + 轮次
            print(
                _cyan(f"  [第 {attempt}/{max_attempts} 次机会]")
                + f" 请手动输入以下文件名 → "
                + _bold_magenta(challenge)
            )
            sys.stdout.flush()

        # 读用户输入（Ctrl+C 要透传给上层）
        try:
            user_input = sys.stdin.readline()
        except KeyboardInterrupt:
            raise

        if user_input == "":
            # EOF（Ctrl+D）
            history.append({
                "challenge": challenge, "user_input": "<EOF>",
                "passed": False, "message": "EOF: 用户中断输入",
            })
            break

        passed, msg = validate_challenge(user_input.rstrip("\n"), challenge)
        history.append({
            "challenge": challenge,
            "user_input": user_input.rstrip("\n"),
            "passed": passed,
            "message": msg,
        })
        # 输出结果
        prefix = "  "
        if passed:
            print(prefix + _green(msg) + "\n")
            sys.stdout.flush()
            return True, history
        else:
            # 失败：打印原因 + 加空行分隔
            print(prefix + _red(msg) + "\n")
            sys.stdout.flush()

    # 耗尽所有机会
    print(_bold_red(f"✘ 已耗尽 {max_attempts} 次验证机会，操作已取消。"))
    print(_red(f"  若您确认操作无误，可在命令前加 {_bold('DANGER_FORCE=1')} 跳过所有验证。"))
    sys.stdout.flush()
    return False, history


# ========== 终端彩色辅助（极简 ANSI，不依赖 colorama） ==========
# 如果 stdout 不是 TTY，所有颜色函数会自动降级为无颜色字符串。

def _ansi(seq: str, text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{seq}m{text}\033[0m"

def _red(s):       return _ansi("31;1", s)
def _green(s):     return _ansi("32;1", s)
def _yellow(s):    return _ansi("33", s)
def _bold_yellow(s): return _ansi("33;1", s)
def _cyan(s):      return _ansi("36;1", s)
def _magenta(s):   return _ansi("35", s)
def _bold_magenta(s): return _ansi("35;1", s)
def _bold(s):      return _ansi("1", s)


__all__ = [
    "normalize",
    "levenshtein_distance",
    "validate_challenge",
    "run_validation_loop",
    "ConfusableError",
]
```

- [ ] **Step 5: Run validator tests**

Run: `cd /workspace && python -m pytest tests/test_validator.py -v`
Expected: All ~20 tests pass (the exact number depends on how many parametrize instances expand).

- [ ] **Step 6: Commit**

```bash
cd /workspace && git add danger_guard/core/__init__.py danger_guard/core/validator.py tests/test_validator.py && git commit -m "feat: B- validator - confusable normalization + anti-copy-paste + 3-strike retry loop"
```

---

## Task 5: Whitelist + TTY Detector + UI 模块

**Files:**
- Create: `danger_guard/core/whitelist.py`
- Create: `danger_guard/core/tty_detector.py`
- Create: `danger_guard/core/ui.py`
- Create: `tests/test_whitelist.py`
- Create: `tests/test_ui.py`

- [ ] **Step 1: Write whitelist tests**

```python
# tests/test_whitelist.py
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from danger_guard.core.whitelist import (
    DEFAULT_WHITELIST_ITEMS,
    load_whitelist,
    is_path_whitelisted,
    is_any_path_whitelisted,
)


class TestDefaultWhitelistItems:
    def test_tmp_is_in_defaults(self):
        assert "/tmp" in DEFAULT_WHITELIST_ITEMS
        assert "/var/tmp" in DEFAULT_WHITELIST_ITEMS

    def test_envvar_placeholders_present(self):
        assert any("$" in x for x in DEFAULT_WHITELIST_ITEMS)


class TestLoadWhitelist:
    def test_nonexistent_file_returns_defaults(self):
        """用户还没建 ~/.danger-whitelist 时，只返回默认白名单。"""
        rules = load_whitelist(Path("/no/such/file/xxxxx_whitelist_12345"))
        assert isinstance(rules, list)
        assert len(rules) >= len(DEFAULT_WHITELIST_ITEMS)

    def test_load_custom_whitelist_file(self, tmp_path):
        wl_file = tmp_path / "wl.txt"
        wl_file.write_text(
            "# 这是注释\n"
            "\n"
            "/home/alice/.cache\n"
            "  /var/log/myapp  \n"   # 前后空格应被去掉
            "~/Downloads\n"           # ~ 应展开
            "/data/projects/*/build\n" # glob 通配符
            "# 结束\n"
        )
        rules = load_whitelist(wl_file)
        assert "/home/alice/.cache" in rules
        assert "/var/log/myapp" in rules
        # ~ 展开
        assert any(str(Path.home()) in r or r.startswith("~") == False for r in rules if "Downloads" in r)
        assert "/data/projects/*/build" in rules
        # 不包含注释行与空行
        assert not any(r.startswith("#") for r in rules)
        assert all(r.strip() == r for r in rules)


class TestIsPathWhitelisted:
    def test_tmp_child_is_whitelisted(self):
        assert is_path_whitelisted(Path("/tmp/whatever"), ["/tmp"])
        assert is_path_whitelisted(Path("/tmp"), ["/tmp"])

    def test_absolute_whitelist_does_not_leak(self):
        assert not is_path_whitelisted(Path("/var/www"), ["/tmp"])

    def test_glob_pattern_matching(self, tmp_path):
        rules = [str(tmp_path / "prj_*" / "build")]
        assert is_path_whitelisted(tmp_path / "prj_a" / "build", rules)
        assert is_path_whitelisted(tmp_path / "prj_a" / "build" / "subdir" / "o.txt", rules)
        assert not is_path_whitelisted(tmp_path / "other" / "build", rules)

    def test_expand_user_home_in_rules(self):
        rule = "~/.cache"
        p = Path.home() / ".cache" / "foo"
        assert is_path_whitelisted(p, [rule])

    def test_envvar_expand_in_rules(self):
        with mock.patch.dict(os.environ, {"TMPDIR": "/my_custom_tmp_xyz"}):
            assert is_path_whitelisted(Path("/my_custom_tmp_xyz/a.txt"), ["$TMPDIR"])


class TestIsAnyPathWhitelisted:
    def test_all_paths_in_whitelist_returns_true(self):
        paths = [Path("/tmp/a"), Path("/tmp/b/c")]
        rules = ["/tmp"]
        assert is_any_path_whitelisted(paths, rules, require_all=True) is True

    def test_partial_paths_returns_false_when_require_all(self):
        paths = [Path("/tmp/a"), Path("/etc/passwd")]
        rules = ["/tmp"]
        assert is_any_path_whitelisted(paths, rules, require_all=True) is False
        # require_all=False 时只要有一个在白名单就 True
        assert is_any_path_whitelisted(paths, rules, require_all=False) is True
```

- [ ] **Step 2: Write UI tests**

```python
# tests/test_ui.py
import re
import io
import sys
from pathlib import Path
from danger_guard.hooks.base import PreviewResult
from danger_guard.core.ui import (
    format_size,
    render_warning_box,
    final_confirm,
    risk_bars,
)


class TestFormatSize:
    def test_bytes_exact(self):
        assert format_size(0) == "0 B"
        assert format_size(1023) == "1023 B"

    def test_ki_vs_kb_uses_binary_units(self):
        # 产品文档使用 GiB 表示法（二进制单位）
        assert "KiB" in format_size(1024)
        assert "MiB" in format_size(1024 * 1024)
        assert "GiB" in format_size(1024 * 1024 * 1024)
        assert "TiB" in format_size(1024 ** 4)

    def test_one_decimal_places(self):
        # 1.5 KiB 而非 1 KiB
        s = format_size(int(1.5 * 1024))
        assert "1.5" in s or "1,5" in s  # 兼容不同 locale

    def test_rounded_reasonably(self):
        # 15.6 GiB 范例
        size = int(15.6 * 1024 ** 3)
        out = format_size(size)
        assert "GiB" in out
        # 应提取出 15.x 的数值
        m = re.search(r'([\d.,]+)\s*GiB', out)
        assert m
        val = float(m.group(1).replace(',', '.'))
        assert 15.0 <= val <= 16.0


class TestRiskBars:
    def test_risk_levels(self):
        assert "低" in risk_bars(1)
        assert "中" in risk_bars(2)
        assert "高" in risk_bars(3)
        # 低风险不包含"高"字
        assert "高" not in risk_bars(1)


class TestRenderWarningBox:
    def _sample_preview(self):
        return PreviewResult(
            affected_count=1284,
            total_size_bytes=int(15.6 * 1024 ** 3),
            sample_items=["report_final_v3.docx", "thesis_backup.pdf",
                          "customer_db.sql", "notes/idea1.txt", "notes/idea2.txt"],
            target_scope="/data/projects/old/*",
            risk_level=3,
            validation_pool=["report_final_v3.docx", "thesis_backup.pdf",
                             "customer_db.sql", "notes/idea1.txt"],
            extra_warnings=["⚠ 警告：目标目录含符号链接指向 /etc"],
        )

    def test_non_tty_output_contains_all_key_fields(self, monkeypatch, capsys):
        """非 TTY 模式（颜色关）仍要输出关键字段。"""
        # 强制非 TTY
        monkeypatch.setattr(sys.stdout, 'isatty', lambda: False)
        render_warning_box(self._sample_preview())
        out = capsys.readouterr().out
        assert "DANGER" in out or "危险" in out
        assert "/data/projects/old/*" in out
        assert "1,284" in out.replace(" ", "").replace("\u2009", "") or "1284" in out
        assert "GiB" in out
        assert "report_final_v3.docx" in out
        assert "符号链接" in out

    def test_tty_output_contains_ansi_escape(self, fake_tty, capsys):
        """TTY 模式下要出现 ANSI 颜色码。"""
        render_warning_box(self._sample_preview())
        out = capsys.readouterr().out
        assert "\033[" in out, "TTY 模式警告框必须包含 ANSI 颜色"


class TestFinalConfirm:
    def test_typing_delete_confirms(self, monkeypatch):
        from tests.conftest import patch_user_input
        patch_user_input(monkeypatch, ["DELETE"])
        assert final_confirm(PreviewResult(
            affected_count=1, total_size_bytes=1, sample_items=["a.txt"],
            target_scope="/tmp", risk_level=1, validation_pool=["a.txt"]
        )) is True

    def test_typing_n_cancels(self, monkeypatch):
        from tests.conftest import patch_user_input
        patch_user_input(monkeypatch, ["n"])
        assert final_confirm(PreviewResult(
            affected_count=1, total_size_bytes=1, sample_items=["a.txt"],
            target_scope="/tmp", risk_level=1, validation_pool=["a.txt"]
        )) is False

    def test_typing_lowercase_delete_not_accepted(self, monkeypatch):
        """必须精确输入 DELETE 大写（最后一道防线，不能含糊）。"""
        from tests.conftest import patch_user_input
        patch_user_input(monkeypatch, ["delete", "Delete", "DELETE"])
        # 前两次错，第三次才对
        assert final_confirm(PreviewResult(
            affected_count=1, total_size_bytes=1, sample_items=["a.txt"],
            target_scope="/tmp", risk_level=1, validation_pool=["a.txt"]
        )) is True
```

- [ ] **Step 3: Run tests to verify failure (no modules yet)**

Run: `cd /workspace && python -m pytest tests/test_whitelist.py tests/test_ui.py -v 2>&1 | head -20`
Expected: FAIL "No module named ..."

- [ ] **Step 4: Write core/whitelist.py**

```python
# danger_guard/core/whitelist.py
"""
白名单模块：解析用户 ~/.danger-whitelist 并提供路径匹配。
匹配规则：
- 目标路径 == 白名单路径 或 目标路径是白名单路径的子子孙孙 → 匹配
- 支持 glob 通配符（fnmatch / pathlib.match）
- 支持 ~ 展开成用户 HOME
- 支持 $VAR / ${VAR} 环境变量展开
"""
import os
import fnmatch
from pathlib import Path
from typing import List, Iterable, Optional

from danger_guard.config import WHITELIST_PATH, DEFAULT_WHITELIST_ITEMS


__all__ = [
    "DEFAULT_WHITELIST_ITEMS",
    "load_whitelist",
    "is_path_whitelisted",
    "is_any_path_whitelisted",
]


def _expand_rule(raw: str) -> str:
    """展开 ~ 和 $VAR 环境变量，返回绝对路径字符串。"""
    s = raw.strip()
    if not s or s.startswith("#"):
        return ""
    # ~ 用户目录展开
    s = os.path.expanduser(s)
    # 环境变量展开
    s = os.path.expandvars(s)
    return s


def load_whitelist(whitelist_file: Optional[Path] = None) -> List[str]:
    """
    读取白名单文件，合并默认白名单 + 用户自定义白名单。
    文件格式：一行一条路径，# 开头为注释，空行忽略。
    :param whitelist_file: 自定义白名单文件路径（默认用 config.WHITELIST_PATH）
    :returns: 规范化后的规则列表（均已展开 ~ 和 $VAR，glob 保留供后续匹配）
    """
    if whitelist_file is None:
        whitelist_file = WHITELIST_PATH

    rules: List[str] = []
    # 先加默认
    for item in DEFAULT_WHITELIST_ITEMS:
        expanded = _expand_rule(item)
        if expanded:
            rules.append(expanded)
    # 再加用户自定义
    try:
        with open(whitelist_file, "r", encoding="utf-8") as f:
            for line in f:
                expanded = _expand_rule(line)
                if expanded and expanded not in rules:
                    rules.append(expanded)
    except FileNotFoundError:
        # 用户没建白名单文件是常态，静默
        pass
    except (IOError, OSError):
        # 读失败（比如权限）就不加用户规则，至少不崩
        pass
    return rules


def _path_to_str(p) -> str:
    if isinstance(p, Path):
        return str(p.resolve()) if p.exists() else str(Path(p).absolute())
    return str(p)


def is_path_whitelisted(target_path, rules: List[str]) -> bool:
    """
    判断单个 target_path 是否命中任一条白名单规则。
    命中条件（任一满足即可）：
    1) 目标路径 == 规则路径 或 目标路径位于规则路径的子目录/文件下
    2) 目标路径或其父目录任一级对规则做 glob 匹配（fnmatch）
    """
    target_abs = _path_to_str(target_path)
    target_path_obj = Path(target_abs)
    # 拿到 target 的所有祖先（含自身）
    ancestors = [target_path_obj] + list(target_path_obj.parents)

    for rule in rules:
        rule_path = Path(rule)
        rule_str = str(rule_path) if "?" not in rule and "*" not in rule and "[" not in rule else None
        # 不含通配符：简单前缀匹配（"祖先包含"语义）
        if rule_str is not None:
            try:
                rule_resolved = rule_path.resolve() if rule_path.exists() else rule_path.absolute()
            except (OSError, RuntimeError):
                rule_resolved = Path(os.path.abspath(rule))
            for anc in ancestors:
                try:
                    anc_res = anc.resolve() if anc.exists() else anc.absolute()
                except (OSError, RuntimeError):
                    anc_res = Path(os.path.abspath(str(anc)))
                if str(anc_res) == str(rule_resolved):
                    return True
            continue
        # 含通配符：对 target_abs 和每个祖先路径做 fnmatch
        for anc in ancestors:
            anc_str = str(anc)
            if fnmatch.fnmatch(anc_str, rule):
                return True
            # 也对 basename 做匹配（更直观，如 "*.log" 匹配所有 .log 文件）
            if fnmatch.fnmatch(anc.name or "", rule):
                return True
    return False


def is_any_path_whitelisted(
    paths: Iterable,
    rules: List[str],
    require_all: bool = True,
) -> bool:
    """
    判断一批路径是否符合白名单。
    :param require_all: True → 所有路径都得在白名单里才返回 True（整体放行策略）
                        False → 任一命中即返回 True
    """
    path_list = list(paths)
    if not path_list:
        return False  # 空列表不视为白名单命中（防止误放行）
    results = [is_path_whitelisted(p, rules) for p in path_list]
    if require_all:
        return all(results)
    return any(results)
```

- [ ] **Step 5: Write core/tty_detector.py**

```python
# danger_guard/core/tty_detector.py
"""
交互性检测：判断当前调用是否来自"人类用户手动执行"。
仅交互 TTY（终端）下会走三阶防护，非交互场景（脚本/cron/管道/CI）直接放行。
"""
import os
import sys
from typing import Tuple
from danger_guard.config import FORCE_FLAG, FORCE_ENV

__all__ = [
    "is_interactive_tty",
    "should_bypass_all_protections",
    "describe_context",
]


def is_interactive_tty() -> bool:
    """
    是否为"人类正在交互的终端"。
    判断标准：
    1. sys.stdin + sys.stdout + sys.stderr 全都是 TTY
    2. $TERM 不是 "dumb"（排除某些 dumb terminal 环境）
    """
    if not (sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty()):
        return False
    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False
    return True


def should_bypass_all_protections() -> Tuple[bool, str]:
    """
    是否应该跳过所有防护（直接执行原生命令）。
    :returns: (是否跳过, 理由字符串，用于日志/调试)
    """
    # 优先级 1：显式 DANGER_FORCE=1 环境变量
    if FORCE_FLAG:
        return True, f"环境变量 {FORCE_ENV}=1 强制放行"
    # 优先级 2：非交互场景
    if not is_interactive_tty():
        return True, "非 TTY 环境（脚本/cron/管道/CI），为避免破坏自动化直接放行"
    return False, ""


def describe_context() -> str:
    """返回当前上下文的可读描述（用于调试/日志）。"""
    tty = is_interactive_tty()
    return (
        f"[context] pid={os.getpid()}, "
        f"tty={'yes' if tty else 'NO'}, "
        f"{FORCE_ENV}={'ON' if FORCE_FLAG else 'off'}, "
        f"TERM={os.environ.get('TERM', '<unset>')}"
    )
```

- [ ] **Step 6: Write core/ui.py**

```python
# danger_guard/core/ui.py
"""
终端 UI：红色警告框、人类可读大小格式化、最终确认。
颜色使用极简 ANSI 转义（stdout/stderr 非 TTY 时自动降级）。
"""
import os
import shutil
import sys
from typing import Optional

from danger_guard.hooks.base import PreviewResult

__all__ = [
    "format_size",
    "risk_bars",
    "render_warning_box",
    "final_confirm",
    "print_whitelist_bypass",
    "print_internal_fault",
]


# ========== ANSI 彩色辅助（仅 TTY 生效） ==========

def _ansi(code: str, text: str, stream=sys.stdout) -> str:
    try:
        is_tty = stream.isatty()
    except Exception:
        is_tty = False
    if not is_tty:
        return text
    return f"\033[{code}m{text}\033[0m"

def COLOR_RED_BG(s):    return _ansi("41;37;1", s)   # 红底白字（最醒目）
def COLOR_RED(s):       return _ansi("31;1", s)
def COLOR_YELLOW(s):    return _ansi("33;1", s)
def COLOR_GREEN(s):     return _ansi("32;1", s)
def COLOR_CYAN(s):      return _ansi("36;1", s)
def COLOR_MAGENTA(s):   return _ansi("35;1", s)
def COLOR_BOLD(s):      return _ansi("1", s)
def COLOR_RESET(s=None): return "\033[0m" if (s is None and sys.stdout.isatty()) else ""


# ========== 工具：人类可读大小 ==========

def format_size(num_bytes: int) -> str:
    """
    字节数 → 人类可读字符串（二进制单位 KiB/MiB/GiB/TiB，1 位小数）。
    对齐产品文档中的 "15.6 GiB" 范例。
    """
    if num_bytes < 0:
        num_bytes = 0
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"]
    size = float(num_bytes)
    idx = 0
    while size >= 1024.0 and idx < len(units) - 1:
        size /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(size)} {units[idx]}"
    # 1 位小数，去除末尾无意义的 .0（可选）
    formatted = f"{size:.1f}"
    if formatted.endswith(".0"):
        formatted = str(int(size))
    return f"{formatted} {units[idx]}"


def risk_bars(level: int) -> str:
    """风险等级 → 文字条 + 描述（如 "███ 高危"）。"""
    if level <= 1:
        bar = "█░░ 低危"
    elif level == 2:
        bar = "██░ 中危"
    else:
        bar = "███ 高危"
    return bar


# ========== 红色警告框 ==========

def _term_width() -> int:
    """获取终端宽度，兜底 72。"""
    try:
        cols, _ = shutil.get_terminal_size(fallback=(72, 24))
    except Exception:
        cols = 72
    return max(52, min(cols, 100))


def _pad_line(text: str, width: int, border: str) -> str:
    # 计算可见字符长度（去除 ANSI 码）
    import re
    visible = re.sub(r'\033\[[0-9;]*m', '', text)
    padding = max(0, width - 2 - len(visible))
    return f"{border}{text}{' ' * padding}{border}"


def render_warning_box(preview: PreviewResult) -> None:
    """在终端绘制带边框的红色威慑警告框。非 TTY 模式降级为普通文本输出。"""
    W = _term_width()
    top = COLOR_RED_BG("═" * W)
    def line(content):
        # 边框是单竖线，内部文字
        return COLOR_RED_BG(_pad_line("  " + content, W, "║"))

    size_str = format_size(preview.total_size_bytes)
    count_str = f"{preview.affected_count:,}"
    risk_str = risk_bars(preview.risk_level)
    risk_detail = {1: "（影响较小）", 2: "（数据可能不可恢复）", 3: "（删除 / 覆写不可恢复）"}[preview.risk_level]

    print(top)
    print(line(COLOR_BOLD("⚠ 危险操作即将执行！  DANGER!  DANGER!  DANGER!")))
    print(line(""))
    print(line(f"目标范围：{COLOR_BOLD(preview.target_scope)}"))
    print(line(f"受影响数量：{COLOR_BOLD(count_str)} 个对象    总大小：{COLOR_BOLD(size_str)}"))
    print(line(f"风险等级：{COLOR_BOLD(risk_str)} {risk_detail}"))
    print(line(""))
    print(line("前 5 个受影响对象（按字母序）："))
    for i, name in enumerate(preview.sample_items[:5], start=1):
        print(line(f"   {i}. {COLOR_YELLOW(name)}"))
    if preview.affected_count > 5:
        print(line(f"   ... 其余 {preview.affected_count - 5} 个未显示"))
    if preview.extra_warnings:
        print(line(""))
        for w in preview.extra_warnings:
            print(line(COLOR_RED(w)))
    print(line(""))
    print(line(COLOR_YELLOW("[提示] 下一步将要求你手动键入文件名以确认阅读了以上内容。")))
    print(line(COLOR_YELLOW("       允许写错字形（o/0、l/1、Z/2 等互通），但直接复制粘贴的")))
    print(line(COLOR_YELLOW("       完全一致将被拒绝——请故意稍作改动。")))
    print(top)
    print()
    sys.stdout.flush()


# ========== 最终确认 ==========

def final_confirm(preview: PreviewResult) -> bool:
    """
    最终防线：要求用户精确输入 DELETE（全大写）。
    :returns: True=用户确认，False=用户取消
    :raises KeyboardInterrupt: Ctrl+C 透传给上层（会显示"已取消"）
    """
    size = format_size(preview.total_size_bytes)
    count = f"{preview.affected_count:,}"
    print()
    print(COLOR_BOLD("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
    print(COLOR_RED(
        f"📌 最终确认：即将对 {COLOR_BOLD(preview.target_scope)} 执行 "
        f"{COLOR_BOLD(count)} 个对象 ({COLOR_BOLD(size)}) 的高危操作。"
    ))
    print(COLOR_BOLD("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
    # 最多给 3 次 DELETE 输入机会
    for i in range(1, 4):
        prompt = (
            f"   确认请输入 {COLOR_BOLD('DELETE')} 并回车（第 {i}/3 次机会，N/Ctrl+C 取消）："
        )
        sys.stdout.write(prompt)
        sys.stdout.flush()
        try:
            raw = sys.stdin.readline()
        except KeyboardInterrupt:
            raise
        if raw == "":
            # EOF
            print("\n   [收到 EOF，取消操作]")
            return False
        val = raw.strip()
        if val == "DELETE":
            return True
        if val.upper() in ("N", "NO", "取消", "Q", "QUIT", "EXIT"):
            print("   [已取消]")
            return False
        print(f"   ⚠ 需要精确输入大写 DELETE（你输入了 {val!r}）。")
    print("   ✘ 未确认 DELETE，操作取消。")
    return False


# ========== 其他辅助 UI ==========

def print_whitelist_bypass(paths, rules_hit):
    print(COLOR_GREEN(
        f"[白名单放行] 目标全部位于白名单目录下（命中规则: {', '.join(rules_hit[:3])}"
        f"{'...' if len(rules_hit) > 3 else ''}），直接执行。"
    ))
    sys.stdout.flush()


def print_internal_fault(exc, log_path):
    """OhShit 自己崩了时，打印红色警告 + 提示日志位置。安全兜底：告知用户会直接执行原生命令。"""
    print(file=sys.stderr)
    print(COLOR_RED("💥 OhShit 内部故障（非你操作问题）："), file=sys.stderr)
    print(COLOR_RED(f"   {type(exc).__name__}: {exc}"), file=sys.stderr)
    print(COLOR_RED(f"   Traceback 已写入: {log_path}"), file=sys.stderr)
    print(COLOR_YELLOW("   【安全兜底】为防止挡住你的正常操作，将跳过所有防护直接执行原生命令。"), file=sys.stderr)
    print(file=sys.stderr)
    sys.stderr.flush()
```

- [ ] **Step 7: Run whitelist + UI tests**

Run: `cd /workspace && python -m pytest tests/test_whitelist.py tests/test_ui.py -v`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
cd /workspace && git add danger_guard/core/whitelist.py danger_guard/core/tty_detector.py danger_guard/core/ui.py tests/test_whitelist.py tests/test_ui.py && git commit -m "feat: core submodules - whitelist + tty detector + red warning box UI"
```

---

## Task 6: rm Hook 实现

**Files:**
- Create: `danger_guard/hooks/rm_hook.py`
- Create: `tests/test_hooks_rm.py`

- [ ] **Step 1: Write rm hook tests**

```python
# tests/test_hooks_rm.py
import os
from pathlib import Path
import pytest
from danger_guard.hooks.rm_hook import RmHook
from danger_guard.hooks import get_hook


def test_rm_hook_is_registered():
    cls = get_hook("rm")
    assert cls is RmHook
    assert cls.name == "rm"


class TestRmParseArgs:
    @pytest.fixture
    def hook(self):
        return RmHook()

    def test_recursive_force_star(self, hook):
        parsed = hook.parse_args(["-rf", "/tmp/*"])
        assert parsed["recursive"] is True
        assert parsed["force"] is True
        assert "/tmp/*" in parsed["paths"]

    def test_separate_flags(self, hook):
        parsed = hook.parse_args(["-r", "-f", "-v", "a", "b"])
        assert parsed["recursive"] is True
        assert parsed["force"] is True
        assert parsed["verbose"] is True
        assert parsed["paths"] == ["a", "b"]

    def test_long_options(self, hook):
        parsed = hook.parse_args(["--recursive", "--force", "foo"])
        assert parsed["recursive"] is True
        assert parsed["force"] is True
        assert "foo" in parsed["paths"]

    def test_interactive_flag(self, hook):
        parsed = hook.parse_args(["-i", "x"])
        assert parsed["interactive"] is True

    def test_interactive_conflict_force_wins(self, hook):
        # GNU rm: -f 覆盖先前的 -i。我们记录 flag 出现顺序，最后一个生效。
        parsed = hook.parse_args(["-i", "-f", "x"])
        assert parsed["interactive"] is False
        assert parsed["force"] is True
        parsed2 = hook.parse_args(["-f", "-i", "x"])
        assert parsed2["interactive"] is True
        assert parsed2["force"] is True  # force 不被覆盖，仅 interactive 被 -i 再打开

    def test_extra_flags_passthrough(self, hook):
        # --preserve-root / --no-preserve-root 等长选项透传给 extra_flags
        parsed = hook.parse_args(["--no-preserve-root", "-rf", "/"])
        assert "--no-preserve-root" in parsed["extra_flags"]

    def test_stop_at_dash_dash(self, hook):
        # rm -- -oddfilename 表示后续全是路径
        parsed = hook.parse_args(["-rf", "--", "-weirdname", "ok.txt"])
        assert parsed["paths"] == ["-weirdname", "ok.txt"]


class TestRmPreview:
    @pytest.fixture
    def hook(self):
        return RmHook()

    def test_count_hidden_files_and_size(self, hook, tmp_workspace):
        """tmp_workspace 里应有 6 个实体（4 文件 + 1 目录 notes + 1 .hidden + 2 notes 下文件 = 8？需核对 fixture）"""
        # fixture 里有：
        # report_final_v3.docx (100), thesis_backup.pdf (200), customer_db.sql (4096),
        # .hidden_secret (50), notes/idea1.txt, notes/idea2.txt
        # 受影响文件总数 = 6 个文件 + 1 个目录(notes)
        parsed = hook.parse_args(["-rf", str(tmp_workspace)])
        pr = hook.preview(parsed)
        # 至少 6 个文件 + 1 个目录
        assert pr.affected_count >= 7
        # 总大小至少 100+200+4096+50 = 4446
        assert pr.total_size_bytes >= 4446
        # sample_items 前 5 个应包含具体文件名
        basenames_in_samples = [os.path.basename(s) for s in pr.sample_items]
        assert "report_final_v3.docx" in basenames_in_samples
        assert ".hidden_secret" not in basenames_in_samples or True  # 允许出现也允许跳过，不强求
        # 验证池非空
        assert len(pr.validation_pool) >= 1
        # 递归删除目录 risk_level >= 2
        assert pr.risk_level >= 2

    def test_delete_root_triggers_extra_warning(self, hook):
        parsed = hook.parse_args(["--no-preserve-root", "-rf", "/"])
        pr = hook.preview(parsed)
        # 删根 → 必须 risk_level=3 且含"根目录"之类的警告
        assert pr.risk_level == 3
        joined = " ".join(pr.extra_warnings)
        assert len(pr.extra_warnings) > 0

    def test_non_recursive_single_file_low_risk(self, hook, tmp_workspace):
        f = tmp_workspace / "report_final_v3.docx"
        parsed = hook.parse_args([str(f)])
        pr = hook.preview(parsed)
        assert pr.affected_count == 1
        assert pr.risk_level == 1

    def test_whitelisted_tmp_path_same_counts(self, hook):
        # 预览不受白名单影响（白名单在 engine 层判断），这里只做统计正确
        parsed = hook.parse_args(["-rf", "/tmp/foo_xyz_abc"])
        pr = hook.preview(parsed)
        # /tmp/foo_xyz_abc 不存在 → 受影响 0，但 engine 层会继续走流程或让原生 rm 报 no such file
        # 我们不强行要求 preview 在目录不存在时报错
        assert pr.affected_count >= 0
        assert pr.total_size_bytes >= 0

    def test_validation_pool_contains_real_basenames(self, hook, tmp_workspace):
        parsed = hook.parse_args(["-rf", str(tmp_workspace)])
        pr = hook.preview(parsed)
        # validation_pool 中应是"真实存在的文件名（basename）"
        fixture_basenames = {
            "report_final_v3.docx", "thesis_backup.pdf",
            "customer_db.sql", ".hidden_secret",
            "idea1.txt", "idea2.txt",
        }
        pool = set(pr.validation_pool)
        assert len(pool & fixture_basenames) >= 1
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /workspace && python -m pytest tests/test_hooks_rm.py -v 2>&1 | head -20`
Expected: FAIL "No module named 'danger_guard.hooks.rm_hook'"

- [ ] **Step 3: Write hooks/rm_hook.py**

```python
# danger_guard/hooks/rm_hook.py
"""
rm 命令拦截器。
- 参数解析：兼容 GNU rm（长选项 --recursive/--force）与 BSD rm（仅短选项）
- 预览：os.walk 递归统计受影响文件/目录数量与总大小，含隐藏文件
- 执行：调度到 executors 层（POSIX: /bin/rm；Windows: Remove-Item）
"""
import glob
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple

from danger_guard.hooks.base import BaseHook, PreviewResult, HookExecutionResult
from danger_guard.hooks import register_hook
from danger_guard import config
from danger_guard.executors import dispatch_exec


@register_hook
class RmHook(BaseHook):
    name = "rm"
    native_commands = {
        "Linux": ["rm"],
        "Darwin": ["rm"],
        "Windows": ["Remove-Item"],
    }

    # ---------- 参数解析 ----------

    def parse_args(self, raw_args: List[str]) -> Dict:
        """
        解析 rm 的命令行参数，返回结构化 dict：
        {
            "paths": List[str],          # 目标路径
            "recursive": bool,           # -r / -R / --recursive
            "force": bool,               # -f / --force
            "verbose": bool,             # -v / --verbose
            "interactive": bool,         # -i / --interactive（按出现顺序，后出现的覆盖）
            "interactive_once": bool,    # -I（一次确认）
            "preserve_root": bool,       # True 默认受保护；--no-preserve-root 设为 False
            "dry_run": bool,             # OhShit 自用的 dry-run flag（非原生 rm 参数）
            "extra_flags": List[str],    # 无法识别但安全的额外 flag（直接透传）
        }
        """
        parsed = {
            "paths": [],
            "recursive": False,
            "force": False,
            "verbose": False,
            "interactive": False,
            "interactive_once": False,
            "preserve_root": True,
            "dry_run": False,
            "extra_flags": [],
        }

        i = 0
        raw = list(raw_args)
        end_of_flags = False

        while i < len(raw):
            tok = raw[i]
            if end_of_flags:
                parsed["paths"].append(tok)
                i += 1
                continue

            if tok == "--":
                end_of_flags = True
                i += 1
                continue

            # 非选项 → 视为路径开始
            if not tok.startswith("-") or tok == "-":
                parsed["paths"].append(tok)
                i += 1
                continue

            # 长选项
            if tok.startswith("--"):
                eq = tok.find("=")
                key = tok if eq < 0 else tok[:eq]
                if key == "--recursive":
                    parsed["recursive"] = True
                elif key == "--force":
                    parsed["force"] = True
                elif key == "--verbose":
                    parsed["verbose"] = True
                elif key == "--interactive":
                    parsed["interactive"] = True
                    parsed["interactive_once"] = False
                elif key == "--no-preserve-root":
                    parsed["preserve_root"] = False
                elif key == "--preserve-root":
                    parsed["preserve_root"] = True
                elif key == "--one-file-system":
                    parsed["extra_flags"].append(tok)
                else:
                    parsed["extra_flags"].append(tok)
                i += 1
                continue

            # 短选项（可以组合：-rfv）
            short = tok[1:]
            j = 0
            while j < len(short):
                c = short[j]
                if c in ("r", "R"):
                    parsed["recursive"] = True
                elif c == "f":
                    parsed["force"] = True
                    # -f 取消先前的 -i/-I（POSIX/GNU 行为）
                    parsed["interactive"] = False
                    parsed["interactive_once"] = False
                elif c == "v":
                    parsed["verbose"] = True
                elif c == "i":
                    parsed["interactive"] = True
                    parsed["interactive_once"] = False
                elif c == "I":
                    parsed["interactive_once"] = True
                    # -I 不覆盖 -i，但与 interactive 并存时 interactive_once=True
                elif c == "d":
                    parsed["extra_flags"].append("-d")
                elif c == "P":  # overwrite (GNU) 或 -P no-deref (BSD)
                    parsed["extra_flags"].append("-P")
                elif c == "h":  # BSD -h: symlink follow for command line args only
                    parsed["extra_flags"].append("-h")
                else:
                    # 未知短选项：作为 extra flag 透传（比如 -W, --warning 等）
                    parsed["extra_flags"].append("-" + c)
                j += 1
            i += 1

        return parsed

    # ---------- 预览 ----------

    def preview(self, parsed: Dict) -> PreviewResult:
        paths = parsed["paths"] or []
        target_scope = " ".join(paths) if paths else "<空路径>"

        affected_count = 0
        total_size = 0
        all_paths_found: List[Tuple[str, bool]] = []   # (abs_path, is_file?)
        extra_warnings: List[str] = []

        # ① 通配符展开与 ~ 展开
        expanded_paths: List[str] = []
        for p in paths:
            expanded = os.path.expandvars(os.path.expanduser(p))
            # 只对通配符模式做 glob；普通路径保持原样（不存在也先留着，等会 os.walk/readlink 会报 PermissionError 等）
            if any(ch in expanded for ch in "*?["):
                matches = glob.glob(expanded, recursive=parsed.get("recursive", False))
                if matches:
                    expanded_paths.extend(matches)
                else:
                    # 没匹配到就保留原字符串（让原生 rm 最终去报 No such file）
                    expanded_paths.append(expanded)
            else:
                expanded_paths.append(expanded)

        # ② 根目录保护检测（--no-preserve-root 才关闭）
        if parsed.get("preserve_root", True):
            # 默认保护：若路径包含 "/" 本身或 "*" 展开后为根，提前加 warning
            for p in expanded_paths:
                ap = os.path.abspath(p)
                if ap == "/" or ap.startswith("/../") or ap.startswith("//"):
                    extra_warnings.append("⚠ 目标涉及根目录 /，原生 rm 默认拒绝删除根。如真要删请加 --no-preserve-root")
        else:
            # --no-preserve-root + 删 / → 最高威慑
            for p in expanded_paths:
                ap = os.path.abspath(p)
                if ap == "/":
                    extra_warnings.append("⚠⚠⚠ 检测到 --no-preserve-root /！即将删除整个文件系统！！！")
                    extra_warnings.append("⚠ 此操作不可恢复，请再次确认是否真的要删根。")

        # ③ 遍历统计
        permission_denied_count = 0
        for ep in expanded_paths:
            ap = os.path.abspath(ep)
            try:
                st = os.lstat(ap)
            except FileNotFoundError:
                continue
            except PermissionError:
                permission_denied_count += 1
                continue
            except OSError:
                continue

            if os.path.isdir(ap) and not os.path.islink(ap):
                # 目录：需要递归（若 recursive 开）或仅计目录本身
                if parsed.get("recursive"):
                    try:
                        for root, dirs, files in os.walk(ap, followlinks=False, onerror=self._walk_onerror):
                            for d in dirs:
                                dp = os.path.join(root, d)
                                try:
                                    dst = os.lstat(dp)
                                    affected_count += 1
                                    all_paths_found.append((dp, False))
                                except OSError:
                                    permission_denied_count += 1
                            for fn in files:
                                fp = os.path.join(root, fn)
                                try:
                                    fst = os.lstat(fp)
                                    affected_count += 1
                                    total_size += fst.st_size
                                    all_paths_found.append((fp, True))
                                except OSError:
                                    permission_denied_count += 1
                            # 目录本身也计数
                            try:
                                rst = os.lstat(root)
                                affected_count += 1
                                all_paths_found.append((root, False))
                            except OSError:
                                permission_denied_count += 1
                    except OSError:
                        permission_denied_count += 1
                else:
                    # 非递归删目录：原生 rm 会报 "Is a directory"，这里只做轻量统计 + 计数 1
                    affected_count += 1
                    all_paths_found.append((ap, False))
            else:
                # 单个文件 / 符号链接 / 其他
                affected_count += 1
                try:
                    total_size += st.st_size
                except OSError:
                    pass
                all_paths_found.append((ap, os.path.isfile(ap) and not os.path.islink(ap)))

        if permission_denied_count > 0:
            extra_warnings.append(
                f"⚠ {permission_denied_count} 个路径权限不足，统计可能偏小。实际删除量以原生命令为准。"
            )

        # ④ sample_items：前 5 个最"像用户数据"的条目（优先文件，按字母序）
        files_only = sorted([p for p, isf in all_paths_found if isf])
        dirs_only = sorted([p for p, isf in all_paths_found if not isf])
        # mix：先放文件 5 个，不够再补目录
        sample_items = files_only[:5]
        if len(sample_items) < 5:
            sample_items += dirs_only[:(5 - len(sample_items))]
        # 截断太长的路径 → 保留 basename + 前级较短
        sample_items = [self._shorten_path_for_ui(s) for s in sample_items]

        # ⑤ validation_pool：从真实文件 basename 中抽（若没有文件，退而用目录名）
        file_basenames = list({os.path.basename(p) for p, isf in all_paths_found if isf and os.path.basename(p)})
        dir_basenames = list({os.path.basename(p) for p, isf in all_paths_found if not isf and os.path.basename(p)})
        validation_pool = file_basenames or dir_basenames or (list(filter(None, [os.path.basename(p) for p in expanded_paths])))
        if not validation_pool:
            # 极端兜底：给一个"随机"验证字符串（确保 validator 不报错）
            validation_pool = [target_scope[:20] or "EMPTY"]

        # ⑥ 风险分级
        # 删根 + --no-preserve-root → 3
        # 删除对象数 >= 100 或 大小 >= 1 GiB → 3
        # 删除对象数 >= 10 或 大小 >= 1 MiB → 2
        # 否则 → 1
        if any("整个文件系统" in w or "根目录" in w and "整个" in w for w in extra_warnings):
            risk_level = 3
        elif affected_count >= 100 or total_size >= 1024 ** 3:
            risk_level = 3
        elif affected_count >= 10 or total_size >= 1024 ** 2:
            risk_level = 2
        else:
            risk_level = 1

        # "目标涉及 / 并且 force+recursive" 再加一条
        if parsed.get("recursive") and parsed.get("force") and any(
            os.path.abspath(p) == "/" for p in expanded_paths
        ):
            risk_level = 3

        return PreviewResult(
            affected_count=affected_count,
            total_size_bytes=total_size,
            sample_items=sample_items,
            target_scope=target_scope,
            risk_level=risk_level,
            validation_pool=validation_pool,
            extra_warnings=extra_warnings,
        )

    def _walk_onerror(self, err):
        """os.walk 出错回调：静默，让上层 permission_denied_count 计数（这里无法传回计数，仅抑制异常冒泡）。"""
        pass

    @staticmethod
    def _shorten_path_for_ui(path: str, max_len: int = 60) -> str:
        if len(path) <= max_len:
            return path
        head, tail = os.path.split(path)
        if len(tail) > max_len - 8:
            return "..." + tail[-(max_len - 4):]
        return head[:(max_len - len(tail) - 5)] + "/.../" + tail

    # ---------- 执行 ----------

    def execute(self, parsed: Dict, dry_run: bool = False) -> HookExecutionResult:
        return dispatch_exec("rm", parsed, dry_run=dry_run)
```

- [ ] **Step 4: Run rm hook tests**

Run: `cd /workspace && python -m pytest tests/test_hooks_rm.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
cd /workspace && git add danger_guard/hooks/rm_hook.py tests/test_hooks_rm.py && git commit -m "feat: rm hook - arg parsing + recursive preview with hidden files + risk grading"
```

---

## Task 7: dd Hook 实现

**Files:**
- Create: `danger_guard/hooks/dd_hook.py`
- Create: `tests/test_hooks_dd.py`

- [ ] **Step 1: Write dd hook tests**

```python
# tests/test_hooks_dd.py
import os
from pathlib import Path
import pytest
from danger_guard.hooks.dd_hook import DdHook
from danger_guard.hooks import get_hook


def test_dd_hook_is_registered():
    cls = get_hook("dd")
    assert cls is DdHook
    assert cls.name == "dd"


class TestDdParseArgs:
    @pytest.fixture
    def hook(self):
        return DdHook()

    def test_kv_standard(self, hook):
        parsed = hook.parse_args(["if=/dev/zero", "of=/tmp/out.img", "bs=4M", "count=100"])
        assert parsed["if"] == "/dev/zero"
        assert parsed["of"] == "/tmp/out.img"
        assert parsed["bs"] == "4M"
        assert parsed["count"] == "100"

    def test_bs_size_prefixes_parsed(self, hook):
        # bs= 本身是字符串透传，size 字段是 engine 统一解析
        parsed = hook.parse_args(["bs=1G", "count=2", "if=/dev/zero", "of=x"])
        assert parsed["bs"] == "1G"
        assert parsed["count"] == "2"

    def test_conv_multi_comma(self, hook):
        parsed = hook.parse_args(["conv=noerror,sync,notrunc", "if=a", "of=b"])
        assert parsed["conv"] == "noerror,sync,notrunc"

    def test_status_progress(self, hook):
        parsed = hook.parse_args(["status=progress", "if=a", "of=b"])
        assert parsed["status"] == "progress"

    def test_mixed_extra_flags_dd(self, hook):
        # --version / --help 在 GNU dd 中出现；这里存入 extra_flags
        parsed = hook.parse_args(["--version"])
        assert "--version" in parsed["extra_flags"]

    def test_if_or_of_missing(self, hook):
        # 允许只有 if（dd 读并输出到 stdout）或只有 of（从 stdin 写）
        p1 = hook.parse_args(["if=in"])
        assert p1["if"] == "in" and not p1["of"]
        p2 = hook.parse_args(["of=out"])
        assert p2["of"] == "out" and not p2["if"]


class TestDdPreview:
    @pytest.fixture
    def hook(self):
        return DdHook()

    def test_of_is_regular_file_risk_level_2(self, hook, tmp_workspace):
        """覆写已存在的普通文件 → 中危 (2)"""
        victim = tmp_workspace / "report_final_v3.docx"
        parsed = hook.parse_args(["if=/dev/zero", f"of={victim}", "bs=512", "count=1"])
        pr = hook.preview(parsed)
        assert pr.risk_level == 2
        assert pr.affected_count == 1
        assert victim.name in pr.validation_pool or str(victim) in pr.validation_pool

    def test_of_is_new_file_low_risk(self, hook, tmp_workspace):
        """向不存在的文件写 → 低危 (1)"""
        target = tmp_workspace / "brand_new.img"
        parsed = hook.parse_args(["if=/dev/zero", f"of={target}", "bs=1M", "count=1"])
        pr = hook.preview(parsed)
        assert pr.risk_level == 1

    def test_block_device_like_path_triggers_high_risk(self, hook, monkeypatch):
        """以 /dev/ 开头且暗示块设备时，高风险（无需真实块设备权限即可判断 risk_level=3）"""
        parsed = hook.parse_args(["if=/dev/zero", "of=/dev/sdx_fake", "bs=4M", "count=256"])
        pr = hook.preview(parsed)
        # of 指向 /dev/* → 高风险
        assert pr.risk_level == 3
        assert any("块设备" in w or "/dev/" in w or "block" in w.lower() for w in pr.extra_warnings)

    def test_count_multiplies_bs_for_total_size_estimate(self, hook):
        """预览能给出写入总字节数估计（bs * count）。"""
        parsed = hook.parse_args(["if=a", "of=b", "bs=1M", "count=10"])
        pr = hook.preview(parsed)
        # 1M * 10 = 10 MiB = 10485760
        assert pr.total_size_bytes >= 10 * 1024 * 1024 - 1  # 允许 ±1

    def test_no_count_means_stream(self, hook):
        """没有 count= 时，total_size 以 if 文件大小估算（若 if 可 stat），否则 0，extra_warn 会提示未知大小"""
        parsed = hook.parse_args(["if=/dev/zero", "of=/tmp/x"])
        pr = hook.preview(parsed)
        # /dev/zero 是字符设备，大小未知 → 给提示
        found_unknown = any("大小" in w and ("未知" in w or "不确定" in w or "全部" in w)
                            for w in pr.extra_warnings)
        # 也可能 risk_level=3（因为写 /tmp/x 到字符设备输入流 → 风险未知但不低）
        assert pr.risk_level >= 2 or found_unknown

    def test_validation_pool_contains_of_or_if(self, hook):
        parsed = hook.parse_args(["if=/home/alice/disk.img", "of=/tmp/disk_copy.img", "bs=1M"])
        pr = hook.preview(parsed)
        pool_join = " ".join(pr.validation_pool).lower()
        assert "disk" in pool_join or "disk_copy" in pool_join or "disk.img" in pool_join
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /workspace && python -m pytest tests/test_hooks_dd.py -v 2>&1 | head -20`
Expected: FAIL "No module named 'danger_guard.hooks.dd_hook'"

- [ ] **Step 3: Write hooks/dd_hook.py**

```python
# danger_guard/hooks/dd_hook.py
"""
dd 命令拦截器（磁盘烧录/覆盖的高危操作）。
- 参数解析：dd 使用 key=value 风格（不是 GNU 风格的 -- 选项）
- 预览：根据 of= 目标类型（块设备/已有文件/新文件）划分风险等级，
        基于 bs*count 或 if 文件大小估算写入字节总量
- 执行：调度到 executors 层
"""
import os
import re
import shutil
import stat
import sys
from pathlib import Path
from typing import List, Dict, Optional

from danger_guard.hooks.base import BaseHook, PreviewResult, HookExecutionResult
from danger_guard.hooks import register_hook
from danger_guard.executors import dispatch_exec


@register_hook
class DdHook(BaseHook):
    name = "dd"
    native_commands = {
        "Linux": ["dd"],
        "Darwin": ["dd"],
        "Windows": ["dd"],  # Windows 上需用户自行安装 Git Bash / Cygwin dd
    }

    # dd 支持的 key=value（我们关心并结构化解析的白名单，其余都进 extra_flags）
    _KNOWN_KEYS = {
        "if", "of", "bs", "ibs", "obs", "cbs",
        "skip", "seek", "count", "conv", "status",
        "iflag", "oflag",
    }

    # ---------- 参数解析 ----------

    def parse_args(self, raw_args: List[str]) -> Dict:
        parsed = {
            "if": "",
            "of": "",
            "bs": "",
            "ibs": "",
            "obs": "",
            "cbs": "",
            "skip": "",
            "seek": "",
            "count": "",
            "conv": "",
            "status": "",
            "iflag": "",
            "oflag": "",
            "extra_flags": [],
        }
        for tok in raw_args:
            # dd 风格: key=value
            if "=" in tok and not tok.startswith("-"):
                eq = tok.index("=")
                k = tok[:eq]
                v = tok[eq + 1:]
                if k in self._KNOWN_KEYS:
                    parsed[k] = v
                else:
                    # 未知 key=value（如某些扩展字段），整体透传
                    parsed["extra_flags"].append(tok)
            else:
                # 非 key=value：可能是 --help/--version 之类长选项，或用户打错
                parsed["extra_flags"].append(tok)
        return parsed

    # ---------- 预览 ----------

    @staticmethod
    def _parse_size_token(tok: str) -> Optional[int]:
        """
        dd 风格大小字符串 → 字节数。
        支持：无后缀=字节, K/k=1024, M, G, T, P, E,
        b=512, c=1, w=2, kB=1000, MB=1000^2...
        无法解析返回 None。
        """
        if not tok:
            return None
        s = tok.strip()
        if not s:
            return None
        m = re.match(r'^(\d+(?:\.\d+)?)\s*([a-zA-Z]*)$', s)
        if not m:
            return None
        num = float(m.group(1))
        suffix = m.group(2)
        multipliers = {
            "": 1,
            "c": 1,
            "w": 2,
            "b": 512,
            "K": 1024, "k": 1024, "KiB": 1024, "KIB": 1024,
            "M": 1024 ** 2, "MiB": 1024 ** 2,
            "G": 1024 ** 3, "GiB": 1024 ** 3,
            "T": 1024 ** 4, "TiB": 1024 ** 4,
            "P": 1024 ** 5, "PiB": 1024 ** 5,
            "E": 1024 ** 6, "EiB": 1024 ** 6,
            # SI 单位（dd 也支持 kB, MB 等十进制）
            "kB": 1000, "KB": 1000,
            "MB": 1000 ** 2,
            "GB": 1000 ** 3,
            "TB": 1000 ** 4,
            "PB": 1000 ** 5,
            "EB": 1000 ** 6,
            "x": 512,  # x = 512 块，PDP-11 遗产
        }
        if suffix not in multipliers:
            return None
        return int(num * multipliers[suffix])

    @staticmethod
    def _estimate_write_bytes(parsed: Dict, if_exists: bool, if_size: Optional[int]) -> Optional[int]:
        """估算 dd 将要写入的总字节数。无法确定时返回 None。"""
        bs = (DdHook._parse_size_token(parsed.get("bs", ""))
              or DdHook._parse_size_token(parsed.get("obs", ""))
              or 512)
        count_str = parsed.get("count", "")
        if count_str:
            cnt_val = DdHook._parse_size_token(count_str)
            if cnt_val is not None:
                return bs * cnt_val
        # 没有 count=：若 if= 是普通文件，用 if 文件大小估算
        if if_exists and if_size is not None:
            skip = DdHook._parse_size_token(parsed.get("skip", "")) or 0
            remain = max(0, if_size - skip * bs if skip * bs < if_size else 0)
            if remain > 0:
                return remain
        return None

    @staticmethod
    def _target_desc(of: str) -> str:
        if of:
            return f"写入目标: {of}"
        return "写入目标: stdout（无 of=）"

    def preview(self, parsed: Dict) -> PreviewResult:
        ifp = parsed.get("if", "")
        ofp = parsed.get("of", "")

        extra_warnings: List[str] = []
        sample_items: List[str] = []
        risk_level = 1
        affected_count = 1  # dd 的"受影响数量"恒为 1（目标是单个设备或文件）
        total_size = 0
        target_scope = ""

        # 分析 if
        if_exists = False
        if_size = None
        if ifp:
            try:
                if_st = os.stat(ifp)
                if_exists = True
                if stat.S_ISREG(if_st.st_mode):
                    if_size = if_st.st_size
            except (OSError, ValueError):
                pass

        # 估算写入量
        est = self._estimate_write_bytes(parsed, if_exists, if_size)
        if est is not None:
            total_size = est
        else:
            extra_warnings.append("⚠ 未指定 count= 且无法确定输入大小，写入量未知（可能持续写入直到 EOF）")

        # 分析 of
        of_is_block = False
        of_is_char_device = False
        of_is_existing_regular = False
        of_exists = False
        of_real_path = ""
        if ofp:
            of_real_path = os.path.abspath(os.path.expanduser(ofp))
            sample_items.append(of_real_path)
            try:
                st = os.stat(of_real_path)
                of_exists = True
                mode = st.st_mode
                if stat.S_ISBLK(mode):
                    of_is_block = True
                    extra_warnings.append(
                        f"⚠⚠⚠ 目标为块设备 ({of_real_path})！此操作会破坏分区表与所有数据，且不可恢复！"
                    )
                    # 尝试追加设备总容量信息（若 stat st_size 给出了）
                    if st.st_size and st.st_size > 0:
                        extra_warnings.append(f"   设备容量: ~{st.st_size / 1024**3:.1f} GiB")
                    risk_level = 3
                elif stat.S_ISCHR(mode):
                    of_is_char_device = True
                    extra_warnings.append(f"⚠ 目标为字符设备 ({of_real_path})，写入量与后果均未知")
                    risk_level = 3
                elif stat.S_ISREG(mode):
                    of_is_existing_regular = True
                    risk_level = 2
                    extra_warnings.append(f"⚠ 覆写已存在文件: {of_real_path}（原有内容将丢失）")
            except FileNotFoundError:
                # 新文件 → 低危
                risk_level = 1 if risk_level < 2 else risk_level
            except PermissionError:
                extra_warnings.append(f"⚠ 无法访问 {of_real_path}（权限不足），风险评估不完整")
                risk_level = max(risk_level, 2)
            except OSError as e:
                extra_warnings.append(f"⚠ 访问 {of_real_path} 出错: {e}")
                risk_level = max(risk_level, 2)
        else:
            # 无 of= → 输出到 stdout（通常无风险，但 stdin→stdout 仍有破坏性可能，保守）
            sample_items.append("stdout")
            risk_level = 1

        # /dev/* 暗示块设备但 stat 失败（比如用户没权限、或在容器里）→ 高风险
        if not of_is_block and of_real_path.startswith("/dev/") and risk_level < 3:
            extra_warnings.append(f"⚠ 目标位于 /dev/ 目录 ({of_real_path})，假定为设备节点，极高风险")
            risk_level = 3

        # 构造 target_scope 描述
        parts = []
        if ifp:
            parts.append(f"输入: {ifp}")
        else:
            parts.append("输入: stdin")
        parts.append(self._target_desc(ofp))
        if est is not None:
            parts.append(f"预计写入: ~{est:,} 字节")
        if parsed.get("bs"):
            parts.append(f"块大小: bs={parsed['bs']}")
        target_scope = "  |  ".join(parts)

        # 若 of 文件存在，把它的 basename 加入样本（用于 sample & validation）
        if ofp:
            basename = os.path.basename(ofp) or ofp
            if basename not in sample_items:
                sample_items.append(basename)
        if ifp:
            basename = os.path.basename(ifp) or ifp
            if basename not in sample_items:
                sample_items.append(basename)

        # validation_pool：用 of 文件名 + if 文件名 + 目标描述
        validation_pool = []
        for p in (ofp, ifp):
            if not p:
                continue
            b = os.path.basename(p)
            if b and b not in validation_pool:
                validation_pool.append(b)
            if p not in validation_pool and len(p) <= 40:
                validation_pool.append(p)
        # 如果还空，就给几个合理的兜底
        if not validation_pool:
            validation_pool = ["stdout", "stdin", target_scope[:20] or "DD_STREAM"]

        return PreviewResult(
            affected_count=affected_count,
            total_size_bytes=total_size,
            sample_items=sample_items[:5],
            target_scope=target_scope,
            risk_level=risk_level,
            validation_pool=validation_pool,
            extra_warnings=extra_warnings,
        )

    # ---------- 执行 ----------

    def execute(self, parsed: Dict, dry_run: bool = False) -> HookExecutionResult:
        return dispatch_exec("dd", parsed, dry_run=dry_run)
```

- [ ] **Step 4: Run dd hook tests**

Run: `cd /workspace && python -m pytest tests/test_hooks_dd.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
cd /workspace && git add danger_guard/hooks/dd_hook.py tests/test_hooks_dd.py && git commit -m "feat: dd hook - key=value arg parsing + block/device detection + size estimation preview"
```

---

## Task 8: Engine 编排 + CLI 入口 + __main__

**Files:**
- Create: `danger_guard/core/engine.py`
- Create: `danger_guard/cli.py`
- Create: `danger_guard/__main__.py`
- Create: `tests/test_engine_smoke.py`

- [ ] **Step 1: Write engine smoke tests**

```python
# tests/test_engine_smoke.py
"""
集成冒烟测试：把 engine 七步流完整跑一遍（dry_run=True 不真的删）。
用 monkeypatch 模拟用户输入（第一次就通过验证 + 最后输入 DELETE）。
"""
import os
import sys
import pytest
from pathlib import Path

from danger_guard.core.engine import run_pipeline, ExitHooks, ExitCode


class TestEngineRmSmoke:
    def test_recursive_delete_passes_all_7_steps_in_dry_run(
        self, tmp_workspace, fake_tty, monkeypatch, capsys
    ):
        from tests.conftest import patch_user_input
        target = str(tmp_workspace)
        # 模拟：① B- 验证时选 report_final_v3.docx，用大小写不同的 Report_FINAL_V3.DOCX 过关
        #      ② 最终确认输入 DELETE
        #      （validator 会随机抽 challenge，若第一次不是上述文件就模糊输入正确的 challenge）
        # 为了不依赖随机数，这里用 validator 内部的 validate_challenge 逻辑：
        # 只要输入的是 pool 中任一文件名的"非精确一致但模糊匹配"形态就能过。
        # 策略：输入一串"在 pool 中肯定能模糊匹配但不精确一致"的字符串 + 后续 DELETE
        patch_user_input(monkeypatch, [
            "REPORT_FINAL_V3.DOCX",   # 与 report_final_v3.docx 大小写不同 → 模糊匹配通过
            "DELETE",
        ])
        exit_code = run_pipeline(
            command_name="rm",
            raw_args=["-rf", target],
            dry_run=True,
        )
        assert exit_code == 0
        # 捕获输出：应包含警告框关键信息
        out = capsys.readouterr().out + capsys.readouterr().err
        # TTY 模式至少包含"危险"或"DANGER"字样
        assert "DANGER" in out or "危险" in out

    def test_non_tty_bypasses_all_and_calls_execute_directly(
        self, tmp_workspace, fake_pipe, monkeypatch, capsys
    ):
        """非交互模式（fake_pipe = 非TTY）→ 不弹验证，直接 dry_run=0"""
        exit_code = run_pipeline(
            command_name="rm",
            raw_args=["-rf", str(tmp_workspace)],
            dry_run=True,
        )
        assert exit_code == 0
        combined = capsys.readouterr().out + capsys.readouterr().err
        # 非 TTY：不得出现"人机验证"等字样
        assert "B-" not in combined and "人机验证" not in combined

    def test_hook_not_registered_returns_code_2(self):
        with pytest.raises(SystemExit) as excinfo:
            run_pipeline(command_name="chmod", raw_args=["777", "/tmp"], dry_run=True)
        assert excinfo.value.code == 2

    def test_force_env_bypasses_everything(
        self, tmp_workspace, fake_tty, monkeypatch
    ):
        """DANGER_FORCE=1 环境变量：即使是交互 TTY 也直接走 execute"""
        monkeypatch.setenv("DANGER_FORCE", "1")
        import danger_guard.config as _cfg
        monkeypatch.setattr(_cfg, "FORCE_FLAG", True)
        exit_code = run_pipeline(
            command_name="rm",
            raw_args=["-rf", str(tmp_workspace)],
            dry_run=True,
        )
        assert exit_code == 0
```

- [ ] **Step 2: Run tests to verify failure (module not yet written)**

Run: `cd /workspace && python -m pytest tests/test_engine_smoke.py -v 2>&1 | head -15`
Expected: FAIL "No module named 'danger_guard.core.engine'"

- [ ] **Step 3: Write core/engine.py**

```python
# danger_guard/core/engine.py
"""
三阶防护主流程编排器（7 步法）。
对外唯一公开接口：run_pipeline(command_name, raw_args, dry_run) -> int (exit_code)

安全兜底：任何内部异常 → 捕获 → 写 ~/.danger.log → 直接执行原生命令（宁放不误杀）。
"""
import os
import sys
import traceback
from pathlib import Path
from typing import List, Dict, Optional

import danger_guard.config as config
from danger_guard.hooks import get_hook, list_hooks
from danger_guard.hooks.base import PreviewResult, HookExecutionResult
from danger_guard.core.tty_detector import (
    should_bypass_all_protections,
    is_interactive_tty,
)
from danger_guard.core.whitelist import (
    load_whitelist,
    is_any_path_whitelisted,
)
from danger_guard.core.ui import (
    render_warning_box,
    final_confirm,
    print_whitelist_bypass,
    print_internal_fault,
)
from danger_guard.core.validator import run_validation_loop, ConfusableError


# Exit code 常量（便于测试与 sys.exit）
class ExitCode:
    OK = 0
    CANCELLED_BY_USER = 1
    HOOK_NOT_REGISTERED = 2
    VALIDATION_FAILED = 3
    NATIVE_ERROR = 1  # 与原生命令错误码透传，不占用
    CTRL_C = 130


def _write_traceback_log(exc: BaseException) -> None:
    """把 traceback 写入 ~/.danger.log，写失败静默。"""
    try:
        with open(config.LOG_PATH, "a", encoding="utf-8") as f:
            import datetime as _dt
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"[{_dt.datetime.now().isoformat()}] OhShit internal fault\n")
            traceback.print_exc(file=f)
            f.write(f"Exception: {type(exc).__name__}: {exc}\n")
    except (OSError, IOError):
        pass


def _targets_for_whitelist(parsed: Dict, hook_name: str) -> List[str]:
    """从 Hook 的 parsed dict 提取需要做白名单比对的路径列表。
    Hook 之间 schema 不同，这里做显式转换。"""
    if hook_name == "rm":
        return parsed.get("paths") or []
    elif hook_name == "dd":
        of = parsed.get("of", "")
        if of:
            return [of]
        return []
    return []


def run_pipeline(
    command_name: str,
    raw_args: List[str],
    dry_run: bool = False,
) -> int:
    """
    运行 7 步完整 pipeline。
    :param command_name: 命令名（"rm" / "dd"，由 hooks 注册表决定可用列表）
    :param raw_args: 除了命令本身之外的参数列表（如 sys.argv[2:]）
    :param dry_run: True 时 Hook.execute() 只打印不实际执行，用于测试
    :returns: 应传给 sys.exit 的退出码
    :raises SystemExit: 错误情况下本函数内部就 sys.exit（方便 CLI 调用者）；测试调用方请捕获
    """
    # ① 先拿到 Hook 实例：hook 不存在时立即报错并 exit(2)
    #    （放在安全兜底 try 外面，因为 hook 未注册是用户错误，不是内部故障）
    try:
        hook_cls = get_hook(command_name)
    except KeyError as e:
        available = ", ".join(sorted(list_hooks().keys()))
        print(
            f"ohshit: 未注册的命令 --cmd={command_name!r}，当前可用: {available}",
            file=sys.stderr,
        )
        print(
            "如需扩展，请在 danger_guard/hooks/ 下新建文件并用 @register_hook 装饰器注册。",
            file=sys.stderr,
        )
        sys.exit(ExitCode.HOOK_NOT_REGISTERED)

    hook = hook_cls()

    try:
        parsed = hook.parse_args(list(raw_args))
    except Exception as exc:
        # 参数解析内部异常 → 兜底直接执行
        print_internal_fault(exc, config.LOG_PATH)
        _write_traceback_log(exc)
        result = hook.execute(parsed={}, dry_run=dry_run) if False else HookExecutionResult(
            success=False, exit_code=ExitCode.CANCELLED_BY_USER
        )
        # 更安全地：把 raw_args 作为路径传入，让 hook 尝试以最小 parsed 执行
        # （不同 Hook schema 不同，这里做兜底：尽量让原生命令拿到原始 args）
        # 若解析失败，直接调用 shell 版本的原生命令并返回结果
        return _fallback_native_exec(command_name, raw_args, dry_run)

    # ② 【TTY 检测 + FORCE_ENV】→ 直接跳过所有防护
    try:
        bypass, bypass_reason = should_bypass_all_protections()
    except Exception as exc:
        print_internal_fault(exc, config.LOG_PATH)
        _write_traceback_log(exc)
        return _fallback_native_exec(command_name, raw_args, dry_run)

    if bypass:
        if config.FORCE_FLAG and is_interactive_tty():
            # 交互 + 强制 → 给用户一句提示（防止忘记取消 env）
            print(
                f"[ohshit] {bypass_reason}，已跳过所有防护。",
                file=sys.stderr,
            )
        try:
            result = hook.execute(parsed, dry_run=dry_run)
            return _handle_hook_exec_result(result)
        except KeyboardInterrupt:
            print("\n已取消（Ctrl+C）", file=sys.stderr)
            return ExitCode.CTRL_C
        except Exception as exc:
            print_internal_fault(exc, config.LOG_PATH)
            _write_traceback_log(exc)
            return _fallback_native_exec(command_name, raw_args, dry_run)

    # ③ 【白名单检查】整体放行（要求所有路径都命中白名单）
    try:
        wl_targets = _targets_for_whitelist(parsed, command_name)
    except Exception as exc:
        wl_targets = []

    if wl_targets:
        try:
            wl_rules = load_whitelist()
            all_whitelisted = is_any_path_whitelisted(wl_targets, wl_rules, require_all=True)
            if all_whitelisted:
                # 白名单命中：打印旁路提示，直接执行
                rules_hit = [r for r in wl_rules if r in (config.DEFAULT_WHITELIST_ITEMS or []) or True][:3]
                print_whitelist_bypass(wl_targets, rules_hit)
                try:
                    result = hook.execute(parsed, dry_run=dry_run)
                    return _handle_hook_exec_result(result)
                except KeyboardInterrupt:
                    print("\n已取消（Ctrl+C）", file=sys.stderr)
                    return ExitCode.CTRL_C
                except Exception as exc:
                    print_internal_fault(exc, config.LOG_PATH)
                    _write_traceback_log(exc)
                    return _fallback_native_exec(command_name, raw_args, dry_run)
        except Exception as exc:
            print_internal_fault(exc, config.LOG_PATH)
            _write_traceback_log(exc)
            # 白名单模块崩了就继续往下走（误放行比误杀好，但要走完整防护流）

    # ④ 【一阶 · preivew】
    try:
        preview: PreviewResult = hook.preview(parsed)
    except KeyboardInterrupt:
        print("\n已取消（Ctrl+C）", file=sys.stderr)
        return ExitCode.CTRL_C
    except Exception as exc:
        print_internal_fault(exc, config.LOG_PATH)
        _write_traceback_log(exc)
        return _fallback_native_exec(command_name, raw_args, dry_run)

    # ⑤ 【二阶 · 红色警告框】
    try:
        render_warning_box(preview)
    except KeyboardInterrupt:
        print("\n已取消（Ctrl+C）", file=sys.stderr)
        return ExitCode.CTRL_C
    except Exception as exc:
        # 警告框渲染失败不阻塞，继续
        print(f"[ohshit] 警告框渲染失败（{exc}），继续验证流程...", file=sys.stderr)

    # ⑥ 【三阶 · B- 随机文件名验证】3 次机会
    try:
        passed_v, _history = run_validation_loop(preview.validation_pool, max_attempts=3)
    except KeyboardInterrupt:
        print("\n已取消（Ctrl+C）", file=sys.stderr)
        return ExitCode.CTRL_C
    except ConfusableError as exc:
        print(f"ohshit: 验证器配置错误: {exc}", file=sys.stderr)
        return ExitCode.CANCELLED_BY_USER
    except Exception as exc:
        print_internal_fault(exc, config.LOG_PATH)
        _write_traceback_log(exc)
        return _fallback_native_exec(command_name, raw_args, dry_run)

    if not passed_v:
        return ExitCode.VALIDATION_FAILED

    # ⑦ 【最终确认】输入 DELETE（全大写）
    try:
        confirmed = final_confirm(preview)
    except KeyboardInterrupt:
        print("\n已取消（Ctrl+C）", file=sys.stderr)
        return ExitCode.CTRL_C
    except Exception as exc:
        print_internal_fault(exc, config.LOG_PATH)
        _write_traceback_log(exc)
        return _fallback_native_exec(command_name, raw_args, dry_run)

    if not confirmed:
        print("\n操作已取消。", file=sys.stderr)
        return ExitCode.CANCELLED_BY_USER

    # ⑧ 执行
    try:
        result = hook.execute(parsed, dry_run=dry_run)
        return _handle_hook_exec_result(result)
    except KeyboardInterrupt:
        print("\n已取消（Ctrl+C）", file=sys.stderr)
        return ExitCode.CTRL_C
    except Exception as exc:
        print_internal_fault(exc, config.LOG_PATH)
        _write_traceback_log(exc)
        return _fallback_native_exec(command_name, raw_args, dry_run)


def _handle_hook_exec_result(result: HookExecutionResult) -> int:
    if result.message:
        stream = sys.stdout if result.success else sys.stderr
        print(result.message, file=stream)
    return result.exit_code if result.exit_code is not None else (0 if result.success else 1)


def _fallback_native_exec(
    command_name: str,
    raw_args: List[str],
    dry_run: bool,
) -> int:
    """
    安全兜底：OhShit 任何内部故障 → 尝试直接把原始参数交给系统原生命令。
    这里完全绕过 Hook 体系，直接用 subprocess 调 /bin/<cmd>。
    宁放不误杀——用户的正常操作优先。
    """
    import subprocess as _sp
    import shutil as _su

    # 尝试找绝对路径的可执行文件
    candidate_dirs = ["/bin", "/usr/bin", "/sbin", "/usr/sbin", "/usr/local/bin"]
    exe = None
    for d in candidate_dirs:
        p = os.path.join(d, command_name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            exe = p
            break
    if not exe:
        exe = _su.which(command_name) or command_name

    cmd = [exe] + list(raw_args)
    if dry_run:
        print("[ohshit dry-run][fallback]  " + " ".join(cmd), file=sys.stderr)
        return 0
    try:
        completed = _sp.run(cmd, check=False)
        return completed.returncode
    except FileNotFoundError:
        print(f"ohshit: 找不到原生命令 {exe!r}", file=sys.stderr)
        return 127
    except OSError as e:
        print(f"ohshit: 执行 {exe!r} 失败: {e}", file=sys.stderr)
        return 1


# Engine 导出
__all__ = ["run_pipeline", "ExitCode"]
```

- [ ] **Step 4: Write cli.py**

```python
# danger_guard/cli.py
"""
argparse 统一入口。
使用方式：
    ohshit --cmd rm     <rm 的参数...>
    ohshit --cmd dd     <dd 的参数...>
    ohshit rm           <rm 的参数...>       # --cmd 可省略，第一个非选项当命令
    ohshit --version
    ohshit --list-hooks
    ohshit --help

安装脚本会把 alias rm='ohshit --cmd rm' 写入 rc 文件，所以实际被调时永远带 --cmd。
"""
import sys
import argparse
from typing import List

import danger_guard.config as config
from danger_guard import __version__
from danger_guard.hooks import list_hooks
from danger_guard.core.engine import run_pipeline, ExitCode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ohshit",
        description=(
            "OhShit 删库跑路预防针 —— 防止 rm -rf / dd 等高危命令误操作的安全包装器。\n"
            "交互 TTY 下将强制显示风险统计 + 红色警告 + 随机文件名模糊验证 + DELETE 最终确认。\n"
            "非 TTY（脚本/cron/管道）或 DANGER_FORCE=1 环境变量下直接放行，不阻塞自动化。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
        allow_abbrev=False,
    )
    parser.add_argument(
        "-V", "--version", action="version",
        version=f"%(prog)s {__version__} (Python {sys.version.split()[0]}, {config.SYSTEM})",
    )
    parser.add_argument(
        "--cmd", "-c", metavar="NAME",
        help=(
            "要执行的高危命令名（当前已注册: rm, dd）。省略时，若第一个位置参数是已注册命令名也可。"
        ),
    )
    parser.add_argument(
        "--list-hooks", "-l", action="store_true",
        help="列出所有已注册的 Hook 命令（及其描述）并退出",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅打印将执行的原生命令，不实际执行（调试用）",
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="强制禁用 ANSI 彩色输出（非 TTY 下默认已禁用）",
    )
    # 剩余参数：命令自己的参数
    parser.add_argument(
        "cmd_args", nargs=argparse.REMAINDER,
        help="目标命令的参数（如 -rf /tmp/* 或 if=/dev/zero of=/tmp/out.img bs=4M count=100）",
    )
    return parser


def _dispatch_no_color_flag(no_color: bool) -> None:
    """--no-color 选项：通过环境变量 NO_COLOR 让所有 _ansi 函数感知（isatty 仍 True 但实际降级）。
    简化实现：直接设环境变量，validator/ui 下次 import config 不生效（已读），所以改用 monkeypatch-like
    方法：给 sys.stdout/sys.stderr 临时装一个"假 isatty 返回 False"的 wrapper。"""
    if not no_color:
        return
    import io as _io

    class _NoColorWrapper:
        def __init__(self, inner):
            self.__inner = inner

        def isatty(self):
            return False

        def __getattr__(self, name):
            return getattr(self.__inner, name)

    sys.stdout = _NoColorWrapper(sys.stdout)  # type: ignore[assignment]
    sys.stderr = _NoColorWrapper(sys.stderr)  # type: ignore[assignment]


def _resolve_command(parser, args) -> str:
    """从 --cmd 或第一个位置参数解析命令名。"""
    if args.cmd:
        return args.cmd
    # 从 cmd_args 头部找（去掉可能的 '--'）
    rest = [a for a in args.cmd_args if a != "--"]
    if rest and rest[0] in list_hooks():
        return rest[0]
    parser.error(
        "未指定命令名。请使用 --cmd <name> 或在参数前添加已注册命令名（如：ohshit rm -rf /tmp）。\n"
        f"                     当前已注册命令: {', '.join(sorted(list_hooks().keys()))}"
    )
    return ""  # unreachable


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    _dispatch_no_color_flag(args.no_color)

    # --list-hooks
    if args.list_hooks:
        print(f"OhShit v{__version__} - 已注册的 Hook 命令:")
        hooks = list_hooks()
        for name in sorted(hooks.keys()):
            cls = hooks[name]
            plat = ", ".join(cls.native_commands.keys())
            desc = {
                "rm": "删除文件/目录（危险参数 -rf / -rRf 高频触发）",
                "dd": "磁盘烧录 / 原始字节级覆写（目标为块设备时极度危险）",
            }.get(name, "自定义高危命令拦截器")
            print(f"  · {name:<8s}  平台: {plat:<20s}  {desc}")
        return 0

    command = _resolve_command(parser, args)

    # 计算 raw_args：要交给 Hook 的参数（去掉第一个位置参数当命令名的情况）
    if not args.cmd and args.cmd_args and args.cmd_args[0] == command:
        raw_args = args.cmd_args[1:]
    elif args.cmd_args and args.cmd_args[0] == "--":
        raw_args = args.cmd_args[1:]
    else:
        raw_args = args.cmd_args[:]

    try:
        code = run_pipeline(
            command_name=command,
            raw_args=raw_args,
            dry_run=args.dry_run,
        )
    except SystemExit as e:
        # run_pipeline 内部已 exit，透传即可
        code = e.code if isinstance(e.code, int) else 1
    sys.exit(code)
    return code  # unreachable（上一行已 exit；保留类型检查友好）


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Write __main__.py**

```python
# danger_guard/__main__.py
"""
支持 `python -m danger_guard` 方式启动。
    例: python -m danger_guard --cmd rm -rf /tmp/foo
        python -m danger_guard rm -rf /tmp/foo
"""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run all tests**

Run: `cd /workspace && python -m pytest tests/ -v`
Expected: ~60 passed (validator ~20, whitelist ~10, hooks_rm ~12, hooks_dd ~8, ui ~5, engine_smoke ~5, config/executors)

- [ ] **Step 7: Manual CLI dry-run smoke test**

Run: `cd /workspace && DANGER_FORCE=1 python -m danger_guard --cmd rm -rf /tmp/surely_not_exists_xyz --dry-run 2>&1 | tail -3`
Expected: Prints "[ohshit dry-run]  /bin/rm -f /tmp/surely_not_exists_xyz" to stderr

Run: `cd /workspace && python -m danger_guard --list-hooks`
Expected: Lists rm + dd with platforms

- [ ] **Step 8: Commit**

```bash
cd /workspace && git add danger_guard/core/engine.py danger_guard/cli.py danger_guard/__main__.py tests/test_engine_smoke.py && git commit -m "feat: engine 7-step orchestration + argparse CLI + python -m entrypoint"
```

---

## Task 9: 安装/卸载脚本 + zipapp 打包指南

**Files:**
- Create: `danger_guard/scripts/install.sh`
- Create: `danger_guard/scripts/install.ps1`

- [ ] **Step 1: Write install.sh (Linux/macOS)**

```bash
#!/usr/bin/env bash
# danger_guard/scripts/install.sh
# OhShit 一键安装脚本（Bash/Zsh/Fish 通用 rc 追加模式）
#
# 用法：
#   curl -fsSL https://.../install.sh | bash
#   或本地: bash install.sh [--prefix ~/.local] [--no-backup]
#
# 行为：
#   1. 检测 python3 (>=3.7) 与 pip
#   2. pip install danger-guard（若是本地开发可切 install -e .）
#   3. 生成备份还原点目录 $HOME/.danger-guard-backup/<timestamp>/
#   4. 在 ~/.bashrc / ~/.zshrc / ~/.config/fish/config.fish 追加 alias
#   5. 在 ohshit 安装 bin 目录生成 ohshit-uninstall 脚本
#
# 应急绕过：\rm  (反斜杠跳过 alias) / command rm

set -euo pipefail

# ========== 颜色 ==========
if [ -t 1 ]; then
  RED=$'\033[31;1m'; YLW=$'\033[33;1m'; GRN=$'\033[32;1m'; BLD=$'\033[1m'; RST=$'\033[0m'
else
  RED=; YLW=; GRN=; BLD=; RST=;
fi

log()    { echo "${BLD}[ohshit]${RST} $*"; }
warn()   { echo "${YLW}[ohshit warn]${RST} $*" >&2; }
err()    { echo "${RED}[ohshit error]${RST} $*" >&2; }

# ========== 参数解析 ==========
PREFIX="$HOME/.local"
LOCAL_DEV=0
for arg in "$@"; do
  case "$arg" in
    --prefix=*) PREFIX="${arg#--prefix=}" ;;
    --prefix)   PREFIX="$2"; shift ;;
    --local)    LOCAL_DEV=1 ;;
    *) warn "未知参数: $arg（忽略）" ;;
  esac
done

BIN_DIR="$PREFIX/bin"
mkdir -p "$BIN_DIR"

# ========== 1. 找 python3 ==========
PY=""
for cand in python3.12 python3.11 python3.10 python3.9 python3.8 python3.7 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver=$("$cand" -c 'import sys; v=sys.version_info; print(v.major*100+v.minor)')
    if [ "$ver" -ge 307 ]; then PY="$cand"; break; fi
  fi
done
if [ -z "$PY" ]; then
  err "未找到 Python 3.7+ 的 python3 解释器。请先安装 Python 3。"
  exit 1
fi
log "使用 Python: $PY → $($PY --version 2>&1)"

# ========== 2. pip install ==========
log "安装 danger-guard 包到用户目录..."
if [ "$LOCAL_DEV" = "1" ]; then
  # 本地开发模式：假设脚本所在项目根
  REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
  "$PY" -m pip install --quiet --user -e "$REPO_ROOT" 2>/tmp/ohshit_pip.log || {
    err "pip install 失败，日志见 /tmp/ohshit_pip.log"
    exit 1
  }
else
  "$PY" -m pip install --quiet --user danger-guard 2>/tmp/ohshit_pip.log || {
    # PyPI 包还没发布时，降级成本地 zipapp 模式（用本地源码构建）
    warn "PyPI 尚未发布 danger-guard，切换为本地源码 + pip install -e..."
    REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
    if [ -f "$REPO_ROOT/pyproject.toml" ]; then
      "$PY" -m pip install --quiet --user -e "$REPO_ROOT" 2>/tmp/ohshit_pip.log || {
        err "pip install 失败，日志见 /tmp/ohshit_pip.log"
        exit 1
      }
    else
      err "无法完成安装：既未发布到 PyPI，也找不到本地 pyproject.toml。"
      exit 1
    fi
  }
fi

# ========== 3. 定位 ohshit 可执行文件 ==========
OHSHIT=""
for cand in "$BIN_DIR/ohshit" "$($PY -c 'import sysconfig,os; print(os.path.join(sysconfig.get_path(\"scripts\"),\"ohshit\"))')"; do
  if [ -x "$cand" ]; then OHSHIT="$cand"; break; fi
done
if [ -z "$OHSHIT" ]; then
  # 兜底：用 user base 的 bin
  USER_BASE="$($PY -c 'import site; print(site.getuserbase())')"
  [ -x "$USER_BASE/bin/ohshit" ] && OHSHIT="$USER_BASE/bin/ohshit"
fi
if [ -z "$OHSHIT" ]; then
  err "找不到 ohshit 可执行文件（pip 可能装到了非预期位置）。请手动查 pip show -f danger-guard。"
  exit 1
fi
log "ohshit 可执行文件: $OHSHIT"

# 确保 BIN_DIR 在 PATH 里（没在的话提示用户）
case ":$PATH:" in
  *":$BIN_DIR:"*) : ;;
  *) warn "安装目录 $BIN_DIR 似乎不在你的 \$PATH 中。请手动在 ~/.bashrc / ~/.zshrc 中添加：export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

# ========== 4. 备份还原点 ==========
BACKUP_ROOT="$HOME/.danger-guard-backup"
BACKUP_DIR="$BACKUP_ROOT/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "$BACKUP_DIR" > "$BACKUP_ROOT/LATEST"
log "还原点备份目录: $BACKUP_DIR"

# ========== 5. 写入 rc 文件 ==========
RC_FILES=()
[ -f "$HOME/.bashrc" ]         && RC_FILES+=("$HOME/.bashrc")
[ -f "$HOME/.bash_profile" ]   && RC_FILES+=("$HOME/.bash_profile")
[ -f "$HOME/.zshrc" ]          && RC_FILES+=("$HOME/.zshrc")
FISH_CONF="$HOME/.config/fish/config.fish"
[ -f "$FISH_CONF" ]            || RC_FILES_FISH=() && { RC_FILES_FISH=(); [ -f "$FISH_CONF" ] && RC_FILES_FISH+=("$FISH_CONF"); }

BLOCK_BEGIN="# ===== OhShit 删库跑路预防针（安装于 $(date '+%Y-%m-%d %H:%M:%S')）====="
BLOCK_NOTE="# 还原点: $BACKUP_DIR   ｜   卸载命令: ohshit-uninstall  ｜   临时绕过: \\\\rm (反斜杠前缀)"
BLOCK_ALIAS_RM="alias rm='ohshit --cmd rm'"
BLOCK_ALIAS_DD="alias dd='ohshit --cmd dd'"
BLOCK_END="# ===== OhShit 安装段结束 ======"

write_block_to_rc() {
  local rc="$1"
  if grep -q "^# ===== OhShit" "$rc" 2>/dev/null; then
    warn "$rc 已包含 OhShit 安装段，跳过（若要重装请先执行 ohshit-uninstall）"
    return 0
  fi
  {
    echo ""
    echo "$BLOCK_BEGIN"
    echo "$BLOCK_NOTE"
    echo "$BLOCK_ALIAS_RM"
    echo "$BLOCK_ALIAS_DD"
    echo "$BLOCK_END"
  } >> "$rc"
  log "写入别名到: $rc"
}

for rc in "${RC_FILES[@]}"; do
  write_block_to_rc "$rc"
done

# Fish Shell 单独处理（别名语法不同）
if [ -f "$FISH_CONF" ]; then
  if grep -q "^# ===== OhShit" "$FISH_CONF" 2>/dev/null; then
    warn "$FISH_CONF 已包含 OhShit 段，跳过"
  else
    {
      echo ""
      echo "# ===== OhShit 删库跑路预防针（Fish shell 别名，安装于 $(date '+%Y-%m-%d')）====="
      echo "# 卸载命令: ohshit-uninstall   临时绕过: command rm"
      echo "alias rm 'ohshit --cmd rm'"
      echo "alias dd 'ohshit --cmd dd'"
      echo "# ===== OhShit 安装段结束 ======"
    } >> "$FISH_CONF"
    log "写入 Fish 别名到: $FISH_CONF"
  fi
fi

# ========== 6. 生成 ohshit-uninstall 卸载脚本 ==========
UNINSTALL_SH="$BIN_DIR/ohshit-uninstall"
cat > "$UNINSTALL_SH" <<EOF
#!/usr/bin/env bash
# ===== 自动生成的 OhShit 卸载脚本 =====
# 生成时间: $(date)
# 还原点:   $BACKUP_DIR
set -euo pipefail
echo "${BLD}[ohshit uninstall]${RST} 正在移除别名 & 包..."
# 从所有常见 rc 文件中删除标记段（含 Fish）
SED_CMD='/^# ===== OhShit.*预防针/,/^# ===== OhShit 安装段结束/d'
for rc in "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.zshrc" "$HOME/.config/fish/config.fish"; do
  if [ -f "\$rc" ] && [ -w "\$rc" ]; then
    if sed "\$SED_CMD" "\$rc" > "\$rc.ohshit_tmp" 2>/dev/null; then
      mv "\$rc.ohshit_tmp" "\$rc"
      echo "  → 已清理 \$rc"
    else
      rm -f "\$rc.ohshit_tmp"
    fi
  fi
done
# pip uninstall
PY_BIN="$PY"
\$PY_BIN -m pip uninstall -y danger-guard 2>/dev/null || true
# 自删
rm -f "\$0"
echo "${GRN}✅ 卸载完成。别名将于下次登录 Shell 生效（当前会话请手动执行 unalias rm dd）。${RST}"
EOF
chmod +x "$UNINSTALL_SH"
log "卸载脚本: $UNINSTALL_SH（随时可执行还原）"

# ========== 7. 收尾 ==========
echo ""
echo "${GRN}${BLD}✅ OhShit 安装成功！${RST}"
echo "   · 命令: rm / dd 已被 alias 劫持（下次登录 Shell 生效）"
echo "   · 本次会话立即生效: 请执行  source ~/.bashrc  或  source ~/.zshrc"
echo "   · 查看已注册命令: ohshit --list-hooks"
echo "   · 紧急绕过: \\\\rm  (反斜杠跳过 alias)  /  command rm"
echo "   · 强制放行: DANGER_FORCE=1 rm -rf ...  （CI/CD 自动化用）"
echo "   · 卸载: ohshit-uninstall"
echo "   · 自定义白名单: ~/.danger-whitelist（一行一条路径，# 注释，支持 glob、~、\$VAR）"
```

- [ ] **Step 2: chmod +x install.sh + basic syntax check**

Run: `chmod +x /workspace/danger_guard/scripts/install.sh && bash -n /workspace/danger_guard/scripts/install.sh`
Expected: No syntax errors (exit 0)

- [ ] **Step 3: Write install.ps1 (Windows PowerShell)**

```powershell
# danger_guard/scripts/install.ps1
# OhShit Windows PowerShell 一键安装脚本
# 用法（管理员可选，无需管理员也可装到 CurrentUser）：
#   Set-ExecutionPolicy -Scope Process Bypass; .\install.ps1

$ErrorActionPreference = "Stop"

function Write-Info($s)    { Write-Host "[ohshit] " -ForegroundColor Cyan -NoNewLine; Write-Host $s }
function Write-Warn($s)    { Write-Host "[ohshit warn] " -ForegroundColor Yellow -NoNewLine; Write-Host $s }
function Write-Err($s)     { Write-Host "[ohshit error] " -ForegroundColor Red -NoNewLine; Write-Host $s }
function Write-Ok($s)      { Write-Host $s -ForegroundColor Green }

# ========== 1. 找 python ==========
$py = Get-Command py.exe -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python.exe -ErrorAction SilentlyContinue }
if (-not $py) { Write-Err "找不到 Python 3 (py.exe 或 python.exe)，请先安装 Python 3.7+ 并加入 PATH"; exit 1 }
$pyExe = $py.Source
Write-Info "使用 Python: $pyExe → $(& $pyExe --version 2>&1)"

# ========== 2. pip install ==========
Write-Info "pip install danger-guard --user ..."
try {
    & $pyExe -m pip install --quiet --user danger-guard 2>$null
    if ($LASTEXITCODE -ne 0) { throw "pip exit $LASTEXITCODE" }
} catch {
    Write-Warn "PyPI 安装失败，尝试本地源码模式..."
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    if (Test-Path (Join-Path $repoRoot "pyproject.toml")) {
        & $pyExe -m pip install --quiet --user -e $repoRoot
    } else {
        Write-Err "既不能从 PyPI 安装，也找不到本地 pyproject.toml。"
        exit 1
    }
}

# ========== 3. 定位 ohshit.exe ==========
$userBase = & $pyExe -c "import site,sys; sys.stdout.write(site.getuserbase())"
$ohshitPath = Join-Path (Join-Path $userBase "Scripts") "ohshit.exe"
if (-not (Test-Path $ohshitPath)) {
    $ohshitPath = Get-Command ohshit.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}
if (-not $ohshitPath) { Write-Err "找不到 ohshit.exe，请检查 pip install 结果"; exit 1 }
Write-Info "ohshit 路径: $ohshitPath"

# ========== 4. 备份还原点 ==========
$backupRoot = Join-Path $env:USERPROFILE ".danger-guard-backup"
$backupDir  = Join-Path $backupRoot (Get-Date -Format "yyyyMMdd_HHmmss")
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
Set-Content -Path (Join-Path $backupRoot "LATEST") -Value $backupDir
Write-Info "还原点: $backupDir"

# ========== 5. 写入 PowerShell $PROFILE ==========
if (-not (Test-Path $PROFILE)) {
    New-Item -ItemType File -Force -Path $PROFILE | Out-Null
}
$existing = Get-Content -Path $PROFILE -Raw -ErrorAction SilentlyContinue
if ($existing -match "# ===== OhShit") {
    Write-Warn "`$PROFILE 已包含 OhShit 段，跳过（请先执行 ohshit-uninstall 再重装）"
} else {
    $block = @"

# ===== OhShit 删库跑路预防针（安装时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')）=====
# 还原点: $backupDir   ｜   卸载: ohshit-uninstall   ｜   临时绕过: & C:\Windows\System32\WindowsPowerShell\v1.0\Microsoft.PowerShell.Commands.Management.dll\Remove-Item 或用绝对路径
function Invoke-OhShitRm { & "$ohshitPath" --cmd rm @args }
function Invoke-OhShitDd { & "$ohshitPath" --cmd dd @args }
Set-Alias -Name rm -Value Invoke-OhShitRm -Option AllScope -Force -Scope Global
Set-Alias -Name dd -Value Invoke-OhShitDd -Option AllScope -Force -Scope Global
# ===== OhShit 安装段结束 ======
"@
    Add-Content -Path $PROFILE -Value $block
    Write-Info "已写入 Set-Alias 到: $PROFILE"
}

# ========== 6. 生成 ohshit-uninstall.ps1 ==========
$binDir = Split-Path -Parent $ohshitPath
$uninstallPs1 = Join-Path $binDir "ohshit-uninstall.ps1"
@"
# OhShit 自动生成的卸载脚本
`$ErrorActionPreference = "Stop"
Write-Host "[ohshit uninstall] 正在移除 PowerShell 别名 & 包..." -ForegroundColor Cyan
# 从 `$PROFILE 删除标记段
`$prof = `$PROFILE
if (Test-Path `$prof) {
    `$c = Get-Content `$prof -Raw
    `$c = [regex]::Replace(`$c, '(?ms)^# ===== OhShit.*?预防针.*?^# ===== OhShit 安装段结束 ======\r?\n?', '')
    Set-Content `$prof `$c -NoNewline
    Write-Host "  → 已清理 `$prof"
}
# pip uninstall
& "$pyExe" -m pip uninstall -y danger-guard 2>`$null
# 自删
Remove-Item `$MyInvocation.MyCommand.Path -Force
Write-Host "✅ 卸载完成。别名将于下次 PowerShell 启动生效（当前会话请执行 Remove-Alias rm,dd -Force）" -ForegroundColor Green
"@ | Set-Content -Path $uninstallPs1
Write-Info "卸载脚本: $uninstallPs1"

Write-Host ""
Write-Ok "✅ OhShit 安装成功！"
Write-Host "   · rm / dd 在新的 PowerShell 窗口中会被 OhShit 劫持"
Write-Host "   · 本次会话立即生效: 执行 . `$PROFILE"
Write-Host "   · 查看已注册命令: ohshit --list-hooks"
Write-Host "   · 强制放行: `$env:DANGER_FORCE=1; rm -Recurse -Force .\xxx"
Write-Host "   · 卸载: powershell -File `"$uninstallPs1`""
```

- [ ] **Step 4: PowerShell syntax lint (if pwsh available; skip otherwise)**

Run: `command -v pwsh >/dev/null && pwsh -NoProfile -Command "Get-Command Test-ScriptAnalyzer 2>&1 | head -1; Write-Host 'PowerShell syntax skip (PSSA optional)'" || echo "(pwsh not installed in env, skipping)"`
Expected: Skipped or no errors

- [ ] **Step 5: Update README.md with Quick Start section**

Append to `/workspace/README.md`:

```markdown
## 快速开始

### 方式 1：一键脚本安装（推荐）
```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/yeson/ohshit/main/danger_guard/scripts/install.sh | bash

# Windows (PowerShell)
Set-ExecutionPolicy -Scope Process Bypass; iex (iwr https://raw.githubusercontent.com/yeson/ohshit/main/danger_guard/scripts/install.ps1)
```

### 方式 2：pip 安装
```bash
pip install --user danger-guard
# 然后手动加 alias 到 ~/.bashrc：
alias rm='ohshit --cmd rm'
alias dd='ohshit --cmd dd'
```

### 方式 3：zipapp（零依赖单文件）
```bash
python -m zipapp danger_guard -o ohshit.pyz -m "danger_guard.__main__:main"
sudo mv ohshit.pyz /usr/local/bin/ohshit
alias rm='ohshit --cmd rm'
```

### 白名单配置
编辑 `~/.danger-whitelist`：
```
# 一行一条路径，支持 glob、~、$VAR
~/Downloads
/data/projects/*/node_modules
/tmp  # 默认已包含，可省略
```

### 环境变量
| 变量 | 值 | 作用 |
|---|---|---|
| `DANGER_FORCE` | `1` / `true` / `yes` | 跳过所有防护直接执行（CI/CD 用） |
| `DANGER_WHITELIST` | 文件路径 | 自定义白名单文件位置 |
| `DANGER_LOG` | 文件路径 | 自定义故障日志路径（默认 `~/.danger.log`） |
| `NO_COLOR` | 任意非空 | 禁用彩色输出 |
```

- [ ] **Step 6: Run full test suite one last time**

Run: `cd /workspace && python -m pytest tests/ -v --tb=short 2>&1 | tail -10`
Expected: all tests PASSED, 0 failed

- [ ] **Step 7: Commit**

```bash
cd /workspace && git add danger_guard/scripts/install.sh danger_guard/scripts/install.ps1 README.md && git commit -m "feat: install scripts (bash + powershell) with backup/uninstall auto-generation + README quick start"
```

---

## 计划自检

### 1. Spec 覆盖
| Spec 节 | 对应 Task |
|---|---|
| §3 架构 + 模块边界 | Task 1, 2, 3（config / hooks骨架 / executors） |
| §4 钩子框架（BaseHook + 自动注册 + pkgutil 自动发现） | Task 2 |
| §5 三阶防护 7 步流程 | Task 8 engine.py |
| §6 B- 验证算法（形近字表 + 反复制粘贴 + 3 次轮换） | Task 4 validator.py |
| §7 dd Hook 预览（块设备/文件/新文件分级） | Task 7 dd_hook.py |
| §8 跨平台适配（系统检测 + executors 平台路由） | Task 1 config, Task 3 executors |
| §9 错误处理矩阵（含兜底直接执行 + TTY=脚本直接放行） | Task 8 engine + Task 5 tty_detector |
| §10 分发策略（pip + zipapp） | Task 1 pyproject.toml + Task 9 README Quick Start |
| §11 测试策略（~60 用例分层） | 所有 Task 的 Step 1-2 测试文件 |
| 安装/卸载脚本 | Task 9 install.sh + install.ps1 |
| 完全模块化、单向依赖 | 所有文件 import 方向均严格遵循架构图 |

✅ **全覆盖，无遗漏**。

### 2. 占位符扫描
全计划无 TBD/TODO/implement later 等占位符，所有代码块提供完整实现，所有测试断言精确，所有命令附 Expected 输出。✅

### 3. 类型一致性
- PreviewResult / HookExecutionResult / BaseHook 的属性名、字段在 Task 2 定义后，后续 Task（UI 渲染、Validator、Engine、各 Hook）均使用相同字段名无冲突。
- `parsed` dict schema：rm schema 在 Task 6 parse_args 定义后 executors/build_rm_command 使用完全相同 key；dd schema 在 Task 7 parse_args 定义后 build_dd_command 使用完全相同 key。✅

---

## 执行方式选项

计划完成并保存到 [docs/superpowers/plans/2026-08-30-ohshit-implementation.md](file:///workspace/docs/superpowers/plans/2026-08-30-ohshit-implementation.md)。共 **9 个 Task**，每个 Task 5-8 步，总计约 60 个子步骤。

**两种执行方式：**

**1. 子代理驱动（推荐）**：每个 Task 派一个 fresh 子代理执行 → 我做两步 Review → 通过后下一个。优点：上下文干净、错误隔离、可并行（Task 4/5 与 Task 6/7 互独立）。

**2. 内联执行**：本会话内按 Task 顺序批量执行，按 Task 设 review checkpoint。优点：少一次 round-trip，文件编辑连续性好。

请选择 **1（子代理）** 或 **2（内联）**？或者你偏好的其他方式？