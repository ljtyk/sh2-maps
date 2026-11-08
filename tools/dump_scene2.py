"""Parse a scene bundle with UnityPy: object type counts + all names +
transforms. Usage: dump_scene2.py <bundle> [name_substr]"""
import sys, collections
import UnityPy
env = UnityPy.load(sys.argv[1])
pat = sys.argv[2].lower() if len(sys.argv) > 2 else None
types = collections.Counter()
names = {}
for o in env.objects:
    t = o.type_str
    types[t] += 1
    try:
        d = o.read()
        n = getattr(d, 'm_Name', None) or getattr(d, 'name', None)
        if n and (pat is None or pat in str(n).lower()):
            names[str(n)] = names.get(str(n), 0) + 1
    except Exception:
        pass
print('types:', dict(types.most_common(15)))
for s, c in sorted(names.items()):
    print(f'{c:4d}  {s[:80]}')
