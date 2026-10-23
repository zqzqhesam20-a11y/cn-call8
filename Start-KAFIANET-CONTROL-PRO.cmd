@echo off
setlocal EnableExtensions

rem KAFIA NET CONTROL PRO - external Python runtime
rem The Python runtime stays on SERVER06 and is never copied into this app/repository.
set "PYTHON_ROOT=\\SERVER06\c$\العابي\222\66\الاخييير\py"
set "PYTHON_EXE=%PYTHON_ROOT%\python.exe"
set "APP_ROOT=%~dp0"
set "SITE_PACKAGES=%PYTHON_ROOT%\Lib\site-packages"

if not exist "%PYTHON_EXE%" (
    echo.
    echo [KAFIA NET CONTROL PRO] Python runtime was not found:
    echo %PYTHON_EXE%
    echo Check that SERVER06 is online and this Windows account can access the C$ share.
    pause
    exit /b 10
)

if not exist "%PYTHON_ROOT%\Lib" (
    echo.
    echo [KAFIA NET CONTROL PRO] The external Python Lib folder is missing:
    echo %PYTHON_ROOT%\Lib
    pause
    exit /b 11
)

rem Prefer DLLs shipped with the external runtime and the PySide6 package.
set "PATH=%PYTHON_ROOT%;%PYTHON_ROOT%\DLLs;%SITE_PACKAGES%\PySide6;%SITE_PACKAGES%\PySide6\Qt\bin;%SITE_PACKAGES%\shiboken6;%APP_ROOT%platform-tools;%PATH%"
set "PYTHONHOME=%PYTHON_ROOT%"
set "PYTHONPATH=%APP_ROOT%;%SITE_PACKAGES%;%PYTHONPATH%"
set "PYTHONUTF8=1"

rem Preflight QtWidgets and construct QApplication using Qt's offscreen plugin.
rem This tests the native Qt DLL/plugin load before starting the desktop UI.
set "KAFIANET_OLD_QT_QPA_PLATFORM=%QT_QPA_PLATFORM%"
set "QT_QPA_PLATFORM=offscreen"
"%PYTHON_EXE%" "%APP_ROOT%app_qml.py" --qt-import-smoke-test
set "QT_SMOKE_EXIT=%ERRORLEVEL%"
if defined KAFIANET_OLD_QT_QPA_PLATFORM (
    set "QT_QPA_PLATFORM=%KAFIANET_OLD_QT_QPA_PLATFORM%"
) else (
    set "QT_QPA_PLATFORM="
)
if not "%QT_SMOKE_EXIT%"=="0" (
    echo.
    echo [KAFIA NET CONTROL PRO] Qt startup failed using the external Python runtime.
    echo Python 3.14 requires PySide6 6.10.1 or newer, plus compatible Qt DLLs and plugins.
    echo Check PySide6 and psutil in:
    echo %PYTHON_ROOT%
    echo requirements.txt lists the supported dependency versions.
    echo This launcher does not download or install runtime files.
    pause
    exit /b 12
)

pushd "%APP_ROOT%" >nul
if errorlevel 1 (
    echo [KAFIA NET CONTROL PRO] Cannot enter application folder: %APP_ROOT%
    pause
    exit /b 13
)

"%PYTHON_EXE%" "%APP_ROOT%app_qml.py"
set "APP_EXIT_CODE=%ERRORLEVEL%"
popd

if not "%APP_EXIT_CODE%"=="0" (
    echo.
    echo [KAFIA NET CONTROL PRO] Application exited with code %APP_EXIT_CODE%.
    pause
)

exit /b %APP_EXIT_CODE%
