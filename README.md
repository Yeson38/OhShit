# OhShit
删库跑路预防针

## Quick Start（30 秒上手）

### 1. 安装（Linux / macOS）

```bash
# 从仓库本地安装（推荐开发/试用）
git clone https://<your-repo>/OhShit.git && cd OhShit
bash danger_guard/scripts/install.sh
source ~/.bashrc  # 或 source ~/.zshrc
```

安装后会：
- 写 `~/.local/bin/dang` 与 `~/.local/bin/ohshit` 两个入口
- 在 `~/.bashrc` / `~/.zshrc` 里注入 `source ~/.ohshit-aliases.sh`
- `rm` / `dd` 在交互 shell 下变成 `dang -- rm` / `dang -- dd`

### 2. 安装（Windows / PowerShell）

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
git clone https://<your-repo>/OhShit.git ; cd OhShit
.\danger_guard\scripts\install.ps1
# 之后重新开一个 PowerShell 窗口
```

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
| `DANGER_FORCE` | `1` / `true` / `yes` / `on`（大小写不敏感，strip 后比较） | 跳过所有三阶防护（红色警告框仍会打印？→**否：连警告框都不打，直接透传给原生命令**）。用于 CI/CD、脚本自动化。等价于 CLI 加 `--force` flag。 |
| `DANGER_WHITELIST` | 绝对或相对路径（指向文本文件） | 覆盖默认白名单文件位置 `~/.danger-whitelist`。团队共用一份白名单时设成共享路径即可。 |
| `DANGER_LOG` | 绝对或相对路径（指向 JSON Lines 日志） | 覆盖默认审计日志位置 `~/.danger.log`。每次成功执行/取消/失败会写一行 JSON（含时间戳、命令、参数、count、size、risk level、exit code、错误消息）。写失败静默，不阻塞主流程。 |
| `NO_COLOR` | 任意非空字符串（标准环境变量） | 禁用终端 ANSI 彩色输出。用于 CI 日志收集、不支持 ANSI 的终端、`| grep` 管线。 |

### 8. 验证防护（必须看）

当你执行高风险命令时，会看到：

1. **红色警告框**：列出受影响对象数、估算总大小、风险等级 1–3，风险≥3 自动加粗红色边框
2. **示例预览**：最多 10 条实际会被删掉的文件名（含完整路径）
3. **B- 人机验证**：随机从 validation_pool 抽 1 个文件名让你手动输入（3 次机会，每次失败会自动换题，避免死磕同一个）
   - ✅ 通过的情况：
     - 完全手打的精确匹配（一字不差 = 一次通过）
     - 只改大小写（`Report_Final.DOCX` vs `report_final.docx`）
     - 字形混淆（O↔0、l↔1↔I、S↔5、Z↔2、B↔8、G↔9、符号全半角、括号、斜杠/反斜杠…共 27 组等价类）
     - 前后多打空格（自动 strip）
   - ⚠️ 不扣次数的重试（不计入 3 次配额，会要求「请手打，不要复制粘贴」）：
     - 逐字符输入间隔 < 4ms 连续出现 3 次以上（典型粘贴爆发速度）
     - Bracketed Paste Marker：检测到 `\x1b[200~` 或 `\x9b200~` 开头 + `\x1b[201~` 或 `\x9b201~` 结尾（终端原生粘贴协议 7-bit + 8-bit 双编码都拦截）
     - 整行从出现到回车 < 120ms 打完（正常人打字速度 ≫120ms/行）
     - Windows PowerShell PSReadLine：粘贴后 ReadKey 返回空串立即被 `msvcrt.getwch()` 第二轮感知
   - ❌ 真错误（扣 1 次配额）：字形/字母明显不对，会给你「还差 N 个字符」的编辑距离提示和常见形近字替换参考示例
4. **验证通过才执行 rm/dd**：执行结果会追加一行 JSON 到 `~/.danger.log`（可审计）

> 注：如果命令目标在白名单目录（`/tmp/*` 等）且 risk_level=1，会直接放行不会出验证框（这些就是临时文件，删了不心疼）。如果 stdin/stdout 任意一个不是 TTY（脚本/cron/CI 管道模式）则自动跳过整个验证层（不阻塞自动化）。

### 9. 卸载

```bash
# 一键删除本地安装 + 注入项（install.sh 创建的路径）
rm ~/.local/bin/dang ~/.local/bin/ohshit ~/.ohshit-aliases.sh ~/.ohshit -rf 2>/dev/null
sed -i '/ohshit-aliases/d' ~/.bashrc ~/.zshrc

# 若用 pip 安装的方式 2：
pip uninstall -y danger-guard

# 若用 zipapp 方式 3：
sudo rm -f /usr/local/bin/ohshit
```

### 10. 自测（开发者）

```bash
cd OhShit
python -m pytest tests/ -q   # 全量测试（当前 105 passed）
```
