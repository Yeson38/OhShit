"""Base hook abstractions and result dataclasses for danger_guard.

Defines the BaseHook ABC that all concrete hooks (rm, dd, etc.) must
implement, plus the PreviewResult and HookExecutionResult dataclasses
used to communicate analysis and execution outcomes back to the guard
orchestration layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PreviewResult:
    """Output of BaseHook.preview() – describes what *would* happen.

    Attributes
    ----------
    affected_count:
        Number of filesystem objects (files, dirs, partitions, …) that
        would be touched.
    total_size_bytes:
        Aggregate byte size of the affected payload.  0 when unknown or
        not applicable (e.g. destroying a raw device).
    sample_items:
        Short representative list of paths / targets so the user can
        sanity-check the scope.  Length MUST be <= affected_count.
    target_scope:
        Human-readable description of the overall scope (e.g. the
        original path pattern, device node, or shell scope string).
    risk_level:
        Integer in 0..5, where 0 is harmless (e.g. dry-run that never
        writes) and 5 is irreversible (e.g. `dd` writing to a raw disk).
    validation_pool:
        Full list of targets that the interactive confirmation prompt
        may check the user input against.  Typically equals or superset
        of sample_items.
    extra_warnings:
        Arbitrary warning strings surfaced to the user before approval.
    """

    affected_count: int
    total_size_bytes: int
    sample_items: Sequence[str]
    target_scope: str
    risk_level: int
    validation_pool: Sequence[str]
    extra_warnings: Sequence[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # --- field validation ------------------------------------------------
        if not isinstance(self.affected_count, int) or self.affected_count < 0:
            raise ValueError("affected_count must be a non-negative int")
        if not isinstance(self.total_size_bytes, int) or self.total_size_bytes < 0:
            raise ValueError("total_size_bytes must be a non-negative int")
        if not isinstance(self.risk_level, int) or not (0 <= self.risk_level <= 5):
            raise ValueError("risk_level must be an int between 0 and 5 (inclusive)")
        if not isinstance(self.target_scope, str) or not self.target_scope:
            raise ValueError("target_scope must be a non-empty string")
        # sample_items / validation_pool / extra_warnings 必须是 Sequence of str
        for attr_name, val in (
            ("sample_items", self.sample_items),
            ("validation_pool", self.validation_pool),
            ("extra_warnings", self.extra_warnings),
        ):
            if not isinstance(val, (list, tuple)) or not all(isinstance(x, str) for x in val):
                raise ValueError(f"{attr_name} must be a list/tuple of str")
        # sample_items 长度不能超过 affected_count
        if len(self.sample_items) > self.affected_count:
            raise ValueError(
                f"sample_items length ({len(self.sample_items)}) exceeds "
                f"affected_count ({self.affected_count})"
            )


@dataclass
class HookExecutionResult:
    """Output of BaseHook.execute() – whether the native call succeeded.

    Attributes
    ----------
    success:
        True iff the delegated command completed without error from the
        guard's perspective.
    exit_code:
        Exit code returned by the underlying OS process (or synthetically
        produced for in-process hooks).
    message:
        Optional human-readable note (stderr summary, skip-reason, etc.).
    """

    success: bool
    exit_code: int
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Hook ABC
# ---------------------------------------------------------------------------


class BaseHook(ABC):
    """Abstract base class for every danger_guard hook.

    Subclasses MUST be decorated with ``@register_hook`` so the module
    auto-discovery mechanism can find them and insert them into the
    global hook registry.

    Class attributes (overridden by subclasses)
    -------------------------------------------
    name: str
        Stable machine-readable identifier (e.g. ``"rm"``, ``"dd"``).
        Used by ``get_hook()`` and config bindings.  Must be unique.
    native_commands: tuple[str, ...]
        Shell command tokens that this hook understands.  Example:
        ``("rm", "del", "unlink")``.  Used by the guard dispatcher to
        map a raw argv to a hook.
    """

    # Subclasses MUST override these two class attributes.
    name: str = ""
    native_commands: tuple = ()

    # ----- public helpers (NOT @abstractmethod – do NOT override) -----------

    @classmethod
    def is_natively_supported(cls, command_token: str) -> bool:
        """Return True if *command_token* is listed in native_commands.

        This method is intentionally final – subclasses should express
        their supported commands purely via the ``native_commands``
        class attribute.
        """
        if not isinstance(cls.native_commands, (tuple, list, set, frozenset)):
            return False
        return command_token in cls.native_commands

    # ----- abstract contract -----------------------------------------------

    @abstractmethod
    def parse_args(self, argv: Sequence[str]) -> Dict[str, Any]:
        """Parse a raw argv vector into a structured options dict.

        Implementations should mirror the semantics of the underlying
        native command (e.g. GNU ``rm``) as closely as possible so the
        guard's preview accurately reflects what would happen.

        Parameters
        ----------
        argv:
            The argv *after* the command name itself.  Example: for a
            shell line ``rm -rf /tmp/foo``, argv equals
            ``["-rf", "/tmp/foo"]``.

        Returns
        -------
        dict
            A dict consumed by :meth:`preview` / :meth:`execute`.  The
            exact schema is hook-specific but always JSON-serialisable.
        """
        ...

    @abstractmethod
    def preview(self, parsed_opts: Dict[str, Any]) -> PreviewResult:
        """Compute the impact *without* mutating anything.

        Implementations MUST be side-effect-free.
        """
        ...

    @abstractmethod
    def execute(
        self,
        parsed_opts: Dict[str, Any],
        confirmed_items: Optional[Sequence[str]] = None,
    ) -> HookExecutionResult:
        """Perform the actual (dangerous) operation after approval.

        Parameters
        ----------
        parsed_opts:
            The same dict returned by :meth:`parse_args`.
        confirmed_items:
            Optional explicit list of items the user confirmed.  When
            provided the hook MUST restrict itself to this subset.
        """
        ...
