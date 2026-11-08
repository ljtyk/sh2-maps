"""Write re/out/maps_v2/INDEX.md: every map PNG -> the legend the renderer
draws for it (same structure as draw_objectives: one line per request
'ERnn Title (marks)' + gold aion lines)."""

import sh2paths
import json, os, re, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, '..', 'out', 'digest')
OUT = os.path.join(HERE, '..', 'out')
MAPS = os.path.join(OUT, 'maps_v2')


def load(f):
    return json.load(open(os.path.join(D, f), encoding='utf-8'))


quests, orders = load('quests.json'), load('aion_orders.json')
_pl = load('object_placements.json') if os.path.exists(os.path.join(D, 'object_placements.json')) else {}
_npc = json.load(open(os.path.join(OUT, 'event_npc_points.json'), encoding='utf-8')) \
    if os.path.exists(os.path.join(OUT, 'event_npc_points.json')) else {}
PL2DUN = {1001: 'du001', 1002: 'du002', 1003: 'du003', 1004: 'du004',
          1005: 'du005', 1007: 'du007', 1101: 'du101', 1102: 'du102',
          1103: 'du103'}


def pretty(suf):
    s2 = re.sub(r'^\d+', '', suf)
    s2 = re.sub(r'_(\d+)$', ' \\1', s2)
    return ({'rs_fellow': 'R.S.'}.get(s2.lower())
            or re.sub(r'(?<!\d)frost\d', 'frost', s2.lower()).replace('_', ' ').title())


floors = collections.defaultdict(list)
for line in open(sh2paths.COMBOS, encoding='utf-8'):
    d, a = line.split()
    floors[d].append(a)

# quest -> floors where it has an EXACT NPC pin (event_npc_points)
pinned = collections.defaultdict(set)
for area, pts in _npc.items():
    for p in pts:
        m = re.match(r'ER(\d+)_', p['ident'])
        if m and not p['ident'].lower().endswith(('_hit', '_check')):
            pinned[f'ER{int(m.group(1)):02d}'].add(area)

marks = collections.defaultdict(list)          # (dun, area) -> [(qid, text)]
qids_placed = collections.defaultdict(set)
for key, items in _pl.items():
    dd, aa = key.split('_')
    byq = collections.defaultdict(list)
    for it in items:
        if it.get('quest'):
            suf = it['itemId'].split('_', 1)[1] if '_' in it['itemId'] else it['itemId']
            byq[it['quest']].append(pretty(suf))
    for qid, names in byq.items():
        qids_placed[(dd, aa)].add(qid)
        uniq = sorted(set(names))
        txt = '/'.join(uniq[:3]) + (f" +{len(uniq) - 3} more" if len(uniq) > 3 else '')
        marks[(dd, aa)].append((qid, '◆ Find ' + txt + ' — ' +
                                ('pinned' if key in pinned.get(qid, ()) else 'this floor')))
for q in quests:
    qid = q['id']
    for t in q.get('targets') or []:
        if PL2DUN.get(t.get('mapPlaceId')):
            for a in floors[PL2DUN[t['mapPlaceId']]]:
                marks[(PL2DUN[t['mapPlaceId']], a)].append((qid, '● target in this dungeon'))
        if t.get('type') == 1:
            for l in t.get('spawn_locs') or []:
                a = f"{int(l['floor']):04d}"
                if a in floors.get(l['dun'], []):
                    marks[(l['dun'], a)].append(
                        (qid, f"x {t.get('enemyName')} x{t.get('count')} - spawn points"))
for q in quests:
    if q.get('requester_dun') and q.get('requester'):
        for a in floors[q['requester_dun']]:
            got = any(qid == q['id'] for qid, _ in marks.get((q['requester_dun'], a), []))
            if not got and q['id'] not in qids_placed.get((q['requester_dun'], a), ()):
                marks[(q['requester_dun'], a)].append(
                    (q['id'], f"Find {q['requester']} — requester here"))
aion_lines = collections.defaultdict(list)
for o in orders:
    for t in o.get('targets') or []:
        if not t.get('dun'):
            continue
        a = f"{int(t.get('floor') or 0):04d}"
        if a in floors.get(t['dun'], []):
            pre = 'Target: ' if t.get('type') == 2 else ('' if t.get('type') == 1 else 'Item: ')
            suf = f" x{t['count']}" if t.get('type') in (1, 2) and (t.get('count') or 1) > 1 else ''
            aion_lines[(t['dun'], a)].append(f"{o['id']} {pre}{t.get('name')}{suf}")

QTITLE = {q['id']: (q.get('title') or '') for q in quests}
lines = ['# maps_v2 index — legend per map (matches the drawn legend)\n',
         'Format: `ERnn <request name> (marks)`; gold aion-order lines plain. '
         '◆ = NPC/item on this floor (pinned = exact diamond on the map), '
         'x = enemy objective served by the floor\'s spawn-point pool, '
         '● = target dungeon.\n']
for d in sorted(floors):
    for a in sorted(floors[d]):
        files = sorted(glob.glob(os.path.join(MAPS, f'{d}_{a}_L*.png')))
        byq = collections.OrderedDict()
        for qid, m in marks.get((d, a), []):
            byq.setdefault(qid, []).append(m)
        labs = [f"{qid} {QTITLE.get(qid, '')} (" + '; '.join(dict.fromkeys(ms)) + ')'
                for qid, ms in sorted(byq.items())]
        labs += aion_lines.get((d, a), [])
        for fp in files:
            lines.append(f'- `{os.path.basename(fp)}`: ' + ('; '.join(labs) if labs else '-'))
        if not files:
            lines.append(f'- `{d}_{a}_L0.png`  [NO PNG]: ' + ('; '.join(labs) if labs else '-'))
open(os.path.join(MAPS, 'INDEX.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('maps with legend:', sum(1 for k in marks if marks[k]))
print('total maps:', sum(len(v) for v in floors.values()))
