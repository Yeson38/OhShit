# tests/test_scripts_install.py — 安装脚本的 TDD 用例（沙箱 HOME 不污染真实用户）
"""
本文件用 pytest 做 Shell 脚本的行为测试：
- 构造临时 HOME 目录，执行 install.sh / install.ps1
- 验证 3 项缺失能力：Fish 注入、Linux 真·卸载脚本、Windows 卸载模板
- 用 OHSHIT_TEST_SKIP_PIP=1 跳过真实 pip 安装，加速并避免网络依赖
"""
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

INSTALL_SH = Path(__file__).resolve().parents[1] / "danger_guard" / "scripts" / "install.sh"
INSTALL_PS1 = Path(__file__).resolve().parents[1] / "danger_guard" / "scripts" / "install.ps1"

# ---- helpers ----

def _run_install_sh(tmp_home: Path) -> subprocess.CompletedProcess:
    """在沙箱 HOME 中执行 install.sh（跳过真实 pip 安装）。"""
    env = os.environ.copy()
    env["HOME"] = str(tmp_home)
    env["OHSHIT_TEST_SKIP_PIP"] = "1"
    env["XDG_CONFIG_HOME"] = str(tmp_home / ".config")   # Fish 规范
    # Fish 默认读 ~/.config/fish ，XDG_CONFIG_HOME 已覆盖
    return subprocess.run(
        ["bash", str(INSTALL_SH)],
        env=env, capture_output=True, text=True, timeout=120,
    )


def _file_mode_x(path: Path) -> bool:
    return bool(path.stat().st_mode & stat.S_IXUSR)


# =========================================================
# TEST F1 — Fish 段缺失
# 修复前断言：config.fish 中必须出现 FISH 原生 alias 语法 alias rm 'dang -- rm'
#            （注意是空格分隔，不是 bash 的 alias rm='...' 等号写法）
# =========================================================
def test_install_sh_injects_fish_aliases_with_fish_syntax(tmp_path):
    tmp_home = tmp_path / "home"
    tmp_home.mkdir()
    # 预先模拟 Fish RC 文件已存在（更严格的注入检查：不得覆盖，只可追加到末尾）
    fish_conf = tmp_home / ".config" / "fish" / "config.fish"
    fish_conf.parent.mkdir(parents=True, exist_ok=True)
    fish_conf.write_text("# pre-existing fish config\nset -g fish_greeting\n", encoding="utf-8")

    result = _run_install_sh(tmp_home)
    # install.sh 本身必须成功退出（exit 0）
    assert result.returncode == 0, f"install.sh 非0退出:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    assert fish_conf.exists(), "Fish config.fish 不存在——install.sh 未注入 Fish"
    content = fish_conf.read_text(encoding="utf-8")

    # 1) marker 段必须包含（和 bashrc/zshrc 保持一致，便于 uninstall 统一删除）
    assert ">>> OhShit 删库跑路预防针 >>>" in content, (
        f"config.fish 缺少注入 marker，当前内容：\n{content}"
    )
    assert "<<< OhShit 删库跑路预防针 <<<" in content

    # 2) FISH 原生语法 alias（空格分隔参数，不是 =）
    #    ❌ 错误（Bash 语法污染到 Fish，Fish 会当成 function name=value 字符串报错）：alias rm='dang -- rm'
    #    ✅ 正确（Fish 原生）：alias rm 'dang -- rm'
    fish_alias_pattern = re.compile(r"^\s*alias\s+rm\s+'dang -- rm'\s*$", re.MULTILINE)
    assert fish_alias_pattern.search(content), (
        "config.fish 中未找到 Fish 原生语法 alias rm 'dang -- rm'（不能是 Bash 式 alias rm=...）。\n"
        f"Fish config 相关片段：\n{content}"
    )
    fish_alias_dd = re.compile(r"^\s*alias\s+dd\s+'dang -- dd'\s*$", re.MULTILINE)
    assert fish_alias_dd.search(content), "config.fish 中未找到 Fish 原生语法 alias dd 'dang -- dd'"

    # 3) Fish 交互判断（status is-interactive 或 [[ $- == *i* ]] 中前者优先，后者也行，但
    #    不能直接在非交互 shell 下 set alias 会污染 scp/non-interactive 管道模式）
    assert ("status is-interactive" in content) or ("$- == *i*" in content), (
        "Fish 段未加交互检查，会污染 scp / rsync 等非交互登录环境。"
    )

    # 4) 原来的预置内容必须保留（不能覆盖原 config.fish）
    assert "set -g fish_greeting" in content, (
        "原来的 Fish config 预置行被 install.sh 覆盖了！必须追加，不能覆盖写。"
    )


# =========================================================
# TEST U1 — Linux 真·ohshit-uninstall 脚本缺失（之前只是 echo 别名假的）
# =========================================================
def test_install_sh_writes_real_ohshit_uninstall_executable(tmp_path):
    tmp_home = tmp_path / "home"
    tmp_home.mkdir()

    result = _run_install_sh(tmp_home)
    assert result.returncode == 0, f"install.sh 非0退出:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    bin_dir = tmp_home / ".local" / "bin"
    uninstall = bin_dir / "ohshit-uninstall"

    # A) 必须是真实文件 + 可执行
    assert uninstall.is_file(), (
        f"未生成 {uninstall}！之前只在 .ohshit-aliases.sh 写了一个『echo 提示用户复制命令』的假 alias。"
    )
    assert _file_mode_x(uninstall), f"{uninstall} 不是可执行文件（缺少 chmod +x）。"

    content = uninstall.read_text(encoding="utf-8")

    # B) 不能是假 alias（之前版本的 echo 提示版）—— 必须真的含 sed pip rm 命令
    assert "alias ohshit-uninstall=" not in content, (
        "生成的 ohshit-uninstall 里包含 alias 声明，这是之前假 alias 的 echo 内容，不是真脚本。"
    )

    # C) 必须含 sed 范围删除（删除 3 个 RC 文件中 marker 之间整段注入）
    #    sed range delete 模式：/^# >>> OhShit.*预防针 >>>$/,/^# <<< OhShit.*预防针 <<<$/d
    #    只要出现「sed」且出现「预防针.*d」或 sed 的 range 形式任一种即视为实现
    has_sed_range = bool(re.search(
        r"sed[^;\n]*#\s*>>>\s*OhShit.*预防针\s*>>>.*#\s*<<<\s*OhShit.*预防针\s*<<<.*d",
        content, flags=re.DOTALL,
    )) or ("sed " in content and "预防针" in content and (" -i " in content or " -i.bak" in content or ".bak" in content))
    assert has_sed_range, (
        "ohshit-uninstall 必须包含 sed 范围删除命令（删除 ~/.bashrc / ~/.zshrc / ~/.config/fish/config.fish 中 marker 块）。\n"
        f"当前脚本内容开头 40 行：\n" + "\n".join(content.splitlines()[:40])
    )

    # D) 必须含 pip uninstall -y danger-guard （不要求必须成功，continue on error 即可）
    assert ("pip uninstall -y danger-guard" in content) or ("pip uninstall --yes danger-guard" in content), (
        "ohshit-uninstall 必须调用 python -m pip uninstall -y danger-guard 来彻底卸载 pip 包，"
        "否则用户手动 pip show danger-guard 还在。"
    )

    # E) 必须含 wrapper 删除：~/.local/bin 下 dang 和 ohshit 两者都要被 rm 掉
    #    允许两种实现：(a) 硬编码路径 ~/.local/bin/dang 或 (b) 通过 WRAPPER_DIR/.local/bin 变量 + 文件名拼接
    lines = content.splitlines()
    has_local_bin = any((".local/bin" in ln) for ln in lines)
    has_rm_dang   = any((("dang" in ln and "rm " in ln and "ohshit" not in ln.split("rm ")[-1] if "rm " in ln else False)
                         or ("WRAPPER_DIR" in ln and "/dang" in ln and "rm " in ln)) for ln in lines)
    has_rm_ohshit = any((("ohshit.cmd" not in ln and "/ohshit" in ln and "rm " in ln)
                         or ("WRAPPER_DIR" in ln and "/ohshit" in ln and "rm " in ln)
                         or ("/ohshit" in ln and "rm " in ln and "aliases" not in ln)) for ln in lines)
    # 更稳妥：必须出现 .local/bin 路径关键字，且脚本某处同时明确 rm 了 dang 和 ohshit 两个名字
    assert has_local_bin, "ohshit-uninstall 必须指向 ~/.local/bin 作为 wrapper 目录"
    dang_mentioned = bool(re.search(r"\brm\b.*[^\w.-]dang(?![.-])", content)) or (
        "WRAPPER_DIR" in content and '"/dang"' in content
    )
    ohshit_mentioned = bool(re.search(r"\brm\b.*/ohshit\b", content)) or (
        "WRAPPER_DIR" in content and '"/ohshit"' in content
    )
    assert dang_mentioned, (
        "ohshit-uninstall 必须调用 rm 删除 dang wrapper（允许硬编码路径或 WRAPPER_DIR 拼接）。"
    )
    assert ohshit_mentioned, (
        "ohshit-uninstall 必须调用 rm 删除 ohshit wrapper（允许硬编码路径或 WRAPPER_DIR 拼接）。"
    )

    # F) 必须含 ~/.ohshit-aliases.sh 删除
    assert ".ohshit-aliases.sh" in content, "ohshit-uninstall 必须删除 ~/.ohshit-aliases.sh"

    # G) 自删：脚本最后一行或接近尾处 rm "$0"
    assert ('rm -f -- "$0"' in content) or ('rm -f "$0"' in content) or ('rm "$0"' in content), (
        "ohshit-uninstall 必须自删（rm -f -- \"$0\"），否则卸载后残留 uninstaller 本身。"
    )

    # H) 成功提示（绿色 ✅ 或 log_ok 格式）
    assert (
        ("✅" in content and "卸载" in content)
        or ("log_ok" in content and "卸载" in content)
        or ("卸载完成" in content)
    ), "ohshit-uninstall 必须打印一行绿色卸载完成信息（带 ✅ 或 log_ok）。"


# =========================================================
# TEST W1 — Windows install.ps1 必须生成 ohshit-uninstall.ps1（静态模板校验 + 沙箱中 pwsh dry）
# =========================================================
def test_install_ps1_generates_ohshit_uninstall_ps1_with_required_steps():
    ps1_text = INSTALL_PS1.read_text(encoding="utf-8")

    # 1) 安装脚本本身必须生成 ohshit-uninstall.ps1 文件（模板内必须有文件名引用）
    assert "ohshit-uninstall.ps1" in ps1_text, (
        "install.ps1 里没有提到 ohshit-uninstall.ps1——卸载脚本生成逻辑完全缺失。"
    )
    assert (
        (("Join-Path $BinDir" in ps1_text) and ("ohshit-uninstall.ps1" in ps1_text))
        or (("Set-Content" in ps1_text) and ("ohshit-uninstall.ps1" in ps1_text))
    ), (
        r"install.ps1 必须通过 Set-Content (或 Out-File) 把模板写入 $BinDir\ohshit-uninstall.ps1，"
        "现在只有字符串引用，没有实际写入动作。"
    )

    # 2) 卸载模板必须包含：$PROFILE 的 marker 段删除（PowerShell 多行 regex (?ms) 形式最佳）
    #    接受两种实现：
    #      a) -replace 形式带 (?ms)： '(?ms)\s*#\s*>>>\s*OhShit.*?预防针.*?#\s*<<<\s*OhShit.*?预防针\s*<<<\s*'
    #      b) Get-Content + Select-String -NotMatch + marker 行号上下界跳过 （不推荐但允许）
    has_profile_cleanup = bool(re.search(
        r"\(\?ms\).*OhShit.*预防针", ps1_text, flags=re.DOTALL,
    )) or bool(re.search(
        r"#\s*>>>\s*OhShit\s+删库跑路预防针\s*>>>.*#\s*<<<\s*OhShit\s+删库跑路预防针\s*<<<",
        ps1_text, flags=re.DOTALL,
    ))
    assert has_profile_cleanup, (
        "生成的 ohshit-uninstall.ps1 模板必须包含 PowerShell $PROFILE marker 范围删除 regex "
        "（推荐用 (?ms) 多行模式）。请对照计划 Task 9 Step 3。"
    )

    # 3) 必须含 python -m pip uninstall -y danger-guard（卸载 pip 包）
    assert ("pip uninstall -y danger-guard" in ps1_text) or ("pip uninstall --yes danger-guard" in ps1_text), (
        "ohshit-uninstall.ps1 模板必须调用 python -m pip uninstall -y danger-guard 彻底卸载包。"
    )

    # 4) 必须含自删：Remove-Item $MyInvocation.MyCommand.Path（或相同语义）
    self_del = (
        ("Remove-Item" in ps1_text and "MyInvocation.MyCommand.Path" in ps1_text)
        or ("Remove-Item" in ps1_text and "-Force" in ps1_text and "$PSCommandPath" in ps1_text)
        or ('Remove-Item $MyInvocation.MyCommand.Path' in ps1_text)
    )
    assert self_del, (
        "ohshit-uninstall.ps1 模板必须自删（Remove-Item $MyInvocation.MyCommand.Path -Force）。"
    )

    # 5) 必须含会话内 alias 清理（Remove-Alias / Remove-Item Alias:）
    has_alias_cleanup = (
        "Remove-Alias" in ps1_text
        or ("Remove-Item" in ps1_text and "Alias:" in ps1_text)
        or ('Remove-Item -Path Alias:\rm' in ps1_text)
    )
    assert has_alias_cleanup, (
        "ohshit-uninstall.ps1 模板必须清理当前会话中的 rm/dd alias（Remove-Alias rm,dd 或 Remove-Item Alias:\\rm），"
        "否则用户不重新开 PowerShell，rm 仍会拦截。"
    )

    # 6) 必须含绿色✅ 成功提示（Write-Host -ForegroundColor Green 或 Write-Ok 模板内复用）
    has_green_success = bool(re.search(
        r"(ForegroundColor\s+Green|Write-Ok).*(卸载|完成|✅)", ps1_text, flags=re.DOTALL | re.IGNORECASE,
    )) or ("✅" in ps1_text and "卸载" in ps1_text)
    assert has_green_success, (
        "ohshit-uninstall.ps1 模板必须包含绿色的 ✅ 卸载完成提示（和安装脚本对称）。"
    )
