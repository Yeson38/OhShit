#!/usr/bin/env bash
# OhShit 一键安装脚本（Linux / macOS）
# 用法：  bash <(curl -fsSL https://<domain>/install.sh)
# 或者本地：bash danger_guard/scripts/install.sh

set -euo pipefail

log_info()  { printf "\033[36m[ohshit install]\033[0m %s\n" "$*"; }
log_warn()  { printf "\033[33m[ohshit install]\033[0m %s\n" "$*" >&2; }
log_ok()    { printf "\033[32m[ohshit install]\033[0m %s\n" "$*"; }
log_err()   { printf "\033[31m[ohshit install]\033[0m %s\n" "$*" >&2; }

# ---------- 基础检查 ----------
if [ "${EUID:-$(id -u)}" = "0" ]; then
  log_warn "当前为 root 用户。建议在普通用户下执行以写家目录 .bashrc/.zshrc。"
fi

case "$(uname -s)" in
  Linux|Darwin) ;;
  *) log_err "未识别的 OS: $(uname -s)，此安装脚本仅支持 Linux / macOS。Windows 用户请使用 install.ps1。"; exit 1 ;;
esac

# ---------- 依赖检查 ----------
command -v python3 >/dev/null 2>&1 || { log_err "缺少 python3。请先安装 Python 3.7+"; exit 1; }
PY_VER_OK=$(python3 -c "import sys; sys.exit(0 if sys.version_info>=(3,7) else 1)" && echo 1 || echo 0)
[ "$PY_VER_OK" = "1" ] || { log_err "Python 版本过低：$(python3 -V)，需要 >= 3.7"; exit 1; }

# ---------- 路径配置 ----------
INSTALL_DIR="${HOME}/.ohshit"
BIN_DIR="${HOME}/.local/bin"
BACKUP_DIR="${HOME}/.ohshit-backups/$(date +%Y%m%d-%H%M%S)"
PACKAGE_INSTALL_DIR="${INSTALL_DIR}/lib"
WRAPPER="${BIN_DIR}/dang"
ohshit_WRAPPER="${BIN_DIR}/ohshit"

mkdir -p "${INSTALL_DIR}" "${BIN_DIR}" "${PACKAGE_INSTALL_DIR}" "${BACKUP_DIR}"
log_info "安装目录: ${INSTALL_DIR}"
log_info "可执行文件: ${WRAPPER}, ${ohshit_WRAPPER}"

# ---------- Step A: 安装 danger_guard 包到 PACKAGE_INSTALL_DIR ----------
# 方案 1: 项目目录本地（开发/仓库场景）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"  # danger_guard/scripts/install.sh -> 项目根
if [ -f "${PROJECT_ROOT}/pyproject.toml" ] && grep -q "name.*danger[_-]guard" "${PROJECT_ROOT}/pyproject.toml"; then
  log_info "发现项目根目录 ${PROJECT_ROOT}，使用 pip 安装（editable 模式）..."
  python3 -m pip install --quiet --user --break-system-packages 2>/dev/null || true
  if python3 -m pip install --break-system-packages --quiet -e "${PROJECT_ROOT}" 2>/dev/null; then
    log_ok "pip 安装成功 (editable)"
  elif python3 -m pip install --quiet -e "${PROJECT_ROOT}" 2>/dev/null; then
    log_ok "pip 安装成功 (editable, no --break-system-packages)"
  else
    log_warn "pip editable 失败，退回到 cp 方式。"
    cp -r "${PROJECT_ROOT}/danger_guard" "${PACKAGE_INSTALL_DIR}/"
  fi
else
  # 方案 2: 远程拉取（这里做占位：如果有 PyPI，就 pip install danger-guard）
  log_warn "未发现本地项目根。暂不支持远程安装——请先 git clone 后执行本脚本。"
fi

# 确保 danger_guard.core.engine 能被 import
python3 -c "from danger_guard.core.engine import run_pipeline" || {
  log_err "danger_guard 模块导入失败，尝试用 PACKAGE_INSTALL_DIR："
  [ -d "${PACKAGE_INSTALL_DIR}/danger_guard" ] || { log_err "找不到 danger_guard 包"; exit 1; }
  cp -r "${PACKAGE_INSTALL_DIR}/danger_guard" "${INSTALL_DIR}/"
  log_warn "已把包复制到 ${INSTALL_DIR}/danger_guard"
}

# ---------- Step B: 写 dang / ohshit shebang wrapper ----------
write_wrapper() {
  local target="$1"
  if [ -e "$target" ]; then
    mv "$target" "${BACKUP_DIR}/$(basename "$target")-$$"
    log_info "备份旧文件到 ${BACKUP_DIR}/$(basename "$target")-$$"
  fi
  cat > "$target" <<'WRAPPER_EOF'
#!/usr/bin/env python3
import sys, os
# 若本地安装过（~/.ohshit/danger_guard）则优先
LOCAL = os.path.expanduser("~/.ohshit")
if LOCAL not in sys.path:
    sys.path.insert(0, LOCAL)
from danger_guard.__main__ import main
sys.exit(main())
WRAPPER_EOF
  chmod +x "$target"
}

write_wrapper "${WRAPPER}"
write_wrapper "${ohshit_WRAPPER}"
log_ok "已写入 ${WRAPPER} / ${ohshit_WRAPPER}"

# ---------- Step C: 写 Shell alias 到 ~/.ohshit-aliases.sh ----------
ALIASES_FILE="${HOME}/.ohshit-aliases.sh"
if [ -f "${ALIASES_FILE}" ]; then
  cp "${ALIASES_FILE}" "${BACKUP_DIR}/ohshit-aliases.sh"
  log_info "备份已存在的 ${ALIASES_FILE} → ${BACKUP_DIR}"
fi
cat > "${ALIASES_FILE}" <<'ALIASES_EOF'
# OhShit 删库跑路预防针 — shell aliases
# 由 danger_guard/scripts/install.sh 自动生成。

# 1) 交互 shell 下覆盖 rm/dd 为 dang
if [[ $- == *i* ]]; then
  alias rm='dang -- rm'
  alias dd='dang -- dd'
fi

# 2) 提示如何卸载
alias ohshit-uninstall='dang --version >/dev/null 2>&1 && echo "执行: rm ~/.ohshit-aliases.sh && sed -i '/ohshit-aliases/d' ~/.bashrc ~/.zshrc && rm ~/.local/bin/dang ~/.local/bin/ohshit" || echo "(dang not found)"'
ALIASES_EOF
log_ok "已写入 aliases: ${ALIASES_FILE}"

# ---------- Step D: 注入 ~/.bashrc / ~/.zshrc ----------
inject_rc() {
  local rcfile="$1"
  [ -f "$rcfile" ] || return 0
  if grep -q "ohshit-aliases.sh" "$rcfile" 2>/dev/null; then
    log_info "${rcfile} 已包含 ohshit 注入，跳过"
    return 0
  fi
  cp "$rcfile" "${BACKUP_DIR}/$(basename "$rcfile")"
  {
    echo ""
    echo "# >>> OhShit 删库跑路预防针 >>>"
    echo "[ -f ~/.ohshit-aliases.sh ] && source ~/.ohshit-aliases.sh"
    echo "# <<< OhShit 删库跑路预防针 <<<"
  } >> "$rcfile"
  log_ok "已注入 ${rcfile}"
}

inject_rc "${HOME}/.bashrc"
inject_rc "${HOME}/.zshrc"

# ---------- 完成 ----------
log_ok "✅ 安装完成！执行："
echo "   1) source ~/.bashrc   (或 zsh: source ~/.zshrc)"
echo "   2) 验证：dang --list-hooks"
echo "   3) 体验：dang --dry-run -- rm -rf /tmp/*"
log_info "卸载方式：删除 ~/.local/bin/dang ~/.local/bin/ohshit ~/.ohshit-aliases.sh，再移除 bashrc/zshrc 末尾注入。"
