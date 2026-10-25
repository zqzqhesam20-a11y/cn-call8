# KAFIA NET CONTROL PRO

## Standalone Windows installer

The released Windows installer is built as a self-contained PyInstaller onedir application. It includes the required Python 3.14 runtime, PySide6/Qt binaries and plugins, application modules, ADB binaries, and compiled Qt resources for the QML interface, images, and games.json.

**The installed application does not use `D:\games\py` as its Python runtime and does not need Python or PySide6 installed system-wide.** The app folder installed by the installer contains the runtime libraries it needs. It does not download or copy a Python runtime at launch.

## Paths intentionally retained

- The game library on SERVER06 remains the network source for the wireless/network source mode.
- `D:\games` remains the optional local/USB game-library source. That is game data, not the Python runtime.
- The MT Manager APK remains at the existing SERVER06 application-source path.
- The installer includes ADB and its DLLs with the application so it does not require a separate ADB installation.

## Source protection

The packaged output embeds active QML files, game images and `games.json` into Qt resources and does not copy those files as loose plaintext resources. Python modules are packed by PyInstaller rather than shipped as loose `.py` files. This reduces casual source access but is not unbreakable encryption; a determined analyst may reverse engineer a local executable.

The GitHub repository remains public, so files committed to the repository can still be read online. Protecting the distributed installer does not hide the repository's source history.

## Build validation

The self-contained workflow performs regression simulations, builds the PyInstaller onedir bundle, verifies that Python and Qt runtime DLLs and ADB are present, rejects loose QML/game metadata in the output, runs frozen Qt and embedded-QML smoke tests, and builds a compressed Inno Setup installer.
