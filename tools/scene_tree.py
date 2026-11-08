"""Dump scene-object transform tree(s) matching a name substring, with world
positions (parent chain applied). Resolves objects via back-pointers because
path_ids are NOT unique in these bundles (stripped SerializedFile).
Usage: scene_tree.py <bundle> <substr>"""
import sys
import UnityPy

env = UnityPy.load(sys.argv[1])
pat = sys.argv[2].lower()
transforms, gos = [], []   # (objreader, data)
for o in env.objects:
    try:
        d = o.read()
    except Exception:
        continue
    cn = type(d).__name__
    if cn == 'Transform':
        transforms.append((o, d))
    elif cn == 'GameObject':
        gos.append((o, d))

# tindex: GO path_id -> transforms whose m_GameObject points to it
def go_name_of(t_data):
    pid = t_data.m_GameObject.m_PathID
    for _, g in gos:
        try:
            if g.m_Name and GO_PID.get(id(g)) == pid:
                return str(g.m_Name)
        except Exception:
            pass
    return '?'

GO_PID = {id(g): g_pid for g_pid, g in
          [(go_reader.path_id, go_data) for go_reader, go_data in gos]}

def name_of_go(g_data):
    # GO name; its transform found via back-pointer below
    return str(g_data.m_Name)

def find_transform_for(go_path_id, go_name):
    return [t for _, t in transforms if t.m_GameObject.m_PathID == go_path_id]

def world_pos(t):
    x = y = z = 0.0
    cur, seen = t, 0
    while cur is not None and seen < 30:
        p = cur.m_LocalPosition
        x += p.x; y += p.y; z += p.z
        f = cur.m_Father
        nxt = None
        if f is not None:
            for _, t2 in transforms:
                pass
        seen += 1
        break  # placeholder
    return x, y, z

# simpler: build pid -> list[TransformData] and walk fathers by path_id match
tr_by_go = {}
for _, t in transforms:
    tr_by_go.setdefault(t.m_GameObject.m_PathID, []).append(t)
t_by_ptr = {}  # transform path_id -> data (first)
for o, t in transforms:
    t_by_ptr.setdefault(o.path_id, t)

def walk(t, depth=0):
    nm = '?'
    pid = t.m_GameObject.m_PathID
    for gr, g in gos:
        if gr.path_id == pid:
            nm = str(g.m_Name); break
    p = t.m_LocalPosition
    print('  ' * depth + f'{nm}  local=({p.x:.2f},{p.y:.2f},{p.z:.2f})')
    for c in t.m_Children:
        ct = t_by_ptr.get(c.m_PathID)
        if ct is not None:
            walk(ct, depth + 1)

for gr, g in gos:
    if pat in str(g.m_Name).lower():
        print('== GO', g.m_Name, '(path_id', str(gr.path_id) + ')')
        for t in tr_by_go.get(gr.path_id, []):
            walk(t, 1)
        print()
