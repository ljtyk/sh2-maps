import sh2paths
# Bulk-decrypt every encrypted StreamingAssets file to re/dec/<relpath>.
# Reuses the old project's verified cipher (sh2_decrypt.py), read-only on originals.
import os
import sys

sys.path.insert(0, sh2paths.OLD)
from sh2_decrypt import crypt, looks_decrypted  # noqa: E402

ROOT = sh2paths.SS
OUT = os.path.join(os.path.dirname(__file__), '..', 'dec')


def main():
    n_ok = n_fail = n_skip = 0
    for dirpath, dirs, files in os.walk(ROOT):
        for f in files:
            if f.endswith('.manifest') or f.endswith('.txt'):
                continue
            p = os.path.join(dirpath, f)
            with open(p, 'rb') as fh:
                data = fh.read()
            if data.startswith(b'UnityFS') or data.startswith(b'Manifest'):
                n_skip += 1
                continue
            rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
            outp = os.path.join(OUT, rel.replace('/', os.sep))
            os.makedirs(os.path.dirname(outp), exist_ok=True)
            dec = crypt(data, os.path.splitext(f)[0])
            if looks_decrypted(dec[:8]):
                with open(outp, 'wb') as fh:
                    fh.write(dec)
                n_ok += 1
            else:
                n_fail += 1
                print('FAIL', rel)
    print(f'ok={n_ok} fail={n_fail} plain_skipped={n_skip} -> {os.path.abspath(OUT)}')


if __name__ == '__main__':
    main()
