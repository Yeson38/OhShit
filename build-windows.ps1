# =============================================================================
# build-windows.ps1  —  Build OhShit standalone .exe for Windows x86_64
# Platform:           Windows 10 / 11 x64 (PowerShell 5.1 or PowerShell 7+)
# Prerequisites:      Python 3.8+ installed, pip works, build machine has
#                     internet for pip install (TARGET MACHINE NEEDS NEITHER).
#                     pip packages: danger-guard's 0 deps; build-only: pyinstaller
# Output:             .\dist\ohshit.exe    (standalone EXE, ~22-28 MB)
#                     .\dist\SHA256SUMS.win
# Usage (one of):
#   A) GUI: Right-click this file -> "Run with PowerShell"
#   B) PS console (ExecutionPolicy may require):
#      Set-ExecutionPolicy -Scope Process Bypass -Force
#      .\build-windows.ps1
#   C) If ExecutionPolicy still blocked, run build-windows.bat (CMD batch)
#      in the same folder instead — it bypasses PowerShell entirely.
# =============================================================================

$ErrorActionPreference = "Stop"

# --- Script-root based paths (not $PWD) so double-click-from-anywhere works
$ScriptDir = $PSScriptRoot
Set-Location $ScriptDir

if (-not (Test-Path (Join-Path $ScriptDir "danger_guard\__main__.py"))) {
    Write-Host "ERROR: danger_guard\__main__.py not found." -ForegroundColor Red
    Write-Host "       Place this script inside the OhShit project root." -ForegroundColor Red
    exit 2
}

Write-Host "[1/4] Installing/upgrading PyInstaller (build-machine only step)" -ForegroundColor Cyan
python -m pip install --quiet --upgrade pip setuptools wheel
python -m pip install --quiet "pyinstaller>=6.16"

Write-Host "[2/4] Cleaning old build artifacts" -ForegroundColor Cyan
if (Test-Path "dist") { Remove-Item -Recurse -Force dist }
if (Test-Path "build") { Remove-Item -Recurse -Force build }
if (Test-Path "ohshit.spec") { Remove-Item -Force ohshit.spec }

Write-Host "[3/4] Building standalone EXE with PyInstaller --onefile" -ForegroundColor Cyan
& pyinstaller --clean --noconfirm --onefile --name ohshit `
    --paths . `
    --collect-submodules danger_guard `
    --copy-metadata danger-guard `
    --log-level WARN `
    danger_guard\__main__.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed (exit=$LASTEXITCODE)" }

Write-Host "[4/4] Computing SHA256 checksum" -ForegroundColor Cyan
$Dist = Join-Path $ScriptDir "dist"
$Exe  = Join-Path $Dist "ohshit.exe"
$Sum  = Join-Path $Dist "SHA256SUMS.win"
$Hash = (Get-FileHash -Path $Exe -Algorithm SHA256).Hash.ToLower()
# GNU shasum-compatible format: "<hash>  ohshit.exe"
"$Hash  ohshit.exe" | Out-File -FilePath $Sum -Encoding ascii -NoNewline
Write-Host "SHA256: $Hash"

$ExeSize = [math]::Round((Get-Item $Exe).Length / 1MB, 1)
Write-Host ""
Write-Host "BUILD OK." -ForegroundColor Green
Write-Host "  Platform : Windows x86_64 EXE"
Write-Host "  Binary   : $Exe ($ExeSize MB)"
Write-Host "  Checksum : $Sum"
Write-Host ""
Write-Host "Smoke test (target machine NO python / NO pip required):"
Write-Host "  .\ohshit.exe --version"
Write-Host ""
Write-Host "Upload to GitHub Release v1.0.1:" -ForegroundColor Yellow
Write-Host "  https://github.com/Yeson38/OhShit/releases/tag/v1.0.1 -> Edit"
Write-Host "  Drop ohshit.exe into Attach binaries box, rename -> ohshit-windows-x86_64.exe"
Write-Host "  Drop SHA256SUMS.win too so users can verify."
