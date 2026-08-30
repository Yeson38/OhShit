"""
UI 渲染模块：红色警告框、预览摘要、彩色辅助。

设计：
  - 复用 validator 里的极简 ANSI 彩色方案，不引入 colorama 第三方依赖。
  - NO_COLOR 环境变量（任何非空值）下，所有颜色函数自动降级为纯文本。
  - warning_box 统一绘制 ASCII 盒框带标题、红/黄/青边框 + 取消提示语。
  - preview_summary 负责将"受影响数量 + 总大小 + 样本条目"格式化输出。
"""
import os
import sys
import textwrap
from typing import List

# ========== 终端彩色辅助（与 validator 同风格，加 NO_COLOR 支持） ==========

def _no_color_set() -> bool:
    """动态读取 NO_COLOR 环境变量（每次调用都读，支持 monkeypatch 测试）。"""
    return bool(os.environ.get("NO_COLOR", ""))


def _ansi(seq: str, text: str) -> str:
    """
    包一层 ANSI 颜色码。
    降级条件：stdout 非 TTY，或 NO_COLOR 环境变量被设置（非空）。
    """
    if _no_color_set():
        return text
    try:
        if not sys.stdout.isatty():
            return text
    except (AttributeError, ValueError):
        return text
    return f"\x1b[{seq}m{text}\x1b[0m"


def _bold(s):          return _ansi("1", s)
def _red(s):           return _ansi("31", s)
def _bold_red(s):      return _ansi("31;1", s)
def _yellow(s):        return _ansi("33", s)
def _bold_yellow(s):   return _ansi("33;1", s)
def _green(s):         return _ansi("32;1", s)
def _cyan(s):          return _ansi("36;1", s)
def _bold_magenta(s):  return _ansi("35;1", s)


# ========== 盒框绘制辅助 ==========

def _wrap_text(text: str, width: int) -> List[str]:
    """
    按词断行到指定宽度；空字符串保留为空行（不被 textwrap 吞掉）。
    """
    if not text:
        return [""]
    # textwrap.wrap 对空串返回 []，这里已经先行拦截
    return textwrap.wrap(
        text,
        width=width - 4,  # 预留左右边框 + 空格：│ text │
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]


def _box_pad(text: str, width: int, left: str = "│ ", right: str = " │") -> str:
    """
    将单行文本填入盒框中间行：│ text            │
    宽度不足用空格填充；超长则直接截断（保证盒框不歪）。
    """
    inner_width = width - len(left) - len(right)
    if inner_width <= 0:
        inner_width = 1
    if len(text) > inner_width:
        text = text[:inner_width - 1] + "…"
    padded = text + " " * (inner_width - len(text))
    return f"{left}{padded}{right}"


# ========== 公共：警告框 ==========

def warning_box(
    title: str = "⚠ 高风险操作 WARNING",
    message_lines: List[str] = None,
    risk_level: int = 3,
    border_color: str = "red",
) -> str:
    """
    绘制带 ASCII 边框的彩色警告框。
    :param title: 标题（会自动加粗）
    :param message_lines: 正文行列表（行内自动按盒宽断行，含空行会被保留）
    :param risk_level: 1=低(青) 2=中(黄) 3=高(红)
    :param border_color: "red" / "yellow" / "cyan"（会被 risk_level 覆盖）
    :return: 完整的多行字符串（含换行，末尾已带换行）
    """
    # ---- 颜色按 risk_level 覆盖 ----
    if risk_level >= 3:
        color_fn = _bold_red
    elif risk_level == 2:
        color_fn = _bold_yellow
    elif risk_level == 1:
        color_fn = _cyan
    else:
        # 兜底：按 border_color 字面
        color_fn = {
            "red": _bold_red,
            "yellow": _bold_yellow,
            "cyan": _cyan,
        }.get(border_color, _bold_red)

    width = 80
    inner_width = width - 4  # 除去 ┌─ 和 ─┐

    # ---- 标题行：┌─ title ────┐ ----
    bold_title = _bold(title)
    title_inner = f" {bold_title} "
    # 计算填充的 '─' 数量（ANSI 码不占显示宽度，这里按"去掉码后"的实际字符数对齐）
    title_plain = title
    # 显示宽度：两边各一个空格 + title 字符数
    pad_total = max(0, inner_width - 2 - len(title_plain))
    # 分配给左/右：左边少一点，让视觉居左
    left_dashes = 1
    right_dashes = max(0, pad_total - left_dashes)
    top_line = (
        color_fn("┌")
        + color_fn("─" * left_dashes)
        + title_inner
        + color_fn("─" * right_dashes)
        + color_fn("┐")
    )

    # ---- 盒内正文 ----
    if message_lines is None:
        message_lines = []
    content_lines: List[str] = []
    for ml in message_lines:
        wrapped = _wrap_text(ml, width)
        for w in wrapped:
            # 先 _box_pad 生成纯文本结构，再给整行加边框颜色
            raw = _box_pad(w, width)
            content_lines.append(_colorize_box_line(raw, color_fn))

    # ---- 分隔线：分隔正文与底部操作提示 ├────┤ ----
    sep_line = (
        color_fn("├")
        + color_fn("─" * inner_width)
        + color_fn("┤")
    )

    # ---- 固定底部提示 ----
    tips = [
        "按 Ctrl+C 随时中止；改主意按回车跳过",
        "若确认无误，可在命令前加 DANGER_FORCE=1 跳过所有验证",
    ]
    tip_lines: List[str] = []
    for t in tips:
        wrapped = _wrap_text(t, width)
        for w in wrapped:
            raw = _box_pad(w, width)
            tip_lines.append(_colorize_box_line(raw, color_fn))

    # ---- 底行 └─────┘ ----
    bottom_line = (
        color_fn("└")
        + color_fn("─" * inner_width)
        + color_fn("┘")
    )

    # ---- 拼接 ----
    out_parts = [top_line]
    if content_lines:
        out_parts.extend(content_lines)
    else:
        # 至少一行空内容撑框
        raw = _box_pad("", width)
        out_parts.append(_colorize_box_line(raw, color_fn))
    out_parts.append(sep_line)
    out_parts.extend(tip_lines)
    out_parts.append(bottom_line)
    return "\n".join(out_parts) + "\n"


def _colorize_box_line(raw: str, color_fn) -> str:
    """
    给盒框的左右边界字符上色（保留内部文字原样，避免颜色嵌套出问题）。
    行结构：│ text_... │
    """
    if len(raw) < 3:
        return color_fn(raw)
    # 第一个字符：左边界
    left_border = raw[0]
    # 最后一个字符：右边界
    right_border = raw[-1]
    # 中间内容保持不变（含内部空格和文字）
    middle = raw[1:-1]
    return f"{color_fn(left_border)}{middle}{color_fn(right_border)}"


# ========== 公共：预览摘要 ==========

def human_size(num_bytes: int) -> str:
    """
    将字节数格式化为人类可读大小（1024 进制）：B / KB / MB / GB / TB。
    """
    if num_bytes is None:
        return "0 B"
    try:
        n = int(num_bytes)
    except (TypeError, ValueError):
        return "0 B"
    if n < 0:
        n = 0
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(n)
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    if idx == 0:
        return f"{int(size)} {units[idx]}"
    return f"{size:.1f} {units[idx]}"


def preview_summary(
    header: str,
    affected_count: int,
    total_size_bytes: int,
    target_scope: str,
    sample_items: List[str],
    risk_level: int = 3,
) -> str:
    """
    生成"受影响预览"的多行摘要文本（纯文本 + 少量配色）。
    :param header: 头部标题，如 "预删除预览"
    :param affected_count: 受影响文件/目录数
    :param total_size_bytes: 总字节数
    :param target_scope: 目标范围（路径或通配），如 "/data"
    :param sample_items: 样本条目列表（只展示前 10 条）
    :param risk_level: 1/2/3，决定标题颜色
    :return: 多行字符串（末尾带换行）
    """
    # 标题颜色
    if risk_level >= 3:
        title_color = _bold_red
    elif risk_level == 2:
        title_color = _bold_yellow
    else:
        title_color = _cyan

    lines: List[str] = []
    lines.append(title_color(f"━━ {header} ━━"))
    lines.append(f"  目标范围 : {target_scope}")
    lines.append(f"  受影响数 : {affected_count} 项")
    lines.append(f"  估算大小 : {human_size(total_size_bytes)}")

    # 样本条目
    if sample_items:
        shown = sample_items[:10]
        more = len(sample_items) - len(shown)
        lines.append("  样本条目 :")
        for item in shown:
            lines.append(f"    • {item}")
        if more > 0:
            lines.append(f"    ... and {more} more")

    return "\n".join(lines) + "\n"


def print_preview(
    header: str,
    affected_count: int,
    total_size_bytes: int,
    target_scope: str,
    sample_items: List[str],
    risk_level: int = 3,
) -> None:
    """
    preview_summary 的便利封装：直接 print 并 flush。
    """
    print(preview_summary(
        header=header,
        affected_count=affected_count,
        total_size_bytes=total_size_bytes,
        target_scope=target_scope,
        sample_items=sample_items,
        risk_level=risk_level,
    ), end="")
    try:
        sys.stdout.flush()
    except (AttributeError, ValueError):
        pass


__all__ = [
    "warning_box",
    "preview_summary",
    "print_preview",
    "human_size",
    # 彩色工具（对外暴露，方便 engine/validator 复用）
    "_ansi", "_bold", "_red", "_bold_red", "_yellow", "_bold_yellow",
    "_green", "_cyan", "_bold_magenta",
]
