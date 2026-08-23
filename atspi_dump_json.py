#!/usr/bin/env python3
# Dumps the AT-SPI accessibility tree of every top-level window into JSON files.
# Each window goes to a separate file in the dumps directory, then every file is
# read back from disk and written again as a token-lean variant
# <same name>-filtered.json.

import gi
import json
import os
import subprocess
import time

gi.require_version('Atspi', '2.0')
from gi.repository import Atspi

# Script location is the base for the dumps directory.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DUMPS_DIR = os.path.join(BASE_DIR, 'dumps')
# Overall time budget so a stuck application cannot hang the run forever.
DEADLINE = time.monotonic() + 30.0
# Safety cap against pathological nesting depth.
MAX_DEPTH = 30
# Roles that identify a top-level window of an application.
WINDOW_ROLES = ('frame', 'window')
# States that are near-universal on KDE and carry no information for an agent.
BOILER_STATES = {'enabled', 'sensitive'}


def expired():
    # True once the overall time budget is spent.
    return time.monotonic() > DEADLINE


def folder_birth_ts(path):
    # Returns the creation time of a directory. The stat command exposes the
    # birth time on Linux; os.stat does not, so mtime is the fallback.
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
    # Keeps one live dumps directory. A previous run is archived as
    # <creation-time>-dumps in the project datetime format YYYY-MM-DD-HH-MM-SS.
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


def sanitize_file_name(name):
    # Removes characters that are not allowed or are misleading in file names.
    return name.replace('/', '_').replace('\x00', '_')


def unique_path(directory, name):
    # Returns a non-colliding path by appending a counter when the name is taken.
    path = os.path.join(directory, name + '.json')
    suffix = 1
    while os.path.exists(path):
        path = os.path.join(directory, '%s-%d.json' % (name, suffix))
        suffix += 1
    return path


def node_data(acc):
    # Converts one AT-SPI accessible into a plain dict with the raw values.
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
    # Builds the tree below an accessible by recursing into its children.
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


def is_decorative_leaf(node):
    # A leaf that carries no readable data for an agent: no name, text, value,
    # coordinates, and at most boilerplate states. Such nodes are pure layout.
    if node.get('children'):
        return False
    if node.get('name') or node.get('text') or node.get('value') or node.get('extents'):
        return False
    states = node.get('states') or []
    return not (set(states) - BOILER_STATES)


def is_bare_filler(node):
    # A filler container that holds no own data, only a single child.
    return node.get('role') == 'filler' and set(node.keys()) == {'role'}


def lean_node(node):
    # Keeps only fields that carry meaning for a reading agent. Interfaces are
    # derivable from role plus value and text, so they are dropped. Boilerplate
    # states are dropped as well.
    out = {}
    role = node.get('role')
    if role:
        out['role'] = role
    name = node.get('name')
    if name:
        out['name'] = name
    states = [s for s in (node.get('states') or []) if s not in BOILER_STATES]
    if states:
        out['states'] = states
    for field in ('value', 'text', 'extents'):
        if node.get(field):
            out[field] = node[field]
    return out


def filter_window_tree(node):
    # Produces the token-lean version of a window tree: decorative leaves are
    # dropped, single-child fillers are collapsed, and each node is stripped of
    # derivable and boilerplate fields.
    if is_decorative_leaf(node):
        return None
    children = []
    for child in node.get('children', []):
        filtered_child = filter_window_tree(child)
        if filtered_child is not None:
            children.append(filtered_child)
    node = lean_node(node)
    if children:
        if len(children) == 1 and is_bare_filler(node):
            return children[0]
        node['children'] = children
    elif set(node.keys()) == {'role'}:
        # No own data and no surviving children, so it is pure structure.
        return None
    return node


def write_filtered_dumps():
    # Reads every original dump from disk and writes its filtered variant as
    # <same name>-filtered.json next to it.
    for name in sorted(os.listdir(DUMPS_DIR)):
        if not name.endswith('.json') or name.endswith('-filtered.json'):
            continue
        src = os.path.join(DUMPS_DIR, name)
        with open(src) as f:
            tree = json.load(f)
        filtered = filter_window_tree(tree)
        dest = os.path.join(DUMPS_DIR, name[:-5] + '-filtered.json')
        with open(dest, 'w') as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)
            f.write('\n')


def main():
    # Moves a previous dumps directory aside, then dumps every top-level window
    # into its own file and finally writes the filtered variants from disk.
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
                window_name = win.get_name() or ''
                if not window_name:
                    window_name = '%s-%s-%d' % (app.get_name() or 'unknown', role, j)
                path = unique_path(DUMPS_DIR, sanitize_file_name(window_name))
                with open(path, 'w') as f:
                    json.dump(tree, f, ensure_ascii=False, indent=2)
                    f.write('\n')
    write_filtered_dumps()
    print('dumps dir: %s' % DUMPS_DIR)
    print('windows dumped: %d' % window_index)


main()
