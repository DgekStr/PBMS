#!/usr/bin/env python3
"""Send the generated PBMS HTML report to a Mattermost incoming webhook."""
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    if len(sys.argv) != 5:
        print(f"usage: {sys.argv[0]} DATA_FILE REPORT_FILE WEBHOOK_URL HOSTNAME", file=sys.stderr)
        return 2

    data_file, report_file, webhook_url, hostname = sys.argv[1:]
    if not webhook_url or webhook_url == "CHANGE_ME":
        return 0

    try:
        with open(data_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"PBMS Mattermost: cannot read data: {exc}", file=sys.stderr)
        return 1

    try:
        with open(report_file, encoding="utf-8") as fh:
            report = fh.read()
    except OSError as exc:
        print(f"PBMS Mattermost: cannot read report: {exc}", file=sys.stderr)
        return 1

    # Mattermost Incoming Webhook accepts Markdown, not an HTML email body.
    # Send a readable summary plus the complete generated report as an attachment.
    from html import unescape
    import re

    text = unescape(re.sub(r"<[^>]+>", " ", report))
    text = re.sub(r"\s+", " ", text).strip()
    payload = json.dumps({
        "text": f"**PBMS | {hostname}**\n\n{text}",
    }, ensure_ascii=False).encode("utf-8")
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
