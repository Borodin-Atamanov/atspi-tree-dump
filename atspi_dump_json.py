#!/usr/bin/env python3
import gi
import json
import os
import subprocess
import time
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DUMPS_DIR = os.path.join(BASE_DIR, 'dumps')
DEADLINE = time.monotonic() + 30.0
MAX_DEPTH = 30
WINDOW_ROLES = ('frame', 'window')


def expired():
    return time.monotonic() > DEADLINE


def folder_birth_ts(path):
    try:
        res = subprocess.run(['stat', '-c', '%W', path], capture_output=True,
                             text=True, timeout=5)
        ts = int(res.stdout.strip())
        if ts > 0:
            return ts
    except Exception:
        pass
    return os.stat(path).st_mtime


def rotate_dumps_dir():
    if not os.path.isdir(DUMPS_DIR):
        return
    import datetime
    stamp = datetime.datetime.fromtimestamp(folder_birth_ts(DUMPS_DIR)).strftime('%Y-%m-%d-%H-%M-%S')
    target = os.path.join(BASE_DIR, '%s-dumps' % stamp)
    suffix = 1
    while os.path.exists(target):
        target = os.path.join(BASE_DIR, '%s-dumps-%d' % (stamp, suffix))
        suffix += 1
    os.rename(DUMPS_DIR, target)


def safe_window_name(name, index):
    if not name:
        return 'window_%d' % index
    return name.replace('/', '_').replace('\x00', '_')


def unique_path(directory, name):
    path = os.path.join(directory, name + '.json')
    suffix = 1
    while os.path.exists(path):
        path = os.path.join(directory, '%s-%d.json' % (name, suffix))
        suffix += 1
    return path


def node_data(acc):
    data = {'role': acc.get_role_name(), 'name': acc.get_name() or ''}
    try:
        ss = acc.get_state_set()
        data['states'] = [s.value_nick for s in ss.get_states()]
    except Exception:
        pass
    try:
        data['interfaces'] = sorted(acc.get_interfaces())
    except Exception:
        pass
    try:
        attrs = acc.get_attributes()
        if isinstance(attrs, list):
            attrs = dict(attrs)
        if attrs:
            data['attributes'] = dict(attrs)
    except Exception:
        pass
    try:
        v = acc.query_value()
        data['value'] = {'current': v.get_current_value(),
                         'minimum': v.get_minimum_value(),
                         'maximum': v.get_maximum_value()}
    except Exception:
        pass
    try:
        t = acc.query_text()
        n = t.get_character_count()
        if n > 0:
            data['text'] = t.get_text(0, n)
    except Exception:
        pass
    try:
        x, y, w, h = acc.get_extents(Atspi.CoordType.SCREEN)
        data['extents'] = {'x': x, 'y': y, 'w': w, 'h': h}
    except Exception:
        pass
    return data


def walk(acc, depth):
    data = node_data(acc)
    if depth < MAX_DEPTH:
        children = []
        try:
            n = acc.get_child_count()
        except Exception:
            n = 0
        for i in range(n):
            if expired():
                data['truncated'] = True
                break
            try:
                child = acc.get_child_at_index(i)
            except Exception:
                continue
            if child is not None:
                children.append(walk(child, depth + 1))
        if children:
            data['children'] = children
    return data


def main():
    rotate_dumps_dir()
    os.makedirs(DUMPS_DIR, exist_ok=True)
    window_index = 0
    for n in range(8):
        if expired():
            break
        try:
            d = Atspi.get_desktop(n)
        except Exception:
            break
        if d is None:
            break
        try:
            napps = d.get_child_count()
        except Exception:
            napps = 0
        for i in range(napps):
            if expired():
                break
            try:
                app = d.get_child_at_index(i)
            except Exception:
                continue
            if app is None:
                continue
            try:
                nwin = app.get_child_count()
            except Exception:
                nwin = 0
            for j in range(nwin):
                if expired():
                    break
                try:
                    win = app.get_child_at_index(j)
                except Exception:
                    continue
                if win is None:
                    continue
                try:
                    role = win.get_role_name()
                except Exception:
                    role = ''
                if role not in WINDOW_ROLES:
                    continue
                window_index += 1
                tree = walk(win, 0)
                path = unique_path(DUMPS_DIR, safe_window_name(win.get_name() or '', window_index))
                with open(path, 'w') as f:
                    json.dump(tree, f, ensure_ascii=False, indent=2)
                    f.write('\n')
    print('dumps dir: %s' % DUMPS_DIR)
    print('windows dumped: %d' % window_index)


main()
