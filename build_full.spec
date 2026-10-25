# Self-contained PyInstaller spec. Python, PySide6 and Qt runtime files are collected by PyInstaller.
# UI/QML/images and game metadata are compiled into ui_resources_rc before this spec runs.
# Do not copy source folders (engine/, ui/, qml/, assets/) as loose data files.

import os

resource_build_dir = os.path.abspath("build")

datas = [
    ("platform-tools", "platform-tools"),
]

hiddenimports = [
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "ui_resources_rc",
]

a = Analysis(
    ["app_qml.py"],
    pathex=[".", resource_build_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)


def _keep_ui_bundle(entry):
    destination = str(entry[0]).replace("\\", "/")
    marker = "PySide6/qml/"
    if marker in destination:
        module_path = destination.split(marker, 1)[1]
        if not module_path.startswith(("QtQuick/", "QtQml/", "Qt/")):
            return False

    normalized = "/" + destination.lower().strip("/") + "/"
    if "/translations/" in normalized and destination.lower().endswith(".qm"):
        filename = destination.rsplit("/", 1)[-1].lower()
        language = filename[:-3].rsplit("_", 1)[-1]
        if language not in {"ar", "en", "en_us", "en_gb"}:
            return False
    return True


a.datas = [entry for entry in a.datas if _keep_ui_bundle(entry)]
a.binaries = [entry for entry in a.binaries if _keep_ui_bundle(entry)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KAFIA_NET_CONTROL_PRO",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

bundle = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="KAFIA_NET_CONTROL_PRO",
)
