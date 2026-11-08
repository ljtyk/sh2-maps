import sh2paths
#!/usr/bin/env python3
"""Task C fix: MapGimmic_Portal world positions sit in their own frame
(clustered near the origin, not on the map). Test whether a per-area
similarity transform (s, a, b) with NO rotation maps each area's portal
cluster onto its _02 warp-gate icons (Hungarian assignment), and save
any sane per-area transform to re/out/portal_tf.json.

Usage: python -X utf8 fit_portal_transforms.py
"""
import json, os, re
import numpy as np
from scipy.optimize import linear_sum_assignment

OLD = sh2paths.OLD
OUT = sh2paths.OUT

def load_portals():
    rows = json.load(open(os.path.join(OUT, 'portals.json')))
    by = {}
    for r in rows:
        if not r['pos']:
            continue
        by.setdefault((r['dun'], r['area']), []).append(r)
    return by

def load_icons(dun, area, L):
    tree = json.load(open(sh2paths.oldfile(f'dbg_ui_tree_{dun}.json')))
    by = {r['pid']: r for r in tree}
    icon_root = f'{dun}_{area}_{L}_icon'
    def in_sub(d, root):
        cur = d
        for _ in range(8):
            p = by.get(cur['pid'])
            if p is None:
                return False
            if p['name'] == root:
                return True
            cur = by.get(p.get('parent_pid')) or {}
            if not cur:
                return False
    out = []
    for d in tree:
        if d['active'] and d['name'] == 'Icon' and in_sub(d, icon_root) and d.get('sprite') == 'Icon_AutoMap01_02':
            out.append(d['world'])
    # each _02 icon node appears twice at the same position -> dedupe
    uniq = []
    for x, z in out:
        if all(abs(x - a) > 2 or abs(z - b) > 2 for a, b in uniq):
            uniq.append((x, z))
    return uniq

def layer_of(dun, area, y):
    sol = os.path.join(OUT, f'dbg_layers_{dun}_{area}.json')
    if not os.path.exists(sol):
        return 0
    info = json.load(open(sol))
    n = info['n_layers']
    if n <= 1:
        return 0
    bands = info['y_of_layer']
    sp = info.get('spacing') or 120.0
    half = max(2.0, 0.6 * sp)
    L = int(min(range(n), key=lambda i: abs(bands[i] - y)))
    return L if abs(bands[L] - y) <= half else None

def fit(p, i):
    # p, i: (n,2) world (x,z); fit ux = s*x + a, uy = s*z + b
    n = len(p)
    if n == 1:
        return None
    D = np.linalg.norm(p[:, None, :] - i[None, :, :], axis=2)
    if n > 1:
        ri, ci = linear_sum_assignment(D)
        pp, ii = p[ri], i[ci]
    else:
        pp, ii = p, i
    if n == 2:
        d_p = np.linalg.norm(pp[1] - pp[0]); d_i = np.linalg.norm(ii[1] - ii[0])
        if d_p < 1e-6 or d_i < 1e-6:
            return None
        s = d_i / d_p
        ab = ii[0] - s * pp[0]
        return (float(s), float(ab[0]), float(ab[1]), 0.0, 0.0)  # exact by construction (2 points)
    # n>=3: grid fit for s then median offsets (fast, coarse; refine by EM)
    best = None
    for s in np.linspace(4.0, 10.0, 61):
        a = np.median(ii[:, 0] - s * pp[:, 0])
        b = np.median(ii[:, 1] - s * pp[:, 1])
        res = np.linalg.norm(ii - (s * pp + [a, b]), axis=1)
        med = float(np.median(res))
        if best is None or med < best[4]:
            best = (s, a, b, float(np.max(res)), med)
    # 2 EM iters
    for _ in range(3):
        for s in np.linspace(max(4.0, best[0] - 0.8), min(10.0, best[0] + 0.8), 41):
            a = np.median(ii[:, 0] - s * pp[:, 0])
            b = np.median(ii[:, 1] - s * pp[:, 1])
            res = np.linalg.norm(ii - (s * pp + [a, b]), axis=1)
            med = float(np.median(res))
            if med < best[4]:
                best = (s, a, b, float(np.max(res)), med)
        m = res <= 2.0 * best[4] + 1.0
        pp, ii = pp[m], ii[m]
        if len(pp) < 2:
            break
    return (float(best[0]), float(best[1]), float(best[2]), float(best[3]), float(best[4]))

def main():
    P = load_portals()
    combos = set(P.keys())
    # icon counts per (dun, area, layer)
    tfs, report = {}, []
    for dun, area in sorted(combos):
        sol = os.path.join(OUT, f'dbg_layers_{dun}_{area}.json')
        n_layers = json.load(open(sol))['n_layers'] if os.path.exists(sol) else 1
        # gather (dun,area) _02 icons across its layers
        icons_all = {}
        for L in range(n_layers):
            ics = load_icons(dun, area, L)
            if ics:
                icons_all[L] = ics
        # portal assignment per layer
        port_by_L = {}
        unassigned = []
        for r in P[(dun, area)]:
            L = layer_of(dun, area, r['pos'][1])
            (port_by_L.setdefault(L, []) if L is not None else unassigned).append(r)
        per_area = {}
        for L, ports in port_by_L.items():
            ics = icons_all.get(L)
            if not ics or len(ics) != len(ports):
                continue
            f = fit(np.array([p['pos'][:2] for p in ports]), np.array(ics))
            if f:
                per_area[str(L)] = list(f)
        if per_area:
            tfs[f'{dun}_{area}'] = per_area
        report.append((f'{dun}_{area}', len(P[(dun, area)]), sum(len(v) for v in icons_all.values()),
                       {k: (round(v[0], 2), round(v[4], 1)) for k, v in per_area.items()}))
    json.dump(tfs, open(os.path.join(OUT, 'portal_tf.json'), 'w'), indent=1)
    print(f'{len(tfs)} areas with transforms')
    print(f'{"area":14} {"port":>5} {"icon02":>7}   s,medres')
    for row in report:
        print(f'{row[0]:14} {row[1]:5d} {row[2]:7d}   {row[3]}')

if __name__ == '__main__':
    main()
