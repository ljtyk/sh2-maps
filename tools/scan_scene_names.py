"""List object names in a scene bundle (raw byte scan; UnityPy exposes no
names for objects in area_scenes bundles).
Usage: scan_scene_names.py <bundle> [substr]"""
import sys
import re
import UnityPy

env = UnityPy.load(sys.argv[1])
pat = sys.argv[2].lower() if len(sys.argv) > 2 else None
names = {}
objs = env.objects
if callable(objs):
    objs = list(objs)
for o in objs:
    try:
        raw = o.file.read_object()
        raw = raw if isinstance(raw, (bytes, bytearray)) else b''
    except Exception:
        raw = b''
    if not raw:
        continue
    for m in re.finditer(rb'[\x20-\x7e]{6,}', bytes(raw)):
        s = m.group().decode()
        if pat and pat not in s.lower():
            continue
        if any(ch.isalpha() for ch in s):
            names[s] = names.get(s, 0) + 1
for s, c in sorted(names.items()):
    print(f'{c:4d}  {s}')
