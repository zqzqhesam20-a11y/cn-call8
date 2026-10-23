$ErrorActionPreference = "Stop"

# Keep this source ASCII-only. Construct Arabic folder names by Unicode code points
# so Windows PowerShell 5.1 never has to decode Arabic bytes from this script.
$gameLibrary = -join ([char[]]@(0x0627, 0x0644, 0x0639, 0x0627, 0x0628, 0x064A))
$releaseFolder = -join ([char[]]@(0x0627, 0x0644, 0x0627, 0x062E, 0x064A, 0x064A, 0x064A, 0x0631))
$pythonRoot = "\\SERVER06\c$\{0}\222\66\{1}\py" -f $gameLibrary, $releaseFolder
$pythonExe = Join-Path -Path $pythonRoot -ChildPath "python.exe"
$libRoot = Join-Path -Path $pythonRoot -ChildPath "Lib"
$dllRoot = Join-Path -Path $pythonRoot -ChildPath "DLLs"
$appRoot = $PSScriptRoot
$sitePackages = Join-Path -Path $libRoot -ChildPath "site-packages"
$bootstrap = Join-Path -Path $appRoot -ChildPath "kafianet_external_runtime.py"

function Stop-KafiaLauncher([int]$Code, [string]$Message) {
    $fullMessage = "[KAFIA NET CONTROL PRO] $Message"
    try {
        $shell = New-Object -ComObject WScript.Shell
        [void]$shell.Popup($fullMessage, 0, "KAFIA NET CONTROL PRO", 16)
    } catch {
        Write-Host $fullMessage
    }
    exit $Code
}

if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    Stop-KafiaLauncher 10 "Python runtime was not found on SERVER06. Confirm the server is online and this Windows account can access C$."
}
if (-not (Test-Path -LiteralPath $libRoot -PathType Container)) {
    Stop-KafiaLauncher 11 "The external Python Lib folder is missing."
}
if (-not (Test-Path -LiteralPath $dllRoot -PathType Container)) {
    Stop-KafiaLauncher 11 "The external Python DLLs folder is missing."
}
if (-not (Test-Path -LiteralPath $bootstrap -PathType Leaf)) {
    Stop-KafiaLauncher 13 "kafianet_external_runtime.py is missing from the application folder."
}

# Use the external runtime only. No runtime download, installation, or copy occurs.
$env:PYTHONHOME = $pythonRoot
$env:PYTHONUTF8 = "1"
$pythonPathItems = @($appRoot, $sitePackages, $env:PYTHONPATH) |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
$env:PYTHONPATH = $pythonPathItems -join ";"
$pathItems = @(
    $pythonRoot,
    $dllRoot,
    $sitePackages,
    (Join-Path $sitePackages "PySide6"),
    (Join-Path $sitePackages "PySide6\Qt\bin"),
    (Join-Path $sitePackages "shiboken6"),
    (Join-Path $appRoot "platform-tools"),
    $env:PATH
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
$env:PATH = $pathItems -join ";"

# Preflight QtWidgets and QApplication before showing the real interface.
$hadQpaPlatform = Test-Path Env:QT_QPA_PLATFORM
$previousQpaPlatform = $env:QT_QPA_PLATFORM
$env:QT_QPA_PLATFORM = "offscreen"
& $pythonExe $bootstrap --qt-import-smoke-test
$smokeExitCode = $LASTEXITCODE
if ($hadQpaPlatform) {
    $env:QT_QPA_PLATFORM = $previousQpaPlatform
} else {
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
}
if ($smokeExitCode -ne 0) {
    Stop-KafiaLauncher 12 "Qt startup preflight failed. Check compatible PySide6, Qt DLLs and plugins in the external Python environment."
}

try {
    $quotedBootstrap = '"' + $bootstrap + '"'
    $appProcess = Start-Process -FilePath $pythonExe -ArgumentList $quotedBootstrap -WorkingDirectory $appRoot -WindowStyle Hidden -PassThru -Wait
    $appExitCode = $appProcess.ExitCode
} catch {
    Stop-KafiaLauncher 14 ("Unable to launch the application: " + $_.Exception.Message)
}
if ($appExitCode -ne 0) {
    Stop-KafiaLauncher $appExitCode "The application exited with an error."
}
exit 0
