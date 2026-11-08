import sh2paths
#!/usr/bin/env python
"""Per-layer minimap renderer (extends build_minimap.py for multi-layer areas).

Usage:
  build_minimap_layers.py <dun> <area> <out.png> [--layer N] [--all]

  --layer N   render only tile-layer N (default 0)
  --all       render every layer: <out_stem>_L<idx><ext>

Multi-layer areas (du004_0000/0010, du007_0000..0040) ship one pre-rendered
tile set + one icon root per map layer.  The layer -> Y-level assignment and
floor labels come from re/out/dbg_layers_<dun>_<area>.json (solve_layers_labelled.py
or layers.py).

Warp-arrow rules (extend the single-layer pipeline):
  * single-layer areas: unchanged (soul filter, one-way curves, two-way straights).
  * multi-layer: warps are assigned to the layer whose Y band (y_of_layer,
    half-width 0.6*spacing) their pos sits in; a warp whose warp_to is OUTSIDE
    the band is a cross-layer connector -> straight arrow + destination-layer
    badge at the head.
  * two-way pair with legs on different layers -> one straight double-headed
    arrow on EACH leg's layer, badge = the other layer's label.
  * soul filter is bypassed ONLY in areas that have labelled warps
    ('B3->B4へ移動' / 'Warp(B16)' / '扉1_2F') and zero warp-soul objects —
    those warps are floor connectors (du004/du007), not soul-warps.
    Verified: no other dungeon's warp labels match these patterns.
"""
import sys, os, glob, json, re, math, collections
import numpy as np
import texture2ddecoder
from PIL import Image, ImageDraw, ImageFont
import UnityPy

OLD = sh2paths.OLD
OUT = sh2paths.OUT
GAME_IFACE = sh2paths.WIN + '/Interface/interface_mapnew_automap_common'
FONT = r'C:\Windows\Fonts\msyh.ttc'

def P(n): return sh2paths.oldfile(n)
def O(n): return os.path.join(OUT, n)

LABEL_PATS = [re.compile(r'B(\d+)→B(\d+)'), re.compile(r'Warp（B(\d+)）')]


def warp_label_floor(r):
    lab = r.get('label', '') or r.get('go_name', '')
    for p in LABEL_PATS:
        m = p.match(lab)
        if m:
            return True
    m = re.search(r'(\d)F', lab)
    return bool(m)


# ---------- icon sheet (cached in OLD, read-only) ----------

def _iter_objects(env):
    for c in env.cabs.values():
        if not hasattr(c, 'objects'):
            continue
        for o in c.objects.values():
            yield o


def load_sheet():
    c = P('dbg_iconsheet_unitypy.npy')
    if os.path.exists(c):
        return np.load(c)
    env = UnityPy.load(GAME_IFACE)
    tex = None
    for o in _iter_objects(env):
        tn = o.type.name if hasattr(o.type, 'name') else str(o.type)
        if tn == 'Texture2D' and o.read().m_Name == 'Icon_AutoMap01':
            tex = o.read()
    a = np.array(tex.image.convert('RGBA'))
    np.save(c, a)
    return a


def sprite_rects():
    c = P('dbg_iconsheet_rects.json')
    if os.path.exists(c):
        return json.load(open(c))
    env = UnityPy.load(GAME_IFACE)
    out = {}
    for o in _iter_objects(env):
        tn = o.type.name if hasattr(o.type, 'name') else str(o.type)
        if tn == 'Sprite':
            s = o.read()
            r = s.m_Rect
            out[s.m_Name] = [int(r.x), int(r.y), int(r.width), int(r.height)]
    json.dump(out, open(c, 'w'))
    return out


def crop_sprite(sheet, rect, name):
    x, y, w, h = rect
    top = sheet.shape[0] - y - h
    return sheet[top:top + h, x:x + w]


# ---------- two-way pairs (per area, unchanged rule) ----------

def _v(a):
    return np.asarray(a, float)


def two_way_pairs(area_warps, tol=5.0):
    def dist(a, b):
        return float(np.linalg.norm(_v(a) - _v(b)))
    pairs = []
    seen = set()
    def nearest(pos, excl):
        best, bd = None, 1e9
        for w in area_warps:
            if w is excl:
                continue
            dd = dist(pos, w['pos'])
            if dd < bd:
                bd, best = dd, w
        return best, bd
    for a in area_warps:
        b, bd = nearest(a.get('warp_to') or a['pos'], a)
        if b is not None and bd < tol:
            c, cd = nearest(b.get('warp_to') or b['pos'], b)
            if c is not None and cd < tol and c is a:
                key = tuple(sorted([a['gimmic_id'], b['gimmic_id']]))
                if key not in seen:
                    seen.add(key)
                    pairs.append(key)
    return pairs


# ---------- layer info ----------

def layer_info(dun, area):
    f = O(f'dbg_layers_{dun}_{area}.json')
    if os.path.exists(f):
        return json.load(open(f))
    return {'n_layers': 1, 'y_of_layer': [0.0], 'labels': [None], 'spacing': 0.0,
            'matched': True, 'method': 'single'}


def area_warps(dun, area):
    gj = json.load(open(P('gimmicks.json'), encoding='utf-8'))
    key = [k for k in gj.get(dun, {}) if str(k) == area or (str(k).isdigit() and str(int(k)) == area)]
    if not key:
        return []
    return [x for x in gj[dun][key[0]] if x['kind'] == 'MapGimmic_Warp']


def warp_souls(dun, area):
    f = P(f'dbg_warpsoul_{dun}_{area}.json')
    if not os.path.exists(f):
        return np.zeros((0, 3))
    rows = json.load(open(f, encoding='utf-8'))
    return np.array([r[:3] for r in rows], dtype=float) if rows else np.zeros((0, 3))


def keep_warps(warps, souls):
    """Interactability gate (user rule: arrows only for physically interactable
    objects the player can actually use; never on plain doors).  A warp is
    kept iff a warp-soul (mp_warp_soul) sits within 2m of its pos — the only
    hard evidence of in-game interactability.  Soul data exists only for 10
    du10x floors (du101_0020-0050, du102_0020-0040, du103_0020-0040); every
    other area (all du00x, all du007, du101_0000/0010, du102_0000/0010,
    du103_0000/0010) has an empty soul file -> NO warp arrows there.
    (The earlier door-icon-proximity fallback let unplaced editor warps
    through — e.g. du003_0000's 22 'N個目の扉①/②' warps: only 5 sat near a
    _06 icon but their warp_to destinations span the whole map; rejected by
    the user as random. du007_0050's 'Warp（B20）(n)' junk was likewise
    unplaceable. Door icons still render, just without arrows.)"""
    if len(souls) == 0:
        return []
    keep = []
    for w in warps:
        if float(np.linalg.norm(souls - np.array(w['pos']), axis=1).min()) <= 2.0:
            keep.append(w)
    return keep


def band_of(warp, info, L):
    """Layer assignment for a warp pos (multi-layer only)."""
    if info['n_layers'] <= 1:
        return 0, True
    bands = info['y_of_layer']
    sp = info.get('spacing') or 120.0
    half = max(2.0, 0.6 * sp)
    y = warp['pos'][1]
    d = [abs(y - b) for b in bands]
    Lbest = int(np.argmin(d))
    if d[Lbest] > half:
        return Lbest, False
    return Lbest, True


# ---------- arrows ----------

def _arrowhead(draw, tip, prev, color, size):
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
        out.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))
    return out


def _badge(od, p, text, font, col_bg=(16, 18, 24, 120), col_fg=(255, 210, 120, 255)):
    w, h = od.textbbox((0, 0), text, font=font)[2:]
    x, y = p
    od.rounded_rectangle([x - w / 2 - 5, y - h / 2 - 3, x + w / 2 + 5, y + h / 2 + 5],
                         radius=5, fill=col_bg)
    od.text((x - w / 2, y - h / 2 - 1), text, font=font, fill=col_fg)


_PLACED = []   # label boxes (x1,y1,x2,y2) taken this render, map px space


def place_label(d, im, W, H, px, py, tw, th):
    """Label box (top-left) near (px,py): right/left/above/below, avoiding
    all labels drawn so far (portals, pins, rings...) and preferring dark
    off-floor pixels. Returns (lx, ly) or None if nowhere is clean."""
    cand = [(px + 14, py - th / 2), (px - 14 - tw - 12, py - th / 2),
            (px - (tw + 12) / 2, py - th - 12), (px - (tw + 12) / 2, py + 12)]

    def overlaps(lx, ly):
        for (ox1, oy1, ox2, oy2) in _PLACED:
            if not (lx + tw + 6 < ox1 or lx - 6 > ox2 or
                    ly + th < oy1 or ly > oy2):
                return True
        return False

    def darkish(lx, ly):
        cx = min(W - 1, max(0, int(lx + tw / 2)))
        cy = min(H - 1, max(0, int(ly + th / 2)))
        rr, gg, bb = im.getpixel((cx, cy))[:3]
        return rr < 70 and gg < 70 and bb < 70
    best = None
    for lx, ly in cand:
        if not (0 <= lx and lx + tw + 12 <= W and 0 <= ly and ly + th <= H):
            continue
        if overlaps(lx, ly):
            continue
        if darkish(lx, ly):
            best = (lx, ly)
            break
        if best is None:
            best = (lx, ly)
    if best:
        lx, ly = best
        _PLACED.append((lx - 6, ly, lx + tw + 6, ly + th))
    return best


def tag_label(d, im, W, H, px, py, txt, fnt, fg, bg):
    """place_label + draw pill. Returns True when it fit."""
    tw = d.textlength(txt, font=fnt)
    fs = getattr(fnt, 'size', 17)
    th = fs + 6
    pos = place_label(d, im, W, H, px, py, tw, th)
    if not pos:
        return False
    lx, ly = pos
    d.rounded_rectangle((lx - 6, ly, lx + tw + 6, ly + th), 6, fill=bg)
    d.text((lx, ly + 3), txt, font=fnt, fill=fg)
    return True


def draw_portals(im, dun, area, x0, y0, W, H, info, L, tree, by):
    """EN destination label next to each _02 portal icon of layer L.

    The MapGimmic_Portal world positions (MapPortalTable in _commontable.dec)
    are portal-room-LOCAL coords (clustered near the origin, NOT on the map),
    so labels are anchored to the active IconAM02 leaves of the layer's icon
    root (the in-game minimap's own portal markers, one per portal).
    Pairing = document order of both lists (gimmick-ID order); UNVERIFIED.
    Layer for multi-layer areas = MapPortalData.m_SubAreaID. Returns count."""
    pf = O('portals.json')
    if not os.path.exists(pf):
        return 0
    data = json.load(open(pf))
    rows = [r for r in data if r['dun'] == dun and r['area'] == area]
    if info['n_layers'] > 1:
        # multi-layer: m_SubAreaID selects the layer (verified for du007_0000 0/2/6,
        # du004_0010 0/4/6); single-layer areas: subarea is a sub-area id, keep all
        rows = [r for r in rows if r['subarea'] == L]
    if not rows:
        return 0
    root_name = f'{dun}_{area}_{L}_icon'
    ics = []
    for d in tree:  # document order
        if (d['active'] and d.get('sprite') == 'Icon_AutoMap01_02'
                and by.get(d.get('parent_pid'), {}).get('name') == 'IconAM02'
                and by.get(by.get(d.get('parent_pid'), {}).get('parent_pid'), {}).get('name') == root_name):
            w = d['world']
            if all(abs(w[0] - a[0]) > 2 or abs(w[1] - a[1]) > 2 for a in ics):
                ics.append(w)  # dedupe the minimap/PartsTraverse twin copies
    if not ics:
        return 0
    if len(ics) != len(rows):
        print(f'  WARNING {dun}_{area} L{L}: {len(rows)} portals vs {len(ics)} _02 icons; pairing first {min(len(rows), len(ics))}')
    # ImageDraw replaces pixels instead of blending -> draw onto a transparent
    # overlay and alpha_composite so the badge bg is truly semi-transparent
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    # scale label with the floor's extent (canvas px ~= s*world)
    fs = int(max(13, min(34, min(W, H) * 0.02)))
    try:
        fnt = ImageFont.truetype(FONT, fs)
    except OSError:
        fnt = ImageFont.load_default()
    n = 0
    for r, (ix, iz) in zip(rows, ics):
        px, py = int(ix) - x0, H - 1 - (int(iz) - y0)
        _PLACED.append((px - 28, py - 28, px + 28, py + 28))  # icon footprint
        tag_label(od, im, W, H, px, py, ' ' + r['name_en'] + ' ', fnt,
                  (225, 170, 255, 255), (24, 16, 30, 150))
        n += 1
    im.alpha_composite(ov)
    return n


def draw_enemies(im, dun, area, x0, y0, W, H, info, L):
    """Static enemy/boss markers (Task D, 2025-01).

    Sources (both in world space, verified to land on the geometry):
    - re/out/enemy_spawns.json: Gimmic_SpawnEnemy* scene objects. v2 audit of
      ALL 97 bundles (2025-01) finds them on 7 floors: du001_0010 (1, ER41
      horde room), du004_0000 (1), du101_0000 (1), du101_0020 (1), du101_0050
      (18, under the EA13 zone), du102_0040 (36), du103_0040 (28).
      Regular-floor enemies have NO static positions (runtime spawns via
      AreaSpawnTable/EncountPackParamTable — ID tables only; the in-game
      minimap draws them with the 'Enemysymbol' sprite from
      map_resident_data at runtime).
    - event_points.json (old project cache, LIVE memory dump — no static
      source found despite scanning all 19G of StreamingAssets): BossModel
      positions per du10x floor (ident contains 'BossModel').

    Style: enemy spawn = small red dot; boss arena = red target (ring+dot).
    """
    ev = O('enemy_spawns.json')
    if not os.path.exists(ev):
        ev = P('enemy_spawns.json')
    spawns = []
    if os.path.exists(ev):
        spawns = json.load(open(ev)).get(f'{dun}_{area}', [])
    bosses = []
    ep = P('event_points.json')
    if os.path.exists(ep):
        for p in json.load(open(ep, encoding='utf-8')).get(dun, {}).get(area, []):
            if 'BossModel' in p.get('ident', '') and len(p.get('pos', [])) == 3:
                bosses.append(p['pos'])
    if not spawns and not bosses:
        return 0, 0
    u2w = json.load(open(O(f'dbg_ui2world_{dun}_{area}.json') if os.path.exists(O(f'dbg_ui2world_{dun}_{area}.json')) else P(f'dbg_ui2world_{dun}_{area}.json')))
    s, t = u2w['s'], u2w['t']
    def to_wm(x, z):
        return (x * s + t[0] - x0, (H - 1) - (z * s + t[1] - y0))
    def on_layer(y):
        if info['n_layers'] <= 1:
            return True
        bands = info['y_of_layer']
        sp = info.get('spacing') or 120.0
        return min(abs(y - b) for b in bands) <= max(2.0, 0.6 * sp)
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    r = max(5, min(9, min(W, H) * 0.0045))
    n = 0
    for p in spawns:
        if not on_layer(p['pos'][1]):
            continue
        px, py = to_wm(p['pos'][0], p['pos'][2])
        if not (0 <= px < W and 0 <= py < H):
            continue
        od.ellipse((px - r, py - r, px + r, py + r), fill=(235, 55, 45, 235),
                   outline=(255, 215, 130, 200), width=2)
        n += 1
    nb = 0
    for x, y, z in bosses:
        if not on_layer(y):
            continue
        px, py = to_wm(x, z)
        if not (0 <= px < W and 0 <= py < H):
            continue
        rb = r * 1.9
        od.ellipse((px - rb, py - rb, px + rb, py + rb), outline=(255, 60, 60, 230), width=4)
        od.ellipse((px - r * 0.6, py - r * 0.6, px + r * 0.6, py + r * 0.6), fill=(255, 60, 60, 235))
        nb += 1
    if n or nb:
        im.alpha_composite(ov)
    return n, nb


def _pretty_npc(suf):
    s2 = re.sub(r'^\d+', '', suf)
    s2 = re.sub(r'_(\d+)$', ' \\1', s2)
    return ({'rs_fellow': 'R.S.'}.get(s2.lower())
            or re.sub(r'(?<!\d)frost\d', 'frost', s2.lower())
            .replace('_', ' ').title())


def draw_event_positions(im, dun, area, x0, y0, W, H, info, L):
    """Cyan diamonds for map events with extracted stage coordinates
    (re/out/event_positions.json, from demo-graph StCharaSetPos nodes).

    Drawn only on floors listed in the event's EventListAll registration,
    inside the floor's Y band, and only where the projected pixel lands on a
    PAINTED automap tile (kills wrong-canvas duplicates). Label = quest id
    when request-bound, else the event code; text = first dialogue line.
    """
    # NOTE: demo-graph diamonds (event_positions.json) are intentionally NOT
    # drawn any more -- redundant with the exact Points_Event pins; the file
    # stays as extracted data.
    evs = {}
    key = f'{dun}_{area}'
    evs = {k: e for k, e in evs.items() if key in (e.get('areas') or [])}
    # curated overlays (hand-checked hypotheses, e.g. suspected bomb site)
    cp = O('event_overlays.json')
    if os.path.exists(cp):
        for k, e in json.load(open(cp, encoding='utf-8')).items():
            if key in (e.get('areas') or []):
                evs[k] = e
    # ground-truth event/NPC placement points (map_resident_data MapAreaData_
    # EventPlan.Points_Event): ERnn_* -> exact quest-NPC pin; others -> small dot
    np_ = O('event_npc_points.json')
    if os.path.exists(np_):
        npts = json.load(open(np_, encoding='utf-8')).get(key, [])
        for i, it in enumerate(npts):
            ident = it['ident']
            suf = ident.split('_', 1)[1] if '_' in ident else ''
            mq = re.match(r'ER(\d+)_', ident)
            quest = f'ER{int(mq.group(1)):02d}' if mq else None
            is_npc = quest and not suf.lower().endswith(('_hit', '_check'))
            if is_npc:
                evs[f'npc{i}_{ident.lower()}'] = dict(
                    pts=[it['pos']], quest=quest, name=_pretty_npc(suf),
                    col=[240, 130, 240, 235], bg=[28, 10, 28, 200])
            else:
                evs[f'pt{i}_{ident.lower()}'] = dict(pts=[it['pos']], small=True)
    # spawn-point pools -> x marks, grouped by encounter pack (color-coded)
    sp_ = O('spawn_points.json')
    spawn_hits = []
    if os.path.exists(sp_):
        rec = json.load(open(sp_, encoding='utf-8')).get(key) or {}
        for kind in ('enemy', 'mob'):
            for p in rec.get(kind) or []:
                if isinstance(p, dict):
                    spawn_hits.append((kind, p['pos'], p.get('enc') or 0))
                else:
                    spawn_hits.append((kind, p, 0))
    PALETTE = [((200, 150, 70), 'brown'), ((120, 210, 130), 'green'),
               ((100, 170, 235), 'blue'), ((215, 120, 225), 'purple'),
               ((235, 95, 95), 'red'), ((230, 205, 85), 'yellow')]
    GRAY = ((165, 165, 165), 'gray')
    encs = sorted({c for _, _, c in spawn_hits})
    encn = {}
    enp = O('enc_names.json')
    if os.path.exists(enp):
        encn = json.load(open(enp, encoding='utf-8'))
    # color groups: packs with ONE enemy (quest targets) get palette colors;
    # multi-enemy generic packs share gray
    enc_col, single_groups, mixed_names = {}, [], set()
    for c in encs:
        names = encn.get(str(c))
        if names and len(names) == 1:
            single_groups.append((names[0], c))
        else:
            enc_col[c] = GRAY
            mixed_names.update(names or [f'pack #{c}'])
    seen = {}
    for sg, c in single_groups:
        if sg not in seen:
            seen[sg] = PALETTE[len(seen) % len(PALETTE)]
        enc_col[c] = seen[sg]
    # FIXED demon-recon points (devilsearch_points.json): quest items & bombs
    dsv = O('devilsearch_points.json')
    if os.path.exists(dsv):
        JPW = {'時限爆弾': 'Time Bomb', 'キーアイテム': 'Key Item',
               'ブローチ': 'Brooch', 'エリザ': 'Eliza', '壊れた': 'Broken',
               'ペンダント': 'Pendant', '研究ノート': 'Research Notes',
               'ブライトソウル': 'Bright Soul', 'A棟': 'Tower A',
               'B棟': 'Tower B', 'C棟': 'Tower C',
               'リクエスト': '', '探索悪魔': '', '悪魔探索': '',
               '心理テストの本': 'Psychology Test Book',
               '漫才のネタ帳': 'Comedy Script',
               '深草土産の手裏剣': 'Fushimi Souvenir Shuriken',
               '汚れた鍵': 'Dirty Key', '血まみれの鍵': 'Bloody Key',
               '鍵': 'Key', '携帯ゲーム機': 'Handheld Game',
               '桜の造花': 'Artificial Cherry Blossom',
               '謎の通信機': 'Mystery Communicator',
               'ヴィンテージワイン': 'Vintage Wine',
               'パーソナル': 'Personal', 'オーダー': 'Aion Order',
               '固定配信': 'Delivery', '固定配置': 'Placement',
               '固定': 'Fixed', 'ポイント': '', 'ミタマ様': 'Mitama',
               '運河': 'Canal'}
        for i, e in enumerate(json.load(open(dsv, encoding='utf-8')).get(key, [])):
            if not e.get('fixed'):
                continue
            m = re.search(r'[（(]([^)）]*)[)）]', e['label'])
            core = m.group(1) if m else e['label']
            tr = core
            for k, v in JPW.items():
                tr = tr.replace(k, v)
            tr = tr.replace('_', ' ').replace('ポイント', '').strip(' -')
            tr = re.sub(r'(?<=[a-zA-Z])(\d)$', r' \1', tr.strip(' -')) or core
            is_bomb = '時限爆弾' in core
            generic = bool(re.search(r'固定|配信|配置', e['label']))
            if 'キーアイテム' in e['label']:
                tr = 'Key Item - ' + tr
            elif 'パーソナル' in e['label'] and not generic:
                tr = 'Personal - ' + tr
            elif 'オーダー' in core:
                tr = 'Aion Order ' + tr
            elif 'リクエスト' in e['label'] and not is_bomb:
                tr = 'Quest item - ' + tr
            evs[f'ds{i}'] = dict(pts=[e['pos']], quest='ER43' if is_bomb else None,
                                 name=tr + ('' if is_bomb else ''),
                                 text=None, small=bool(generic and not is_bomb),
                                 col=[255, 200, 60, 240] if is_bomb else [255, 200, 60, 220],
                                 bg=[40, 30, 0, 200])
    if not evs and not spawn_hits:
        return 0, frozenset(), [], {}
    u2wp = O(f'dbg_ui2world_{dun}_{area}.json')
    if not os.path.exists(u2wp):
        u2wp = P(f'dbg_ui2world_{dun}_{area}.json')
    if not os.path.exists(u2wp):
        return 0, frozenset(), [], {}
    u2w = json.load(open(u2wp))
    s, t = u2w['s'], u2w['t']
    FONT_SM = ImageFont.truetype(FONT, 17)
    bands = info['y_of_layer']
    sp = info.get('spacing') or 120.0
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    drawn = 0
    placed = []
    notes = []
    pinned = set()
    small_drawn = 0
    small_gold = 0
    for (kind, p, c) in spawn_hits:
        x, y, z = p
        bi = min(range(len(bands)), key=lambda k: abs(bands[k] - y))
        if info['n_layers'] > 1 and (bi != L or abs(bands[bi] - y) > 5):
            continue
        px = x * s + t[0] - x0
        py = (H - 1) - (z * s + t[1] - y0)
        if not (4 <= px < W - 4 and 4 <= py < H - 4):
            continue
        r_, g_, b_ = im.getpixel((int(px), int(py)))[:3]
        if r_ < 70 and g_ < 70 and b_ < 70:
            continue    # dark canvas = off the floor plane
        scol = tuple((enc_col.get(c) or GRAY)[0] + (230,)) if kind == 'enemy' \
            else (120, 210, 130, 230)
        d.line((px - 6, py - 6, px + 6, py + 6), fill=scol, width=4)
        d.line((px - 6, py + 6, px + 6, py - 6), fill=scol, width=4)
        drawn += 1
    enemy_cols = {}
    for i, (sg, (cname, cnameen)) in enumerate(seen.items()):
        enemy_cols.setdefault(sg, cname)
        notes.append((f'spawnq{i}', {'note': f'{cnameen} x: {sg} spawn spots',
                                     'col': list(cname)}))
    if mixed_names:
        for nm in mixed_names:
            enemy_cols.setdefault(nm, GRAY[0])
        notes.append(('spawnsx', {'note': 'gray x: general packs (' +
                           '/'.join(sorted(mixed_names)) + ')',
                                  'col': [165, 165, 165]}))
    if any(k == 'mob' for k, _, _ in spawn_hits):
        notes.append(('spawns_m', {'note':
            'green x: roaming-mob spawn spots',
            'col': [150, 220, 140], 'bg': (0, 28, 10, 170)}))
    for code, e in sorted(evs.items()):
        pts = e.get('pts') or []
        if not pts and e.get('note'):
            notes.append((code, e))
            continue
        if len(pts) > 2:  # party staging / walk route -> centroid
            xs = [q[0] for q in pts]
            zs = [q[2] for q in pts]
            ys = [q[1] for q in pts]
            pts = [(round(sum(xs) / len(xs), 2), round(sum(ys) / len(ys), 2),
                    round(sum(zs) / len(zs), 2))]
        for (x, y, z) in pts:
            bi = min(range(len(bands)), key=lambda k: abs(bands[k] - y))
            if abs(bands[bi] - y) > max(2.0, 0.6 * sp):
                continue
            if info['n_layers'] > 1 and bi != L:
                continue
            px = x * s + t[0] - x0
            py = (H - 1) - (z * s + t[1] - y0)
            if not (4 <= px < W - 4 and 4 <= py < H - 4):
                continue
            r_, g_, b_ = im.getpixel((int(px), int(py)))[:3]
            if r_ < 70 and g_ < 70 and b_ < 70:
                continue    # dark canvas = off the floor plane
            if e.get('small'):
                col = tuple((e.get('col') or (0, 200, 200, 200))[:4])
                d.ellipse((px - 6, py - 6, px + 6, py + 6),
                          fill=col, outline=(255, 255, 255, 255))
                drawn += 1
                if col[0] > 200:
                    small_gold += 1
                else:
                    small_drawn += 1
                continue
            r = 11
            col = tuple((e.get('col') or (0, 220, 220, 235))[:4])
            d.polygon([(px, py - r), (px + r, py), (px, py + r), (px - r, py)],
                      fill=col, outline=(255, 255, 255, 255))
            q = e.get('quest')
            # short tag near the pin: 'ER41 R.S.' (quest title lives in the
            # legend; dialogue text removed for cleanliness)
            txt = (q + ' ' + e['name']) if q and e.get('name') else \
                  (q or e.get('name') or code.upper())
            tag_label(d, im, W, H, px, py, txt, FONT_SM,
                      tuple((e.get('col') or (0, 220, 220))[:3]) + (255,)
                      if e.get('col') else (180, 255, 255, 255),
                      tuple(e.get('bg') or (0, 60, 70, 200)))
            if q:
                pinned.add(q)
            drawn += 1
    if small_gold:
        notes.append(('dotsg', {'note':
            'small gold dots: Demon-Recon sweep spots (dig for items)',
            'col': [255, 205, 90], 'bg': (30, 22, 0, 170)}))
    if small_drawn:
        notes.append(('dots', {'note':
            'cyan dots: event trigger zones (walk near to fire)',
            'col': [0, 220, 220], 'bg': (0, 30, 34, 170)}))
    y = H - 8
    for code, e in reversed(notes):
        q = e.get('quest')
        nt = (('[' + q + '] ' if q else '') + e['note'])
        col = tuple(e.get('col') or (255, 170, 60))[:3] + (255,)
        bg = tuple(e.get('bg') or (30, 20, 0, 170))
        tw = d.textlength(nt, font=FONT_SM)
        if tw > W - 24:  # wrap once, taller box
            half = nt[:len(nt) // 2].rsplit(' ', 1)[0]
            d.rounded_rectangle((8, y - 52, W - 8, y - 4), 6, fill=bg)
            d.text((14, y - 48), nt[:len(half)], font=FONT_SM, fill=col)
            d.text((14, y - 26), nt[len(half):].strip(), font=FONT_SM, fill=col)
            y -= 56
        else:
            d.rounded_rectangle((8, y - 26, tw + 20, y - 4), 6, fill=bg)
            d.text((14, y - 24), nt, font=FONT_SM, fill=col)
            y -= 28
        drawn += 1
    if drawn:
        im.alpha_composite(ov)
    gold_names = [e.get('name') for c, e in evs.items()
                  if c.startswith('ds') and e.get('name') and not e.get('small')]
    return drawn, frozenset(pinned), gold_names, enemy_cols


def draw_objectives(im, dun, area, x0, y0, W, H, info, L, skip_q=(), gold=(),
                    enemy_cols=None):
    """Quest/objective badges (Task E2, 2025-01).

    No world coordinates exist for quest targets (QuestTargetData carries only
    mapPlaceId+areaId, all ER-quest areaId=0; 21/24 point to unmapped place
    1000), so badges are edge-pinned, not map-pinned:
    - Aion orders (AionOrderData, 45): targets DO carry floor granularity
      (mapPlaceId 1101/1102/1103 = du101/du102/du103, VERIFIED against the
      'Soul Matrix - Arrow/Milady/Saizo Sector' map titles; areaId = floor).
      Shown on the matching floor, or all floors with (L{n}) on composites.
    - ER quest targets (4 resolve to du002/du003/du004/du005 at place level,
      no floor): shown on EVERY floor of the target dungeon.
    Gold = aion order, blue = quest. Semi-transparent (overlay+composite).

    Region isolation (LIVE-dump sourced, boss arenas are fixed rooms):
    - 'Target:' orders (type 2): event_points.json carries one 'EAxx_Boss'
      point per order on the exact floor (15/15 match) -> gold ring + label
      around the boss arena.
    - cleanup orders (type 1) on floors with static minion spawns (du102_0040,
      du103_0040): translucent gold bounding rect around the spawn dots.
    Other cleanups have no position source (runtime spawn tables only).
    """
    def digest(f):
        p = os.path.join(os.path.dirname(__file__), '..', 'out', 'digest', f)
        return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None
    aion = digest('aion_orders.json')
    quests = digest('quests.json')
    placements = digest('object_placements.json') or {}
    # structured legend: per quest -> 'ERnn <request name>' line + sub-marks;
    # aion orders get plain gold lines. Corner badges replaced (mess cleanup).
    QTITLE = {q['id']: (q.get('title') or '') for q in (quests or [])}
    marks = collections.defaultdict(list)   # qid -> [(text, fg)]
    rows = []                               # aion lines (text, fg)
    # --- magenta: quest NPC/object physically registered on THIS floor
    # (EventListObjectAll join; e.g. er43_natsuhiko -> du004_0000, ER43) ---
    qids_placed = set()
    by_quest = {}
    for it in placements.get(f'{dun}_{area}', []):
        if not it.get('quest'):
            continue
        suf = it['itemId'].split('_', 1)[1] if '_' in it['itemId'] else it['itemId']
        nm = _pretty_npc(suf)
        by_quest.setdefault(it['quest'], []).append(nm)
    for qid, names in sorted(by_quest.items()):
        qids_placed.add(qid)
        uniq = sorted(set(names))
        txt = '/'.join(uniq[:3]) + (f" +{len(set(names)) - 3} more" if len(set(names)) > 3 else '')
        marks[qid].append(('◆ Find ' + txt + ' — ' +
                           ('pinned' if qid in skip_q else
                            'somewhere on this floor, no pin'),
                           (240, 130, 240, 255)))
    if aion:
        for o in aion:
            for tg in o['targets']:
                if tg.get('dun') != dun or tg.get('floor') is None:
                    continue
                fl = tg['floor']
                if L is not None and fl != int(area):
                    continue
                nm = tg.get('name') or f"id {tg.get('id')}"
                if tg['type'] == 2:
                    txt = f"Target: {nm}" + (f" x{tg['count']}" if (tg.get('count') or 1) > 1 else '')
                elif tg['type'] == 1:
                    txt = f"{nm} x{tg['count']}"  # ASCII x: the font mis-measures U+00D7
                else:
                    txt = f"Item: {nm}"
                if L is None:
                    txt += f" (L{fl // 10})"
                rows.append((f"{o['id']}  {txt}", (255, 205, 80, 255)))
    if quests:
        # eMapPlaceID (dump/csharp/Assembly-CSharp.decompiled.cs): 1000=DU000_NONE
        # (no dungeon by design), 1001..1007=du00x, 1100..1105=Soul Matrix.
        # Blue = target dungeon (every floor of it); cyan = 'defeat enemy' quest
        # located via AreaSpawnTable/EnemySpawnTable join (dungeon+floor of the
        # enemy's spawns); blue requester badge when the NPC itself is in a
        # dungeon (requesterMapId 1001-1007) and no target badge covers it.
        PL2DUN = {1001: 'du001', 1002: 'du002', 1003: 'du003', 1004: 'du004',
                  1005: 'du005', 1007: 'du007', 1101: 'du101', 1102: 'du102', 1103: 'du103'}
        for q in quests:
            qid = q.get('id')
            got = False
            for tt in q.get('targets') or []:
                d = PL2DUN.get(tt.get('mapPlaceId'))
                if d == dun:
                    marks[qid].append(('story target — this dungeon',
                                       (130, 190, 255, 255)))
                    got = True
                if tt.get('type') == 1:
                    for loc in tt.get('spawn_locs') or []:
                        if loc.get('dun') == dun and (L is None or loc.get('floor') == int(area)):
                            nm = tt.get('enemyName') or f"id {tt.get('id')}"
                            c = (enemy_cols or {}).get(nm) or (222, 166, 90)
                            marks[qid].append((f"x {nm} x{tt.get('count')} - rolls from enemy spawn x marks",
                                               tuple(c) + (255,)))
                            got = True
                            break
            if q.get('requester_dun') == dun and not got and q.get('requester') \
                    and qid not in qids_placed:
                marks[qid].append((f"Find {q['requester']} — somewhere here, no pin",
                                   (130, 190, 255, 255)))
    if not marks and not rows:
        return im
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    fs = int(max(13, min(26, min(W, H) * 0.016)))
    try:
        fnt = ImageFont.truetype(FONT, fs)
    except OSError:
        fnt = ImageFont.load_default()
    lines = []   # (text, fg, indent)
    for qid in sorted(marks):
        lines.append((f"{qid}  {QTITLE.get(qid, '')}", (255, 255, 255, 255), 0))
        for t, fg in marks[qid]:
            lines.append((t, fg, 1))
    for t, fg in rows:
        lines.append((t, fg, 0))
    for nm in sorted(set(gold or ())):
        lines.append(('◆ ' + nm + ' — gold pin on map', (255, 205, 90, 255), 0))
    n = len(lines)
    lw = max(od.textbbox((0, 0), t, font=fnt)[2] for t, _, _ in lines)
    lh = fs + 6
    block_h = n * lh + 16
    # legend goes in its OWN column right of the map (never overlaps tiles)
    new = Image.new('RGBA', (W + lw + 34, H), (24, 26, 30, 255))
    new.paste(im, (0, 0))
    ld = ImageDraw.Draw(new)
    ly0 = max(16, (H - block_h) // 2)
    ld.rounded_rectangle((W + 8, ly0, W + lw + 26, ly0 + block_h), 10,
                         fill=(10, 11, 14, 220))
    y = ly0 + 10
    for t, fg, ind in lines:
        ld.text((W + 20 + (0 if ind == 0 else fs), y), t, font=fnt, fill=fg)
        y += lh
    im = new
    W, H = im.size
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    ring_targets = []  # (oid, onm, px, py) - composited LAST, own overlay
    # --- region isolation + dot labels (world space) ---
    esf = O('enemy_spawns.json')
    if not os.path.exists(esf):
        esf = P('enemy_spawns.json')
    dot_spawns = json.load(open(esf)).get(f'{dun}_{area}', []) if os.path.exists(esf) else []
    if (aion and dun.startswith('du1')) or dot_spawns:
        u2w = json.load(open(O(f'dbg_ui2world_{dun}_{area}.json') if os.path.exists(O(f'dbg_ui2world_{dun}_{area}.json')) else P(f'dbg_ui2world_{dun}_{area}.json')))
        s, t = u2w['s'], u2w['t']

        def to_wm(x, z):
            return (x * s + t[0] - x0, (H - 1) - (z * s + t[1] - y0))

        def on_layer(yy):
            if info['n_layers'] <= 1:
                return True
            sp = info.get('spacing') or 120.0
            return min(abs(yy - b) for b in info['y_of_layer']) <= max(2.0, 0.6 * sp)
        # Target orders: gold ring around the BossModel (the verified boss-room
        # position). The EAxx_Boss event points are triggers OUTSIDE the room
        # (85m away) - do NOT anchor to them. 1 BossModel per floor == the
        # single 'Target:' order on that floor.
        epf = P('event_points.json')
        pts = json.load(open(epf, encoding='utf-8')).get(dun, {}).get(area, []) if os.path.exists(epf) else []
        r0 = max(5, min(9, min(W, H) * 0.0045))
        t2 = [(o, tg) for o in (aion or []) for tg in o['targets']
              if tg.get('dun') == dun and tg.get('floor') == int(area) and tg.get('type') == 2]
        if t2:
            oid, onm = t2[0][0]['id'], t2[0][1].get('name', '')
            for p in pts:
                if 'BossModel' in p.get('ident', '') and len(p.get('pos', [])) == 3 and on_layer(p['pos'][1]):
                    px, py = to_wm(p['pos'][0], p['pos'][2])
                    if 0 <= px < W and 0 <= py < H:
                        ring_targets.append((oid, onm, px, py))
        # cleanup orders: gold zone rect around the static minion spawn dots
        dots = [sp['pos'] for sp in dot_spawns if on_layer(sp['pos'][1])]
        if len(dots) >= 3 and aion:
            for o in aion:
                for tg in o['targets']:
                    if tg.get('dun') == dun and tg.get('floor') == int(area) and tg.get('type') == 1:
                        xs = [to_wm(d[0], d[2])[0] for d in dots]
                        ys = [to_wm(d[0], d[2])[1] for d in dots]
                        m = fs * 1.6
                        od.rounded_rectangle([min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m],
                                             radius=10, outline=(255, 200, 60, 220), width=3, fill=(255, 190, 40, 26))
                        tag_label(od, im, W, H, min(xs) - m + 10, min(ys) - m - 6,
                                  f"{o['id']} {tg.get('name')} x{tg['count']} (spawn zone)",
                                  fnt, (255, 210, 90, 255), (30, 24, 8, 190))
        # FEW static dots (<=3): pin the objectives that resolve to THIS floor
        # right under the dot (draw_enemies draws the dot itself). Data-driven:
        # quest type-1 targets whose AreaSpawnTable floors include this floor,
        # plus cleanup orders on this floor. Answers 'find R.S. -> where?' with
        # a label attached to the actual room, not just the corner badge list.
        if dots and len(dots) <= 3:
            labs = []
            if quests:
                for q in quests:
                    for tt in q.get('targets') or []:
                        if tt.get('type') == 1 and any(
                                l.get('dun') == dun and l.get('floor') == int(area)
                                for l in tt.get('spawn_locs') or []):
                            labs.append(f"{q['id']} {tt.get('enemyName')} x{tt.get('count')}")
            if aion:
                for o in aion:
                    for tg in o['targets']:
                        if tg.get('dun') == dun and tg.get('floor') == int(area) and tg.get('type') == 1:
                            labs.append(f"{o['id']} {tg.get('name')} x{tg.get('count')}")
            if labs:
                fns = int(max(11, fs - 3))
                try:
                    fn2 = ImageFont.truetype(FONT, fns)
                except OSError:
                    fn2 = fnt
                px, py = to_wm(dots[0][0], dots[0][2])
                for i, ltxt in enumerate(dict.fromkeys(labs)):
                    tag_label(od, im, W, H, px, py + 16 + i * (fns + 8),
                              ltxt, fn2, (255, 120, 110, 255), (40, 8, 6, 190))
    im.alpha_composite(ov)
    # Boss rings go on a SEPARATE overlay composited last. This PIL version
    # REPLACES a pixel's alpha when a translucent fill is drawn over another
    # translucent shape: a ring (a=235) drawn before the zone-rect fill
    # (a=26) gets its alpha clobbered to 26 and becomes invisible after
    # compositing. Verified with a minimal repro (repro3.py behaviour).
    if ring_targets:
        ov2 = Image.new('RGBA', im.size, (0, 0, 0, 0))
        od2 = ImageDraw.Draw(ov2)
        for oid, onm, px, py in ring_targets:
            rg = r0 * 3.4  # sits just outside the red boss ring
            od2.ellipse((px - rg, py - rg, px + rg, py + rg), outline=(255, 200, 60, 235), width=4)
            tag_label(od2, im, W, H, px, py - rg - 10, f"{oid} {onm}", fnt,
                      (255, 210, 90, 255), (30, 24, 8, 200))
        im.alpha_composite(ov2)
    return im


def draw_warp_arrows(im, dun, area, x0, y0, W, H, info, L):
    """Draw warp arrows for tile-layer L of a (possibly multi-layer) area."""
    uf = O(f'dbg_ui2world_{dun}_{area}.json')
    if not os.path.exists(uf):
        uf = P(f'dbg_ui2world_{dun}_{area}.json')
    if not os.path.exists(uf):
        return 0
    u2w = json.load(open(uf))
    s, t = u2w['s'], u2w['t']
    def to_wm(x, z):
        return (x * s + t[0] - x0, (H - 1) - (z * s + t[1] - y0))
    warps = area_warps(dun, area)
    if not warps:
        return 0
    souls = warp_souls(dun, area)
    kept = keep_warps(warps, souls)
    multi = info['n_layers'] > 1
    # assign warps to layers
    on_layer, dropped = [], 0
    for w in kept:
        LL, ok = band_of(w, info, L)
        if not ok or LL != L:
            dropped += 1
            continue
        on_layer.append(w)
    allmap = {w['gimmic_id']: w for w in warps}
    pairs = two_way_pairs(warps)
    pair_set = set(i for p in pairs for i in p)
    partner = {}
    for a, b in pairs:
        partner[a] = b
        partner[b] = a
    # same-layer two-way pairs: skip higher-id leg (one arrow per pair)
    same_layer_pairs = []
    for a, b in pairs:
        la, _ = band_of(allmap[a], info, L)
        lb, _ = band_of(allmap[b], info, L)
        if la == lb == L:
            same_layer_pairs.append((a, b))
    skip = {max(p) for p in same_layer_pairs}
    arrows = []   # (p0, p2, length, is_tw, badge_text or None)
    for w in on_layer:
        if w['gimmic_id'] in skip:
            continue
        p0 = to_wm(w['pos'][0], w['pos'][2])
        is_tw = w['gimmic_id'] in pair_set
        badge = None
        if is_tw:
            pr = allmap.get(partner.get(w['gimmic_id']))
            if pr is None:
                dropped += 1
                continue
            lp, okp = band_of(pr, info, L)
            p2 = to_wm(pr['pos'][0], pr['pos'][2])
            if multi and (not okp or lp != L):
                # cross-layer two-way: straight arrow on both layers + badge
                badge = ('→' + (info['labels'][lp] or f'L{lp}')).strip()
        else:
            wt = w.get('warp_to') or w['pos']
            p2 = to_wm(wt[0], wt[2])
            if multi:
                d = [abs(wt[1] - b) for b in info['y_of_layer']]
                Ld = int(np.argmin(d))
                if Ld != L:
                    badge = ('→' + (info['labels'][Ld] or f'L{Ld}')).strip()
        length = float(np.hypot(p2[0] - p0[0], p2[1] - p0[1]))
        if length < 3:
            dropped += 1
            continue
        arrows.append((p0, p2, length, is_tw, badge))
    if not arrows:
        if dropped:
            print(f'  [L{L}] no arrows ({dropped} off-layer/dropped)')
        return 0
    # greedy placement (two-way/straight first as obstacles, curves longest-first)
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
    straight = lambda a: a[3] or a[4] is not None   # two-way or cross-layer -> straight
    order = [i for i, a in enumerate(arrows) if straight(a)] + sorted(
        (i for i, a in enumerate(arrows) if not straight(a)), key=lambda i: -arrows[i][2])
    for i in order:
        p0, p2, length, is_tw, badge = arrows[i]
        mx, my = (p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2
        if straight((p0, p2, length, is_tw, badge)):
            ctrl = (mx, my)
            pts = curve_pts(p0, ctrl, p2)
        else:
            ux, uy = (p2[0] - p0[0]) / length, (p2[1] - p0[1]) / length
            nx, ny = -uy, ux
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
    try:
        bfont = ImageFont.truetype(FONT, 18)
    except OSError:
        bfont = ImageFont.load_default()
    drawn = 0
    for i, (p0, p2, length, is_tw, badge) in enumerate(arrows):
        ctrl, pts = chosen[i]
        col_line = (86, 224, 128, 165) if is_tw else (255, 74, 74, 165)
        col_head = (86, 224, 120, 220) if is_tw else (255, 74, 74, 220)
        head = max(9, min(20, length * 0.12))
        if is_tw or badge:
            od.line([p0, p2], fill=col_line, width=5)
            _arrowhead(od, p2, p0, col_head, head)
            if is_tw:
                _arrowhead(od, p0, p2, col_head, head)
        else:
            od.line([(float(x), float(y)) for x, y in pts], fill=col_line, width=5, joint='curve')
            _arrowhead(od, (float(pts[-1][0]), float(pts[-1][1])), ctrl, col_head, head)
        if badge:
            # badge just past the head
            ang = math.atan2(p2[1] - p0[1], p2[0] - p0[0])
            _badge(od, (p2[0] + 26 * math.cos(ang), p2[1] + 26 * math.sin(ang)), badge, bfont)
        drawn += 1
    im.alpha_composite(ov)
    if dropped:
        print(f'  [L{L}] off-layer/dropped warps: {dropped}')
    return drawn


# ---------- main ----------

def render(dun, area, L, out):
    info = layer_info(dun, area)
    if L >= info['n_layers']:
        sys.exit(f'layer {L} out of range (n={info["n_layers"]})')
    tree = json.load(open(P(f'dbg_ui_tree_{dun}.json')))
    dims = {}
    tl = P(f'dbg_automap_texlist_{dun}.json')
    if os.path.exists(tl):
        for r in json.load(open(tl)):
            dims[r['name']] = (r['w'], r['h'])

    tiles = {}
    for p in glob.glob(P(f'automap_{dun}/*.bin')):
        nm = os.path.basename(p)[:-4]
        if re.match(rf'^{re.escape(dun)}_{re.escape(area)}_{L}_\d+_\d+$', nm):
            tiles[nm] = p
    quads = {}
    for d in tree:
        s = d.get('sprite')
        if s in tiles and d['active']:
            quads.setdefault(s, d['world'])
    if not quads:
        sys.exit(f'no tile quads for {dun}_{area} layer {L}')

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
    icons = [d for d in tree if d['active'] and d['name'] == 'Icon' and in_sub(d, icon_root)]
    xs = [w[0] for w in quads.values()] + [d['world'][0] for d in icons]
    ys = [w[1] for w in quads.values()] + [d['world'][1] for d in icons]
    x0, x1 = int(min(xs) - 300), int(max(xs) + 300)
    y0, y1 = int(min(ys) - 300), int(max(ys) + 300)
    W, H = x1 - x0, y1 - y0
    print(f'{dun}_{area} L{L}: {len(tiles)} tiles, {len(icons)} icons, canvas {W}x{H} origin({x0},{y0})')

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
    mask = acv > 40

    canvas = np.empty((H, W, 4), np.uint8)
    canvas[:] = (24, 26, 30, 255)
    canvas[mask] = (232, 234, 238, 255)
    im = Image.fromarray(canvas, 'RGBA')
    sheet = load_sheet()
    rects = sprite_rects()

    def to_img(wx, wy):
        return int(wx) - x0, H - 1 - (int(wy) - y0)

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

    _PLACED.clear()
    n_portals = draw_portals(im, dun, area, x0, y0, W, H, info, L, tree, by)
    n_en, n_bs = draw_enemies(im, dun, area, x0, y0, W, H, info, L)
    n_arrows = draw_warp_arrows(im, dun, area, x0, y0, W, H, info, L)
    n_ev, pinned_ev, gold_ev, ec_ev = draw_event_positions(im, dun, area, x0, y0, W, H, info, L)
    im = draw_objectives(im, dun, area, x0, y0, W, H, info, L,
                         skip_q=pinned_ev, gold=gold_ev, enemy_cols=ec_ev)
    W, H = im.size    # legend column may have widened the canvas

    # title bar
    names = json.load(open(P('dungeon_names.json'), encoding='utf-8'))
    info_nm = names.get(f'{dun}_{area}')
    TH = 60
    bar = Image.new('RGBA', (W, TH), (10, 11, 14, 255))
    bd = ImageDraw.Draw(bar)
    try:
        fnt = ImageFont.truetype(FONT, 30)
        fnt_s = ImageFont.truetype(FONT, 20)
    except OSError:
        fnt = fnt_s = ImageFont.load_default()
    title = (info_nm.get('en') if info_nm else '') or ''
    if info_nm and info_nm.get('detail_en'):
        title += '  -  ' + info_nm['detail_en']
    if info['n_layers'] > 1:
        lab = info['labels'][L] or f'layer {L}'
        title += f'   [Layer {L + 1}/{info["n_layers"]} · {lab}]'
    jp = (info_nm.get('jp') if info_nm else '') or ''
    if info_nm and info_nm.get('detail_jp'):
        jp += ' ' + info_nm['detail_jp']
    bd.text((16, 4), title, font=fnt, fill=(235, 238, 245, 255))
    bd.text((16, 36), jp, font=fnt_s, fill=(150, 158, 170, 255))
    out_im = Image.new('RGBA', (W, H + TH), (10, 11, 14, 255))
    out_im.paste(bar, (0, 0))
    out_im.alpha_composite(im, (0, TH))
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    out_im.save(out)
    print('icon sprites:', dict(cnt), f'| portal labels: {n_portals}')
    print(f'warp arrows drawn: {n_arrows}')
    print(f'saved {out} ({out_im.size})')


if __name__ == '__main__':
    args = sys.argv[1:]
    alll = '--all' in args
    args = [a for a in args if a != '--all']
    layer = 0
    if '--layer' in args:
        i = args.index('--layer')
        layer = int(args[i + 1])
        del args[i:i + 2]
    dun, area, out = args[0], args[1], args[2]
    if alll:
        info = layer_info(dun, area)
        stem, ext = os.path.splitext(out)
        for L in range(info['n_layers']):
            render(dun, area, L, f'{stem}_L{L}{ext}')
    else:
        render(dun, area, layer, out)
