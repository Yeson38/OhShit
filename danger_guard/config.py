"""
全局配置常量与平台检测。
所有业务模块一律从此处取平台信息，禁止自行调用 platform.system()。
此模块禁止 import 任何业务模块，仅允许标准库。
"""
import os
import platform
from pathlib import Path
from typing import List


def detect_system() -> str:
    """
    检测当前操作系统，保证返回 "Linux" / "Darwin" / "Windows" 三选一。
    Cygwin / MinGW / MSYS 统一视为 Windows（因为它们在 Windows 内核上运行）。
    未知系统兜底为 Linux（避免报错中断用户）。
    """
    s = platform.system()
    if s.startswith(("CYGWIN", "MINGW", "MSYS")):
        return "Windows"
    if s in ("Linux", "Darwin", "Windows"):
        return s
    return "Linux"


# ========== 运行时常量（可被环境变量覆盖） ==========

SYSTEM = detect_system()
HOME = Path.home()

# 用户可通过 DANGER_WHITELIST 指定自定义白名单文件路径
WHITELIST_PATH: Path = Path(
    os.environ.get("DANGER_WHITELIST", str(HOME / ".danger-whitelist"))
)

# 审计日志路径（记录被 OhShit 拦截的操作与内部故障）
LOG_PATH: Path = Path(
    os.environ.get("DANGER_LOG", str(HOME / ".danger.log"))
)

# 强制放行环境变量：设置 DANGER_FORCE=1 时跳过所有防护直接执行
FORCE_ENV: str = "DANGER_FORCE"
FORCE_FLAG: bool = os.environ.get(FORCE_ENV, "").strip() in ("1", "true", "yes", "on")

# 默认白名单目录（跨平台），这些目录下的操作一律放行
DEFAULT_WHITELIST_ITEMS: List[str] = [
    # Linux/POSIX 临时目录
    "/tmp",
    "/var/tmp",
    "/dev/shm",
    # macOS 独有
    "/private/tmp",
    "/private/var/tmp",
    # 环境变量占位（解析时展开）
    "$TMPDIR",
    "$TEMP",
    "$TMP",
]
