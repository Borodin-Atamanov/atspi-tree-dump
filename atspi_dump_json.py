#!/usr/bin/env python3
# Dumps the AT-SPI accessibility tree of every top-level window into JSON files.
# Each window goes to a separate file in the dumps directory, then every file is
# read back from disk and written again as one fully filtered file
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
# States that are noise for a reading agent and are always dropped from records.
NOISE_STATES = {'showing', 'visible', 'focusable', 'read-only', 'checkable'}


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
        v = acc.get_value_iface()
        if v is not None:
            data['value'] = {'current': v.get_current_value(),
                             'minimum': v.get_minimum_value(),
                             'maximum': v.get_maximum_value()}
    except Exception:
        pass
    try:
        t = acc.get_text_iface()
        if t is not None:
            n = t.get_character_count()
            if n > 0:
                data['text'] = Atspi.Text.get_text(t, 0, n)
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


def extract_records(node, parent_name, records):
    # Applies the filtering spec to one node and recurses into its children.
    states = node.get('states') or []
    name = node.get('name') or ''
    role = node.get('role') or ''

    if 'checkable' in states:
        # A switch is always recorded, with an explicit checked field, so that
        # unmarked toggles are never lost.
        record = {'role': role}
        if name:
            record['name'] = name
        record['checked'] = 'checked' in states
        if node.get('value'):
            record['value'] = node['value']
        meaningful = [s for s in states if s not in NOISE_STATES]
        if meaningful:
            record['states'] = meaningful
        records.append(record)
        child_parent = name if name else parent_name
    elif not name:
        # Technical wrapper such as a container: skip the node itself, keep the
        # parent name for its children.
        child_parent = parent_name
    elif name == parent_name:
        # Direct text duplicate of the nearest meaningful ancestor: skip it
        # without saving and without updating the parent name.
        child_parent = parent_name
    else:
        # Meaningful node: save it and propagate its name as the new parent
        # name for its children.
        record = {'role': role, 'name': name}
        if node.get('value'):
            record['value'] = node['value']
        meaningful = [s for s in states if s not in NOISE_STATES]
        if meaningful:
            record['states'] = meaningful
        records.append(record)
        child_parent = name

    for child in node.get('children', []):
        extract_records(child, child_parent, records)


def filter_window_tree(node):
    # Flattens the tree into the ordered list of meaningful records.
    records = []
    extract_records(node, '', records)
    return records


def write_filtered_dumps():
    # Reads every original dump from disk and writes its filtered variant as
    # <same name>-filtered.json next to it.
    for name in sorted(os.listdir(DUMPS_DIR)):
        if not name.endswith('.json') or name.endswith('-filtered.json'):
            continue
        src = os.path.join(DUMPS_DIR, name)
        with open(src) as f:
            tree = json.load(f)
        records = filter_window_tree(tree)
        filtered = compress_records(records)
        dest = os.path.join(DUMPS_DIR, name[:-5] + '-filtered.json')
        with open(dest, 'w') as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)
            f.write('\n')


def drop_stage2_states(records):
    # Rule 1: strip uninformative states from every record. The checked state
    # string is redundant when the boolean checked field is present.
    out = []
    for rec in records:
        states = rec.get('states')
        if not states:
            out.append(rec)
            continue
        kept = [s for s in states if s not in ('enabled', 'sensitive')]
        if 'checked' in rec:
            kept = [s for s in kept if s != 'checked']
        rec = dict(rec)
        if kept:
            rec['states'] = kept
        else:
            rec.pop('states', None)
        out.append(rec)
    return out


def drop_radio_ghosts(records):
    # Rule 2: remove an unnamed radio button that repeats the checked value of
    # the radio button directly before it in the same group.
    out = []
    prev = None
    for rec in records:
        if (rec.get('role') == 'radio button'
                and not rec.get('name')
                and prev is not None
                and prev.get('role') == 'radio button'
                and prev.get('checked') == rec.get('checked')):
            continue
        out.append(rec)
        prev = rec
    return out


def dedup_role_name(records):
    # Rule 3: keep only the first occurrence of each (role, name) pair, but never
    # remove a real switch that carries a checked field.
    seen = set()
    out = []
    for rec in records:
        name = rec.get('name')
        if name and 'checked' not in rec:
            key = (rec.get('role'), name)
            if key in seen:
                continue
            seen.add(key)
        out.append(rec)
    return out


def sidebar_node(block):
    # Builds the folded navigation node from a list item block.
    return {'role': 'sidebar categories',
            'items': [item.get('name') for item in block]}


def fold_sidebar_items(records):
    # Rule 4: fold consecutive navigation list items whose states are empty
    # after rule 1 into one sidebar categories node; headings stay separate.
    out = []
    block = []
    for rec in records:
        if rec.get('role') == 'list item' and not rec.get('states'):
            block.append(rec)
            continue
        if block:
            out.append(sidebar_node(block))
            block = []
        out.append(rec)
    if block:
        out.append(sidebar_node(block))
    return out


def compress_records(records):
    # Applies the four compression rules in order to the flat record list.
    records = drop_stage2_states(records)
    records = drop_radio_ghosts(records)
    records = dedup_role_name(records)
    records = fold_sidebar_items(records)
    return records


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
                # Every top-level child of an application is a window in the
                # AT-SPI model, so no role whitelist is applied here. Filtering
                # by role silently dropped whole window types (a modal dialog
                # was missed this way), which defeats the mission of dumping
                # every window in the system.
                window_index += 1
                tree = walk(win, 0)
                app_name = app.get_name() or 'unknown'
                window_name = win.get_name() or ''
                if not window_name:
                    window_name = '%s-%s-%d' % (app_name, role, j)
                else:
                    window_name = '%s — %s' % (app_name, window_name)
                path = unique_path(DUMPS_DIR, sanitize_file_name(window_name))
                with open(path, 'w') as f:
                    json.dump(tree, f, ensure_ascii=False, indent=2)
                    f.write('\n')
    write_filtered_dumps()
    print('dumps dir: %s' % DUMPS_DIR)
    print('windows dumped: %d' % window_index)


main()
