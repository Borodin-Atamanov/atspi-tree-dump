#!/usr/bin/env python3
import gi
import json
import time
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi

OUT = '/tmp/atspi_dump.json'
DEADLINE = time.monotonic() + 30.0
MAX_DEPTH = 30


def expired():
    return time.monotonic() > DEADLINE


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
    desktops = []
    for n in range(8):
        if expired():
            break
        try:
            d = Atspi.get_desktop(n)
        except Exception:
            break
        if d is None:
            break
        dd = {'index': n, 'role': d.get_role_name(), 'name': d.get_name() or ''}
        children = []
        try:
            nc = d.get_child_count()
        except Exception:
            nc = 0
        for i in range(nc):
            if expired():
                dd['truncated'] = True
                break
            try:
                app = d.get_child_at_index(i)
            except Exception:
                continue
            if app is not None:
                children.append(walk(app, 0))
        if children:
            dd['children'] = children
        desktops.append(dd)
    with open(OUT, 'w') as f:
        json.dump({'desktops': desktops}, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('wrote %s' % OUT)


main()
