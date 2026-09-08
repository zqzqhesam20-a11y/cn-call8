import os
import shutil
import threading
import time

from PySide6.QtCore import QObject, Signal, Slot


class TransferEngine(QObject):

    progressChanged = Signal(int, str, str)
    statusChanged = Signal(str)
    finished = Signal(bool, str)

    def __init__(self):
        super().__init__()

        self._pause_event = threading.Event()
        self._pause_event.set()

        self._cancel_event = threading.Event()

        self._thread = None

    def _folder_size(self, folder):
        total = 0

        for root, _, files in os.walk(folder):
            for name in files:
                path = os.path.join(root, name)

                try:
                    total += os.path.getsize(path)
                except OSError:
                    pass

        return total

    def _copy_file(self, source, destination, copied, total, start_time):

        os.makedirs(os.path.dirname(destination), exist_ok=True)

        chunk_size = 4 * 1024 * 1024

        with open(source, "rb") as src, open(destination, "wb") as dst:

            while True:

                if self._cancel_event.is_set():
                    return False, copied

                self._pause_event.wait()

                chunk = src.read(chunk_size)

                if not chunk:
                    break

                dst.write(chunk)

                copied += len(chunk)

                elapsed = max(time.time() - start_time, 0.001)

                speed = copied / elapsed

                remaining = 0

                if speed > 0:
                    remaining = max(
                        int((total - copied) / speed),
                        0
                    )

                percent = int(
                    (copied / total) * 100
                ) if total else 100

                speed_text = self._format_size(speed) + "/s"

                eta_text = self._format_time(
                    remaining
                )

                self.progressChanged.emit(
                    percent,
                    speed_text,
                    eta_text
                )

        return True, copied

    def _copy_folder(self, source, destination):

        files = []

        for root, _, filenames in os.walk(source):

            for filename in filenames:

                source_file = os.path.join(
                    root,
                    filename
                )

                relative = os.path.relpath(
                    source_file,
                    source
                )

                destination_file = os.path.join(
                    destination,
                    relative
                )

                files.append(
                    (source_file, destination_file)
                )

        total = 0

        for source_file, _ in files:

            try:
                total += os.path.getsize(source_file)
            except OSError:
                pass

        copied = 0

        start_time = time.time()

        for source_file, destination_file in files:

            ok, copied = self._copy_file(
                source_file,
                destination_file,
                copied,
                total,
                start_time
            )

            if not ok:
                return False

        return True

    def _run(self, source, destination):

        try:

            self.statusChanged.emit(
                "جاري النسخ..."
            )

            if os.path.isdir(source):

                success = self._copy_folder(
                    source,
                    destination
                )

            else:

                total = os.path.getsize(source)

                start_time = time.time()

                success, _ = self._copy_file(
                    source,
                    destination,
                    0,
                    total,
                    start_time
                )

            if self._cancel_event.is_set():

                self.statusChanged.emit(
                    "تم إلغاء النقل"
                )

                self.finished.emit(
                    False,
                    "تم إلغاء النقل"
                )

                return

            if success:

                self.progressChanged.emit(
                    100,
                    "0 B/s",
                    "00:00"
                )

                self.statusChanged.emit(
                    "اكتمل النقل"
                )

                self.finished.emit(
                    True,
                    "اكتمل النقل بنجاح"
                )

        except Exception as e:

            self.statusChanged.emit(
                "حدث خطأ"
            )

            self.finished.emit(
                False,
                str(e)
            )

    @Slot(str, str)
    def start(self, source, destination):

        if self._thread and self._thread.is_alive():
            return

        self._pause_event.set()

        self._cancel_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            args=(source, destination),
            daemon=True
        )

        self._thread.start()

    @Slot()
    def pause(self):

        self._pause_event.clear()

        self.statusChanged.emit(
            "متوقف مؤقتًا"
        )

    @Slot()
    def resume(self):

        self._pause_event.set()

        self.statusChanged.emit(
            "جاري النسخ..."
        )

    @Slot()
    def cancel(self):

        self._cancel_event.set()

        self._pause_event.set()

    @staticmethod
    def _format_size(size):

        units = [
            "B",
            "KB",
            "MB",
            "GB",
            "TB"
        ]

        size = float(size)

        for unit in units:

            if size < 1024:
                return f"{size:.1f} {unit}"

            size /= 1024

        return f"{size:.1f} PB"

    @staticmethod
    def _format_time(seconds):

        seconds = int(seconds)

        hours = seconds // 3600

        minutes = (seconds % 3600) // 60

        seconds = seconds % 60

        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        return f"{minutes:02d}:{seconds:02d}"
