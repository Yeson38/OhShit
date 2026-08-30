# OhShit 删库跑路预防针 - 设计文档

> **版本**: 1.0  
> **日期**: 2026-08-30  
> **状态**: 待 Review  
> **技术栈**: Python 3.7+（标准库为主）  
> **MVP 范围**: rm + dd + 钩子框架（可扩展）

---

## 一、项目背景与目标

### 1.1 痛点

`rm -rf *`、`dd` 烧录失误、`> file` 意外覆盖是"删库跑路"悲剧的导火索。现有方案缺陷：

- 原生 `rm -i`：逐文件确认效率低，无法显示总数量与总大小
- 管道忽视：`rm -rf *` 与 `find`/`xargs` 组合时 alias 拦截失效
- 疲劳操作：深夜加班时单纯 `yes/no` 确认极易形成肌肉记忆

### 1.2 核心价值

将"事后懊悔"转化为"事中强制认知"，通过量化视觉冲击与随机挑战认证，杜绝无意识高危操作。

### 1.3 MVP 交付目标（2 个开发日）

- 覆盖 `rm`（删除）和 `dd`（磁盘烧录）两个高危命令
- 提供可扩展的钩子框架（BaseHook + 装饰器自动注册）
- 三阶防护完整落地：参数预演 → 红色警告 → B- 随机文件名验证
- 跨平台支持 Linux / macOS / Windows（WSL/PowerShell）
- 一键安装/卸载脚本
- pip + zipapp 分发（PyInstaller 非阻塞项）

---

## 二、用户确认的关键决策

| 决策点 | 选择 | 说明 |
|---|---|---|
| 命令范围 | C：rm + dd + 钩子框架 | 含可扩展拦截器结构 |
| 技术栈 | A：Python 3 标准库为主 | PyInstaller 不作为 MVP 阻塞条件 |
| 验证规则 | B-：忽略大小写 + 形近字模糊 + 反复制粘贴 | 完全精确匹配 = 拒绝（防复制粘贴） |
| 拦截范围 | A：仅交互 TTY 拦截 | 非 TTY（脚本/cron/CI）直接放行 |
| 架构方案 | 2：包结构 + 插件注册表 | 完全模块化，单向依赖 |

---

## 三、架构设计

### 3.1 模块结构与依赖方向

```
依赖方向（自上而下，绝不反向）：

  cli.py / __main__            入口：argparse 解析 → 调 engine
        │
  core/engine.py               三阶防护编排器
  公开接口：run_pipeline(command_name, args, env)
        │
  ┌─────┼─────────┬───────────┬──────────────┐
  │     │         │           │              │
tty_   ui.py   validator.py  whitelist.py   core 子模块
detector       (B-规则)      (~/.danger)    （互相独立无依赖）
        │
  hooks/ (插件层)              每个 Hook ≡ 一个命令
  BaseHook (base.py) → rm_hook / dd_hook / ...
  公开：get_hook(name)
        │
  executors/ (系统命令执行层)
  posix_exec.py / windows_exec.py
  公开：exec(cmd, args)
        │
  config.py (全局常量)        所有模块都可 import config
  DANGER_FORCE / WHITELIST_PATH / LOG_PATH
  但 config 不 import 任何业务模块
```

### 3.2 模块独立性约束（强制执行）

| 模块 | 允许 import | 禁止 import |
|---|---|---|
| `config.py` | 仅标准库（os, pathlib, platform） | 所有业务模块 |
| `executors/*` | config, 标准库（subprocess, shutil） | core, hooks, cli |
| `hooks/base.py` | config, 标准库（abc） | executors（由子类按需 import） |
| `hooks/rm_hook.py` `hooks/dd_hook.py` | hooks.base, executors, config, 标准库 | core, cli |
| `core/tty_detector.py` `core/ui.py` `core/validator.py` `core/whitelist.py` | config, 标准库 | hooks, executors, cli |
| `core/engine.py` | 所有 core 子模块 + hooks（只读拿 Hook 实例） | executors（通过 Hook 间接调用） |
| `cli.py` `__main__.py` | core.engine, config | executors, hooks 子模块, core 子模块（走 engine 公开方法） |

### 3.3 完整目录结构

```
danger_guard/
├── __init__.py
├── __main__.py          # 入口：python -m danger_guard
├── cli.py               # argparse 统一入口
├── core/
│   ├── __init__.py
│   ├── engine.py        # 三阶防护主流程编排
│   ├── tty_detector.py  # TTY / 非TTY判定
│   ├── validator.py     # B- 验证规则
│   ├── ui.py            # 红色警告框 + 彩色输出
│   └── whitelist.py     # ~/.danger-whitelist 解析
├── hooks/               # 钩子框架，每个命令一个文件
│   ├── __init__.py      # 插件注册表 + @register_hook 装饰器
│   ├── base.py          # BaseHook 抽象基类
│   ├── rm_hook.py       # rm 拦截器
│   └── dd_hook.py      # dd 拦截器
├── executors/
│   ├── __init__.py
│   ├── posix_exec.py    # subprocess 调用原生 rm/dd
│   └── windows_exec.py  # Remove-Item / PowerShell 路由
├── config.py            # 环境变量、白名单路径等常量
└── scripts/
    ├── install.sh        # Linux/macOS 安装脚本
    ├── install.ps1      # Windows 安装脚本
    └── uninstall         # 卸载（安装时自动生成对应版本）
```

---

## 四、钩子框架设计

### 4.1 BaseHook 抽象基类（hooks/base.py）

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import config

class PreviewResult:
    """预演结果数据类（值对象，无行为）"""
    affected_count: int           # 受影响文件/设备数
    total_size_bytes: int         # 总大小（字节）
    sample_items: List[str]       # 前 N 个样本路径/名
    target_scope: str             # 人类可读范围描述
    risk_level: int               # 1=低 2=中 3=高（决定警告框颜色深度）
    validation_pool: List[str]    # 随机抽取验证用的真实文件名/设备名
    extra_warnings: List[str]     # 额外警示行

class HookExecutionResult:
    """执行结果数据类"""
    success: bool
    exit_code: int
    message: Optional[str]

class BaseHook(ABC):
    name: str                                  # 命令名，如 "rm", "dd"
    native_commands: Dict[str, List[str]]      # 各平台原生命令映射

    @abstractmethod
    def parse_args(self, raw_args: List[str]) -> Dict:
        """解析该命令的原始参数，返回结构化 dict"""

    @abstractmethod
    def preview(self, parsed: Dict) -> PreviewResult:
        """预演计算：统计、样本、风险分级。禁止执行任何写操作。"""

    @abstractmethod
    def execute(self, parsed: Dict, dry_run: bool = False) -> HookExecutionResult:
        """真正执行原生命令。dry_run=True 时只打印将要执行的命令。"""

    def is_natively_supported(self, system: str) -> bool:
        """平台适配判断（公共工具，子类不得重写）"""
        return system in self.native_commands
```

### 4.2 自动注册机制（hooks/__init__.py）

使用装饰器 + `pkgutil` 自动扫描，实现"新建文件即生效"：

```python
import pkgutil, importlib
from typing import Dict, Type
from .base import BaseHook

_REGISTRY: Dict[str, Type[BaseHook]] = {}

def register_hook(cls: Type[BaseHook]) -> Type[BaseHook]:
    assert issubclass(cls, BaseHook)
    assert cls.name not in _REGISTRY, f"Hook 名称 {cls.name} 重复"
    _REGISTRY[cls.name] = cls
    return cls

def get_hook(name: str) -> Type[BaseHook]:
    _ensure_loaded()
    if name not in _REGISTRY:
        raise KeyError(f"未注册的 Hook: {name}，可用: {list(_REGISTRY)}")
    return _REGISTRY[name]

_LOADED = False

def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    for _finder, modname, _ispkg in pkgutil.iter_modules(__path__):
        if modname != "base":
            importlib.import_module(f"{__name__}.{modname}")
    _LOADED = True
```

**新增命令步骤（社区贡献者视角）**：
1. 在 `hooks/` 下新建 `foo_hook.py`
2. 继承 `BaseHook`，顶部加 `@register_hook`
3. 实现 3 个抽象方法
4. 结束。无需改 `__init__.py`、`cli.py`、`engine.py`。零侵入。

---

## 五、三阶防护主流程

### 5.1 Engine 编排（core/engine.py）

`run_pipeline()` 是对外唯一公开方法，内部严格按 7 步走，任何一步失败直接短路返回：

```
输入：command_name, raw_args, env
  │
  ▼ ①【TTY 检测】tty_detector.is_interactive()
  ├─ 否（脚本/cron）→ 直接放行 → goto ⑦ 执行
  └─ 是（交互 TTY）→ 继续
  │
  ▼ ②【白名单检查】whitelist.check(parsed_paths)
  ├─ 所有目标均在白名单内 → 打印"[白名单放行] /tmp" → goto ⑦
  └─ 部分或全部不在 → 继续
  │
  ▼ ③【一阶 · 参数预演与风险量化】hook.preview(parsed) → PreviewResult
  │
  ▼ ④【二阶 · 红色威慑警告框】ui.render_warning_box(preview)
  │   展示：目标范围、受影响文件数、总大小、风险等级、前 5 个样本
  │   提示：手动键入，允许写错字形，但直接复制粘贴的完全一致将被拒绝
  │
  ▼ ⑤【三阶 · B- 随机文件名验证】validator.run(preview)
  │   3 次机会，每次随机从 validation_pool 抽一个文件名
  │
  ▼ ⑥【用户最终确认】ui.final_confirm(preview)
  │   必须精确输入 DELETE（全大写）或按 Ctrl+C / N 取消
  │
  ▼ ⑦【执行】hook.execute(parsed) → HookExecutionResult
  │
输出：exit_code
```

### 5.2 警告框示例（ui.py 渲染）

```
┌══════════════════════════════════════════════┐
║  ⚠ 危险操作即将执行！DANGER!                ║
║                                              ║
║  目标范围：/data/projects/old/*              ║
║  受影响文件：1,284 个   总大小：15.6 GiB    ║
║  风险等级：███ 高危（删除不可恢复）          ║
║                                              ║
║  前 5 个受影响对象：                         ║
║    1. report_final_v3.docx                   ║
║    2. thesis_backup_20240312.pdf             ║
║    3. customer_db.sql                        ║
║    4. ...（列表见终端上方滚动）              ║
║                                              ║
║  [提示] 下面请手动键入文件名，允许写错字形， ║
║         但直接复制粘贴的完全一致将被拒绝。    ║
└══════════════════════════════════════════════┘
```

使用 ANSI 24 位真彩红色 + 粗体边框，非 TTY 时降级为纯文本。

---

## 六、B- 验证算法详细设计

### 6.1 验证规则

1. **忽略大小写**：`lower()` 统一
2. **形近字模糊容忍**：`O/0/Q`、`l/1/I/|`、`S/5`、`Z/2`、`B/8` 等形近字符互相视为等价
3. **完全精确匹配 = 拒绝**：如果用户输入与目标文件名字节级完全一致（说明是复制粘贴的），判定失败，强制人工输入

### 6.2 形近字等价类映射表

```python
_CONFUSABLE_GROUPS = [
    ('o', '0', 'q', '○', '●'),            # → 归一成 'o'
    ('l', '1', 'i', '|', 'Ι', 'Ⅰ'),       # → 归一成 'l'
    ('s', '5', '§'),                       # → 归一成 's'
    ('z', '2', 'ƻ'),                       # → 归一成 'z'
    ('b', '8', 'Β'),                       # → 归一成 'b'
    ('g', '9', 'q'),                       # → 归一成 'g'
    ('a', '@', 'α'),                       # → 归一成 'a'
    ('x', '×', '✕'),                       # → 归一成 'x'
    ('-', '—', '–', '_'),                  # → 归一成 '-'
    ('.', '。', '·'),                      # → 归一成 '.'
    (',', '，'),                           # → 归一成 ','
    ('!', '！', '¡'),                      # → 归一成 '!'
    ('?', '？', '¿'),                      # → 归一成 '?'
    ('+', '＋'),
    ('=', '＝'),
    ('(', '（', '['),                      # → 归一成 '('
    (')', '）', ']'),                      # → 归一成 ')'
    ("'", '’', '`', '´'),                  # → 归一成 "'"
    ('"', '”', '“', '«', '»'),             # → 归一成 '"'
    ('/', '\\', '／', '＼'),               # → 归一成 '/'
    (' ', '　'),                           # 全角空格 vs 半角
]
```

### 6.3 规范化函数

```
_normalize(s) = 逐字符查等价类表替换 → lower()
```

示例：
- `"Report_V3-Final.docx"` → `"report-v3-final.docx"`
- `"Rep0rt_V3—Final．docx"` → `"report-v3-final.docx"`（0→o，—→-，．→.）
- 两者规范化后相同 → 模糊匹配通过

### 6.4 B- 判定逻辑

```python
def validate(user_input: str, challenge_filename: str) -> Tuple[bool, str]:
    exact_match = (user_input.strip() == challenge_filename)
    if exact_match:
        return (False, "❌ 检测到直接复制粘贴，请手动键入并故意稍作改动")

    norm_user = _normalize(user_input.strip())
    norm_challenge = _normalize(challenge_filename)

    if norm_user == norm_challenge:
        return (True, "✅ 模糊匹配通过")
    else:
        dist = levenshtein(norm_user, norm_challenge)
        return (False, f"❌ 不匹配。还差 {dist} 个字符修正")
```

### 6.5 重试循环

- 3 次机会，每次随机从 `validation_pool` 抽一个文件名
- 失败后换文件名（不再用同一个，防止死磕）
- 3 次全部失败 → 打印"验证失败，操作已取消" → exit(1)
- 每次 `KeyboardInterrupt` → 打印"\n已取消（Ctrl+C）"→ exit(130)

### 6.6 验证界面提示语

```
[提示] 请手动键入下方文件名以确认你已阅读警告。
       允许写错字形（如 o/0、l/1 互通），但直接复制粘贴的
       完全一致将被拒绝——请故意稍作改动。
请输入文件名: ___
```

---

## 七、dd Hook 预览特殊性

`dd` 的受影响对象不是文件树，而是块设备/文件。其 `preview()` 逻辑：

```
parsed.of 指向路径：
  ├─ 是块设备（/dev/sda, /dev/mmcblk0）→ risk_level=3
  │    affected_count = 1
  │    total_size = ioctl(BLKGETSIZE64) 读设备大小
  │    sample_items = ["/dev/sda → 512 GiB SSD"]
  │    validation_pool = ["/dev/sda", "Samsung SSD 860", "512.1 GB"]
  │    extra_warnings = ["⚠ 目标为块设备！将破坏分区表与所有数据"]
  ├─ 是已有普通文件 → risk_level=2（覆盖文件）
  ├─ 不存在 → risk_level=1（新建文件，通常无害，但仍做防护）
```

dd 不做递归遍历，通过 `os.stat()` + 可选 `shutil.disk_usage()` 计算。

---

## 八、跨平台适配

### 8.1 系统检测（config.py）

```python
def detect_system() -> str:
    s = platform.system()
    if s.startswith("CYGWIN") or s.startswith("MINGW") or s.startswith("MSYS"):
        return "Windows"
    return s if s in ("Linux", "Darwin", "Windows") else "Linux"
```

### 8.2 executors 平台差异

| 执行器 | 命令 | 实现方式 |
|---|---|---|
| `posix_exec.exec_rm` | rm | `subprocess.run(["/bin/rm"] + args)` — 绝对路径避免 alias 递归 |
| `posix_exec.exec_dd` | dd | `subprocess.run(["/bin/dd"] + args)` |
| `windows_exec.exec_remove_item` | Remove-Item | `subprocess.run(["powershell", "-NoProfile", "-Command", ...])` — NoProfile 避免 $PROFILE 别名递归 |
| `windows_exec.exec_dd` | dd（WSL/Git Bash） | 优先找 `dd.exe`，找不到报错提示 |

**防递归别名关键**：executors 层一律不经过 Shell alias，用绝对路径或 `-NoProfile`。

### 8.3 安装脚本

**Linux/macOS（install.sh）**：
1. 找 python3（≥3.7）
2. pip install
3. 生成还原点备份目录
4. 在 `.bashrc`/`.zshrc`/`.config/fish/config.fish` 末尾追加 alias
5. 生成 `ohshit-uninstall` 脚本

**Windows（install.ps1）**：
1. pip install
2. 在 `$PROFILE` 写入 PowerShell function + Set-Alias
3. 生成 `ohshit-uninstall.ps1`

**应急还原**：用户输入 `\rm`（Bash/Zsh）或 `command rm` 即可临时绕过 alias。

---

## 九、错误处理矩阵

| 场景 | 行为 | 退出码 |
|---|---|---|
| 非 TTY 调用 | 直接执行原生命令，不输出任何警告 | 同原生命令 |
| DANGER_FORCE=1 | 跳过所有防护，直接执行 | 同原生命令 |
| Ctrl+C 任何阶段 | 捕获 → 打印"\n已取消（Ctrl+C）"→ 退出 | 130 |
| 3 次 B- 验证全失败 | "验证失败，操作已取消。若确认无误请检查命令或使用 DANGER_FORCE=1" | 1 |
| Hook 未注册 | "未注册的命令：{name}，可用: rm, dd" | 2 |
| preview() 权限不足 | 统计能读的，警告框加"⚠ N 个目录权限不足，统计可能偏小"，继续流程 | 不影响 |
| 原生命令执行失败 | 透传 exit_code 和 stderr | 透传 |
| 意外异常 | 捕获 → 红色"💥 OhShit 内部故障：{exc}"→ **兜底直接执行原生命令**→ traceback 写 ~/.danger.log | 透传 |

最后一条是安全兜底：OhShit 自身崩了，绝不挡住用户正常操作。

---

## 十、分发策略

| 分发渠道 | 方案 | 稳定性 | 说明 |
|---|---|---|---|
| 主力：pip + 安装脚本 | `pip install danger-guard` + `curl install.sh \| bash` | 极稳 | 不依赖打包 |
| 备选：zipapp | `python -m zipapp danger_guard -o ohshit.pyz -m "danger_guard.__main__:main"` | 极稳 | 标准库，零外部依赖 |
| PyInstaller：尽力而为 | 本地测试环境能过就出二进制 | 不兜底 | 只在本机 Linux/macOS 尝试，Windows 作为社区贡献项 |

PyInstaller **不作为** MVP 交付的阻塞条件。

---

## 十一、测试策略

| 层级 | 测试文件 | 覆盖内容 | 用例数 |
|---|---|---|---|
| 单元 | `tests/test_validator.py` | B- 规范化、形近字表、反复制粘贴、3 次重试 | ~20 |
| 单元 | `tests/test_whitelist.py` | 白名单解析（注释/空行/通配/相对路径）、默认白名单 | ~10 |
| 单元 | `tests/test_hooks_rm.py` | rm 参数解析、preview 统计（数量/大小/隐藏文件/符号链接）、validation_pool | ~12 |
| 单元 | `tests/test_hooks_dd.py` | dd 参数解析（if=/of=/bs=）、块设备检测降级 | ~8 |
| 单元 | `tests/test_ui.py` | 警告框渲染（mock TTY + ANSI）、人类可读大小格式 | ~5 |
| 集成 | `tests/test_engine_smoke.py` | 临时目录 + fake TTY + monkeypatch stdin，跑完整 pipeline（dry_run=True） | ~5 |
| **合计** | | | **~60** |

**不做的事**：不配置 GitHub Actions CI、不做 Windows 真机组测试（用 monkeypatch 模拟）、不做 PyInstaller 打包测试。
