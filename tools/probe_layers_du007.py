import sh2paths
#!/usr/bin/env python
"""Probe: assign du007 tile-layer indices to Y levels using warp LABELS.

Idea: a warp labelled 'B3->B4' has pos on B3 (y of B3) and warp_to on B4.
For a candidate (layer L, level y): every labelled point whose floor sits at
~y must project (ui2world) onto CORRIDOR (alpha>40) in layer L's tile mask.
Score = fraction on corridor. Solve the layer->level permutation.
No door icons needed. Transform quality is part of what this tests.
"""
import sys, os, glob, json, re
import numpy as np
import texture2ddecoder
from PIL import Image

OLD = sh2paths.OLD
def P(n): return sh2paths.oldfile(n)

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
    return acv > 40, x0, y0, W, H

def labelled_points(dun, area):
    """(y, x, z) points with a floor label: warp pos (src floor) + warp_to (dst floor)."""
    g = json.load(open(P('gimmicks.json'), encoding='utf-8'))[dun][area]
    pts = []  # (y, x, z, floornumber)
    def ok(x, z):
        return not (abs(x) < 1.0 and abs(z) < 1.0)  # origin garbage
    for r in g:
        lab = r.get('label', '') or r.get('go_name', '')
        wt = r.get('warp_to')
        px, py, pz = r['pos']
        m = re.match(r'B(\d+)→B(\d+)', lab)
        if m and ok(px, pz):
            pts.append((py, px, pz, int(m.group(1))))
            if wt and ok(wt[0], wt[2]):
                pts.append((wt[1], wt[0], wt[2], int(m.group(2))))
        m = re.match(r'Warp（B(\d+)）', lab)
        if m and ok(px, pz):
            f = int(m.group(1))
            pts.append((py, px, pz, f))
            if wt and ok(wt[0], wt[2]):
                pts.append((wt[1], wt[0], wt[2], f))
    return pts

def floor_y_table(pts):
    """floor number -> y (majority vote rounded to 10m)."""
    from collections import defaultdict
    votes = defaultdict(list)
    for y, x, z, f in pts:
        votes[f].append(round(y / 10) * 10)
    ty = {f: float(np.median(v)) for f, v in votes.items()}
    return ty

def main():
    for area in ['0000', '0010', '0020', '0030', '0040']:
        dun = 'du007'
        n = 0
        for p in glob.glob(P(f'automap_{dun}/*.bin')):
            m = re.match(rf'^{dun}_{area}_(\d+)_\d+_\d+$', os.path.basename(p)[:-4])
            if m:
                n = max(n, int(m.group(1)) + 1)
        pts = labelled_points(dun, area)
        if not pts:
            print(f'{dun}_{area}: no labelled points')
            continue
        fy = floor_y_table(pts)
        levels = sorted(set(fy.values()))
        # pad levels to n (alternate hi+step / lo-step, 120m grid)
        step = 120.0
        i = 0
        while len(levels) < n:
            cand = (max(levels) + step) if i % 2 == 0 else (min(levels) - step)
            if any(abs(cand - v) < 10 for v in levels):
                cand = max(levels) + step * (i // 2 + 1)
            levels.append(cand)
            i += 1
        u2w = json.load(open(P(f'dbg_ui2world_{dun}_{area}.json')))
        s, t = u2w['s'], u2w['t']
        print(f'== {dun}_{area}: {n} layers, floor->y = {fy}')
        print(f'   levels={levels}  s={s}')
        # per-layer mask
        masks = {}
        for L in range(n):
            r = load_layer_mask(dun, area, L)
            if r:
                masks[L] = r
        # score matrix
        import itertools
        score = np.zeros((len(levels), n))
        support = np.zeros((len(levels), n), int)
        for li, lv in enumerate(levels):
            flrs = [f for f, y in fy.items() if abs(y - lv) <= 60]
            sel = [(y, x, z) for y, x, z, f in pts if f in flrs]
            for L, (mask, x0, y0, W, H) in masks.items():
                if not sel:
                    continue
                hit = 0
                for y, x, z in sel:
                    px = int(x * s + t[0] - x0)
                    py = int(H - 1 - (z * s + t[1] - y0))
                    if 0 <= px < W and 0 <= py < H and mask[py, px]:
                        hit += 1
                score[li, L] = hit / len(sel)
                support[li, L] = len(sel)
        # best permutation
        best = None
        for perm in itertools.permutations(range(len(levels))):
            c = sum(score[perm[L], L] for L in range(n))
            if best is None or c > best[0]:
                best = (c, perm)
        perm = best[1]
        out = {L: f'B{[f for f,y in fy.items() if abs(y-levels[perm[L]])<=60]}@y{levels[perm[L]]:.0f} score={score[perm[L],L]:.2f} n={support[perm[L],L]}' for L in range(n)}
        print('   assignment:', out)

if __name__ == '__main__':
    main()
