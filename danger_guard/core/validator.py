"""
B- 随机文件名验证算法（核心防呆）。
规则（方案A：允许精确一次过，纯时序检测粘贴）：
1. 忽略大小写（底层统一 lower()）
2. 形近字模糊容忍：O/0/Q, l/1/I/|, S/5, Z/2, B/8, G/9 等等价
3. 精确匹配（一字不差）= 直接通过（一次过，不再拒绝）。
   检测"粘贴"不靠静态文字一致性，靠**动态时序**：
     3a. 用户从 prompt 出现到完整输入一行的时间 < FAST_THRESHOLD_MS(120 ms)
         → 判定为"粘贴嫌疑"，提示疑似粘贴并重抽同题（不消耗 3 次 quota）。
     3b. 若用户非精确匹配（改字或形近）但 3a 触发，仍按"粘贴嫌疑"走重抽同题。
   （人眼扫题 + 定位键盘 + 敲第一下字符 至少 120~200 ms，< 120 ms 一定是粘贴/历史命令补全。）
4. 3 次"真实机会"轮换，paste_suspect 不占次数；改字示例每次 prompt 都给一个具体参考。
"""
import random
import sys
import time
from typing import List, Tuple, Dict, Any, Optional

# 过快判定阈值（毫秒）。从 prompt 打完输出 flush → 拿到完整一行 readline 的时间差。
# 120 ms 是人类"看懂题 + 启动手指 + 输入完一个文件名"的极限下界；粘贴永远 < 1 ms。
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
    :param validation_pool: 候选文件名/设备名池（必须非空）
    :param max_attempts: 最大真实尝试次数（默认 3）。"粘贴嫌疑（过快输入或有 Bracketed Paste marker）"不消耗本次 quota。
    :param challenge_prompt_fn: 可选，自定义 prompt 函数。签名: fn(challenge, attempt, max_attempts) -> None
    :returns: (是否全部通过, 历史记录列表)
              历史记录每项为 {"challenge": str, "user_input": str, "passed": bool, "message": str,
                                 "paste_suspect": bool, "elapsed_ms": int, "cancelled": bool}
    """
    if not validation_pool:
        raise ConfusableError("validation_pool 不能为空，至少需要 1 个候选")

    pool = list(validation_pool)
    history: List[Dict[str, Any]] = []
    used_this_round: List[str] = []

    # 先输出验证规则的提示语（只打一次）
    print("\n" + _bold_yellow("━" * 52))
    print(_bold_yellow(" 🔐 OhShit B- 人机验证"))
    print(_yellow("    · 精确一字不差的文件名 → 直接通过（一次过）"))
    print(_yellow("    · 允许写错字形（o↔0、l↔1、Z↔2 等互通），允许改大小写"))
    print(_yellow(f"    · ⚠️ 输入 < {FAST_THRESHOLD_MS} 毫秒视为疑似粘贴（或历史命令补全），"))
    print(_yellow("      不占用 3 次机会，请放慢节奏，再输一遍同样的（或形近字）。"))
    print(_yellow("    · ⚠️ 检测到 Bracketed Paste marker（终端 Ctrl+Shift+V 会注入）→ 直接判粘贴嫌疑，"))
    print(_yellow("      不占次数，手动再打一遍就行。"))
    print(_bold_yellow("━" * 52) + "\n")
    sys.stdout.flush()

    attempt = 1  # 真实尝试计数，只有 paste_suspect=False 才递增
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
            sys.stdout.flush()

        # timing 从 prompt 刷新前（即已经开始显示"你可以输入了"）就取 t_start。
        # winpty 这类伪 TTY 有缓冲语义，如果 t_start 取在 flush 之后会"吃"掉 prompt 输出时间，
        # 导致 elapsed_ms 偏低 → 粘贴漏判。取在 flush 之前（即便没 flush 完）更保守。
        sys.stdout.flush()
        t_start = time.perf_counter()

        try:
            user_input = sys.stdin.readline()
        except KeyboardInterrupt:
            # Ctrl+C：内部处理为"已取消"，不再冒泡抛栈。
            # 打印友好提示，返回 (False, history)。engine 与 __main__ 还会再兜底防止任何残留堆栈。
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
        except BaseException as be:   # pragma: no cover — 兜底其它中断（SystemExit/自定义信号）
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
        elapsed_ms = int((t_end - t_start) * 1000)

        if user_input == "":
            history.append({
                "challenge": challenge, "user_input": "<EOF>",
                "passed": False, "message": "EOF: 用户中断输入",
                "paste_suspect": False, "elapsed_ms": elapsed_ms,
            })
            break

        raw_line = user_input.rstrip("\n")

        # ---- 动态检测 1：Bracketed Paste marker（优先级高于一切）----
        bp_markers = _has_bracketed_paste_markers(raw_line)
        # 把 marker 剥离后再做 validate，否则 ESC 字符会让"精确匹配"永远失败
        visible_input = _strip_bracketed_paste_markers(raw_line) if bp_markers else raw_line
        # 只有 visible_input 非空时才 validate（纯 marker 或空串的直接判粘贴）
        passed_from_input = False
        msg_from_input = ""
        if visible_input:
            passed_from_input, msg_from_input = validate_challenge(visible_input, challenge)
        else:
            passed_from_input = False
            msg_from_input = "粘贴内容为空，无法验证。"

        # ---- 动态检测 2：时序过快 ----
        fast_suspect = len(challenge.strip()) > 0 and elapsed_ms < FAST_THRESHOLD_MS

        paste_suspect = bp_markers or fast_suspect
        paste_reason = ""
        if bp_markers and fast_suspect:
            paste_reason = "Bracketed Paste marker + 过快输入"
        elif bp_markers:
            paste_reason = "Bracketed Paste marker（检测到 Ctrl+Shift+V / 终端粘贴模式序列）"
        else:  # fast_suspect
            paste_reason = f"过快输入（{elapsed_ms} ms < {FAST_THRESHOLD_MS} ms）"

        if paste_suspect:
            paste_msg = (
                f"⏱  粘贴嫌疑（{paste_reason}）。"
                f"\n   不占用 3 次机会，请放慢节奏，再手打一遍："
                f"\n     · 原题：{challenge!r}"
                f"\n     · 改字版参考：{example!r}"
            )
            # 若用户"粘贴但本来内容是对的"，给个额外提示：内容是对的，只是触发了粘贴检测器
            if passed_from_input:
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

        # ---- 非粘贴嫌疑，正常消耗一次 quota ----
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

    # 耗尽所有真实机会
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
