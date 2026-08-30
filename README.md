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

### 3. 手动 CLI 用法（不装 alias 也能用）

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

### 4. 验证防护（必须看）

当你执行高风险命令时，会看到：

1. **红色警告框**：列出受影响对象数、估算总大小、风险等级 1–3
2. **示例预览**：最多 10 条实际会被删掉的文件名
3. **B- 验证**：随机让你输入 1 个文件名（3 次机会）
   - ✅ 允许：改大小写、把 O 看成 0、l 看成 1、S→5、Z→2、B→8、G→9…（形近字模糊匹配）
   - ⚠️ 拒绝：**一字不差复制粘贴**（强迫你"读一遍再敲"）
4. **通过才执行**

### 5. 卸载

```bash
rm ~/.local/bin/dang ~/.local/bin/ohshit ~/.ohshit-aliases.sh
sed -i '/ohshit-aliases/d' ~/.bashrc ~/.zshrc
```

### 6. 自测（开发者）

```bash
cd OhShit
python -m pytest tests/ -q   # 全量测试（~80 条）
```
