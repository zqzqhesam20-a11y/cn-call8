import sys
import os
from pathlib import Path

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Fusion"

from PySide6.QtCore import QObject, Signal, Slot, Property
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from engine.transfer_engine import TransferEngine
from engine.adb_engine import ADBEngine
from engine.path_manager import PathManager
from engine.game_config import get_game, find_game_folder


BASE_DIR = Path(__file__).resolve().parent


class AppController(QObject):

    messageChanged = Signal(str)
    transferPercentChanged = Signal(int)
    transferSpeedChanged = Signal(str)
    transferEtaChanged = Signal(str)
    transferFinished = Signal(bool, str)
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

        self.source_root = Path(r"\\SERVER06\c$\العابي")

        self.destination_root = Path(
            r"D:\games"
        )

        self._current_game = ""

        # ???? ADB ??????
        self.selected_device = ""

        print("CONTROLLER READY")
        print("SOURCE:", self.source_root)
        print("DEST:", self.destination_root)

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

    def _progress(self, percent, speed, eta):
        print(
            f"PROGRESS: {percent}% | {speed} | ETA {eta}"
        )

        self.transferPercentChanged.emit(percent)
        self.transferSpeedChanged.emit(speed)
        self.transferEtaChanged.emit(eta)

    def _status(self, message):
        print("STATUS:", message)
        self.messageChanged.emit(message)

    def _finished(self, success, message):
        print(
            "FINISHED:",
            success,
            message
        )

        self.transferFinished.emit(
            success,
            message
        )

        self.messageChanged.emit(
            message
        )

    @Slot(result=list)
    def getADBDevices(self):

        devices = self.adb_engine.get_devices()

        print("ADB DEVICES:", devices)

        self.adbDevicesChanged.emit(devices)

        return devices


    @Slot(str)
    def selectADBDevice(self, device):

        self.selected_device = device

        print(
            "ADB DEVICE SELECTED:",
            device
        )

        self.messageChanged.emit(
            f"?? ?????? ??????: {device}"
        )


    @Slot(str)
    def copyGame(self, game_name):

        print()
        print("==============================")
        print("COPY REQUEST:", game_name)
        print("==============================")

        if not self.source_root.exists():

            print("SOURCE NOT FOUND")

            self.messageChanged.emit(
                "ط§ظ„ظ…طµط¯ط± ط؛ظٹط± ظ…طھطµظ„"
            )

            return

        source = find_game_folder(
            self.source_root,
            game_name
        )

        if source is None:

            print("GAME NOT FOUND:", game_name)

            self.messageChanged.emit(
                f"ظ„ظ… ظٹطھظ… ط§ظ„ط¹ط«ظˆط± ط¹ظ„ظ‰ {game_name}"
            )

            return

        game = get_game(game_name)

        if not game:

            print("GAME CONFIG NOT FOUND")

            self.messageChanged.emit(
                "ط§ظ„ظ„ط¹ط¨ط© ط؛ظٹط± ظ…ظˆط¬ظˆط¯ط© ظپظٹ ط§ظ„ط¥ط¹ط¯ط§ط¯ط§طھ"
            )

            return

        destination = (
            self.destination_root
            / game["destination"]
        )

        destination.mkdir(
            parents=True,
            exist_ok=True
        )

        print("SOURCE:", source)
        print("DESTINATION:", destination)

        self.currentGame = game_name

        self.messageChanged.emit(
            f"ط¬ط§ط±ظٹ ظ†ط³ط® {game_name}..."
        )

        self.engine.start(
            str(source),
            str(destination)
        )

    @Slot(str)
    def startGameTransfer(self, game_name):
        self.copyGame(game_name)

    @Slot(str)
    def installGame(self, game_name):

        print(
            "INSTALL REQUEST:",
            game_name
        )

        self.messageChanged.emit(
            f"ط§ظ„طھط«ط¨ظٹطھ: {game_name}"
        )

    @Slot()
    def pauseTransfer(self):
        self.engine.pause()

    @Slot()
    def resumeTransfer(self):
        self.engine.resume()

    @Slot()
    def cancelTransfer(self):
        self.engine.cancel()


print("STARTING KAFIA NET CONTROL PRO")

app = QGuiApplication(sys.argv)

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

