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
        self._cancelled_by_user = False

    def _get_adb_path(self):
        # Prefer the shared fixed ADB installation used by all
        # KAFIA NET CONTROL PRO updates.
        external_adb = Path(
            r"D:\games\programe files\platform-tools\adb.exe"
        )

        if external_adb.is_file():
            return str(external_adb)

        # Development/local fallback.
        local_adb = BASE_DIR / "platform-tools" / "adb.exe"

        if local_adb.is_file():
            return str(local_adb)

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

        result = self._run(
            ["devices"]
        )

        devices = []

        for line in result.stdout.splitlines():

            line = line.strip()

            if not line or line.startswith("List of devices"):
                continue

            parts = line.split()

            if len(parts) < 2:
                continue

            serial = parts[0]
            state = parts[1]

            if state != "device":
                continue

            model_result = self._run(
                [
                    "-s",
                    serial,
                    "shell",
                    "getprop",
                    "ro.product.model"
                ]
            )

            manufacturer_result = self._run(
                [
                    "-s",
                    serial,
                    "shell",
                    "getprop",
                    "ro.product.manufacturer"
                ]
            )

            model = model_result.stdout.strip()
            manufacturer = manufacturer_result.stdout.strip()

            if not model:
                model = "Android"

            if not manufacturer:
                manufacturer = "Android"

            devices.append({
                "serial": serial,
                "model": model,
                "manufacturer": manufacturer,
                "name": f"{manufacturer} {model} [{serial}]"
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

    def _wait_for_device_reconnect(self, device):
        self.statusChanged.emit(
            "الهاتف مفصول — بانتظار إعادة التوصيل..."
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
                )

                if (
                    result.returncode == 0
                    and result.stdout.strip().lower() == "device"
                ):
                    self.statusChanged.emit(
                        "تمت إعادة توصيل الهاتف — استئناف النقل..."
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
            )

            return result.returncode == 0

        except Exception as e:
            print(
                "ADB REMOTE FILE CHECK ERROR:",
                e
            )
            return None

    def _push_thread(
        self,
        device,
        source,
        destination
    ):

        process = None

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

            # Treat the configured destination as the exact root
            # of the copy. The trailing "/." prevents adb from
            # introducing the source directory name underneath it.
            destination = destination.rstrip("/") + "/."

            # --------------------------------------------------------
            # --------------------------------------------------------
            # PRE-FLIGHT DESTINATION WRITE CHECK
            # Direct ADB shell commands only.
            # --------------------------------------------------------
            check_path = destination.rstrip('/.') or destination
            check_file = (
                check_path.rstrip('/')
                + '/.cncall_write_test'
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

            print()
            print("========================================")
            print("ADB FAST TRANSFER ENGINE")
            print("========================================")
            print("SOURCE:", source_path)
            print("DESTINATION:", destination)
            print("TOTAL SIZE:", self._format_size(total_bytes))
            print("========================================")

            self._pause_event.set()


            # RESUMABLE FILE-BY-FILE TRANSFER
            #
            # Existing final files are never overwritten.
            # The current file is first pushed to .cncall.part.
            # A disconnected phone is never reported as a permanent
            # failure: wait for reconnect, reconcile, then continue.
            # --------------------------------------------------------
            remote_root = destination.rstrip('/.')

            if source_path.is_dir():
                local_files = [
                    f
                    for f in source_path.rglob('*')
                    if f.is_file()
                ]
            else:
                local_files = [source_path]

            source_total_bytes = sum(
                f.stat().st_size
                for f in local_files
            )

            completed_bytes = 0
            skipped_files = 0
            completed_files = 0

            for local_file in local_files:

                if self._cancel_event.is_set():
                    self.finished.emit(
                        False,
                        "تم إلغاء النسخ"
                    )
                    return

                if source_path.is_dir():
                    relative = local_file.relative_to(source_path)
                    remote_file = (
                        remote_root
                        + '/'
                        + '/'.join(relative.parts)
                    )
                else:
                    remote_file = (
                        remote_root
                        + '/'
                        + local_file.name
                    )

                temporary_file = remote_file + '.cncall.part'

                # Never overwrite a completed destination file.
                while not self._cancel_event.is_set():

                    exists = self._remote_file_exists(
                        device,
                        remote_file
                    )

                    if exists is True:
                        completed_bytes += local_file.stat().st_size
                        completed_files += 1
                        skipped_files += 1
                        break

                    if exists is None:
                        if not self._wait_for_device_reconnect(device):
                            self.finished.emit(
                                False,
                                "تم إلغاء النسخ"
                            )
                            return
                        continue

                    # The destination file does not exist.
                    # Remove any stale .part from a previous interrupted run.
                    subprocess.run(
                        [
                            self.adb,
                            '-s',
                            device,
                            'shell',
                            'rm',
                            '-f',
                            temporary_file,
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                    )

                    remote_parent = remote_file.rsplit('/', 1)[0]

                    mkdir_result = subprocess.run(
                        [
                            self.adb,
                            '-s',
                            device,
                            'shell',
                            'mkdir',
                            '-p',
                            remote_parent,
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.DEVNULL,
                        text=True,
                        encoding='utf-8',
                        errors='ignore',
                    )

                    if mkdir_result.returncode != 0:
                        if not self._wait_for_device_reconnect(device):
                            self.finished.emit(
                                False,
                                "تم إلغاء النسخ"
                            )
                            return
                        continue

                    command = [
                        self.adb,
                        '-s',
                        device,
                        'push',
                        str(local_file),
                        temporary_file,
                    ]

                    print(
                        "ADB RESUMABLE FILE:",
                        local_file,
            "->",
                        temporary_file,
                    )

                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE

                    process = subprocess.Popen(
                        command,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.DEVNULL,
                        startupinfo=startupinfo,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )

                    with self._process_lock:
                        self._current_process = process

                    start_time = time.monotonic()

                    return_code = process.wait()

                    stderr_text = ''
                    try:
                        if process.stderr is not None:
                            data = process.stderr.read()
                            if data:
                                stderr_text = data.decode(
                                    'utf-8',
                                    errors='ignore'
                                ).strip()
                    except Exception:
                        stderr_text = ''

                    with self._process_lock:
                        if self._current_process is process:
                            self._current_process = None

                    if self._cancel_event.is_set():
                        self.finished.emit(
                            False,
                            "تم إلغاء النسخ"
                        )
                        return

                    if return_code != 0:

                        device_connected = False

                        try:
                            state = subprocess.run(
                                [
                                    self.adb,
                                    '-s',
                                    device,
                                    'get-state',
                                ],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL,
                                text=True,
                                encoding='utf-8',
                                errors='ignore',
                                timeout=5,
                            )
                            device_connected = (
                                state.returncode == 0
                                and state.stdout.strip().lower() == 'device'
                            )
                        except Exception:
                            device_connected = False

                        if not device_connected:
                            if not self._wait_for_device_reconnect(device):
                                self.finished.emit(
                                    False,
                                    "تم إلغاء النسخ"
                                )
                                return

                            # Recheck the final destination after reconnect.
                            final_exists = self._remote_file_exists(
                                device,
                                remote_file,
                            )

                            if final_exists is True:
                                completed_bytes += local_file.stat().st_size
                                completed_files += 1
                                skipped_files += 1
                                break

                            self.statusChanged.emit(
                                "تمت إعادة التوصيل — إعادة نقل الملف..."
                            )
                            continue

                        self.finished.emit(
                            False,
                            (
                                "فشل النسخ عبر ADB: "
                                + stderr_text
                                if stderr_text
                                else "فشل النسخ عبر ADB"
                            )
                        )
                        return

                    # Push succeeded to .part.
                    # Publish the final filename without replacing an existing file.
                    final_exists = self._remote_file_exists(
                        device,
                        remote_file,
                    )

                    if final_exists is None:
                        if not self._wait_for_device_reconnect(device):
                            self.finished.emit(
                                False,
                                "تم إلغاء النسخ"
                            )
                            return
                        continue

                    if final_exists is True:
                        subprocess.run(
                            [
                                self.adb,
                                '-s',
                                device,
                                'shell',
                                'rm',
                                '-f',
                                temporary_file,
                            ],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL,
                        )
                        completed_bytes += local_file.stat().st_size
                        completed_files += 1
                        skipped_files += 1
                        break

                    rename_result = subprocess.run(
                        [
                            self.adb,
                            '-s',
                            device,
                            'shell',
                            'mv',
                            temporary_file,
                            remote_file,
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.DEVNULL,
                        text=True,
                        encoding='utf-8',
                        errors='ignore',
                    )

                    if rename_result.returncode != 0:
                        if not self._wait_for_device_reconnect(device):
                            self.finished.emit(
                                False,
                                "تم إلغاء النسخ"
                            )
                            return

                        final_exists = self._remote_file_exists(
                            device,
                            remote_file,
                        )

                        if final_exists is True:
                            completed_bytes += local_file.stat().st_size
                            completed_files += 1
                            break

                        continue

                    completed_bytes += local_file.stat().st_size
                    completed_files += 1

                    percent = (
                        int(completed_bytes * 100 / source_total_bytes)
                        if source_total_bytes > 0
                        else 100
                    )

                    self.progressChanged.emit(
                        max(0, min(percent, 100)),
                        "0 B/s",
            "00:00"
                    )

            if self._cancel_event.is_set():
                self.finished.emit(False, 'تم إلغاء النسخ')
                return

            self.progressChanged.emit(
                100,
                "0 B/s",
            "00:00"
            )

            self.statusChanged.emit(
                "اكتمل النسخ بدون استبدال الملفات الموجودة"
            )

            self.finished.emit(
                True,
                (
                    "تم النسخ بنجاح — "
                    + str(skipped_files)
                    + " ملف تم تخطيه أو كان موجودًا مسبقًا"
                )
            )

            return
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

    @Slot()
    def pause(self):

        if self._process_paused:
            return

        process = self._current_process

        if process is None or process.poll() is not None:

            self.statusChanged.emit(
                "لا توجد عملية نقل جارية"
            )

            return

        if self._suspend_current_process():

            self._pause_event.clear()

            self.statusChanged.emit(
                "تم إيقاف النقل مؤقتًا"
            )

        else:

            self.statusChanged.emit(
                "تعذر إيقاف النقل مؤقتًا"
            )

    @Slot()
    def resume(self):

        process = self._current_process

        if process is None or process.poll() is not None:

            self._pause_event.set()

            self.statusChanged.emit(
                "لا توجد عملية نقل جارية"
            )

            return

        if self._process_paused:

            if self._resume_current_process():

                self._pause_event.set()

                self.statusChanged.emit(
                    "تم استئناف النقل..."
                )

            else:

                self.statusChanged.emit(
                    "تعذر استئناف النقل"
                )

        else:

            self._pause_event.set()

            self.statusChanged.emit(
                "تم استئناف النقل..."
            )

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
