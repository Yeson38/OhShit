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
# OhShit 删库跑路预防针 — shell aliases (Bash / Zsh 专用；Fish 用 config.fish 原生段)
# 由 danger_guard/scripts/install.sh 自动生成。

# 1) 交互 shell 下覆盖 rm/dd 为 dang
if [[ $- == *i* ]]; then
  alias rm='dang -- rm'
  alias dd='dang -- dd'
fi
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

# ---------- Step E: 注入 Fish ~/.config/fish/config.fish（XDG_CONFIG_HOME 兼容）----------
# 说明：Fish 不认识 bash 的 alias rm='dang -- rm'（=赋值）语法，也不能 source ~/.ohshit-aliases.sh。
#       必须独立注入一段 Fish 原生 alias（空格分隔语法）。用与 Bash/Zsh 完全一致的 marker 前缀/后缀，
#       便于 ohshit-uninstall 中 sed 范围删除一条命令同时覆盖 3 个 RC。
FISH_XDG_CONFIG="${XDG_CONFIG_HOME:-${HOME}/.config}"
FISH_CONFIG_DIR="${FISH_XDG_CONFIG}/fish"
FISH_CONFIG="${FISH_CONFIG_DIR}/config.fish"
mkdir -p "${FISH_CONFIG_DIR}"
[ -f "${FISH_CONFIG}" ] || : > "${FISH_CONFIG}"   # 不存在则建空，让 grep / inject 逻辑统一

# 注入内容：status is-interactive 兼容 Fish ≥3.0；fallback 到 test -n "$PS1" 兼容 Fish 2.x
if grep -q "OhShit 删库跑路预防针" "${FISH_CONFIG}" 2>/dev/null; then
  log_info "${FISH_CONFIG} 已包含 ohshit Fish 注入，跳过"
else
  cp "${FISH_CONFIG}" "${BACKUP_DIR}/config.fish"
  {
    echo ""
    echo "# >>> OhShit 删库跑路预防针 >>>"
    echo "# 交互 shell 下覆盖 rm/dd 为 dang（Fish 原生语法；不要写 bash 式 alias=value）"
    echo "if status is-interactive 2>/dev/null; or test -n \"\$PS1\""
    echo "  alias rm 'dang -- rm'"
    echo "  alias dd 'dang -- dd'"
    echo "end"
    echo "# <<< OhShit 删库跑路预防针 <<<"
  } >> "${FISH_CONFIG}"
  log_ok "已注入 Fish RC: ${FISH_CONFIG}"
fi

# ---------- Step F: 写真实的 ohshit-uninstall 可执行脚本（一键卸载，自删）----------
UNINSTALL_BIN="${BIN_DIR}/ohshit-uninstall"
if [ -e "$UNINSTALL_BIN" ]; then
  mv "$UNINSTALL_BIN" "${BACKUP_DIR}/ohshit-uninstall-$$"
  log_info "备份旧 uninstaller 到 ${BACKUP_DIR}"
fi
cat > "$UNINSTALL_BIN" <<'UNINSTALL_EOF'
#!/usr/bin/env bash
# OhShit 一键卸载脚本（由 danger_guard/scripts/install.sh 在安装时生成）。
# 用法：直接执行 ohshit-uninstall（已在 ~/.local/bin 下）
# 设计原则：单环节失败不中断（set +e）；RC marker 统一范围删除；保留用户审计日志与备份目录。

set -uo pipefail   # 不使用 set -e：卸载必须「尽力清理」而非「一步失败全停」

# --- 日志函数（TTY 才上色，兼容 CI / pipe 场景）---
_col()  { if [ -t "${2:-1}" ]; then printf "\033[%sm[ohshit uninstall]\033[0m %s\n" "$1" "$3"; else printf "[ohshit uninstall] %s\n" "$3"; fi; }
log_ok()   { _col "32" 1 "$*"; }
log_warn() { _col "33" 2 "$*" >&2; }
log_info() { _col "36" 1 "$*"; }

MARKER_START='# >>> OhShit 删库跑路预防针 >>>'
MARKER_END='# <<< OhShit 删库跑路预防针 <<<'

# -------- 1) 统一 sed 范围删除（GNU sed + BSD sed 双兼容：-i.bak 形式均支持）---------
strip_markers_from_file() {
  local file="$1"
  [ -f "$file" ] || return 0
  local ok=0
  # GNU sed 常用写法
  sed -i.ohshit-tmpbak "/^${MARKER_START}\$/,/^${MARKER_END}\$/d" "$file" 2>/dev/null && ok=1
  if [ "$ok" -ne 1 ]; then
    # BSD sed（macOS）写法：-i ""（空后缀不生成 bak，我们这里仍手动显式兼容）
    sed -i "" "/^${MARKER_START}\$/,/^${MARKER_END}\$/d" "$file" 2>/dev/null && ok=1
  fi
  rm -f "${file}.ohshit-tmpbak" 2>/dev/null   # 清理 GNU sed 临时 bak
  if [ "$ok" -eq 1 ]; then
    log_info "已移除 RC 注入段：${file}"
  else
    log_warn "无法用 sed 修改 ${file}，请手动删除『${MARKER_START}』到『${MARKER_END}』之间所有行"
  fi
}

strip_markers_from_file "${HOME}/.bashrc"
strip_markers_from_file "${HOME}/.zshrc"
strip_markers_from_file "${XDG_CONFIG_HOME:-${HOME}/.config}/fish/config.fish"

# -------- 2) 删除 Bash/Zsh 的 aliases 文件 --------
if [ -f "${HOME}/.ohshit-aliases.sh" ]; then
  rm -f "${HOME}/.ohshit-aliases.sh"
  log_info "已删除 ${HOME}/.ohshit-aliases.sh"
fi

# -------- 3) pip 卸载 danger-guard（报 not installed 直接忽略；--break-system-packages 双写兼容 Debian/Ubuntu）---------
PY3_BIN="$(command -v python3 || command -v python)"
if [ -n "$PY3_BIN" ]; then
  log_info "调用 pip uninstall -y danger-guard（若出现『not installed』属正常，可忽略）..."
  "$PY3_BIN" -m pip uninstall -y danger-guard --break-system-packages >/dev/null 2>&1 || true
  "$PY3_BIN" -m pip uninstall -y danger-guard >/dev/null 2>&1 || true
fi

# -------- 4) 删除 dang / ohshit wrapper --------
WRAPPER_DIR="${HOME}/.local/bin"
if rm -f "${WRAPPER_DIR}/dang" "${WRAPPER_DIR}/ohshit"; then
  log_info "已删除 ${WRAPPER_DIR}/{dang,ohshit}"
fi

# -------- 5) 审计日志 / 备份目录保留（禁止自动 rm -rf ~/.ohshit 避免误删用户数据）---------
log_info "保留 ${HOME}/.ohshit 备份目录与审计日志（~/.danger.log 等），如需彻底清理请手动删除。"

# -------- 6) 完成提示 + 自删（rm -f -- "$0" 必须放在最后一行执行路径的末尾）---------
log_ok "✅ OhShit 卸载完成！若当前终端别名仍生效，请："
echo "   • Bash:  exec bash   (或新开终端)"
echo "   • Zsh :  exec zsh    (或新开终端)"
echo "   • Fish: exec fish    (或新开终端)"

rm -f -- "$0"
UNINSTALL_EOF
chmod +x "$UNINSTALL_BIN"
log_ok "已写入一键卸载脚本：${UNINSTALL_BIN}（直接执行『ohshit-uninstall』即可）"

# ---------- 完成 ----------
log_ok "✅ 安装完成！下一步："
echo "   1) 加载当前终端（按你用的 shell 选一条）："
echo "        Bash: source ~/.bashrc        Zsh:  source ~/.zshrc"
echo "        Fish: source ~/.config/fish/config.fish   (或新开终端)"
echo "   2) 验证钩子注册： dang --list-hooks"
echo "   3) 体验干跑模式： dang --dry-run -- rm -rf /tmp/*"
echo "   4) 完全卸载：    ohshit-uninstall   (自动清理 RC + pip 包，脚本自删)"
