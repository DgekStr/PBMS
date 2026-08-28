#!/usr/bin/env python3
# PBMS — проект сервиса подготовлен для публикации на https://focuslens.dev
# © 2026 FocusLens. Все права защищены.
import html,json,sys
from datetime import datetime

data = json.load(open(sys.argv[1]))
dest, host = sys.argv[2:]
items = data['objects']
esc = html.escape

vm = [x for x in items if x['type'] == 'VM']
lx = [x for x in items if x['type'] == 'LXC']
run = lambda a: sum(x['status'] == 'running' for x in a)

def bstatus(x):
    b = x.get('backup')
    if not b:
        return '<span class="warn">⚠️ Нет бэкапа</span>'
    return '<span class="bad">❌ Ошибка</span>' if b['status'] == 'ERROR' else '<span class="good">✅ OK</span>'

def card(a, b, c):
    return f'<div class="card"><div class="card-label">{a}</div><div class="card-value">{b}</div><div class="card-sub">{c}</div></div>'

rows = []
for x in sorted(items, key=lambda q: (q['node'], q['type'], q['id'])):
    b = x.get('backup') or {}
    cls = 'status-running' if x['status'] == 'running' else 'status-stopped'
    rows.append(f"""
        <tr>
            <td><strong>{esc(x['node'])}</strong></td>
            <td>{esc(x['id'])}</td>
            <td>{esc(x['name'])}</td>
            <td><span class="type-badge">{x['type']}</span></td>
            <td><span class="{cls}">● {esc(x['status'])}</span></td>
            <td>{esc(b.get('date', '—').replace('T', ' '))}</td>
            <td>{esc(b.get('size', '—'))}</td>
            <td>{bstatus(x)}</td>
        </tr>
    """)

err = ''.join(f'<li>{esc(e)}</li>' for e in data['errors']) or '<li>Сбоев сбора нет</li>'
dt = datetime.now().astimezone().strftime('%d.%m.%Y %H:%M')

doc = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PBMS — Отчет по бэкапам Proxmox</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #f5f7fa;
            color: #1a202c;
            padding: 30px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            padding: 32px 36px;
        }}
        h1 {{
            font-size: 26px;
            font-weight: 700;
            color: #1a202c;
            margin-bottom: 4px;
        }}
        .subtitle {{
            color: #718096;
            font-size: 15px;
            margin-bottom: 24px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .card {{
            background: #f7fafc;
            padding: 16px 20px;
            border-radius: 12px;
            border-left: 4px solid #4299e1;
        }}
        .card-label {{
            font-size: 12px;
            text-transform: uppercase;
            color: #718096;
            font-weight: 600;
            letter-spacing: 0.3px;
        }}
        .card-value {{
            font-size: 30px;
            font-weight: 700;
            color: #2d3748;
            margin: 4px 0 2px;
        }}
        .card-sub {{
            font-size: 13px;
            color: #a0aec0;
        }}
        .card:nth-child(2) {{ border-left-color: #9f7aea; }}
        .card:nth-child(3) {{ border-left-color: #48bb78; }}
        .card:nth-child(4) {{ border-left-color: #fc8181; }}
        .card:nth-child(5) {{ border-left-color: #ed8936; }}

        h2 {{
            font-size: 18px;
            font-weight: 600;
            color: #2d3748;
            margin: 28px 0 14px;
        }}
        .table-wrap {{
            overflow-x: auto;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th {{
            background: #f7fafc;
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            color: #4a5568;
            border-bottom: 2px solid #e2e8f0;
            white-space: nowrap;
        }}
        td {{
            padding: 12px 16px;
            border-bottom: 1px solid #edf2f7;
            color: #2d3748;
        }}
        tr:hover td {{
            background: #f7fafc;
        }}
        .type-badge {{
            display: inline-block;
            padding: 2px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            background: #e2e8f0;
            color: #2d3748;
        }}
        .type-badge:contains("VM") {{ background: #bee3f8; color: #2a4365; }}
        .type-badge:contains("LXC") {{ background: #e9d8fd; color: #44337a; }}
        .status-running {{ color: #38a169; font-weight: 600; }}
        .status-stopped {{ color: #e53e3e; font-weight: 600; }}
        .good {{ color: #38a169; font-weight: 600; }}
        .bad {{ color: #e53e3e; font-weight: 600; }}
        .warn {{ color: #dd6b20; font-weight: 600; }}
        .errors {{
            margin-top: 20px;
            padding: 14px 20px;
            background: #fffbeb;
            border: 1px solid #f6c23e;
            border-radius: 12px;
            color: #7b341e;
            font-size: 14px;
        }}
        .errors ul {{
            padding-left: 20px;
            margin-top: 6px;
        }}
        .footer {{
            margin-top: 24px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
            font-size: 13px;
            color: #a0aec0;
            text-align: center;
        }}
        @media (max-width: 600px) {{
            .container {{ padding: 20px 16px; }}
            .stats {{ grid-template-columns: repeat(2, 1fr); }}
            th, td {{ padding: 10px 12px; font-size: 13px; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <h1>📊 Отчет по бэкапам Proxmox</h1>
    <div class="subtitle">{esc(host)} · {dt} · Нод: {len(data['nodes'])}</div>

    <div class="stats">
        {card('VM всего', len(vm), f'{run(vm)} running · {len(vm)-run(vm)} stopped')}
        {card('LXC всего', len(lx), f'{run(lx)} running · {len(lx)-run(lx)} stopped')}
        {card('Запущено', run(items), 'виртуальных объектов')}
        {card('Остановлено', len(items)-run(items), 'виртуальных объектов')}
        {card('Всего объектов', len(items), 'VM + LXC')}
    </div>

    <h2>📋 Детализация объектов</h2>
    <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>Нода</th>
                    <th>ID</th>
                    <th>Имя</th>
                    <th>Тип</th>
                    <th>Статус</th>
                    <th>Последний бэкап</th>
                    <th>Размер</th>
                    <th>Статус бэкапа</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows) or '<tr><td colspan="8" style="text-align:center;color:#a0aec0;">Объекты не найдены</td></tr>'}
            </tbody>
        </table>
    </div>

    <div class="errors">
        <b>ℹ️ Состояние сбора</b>
        <ul>{err}</ul>
    </div>

    <div class="footer">
        PBMS · Proxmox Backup Monitoring System · <a href="https://focuslens.dev">focuslens.dev</a>
        <br>© 2026 FocusLens. Все права защищены.
    </div>
</div>
</body>
</html>'''

open(dest, 'w', encoding='utf-8').write(doc)
