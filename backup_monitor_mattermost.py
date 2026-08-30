#!/usr/bin/env python3
"""Send a compact, readable PBMS report and change list to Mattermost."""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime

MAX_MESSAGE_LENGTH = 12000


def clean(value, fallback="—"):
    return str(value) if value not in (None, "") else fallback


def format_date(value):
    value = clean(value)
    return value.replace("T", " ")[:16] if value != "—" else value


def format_changes(diff):
    if not diff.get("has_previous"):
        return "_Предыдущий отчёт отсутствует; текущий результат сохранён как baseline._"
    changes = diff.get("changes", [])
    summary = diff.get("summary", {})
    if not changes:
        return "_Изменений с предыдущей проверки нет._"
    lines = [
        "**🔄 Изменения с предыдущей проверки**",
        f"Добавлено: {summary.get('added', 0)} · Удалено: {summary.get('removed', 0)} · Изменено: {summary.get('changed', 0)}",
    ]
    for item in changes:
        kind = item.get("kind")
        prefix = {"added": "+", "removed": "-", "changed": "~"}.get(kind, "•")
        label = item.get("label", "объект")
        if kind in ("added", "removed"):
            lines.append(f"{prefix} {label}: {item.get('message', kind)}")
        else:
            old = clean(item.get("old"), "нет")
            new = clean(item.get("new"), "нет")
            lines.append(f"{prefix} {label} — {item.get('field_label', item.get('field', 'поле'))}: `{old}` → `{new}`")
    return "\n".join(lines)


def current_report(data, hostname):
    objects = data.get("objects", [])
    running = sum(x.get("status") == "running" for x in objects)
    backups_ok = sum(bool(x.get("backup")) and x["backup"].get("status") == "OK" for x in objects)
    backups_error = sum(bool(x.get("backup")) and x["backup"].get("status") == "ERROR" for x in objects)
    no_backup = len(objects) - backups_ok - backups_error
    lines = [
        "**📊 Текущий отчёт**",
        f"{hostname} · {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')}",
        "",
        "📈 **Статистика:**",
        f"• Всего объектов: {len(objects)} (запущено: {running})",
        f"• Бэкапы: ✅ {backups_ok} OK · ❌ {backups_error} ошибок · ⚠️ {no_backup} нет бэкапа",
        "",
        "| Нода | ID | Имя | Статус | Бэкап | Размер | Статус |",
        "|---|---:|---|---|---|---:|---|",
    ]
    for item in sorted(objects, key=lambda x: (x.get("node", ""), x.get("type", ""), str(x.get("id", "")))):
        backup = item.get("backup") or {}
        status = "🟢 running" if item.get("status") == "running" else "🔴 " + clean(item.get("status"), "unknown")
        backup_status = "✅ OK" if backup.get("status") == "OK" else "❌ ERROR" if backup.get("status") == "ERROR" else "⚠️ Нет"
        cells = [
            clean(item.get("node")), clean(item.get("id")), clean(item.get("name")), status,
            format_date(backup.get("date")), clean(backup.get("size")), backup_status,
        ]
        # Escape Markdown table delimiters so object names cannot break the layout.
        lines.append("| " + " | ".join(value.replace("|", "\\|").replace("\n", " ") for value in cells) + " |")
    if data.get("errors"):
        lines.extend(["", "⚠️ **Ошибки сбора:**", *[f"• {error}" for error in data["errors"]]])
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) != 6:
        print(f"usage: {sys.argv[0]} DATA_FILE REPORT_FILE DIFF_FILE WEBHOOK_URL HOSTNAME", file=sys.stderr)
        return 2
    data_file, _report_file, diff_file, webhook_url, hostname = sys.argv[1:]
    if not webhook_url or webhook_url == "CHANGE_ME":
        return 0
    try:
        with open(data_file, encoding="utf-8") as fh:
            data = json.load(fh)
        with open(diff_file, encoding="utf-8") as fh:
            diff = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"PBMS Mattermost: cannot read report files: {exc}", file=sys.stderr)
        return 1

    message = f"**PBMS | {hostname}**\n\n{format_changes(diff)}\n\n{current_report(data, hostname)}"
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
