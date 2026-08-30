r"""
B- 随机文件名验证算法（核心防呆）。
规则（方案A：允许精确一次过，3 层粘贴检测 + PS/PowerShell/PSReadLine 兼容）：
1. 忽略大小写 + 形近字模糊容忍。
2. 精确匹配（一字不差）= 直接通过（一次过）。
3. 粘贴检测（按检测优先级）：
   3a. 逐字符 burst：`inter-char dt < 4ms` 且连续 ≥ 3 个 → 粘贴嫌疑（命中 PSReadLine 注入式粘贴，
       这类粘贴终端不会发 bracketed marker，也不会被 readline 看到"内容"）。
   3b. Bracketed Paste marker（`\e[200~…\e[201~`）。
   3c. 整行耗时 < 120 ms（兜底：老终端 + 非 burst 的小块粘贴）。
   任一命中 → 判 paste_suspect（不占 3 次 quota，同题重出）。
   3d. PowerShell/PSReadLine 兜底：如果 keystroke 读到"一行 0 字符"但 Enter 被按了（典型表现：
       PSReadLine 在粘贴完成后把自己的 prompt + 清理逻辑写回了 conhost，我们读到的是空串），
       也算粘贴嫌疑"未检测到实际输入"，提示用户手打（不占 quota）。
4. 平台兼容：
   - Windows PowerShell：走 msvcrt.getwch() 逐字（keystroke.read_line_timed），绕开
     PSReadLine 的 readline 拦截；剥 CRLF；SIGINT handler 保证 Ctrl+C 到 rc=130。
   - POSIX：走 termios raw VMIN=1，逐字带时间戳。
5. Ctrl+C：3 层捕获（validator → engine → __main__），一律打印"✅ 已取消"返回 rc=130，
   在 Windows 额外识别 STATUS_CONTROL_C_EXIT(-1073741510) 也转 130。
"""
import random
import sys
import time
import signal
from typing import List, Tuple, Dict, Any, Optional

from danger_guard.core.keystroke import (
    read_line_timed as _read_line_timed,
    is_burst_paste as _is_burst_paste,
    paste_reason_burst as _paste_reason_burst,
    BURST_DT_MS as _BURST_DT_MS,
    BURST_MIN_RUN as _BURST_MIN_RUN,
)
# 整行耗时阈值（毫秒）。从 prompt flush 完成到拿到 Enter 的总耗时。
FAST_THRESHOLD_MS = 120

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
    ('.', '。', '·', '｡', '˙', '．'),
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


def _build_change_example(challenge: str) -> str:
    """给出一个"请改一个字符"的具体参考示例（避免用户不知道怎么改）。

    优先级：
    1) 有 o/O/0 → 把第一个换成 O/0/o
    2) 有 l/L/1/i/I → 改成 1/L
    3) 有英文字母 → 第一个字母切大小写
    4) 纯数字/符号 → 把一个数字换成等价形近字（5↔S 找不到 S 就换成 2→Z 同理，
       这里简化：把第一个数字改成 "数字形状的字母" 对应的数字变体，
       若还是找不到就翻第一个字符大小写或在末尾加 'x'）。
    """
    if not challenge:
        return ""
    # 1) o ↔ 0
    pairs_o = [('o', '0'), ('O', '0'), ('0', 'o')]
    for a, b in pairs_o:
        if a in challenge:
            return challenge.replace(a, b, 1)
    # 2) l ↔ 1
    pairs_l = [('l', '1'), ('L', '1'), ('1', 'L'), ('i', '1'), ('I', '1')]
    for a, b in pairs_l:
        if a in challenge:
            return challenge.replace(a, b, 1)
    # 3) 有字母 → 切大小写
    for i, ch in enumerate(challenge):
        if ch.isalpha():
            swapped = ch.upper() if ch.islower() else ch.lower()
            return challenge[:i] + swapped + challenge[i+1:]
    # 4) 数字形状 5↔S 2↔Z 8↔B 9↔G（反向）
    pairs_digit = [('5', 'S'), ('2', 'Z'), ('8', 'B'), ('9', 'G')]
    for a, b in pairs_digit:
        if a in challenge:
            return challenge.replace(a, b, 1)
    # 兜底：末尾加一个 x
    return challenge + "x"


def validate_challenge(user_input: str, challenge: str) -> Tuple[bool, str]:
    """
    B- 单次验证判定。
    :returns: (是否通过, 给用户看的提示文案)
    规则（从高到低，不再静态拒绝"精确一致"）：
        1) 精确字节一致（strip 后）= 直接通过（一次过）✅
        2) 模糊等价（normalize 相等）= 通过 ✅
        3) 其他 = 失败，附编辑距离提示 + 改字示例
    """
    stripped = user_input.strip()
    challenge_stripped = challenge.strip()

    # 规则 1：一字不差的精确 = 直接通过（一次过）
    if stripped == challenge_stripped and len(challenge_stripped) > 0:
        return (
            True,
            "✅ 验证通过（精确一字不差匹配，一次过）。",
        )

    norm_user = normalize(stripped)
    norm_challenge = normalize(challenge_stripped)

    # 规则 2：模糊匹配通过
    if norm_user == norm_challenge:
        diff_flags = []
        if stripped.lower() != challenge_stripped.lower():
            diff_flags.append("容忍了字形混淆（形近字符互通）")
        elif stripped != challenge_stripped:
            diff_flags.append("容忍了大小写差异")
        else:
            diff_flags.append("匹配通过")
        suffix = f"（{diff_flags[0]}）"
        return (True, f"✅ 验证通过{suffix}。")

    # 规则 3：不匹配
    dist = levenshtein_distance(norm_user, norm_challenge)
    hint = f"规范化后还差约 {dist} 个字符修正。" if dist <= 20 else "差异较大，请重新阅读警告框中的文件名。"
    example = _build_change_example(challenge_stripped)
    return (
        False,
        f"❌ 不匹配。{hint}"
        f"\n   你输入: {stripped!r}"
        f"\n   期望任一形: {challenge_stripped!r}（允许写错字形或改大小写）"
        f"\n   💡 参考（只需改一个字符即可通过）: {example!r}"
    )


# ========== 交互循环 ==========

# Bracketed Paste Mode (xterm/Windows Terminal/mintty/iTerm2/Tmux/VTE 通用)
# 在 readline() 返回的整行里只要出现开头 ESC[200~ 或结尾 ESC[201~ 就判定为粘贴。
# ESC 同时接受 \x1b(7-bit) 与 \x9b(8-bit C1) 两种编码，防止老终端/直接字节下发。
_BRACKET_PASTE_OPEN = ("\x1b[200~", "\x9b200~")
_BRACKET_PASTE_CLOSE = ("\x1b[201~", "\x9b201~")


def _has_bracketed_paste_markers(line: str) -> bool:
    if not line:
        return False
    # 99% 场景：开头紧跟 ESC[200~，结尾紧跟 ESC[201~\n
    stripped_line = line.rstrip("\n").rstrip("\r")
    if any(stripped_line.startswith(op) for op in _BRACKET_PASTE_OPEN):
        return True
    if any(stripped_line.endswith(cl) for cl in _BRACKET_PASTE_CLOSE):
        return True
    # 中间夹带（很少见，但只要出现一对中的任一就保守判）
    if any(op in line for op in _BRACKET_PASTE_OPEN):
        return True
    if any(cl in line for cl in _BRACKET_PASTE_CLOSE):
        return True
    return False


def _strip_bracketed_paste_markers(line: str) -> str:
    """把 line 中的 bracketed 序列拿掉，得到用户真想输入的内容（仅用于展示：粘贴被拒时显示内容本身，不要打印 ESC 乱码）。"""
    s = line
    for op in _BRACKET_PASTE_OPEN:
        s = s.replace(op, "")
    for cl in _BRACKET_PASTE_CLOSE:
        s = s.replace(cl, "")
    return s.rstrip("\n").rstrip("\r")


def run_validation_loop(
    validation_pool: List[str],
    max_attempts: int = 3,
    challenge_prompt_fn=None,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    运行多轮 B- 验证交互，直到通过或耗尽次数。
    """
    if not validation_pool:
        raise ConfusableError("validation_pool 不能为空，至少需要 1 个候选")

    pool = list(validation_pool)
    history: List[Dict[str, Any]] = []
    used_this_round: List[str] = []

    # 安装 SIGINT handler（Windows 也能捕获 signal.SIGINT；重复调用是安全的）。
    # 目的：conhost 在 Ctrl+C 时可能不按顺序抛 KeyboardInterrupt，
    # 但 signal handler 会先执行——这里只做"提醒"，真正的退出仍走 KBI 捕获分支。
    # 多线程/嵌套调用下 signal.signal 返回上一个 handler，不做任何恢复（我们不恢复）。
    try:
        signal.signal(signal.SIGINT, signal.default_int_handler)  # 先还原默认（保证抛 KBI）
    except (ValueError, AttributeError, OSError):
        pass

    print("\n" + _bold_yellow("━" * 52))
    print(_bold_yellow(" 🔐 OhShit B- 人机验证"))
    print(_yellow("    · 精确一字不差的文件名 → 直接通过（一次过）"))
    print(_yellow("    · 允许写错字形（o↔0、l↔1、Z↔2 等互通），允许改大小写"))
    print(_yellow(f"    · ⚠️ 粘贴检测（不占 3 次机会）："))
    print(_yellow(f"        · 逐字爆发（{_BURST_MIN_RUN} 个字符间隔 < {_BURST_DT_MS} ms）"))
    print(_yellow(f"        · Bracketed Paste marker（ESC[200~…）"))
    print(_yellow(f"        · 整行耗时 < {FAST_THRESHOLD_MS} ms；"))
    print(_yellow("    · ⚠️ Windows PowerShell 下若粘贴无效 → 很可能 PSReadLine 拦截了粘贴内容。"))
    print(_yellow("      OhShit 会自动识别为空输入'疑似粘贴'，请手打即可。"))
    print(_bold_yellow("━" * 52) + "\n")
    sys.stdout.flush()

    attempt = 1
    while attempt <= max_attempts:
        remaining = [p for p in pool if p not in used_this_round]
        if not remaining:
            remaining = pool
            used_this_round.clear()
        challenge = random.choice(remaining)
        used_this_round.append(challenge)
        example = _build_change_example(challenge)

        if challenge_prompt_fn:
            challenge_prompt_fn(challenge, attempt, max_attempts)
        else:
            print(
                _cyan(f"  [第 {attempt}/{max_attempts} 次机会]")
                + f" 请输入文件名 → "
                + _bold_magenta(challenge)
            )
            if example != challenge:
                print(
                    "  " + _yellow("💡 想试试改字版（不必真改）：")
                    + _bold(example)
                    + _yellow("  （和原题随便选一个都行）")
                )

        # timing 从 flush + t_start 之后开始（与方案 2d 一致）
        sys.stdout.flush()
        t_start = time.perf_counter()

        raw_line: str = ""
        dts_ms: List[int] = []
        total_ms: Optional[int] = None
        fell_back_to_stdin: bool = False
        try:
            # 逐字带时间戳读取（Win=msvcrt / POSIX=termios raw）
            raw_line, dts_ms, total_ms = _read_line_timed(echo=True)
            fell_back_to_stdin = (not dts_ms and total_ms is None)
        except KeyboardInterrupt:
            cancel_msg = "✅ 已取消（Ctrl+C）。操作未执行。"
            history.append({
                "challenge": challenge,
                "user_input": "<Ctrl+C>",
                "passed": False,
                "message": cancel_msg,
                "paste_suspect": False,
                "elapsed_ms": 0,
                "cancelled": True,
            })
            print("\n  " + _green(cancel_msg))
            sys.stdout.flush()
            return False, history
        except BaseException as be:
            cancel_msg = f"✅ 已取消（{type(be).__name__}）。操作未执行。"
            history.append({
                "challenge": challenge,
                "user_input": f"<{type(be).__name__}>",
                "passed": False,
                "message": cancel_msg,
                "paste_suspect": False,
                "elapsed_ms": 0,
                "cancelled": True,
            })
            print("\n  " + _green(cancel_msg))
            sys.stdout.flush()
            return False, history

        t_end = time.perf_counter()
        # 如果 keystroke 回退到 stdin（非 TTY 或失败），用 perf_counter 做整行耗时兜底
        if total_ms is None:
            total_ms = int((t_end - t_start) * 1000)
        elapsed_ms = total_ms

        # EOF（keystroke 层 EOF 时 raw_line="",dts=[],total=0）
        if raw_line == "" and (not dts_ms):
            # 3d. PSReadLine 特殊兜底：逐字 reader 根本没读到字（不是回退 stdin 模式）。
            # 这种情况最常出现于 PSReadLine 在 conhost 层把我们 getwch() 和 PSReadLine 的
            # 读取混在一起 → OhShit 这边读空 Enter。
            if not fell_back_to_stdin:
                # 没回退 stdin 但仍空 → PSReadLine 粘贴拦截高概率
                paste_msg = (
                    "⏱  粘贴嫌疑（PSReadLine / 终端控制台拦截：未读到任何输入字符，只收到 Enter）。\n"
                    "   不占用 3 次机会，请不要用粘贴，手动打一遍文件名：\n"
                    f"     · 原题：{challenge!r}\n"
                    f"     · 改字版参考：{example!r}"
                )
                history.append({
                    "challenge": challenge, "user_input": "<PSReadLine-empty>",
                    "passed": False, "message": paste_msg,
                    "paste_suspect": True, "elapsed_ms": elapsed_ms,
                })
                print("  " + _red(paste_msg) + "\n")
                sys.stdout.flush()
                if challenge in used_this_round:
                    used_this_round.remove(challenge)
                continue
            # 真 EOF（非交互管道）
            history.append({
                "challenge": challenge, "user_input": "<EOF>",
                "passed": False, "message": "EOF: 用户中断输入",
                "paste_suspect": False, "elapsed_ms": elapsed_ms,
            })
            break

        # Windows CRLF 剥离（PowerShell / cmd 经常在行尾混 \r）
        raw_line = raw_line.rstrip("\r\n")

        # ---- 检测 3a：burst（逐字爆发）----
        burst_suspect = not fell_back_to_stdin and _is_burst_paste(dts_ms)

        # ---- 检测 3b：Bracketed Paste marker ----
        bp_markers = _has_bracketed_paste_markers(raw_line)
        visible_input = _strip_bracketed_paste_markers(raw_line) if bp_markers else raw_line

        # ---- 检测 3c：整行过快 ----
        fast_suspect = len(challenge.strip()) > 0 and elapsed_ms < FAST_THRESHOLD_MS

        # PSReadLine 空粘贴兜底的另一形态：visible_input 为空但 raw_line 非空（极少）
        empty_input_suspect = (len(visible_input.strip()) == 0) and bp_markers

        paste_suspect = burst_suspect or bp_markers or fast_suspect or empty_input_suspect
        reasons: List[str] = []
        if burst_suspect:
            reasons.append(_paste_reason_burst(dts_ms))
        if bp_markers:
            reasons.append("Bracketed Paste marker（检测到 Ctrl+Shift+V / 终端粘贴模式序列）")
        if fast_suspect and not burst_suspect:
            reasons.append(f"整行过快（{elapsed_ms} ms < {FAST_THRESHOLD_MS} ms）")
        if empty_input_suspect:
            reasons.append("粘贴后内容为空（可能是终端 control 字符混入）")
        paste_reason = "；".join(reasons) if reasons else "疑似粘贴"

        # 在粘贴嫌疑下，先剥离 marker 再看"内容是否正确"，提示用户"你的输入是对的只要手打"
        passed_from_input = False
        msg_from_input = ""
        if visible_input:
            passed_from_input, msg_from_input = validate_challenge(visible_input, challenge)
        else:
            passed_from_input = False
            msg_from_input = "输入内容为空，无法验证。" if not raw_line else ""

        if paste_suspect:
            paste_msg = (
                f"⏱  粘贴嫌疑（{paste_reason}）。\n"
                f"   不占用 3 次机会，请放慢节奏，再手打一遍：\n"
                f"     · 原题：{challenge!r}\n"
                f"     · 改字版参考：{example!r}"
            )
            if passed_from_input and visible_input:
                paste_msg += f"\n   💡 检测到你粘的内容本身是正确的（{visible_input!r}），只要手打一遍就直接过。"
            history.append({
                "challenge": challenge,
                "user_input": visible_input if visible_input else raw_line,
                "passed": False,
                "message": paste_msg,
                "paste_suspect": True,
                "elapsed_ms": elapsed_ms,
            })
            print("  " + _red(paste_msg) + "\n")
            sys.stdout.flush()
            if challenge in used_this_round:
                used_this_round.remove(challenge)
            continue

        # ---- 非粘贴嫌疑 ----
        passed = passed_from_input
        msg = msg_from_input
        history.append({
            "challenge": challenge,
            "user_input": visible_input,
            "passed": passed,
            "message": msg,
            "paste_suspect": False,
            "elapsed_ms": elapsed_ms,
        })
        prefix = "  "
        if passed:
            print(prefix + _green(msg) + "\n")
            sys.stdout.flush()
            return True, history
        else:
            print(prefix + _red(msg) + "\n")
            sys.stdout.flush()
            attempt += 1

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
def _bold_red(s):  return _ansi("31;1", s)
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
