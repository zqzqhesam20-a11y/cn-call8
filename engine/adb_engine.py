import os
import re
import subprocess
import threading
import time
import ctypes
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot


BASE_DIR = Path(__file__).resolve().parent.parent



# ============================================================
# INTERNAL ADB I/O PROGRESS MONITOR
# ============================================================

def monitor_adb_io(
    pid,
    callback,
    stop_event,
    interval=0.20
):

    try:
        import psutil
    except Exception:
        return

    try:
        process = psutil.Process(pid)
    except Exception:
        return

    try:
        previous_bytes = (
            process.io_counters().read_bytes
        )
    except Exception:
        return

    previous_time = time.monotonic()

    try:

        while not stop_event.is_set():

            try:
                if not process.is_running():
                    break
            except Exception:
                break

            time.sleep(interval)

            try:
                current_bytes = (
                    process.io_counters().read_bytes
                )
            except Exception:
                break

            now = time.monotonic()

            delta_bytes = max(
                current_bytes - previous_bytes,
                0
            )

            elapsed = max(
                now - previous_time,
                0.001
            )

            speed = (
                delta_bytes / elapsed
            )

            previous_bytes = current_bytes
            previous_time = now

            try:
                callback(
                    delta_bytes,
                    speed
                )
            except Exception:
                pass

    except Exception:
        pass


class ADBEngine(QObject):

    progressChanged = Signal(int, str, str)
    statusChanged = Signal(str)
    finished = Signal(bool, str)
    devicesChanged = Signal(list)
    logChanged = Signal(str)

    def __init__(self):
        super().__init__()

        self.adb = self._get_adb_path()

        self._pause_event = threading.Event()
        self._pause_event.set()

        self._cancel_event = threading.Event()

        self._thread = None
        self._current_process = None
        self._process_lock = threading.Lock()
        self._process_paused = False
        self._reconnect_retry_count = 0
        self._progress_offset_bytes = 0
        self._cancelled_by_user = False

    def _get_adb_path(self):
        # Prefer the ADB binary bundled with this application. This keeps
        # packaged builds independent of a machine-specific D:\games path.
        local_adb = BASE_DIR / "platform-tools" / "adb.exe"
        if local_adb.is_file():
            return str(local_adb)

        # Development fallback for the shared workstation installation.
        external_adb = Path(
            r"D:\games\programe files\platform-tools\adb.exe"
        )
        if external_adb.is_file():
            return str(external_adb)

        # Final fallback: allow adb.exe from PATH.
        return "adb"

    def _run(self, args, timeout=None):

        command = [
            self.adb,
            *args
        ]

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            startupinfo=startupinfo,
            creationflags=0x08000000,
            timeout=timeout
        )

    def _run_install_command(self, args, timeout):
        command = [
            self.adb,
            *args
        ]
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
            startupinfo=startupinfo,
            creationflags=0x08000000
        )
        with self._process_lock:
            self._current_process = process
            cancelled = self._cancel_event.is_set()

        if cancelled:
            process.terminate()

        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.terminate()
            stdout, stderr = process.communicate()
            process.returncode = process.returncode or 1
        finally:
            with self._process_lock:
                if self._current_process is process:
                    self._current_process = None

        return subprocess.CompletedProcess(
            command,
            process.returncode,
            stdout,
            stderr
        )

    @Slot(result=list)
    def get_devices(self):
        try:
            result = self._run(["devices"], timeout=10)
        except Exception as exc:
            print("ADB DEVICE LIST FAILED:", exc)
            self.devicesChanged.emit([])
            return []

        devices = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue

            parts = line.split()
            if len(parts) < 2 or parts[1] != "device":
                continue

            serial = parts[0]

            def read_device_property(args):
                try:
                    property_result = self._run(args, timeout=3)
                    return property_result.stdout.strip()
                except Exception as exc:
                    print("ADB DEVICE PROPERTY WARNING:", serial, exc)
                    return ""

            model = read_device_property([
                "-s", serial, "shell", "getprop", "ro.product.model"
            ]) or "Android"
            manufacturer = read_device_property([
                "-s", serial, "shell", "getprop", "ro.product.manufacturer"
            ]) or "Android"
            device_name = read_device_property([
                "-s", serial, "shell", "settings", "get", "global", "device_name"
            ])

            if not device_name or device_name.lower() in {"null", "unknown"}:
                device_name = f"{manufacturer} {model}".strip()

            devices.append({
                "serial": serial,
                "model": model,
                "manufacturer": manufacturer,
                "name": device_name
            })

        self.devicesChanged.emit(devices)
        return devices

    def _format_size(self, size):

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

    def _format_time(self, seconds):

        seconds = max(int(seconds), 0)

        hours = seconds // 3600

        minutes = (seconds % 3600) // 60

        seconds = seconds % 60

        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        return f"{minutes:02d}:{seconds:02d}"

    def _get_remote_size(self, device, remote_path):

        try:

            result = self._run(
                [
                    '-s',
                    device,
                    'shell',
                    'stat',
                    '-c',
                    '%s',
                    remote_path
                ],
                timeout=5
            )

            value = result.stdout.strip()

            if value.isdigit():
                return int(value)

        except Exception:
            pass

        return 0

    def _emit_adb_live_progress(
        self,
        line,
        completed_bytes,
        current_file_size,
        source_total_bytes,
        start_time
    ):
        match = re.search(
            r'(\d+)%\s+(\d+(?:\.\d+)?)([KMGTP]?B)/s',
            line
        )

        if not match:
            return

        percent_in_file = int(match.group(1))

        speed_value = float(match.group(2))

        speed_unit = match.group(3)

        multipliers = {
            "B": 1,
            "KB": 1024,
            "MB": 1024 ** 2,
            "GB": 1024 ** 3,
            "TB": 1024 ** 4
        }

        speed = speed_value * multipliers.get(
            speed_unit,
            1
        )

        current_bytes = (
            completed_bytes
            + (
                current_file_size
                * percent_in_file
                / 100.0
            )
        )

        percent = (
            int(current_bytes * 100 / source_total_bytes)
            if source_total_bytes > 0
            else percent_in_file
        )

        if speed > 0 and source_total_bytes > 0:
            remaining_bytes = max(
                source_total_bytes - current_bytes,
                0
            )
            remaining_seconds = int(
                remaining_bytes / speed
            )
            eta = self._format_time(remaining_seconds)
        else:
            eta = "00:00"

        self.progressChanged.emit(
            max(0, min(percent, 100)),
            self._format_size(speed) + "/s",
            eta
        )

    @staticmethod
    def _parse_adb_progress_details(line):
        """Parse ADB's overall progress line and current local-file progress."""
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(line or "")).strip()
        overall = re.search(r"^\[\s*(\d{1,3})%\s*\]\s*(.*)$", text)
        if overall:
            percent = max(0, min(int(overall.group(1)), 100))
            remainder = overall.group(2).strip()
            file_match = re.match(r"^(.*):\s*(\d{1,3})%\s*$", remainder)
            if file_match:
                file_path = file_match.group(1).strip().strip('"')
                file_percent = max(0, min(int(file_match.group(2)), 100))
                return percent, file_path, file_percent
            file_path = remainder.strip('"')
            return percent, (file_path or None), (percent if file_path else None)

        # Compatibility with platform-tools that emit a per-file percent/rate.
        legacy = re.search(
            r"(?<!\d)(\d{1,3})%\s+(\d+(?:\.\d+)?)([KMGTP]?B)/s",
            text,
            re.IGNORECASE
        )
        if legacy:
            return max(0, min(int(legacy.group(1)), 100)), None, None
        return None, None, None

    @staticmethod
    def _parse_adb_transfer_speed(line):
        """Return measured ADB throughput in bytes/second, when present."""
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(line or ""))
        transfer = re.search(
            r"\(\s*(\d+)\s+bytes\s+in\s+(\d+(?:\.\d+)?)s\s*\)",
            text,
            re.IGNORECASE
        )
        if transfer:
            seconds = float(transfer.group(2))
            if seconds > 0:
                return float(transfer.group(1)) / seconds

        rate = re.search(
            r"(\d+(?:\.\d+)?)\s*(KB|MB|GB|TB|B)/s\b",
            text,
            re.IGNORECASE
        )
        if not rate:
            return None
        multipliers = {
            "B": 1,
            "KB": 1024,
            "MB": 1024 ** 2,
            "GB": 1024 ** 3,
            "TB": 1024 ** 4,
        }
        return float(rate.group(1)) * multipliers[rate.group(2).upper()]

    def _parse_progress(self, line):

        match = re.search(
            r'(\d+)%\s+(\d+(?:\.\d+)?)([KMGTP]?B)/s',
            line
        )

        if not match:
            return

        percent = int(match.group(1))

        speed_value = float(match.group(2))

        speed_unit = match.group(3)

        multipliers = {
            "B": 1,
            "KB": 1024,
            "MB": 1024 ** 2,
            "GB": 1024 ** 3,
            "TB": 1024 ** 4
        }

        speed = speed_value * multipliers.get(
            speed_unit,
            1
        )

        self.progressChanged.emit(
            percent,
            self._format_size(speed) + "/s",
            "00:00"
        )

    def _device_is_connected(self, device):
        """Return whether ADB currently sees this serial as an online device."""
        try:
            result = self._run(["-s", device, "get-state"], timeout=5)
            return (
                result.returncode == 0
                and result.stdout.strip().lower() == "device"
            )
        except Exception as exc:
            print("ADB DEVICE STATE CHECK FAILED:", device, exc)
            return False

    def _wait_for_device_reconnect(self, device):
        self.statusChanged.emit(
            "انقطع اتصال الهاتف. الرجاء إعادة توصيله لاستمرار النسخ..."
        )

        print(
            "ADB DEVICE DISCONNECTED; WAITING:",
            device
        )

        while not self._cancel_event.is_set():
            try:
                result = subprocess.run(
                    [
                        self.adb,
                        "-s",
                        device,
                        "get-state",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

                if (
                    result.returncode == 0
                    and result.stdout.strip().lower() == "device"
                ):
                    self.statusChanged.emit(
                        "تمت إعادة توصيل الهاتف — استكمال النسخ..."
                    )

                    print(
                        "ADB DEVICE RECONNECTED:",
                        device
                    )

                    return True

            except Exception as e:
                print(
                    "ADB RECONNECT CHECK ERROR:",
                    e
                )

            time.sleep(2.0)

        return False

    def _remote_file_exists(self, device, remote_file):
        try:
            result = subprocess.run(
                [
                    self.adb,
                    "-s",
                    device,
                    "shell",
                    "test",
                    "-f",
                    remote_file,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            return result.returncode == 0

        except Exception as e:
            print(
                "ADB REMOTE FILE CHECK ERROR:",
                e
            )
            return None

    @staticmethod
    def _adb_source_plan(source_path, destination):
        """Choose source args/ADB target without nesting a source root.

        When the local directory basename matches the remote directory name,
        pass the directory itself to its remote parent. This keeps very large
        folders to one source argument, including Windows case-only aliases
        such as local "saved" and remote "Saved". Otherwise pass each direct
        child into the exact destination root.
        """
        remote_destination = destination.rstrip("/")
        remote_leaf = remote_destination.rsplit("/", 1)[-1]
        remote_parent = remote_destination.rsplit("/", 1)[0] or "/"

        if (
            source_path.is_dir()
            and source_path.name.casefold() == remote_leaf.casefold()
        ):
            source_alias = source_path.with_name(remote_leaf)
            if source_alias.exists():
                return [str(source_alias)], remote_parent

        if source_path.is_dir():
            return (
                [
                    str(path)
                    for path in sorted(
                        source_path.iterdir(),
                        key=lambda item: item.name.casefold()
                    )
                ],
                remote_destination
            )
        return [str(source_path)], remote_destination

    @staticmethod
    def _combined_progress_percent(total_bytes, offset_bytes, attempt_bytes):
        """Return monotonic overall progress across reconnect retries."""
        if total_bytes <= 0:
            return 0
        transferred = min(max(offset_bytes + attempt_bytes, 0), total_bytes)
        return max(0, min(int(transferred * 100 / total_bytes), 99))

    def _push_thread(
        self,
        device,
        source,
        destination
    ):

        process = None
        requested_source = str(source)
        requested_destination = destination

        try:

            self.statusChanged.emit(
                "جاري نسخ الملفات..."
            )

            source_path = Path(source)

            if not source_path.exists():

                self.finished.emit(
                    False,
                    "المصدر غير موجود"
                )

                return

            # The destination is the exact root for the source contents.
            # Explicit child source arguments avoid ADB appending the source
            # directory name under an already-created destination.
            destination = destination.rstrip("/")

            # --------------------------------------------------------
            # --------------------------------------------------------
            # PRE-FLIGHT DESTINATION WRITE CHECK
            # Direct ADB shell commands only.
            # --------------------------------------------------------
            check_path = destination.rstrip('/') or destination
            check_file = (
                check_path.rstrip('/')
                + f'/.cncall_write_test_{os.getpid()}_'
                f'{threading.get_ident()}_{time.time_ns()}'
            )

            print(
                "ADB DESTINATION WRITE CHECK:",
                check_path
            )

            mkdir_result = subprocess.run(
                [
                    self.adb,
                    "-s",
                    device,
                    "shell",
                    "mkdir",
                    "-p",
                    check_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10,
            )

            if mkdir_result.returncode != 0:
                check_error = (
                    mkdir_result.stderr.strip()
                    or mkdir_result.stdout.strip()
                    or "mkdir failed"
                )

                print(
                    "ADB DESTINATION MKDIR CHECK FAILED:",
                    check_error
                )

                self.statusChanged.emit(
                    "تعذر تجهيز مجلد الوجهة"
                )

                self.finished.emit(
                    False,
                    "فشل تجهيز وجهة النسخ عبر ADB: "
                    + check_error
                )

                return

            write_result = subprocess.run(
                [
                    self.adb,
                    "-s",
                    device,
                    "shell",
                    "touch",
                    check_file,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10,
            )

            if write_result.returncode != 0:
                check_error = (
                    write_result.stderr.strip()
                    or write_result.stdout.strip()
                    or "write test failed"
                )

                print(
                    "ADB DESTINATION WRITE CHECK FAILED:",
                    check_error
                )

                self.statusChanged.emit(
                    "تعذر الكتابة إلى مجلد الوجهة"
                )

                self.finished.emit(
                    False,
                    "فشل الوصول إلى وجهة النسخ عبر ADB: "
                    + check_error
                )

                return

            cleanup_result = subprocess.run(
                [
                    self.adb,
                    "-s",
                    device,
                    "shell",
                    "rm",
                    "-f",
                    check_file,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10,
            )

            if cleanup_result.returncode != 0:
                print(
                    "ADB PREFLIGHT CLEANUP WARNING:",
                    cleanup_result.stderr.strip()
                )

            total_bytes = (
                sum(
                    p.stat().st_size
                    for p in source_path.rglob("*")
                    if p.is_file()
                )
                if source_path.is_dir()
                else source_path.stat().st_size
            )

            progress_offset_bytes = min(
                self._progress_offset_bytes,
                total_bytes
            )

            if source_path.is_dir() and next(source_path.iterdir(), None) is None:
                self.progressChanged.emit(100, "0 B/s", "00:00")
                self.statusChanged.emit("اكتمل النسخ")
                self.finished.emit(True, "المصدر فارغ؛ تم تجهيز مجلد الوجهة")
                return

            adb_sources, adb_destination = self._adb_source_plan(
                source_path,
                destination
            )
            if not adb_sources:
                self.progressChanged.emit(100, "0 B/s", "00:00")
                self.statusChanged.emit("اكتمل النسخ")
                self.finished.emit(True, "المصدر فارغ؛ تم تجهيز مجلد الوجهة")
                return
            print("ADB SOURCE ARGUMENT COUNT:", len(adb_sources))
            print("ADB DESTINATION ARGUMENT:", adb_destination)

            print()
            print("========================================")
            print("ADB FAST TRANSFER ENGINE")
            print("========================================")
            print("SOURCE:", source_path)
            print("DESTINATION:", destination)
            print("TOTAL SIZE:", self._format_size(total_bytes))
            print("========================================")

            self._pause_event.set()

            command = [
                self.adb,
                "-s",
                device,
                "push",
                "--sync",
                *adb_sources,
                adb_destination
            ]

            print(
                "ADB FAST PUSH:",
                " ".join(command)
            )

            print(
                "STARTING DIRECT ADB TRANSFER"
            )

            # --------------------------------------------------------
            # DIRECT ADB PROCESS
            # No CMD wrapper.
            # process.pid is the real adb.exe PID.
            # --------------------------------------------------------

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= (
                subprocess.STARTF_USESHOWWINDOW
            )
            startupinfo.wShowWindow = (
                subprocess.SW_HIDE
            )

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                )
            )

            # ADB writes its live transfer progress to stdout when stdout is
            # redirected (the normal case for this hidden GUI). Keep both streams
            # captured and parsed, so neither LAN nor local HDD loses progress.
            stdout_chunks = []
            stderr_chunks = []
            progress_stop = threading.Event()
            progress_lock = threading.Lock()
            start_time = time.monotonic()
            progress_state = {
                "bytes": 0,
                "speed": 0.0,
                "last_percent": -1,
                "speed_samples": [],
                "native_seen": False,
                "native_percent": 0,
                "native_bytes": 0,
                "native_speed_seen": False,
                "current_file_path": "",
                "current_file_percent": 0,
                "current_file_time": start_time,
                "file_size_cache": {},
            }

            def progress_snapshot_locked():
                if progress_state["native_seen"]:
                    transferred_bytes = min(
                        progress_offset_bytes + progress_state["native_bytes"],
                        total_bytes
                    )
                    percent = self._combined_progress_percent(
                        total_bytes,
                        progress_offset_bytes,
                        progress_state["native_bytes"]
                    )
                else:
                    transferred_bytes = min(
                        progress_offset_bytes + progress_state["bytes"],
                        total_bytes
                    )
                    percent = self._combined_progress_percent(
                        total_bytes,
                        progress_offset_bytes,
                        progress_state["bytes"]
                    )

                percent = max(progress_state["last_percent"], percent)
                progress_state["last_percent"] = percent
                speed = progress_state["speed"]
                remaining_bytes = max(total_bytes - transferred_bytes, 0)
                eta = (
                    self._format_time(remaining_bytes / speed)
                    if speed > 0
                    else "--"
                )
                speed_text = (
                    self._format_size(speed) + "/s"
                    if speed > 0
                    else "0 B/s"
                )
                return percent, speed_text, eta, transferred_bytes

            def emit_progress():
                with progress_lock:
                    percent, speed_text, eta, transferred = progress_snapshot_locked()
                self.progressChanged.emit(percent, speed_text, eta)
                print(
                    "ADB TRANSFER PROGRESS:",
                    f"{percent}%",
                    "|",
                    self._format_size(transferred),
                    "/",
                    self._format_size(total_bytes),
                    "|",
                    speed_text,
                    "| ETA:",
                    eta
                )

            def report_adb_output_line(line):
                overall_percent, file_path, file_percent = (
                    self._parse_adb_progress_details(line)
                )
                measured_speed = self._parse_adb_transfer_speed(line)
                if overall_percent is None and measured_speed is None:
                    return

                now = time.monotonic()
                with progress_lock:
                    if overall_percent is not None:
                        progress_state["native_seen"] = True
                        progress_state["native_percent"] = max(
                            progress_state["native_percent"], overall_percent
                        )
                        remaining_capacity = max(
                            total_bytes - progress_offset_bytes, 0
                        )
                        native_bytes = int(
                            remaining_capacity * progress_state["native_percent"] / 100
                        )
                        progress_state["native_bytes"] = max(
                            progress_state["native_bytes"], native_bytes
                        )

                    samples = progress_state["speed_samples"]
                    if measured_speed is not None and measured_speed > 0:
                        samples.append(measured_speed)
                        progress_state["native_speed_seen"] = True

                    if file_path and file_percent is not None:
                        file_key = os.path.normcase(os.path.normpath(file_path))
                        cache = progress_state["file_size_cache"]
                        if file_key not in cache:
                            try:
                                cache[file_key] = Path(file_path).stat().st_size
                            except (OSError, ValueError):
                                cache[file_key] = 0
                        file_size = cache[file_key]

                        is_new_file = (
                            file_key != progress_state["current_file_path"]
                        )
                        if is_new_file:
                            progress_state["current_file_path"] = file_key
                            progress_state["current_file_percent"] = 0
                            progress_state["current_file_time"] = now

                        previous_percent = progress_state["current_file_percent"]
                        previous_time = progress_state["current_file_time"]
                        if (
                            not is_new_file
                            and file_size > 0
                            and file_percent > previous_percent
                            and now > previous_time
                        ):
                            delta_bytes = (
                                file_size * (file_percent - previous_percent) / 100.0
                            )
                            elapsed = max(now - previous_time, 0.001)
                            file_speed = delta_bytes / elapsed
                            if file_speed > 0:
                                samples.append(file_speed)
                                progress_state["native_speed_seen"] = True

                        if file_percent >= previous_percent:
                            progress_state["current_file_percent"] = file_percent
                            progress_state["current_file_time"] = now

                    if len(samples) > 8:
                        del samples[:-8]
                    if samples:
                        progress_state["speed"] = sum(samples) / len(samples)

                emit_progress()
                print("ADB NATIVE PROGRESS LINE:", line.strip())

            def drain_output(stream, chunks, channel):
                if stream is None:
                    return
                pending = ""
                try:
                    while True:
                        chunk = stream.read1(4096)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        pending += chunk.decode("utf-8", errors="replace")
                        fragments = re.split(r"[\\r\\n]+", pending)
                        pending = fragments.pop()
                        for fragment in fragments:
                            report_adb_output_line(fragment)
                    if pending:
                        report_adb_output_line(pending)
                except Exception as exc:
                    print(f"ADB {channel.upper()} DRAIN WARNING:", exc)

            with self._process_lock:
                self._current_process = process
                cancelled = self._cancel_event.is_set()

            if cancelled:
                process.terminate()

            stdout_reader = threading.Thread(
                target=drain_output,
                args=(process.stdout, stdout_chunks, "stdout"),
                name=f"ADB-stdout-{device}",
                daemon=True
            )
            stderr_reader = threading.Thread(
                target=drain_output,
                args=(process.stderr, stderr_chunks, "stderr"),
                name=f"ADB-stderr-{device}",
                daemon=True
            )
            stdout_reader.start()
            stderr_reader.start()

            def io_progress_callback(io_bytes, io_speed):
                if progress_stop.is_set():
                    return

                delta_bytes = max(int(io_bytes), 0)
                raw_speed = max(float(io_speed), 0.0)
                with progress_lock:
                    progress_state["bytes"] += delta_bytes
                    # Process-I/O speed is only a fallback. ADB's file/summary
                    # measurements take precedence when the tool reports them.
                    if raw_speed > 0 and not progress_state["native_speed_seen"]:
                        samples = progress_state["speed_samples"]
                        samples.append(raw_speed)
                        if len(samples) > 8:
                            del samples[:-8]
                        progress_state["speed"] = sum(samples) / len(samples)
                emit_progress()

            progress_thread = threading.Thread(
                target=monitor_adb_io,
                args=(process.pid, io_progress_callback, progress_stop),
                daemon=True
            )
            progress_thread.start()

            # Drain both pipes while the real adb.exe process is running.
            return_code = process.wait()
            progress_stop.set()
            progress_thread.join(timeout=1.0)
            stdout_reader.join(timeout=2.0)
            stderr_reader.join(timeout=2.0)

            stdout_text = b"".join(stdout_chunks).decode(
                "utf-8", errors="ignore"
            ).strip()
            stderr_text = b"".join(stderr_chunks).decode(
                "utf-8", errors="ignore"
            ).strip()
            combined_output = "\\n".join(
                part for part in (stdout_text, stderr_text) if part
            )

            with self._process_lock:
                if self._current_process is process:
                    self._current_process = None

            # --------------------------------------------------------
            # SUCCESS
            # --------------------------------------------------------

            if self._cancel_event.is_set():
                self.statusChanged.emit(
                    "تم إلغاء النقل"
                )
                self.finished.emit(
                    False,
                    "تم إلغاء النسخ"
                )
                return

            if return_code == 0:

                elapsed = max(
                    time.monotonic()
                    - start_time,
                    0.001
                )

                average_speed = (
                    total_bytes / elapsed
                    if total_bytes > 0
                    else 0
                )

                progress_state["bytes"] = (
                    total_bytes
                )

                self.progressChanged.emit(
                    100,
                    self._format_size(
                        average_speed
                    ) + "/s",
                    "00:00"
                )
                self._reconnect_retry_count = 0

                self.statusChanged.emit(
                    "اكتمل النسخ"
                )

                print()
                print(
                    "========================================"
                )
                print(
                    "ADB FAST TRANSFER COMPLETE"
                )
                print(
                    "TOTAL:",
                    self._format_size(
                        total_bytes
                    )
                )
                print(
                    "TIME:",
                    self._format_time(
                        elapsed
                    )
                )
                print(
                    "AVERAGE SPEED:",
                    self._format_size(
                        average_speed
                    ) + "/s"
                )
                print(
                    "========================================"
                )

                self.finished.emit(
                    True,
                    "تم نسخ اللعبة بنجاح"
                )

                return

            # --------------------------------------------------------
            # FAILURE
            # --------------------------------------------------------

            print(
                "ADB EXIT CODE:",
                return_code
            )

            if combined_output:

                print(
                    "ADB OUTPUT:",
                    combined_output
                )

            # A disconnected handset often makes adb push exit with a transport error.
            # Wait for the same serial to return, then retry with --sync so files already
            # copied successfully are not needlessly sent again.
            stderr_lower = (combined_output or stderr_text or "").lower()
            disconnect_markers = (
                "device offline",
                "device not found",
                "no devices/emulators found",
                "device disconnected",
                "transport error",
                "connection reset",
                "error: closed",
            )
            looks_disconnected = any(
                marker in stderr_lower
                for marker in disconnect_markers
            )
            device_connected = self._device_is_connected(device)
            if not device_connected or looks_disconnected:
                # Preserve the completed/attempted byte estimate before starting
                # a new adb process. --sync skips files already present on-device,
                # but each new process has fresh local I/O counters.
                self._progress_offset_bytes = min(
                    total_bytes,
                    progress_offset_bytes + progress_state["bytes"]
                )
                print(
                    "ADB PROGRESS OFFSET PRESERVED:",
                    self._format_size(self._progress_offset_bytes),
                    "/",
                    self._format_size(total_bytes)
                )

                self.statusChanged.emit(
                    "انقطع اتصال الهاتف. الرجاء إعادة توصيله لاستمرار النسخ..."
                )
                print("ADB PUSH INTERRUPTED; WAITING FOR RECONNECT:", device)
                if self._wait_for_device_reconnect(device):
                    if self._cancel_event.is_set():
                        self.finished.emit(
                            False,
                            "تم إلغاء النسخ أثناء انتظار إعادة توصيل الهاتف"
                        )
                        return

                    if self._reconnect_retry_count >= 10:
                        self.finished.emit(
                            False,
                            "تكرر فشل اتصال الهاتف بعد إعادة التوصيل؛ أعد المحاولة يدويًا."
                        )
                        return
                    self._reconnect_retry_count += 1
                    self._process_paused = False
                    self._pause_event.set()
                    retry_thread = threading.Thread(
                        target=self._push_thread,
                        args=(device, requested_source, requested_destination),
                        name=f"ADB-push-resume-{device}",
                        daemon=True
                    )
                    self._thread = retry_thread
                    retry_thread.start()
                    return

                self.finished.emit(
                    False,
                    "تعذر استعادة اتصال الهاتف أو تم إلغاء النسخ"
                )
                return

            self.finished.emit(
                False,
                (
                    "فشل النسخ عبر ADB: "
                    + (combined_output or stderr_text)
                    if (combined_output or stderr_text)
                    else "فشل النسخ عبر ADB"
                )
            )

        except Exception as e:

            with self._process_lock:
                if self._current_process is process:
                    self._current_process = None

            print(
                "ADB FAST TRANSFER ERROR:",
                e
            )

            self.finished.emit(
                False,
                str(e)
            )


    @Slot(str, str, str)
    def push(self, device, source, destination):

        if self._thread and self._thread.is_alive():
            return

        self._pause_event.set()
        self._process_paused = False
        self._reconnect_retry_count = 0
        self._progress_offset_bytes = 0

        self._cancel_event.clear()
        self._cancelled_by_user = False

        self._thread = threading.Thread(
            target=self._push_thread,
            args=(
                device,
                source,
                destination
            ),
            daemon=True
        )

        self._thread.start()

    @Slot(str, str)
    def install_apks(self, device, apks_file):

        self._cancel_event.clear()

        def worker():

            import tempfile
            import zipfile

            temp_dir = None

            try:
                if not os.path.isfile(apks_file):

                    self.finished.emit(
                        False,
                        "ملف APKS غير موجود"
                    )

                    return

                self.statusChanged.emit(
                    "جاري تجهيز حزمة APKS..."
                )

                temp_dir = tempfile.mkdtemp(
                    prefix="kafia_apks_"
                )

                with zipfile.ZipFile(
                    apks_file,
                    "r"
                ) as z:

                    apk_names = [
                        name
                        for name in z.namelist()
                        if name.lower().endswith(".apk")
                    ]

                    for name in apk_names:
                        z.extract(name, temp_dir)

                apk_files = [
                    str(Path(temp_dir) / name)
                    for name in apk_names
                ]

                if not apk_files:

                    self.finished.emit(
                        False,
                        "لم توجد ملفات APK داخل APKS"
                    )

                    return

                self.statusChanged.emit(
                    "جاري تثبيت حزمة Free Fire..."
                )

                result = self._run_install_command(
                    [
                        "-s",
                        device,
                        "install-multiple",
                        "-r",
                        *apk_files
                    ],
                    timeout=3600
                )

                output = (
                    result.stdout.strip()
                    + "\n"
                    + result.stderr.strip()
                ).strip()

                print(
                    "ADB INSTALL-MULTIPLE:",
                    output
                )

                if result.returncode == 0:

                    self.statusChanged.emit(
                        "اكتمل التثبيت"
                    )

                    self.finished.emit(
                        True,
                        "تم تثبيت التطبيق بنجاح"
                    )

                else:

                    self.finished.emit(
                        False,
                        output or "فشل تثبيت حزمة APKS"
                    )

            except Exception as e:

                print(
                    "APKS INSTALL ERROR:",
                    e
                )

                self.finished.emit(
                    False,
                    str(e)
                )

            finally:

                if temp_dir:

                    import shutil

                    try:
                        shutil.rmtree(
                            temp_dir,
                            ignore_errors=True
                        )
                    except Exception:
                        pass

        threading.Thread(
            target=worker,
            daemon=True
        ).start()

    @Slot(str)
    def install(self, device, apk):

        self._cancel_event.clear()

        def worker():

            try:
                if not os.path.isfile(apk):

                    self.finished.emit(
                        False,
                        "ملف APK غير موجود"
                    )

                    return

                self.statusChanged.emit(
                    "جاري تثبيت التطبيق..."
                )

                result = self._run_install_command(
                    [
                        "-s",
                        device,
                        "install",
                        "-r",
                        apk
                    ],
                    timeout=3600
                )

                output = (
                    result.stdout.strip()
                    + "\n"
                    + result.stderr.strip()
                ).strip()

                print("ADB INSTALL:", output)

                if result.returncode == 0:

                    self.statusChanged.emit(
                        "اكتمل التثبيت"
                    )

                    self.finished.emit(
                        True,
                        "تم تثبيت التطبيق بنجاح"
                    )

                else:

                    self.finished.emit(
                        False,
                        output or "فشل تثبيت التطبيق"
                    )

            except Exception as e:

                self.finished.emit(
                    False,
                    str(e)
                )

        threading.Thread(
            target=worker,
            daemon=True
        ).start()

    def _suspend_current_process(self):

        with self._process_lock:
            process = self._current_process

        if process is None:
            return False

        if process.poll() is not None:
            return False

        try:

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            ntdll = ctypes.WinDLL("ntdll")

            PROCESS_SUSPEND_RESUME = 0x0800

            OpenProcess = kernel32.OpenProcess
            OpenProcess.argtypes = [
                ctypes.c_uint32,
                ctypes.c_int,
                ctypes.c_uint32
            ]
            OpenProcess.restype = ctypes.c_void_p

            CloseHandle = kernel32.CloseHandle
            CloseHandle.argtypes = [ctypes.c_void_p]
            CloseHandle.restype = ctypes.c_int

            NtSuspendProcess = ntdll.NtSuspendProcess
            NtSuspendProcess.argtypes = [ctypes.c_void_p]
            NtSuspendProcess.restype = ctypes.c_long

            handle = OpenProcess(
                PROCESS_SUSPEND_RESUME,
                False,
                process.pid
            )

            if not handle:
                error = ctypes.get_last_error()
                print("PAUSE OPENPROCESS ERROR:", error)
                return False

            status = NtSuspendProcess(handle)

            CloseHandle(handle)

            if status == 0:

                self._process_paused = True

                print(
                    "ADB PROCESS PAUSED:",
                    process.pid
                )

                return True

            print(
                "NT SUSPEND ERROR:",
                status
            )

        except Exception as e:

            print(
                "PAUSE PROCESS ERROR:",
                e
            )

        return False

    def _resume_current_process(self):

        with self._process_lock:
            process = self._current_process

        if process is None:
            return False

        try:

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            ntdll = ctypes.WinDLL("ntdll")

            PROCESS_SUSPEND_RESUME = 0x0800

            OpenProcess = kernel32.OpenProcess
            OpenProcess.argtypes = [
                ctypes.c_uint32,
                ctypes.c_int,
                ctypes.c_uint32
            ]
            OpenProcess.restype = ctypes.c_void_p

            CloseHandle = kernel32.CloseHandle
            CloseHandle.argtypes = [ctypes.c_void_p]
            CloseHandle.restype = ctypes.c_int

            NtResumeProcess = ntdll.NtResumeProcess
            NtResumeProcess.argtypes = [ctypes.c_void_p]
            NtResumeProcess.restype = ctypes.c_long

            handle = OpenProcess(
                PROCESS_SUSPEND_RESUME,
                False,
                process.pid
            )

            if not handle:
                error = ctypes.get_last_error()
                print("RESUME OPENPROCESS ERROR:", error)
                return False

            status = NtResumeProcess(handle)

            CloseHandle(handle)

            if status == 0:

                self._process_paused = False

                print(
                    "ADB PROCESS RESUMED:",
                    process.pid
                )

                return True

            print(
                "NT RESUME ERROR:",
                status
            )

        except Exception as e:

            print(
                "RESUME PROCESS ERROR:",
                e
            )

        return False

    @Slot(result=bool)
    def pause(self):

        if self._process_paused:
            return True

        with self._process_lock:
            process = self._current_process

        if process is None or process.poll() is not None:

            self.statusChanged.emit(
                "لا توجد عملية نقل يمكن إيقافها مؤقتًا الآن"
            )

            return False

        if self._suspend_current_process():

            self._pause_event.clear()

            self.statusChanged.emit(
                "تم إيقاف النقل مؤقتًا"
            )
            return True

        else:

            self.statusChanged.emit(
                "تعذر إيقاف النقل مؤقتًا"
            )
            return False

    @Slot(result=bool)
    def resume(self):

        process = self._current_process

        if process is None or process.poll() is not None:

            self._pause_event.set()

            self.statusChanged.emit(
                "لا توجد عملية نقل جارية"
            )

            return False

        if self._process_paused:

            if self._resume_current_process():

                self._pause_event.set()

                self.statusChanged.emit(
                    "تم استئناف النقل..."
                )
                return True

            else:

                self.statusChanged.emit(
                    "تعذر استئناف النقل"
                )
                return False

        else:

            self._pause_event.set()

            self.statusChanged.emit(
                "تم استئناف النقل..."
            )
            return True

    @Slot()
    def cancel(self):

        print("ADB CANCEL REQUESTED")

        self._cancelled_by_user = True

        self._cancel_event.set()

        self._pause_event.set()

        with self._process_lock:
            process = self._current_process

        if process is not None:

            try:

                if self._process_paused:

                    self._resume_current_process()

                if process.poll() is None:

                    process.terminate()

                    print(
                        "ADB PROCESS TERMINATED:",
                        process.pid
                    )

            except Exception as e:

                print(
                    "CANCEL ERROR:",
                    e
                )

        self._process_paused = False
