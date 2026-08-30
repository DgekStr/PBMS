#!/usr/bin/env python3
import html
import json
import sys
from datetime import datetime


data = json.load(open(sys.argv[1], encoding="utf-8"))
dest, host = sys.argv[2:4]
diff_file = sys.argv[4] if len(sys.argv) > 4 else ""
try:
    diff = json.load(open(diff_file, encoding="utf-8")) if diff_file else {}
except (OSError, json.JSONDecodeError):
    diff = {}
items = data.get("objects", [])
esc = html.escape

vm = [x for x in items if x.get("type") == "VM"]
lx = [x for x in items if x.get("type") == "LXC"]
run = lambda a: sum(x.get("status") == "running" for x in a)


def object_key(item):
    return (str(item.get("node", "")), str(item.get("type", "")), str(item.get("id", "")))


def bstatus(x):
    b = x.get("backup")
    if not b:
        return '<span class="warn">⚠️ Нет бэкапа</span>'
    if b.get("status") == "TOO_SMALL":
        return f'<span class="bad">⚠️ Слишком мал (менее {esc(str(b.get("min_size_mb", 100)).rstrip(".0"))} MB)</span>'
    return '<span class="bad">❌ Ошибка</span>' if b.get("status") == "ERROR" else '<span class="good">✅ OK</span>'


def backup_path(x):
    return (x.get("backup") or {}).get("path", "—")


def card(a, b, c):
    return f'<div class="card"><div class="card-label">{a}</div><div class="card-value">{b}</div><div class="card-sub">{c}</div></div>'


changes = diff.get("changes", [])
row_kinds = {}
changed_fields = {}
for item in changes:
    key = tuple(item.get("key", []))
    row_kinds[key] = item.get("kind", "changed")
    if item.get("field"):
        changed_fields.setdefault(key, {})[item["field"]] = item.get("severity", "neutral")


def cell(value, key, field):
    severity = changed_fields.get(key, {}).get(field)
    cls = f" changed-cell {severity}" if severity else ""
    return f'<td class="{cls.strip()}">{value}</td>' if cls else f"<td>{value}</td>"


rows = []
for x in sorted(items, key=lambda q: (q.get("node", ""), q.get("type", ""), str(q.get("id", "")))):
    key = object_key(x)
    b = x.get("backup") or {}
    row_class = {"added": "added-row", "changed": "changed-row"}.get(row_kinds.get(key), "")
    status_cls = "status-running" if x.get("status") == "running" else "status-stopped"
    rows.append(f"""
        <tr class="{row_class}">
            {cell(f'<strong>{esc(str(x.get("node", "")))}</strong>', key, "node")}
            {cell(esc(str(x.get("id", ""))), key, "id")}
            {cell(esc(str(x.get("name", ""))), key, "name")}
            <td><span class="type-badge">{esc(str(x.get("type", "")))}</span></td>
            {cell(f'<span class="{status_cls}">● {esc(str(x.get("status", "")))}</span>', key, "status")}
            {cell(esc(str(b.get("date", "—")).replace("T", " ")), key, "backup.date")}
            {cell(('<span class="bad-size">' + esc(str(b.get("size", "—"))) + '</span>') if b.get("size_warning") else esc(str(b.get("size", "—"))), key, "backup.size")}
            {cell(esc(str(backup_path(x))), key, "backup.path")}
            {cell(bstatus(x), key, "backup.status")}
        </tr>
    """)


def change_text(item):
    kind = item.get("kind")
    label = esc(item.get("label", "Объект"))
    if kind in ("added", "removed"):
        return f"<li><b>{'Добавлен' if kind == 'added' else 'Удалён'}:</b> {label}</li>"
    if kind == "stale":
        return f"<li class=\"bad\"><b>⚠️ {label}:</b> дата бэкапа не менялась более 10 дней. Нужна проверка!</li>"
    old = esc(str(item.get("old") if item.get("old") not in (None, "") else "нет"))
    new = esc(str(item.get("new") if item.get("new") not in (None, "") else "нет"))
    return f"<li><b>{label}</b>: {esc(item.get('field_label', item.get('field', 'поле')))} — {old} → {new}</li>"


summary = diff.get("summary", {})
if not diff.get("has_previous"):
    changes_html = "<p>Предыдущий отчёт отсутствует. Текущий результат сохранён как базовый.</p>"
elif changes:
    changes_html = (
        f"<p><b>Добавлено:</b> {summary.get('added', 0)} · "
        f"<b>Удалено:</b> {summary.get('removed', 0)} · "
        f"<b>Изменено:</b> {summary.get('changed', 0)}</p>"
        f"<ul>{''.join(change_text(item) for item in changes)}</ul>"
    )
else:
    changes_html = "<p>Изменений нет.</p>"

size_warnings = [
    f'Размер бэкапа на {esc(str(x.get("type", "VM")))}{esc(str(x.get("id", "")))} слишком мал '
    f'( {esc(str((x.get("backup") or {}).get("size", "—")))}; менее {esc(str((x.get("backup") or {}).get("min_size_mb", 100)).rstrip(".0"))} MB), возможны повреждения. Нужна проверка!'
    for x in items if (x.get("backup") or {}).get("size_warning")
]
err_items = [f'<li>{esc(str(e))}</li>' for e in data.get("errors", [])]
err_items.extend(f'<li class="bad">⚠️ {warning}</li>' for warning in size_warnings)
err = "".join(err_items) or "<li>Сбоев сбора нет</li>"
dt = datetime.now().astimezone().strftime("%d.%m.%Y %H:%M")

doc = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PBMS — Отчёт по бэкапам Proxmox</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f7fa; color: #1a202c; padding: 30px 20px; }}
.container {{ max-width: 1200px; margin: 0 auto; background: #fff; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,.08); padding: 32px 36px; }}
h1 {{ font-size: 26px; margin-bottom: 4px; }}
.subtitle {{ color: #718096; font-size: 15px; margin-bottom: 24px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(150px,1fr)); gap: 16px; margin-bottom: 28px; }}
.card {{ background: #f7fafc; padding: 16px 20px; border-radius: 12px; border-left: 4px solid #4299e1; }}
.card-label {{ font-size: 12px; text-transform: uppercase; color: #718096; font-weight: 600; }}
.card-value {{ font-size: 30px; font-weight: 700; color: #2d3748; margin: 4px 0 2px; }}
.card-sub {{ font-size: 13px; color: #a0aec0; }}
h2 {{ font-size: 18px; color: #2d3748; margin: 28px 0 14px; }}
.table-wrap {{ overflow-x: auto; border-radius: 12px; border: 1px solid #e2e8f0; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th {{ background: #f7fafc; padding: 12px 16px; text-align: left; color: #4a5568; border-bottom: 2px solid #e2e8f0; white-space: nowrap; }}
td {{ padding: 12px 16px; border-bottom: 1px solid #edf2f7; color: #2d3748; }}
tr:hover td {{ background: #f7fafc; }}
.changed-row td {{ background: #fff8e1; }} .added-row td {{ background: #e6ffed; }} .changed-cell {{ box-shadow: inset 0 -3px 0 #ed8936; }} .changed-cell.good {{ background: #e6ffed; box-shadow: inset 0 -3px 0 #38a169; }} .changed-cell.bad {{ background: #fff0f0; box-shadow: inset 0 -3px 0 #e53e3e; }}
.type-badge {{ display: inline-block; padding: 2px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; background: #e2e8f0; }}
.status-running,.good {{ color: #38a169; font-weight: 600; }} .status-stopped,.bad {{ color: #e53e3e; font-weight: 600; }} .warn {{ color: #dd6b20; font-weight: 600; }} .bad-size {{ color: #e53e3e; font-weight: 700; background: #fff5f5; padding: 2px 5px; border-radius: 4px; }}
.changes {{ padding: 14px 20px; background: #f0f9ff; border: 1px solid #90cdf4; border-radius: 12px; font-size: 14px; }}
.changes ul,.errors ul {{ padding-left: 20px; margin-top: 8px; }}
.errors {{ margin-top: 20px; padding: 14px 20px; background: #fffbeb; border: 1px solid #f6c23e; border-radius: 12px; color: #7b341e; font-size: 14px; }}
.footer {{ margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #a0aec0; text-align: center; }}
@media (max-width:600px) {{ .container {{ padding:20px 16px; }} th,td {{ padding:10px 12px; font-size:13px; }} }}
</style>
</head>
<body><div class="container">
<h1>📊 Отчёт по бэкапам Proxmox</h1><div class="subtitle">{esc(host)} · {dt} · Нод: {len(data.get('nodes', []))}</div>
<div class="stats">{card('VM всего', len(vm), f'{run(vm)} running · {len(vm)-run(vm)} stopped')}{card('LXC всего', len(lx), f'{run(lx)} running · {len(lx)-run(lx)} stopped')}{card('Запущено', run(items), 'виртуальных объектов')}{card('Остановлено', len(items)-run(items), 'виртуальных объектов')}{card('Всего объектов', len(items), 'VM + LXC')}</div>
<h2>🔄 Изменения с предыдущей проверки</h2><div class="changes">{changes_html}</div>
<h2>📋 Детализация объектов</h2><div class="table-wrap"><table><thead><tr><th>Нода</th><th>ID</th><th>Имя</th><th>Тип</th><th>Статус</th><th>Последний бэкап</th><th>Размер</th><th>Хранилище</th><th>Статус бэкапа</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="9" style="text-align:center;color:#a0aec0;">Объекты не найдены</td></tr>'}</tbody></table></div>
<div class="errors"><b>ℹ️ Состояние сбора</b><ul>{err}</ul></div>
<div class="footer">PBMS · Proxmox Backup Monitoring System · Dgek.ru</div>
</div></body></html>'''

with open(dest, "w", encoding="utf-8") as fh:
    fh.write(doc)
