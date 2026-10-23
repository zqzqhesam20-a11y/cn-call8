"""Deterministic simulation of independent per-device operations."""

import os
import subprocess
import sys
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from engine.adb_engine import ADBEngine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_controller():
    module = ModuleType("app_qml")
    module.__file__ = str(ROOT / "app_qml.py")
    sys.modules["app_qml"] = module
    source = Path(module.__file__).read_text(encoding="utf-8")
    source = source[:source.index('\nprint("STARTING KAFIA NET CONTROL PRO")')]
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


app_qml = load_controller()

DEVICES = [
    {"serial": "SERIAL_A", "model": "Samsung A", "name": "Samsung A"},
    {"serial": "SERIAL_B", "model": "Samsung B", "name": "Samsung B"},
    {"serial": "SERIAL_C", "model": "Samsung C", "name": "Samsung C"},
]


class FakeOperationEngine(QObject):
    progressChanged = Signal(int, str, str)
    statusChanged = Signal(str)
    finished = Signal(bool, str)
    logChanged = Signal(str)

    instances = []

    def __init__(self):
        super().__init__()
        self.serial = None
        self.calls = []
        self.cancelled = False
        self.paused = False
        FakeOperationEngine.instances.append(self)

    def push(self, serial, source, destination):
        self.serial = serial
        self.calls.append(("push", serial, source, destination))

    def install(self, serial, apk):
        self.serial = serial
        self.calls.append(("install", serial, apk))

    def install_apks(self, serial, apk):
        self.serial = serial
        self.calls.append(("install_apks", serial, apk))

    def cancel(self):
        self.cancelled = True

    def pause(self):
        self.paused = True
        return True

    def resume(self):
        self.paused = False
        return True

    def progress(self, percent, speed="--", eta="--"):
        self.progressChanged.emit(percent, speed, eta)

    def finish(self, success, message):
        self.finished.emit(success, message)


class DiscoveryEngine:
    _thread = None

    def __init__(self):
        self.discovery = list(DEVICES)

    def get_devices(self):
        return list(self.discovery)


def rows(serials):
    return [
        {
            "serial": serial,
            "model": serial,
            "game": "PUBG Mobile",
            "kind": "copy",
            "status": "انتظار",
            "percent": 0,
            "operation": "في قائمة الانتظار",
            "speed": "--",
            "eta": "--",
            "error": "",
            "completed": False,
            "cancelled": False,
        }
        for serial in serials
    ]


def make_controller():
    app_qml.ADBEngine = FakeOperationEngine
    controller = app_qml.AppController()
    controller.adb_engine = DiscoveryEngine()
    FakeOperationEngine.instances = []
    return controller


def engine_for(serial):
    return next(
        engine for engine in FakeOperationEngine.instances
        if engine.serial == serial
    )


def test_discovery_and_selection(controller):
    models = []
    controller.adbDevicesChanged.connect(models.append)
    controller.getADBDevices()
    assert [item["serial"] for item in models[-1]] == [
        "SERIAL_A", "SERIAL_B", "SERIAL_C"
    ]
    assert controller.selected_devices == []
    assert controller.selected_device == ""


def test_zero_selection(controller):
    rejected = []
    controller.operationRejected.connect(rejected.append)
    controller.copyGame("Free Fire")
    controller.installGame("Free Fire")
    assert "تحديد هاتف" in rejected[0]
    assert "تحديد هاتف" in rejected[1]


def test_independent_operations(controller):
    controller._start_operation(
        dict(rows(["SERIAL_A"])[0], source="src", destination="dst")
    )
    controller._start_operation(
        dict(rows(["SERIAL_B"])[0], source="src", destination="dst")
    )
    assert set(controller._active_operations) == {"SERIAL_A", "SERIAL_B"}
    assert engine_for("SERIAL_A").calls[-1][1] == "SERIAL_A"
    assert engine_for("SERIAL_B").calls[-1][1] == "SERIAL_B"
    engine_for("SERIAL_A").progress(35, "10 MB/s", "00:10")
    engine_for("SERIAL_B").progress(78, "20 MB/s", "00:05")
    state = {row["serial"]: row for row in controller._operation_rows()}
    assert state["SERIAL_A"]["percent"] == 35
    assert state["SERIAL_B"]["percent"] == 78
    assert state["SERIAL_A"]["speed"] == "10 MB/s"
    assert state["SERIAL_B"]["speed"] == "20 MB/s"


def test_busy_serial_and_idle_serial(controller):
    controller._start_operation(
        dict(rows(["SERIAL_A"])[0], source="src", destination="dst")
    )
    rejected = []
    controller.messageChanged.connect(rejected.append)
    controller.selected_devices = ["SERIAL_A", "SERIAL_B"]
    with TemporaryDirectory() as directory:
        root = Path(directory)
        game = root / "game"
        (game / "saved").mkdir(parents=True)
        controller.source_root = root
        app_qml.find_game_folder = lambda _root, _name: game
        app_qml.get_game = lambda _name: {"name": "test"}
        controller.copyGame("PUBG Mobile")
    assert "SERIAL_A" not in [
        call[1] for call in FakeOperationEngine.instances[-1].calls
    ]
    assert "SERIAL_B" in controller._active_operations
    assert any("عملية نقل قيد التنفيذ" in message for message in rejected)
    # The controller must pass the source root, not append '/.' and accidentally
    # let adb create a nested `saved` folder under an already-existing `Saved`.
    assert engine_for("SERIAL_B").calls[-1][2] == str(game / "saved")


def test_adb_source_arguments_and_progress_offset():
    with TemporaryDirectory() as directory:
        source = Path(directory) / "saved"
        source.mkdir()
        (source / "asset.pak").write_bytes(b"data")
        nested = source / "Paks"
        nested.mkdir()
        assert ADBEngine._adb_source_arguments(source) == [
            str(source / "asset.pak"),
            str(nested),
        ]
        asset = source / "asset.pak"
        assert ADBEngine._adb_source_arguments(asset) == [str(asset)]

    assert ADBEngine._combined_progress_percent(1000, 600, 0) == 60
    assert ADBEngine._combined_progress_percent(1000, 600, 150) == 75
    assert ADBEngine._combined_progress_percent(1000, 1000, 0) == 99
    assert ADBEngine._combined_progress_percent(0, 0, 0) == 0


def test_failure_cancel_and_completion_isolation(controller):
    for serial in ("SERIAL_A", "SERIAL_B", "SERIAL_C"):
        controller._start_operation(
            dict(rows([serial])[0], source="src", destination="dst")
        )
    a = engine_for("SERIAL_A")
    b = engine_for("SERIAL_B")
    c = engine_for("SERIAL_C")
    a.finish(False, "A original error")
    assert controller._active_operations["SERIAL_B"]["status"] != "فشل"
    controller.cancelDevice("SERIAL_A")
    assert not b.cancelled and not c.cancelled
    b.finish(True, "B complete")
    c.finish(True, "C complete")
    assert controller._active_operations["SERIAL_A"]["error"] == "A original error"
    assert controller._active_operations["SERIAL_B"]["status"] == "اكتمل"
    assert controller._active_operations["SERIAL_C"]["status"] == "اكتمل"
    assert not controller.operationBusy
    assert controller._operation_state == "IDLE"


def test_install_operations(controller):
    for serial in ("SERIAL_A", "SERIAL_B", "SERIAL_C"):
        operation = dict(rows([serial])[0])
        operation.update(
            kind="install",
            game="Free Fire",
            percent=-1,
            apk="game.apk",
            install_type="apk",
        )
        controller._start_operation(operation)
    assert [
        engine.calls[-1][1] for engine in FakeOperationEngine.instances
    ] == ["SERIAL_A", "SERIAL_B", "SERIAL_C"]
    assert all(
        controller._active_operations[serial]["percent"] == -1
        for serial in ("SERIAL_A", "SERIAL_B", "SERIAL_C")
    )
    controller.cancelDevice("SERIAL_A")
    assert not engine_for("SERIAL_B").cancelled
    engine_for("SERIAL_A").finish(False, "cancelled")
    engine_for("SERIAL_B").finish(False, "B install error")
    engine_for("SERIAL_C").finish(True, "C installed")
    assert controller._active_operations["SERIAL_B"]["error"] == "B install error"
    assert controller._active_operations["SERIAL_C"]["status"] == "اكتمل"


def test_pause_resume_operations():
    FakeOperationEngine.instances = []
    controller = make_controller()
    for serial in ("SERIAL_A", "SERIAL_B"):
        controller._start_operation(
            dict(rows([serial])[0], source="src", destination="dst")
        )

    pause_events = []
    controller.transferPausedChanged.connect(pause_events.append)
    controller.pauseTransfer()
    assert controller._transfer_paused
    assert engine_for("SERIAL_A").paused
    assert engine_for("SERIAL_B").paused
    assert pause_events[-1] is True

    controller.resumeTransfer()
    assert not controller._transfer_paused
    assert not engine_for("SERIAL_A").paused
    assert not engine_for("SERIAL_B").paused
    assert pause_events[-1] is False

    controller.cancelDevice("SERIAL_A")
    controller.cancelDevice("SERIAL_B")
    engine_for("SERIAL_A").finish(False, "cancelled")
    engine_for("SERIAL_B").finish(False, "cancelled")


def test_oem_permission_guidance():
    controller = make_controller()
    serial = "XIAOMI_SERIAL"
    controller._device_info[serial] = {
        "manufacturer": "Xiaomi",
        "model": "Redmi Note"
    }
    operation = {
        "serial": serial,
        "kind": "copy",
        "destination": "/sdcard/Android/data/com.test.game/",
        "status": "فشل",
        "percent": 0,
        "operation": "فشل النسخ",
        "speed": "--",
        "eta": "--",
        "error": "Permission denied",
        "raw_error": "remote secure_mkdirs failed: Permission denied",
        "completed": True,
        "cancelled": False,
    }
    controller._active_operations[serial] = operation

    summary = controller._device_copy_failure_summary(
        serial, operation, operation["raw_error"]
    )
    assert "Android/data" in summary
    assert "إرشادات الإصلاح" in summary

    help_text = controller.deviceCopyHelp(serial)
    assert "Xiaomi Redmi Note" in help_text
    assert "USB debugging (Security settings)" in help_text
    assert "Install via USB" in help_text
    assert "remote secure_mkdirs failed: Permission denied" in help_text
    assert "لا يحاول التطبيق تعطيل حماية النظام" in help_text


def test_duplicate_completion(controller):
    operation = dict(rows(["SERIAL_A"])[0], source="src", destination="dst")
    controller._start_operation(operation)
    engine = engine_for("SERIAL_A")
    completions = []
    controller.operationFinished.connect(completions.append)
    engine.finish(True, "complete")
    engine.finish(True, "duplicate")
    assert len(completions) == 1


class FakeProcess:
    next_pid = 100

    def __init__(self):
        FakeProcess.next_pid += 1
        self.pid = FakeProcess.next_pid
        self.returncode = 0
        self.done = threading.Event()
        self.terminated = False

    def communicate(self, timeout=None):
        if timeout is not None and not self.done.wait(timeout):
            raise subprocess.TimeoutExpired([], timeout)
        return "stdout", ""

    def poll(self):
        return None if not self.done.is_set() else self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15
        self.done.set()


class FakeStartupInfo:
    def __init__(self):
        self.dwFlags = 0
        self.wShowWindow = 0


def test_process_ownership():
    import engine.adb_engine as adb_module

    original = {
        key: getattr(adb_module.subprocess, key, None)
        for key in ("Popen", "STARTUPINFO", "STARTF_USESHOWWINDOW", "SW_HIDE")
    }
    processes = []

    def fake_popen(*_args, **_kwargs):
        process = FakeProcess()
        processes.append(process)
        return process

    adb_module.subprocess.Popen = fake_popen
    adb_module.subprocess.STARTUPINFO = FakeStartupInfo
    adb_module.subprocess.STARTF_USESHOWWINDOW = 1
    adb_module.subprocess.SW_HIDE = 0
    engine = adb_module.ADBEngine()
    try:
        first = threading.Thread(
            target=lambda: engine._run_install_command(["install", "a"], 30)
        )
        first.start()
        while len(processes) < 1:
            pass
        old = processes[0]
        second = threading.Thread(
            target=lambda: engine._run_install_command(["install", "b"], 30)
        )
        second.start()
        while len(processes) < 2:
            pass
        new = processes[1]
        old.done.set()
        first.join(1)
        assert engine._current_process is new
        new.done.set()
        second.join(1)
        assert engine._current_process is None
        third = threading.Thread(
            target=lambda: engine._run_install_command(["install", "c"], 30)
        )
        third.start()
        while engine._current_process is None:
            pass
        active = engine._current_process
        engine.cancel()
        third.join(1)
        assert active.terminated and engine._current_process is None
    finally:
        for key, value in original.items():
            if value is not None:
                setattr(adb_module.subprocess, key, value)


def test_paths_and_ui():
    current = Path("app_qml.py").read_text(encoding="utf-8")
    head = subprocess.check_output(
        ["git", "show", "HEAD:app_qml.py"],
        encoding="utf-8",
        errors="strict"
    )
    for start, end in (
        ('        elif game_name == "PUBG Mobile":',
         '        elif game_name == "Call of Duty Mobile":'),
        ('        elif game_name == "Call of Duty Mobile":', "        else:"),
    ):
        a, b = current.index(start), current.index(end, current.index(start))
        x, y = head.index(start), head.index(end, head.index(start))
        assert current[a:b] == head[x:y]
    engine_source = Path("engine/adb_engine.py").read_text()
    install_start = engine_source.index("def install_apks")
    install_end = engine_source.index("def _suspend_current_process")
    assert "progressChanged.emit(\n                        100" not in (
        engine_source[install_start:install_end]
    )
    qml = Path("qml/main.qml").read_text()
    assert "model: window.transferDevices" in qml
    assert "onClicked: appController.cancelDevice" in qml
    assert '"إيقاف مؤقت"' in qml
    assert '"استئناف"' in qml
    assert "appController.pauseTransfer()" in qml
    assert "appController.resumeTransfer()" in qml
    assert "إرشادات الإصلاح" in qml
    assert "deviceCopyHelpDialog.open()" in qml
    assert "deviceCopyHelpText" in qml
    assert "TransferWindow()" not in current

    # Regression checks for the repaired lifecycle and physical source paths.
    assert 'return Path(r"D:\\games")' in current
    assert "source = build_usb_source_root()" in current
    assert "if not source.is_dir():" in current
    assert "self.adbDiscoveryCompleted.connect(self._apply_adb_devices)" in current
    assert "def refreshADBDevices(self):" in current
    assert "active = any(" in current
    launch = current[current.index("def launchGame(self, game_name):"):]
    launch = launch[:launch.index("package_id = ADB_PACKAGE_IDS.get(")]
    assert "self.adb_engine.get_devices()" not in launch
    assert "يرجى تحديد هاتف واحد على الأقل قبل تشغيل اللعبة." in launch

    # Disconnected phones wait for reconnection and retry only unsynced files.
    assert "def _device_is_connected(self, device):" in engine_source
    assert "self._wait_for_device_reconnect(device)" in engine_source
    assert "انقطع اتصال الهاتف. الرجاء إعادة توصيله لاستمرار النسخ..." in engine_source
    assert '"--sync"' in engine_source
    assert "تمت إعادة توصيل الهاتف" in engine_source

    # Protect against ADB stderr pipe deadlocks and false 100% completion.
    wait_start = engine_source.index("def _push_thread")
    stderr_start = engine_source.index("stderr_reader.start()", wait_start)
    wait_call = engine_source.index("return_code = process.wait()", wait_start)
    assert stderr_start < wait_call
    assert "stderr_reader.join(timeout=2.0)" in engine_source
    assert "min(percent, 99)" in engine_source
    assert "time.time_ns()" in engine_source
    assert engine_source.index(
        'local_adb = BASE_DIR / "platform-tools" / "adb.exe"'
    ) < engine_source.index('external_adb = Path(')

    assert "appController.refreshADBDevices()" in qml
    assert "appController.getADBDevices()" not in qml
    assert "if (appController.useWirelessSource())" in qml
    assert "if (appController.useUsbSource())" in qml

    # Shipping launchers must avoid CMD codepage corruption for Arabic UNC components.
    launcher = Path("Start-KAFIANET-CONTROL-PRO.cmd").read_text(encoding="utf-8")
    assert all(ord(char) < 128 for char in launcher)
    assert "Launch-KAFIA-NET-CONTROL-PRO.vbs" in launcher
    assert "wscript.exe" in launcher
    hidden_launcher = Path("Launch-KAFIA-NET-CONTROL-PRO.vbs").read_text(encoding="utf-8")
    assert all(ord(char) < 128 for char in hidden_launcher)
    assert "Start-KAFIANET-CONTROL-PRO.ps1" in hidden_launcher
    assert "shell.Run(command, 0, True)" in hidden_launcher

    external_launcher = Path("Start-KAFIANET-CONTROL-PRO.ps1").read_text(
        encoding="utf-8"
    )
    assert all(ord(char) < 128 for char in external_launcher)
    assert "SERVER06\\c$" in external_launcher
    assert "0x0639" in external_launcher
    assert "0x062E" in external_launcher
    assert "PYTHONHOME" in external_launcher
    assert "PYTHONPATH" in external_launcher
    assert "--qt-import-smoke-test" in external_launcher
    assert "kafianet_external_runtime.py" in external_launcher
    assert "Start-Process" in external_launcher
    assert "-WindowStyle Hidden" in external_launcher
    assert "WScript.Shell" in external_launcher
    assert "Invoke-WebRequest" not in external_launcher
    assert "pip install" not in external_launcher
    assert "vc_redist" not in external_launcher

    bootstrap = Path("kafianet_external_runtime.py").read_text(encoding="utf-8")
    runtime_root = r"\\SERVER06\c$\العابي\222\66\الاخييير\py"
    assert runtime_root in bootstrap
    assert "os.add_dll_directory" in bootstrap
    assert "QT_QPA_PLATFORM_PLUGIN_PATH" in bootstrap
    assert "runpy.run_path" in bootstrap
    assert "from PySide6.QtWidgets import QApplication" in current
    assert "QTWIDGETS_QAPPLICATION_SMOKE_TEST: PASS" in current
    assert "pyside_parts < (6, 10, 1)" in current
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    assert "PySide6>=6.10.1,<7" in requirements

    for workflow_path in (
        Path(".github/workflows/build-windows.yml"),
        Path(".github/workflows/build-windows-runtime.yml"),
    ):
        workflow = workflow_path.read_text(encoding="utf-8")
        assert "PyInstaller" not in workflow
        assert "https://aka.ms/vc14/vc_redist.x64.exe" not in workflow
        assert "python314.dll" not in workflow
        assert "Forbidden runtime file" in workflow


def run_once():
    controller = make_controller()
    test_discovery_and_selection(controller)
    test_zero_selection(controller)
    test_independent_operations(controller)
    test_busy_serial_and_idle_serial(make_controller())
    test_adb_source_arguments_and_progress_offset()
    test_failure_cancel_and_completion_isolation(make_controller())
    test_install_operations(make_controller())
    test_pause_resume_operations()
    test_oem_permission_guidance()
    test_duplicate_completion(make_controller())
    test_process_ownership()
    test_paths_and_ui()


def main():
    QApplication.instance() or QApplication([])
    run_once()
    run_once()
    print("RUN 1: ALL PASS")
    print("RUN 2: ALL PASS")


if __name__ == "__main__":
    main()
