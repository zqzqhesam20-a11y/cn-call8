import sys
import os
from pathlib import Path

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Fusion"

from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

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



class AppController(QObject):

    messageChanged = Signal(str)
    transferPercentChanged = Signal(int)
    transferSpeedChanged = Signal(str)
    transferEtaChanged = Signal(str)
    transferFinished = Signal(bool, str)
    operationStateChanged = Signal(str)
    operationRejected = Signal(str)
    transferBatchChanged = Signal(list)
    deviceProgressChanged = Signal(str, int, str, str, str, str, str)
    operationFinished = Signal(str)
    busyChanged = Signal(bool)
    usbChanged = Signal(str)
    destinationChanged = Signal(str)
    adbDevicesChanged = Signal(list)

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
        self._device_info = {}

        self.current_source = "WIRELESS"

    @Slot()
    def useWirelessSource(self):
        self.current_source = "WIRELESS"
        self.source_root = build_server_source_root()
        print("SOURCE SELECTED: WIRELESS", self.source_root)

    @Slot()
    def useUsbSource(self):
        self.current_source = "USB"
        self.source_root = Path(r"D:\games") / SERVER_GAMES_FOLDER
        print("SOURCE SELECTED: USB", self.source_root)


        print("CONTROLLER READY")
        print("SOURCE:", self.source_root)
        print("DEST:", self.destination_root)


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
        self._set_operation_state(
            "ACTIVE" if self._active_operations else "IDLE"
        )

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
            self._update_operation(
                s,
                status=message,
                operation_text=message
            )
        )
        engine.finished.connect(
            lambda success, message, s=serial:
            self._finished_for_device(
                s,
                success,
                message
            )
        )

        self._emit_operation_state()
        self._update_operation(
            serial,
            status="جاري التثبيت"
            if operation["kind"] == "install"
            else "جاري النسخ",
            operation_text="تثبيت التطبيق"
            if operation["kind"] == "install"
            else "نسخ بيانات اللعبة",
            speed="--" if operation["kind"] == "install" else "0 B/s",
            eta="--"
        )

        if operation["kind"] == "install":
            if operation["install_type"] == "apks":
                engine.install_apks(serial, operation["apk"])
            else:
                engine.install(serial, operation["apk"])
        else:
            engine.push(
                serial,
                operation["source"],
                operation["destination"]
            )

    def _finished(self, success, message):
        self.messageChanged.emit(message)

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

    @Slot(result=list)
    def getADBDevices(self):

        devices = self.adb_engine.get_devices()

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
            target_devices = []

        if not target_devices:

            self._reject_operation(
                "يرجى تحديد هاتف واحد على الأقل قبل بدء النسخ."
            )
            return

        # ==========================================
        # CHECK SOURCE
        # ==========================================

        if not self.source_root.exists():

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

        # Always push the CONTENTS of the selected source directory
        # into the configured Android destination, never the source
        # directory itself.
        push_source = (
            str(source) + "/."
            if source.is_dir()
            else str(source)
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
                    "cancelled": False
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
            devices = self.adb_engine.get_devices()

            if devices:
                self.selected_device = devices[0].get(
                    "serial",
                    ""
                )

        if not self.selected_device:
            self.messageChanged.emit(
                "لا يوجد جهاز أندرويد متصل"
            )
            return

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
        active = list(self._active_operations.items())

        if not active:
            return

        for serial, operation in active:
            if operation.get("completed", False):
                continue

            engine = operation.get("engine")
            if engine is None:
                continue

            try:
                engine.pause()
            except Exception as e:
                print("PAUSE ERROR:", serial, e)

    @Slot()
    def resumeTransfer(self):
        active = list(self._active_operations.items())

        if not active:
            return

        for serial, operation in active:
            if operation.get("completed", False):
                continue

            engine = operation.get("engine")
            if engine is None:
                continue

            try:
                engine.resume()
            except Exception as e:
                print("RESUME ERROR:", serial, e)

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


print("STARTING KAFIA NET CONTROL PRO")

app = QApplication(sys.argv)

engine = QQmlApplicationEngine()

controller = AppController()

engine.rootContext().setContextProperty(
    "appController",
    controller
)

engine.rootContext().setContextProperty(
    "baseDirectory",
    str(BASE_DIR)
)

qml_file = BASE_DIR / "qml" / "main.qml"

print("LOADING:", qml_file)

engine.load(
    str(qml_file)
)

print(
    "ROOT OBJECTS:",
    len(engine.rootObjects())
)

if not engine.rootObjects():

    print("QML FAILED TO LOAD")

    sys.exit(-1)

print("QML LOADED SUCCESSFULLY")
print("STARTING QT EVENT LOOP")

exit_code = app.exec()

print(
    "QT EVENT LOOP ENDED:",
    exit_code
)

sys.exit(exit_code)
