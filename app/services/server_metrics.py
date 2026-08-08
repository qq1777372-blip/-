"""Host metric collection, standard library only.

This is deliberately free of third-party imports so the same code can run on a
box that has no virtualenv for this project: `scripts/report_server_status.py`
copies this file to the secondary server and pushes the result back to the main
site. `app/services/server_status.py` wraps it with the SQLAlchemy engine probe
for the local node.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


PROCESS_STARTED_MONOTONIC = time.monotonic()
DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
SKIPPED_DIRECTORY_NAMES = {
    ".git",
    ".idea",
    ".venv",
    "__pycache__",
    "node_modules",
    "uploads",
}


def _percent(used: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(used * 100.0 / total, 1)


def _read_cpu_percent() -> float | None:
    if platform.system() != "Linux":
        return None

    def read_snapshot() -> tuple[int, int] | None:
        try:
            values = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0].split()[1:]
            counters = [int(value) for value in values]
        except (OSError, ValueError, IndexError):
            return None

        idle = counters[3] + (counters[4] if len(counters) > 4 else 0)
        return sum(counters), idle

    first = read_snapshot()
    if first is None:
        return None
    time.sleep(0.12)
    second = read_snapshot()
    if second is None:
        return None

    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]
    if total_delta <= 0:
        return None
    return round(max(0.0, min(100.0, (total_delta - idle_delta) * 100.0 / total_delta)), 1)


def _read_memory() -> tuple[int, int, int, float]:
    if platform.system() == "Linux":
        values: dict[str, int] = {}
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, raw_value = line.split(":", 1)
                values[key] = int(raw_value.strip().split()[0]) * 1024
        except (OSError, ValueError, IndexError):
            values = {}

        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", values.get("MemFree", 0))
        used = max(0, total - available)
        return total, used, available, _percent(used, total)

    return 0, 0, 0, 0.0


def _read_system_uptime_seconds() -> int | None:
    if platform.system() == "Linux":
        try:
            return int(float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0]))
        except (OSError, ValueError, IndexError):
            return None
    return None


def _read_load_average() -> tuple[float | None, float | None, float | None]:
    try:
        values = os.getloadavg()
    except (AttributeError, OSError):
        return None, None, None
    return tuple(round(value, 2) for value in values)


def _collect_service_status(service_name: str, display_name: str) -> dict[str, Any]:
    normalized = service_name.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", normalized):
        return {
            "name": normalized or service_name,
            "display_name": display_name,
            "active_state": "invalid",
            "sub_state": "invalid",
            "description": "服务名称无效",
            "is_active": False,
        }

    unit_name = normalized if normalized.endswith(".service") else f"{normalized}.service"
    try:
        result = subprocess.run(
            [
                "systemctl",
                "show",
                unit_name,
                "--property=Id,Description,ActiveState,SubState",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {
            "name": unit_name,
            "display_name": display_name,
            "active_state": "unavailable",
            "sub_state": "unavailable",
            "description": "无法读取服务状态",
            "is_active": False,
        }

    properties: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        properties[key] = value

    active_state = properties.get("ActiveState") or ("not-found" if result.returncode else "unknown")
    return {
        "name": properties.get("Id") or unit_name,
        "display_name": display_name,
        "active_state": active_state,
        "sub_state": properties.get("SubState") or active_state,
        "description": properties.get("Description") or display_name,
        "is_active": active_state == "active",
    }


def _database_category(path: Path) -> str:
    lowered_parts = [part.lower() for part in path.parts]
    lowered_name = path.name.lower()
    if any("backup" in part for part in lowered_parts) or "before_" in lowered_name:
        return "backup"
    return "active"


def _check_sqlite_database(path: Path) -> tuple[str, str | None]:
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.5)
        try:
            connection.execute("PRAGMA schema_version").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        error_message = str(exc)[:160]
        if "unable to open database file" in error_message.lower():
            return "restricted", error_message
        return "error", error_message
    return "available", None


def _collect_database_files(database_roots: Iterable[tuple[str, Path]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()

    for source_name, configured_root in database_roots:
        try:
            root = configured_root.expanduser().resolve()
        except OSError:
            continue
        if not root.exists() or not root.is_dir():
            continue

        for current_root, directory_names, file_names in os.walk(root):
            directory_names[:] = [
                name for name in directory_names if name not in SKIPPED_DIRECTORY_NAMES
            ]
            current_path = Path(current_root)
            for file_name in file_names:
                path = current_path / file_name
                if path.suffix.lower() not in DATABASE_SUFFIXES:
                    continue
                try:
                    resolved_path = path.resolve()
                    if resolved_path in seen_paths or not resolved_path.is_file():
                        continue
                    seen_paths.add(resolved_path)
                    stat = resolved_path.stat()
                    relative_path = resolved_path.relative_to(root).as_posix()
                except (OSError, ValueError):
                    continue

                sidecar_size = 0
                for suffix in ("-wal", "-shm"):
                    sidecar_path = Path(f"{resolved_path}{suffix}")
                    try:
                        if sidecar_path.is_file():
                            sidecar_size += sidecar_path.stat().st_size
                    except OSError:
                        continue

                database_status, error_message = _check_sqlite_database(resolved_path)
                rows.append(
                    {
                        "name": resolved_path.name,
                        "source": source_name,
                        "relative_path": relative_path,
                        "category": _database_category(resolved_path),
                        "status": database_status,
                        "error_message": error_message,
                        "main_size_bytes": stat.st_size,
                        "sidecar_size_bytes": sidecar_size,
                        "size_bytes": stat.st_size + sidecar_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone(),
                    },
                )

    rows.sort(key=lambda item: (item["category"] == "backup", -item["size_bytes"], item["name"]))
    return rows


def compute_health(
    *,
    disk_percent: float,
    memory_percent: float,
    database_ok: bool,
    services: Iterable[dict[str, Any]],
) -> str:
    """Same thresholds for every node, wherever the numbers were collected."""
    if not database_ok or disk_percent >= 95:
        return "critical"
    if (
        disk_percent >= 85
        or memory_percent >= 90
        or any(not item.get("is_active") for item in services)
    ):
        return "warning"
    return "healthy"


def collect_node_metrics(
    base_dir: Path,
    database_roots: Iterable[tuple[str, Path]],
    services: Iterable[tuple[str, str]],
) -> dict[str, Any]:
    """Everything about a host that needs no database engine.

    The caller adds the `database_engine` / `database_connection_status` /
    `database_latency_ms` / `database_error` / `health` fields, because only it
    knows whether this node owns the application database.
    """
    disk = shutil.disk_usage(base_dir)
    memory_total, memory_used, memory_available, memory_percent = _read_memory()
    load_1m, load_5m, load_15m = _read_load_average()
    cpu_percent = _read_cpu_percent()

    service_rows = [_collect_service_status(name, label) for name, label in services]
    database_rows = _collect_database_files(database_roots)
    database_total_size = sum(item["size_bytes"] for item in database_rows)
    active_database_total_size = sum(
        item["size_bytes"] for item in database_rows if item["category"] == "active"
    )

    return {
        "generated_at": datetime.now().astimezone(),
        "hostname": platform.node() or "-",
        "operating_system": f"{platform.system()} {platform.release()}".strip(),
        "architecture": platform.machine() or "-",
        "cpu_count": os.cpu_count() or 0,
        "cpu_percent": cpu_percent,
        "load_1m": load_1m,
        "load_5m": load_5m,
        "load_15m": load_15m,
        "memory_total_bytes": memory_total,
        "memory_used_bytes": memory_used,
        "memory_available_bytes": memory_available,
        "memory_percent": memory_percent,
        "disk_total_bytes": disk.total,
        "disk_used_bytes": disk.used,
        "disk_free_bytes": disk.free,
        "disk_percent": _percent(disk.used, disk.total),
        "system_uptime_seconds": _read_system_uptime_seconds(),
        "process_uptime_seconds": int(time.monotonic() - PROCESS_STARTED_MONOTONIC),
        "process_id": os.getpid(),
        "database_count": len(database_rows),
        "database_total_size_bytes": database_total_size,
        "active_database_total_size_bytes": active_database_total_size,
        "backup_database_total_size_bytes": database_total_size - active_database_total_size,
        "services": service_rows,
        "databases": database_rows,
    }
