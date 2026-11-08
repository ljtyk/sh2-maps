import sh2paths
#!/usr/bin/env python
"""Solve du007 (and labelled du004) tile-layer -> Y-level assignment.

Method (no door icons, no transform fitting):
  * labelled points: warp/jump labelled 'B{a}->B{b}' contributes pos (floor a)
    and warp_to (floor b); 'Warp(B{f})' contributes both at floor f.
  * candidate levels: observed Y levels in the area (navmesh + gimmick Y
    clusters, merged <=3m), padded to the layer count on the 120m grid.
  * score(level, layer) = fraction of labelled points with |y - level| <= 60m
    that land on corridor (alpha>40) in that layer's tile mask, projected with
    the floor's ui2world transform.
  * best layer->level permutation (n <= 8, exhaustive).
Label = majority floor number of the points assigned to each level
('?' suffix if extrapolated / no direct support).

Writes re/out/dbg_layers_<dun>_<area>.json in the same schema as layers.py.
"""
import sys, os, glob, json, re, itertools
from collections import Counter, defaultdict
import numpy as np
import texture2ddecoder
from PIL import Image

OLD = sh2paths.OLD
OUT = sh2paths.OUT
def P(n): return sh2paths.oldfile(n)
def O(n): return os.path.join(OUT, n)

def layer_count(dun, area):
    n = 0
    for p in glob.glob(P(f'automap_{dun}/*.bin')):
        m = re.match(rf'^{re.escape(dun)}_{re.escape(area)}_(\d+)_\d+_\d+$', os.path.basename(p)[:-4])
        if m:
            n = max(n, int(m.group(1)) + 1)
    return n

def observed_levels(dun, area):
    ys = []
    try:
        nm = json.load(open(P(f'navmesh_{dun}_{area}.json')))
        ys += [v[2] for t in nm['tiles'] for v in t['verts']]
    except FileNotFoundError:
        pass
    g = json.load(open(P('gimmicks.json'), encoding='utf-8')).get(dun, {}).get(area, [])
    for r in g:
        ys.append(r['pos'][1])
        if r.get('warp_to'):
            ys.append(r['warp_to'][1])
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

def pad_levels(levels, n, step=None):
    if step is None:
        levels0 = sorted(levels)
        step = float(np.median(np.diff(levels0))) if len(levels0) >= 2 else 4.0
        step = max(2.0, step)
    levels = list(levels)
    i = 0
    while len(levels) < n:
        cand = (max(levels) + step) if i % 2 == 0 else (min(levels) - step)
        if any(abs(cand - v) < 10 for v in levels):
            cand = max(levels) + step * (i // 2 + 1)
        levels.append(cand)
        i += 1
    return levels

def labelled_points(dun, area):
    g = json.load(open(P('gimmicks.json'), encoding='utf-8')).get(dun, {}).get(area, [])
    pts = []
    def ok(x, z):
        return not (abs(x) < 1.0 and abs(z) < 1.0)
    for r in g:
        lab = r.get('label', '') or r.get('go_name', '')
        wt = r.get('warp_to')
        px, py, pz = r['pos']
        m = re.match(r'B(\d+)→B(\d+)', lab)
        if m and ok(px, pz):
            pts.append((py, px, pz, int(m.group(1))))
            if wt and ok(wt[0], wt[2]):
                pts.append((wt[1], wt[0], wt[2], int(m.group(2))))
            continue
        m = re.match(r'Warp（B(\d+)）', lab)
        if m and ok(px, pz):
            f = int(m.group(1))
            pts.append((py, px, pz, f))
            if wt and ok(wt[0], wt[2]):
                pts.append((wt[1], wt[0], wt[2], f))
            continue
        # du004-style: floor suffix like 扉1_2F / ダクト(1F)
        m = re.search(r'(\d)F', lab)
        if m and ok(px, pz):
            f = int(m.group(1))
            pts.append((py, px, pz, f))
            if wt and ok(wt[0], wt[2]):
                pts.append((wt[1], wt[0], wt[2], f))
    return pts

def load_layer_mask(dun, area, L):
    dims = {}
    for r in json.load(open(P(f'dbg_automap_texlist_{dun}.json'))):
        dims[r['name']] = (r['w'], r['h'])
    tree = json.load(open(P(f'dbg_ui_tree_{dun}.json')))
    tiles = {}
    for p in glob.glob(P(f'automap_{dun}/*.bin')):
        nm = os.path.basename(p)[:-4]
        if re.match(rf'^{dun}_{area}_{L}_\d+_\d+$', nm):
            tiles[nm] = p
    quads = {}
    for d in tree:
        s = d.get('sprite')
        if s in tiles and d['active']:
            quads.setdefault(s, d['world'])
    if not quads:
        return None
    xs = [w[0] for w in quads.values()]
    ys = [w[1] for w in quads.values()]
    x0, x1 = int(min(xs)) - 256, int(max(xs)) + 256
    y0, y1 = int(min(ys)) - 256, int(max(ys)) + 256
    W, H = x1 - x0, y1 - y0
    acv = np.zeros((H, W), np.float32)
    for nm, pth in tiles.items():
        w = quads.get(nm)
        if not w:
            continue
        tw, th = dims.get(nm, (256, 256))
        px = np.frombuffer(texture2ddecoder.decode_bc7(open(pth, 'rb').read(), tw, th), np.uint8).reshape(th, tw, 4)
        if px.shape[0] != 512:
            px = np.array(Image.fromarray(px, 'RGBA').resize((512, 512), Image.NEAREST))
        cx, cy = int(w[0]) - x0, int(w[1]) - y0
        acv[cy - 256:cy + 256, cx - 256:cx + 256] = px[:, :, 3].astype(np.float32)
    acv = acv[::-1]
    return (acv > 40), x0, y0, W, H

def solve(dun, area, verbose=True, refresh=False):
    cache = O(f'dbg_layers_{dun}_{area}.json')
    if os.path.exists(cache) and not refresh:
        return json.load(open(cache))
    n = layer_count(dun, area)
    pts = labelled_points(dun, area)
    if n <= 1 or not pts:
        # no labelled points -> this method cannot help; leave any existing
        # cache (e.g. from icon matching) untouched
        if verbose:
            print(f'{dun}_{area}: n={n}, labelled points={len(pts)} -> not solvable here')
        return None
    obs = observed_levels(dun, area)
    levels = pad_levels(obs, n)
    ls = sorted(levels)
    step = float(np.median(np.diff(ls))) if len(ls) >= 2 else 4.0
    radius = max(2.0, 0.45 * step)   # point must sit near its candidate level
    u2w = json.load(open(P(f'dbg_ui2world_{dun}_{area}.json')))
    s, t = u2w['s'], u2w['t']
    masks = {}
    for L in range(n):
        r = load_layer_mask(dun, area, L)
        if r:
            masks[L] = r
    score = np.zeros((len(levels), n))
    support = np.zeros((len(levels), n), int)
    floors_at = []
    for li, lv in enumerate(levels):
        sel = [p for p in pts if abs(p[0] - lv) <= radius]
        floors_at.append(Counter(f for _, _, _, f in sel))
        for L, (mask, x0, y0, W, H) in masks.items():
            if not sel:
                continue
            hit = 0
            for y, x, z, f in sel:
                px = int(x * s + t[0] - x0)
                py = int(H - 1 - (z * s + t[1] - y0))
                if 0 <= px < W and 0 <= py < H and mask[py, px]:
                    hit += 1
            score[li, L] = hit / len(sel)
            support[li, L] = len(sel)
    # exhaustive assignment; tie-break: prefer higher total support
    best = None
    for perm in itertools.permutations(range(len(levels))):
        c = (sum(score[perm[L], L] for L in range(n)),
             sum(support[perm[L], L] for L in range(n)))
        if best is None or c > best[0]:
            best = (c, perm)
    perm = best[1]
    # labels: majority floor of the points at the assigned level; extrapolate
    # with '?' when a level has no direct support
    known = {f: yv for f, yv in []}
    fy = defaultdict(list)
    for y, x, z, f in pts:
        fy[f].append(y)
    fymed = {f: float(np.median(v)) for f, v in fy.items()}
    def fmt(f):
        # du007 floors are 'B12', du004 sub-levels are '2F';
        # a du007 extrapolated floor above B1 is the street level
        if dun == 'du007':
            return 'Street' if f < 1 else f'B{f}'
        return f'{f}F'
    labels = []
    for L in range(n):
        lv = levels[perm[L]]
        c = floors_at[perm[L]]
        if c:
            top = max(c.values())
            winners = sorted(f for f, v in c.items() if v == top)
            lab = '/'.join(fmt(w) for w in winners)
        else:
            # extrapolate from the floor->y relation
            if len(fymed) >= 2:
                A = np.vstack([np.ones(len(fymed)), list(fymed.values())]).T
                b = np.linalg.lstsq(A, list(fymed.keys()), rcond=None)[0]
                f = b[0] + b[1] * lv
                lab = fmt(round(f)) + '?'
            else:
                lab = '?'
        labels.append(lab)
    ys = sorted(levels[perm[L]] for L in range(n))
    spacing = float(np.median(np.diff(ys))) if len(ys) >= 2 else 0.0
    out = {'n_layers': n, 'y_of_layer': [float(levels[perm[L]]) for L in range(n)],
           'labels': labels, 'spacing': spacing, 'obs_levels': obs,
           'matched': int(sum(1 for L in range(n) if support[perm[L], L] > 0)) > 0,
           'score': [float(score[perm[L], L]) for L in range(n)],
           'support': [int(support[perm[L], L]) for L in range(n)],
           'method': 'label-corridor'}
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(cache, 'w'), indent=1)
    if verbose:
        print(f'{dun}_{area}: n={n} obs={obs}')
        for L in range(n):
            print(f'   L{L}: y={levels[perm[L]]:>8.1f} {labels[L]:<8} score={score[perm[L],L]:.2f} n={support[perm[L],L]}')
    return out

if __name__ == '__main__':
    args = sys.argv[1:]
    refresh = '--refresh' in args
    args = [a for a in args if a != '--refresh']
    if not args:
        args = ['du007 0000', 'du007 0010', 'du007 0020', 'du007 0030', 'du007 0040', 'du007 0050',
                'du004 0000', 'du004 0010']
    for pr in args:
        a, b = pr.split()[:2]
        solve(a, b, refresh=refresh)
