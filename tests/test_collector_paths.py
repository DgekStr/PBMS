#!/usr/bin/env python3
"""Verify that the collector chooses the newest archive across configured paths."""
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
    alternate = os.path.join(root, "alternate")
    os.makedirs(default)
    os.makedirs(alternate)

    old_file = os.path.join(default, "vzdump-qemu-101-old.vma.zst")
    new_file = os.path.join(alternate, "vzdump-qemu-101-new.vma.zst")
    open(old_file, "wb").write(b"old")
    open(new_file, "wb").write(b"newer")
    now = time.time()
    os.utime(old_file, (now - 86400, now - 86400))
    os.utime(new_file, (now, now))

    namespace["backup_dir"] = default
    namespace["NODE_BACKUP_PATHS"] = {"pve": [default, alternate]}
    result = namespace["find_backup_for_node"]("qemu", "101", "pve")

    assert result["file"] == "vzdump-qemu-101-new.vma.zst", result
    assert result["path"] == alternate, result

print("multi-path backup selection passed")
