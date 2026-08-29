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

DATA_FILE="${PBMS_DATA_FILE:-/tmp/backup_data.json}"
REPORT_FILE="${PBMS_REPORT_FILE:-/tmp/backup_report.html}"

# Сбор данных
/usr/local/bin/backup_monitor_collector.py "$DATA_FILE" "$PBMS_BACKUP_DIR" "$PBMS_NODES" "$PBMS_PVESH_TIMEOUT"

# Генерация HTML
/usr/local/bin/backup_monitor_html.py "$DATA_FILE" "$REPORT_FILE" "$PBMS_HOSTNAME"

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

# Отправка краткого уведомления в Mattermost. Webhook не попадает в отчёт или Git.
if [[ "$PBMS_MATTERMOST_ENABLED" == "true" ]]; then
  if [[ "$PBMS_MATTERMOST_ONLY_ON_ERROR" != "true" || $(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(bool(d.get("errors") or any(not x.get("backup") or x["backup"].get("status") == "ERROR" for x in d.get("objects", [])))' "$DATA_FILE") == "True" ]]; then
    /usr/local/bin/backup_monitor_mattermost.py "$DATA_FILE" "$PBMS_MATTERMOST_WEBHOOK_URL" "$PBMS_HOSTNAME" || echo "⚠️ Mattermost notification failed" >&2
  fi
fi

echo "✅ Отчет отправлен на $PBMS_RECIPIENT"
echo "📋 Тема: $subject"
