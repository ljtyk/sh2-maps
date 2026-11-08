import sh2paths
# -*- coding: utf-8 -*-
"""Extract fixed world positions of map events from demo-graph node blobs.

Demo bundles (win/Demo/demo_dungeon_*, demo_request_*) contain typeless
MonoBehaviour nodes; StCharaSetPos / StCharaMoveRoute nodes serialize world
(x, y, z) float triples (VERIFIED: ED05_012 'There's something on the floor'
projects onto the Tower A 1F west room with the fitted ui2world transform).

Also joins:
 * code:   bundle -> event code (ED05_012 / ER09_005 / ...)
 * quest:  ER codes themselves; ED/BD/EM codes -> EventListAll contacts whose
           events fire this demo (contacts named ERnn_xxx tie it to a request)
 * areas:  (placeId, areaId) the event is registered in (EventListAll)
 * text:   first meaningful decrypted En dialogue line (re/dec/win/Message/En)

Output re/out/event_positions.json:
  { code: {pts:[[x,y,z]...], quest:'ERnn'|None, areas:['du004_0000'...],
           text:'...'} }

Run: "$PY" -X utf8 re/tools/extract_event_positions.py
"""
import json
import glob as _glob
import os
import re
import struct
import sys

import UnityPy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'out')
DEMO = sh2paths.WIN + '/Demo'
MSG = os.path.join(HERE, '..', 'dec', 'win', 'Message', 'En')
PL2DUN = {1001: 'du001', 1002: 'du002', 1003: 'du003', 1004: 'du004',
          1005: 'du005', 1007: 'du007', 1101: 'du101', 1102: 'du102',
          1103: 'du103'}
POS_CLASSES = ('StCharaSetPos', 'StCharaMoveRoute')


def triples(raw):
    out = []
    for off in range(0, len(raw) - 11):
        a, b, c = struct.unpack_from('<3f', raw, off)
        if all(1.5 < abs(v) < 400 for v in (a, b, c)) and 0.5 < abs(b) < 200:
            out.append((round(a, 2), round(b, 2), round(c, 2)))
    return out


def first_line(code):
    """First non-trivial En line of the decrypted message bundle for code."""
    c = code.lower()
    cands = _glob.glob(os.path.join(MSG, f'*{c.replace("_", "_")}*')) or \
        _glob.glob(os.path.join(MSG, f'*{c}*'))
    for p in cands[:1]:
        try:
            env = UnityPy.load(p)
        except Exception:
            continue
        for o in env.objects:
            if o.type != 114:
                continue
            try:
                d = o.read()
                lines = d.m_oneLineData
            except Exception:
                continue
            for ln in lines or []:
                for t in (getattr(ln, 'text', None) or []):
                    if isinstance(t, str):
                        t2 = re.sub(r'<[^>]*>', '', t).replace('\r', ' ').strip()
                        if len(t2) > 8:
                            return t2[:60]
    return None


def main():
    ct = json.load(open(os.path.join(OUT, 'commontable.json'), encoding='utf-8'))
    # event code -> set of 'dun_area' areas + quest via contact names
    ev_areas, ev_quest = {}, {}
    for sc in ct['EventListAll'][0]['scenes']:
        for p in sc.get('places') or []:
            dun = PL2DUN.get(p['placeId'])
            if not dun:
                continue
            for a in p['areas']:
                key = f'{dun}_{a["areaId"]:04d}'
                for t in a['timings']:
                    for c in t['contacts']:
                        s = str(c)
                        cn = re.search(r"contactName='([^']*)'", s)
                        for em in re.finditer(r"eventName='([^']+)'", s):
                            code = em.group(1).upper()
                            ev_areas.setdefault(code, set()).add(key)
                            m = re.match(r'ER(\d+)', code)
                            if m:
                                ev_quest[code] = f'ER{int(m.group(1)):02d}'
                            if cn and cn.group(1).upper().startswith('ER'):
                                mc = re.match(r'ER(\d+)', cn.group(1).upper())
                                if mc:
                                    ev_quest.setdefault(
                                        code, f'ER{int(mc.group(1)):02d}')
    # bundle -> pts
    res = {}
    bundles = [p for p in _glob.glob(os.path.join(DEMO, 'demo_*'))
               if not p.endswith('.manifest')]
    for p in bundles:
        m = re.match(r'demo_(?:dungeon|request)_([a-z]+\d+)_([a-z]+\d+_\d+)',
                     os.path.basename(p))
        if not m:
            continue
        code = m.group(2).upper()
        try:
            env = UnityPy.load(p)
        except Exception:
            continue
        scripts = {o.path_id: str(o.read().m_ClassName)
                   for o in env.objects if o.type == 115}
        if not any(v in POS_CLASSES for v in scripts.values()):
            continue
        pts = set()
        for o in env.objects:
            if o.type != 114:
                continue
            try:
                d = o.read()
                cls = scripts.get(d.m_Script.m_PathID, '')
            except Exception:
                continue
            if cls in POS_CLASSES:
                pts.update(triples(o.get_raw_data()))
        if not pts:
            continue
        ent = res.setdefault(code.lower(), {'pts': [], 'quest': None,
                                            'areas': [], 'text': None})
        ent['pts'] = sorted(set(ent['pts']) | pts)
    # enrich
    for code, ent in res.items():
        up = code.upper()
        ent['quest'] = ev_quest.get(up)
        areas = ev_areas.get(up)
        if not areas:
            m = re.match(r'er(\d+)_', code)
            if m:
                qid = f'ER{int(m.group(1)):02d}'
                q = next((q for q in json.load(
                    open(os.path.join(OUT, 'digest', 'quests.json'),
                         encoding='utf-8')) if q['id'] == qid), None)
                if q and q.get('requester_dun'):
                    areas = set()
            ent['areas'] = sorted(areas or [])
        else:
            ent['areas'] = sorted(areas)
        ent['text'] = first_line(code)
    with open(os.path.join(OUT, 'event_positions.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print('events with positions:', len(res))
    for c, e in sorted(res.items()):
        print(f"  {c:14s} pts={len(e['pts']):2d} quest={e['quest']} "
              f"areas={','.join(e['areas']) or '-'} :: {e['text']}")


if __name__ == '__main__':
    main()
