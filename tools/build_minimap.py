import sh2paths
#!/usr/bin/env python
"""Build a readable Soul Hackers 2 minimap for a dungeon/area.

Correct pipeline (verified 2026 vs game source + in-game reference):
  TILES  : plain BC7, NO XOR.  decode_bc7(raw,w,h) -> RGBA.
           The map is an ALPHA MASK: corridors = high alpha, void = low.
           (tile luminance is dark in corridors - do NOT use it as color.)
  LAYOUT : place each 512px tile quad at its UI-tree world CENTER.
           Vertical Y-FLIP only (top tile row = highest world y -> top of image).
           No row-band reversal, no half-tile roll.
  ICONS  : Icon_AutoMap01 sheet decoded with UnityPy (NOT texture2ddecoder,
           which mis-decodes BC7 alpha -> salmon/black wrong).
           Each UI-tree 'Icon' object carries its exact sprite name + size +
           world center.  Crop the sprite rect, resize to icon size, center.

Usage: build_minimap.py <dun> <area> <out.png>
"""
import sys, os, glob, json, re, math, collections
import numpy as np
import texture2ddecoder
from PIL import Image, ImageDraw, ImageFont
import UnityPy

BASE = sh2paths.WIN + '/Interface/interface_mapnew_automap_common'
SHEET_CACHE = 'dbg_iconsheet_unitypy.npy'
RECTS_CACHE = 'dbg_iconsheet_rects.json'


def _iter_objects(env):
    for c in env.cabs.values():
        if not hasattr(c, 'objects'):
            continue
        for o in c.objects.values():
            yield o


def load_sheet():
    if os.path.exists(SHEET_CACHE):
        return np.load(SHEET_CACHE)
    env = UnityPy.load(BASE)
    tex = None
    for o in _iter_objects(env):
        tn = o.type.name if hasattr(o.type, 'name') else str(o.type)
        if tn == 'Texture2D' and o.read().m_Name == 'Icon_AutoMap01':
            tex = o.read()
    a = np.array(tex.image.convert('RGBA'))
    np.save(SHEET_CACHE, a)
    return a


def sprite_rects():
    if os.path.exists(RECTS_CACHE):
        return json.load(open(RECTS_CACHE))
    env = UnityPy.load(BASE)
    out = {}
    for o in _iter_objects(env):
        tn = o.type.name if hasattr(o.type, 'name') else str(o.type)
        if tn == 'Sprite':
            s = o.read()
            r = s.m_Rect
            out[s.m_Name] = [int(r.x), int(r.y), int(r.width), int(r.height)]
    json.dump(out, open(RECTS_CACHE, 'w'))
    return out


def crop_sprite(sheet, rect, name):
    x, y, w, h = rect
    # texture y (0=bottom) -> image row (0=top)
    top = sheet.shape[0] - y - h
    return sheet[top:top + h, x:x + w]


def _v(a):
    return np.asarray(a, float)


def two_way_pairs(tol=5.0):
    """Reciprocal SAME-FLOOR warp pairs (the original two-way detector rule).

    Per floor: for warp a, the NEAREST warp b to a.warp_to (same floor only, no
    cross-floor pairs) must be within `tol`, and the nearest warp c to b.warp_to
    must be a itself (reciprocal).  Returns a de-duplicated list of
    (gimmic_id_a, gimmic_id_b) tuples, one per pair.
    """
    gj = json.load(open('gimmicks.json', encoding='utf-8'))
    def dist(a, b):
        return float(np.linalg.norm(_v(a) - _v(b)))
    pairs = []
    seen = set()
    for dun in gj:
        for area in gj[dun]:
            warps = [x for x in gj[dun][area] if x['kind'] == 'MapGimmic_Warp']
            def nearest(pos, excl):
                best, bd = None, 1e9
                for w in warps:
                    if w is excl:
                        continue
                    dd = dist(pos, w['pos'])
                    if dd < bd:
                        bd, best = dd, w
                return best, bd
            for a in warps:
                b, bd = nearest(a['warp_to'], a)
                if b is not None and bd < tol:
                    c, cd = nearest(b['warp_to'], b)
                    if c is not None and cd < tol and c is a:
                        key = tuple(sorted([a['gimmic_id'], b['gimmic_id']]))
                        if key not in seen:
                            seen.add(key)
                            pairs.append(key)
    return pairs


def two_way_warp_ids(tol=5.0):
    """Set of gimmic_ids that belong to a two-way pair (both legs)."""
    return set(i for p in two_way_pairs(tol) for i in p)


_TWO_WAY_CACHE = None


def get_two_way():
    global _TWO_WAY_CACHE
    if _TWO_WAY_CACHE is None:
        _TWO_WAY_CACHE = two_way_warp_ids()
    return _TWO_WAY_CACHE


_TWO_WAY_SKIP_CACHE = None


def get_two_way_skip():
    """Set of gimmic_ids to SKIP so a two-way pair draws ONE arrow, not two.
    Two-way pairs are same-floor; drop the HIGHER-id leg of each pair so the
    lower-id leg survives and is drawn as a single straight green arrow (heads
    on both ends) from its own pos to its warp_to (= the other warp's pos).
    """
    global _TWO_WAY_SKIP_CACHE
    if _TWO_WAY_SKIP_CACHE is None:
        _TWO_WAY_SKIP_CACHE = set(max(p) for p in two_way_pairs())
    return _TWO_WAY_SKIP_CACHE


def _arrowhead(draw, tip, prev, color, size):
    import math
    ang = math.atan2(tip[1] - prev[1], tip[0] - prev[0])
    spread = math.pi / 7
    p1 = (tip[0] - size * math.cos(ang - spread), tip[1] - size * math.sin(ang - spread))
    p2 = (tip[0] - size * math.cos(ang + spread), tip[1] - size * math.sin(ang + spread))
    draw.polygon([tip, p1, p2], fill=color)


def _bezier(p0, p1, p2, n=24):
    out = []
    for i in range(n + 1):
        t = i / n
        a = (1 - t) ** 2
        b = 2 * (1 - t) * t
        c = t ** 2
        out.append((a * p0[0] + b * p1[0] + c * p2[0],
                    a * p0[1] + b * p1[1] + c * p2[1]))
    return out


def draw_warp_arrows(im, dun, area, x0, y0, W, H):
    """Draw same-floor warp-point arrows: tail at the warp's own trigger position
    (`pos`), head at `warp_to`, both down-projected with this floor's ui2world
    transform.  The warp point is its own location on the floor — NOT a door
    (the 06/07/08 door icons are a separate icon-layer marker).
    A warp is drawn ONLY if it is INTERACTABLE: there is a `mp_warp_soul` visual
    (the object the player presses the interact button on) within 2m (3D world)
    of its start.  Warps with no warp-soul are dead/non-interactable and are the
    only thing dropped here (all du00x warps; a few du10x).  Red = one-way (head
    at warp_to); green = two-way (heads at both ends).  Composited over the
    icons, semi-transparent.
    """
    from PIL import ImageDraw
    uf = f'dbg_ui2world_{dun}_{area}.json'
    if not os.path.exists(uf):
        return 0
    u2w = json.load(open(uf))
    s, t = u2w['s'], u2w['t']
    def to_wm(x, z):
        return (x * s + t[0] - x0, (H - 1) - (z * s + t[1] - y0))
    gj = json.load(open('gimmicks.json', encoding='utf-8'))
    key = [k for k in gj.get(dun, {}) if str(k) == area or (str(k).isdigit() and str(int(k)) == area)]
    if not key:
        return 0
    warps = [x for x in gj[dun][key[0]] if x['kind'] == 'MapGimmic_Warp']
    if not warps:
        return 0
    # Interactability: the warp start must have a `mp_warp_soul` visual within
    # 2m (3D world distance) — that is the object you press the interact button
    # on.  du00x dungeons ship no warp-soul at all, so none of their warps are
    # usable; du10x do.
    sf = f'dbg_warpsoul_{dun}_{area}.json'
    if not os.path.exists(sf):
        return 0
    souls = np.array([r[:3] for r in json.load(open(sf, encoding='utf-8'))], dtype=float)
    tw = get_two_way()
    # Two-way pairs are cross-floor, so de-dup GLOBALLY: skip the higher-id leg
    # of each reciprocal pair so only ONE straight green arrow (heads both ends)
    # is drawn, not one per floor.
    skip = get_two_way_skip()
    # Two-way arrows span the TWO warp positions (the partner is on the same
    # floor); warp_to sits ~2.3m past the partner along the corridor, so use the
    # partner's pos as the arrow end, not warp_to.
    gmap = {w['gimmic_id']: w for w in warps}
    partner_id = {}
    for a, b in two_way_pairs():
        partner_id[a] = b
        partner_id[b] = a
    arrows = []
    dropped = 0
    for w in warps:
        if w['gimmic_id'] in skip:
            continue
        # The ONLY filter: interactable iff a warp-soul sits within 2m (3D world)
        # of the start.  No warp-soul -> dead, non-interactable -> dropped.
        if len(souls):
            if float(np.linalg.norm(souls - np.array(w['pos']), axis=1).min()) > 2.0:
                dropped += 1
                continue
        else:
            dropped += 1
            continue
        # Tail = the warp's own trigger position (its warp point on the floor).
        # Not snapped to any door icon.
        p0 = to_wm(w['pos'][0], w['pos'][2])
        is_tw = w['gimmic_id'] in tw
        if is_tw:
            # Two-way: head = the partner's position (same floor), so the arrow
            # spans the two warp positions.
            pr = gmap.get(partner_id.get(w['gimmic_id']))
            if pr is None:
                dropped += 1
                continue
            p2 = to_wm(pr['pos'][0], pr['pos'][2])
        else:
            # One-way: head = warp_to.
            p2 = to_wm(w['warp_to'][0], w['warp_to'][2])
        length = float(np.hypot(p2[0] - p0[0], p2[1] - p0[1]))
        if length < 3:  # drawing guard: no horizontal displacement to draw
            dropped += 1
            continue
        arrows.append((p0, p2, length, is_tw))
    # --- Geometry: greedy placement to minimize overlaps/crossings.  Two-way
    # (straight, fixed) arrows are placed FIRST and act as obstacles; one-way
    # curves are placed longest-first.  Each curve tries a LEFT and a RIGHT bow
    # at increasing magnitudes and keeps the candidate whose sampled points stay
    # farthest from the already-placed arrows (KDTree; cost = points within 14px
    # + 0.5 x points within 40px, ties go to the gentler bow).  When a crossing
    # is unavoidable the larger bows push the curve away, so crossings separate
    # and stay traceable.
    from scipy.spatial import cKDTree
    NS = 32
    BOWS = (0.18, 0.30, 0.45, 0.62)
    tt = np.linspace(0.0, 1.0, NS)
    def curve_pts(a, c, b):
        a = np.asarray(a, dtype=float)
        c = np.asarray(c, dtype=float)
        b = np.asarray(b, dtype=float)
        o = (1 - tt)[:, None]
        t2 = tt[:, None]
        return o * o * a + 2 * o * t2 * c + t2 * t2 * b
    placed, chosen = [], {}
    order = [i for i, a in enumerate(arrows) if a[3]] + sorted(
        (i for i, a in enumerate(arrows) if not a[3]), key=lambda i: -arrows[i][2])
    for i in order:
        p0, p2, length, is_tw = arrows[i]
        mx, my = (p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2
        if is_tw:
            ctrl = (mx, my)  # control at the midpoint => exact straight line
            pts = curve_pts(p0, ctrl, p2)
        else:
            ux, uy = (p2[0] - p0[0]) / length, (p2[1] - p0[1]) / length
            nx, ny = -uy, ux  # left normal
            tree = cKDTree(np.vstack(placed)) if placed else None
            best = None
            for bow in BOWS:
                for sgn in (+1, -1):
                    ctrl = (mx + nx * bow * length * sgn, my + ny * bow * length * sgn)
                    pts = curve_pts(p0, ctrl, p2)
                    if tree is not None:
                        dist, _ = tree.query(pts)
                        cost = float((dist < 14).sum()) + 0.5 * float((dist < 40).sum())
                    else:
                        cost = 0.0
                    if best is None or (cost, bow) < (best[0], best[1]):
                        best = (cost, bow, ctrl, pts)
            ctrl, pts = best[2], best[3]
        chosen[i] = (ctrl, pts)
        placed.append(pts)
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    drawn = 0
    for i, (p0, p2, length, is_tw) in enumerate(arrows):
        ctrl, pts = chosen[i]
        col_line = (86, 224, 128, 165) if is_tw else (255, 74, 74, 165)
        col_head = (86, 224, 128, 220) if is_tw else (255, 74, 74, 220)
        head = max(9, min(20, length * 0.12))
        if is_tw:
            # Two-way: ONE straight green arrow spanning the two warp positions,
            # heads on BOTH ends.
            od.line([p0, p2], fill=col_line, width=5)
            _arrowhead(od, p2, p0, col_head, head)
            _arrowhead(od, p0, p2, col_head, head)
        else:
            # One-way: curved Bézier from pos -> warp_to, single head at warp_to.
            # The head uses the exact Bézier tangent (ctrl -> head).
            od.line([(float(x), float(y)) for x, y in pts], fill=col_line, width=5, joint='curve')
            _arrowhead(od, (float(pts[-1][0]), float(pts[-1][1])), ctrl, col_head, head)
        drawn += 1
    im.alpha_composite(ov)
    if dropped:
        print(f'  dropped {dropped} non-interactable warp(s) (no warp-soul within 2m)')
    return drawn


def main():
    dun, area, out = sys.argv[1], sys.argv[2], sys.argv[3]
    tree = json.load(open(f'dbg_ui_tree_{dun}.json'))
    dims = {}
    tl = f'dbg_automap_texlist_{dun}.json'
    if os.path.exists(tl):
        for r in json.load(open(tl)):
            dims[r['name']] = (r['w'], r['h'])

    # ---- tiles ----
    tiles = {}
    for p in glob.glob(f'automap_{dun}/*.bin'):
        nm = os.path.basename(p)[:-4]
        if re.match(rf'^{re.escape(dun)}_{area}_0_\d+_\d+$', nm):
            tiles[nm] = open(p, 'rb').read()
    quads = {}
    for d in tree:
        s = d.get('sprite')
        if s in tiles and d['active']:
            quads.setdefault(s, d['world'])
    if not quads:
        sys.exit(f'no tile quads for {dun}_{area}')

    xs = [w[0] for w in quads.values()]
    ys = [w[1] for w in quads.values()]
    # icon world positions also influence the canvas bounds
    icon_root = f'{dun}_{area}_0_icon'
    by = {r['pid']: r for r in tree}

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
    icons = [d for d in tree if d['active'] and d['name'] == 'Icon' and in_sub(d, icon_root)]
    if icons:
        xs += [d['world'][0] for d in icons]
        ys += [d['world'][1] for d in icons]
    x0, x1 = int(min(xs) - 300), int(max(xs) + 300)
    y0, y1 = int(min(ys) - 300), int(max(ys) + 300)
    W, H = x1 - x0, y1 - y0
    print(f'{dun}_{area}: {len(tiles)} tiles, {len(icons)} icons, canvas {W}x{H} origin({x0},{y0})')

    # alpha mask canvas (1 px = 1 UI unit)
    acv = np.zeros((H, W), np.float32)
    for nm, raw in tiles.items():
        w = quads.get(nm)
        if not w:
            continue
        tw, th = dims.get(nm, (256, 256))
        px = np.frombuffer(texture2ddecoder.decode_bc7(raw, tw, th), np.uint8).reshape(th, tw, 4)
        if px.shape[0] != 512:
            px = np.array(Image.fromarray(px, 'RGBA').resize((512, 512), Image.NEAREST))
        cx, cy = int(w[0]) - x0, int(w[1]) - y0
        acv[cy - 256:cy + 256, cx - 256:cx + 256] = px[:, :, 3].astype(np.float32)
    # vertical flip: top tile row (highest wy) -> top of image
    acv = acv[::-1]
    mask = acv > 40

    # ---- render base ----
    bg = (24, 26, 30)
    fg = (232, 234, 238)
    canvas = np.empty((H, W, 4), np.uint8)
    canvas[:] = (*bg, 255)
    canvas[mask] = (*fg, 255)
    im = Image.fromarray(canvas, 'RGBA')
    sheet = load_sheet()
    rects = sprite_rects()

    def to_img(wx, wy):
        return int(wx) - x0, H - 1 - (int(wy) - y0)

    # ---- icons ----
    cnt = collections.Counter()
    for d in icons:
        spr = d.get('sprite')
        rect = rects.get(spr)
        if not rect:
            continue
        cnt[spr] += 1
        sp = crop_sprite(sheet, rect, spr)
        sz = (d.get('size') or [rect[2], rect[3]])
        sc = (d.get('scale') or [1.0, 1.0])
        tw = max(1, int(sz[0] * sc[0]))
        th = max(1, int(sz[1] * sc[1]))
        sp = Image.fromarray(sp, 'RGBA').resize((tw, th), Image.LANCZOS)
        cx, cy = to_img(*d['world'])
        im.alpha_composite(sp, (cx - tw // 2, cy - th // 2))

    # ---- warp-point arrows (same-floor: pos -> warp_to) ----
    n_arrows = draw_warp_arrows(im, dun, area, x0, y0, W, H)

    # ---- title bar ----
    names = json.load(open('dungeon_names.json', encoding='utf-8'))
    info = names.get(f'{dun}_{area}')
    if info:
        TH = 60
        bar = Image.new('RGBA', (W, TH), (10, 11, 14, 255))
        bd = ImageDraw.Draw(bar)
        try:
            fnt = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 30)
            fnt_s = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 20)
        except OSError:
            fnt = fnt_s = ImageFont.load_default()
        title = info.get('en') or ''
        if info.get('detail_en'):
            title += '  -  ' + info['detail_en']
        jp = info.get('jp') or ''
        if info.get('detail_jp'):
            jp += ' ' + info['detail_jp']
        bd.text((16, 4), title, font=fnt, fill=(235, 238, 245, 255))
        bd.text((16, 36), jp, font=fnt_s, fill=(150, 158, 170, 255))
        out_im = Image.new('RGBA', (W, H + TH), (10, 11, 14, 255))
        out_im.paste(bar, (0, 0))
        out_im.alpha_composite(im, (0, TH))
        im = out_im
    im.save(out)
    print('icon sprites:', dict(cnt))
    print(f'warp arrows drawn: {n_arrows}')
    print(f'saved {out} ({im.size})')


if __name__ == '__main__':
    main()
