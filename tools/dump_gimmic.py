"""Dump named scene objects with transforms + MonoBehaviour field ints.
Usage: dump_gimmic.py <bundle> <name_substr>"""
import sys, struct
import UnityPy

env = UnityPy.load(sys.argv[1])
pat = sys.argv[2].lower()
trs, gos, mbs = {}, [], []
for o in env.objects:
    try:
        d = o.read()
    except Exception:
        continue
    cn = type(d).__name__
    if cn == 'Transform':
        trs[o.sourceID] = (d.m_LocalPosition.x, d.m_LocalPosition.y, d.m_LocalPosition.z)
    elif cn == 'GameObject':
        gos.append((str(d.m_Name), [c.component.m_PathID for c in d.m_Component]))
    elif cn == 'MonoBehaviour':
        mbs.append((o.sourceID, d))
want = [(g, comps) for g, comps in gos if pat in g.lower()]
for g, comps in sorted(want):
    print(f'== {g}')
    for c in comps:
        if c in trs:
            p = trs[c]
            print(f'   pos=({p[0]:.2f},{p[1]:.2f},{p[2]:.2f})')
# raw ints for matching MBs (re-read via objects list)
for o in env.objects:
    try:
        d = o.read()
    except Exception:
        continue
    if type(d).__name__ != 'MonoBehaviour':
        continue
    if o.sourceID in {c for _, comps in want for c in comps}:
        raw = o.file.read_object()
        raw = raw if isinstance(raw, (bytes, bytearray)) else b''
        ints = [struct.unpack_from('<i', raw, i)[0] for i in range(0, max(0, len(raw) - 4), 4)]
        small = [v for v in ints if -2000 < v < 40000]
        print(f'   MB@{o.sourceID} ints: {small[:40]}')
