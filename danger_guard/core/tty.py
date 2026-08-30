"""
TTY / 交互模式检测与强制覆盖判定。

核心原则：
  - 交互 TTY（用户直接在终端打字）→ 运行所有安全校验（正常模式）
  - 非交互（脚本/cron/CI管道）→ 默认自动跳过所有校验（避免阻塞自动化流水线）
  - 用户明确 DANGER_FORCE=1 或传了 --force → 跳过所有校验（强制放行）

暴露：
  - is_interactive_tty() → bool
  - is_force_overridden(cli_force_flag=False) → bool
  - should_run_checks(cli_force_flag=False) → bool
"""
import sys
import os
from danger_guard import config


# CLI 强制覆盖的 flag 名称（长选项）
FORCE_CLI_FLAGS = ("--force", "--danger-force")


def is_interactive_tty() -> bool:
    """
    判断当前进程是否在交互式 TTY 下运行。
    规则：sys.stdin.isatty() 与 sys.stdout.isatty() **同时**为 True 才算交互。
    （防止 stdin 来自管道但 stdout 打到终端的半交互状态）
    """
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        # 异常情况下保守返回 False（跳过校验比阻塞用户强）
        return False


def is_force_overridden(cli_force_flag: bool = False) -> bool:
    """
    判断是否存在"强制放行"覆盖条件（命中任一即 True）。
    优先级：
      1) CLI 调用者显式传 cli_force_flag=True → True
      2) 环境变量 DANGER_FORCE 非空且 != '0' → True
      3) sys.argv 中包含 --force / --danger-force → True
    """
    # 1) 调用方直接传的 flag（最高优先级）
    if cli_force_flag:
        return True

    # 2) 环境变量覆盖
    env_val = os.environ.get(config.FORCE_ENV, "0").strip()
    if env_val and env_val != "0":
        return True

    # 3) 命令行 argv 中含 force flag
    try:
        argv = sys.argv
    except AttributeError:
        argv = []
    for flag in FORCE_CLI_FLAGS:
        if flag in argv:
            return True

    return False


def should_run_checks(cli_force_flag: bool = False) -> bool:
    """
    综合判断：OhShit 的安全校验是否应该被执行。

    返回 True → 正常执行所有校验（默认交互终端）
    返回 False → 跳过所有校验直接执行命令

    逻辑（任一命中即跳过）：
      - is_force_overridden=True → 跳过（用户明确强制）
      - 非交互 TTY → 跳过（脚本/cron/CI 自动跳过）
    否则 → 执行校验
    """
    # 强制覆盖 → 跳过
    if is_force_overridden(cli_force_flag=cli_force_flag):
        return False

    # 非交互环境（管道/脚本/CI）→ 自动跳过，不阻塞自动化
    if not is_interactive_tty():
        return False

    return True


__all__ = [
    "is_interactive_tty",
    "is_force_overridden",
    "should_run_checks",
]
