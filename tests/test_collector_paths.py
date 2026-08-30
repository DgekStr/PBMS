#!/usr/bin/env python3
"""Проверяет, что коллектор выбирает самый новый архив среди настроенных путей.

Второй сценарий проверяет SSH-fallback: когда каталог с дампами принадлежит
другой ноде (например /mnt/hdd2/dump на pve2) и недоступен локально, список
файлов читается по ssh с ноды-владельца.
"""
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
source = open(os.path.join(ROOT, "backup_monitor_collector.py"), encoding="utf-8").read()
sys.argv = ["backup_monitor_collector.py", "out.json", "default", "pve", "15", "0"]
namespace = {"__name__": "collector_test"}
exec(source.split("for node in nodes:")[0], namespace)

now = time.time()


def make_backup(directory, name, mtime_offset, size_bytes=4):
    path = os.path.join(directory, name)
    with open(path, "wb") as fh:
        fh.write(b"x" * size_bytes)
    os.utime(path, (now - mtime_offset, now - mtime_offset))
    return path


# --- Сценарий 1: самый новый локальный архив среди нескольких путей ---
with tempfile.TemporaryDirectory(prefix="pbms-paths-") as root:
    default = os.path.join(root, "default")
    hdd2 = os.path.join(root, "hdd2")
    os.makedirs(default)
    os.makedirs(hdd2)

    make_backup(default, "vzdump-qemu-101-old.vma.zst", 86400)
    make_backup(hdd2, "vzdump-qemu-101-new.vma.zst", 0)

    namespace["backup_dir"] = default
    namespace["NODE_BACKUP_PATHS"] = {"pve2": [hdd2]}
    namespace["discovered_backup_paths"] = lambda: []

    result = namespace["find_backup_for_node"]("qemu", "101", "pve2")
    assert result is not None, result
    assert result["file"] == "vzdump-qemu-101-new.vma.zst", result
    assert result["path"] == hdd2, result

print("hdd2 backup selection passed")


# --- Сценарий 2: путь другой ноды недоступен локально, читается по ssh ---
remote_dir = "/mnt/hdd2/dump"
remote_entries = [
    ("vzdump-qemu-101-2026_08_29-00_00_00.vma.zst", now, 200 * 1024 * 1024),
]


def fake_list_remote_dir(path, owner):
    if path == remote_dir:
        return remote_entries
    return []


namespace["backup_dir"] = "/nonexistent/default"
namespace["NODE_BACKUP_PATHS"] = {"pve2": ["/mnt/pve/backup/dump", remote_dir]}
namespace["discovered_backup_paths"] = lambda: []
namespace["list_remote_dir"] = fake_list_remote_dir

result = namespace["find_backup_for_node"]("qemu", "101", "pve2")
assert result is not None, result
assert result["file"] == "vzdump-qemu-101-2026_08_29-00_00_00.vma.zst", result
assert result["path"] == remote_dir, result
assert result["size_bytes"] == 200 * 1024 * 1024, result

print("hdd2 ssh-fallback selection passed")
