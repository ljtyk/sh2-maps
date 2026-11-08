# -*- coding: utf-8 -*-
"""Typed recursive string search across UnityPy bundles (scenes/demos).
Usage: scene_str_search.py <glob> <regex>"""
import sys, re, glob, UnityPy

def walk(o, out, seen, depth=0):
    if depth > 12 or o is None or id(o) in seen:
        return
    seen.add(id(o))
    if isinstance(o, str):
        out.append(o); return
    if isinstance(o, (bytes, bytearray)):
        try: out.append(o.decode('utf-8', 'ignore'))
        except Exception: pass
        return
    if isinstance(o, dict):
        for v in o.values(): walk(v, out, seen, depth+1); 
        return
    if isinstance(o, (list, tuple)):
        for v in o: walk(v, out, seen, depth+1)
        return
    d = getattr(o, '__dict__', None)
    if d:
        for v in d.values(): walk(v, out, seen, depth+1)

pat = re.compile(sys.argv[2])
for p in sorted(glob.glob(sys.argv[1])):
    if p.endswith('.manifest'): continue
    try: env = UnityPy.load(p)
    except Exception as e:
        print(p, 'LOADFAIL', e); continue
    hits = []
    for o in env.objects:
        try: d = o.read()
        except Exception: continue
        out = []
        walk(d, out, set())
        for s in out:
            if pat.search(s):
                hits.append((type(d).__name__, s[:100]))
    import os
    print(os.path.basename(p), len(hits), hits[:6] if hits else '')
