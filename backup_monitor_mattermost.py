#!/usr/bin/env python3
"""Send the current PBMS report and its change list to Mattermost."""
import json
import re
import sys
import urllib.error
import urllib.request
from html import unescape


MAX_MESSAGE_LENGTH = 12000


def format_changes(diff):
    if not diff.get("has_previous"):
        return "_Предыдущий отчёт отсутствует; текущий результат сохранён как baseline._"
    changes = diff.get("changes", [])
    summary = diff.get("summary", {})
    if not changes:
        return "_Изменений с предыдущей проверки нет._"
    lines = [
        "**Изменения с предыдущей проверки**",
        f"Добавлено: {summary.get('added', 0)} · Удалено: {summary.get('removed', 0)} · Изменено: {summary.get('changed', 0)}",
    ]
    for item in changes:
        kind = item.get("kind")
        prefix = {"added": "+", "removed": "-", "changed": "~"}.get(kind, "•")
        label = item.get("label", "объект")
        if kind in ("added", "removed"):
            lines.append(f"{prefix} {label}: {item.get('message', kind)}")
        else:
            old = item.get("old") if item.get("old") not in (None, "") else "нет"
            new = item.get("new") if item.get("new") not in (None, "") else "нет"
            lines.append(f"{prefix} {label} — {item.get('field_label', item.get('field', 'поле'))}: `{old}` → `{new}`")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) != 6:
        print(f"usage: {sys.argv[0]} DATA_FILE REPORT_FILE DIFF_FILE WEBHOOK_URL HOSTNAME", file=sys.stderr)
        return 2

    data_file, report_file, diff_file, webhook_url, hostname = sys.argv[1:]
    if not webhook_url or webhook_url == "CHANGE_ME":
        return 0

    try:
        with open(data_file, encoding="utf-8") as fh:
            data = json.load(fh)
        with open(diff_file, encoding="utf-8") as fh:
            diff = json.load(fh)
        with open(report_file, encoding="utf-8") as fh:
            report = fh.read()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"PBMS Mattermost: cannot read report files: {exc}", file=sys.stderr)
        return 1

    text = unescape(re.sub(r"<[^>]+>", " ", report))
    text = re.sub(r"\s+", " ", text).strip()
    summary = f"Объектов: {len(data.get('objects', []))} · Ошибок сбора: {len(data.get('errors', []))}"
    message = f"**PBMS | {hostname}**\n\n{format_changes(diff)}\n\n**Текущий отчёт**\n{summary}\n{text}"
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH - 80].rstrip() + "\n\n_Отчёт сокращён из-за ограничения размера Mattermost._"

    payload = json.dumps({"text": message}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"HTTP {response.status}")
    except (OSError, urllib.error.URLError, RuntimeError) as exc:
        print(f"PBMS Mattermost: webhook failed: {exc}", file=sys.stderr)
        return 1

    print("PBMS: Mattermost notification sent", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
