# KAFIA NET CONTROL PRO — cn-call8

## Runtime and build protection

The application now uses the local 64-bit Python 3.14 runtime at:

    D:\games\py\python.exe

The game library and MT Manager APK source remain on the existing SERVER06 share; only the Python/Qt runtime path changed.

The protected installer compiles application Python modules into Nuitka native extension modules (.pyd) and embeds active QML, game images and games.json as Qt binary resources. The installer does not include raw application .py files, .qml files, image files, or games.json. It includes compiled modules, the small Windows launchers, and the ADB binaries required by existing functionality.

This is source protection/obfuscation, not mathematically unbreakable encryption. A determined analyst may still reverse-engineer a local executable, and strings or behavior observable at runtime cannot be guaranteed secret.

IMPORTANT REPOSITORY LIMITATION: this GitHub repository is public, so source files committed here remain readable online even though the installer artifact is compiled. To keep the source private, the repository itself must be made private or the source must be moved out of a public repository. This build does not change repository visibility.

## Launch and compatibility

- The launcher uses D:\games\py and does not download, install, or copy a Python runtime.
- The runtime must be 64-bit Python 3.14 with compatible PySide6/Qt libraries (PySide6 6.10.1 or newer) and psutil.
- The launcher runs a Qt startup smoke test before opening the UI.
- The active QML UI and game metadata are loaded from compiled Qt resources. Development runs may still use source QML and games.json when no resource module is installed.
- The existing Android/data MT Manager pre-install and permission-denial root-fallback flow remains part of the app.

## Build and CI

- The Windows workflow runs regression simulation, compiles the protected installer, validates that source files did not leak into its payload, and uploads the protected installer.
- The manual package workflow creates a protected ZIP with the same compiler/resource pipeline.
- The external Python runtime is never copied into either artifact.
