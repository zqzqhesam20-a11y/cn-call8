"""Launch KAFIA NET CONTROL PRO with the shared SERVER06 Python/Qt runtime.

This is a source-only bootstrap. It does not download, install, or copy runtimes.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


RUNTIME_ROOT = Path(r"\\SERVER06\c$\العابي\222\66\الاخييير\py")
APP_ROOT = Path(__file__).resolve().parent
SITE_PACKAGES = RUNTIME_ROOT / "Lib" / "site-packages"
PYSIDE_ROOT = SITE_PACKAGES / "PySide6"

# Keep directory handles alive: Windows needs them while importing extension
# modules such as QtCore.pyd and QtWidgets.pyd.
_DLL_DIRECTORY_HANDLES = []
_DLL_DIRECTORIES = (
    RUNTIME_ROOT,
    RUNTIME_ROOT / "DLLs",
    PYSIDE_ROOT,
    PYSIDE_ROOT / "Qt" / "bin",
    PYSIDE_ROOT / "Qt" / "lib",
    SITE_PACKAGES / "shiboken6",
)

if not (RUNTIME_ROOT / "python.exe").is_file():
    raise SystemExit(
        "[KAFIA NET CONTROL PRO] External Python runtime not found: "
        f"{RUNTIME_ROOT / 'python.exe'}"
    )

# Put only existing paths into the Python and Windows DLL search paths.
path_entries = []
for directory in _DLL_DIRECTORIES:
    if directory.is_dir():
        path_entries.append(str(directory))
        if hasattr(os, "add_dll_directory"):
            try:
                _DLL_DIRECTORY_HANDLES.append(
                    os.add_dll_directory(str(directory))
                )
            except OSError as exc:
                print(
                    "DLL DIRECTORY WARNING:",
                    directory,
                    exc,
                    file=sys.stderr,
                )

existing_path = os.environ.get("PATH", "")
os.environ["PATH"] = os.pathsep.join(
    path_entries + ([existing_path] if existing_path else [])
)

for import_path in (APP_ROOT, SITE_PACKAGES):
    if import_path.is_dir() and str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

# Prefer Qt plugins and QML modules from the same external PySide6 install.
_PLUGIN_ROOTS = (
    PYSIDE_ROOT / "plugins",
    PYSIDE_ROOT / "Qt" / "plugins",
)
for plugin_root in _PLUGIN_ROOTS:
    platform_plugin = plugin_root / "platforms" / "qwindows.dll"
    if platform_plugin.is_file():
        os.environ["QT_PLUGIN_PATH"] = str(plugin_root)
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(
            plugin_root / "platforms"
        )
        break

_qml_roots = [
    path
    for path in (
        PYSIDE_ROOT / "qml",
        PYSIDE_ROOT / "Qt" / "qml",
    )
    if path.is_dir()
]
if _qml_roots:
    qml_path = os.pathsep.join(str(path) for path in _qml_roots)
    os.environ["QML_IMPORT_PATH"] = qml_path
    os.environ["QML2_IMPORT_PATH"] = qml_path

# Run the real application, preserving any command-line smoke-test arguments.
application = APP_ROOT / "app_qml.py"
if not application.is_file():
    raise SystemExit(
        f"[KAFIA NET CONTROL PRO] Application source not found: {application}"
    )

sys.argv = [str(application), *sys.argv[1:]]
runpy.run_path(str(application), run_name="__main__")
