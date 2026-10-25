# Compact PyInstaller spec for the KAFIA NET CONTROL PRO Qt/QML app.
#
# Avoid a broad all-package collection here: it copies every PySide extension,
# Qt DLL, translation, and data file, including modules the app never uses.
# PyInstaller's built-in PySide6 hooks collect native dependencies and QML
# plugins/files for the imported QtQml and QtQuick modules.

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

# The Qt/QML hook scans the installed QML tree. This UI imports QtQuick,
# QtQuick.Controls, and QtQuick.Layouts; these and their standard dependencies
# are contained in QtQuick and QtQml. Keep the Qt namespace too, but drop
# unrelated QML modules (for example QtCharts, Qt3D, QtWebEngine, QtMultimedia).
def _keep_ui_qml(entry):
    destination = str(entry[0]).replace("\\", "/")
    marker = "PySide6/qml/"
    if marker not in destination:
        return True
    module_path = destination.split(marker, 1)[1]
    return module_path.startswith(("QtQuick/", "QtQml/", "Qt/"))

a.datas = [entry for entry in a.datas if _keep_ui_qml(entry)]
a.binaries = [entry for entry in a.binaries if _keep_ui_qml(entry)]

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
