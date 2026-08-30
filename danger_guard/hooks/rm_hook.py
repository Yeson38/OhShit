"""危险包装器：rm hook。支持 parse_args/preview/execute 三重流程。"""
import os
import sys
import shlex
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from danger_guard.hooks.base import BaseHook, PreviewResult, HookExecutionResult
from danger_guard.hooks import register_hook
from danger_guard import config
from danger_guard.executors import dispatch_exec


@dataclass
class RmParsed:
    recursive: bool = False
    force: bool = False
    verbose: bool = False
    interactive: str = ""      # "" / "once" / "always"
    preserve_root: str = ""    # "" / "all"
    no_preserve_root: bool = False
    one_file_system: bool = False
    extra_flags: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)


@register_hook
class RmHook(BaseHook):
    name = "rm"
    native_commands = ("rm",)

    # ---------- parse_args ----------
    def parse_args(self, raw_args: List[str]) -> RmParsed:
        """把 `rm -rf --preserve-root=all a/ b/` 这种 POSIX 参数解析成 RmParsed。"""
        p = RmParsed()
        posix_only = [a for a in raw_args if a != "--"]  # 简化，-- 之后不再 flag
        i = 0
        while i < len(posix_only):
            a = posix_only[i]
            if a.startswith("--"):
                # long flag
                key = a[2:]
                eq = key.find("=")
                if eq != -1:
                    k, v = key[:eq], key[eq+1:]
                else:
                    k, v = key, None
                self._apply_long(p, k, v)
            elif a.startswith("-") and a != "-":
                # short: "-rfvI"
                chs = a[1:]
                skip_consumed = 0
                for idx, ch in enumerate(chs):
                    if skip_consumed > 0:
                        skip_consumed -= 1
                        continue
                    extra = self._apply_short(p, ch, chs[idx+1:], posix_only[i+1:] if idx+1 >= len(chs) else None)
                    if extra == 1 and idx+1 < len(chs):
                        # rest of this flag string is the value (unusual for rm)
                        break
            else:
                p.paths.append(a)
            i += 1
        return p

    def _apply_long(self, p, k, v):
        # 长选项：recursive / force / verbose / interactive / preserve-root / no-preserve-root / one-file-system
        if k in ("recursive", "R", "r"):
            p.recursive = True
        elif k == "force" or k == "f":
            p.force = True
        elif k == "verbose" or k == "v":
            p.verbose = True
        elif k in ("interactive", "I", "i"):
            if k == "I" or (v is None and k == "interactive"):
                p.interactive = "once"
            elif k == "i":
                p.interactive = "always"
            else:
                p.interactive = v or "once"
        elif k == "preserve-root":
            p.preserve_root = v or "all"
        elif k == "no-preserve-root":
            p.no_preserve_root = True
        elif k == "one-file-system":
            p.one_file_system = True
        else:
            if v is None:
                p.extra_flags.append(f"--{k}")
            else:
                p.extra_flags.append(f"--{k}={v}")

    def _apply_short(self, p: RmParsed, ch: str, rest: str, after):
        # return 0 or N: means next N tokens are consumed
        if ch == "r" or ch == "R":
            p.recursive = True
        elif ch == "f":
            p.force = True
        elif ch == "v":
            p.verbose = True
        elif ch == "i":
            p.interactive = "always"
        elif ch == "I":
            p.interactive = "once"
        elif ch == "d":
            p.extra_flags.append("-d")
        elif ch == "h":
            p.extra_flags.append("-h")  # rm -h is help-or-human readable? not in POSIX rm
        else:
            p.extra_flags.append(f"-{ch}")
        return 0

    # ---------- preview ----------
    def preview(self, parsed: RmParsed) -> PreviewResult:
        total_count = 0
        total_size = 0
        samples: List[str] = []
        all_real_items: List[str] = []
        warnings: List[str] = []

        for path in parsed.paths:
            p = Path(path)
            if p.is_symlink():
                # symlink：只删 symlink 本身，不 follow
                total_count += 1
                try:
                    st = p.lstat()
                    total_size += st.st_size
                except OSError:
                    pass
                all_real_items.append(str(p))
            elif p.is_file():
                total_count += 1
                try:
                    st = p.stat()
                    total_size += st.st_size
                except OSError:
                    pass
                all_real_items.append(str(p))
            elif p.is_dir():
                if not parsed.recursive:
                    warnings.append(f"rm: 目录 '{p}' 但未加 -r/-R → 原生 rm 会失败，ohshit 仍放行但风险低")
                    all_real_items.append(str(p) + "/")
                else:
                    for root, dirs, files in os.walk(p, followlinks=False, onerror=lambda e: warnings.append(str(e))):
                        for d in dirs:
                            full = os.path.join(root, d)
                            total_count += 1
                            all_real_items.append(full)
                        for f in files:
                            full = os.path.join(root, f)
                            total_count += 1
                            try:
                                st = os.stat(full)
                                total_size += st.st_size
                            except OSError:
                                pass
                            all_real_items.append(full)
            elif not p.exists():
                warnings.append(f"路径不存在: {p}")

        # samples 取所有真实 item 前 10
        samples = all_real_items[:10]
        # target_scope：最长公共前缀
        target_scope = self._lcp([str(Path(x)) for x in parsed.paths]) if parsed.paths else "<none>"
        if not target_scope:
            target_scope = "<none>"
        # risk_level
        risk = self._calc_risk(total_count, total_size, parsed)
        # validation_pool：取 3-5 个最长 basename（有差异）
        pool = self._pick_validation_pool(all_real_items, 5)
        return PreviewResult(
            affected_count=total_count,
            total_size_bytes=total_size,
            sample_items=samples,
            target_scope=target_scope,
            risk_level=risk,
            validation_pool=pool,
            extra_warnings=warnings,
        )

    @staticmethod
    def _lcp(items: List[str]) -> str:
        if not items:
            return ""
        s, *rest = items
        for i, ch in enumerate(s):
            for r in rest:
                if i >= len(r) or r[i] != ch:
                    return s[:i]
        return s

    @staticmethod
    def _pick_validation_pool(all_real: List[str], n: int) -> List[str]:
        # 对 path 取 basename，按长度降序取 n 个不重复的，若不足 3 个则 pad 成随机常见扩展名
        import random
        seen = set()
        picked: List[str] = []
        sorted_items = sorted(all_real, key=lambda x: -len(os.path.basename(x)))
        for it in sorted_items:
            bn = os.path.basename(it)
            if not bn or bn in seen:
                continue
            seen.add(bn)
            picked.append(bn)
            if len(picked) >= n:
                break
        while len(picked) < 3:
            pads = ["Report_Final.docx", "customer_2026.sql", "photo.jpg", "thesis.pdf"]
            cand = random.choice(pads)
            if cand not in picked:
                picked.append(cand)
        return picked

    @staticmethod
    def _calc_risk(count: int, size: int, parsed: RmParsed) -> int:
        # 风险 1-3：3=高；递归目录或 size>1GB 或 >1000 items
        if any(p in ("", "/") for p in parsed.paths):
            return 3
        if any(p in ("/", "/home", "/root", "/etc", "/var", "/usr", "/boot") for p in parsed.paths):
            return 3
        if count >= 1000 or size >= 1024**3:
            return 3
        if count >= 50 or size >= 100 * 1024**2 or parsed.recursive:
            return 2
        return 1

    # ---------- execute ----------
    def execute(
        self,
        parsed: RmParsed,
        confirmed_items: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> HookExecutionResult:
        # 注意：dispatch_exec / posix_exec.exec_rm 内部使用 parsed.get(...)，
        # 因此必须把 dataclass 转成 dict 后再传入。
        parsed_dict = asdict(parsed)
        return dispatch_exec("rm", parsed_dict, dry_run)
