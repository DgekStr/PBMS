#!/usr/bin/env python3
"""Сравнивает два JSON-файла коллектора PBMS и формирует JSON-отчёт об изменениях."""
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta


FIELDS = (
    ("name", "Имя"),
    ("status", "Состояние"),
    ("backup.status", "Статус бэкапа"),
    ("backup.date", "Дата бэкапа"),
    ("backup.size", "Размер бэкапа"),
    ("backup.path", "Хранилище"),
    ("backup.file", "Файл бэкапа"),
)


def object_key(item):
    return (
        str(item.get("node", "")),
        str(item.get("type", "")),
        str(item.get("id", "")),
    )


def value(item, field):
    current = item
    for part in field.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def display(value):
    if value is None or value == "":
        return "нет"
    return str(value)


def label(item):
    key = object_key(item)
    name = item.get("name") or ""
    return f"{key[0]} / {key[1]}-{key[2]}" + (f" ({name})" if name else "")


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_size_bytes(value):
    """Преобразует размеры из отчёта коллектора (например, 200M или 1.5G) в байты."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if value is None:
        return None
    match = re.fullmatch(
        r"\s*([0-9]+(?:\.[0-9]+)?)\s*([KMGTPE]?)B?\s*",
        str(value),
        re.IGNORECASE,
    )
    if not match:
        return None
    number = float(match.group(1))
    multiplier = {
        "": 1,
        "K": 1024,
        "M": 1024 ** 2,
        "G": 1024 ** 3,
        "T": 1024 ** 4,
        "P": 1024 ** 5,
        "E": 1024 ** 6,
    }[match.group(2).upper()]
    return number * multiplier


def severity(field, old, new):
    if field in ("status", "backup.status"):
        if str(new).upper() in ("ERROR", "TOO_SMALL", "STOPPED", "UNKNOWN"):
            return "bad"
        if str(old).upper() in ("ERROR", "TOO_SMALL", "STOPPED", "UNKNOWN"):
            return "good"
    if field == "backup.size" and old != new:
        new_size = parse_size_bytes(new)
        if new_size is not None and new_size >= 100 * 1024 * 1024:
            return "good"
    return "neutral"


def change(kind, item, field=None, old=None, new=None, message=None):
    result = {
        "kind": kind,
        "key": list(object_key(item)),
        "label": label(item),
    }
    if field:
        result.update({
            "field": field,
            "field_label": dict(FIELDS).get(field, field),
            "old": old,
            "new": new,
            "severity": "bad" if kind == "stale" else severity(field, old, new),
        })
    if message:
        result["message"] = message
    return result


def compare_reports(previous, current):
    previous_objects = {object_key(x): x for x in previous.get("objects", [])}
    current_objects = {object_key(x): x for x in current.get("objects", [])}
    changes = []

    for key in sorted(current_objects.keys() - previous_objects.keys()):
        changes.append(change("added", current_objects[key], message="Объект добавлен"))

    for key in sorted(previous_objects.keys() - current_objects.keys()):
        changes.append(change("removed", previous_objects[key], message="Объект удалён"))

    for key in sorted(current_objects.keys() & previous_objects.keys()):
        old_item = previous_objects[key]
        new_item = current_objects[key]
        for field, _ in FIELDS:
            old_value = value(old_item, field)
            new_value = value(new_item, field)
            if old_value != new_value:
                changes.append(change("changed", new_item, field, old_value, new_value))
        old_date = value(old_item, "backup.date")
        new_date = value(new_item, "backup.date")
        parsed_date = parse_date(new_date)
        if old_date == new_date and parsed_date:
            age = datetime.now(parsed_date.tzinfo) - parsed_date
            if age > timedelta(days=10):
                changes.append(change("stale", new_item, "backup.date", new_date, new_date,
                                      "Дата бэкапа не менялась более 10 дней"))

    return {
        "has_previous": True,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "changes": changes,
        "summary": {
            "added": sum(c["kind"] == "added" for c in changes),
            "removed": sum(c["kind"] == "removed" for c in changes),
            "changed": sum(c["kind"] == "changed" for c in changes),
        },
    }


def write_json_atomic(path, data):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pbms-diff-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} PREVIOUS_DATA_FILE CURRENT_DATA_FILE DIFF_FILE", file=sys.stderr)
        return 2
    previous_file, current_file, diff_file = sys.argv[1:]
    try:
        with open(current_file, encoding="utf-8") as fh:
            current = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"PBMS diff: cannot read current data: {exc}", file=sys.stderr)
        return 1

    try:
        with open(previous_file, encoding="utf-8") as fh:
            previous = json.load(fh)
        result = compare_reports(previous, current)
    except FileNotFoundError:
        result = {
            "has_previous": False,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "changes": [],
            "summary": {"added": 0, "removed": 0, "changed": 0},
        }
    except (OSError, json.JSONDecodeError) as exc:
        print(f"PBMS diff: previous state ignored: {exc}", file=sys.stderr)
        result = {
            "has_previous": False,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "changes": [],
            "summary": {"added": 0, "removed": 0, "changed": 0},
        }

    try:
        write_json_atomic(diff_file, result)
    except OSError as exc:
        print(f"PBMS diff: cannot write diff: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result["summary"], ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
