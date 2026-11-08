"""Dump MonoBehaviour components attached to GameObjects matching a name
substr: raw int32 histogram + printable strings (to find enemy/item IDs)."""
import sys, struct, re, collections
import UnityPy

path, pat = sys.argv[1], sys.argv[2].lower()
env = UnityPy.load(path)
objs = list(env.objects)
G = {}
for o in objs:
    if o.type == 1:
        try:
            G.setdefault(o.path_id, []).append((o.byte_start, str(o.read().m_Name)))
        except Exception:
            pass
T, MB = [], []
for o in objs:
    if o.type == 4:
        T.append((o.byte_start, o.path_id, o.read()))
    elif o.type == 2:
        MB.append((o.byte_start, o.path_id, o))
# which transforms belong to matching GOs
want_tpids = set()
for bs, pid, d in T:
    gp = d.m_GameObject.m_PathID
    cands = G.get(gp, [])
    if not cands:
        continue
    nm = min(cands, key=lambda c: abs(c[0] - bs))[1]
    if pat in nm.lower():
        want_tpids.add(pid)
        print(f'T@{bs} go_pid{gp} {nm}  components?')
# GameObject components -> MB path ids
for o in objs:
    if o.type != 1:
        continue
    try:
        d = o.read()
    except Exception:
        continue
    n = str(d.m_Name)
    if pat not in n.lower():
        continue
    comp_pids = [c.component.m_PathID for c in d.m_Component]
    for bs, pid, mo in MB:
        if pid in comp_pids:
            raw = mo.get_raw_data()
            ints = [struct.unpack_from('<i', raw, i)[0] for i in range(0, len(raw) - 4, 4)]
            interesting = [v for v in ints if 1000 < v < 99999]
            strs = [m.group().decode() for m in re.finditer(rb'[\x20-\x7e]{4,}', raw)]
            print(f'MB@{bs} pid{pid} len={len(raw)} ints(1k..99k)={interesting[:20]} strs={strs[:12]}')
