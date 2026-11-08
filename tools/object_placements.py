# -*- coding: utf-8 -*-
"""Extract quest-object placements from commontable EventListObjectAll.

EventListObjectAll is the table the runtime uses to instantiate quest NPCs /
event objects per floor: places[placeId].areas[areaId].npcs/extras =
[{itemId: 'er43_natsuhiko', arranges:[{enableCondition:{startFlag1,endFlag1}}]}].
itemId prefix erNN -> request ERNN (VERIFIED: er43_natsuhiko = ER43 bomber in
du004_0000, er41_rs_fellow = ER41 impostor in du001_0010, both matching quest
text decrypted from win/Message).

Output re/out/digest/object_placements.json:
  { '<dun>_<area>': [ {itemId, quest, npc, flags:[[start,end],...]}, ... ] }

Run:  "$PY" -X utf8 re/tools/object_placements.py
"""
import os
import re
import json

CT = os.path.join(os.path.dirname(__file__), '..', 'out', 'commontable.json')
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'digest', 'object_placements.json')

# eMapPlaceID -> dungeon folder (see dump/csharp eMapPlaceID enum)
PL2DUN = {1001: 'du001', 1002: 'du002', 1003: 'du003', 1004: 'du004',
          1005: 'du005', 1007: 'du007', 1101: 'du101', 1102: 'du102',
          1103: 'du103', 1104: 'du104', 1105: 'du105'}


def main():
    ct = json.load(open(CT, encoding='utf-8'))
    places = ct['EventListObjectAll'][0]['places']
    out = {}
    for p in places:
        dun = PL2DUN.get(p['placeId'])
        if not dun:
            continue
        for a in p['areas']:
            key = f"{dun}_{a['areaId']:04d}"
            for kind in ('npcs', 'extras'):
                for n in a.get(kind) or []:
                    iid = n['itemId']
                    m = re.match(r'^(?:er|ER)(\d+)_', iid)
                    quest = f'ER{int(m.group(1)):02d}' if m else None
                    flags = [[int(x['enableCondition']['startFlag1']),
                              int(x['enableCondition']['endFlag1'])]
                             for x in n.get('arranges') or []]
                    out.setdefault(key, []).append(
                        {'itemId': iid, 'quest': quest,
                         'kind': kind, 'flags': flags})
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    er = sum(1 for v in out.values() for x in v if x['quest'])
    print(f'{len(out)} floors, {sum(len(v) for v in out.values())} objects '
          f'({er} quest-bound) -> {OUT}')


if __name__ == '__main__':
    main()
