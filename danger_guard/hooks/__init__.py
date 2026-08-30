"""danger_guard hooks registry with auto-discovery.

Public API
----------
- :class:`BaseHook` / :class:`PreviewResult` / :class:`HookExecutionResult`
  — types to subclass / consume.
- :func:`register_hook` — decorator for hooking a BaseHook subclass into
  the registry (used by concrete hook modules).
- :func:`get_hook` — retrieve a hook class by its ``name`` identifier.
- :func:`list_hooks` — list currently registered hook names.

Auto-discovery
--------------
The first time :func:`get_hook` or :func:`list_hooks` is called we walk
all modules in the ``danger_guard.hooks`` package via
:func:`pkgutil.iter_modules` and import them (side-effect: their
``@register_hook`` decorated classes enter ``_REGISTRY``).  This avoids
import-order footguns and lets third-party code drop new hook files into
this directory without touching any wiring code.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Dict, List, Type

from .base import BaseHook, HookExecutionResult, PreviewResult

# ---------------------------------------------------------------------------
# Registry internals
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, Type[BaseHook]] = {}
_LOADED = False


# ---------------------------------------------------------------------------
# Public decorator
# ---------------------------------------------------------------------------


def register_hook(cls: Type[BaseHook]) -> Type[BaseHook]:
    """Class decorator – add *cls* to the global hook registry.

    Raises
    ------
    TypeError
        If *cls* is not a subclass of :class:`BaseHook`.
    ValueError
        If the class's ``name`` attribute is empty or collides with an
        already-registered hook.
    """
    if not isinstance(cls, type) or not issubclass(cls, BaseHook):
        raise TypeError(
            f"@register_hook: {cls!r} is not a subclass of BaseHook"
        )
    if not getattr(cls, "name", None):
        raise ValueError(
            f"@register_hook: {cls!r} must set a non-empty 'name' class attribute"
        )
    if cls.name in _REGISTRY:
        raise ValueError(
            f"@register_hook: duplicate hook name {cls.name!r} "
            f"(existing: {_REGISTRY[cls.name]!r}, new: {cls!r})"
        )
    _REGISTRY[cls.name] = cls
    return cls


# ---------------------------------------------------------------------------
# Public accessors + lazy loader
# ---------------------------------------------------------------------------


def _ensure_loaded() -> None:
    """Import every submodule of danger_guard.hooks exactly once.

    Each imported module will trigger its own ``@register_hook`` calls
    as a side-effect, filling ``_REGISTRY``.
    """
    global _LOADED
    if _LOADED:
        return
    # __path__ comes from being a package; this walk is safe even when
    # the directory currently only contains __init__.py / base.py.
    for _finder, module_name, _ispkg in pkgutil.iter_modules(__path__):
        # __name__ here is "danger_guard.hooks" so we need an absolute
        # import of each sibling module.
        importlib.import_module(f"{__name__}.{module_name}")
    _LOADED = True


def get_hook(name: str) -> Type[BaseHook]:
    """Return the hook class registered as *name*, or raise KeyError."""
    _ensure_loaded()
    return _REGISTRY[name]


def list_hooks() -> List[str]:
    """Return a sorted list of currently registered hook names."""
    _ensure_loaded()
    return sorted(_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Re-exports
# ---------------------------------------------------------------------------

__all__ = [
    "BaseHook",
    "PreviewResult",
    "HookExecutionResult",
    "register_hook",
    "get_hook",
    "list_hooks",
]
