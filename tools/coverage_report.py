"""Coverage audit: every ER quest + Aion order objective -> what our minimaps
show. Reads re/out/digest/*.json + enemy_spawns.json + event_points.json.
Writes re/out/digest/coverage.md and prints summary."""

import sh2paths
import json, os, collections
D = os.path.join(os.path.dirname(__file__), '..', 'out', 'digest')
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'digest', 'coverage.md')
def load(f):
    return json.load(open(os.path.join(D, f), encoding='utf-8'))
quests = load('quests.json')
orders = load('aion_orders.json')
spawns = json.load(open(os.path.join(D, '..', 'enemy_spawns.json'), encoding='utf-8'))
ep = json.load(open(sh2paths.oldfile('event_points.json'), encoding='utf-8'))
boss_floors = {f'{d}_{a}' for d, v in ep.items() for a, ps in v.items()
               if any('BossModel' in p.get('ident', '') for p in ps)}
static = {k: len(v) for k, v in spawns.items() if v}
# EventListObjectAll placements: quest -> floors/objects physically registered
_pl = load('object_placements.json') if os.path.exists(os.path.join(D, 'object_placements.json')) else {}
Q2FLOOR = collections.defaultdict(lambda: collections.defaultdict(list))
for key, items in _pl.items():
    for it in items:
        if it.get('quest'):
            Q2FLOOR[it['quest']][key].append(it['itemId'])
Q2FSTR = {q: ', '.join(f"{k.rsplit('_', 1)[0]} L{int(k.split('_')[1]) // 10}"
                       for k in sorted(fl)) for q, fl in Q2FLOOR.items()}
# exact NPC placement points (map_resident_data Points_Event): quest -> floors
_npc = json.load(open(os.path.join(D, '..', 'event_npc_points.json'),
                      encoding='utf-8')) \
    if os.path.exists(os.path.join(D, '..', 'event_npc_points.json')) else {}
NPCQ = collections.defaultdict(list)
for _a, _pts in _npc.items():
    for _p in _pts:
        _m = __import__('re').match(r'ER(\d+)_', _p['ident'])
        if _m and not _p['ident'].lower().endswith(('_hit', '_check')):
            NPCQ[f'ER{int(_m.group(1)):02d}'].append(_a)
# demo-graph stage positions: quest -> floors where an event has world coords
_evp = json.load(open(os.path.join(D, '..', 'event_positions.json'),
                      encoding='utf-8')) \
    if os.path.exists(os.path.join(D, '..', 'event_positions.json')) else {}
EVQ = collections.defaultdict(set)
for _c, _e in _evp.items():
    if _e.get('quest') and _e.get('areas'):
        EVQ[_e['quest']].update(_e['areas'])
EVQSTR = {q: ', '.join(sorted(v)) for q, v in EVQ.items()}

def q_status(t):
    """One target -> (marker, where)."""
    dun = t.get('dun')
    typ = t.get('type')
    locs = t.get('spawn_locs') or []
    if typ == 1 and locs:
        pins = [l for l in locs if f"{l['dun']}_{int(l['floor']):04d}" in static]
        if pins:
            return 'PIN+FLOOR', ', '.join(f"{l['dun']} L{l['floor']//10}" for l in locs)
        return 'FLOOR', ', '.join(f"{l['dun']} L{l['floor']//10}" for l in locs)
    if typ == 2 and dun:  # devil/boss target on a dungeon
        fl = t.get('areaId')
        ring = dun and f"{dun}_{int(fl or 0):04d}" in boss_floors
        return ('RING' if ring else 'FLOOR'), f"{dun} L{(fl or 0)//10}"
    if dun:
        return 'DUNGEON', dun
    return 'NONE', ''

rows, cnt = [], collections.Counter()
for q in quests:
    if not (q.get('targets') or []) and not q.get('requester_dun'):
        if q['id'] in EVQSTR:
            rows.append((q['id'], q['title'], 'event scene', 'event',
                         'EVENT-PIN', EVQSTR[q['id']]))
            cnt['EVENT-PIN'] += 1
            continue
        rows.append((q['id'], q['title'], '-', '-', 'story-flag', '-'))
        cnt['story-flag'] += 1
        continue
    if q.get('requester_dun'):
        rows.append((q['id'], q['title'], f"NPC in {q['requester_dun']}", '-', 'NPC-BADGE', 'all floors'))
        cnt['NPC-BADGE'] += 1
    if q['id'] in NPCQ:
        locs = '; '.join(f"{k}@{next(p['pos'] for p in _npc[k] if p['ident'].upper().startswith(q['id'].replace('ER','ER')+'_'))}"
                         for k in sorted(set(NPCQ[q['id']]))[:3])
        rows.append((q['id'], q['title'], locs[:90], 'npc', 'PIN-NPC',
                     'exact xyz (Points_Event)'))
        cnt['PIN-NPC'] += 1
    elif q['id'] in Q2FSTR:
        fl_names = '; '.join(f"{k}={'/'.join(sorted(set(v)))}"
                             for k, v in sorted(Q2FLOOR[q['id']].items()))
        rows.append((q['id'], q['title'], fl_names[:80], 'npc', 'PLACED', Q2FSTR[q['id']]))
        cnt['PLACED'] += 1
    for t in q.get('targets') or []:
        m, w = q_status(t)
        if m == 'NONE' and q['id'] in EVQSTR:
            m, w = 'EVENT-PIN', EVQSTR[q['id']]
        elif m == 'NONE' and q['id'] in Q2FSTR:
            m, w = 'VIA-NPC', Q2FSTR[q['id']]
        label = t.get('text') or t.get('enemyName') or t.get('label') or ''
        rows.append((q['id'], q['title'], label[:40], t.get('type'), m, w))
        cnt[m] += 1
for o in orders:
    for t in o.get('targets') or []:
        dun, fl = t.get('dun'), t.get('floor')
        typ = t.get('type')
        if dun is None:
            rows.append((o['id'], o['title'], t.get('name') or '', typ, 'NONE', 'safehouse (no map)'))
            cnt['NONE'] += 1
            continue
        da = f"{dun}_{int(fl or 0):04d}"
        if typ == 2:
            m = 'RING' if da in boss_floors else 'FLOOR'
        elif typ == 1:
            m = 'PIN+FLOOR' if da in static else 'FLOOR'
        else:
            m = 'FLOOR'
        rows.append((o['id'], o['title'], (t.get('name') or '')[:40], typ, m, f'{dun} L{(fl or 0)//10}'))
        cnt[m] += 1

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('# Objective coverage on minimaps\n\n')
    f.write('Markers: PIN=world dot/rect (static gimmic), RING=boss ring (event_points), '
            'FLOOR=floor badge, DUNGEON=dungeon-wide badge, NPC-BADGE=find <npc> (requester), '
            'PLACED=registered on exact floor (EventListObjectAll), '
            'PIN-NPC=exact world xyz from map_resident_data Points_Event, '
            'EVENT-PIN=exact world coords from demo-graph StCharaSetPos, '
            'VIA-NPC=location-less target resolved via the quest NPC registration, '
            'NONE=no location data by design.\n\n')
    f.write('| id | objective | target | type | marker | location |\n|---|---|---|---|---|---|\n')
    for r in rows:
        f.write('| ' + ' | '.join(str(x) for x in r) + ' |\n')
    f.write('\n## Totals\n\n')
    for k, v in sorted(cnt.items()):
        f.write(f'- {k}: {v}\n')
print('rows:', len(rows))
for k, v in sorted(cnt.items()):
    print(f'  {k:10s} {v}')
print('static-pin floors:', sorted(static))
print('boss-ring floors:', len(boss_floors))
