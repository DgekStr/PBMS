#!/usr/bin/env python3
import json,os,re,subprocess,sys
from datetime import datetime

out, backup_dir, nodes_arg, timeout_arg = sys.argv[1:5]
MIN_BACKUP_SIZE_MB = float(sys.argv[5]) if len(sys.argv) > 5 else 100.0
MIN_BACKUP_SIZE_BYTES = MIN_BACKUP_SIZE_MB * 1024 * 1024
PVESH_TIMEOUT = float(timeout_arg)
errors = []
objects = []
nodes = nodes_arg.split()

# ПАПКИ С БЭКАПАМИ ДЛЯ КАЖДОЙ НОДЫ (из скрина)
NODE_BACKUP_PATHS = {
    "pve": [
        "/mnt/pve/backup/dump",
    ],
    "pve2": [
        "/mnt/pve/backup/dump",
        "/mnt/hdd1/dump",
        "/mnt/hdd2/dump",
        "/var/lib/vz/dump",
    ],
    "pve3": [
        "/mnt/pve/backup/dump",
        "/mnt/pve/HDD4_1/dump",
    ],
}

# Расширения файлов бэкапов (исключаем .notes и .log)
BACKUP_EXTENSIONS = ['.vma', '.vma.zst', '.tar', '.tar.zst', '.gz', '.lzo']


def discovered_backup_paths():
    """Находит каталоги дампов Proxmox-хранилищ типа directory без использования имён хранилищ."""
    paths = []

    # Каталог-хранилище может быть смонтирован в любой путь (например
    # /mnt/pve/HDD2), поэтому идентификаторы хранилищ нельзя использовать
    # для построения путей.
    try:
        in_dir_storage = False
        with open('/etc/pve/storage.cfg', encoding='utf-8', errors='replace') as storage_cfg:
            for line in storage_cfg:
                if line.startswith('dir:'):
                    in_dir_storage = True
                    continue
                if line and not line[0].isspace():
                    in_dir_storage = False
                if in_dir_storage:
                    path_match = re.match(r'\s+path\s+(\S+)', line)
                    if path_match:
                        storage_path = path_match.group(1).rstrip('/')
                        paths.extend((os.path.join(storage_path, 'dump'), storage_path))
    except OSError:
        pass

    # Добавляем смонтированные корни Proxmox-хранилищ. Это позволяет поймать
    # точки монтирования вида /mnt/pve/HDD2 или /mnt/hdd2, даже если в
    # storage.cfg указано другое имя.
    try:
        with open('/proc/mounts', encoding='utf-8', errors='replace') as mounts:
            for line in mounts:
                fields = line.split()
                if len(fields) < 2:
                    continue
                mountpoint = fields[1].replace('\\040', ' ').replace('\\011', '\\t').rstrip('/')
                if mountpoint.startswith(('/mnt/', '/media/', '/var/lib/vz')):
                    paths.extend((os.path.join(mountpoint, 'dump'), mountpoint))
    except OSError:
        pass

    # Запасные пути для распространённых Proxmox-хранилищ, смонтированных вне
    # /mnt/pve или экспортируемых с именем хранилища, не совпадающим с путём.
    for fallback in ('/mnt/hdd2', '/mnt/hdd1', '/var/lib/vz'):
        paths.extend((os.path.join(fallback, 'dump'), fallback))

    return paths

def save():
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'nodes': nodes,
            'objects': objects,
            'errors': errors,
            'node_backup_paths': NODE_BACKUP_PATHS
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
    try:
        n = float(n)
    except:
        return '0B'
    for u in ('B','K','M','G','T','P'):
        if n < 1024 or u == 'P':
            return f'{n:.1f}{u}' if u != 'B' else f'{int(n)}B'
        n /= 1024
    return f'{n:.1f}P'

def is_backup_file(filename, kind, vmid):
    """Проверяет, является ли файл основным файлом бэкапа (не .notes и не .log)"""
    if not filename.startswith(f'vzdump-{kind}-{vmid}-'):
        return False
    if filename.endswith('.notes') or filename.endswith('.log'):
        return False
    # Проверяем расширение
    for ext in BACKUP_EXTENSIONS:
        if filename.endswith(ext):
            return True
    # Если нет известного расширения, но файл не .notes/.log — считаем бэкапом
    return True

def find_backup_for_node(kind, vmid, node):
    """Находит самый новый бэкап среди стандартных и дополнительных путей ноды."""
    best = None
    best_mtime = 0

    # PBMS_BACKUP_DIR и встроенные пути по-прежнему поддерживаются, а поиск
    # хранилищ и точек монтирования Proxmox делает поиск независимым от имён хранилищ.
    paths = []
    for path in [backup_dir, *NODE_BACKUP_PATHS.get(node, []), *discovered_backup_paths()]:
        if path and path not in paths:
            paths.append(path)

    for path in paths:
        if not os.path.isdir(path):
            continue
        try:
            for name in os.listdir(path):
                if not is_backup_file(name, kind, vmid):
                    continue
                filepath = os.path.join(path, name)
                if os.path.isfile(filepath):
                    mtime = os.path.getmtime(filepath)
                    if mtime > best_mtime:
                        best_mtime = mtime
                        best = {
                            'path': path,
                            'file': name,
                            'fullpath': filepath,
                            'mtime': mtime
                        }
        except OSError:
            continue

    if not best:
        return None

    logpath = best['fullpath'] + '.log'
    result = 'OK'
    if os.path.exists(logpath):
        try:
            if re.search(r'\b(error|failed|failure|critical|unable)\b',
                         open(logpath, errors='replace').read()[-20000:].lower()):
                result = 'ERROR'
        except OSError:
            result = 'ERROR'

    archive_size = os.path.getsize(best['fullpath'])
    too_small = archive_size < MIN_BACKUP_SIZE_BYTES
    if too_small:
        result = 'TOO_SMALL'

    return {
        'date': datetime.fromtimestamp(best['mtime']).isoformat(timespec='seconds'),
        'size': size(archive_size),
        'size_bytes': archive_size,
        'min_size_mb': MIN_BACKUP_SIZE_MB,
        'status': result,
        'file': best['file'],
        'path': best['path'],
        'size_warning': too_small
    }

for node in nodes:
    print(f'PBMS: processing node {node}', file=sys.stderr, flush=True)
    print(f'PBMS: backup paths for {node}: {NODE_BACKUP_PATHS.get(node, [])}', file=sys.stderr, flush=True)

    for kind, endpoint, filekind in [('VM','qemu','qemu'), ('LXC','lxc','lxc')]:
        for item in pvesh(f'/nodes/{node}/{endpoint}'):
            vmid = str(item.get('vmid', item.get('id', '')))
            if not vmid:
                continue
            cfg = pvesh(f'/nodes/{node}/{endpoint}/{vmid}/config')
            cfg = cfg[0] if cfg else {}

            backup_info = find_backup_for_node(filekind, vmid, node)

            objects.append({
                'node': node,
                'id': vmid,
                'name': cfg.get('name') or item.get('name') or f'{kind}-{vmid}',
                'type': kind,
                'status': item.get('status', 'unknown'),
                'backup': backup_info
            })
            save()
save()
