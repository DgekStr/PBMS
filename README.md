# PBMS — Proxmox Backup Monitoring System

> Проект сервиса подготовлен для публикации на [focuslens.dev](https://focuslens.dev).
> © 2026 FocusLens. Все права защищены.

Минималистичный мониторинг резервных копий виртуальных машин и контейнеров в Proxmox VE 7/8. PBMS получает список VM/LXC через `pvesh`, ищет последние файлы `vzdump-*`, проверяет связанные `.log`, формирует HTML-отчёт и отправляет его через локально настроенный MTA, например `msmtp`.

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
- mock-тест без установленного Proxmox.

## Структура

| Файл | Назначение |
|---|---|
| [`backup_monitor.sh`](backup_monitor.sh) | Оркестрация сбора, генерации отчёта и отправки письма |
| [`backup_monitor_collector.py`](backup_monitor_collector.py) | Сбор данных через `pvesh` и поиск backup-файлов |
| [`backup_monitor_html.py`](backup_monitor_html.py) | Генерация HTML |
| [`backup_monitor.conf.example`](backup_monitor.conf.example) | Публичный шаблон конфигурации PBMS |
| [`msmtprc.example`](msmtprc.example) | Публичный шаблон конфигурации SMTP без учётных данных |
| [`backup_monitor.cron`](backup_monitor.cron) | Ежедневный запуск в 08:00 |
| [`install.sh`](install.sh) | Установка скриптов и cron-задачи |
| [`tests/test_mock.sh`](tests/test_mock.sh) | Локальная проверка с mock `pvesh` |
| [`.gitignore`](.gitignore) | Исключение рабочих конфигов, секретов и артефактов |

## Требования

- Proxmox VE 7 или 8;
- Bash;
- Python 3;
- `pvesh` и права `root`;
- `msmtp` либо совместимая команда, принимающая сообщение через `-t`;
- доступ к каталогу хранения backup-файлов.

Для установки зависимостей на Debian/Proxmox:

```bash
apt install python3 msmtp
```

## Установка

```bash
cd /path/to/PBMS
cp backup_monitor.conf.example /etc/backup_monitor.conf
chmod 600 /etc/backup_monitor.conf
editor /etc/backup_monitor.conf
chmod +x install.sh backup_monitor.sh
./install.sh
```

`install.sh` устанавливает основной скрипт в `/usr/local/bin`, cron-файл в `/etc/cron.d`, а конфигурацию копирует только если `/etc/backup_monitor.conf` ещё не существует.

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
- `PBMS_HOSTNAME` — подпись кластера в отчёте.

SMTP-профиль создаётся отдельно на сервере. Используйте [`msmtprc.example`](msmtprc.example) как основу, затем сохраните рабочий файл с правами `600`, например `/root/.msmtprc`. Рабочие адреса, логины и пароли не должны попадать в репозиторий.

## Логика проверки

Для каждого VM/LXC PBMS выбирает самый новый файл с префиксом `vzdump-qemu-ID-` или `vzdump-lxc-ID-`. Если рядом существует `.log`, последние 20 000 символов проверяются по словам `error`, `failed`, `failure`, `critical` и `unable`. Результат имеет статус `OK`, `ERROR` или «Нет бэкапа».

При таймауте или ошибке одной ноды сбор продолжается для остальных объектов, а проблема попадает в блок «Состояние сбора» отчёта.

## Запуск

```bash
/usr/local/bin/backup_monitor.sh
cat /tmp/backup_report.html
```

После установки cron запускает PBMS ежедневно в 08:00. Расписание можно изменить в `/etc/cron.d/backup_monitor`.

## Тестирование без Proxmox

Тест использует mock `pvesh`, временный каталог и демонстрационные backup-файлы:

```bash
bash tests/test_mock.sh
```

Тест проверяет генерацию HTML и наличие данных mock-объектов. Отправка почты в тестовом окружении намеренно может завершиться ошибкой, поскольку MTA не требуется для проверки сбора и генерации.

## Безопасность перед публикацией

- [`backup_monitor.conf`](backup_monitor.conf) — локальный рабочий конфиг и намеренно исключён из Git;
- `.msmtprc`, `msmtprc` и `.env*` исключены из Git;
- в публичных example-файлах используются только `CHANGE_ME` и `example.com`;
- перед первым push проверьте историю Git и не добавляйте рабочий SMTP-профиль;
- если секрет уже попал в историю, его необходимо отозвать/заменить и очистить историю отдельно.

## Авторские права

Проект сервиса подготовлен компанией [FocusLens](https://focuslens.dev). © 2026 FocusLens. Все права защищены, но нам не жалко - забирайте :)

Лицензия пока не задана. Перед публичной публикацией добавьте файл `LICENSE` с выбранными условиями использования.
