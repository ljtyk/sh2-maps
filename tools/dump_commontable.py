import sh2paths
# -*- coding: utf-8 -*-
"""Dump every MonoBehaviour table in _commontable.dec to JSON (Task E).

The bundle carries full IL2CPP class metadata, so UnityPy `o.read()`
yields TYPED fields directly (verified on QuestData/EnemyTable/
CharParamTable) — no raw-byte parsing needed.

Output: re/out/commontable.json
  { '<ScriptName>': [ {field: value, ...}, ... ] }   (one entry per object)
UnknownObject / nested structs are converted recursively to plain dicts.

Run:  "$PY" -X utf8 re/tools/dump_commontable.py [ScriptName ...]
      (optional filter: only dump the named scripts)
"""
import os
import sys
import json
import UnityPy

SRC = sh2paths.commontable_dec()
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'commontable.json')


def conv(v, depth=0):
    if depth > 8:
        return repr(v)
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        return [conv(x, depth + 1) for x in v]
    if hasattr(v, 'read'):
        try:
            r = v.read()
            return conv(r, depth + 1)
        except Exception:
            return repr(v)
    if hasattr(v, 'vars') or True:
        try:
            vs = vars(v)
        except TypeError:
            vs = None
        if vs is not None:
            out = {}
            for k, x in vs.items():
                if k.startswith('_') and k not in ('_flags',):
                    continue
                if k in ('object_reader',):
                    continue
                out[k] = conv(x, depth + 1)
            if out:
                return out
    try:
        return float(v)
    except Exception:
        return repr(v)


def main():
    filt = sys.argv[1:]
    env = UnityPy.load(SRC)
    data = {}
    for o in env.objects:
        if o.type != 114:
            continue
        d = o.read()
        try:
            nm = d.m_Script.read().m_Name
        except Exception:
            nm = '?'
        if filt and nm not in filt:
            continue
        row = {}
        for k, v in vars(d).items():
            if k in ('m_Enabled', 'm_GameObject', 'm_Name', 'm_Script', 'object_reader'):
                continue
            row[k] = conv(v)
        data.setdefault(nm, []).append(row)
    for nm in data:
        print(f'{nm}: {len(data[nm])} rows')
    json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print('saved', OUT)


if __name__ == '__main__':
    main()
