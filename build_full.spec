# Compact PyInstaller spec for the KAFIA NET CONTROL PRO Qt/QML app.
#
# Intentionally avoid collect_all("PySide6"): it copies every PySide extension,
# Qt DLL, translation, and data file, including modules the app never uses.
# PyInstaller's built-in PySide6 hooks collect the native dependencies and the
# QML plugins/files required by the imported QtQml/QtQuick modules.

datas = [
    ("qml", "qml"),
    ("assets", "assets"),
    ("ui", "ui"),
    ("engine", "engine"),
    ("games.json", "."),
    ("platform-tools", "platform-tools"),
]

hiddenimports = [
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
]

a = Analysis(
    ["app_qml.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="KAFIA_NET_CONTROL_PRO",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
