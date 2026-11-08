# Objective coverage on minimaps

Markers: PIN=world dot/rect (static gimmic), RING=boss ring (event_points), FLOOR=floor badge, DUNGEON=dungeon-wide badge, NPC-BADGE=find <npc> (requester), PLACED=registered on exact floor (EventListObjectAll), PIN-NPC=exact world xyz from map_resident_data Points_Event, EVENT-PIN=exact world coords from demo-graph StCharaSetPos, VIA-NPC=location-less target resolved via the quest NPC registration, NONE=no location data by design.

| id | objective | target | type | marker | location |
|---|---|---|---|---|---|
| ER51 | Glory Days | fi009_0000@[15.73, 0.1, -43.4] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER51 | Glory Days |  | 0 | NONE |  |
| ER26 | A New Hee-Home: Part 1 | NPC in du001 | - | NPC-BADGE | all floors |
| ER26 | A New Hee-Home: Part 1 | du001_0000@[-41.79, 0.0, -32.66] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER26 | A New Hee-Home: Part 1 | Tsuchigumo | 1 | PIN+FLOOR | du001 L0, du101 L0 |
| ER48 | That Which Lurks in Shadow | - | - | story-flag | - |
| ER37 | Mad Dog | - | - | story-flag | - |
| ER52 | Mistiqal Maiden | - | - | story-flag | - |
| ER34 | Many Birds, One Stone | Zhen | 1 | FLOOR | du001 L0 |
| ER47 | Academics Wanted (Yes, Again) | - | - | story-flag | - |
| ER93 | Unforgettable | - | - | story-flag | - |
| ER29 | A New Hee-Home: Part 4 | NPC in du004 | - | NPC-BADGE | all floors |
| ER29 | A New Hee-Home: Part 4 | du004_0000@[13.71, 0.0, -24.29] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER29 | A New Hee-Home: Part 4 | Orobas | 1 | FLOOR | du004 L1, du101 L3, du103 L2 |
| ER16 | The Gunsmith | Qing Long | 1 | FLOOR | du002 L0, du102 L0, du103 L0 |
| ER07 | Merch Search | du001_0000@[-20.42, 0.0, -14.36] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER07 | Merch Search |  | 0 | VIA-NPC | du001 L0 |
| ER03 | Dark Night Rises | event scene | event | EVENT-PIN | du005_0000 |
| ER38 | Lady on the Mind | - | - | story-flag | - |
| ER33 | Vengeance Claimed | du001_0000@[-65.39, 0.0, -8.47]; fi003_0000@[-0.46, 10.13, 58.17] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER33 | Vengeance Claimed |  | 0 | VIA-NPC | du001 L0 |
| ER22 | ...Scientist |  | 2 | NONE |  |
| ER04 | Does Aion Dream of Electric Sheep? | - | - | story-flag | - |
| ER11 | An Earring, A Memory, and Me | fi007_0000@[-2.99, 0.2, 29.58] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER11 | An Earring, A Memory, and Me |  | 0 | NONE |  |
| ER32 | The Wolf Who Cried Wolf Again | NPC in du001 | - | NPC-BADGE | all floors |
| ER32 | The Wolf Who Cried Wolf Again | du001_0010@[82.83, 0.0, 14.1]; du002_0000@[-20.21, 0.5, -3.15] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER19 | Mock the Invisible World |  | 2 | NONE |  |
| ER44 | Vanity, Calamity, Humanity | fi009_0000@[65.96, 0.1, -48.18] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER44 | Vanity, Calamity, Humanity |  | 0 | NONE |  |
| ER28 | A New Hee-Home: Part 3 | NPC in du003 | - | NPC-BADGE | all floors |
| ER28 | A New Hee-Home: Part 3 | du003_0000@[-10.44, -0.0, -30.68] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER28 | A New Hee-Home: Part 3 | Shiisaa | 1 | FLOOR | du003 L0, du101 L1, du102 L1, du103 L1 |
| ER08 | Raiders of the Lost Gift | du003_0000@[-39.88, 0.0, 54.9] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER08 | Raiders of the Lost Gift |  | 0 | VIA-NPC | du003 L0 |
| ER41 | Requiem for a G | NPC in du001 | - | NPC-BADGE | all floors |
| ER41 | Requiem for a G | du001_0010@[118.87, 0.0, -30.57] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER41 | Requiem for a G | Valkyrie | 1 | PIN+FLOOR | du001 L1 |
| ER35 | Night of the Living Snowman | event scene | event | EVENT-PIN | du004_0010 |
| ER36 | Curiosity Shopper |  | 0 | NONE |  |
| ER02 | Girl's Night Out | - | - | story-flag | - |
| ER15 | A Woman of Many Faces | - | - | story-flag | - |
| ER96 | Nana's Lonely Heart | - | - | story-flag | - |
| ER20 | Accursed Creator |  | 2 | NONE |  |
| ER12 | A Brooch, A Fresh Start, and Me | - | - | story-flag | - |
| ER17 | Master and Apprentice | Quetzalcoatl | 1 | PIN+FLOOR | du004 L0, du101 L3, du102 L2 |
| ER09 | Priceless Treasure | - | - | story-flag | - |
| ER23 | A Christmas Memory | - | - | story-flag | - |
| ER97 | A Homecoming | - | - | story-flag | - |
| ER01 | Phantom of the Night | - | - | story-flag | - |
| ER06 | Hopes, Dreams, and Aion | - | - | story-flag | - |
| ER43 | Fatal Countdown | du004_0000@[11.77, 0.0, 17.6]; fi009_0000@[63.01, 0.1, -43.78] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER43 | Fatal Countdown |  | 0 | VIA-NPC | du004 L0 |
| ER40 | Farewell, My Love | NPC in du004 | - | NPC-BADGE | all floors |
| ER40 | Farewell, My Love | du004_0020@[-14.85, 0.0, -7.15]; fi001_0000@[37.37, 9.49, -28.66]; fi003_0000@[9.48, 12.49 | npc | PIN-NPC | exact xyz (Points_Event) |
| ER50 | That Which Lies Ahead | - | - | story-flag | - |
| ER10 | A Necklace, A Movie, and Me | fi001_0000@[40.52, 9.49, -23.12] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER10 | A Necklace, A Movie, and Me |  | 0 | NONE |  |
| ER39 | The Little Sister | - | - | story-flag | - |
| ER18 | Light at the End of the Tunnel | Vritra | 1 | PIN+FLOOR | du001 L1, du007 L0, du101 L5, du102 L4, du103 L4 |
| ER46 | Academics Wanted (Again) | - | - | story-flag | - |
| ER82 | Hachigaya Hokudo Crackdown | NPC in du007 | - | NPC-BADGE | all floors |
| ER82 | Hachigaya Hokudo Crackdown | du007_0020@[-22.78, -360.0, 38.04] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER45 | Academics Wanted | - | - | story-flag | - |
| ER30 | A New Hee-Home: Part 5 | NPC in du005 | - | NPC-BADGE | all floors |
| ER30 | A New Hee-Home: Part 5 | du005_0000@[-43.11, -0.6, -65.43] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER30 | A New Hee-Home: Part 5 | Baihu | 1 | PIN+FLOOR | du005 L0, du005 L1, du007 L0, du101 L5, du102 L4, du103 L4 |
| ER91 | Rumors of a Summoner | - | - | story-flag | - |
| ER21 | Deepest Mysteries of Creation |  | 2 | NONE |  |
| ER25 | A Wintry Friend | - | - | story-flag | - |
| ER24 | The Heartbreaker | - | - | story-flag | - |
| ER05 | Story of Your Love | - | - | story-flag | - |
| ER14 | All's Fair in Love and Commerce | - | - | story-flag | - |
| ER42 | Close My Eyes and Think of You | NPC in du002 | - | NPC-BADGE | all floors |
| ER42 | Close My Eyes and Think of You | du002_0010@[36.3, 0.5, 74.96] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER42 | Close My Eyes and Think of You |  | 0 | VIA-NPC | du002 L1 |
| ER81 | Hachigaya Seido Crackdown | NPC in du007 | - | NPC-BADGE | all floors |
| ER81 | Hachigaya Seido Crackdown | du007_0010@[-94.98, 0.5, 38.63] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER49 | That Which Thirsts for Blood | event scene | event | EVENT-PIN | du004_0010 |
| ER94 | A Girl's Resolve | - | - | story-flag | - |
| ER27 | A New Hee-Home: Part 2 | NPC in du002 | - | NPC-BADGE | all floors |
| ER27 | A New Hee-Home: Part 2 | du002_0010@[-34.96, 1.0, -88.55] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER27 | A New Hee-Home: Part 2 | Zhu Tun She | 1 | FLOOR | du002 L1, du102 L0 |
| ER92 | Problem Child | NPC in du001 | - | NPC-BADGE | all floors |
| ER92 | Problem Child | du001_0000@[-31.29, 0.0, -41.06] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER95 | Last Stop | - | - | story-flag | - |
| ER31 | The Wolf Who Cried Wolf | NPC in du002 | - | NPC-BADGE | all floors |
| ER31 | The Wolf Who Cried Wolf | du002_0000@[-20.21, 0.5, -3.15]; du002_0010@[-41.26, -0.0, -45.48] | npc | PIN-NPC | exact xyz (Points_Event) |
| ER83 | Tribute and Worship | NPC in du007 | - | NPC-BADGE | all floors |
| ER83 | Tribute and Worship | du007_0000@[10.78, 0.0, -22.03]; du007_0020@[-19.23, -360.0, -19.23]; du007_0050@[-1.0, 0. | npc | PIN-NPC | exact xyz (Points_Event) |
| ER13 | Money Makes the World Go Round | - | - | story-flag | - |
| EA13 | Arrow Sector Cleanup 5 | Cerberus | 1 | PIN+FLOOR | du101 L5 |
| EA33 | Target: Halphas | Halphas | 2 | RING | du103 L0 |
| EA40 | Saizo Sector Cleanup 4 | Zhuque | 1 | FLOOR | du103 L3 |
| EA36 | Target: Muu Shuwuu | Muu Shuwuu | 2 | RING | du103 L1 |
| EA45 | Target: Jack Frost | Jack Frost | 2 | RING | du103 L4 |
| EA18 | Target: Nozuchi | Nozuchi | 2 | RING | du102 L0 |
| EA24 | Target: Quetzalcoatl | Quetzalcoatl | 2 | RING | du102 L2 |
| EA03 | Target: Mokoi | Mokoi | 2 | RING | du101 L0 |
| EA44 | Retrieve Orb Crystaloid Epsilon | キーアイテム085 | 0 | NONE | safehouse (no map) |
| EA28 | Milady Sector Cleanup 5 | Anubis | 1 | PIN+FLOOR | du102 L4 |
| EA08 | Retrieve Chain Crystaloid Gamma | Chain Crystaloid Delta | 0 | NONE | safehouse (no map) |
| EA42 | Target: Zenon | Zenon | 2 | RING | du103 L3 |
| EA25 | Milady Sector Cleanup 4 | Vouivre | 1 | FLOOR | du102 L3 |
| EA23 | Retrieve Needle Crystaloid Gamma | Needle Crystaloid Delta | 0 | NONE | safehouse (no map) |
| EA14 | Retrieve Chain Crystaloid Epsilon | Needle Crystaloid Alpha | 0 | NONE | safehouse (no map) |
| EA15 | Target: Raven | Raven | 2 | RING | du101 L5 |
| EA30 | Target: Skadi | Skadi | 2 | RING | du102 L4 |
| EA41 | Retrieve Orb Crystaloid Delta | Orb Crystaloid Epsilon | 0 | NONE | safehouse (no map) |
| EA19 | Milady Sector Cleanup 2 | Jack-o'-Lantern | 1 | FLOOR | du102 L1 |
| EA04 | Arrow Sector Cleanup 2 | Inugami | 1 | FLOOR | du101 L1 |
| EA39 | Target: Ippon-Datara | Ippon-Datara | 2 | RING | du103 L2 |
| EA07 | Arrow Sector Cleanup 3 | Nekomata | 1 | FLOOR | du101 L3 |
| EA16 | Milady Sector Cleanup 1 | Jack Frost | 1 | FLOOR | du102 L0 |
| EA11 | Retrieve Chain Crystaloid Delta | Chain Crystaloid Epsilon | 0 | NONE | safehouse (no map) |
| EA06 | Target: Inugami | Inugami | 2 | RING | du101 L1 |
| EA12 | Target: Succubus | Unicorn | 2 | RING | du101 L4 |
| EA27 | Target: B Hawaii Frost | B Hawaii Frost | 2 | RING | du102 L3 |
| EA20 | Retrieve Needle Crystaloid Beta | Needle Crystaloid Gamma | 0 | NONE | safehouse (no map) |
| EA17 | Retrieve Needle Crystaloid Alpha | Needle Crystaloid Beta | 0 | NONE | safehouse (no map) |
| EA29 | Retrieve Needle Crystaloid Epsilon | Orb Crystaloid Alpha | 0 | NONE | safehouse (no map) |
| EA37 | Saizo Sector Cleanup 3 | Lamia | 1 | FLOOR | du103 L2 |
| EA10 | Arrow Sector Cleanup 4 | Unicorn | 1 | FLOOR | du101 L4 |
| EA05 | Retrieve Chain Crystaloid Beta | Chain Crystaloid Gamma | 0 | NONE | safehouse (no map) |
| EA34 | Saizo Sector Cleanup 2 | Archangel | 1 | FLOOR | du103 L1 |
| EA02 | Retrieve Chain Crystaloid Alpha | Chain Crystaloid Beta | 0 | FLOOR | du101 L0 |
| EA35 | Retrieve Orb Crystaloid Beta | Orb Crystaloid Gamma | 0 | NONE | safehouse (no map) |
| EA22 | Milady Sector Cleanup 3 | Apsaras | 1 | FLOOR | du102 L2 |
| EA38 | Retrieve Orb Crystaloid Gamma | Orb Crystaloid Delta | 0 | NONE | safehouse (no map) |
| EA31 | Saizo Sector Cleanup 1 | Mad Gasser | 1 | FLOOR | du103 L0 |
| EA43 | Saizo Sector Cleanup 5 | Titania | 1 | PIN+FLOOR | du103 L4 |
| EA21 | Target: R.S. | R.S. | 2 | RING | du102 L1 |
| EA09 | Target: Unicorn | Unicorn | 2 | RING | du101 L3 |
| EA26 | Retrieve Needle Crystaloid Delta | Needle Crystaloid Epsilon | 0 | NONE | safehouse (no map) |
| EA32 | Retrieve Orb Crystaloid Alpha | Orb Crystaloid Beta | 0 | NONE | safehouse (no map) |
| EA01 | Arrow Sector Cleanup 1 | Gremlin | 1 | PIN+FLOOR | du101 L0 |

## Totals

- EVENT-PIN: 3
- FLOOR: 17
- NONE: 23
- NPC-BADGE: 14
- PIN+FLOOR: 9
- PIN-NPC: 22
- RING: 15
- VIA-NPC: 5
- story-flag: 28
