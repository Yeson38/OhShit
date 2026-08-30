"""danger_guard.__main__ —— 让 `python -m danger_guard` / zipapp / shebang 都能跑。"""
import sys
import argparse

from danger_guard import __version__
from danger_guard.core.engine import run_pipeline, detect_command, EXIT_SIGINT
from danger_guard.hooks import list_hooks, _ensure_loaded, get_hook


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="dang",
        description="OhShit 删库跑路预防针：防止 rm/dd 等高危命令误操作",
        usage="%(prog)s [--dry-run] [--force] [--list-hooks] [--] <command> <args...>",
    )
    ap.add_argument("--version", action="version", version=f"dang {__version__}")
    ap.add_argument("--dry-run", action="store_true", help="只预览 + 验证，不真正执行")
    ap.add_argument("--force", action="store_true", dest="force",
                    help=f"跳过 B- 验证（等同于设置 DANGER_FORCE=1）")
    ap.add_argument("--list-hooks", action="store_true", dest="list_hooks", help="列出当前注册的 hooks")
    ap.add_argument("rest", nargs=argparse.REMAINDER, help="子命令和参数（可用 -- 分隔，如：dang -- rm -rf /tmp/xyz）")
    return ap


def main(argv=None) -> int:
    try:
        raw_rc = _main_inner(argv)
    except KeyboardInterrupt:
        msg = "\n[ohshit] ✅ 已取消（Ctrl+C）。操作未执行。"
        try:
            print(msg, file=sys.stderr)
            sys.stderr.flush()
        except Exception:
            pass
        raw_rc = EXIT_SIGINT
    except SystemExit as se:
        raw_rc = int(se.code) if isinstance(se.code, int) else 2
    except Exception as e:   # pragma: no cover —— 最后保险
        print(f"[ohshit] 未预期的错误: {type(e).__name__}: {e}", file=sys.stderr)
        raw_rc = 1
    return normalize_exit_code(raw_rc)


# Windows 下 conhost 有时把 Ctrl+C 进程退出码写成 NTSTATUS：
#   STATUS_CONTROL_C_EXIT = 0xC000013A (unsigned 3221225786 / signed -1073741510)
# 统一翻译成 shell 约定的 SIGINT rc=130(128+2)。
_NTSTATUS_CONTROL_C_EXIT_CODES = frozenset([
    -1073741510,            # signed 32-bit
    3221225786,             # unsigned 32-bit
    0xC000013A,             # Python 平台可能按无符号 int 上报
])


def normalize_exit_code(rc: int) -> int:
    if rc in _NTSTATUS_CONTROL_C_EXIT_CODES:
        return EXIT_SIGINT
    # Python 在 Windows 偶尔也把负值（signed overflow 超过 int 范围）当大正数返回，
    # 兜底：按模 2**32 映射一次再看
    try:
        if (rc & 0xFFFFFFFF) in _NTSTATUS_CONTROL_C_EXIT_CODES:
            return EXIT_SIGINT
    except Exception:
        pass
    # 保证 rc 非负（shell 惯例）
    if rc < 0:
        return 128 + min(255, -rc) if (-rc) < 256 else 1
    return rc


def _main_inner(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    ns = parser.parse_args(argv)

    if ns.list_hooks:
        _ensure_loaded()
        items = list_hooks()
        print(f"已注册 {len(items)} 个 hook:")
        for name in items:
            cls = get_hook(name)
            inst = cls()
            print(f"  - {name}")
            print(f"      原生命令名: {', '.join(inst.native_commands) if hasattr(inst, 'native_commands') else '(none)'}")
        return 0

    rest = list(ns.rest)
    # 去掉 REMAINDER 可能自带的 "--"
    if rest and rest[0] == "--":
        rest = rest[1:]
    if not rest:
        parser.error("缺少子命令。用法: dang [--dry-run] [--force] -- <command> <args...>  (尝试：dang --list-hooks)")
        return 2

    name, raw_args = detect_command(rest)
    if not name:
        parser.error(f"无法从参数中识别命令: {rest}")
        return 2

    return run_pipeline(name, raw_args, dry_run=ns.dry_run, cli_force_flag=ns.force)


if __name__ == "__main__":
    sys.exit(main())
