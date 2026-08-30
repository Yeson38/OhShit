#!/usr/bin/env bash
# =============================================================================
# build-linux.sh  —  Build OhShit standalone ELF for Linux (x86_64 or aarch64)
# Platform:       Any Linux distro with glibc (Ubuntu 14.04+, CentOS 7+, ...)
# Prerequisites:  python3 (>= 3.7) + python3-pip installed, internet for pip
#                 (only needed ON THIS BUILD MACHINE; target machine needs none)
# Output:         ./dist/ohshit   (standalone ELF, ~22-28 MB)
#                 ./dist/SHA256SUMS
# Usage:          chmod +x build-linux.sh  &&  ./build-linux.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Guard: must run inside OhShit source root (danger_guard/__main__.py here)
if [ ! -f "danger_guard/__main__.py" ]; then
    echo "ERROR: danger_guard/__main__.py not found." >&2
    echo "       Place this script inside the OhShit project root." >&2
    exit 2
fi

echo "[1/4] Installing/upgrading PyInstaller (build-machine only step)"
python3 -m pip install --quiet --upgrade pip setuptools wheel
python3 -m pip install --quiet 'pyinstaller>=6.16'

echo "[2/4] Cleaning old build artifacts"
rm -rf dist build ohshit.spec

echo "[3/4] Building standalone ELF with PyInstaller --onefile"
pyinstaller --clean --noconfirm --onefile --name ohshit \
    --paths . \
    --collect-submodules danger_guard \
    --copy-metadata danger-guard \
    --log-level WARN \
    danger_guard/__main__.py

echo "[4/4] Computing SHA256 checksum"
cd dist
sha256sum ohshit > SHA256SUMS
cat SHA256SUMS

echo ""
echo "BUILD OK."
echo "  Platform : $(uname -m) Linux ELF"
echo "  Binary   : $PWD/ohshit ($(du -h ohshit | awk '{print $1}'))"
echo "  Checksum : $PWD/SHA256SUMS"
echo ""
echo "Next step on this build machine:"
echo "  sha256sum -c SHA256SUMS   # verify"
echo "  ./ohshit --version        # smoke test"
echo ""
echo "Upload ohshit to GitHub Release assets:"
echo "  - Open https://github.com/Yeson38/OhShit/releases/tag/v1.0.1 -> Edit"
echo "  - Drop 'ohshit' into the 'Attach binaries' box, rename before upload"
echo "    to 'ohshit-linux-$(uname -m)' so x86_64 / arm64 assets don't collide."
