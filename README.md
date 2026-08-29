# PBMS — Proxmox Backup Monitoring System

> Проект сервиса подготовлен для публикации на [focuslens.dev](https://focuslens.dev).
> © 2026 FocusLens. Все права защищены.

Минималистичный мониторинг резервных копий виртуальных машин и контейнеров в Proxmox VE 7/8. PBMS получает список VM/LXC через `pvesh`, ищет последние файлы `vzdump-*`, проверяет связанные `.log`, формирует HTML-отчёт и отправляет его через локально настроенный MTA, например `msmtp`.

![Пример HTML-отчёта PBMS](accets/demo.png)

> Проект предназначен для запуска непосредственно на ноде Proxmox от имени `root`.

## Возможности

- сбор VM и LXC с нескольких Proxmox-нод;
- определение последнего backup-файла для каждого объекта;
- отображение даты, размера и статуса резервной копии;
- анализ последних 20 000 символов `.log` на признаки ошибок;
- отдельная фиксация ошибок и таймаутов `pvesh`;
- постепенное сохранение JSON во время сбора;
- адаптивный HTML-отчёт для письма;
- защита от публикации локальных конфигураций и runtime-файлов;
- поиск backup-файлов в нескольких хранилищах для каждой ноды;
- mock-тест без установленного Proxmox.

## Структура

| Файл | Назначение |
|---|---|
| [`backup_monitor.sh`](backup_monitor.sh) | Оркестрация сбора, генерации отчёта, отправки письма и Mattermost-уведомления |
| [`backup_monitor_collector.py`](backup_monitor_collector.py) | Сбор данных через `pvesh` и поиск backup-файлов |
| [`backup_monitor_html.py`](backup_monitor_html.py) | Генерация HTML |
| [`backup_monitor_mattermost.py`](backup_monitor_mattermost.py) | Отправка краткого статуса в Mattermost через Incoming Webhook |
| [`backup_monitor.conf.example`](backup_monitor.conf.example) | Публичный шаблон конфигурации PBMS |
| [`msmtprc.example`](msmtprc.example) | Публичный шаблон конфигурации SMTP без учётных данных |
| [`backup_monitor.cron`](backup_monitor.cron) | Ежедневный запуск в 09:00 |
| [`install.sh`](install.sh) | Установка скриптов и cron-задачи |
| [`tests/test_mock.sh`](tests/test_mock.sh) | Локальная проверка с mock `pvesh` |
| [`.gitignore`](.gitignore) | Исключение рабочих конфигов, секретов и артефактов |

## Требования

- Proxmox VE 7 или 8;
- Bash;
- Python 3;
- `pvesh` и права `root`;
- `msmtp` либо совместимая команда, принимающая сообщение через `-t`;
- `curl` не требуется: Mattermost отправляется стандартной библиотекой Python;
- доступ к каталогу хранения backup-файлов.

Для установки зависимостей на Debian/Proxmox:

```bash
apt install python3 msmtp
```

## Установка через Git

На чистой ноде Proxmox установите Git, клонируйте репозиторий и запустите установщик от имени `root`:

```bash
apt update
apt install -y git python3 msmtp
sudo git clone https://github.com/DgekStr/PBMS.git /opt/PBMS
cd /opt/PBMS
sudo ./install.sh
```

Затем заполните конфигурацию:

```bash
sudo editor /etc/backup_monitor.conf
sudo chmod 600 /etc/backup_monitor.conf
sudo /usr/local/bin/backup_monitor.sh
```

Для обновления существующей установки:

```bash
cd /opt/PBMS
sudo git pull --ff-only origin main
sudo ./install.sh
```

`install.sh` устанавливает скрипты в `/usr/local/bin`, cron-файл в `/etc/cron.d/backup_monitor`, а конфигурацию копирует только если `/etc/backup_monitor.conf` ещё не существует. Рабочая конфигурация при обновлении не перезаписывается.

## Настройка PBMS

Скопируйте [`backup_monitor.conf.example`](backup_monitor.conf.example) и замените все значения `CHANGE_ME`:

- `PBMS_NODES` — имена нод через пробел;
- `PBMS_BACKUP_DIR` — каталог backup-файлов;
- `PBMS_RECIPIENT` — адрес получателя отчёта;
- `PBMS_SENDER` — адрес отправителя;
- `PBMS_SMTP_BIN` — команда MTA;
- `PBMS_PVESH_TIMEOUT` — таймаут одного запроса `pvesh` в секундах;
- `PBMS_MAX_RUNTIME` — зарезервированная настройка общего лимита запуска;
- `PBMS_DEBUG_FILE` — путь диагностического лога;
- `PBMS_HOSTNAME` — подпись кластера в отчёте;
- `PBMS_MATTERMOST_ENABLED` — включение уведомлений Mattermost (`true`/`false`);
- `PBMS_MATTERMOST_WEBHOOK_URL` — Incoming Webhook URL, хранить только в локальном конфиге;
- `PBMS_MATTERMOST_ONLY_ON_ERROR` — отправлять уведомление только при проблемах (`true`/`false`).

По умолчанию коллектор ищет backup-файлы в следующих хранилищах:

- `pve`: `/mnt/pve/backup/dump`;
- `pve2`: `/mnt/pve/backup/dump`, `/mnt/hdd1/dump`, `/mnt/hdd2/dump`, `/var/lib/vz/dump`;
- `pve3`: `/mnt/pve/backup/dump`, `/mnt/pve/HDD4_1/dump`.

Пути заданы в [`backup_monitor_collector.py`](backup_monitor_collector.py) и должны быть изменены под фактическую схему хранилищ кластера до установки.

SMTP-профиль создаётся отдельно на сервере. Используйте [`msmtprc.example`](msmtprc.example) как основу, затем сохраните рабочий файл с правами `600`, например `/root/.msmtprc`. Рабочие адреса, логины и пароли не должны попадать в репозиторий.

Для отправки уведомлений в Mattermost добавьте настоящий webhook только в `/etc/backup_monitor.conf`, например:

```bash
PBMS_MATTERMOST_ENABLED="true"
PBMS_MATTERMOST_WEBHOOK_URL="https://chat.example/hooks/REPLACE_ME"
PBMS_MATTERMOST_ONLY_ON_ERROR="false"
```

Webhook является секретом: не вставляйте его в README, example-файлы, issue или командную строку. Если URL уже был опубликован, после тестирования отзовите его в Mattermost и создайте новый.

## Логика проверки

Для каждого VM/LXC PBMS выбирает самый новый файл с префиксом `vzdump-qemu-ID-` или `vzdump-lxc-ID-`. Если рядом существует `.log`, последние 20 000 символов проверяются по словам `error`, `failed`, `failure`, `critical` и `unable`. Результат имеет статус `OK`, `ERROR` или «Нет бэкапа».

При таймауте или ошибке одной ноды сбор продолжается для остальных объектов, а проблема попадает в блок «Состояние сбора» отчёта.

## Запуск

```bash
/usr/local/bin/backup_monitor.sh
cat /tmp/backup_report.html
```

После установки cron запускает PBMS ежедневно в 09:00. Расписание можно изменить в `/etc/cron.d/backup_monitor`.

## Тестирование без Proxmox

Тест использует mock `pvesh`, временный каталог и демонстрационные backup-файлы:

```bash
bash tests/test_mock.sh
```

Тест проверяет генерацию HTML и наличие данных mock-объектов. Отправка почты в тестовом окружении намеренно может завершиться ошибкой, поскольку MTA не требуется для проверки сбора и генерации. Уведомления Mattermost в mock-тесте не отправляются.

## Безопасность перед публикацией

- [`backup_monitor.conf`](backup_monitor.conf) — локальный рабочий конфиг и намеренно исключён из Git;
- `.msmtprc`, `msmtprc` и `.env*` исключены из Git;
- в публичных example-файлах используются только `CHANGE_ME` и `example.com`;
- перед первым push проверьте историю Git и не добавляйте рабочий SMTP-профиль;
- если секрет уже попал в историю, его необходимо отозвать/заменить и очистить историю отдельно.

## Авторские права

Проект сервиса подготовлен компанией [FocusLens](https://focuslens.dev). © 2026 FocusLens. Все права защищены.
