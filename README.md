# KAFIA NET CONTROL PRO — self-contained Windows build

The released installer is built from the current branch using PyInstaller. Python, PySide6, Qt DLLs, Qt Quick/QML runtime modules, ADB, application logic, QML screens, game images and game metadata are bundled or embedded; the installed application does not need an external Python runtime under D:\games\py.

The game library and MT Manager APK can still be read from the configured game source locations as part of their existing features. Those are application data sources, not a Python/Qt runtime dependency.

## UI and build verification

- The build retains all PySide6 QML modules instead of pruning them to save package size.
- The frozen-app smoke test checks the sidebar, games dashboard, and transfer panel in the embedded QML.
- The smoke test emits a test transfer-list signal and verifies that the transfer panel actually becomes visible.
- The installer is not published unless the frozen UI and transfer-panel smoke tests pass.

The installer is self-contained, but no locally distributed executable can be guaranteed impossible to reverse-engineer. The repository is public, so source files committed here remain readable on GitHub; compiled packaging protects the shipped artifact from simple source browsing, not from a determined analyst.
