#!/usr/bin/env bash
# PBMS — проект сервиса подготовлен для публикации на https://focuslens.dev
# © 2026 FocusLens. Все права защищены.
set -Eeuo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -o root -g root -m 0755 "$ROOT/backup_monitor.sh" /usr/local/bin/backup_monitor.sh
install -o root -g root -m 0755 "$ROOT/backup_monitor_collector.py" /usr/local/bin/backup_monitor_collector.py
install -o root -g root -m 0755 "$ROOT/backup_monitor_diff.py" /usr/local/bin/backup_monitor_diff.py
install -o root -g root -m 0755 "$ROOT/backup_monitor_html.py" /usr/local/bin/backup_monitor_html.py
install -o root -g root -m 0755 "$ROOT/backup_monitor_mattermost.py" /usr/local/bin/backup_monitor_mattermost.py
install -d -o root -g root -m 0750 /var/lib/pbms
install -o root -g root -m 0644 "$ROOT/backup_monitor.cron" /etc/cron.d/backup_monitor
if [[ ! -e /etc/backup_monitor.conf ]]; then
  install -o root -g root -m 0600 "$ROOT/backup_monitor.conf.example" /etc/backup_monitor.conf
  echo "Создан /etc/backup_monitor.conf; проверьте настройки перед запуском."
else
  echo "/etc/backup_monitor.conf уже существует и не изменен."
fi
echo "PBMS установлен. Запуск: /usr/local/bin/backup_monitor.sh"
