# -*- coding: utf-8 -*-
"""Scan bundles for MonoScript class names matching a regex.
Usage: scan_class_names.py <root_glob> <regex>"""
import sys, os, glob, re, UnityPy
pat = re.compile(sys.argv[2])
roots = sys.argv[1]
n = 0
for p in glob.glob(roots, recursive=True):
    if p.endswith('.manifest') or os.path.isdir(p):
        continue
    try:
        env = UnityPy.load(p)
        names = [str(o.read().m_ClassName) for o in env.objects
                 if o.type == 115]
    except Exception:
        continue
    hits = [x for x in names if pat.search(x or '')]
    if hits:
        n += 1
        print(os.path.basename(p), sorted(set(hits))[:8])
print('files with hits:', n)
