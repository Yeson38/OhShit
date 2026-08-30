"""OhShit engine：7 步编排（预览→白名单→TTY→红框→B-验证→执行）"""
import os
import sys
from typing import List, Optional, Tuple

from danger_guard.hooks import get_hook, list_hooks, _ensure_loaded
from danger_guard.hooks.base import BaseHook, HookExecutionResult
from danger_guard.core import tty as tty_core
from danger_guard.core import whitelist as whitelist_core
from danger_guard.core import ui as ui_core
from danger_guard.core.validator import run_validation_loop
from danger_guard import config
from danger_guard.executors import dispatch_exec


# shell 约定：Ctrl+C → 进程收到 SIGINT → returncode = 128 + 2 = 130
EXIT_SIGINT = 130


def detect_command(argv: List[str]) -> Tuple[str, List[str]]:
    """
    从参数中识别命令名和剩余参数。

    模式 A（子命令/包装器式）:
        ohshit rm -rf /tmp/a        → "rm", ["-rf","/tmp/a"]
        python -m danger_guard dd if=/dev/zero → "dd", ["if=/dev/zero", ...]

    模式 B（直接 hook 名前缀）:
        /usr/local/bin/rm_wrapper ... 或者 alias 直接调用，但第一个 token 是 "/bin/rm" 时剥路径。
    """
    if not argv:
        return "", []

    _ensure_loaded()  # 先注册所有 hooks，这样才能匹配 native_commands

    # 遍历 argv 的第一个 token：如果它匹配某 hook 的 name 或 native_commands 就走它
    first = argv[0]
    # 可能是路径 "/bin/rm" → basename
    base = os.path.basename(first)

    # 先尝试精确匹配某个 hook name
    if base == "danger_guard" or base.endswith("dang") or base.endswith("ohshit") or base.startswith("danger"):
        # CLI wrapper 形式，下一个 token 才是命令名
        rest = argv[1:]
        if not rest:
            return "", []
        c2 = os.path.basename(rest[0])
        hook2 = _match_hook_by_name_or_native(c2)
        if hook2 is not None:
            return hook2.name, rest[1:]
        return c2, rest[1:]

    hook = _match_hook_by_name_or_native(base)
    if hook is not None:
        return hook.name, argv[1:]
    # 最后 fallback：first 就是 hook 名字符串（还没出现的新 hook 名也行？让后面 get_hook 报错）
    return base, argv[1:]


def _match_hook_by_name_or_native(tok: str) -> Optional[BaseHook]:
    try:
        cls = get_hook(tok)  # name 精确匹配
        return cls()
    except (KeyError, ValueError):
        pass
    # list_hooks() 返回 List[str]，遍历每个 name 取 class 查 native_commands
    for hook_name in list_hooks():
        cls = get_hook(hook_name)
        h = cls()
        if tok in getattr(h, "native_commands", ()):
            return h
    return None


def run_pipeline(
    command_name: str,
    raw_args: List[str],
    dry_run: bool = False,
    cli_force_flag: bool = False,
) -> int:
    """
    7 步编排。返回 exit_code。
    Step 1. 解析参数
    Step 2. 受影响对象预览（预览失败 → 报错 1）
    Step 3. Whitelist（白名单命中 → 放行 return 0）
    Step 4. TTY / force 判断（非交互且不 override → 跳过所有保护，直接 dispatch）
    Step 5. 红色警告框 + 预览摘要
    Step 6. B- 验证（force override → 跳过；dry_run → 仍跑验证但不执行）
    Step 7. 执行
    顶层保证：任何 Ctrl+C / SystemExit 都不打 Traceback，返回对应 rc（SIGINT=130）。
    """
    try:
        return _pipeline_inner(command_name, raw_args, dry_run=dry_run, cli_force_flag=cli_force_flag)
    except KeyboardInterrupt:
        # 兜底：validator 已经吞了 KBI，但 Step 1~4 或 Step 7 execute 期间也可能被 Ctrl+C。
        msg = "\n[ohshit] ✅ 已取消（Ctrl+C）。操作未执行。"
        try:
            if ui_core.color_supported():
                # 用 ui 里的颜色（若 color_supported False 直接原样字符串即可）
                from danger_guard.core.ui import _red, _bold
                msg = "\n" + _red(_bold("[ohshit] ✅ 已取消（Ctrl+C）。操作未执行。"))
            print(msg, file=sys.stderr)
            sys.stderr.flush()
        except Exception:
            print(msg, file=sys.stderr)
        return EXIT_SIGINT
    except SystemExit as se:
        # argparse 的 .error() 本身也抛 SystemExit(2)，这里透传 rc
        return int(se.code) if isinstance(se.code, int) else 2


def _pipeline_inner(
    command_name: str,
    raw_args: List[str],
    dry_run: bool,
    cli_force_flag: bool,
) -> int:
    # Step 1: hook lookup + parse
    try:
        hook_cls = get_hook(command_name)
        hook: BaseHook = hook_cls()
    except (KeyError, ValueError) as e:
        print(f"[ohshit] 未知命令: {command_name}. 使用 --list-hooks 查看支持的命令。", file=sys.stderr)
        return 2

    parsed = hook.parse_args(raw_args)

    # Step 2: preview
    try:
        preview = hook.preview(parsed)
    except Exception as e:
        print(f"[ohshit] 预览阶段异常: {e}", file=sys.stderr)
        return 1

    # Step 3: Whitelist 放行
    wl = whitelist_core.load_all_whitelist()
    any_whitelisted = False
    for it in preview.sample_items:
        if whitelist_core.is_whitelisted_path(it, wl):
            any_whitelisted = True
            break
    # 另外检查 parsed.paths（rm hook 才有）
    for p in getattr(parsed, "paths", []) or []:
        if whitelist_core.is_whitelisted_path(p, wl):
            any_whitelisted = True
            break
    # dd 的 of/if
    dd_of = getattr(parsed, "dd_of", None)
    dd_if = getattr(parsed, "dd_if", None)
    if dd_of and whitelist_core.is_whitelisted_path(dd_of, wl):
        any_whitelisted = True
    if dd_if and whitelist_core.is_whitelisted_path(dd_if, wl):
        # 输入白名单不意味着输出白名单，只有都白名单才放行
        pass
    if any_whitelisted and preview.risk_level == 1:
        print(f"[ohshit] 白名单路径，直接放行（risk=1）")
        exec_result = hook.execute(parsed, dry_run=dry_run)
        _log_execution(command_name, raw_args, preview, exec_result)
        return exec_result.exit_code

    # Step 4: TTY 检测 - 非交互且不 override → 跳过保护直接执行
    if not tty_core.should_run_checks(cli_force_flag=cli_force_flag):
        if tty_core.is_force_overridden(cli_force_flag=cli_force_flag):
            # force：仍执行，但跳过验证
            pass  # 不跳过，继续往下，只是会在 Step 6 跳过验证
        else:
            # 真正的非交互管道模式 → 直接 dispatch
            exec_result = hook.execute(parsed, dry_run=dry_run)
            _log_execution(command_name, raw_args, preview, exec_result)
            return exec_result.exit_code

    # Step 5: UI 红框 + 预览
    print()
    box = ui_core.warning_box(
        title="高风险操作 WARNING",
        message_lines=[
            f"命令: {command_name} {' '.join(raw_args)}",
            f"目标范围: {preview.target_scope}",
            f"受影响对象: {preview.affected_count} 项",
            f"估算总大小: {ui_core.human_size(preview.total_size_bytes) if preview.total_size_bytes else '未知'}",
            f"风险等级: {'🔴 高 (3)' if preview.risk_level>=3 else '🟡 中 (2)' if preview.risk_level==2 else '🟢 低 (1)'}",
        ] + [f"⚠ {w}" for w in (preview.extra_warnings or [])],
        risk_level=preview.risk_level,
    )
    print(box)
    print(ui_core.preview_summary(
        header="受影响对象示例",
        affected_count=preview.affected_count,
        total_size_bytes=preview.total_size_bytes,
        target_scope=preview.target_scope,
        sample_items=list(preview.sample_items),
        risk_level=preview.risk_level,
    ))

    # Step 6: B- 验证（force override 跳过）
    force_skip = tty_core.is_force_overridden(cli_force_flag=cli_force_flag)
    if force_skip:
        print(f"[ohshit] ✘ 跳过 B- 验证（{config.FORCE_ENV}=1 或 CLI --force），请确认你真的懂！")
    else:
        ok, _ = run_validation_loop(list(preview.validation_pool), max_attempts=3)
        if not ok:
            print("[ohshit] ✘ 未通过 B- 验证，操作已中止。按 Ctrl+C 随时中止。", file=sys.stderr)
            return 1

    # Step 7: execute
    exec_result = hook.execute(parsed, dry_run=dry_run)
    _log_execution(command_name, raw_args, preview, exec_result)
    return exec_result.exit_code


def _log_execution(command_name, raw_args, preview, result: HookExecutionResult):
    """最小化写入 ~/.ohshit-executions.log，不阻断主流程（失败静默）。"""
    try:
        with open(config.LOG_PATH, "a", encoding="utf-8") as f:
            import json
            import datetime
            f.write(json.dumps({
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "cmd": command_name,
                "args": raw_args,
                "count": preview.affected_count,
                "size": preview.total_size_bytes,
                "scope": preview.target_scope,
                "risk": preview.risk_level,
                "ok": result.success,
                "rc": result.exit_code,
                "msg": result.message,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
