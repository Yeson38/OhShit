"""
B- 随机文件名验证算法（核心防呆）。
规则：
1. 忽略大小写（底层统一 lower()）
2. 形近字模糊容忍：O/0/Q, l/1/I/|, S/5, Z/2, B/8, G/9 等等价
3. 完全精确字节匹配 = 拒绝：如果用户输入与 challenge 字节级完全一致，
   说明是复制粘贴的，必须拒绝以强制人工输入。
4. 3 次机会，每次随机从 validation_pool 抽新文件名（失败则轮换，避免死磕同一个）。
"""
import random
import sys
from typing import List, Tuple, Dict, Any, Optional

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


def validate_challenge(user_input: str, challenge: str) -> Tuple[bool, str]:
    """
    B- 单次验证判定。
    :returns: (是否通过, 给用户看的提示文案)
    规则优先级（从高到低）：
        1) user_input.strip() == challenge → 精确字节一致 = 拒绝（防复制粘贴）
        2) normalize(user_input.strip()) == normalize(challenge) → 模糊通过 ✅
        3) 其他 → 失败，附编辑距离提示
    """
    stripped = user_input.strip()
    challenge_stripped = challenge.strip()

    # 规则 1：完全精确一致 → 故意拒绝
    if stripped == challenge_stripped and len(challenge_stripped) > 0:
        return (
            False,
            "❌ 检测到直接复制粘贴。OhShit 要求必须人工输入："
            "请故意稍作改动（例如把 o 写成 0，或调整大小写），再试一次。"
        )

    norm_user = normalize(stripped)
    norm_challenge = normalize(challenge_stripped)

    # 规则 2：模糊匹配通过
    if norm_user == norm_challenge:
        diff_flags = []
        if stripped.lower() != challenge_stripped.lower():
            diff_flags.append("容忍了字形混淆（形近字符互通）")
        else:
            if stripped != challenge_stripped:
                diff_flags.append("容忍了大小写差异")
            else:
                diff_flags.append("匹配通过")
        suffix = ""
        if diff_flags:
            suffix = f"（{diff_flags[0]}）"
        return (True, f"✅ 验证通过{suffix}。")

    # 规则 3：不匹配
    dist = levenshtein_distance(norm_user, norm_challenge)
    hint = f"规范化后还差约 {dist} 个字符修正。" if dist <= 20 else "差异较大，请重新阅读警告框中的文件名。"
    return (
        False,
        f"❌ 不匹配。{hint}"
        f"\n   你输入: {stripped!r}"
        f"\n   期望的任一形: {challenge_stripped!r}（允许写错字形或改大小写）"
    )


# ========== 交互循环 ==========

def run_validation_loop(
    validation_pool: List[str],
    max_attempts: int = 3,
    challenge_prompt_fn=None,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    运行多轮 B- 验证交互，直到通过或耗尽次数。
    :param validation_pool: 候选文件名/设备名池（必须非空）
    :param max_attempts: 最大尝试次数（默认 3）
    :param challenge_prompt_fn: 可选，自定义 prompt 函数。签名: fn(challenge, attempt, max_attempts) -> None
                                 默认会把提示文案写到 stdout。
    :returns: (是否全部通过, 历史记录列表)
              历史记录每项为 {"challenge": str, "user_input": str, "passed": bool, "message": str}
    :raises KeyboardInterrupt: 用户按 Ctrl+C 时透传（由上层 engine 捕获显示"已取消"）
    """
    if not validation_pool:
        raise ConfusableError("validation_pool 不能为空，至少需要 1 个候选")

    pool = list(validation_pool)
    history: List[Dict[str, Any]] = []
    used_this_round: List[str] = []

    # 先输出验证规则的提示语（只打一次）
    print("\n" + _bold_yellow("━" * 52))
    print(_bold_yellow(" 🔐 OhShit B- 人机验证"))
    print(_yellow("    · 允许写错字形（如 o↔0、l↔1、Z↔2 等互通）"))
    print(_yellow("    · 允许改大小写"))
    print(_yellow("    · ⚠️ 直接复制粘贴的完全一致将被拒绝——请故意稍作改动"))
    print(_bold_yellow("━" * 52) + "\n")
    sys.stdout.flush()

    for attempt in range(1, max_attempts + 1):
        # 选一个"在本次还没被用过"的文件名（如果都用完了就重置）
        remaining = [p for p in pool if p not in used_this_round]
        if not remaining:
            remaining = pool
            used_this_round.clear()
        challenge = random.choice(remaining)
        used_this_round.append(challenge)

        # 出挑战题
        if challenge_prompt_fn:
            challenge_prompt_fn(challenge, attempt, max_attempts)
        else:
            # 默认提示：展示挑战文件名 + 轮次
            print(
                _cyan(f"  [第 {attempt}/{max_attempts} 次机会]")
                + f" 请手动输入以下文件名 → "
                + _bold_magenta(challenge)
            )
            sys.stdout.flush()

        # 读用户输入（Ctrl+C 要透传给上层）
        try:
            user_input = sys.stdin.readline()
        except KeyboardInterrupt:
            raise

        if user_input == "":
            # EOF（Ctrl+D）
            history.append({
                "challenge": challenge, "user_input": "<EOF>",
                "passed": False, "message": "EOF: 用户中断输入",
            })
            break

        passed, msg = validate_challenge(user_input.rstrip("\n"), challenge)
        history.append({
            "challenge": challenge,
            "user_input": user_input.rstrip("\n"),
            "passed": passed,
            "message": msg,
        })
        # 输出结果
        prefix = "  "
        if passed:
            print(prefix + _green(msg) + "\n")
            sys.stdout.flush()
            return True, history
        else:
            # 失败：打印原因 + 加空行分隔
            print(prefix + _red(msg) + "\n")
            sys.stdout.flush()

    # 耗尽所有机会
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
