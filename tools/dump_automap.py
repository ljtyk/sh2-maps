"""Dump the in-game automap tile textures (XOR-obfuscated raw BC7) for a
dungeon.

Reads  <win>/Interface/interface_mapnew_automap_<dun>  for Texture2D objects
named <dun>_<area>_<layer>_<i>_<j> (pixel data lives in the CAB .resS
stream) and writes, under tools/data/:
  automap_<dun>/<name>.bin           raw stream bytes (still XOR-obfuscated;
                                     build_minimap_layers applies the key)
  dbg_automap_texlist_<dun>.json     [{name, w, h}, ...]
These caches are consumed by build_minimap_layers.py.
  python dump_automap.py du001 [du002 ...]
"""
import os
import re
import sys
import json
import UnityPy

import sh2paths

NAME = re.compile(r'^(\w+\d+)_(\d+)_(\d+)_(\d+)_(\d+)$')


def dump(dun):
    outdir = os.path.join(sh2paths.DATA, f'automap_{dun}')
    os.makedirs(outdir, exist_ok=True)
    bundle = os.path.join(sh2paths.WIN, 'Interface',
                          f'interface_mapnew_automap_{dun}')
    env = UnityPy.load(bundle)
    tl, n = [], 0
    for o in env.objects:
        try:
            d = o.read()
        except Exception:
            continue
        if type(d).__name__ != 'Texture2D':
            continue
        nm = str(d.m_Name)
        if not nm.startswith(dun + '_') or not NAME.match(nm):
            continue
        w, h = d.m_Width, d.m_Height
        sd = d.m_StreamData
        if sd and getattr(sd, 'size', 0):
            key = sd.path.split('/')[-1].lower()
            if not key.endswith('.ress'):
                key += '.ress'
            r = env.cabs[key]
            r.position = sd.offset
            b = r.read(sd.size)
        else:
            b = bytes(d.image_data)
        if len(b) != w * h:
            print('skip', nm, len(b), '!=', w * h)
            continue
        open(os.path.join(outdir, nm + '.bin'), 'wb').write(b)
        tl.append({'name': nm, 'w': w, 'h': h})
        n += 1
    json.dump(tl, open(os.path.join(sh2paths.DATA,
                                    f'dbg_automap_texlist_{dun}.json'), 'w'))
    print(f'{dun}: {n} textures -> data/automap_{dun}')


if __name__ == '__main__':
    for dun in (sys.argv[1:] or ['du001']):
        dump(dun)
