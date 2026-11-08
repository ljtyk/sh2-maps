"""Audit mapnew scene bundles for GameObjects whose name matches a pattern
(default: spawn) and print their WORLD-frame positions.

These stripped SerializedFiles serialize the scene twice (editor frame at the
origin + real world frame) with COLLIDING path_ids between halves; PPtrs carry
m_FileID=0 only. Disambiguate a PPtr by byte-proximity: among objects sharing
the path_id, pick the one nearest to the referring object.
World frame = the transform instance whose (x,z) matches a gimmicks.json world
pos, else the non-origin instance.
Usage: audit_spawn_gimmics.py <dun> <area> [name-pattern=spawn]"""

import sh2paths
import sys, os, json
import UnityPy

ROOT = sh2paths.WIN + '/mapnew'
GIMM = json.load(open(sh2paths.oldfile('gimmicks.json'), encoding='utf-8'))

dun, area = sys.argv[1], sys.argv[2]
pat = (sys.argv[3] if len(sys.argv) > 3 else 'spawn').lower()
bundle = os.path.join(ROOT, f'{dun}_{area}_area_scenes')
if not os.path.exists(bundle):
    print(f'no bundle {bundle}')
    sys.exit(0)
env = UnityPy.load(bundle)
T, gos = [], []
for o in env.objects:
    try:
        d = o.read()
    except Exception:
        continue
    cn = type(d).__name__
    if cn == 'Transform':
        p = d.m_LocalPosition
        T.append((o.byte_start, d.m_GameObject.m_PathID, (p.x, p.y, p.z)))
    elif cn == 'GameObject':
        gos.append((o.path_id, o.byte_start, str(d.m_Name)))

by_pid = {}
for pid, bs, n in gos:
    by_pid.setdefault(pid, []).append((bs, n))

def go_name(pid, near):
    cands = by_pid.get(pid)
    if not cands:
        return '?'
    return min(cands, key=lambda c: abs(c[0] - near))[1]

world_pts = set()
for g in GIMM.get(dun, {}).get(area, []):
    p = g.get('pos')
    if p:
        world_pts.add((round(p[0], 2), round(p[2], 2)))

hits = {}
for bs, gp, p in T:
    nm = go_name(gp, bs)
    if pat in nm.lower():
        key = nm.lower().replace(' (clone)', '')
        origin = p == (0.0, 0.0, 0.0)
        wm = (round(p[0], 2), round(p[2], 2)) in world_pts and not origin
        cur = hits.get(nm)
        rank = (2 if wm else (1 if not origin else 0))
        if cur is None or rank > cur[0]:
            hits[nm] = (rank, bs, p, wm)
if not hits:
    print(f'{dun}_{area}: no matches for {pat!r}')
else:
    for nm, (rank, bs, p, wm) in sorted(hits.items()):
        tag = 'WORLD' if wm else ('origin-copy' if rank == 0 else 'other')
        print(f'{dun}_{area}: {nm}  ({p[0]:.2f},{p[1]:.2f},{p[2]:.2f})  [{tag}]')
