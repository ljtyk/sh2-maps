"""Dump label->text message tables from the decrypted Message bundles.

Reads <dec>/win/Message/{En,Jp}/* (everything EXCEPT event_*) and writes
  <out>/msg_common_en.json / msg_common_jp.json
(label -> text dicts; ~6.7k entries: CNAME_*, SKILLNAME_*, RACE_*, MAP_*,
ITEM*NAME_*, ...).  Run after decrypt_all.py.
"""
import os
import re
import json
import glob
import UnityPy

import sh2paths

LABEL = re.compile(r'^[A-Z0-9][A-Za-z0-9_]*$')


def dump(lang, out):
    root = sh2paths.dec(f'Message/{lang}')
    msgs = {}
    files = [p for p in glob.glob(os.path.join(root, '*'))
             if os.path.isfile(p) and not
             os.path.basename(p).startswith(('event_',)) and
             not p.endswith('.manifest')]
    for f in files:
        try:
            env = UnityPy.load(f)
        except Exception:
            continue
        for o in env.objects:
            try:
                d = o.read()
            except Exception:
                continue
            if type(d).__name__ != 'MonoBehaviour':
                continue
            for r in getattr(d, 'm_oneLineData', None) or []:
                name = getattr(r, 'name', '') or ''
                if not LABEL.match(str(name)):
                    continue
                txt = ''.join(str(x) for x in (getattr(r, 'text', None) or []))
                txt = re.sub(r'</?tags?[^>]*>', '', txt)
                if txt and name not in msgs:
                    msgs[str(name)] = txt
    json.dump(msgs, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(len(msgs), 'labels ->', out)


if __name__ == '__main__':
    os.makedirs(sh2paths.OUT, exist_ok=True)
    for lang in ('En', 'Jp'):
        dump(lang, os.path.join(sh2paths.OUT, f'msg_common_{lang.lower()}.json'))
