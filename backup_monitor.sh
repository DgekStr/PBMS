#!/bin/bash
# PBMS - Proxmox Backup Monitoring System
# Сбор данных, генерация HTML и отправка на почту

# Конфигурация
CONFIG_FILE="${PBMS_CONFIG:-/etc/backup_monitor.conf}"
[[ -r "$CONFIG_FILE" ]] && source "$CONFIG_FILE"

: "${PBMS_NODES:=pve pve2 pve3}"
: "${PBMS_BACKUP_DIR:=/mnt/pve/backup/dump}"
: "${PBMS_RECIPIENT:=CHANGE_ME@example.com}"
: "${PBMS_SENDER:=CHANGE_ME@example.com}"
: "${PBMS_HOSTNAME:=Proxmox cluster}"
: "${PBMS_SMTP_BIN:=msmtp}"
: "${PBMS_PVESH_TIMEOUT:=15}"
: "${PBMS_MATTERMOST_ENABLED:=false}"
: "${PBMS_MATTERMOST_WEBHOOK_URL:=CHANGE_ME}"
: "${PBMS_MATTERMOST_ONLY_ON_ERROR:=false}"
: "${PBMS_PREVIOUS_DATA_FILE:=/var/lib/pbms/previous_backup_data.json}"

DATA_FILE="${PBMS_DATA_FILE:-/tmp/backup_data.json}"
REPORT_FILE="${PBMS_REPORT_FILE:-/tmp/backup_report.html}"
CHANGES_FILE="${PBMS_CHANGES_FILE:-/tmp/backup_changes.json}"

# Сбор данных
/usr/local/bin/backup_monitor_collector.py "$DATA_FILE" "$PBMS_BACKUP_DIR" "$PBMS_NODES" "$PBMS_PVESH_TIMEOUT"

# Сравнение с предыдущим завершённым сбором
/usr/local/bin/backup_monitor_diff.py "$PBMS_PREVIOUS_DATA_FILE" "$DATA_FILE" "$CHANGES_FILE"

# Генерация HTML
/usr/local/bin/backup_monitor_html.py "$DATA_FILE" "$REPORT_FILE" "$PBMS_HOSTNAME" "$CHANGES_FILE"

# Отправка письма
CURRENT_DATE=$(date '+%d.%m.%Y')
CURRENT_TIME=$(date '+%H:%M:%S')
subject="PROXMOX Cluster | Отчёт о состоянии на $CURRENT_DATE $CURRENT_TIME"

encode_rfc2047(){
  printf '=?UTF-8?B?%s?=' "$(printf '%s' "$1" | base64 -w 0)"
}

{
  printf 'From: %s\n' "$PBMS_SENDER"
  printf 'To: %s\n' "$PBMS_RECIPIENT"
  printf 'Subject: %s\n' "$(encode_rfc2047 "$subject")"
  printf 'MIME-Version: 1.0\n'
  printf 'Content-Type: text/html; charset=UTF-8\n'
  printf 'Content-Transfer-Encoding: 8bit\n\n'
  cat "$REPORT_FILE"
} | "$PBMS_SMTP_BIN" -t

# Отправка актуального отчёта и списка изменений в Mattermost.
if [[ "$PBMS_MATTERMOST_ENABLED" == "true" ]]; then
  if [[ "$PBMS_MATTERMOST_ONLY_ON_ERROR" != "true" || $(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(bool(d.get("errors") or any(not x.get("backup") or x["backup"].get("status") == "ERROR" for x in d.get("objects", [])))' "$DATA_FILE") == "True" ]]; then
    /usr/local/bin/backup_monitor_mattermost.py "$DATA_FILE" "$REPORT_FILE" "$CHANGES_FILE" "$PBMS_MATTERMOST_WEBHOOK_URL" "$PBMS_HOSTNAME" || echo "⚠️ Mattermost notification failed" >&2
  fi
fi

# Обновляем baseline только после подготовки отчёта и уведомлений.
state_dir=$(dirname -- "$PBMS_PREVIOUS_DATA_FILE")
install -d -m 0750 "$state_dir"
tmp_state="${PBMS_PREVIOUS_DATA_FILE}.tmp.$$"
install -m 0600 "$DATA_FILE" "$tmp_state"
mv -f -- "$tmp_state" "$PBMS_PREVIOUS_DATA_FILE"

echo "✅ Отчет отправлен на $PBMS_RECIPIENT"
echo "📋 Тема: $subject"
