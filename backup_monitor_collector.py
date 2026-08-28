#!/usr/bin/env python3
# PBMS — проект сервиса подготовлен для публикации на https://focuslens.dev
# © 2026 FocusLens. Все права защищены.
import json,os,re,subprocess,sys
from datetime import datetime

out, backup_dir, nodes_arg, timeout_arg = sys.argv[1:]
PVESH_TIMEOUT = float(timeout_arg)
errors = []
objects = []
nodes = nodes_arg.split()

def save():
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'nodes': nodes,
            'objects': objects,
            'errors': errors
        }, fh, ensure_ascii=False, indent=2)

save()

def pvesh(path):
    print(f'PBMS: pvesh get {path}', file=sys.stderr, flush=True)
    try:
        p = subprocess.run(
            ['pvesh', 'get', path, '--output-format', 'json'],
            capture_output=True, text=True, timeout=PVESH_TIMEOUT, check=True
        )
        v = json.loads(p.stdout or '[]')
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            return [v]
        return []
    except subprocess.TimeoutExpired:
        errors.append(f'{path}: timeout after {PVESH_TIMEOUT:g}s')
        return []
    except Exception as e:
        errors.append(f'{path}: {e}')
        return []

def size(n):
    n = float(n)
    for u in ('B','K','M','G','T','P'):
        if n < 1024 or u == 'P':
            return f'{n:.1f}{u}' if u != 'B' else f'{int(n)}B'
        n /= 1024

def find_backup(kind, vmid):
    if not os.path.isdir(backup_dir):
        return None
    files = []
    for name in os.listdir(backup_dir):
        if name.startswith(f'vzdump-{kind}-{vmid}-') and not name.endswith('.log'):
            path = os.path.join(backup_dir, name)
            if os.path.isfile(path):
                files.append((os.path.getmtime(path), path, name))
    if not files:
        return None
    _, path, name = max(files)
    logpath = path + '.log'
    result = 'OK'
    if os.path.exists(logpath):
        try:
            if re.search(r'\b(error|failed|failure|critical|unable)\b', 
                         open(logpath, errors='replace').read()[-20000:].lower()):
                result = 'ERROR'
        except OSError:
            result = 'ERROR'
    return {
        'date': datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec='seconds'),
        'size': size(os.path.getsize(path)),
        'status': result,
        'file': name
    }

for node in nodes:
    print(f'PBMS: processing node {node}', file=sys.stderr, flush=True)
    for kind, endpoint, filekind in [('VM','qemu','qemu'), ('LXC','lxc','lxc')]:
        for item in pvesh(f'/nodes/{node}/{endpoint}'):
            vmid = str(item.get('vmid', item.get('id', '')))
            if not vmid:
                continue
            cfg = pvesh(f'/nodes/{node}/{endpoint}/{vmid}/config')
            cfg = cfg[0] if cfg else {}
            objects.append({
                'node': node,
                'id': vmid,
                'name': cfg.get('name') or item.get('name') or f'{kind}-{vmid}',
                'type': kind,
                'status': item.get('status', 'unknown'),
                'backup': find_backup(filekind, vmid)
            })
            save()
save()
