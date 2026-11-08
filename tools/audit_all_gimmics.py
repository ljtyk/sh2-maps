"""Typed audit of ALL Gimmic_*/MapGimmic* GameObjects in every mapnew scene
bundle, with world-frame positions (same parser rules as
extract_enemy_spawns v2: transform stream split at largest byte gap; pid-set
membership by GO name; parent chains within block; drop (0,0,0); dedupe tol 1).
Usage: audit_all_gimmics.py [out.json]"""

import sh2paths
import sys, os, json, collections
import numpy as np
import UnityPy

GAME = sh2paths.WIN + '/mapnew'
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'out', 'gimmics_all.json')

def mat4(t):
    e = np.eye(4)
    e[0, 0] = t.m_LocalScale.x; e[1, 1] = t.m_LocalScale.y; e[2, 2] = t.m_LocalScale.z
    x, y, z, w = t.m_LocalRotation.x, t.m_LocalRotation.y, t.m_LocalRotation.z, t.m_LocalRotation.w
    R = np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)]])
    e[:3, :3] = R
    e[:3, 3] = [t.m_LocalPosition.x, t.m_LocalPosition.y, t.m_LocalPosition.z]
    return e

def extract(path):
    env = UnityPy.load(path)
    trs, gos = [], []
    for o in env.objects:
        try:
            d = o.read()
        except Exception:
            continue
        if o.type == 4:
            trs.append((o.byte_start, o.path_id, d))
        elif o.type == 1:
            try:
                gos.append((o.byte_start, o.path_id, str(d.m_Name)))
            except Exception:
                pass
    if not trs:
        return []
    tb = sorted(t[0] for t in trs)
    gaps = [(b2 - b1, i) for i, (b1, b2) in enumerate(zip(tb, tb[1:]))]
    split = tb[max(gaps, key=lambda g: g[0])[1]] if len(tb) > 1 else tb[0]
    gim_pids = {pid for _, pid, n in gos if n.startswith('Gimmic_') or n.startswith('MapGimmic')}
    names_by_pid = {}
    for _, pid, n in gos:
        names_by_pid.setdefault(pid, []).append(n)
    out = []
    for half in (0, 1):
        tr_h = {pid: d for bs, pid, d in trs if (bs <= split) == (half == 0)}
        wm = {}
        def wm4(pid):
            if pid in wm:
                return wm[pid]
            t = tr_h[pid]
            m = mat4(t)
            f = t.m_Father
            if f and f.path_id in tr_h and f.path_id not in wm:
                m = wm4(f.path_id) @ m
            wm[pid] = m
            return m
        for pid, t in tr_h.items():
            gp = t.m_GameObject.path_id
            if gp not in gim_pids:
                continue
            nm = next((n for n in names_by_pid[gp] if n.startswith('Gimmic_')), None)
            if nm is None:
                continue
            p = wm4(pid)[:3, 3]
            if abs(p[0]) < .01 and abs(p[1]) < .01 and abs(p[2]) < .01:
                continue
            out.append({'name': nm, 'pos': [round(float(v), 2) for v in p]})
    ded = []
    for e in out:
        if all(np.linalg.norm(np.array(e['pos']) - np.array(d['pos'])) > 1.0 for d in ded):
            ded.append(e)
    return ded

bundles = sorted(f for f in os.listdir(GAME)
                 if f.endswith('_area_scenes') and (f.startswith('du') or f.startswith('fi')))
res = {}
for b in bundles:
    da = b[:-len('_area_scenes')]
    rows = extract(os.path.join(GAME, b))
    if rows:
        res[da] = rows
        fam = collections.Counter(r['name'].split('（')[0].split(' (')[0] for r in rows)
        print(da, len(rows), dict(fam))
json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved', OUT, 'bundles with gimmics:', len(res))
