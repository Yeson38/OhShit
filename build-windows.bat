@ECHO OFF
REM ============================================================================
REM  build-windows.bat  —  Build OhShit standalone .exe for Windows x86_64
REM  Platform:           Windows 10/11 x64, ANY cmd.exe (DOES NOT REQUIRE
REM                       PowerShell; bypasses ExecutionPolicy restrictions)
REM  Prerequisites:      Python 3.8+ on %%PATH%% (so `python --version` works)
REM                       Build machine needs internet for pip install;
REM                       TARGET MACHINE NEEDS NO PYTHON AND NO NETWORK.
REM  Output:             .\dist\ohshit.exe   (~22-28 MB standalone EXE)
REM                      .\dist\SHA256SUMS.win
REM  Usage:              Just double-click this .bat, or run from cmd:
REM                          cd OhShit
REM                          build-windows.bat
REM ============================================================================
SETLOCAL ENABLEEXTENSIONS
CHCP 437 > NUL
PUSHD "%~dp0"

IF NOT EXIST "danger_guard\__main__.py" (
    ECHO ERROR: danger_guard\__main__.py not found.
    ECHO        Run this batch from inside the OhShit project root.
    POPD
    EXIT /B 2
)

ECHO [1/4] Installing/upgrading PyInstaller (build-machine only step)
python -m pip install --quiet --upgrade pip setuptools wheel
IF ERRORLEVEL 1 GOTO :ERR
python -m pip install --quiet "pyinstaller>=6.16"
IF ERRORLEVEL 1 GOTO :ERR

ECHO [2/4] Cleaning old build artifacts
IF EXIST "dist" RD /S /Q "dist"
IF EXIST "build" RD /S /Q "build"
IF EXIST "ohshit.spec" DEL /F /Q "ohshit.spec"

ECHO [3/4] Building standalone EXE with PyInstaller --onefile
pyinstaller --clean --noconfirm --onefile --name ohshit ^
    --paths . ^
    --collect-submodules danger_guard ^
    --copy-metadata danger-guard ^
    --log-level WARN ^
    danger_guard\__main__.py
IF ERRORLEVEL 1 GOTO :ERR

ECHO [4/4] Computing SHA256 checksum (writing dist\SHA256SUMS.win)
FOR /F "usebackq delims=" %%H IN (`powershell -NoProfile -Command ^
    "(Get-FileHash -Path '.\dist\ohshit.exe' -Algorithm SHA256).Hash.ToLower()"`) DO (
        SET "HASH=%%H"
)
ECHO %HASH%  ohshit.exe > dist\SHA256SUMS.win
ECHO SHA256: %HASH%

FOR %%I IN (dist\ohshit.exe) DO SET "BYTES=%%~zI"
ECHO.
ECHO BUILD OK.
ECHO   Platform : Windows x86_64 EXE
ECHO   Binary   : %CD%\dist\ohshit.exe  (%BYTES% bytes)
ECHO   Checksum : %CD%\dist\SHA256SUMS.win
ECHO.
ECHO Smoke test ^(target machine needs NO python^):
ECHO     dist\ohshit.exe --version
ECHO.
ECHO Upload: https://github.com/Yeson38/OhShit/releases/tag/v1.0.0 -^> Edit
ECHO         Attach ohshit.exe as ohshit-windows-x86_64.exe
ECHO         Attach SHA256SUMS.win as SHA256SUMS.windows-x86_64
POPD
ENDLOCAL
EXIT /B 0

:ERR
POPD
ENDLOCAL
ECHO.
ECHO BUILD FAILED (step above this line). Exit code %ERRORLEVEL%.
EXIT /B %ERRORLEVEL%
