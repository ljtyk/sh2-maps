import sh2paths
# -*- coding: utf-8 -*-
"""Human-readable digest of re/out/commontable.json (Task E).

Resolves text labels via _msg_common_en.json / _msg_common_jp.json using
the game's index-based label patterns (verified against the common msg
table's own keys):

  ItemUseTable.param[i]  -> ITEMUSENAME_{i:02d} / ITEMUSEINFO_{i:02d}
  ItemKeyTable.param[i]  -> ITEMKEYNAME_{i:02d} / ITEMKEYINFO_{i:02d}
  ItemAcsTable.param[i]  -> ITEMACSNAME_{i:02d} / ITEMACSINFO_{i:02d}
  ItemManaTable.param[i] -> ITEMMANANAME_{i:03d} / ITEMMANAINFO_{i:03d}
  ItemMatTable/ItemMealTable/ItemCosTable -> ITEMMAT/MEAL/COS...
  EnemyTable.m_Table[].m_NameLabel -> NAKAMA_xxx (397/398 resolved)
  CharParamTable.param[].nameLabel -> CNAME_* (241 names in msg)
  MapAreaInfoDataArray -> MAP_PLACE_NAME_*
  QuestData -> titleText/requesterName/... (62/62 titles resolved)

Outputs (re/out/digest/):
  quests.json     62 quests (id, title en/jp, requester, rec level, rewards)
  enemies.json    398 enemies (id, name, level, AI, base stats, weapons)
  nakama.json     373 devil codex entries (NAKAMA_ + NAKAMAINFO_)
  items.json      all 7 item tables with names/descriptions
  skills.json     SKILLNAME_* lookup (851)
  chars.json      601 CharParam rows (name/model/weapon refs)
  map_areas.json  85 place/area entries (names resolved)

Run:  "$PY" -X utf8 re/tools/commontable_digest.py
"""
import os
import json
import re

OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'digest')
CT = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'out', 'commontable.json'), encoding='utf-8'))
MSG = {}
for lang in ('en', 'jp'):
    p = sh2paths.msg_common(lang)
    if p and os.path.exists(p):
        MSG[lang] = json.load(open(p, encoding='utf-8'))


def t(label, lang='en'):
    if not label:
        return ''
    return MSG.get(lang, {}).get(label, '')


def item_name(tab, i, prefix):
    n = f'{prefix}NAME_{i:02d}' if len(prefix) != 7 else f'{prefix}NAME_{i:03d}'
    return t(n)


PL2DUN = {1001: 'du001', 1002: 'du002', 1003: 'du003', 1004: 'du004', 1005: 'du005',
          1007: 'du007', 1101: 'du101', 1102: 'du102', 1103: 'du103'}


def enemy_name(eid):
    for e in CT['EnemyTable'][0]['m_Table']:
        if isinstance(e, dict) and e.get('m_EnemyID') == eid:
            return t(e.get('m_NameLabel', ''))
    return ''


def enemy_spawn_locs(eid):
    # AreaSpawnTable/EnemySpawnTable: (m_PlaceID, m_AreaID) rows whose enemy list / id
    # matches. areaId 0 = literal floor 0 (same convention as AionOrderData, verified
    # Task E3). EnemySpawnTable used as fallback (place -1 = global: skip).
    locs, seen = [], set()
    for r in CT['AreaSpawnTable'][0]['m_Table']:
        if isinstance(r, dict) and eid in (r.get('m_EnemyIDs') or []):
            d = PL2DUN.get(r.get('m_PlaceID'))
            if d and (d, r.get('m_AreaID')) not in seen:
                seen.add((d, r.get('m_AreaID'))); locs.append({'dun': d, 'floor': r.get('m_AreaID')})
    if not locs:
        for r in CT['EnemySpawnTable'][0]['m_Table']:
            if isinstance(r, dict) and r.get('m_EnemyID') == eid:
                d = PL2DUN.get(r.get('m_PlaceID'))
                if d and (d, r.get('m_AreaID')) not in seen:
                    seen.add((d, r.get('m_AreaID'))); locs.append({'dun': d, 'floor': r.get('m_AreaID')})
    return locs


def main():
    os.makedirs(OUT, exist_ok=True)

    # --- quests ---
    quests = []
    for q in CT['QuestData']:
        qid = q.get('id', '')
        num = q.get('number', 0)
        rewards = []
        for r in q.get('rewards') or []:
            rtype, rid, val = r.get('type'), r.get('id'), r.get('value')
            nm = item_name('use', rid, 'ITEMUSE') if rtype == 1 else ''
            rewards.append({'type': rtype, 'id': rid, 'value': val, 'name': nm})
        targets = []
        for tt in q.get('targets') or []:
            tg = {'label': tt.get('textLabel', ''), 'text': t(tt.get('textLabel', '')),
                  'type': tt.get('type'), 'id': tt.get('id'), 'count': tt.get('count'),
                  'enemyPlaceType': tt.get('enemyPlaceType'),
                  'mapPlaceId': tt.get('mapPlaceId'), 'areaId': tt.get('areaId')}
            tg['dun'] = PL2DUN.get(tt.get('mapPlaceId'))
            tg['enemyName'] = enemy_name(tt.get('id')) if tt.get('type') == 1 else ''
            tg['spawn_locs'] = enemy_spawn_locs(tt.get('id')) if tt.get('type') == 1 else []
            targets.append(tg)
        quests.append({
            'id': qid, 'number': num,
            'title': t(q.get('titleText', '')), 'title_jp': t(q.get('titleText', ''), 'jp'),
            'requester': t(q.get('requesterName', '')),
            'requesterMapId': q.get('requesterMapId'),
            'requester_dun': PL2DUN.get(q.get('requesterMapId')),
            'recommendLevel': q.get('recommendLevel'),
            'questType': q.get('questType'), 'isDLC': q.get('isDLC'),
            'rewards': rewards,
            'targets': targets,
            'orderText': t((q.get('orderText') or {}).get('textLabel', '') if isinstance(q.get('orderText'), dict) else ''),
        })
    json.dump(quests, open(f'{OUT}/quests.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # --- enemies ---
    enemies = []
    for e in CT['EnemyTable'][0]['m_Table']:
        nl = e.get('m_NameLabel', '')
        enemies.append({
            'id': e.get('m_EnemyID'), 'name': t(nl), 'name_jp': t(nl, 'jp'), 'label': nl,
            'level': e.get('m_Level'), 'ai': e.get('m_AiID'),
            'hp': e.get('m_EnemyBaseHp'), 'mp': e.get('m_EnemyBaseMp'),
            'str': e.get('m_EnemyBaseStr'), 'int': e.get('m_EnemyBaseInt'),
            'vit': e.get('m_EnemyBaseVit'), 'agi': e.get('m_EnemyBaseAgi'), 'luk': e.get('m_EnemyBaseLuk'),
        })
    json.dump(enemies, open(f'{OUT}/enemies.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # --- nakama codex (from msg table itself) ---
    nakama = []
    for k in sorted(MSG['en']):
        m = re.match(r'^NAKAMAINFO_(\d{3})$', k)
        if m:
            idx = m.group(1)
            nakama.append({'id': int(idx), 'name': t(f'NAKAMA_{idx}'), 'info': MSG['en'][k],
                           'info_jp': MSG['jp'].get(k, '')})
    json.dump(nakama, open(f'{OUT}/nakama.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # --- items ---
    spec = [('ItemUseTable', 'param', 2, 'ITEMUSE'), ('ItemKeyTable', 'param', 2, 'ITEMKEY'),
            ('ItemAcsTable', 'param', 2, 'ITEMACS'), ('ItemManaTable', 'param', 3, 'ITEMMANA'),
            ('ItemMatTable', 'param', 3, 'ITEMMAT'), ('ItemMealTable', 'param', 2, 'ITEMMEAL'),
            ('ItemCosTable', 'param', 2, 'ITEMCOS')]
    items = {}
    for tab, fld, nd, pref in spec:
        rows = []
        for i, r in enumerate(CT[tab][0][fld]):
            nm = MSG['en'].get(f'{pref}NAME_{i:0{nd}d}', '')
            if nm or any(v not in (0, '', None) for k, v in r.items() if k not in ('sortId', 'flag')):
                rows.append({'index': i, 'name': nm, 'desc': MSG['en'].get(f'{pref}INFO_{i:0{nd}d}', ''), **r})
        items[tab] = rows
    json.dump(items, open(f'{OUT}/items.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # --- skills ---
    skills = {k: MSG['en'][k] for k in sorted(MSG['en']) if k.startswith('SKILLNAME_')}
    json.dump(skills, open(f'{OUT}/skills.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # --- chars ---
    chars = []
    for r in CT['CharParamTable'][0]['param']:
        nl = r.get('nameLabel', '')
        if nl:
            chars.append({k: r[k] for k in ('charId', 'kind', 'genderType', 'iconId', 'nameLabel',
                                            'rightWeaponId', 'leftWeaponId', 'dressId', 'bustupId') if k in r}
                         | {'name': t(nl)})
    json.dump(chars, open(f'{OUT}/chars.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # --- aion orders (soul-matrix objectives; floor-granular) ---
    # place->dungeon VERIFIED against our rendered map titles:
    # 1101='Soul Matrix - Arrow Sector'=du101, 1102=Milady=du102, 1103=Saizo=du103
    aion = []
    item_names = {}
    for tab, pref, nd in (('ItemUseTable', 'ITEMUSE', 2), ('ItemKeyTable', 'ITEMKEY', 2)):
        for i, r in enumerate(CT[tab][0]['param']):
            nm = MSG['en'].get(f'{pref}NAME_{i:0{nd}d}', '')
            item_names[i] = nm  # target id == table index (EA02: 71='Ancient Scripture' verified)
    for r in CT['AionOrderData']:
        tgs = []
        for tg in r.get('targets') or []:
            mp, ai = tg.get('mapPlaceId'), tg.get('areaId')
            tt = tg.get('type')
            nm = None
            if tt in (1, 2):
                nm = next((e['name'] for e in enemies if e['id'] == tg.get('id')), None)
            elif tt == 0:
                nm = item_names.get(tg.get('id')) or f'item#{tg.get("id")}'
            tgs.append({'type': tt, 'id': tg.get('id'), 'count': tg.get('count'), 'name': nm,
                        'place': mp, 'dun': {1101: 'du101', 1102: 'du102', 1103: 'du103'}.get(mp),
                        'floor': ai if (mp in (1101, 1102, 1103) and ai is not None) else None})
        aion.append({'id': r.get('id'), 'title': t(r.get('titleText', '')), 'title_jp': t(r.get('titleText', ''), 'jp'),
                     'recommendLevel': r.get('recommendLevel'), 'targets': tgs})
    json.dump(aion, open(f'{OUT}/aion_orders.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # --- map areas ---
    areas = []
    for r in CT['MapAreaInfoDataArray'][0]['m_Params']:
        lbl = r.get('m_PlaceNameLabel', '')
        areas.append({'place': r.get('m_PlaceID'), 'area': r.get('m_AreaID'), 'sub': r.get('m_SubAreaID'),
                      'label': lbl, 'name': t(lbl), 'name_jp': t(lbl, 'jp')})
    # place -> dungeon (VERIFIED against the map titles we render):
    # 1001 Shipping District=du001, 1002 Central Line=du002, 1003 Subway Line 14=du003,
    # 1004 Ozaki Hope Towers=du004, 1005 24th Ward Municipal Tower=du005,
    # 1007 Hachigaya Training Field=du007, 11xx Soul Matrix=du10x
    places = {}
    for a in areas:
        p = a['place']
        places.setdefault(p, a['name'])
    for p in (1001, 1002, 1003, 1004, 1005, 1007):
        if p in places:
            places[p] += f' (du{p-1000:03d})'
    json.dump({'places': places, 'areas': areas}, open(f'{OUT}/map_areas.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    for f in ('quests', 'enemies', 'nakama', 'items', 'skills', 'chars', 'aion_orders', 'map_areas'):
        d = json.load(open(f'{OUT}/{f}.json'))
        n = len(d) if isinstance(d, list) else len(d.keys())
        print(f'{f}.json: {n}')


if __name__ == '__main__':
    main()
