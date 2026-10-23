@echo off
setlocal
rem Keep this CMD launcher ASCII-only; PowerShell resolves the Unicode UNC path safely.
set "PS_LAUNCHER=%~dp0Start-KAFIANET-CONTROL-PRO.ps1"
if not exist "%PS_LAUNCHER%" (
    echo [KAFIA NET CONTROL PRO] PowerShell launcher is missing.
    pause
    exit /b 2
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PS_LAUNCHER%"
exit /b %ERRORLEVEL%
