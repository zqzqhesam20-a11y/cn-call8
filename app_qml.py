import sys
import os
import threading
from pathlib import Path

# Keep Arabic diagnostics from crashing when launched with a legacy Windows
# console code page. Packaged GUI builds may have no console streams at all.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Fusion"

from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

# CI/runtime smoke test: importing QtWidgets alone is insufficient because
# Qt's platform plugins are loaded when QApplication is constructed.
# Build verification invokes this mode against the frozen executable.
if "--qt-import-smoke-test" in sys.argv:
    pyside_version = getattr(__import__("PySide6"), "__version__", "0.0.0")
    print("PYTHON_RUNTIME:", sys.executable)
    print("PYSIDE6_VERSION:", pyside_version)
    try:
        pyside_parts = tuple(int(part) for part in pyside_version.split(".")[:3])
    except (TypeError, ValueError):
        pyside_parts = (0, 0, 0)
    if pyside_parts < (6, 10, 1):
        raise RuntimeError(
            "Python 3.14 requires PySide6 6.10.1 or newer; "
            f"found {pyside_version}."
        )
    app = QApplication([])
    print("QTWIDGETS_QAPPLICATION_SMOKE_TEST: PASS")
    sys.exit(0)

from engine.transfer_engine import TransferEngine
from engine.adb_engine import ADBEngine
from engine.path_manager import PathManager
from engine.game_config import get_game, find_game_folder


BASE_DIR = Path(__file__).resolve().parent

# ?????? Android ???????? ???????
ADB_PACKAGE_IDS = {
    "MT Manager": "bin.mt.plus",
    "Free Fire": "com.dts.freefireth",
    "Fortnite": "com.epicgames.fortnite",
    "Genshin Impact": "com.miHoYo.GenshinImpact",
    "eFootball": "com.konami.pesam",
    "PUBG Mobile": "com.tencent.ig",
    "Call of Duty Mobile": "com.activision.callofduty.shooter",
}

ADB_GAME_DESTINATIONS = {
    "Fortnite": "/sdcard/Android/data/com.epicgames.fortnite/",
    "Genshin Impact": "/sdcard/Android/data/com.miHoYo.GenshinImpact/",
    "eFootball": "/sdcard/Android/data/com.konami.pesam/",
    "Free Fire": "/sdcard/Android/data/com.dts.freefireth/",
    "PUBG Mobile": "/sdcard/Android/data/com.tencent.ig/files/UE4Game/ShadowTrackerExtra/ShadowTrackerExtra/Saved/",
    "Call of Duty Mobile": "/sdcard/Android/data/com.activision.callofduty.shooter/",
}

# ????? ?????? ??????? ??? ?????? ???? Python ??? ?? ?????
# ?????? PowerShell.
def _arabic_name(codepoints):
    return "".join(chr(x) for x in codepoints)


SERVER_GAMES_FOLDER = _arabic_name([
    0x627, 0x644, 0x639, 0x627, 0x628, 0x64a
])


def build_server_source_root():
    return Path(r"\\SERVER06\c$") / SERVER_GAMES_FOLDER


def build_usb_source_root():
    return Path(r"D:\games")



def build_mt_manager_apk_path():
    return build_server_source_root() / "تطبيقات للنسخ" / "MT_Manager_2.26.4.apk"


class AppController(QObject):

    messageChanged = Signal(str)
    transferPercentChanged = Signal(int)
    transferSpeedChanged = Signal(str)
    transferEtaChanged = Signal(str)
    transferFinished = Signal(bool, str)
    operationStateChanged = Signal(str)
    transferPausedChanged = Signal(bool)
    operationRejected = Signal(str)
    transferBatchChanged = Signal(list)
    deviceProgressChanged = Signal(str, int, str, str, str, str, str)
    operationFinished = Signal(str)
    androidDataFallbackRequested = Signal(str, str, str, str)
    busyChanged = Signal(bool)
    usbChanged = Signal(str)
    destinationChanged = Signal(str)
    adbDevicesChanged = Signal(list)
    adbDiscoveryCompleted = Signal(list)

    def __init__(self):
        super().__init__()

        self.paths = PathManager()

        # ?????? ??????: ????? ??????
        self.engine = TransferEngine()

        # ???? ADB: ????? ???????? ??? ??????
        self.adb_engine = ADBEngine()

        self.adb_engine.progressChanged.connect(
            self._progress
        )

        self.adb_engine.statusChanged.connect(
            self._transfer_status
        )

        self.adb_engine.logChanged.connect(
            self._transfer_log
        )

        self.adb_engine.statusChanged.connect(
            self._status
        )

        self.adb_engine.finished.connect(
            self._finished
        )

        self.engine.progressChanged.connect(
            self._progress
        )

        self.engine.statusChanged.connect(
            self._status
        )

        self.engine.finished.connect(
            self._finished
        )

        self.source_root = build_server_source_root()

        self.destination_root = Path(
            r"D:\games"
        )

        self._current_game = ""

        # ???? ADB ??????
        self.selected_device = ""
        self.selected_devices = []
        self._active_operations = {}
        self._operation_state = "IDLE"
        self._operation_busy = False
        self._transfer_paused = False
        self._device_info = {}

        self.current_source = "WIRELESS"
        self._adb_discovery_lock = threading.Lock()
        self._adb_discovery_thread = None
        self.adbDiscoveryCompleted.connect(self._apply_adb_devices)
        print("CONTROLLER READY")
        print("SOURCE:", self.source_root)
        print("DEST:", self.destination_root)

    @Slot(result=bool)
    def useWirelessSource(self):
        source = build_server_source_root()
        if not source.is_dir():
            self.messageChanged.emit(
                f"تعذر الوصول إلى مصدر الشبكة: {source}"
            )
            return False

        self.current_source = "WIRELESS"
        self.source_root = source
        self.messageChanged.emit(f"تم اختيار مصدر الشبكة: {source}")
        print("SOURCE SELECTED: WIRELESS", self.source_root)
        return True

    @Slot(result=bool)
    def useUsbSource(self):
        source = build_usb_source_root()
        if not source.is_dir():
            self.messageChanged.emit(
                f"مجلد USB غير موجود أو غير متاح: {source}"
            )
            return False

        self.current_source = "USB"
        self.source_root = source
        self.messageChanged.emit(f"تم اختيار مصدر USB: {source}")
        print("SOURCE SELECTED: USB", self.source_root)
        return True



    def _transfer_progress(self, percent, speed, eta):
        self._progress(percent, speed, eta)


    def _transfer_status(self, text):
        self._status(text)


    def _transfer_log(self, text):
        print("TRANSFER LOG:", text)

    def _get_current_game(self):
        return self._current_game

    def _set_current_game(self, value):
        if self._current_game != value:
            self._current_game = value
            self.currentGameChanged.emit()

    currentGameChanged = Signal()
    currentGame = Property(
        str,
        _get_current_game,
        _set_current_game,
        notify=currentGameChanged
    )

    def _get_operation_busy(self):
        return self._operation_busy

    operationBusy = Property(
        bool,
        _get_operation_busy,
        notify=busyChanged
    )

    def _progress(self, percent, speed, eta):
        print(
            f"PROGRESS: {percent}% | {speed} | ETA {eta}"
        )

        self.transferPercentChanged.emit(percent)
        self.transferSpeedChanged.emit(speed)
        self.transferEtaChanged.emit(eta)

        for serial, operation in self._active_operations.items():
            if operation.get("engine") is self.adb_engine:
                self._update_operation(
                    serial,
                    percent=percent,
                    speed=speed,
                    eta=eta
                )

    def _status(self, message):
        print("STATUS:", message)
        self.messageChanged.emit(message)

        for serial, operation in self._active_operations.items():
            if operation.get("engine") is self.adb_engine:
                self._update_operation(
                    serial,
                    status=message,
                    operation_text=message
                )

    def _set_operation_state(self, state):
        self._operation_state = state
        busy = any(
            not operation.get("completed", False)
            for operation in self._active_operations.values()
        )

        if self._operation_busy != busy:
            self._operation_busy = busy
            self.busyChanged.emit(busy)

        if not busy and self._transfer_paused:
            self._transfer_paused = False
            self.transferPausedChanged.emit(False)

        self.operationStateChanged.emit(state)

    def _reject_operation(self, message):
        self.messageChanged.emit(message)
        self.operationRejected.emit(message)

    def _operation_rows(self):
        return [
            {
                "serial": operation["serial"],
                "model": operation.get("model", "Android"),
                "game": operation.get("game", ""),
                "kind": operation.get("kind", ""),
                "status": operation.get("status", "انتظار"),
                "percent": operation.get("percent", 0),
                "operation": operation.get("operation", ""),
                "speed": operation.get("speed", "--"),
                "eta": operation.get("eta", "--"),
                "error": operation.get("error", ""),
                "raw_error": operation.get("raw_error", ""),
                "cancelled": operation.get("cancelled", False)
            }
            for operation in self._active_operations.values()
        ]

    def _update_operation(
        self,
        serial,
        percent=None,
        status=None,
        operation_text=None,
        speed=None,
        eta=None,
        error=None
    ):
        operation = self._active_operations.get(serial)
        if operation is None:
            return

        if percent is not None:
            operation["percent"] = percent
        if status is not None:
            operation["status"] = status
        if operation_text is not None:
            operation["operation"] = operation_text
        if speed is not None:
            operation["speed"] = speed
        if eta is not None:
            operation["eta"] = eta
        if error is not None:
            operation["error"] = error

        self.deviceProgressChanged.emit(
            serial,
            operation["percent"],
            operation["status"],
            operation["operation"],
            operation["speed"],
            operation["eta"],
            operation["error"]
        )
        self.transferBatchChanged.emit(self._operation_rows())

    def _emit_operation_state(self):
        self.transferBatchChanged.emit(self._operation_rows())
        active = any(
            not operation.get("completed", False)
            for operation in self._active_operations.values()
        )
        self._set_operation_state("ACTIVE" if active else "IDLE")

    def _operation_status_changed(self, serial, message):
        self._update_operation(
            serial,
            status=message,
            operation_text=message
        )
        self.messageChanged.emit(message)

    def _start_operation(self, operation):
        serial = operation["serial"]
        engine = ADBEngine()
        operation["engine"] = engine
        self._active_operations[serial] = operation

        engine.progressChanged.connect(
            lambda percent, speed, eta, s=serial:
            self._update_operation(
                s,
                percent=percent,
                speed=speed,
                eta=eta
            )
        )
        engine.statusChanged.connect(
            lambda message, s=serial:
            self._operation_status_changed(s, message)
        )
        engine.finished.connect(
            lambda success, message, s=serial:
            self._finished_for_device(
                s,
                success,
                message
            )
        )

        preinstall_stage = (
            operation["kind"] == "copy"
            and operation.get("preinstall_mt_manager", False)
            and not operation.get("mt_manager_preinstall_done", False)
        )

        self._emit_operation_state()
        self._update_operation(
            serial,
            status="جاري التثبيت"
            if operation["kind"] == "install"
            else "جاري فحص MT Manager"
            if preinstall_stage
            else "جاري النسخ",
            operation_text="تثبيت التطبيق"
            if operation["kind"] == "install"
            else "التحقق من MT Manager قبل النسخ"
            if preinstall_stage
            else "نسخ بيانات اللعبة",
            speed="--"
            if operation["kind"] == "install" or preinstall_stage
            else "0 B/s",
            eta="--"
        )

        if operation["kind"] == "install":
            if operation["install_type"] == "apks":
                engine.install_apks(serial, operation["apk"])
            else:
                engine.install(serial, operation["apk"])
        elif preinstall_stage:
            engine.install_if_missing(
                serial,
                operation["mt_manager_apk"],
                operation.get("mt_manager_package", "bin.mt.plus")
            )
        else:
            engine.push(
                serial,
                operation["source"],
                operation["destination"]
            )

    def _finished(self, success, message):
        self.messageChanged.emit(message)

    def _device_copy_failure_summary(self, serial, operation, raw_message):
        """Map common OEM/Android storage denials to a useful short message."""
        if operation.get("kind") != "copy":
            return raw_message

        text = str(raw_message or "")
        lowered = text.lower()
        permission_markers = (
            "permission denied",
            "remote secure_mkdirs failed",
            "read-only file system",
            "operation not permitted",
            "eacces",
            "errno 13",
        )
        if not any(marker in lowered for marker in permission_markers):
            return raw_message

        destination = str(operation.get("destination", ""))
        if "/android/data/" in destination.lower() or destination.lower().endswith("/android/data"):
            return (
                "الهاتف منع الكتابة داخل Android/data. "
                "افتح «إرشادات الإصلاح» لمعرفة السبب والخطوات المناسبة."
            )

        return (
            "الهاتف رفض الكتابة إلى وجهة النسخ. "
            "افتح «إرشادات الإصلاح» لمعرفة خطوات التشخيص."
        )

    @Slot(str, result=str)
    def deviceCopyHelp(self, serial):
        operation = self._active_operations.get(serial, {})
        info = self._device_info.get(serial, {})
        model = str(info.get("model") or info.get("name") or "Android")
        manufacturer = str(info.get("manufacturer") or "")
        brand_text = (manufacturer + " " + model).strip()
        brand_lower = (manufacturer + " " + model).lower()
        destination = str(operation.get("destination", ""))
        raw_error = str(operation.get("raw_error") or operation.get("error") or "")

        lines = [
            "الجهاز: " + brand_text,
            "",
            "1) افتح قفل الهاتف وأبقِ الشاشة مفتوحة. إذا ظهر طلب «السماح بتصحيح USB» لهذا الكمبيوتر، وافق عليه بعد التأكد أنك تثق بهذا الكمبيوتر.",
            "2) افتح إعدادات المطوّر وتأكد من تفعيل USB debugging. افصل الكابل وأعد توصيله، ثم جرّب منفذًا وكابل بيانات آخر عند الحاجة.",
        ]

        if any(name in brand_lower for name in ("xiaomi", "redmi", "poco", "شاومي", "ريدمي")):
            lines.extend([
                "",
                "شاومي / Redmi / POCO (MIUI أو HyperOS):",
                "• الإعدادات > الإعدادات الإضافية > خيارات المطوّر > USB debugging.",
                "• إذا كان الخيار موجودًا وكان إصدار النظام يطلبه، راجع USB debugging (Security settings) واقبل التحذير بعد قراءته. قد يتطلب النظام موافقة حساب Xiaomi أو شروطًا إضافية.",
                "• خيار Install via USB يتعلق أساسًا بتثبيت APK؛ تفعيله وحده لا يمنح بالضرورة حق الكتابة إلى Android/data.",
            ])
        elif any(name in brand_lower for name in ("oneplus", "oppo", "realme", "ون بلس")):
            lines.extend([
                "",
                "OnePlus / OPPO / realme:",
                "• الإعدادات > إعدادات النظام (أو الإعدادات الإضافية) > خيارات المطوّر > USB debugging.",
                "• وافق على طلب تصحيح USB على الهاتف. ويمكن ضبط USB default configuration على File transfer إذا كان اتصال USB نفسه غير مستقر.",
            ])
        else:
            lines.extend([
                "",
                "الإعدادات العامة:",
                "• خيارات المطوّر > USB debugging، ثم اقبل مفتاح RSA لهذا الكمبيوتر على شاشة الهاتف.",
            ])

        if "/android/data/" in destination.lower() or destination.lower().endswith("/android/data"):
            lines.extend([
                "",
                "مهم بخصوص Android/data:",
                "إذا كان الخطأ Permission denied أو remote secure_mkdirs failed، فقد يمنع إصدار Android أو واجهة الشركة الكتابة إلى هذا المسار عبر ADB. خيارات USB debugging لا تتجاوز هذا القيد دائمًا. لا يحاول التطبيق تعطيل حماية النظام أو استعمال صلاحيات root.",
                "الحل الآمن هو استخدام طريقة نقل يسمح بها الهاتف/النظام، أو اختيار مجلد وجهة غير محمي إذا كانت اللعبة تدعم ذلك. إذا كانت اللعبة تشترط Android/data وكان النظام يمنع الكتابة إليه، فسنعرض الرفض بدل الإبلاغ عن نجاح وهمي.",
            ])

        if raw_error:
            lines.extend([
                "",
                "رسالة ADB الأصلية:",
                raw_error,
            ])

        return "\n".join(lines)

    @staticmethod
    def _is_android_data_permission_denial(destination, raw_message):
        target = str(destination or "").lower()
        if "/android/data/" not in target and not target.endswith("/android/data"):
            return False

        lowered = str(raw_message or "").lower()
        permission_markers = (
            "permission denied",
            "remote secure_mkdirs failed",
            "read-only file system",
            "operation not permitted",
            "eacces",
            "errno 13",
        )
        return any(marker in lowered for marker in permission_markers)

    @staticmethod
    def _root_fallback_destination(game_name):
        folder = str(game_name or "GameData").strip()
        for character in ('\\', '/', ':', '*', '?', '"', '<', '>', '|'):
            folder = folder.replace(character, "_")
        folder = folder.replace(" ", "_").strip("._")
        if not folder:
            folder = "GameData"
        # Isolate fallback data in its own folder at the storage root.
        return f"/sdcard/{folder}/"

    def _finished_for_device(self, serial, success, message):
        print(
            "FINISHED:",
            serial,
            success,
            message
        )

        operation = self._active_operations.get(serial)
        if operation is None or operation.get("completed"):
            return

        preinstall_stage = (
            operation.get("kind") == "copy"
            and operation.get("preinstall_mt_manager", False)
            and not operation.get("mt_manager_preinstall_done", False)
        )
        preinstall_stage_failed = False

        if preinstall_stage and success:
            engine = operation.get("engine")
            if engine is None:
                success = False
                message = "تم فحص MT Manager لكن محرك النقل غير جاهز؛ لم يبدأ النسخ."
            else:
                operation["mt_manager_preinstall_done"] = True
                operation["raw_error"] = ""
                operation["error"] = ""
                operation["status"] = "جاري النسخ"
                operation["percent"] = 0
                operation["operation"] = "تم تجهيز MT Manager؛ جاري نسخ بيانات اللعبة"
                operation["speed"] = "0 B/s"
                operation["eta"] = "--"
                self._update_operation(
                    serial,
                    percent=0,
                    status=operation["status"],
                    operation_text=operation["operation"],
                    speed=operation["speed"],
                    eta=operation["eta"],
                    error=""
                )
                engine.push(
                    serial,
                    operation["source"],
                    operation["destination"]
                )
                return

        if preinstall_stage and not success:
            preinstall_stage_failed = True
            operation["raw_error"] = str(message or "")
            message = (
                "تعذر تثبيت MT Manager قبل النسخ؛ لم يبدأ نسخ اللعبة. "
                + str(message or "")
            )

        request_root_fallback = (
            not success
            and not operation.get("cancelled", False)
            and not preinstall_stage_failed
            and operation.get("kind") == "copy"
            and operation.get("mt_manager_preinstall_done", False)
            and not operation.get("root_fallback_attempted", False)
            and self._is_android_data_permission_denial(
                operation.get("destination", ""),
                message
            )
        )
        fallback_destination = (
            self._root_fallback_destination(operation.get("game", ""))
            if request_root_fallback
            else ""
        )

        if not success and operation.get("kind") == "copy":
            if not preinstall_stage_failed:
                operation["raw_error"] = str(message or "")
                message = self._device_copy_failure_summary(serial, operation, message)
            operation["awaiting_root_fallback"] = request_root_fallback

        operation["completed"] = True
        operation["status"] = (
            "ملغي"
            if operation.get("cancelled")
            else "اكتمل"
            if success
            else "فشل"
        )
        operation["operation"] = (
            "تم إلغاء العملية"
            if operation.get("cancelled")
            else "اكتمل التثبيت"
            if operation["kind"] == "install" and success
            else "فشل التثبيت"
            if operation["kind"] == "install"
            else "اكتمل النسخ"
            if success
            else "بانتظار اختيار وجهة بديلة"
            if request_root_fallback
            else "فشل النسخ"
        )
        operation["percent"] = 100 if success and operation["kind"] == "copy" else operation["percent"]
        operation["error"] = "" if success else message
        operation["result"] = {
            "serial": serial,
            "success": success and not operation.get("cancelled"),
            "message": message
        }
        self._emit_operation_state()
        self.operationFinished.emit(
            f"{serial}: {'SUCCESS' if success else 'FAILED'}"
        )
        self.transferFinished.emit(
            operation["result"]["success"],
            operation["result"]["message"]
        )
        self.messageChanged.emit(message)
        if operation.get("engine") is not None:
            operation["engine"] = None

        if request_root_fallback:
            reason = (
                str(message)
                + "\n\nرسالة ADB الأصلية:\n"
                + str(operation.get("raw_error") or "")
            )
            self.androidDataFallbackRequested.emit(
                serial,
                str(operation.get("game", "")),
                fallback_destination,
                reason
            )

    @Slot(str, result=bool)
    def copyToDeviceRoot(self, serial):
        operation = self._active_operations.get(serial)
        if operation is None or not operation.get("awaiting_root_fallback", False):
            self.messageChanged.emit("لا يوجد طلب نسخ بديل معلّق لهذا الهاتف.")
            return False

        if not operation.get("mt_manager_preinstall_done", False):
            self.messageChanged.emit(
                "لم يتم تجهيز MT Manager بنجاح؛ أُلغي النسخ البديل."
            )
            return False

        original_destination = operation.get(
            "original_destination",
            operation.get("destination", "")
        )
        destination = self._root_fallback_destination(operation.get("game", ""))
        operation.update({
            "original_destination": original_destination,
            "destination": destination,
            "root_fallback_attempted": True,
            "awaiting_root_fallback": False,
            "completed": False,
            "status": "جاري النسخ إلى الجذر",
            "percent": 0,
            "operation": "نسخ إلى مجلد مستقل في جذر الذاكرة",
            "speed": "0 B/s",
            "eta": "--",
            "error": "",
            "raw_error": ""
        })
        operation.pop("result", None)
        self.messageChanged.emit(
            f"إعادة نسخ {operation.get('game', 'البيانات')} إلى {destination}"
        )
        self._start_operation(operation)
        return True

    @Slot(str, result=bool)
    def declineRootFallback(self, serial):
        operation = self._active_operations.get(serial)
        if operation is None or not operation.get("awaiting_root_fallback", False):
            return False

        operation["awaiting_root_fallback"] = False
        operation["completed"] = True
        operation["status"] = "فشل"
        operation["operation"] = "تم إلغاء النسخ إلى الجذر"
        self._emit_operation_state()
        self.messageChanged.emit("تم إلغاء النسخ إلى الجذر؛ لم يُجرَ نقل بديل.")
        return True

    @Slot(result=list)
    def getADBDevices(self):
        # Synchronous compatibility entry point for non-UI callers/tests.
        return self._apply_adb_devices(self.adb_engine.get_devices())

    @Slot()
    def refreshADBDevices(self):
        # ADB commands can stall on disconnected devices; never run discovery
        # directly on the Qt UI thread.
        with self._adb_discovery_lock:
            if (
                self._adb_discovery_thread is not None
                and self._adb_discovery_thread.is_alive()
            ):
                return

            self._adb_discovery_thread = threading.Thread(
                target=self._discover_adb_devices,
                name="KafiaNet-ADB-Discovery",
                daemon=True
            )
            worker = self._adb_discovery_thread

        worker.start()

    def _discover_adb_devices(self):
        try:
            devices = self.adb_engine.get_devices()
        except Exception as exc:
            print("ADB DISCOVERY FAILED:", exc)
            devices = []
        self.adbDiscoveryCompleted.emit(devices)

    @Slot(list)
    def _apply_adb_devices(self, devices):
        devices = list(devices or [])
        print("ADB DEVICES:", devices)

        available_serials = {
            d.get("serial", "")
            for d in devices
        }
        self.selected_devices = [
            serial
            for serial in self.selected_devices
            if serial in available_serials
        ]
        self._device_info = {
            d.get("serial", ""): d
            for d in devices
        }
        if self.selected_device not in available_serials:
            self.selected_device = (
                self.selected_devices[0]
                if self.selected_devices
                else ""
            )

        qml_devices = []
        for d in devices:
            qml_devices.append(
                {
                    "serial": d.get("serial", ""),
                    "model": d.get("model", d.get("name", "Android")),
                    "name": d.get("name", d.get("serial", "Android"))
                }
            )

        self.adbDevicesChanged.emit(qml_devices)
        return devices


    @Slot(str)
    def selectADBDevice(self, device):

        self.selected_device = device
        self.selected_devices = [device] if device else []

        print(
            "ADB DEVICE SELECTED:",
            device
        )

        self.messageChanged.emit(
            f"تم تحديد الجهاز: {device}"
        )

    @Slot(list)
    def setADBDeviceSelection(self, devices):
        self.selected_devices = [
            device
            for device in devices
            if isinstance(device, str) and device
        ]
        self.selected_device = (
            self.selected_devices[0]
            if self.selected_devices
            else ""
        )
        print(
            "ADB DEVICES SELECTED:",
            self.selected_devices
        )

    @Slot(str)
    def copyGame(self, game_name):

        print()
        print("==============================")
        print("ADB COPY REQUEST:", game_name)
        print("==============================")

        # ==========================================
        # EXPLICITLY SELECTED ADB DEVICES
        # ==========================================

        target_devices = list(self.selected_devices)

        if not target_devices and self.selected_device:
            target_devices = [self.selected_device]

        if not target_devices:

            self._reject_operation(
                "يرجى تحديد هاتف واحد على الأقل قبل بدء النسخ."
            )
            return

        # ==========================================
        # CHECK SOURCE
        # ==========================================

        if not self.source_root.is_dir():

            print(
                "SOURCE NOT FOUND:",
                self.source_root
            )

            self.messageChanged.emit(
                "مجلد مصدر اللعبة غير موجود"
            )

            return

        # ==========================================
        # FIND GAME
        # ==========================================

        source = find_game_folder(
            self.source_root,
            game_name
        )

        if source is None:

            print(
                "GAME NOT FOUND:",
                game_name
            )

            self.messageChanged.emit(
                f"لم يتم العثور على اللعبة: {game_name}"
            )

            return

        game = get_game(game_name)

        if not game:

            print(
                "GAME CONFIG NOT FOUND:",
                game_name
            )

            self.messageChanged.emit(
                "إعدادات اللعبة غير موجودة"
            )

            return

        # ==========================================
        # ADB SOURCE / DESTINATION
        # ==========================================

        if game_name == "Free Fire":

            source = source / "com.dts.freefireth"

            print("FREE FIRE DATA SOURCE:", source)

            if not source.exists() or not source.is_dir():
                print("FREE FIRE DATA NOT FOUND:", source)
                self.messageChanged.emit(
                    "مجلد Free Fire com.dts.freefireth غير موجود"
                )
                return

            adb_destination = (
                "/sdcard/Android/data/com.dts.freefireth/"
            )

        elif game_name == "PUBG Mobile":

            # PUBG source on SERVER06 contains the game
            # folder, while the actual transferable data
            # is inside the "saved" directory.
            source = source / "saved"

            adb_destination = (
                "/sdcard/Android/data/com.tencent.ig/"
                "files/UE4Game/ShadowTrackerExtra/"
                "ShadowTrackerExtra/Saved/"
            )

            print("PUBG SAVED SOURCE:", source)

            if not source.exists() or not source.is_dir():

                print(
                    "PUBG SAVED SOURCE NOT FOUND:",
                    source
                )

                self.messageChanged.emit(
                    "مجلد PUBG saved غير موجود"
                )

                return

        elif game_name == "Call of Duty Mobile":

            # COD data is stored inside the package-named directory.
            source = source / "com.activision.callofduty.shooter"

            adb_destination = (
                "/sdcard/Android/data/com.activision.callofduty.shooter/"
            )

            print("COD PACKAGE SOURCE:", source)

            if not source.exists() or not source.is_dir():

                print(
                    "COD PACKAGE SOURCE NOT FOUND:",
                    source
                )

                self.messageChanged.emit(
                    "مجلد COD package غير موجود"
                )

                return

        else:

            adb_destination = ADB_GAME_DESTINATIONS.get(
                game_name
            )

            if not adb_destination:

                print(
                    "ADB DESTINATION NOT CONFIGURED:",
                    game_name
                )

                self.messageChanged.emit(
                    "وجهة ADB غير مهيأة لهذه اللعبة"
                )

                return

        # ==========================================
        # DEBUG
        # ==========================================

        print("SOURCE:", source)
        print("SOURCE EXISTS:", source.exists())
        print("SOURCE IS DIR:", source.is_dir())
        print("ADB DEVICES:", target_devices)
        print("ADB DESTINATION:", adb_destination)

        if source.is_dir():

            try:
                files = [
                    p
                    for p in source.rglob("*")
                    if p.is_file()
                ]

                print(
                    "SOURCE FILE COUNT:",
                    len(files)
                )

            except Exception as e:

                print(
                    "SOURCE SCAN ERROR:",
                    e
                )

        self.currentGame = game_name

        self.messageChanged.emit(
            f"جاري تجهيز {game_name} للنسخ..."
        )

        # ==========================================
        # START ADB TRANSFER
        # ==========================================

        # Pass the source root unchanged. ADBEngine either transfers this
        # directory to the exact remote parent (when names match) or passes
        # direct children to the target root, avoiding nested Saved/saved.
        push_source = str(source)

        started = 0
        for serial in target_devices:
            existing = self._active_operations.get(serial)
            if existing and not existing.get("completed", False):
                self.messageChanged.emit(
                    f"الهاتف المحدد لديه عملية نقل قيد التنفيذ: {serial}"
                )
                continue

            self._start_operation(
                {
                    "serial": serial,
                    "model": self._device_info.get(
                        serial,
                        {}
                    ).get("name", serial),
                    "game": game_name,
                    "kind": "copy",
                    "source": push_source,
                    "destination": adb_destination,
                    "status": "جاري التجهيز",
                    "percent": 0,
                    "operation": "جاري بدء العملية",
                    "speed": "--",
                    "eta": "--",
                    "error": "",
                    "completed": False,
                    "cancelled": False,
                    "preinstall_mt_manager": "/android/data/" in adb_destination.lower(),
                    "mt_manager_preinstall_done": False,
                    "mt_manager_apk": str(build_mt_manager_apk_path()),
                    "mt_manager_package": ADB_PACKAGE_IDS["MT Manager"],
                    "root_fallback_attempted": False,
                    "awaiting_root_fallback": False,
                    "original_destination": adb_destination
                }
            )
            started += 1

        if not started:
            self._reject_operation(
                "كل الهواتف المحددة مشغولة بعمليات نقل حالية."
            )

    @Slot(str)
    def startGameTransfer(self, game_name):
        self.copyGame(game_name)

    @Slot(str)
    def launchGame(self, game_name):
        print()
        print("==============================")
        print("ADB LAUNCH REQUEST:", game_name)
        print("==============================")

        target_devices = list(self.selected_devices)
        if not target_devices and self.selected_device:
            target_devices = [self.selected_device]

        if not target_devices:
            self._reject_operation(
                "يرجى تحديد هاتف واحد على الأقل قبل تشغيل اللعبة."
            )
            return

        # Launching supports one explicitly selected target. For multi-select,
        # use the first selected serial consistently with selected_device.
        self.selected_device = target_devices[0]

        package_id = ADB_PACKAGE_IDS.get(
            game_name
        )

        if not package_id:
            self.messageChanged.emit(
                f"لا يوجد Package ID للعبة {game_name}"
            )
            return

        print(
            "DEVICE:",
            self.selected_device
        )

        print(
            "PACKAGE:",
            package_id
        )

        try:

            result = self.adb_engine._run(
                [
                    "-s",
                    self.selected_device,
                    "shell",
                    "monkey",
                    "-p",
                    package_id,
                    "1"
                ],
                timeout=30
            )

            output = (
                result.stdout
                + "\n"
                + result.stderr
            ).strip()

            print(
                "ADB LAUNCH:",
                output
            )

            if result.returncode == 0:

                self.messageChanged.emit(
                    f"تم فتح {game_name}"
                )

            else:

                self.messageChanged.emit(
                    f"فشل فتح {game_name}: "
                    + (
                        output
                        or "تأكد من تثبيت اللعبة"
                    )
                )

        except Exception as e:

            print(
                "ADB LAUNCH ERROR:",
                e
            )

            self.messageChanged.emit(
                f"خطأ في فتح اللعبة: {e}"
            )

    @Slot(str)
    def installGame(self, game_name):

        print()
        print("==============================")
        print("ADB INSTALL REQUEST:", game_name)
        print("==============================")

        target_devices = list(self.selected_devices)
        if not target_devices:
            self._reject_operation(
                "يرجى تحديد هاتف واحد على الأقل قبل بدء التثبيت."
            )
            return

        if not self.source_root.exists():

            print(
                "SOURCE NOT FOUND:",
                self.source_root
            )

            self.messageChanged.emit(
                "المصدر غير موجود"
            )

            return

        source = find_game_folder(
            self.source_root,
            game_name
        )

        if source is None:

            print(
                "GAME FOLDER NOT FOUND:",
                game_name
            )

            self.messageChanged.emit(
                f"لم يتم العثور على مجلد اللعبة: {game_name}"
            )

            return

        # ==========================================
        # FIND APK INSIDE GAME FOLDER ONLY
        # ==========================================

        # Never search source.parent.
        # This prevents installing unrelated APK files
        # such as MT Manager from another folder.

        apk_files = [
            p
            for p in source.rglob("*")
            if p.is_file() and p.suffix.lower() in [".apk", ".apks", ".apk+"]
        ]

        if not apk_files:

            print(
                "GAME APK NOT FOUND:",
                game_name
            )

            self.messageChanged.emit(
                f"لم يتم العثور على APK الخاص بـ {game_name}"
            )

            return

        if len(apk_files) > 1:

            print(
                "MULTIPLE GAME APK FILES:",
                game_name
            )

            for candidate in apk_files:
                print(
                    "APK CANDIDATE:",
                    candidate
                )

        # Prefer a real APK. If only an APKS bundle exists,
        # let ADBEngine install all split APKs together.

        normal_apks = [
            p for p in apk_files
            if p.suffix.lower() == ".apk"
        ]

        apks_bundles = [
            p for p in apk_files
            if p.suffix.lower() == ".apks"
        ]

        if normal_apks:
            apk = normal_apks[0]
            install_type = "apk"
        elif apks_bundles:
            apk = apks_bundles[0]
            install_type = "apks"
        else:
            self.messageChanged.emit(
                f"لم يتم العثور على APK صالح لـ {game_name}"
            )
            return

        print(
            "GAME APK SELECTED:",
            apk
        )

        print("DEVICES:", target_devices)
        print("APK:", apk)
        print("INSTALL TYPE:", install_type)

        self.currentGame = game_name

        self.messageChanged.emit(
            f"جاري تثبيت {game_name} على {len(target_devices)} جهاز..."
        )

        started = 0
        for serial in target_devices:
            existing = self._active_operations.get(serial)
            if existing and not existing.get("completed", False):
                self.messageChanged.emit(
                    f"الهاتف المحدد لديه عملية نقل قيد التنفيذ: {serial}"
                )
                continue

            self._start_operation(
                {
                    "serial": serial,
                    "model": self._device_info.get(
                        serial,
                        {}
                    ).get("name", serial),
                    "game": game_name,
                    "kind": "install",
                    "apk": str(apk),
                    "install_type": install_type,
                    "status": "جاري التجهيز",
                    "percent": -1,
                    "operation": "جاري بدء العملية",
                    "speed": "--",
                    "eta": "--",
                    "error": "",
                    "completed": False,
                    "cancelled": False
                }
            )
            started += 1

        if not started:
            self._reject_operation(
                "كل الهواتف المحددة مشغولة بعمليات تثبيت حالية."
            )

    @Slot()
    def pauseTransfer(self):
        paused_any = False

        for serial, operation in list(self._active_operations.items()):
            if operation.get("completed", False):
                continue

            engine = operation.get("engine")
            if engine is None:
                continue

            try:
                paused_any = bool(engine.pause()) or paused_any
            except Exception as e:
                print("PAUSE ERROR:", serial, e)

        if paused_any != self._transfer_paused:
            self._transfer_paused = paused_any
            self.transferPausedChanged.emit(paused_any)

        if not paused_any:
            self.messageChanged.emit(
                "لا توجد عملية نقل نشطة يمكن إيقافها مؤقتًا الآن."
            )

    @Slot()
    def resumeTransfer(self):
        resumed_any = False

        for serial, operation in list(self._active_operations.items()):
            if operation.get("completed", False):
                continue

            engine = operation.get("engine")
            if engine is None:
                continue

            try:
                resumed_any = bool(engine.resume()) or resumed_any
            except Exception as e:
                print("RESUME ERROR:", serial, e)

        if resumed_any and self._transfer_paused:
            self._transfer_paused = False
            self.transferPausedChanged.emit(False)

        if not resumed_any:
            self.messageChanged.emit(
                "لا توجد عملية نقل متوقفة مؤقتًا لاستئنافها."
            )

    @Slot()
    def cancelTransfer(self):
        if not self._operation_busy:
            return

        self.messageChanged.emit(
            "جاري إلغاء العمليات المحددة..."
        )
        for serial in list(self._active_operations):
            self.cancelDevice(serial)

    @Slot(str)
    def cancelDevice(self, serial):
        operation = self._active_operations.get(serial)
        if operation is None or operation.get("completed"):
            return

        operation["cancelled"] = True
        operation["status"] = "ملغي"
        operation["operation"] = "جاري إلغاء العملية"
        self._update_operation(serial)
        engine = operation.get("engine")
        if engine is not None:
            engine.cancel()


def main():
    print("STARTING KAFIA NET CONTROL PRO")

    app = QApplication(sys.argv)
    engine = QQmlApplicationEngine()

    try:
        import ui_resources_rc
        qml_entry = QUrl("qrc:/qml/main.qml")
        print("LOADING EMBEDDED QML:", qml_entry.toString())
    except ImportError:
        qml_entry = QUrl.fromLocalFile(str(BASE_DIR / "qml" / "main.qml"))
        print("LOADING SOURCE QML:", qml_entry.toString())

    controller = AppController()
    engine.rootContext().setContextProperty("appController", controller)
    engine.rootContext().setContextProperty("baseDirectory", str(BASE_DIR))
    engine.load(qml_entry)

    root_count = len(engine.rootObjects())
    print("ROOT OBJECTS:", root_count)
    if not root_count:
        print("QML FAILED TO LOAD")
        return 2

    print("QML LOADED SUCCESSFULLY")
    if "--protected-build-smoke-test" in sys.argv:
        root = engine.rootObjects()[0]
        required_objects = ("mainSidebar", "dashboardPage", "transferPanel")
        found_objects = {
            name: root.findChild(QObject, name)
            for name in required_objects
        }
        missing_objects = [
            name for name, obj in found_objects.items() if obj is None
        ]
        if missing_objects:
            print(
                "UI_SMOKE_TEST_FAILED: missing QML objects: "
                + ", ".join(missing_objects),
                file=sys.stderr,
            )
            return 3

        # Simulate the controller's real transfer-list signal. The panel is
        # hidden while idle, so this verifies the signal that reveals it during
        # a genuine copy/install operation.
        controller.transferBatchChanged.emit([
            {
                "serial": "CI-SMOKE-DEVICE",
                "model": "CI Smoke Device",
                "game": "PUBG Mobile",
                "kind": "copy",
                "status": "جاري النسخ",
                "percent": 25,
                "operation": "اختبار ظهور لوحة النقل",
                "speed": "1 MB/s",
                "eta": "00:01",
                "error": "",
                "cancelled": False,
                "raw_error": "",
            }
        ])
        for _ in range(3):
            app.processEvents()

        panel = found_objects["transferPanel"]
        if not bool(panel.property("visible")):
            print(
                "UI_SMOKE_TEST_FAILED: transfer panel did not become visible "
                "after the transfer-list signal.",
                file=sys.stderr,
            )
            return 4

        print("DASHBOARD_UI_SMOKE_TEST: PASS")
        print("TRANSFER_PANEL_SIGNAL_SMOKE_TEST: PASS")
        print("PROTECTED_BUILD_SMOKE_TEST: PASS")
        return 0

    print("STARTING QT EVENT LOOP")
    exit_code = app.exec()
    print("QT EVENT LOOP ENDED:", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
