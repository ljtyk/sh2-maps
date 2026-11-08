import sh2paths
# -*- coding: utf-8 -*-
"""Probe: do dungeon-event demo stage positions (StCharaSetPos floats) land on
the real floor when projected with the fitted ui2world transform?

Collects (x,y,z) triples from StCharaSetPos / StCharaMoveRoute nodes of
demo_dungeon_{ed,bd,em}0X_* bundles (world-space staging coords, VERIFIED to
exist in ed05_012/018), then overlays them on re-rendered maps of a dungeon.

Run:  "$PY" -X utf8 re/tools/probe_stage_coords.py du004
"""
import json
import os
import struct
import sys
import glob as _glob

import UnityPy
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_minimap_layers as B  # noqa: E402

DEMO = sh2paths.WIN + '/Demo'
OUT = os.path.join(HERE, '..', 'out')
POS_CLASSES = ('StCharaSetPos', 'StCharaMoveRoute')


def demo_positions(family):
    """{bundle: [(x,y,z), ...]} over demo_dungeon_<family>_* bundles."""
    out = {}
    for p in _glob.glob(os.path.join(DEMO, f'demo_dungeon_{family}_*')):
        if p.endswith('.manifest'):
            continue
        try:
            env = UnityPy.load(p)
        except Exception:
            continue
        scripts = {o.path_id: str(o.read().m_ClassName)
                   for o in env.objects if o.path_id and o.type == 115}
        pts = []
        for o in env.objects:
            if o.type != 114:
                continue
            try:
                d = o.read()
                cls = scripts.get(d.m_Script.m_PathID, '')
            except Exception:
                continue
            if cls not in POS_CLASSES:
                continue
            raw = o.get_raw_data()
            for off in range(0, len(raw) - 11):
                a, b, c = struct.unpack_from('<3f', raw, off)
                if all(1.5 < abs(v) < 400 for v in (a, b, c)):
                    pts.append((round(a, 2), round(b, 2), round(c, 2)))
        if pts:
            out[os.path.basename(p)] = pts
    return out


def main():
    dun = sys.argv[1] if len(sys.argv) > 1 else 'du004'
    fam = dun[-2:]  # du004 -> 04 (family numbering is off-by-one: du004 events are 05)
    fam = f'{int(fam) + 1:02d}'
    pos = demo_positions('e' + 'd' + fam) or demo_positions('bd' + fam)
    allp = demo_positions('ed' + fam)
    allp.update(demo_positions('bd' + fam))
    allp.update(demo_positions('em' + fam))
    print('bundles with stage positions:', len(allp))
    for b, pts in allp.items():
        print('  ', b, pts[:6])
    combos = [l.split() for l in open(
        sh2paths.COMBOS, encoding='utf-8')
        if l.strip().split()[0] == dun]
    ctx = {}
    infos = {}
    orig_obj = B.draw_objectives

    def wrap(im, d, a, x0, y0, W, H, info, L):
        ctx[L] = (x0, y0, W, H, info)
        infos[a] = info
        return orig_obj(im, d, a, x0, y0, W, H, info, L)
    B.draw_objectives = wrap
    for d, a in combos:
        u2wf = os.path.join(OUT, f'dbg_ui2world_{d}_{a}.json')
        if not os.path.exists(u2wf):
            continue
        u2w = json.load(open(u2wf))
        s, t = u2w['s'], u2w['t']
        stem = os.path.join(OUT, 'probe_stage', f'{d}_{a}')
        os.makedirs(os.path.dirname(stem), exist_ok=True)
        info0 = B.layer_info(d, a)
        for L in range(info0['n_layers']):
            B.render(d, a, L, f'{stem}_L{L}.png')
        layers = sorted(_glob.glob(stem + '_L*.png'))
        info = infos.get(a, {})
        bands = info.get('y_of_layer') or []
        sp = info.get('spacing') or 120.0
        for lf in layers:
            L = int(lf.rsplit('_L', 1)[1].split('.')[0])
            im = Image.open(lf).convert('RGBA')
            W, H = im.size
            x0, y0, Wc, Hc, _i = ctx.get(L, (0, 0, W, H, {}))
            dr = ImageDraw.Draw(im)
            n = 0
            for b, pts in allp.items():
                tag = b.replace(f'demo_dungeon_ed{fam}_', 'ED').replace(
                    f'demo_dungeon_bd{fam}_', 'BD').replace(f'demo_dungeon_em{fam}_', 'EM')
                for (x, y, z) in pts:
                    if bands and info.get('n_layers', 1) > 1:
                        bi = min(range(len(bands)), key=lambda k: abs(bands[k] - y))
                        if abs(bands[bi] - y) > max(2.0, 0.6 * sp) or bi != L:
                            continue
                    px = x * s + t[0] - x0
                    py = (H - 1) - (z * s + t[1] - y0)
                    if not (0 <= px < W and 0 <= py < H):
                        continue
                    dr.ellipse((px - 9, py - 9, px + 9, py + 9),
                               outline=(0, 255, 255, 255), width=3)
                    dr.text((px + 12, py - 8), f'{tag} y{y}', fill=(0, 255, 255, 255))
                    print('   ', os.path.basename(lf), tag, f'y{y}', f'({x},{z})')
                    n += 1
            dr.text((12, H - 26), f'stage-pos marks: {n}',
                    fill=(255, 255, 255, 255))
            im.save(lf)
            print(lf, 'marks:', n)


if __name__ == '__main__':
    main()
