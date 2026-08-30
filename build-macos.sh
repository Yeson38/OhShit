#!/usr/bin/env bash
# =============================================================================
# build-macos.sh  —  Build OhShit standalone Mach-O for macOS (x86_64 / arm64)
# Platform:       macOS 11+ (Big Sur and later, Intel or Apple Silicon)
# Prerequisites:  python3 (>= 3.7) via python.org pkg / brew / Xcode CLT
#                 internet for pip (build machine only; target machine needs none)
# Output:         ./dist/ohshit   (standalone Mach-O, ~22-26 MB)
#                 ./dist/SHA256SUMS
# Usage:          chmod +x build-macos.sh  &&  ./build-macos.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "danger_guard/__main__.py" ]; then
    echo "ERROR: danger_guard/__main__.py not found." >&2
    echo "       Place this script inside the OhShit project root." >&2
    exit 2
fi

echo "[1/4] Installing/upgrading PyInstaller (build-machine only step)"
python3 -m pip install --quiet --user --upgrade pip
python3 -m pip install --quiet --user 'pyinstaller>=6.16'
# Ensure pyinstaller on PATH when --user install used
export PATH="$HOME/Library/Python/$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')/bin:$PATH"

echo "[2/4] Cleaning old build artifacts"
rm -rf dist build ohshit.spec

echo "[3/4] Building standalone Mach-O with PyInstaller --onefile"
pyinstaller --clean --noconfirm --onefile --name ohshit \
    --paths . \
    --collect-submodules danger_guard \
    --copy-metadata danger-guard \
    --log-level WARN \
    danger_guard/__main__.py

echo "[4/4] Computing SHA256 checksum"
cd dist
shasum -a 256 ohshit | tee SHA256SUMS

ARCH="$(uname -m)"     # x86_64 (Intel) or arm64 (Apple Silicon)
echo ""
echo "BUILD OK."
echo "  Platform : macOS $ARCH Mach-O"
echo "  Binary   : $PWD/ohshit ($(du -h ohshit | awk '{print $1}'))"
echo "  Checksum : $PWD/SHA256SUMS"
echo ""
echo "Smoke test (target machine needs NO python3 at all):"
echo "  env -i PATH=/usr/bin:/bin HOME=/tmp ./ohshit --version"
echo ""
echo "Upload to GitHub Release (https://github.com/Yeson38/OhShit/releases/tag/v1.0.1 -> Edit):"
echo "  rename ohshit -> ohshit-macos-$ARCH before attaching."
echo "  If Gatekeeper complains on target Mac: xattr -d com.apple.quarantine ./ohshit"
