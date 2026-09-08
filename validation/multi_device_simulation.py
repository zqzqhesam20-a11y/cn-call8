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
    head = subprocess.check_output(["git", "show", "HEAD:app_qml.py"], text=True)
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
    assert "TransferWindow()" not in current


def run_once():
    controller = make_controller()
    test_discovery_and_selection(controller)
    test_zero_selection(controller)
    test_independent_operations(controller)
    test_busy_serial_and_idle_serial(make_controller())
    test_failure_cancel_and_completion_isolation(make_controller())
    test_install_operations(make_controller())
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
