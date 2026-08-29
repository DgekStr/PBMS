#!/usr/bin/env python3
"""Send a concise PBMS status notification to a Mattermost incoming webhook."""
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} DATA_FILE WEBHOOK_URL HOSTNAME", file=sys.stderr)
        return 2

    data_file, webhook_url, hostname = sys.argv[1:]
    if not webhook_url or webhook_url == "CHANGE_ME":
        return 0

    try:
        with open(data_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"PBMS Mattermost: cannot read data: {exc}", file=sys.stderr)
        return 1

    objects = data.get("objects", [])
    errors = data.get("errors", [])
    failed = [item for item in objects if not item.get("backup") or item["backup"].get("status") == "ERROR"]
    running = sum(item.get("status") == "running" for item in objects)
    healthy = len(objects) - len(failed)

    lines = [
        f"**PBMS | {hostname}**",
        f"Проверка: {len(objects)} объектов, запущено: {running}, OK: {healthy}, проблем: {len(failed)}.",
    ]
    if failed:
        lines.append("**Проблемные объекты:**")
        for item in failed[:20]:
            backup = item.get("backup") or {}
            status = "нет бэкапа" if not backup else "ошибка backup"
            lines.append(f"- `{item.get('node', '—')}` / `{item.get('type', '—')}-{item.get('id', '—')}` ({item.get('name', '—')}): {status}")
        if len(failed) > 20:
            lines.append(f"- … ещё {len(failed) - 20}")
    if errors:
        lines.append("**Ошибки сбора:**")
        lines.extend(f"- {error}" for error in errors[:10])

    payload = json.dumps({"text": "\n".join(lines)}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
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
