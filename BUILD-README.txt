================================================================================
  OhShit  Cross-Platform Build Kit README (ASCII / English only, no encoding
  issues on any terminal, per Windows build lessons from Experience 1425762)
================================================================================

WHAT THIS FOLDER / ASSET SET CONTAINS
-------------------------------------
5 helper files + 1 pre-built Linux x86_64 binary already shipped in the
v1.0.0 Release of https://github.com/Yeson38/OhShit

  build-linux.sh      -> Standalone Linux ELF (x86_64 or aarch64/ARM64,
                         whichever architecture the build machine runs).
                         Builds on any Linux with python3 + pip + internet.
  build-macos.sh      -> Standalone macOS Mach-O (x86_64 = Intel, or
                         arm64 = Apple Silicon M1/M2/M3/...).
                         Builds on any Mac with python3.
  build-windows.ps1   -> Standalone Windows x86_64 .exe via PowerShell.
                         (ExecutionPolicy may need "Run with PowerShell" or
                         Set-ExecutionPolicy -Scope Process Bypass -Force)
  build-windows.bat   -> STANDALONE .EXE via plain cmd.exe (NO PowerShell
                         required! Use this one if corporate ExecutionPolicy
                         completely blocks .ps1 scripts. Double-click or
                         run from cmd.)
  BUILD-README.txt    -> This file.

  ohshit              -> Pre-built, ALREADY ATTACHED to v1.0.0 Release.
                         Standalone Linux x86_64 ELF compiled on Python 3.14
                         + PyInstaller 6.22 on x86_64 glibc 2.39. SHA256 in
                         the companion SHA256SUMS file (also attached).


WHY DO WE NEED SEPARATE BUILDS PER OS / ARCH?
---------------------------------------------
PyInstaller (the tool we use to embed libpython + all modules into one file)
deliberately does NOT support cross-compiling operating systems or CPU
architectures. In practical terms that means:

  - A Linux build machine CANNOT produce a Windows .exe.
  - An x86_64 build machine CANNOT produce an Apple Silicon arm64 Mach-O.
  - etc.

That's why this v1.0.0 Release ships a PRE-BUILT Linux x86_64 ELF by default
(our build environment is an x86_64 Linux sandbox), AND ships the four
one-click build scripts above so you can run a 5-minute build on any
Windows PC / Mac / ARM server you have access to, and drag-drop the
resulting binary into the v1.0.0 Release assets yourself.


ONE COMMAND TO RUN PER PLATFORM (yes, really just one)
------------------------------------------------------
Linux:
    chmod +x build-linux.sh   &&   ./build-linux.sh

macOS:
    chmod +x build-macos.sh   &&   ./build-macos.sh

Windows option A (GUI, simplest):
    Double-click build-windows.bat   <-- no ExecutionPolicy hassle.

Windows option B (PowerShell console):
    Set-ExecutionPolicy -Scope Process Bypass -Force
    .\build-windows.ps1


WHAT YOU GET AFTER A SUCCESSFUL BUILD
-------------------------------------
All scripts write to the ./dist/ folder next to themselves and print the
absolute path + SHA256 on success:

  Linux:     ./dist/ohshit            (~22-28 MB ELF) + ./dist/SHA256SUMS
  macOS:     ./dist/ohshit            (~22-26 MB Mach-O) + ./dist/SHA256SUMS
  Windows:   ./dist/ohshit.exe        (~22-28 MB EXE) + ./dist/SHA256SUMS.win


VERIFY THE BUILD BEFORE YOU SHIP IT (mandatory 30-second smoke tests)
---------------------------------------------------------------------
After the script prints "BUILD OK." run these in a terminal on the BUILD
machine first, so you know the binary actually works:

  Linux (prove NO external Python required):
      env -i PATH=/usr/bin:/bin HOME=/tmp ./dist/ohshit --version
      expected: "dang 1.0.0" printed, exit code 0.

  macOS (prove NO external Python required):
      env -i PATH=/usr/bin:/bin HOME=/tmp ./dist/ohshit --version
      (on first run, macOS may warn about unverified developer -> right-click
      the binary -> Open, or run: xattr -d com.apple.quarantine ./dist/ohshit)

  Windows (prove NO external Python required):
      cmd /C "set PATH=C:\Windows\System32;C:\Windows & dist\ohshit.exe --version"
      expected: "dang 1.0.0" printed, exit code 0.


HOW TO APPEND THE NEW BINARY / CHECKSUM TO THE v1.0.0 GITHUB RELEASE
--------------------------------------------------------------------
Once you have a working binary from a Windows / Mac / ARM64 build machine:

  1. Go to   https://github.com/Yeson38/OhShit/releases/tag/v1.0.0
  2. Click the  **Edit**  button (top-right of the Release box).
  3. Scroll down to "Attach binaries by dropping them here or selecting them".
  4. Drag-and-drop BOTH the binary AND its matching SHA256 text file into
     that box.  RENAME THEM FIRST so filenames are unique per platform so
     they never collide with the pre-built Linux one already present:

         Build output file         ->    Rename before upload
         ----------------------------------------------------------------
         dist/ohshit        (macOS Intel)   -> ohshit-macos-x86_64
         dist/ohshit        (macOS arm64)   -> ohshit-macos-arm64
         dist/SHA256SUMS    (macOS)         -> SHA256SUMS-macos-<arch>
         dist/ohshit.exe    (Win x64)       -> ohshit-windows-x86_64.exe
         dist/SHA256SUMS.win                -> SHA256SUMS-windows-x86_64
         dist/ohshit        (Linux arm64)   -> ohshit-linux-aarch64
         dist/SHA256SUMS    (Linux arm64)   -> SHA256SUMS-linux-aarch64

  5. Click  **Update release**  (green button at the bottom).

Done. The asset now shows up for every visitor to the v1.0.0 Release page.


WHAT IF THE BUILD FAILS?
------------------------
99 % of build failures fall into these categories:

  (a) "pip install pyinstaller fails" with "No matching distribution found"
      -> Your Python is too old / too new for the PyInstaller version.
         Fix:  python -m pip install --upgrade pip
         then  python -m pip install 'pyinstaller>=6.16'
         (PyInstaller 6.16+ added Python 3.13 / 3.14 support.)

  (b) "ModuleNotFoundError: No module named 'danger_guard.xxx'" at runtime
      on the freshly-built binary
      -> You probably removed the  "--collect-submodules danger_guard"
         flag from the PyInstaller call.  Keep that flag in; pkgutil-based
         hook auto-discovery needs the submodules present in the PYZ.

  (c) "PackageNotFoundError: danger-guard" when running  --version
      -> You removed the  "--copy-metadata danger-guard"  flag. Keep it.

  (d) SyntaxWarning: "\e" is an invalid escape sequence
      -> Cosmetic warning only; already fixed in danger_guard/core/validator.py
         source tree (docstring r-prefix). If you are on an older source zip
         just ignore it, binary still works.

  (e) Windows only: batch/ps1 fails immediately with "python not found"
      -> Install Python from python.org/downloads, tick "Add Python to PATH",
         reopen cmd, retry.


LINKS
-----
  OhShit project home:     https://github.com/Yeson38/OhShit
  PR #2 (source changes):  https://github.com/Yeson38/OhShit/pull/2
  PyInstaller docs:        https://pyinstaller.org/en/stable/usage.html
