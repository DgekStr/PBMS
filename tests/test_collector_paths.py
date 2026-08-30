#!/usr/bin/env python3
"""Проверяет, что коллектор выбирает самый новый архив среди настроенных путей."""
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
source = open(os.path.join(ROOT, "backup_monitor_collector.py"), encoding="utf-8").read()
sys.argv = ["backup_monitor_collector.py", "out.json", "default", "pve", "15", "0"]
namespace = {"__name__": "collector_test"}
exec(source.split("for node in nodes:")[0], namespace)

with tempfile.TemporaryDirectory(prefix="pbms-paths-") as root:
    default = os.path.join(root, "default")
    hdd2 = os.path.join(root, "hdd2")
    os.makedirs(default)
    os.makedirs(hdd2)

    old_file = os.path.join(default, "vzdump-qemu-101-old.vma.zst")
    new_file = os.path.join(hdd2, "vzdump-qemu-101-new.vma.zst")
    open(old_file, "wb").write(b"old")
    open(new_file, "wb").write(b"newer")
    now = time.time()
    os.utime(old_file, (now - 86400, now - 86400))
    os.utime(new_file, (now, now))

    namespace["backup_dir"] = default
    namespace["NODE_BACKUP_PATHS"] = {"pve2": [default]}
    namespace["discovered_backup_paths"] = lambda: [hdd2, os.path.join(hdd2, "dump")]
    result = namespace["find_backup_for_node"]("qemu", "101", "pve2")

    assert result["file"] == "vzdump-qemu-101-new.vma.zst", result
    assert result["path"] == hdd2, result

print("hdd2 backup selection passed")
