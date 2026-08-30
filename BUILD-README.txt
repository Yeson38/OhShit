================================================================================
  OhShit  Cross-Platform Build Kit README (ASCII / English only, avoids
  terminal encoding issues across locales)
================================================================================

WHAT THIS ASSET SET CONTAINS
----------------------------
5 helper files + 1 pre-built Linux x86_64 binary shipped with the release.

  build-linux.sh      -> Standalone Linux ELF (x86_64 or aarch64/ARM64,
                         whichever architecture the build machine runs).
                         Requires python3 + pip + internet on the build host.
  build-macos.sh      -> Standalone macOS Mach-O (x86_64 Intel or arm64
                         Apple Silicon). Requires python3 on a Mac.
  build-windows.ps1   -> Standalone Windows x86_64 .exe via PowerShell.
                         (Run with Scope-Process ExecutionPolicy Bypass or
                         "Run with PowerShell" context menu.)
  build-windows.bat   -> Standalone .EXE via plain cmd.exe.  No PowerShell
                         required.  Double-click or run from cmd.  Use this
                         on corporate machines where ExecutionPolicy fully
                         blocks .ps1 files.
  BUILD-README.txt    -> This file.

  ohshit              -> Pre-built Linux x86_64 ELF. SHA256 is in the
                         companion SHA256SUMS file also attached.


WHY SEPARATE BUILDS PER OS / ARCH?
----------------------------------
PyInstaller embeds the Python interpreter and all modules into a single
file, and intentionally does NOT support cross-compiling operating
systems or CPU architectures:

  - A Linux build machine cannot produce a Windows .exe.
  - An x86_64 build machine cannot produce an Apple Silicon arm64 Mach-O.
  - etc.

That's why the release ships a pre-built Linux x86_64 ELF together with
four one-click build scripts, so you can run a short build on any
Windows PC, Mac, or ARM server you have access to and drop the resulting
binary into the release assets yourself.


ONE COMMAND TO RUN PER PLATFORM
-------------------------------
Linux:
    chmod +x build-linux.sh   &&   ./build-linux.sh

macOS:
    chmod +x build-macos.sh   &&   ./build-macos.sh

Windows option A (GUI, simplest):
    Double-click build-windows.bat

Windows option B (PowerShell console):
    Set-ExecutionPolicy -Scope Process Bypass -Force
    .\build-windows.ps1


WHAT YOU GET AFTER A SUCCESSFUL BUILD
-------------------------------------
All scripts write to ./dist/ next to themselves and print the absolute
path plus SHA256 on success:

  Linux:     ./dist/ohshit            (~22-28 MB ELF)     + ./dist/SHA256SUMS
  macOS:     ./dist/ohshit            (~22-26 MB Mach-O)  + ./dist/SHA256SUMS
  Windows:   ./dist/ohshit.exe        (~22-28 MB EXE)     + ./dist/SHA256SUMS.win


POST-BUILD SMOKE CHECKS (recommended 30-second steps)
-----------------------------------------------------
After "BUILD OK." is printed, confirm the binary works on the build
machine:

  Linux (prove no external Python required):
      env -i PATH=/usr/bin:/bin HOME=/tmp ./dist/ohshit --version
      expected: "dang 1.0.1" printed, exit code 0.

  macOS (prove no external Python required):
      env -i PATH=/usr/bin:/bin HOME=/tmp ./dist/ohshit --version
      If Gatekeeper blocks the binary: right-click -> Open, or run
         xattr -d com.apple.quarantine ./dist/ohshit

  Windows (prove no external Python required):
      cmd /C "set PATH=C:\Windows\System32;C:\Windows & dist\ohshit.exe --version"
      expected: "dang 1.0.1" printed, exit code 0.


HOW TO APPEND THE NEW BINARY / CHECKSUM TO THE GITHUB RELEASE
-------------------------------------------------------------
Once you have a working binary from a Windows, Mac, or ARM64 build
machine:

  1. Open   https://github.com/Yeson38/OhShit/releases/tag/v1.0.1
  2. Click  **Edit**  (top-right of the Release card).
  3. Scroll to "Attach binaries by dropping them here or selecting them".
  4. Drag BOTH the binary AND its matching SHA256 file into that box.
     RENAME them BEFORE upload so each platform / arch pair has a
     distinct filename and never collides with the pre-built Linux
     asset already present:

         Output file                      Rename before upload
         ----------------------------------------------------------------
         dist/ohshit        (macOS Intel) -> ohshit-macos-x86_64
         dist/ohshit        (macOS arm64) -> ohshit-macos-arm64
         dist/SHA256SUMS    (macOS)       -> SHA256SUMS-macos-<arch>
         dist/ohshit.exe    (Win x64)     -> ohshit-windows-x86_64.exe
         dist/SHA256SUMS.win              -> SHA256SUMS-windows-x86_64
         dist/ohshit        (Linux arm64) -> ohshit-linux-aarch64
         dist/SHA256SUMS    (Linux arm64) -> SHA256SUMS-linux-aarch64

  5. Click  **Update release** .

The asset is then visible to all visitors of the v1.0.1 Release page.


BUILD FAILURE TROUBLESHOOTING
-----------------------------
99 % of build failures fall into these categories:

  (a) "pip install pyinstaller fails" with "No matching distribution found"
      -> Python version is outside the range supported by the PyInstaller
         release.  Fix:  python -m pip install --upgrade pip
         then   python -m pip install 'pyinstaller>=6.16'
         (PyInstaller 6.16+ added Python 3.13 / 3.14 support.)

  (b) ModuleNotFoundError at runtime on the freshly-built binary
      -> "--collect-submodules danger_guard" flag was removed from the
         PyInstaller call.  Keep the flag: pkgutil-based hook discovery
         needs every submodule embedded in the PYZ archive.

  (c) PackageNotFoundError: danger-guard when running --version
      -> "--copy-metadata danger-guard" flag was removed. Keep it.

  (d) SyntaxWarning: "\e" is an invalid escape sequence
      -> Ensure validator.py uses a raw-docstring (r""") prefix.

  (e) Windows only: batch / ps1 fails immediately with "python not found"
      -> Install Python from python.org/downloads, enable the official
         installer option "Add Python to PATH", reopen cmd, retry.


LINKS
-----
  Project home:   https://github.com/Yeson38/OhShit
  PR #2:          https://github.com/Yeson38/OhShit/pull/2
  PyInstaller:    https://pyinstaller.org/en/stable/usage.html
