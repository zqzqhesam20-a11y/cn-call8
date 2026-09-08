from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

for package in ["PySide6"]:
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["app_qml.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas + [
        ("qml", "qml"),
        ("assets", "assets"),
        ("ui", "ui"),
        ("engine", "engine"),
        ("games.json", "."),
        ("platform-tools", "platform-tools"),
    ],
    hiddenimports=hiddenimports + [
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
    ],
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
