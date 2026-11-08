# Soul Hackers 2 — automap project: findings & method

*Organised summary of everything verified; `DEVELOPMENT-LOG.md` is the raw
chronological log. Every claim below was checked against real game data or
real code; anything not verified is marked UNVERIFIED.*

Goal: in-game-style minimaps for every dungeon floor, built ONLY from the
game's own data — auto-map tiles, exact world coordinates, quest/objective
data, dialogue mining. Canonical images: **`out/maps_v2/`** (69 PNGs +
`INDEX.md`); the pipeline lives in `tools/` (run scripts from the repo root;
regenerable caches under `tools/data/`).

## 1. Engine & data layout (verified)
- Unity/IL2CPP; `global-metadata.dat` v27 + 118 MB `GameAssembly.dll`.
- Bundles in `StreamingAssets/win/`: `mapnew/` (map scenes + data),
  `Interface/` (automap UI + tile textures), `Message/` (event dialogue),
  `Table/commontable` (all game tables).
- UnityPy quirks (this build): `env.objects` is a property; classify objects
  by `type(o.read()).__name__`; key by `o.path_id`; Transform has no `m_Name`.
- Raw byte scans don't work on these bundles (compressed) — always use typed
  parsing.

## 2. Decryption (VERIFIED)
`win/Message/**` and `win/Table/commontable` use a custom **AES-CTR-XOR**
scheme: `tools/sh2_decrypt.py` — password `lAZr7V4e`, salt
`"<filename>_bKo"`, SHA1-chained key, AES-ECB keystream.
`tools/decrypt_all.py` decrypts the whole tree (9042 files).
`_commontable.dec` uniquely retains the full IL2CPP class-metadata trailer, so
`dump_commontable.py` parses ALL 76 tables generically → `commontable.json`
(19 MB, regenerable, not committed).

## 3. Map geometry pipeline
- Auto-map tiles: `Interface/interface_mapnew_automap_<dun>` bundles hold
  256×256 BC7 tiles (`<dun>_<area>_<layer>_<i>_<j>`, pixel data in the CAB
  `.resS` stream, XOR-obfuscated — key = most common 16-byte tile prefix).
  `dump_automap.py` extracts them.
- Per-floor world→pixel transforms: fitted from the automap UI tree
  (`tools/data/dbg_ui_tree_*.json`, `dbg_ui2world_*.json`) and cached in
  `out/layer_info.json` + `out/dbg_layers_*.json`.
- Layer index→world-Y mapping is **per-area, never assumed**;
  `solve_layers_labelled.py` assigns layers from the game's own floor labels.
- Multi-stage fit (v3) + warp-position-constrained refit: 22/22
  cross-portal floors fit to ≤4 px mean error.
  Remaining UNVERIFIED: du004_0010 L0/L4 (two floors share one plane),
  du007_0020 sub-buildings B/C, portal name→icon pairing.

## 4. Portals
`MapPortalTable` (commontable) has EN names but LOCAL coords → labels are
anchored to the in-game minimap's own `_02` portal icons per layer
(`m_SubAreaID` picks the layer); destinations come from warp-label corridor
matching. Arrow glyphs only on warp-soul-verified interactables (warp-soul
data is the only interactability evidence; never arrows on plain doors).

## 5. Quest/objective intelligence
- `Message/ERnn_nnnn/_commontable.dec` — per-event scenario scripts.
- `QuestMainTable` — id, JP title, `requestNaiCondition` DSL:
  `AND(CheckTalk(ERnn), GetItem(id), EnemyDead(id,count))`.
- `QuestRequestNaiKindTable` type map: 1=enemy, 2=item, 3=chara,
  5/13/25/27/29=flags, 7/34/39=story, 31=map.
- `CharaNameTable` (CNAME_), `DevilVoiceLabelTable` (NAKAMA_/PARTY_),
  `ItemNameTable`, `AreaNameTable` (1000 = DU000_NONE) resolve ids→EN names.
- `commontable_digest.py` → `out/digest/` (quests.json incl. per-target
  `spawn_locs`, items, chars, nakama, skills, aion_orders, map_areas,
  coverage.md).
- `object_placements.py`: joins `EventListObjectAll` (runtime placement
  table) + `EventListAll` (area assignment; multi-area events replicate per
  area) + `demo/<EventID>.assets` graphs (`StGetItem` → exact x/z where an
  item is picked up; key offset: `Key_NNN` = item_id−1) + decrypted dialogue
  (hints). Renderer draws exact dots for single-place placed items, gold
  rings for multi-place, legend text for hinted/floor-level ones.
- Region isolation: `CheckTalk(ERnn)` restricts to the event's area;
  multi-dungeon hunts are resolved with `place|area` counts from
  AreaSpawnTable/EnemySpawnTable; `Place 1000 = overworld` excluded.

## 6. The placement containers (ground truth)
`win/mapnew/map_resident_data` — one bundle, 104 MonoBehaviours (scenes carry
only empty `MapEditorMonoPointManager` shells; the manager fills them from
this bundle at runtime, traced via `EventArrangeManager.Load → MapPoint_*`):
- **`MapAreaData_EventPlan '<area>_evplan'` → `Points_Event`**
  (type `MapPoint_Event`): Identifier, Label, **world Pos/Rotate**,
  ObjectType (0=trigger, 1=NPC), CharacterId, TriggerType (CHECK/HIT),
  MapAreaID. 43 areas / 403 points → `out/event_npc_points.json`.
  **This is where NPC and trigger locations live.**
- **`MapAreaData_MapPlan '<area>_mapplan'` → `Points_SpawnEnemy` /
  `Points_SpawnMob`** with **`NormalEncountPackID`** →
  `out/spawn_points.json` (+ `enc_names.json` joining EncountTable→EnemyTable
  names). 46 areas / 725 points. Single-enemy packs (e.g. **Zhen** = packs
  1181–1185 on du001_0000) get a dedicated x color; multi-enemy generic packs
  share gray.
- **`Points_DevilSearch`** (type `MapPoint_DevilSearch`): **labelled item
  points**, 102 areas / 1020 points → `out/devilsearch_points.json`.
  `IsFixed=1` with a named label = quest item; `_固定N` = generic sweep spot.
  **The ER43 time bombs were here all along**: 時限爆弾1 (−27.5,0,−35.35) and
  時限爆弾2 (10.0,0.4,56.75) on **du004_0000**, 時限爆弾3 (32.35,0,0.02) on
  du004_0010 — all in Tower A (the "Tower B" dialogue was a red herring).
  Also named: Eliza's Brooch, Key Items (ER05), Broken Pendant, Research
  Notes, Bright Soul, Bloody/Dirty Key, Psychology Test Book, Comedy Script.
- Tool: `extract_map_resident_data.py` (rewrites those four JSONs).
- Static `Gimmic_SpawnEnemy` scene objects (7 floors) + BossModel positions
  (`tools/data/event_points.json`) → `out/enemy_spawns.json`: red dots /
  red rings.

## 7. Enemy locations
- **Spawn-based quests CAN be coordinate-pinned**: Points_SpawnEnemy + pack
  id + EncountTable = which points roll which enemy. ER34's 20 Zhen: 5
  purple x on du001_0000.
- Demon Recon (`MapDevilSearch*DataArray`) remains floor-level by design
  EXCEPT the labelled fixed Points_DevilSearch above.
- Coverage across 111 quests (`coverage_report.py` →
  `out/digest/coverage.md`): **PIN-NPC 22 · EVENT-PIN 3 · PLACED 18 ·
  FLOOR 17 · RING 15 · NPC-BADGE 14 · VIA-NPC 5** = 76/111 located; NONE 23
  (no coordinates exist by design: menus, item delivery, post-battle,
  overworld) + 28 story-flags = 51 no-map rows.

## 8. Rendering spec (`build_minimap_layers.py`)
**Map symbols** (color ↔ meaning is 1:1 with legend text color):
- magenta diamond + pill label = NPC/interactable pin (Points_Event);
- cyan dot = event trigger (CHECK/HIT);
- gold diamond + label = named Demon-Recon item (JP labels auto-translated);
- small gold dot = generic recon sweep spot;
- x marks = enemy spawn points, **colored per encounter pack**: single-enemy
  packs palette-colored (e.g. green=Zhen, brown=Ara Mitama), gray=mixed
  packs, green x = roaming-mob points; red dot = static enemy; red ring =
  boss arena;
- gold ring = multi-place placed item; orange dot = exact pickup point;
- purple text = portal destinations; magenta box = quest-region label.

**Labels**: every text label goes through `place_label()`: tries
right/left/above/below, avoids ALL previously placed labels, prefers dark
off-map ground, and is skipped if nowhere is clean.

**Legend**: its own column to the RIGHT of the map (canvas widened; map
never covered). Bold white `ERnn quest title` lines; sub-marks colored
exactly like their map symbol.

**Gate rules**: marks drawn only on painted floor (brightness test — the
canvas bg is opaque, alpha tests are useless) and (spawns) within 5 world-Y
of the layer's floor band.

## 9. Additional decodes (from the data-mining pass)
- **Save format**: the game's save files are **gzip → plain JSON** (items as
  per-index num/flag[1401] arrays, party CharId/Level, Money, demon stock,
  4096 event flags). No encryption.
- **Skill element codes** come from skill names: 1=Fire 2=Ice 3=Electric
  4=Force 5=Physical 6=Gun 7=Curse 8=Almighty, −1=Support. (`ATTRNAME_*`
  labels use a DIFFERENT scheme — enemy attributes.)
- **Enemy defence scale**: 5=weak … 4=neutral … 0=absorb (verified vs
  Jack Frost).
- **Drop ids ≥ 1000** = ItemManaTable id−1000 (a skill); else ItemMat →
  ItemUse → ItemKey.
- **Quest reward type 1** = Mana skill (via `SKILLNAME_COM_<id>`), not an
  item.
- Spawn tables reference **story-variant enemy ids** (3xxx) of bestiary ids
  (2xxx) — roll "found in" up by NAME.

## 10. Known gaps / UNVERIFIED
- du004_0010 L0/L4 share one auto-map plane; du007_0020 sub-building B/C
  mix; portal name↔icon pairing (order-based) — all need in-game
  confirmation.
- Event trigger points fire at range (TriggerDistance up to 10) — dot =
  trigger location, not interaction point.
- Field-area (`fi*`) minimaps not rendered: no auto-map tiles exist for them.
- 23 NONE + 28 story-flag quests have no map position by design.
- 8 demo assets (`ERxx_001_C` pattern) fail to parse.

## 11. Reproduce
```bash
python tools/dump_automap.py du004                     # tiles -> tools/data/
python tools/build_minimap_layers.py du004 0000 out/maps_v2/du004_0000_L0.png
python tools/build_minimap_layers.py du004 0000 out/maps_v2/du004_0000_L0.png --all
# full set: loop tools/data/dbg_all_combos.txt (dun area per line),
# --all for every floor, then map_index.py -> INDEX.md
```
