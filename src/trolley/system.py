import os
import platform
import shutil
import socket
from pathlib import Path
from typing import Any


def runtime_info() -> dict[str, Any]:
    return {
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count(),
        "python_version": platform.python_version(),
    }


def runtime_metrics() -> dict[str, Any]:
    total, available = memory_info()
    disk = shutil.disk_usage(Path("/"))
    memory_percent = None
    if total and available is not None:
        memory_percent = round((total - available) / total * 100, 2)
    return {
        "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        "memory_total": total,
        "memory_available": available,
        "memory_percent": memory_percent,
        "disk_total": disk.total,
        "disk_free": disk.free,
        "disk_percent": round(disk.used / disk.total * 100, 2) if disk.total else None,
    }


def memory_info() -> tuple[int | None, int | None]:
    if platform.system() == "Linux":
        values = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, value = line.split(":", 1)
                values[key] = int(value.strip().split()[0]) * 1024
            return values.get("MemTotal"), values.get("MemAvailable")
        except (OSError, ValueError, IndexError):
            pass
    return None, None
