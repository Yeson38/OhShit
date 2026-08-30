"""
路径白名单模块。
负责管理默认安全路径 + 用户自定义白名单，支持 glob 通配符匹配与嵌套目录放行。
所有业务模块在判定"是否跳过某路径的风险扫描"时统一调 is_whitelisted_path。
"""
from danger_guard import config
from pathlib import Path
import os
import fnmatch
from typing import List


# ========== 默认白名单条目 ==========
# 这些目录/模式下的操作一律视为安全，不触发后续验证。
# 注意：含 ~ / $VAR 的会在 load_default_items 阶段展开。
_DEFAULT_WHITELIST_PATHS: List[str] = [
    "/tmp/*",
    "/var/tmp/*",
    f"{os.path.expanduser('~')}/.cache/*",
    "/dev/null",
]

# 用户白名单文件默认位置（来自 config，可被 DANGER_WHITELIST 环境变量覆盖）
DEFAULT_USER_WHITELIST = config.WHITELIST_PATH


# ========== 加载函数 ==========

def load_default_items() -> List[str]:
    """
    加载默认白名单条目。
    - 展开 ~ 和 $VAR 环境变量
    - 去重
    :returns: 去重后的默认白名单条目列表
    """
    expanded = []
    seen = set()
    for raw in _DEFAULT_WHITELIST_PATHS:
        p = os.path.expanduser(os.path.expandvars(raw))
        key = p
        if key not in seen:
            seen.add(key)
            expanded.append(p)
    # 同时合并 config.DEFAULT_WHITELIST_ITEMS（向后兼容）
    for raw in getattr(config, "DEFAULT_WHITELIST_ITEMS", []):
        p = os.path.expanduser(os.path.expandvars(raw))
        key = p
        if key not in seen:
            seen.add(key)
            expanded.append(p)
    return expanded


def load_user_whitelist(file_path=None) -> List[str]:
    """
    加载用户自定义白名单文件。
    - 文件不存在 → 返回 []，不抛异常
    - 跳过 # 开头的整行注释和空行
    - 支持行尾内联注释 "path  # comment"
    - 每行执行 expanduser + expandvars
    :param file_path: 白名单文件路径；None 时使用 DEFAULT_USER_WHITELIST
    :returns: 解析后的白名单条目列表
    """
    if file_path is None:
        file_path = DEFAULT_USER_WHITELIST

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except FileNotFoundError:
        return []
    except (OSError, PermissionError):
        return []

    items: List[str] = []
    for raw in raw_lines:
        line = raw.rstrip("\n").rstrip("\r")
        # 去行尾内联注释（找到 ' #' 就截断）
        if " #" in line:
            line = line[:line.index(" #")]
        line = line.strip()
        # 跳过整行注释和空行
        if not line or line.startswith("#"):
            continue
        # 展开 ~ 和环境变量
        expanded = os.path.expanduser(os.path.expandvars(line))
        items.append(expanded)
    return items


def load_all_whitelist(file_path=None) -> List[str]:
    """
    加载全部白名单条目：默认 + 用户自定义（合并，不去重由匹配阶段处理）。
    """
    return load_default_items() + load_user_whitelist(file_path)


# ========== 匹配辅助 ==========

def _normalize(p: str) -> str:
    """
    规范化路径：expanduser → expandvars → abspath；末尾多余 / 统一。
    """
    if not p:
        return ""
    expanded = os.path.expanduser(os.path.expandvars(p))
    abs_p = os.path.abspath(expanded)
    # 去掉末尾多余的 /（保留根目录 / 本身）
    if len(abs_p) > 1 and abs_p.endswith("/"):
        abs_p = abs_p.rstrip("/")
    return abs_p


def _match_one(path: str, pattern: str) -> bool:
    """
    判断单个 path 是否匹配单个 pattern。
    规则：
      - 如果 pattern 含有 glob 字符 (* ? [) → fnmatch.fnmatchcase(规范化 path vs pattern)
      - 否则：完全相等，或 path 是 pattern 目录的子项（startswith + '/' 前缀）
    """
    norm_path = _normalize(path)
    # 对 pattern 里的 glob 部分先做 ~/$ 展开（但保留通配符）
    expanded_pattern = os.path.expanduser(os.path.expandvars(pattern))

    has_glob = any(ch in expanded_pattern for ch in ("*", "?", "["))

    if has_glob:
        # fnmatch 通配符匹配（用规范化后的 path 对 pattern）
        # 注意：pattern 本身可能是相对或带通配符的，也尽量转成和 path 同形式
        # 如果 pattern 不是绝对路径，就保持原样让 fnmatch 对比 norm_path 的 basename 也不一定合理。
        # 策略：直接用 fnmatch 对 norm_path 和 expanded_pattern 做匹配
        if fnmatch.fnmatchcase(norm_path, expanded_pattern):
            return True
        # 兜底：如果 pattern 是目录通配符 "/tmp/*"，尝试匹配 "/tmp/subdir/file"
        # fnmatch 对 "/tmp/*" 和 "/tmp/a/b" 会失败（* 不跨 /），这里额外处理嵌套
        # 简化：如果 expanded_pattern 以 /* 结尾，则判断 path 是否以去掉 /* 的部分开头
        if expanded_pattern.endswith("/*"):
            prefix = expanded_pattern[:-2]  # 去掉 /*
            norm_prefix = _normalize(prefix)
            if norm_path == norm_prefix or norm_path.startswith(norm_prefix + os.sep):
                return True
        return False
    else:
        # 字面量 + 嵌套目录匹配
        norm_pattern = _normalize(expanded_pattern)
        if not norm_pattern:
            return False
        if norm_path == norm_pattern:
            return True
        # path 是 pattern 下的嵌套子项
        if norm_path.startswith(norm_pattern.rstrip("/") + os.sep):
            return True
        # 如果 pattern 本身是绝对匹配（比如 /dev/null），再兜底一次
        return False


# ========== 公共 API ==========

def is_whitelisted_path(path, whitelist=None) -> bool:
    """
    判定给定 path 是否在白名单内。
    :param path: 待判定路径（字符串）
    :param whitelist: 可选，自定义白名单条目列表；None 时自动 load_all_whitelist
    :returns: True → 白名单，安全；False → 需要继续校验
    """
    if not path:
        return False
    if whitelist is None:
        whitelist = load_all_whitelist()
    for pattern in whitelist:
        if _match_one(str(path), pattern):
            return True
    return False


__all__ = [
    "DEFAULT_USER_WHITELIST",
    "load_default_items",
    "load_user_whitelist",
    "load_all_whitelist",
    "is_whitelisted_path",
]
