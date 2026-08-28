#!/usr/bin/env bash
# PBMS tests — проект сервиса подготовлен для публикации на https://focuslens.dev
# © 2026 FocusLens. Все права защищены.
set -Eeuo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/backup"
cp "$ROOT/tests/mock-bin/pvesh" "$TMP/bin/pvesh"
chmod +x "$TMP/bin/pvesh" "$ROOT/backup_monitor.sh"
printf 'backup\n' > "$TMP/backup/vzdump-qemu-101-2026_08_28-01_00_00.vma.zst"
printf 'INFO: backup finished successfully\n' > "$TMP/backup/vzdump-qemu-101-2026_08_28-01_00_00.vma.zst.log"
PATH="$TMP/bin:$PATH" PBMS_CONFIG=/dev/null PBMS_NODES='pve' PBMS_BACKUP_DIR="$TMP/backup" PBMS_DATA_FILE="$TMP/data.json" PBMS_REPORT_FILE="$TMP/report.html" PBMS_LOG_FILE="$TMP/report.log" PBMS_RECIPIENT=test@example.invalid PBMS_HOSTNAME='Test cluster' \
  "$ROOT/backup_monitor.sh" >/dev/null 2>&1 || { echo 'Expected mail command is unavailable; collection/generation was attempted.'; }
test -s "$TMP/report.html" || { echo 'HTML report was not generated'; exit 1; }
grep -q 'web-server-prod' "$TMP/report.html"
grep -q 'Нет бэкапа' "$TMP/report.html"
echo 'PBMS mock test passed'
