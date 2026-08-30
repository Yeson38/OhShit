"""danger_guard.__main__ —— 让 `python -m danger_guard` / zipapp / shebang 都能跑。"""
import sys
import argparse

from danger_guard import __version__
from danger_guard.core.engine import run_pipeline, detect_command
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
