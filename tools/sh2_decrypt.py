#!/usr/bin/env python
"""Decrypt Soul Hackers 2 asset bundles.

Algorithm (verified byte-exact against the C# sh2.fileutil tool and the running game):

  password = "lAZr7V4e"            (base64 "bEFacjdWNGU=" in the 2022 tool source)
  salt     = filename_no_ext + "_bKo"        (UTF-8)
  key      = first 16 bytes of SHA1 iterated 100 times over UTF8(password) + salt
             (this is .NET PasswordDeriveBytes(pw, salt): UTF8 password, 100 iter,
              plain hash chain H(H(H(...)))  -- NOT RFC PBKDF1/2, no counter in loop)
  keystream: block n = AES-128-ECB_encrypt(key, LE64(n+1) || 0^8)
  data     = ciphertext XOR keystream

Files that are encrypted (whole file, from offset 0):
  * StreamingAssets/win/Message/** (all leaf bundles; .manifest files are plain text)
  * StreamingAssets/win/Table/commontable   (first ct bytes 4d503999 are just ciphertext,
                                               plaintext starts with "UnityFS")
  * StreamingAssets/win/Version.txt (in old builds)

Everything else (Table/battle, Interface/*, .manifest, the Jp/Table parent bundles)
is plain UnityFS and must NOT be run through this script.

Usage:
  python sh2_decrypt.py <file> [out] [--key NAME]
  python sh2_decrypt.py --check <file>          (validate UnityFS/manifest magic)
  python sh2_decrypt.py <dir>                   (decrypt all encrypted files in dir)
"""
import hashlib
import os
import struct
import sys

from Crypto.Cipher import AES

PASSWORD = "lAZr7V4e"
SALT_ADD = "_bKo"


def derive_key(name: str) -> bytes:
    salt = (name + SALT_ADD).encode("utf-8")
    h = hashlib.sha1(PASSWORD.encode("utf-8") + salt).digest()
    for _ in range(98):  # .NET PDB: 100 total hashes, plain chain
        h = hashlib.sha1(h).digest()
    return hashlib.sha1(h).digest()[:16]


def keystream(key: bytes, nblocks: int) -> bytes:
    out = bytearray()
    enc = AES.new(key, AES.MODE_ECB)
    for n in range(nblocks):
        out += enc.encrypt(struct.pack("<Q", n + 1) + b"\x00" * 8)
    return bytes(out)


def crypt(data: bytes, name: str) -> bytes:
    key = derive_key(name)
    ks = keystream(key, (len(data) + 15) // 16)
    return bytes(c ^ k for c, k in zip(data, ks))


def decrypt_file(path: str, out: str | None = None, key_name: str | None = None) -> str:
    data = open(path, "rb").read()
    name = key_name or os.path.splitext(os.path.basename(path))[0]
    dec = crypt(data, name)
    out = out or path
    open(out, "wb").write(dec)
    return out


def looks_decrypted(data: bytes) -> bool:
    return data.startswith(b"UnityFS") or data.startswith(b"Manifest") or data.startswith(b"{")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    if args[0] == "--check":
        d = open(args[1], "rb").read()
        print(looks_decrypted(d), d[:24])
        sys.exit(0)
    if os.path.isdir(args[0]):
        n = 0
        for root, _, files in os.walk(args[0]):
            for f in files:
                if f.endswith(".manifest") or f.endswith(".txt"):
                    continue
                p = os.path.join(root, f)
                b = open(p, "rb").read(7)
                if b.startswith(b"UnityFS"):
                    continue  # already plain
                out = p + ".dec"
                decrypt_file(p, out)
                ok = looks_decrypted(open(out, "rb").read(7))
                print(("ok  " if ok else "FAIL"), p, "->", out)
                n += 1
        print(f"{n} files processed")
    else:
        key_name = None
        if "--key" in args:
            key_name = args[args.index("--key") + 1]
        src = args[0]
        dst = args[1] if len(args) > 1 and args[1] != "--key" else None
        out = decrypt_file(src, dst, key_name)
        print("ok" if looks_decrypted(open(out, "rb").read(7)) else "FAIL", out)
