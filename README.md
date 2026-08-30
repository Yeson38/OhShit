# OhShit
删库跑路预防针

## Quick Start（30 秒上手）

### 1. 安装（Linux / macOS）

```bash
# 从仓库本地安装（推荐开发/试用）
git clone https://<your-repo>/OhShit.git && cd OhShit
bash danger_guard/scripts/install.sh
source ~/.bashrc           # 或 source ~/.zshrc
# Fish 用户： source ~/.config/fish/config.fish
```

安装后会：
- 写 `~/.local/bin/dang` 与 `~/.local/bin/ohshit` 两个入口
- 在 `~/.bashrc` / `~/.zshrc` 里注入 `source ~/.ohshit-aliases.sh`
- **在 `~/.config/fish/config.fish` 额外注入 Fish 原生 alias（`alias rm 'dang -- rm'`），Fish 开箱即用**
- 额外生成真·一键卸载可执行：`~/.local/bin/ohshit-uninstall`（自清理 RC + pip 包 + wrappers，运行后自删）
- `rm` / `dd` 在交互 shell 下变成 `dang -- rm` / `dang -- dd`

### 2. 安装（Windows / PowerShell）

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
git clone https://<your-repo>/OhShit.git ; cd OhShit
.\danger_guard\scripts\install.ps1
# 之后重新开一个 PowerShell 窗口（加载 Profile 与用户 PATH）
```

安装后会：
- 写 `~\.ohshit\bin\dang.cmd` 和 `ohshit.cmd`，并自动把 `~\.ohshit\bin` 加入用户级 PATH
- 在 `$PROFILE` 中注入交互友好的 `function global:Remove-Item`（-Recurse -Force 命中根路径才拦截；其余命令直通原生命令）
- 额外生成一键卸载脚本：`~\.ohshit\bin\ohshit-uninstall.ps1`（用 `(?ms)` regex 清理 Profile 注入段 + pip uninstall + 自删）

### 3. 方式 2：pip 安装（无需 clone / 无需 root）

```bash
# 装到用户目录（推荐：不污染系统 site-packages）
pip install --user danger-guard

# 之后手动加 alias 到 ~/.bashrc / ~/.zshrc
alias rm='dang -- rm'
alias dd='dang -- dd'
```

> 注：PyPI 包名 `danger-guard`，装完后 `dang` / `ohshit` 两个命令都可以用（等价）。

### 4. 方式 3：zipapp 零依赖单文件（无 pip、无网络也能部署）

Python 3.5+ 自带 `zipapp` 模块，把整个项目打成一个可直接执行的 `.pyz`（因为包根目录已有 `__main__.py`，zipapp 会自动用它作为入口，无需额外指定 `-m`）：

```bash
cd OhShit
python -m zipapp danger_guard -o ohshit.pyz

# 放到系统 PATH 里，就成了全局单文件命令
sudo mv ohshit.pyz /usr/local/bin/ohshit
# 一样用法：
ohshit --list-hooks
alias rm='ohshit -- rm'
```

> 适合离线服务器、Docker 镜像精简、或审计合规要求「不能装 PyPI 包」的场景。无第三方依赖。

### 5. 手动 CLI 用法（不装 alias 也能用）

```bash
# 查看已注册的 hook
dang --list-hooks

# 预览效果 —— 绝不真正执行
dang --dry-run -- rm -rf ~/Downloads/*

# 真实执行（会弹出红框 + B- 验证）
dang -- rm -rf ~/Downloads/*
dang -- dd if=/dev/zero of=/tmp/out.img bs=4M count=100

# 紧急：跳过 B- 验证（懂的才用）
DANGER_FORCE=1 dang -- rm -rf /tmp/stale_cache
dang --force -- rm -rf /tmp/stale_cache
```

### 6. 白名单配置

编辑 `~/.danger-whitelist`（路径可通过 `DANGER_WHITELIST` 环境变量覆盖），一行一条路径，支持：
- `~` 展开到当前用户 home
- 环境变量 `$VAR` / `${VAR}` 展开
- 通配符 `*`、`?`、`[abc]`（`fnmatch` 语义）
- `#` 开头整行注释；行尾空格 + `#` 加内联注释也支持
- 末尾不带 `/*` 的目录 = 该目录下所有文件及子目录都放行（前缀匹配）

```
# 一行一条路径，支持 glob、~、$VAR
~/Downloads

# 公司各项目的 node_modules（肯定可以随便删）
/data/projects/*/node_modules

# CI 临时目录
/tmp  # 默认白名单已含 /tmp，这里写出来仅示范

# 个人重要备份不经过保护（谨慎使用）
$HOME/old_backups
```

> 默认白名单：`/tmp`、`/var/tmp`、`/dev/shm`、`/private/tmp`、`$TMPDIR`、`$TEMP`、`$TMP`、`~/.cache/*`、`/dev/null`。以上无需重复写。

### 7. 环境变量速查表

| 变量名 | 有效值 | 说明 |
|---|---|---|
| `DANGER_FORCE` | `1` / `true` / `yes` / `on`（大小写不敏感，strip 后比较） | 跳过所有三阶防护与警告框，直接透传给原生命令。用于 CI/CD、脚本自动化。等价于 CLI 加 `--force` flag。 |
| `DANGER_WHITELIST` | 绝对或相对路径（指向文本文件） | 覆盖默认白名单文件位置 `~/.danger-whitelist`。团队共用一份白名单时设成共享路径即可。 |
| `DANGER_LOG` | 绝对或相对路径（指向 JSON Lines 日志） | 覆盖默认审计日志位置 `~/.danger.log`。每次成功执行/取消/失败会写一行 JSON（含时间戳、命令、参数、count、size、risk level、exit code、错误消息）。写失败静默，不阻塞主流程。 |
| `NO_COLOR` | 任意非空字符串（标准环境变量） | 禁用终端 ANSI 彩色输出。用于 CI 日志收集、不支持 ANSI 的终端、`| grep` 管线。 |

### 8. 防护流程

当你执行高风险命令时，会看到：

1. **红色警告框**：列出受影响对象数、估算总大小、风险等级 1–3，风险≥3 自动加粗红色边框
2. **示例预览**：最多 10 条实际会被删掉的文件名（含完整路径）
3. **B- 人机验证**：随机从 validation_pool 抽 1 个文件名让你手动输入（3 次机会，每次失败会自动换题，避免死磕同一个）
   - ✅ 通过的情况：
     - 完全手打的精确匹配（一字不差 = 一次通过）
     - 只改大小写（`Report_Final.DOCX` vs `report_final.docx`）
     - 字形混淆（O↔0、l↔1↔I、S↔5、Z↔2、B↔8、G↔9、符号全半角、括号、斜杠/反斜杠…共 27 组等价类）
     - 前后多打空格（自动 strip）
   - 粘贴检测（不计入配额，系统会要求手动输入而非粘贴）：
     - 逐字符输入间隔 < 4ms 连续出现 3 次以上（典型粘贴爆发速度）
     - Bracketed Paste Marker：检测到 `\x1b[200~` 或 `\x9b200~` 开头 + `\x1b[201~` 或 `\x9b201~` 结尾（终端原生粘贴协议 7-bit + 8-bit 双编码都拦截）
     - 整行从出现到回车 < 120ms 打完（正常人打字速度 ≫120ms/行）
     - Windows PowerShell PSReadLine：粘贴后 ReadKey 返回空串立即被 `msvcrt.getwch()` 第二轮感知
   - 错误输入（扣 1 次配额）：字形/字母不符时，系统会显示编辑距离与常见形近字参考。
4. **通过后执行 rm/dd**：执行结果会追加一行 JSON 到 `~/.danger.log`（可审计）

> 命令目标位于白名单目录（如 `/tmp/*`）且 risk_level=1 时直接放行。stdin/stdout 任一非 TTY（脚本/cron/CI 管道模式）自动跳过验证层，不阻塞自动化流程。

### 9. 卸载

按你当初的安装方式选对应命令：

#### 方式 A：用 `bash danger_guard/scripts/install.sh` 安装（Linux / macOS / Fish，通用一键）

```bash
# 安装脚本已在 ~/.local/bin 下生成了真·可执行卸载脚本（它会：sed 批量删除 3 个 RC 文件中的 OhShit marker 注入段
# → rm ~/.ohshit-aliases.sh → pip uninstall -y danger-guard → 删除 dang/ohshit wrapper → 脚本自删）
ohshit-uninstall

# 卸载完若当前终端别名仍生效，按 shell 选一条重启：
exec bash    # 或 exec zsh  或 exec fish
```

Fish shell 用户：`ohshit-uninstall` 会同步清理 `~/.config/fish/config.fish` 中的原生 alias 注入段（与 Bash/Zsh 使用同一 marker 体系）。

#### 方式 B：用 PowerShell `.\danger_guard\scripts\install.ps1` 安装（Windows 一键）

```powershell
# 安装脚本在 ~\.ohshit\bin 下生成了 ohshit-uninstall.ps1
& $env:USERPROFILE\.ohshit\bin\ohshit-uninstall.ps1
```

脚本按顺序执行：从 `$PROFILE` 多行正则移除 Remove-Item 包装函数段 → 执行 `python -m pip uninstall -y danger-guard` → 删除 dang.cmd / ohshit.cmd 包装命令 → 会话级 `Remove-Alias rm,dd` 并恢复原版 `global:Remove-Item` → 保留 `.ohshit` 备份目录防误删 → 延迟自删卸载脚本自身。

#### 方式 C：pip 安装（§3）

```bash
python -m pip uninstall -y danger-guard
# 若之前手动往 ~/.bashrc 加了 alias，手动再删一下对应行即可
```

#### 方式 D：zipapp 单文件（§4）

```bash
# 把放到 PATH 里的 ohshit.pyz 直接删掉就行
sudo rm -f /usr/local/bin/ohshit    # 或你 mv 过去的自定义路径
```

> 🔒 所有卸载方式都 **默认保留 `~/.ohshit` 下的备份目录与 `~/.danger.log` 审计日志**，避免误伤用户重要备份或审计证据。如确实要彻底清理可手动 `rm -rf ~/.ohshit ~/.danger.log`。

### 10. 开发者测试

```bash
cd OhShit
python -m pytest tests/ -q
```


