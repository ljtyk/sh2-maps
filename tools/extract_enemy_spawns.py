import sh2paths
# -*- coding: utf-8 -*-
"""Extract static enemy-spawn gimmics (Gimmic_SpawnEnemy*) from area_scenes
runtime bundles.

v2 (2025-01, NPC hunt): the old 'byte-scan only 4 bundles' finding was WRONG
(stripped/compressed bundles hid the names). UnityPy-typed audit over ALL 97
du*/fi* bundles finds spawn gimmics on: du001_0010, du004_0000, du101_0000,
du101_0020, du101_0050, du102_0040, du103_0040 (Task D had only 4 — du101_0000
and du101_0050 missed because the old path_id dict kept the wrong scene half,
du001_0010 missed because the byte scan found nothing).

These SerializedFiles serialize the scene TWICE (editor frame at origin +
world frame) with colliding path_ids. v2 splits the object stream at the
largest byte gap between Transforms and resolves GameObjects/fathers WITHIN
each half, then dedupes near-identical positions (tol 1.0) across halves.

- du103_0040 has two families: 'Gimmic_SpawnEnemy' (y=-21.9 zone =
  boss arena minions, matches event_points EV03_501_BossModel at
  (-5,-25.9,177.4)) and 'Gimmic_SpawnEnemyWrapAround' (y=-9.9 = the regular
  floor).
- Regular enemy MINIMAP markers are drawn at runtime with the
  'Enemysymbol' sprite (present in map_resident_data, the minimap UI
  bundle) — no static positions exist for them.

Output: re/out/enemy_spawns.json  { '<dun>_<area>': [{name, pos}] }
"""
import os
import sys
import json
import shutil
import numpy as np
import UnityPy

GAME = sh2paths.WIN + '/mapnew'
SAMPLES = os.path.join(os.path.dirname(__file__), '..', 'samples')
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'enemy_spawns.json')
BUNDLES = ['du004_0000', 'du101_0020', 'du102_0040', 'du103_0040']


def mat4(t):
    e = np.eye(4)
    e[0, 0] = t.m_LocalScale.x; e[1, 1] = t.m_LocalScale.y; e[2, 2] = t.m_LocalScale.z
    x, y, z, w = t.m_LocalRotation.x, t.m_LocalRotation.y, t.m_LocalRotation.z, t.m_LocalRotation.w
    R = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    e[:3, :3] = R
    e[:3, 3] = [t.m_LocalPosition.x, t.m_LocalPosition.y, t.m_LocalPosition.z]
    return e


def extract(bundle_name):
    local = os.path.join(SAMPLES, bundle_name + '_area_scenes')
    if not os.path.exists(local):
        src = os.path.join(GAME, bundle_name + '_area_scenes')
        os.makedirs(SAMPLES, exist_ok=True)
        shutil.copy2(src, local)
    env = UnityPy.load(local)
    objs = list(env.objects)
    # collect (byte, pid, data) for GOs + Transforms
    trs, gos = [], []
    for o in objs:
        if o.type == 1:
            try:
                gos.append((o.byte_start, o.path_id, o.read()))
            except Exception:
                pass
        elif o.type == 4:
            try:
                trs.append((o.byte_start, o.path_id, o.read()))
            except Exception:
                pass
    if not trs:
        return []
    # The object stream may contain TWO serialized scenes (editor frame at
    # origin + real world frame) with COLLIDING path_ids, and the two halves
    # do NOT split at the same byte offset for GOs vs Transforms. Pragmatic
    # rule: a Transform is a spawn gimmick if its m_GameObject path_id belongs
    # to ANY GameObject copy whose name contains 'Gimmic_SpawnEnemy'; compute
    # the world chain within its own transform block (largest-byte-gap split);
    # keep non-origin positions; dedupe across blocks by position (tol 1.0).
    # Verified against the 4 Task-D floors (exact positions) + du001_0010.
    tb = sorted(t[0] for t in trs)
    gaps = [(b2 - b1, i) for i, (b1, b2) in enumerate(zip(tb, tb[1:]))]
    split = tb[max(gaps, key=lambda g: g[0])[1]] if len(tb) > 1 else tb[0]
    spawn_pids = {pid for bs, pid, d in gos if 'Gimmic_SpawnEnemy' in str(d.m_Name)}
    names_by_pid = {}
    for bs, pid, d in gos:
        names_by_pid.setdefault(pid, []).append(str(d.m_Name))
    out = []
    for half in (0, 1):
        tr_h = {pid: d for bs, pid, d in trs if (bs <= split) == (half == 0)}
        wm = {}
        def wm4(pid):
            if pid in wm:
                return wm[pid]
            t = tr_h[pid]
            m = mat4(t)
            f = t.m_Father
            if f and f.path_id in tr_h and f.path_id not in wm:
                m = wm4(f.path_id) @ m
            wm[pid] = m
            return m
        for pid, t in tr_h.items():
            gp = t.m_GameObject.path_id
            if gp not in spawn_pids:
                continue
            nm = next((n for n in names_by_pid[gp] if 'Gimmic_SpawnEnemy' in n), None)
            if nm is None:
                continue
            n = nm
            if 'Gimmic_SpawnEnemy' in n:
                p = wm4(pid)[:3, 3]
                if abs(p[0]) < 0.01 and abs(p[1]) < 0.01 and abs(p[2]) < 0.01:
                    continue  # prefab-variant duplicate at origin
                out.append({'name': n, 'pos': [round(float(v), 2) for v in p]})
    # dedupe near-identical positions (both instance lists can repeat)
    ded = []
    for e in out:
        if all(np.linalg.norm(np.array(e['pos']) - np.array(d['pos'])) > 1.0 for d in ded):
            ded.append(e)
    return ded


if __name__ == '__main__':
    bundles = sys.argv[1:] or BUNDLES
    data = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for b in bundles:
        dun, area = b.rsplit('_', 1)
        rows = extract(b)
        data[b] = rows
        print(f'{b}: {len(rows)} spawn points')
    data = {k: v for k, v in data.items() if v}  # never keep empty floors
    json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved', OUT)
