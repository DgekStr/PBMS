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

echo "✅ Отчет отправлен на $PBMS_RECIPIENT"
echo "📋 Тема: $subject"
