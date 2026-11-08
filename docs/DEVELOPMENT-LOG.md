# Soul Hackers 2 — automap project: development log

*Chronological research log (raw). The organised write-up is `DATA.md`.
Published as-is for method transparency — some entries were later
corrected; DATA.md is authoritative.*

## Context
- An earlier prototype pass (auto-map tile extraction, first renderer)
  lived in a separate scratch dir; this log covers the full project.
- Python deps: UnityPy, numpy, pillow, matplotlib, scipy,
  texture2ddecoder.

## Step 1 — Target
"Create better minimaps from the decompiled and decrypted files." User approved the order:
Task A (multi-layer maps) first, then Task B (transform re-fit). Both DONE (see below).
Starting state: 42 in-game-style minimap PNGs (`sh2-minimap/maps/*.png`) built from
pre-rendered BC7 automap tile quads + UI icon sprites + warp arrows.

## Step 2 — Existing work
Local (far ahead of anything public):
- Full pipeline `build_minimap.py` (tiles=plain BC7 alpha masks, icons from UI tree sprite names,
  warp arrows with warp-soul interactability filter), 42 floors rendered.
- Bundle decryption SOLVED & byte-verified (pw `lAZr7V4e`, salt `name_bKo`, .NET PBE 100x SHA1
  plain chain, AES-128-ECB keystream LE64(n+1)); `sh2_decrypt.py`. Decrypted: 2,012 Message
  bundles (Jp/En) + `_commontable.dec`.
- Decompiled C# stubs in `sh2-minimap/dump/csharp/Assembly-CSharp.decompiled.cs` (types/enums/
  fields/constants only — no method bodies).
- `gimmicks.json` (803 warps + jumps + portals), navmesh VAND decoders (8 floors),
  `dungeon_names.json`, `_msg_common_{jp,en}.json` (6,756 strings).
- PAUSE_STATE.md: mid-batch — `layers.py` written (multi-layer support) but untested;
  transform re-fit, portal blobs, enemy/item markers not started.

Web (checked 2026-11-06):
- No public SH2 map viewer/datamine tool found. Community maps = hand-traced (kamigame.jp,
  samurai-gamers, gamefaqs). Nexus mods = BepInEx-style, nothing for map data.
- Megami Tensei Wiki "Complete Guide" has enemy/demon/skill data pages (cross-check source).

## Step 3 — Engine & file layout
- Unity 2020.3.24f1, IL2CPP. Confirmed: `GameAssembly.dll` (~28MB), `UnityPlayer.dll`,
  `SOUL HACKERS2_Data/il2cpp_data/Metadata/global-metadata.dat` (8.9MB),
  `ScriptingAssemblies.json` (empty for IL2CPP).
- `StreamingAssets/win/`: Battle, Demo, Event, Interface, LipSync, Message, Table, character,
  effect, mapnew, shader.
  - `Message/**` + `Table/commontable` = encrypted (now decryptable); everything else plain
    UnityFS bundles (UnityPy-readable).
  - `mapnew/duXXX_YYYY_area_scenes` — 4 subfiles per area (gimmicks+collision in
    `*_runtime.sharedAssets`, visuals in `*_graphics.sharedAssets`).
  - `Interface/interface_mapnew_automap_*` — the automap UI bundles (tiles, icon sheet,
    raw portal blobs).
  - `Table/battle`, `Table/meal` — plain.
- Tooling decision: UnityPy + texture2ddecoder + IL2CPP dump for data; dnSpy not needed
  (IL2CPP — no managed IL; decompiled C# stubs + global-metadata strings are the code view).

## Task A — Multi-layer maps (DONE 2026-11-06)
- Solver: `tools/solve_layers_labelled.py` (replaces broken icon-matching `layers.py`).
  Method: warp labels as anchors — du007 uses `B{n}→B{m}へ移動` (inter-floor) and
  `Warp（B{n}）` (same-floor); du004 uses `{n}F` suffixes (sub-levels within one floor).
  Each layer's world-Y band is solved by scoring labelled warp points against the layer's
  tile alpha mask (corridor projection), not by icon matching (du007 connector floors have
  ZERO `_06` door icons — only stair/portal/entrance sprites).
- Verified all 7 multi-layer areas: du007_0000(8 layers), du007_0010(7), du007_0020(5),
  du007_0030(2), du007_0040(2), du004_0000(4), du004_0010(7).
  Layer-index→Y mapping is PER-AREA: du007_0000 is bottom-up (L0=B7@y=-720 … L7=street
  @y=+120), du007_0030 is top-down (L0=B16@y=0). Never assume.
- du004/du007 warps are FLOOR CONNECTORS (label-named GameObjects + ring of Point Lights
  around floor holes), not soul-warps — zero `mp_warp_soul` objects in those dungeons.
  The soul-warp filter is du10x-specific. Verified no other dungeon's warp labels match the
  B→B / Warp(Bn) / (n)F patterns, so the filter bypass is safe.
- du004_0010 official name: "Tower A 2F" — its 7 "layers" are sub-levels (ducts etc.)
  within one tower floor. du007_0000 official: "B1F - B20F" (8 tile layers = B7…B1 + street).
- Renderer: `tools/build_minimap_layers.py <dun> <area> <out.png> [--layer N] [--all]`
  (per-layer renders + cross-floor badges). 71 maps in `out/maps/` (35 single-layer
  floors + 35 per-layer maps of the 7 multi-layer areas + fi999_0002).
- Regression: single-layer du103_0030 render was pixel-identical to the old pipeline
  before the Task B transform changes (0 diff px of 4.97M).
- KNOWN AMBIGUITIES (need in-game confirmation):
  * du004_0010 L0/L4: twin-structure overlap — both layers score 1.0 on 1F AND 4F points.
  * du007_0020: sub-buildings B/C mix — L0/L4 genuinely ambiguous (0.56/0.44 scores).
- du007 transforms were NOT actually bad: corridor scores of 1.00 on du007_0000 contradict
  the old PIPELINE.md claim (that verdict came from jump-gate↔stair-icon matching, not
  corridor projection).

## Task B — Transform re-fit (DONE 2026-11-06)
- Fitter: `tools/fit_transforms.py`. Model unchanged: ux = s*x + a, uy = s*z + b.
  Anchors: AreaJump↔_03/_13 stair icons, Portal↔_02, Warp(pos)↔_06/_07/_08/_09 door
  icons (du10x doors are _09 pentagons, 2 per warp pair; du00x are _06/07/08).
  Multi-layer aware: each anchor pairs against ITS layer's icons (per-layer icon roots
  `{dun}_{area}_{idx}_icon`).
- Pipeline: (1) EM coarse-s scan 5.2..7.8 (NN re-pair at 25px + median offset), from old
  and global inits; (2) direct s-sweep 5.4..7.4 with median offsets (3 EM iters);
  (3) blind 2D offset grid (a±4000, b±8000 @250px, loose 150px detection, s∈{6.2,6.4,6.6})
  + staged refinement — needed because z spans reach ~2200m → b offsets up to ±7000px;
  (4) RANSAC refine (3-pt samples gated on 10m x AND z span — degenerate 3-pt similarity
  samples were the v1 bug) + shared-s median re-fit + 2 EM iters.
- Write policy: new cache (out/dbg_ui2world_*.json, backs up to out/transform_old/)
  only if 5.0≤s≤8.0 AND (strict improvement for ≥4-inlier fits, or s pinned to the global
  consensus 6.41 for 1–3-inlier fits — with <4 inliers the scale is under-determined and
  drifts to sweep edges, e.g. du007_0000 tried s=7.8). Renderers read out/ first,
  falling back to the old project's caches.
- Results (final run, 42 areas): 22 strong fits (≥12 inliers@12px, incl. all du10x
  floors: du103_0030 57→70, du103_0020 36→51, du102_0030 50→60), ~10 medium (4–11),
  6 weak (1–3, s pinned to 6.41: du002_0000/0020, du003_0030, du005_0020, du007_0000,
  du007_0050, du102_0000), 3 unfit (kept old global transform: du001_0010, du003_0010,
  du007_0020 — their icons and gimmick positions are in inconsistent frames; no
  s/offset pairs any anchor within 12px).
- Old-fit root cause confirmed: the legacy fitter's "sane band" gate (6.0≤s≤7.0, |t|≤25)
  silently fell failing floors back to the dungeon-global transform (s≈6.44, t≈median) —
  that's why du002/du003/du005/du007 floors had off-corridor arrows.
- du005_0030 fits at s=5.70 (6 inliers, rms 0.0) — 11% off the global scale; verified
  visually (all markers on geometry). Trust the data per-floor; scale is not global.
- du007_0000 detail: icons cluster near world origin (±170px) and only 4–5 anchors are
  pairable (2 stairs + 2–3 portals; 12 warps have NO door icons in this area). Portal
  icons sit ~315px off their gimmick positions → permanent outliers; the stair-pair fit
  (s=6.41, t≈(-10,5)) is the usable transform. Verified visually: B7 floor markers all
  on geometry.
- Spot-checked renders (out/maps_v2/): du007_0000 B7, du005_0030, du003_0000,
  du002_0010, du103_0030 — all warp/jump/portal markers on corridors and room edges.
- All 71 maps re-rendered into out/maps/ with the new transforms.

## Environment & runbook (read this on restart)
- Python: the old project venv. Path contains a space — ALWAYS quote it:
  `"<GAME_DIR>/sh2-minimap/venv/Scripts/python" -X utf8 <script>`
  (bash: unquoted `$PY` vars word-split and silently fail; also redirect loop stdin with `</dev/null`).
- Japanese text: keep `-X utf8` / `PYTHONIOENCODING=utf-8`.
- `<GAME_DIR>/sh2-minimap/dbg_all_combos.txt` has CRLF line endings —
  strip `\r` before use (`line=${line%$'\r'}`).
- numpy 2.x in the venv: no `ndarray.ptp()` (use `np.ptp`), cKDTree.query with a single
  point needs shape (1,2) to get array outputs.
- Old project is READ-ONLY. Key input files (all in `<GAME_DIR>/sh2-minimap/`):
  * `gimmicks.json` — per-area gimmick records: {kind: MapGimmic_Warp|MapGimmic_Portal|
    MapGimmic_AreaJump, pos [x,y,z] (world, +y = floor up), label (JP), warp_to (partner
    warp's pos, warps only)}. 803 warps + 116 portals + 89 jumps total.
  * `dbg_ui_tree_<dun>.json` — full automap UI scene tree per dungeon; every node has
    {pid, parent_pid, name, active, world (UI px), sprite}. Icon nodes: name="Icon",
    sprite=Icon_AutoMap01_NN; per-layer icon roots named `{dun}_{area}_{idx}_icon`
    (single-layer areas have `_0_icon`).
  * `automap_<dun>/*.bin` — raw BC7 tile quads, named `{dun}_{area}_{L}_{gx}_{gy}.bin`
    (gx/gy = 15m grid index; decode: BC7 alpha mask, 16x16px per tile).
  * `dbg_ui2world_<dun>_<area>.json` — OLD transforms {s, t:[a,b], flip:[1,1]} (pre-Task B;
    some are the global fallback s≈6.44 t=(0,0)).
  * `dbg_warpsoul_<dun>_<area>.json` — warp-soul positions (du10x only; empty for du004/du007).
  * `dungeon_names.json`, `_msg_common_{en,jp}.json` (6,756 strings), `sh2_decrypt.py`
    (bundle decryption, byte-verified), `dump/csharp/Assembly-CSharp.decompiled.cs` (IL2CPP
    stubs — no method bodies), `fit_ui_areas.py` (legacy fitter — root-caused, superseded),
    `layers.py` (legacy icon-matching layer solver — superseded), `PIPELINE.md`/
    `PAUSE_STATE.md`/`SUMMARY.md` (old docs).
- Repo layout (`tools/`, `out/`, `tools/data/`):
  * `docs/DEVELOPMENT-LOG.md` — this file (source of truth).
    * `tools/solve_layers_labelled.py <dun> <area>` — layer solver (writes
    `out/dbg_layers_<dun>_<area>.json`: n_layers, y_of_layer, labels, spacing, scores).
  * `tools/build_minimap_layers.py <dun> <area> <out.png> [--layer N] [--all]` — renderer.
    Reads transforms from `out/dbg_ui2world_*.json` first, falls back to the old project.
    `--all` writes `<stem>_L<i><ext>` per layer. Header shows official EN+JP names.
  * `tools/fit_transforms.py [dun area ...]` (pairs, or all 42 by default) — transform
    fitter (Task B). Writes `out/dbg_ui2world_*.json` (method coarse-ransac-v3,
    n_inliers, rms) after backing up previous out/ caches to `out/transform_old/`.
    Idempotent: re-running keeps converged floors.
  * `tools/{build_minimap.py, layers.py, probe_layers_du007.py}` — legacy/reference.
  * `out/maps/` — 71 final PNGs (35 single-layer floors as `*_L0.png` + 35 per-layer
    maps of the 7 multi-layer areas + fi999_0002), rendered with the new transforms.
  * `out/maps_v2/` — spot-check renders from Task B verification (5 floors).
  * `out/dbg_layers_*.json` — per-area layer solutions (43 areas).
  * `out/dbg_ui2world_*.json` — per-area NEW transforms (39 areas; 3 have no file →
    renderer uses the old project's global fallback: du001_0010, du003_0010, du007_0020).
  * `out/fit_report.md` — full per-area old-vs-new transform table (regenerated below).
  * `out/transform_old/` — pre-overwrite backups of out/ transform caches.
- End-to-end re-render: `while read line; do line=${line%$'\r'}; set -- $line; python
  -X utf8 tools/build_minimap_layers.py $1 $2 out/maps/${1}_${2}.png --all </dev/null;
  done < tools/data/dbg_all_combos.txt` (≈4 min).

## Task B results (per area; full table in out/fit_report.md)
| area | layers | new s | new t (a,b) px | inliers@12px | status |
|---|---|---|---|---|---|
| du001_0000 | 1 | 6.40 | (-13,-1) | 7 | refit |
| du001_0010 | 1 | 6.44 | (0,0) | - | old(kept, unfit) |
| du002_0000 | 1 | 5.80 | (117,-116) | 2 | refit (weak, UNPINNED — see below) |
| du002_0010 | 1 | 6.45 | (0,-2) | 14 | refit |
| du002_0020 | 1 | 5.20 | (-397,305) | 2 | refit (weak, UNPINNED — see below) |
| du003_0000 | 1 | 6.64 | (-42,-53) | 4 | refit |
| du003_0010 | 1 | 6.44 | (0,0) | - | old(kept, unfit) |
| du003_0020 | 1 | 6.41 | (1,1) | 12 | refit |
| du003_0030 | 1 | 6.41 | (758,1192) | 3 | refit (weak, pinned) |
| du003_0040 | 1 | 6.44 | (0,0) | - | old(kept, <4 anchors) |
| du003_0050 | 1 | 6.44 | (0,0) | - | old(kept, <4 anchors) |
| du004_0000 | 4 | 6.41 | (0,1) | 58 | refit |
| du004_0010 | 7 | 6.40 | (1,1) | 18 | refit |
| du004_0020 | 1 | 6.38 | (4,-1) | 19 | refit |
| du005_0000 | 1 | 6.44 | (-1,1) | 19 | refit |
| du005_0010 | 1 | 6.37 | (-2,-1) | 15 | refit |
| du005_0020 | 1 | 6.41 | (-1,-1) | 2 | refit (weak, pinned) |
| du005_0030 | 1 | 5.70 | (64,-516) | 6 | refit (own scale, verified visually) |
| du005_0040 | 1 | 6.54 | (-2,11) | - | old(kept, <4 anchors) |
| du007_0000 | 8 | 6.41 | (-2,6) | 2 | refit (weak, pinned; portal icons are outliers) |
| du007_0010 | 7 | 6.36 | (-3,2) | 6 | refit |
| du007_0020 | 5 | 6.44 | (0,0) | - | old(kept, unfit) |
| du007_0030 | 2 | 6.44 | (0,0) | - | old(kept — 27 inliers already, no improvement found) |
| du007_0040 | 2 | 6.41 | (2,1) | 21 | refit |
| du007_0050 | 1 | 5.60 | (-4,16) | 2 | refit (weak, UNPINNED — see below) |
| du101_0000 | 1 | 6.41 | (-0,1) | 4 | refit |
| du101_0010 | 1 | 6.40 | (0,-0) | 6 | refit |
| du101_0020 | 1 | 6.40 | (-0,-0) | 15 | refit |
| du101_0030 | 1 | 6.41 | (-0,-1) | 25 | refit |
| du101_0040 | 1 | 6.40 | (0,0) | 40 | refit |
| du101_0050 | 1 | 6.38 | (-0,-0) | 14 | refit |
| du102_0000 | 1 | 6.41 | (2,-0) | 2 | refit (weak, pinned) |
| du102_0010 | 1 | 6.41 | (-1,-0) | 6 | refit |
| du102_0020 | 1 | 6.38 | (0,2) | - | old(kept — 38 inliers already, no improvement found) |
| du102_0030 | 1 | 6.40 | (0,-0) | 60 | refit |
| du102_0040 | 1 | 6.43 | (0,1) | 34 | refit |
| du103_0000 | 1 | 6.39 | (-1,1) | 4 | refit |
| du103_0010 | 1 | 6.38 | (-2,1) | 6 | refit |
| du103_0020 | 1 | 6.40 | (-0,-0) | 51 | refit |
| du103_0030 | 1 | 6.40 | (0,0) | 70 | refit |
| du103_0040 | 1 | 6.40 | (-0,-0) | 22 | refit |
| fi999_0002 | 1 | 6.44 | (0,0) | - | old(kept, no anchors) |

UNPINNED weak fits (du002_0000 s=5.80, du002_0020 s=5.20, du007_0050 s=5.60): the s=6.41
pin produced FEWER inliers than the drifted fit, so the drifted s was kept. These three
floors have only ~2 pairable anchors each — treat their arrow placement as LOW CONFIDENCE;
verify in-game or improve anchors (Task D markers would help).

## Task C — portal destination labels (DONE, verified)

**Names**: the `MapPortalTable` ScriptableObject in `SH2_Data/StreamingAssets/win/_commontable.dec`
(read via UnityPy: MonoBehaviour m_Name='MapPortalTable', MonoScript 'MapPortalDataArray') holds
all 117 `MapPortalData` rows; each `m_GimmicID` matches a `MapGimmic_Portal` in gimmicks.json
(all 116 matched; 1 table-only `du005_0020_GIMMICK_009` = unused). `m_NameLabel` keys resolve in
`_msg_common_{en,jp}.json` (`MAP_PORTAL_NAME_000..127`, 68 distinct, all present).
Dumps: `out/portals_raw.json` (table rows), `out/portals.json` (joined: `dun, area, group
(1..7, 100..102 = Soul Matrix), menu (in-group order), subarea, name_en/jp, pos, in_gimmicks`).

**Positions** (verified by render + count audit): `MapGimmic_Portal` world coords are
PORTAL-ROOM-LOCAL, not floor world — they cluster near the origin (±~120 m) on every floor
while the actual in-map markers span the whole floor. A per-area similarity transform to the
`_02` icons fails in most areas (median residuals 190..535 px; only du103_0040 s=6.34/0.6 px
and du005_0000 s=6.48/13 px fit — coincidences). Don't try to transform them again
(`tools/fit_portal_transforms.py` documents the dead end).

**How labels are drawn** (`build_minimap_layers.py:draw_portals`): the in-game minimap's own
portal markers are the active `Icon_AutoMap01_02` leaves (children of `IconAM02` containers
under the `{dun}_{area}_{L}_icon` root; each icon set is instanced TWICE in the UI scene —
minimap + `PartsTraverse` fullscreen — dedupe by position). Count audit: unique `_02` icons ==
portal count per floor in ALL areas (du00x and du10x alike; du10x `_02` = portal gates, not
some other gimmick). Label = `name_en` badge next to the icon, font scaled with canvas extent
(13..34 px). Multi-layer: portal→layer via `m_SubAreaID` (du007_0000: 0/2/6 ✓, du004_0010:
0/4/6 ✓); single-layer: all rows on L0 (subarea is a sub-area id there, e.g. du103_0030 uses 0/7).
**UNVERIFIED**: which name goes to which icon — pairing assumes icon-container document order ==
gimmick-ID order (editor creation order). Spot-check one floor in-game to confirm; a swap only
matters for same-name-different spots (Gate 2 vs 3 etc.).

Final maps with portal labels: `out/maps_v2/` (69 PNGs).

### Arrows: interactability gate (FINAL, user rule 2025-01)

User rules: warp arrows only for physically interactable objects the player
actually uses; **never on plain door icons**; portal labels genuinely
semi-transparent.

`keep_warps` = **warp-soul gate only**: a warp is kept iff an `mp_warp_soul`
sits within 2m of its pos — the only hard evidence of interactability.
Result: arrows exist ONLY on the 10 du10x floors with populated soul files
(du101_0020..0050, du102_0020..0040, du103_0020..0040; e.g. du103_0030 =
70 arrows). Every other area has an empty soul file → zero warp arrows
(all du00x, all du007 incl. the inter-floor connector floors, du101_0000/
0010, du102_0000/0010, du103_0000/0010). Door/gate icons still render as
sprites; du007 →Bn badges are lost. If arrows are wanted back on specific
floors, the way is more warp-soul data (Task D), not looser gates.

Rejected alternatives (both tried, both rejected by the user on real renders):
- labelled-warp fallback (old): drew du007_0050's 10 unplaced
  `Warp（B20）(n)` editor warps (21–67m from any door, two at (0,0,0)) →
  "random arrows that begin/end in nothing".
- door-icon proximity fallback (warp within 6m of a `_06/_07/_08/_09`
  icon): let du003_0000's 5 of 22 `N個目の扉①/②` door warps through with
  `warp_to` destinations spanning the whole map → "a lot of random arrows"
  (du003 has no soul data, so none of those warps is proven interactable).
  Also note du002_0010's 24 warps ARE real door-pair warps (12 doors ×
  ①/②, 4–6m apart) — they just lack soul proof, so they're arrow-less too.

**Label transparency**: PIL `ImageDraw` REPLACES pixels, it does not blend —
drawing a badge with alpha<255 straight onto the canvas still overwrites the
map. Both badge drawers must paint onto a transparent overlay and
`im.alpha_composite(ov)` (warp arrows already did; `draw_portals` was fixed
to do it too; badge bg alpha 130).

### Task D: enemy/boss markers (2025-01) — DONE

- **du001_0000 red mark IDENTIFIED**: not an enemy/event marker — it is the
  `Icon_AutoMap01_07` warp-door sprite (same П pentagon as the other doors,
  small red triangle badge at its bottom-right; AUTOMAP_NOTES: `_07` =
  door + red/green triangle). Located at icon (733,331) ui-space.
- **`event_points.json` (old project) has NO static source**: byte-scanned
  ALL of StreamingAssets (19G: mapnew 5G, Demo, character, effect, Event,
  Table, Interface, Battle, Message, Data-root scene bundles) for
  'EV03_101_BossModel' / 'Boss_パス' / 'イベントヒット' — zero hits outside
  the file itself. It came from the old project's LIVE in-game memory dumps
  (same origin as the `dbg_*` caches). Only du101/du102/du103 are covered.
- **Static enemy spawns DO exist in scene bundles**: byte-scan for
  'Gimmic_SpawnEnemy' across all 112 mapnew bundles → exactly 4:
  du004_0000 (1), du101_0020 (1), du102_0040 (36), du103_0040 (28 after
  1m dedup). All boss/gauntlet floors. du103_0040 has two families:
  `Gimmic_SpawnEnemy` (7, y=-21.9 = boss-arena minions, co-located with
  event_points EV03_501_BossModel (-5,-25.9,177.4)) and
  `Gimmic_SpawnEnemyWrapAround` (29, y=-9.9 = main gauntlet floor). Each
  object appears twice (instance + (0,0,0) prefab variant) → origin dupes
  dropped. Positions are WORLD space: overlay test puts every point on the
  geometry (7 in the boss room, rest along the gauntlet corridors).
- **No other enemy data is static**: regular-floor enemies spawn at runtime
  (commontable `AreaSpawnTable`/`EncountPackParamTable`/`EnemySpawnTable`
  are ID/count tables with no world positions). The in-game minimap enemy
  marker is the 'Enemysymbol' SPRITE (found in `map_resident_data`, the
  908K minimap-UI bundle — canvases/sprites, no scene data). Item pickups
  also don't exist as scene objects (only VFX `eff_*` nodes) → no static
  item markers possible.
- **Bundle anatomy (duXXX_YYYY_area_scenes, UnityFS, 70–100MB)**:
  environment graphics (clouds/fog/lights/collision), `mp_warp_soul_*`
  (du10x), MapGimmic_Warp/Portal/AreaJump/Switch + MapGimmicPrefab,
  MapCollisionInfo, MapEditorMonoPointManager. NO event objects (EV/Boss/
  NPC names) in any area bundle — not du103_0030 either (same 805 names as
  the old project's archived dump).
- **Renderer**: `draw_enemies()` in build_minimap_layers.py — enemy spawn =
  red dot (r=5–9 by canvas), boss arena = red target ring+dot from
  event_points BossModel (du10x). Multi-layer layer-filter via the same
  y-band rule as warps (verified: du004_0000 spawn dot on L0=1F only,
  absent on L1). All 69 maps re-rendered into out/maps_v2/.
- Tool: `tools/extract_enemy_spawns.py` (copies bundle to local-copies on
  first run; outputs out/enemy_spawns.json; re-runnable on any bundle
  name).

### Task E: _commontable.dec mining (2025-01) — DONE

The commontable bundle carries FULL IL2CPP class metadata, so UnityPy
`o.read()` yields TYPED fields directly — no raw-byte/il2cpp.h parsing
needed (old project's Il2CppDumper dump not required).

- **`tools/dump_commontable.py`** → `out/commontable.json` (19MB,
  76 tables, every MonoBehaviour, nested structs recursively converted).
  Key tables: QuestData×62, EnemyTable 398 rows, CharParamTable 601 rows,
  7 item tables (ItemUse 200 / ItemKey 100 / ItemAcs 200 / ItemMana 500 /
  ItemMat 200 / ItemMeal 100 / ItemCos 100), DropItemTable 375,
  MapAreaInfoDataArray 85, EncountTable/AreaSpawnTable/EnemySpawnTable
  (ID+count tables, no positions — see Task D), Skill tables, NakamaTable.
- **`tools/commontable_digest.py`** → `out/digest/` (labels resolved
  via _msg_common_en/jp.json; patterns VERIFIED against the msg table's own
  keys): quests.json (62, en+jp titles, requester, rewards, map targets),
  enemies.json (397/398 named), nakama.json (162 devil codex entries w/ lore),
  items.json (~900 items, en names + descriptions), skills.json (851),
  chars.json (166 named), map_areas.json (place table + 85 area rows).
- **Place→dungeon map** (VERIFIED against the map titles we render):
  1001=Shipping District=du001, 1002=Central Line=du002, 1003=Subway Line
  14=du003, 1004=Ozaki Hope Towers=du004, 1005=24th Ward Municipal Tower=
  du005, 1007=Hachigaya Training Field=du007, 1100-1105=Soul Matrix=du10x,
  0-12=Tokyo field areas (Marunouchi, Shibuya, Karakucho…). 24 quests carry
  a mapPlaceId target → quest→dungeon routing possible.
### Task E2: quest objectives on the minimaps (2025-01) — DONE

- **ER-quest targets are NOT point-placeable**: QuestTargetData = {skillAttribute,
  iconType, mapPlaceId, areaId} only; ALL 24 have areaId=0 and 21/24 point to
  place 1000 which is absent from MapAreaInfoDataArray (unmapped). No goal/
  target sprite in the icon dumps (icon set = door/portal/unknown-area/one-way-
  arrow only). So 4 resolvable ER quests (ER27→du002, ER28→du003, ER29→du004,
  ER30→du005) get a BLUE badge on every floor of the target dungeon (place-
  level, no floor info).
- **Aion orders ARE floor-placeable** (the real find): AionOrderData (45)
  targets carry mapPlaceId 1101/1102/1103 (=du101/du102/du103, VERIFIED via
  the 'Soul Matrix - Arrow/Milady/Saizo Sector' map titles) + areaId = floor.
  31 targets resolve to named enemies/item + exact floor. Types: 1 = cleanup
  (kill N mass-mob), 2 = 'Target: X' (boss), 0 = item pickup (EA02 'Chain
  Crystaloid Beta', name via item-table index — the only type-0 target, low
  confidence). 14 targets also use place 1000 (unmapped, skipped).
- Digest: `out/digest/aion_orders.json` (45 orders, resolved targets).
- Renderer: `draw_objectives()` in build_minimap_layers.py — gold aion badges
  on the matching floor (right edge, below title bar), blue quest badges on
  all floors of the target dungeon. Note: the font mis-measures '×' (U+00D7),
  badges use ASCII 'x'.
- Result: 15 soul-matrix floors carry 2-3 objective badges each (du101 L0/1/3/
  4/5, du102 L0-4, du103 L0-4); 4 field quests badge du002-005. All 69 maps
  re-rendered into out/maps_v2/.

### Task E3: region isolation for objectives (2025-01) — DONE

- **Boss-target regions ARE locatable**: event_points.json (LIVE dump, du10x
  only) carries one `EVxx_yyy_BossModel` point per soul-matrix floor, and it
  sits in the boss room (verified Task D). The 15 'Target:' (type-2) orders
  map 1:1 to those floors -> gold ring + 'EAxx <name>' label around the red
  boss ring (draw_enemies). **The `EAxx_Boss` points in the same dump are
  event TRIGGERS 40-90m outside the arena - never anchor to them**
  (measured: EA33_Boss (-92,-17.9,17.5) vs EV03_101_BossModel
  (-54.5,-21.9,102.5)).
- **Cleanup (type-1) regions**: only the gauntlet floors with static minion
  dots (du102_0040: 36, du103_0040: 28) get a translucent gold bounding
  rect + '<EA> <name> xN (spawn zone)'. Other cleanups: badge only (no
  position source).
- **PIL gotcha (root-caused with a minimal repro)**: this PIL version
  REPLACES a pixel's alpha when a translucent fill is drawn over another
  translucent shape on the same overlay (ring a=235 under zone-rect fill
  a=26 -> a=26 -> invisible after alpha_composite). Rule: overlapping
  translucent elements need SEPARATE overlays, or draw order matters.
  `draw_objectives` composites the ring on a second overlay drawn last.
- Caveat: BossModel positions come from one live session; boss arenas are
  fixed rooms so they're reliable (Task D: ring lands exactly in the room).
  All 69 maps re-rendered.
### E2 follow-up: place-1000 decode + FULL request sweep (2025-01) — DONE

- **"Place 1000" = `DU000_NONE`** — decoded from decompiled code
  (`dump/csharp/Assembly-CSharp.decompiled.cs`, `eMapPlaceID`):
  0-12 = FI fields (Marunouchi…Komadori), **1000 = DU000_NONE (no dungeon,
  by design)**, 1001-1007 = du001-007 (no 1006), 1100 = SM Entrance,
  1101/1102/1103/1104/1105 = Arrow/Carmilla/PsyZow/Merlin/FIG sectors.
  `eQuestTargetType` 0=Item, 1=Enemy, 2=Devil (named boss).
  `eQuestTargetEnemyPlaceType` 0=None / 1=Map / 2=MapAndArea (floor valid).
  `QuestTargetData` struct has NO hidden coordinate fields (verified in code;
  the game's own `IsDesignatedArea(placeId, areaId)` does exactly what we do).
- **Full sweep of every request table — nothing left unmappable:**
  - QuestData (62): 24 have targets = **5 du001-005** (ER26-30 'A New
    Hee-Home P1-5', Map-only, areaId=0) + **19 DU000_NONE** (Item x10 /
    Enemy x5 / Devil x4, enemyPlaceType=None → field/city objectives like
    deliveries — no location by design); 38 have no target (story flags).
  - AionOrderData (45): **31 du101-103 + floor** (15 Devil / 15 Enemy /
    1 Item EA02 — all drawn) + **14 DU000_NONE Item** (bring-to-safehouse,
    no map by design).
  - PersonalEventData (46): no location fields (event flags).
  - SafeHouseDataAll: NPC cutscene placement (room-local, not maps).
  - UniteHelpParams / EventSubData: no quest locations.
  → every mappable target is drawn; every 1000-target is locationless by
  design; the rest are story flags.
- **Fix found by the sweep**: ER26→du001 was missing (place map lacked
  1001) — added; du001_0000/0010 re-rendered with the ER26 badge.
### E2 follow-up 2: locating 'defeat enemy X' quests + NPC quests (2025-01) — DONE

- **YES, locatable**: `AreaSpawnTable` rows carry `{m_PlaceID, m_AreaID,
  m_EnemyIDs[]}` (+`EnemySpawnTable` `{m_EnemyID, m_PlaceID, m_AreaID}`
  fallback; place -1 = global). areaId 0 = literal floor 0 (du001 has both
  area-0 and area-10 rows; same convention as verified Aion orders). Joining
  quest target enemy ids resolves ALL 10 'defeat enemy' targets to
  dungeon+floor, e.g. ER34 Zhen x20 → du001 L0; ER41 Valkyrie x14 → du001
  L10; ER18 Vritra x3 → du001 L10 + du007 L0 + du101 L5 + du102 L4 + du103
  L4 (enemies have multiple spawn floors — each gets the badge). Enemy names
  via EnemyTable `m_NameLabel` → NAKAMA_xxx. The 4 'Devil' (type-2) targets
  (Koppa Tengu etc.) are NOT in spawn tables (scripted encounters) —
  unplaceable by design.
- **NPC quests**: `requesterMapId` is the NPC's location (same eMapPlaceID).
  14 ER quests have dungeon requesters (1001-1007) → blue 'Find <npc>
  (ERxx)' badge on every floor of that dungeon (dedup: skipped when the quest
  already badged the dungeon). Field requesters (FI001 etc.) unrenderable
  (no field maps). Exact NPC floor not in any table (cutscene placements only).
- Digest: quests.json targets now carry type/id/count/enemyPlaceType/dun/
  enemyName/spawn_locs; quests carry requesterMapId/requester_dun.
- Renderer: draw_objectives() — cyan badge '<ER> <enemy> xN' on spawn floors
  (new color: cyan = spawn-located enemy, blue = target/requester dungeon,
  gold = aion order). Re-rendered all 9 affected dungeons (du001-005, du007,
  du101-103) into out/maps_v2/. Verified: du001_0010 L0 shows Quest ER26
  + Find Makami (ER32) + Find Brodie (ER92) + ER41 Valkyrie x14 + ER18 Vritra
  x3; du101_0050 L0 shows EA13 Cerberus x5 + EA15 Target: Raven + ER18/ER30
  cyan badges.
- **Renderer CLI gotcha**: `--all` writes per-layer files named
  `<dun>_<area>_L<n>_L<n>.png` + stack — NOT `<dun>_<area>_L<n>.png`
  (plain run does). Re-render loops must use the plain run for the canonical
  files. (The follow-up re-render loop dumped 110 byte-identical `_Lx_Lx.png`
  twins into maps_v2 — removed by md5 dedupe; 97 canonical per-layer PNGs
  remain, du007 now has ALL its layers.)
- **Floor level is the MAXIMUM resolution for quest locations (verified
  exhaustively)**: the full spawn chain is Area → Pack → Encounter → Enemy,
  all ID/ratio fields, no coordinates: `EncountPackParamTable` (pack→encounter
  + ratio only), `EncountTable` 620 rows (enemy groups, flags, layout strings —
  the layout names are formation PREFABS shared across dozens of encounters,
  e.g. '02_a' x76, not placed objects), `MapAreaInfoDataArray` (place/area/
  subarea ids + name labels, no positions). Static `Gimmic_SpawnEnemy` points
  exist only on the 4 soul-matrix gauntlet floors (Task D). NPC world
  positions: none (SafeHouseDataAll cutscene room-coords only). Corroborating:
  the in-game icon set has NO goal/objective pin sprite (Task E2) — the game's
  own minimap also only resolves objectives to dungeon/floor level.
  **PARTIALLY RETRACTED 2025-01**: that '4 gauntlet floors only' claim came
  from Task D grepping the exact `Gimmic_SpawnEnemy` name; du001_0010_area_scenes
  actually contains a `Gimmic_SpawnEnemyWrapAround` GameObject (see NPC hunt).

### NPC location hunt — RESOLVED as SPAWN-GIMMICK FIND (2025-01) — DONE

- **Task D's '4 gauntlet floors' claim was a SCAN MISS** (byte-scanning the
  bundles finds nothing — content is compressed; must parse via UnityPy).
  v2 `extract_enemy_spawns.py` audits ALL 97 du*/fi* bundles; static spawn
  gimmics exist on **7 floors**: du001_0010 (1), du004_0000 (1), du101_0000 (1),
  du101_0020 (1), du101_0050 (18), du102_0040 (36), du103_0040 (28).
  The 4 old floors reproduce byte-identically (regression-checked); no field
  map (fi*) has static spawns. Maps re-rendered + visually verified: du101_0050
  dots sit in the NW maze block INSIDE the EA13 zone rect (which the renderer
  now draws there automatically); du101_0000 dot on a corridor junction next to
  a chest icon; **du001_0010 dot at (1206-1217, 1230-1240) px = the south
  corridor junction of the maze = the ER41 'R.S. lure / frenzied Valkyrie
  horde' room** (quest text: 'called me out to the West Shipping District ...
  summoned a whole horde of frenzied demons'; Valkyrie x14 spawn-located to
  du001_0010 via AreaSpawnTable — two independent sources agree).
- **Parser anatomy of these stripped bundles (root-caused, v2 extractor):**
  the object stream may hold TWO serialized scenes (editor frame at origin +
  world frame) with COLLIDING path_ids between halves; GO copies serialize
  befoout/between transform blocks and halves don't split at the same byte
  offset. v2 rule: split the TRANSFORM stream at its largest byte gap; a
  Transform is a gimmick if ANY GameObject copy of its m_GameObject path_id
  has a spawn name; world matrix = parent chain resolved within the same
  transform block; drop (0,0,0) copies; dedupe positions across blocks tol 1.0.
  (Byte-proximity naming alone misnames du004_0000's world copy; pid-set
  membership is robust.)
- R.S. itself: charId 2107 (CNAME_ND_DQN); the du001 'R.S.' you meet is the
  impostor CNAME_NS_ER41_RS_FELLOW (charId 3151). No placed-NPC objects exist
  in scene bundles (models live in win/character/nd041_*, ER41 cutscenes in
  win/Demo/demo_request_er41_*; MB int-scans for placed charIds NOT needed —
  the horde-room pin answers the quest). R.S.-quest pin = Valkyrie-horde room
  = the du001_0010 dot.
- Tools: `tools/audit_spawn_gimmics.py` (per-bundle name+pos audit),
  `tools/scene_tree.py` (tree dump; superseded by v2 extractor),
  `tools/dump_scene2.py`, `tools/dump_gimmic.py`,
  `tools/scan_scene_names.py` (raw scan — USELESS on these bundles:
  content compressed, only header strings visible — explains the Task D miss).

### Map-pinned objective labels (2025-01) — DONE (answers 'where IS it on the map?')

- User feedback: corner badge lists are not 'labelled on the map'. Fix in
  `draw_objectives`: floors with **1-3 static spawn dots** now draw the
  objectives that resolve to that floor (data-driven: quest type-1 targets
  whose AreaSpawnTable floors include this floor + cleanup orders) as red text
  **pinned under the dot**. du001_0010 dot now reads 'ER41 Valkyrie x14 /
  ER18 Vritra x3' (= the R.S.-lure room). Zones (>3 dots) already label
  themselves; 15 boss rings already label themselves.
- `tools/map_index.py` -> `out/maps_v2/INDEX.md`: every map file + the
  labels it shows; '^ PINNED ON MAP' marks floors with dot-pinned labels.
  Index matches renderer dedup (requester 'Find <npc>' badge only shown where
  the quest has no other badge on that floor; R.S.-quest: du001_0000 badge +
  du001_0010 pin). Re-rendered: du001_0010, du004_0000, du101_0000/0020.
- Also: `out/maps/` (71 PNGs) is the OLD pre-objective set — superseded by
  maps_v2, noted so users don't open unlabelled maps by mistake.

### Full coverage audit of ALL requests (2025-01) — DONE

- `tools/coverage_report.py` → `out/digest/coverage.md`: every ER-quest +
  Aion-order objective (114 rows) with its map marker + location. Totals:
  **RING 15** (every 'Target:' boss order — event_points ring), **PIN+FLOOR 9**
  (5 quest kill-targets + 4 cleanup orders on floors with static dots),
  **FLOOR 17** (cyan exact-floor badges; runtime-spawn floors), **NPC-BADGE 14**
  (dungeon requesters), **DUNGEON 0 surplus** (the 5 ER du-place quests all
  upgraded to FLOOR by spawn tables), **NONE 28** (14 safehouse deliveries +
  10 field item deliveries + 4 scripted Devil kills — zero location data by
  design), **story-flag 31** (no target at all).
- Full gimmic inventory of ALL 97 bundles (`tools/audit_all_gimmics.py` →
  `out/gimmics_all.json`, 32 bundles have gimmics): families are Warp,
  Portal, AreaJump, Gate/GateLong, RandomWarp, ElevatorPanel, doors/walls
  (DU003/004/005/007-specific), SafehouseDoor, SpawnEnemy/WrapAround —
  **NO item/treasuout/NPC gimmics exist** → item-pickup & NPC pins are
  definitively impossible from static data; FLOOR badge is the max there too.
- Spawn gimmics carry NO MonoBehaviour (enemy attribution stays table-level;
  AreaSpawnTable is the link).
- `enemy_spawns.json` now never keeps empty-floor keys (write-time prune).

### NPC location hunt (R.S. / ER41) — original investigation notes

Question: the user noted R.S. (ER41 requester, in du001) has a FIXED in-game
spot that's a pain to find — is it in the data?

- **R.S. identified in data**: `CNAME_ND_DQN` = charId **2107** (modelId 4,
  CharParamTable). The du001 encounter is an IMPOSTOR: `CNAME_NS_ER41_RS_FELLOW`
  ("R.S.'s Crewman") = charId **3151** (modelId 105). Quest text confirms
  location: ER41_ORDER "go investigate at the West Shipping District" (= du001,
  matches requesterMapId 1001); ER41_MIDDLE1 "He'd called me out to the West
  Shipping District ... summoned a whole horde of frenzied demons" (the ER41
  Valkyrie x14 target, spawn-located to du001_0010).
- **du001_0010_area_scenes DOES contain a static spawn gimmick**: GameObject
  `Gimmic_SpawnEnemyWrapAround` (root transform at 0,0,0 under
  `du001_0010_Anchor_Gimmics`, also 0,0,0). Real points are expected on CHILD
  transforms — the hierarchy walk was NOT finished (Transform→GameObject name
  join failed: `gos` was keyed by `o.path_id` but the walk looked up
  `t.m_GameObject.m_PathID` in a dict keyed by something else; both are
  path_id, so the actual bug is the name-filter list comprehension — verify
  `gos` was populated before use).
- **UnityPy gotchas (this build, verified)**: `env.objects` is a property
  (LIST, not a method); `o.type_str` and `o.sourceID` are None — classify by
  `type(o.read()).__name__` (GameObject/Transform/MonoBehaviour/...) and key by
  `o.path_id` (GameObject component PPtrs carry `m_PathID` == `o.path_id`).
  `o.peek_name()` exists (name without full read). Transform has NO m_Name
  (Unity 2020: name lives on GameObject, via `m_GameObject.m_PathID`).
  Scripts: `tools/dump_scene2.py` (type counts + names),
  `tools/dump_gimmic.py` (named GOs + transform pos + MB int32 dump — the
  MB-int part untested), `tools/scan_scene_names.py` (raw byte scan — only
  useful for uncompressed header strings; most bundle content is compressed).
- **BONUS find**: field maps have scene bundles too —
  `mapnew/fi000_0000_area_scenes` … `fi012_0000`, `fi009_1000`, `fi010_0010`,
  `fi011_0010`, `fi998_0000/0001/0002`, `du100_0000` (SM entrance),
  `du999_0003` (17 bundles). Field minimaps (and field NPC/requester pins)
  are therefore possible — separate task (needs the field auto-map tile data;
  old project only dumped `automap_<dun>/*.bin` for dungeons).
- Also scanned (dead ends): `win/Event/` = mostly bustup/portrait textures +
  4 `event_extra_npc_*` MODEL bundles (homeless_karakucho, ichika_komadori,
  young_milady — models, no placement); `demo_request_er41_er41_001..004` =
  ER41 cutscene bundles (fixed-camera demos, not open-world placement);
  decompiled Assembly-CSharp has only ER41 flag enums (11200-11219), no
  placement constants; EncountTable layout strings are formation prefabs.
- **PLAN (resumed)**: (a) fix the tree walk, dump `Gimmic_SpawnEnemyWrapAround`
  child points, transform via `dbg_ui2world_du001_0010` → if the cluster sits
  in one room, pin it as the ER41 'frenzy demons' spot (and re-audit ALL
  bundles for `*SpawnEnemy*` name variants — Task D's 4-floor claim is wrong);
  (b) scan every du001 object's MonoBehaviour int32s for charId 3151 (the
  crewman) / 2107 — if a placed NPC object exists, pin the real R.S. spot;
  (c) if (a)+(b) find nothing, conclusion = NPC open-world placement is
  runtime/event-driven (no static coords), floor badge stays the max.

- **Unresolved / out of scope**: per-event DIALOGUE lives in ~700 small
  per-event bundles under StreamingAssets/win/Message/<Lang>/ (event_request_
erXX, event_mainquest_emXX, event_npctalk_enXX, event_visionquest_evXX,
  event_personal_epXX, interface_*, movie_*) — the `common` bundle (240K)
  is already _msg_common_*.json. Extracting all of them = full story
  localisation, a separate project. Quest 'targets' have no text label in
  QuestData (objective lines probably per-event bundles too).

## Open items / next steps (in suggested order)
0. **NPC location hunt** (ACTIVE, paused) — see the "NPC location hunt" section
   above for state + resume plan (fix the scene tree walk, dump the
   SpawnEnemyWrapAround points, MB-scan for charId 3151/2107).
1. **Task D — enemy/item/event markers** — DONE (4 SM gauntlet floors; NOTE:
   the 'only 4 floors' claim needs re-audit — du001_0010 has a
   Gimmic_SpawnEnemyWrapAround the old grep missed).
2. **Task F — confirm in-game**: (a) layer ambiguities du004_0010 L0/L4 + du007_0020 B/C mix;
   (b) portal name→icon pairing (see Task C UNVERIFIED note — one floor is enough to settle it).
3. **Task E — decrypted-data mining** — DONE (commontable.json + digest/).
4. Housekeeping: du007_0030 & du102_0020 use old-project transforms (no out/ cache —
   fine, but a re-run of fit_transforms.py is the way to change that).

## Task G: mass decryption + quest-object placements (2025-01, DONE)
- **Encryption layer found & opened**: `win/Message/**` (9658 leaf bundles, all
  9 langs) + `win/Table/commontable` are AES-CTR-XOR encrypted; old project's
  `sh2_decrypt.py` (password `lAZr7V4e`, salt `<name>_bKo`, .NET PDB SHA1-chain
  key) verified byte-exact and was only ever applied to commontable.
  `tools/decrypt_all.py` -> **<decrypted-output>/** (9042 decrypted; 616 fails are
  CRIWare .acb/.awb voice archives — different container, no UnityFS magic).
  Everything else in win/ was already plain (Demo 2868, Event 1376,
  character 1033, mapnew 112...).
- **ER43 'Fatal Countdown' case study** (user walkthrough challenge): target =
  item id 33 x3 (bombs), mapPlaceId=1000 NONE. Decrypted Message ER43_003:
  Natsuhiko rigged the building with 3 bombs; objective "Find 3 s through
  Demon Recon"; hint line 0023 "close to ground level... Tower B as well".
  Location via table join: **er43_natsuhiko registered place 1004 area 0**
  (du004_0000), flags 11252-11255. Bombs themselves are Demon-Recon finds —
  no object registration, no coords (data ceiling confirmed same as Zhen).
- **object_placements.py** -> `out/digest/object_placements.json`: ALL
  EventListObjectAll places x areas -> 37 dungeon floors, 156 objects, 51
  quest-bound (itemId erNN_* -> ERNN; VERIFIED er41_rs_fellow=du001_0010,
  er43_natsuhiko=du004_0000, er06_pazuzu=du004_0020...). Also covers
  EA/EV/BM objects on du10x (matches live event_points dump).
- **Renderer**: magenta badge 'Find <Npc> (ERNN)' on the EXACT floor an ER
  quest NPC is registered (dedup: suppresses blue requester badge there).
  Name = itemId suffix humanised ('rs_fellow'->'R.S.'). All 41 areas re-
  rendered with --all (69 canonical per-layer PNGs in maps_v2; the 97-count
  earlier included --all naming twins, cleaned).
- **coverage.md refreshed**: PLACED 18, VIA-NPC 5 (bombs etc), NONE 23.
- **Deep-dive asset for later**: <decrypted-output>/ holds every decryptable game file
  (Message En+Jp+... -> AtMsgData m_oneLineData lines; read via
  dump_commontable.conv like ER43 sample, <local-copies>/message/er43_00*.dec).

## Task H: event stage positions (exact coordinates for map events) — DONE
- **Key discovery**: `win/Demo/demo_{dungeon,request}_XX_XX_NNN` bundles contain
  typeless nodes; nodes whose MonoScript class is `StCharaSetPos`/`StCharaMoveRoute`
  serialize world-space (x,y,z) float triples. VERIFIED: they project onto painted
  automap tiles via the fitted ui2world transforms (rooms/corridors, never noise).
  This is the ONLY per-event coordinate source in static data.
- **Tool**: `tools/extract_event_positions.py` -> `out/event_positions.json`.
  Joins: code -> EventListAll registration areas (du_area list), quest id (from
  eventName ERnn or contactName ERnn_*), first decrypted En dialogue line
  (<decrypted-output>/win/Message/En). 23 events have positions game-wide.
- **Renderer**: `draw_event_positions()` in build_minimap_layers.py. Cyan diamond
  + translucent teal label; drawn only (a) on floors in the event's EventListAll
  'areas', (b) inside floor Y-band (multi-layer), (c) where projected pixel is on
  a PAINTED tile (alpha>=60) - kills wrong-canvas duplicates. Multi-point events
  (party staging, walk routes) collapse to centroid.
- **Result highlights** (all 69 maps_v2 PNGs re-rendered):
  * ER35 'Night of the Living Snowman' -> du004_0010 L4 east room:
    'ER35 That demon looks like a black…'
  * ER49 'That Which Thirsts for Blood' -> du004_0010 L1 north room: '…strange
    demon ahead… Mada'
  * ER03 -> du005_0000; ed02_006/014 -> du101_0000; ed07_022 -> du005_0040;
    ed06_001 'Raven is just through here' -> du001_0010 entrance.
  * **ED05_012/ED05_021 'There's something on the floor…'** -> du004_0010 L2
    west room (-21..-25, y5, 22..24) — the hidden floor pickup; prime candidate
    for the walkthrough-marked ER43 bomb spot (bombs themselves still have NO
    coords anywhere: 6th exhaustive check).
- **coverage.md**: new marker EVENT-PIN (3: ER03, ER35, ER49 moved out of
  story-flag). Totals: PLACED 18, EVENT-PIN 3, VIA-NPC 5, NONE 23.
- Bombs (Key_032/item 33): still no coordinates by ANY channel; the ED05_012/021
  fixed spot is the best data-backed match for walkthrough bomb markers.
- **ER43 bomb surfacing (user request)**: out/event_overlays.json = curated
  overlay entries merged by draw_event_positions: orange diamond
  'ER43 Bomb site? floor-pickup spot (ED05_012/021, UNVERIFIED)' on
  du004_0010 L2 (the only fixed floor-pickup coords in du004) + orange note
  strips on du004_0000 (all 4 layers) / du004_0020 summarising the decrypted
  ER43_003 intel ('3 bombs, close to ground level... Tower B'; ER43_004_A fires
  on 0000, _B on 0010 - VERIFIED in EventListAll). 'Tower B' has NO matching
  area in data -> note says UNVERIFIED. Label stacking added (labels at same
  spot offset by 22px). Bug fixed: label col list+tuple TypeError silently
  killed du004 renders when stderr was /dev/null'd — check stderr on renders!

## Task I: map_resident_data = GROUND-TRUTH placement points — DONE (biggest find)
- **What**: `win/mapnew/map_resident_data` (one bundle) holds 104 per-area
  MonoBehaviours found via decompiled class names (MapAreaData_*):
  * `MapAreaData_EventPlan '<area>_evplan'.Points_Event` — every event/NPC
    placement point: Identifier, Label ('NPC ER41_R.S.の部下'), **world Pos**,
    Rotate, ObjectType (0=trigger,1=NPC), CharacterId, TriggerType(Hit/Button).
  * `MapAreaData_MapPlan '<area>_mapplan'.Points_SpawnEnemy/_SpawnMob` —
    fixed enemy/mob spawn-point pools per floor (45 areas, ~700 pts).
- **Tool**: tools/extract_map_resident_data.py -> out/event_npc_points.json
  (43 areas, 403 pts) + out/spawn_points.json. VERIFIED: R.S. (118.87,0,-30.57)
  lands on painted map at 'North: Iron Gates'; Jaaku (29.42,15,28.99) = L4 east
  room; ED05_012_CHECK access point (-18.44,8.85,21.12) ~ demo staging cluster.
- **Answers 'why can't you verify'**: previous searches failed because scenes
  only hold empty MapEditorMonoPointManager shells; the point data is injected
  at runtime from this resident bundle (class trace: EventArrangeManager.Load ->
  MapPoint_Event, decompiled Assembly-CSharp at sh2-minimap/dump/csharp).
- **Zhen (ER34)**: no per-enemy coords exist BY DESIGN — spawns roll from the
  fixed point pools: du001_0000 has 15 pts, du001_0010 has 20 (now drawn as
  orange x marks + legend). ER35's named NPC Jaaku DOES have an exact pin.
- **Renderer**: draw_event_positions now also draws (a) magenta exact pins
  'ERnn Find <Name>' for ERnn_* NPC points (Y-band + painted-tile gated),
  (b) small cyan dots for CHECK/HIT trigger points, (c) orange x spawn-pool
  marks with legend strip; draw_objectives(skip_q=...) suppresses the floor
  badge when an exact pin of that quest is on the same layer. All 69 maps
  re-rendered; INDEX rebuilt.
- **Coverage**: PIN-NPC 22 (exact xyz; incl. field fi00x quests!), EVENT-PIN 3,
  PLACED folded into PIN-NPC, NONE 23 unchanged.
- **2026-06-29 followup**: cyan demo-graph diamond pins REMOVED from renderer
  (user: redundant vs exact Points_Event pins). draw_event_positions now draws
  only: magenta exact NPC pins, curated overlays (orange ER43 bomb pin+notes),
  cyan CHECK/HIT dots, orange spawn x + legend. event_positions.json kept as
  data only. All 69 maps + INDEX re-rendered.
- **Spawn-mark off-map bug fixed**: canvas bg is OPAQUE (24,26,30,255) so the
  alpha>=60 'painted tile' test never rejected anything; marks could land in
  empty space (e.g. du004_0000_L2). Replaced with brightness test (skip if
  r,g,b all <70) + y-band tolerance <=5 world units for spawn points. All 69
  maps re-rendered 2026-06-29; VERIFIED du004_0000 L0-L3: every x on floor.

## Label redesign (2026-06-29) — DONE
- Corner badges replaced by a STRUCTURED LEGEND (draw_objectives): top-right
  translucent block, one bold line per request 'ERnn  <quest title>' with
  indented sub-marks: '◆ Find <Npc> — pinned/this floor' (magenta),
  'x <Enemy> xN - spawn points' (cyan), '● target in this dungeon' /
  'Find <req> — requester here' (blue); aion orders = plain gold lines.
- Pins carry SHORT tags beside the diamond: 'ER41 R.S.' (was long dialogue
  text). Trigger dots, boss rings, spawn-zone rects: NO labels (legend tells
  all). Static enemy dots keep the short red 'ERnn Name xN' under the dot.
- Glyph note: msyh has no U+2715 (renders tofu); use ASCII x in legend text.
- All 69 maps + INDEX re-rendered; verified du001_0010 & du003_0000.
- INDEX.md rewritten (map_index.py) to mirror the drawn legend:
  '`ERnn <request title> (◆ Find X — pinned; x Enemy xN - spawn points; ...)`'
  + gold aion lines. Area-level 'pinned' (renderer decides per-layer).

## TASKS J: BOMBS FOUND (user was right — they're on du004_0000) — DONE
- **Points_DevilSearch in MapAreaData_MapPlan (map_resident_data) carries
  FIXED Demon-Recon item points with labels.** My earlier MapPlan extract took
  only Points_SpawnEnemy/_Mob, and the old table scans only saw MapDevilSearch*
  *tables* — the labelled points are in the MAP PLAN. -> out/devilsearch_points.json
  (1020 pts, 102 areas; fixed=1 are the named ones).
- **ER43 bombs (時限爆弾), all fixed=1**: #1 (-27.5,0,-35.35) du004_0000 S-W room;
  #2 (10.0,0.4,56.75) du004_0000 N-E room; #3 (32.35,0,0.02) du004_0010 E edge.
  VERIFIED drawn as gold 'ER43 Time Bomb n' diamonds on the right floors.
- Other named fixed points now on maps (gold): Eliza's Brooch (du004_0000 L3),
  Key Items Tower A 1-3, Broken Pendant (du002_0020), Research Notes
  (du005_0010), Bright Soul (du101_0000), Bloody/Dirty Key, Psychology Test
  Book & Comedy Script (du004_0010), Fushimi Souvenir Shuriken (du004_0000 L3),
  Aion Order recon points, Personal gifts. Generic '_固定N' points: small gold
  dots, no labels. Label translation dict JPW in renderer.
- Bottom legend now just 'x marks: enemy spawn points' (no ER34 text, per user).
- event_overlays.json: dropped the old guessed bomb pin; note strip on
  du004_0000 states where all three bombs are.
- **Legend/map correlation pass (du004_0000 confusion)**: legend marks now
  color-match the map: brown 'x ... rolls from the brown x spawn marks', blue
  'somewhere here, no pin' / 'story target — this dungeon', gold '◆ <item> —
  gold pin on map' line per named Demon-Recon pin drawn on the floor. Bottom
  notes stack bottom-up (spawns / quest note / 'small gold dots: Demon-Recon
  sweep spots (dig for items)' / 'cyan dots: event trigger zones'). Generic
  _固定N devil-search points are small unlabeled gold dots (fixed: parens
  labels like '固定1(A棟1)' only matched generic on the FULL label, not core).
- **Layout pass (legend/side column)**: legend now drawn in its OWN column
  right of the map (canvas widened W+lw+34, bg same (24,26,30)); map never
  covered. draw_objectives RETURNS im (render re-reads W,H; title bar spans
  new width). Pin labels: 4 candidate sides (right/left/above/below), picks
  first collision-free and prefers DARK off-floor pixels; skips label if
  nowhere clean (pin stays). Spawn marks split by kind: enemy=brown x,
  mob=green x, with matching bottom notes.

## 2026-07-27 FINAL PASS: spawn colors per pack, universal label placement, docs
- Spawn x marks now colored PER ENCOUNTER PACK: Points_SpawnEnemy carries
  NormalEncountPackID; EncountTable+EnemyTable -> out/enc_names.json
  (extract_map_resident_data.py). Single-enemy packs get palette colors
  (green=Zhen on du001_0000 from packs 1181-85, brown=Ara Mitama...),
  multi-enemy generic packs = gray; roaming mobs green x (field maps).
  Legend enemy marks take the same color as their spawn x.
- ALL labels (portals, NPC/item pins, boss rings, dot labels, zone labels)
  now share ONE placer (place_label/tag_label + module _PLACED, cleared per
  render): right/left/above/below, avoid every existing label, prefer dark
  off-floor pixels, skip if nowhere clean. Portal icon footprints registered.
- ER43 bottom note strip REMOVED (event_overlays.json emptied) - bombs show
  as labelled gold x pins now.
- Full documentation written: docs/DATA.md (all findings, tools, spec, gaps).
- All 69 maps + INDEX regenerated.

## 2026-07-27 extra data decodes (from a broader commontable pass)
- SAVES: the game's save files are gzip -> PLAIN JSON (m_ItemData num/
  flag[1401], m_PartySaveData Money/CharData[CharId,Level]/NakamaStock,
  m_EventFlagData.flag[4096]). No encryption; edit = keep keys, re-gzip.
- Skill element codes (from skill names): 1=Fire 2=Ice 3=Electric 4=Force
  5=Physical 6=Gun 7=Curse 8=Almighty, -1=Support; ATTRNAME_* labels use a
  different (enemy-attribute) scheme.
- Enemy defence scale: 5=weak .. 4=neutral .. 0=absorb (verified vs Jack
  Frost). Drop id >=1000 = ItemManaTable id-1000, else ItemMat/ItemUse/
  ItemKey. Quest reward type 1 = Mana skill via SKILLNAME_COM_<id>.
- Spawn tables use 3xxx story-variant ids of 2xxx bestiary ids; roll
  "found in" up by enemy NAME.
