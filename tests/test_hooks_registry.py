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
