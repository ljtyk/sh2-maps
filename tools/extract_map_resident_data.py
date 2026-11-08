import sh2paths
# -*- coding: utf-8 -*-
"""Extract GROUND-TRUTH placement points from win/mapnew/map_resident_data.

That one bundle holds per-area data objects for all 104 map areas:
  * MapAreaData_EventPlan '<dun>_<area>_evplan' . Points_Event:
      Identifier ('ER41_RS_fellow'), Label ('NPC ER41_R.S.の部下'),
      Pos/Rotate/Scale (world xyz!), ObjectType, CharacterId, TriggerType.
      -> exact placement of every quest NPC and event trigger/check point.
  * MapAreaData_MapPlan '<dun>_<area>_mapplan' . Points_SpawnEnemy/_SpawnMob:
      fixed enemy/mob spawn point pools (where random packs materialise).

Outputs:
  re/out/event_npc_points.json  { 'du001_0010': [{ident,label,pos,rot,...}] }
  re/out/spawn_points.json      { 'du001_0010': {'enemy':[[x,y,z]...]} }

VERIFIED: ER41_RS_fellow @ (118.87, 0.0, -30.57) on du001_0010 projects onto
the painted map right by the 'North: Iron Gates' portal; ER35_jaaku lands in
the Tower A 2F L4 east room matching the er35_007 demo staging coords.

Run: "$PY" -X utf8 re/tools/extract_map_resident_data.py
"""
import json
import os

import UnityPy

SRC = sh2paths.WIN + '/mapnew/map_resident_data'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out')


def vec(w):
    return [round(w.x, 2), round(w.y, 2), round(w.z, 2)]


def main():
    env = UnityPy.load(SRC)
    scripts = {o.path_id: str(o.read().m_ClassName)
               for o in env.objects if o.type == 115}
    ev, mob, dsv = {}, {}, {}
    for o in env.objects:
        d = o.read()
        if type(d).__name__ != 'MonoBehaviour':
            continue
        cls = scripts.get(d.m_Script.m_PathID)
        nm = str(d.m_Name or '')
        if cls == 'MapAreaData_EventPlan' and nm.endswith('_evplan'):
            pts = [dict(ident=str(e.Identifier), label=str(e.Label),
                        pos=vec(e.Pos), rot=vec(e.Rotate),
                        objType=int(e.ObjectType), charId=int(e.CharacterId),
                        trig=int(e.TriggerType), act=int(e.ActionType))
                   for e in d.Points_Event or []]
            if pts:
                ev[nm[:-7]] = pts
        elif cls == 'MapAreaData_MapPlan' and nm.endswith('_mapplan'):
            rec = {}
            for src, key in (('Points_SpawnMob', 'mob'),
                             ('Points_SpawnEnemy', 'enemy')):
                lst = getattr(d, src, None) or []
                if lst:
                    rec[key] = [dict(pos=vec(e.Pos),
                                     enc=int(getattr(e, 'NormalEncountPackID',
                                                     0) or 0)) for e in lst]
            if rec:
                mob[nm[:-8]] = rec
            ds = [{'label': str(e.Label), 'pos': vec(e.Pos),
                   'fixed': int(getattr(e, 'IsFixed', 0))}
                  for e in getattr(d, 'Points_DevilSearch', None) or []]
            if ds:
                dsv[nm[:-8]] = ds
    for f, obj in (('event_npc_points.json', ev), ('spawn_points.json', mob),
                   ('devilsearch_points.json', dsv)):
        with open(os.path.join(OUT, f), 'w', encoding='utf-8') as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
    # enc/pack id -> enemy names (EncountTable + enemies digest) so the
    # renderer can label spawn-point groups per enemy
    ct = json.load(open(os.path.join(OUT, 'commontable.json'), encoding='utf-8'))
    ename = {e['id']: e.get('name') or '' for e in
             json.load(open(os.path.join(OUT, 'digest', 'enemies.json'),
                            encoding='utf-8'))}
    enc_names = {}
    for r in ct['EncountTable'][0]['m_Table']:
        if not isinstance(r, dict):
            continue
        ids = [r.get(f'm_EnemyID{i}') for i in range(1, 7)]
        ids = [i for i in ids if i]
        if ids and r.get('m_EncountID'):
            enc_names[str(r['m_EncountID'])] = sorted(
                {ename.get(i) or f'enemy#{i}' for i in ids})
    with open(os.path.join(OUT, 'enc_names.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(enc_names, fh, ensure_ascii=False, indent=1)
    print('event-point areas:', len(ev), 'points:', sum(map(len, ev.values())))
    print('spawn-point areas:', len(mob),
          'points:', sum(len(v.get('enemy', [])) + len(v.get('mob', []))
                         for v in mob.values()))


if __name__ == '__main__':
    main()
