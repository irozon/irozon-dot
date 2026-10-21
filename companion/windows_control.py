"""Per-user Windows process coordination; no network control endpoint or PID files."""
import ctypes
from ctypes import wintypes
import hashlib
from pathlib import Path

kernel = ctypes.WinDLL('kernel32', use_last_error=True)
for name, result, args in (
    ('CreateMutexW', wintypes.HANDLE, [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]),
    ('CreateEventW', wintypes.HANDLE, [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]),
    ('OpenEventW', wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]),
    ('WaitForSingleObject', wintypes.DWORD, [wintypes.HANDLE, wintypes.DWORD]),
    ('ReleaseMutex', wintypes.BOOL, [wintypes.HANDLE]),
    ('SetEvent', wintypes.BOOL, [wintypes.HANDLE]),
    ('ResetEvent', wintypes.BOOL, [wintypes.HANDLE]),
    ('CloseHandle', wintypes.BOOL, [wintypes.HANDLE]),
):
    function = getattr(kernel, name)
    function.restype, function.argtypes = result, args


def names(config):
    identity = hashlib.sha256(str(Path(config).resolve()).casefold().encode()).hexdigest()[:24]
    base = 'Local\\IrozonDot-' + identity
    return base + '-instance', base + '-stop'


class Instance:
    def __init__(self, config):
        mutex_name, event_name = names(config)
        self.mutex = kernel.CreateMutexW(None, False, mutex_name)
        self.event = None
        if not self.mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        self.acquired = kernel.WaitForSingleObject(self.mutex, 0) in (0, 0x80)
        if self.acquired:
            self.event = kernel.CreateEventW(None, True, False, event_name)
            if not self.event:
                self.close()
                raise ctypes.WinError(ctypes.get_last_error())
            kernel.ResetEvent(self.event)

    def stop_requested(self):
        return self.event is not None and kernel.WaitForSingleObject(self.event, 0) == 0

    def close(self):
        if self.event:
            kernel.CloseHandle(self.event)
            self.event = None
        if self.mutex:
            if self.acquired:
                kernel.ReleaseMutex(self.mutex)
            kernel.CloseHandle(self.mutex)
            self.mutex = None


def running(config):
    instance = InstanceProbe(config)
    try:
        return not instance.acquired
    finally:
        instance.close()


class InstanceProbe(Instance):
    # Probes must not create/reset a running process's stop event.
    def __init__(self, config):
        self.mutex = kernel.CreateMutexW(None, False, names(config)[0])
        self.event = None
        if not self.mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        self.acquired = kernel.WaitForSingleObject(self.mutex, 0) in (0, 0x80)


def request_stop(config):
    event = kernel.OpenEventW(0x0002, False, names(config)[1])
    if not event:
        return False
    try:
        if not kernel.SetEvent(event):
            raise ctypes.WinError(ctypes.get_last_error())
        return True
    finally:
        kernel.CloseHandle(event)
