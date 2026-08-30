"""
danger_guard.core.keystroke — 跨平台逐字符带时间戳的"读整行"。

为何不用 sys.stdin.readline()？
  - Windows PowerShell（启用 PSReadLine 时）的 Ctrl+V / 右键"粘贴"在 conhost 内层一次性
    把字符写进 console 输入缓冲区，Python stdin.readline() 在用户按 Enter 之前看到的
    会是"一下全到"的多字符；更极端情况下 PSReadLine 会在 Python 侧 readline() 启动前
    自己把粘贴吃掉（表现：readline() 只读得到 '\n'，粘贴内容是空）。
  - POSIX 侧也有 bracketed paste + 写入整段 stdin 的"管道式粘贴"。

解决方案：逐字符读（Windows 走 msvcrt.getwch() / POSIX 走 termios VMIN=1 阻塞单字），
记录每个字符到达的相对时刻，返回 (line, dts_ms, total_ms)。调用方据此检测"字符到达
burst（间隔 < TH ms 且连续 ≥ N 个）= 粘贴嫌疑"。

行为约定：
  - 如果 stdin 不是 TTY / 缺少底层模块 / 读失败 → 自动回退到 sys.stdin.readline()，
    返回 dts_ms=[]、total_ms=None，调用方需要放过"逐字 burst"检测，只保留
    Bracketed Paste marker + 整行 elapsed < 120 ms 两条检测。
  - Ctrl+C（Windows: \x03 / POSIX: SIGINT）一律抛 KeyboardInterrupt，让上层 validator
    去抓并标记 cancelled=True。
"""
import os
import sys
import time
from typing import Tuple, List, Optional, Callable


# ------- 平台常量 -------
IS_WINDOWS = sys.platform.startswith("win") or (os.name == "nt")
# 逐字 burst 的"粘贴嫌疑"判定阈值：
#   - 人工打字：字符间间隔 40~200 ms（熟练手速）
#   - 粘贴 / PSReadLine 注入：字符间间隔通常 0~1 ms，偶到 3 ms
BURST_DT_MS = 4           # 单字符间 < 4 ms 视为"粘来的"
BURST_MIN_RUN = 3         # 连续 3 个以上的 <BURST_DT_MS 才触发（防止第一个字符偶尔快点）


# ------- 对外主 API -------

def read_line_timed(
    echo: bool = True,
    _getch_fn: Optional[Callable[[], str]] = None,
    _echo_fn: Optional[Callable[[str], None]] = None,
    _monotonic_ms_fn: Optional[Callable[[], int]] = None,
) -> Tuple[str, List[int], Optional[int]]:
    """
    逐字符读取一整行（以 Enter/CR/LF 结束），带时间戳。

    :param echo: 是否回显读到的字符到 stdout（默认 True）。
    :return: (line_without_newline, list_of_dt_ms_between_chars, total_elapsed_ms_or_None)
             当底层回退到 stdin.readline() 时 dt_ms=[], total=None。
    :raises KeyboardInterrupt: 用户按 Ctrl+C（Windows 读得 \x03 或 POSIX signal）。
    """
    # ---- stdin 不是真 TTY → 直接回退（管道/重定向/脚本里）
    # 但如果调用方手动注入了 _getch_fn（比如测试注入），不管是不是 TTY 都走逐字分支。
    if _getch_fn is None and not _stdin_is_tty():
        return _fallback_readline()

    monotonic_ms = _monotonic_ms_fn if _monotonic_ms_fn else _default_monotonic_ms
    getch = _getch_fn if _getch_fn else None
    echo_char = _echo_fn if _echo_fn else (lambda s: sys.stdout.write(s))

    # ---- 取平台依赖的"单字读取器" ----
    if getch is None:
        try:
            getch = _make_getch()
        except Exception:
            return _fallback_readline()

    buf: List[str] = []
    dts: List[int] = []
    start = monotonic_ms()
    last = start

    while True:
        try:
            ch = getch()  # 应阻塞到有字；Ctrl+C 内部应抛 KeyboardInterrupt（或返回 \x03 让我们抛）
        except KeyboardInterrupt:
            raise
        except EOFError:
            # stdin EOF → 读了啥返回啥，外层 validator 会按空串处理
            raw = "".join(buf)
            total = monotonic_ms() - start if buf else 0
            return raw, dts, total

        now = monotonic_ms()
        dt = now - last

        if ch == "\x03":        # ^C
            raise KeyboardInterrupt()
        if ch in ("\r", "\n"):  # Enter
            if echo:
                echo_char("\n")
                sys.stdout.flush()
            break
        if ch in ("\b", "\x7f"):  # Backspace（Win 常发 \b，POSIX raw 发 \x7f）
            if buf:
                buf.pop()
                if echo:
                    echo_char("\b \b")
                    sys.stdout.flush()
            # backspace 不计入 dts，也不推进 last（让下一个字符的 dt 从 last 开始算）。
            # 这样：a b BS c → dts 只有 [a_dt, c_dt]。
            continue
        if ch == "\x04":        # ^D / EOF（POSIX raw 下才会出现）
            raw = "".join(buf)
            return raw, dts, (now - start)
        if ch == "\x16":        # ^V：吞掉，不计 dts，不推进 last
            continue
        if ch in ("\x00", "\xe0"):
            # Windows msvcrt 特殊前置：吞下一扫描码。不计 dts，不推进 last
            try:
                getch()
            except Exception:
                pass
            continue
        # ---- 普通字符 ----
        buf.append(ch)
        dts.append(dt)
        last = now              # 只在有普通字符时推进"上次时间戳"
        if echo:
            echo_char(ch)
            sys.stdout.flush()

    raw = "".join(buf)
    total = monotonic_ms() - start
    return raw, dts, total


# ------- 粘贴嫌疑（burst 模式）判定（独立函数方便单测）-------

def is_burst_paste(dts_ms: List[int]) -> bool:
    """给定逐字间隔，判断是否存在"连续 N 个字符到达过快"（粘贴特征）。"""
    if len(dts_ms) < BURST_MIN_RUN:
        return False
    run = 0
    for dt in dts_ms:
        if dt < BURST_DT_MS:
            run += 1
            if run >= BURST_MIN_RUN:
                return True
        else:
            run = 0
    return False


def paste_reason_burst(dts_ms: List[int]) -> str:
    """把 burst 序列格式化成一句可读提示。"""
    if not dts_ms:
        return ""
    fast = sum(1 for d in dts_ms if d < BURST_DT_MS)
    peak = min(dts_ms) if dts_ms else 0
    return (
        f"逐字时序检测：共 {fast}/{len(dts_ms)} 个字符间隔 < {BURST_DT_MS} ms"
        f"（最快 {peak} ms），典型粘贴模式"
    )


# ------- 平台内部：构造单字 reader -------

def _make_getch() -> Callable[[], str]:
    if IS_WINDOWS:
        import msvcrt  # type: ignore[import-not-found]

        def _w_getch() -> str:
            # getwch() 返回 str 长度 1 的 Unicode（wide）字符。
            # 对 Ctrl+C（\x03）msvcrt 也会返回 \x03；我们在主循环里统一抛。
            ch = msvcrt.getwch()
            return ch
        return _w_getch
    else:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_attrs = termios.tcgetattr(fd)
        raw_attrs = termios.tcgetattr(fd)
        # c_lflag: 关 ICANON(canonical)、ECHO；c_cc[VMIN]=1, VTIME=0 阻塞单字
        raw_attrs[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP | termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON)
        raw_attrs[1] &= ~termios.OPOST
        raw_attrs[2] &= ~(termios.CSIZE | termios.PARENB)
        raw_attrs[2] |= termios.CS8
        raw_attrs[3] &= ~(termios.ISIG | termios.ICANON | termios.ECHO)
        raw_attrs[6][termios.VMIN] = 1
        raw_attrs[6][termios.VTIME] = 0
        # 注意：ISIG 关掉后 ^C 不会被终端翻译为 SIGINT，而是原样传给我们(\x03)——
        # 主循环看到 \x03 就抛 KeyboardInterrupt，行为一致。

        def _posix_getch() -> str:
            # 每次进入读之前切 raw，读完回退。这样就算中途抛异常也能尽量还原
            # （如果上层也没回退，还有 finally in caller 兜底）。
            try:
                termios.tcsetattr(fd, termios.TCSANOW, raw_attrs)
                ch = sys.stdin.read(1)
                if ch == "":
                    raise EOFError()
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSANOW, old_attrs)
        return _posix_getch


# ------- 小工具 -------

def _stdin_is_tty() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def _default_monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


def _fallback_readline() -> Tuple[str, List[int], Optional[int]]:
    """非 TTY / 平台缺失 → 读一行。dts=[], total=None。"""
    line = sys.stdin.readline()
    # line 可能含末尾 \n（以及 Windows \r\n）
    return line, [], None
