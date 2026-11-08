import sh2paths
#!/usr/bin/env python
"""Re-fit per-floor world->UI transforms (task B, v3).

Model (unchanged from the pipeline):  ux = s*x + a ;  uy = s*z + b
(canvas mapping: px = ux - x0, py = (H-1) - (uy - y0)).

Anchors (multi-layer aware, each paired against ITS layer's icons):
  * AreaJump pos <-> nearest _03/_13 stair icon
  * Portal pos   <-> nearest _02 icon
  * Warp pos     <-> nearest _06/_07/_08/_09 door icon

  COARSE: for s in 5.2..7.8 step 0.05, EM from a (s,a,b) init: repeatedly
    NN-repair every anchor to its layer's icon class under the current
    transform (25px gate) and reset (a,b) to the pooled median offset;
    score = #anchors within 12px.  Run from the old-transform init and from
    the global init (s=6.4, a=b=0); take the best s.
  FINE: RANSAC on the 12px inliers (3-point samples gated on 10m x AND z
    span and |s1-s2|<0.5), shared-s median re-fit on an s sweep, 2 EM
    iterations.

A new fit is written to re/out only if it improves (inliers@12px, rms) and
5.0 <= s <= 8.0; previous re/out caches are backed up to re/out/transform_old/.
Old caches in the reference project are never touched.

Usage: fit_transforms.py [dun area ...]   (default: all 42)
"""
import sys, os, json
import numpy as np
from scipy.spatial import cKDTree
import itertools

OLD = sh2paths.OLD
OUT = sh2paths.OUT
def P(n): return sh2paths.oldfile(n)
def O(n): return os.path.join(OUT, n)

STAIRS = ('Icon_AutoMap01_03', 'Icon_AutoMap01_13')
PORTAL = 'Icon_AutoMap01_02'
DOORS = ('Icon_AutoMap01_06', 'Icon_AutoMap01_07', 'Icon_AutoMap01_08', 'Icon_AutoMap01_09')
CLASSES = {'stair': STAIRS, 'portal': (PORTAL,), 'door': DOORS}
GATE = 12.0
REPAIR = 25.0


def layer_info(dun, area):
    f = O(f'dbg_layers_{dun}_{area}.json')
    if os.path.exists(f):
        return json.load(open(f))
    return {'n_layers': 1, 'y_of_layer': [0.0], 'labels': [None], 'spacing': 0.0}


def collect(dun, area):
    """anchors: list of (L, x, z, key) + per-(L,key) icon KDTree + points"""
    gj = json.load(open(P('gimmicks.json'), encoding='utf-8'))
    g = gj[dun][area]
    info = layer_info(dun, area)
    bands, sp = info['y_of_layer'], info.get('spacing') or 120.0
    half = max(2.0, 0.6 * sp) if info['n_layers'] > 1 else 1e9
    def band(y):
        if info['n_layers'] <= 1:
            return 0
        d = [abs(y - b) for b in bands]
        i = int(np.argmin(d))
        return i if d[i] <= half else None
    tree = json.load(open(P(f'dbg_ui_tree_{dun}.json')))
    by = {r['pid']: r for r in tree}
    n = max(info['n_layers'], 1)
    def root_of(d):
        cur = d
        for _ in range(8):
            p = by.get(cur.get('parent_pid'))
            if p is None:
                return None
            if p['name'].startswith(f'{dun}_{area}_') and p['name'].endswith('_icon'):
                return p['name']
            cur = p
        return None
    icons = {L: {} for L in range(n)}
    for d in tree:
        if not d.get('active') or d.get('name') != 'Icon':
            continue
        spr = d.get('sprite', '')
        if spr not in STAIRS + (PORTAL,) + DOORS:
            continue
        r = root_of(d)
        if not r:
            continue
        L = int(r.rsplit('_icon', 1)[0].rsplit('_', 1)[1])
        icons.setdefault(L, {}).setdefault(spr, []).append(d['world'])
    trees = {}
    for L in range(n):
        for key, sprs in CLASSES.items():
            arrs = [v for k, v in icons.get(L, {}).items() if k in sprs]
            if arrs:
                pts = np.unique(np.vstack(arrs), axis=0)
                trees[(L, key)] = (cKDTree(pts), pts)
    anchors = []
    for r in g:
        x, y, z = r['pos']
        L = band(y)
        if L is None:
            continue
        if r['kind'] == 'MapGimmic_AreaJump':
            anchors.append((L, x, z, 'stair'))
        elif r['kind'] == 'MapGimmic_Portal':
            anchors.append((L, x, z, 'portal'))
        elif r['kind'] == 'MapGimmic_Warp' and r.get('warp_to'):
            anchors.append((L, x, z, 'door'))
    return anchors, trees


def repair(anchors, trees, s, a, b, gate=REPAIR):
    """NN-pair each anchor under the current transform; return (Pw, Pu, d)."""
    Pw, Pu, D = [], [], []
    for L, x, z, key in anchors:
        tk = trees.get((L, key))
        if tk is None:
            continue
        tree, pts = tk
        d, i = tree.query(np.array([[s * x + a, s * z + b]]))
        if d[0] < gate:
            Pw.append((x, z)); Pu.append(pts[i[0]]); D.append(float(d[0]))
    if len(Pw) < 2:
        return None
    return np.array(Pw), np.array(Pu), np.array(D)


def em_offset(anchors, trees, s, a, b, iters=3):
    for _ in range(iters):
        r = repair(anchors, trees, s, a, b)
        if r is None:
            return None
        Pw, Pu, _ = r
        a = float(np.median(Pu[:, 0] - s * Pw[:, 0]))
        b = float(np.median(Pu[:, 1] - s * Pw[:, 1]))
    return repair(anchors, trees, s, a, b)


def score(anchors, trees, s, a, b):
    r = repair(anchors, trees, s, a, b)
    if r is None:
        return 0, 1e9, 1e9
    Pw, Pu, _ = r
    d = np.hypot(s * Pw[:, 0] + a - Pu[:, 0], s * Pw[:, 1] + b - Pu[:, 1])
    m = d < GATE
    return int(m.sum()), float(d[m].mean()) if m.sum() else 1e9, float(np.median(d))


def coarse(anchors, trees, s_init, a_init, b_init):
    best = None
    for s in np.arange(5.2, 7.81, 0.05):
        r = em_offset(anchors, trees, float(s), a_init, b_init)
        if r is None:
            continue
        Pw, Pu, _ = r
        a = float(np.median(Pu[:, 0] - s * Pw[:, 0]))
        b = float(np.median(Pu[:, 1] - s * Pw[:, 1]))
        st = score(anchors, trees, s, a, b)
        if best is None or (st[0], -st[1]) > (best[0][0], -best[0][1]):
            best = (st, float(s), a, b)
    if best is None:
        return None
    return best[1], best[2], best[3]


def direct_fit(anchors, trees):
    """s sweep with median offset (for sparse floors). Returns (st, s, a, b)."""
    best = None
    for s in np.arange(5.4, 7.41, 0.05):
        a = b = 0.0
        for _ in range(3):
            r = repair(anchors, trees, float(s), a, b, gate=40.0)
            if r is None:
                break
            Pw, Pu, _ = r
            a = float(np.median(Pu[:, 0] - s * Pw[:, 0]))
            b = float(np.median(Pu[:, 1] - s * Pw[:, 1]))
        st = score(anchors, trees, float(s), a, b)
        if best is None or (st[0], -st[1]) > (best[0][0], -best[0][1]):
            best = (st, float(s), a, b)
    return best


def refine(anchors, trees, s0, a0, b0, iters=2):
    s, a, b = s0, a0, b0
    rng = np.random.default_rng(1)
    for _ in range(iters):
        r = repair(anchors, trees, s, a, b, gate=GATE)
        if r is None:
            break
        Pw, Pu, _ = r
        d = np.hypot(s * Pw[:, 0] + a - Pu[:, 0], s * Pw[:, 1] + b - Pu[:, 1])
        m = np.where(d < GATE)[0]
        if len(m) < 3:
            break
        cands = (list(itertools.combinations(m, 3)) if len(m) < 20
                 else [tuple(rng.choice(m, 3, replace=False)) for _ in range(600)])
        best = None
        for i, j, k in cands:
            xs, zs = Pw[[i, j, k], 0], Pw[[i, j, k], 1]
            if np.ptp(xs) < 10 or np.ptp(zs) < 10:
                continue
            A1 = np.column_stack([xs, np.ones(3)])
            A2 = np.column_stack([zs, np.ones(3)])
            try:
                s1 = np.linalg.lstsq(A1, Pu[[i, j, k], 0], rcond=None)[0][0]
                s2 = np.linalg.lstsq(A2, Pu[[i, j, k], 1], rcond=None)[0][0]
            except np.linalg.LinAlgError:
                continue
            sc = (s1 + s2) / 2
            if abs(s1 - s2) > 0.5 or not (4.5 <= sc <= 8.5):
                continue
            ac = float(np.median(Pu[m, 0] - sc * Pw[m, 0]))
            bc = float(np.median(Pu[m, 1] - sc * Pw[m, 1]))
            st = score(anchors, trees, sc, ac, bc)
            if best is None or (st[0], -st[1]) > (best[0][0], -best[0][1]):
                best = (st, sc, ac, bc)
        if best is None:
            break
        _, sc, ac, bc = best
        # shared-s median re-fit: sweep s around the winner
        best2 = None
        for s2 in np.linspace(max(4.8, sc - 0.6), min(8.2, sc + 0.6), 49):
            r2 = repair(anchors, trees, float(s2), ac, bc)
            if r2 is None:
                continue
            Pw2, Pu2, _ = r2
            a2 = float(np.median(Pu2[:, 0] - s2 * Pw2[:, 0]))
            b2 = float(np.median(Pu2[:, 1] - s2 * Pw2[:, 1]))
            st = score(anchors, trees, float(s2), a2, b2)
            if best2 is None or (st[0], -st[1]) > (best2[0][0], -best2[0][1]):
                best2 = (st, float(s2), a2, b2)
        s, a, b = best2[1], best2[2], best2[3]
    return score(anchors, trees, s, a, b), s, a, b


def score2(anchors, trees, s, a, b, gate=12.0):
    """repair at 2*gate, count at gate; returns (inliers, rms, median)."""
    r = repair(anchors, trees, s, a, b, gate=gate * 2.0)
    if r is None:
        return 0, 1e9, 1e9
    Pw, Pu, _ = r
    d = np.hypot(s * Pw[:, 0] + a - Pu[:, 0], s * Pw[:, 1] + b - Pu[:, 1])
    m = d < gate
    return int(m.sum()), float(d[m].mean()) if m.sum() else 1e9, float(np.median(d))


def grid_refine(anchors, trees, s, a0, b0, span=300, step=25, gate=40.0):
    best = None
    for a in np.arange(a0 - span, a0 + span + 1, step):
        for b in np.arange(b0 - span, b0 + span + 1, step):
            st = score2(anchors, trees, float(s), float(a), float(b), gate=gate)
            if best is None or (st[0], -st[1]) > (best[0][0], -best[0][1]):
                best = (st, float(a), float(b))
    return best


def blind_fit(anchors, trees):
    """2D offset grid search with a loose detection gate, s near 6.4.
    Returns (st, s, a, b) or None."""
    best = None
    for s in (6.2, 6.4, 6.6):
        for a in np.arange(-4000, 4001, 250):
            for b in np.arange(-8000, 8001, 250):
                st = score2(anchors, trees, s, float(a), float(b), gate=150.0)
                if best is None or (st[0], -st[1]) > (best[0][0], -best[0][1]):
                    best = (st, s, float(a), float(b))
    if best is None or best[0][0] == 0:
        return None
    g = grid_refine(anchors, trees, best[1], best[2], best[3], span=250, step=25, gate=60.0)
    g = grid_refine(anchors, trees, best[1], g[1], g[2], span=30, step=5, gate=15.0)
    # s sweep around the found offset
    best2 = None
    for s in np.arange(best[1] - 0.5, best[1] + 0.51, 0.05):
        r = repair(anchors, trees, float(s), g[1], g[2])
        if r is None:
            continue
        Pw, Pu, _ = r
        a = float(np.median(Pu[:, 0] - s * Pw[:, 0]))
        b = float(np.median(Pu[:, 1] - s * Pw[:, 1]))
        st = score(anchors, trees, float(s), a, b)
        if best2 is None or (st[0], -st[1]) > (best2[0][0], -best2[0][1]):
            best2 = (st, float(s), a, b)
    if best2 is None:
        return None
    return best2


def main():
    args = sys.argv[1:]
    if args:
        combos = [f'{a} {b}' for a, b in zip(args[::2], args[1::2])]
    else:
        combos = [' '.join(l.split()) for l in open(P('dbg_all_combos.txt')) if l.strip()]
    os.makedirs(O('transform_old'), exist_ok=True)
    n_write = 0
    for pr in combos:
        dun, area = pr.split()[:2]
        cf = O(f'dbg_ui2world_{dun}_{area}.json')
        old = json.load(open(cf if os.path.exists(cf) else P(f'dbg_ui2world_{dun}_{area}.json')))
        s0, t0 = old['s'], np.array(old['t'])
        anchors, trees = collect(dun, area)
        if len(anchors) < 4:
            print(f'{dun}_{area}: {len(anchors)} anchors -> skipped')
            continue
        # baseline measured on the RAW old transform (0 if nothing pairs)
        r_old = repair(anchors, trees, s0, t0[0], t0[1])
        if r_old is None:
            inl_old, rms_old, med_old = 0, 1e9, 1e9
        else:
            Pw, Pu, _ = r_old
            d_old = np.hypot(s0 * Pw[:, 0] + t0[0] - Pu[:, 0], s0 * Pw[:, 1] + t0[1] - Pu[:, 1])
            m_old = d_old < GATE
            inl_old = int(m_old.sum())
            rms_old = float(d_old[m_old].mean()) if m_old.sum() else 1e9
            med_old = float(np.median(d_old))
        cands = []
        # 1+2: EM coarse-s fits from the old init and the global init
        for init in [(s0, t0[0], t0[1]), (6.4, 0.0, 0.0)]:
            c = coarse(anchors, trees, *init)
            if c is None:
                continue
            st, s1, a1, b1 = refine(anchors, trees, *c)
            cands.append((st, s1, a1, b1))
        # 3: direct s-sweep with median offsets (cheap, robust on sparse floors)
        df = direct_fit(anchors, trees)
        if df is not None:
            cands.append(df)
        # 4: blind 2D offset grid search, only when the best candidate is weak
        best_so_far = max(cands, key=lambda c: (c[0][0], -c[0][1])) if cands else None
        if best_so_far is None or best_so_far[0][0] < 10:
            bf = blind_fit(anchors, trees)
            if bf is not None:
                st, s1, a1, b1 = refine(anchors, trees, bf[1], bf[2], bf[3])
                cands.append((st, s1, a1, b1))
        if not cands:
            print(f'{dun}_{area}: all fits failed -> kept old (s={s0:.2f})')
            continue
        st1, s1, a1, b1 = max(cands, key=lambda c: (c[0][0], -c[0][1]))
        inl_new, rms_new, med_new = st1
        pinned = abs(s1 - 6.41) < 0.05
        # with <4 inliers the scale is under-determined: pin s to the global
        # consensus and re-fit only (a, b) by median offset
        if 1 <= inl_new < 4:
            sfix = 6.41
            bestf = None
            for init in ((0.0, 0.0), (a1, b1), (t0[0], t0[1])):
                r = repair(anchors, trees, sfix, init[0], init[1], gate=40.0)
                if r is None:
                    continue
                Pw, Pu, _ = r
                af = float(np.median(Pu[:, 0] - sfix * Pw[:, 0]))
                bf = float(np.median(Pu[:, 1] - sfix * Pw[:, 1]))
                stf = score(anchors, trees, sfix, af, bf)
                if bestf is None or (stf[0], -stf[1]) > (bestf[0][0], -bestf[0][1]):
                    bestf = (stf, af, bf)
            if bestf is not None and bestf[0][0] >= max(1, st1[0]):
                st1, s1, a1, b1 = bestf[0], sfix, bestf[1], bestf[2]
                inl_new, rms_new, med_new = st1
                pinned = True
        sane = 5.0 <= s1 <= 8.0
        changed = abs(s1 - s0) > 1e-3 or abs(a1 - t0[0]) > 1.0 or abs(b1 - t0[1]) > 1.0
        # strong fits (>=4 inliers): write on strict improvement; weak fits
        # (1-3 inliers): only when s is pinned to the global consensus
        improved = (inl_new > inl_old) or (inl_new == inl_old and rms_new < rms_old - 0.5)
        weak_ok = 1 <= inl_new < 4 and pinned and inl_old < 4
        tag = 'WRITE' if sane and changed and (improved or weak_ok) else 'keep'
        if tag == 'WRITE':
            n_write += 1
            if os.path.exists(cf):
                json.dump(json.load(open(cf)), open(O(f'transform_old/{os.path.basename(cf)}'), 'w'))
            json.dump({'s': float(s1), 't': [float(a1), float(b1)], 'dun': dun, 'area': area,
                       'flip': [1, 1], 'n_inliers': inl_new, 'rms': float(rms_new),
                       'method': 'coarse-ransac-v3'}, open(cf, 'w'), indent=1)
        print(f'{dun}_{area}: {len(anchors)} anchors {tag}: s {s0:.2f}->{s1:.2f} '
              f'inliers(12px) {inl_old}->{inl_new} rms {rms_old:.1f}->{rms_new:.1f} '
              f'med {med_old:.1f}->{med_new:.1f}px')
    print(f'\n{n_write} transforms updated')


if __name__ == '__main__':
    main()
