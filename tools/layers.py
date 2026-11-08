import sh2paths
#!/usr/bin/env python
"""Per-area map layer helpers.

The in-game automap bundles ship one pre-rendered tile set per map layer
(du004/du007 floors have 2-8 layers). This module resolves:

  * how many layers an area has (from automap tile filenames)
  * which 3D Y level each layer depicts (navmesh + gimmick Y clusters,
    assigned to layer indices via warp-door-icon matching)
  * floor labels for du007 (from jump-gate labels like 'B16->B15')

Assignment rule (verified): the layer index -> Y mapping is PER AREA
(du007: layer 0 = highest Y; du004_0000: layer 0 = lowest Y), so it is
solved, never assumed.

Cache: dbg_layers_<dun>_<area>.json   (delete to recompute; or --refresh)
"""
import json, glob, os, re, itertools, sys
import numpy as np
from scipy.spatial import cKDTree

OLD = sh2paths.OLD   # read-only input data
OUT = sh2paths.OUT


def P(name):
    return sh2paths.oldfile(name)


def O(name):
    return os.path.join(OUT, name)


def layer_count(dun, area):
    n = 0
    for p in glob.glob(P(f'automap_{dun}/*.bin')):
        nm = os.path.basename(p)[:-4]
        m = re.match(rf'^{re.escape(dun)}_{re.escape(area)}_(\d+)_\d+_\d+$', nm)
        if m:
            n = max(n, int(m.group(1)) + 1)
    return n


def observed_levels(dun, area):
    """Distinct 3D Y levels present in the area (1 m rounded, merged <=3 m,
    count >= 2 to reject sub-passage offsets)."""
    ys = []
    try:
        nm = json.load(open(P(f'navmesh_{dun}_{area}.json')))
        ys += [v[2] for t in nm['tiles'] for v in t['verts']]
    except FileNotFoundError:
        pass
    g = json.load(open(P('gimmicks.json'), encoding='utf-8')).get(dun, {}).get(area, [])
    ys += [r['pos'][1] for r in g]
    ys += [r['warp_to'][1] for r in g if r.get('warp_to')]
    hist = {}
    for y in ys:
        k = round(y)
        hist[k] = hist.get(k, 0) + 1
    merged = []
    for k in sorted(hist):
        if hist[k] < 2:
            continue
        if merged and k - merged[-1][0] <= 3:
            merged[-1][1] += hist[k]
        else:
            merged.append([k, hist[k]])
    return [k for k, _ in merged]


def _icon_sets(tree, dun, area, nlayers):
    by = {d['pid']: d for d in tree}

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
    for idx in range(nlayers):
        root = f'{dun}_{area}_{idx}_icon'
        pts = [d['world'] for d in tree if d['active'] and d['name'] == 'Icon' and in_sub(d, root)
               and any(d.get('sprite', '').endswith(x) for x in ('_06', '_09', '_07'))]
        out.append(np.array(pts, dtype=float))
    return out


def _score_matrix(dun, area, nlayers, levels):
    """score[level][layer] = mean NN distance (px) of warps-at-level to
    warp-door icons on layer. 1e9 where either side has no support."""
    g = json.load(open(P('gimmicks.json'), encoding='utf-8'))[dun][area]
    tr = json.load(open(P(f'dbg_ui2world_{dun}_{area}.json')))
    s, t = tr['s'], np.array(tr['t'])
    tree = json.load(open(P(f'dbg_ui_tree_{dun}.json')))
    warps = [r for r in g if r['kind'] == 'MapGimmic_Warp']
    score = np.full((len(levels), nlayers), 1e9)
    if not warps:
        return score
    W = np.array([[s * p[0] + t[0], s * p[2] + t[1]] for p in (r['pos'] for r in warps)])
    Wy = np.array([round(r['pos'][1]) for r in warps])
    icon_sets = _icon_sets(tree, dun, area, nlayers)
    for li, lv in enumerate(levels):
        m = np.abs(Wy - lv) <= 3
        if not m.any():
            continue
        for L in range(nlayers):
            if len(icon_sets[L]) == 0:
                continue
            d, _ = cKDTree(icon_sets[L]).query(W[m], k=1)
            score[li, L] = d.mean()
    return score


def _pad(levels, nlayers):
    """Extend the level grid to nlayers entries: alternate hi+step, lo-step."""
    levels = list(levels)
    i = 0
    while len(levels) < nlayers:
        if len(levels) >= 2:
            step = float(np.median(np.diff(sorted(levels))))
        else:
            step = 5.0
        cand = (max(levels) + step) if i % 2 == 0 else (min(levels) - step)
        if any(abs(cand - lv) < 1 for lv in levels):
            cand = max(levels) + step * (i // 2 + 1)
        levels.append(cand)
        i += 1
    return levels


def _inversions(perm_vals):
    inv = 0
    for i in range(len(perm_vals)):
        for j in range(i + 1, len(perm_vals)):
            if perm_vals[i] < perm_vals[j]:
                inv += 1
    return inv


def _du007_labels(dun, area, y_of_layer):
    """Floor labels from jump-gate labels ('B16' etc) anchored at their Y.
    A gate labelled 'B16->B15' sits ON B16, at that floor's Y."""
    if dun != 'du007':
        return None
    g = json.load(open(P('gimmicks.json'), encoding='utf-8'))[dun][area]
    anchors = []
    for r in g:
        if r['kind'] != 'MapGimmic_AreaJump':
            continue
        m = re.match(r'B(\d+)', r.get('label', ''))
        if m:
            anchors.append((r['pos'][1], int(m.group(1))))
    if not anchors:
        return None
    ay = np.array([a[0] for a in anchors], dtype=float)
    af = np.array([a[1] for a in anchors], dtype=float)
    if len(anchors) >= 2 and (ay.max() - ay.min()) > 1:
        A = np.vstack([np.ones_like(ay), -ay]).T
        b = np.linalg.lstsq(A, af, rcond=None)[0]
    else:
        b = np.array([af[0], 0.0])
    labels = []
    for y in y_of_layer:
        f = b[0] + b[1] * y
        labels.append(f'B{round(f)}' if abs(f - round(f)) < 0.5 else '?')
    return labels


def solve(dun, area, verbose=True, refresh=False):
    cache = O(f'dbg_layers_{dun}_{area}.json')
    if os.path.exists(cache) and not refresh:
        return json.load(open(cache))
    n = layer_count(dun, area)
    if n <= 1:
        out = {'n_layers': 1, 'y_of_layer': [0.0], 'labels': [None], 'spacing': 0.0,
               'obs_levels': [0], 'matched': True}
        json.dump(out, open(cache, 'w'))
        return out
    obs = observed_levels(dun, area)
    levels = _pad(obs, n)
    score = _score_matrix(dun, area, n, levels)
    best = None  # (cost, inversions, perm)
    for perm in itertools.permutations(range(len(levels))):
        # perm[L] = level index assigned to layer L
        cost = sum(score[perm[L], L] for L in range(n))
        vals = [levels[perm[L]] for L in range(n)]
        inv = _inversions(vals)
        if best is None or (cost, inv) < (best[0], best[1]):
            best = (cost, inv, perm)
    perm = best[2]
    y_of_layer = [float(levels[perm[L]]) for L in range(n)]
    n_supported = int(sum(1 for row in score if row.min() < 1e8))
    ys = sorted(y_of_layer)
    spacing = float(np.median(np.diff(ys))) if len(ys) >= 2 else 0.0
    labels = _du007_labels(dun, area, y_of_layer)
    if labels is None:
        labels = [f'Level {i + 1}/{n}' for i in range(n)]
    out = {'n_layers': n, 'y_of_layer': y_of_layer, 'labels': labels, 'spacing': spacing,
           'obs_levels': obs, 'matched': n_supported > 0, 'cost': float(best[0]),
           'n_supported': n_supported}
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(cache, 'w'), indent=1)
    if verbose:
        print(f'{dun}_{area}: {n} layers obs={obs}')
        print(f'   y_of_layer={[round(y, 1) for y in y_of_layer]} labels={labels}')
    return out


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--refresh']
    refresh = '--refresh' in sys.argv or not args
    if not args:
        args = [' '.join(l.split()) for l in open(P('dbg_all_combos.txt')) if l.strip()]
    for pr in args:
        a, b = pr.split()[:2]
        solve(a, b, refresh=refresh)
