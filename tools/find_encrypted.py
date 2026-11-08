import sh2paths
# Inventory encrypted vs plain files under StreamingAssets.
import os

root = sh2paths.SS
enc, plain = {}, {}
for dirpath, dirs, files in os.walk(root):
    for f in files:
        if f.endswith('.manifest') or f.endswith('.txt'):
            continue
        p = os.path.join(dirpath, f)
        try:
            with open(p, 'rb') as fh:
                magic = fh.read(7)
        except Exception:
            continue
        rel = os.path.relpath(dirpath, root).replace(os.sep, '/')
        if magic.startswith(b'UnityFS') or magic.startswith(b'Manifest'):
            plain[rel] = plain.get(rel, 0) + 1
        else:
            enc[rel] = enc.get(rel, 0) + 1
print('ENCRYPTED by dir:')
tot = 0
for k, v in sorted(enc.items()):
    print('  ', k, v)
    tot += v
print('total encrypted', tot)
print('plain dirs:', len(plain))
for k, v in sorted(plain.items()):
    print('  plain', k, v)
