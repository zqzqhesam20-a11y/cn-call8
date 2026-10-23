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
set "PYTHONPATH=%APP_ROOT%;%SITE_PACKAGES%;%PYTHONPATH%"
set "PYTHONUTF8=1"

rem Preflight the exact QtWidgets import that previously failed. This only tests;
rem it does not install or copy Python, Qt, PySide6, or any runtime DLLs.
"%PYTHON_EXE%" -c "import sys; print('Python runtime:', sys.executable); import PySide6; print('PySide6:', PySide6.__version__); from PySide6.QtWidgets import QApplication; print('QtWidgets import: OK')"
if errorlevel 1 (
    echo.
    echo [KAFIA NET CONTROL PRO] The external Python runtime or its PySide6 dependencies are not ready.
    echo Confirm PySide6 and psutil are installed in:
    echo %PYTHON_ROOT%
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
