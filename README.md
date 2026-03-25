# Computer Bild Spiele Game List

This repo contains the extraction pipeline and the current best public CSV list of
game titles found on `Computer Bild Spiele` cover discs from the `cbs-2000-09`
Internet Archive set.

This is an unofficial research dataset. `Computer Bild Spiele`, game titles, and
other product names mentioned here may be trademarks of their respective owners.
No affiliation with, endorsement by, or sponsorship from any publisher, rights
holder, or archive source is implied.

What is in the repo:

- `scripts/index_cbs_exes.py`: the main collector for title and executable indexing
- `scripts/prepare_publishable_results.py`: cleanup step that produces the public CSVs
- `scripts/enrich_reference_links.py`: shared Wikimedia matching/cache layer
- `scripts/build_enriched_release.py`: canonical entity and metadata enrichment step
- `results/published-20260324/publishable_master_games.csv`: one row per normalized title
- `results/published-20260324/publishable_issue_titles.csv`: issue-to-title mapping
- `results/published-20260324/final_unresolved_issues.csv`: issues still needing follow-up
- `PUBLIC-RELEASE-AUDIT.md`: notes on the public-repo shape and exclusions

Current published snapshot:

- master titles: `1407`
- issue/title rows: `1718`
- unresolved issues: `35`

The tracked CSVs are a best-effort public dataset, not a claim of perfect completeness.
The unresolved list is the remaining retry queue.

## Licensing

- code in this repo is licensed under the MIT License: `LICENSE`
- dataset and documentation files are licensed under CC BY 4.0: `LICENSE-DATA.md`

## Pipeline

The pipeline is intentionally layered:

1. raw extraction from cover-disc archives
2. cleaned publishable title outputs
3. canonical entity matching
4. metadata enrichment
5. public enriched release outputs

The key design rule is that enrichment is separate from extraction. Raw titles and
publishable titles keep their original meaning; canonical URLs, genres, categories,
and ratings are added in a later step with explicit provenance and confidence.

## Enrichment

The enrichment layer writes new outputs under a dated `results/enriched-*`
directory instead of changing the meaning of the current publishable CSVs.

Main inputs:

- `results/published-20260324/publishable_master_games.csv`
- `results/published-20260324/publishable_issue_titles.csv`

Tracked manual inputs:

- `data/manual_alias_overrides.csv`
- `data/manual_entity_overrides.csv`
- `data/manual_url_overrides.csv`
- `data/manual_rejections.csv`

Main outputs:

- `enriched_master_games.csv`
- `enriched_issue_titles.csv`
- `title_aliases.csv`
- `ambiguous_matches.csv`
- `unmatched_titles.csv`
- `source_attribution.csv`

Local-only artifacts:

- `results/enrichment.sqlite`
- `results/reference_review.csv`

`match_status` is one of `matched`, `ambiguous`, or `unmatched`.
`match_confidence` and the metadata/rating confidence fields are intentionally
conservative. A blank field is preferred over a weak guess.

Ratings are source-labeled and intentionally sparse. Categories and genres come
primarily from Wikidata, with optional best-effort public-page enrichment where
available.

## Commands

Generate the current publishable outputs:

```bash
python3 scripts/prepare_publishable_results.py \
  --input-dir results/vps-linux-full-20260324 \
  --output-dir results/published-20260324
```

Build the enriched release:

```bash
python3 scripts/build_enriched_release.py
```

Useful enrichment flags:

```bash
python3 scripts/build_enriched_release.py \
  --output-dir results/enriched-20260324 \
  --cache-db results/enrichment.sqlite \
  --resume
```

## Full Table

This appendix mirrors `results/published-20260324/publishable_master_games.csv` in a simplified form.

<details>
<summary>Show simplified full title table (1407 rows)</summary>

| Title | First Issue | Issue Count |
| --- | --- | ---: |
| 007 Ein Quantum Trost | CBS022009DVDGold | 1 |
| 18 Wheels of Steel Haulin | CBS042008DVD | 1 |
| 18 Wheelsof Steel Haulin | CBS042008DVD | 1 |
| 187 Ride or Die | CBS082005DVD | 1 |
| 1944 Winterschlacht in den Ardennen | CBS072005DVD | 1 |
| 4 Story | CBS072009DVD | 1 |
| 442 Fussball Manager | CBS112005DVD | 1 |
| A Vampyre Story | CBS022009DVD | 1 |
| Abdurchdie Hecke | CBS082006DVD | 1 |
| Absolute Blue | CBS082005DVD | 1 |
| Achtung Roboter | CBS082005DVD | 1 |
| Act of War Direct Action | CBS032005DVD | 2 |
| Act of War High Treason | CBS042006DVD | 1 |
| Actua Soccer 2 | CBS092000 | 1 |
| Actua Soccer Featuring Oliver Bierhoff | CBS062006DVD | 1 |
| Adash - Stadt der Magie - Kapitel 11 | CBS112008DVD | 1 |
| Adrenalin Extreme Show | CBS062006DVD | 1 |
| Afrika Corps vs | CBS042005DVD | 1 |
| Agatha Christie | CBS032006DVD | 1 |
| Agatha Christie Das Bseunterder Sonne | CBS042008DVD | 1 |
| Agatha Christie Mordim Orient Express | CBS032007DVDGold | 1 |
| Agatha Christie Unddanngabskeinesmehrv | CBS052006DVD | 1 |
| Age of Conan | CBS032006DVD | 1 |
| Age of Empires 3 v 1 | CBS042006DVD | 1 |
| Age of Empires 3 v 1 01a | CBS022006DVD | 1 |
| Age of Empires Gold Edition | CBS082004 | 1 |
| Age of Mythology | CBS012009DVDGold | 1 |
| Ageof Empires Ageof Discoveryv | CBS072006DVD | 1 |
| Ageof Empires The War Chiefs | CBS012007DVDGOLD | 1 |
| Ageof Empiresv | CBS052006DVD | 3 |
| Ages of Empires 3 | CBS112005DVD | 1 |
| Agon The Lost Sword of Toledo | CBS052008DVD | 1 |
| Agon The Lost Swordof Toledo | CBS052008DVD | 1 |
| Air Conflicts | CBS062006DVD | 1 |
| Air Strike 3 D 2 | CBS092005DVD | 1 |
| Airlines Tycoon Deluxe | CBS122004DVD | 1 |
| Al Emmoandthe Lost Dutchmans Mine | CBS112006DVD | 1 |
| Alan Wake | CBS082006DVD | 1 |
| Alarmfr Cobra Nitro | CBS012007DVD | 1 |
| Alarmfr Cobra11 Crash Timev111 | CBS022008DVD | 1 |
| Alexander | CBS022005DVD | 1 |
| Alexander Die Stunde der Helden | CBS052008DVD | 1 |
| Alexander Die Stundeder Helden | CBS052008DVD | 1 |
| Alien Arena | CBS062008DVDGold | 1 |
| Alien Shooter | CBS092006DVD | 1 |
| Aliens Pinball | CBS102006DVD | 1 |
| All Star Strip Poker | CBS092006DVD | 1 |
| Alone in the Dark Komplettlösung | CBS092008DVD | 1 |
| Aloneinthe Dark | CBS082006DVD | 1 |
| Aloneinthe Dark Komplettlsung | CBS092008DVD | 1 |
| Alternate Flip | CBS012005DVD | 1 |
| America | CBS082003 | 1 |
| American Conquest Fight Back | CBS102006DVD | 1 |
| Andersens Maedchen | CBS102005DVD | 1 |
| Angel Knig Spinnfischenin Deutschland | CBS022008DVD | 1 |
| Angriff auf die Westfront | CBS092005DVD | 1 |
| Ankh Herz des Osiris v 1 | CBS032008DVD | 1 |
| Ankh Herzdes Osiris | CBS012007DVD | 1 |
| Ankh Kampfder Gtter | CBS022008DVDGold | 1 |
| Anno 1602 | CBS072003 | 1 |
| Ansto Edition | CBS072006DVD | 1 |
| Anstoss 3 | CBS112003 | 1 |
| Anstoss Action | CBS122003 (CD1) | 2 |
| Anstoss Edition | CBS072006DVD | 2 |
| Anstov | CBS112006DVD | 1 |
| Anstov Zwei | CBS112006DVD | 1 |
| Anti Twin | CBS042008DVD | 1 |
| Antira, Mexiko | CBS012005DVD | 1 |
| Aquanox 2 | CBS092004DVD | 1 |
| Arena Wars | CBS112004DVD | 2 |
| Arena Wars v 1 1 | CBS012005DVD | 1 |
| arma 2 | CBS102009DVDGold | 1 |
| Armagetron Advanced | CBS072009DVD | 1 |
| Armed Assault | CBS032007DVDGold | 1 |
| Armies of Exigo | CBS112004DVD | 2 |
| Armiesof Exigo | CBS122008DVD | 1 |
| armor digit | CBS012005DVD | 1 |
| Armour of God 2 | CBS032008DVD | 1 |
| Armourof God2 | CBS032008DVD | 1 |
| Asghan | CBS012001 | 1 |
| Ashampoo Firewall | CBS052008DVD | 1 |
| Ashampoo Magical | CBS042008DVD | 1 |
| Ashampoo Power Up XPPlatinum2 | CBS042008DVD | 1 |
| Ashampoo Win Optimizer 4 | CBS042008DVD | 1 |
| Ashampoo Win Optimizer4 | CBS042008DVD | 1 |
| Assassins Creed | CBS082006DVD | 2 |
| Assassins Creed Spieltricks | CBS052008DVD | 1 |
| Assault Heroes | CBS062008DVD | 1 |
| Asterix Obelix XXL 2 | CBS032006DVD | 1 |
| Athletics | CBS092001 | 1 |
| Atlantis Evolution | CBS012005DVD | 1 |
| Augustus | CBS012006DVD | 1 |
| Aura Dieheiligen Ringe | CBS102006DVD | 1 |
| Aura Tor zur Ewigkeit | CBS112004DVD | 1 |
| Aura Tor zur Ewigkeit v 1 | CBS032005DVD | 1 |
| Aurora Watching | CBS072005DVD | 1 |
| Auto Cross Racing | CBS062008DVD | 1 |
| Autobahn Raser 2 | CBS042002 | 1 |
| Autobahn Raser 4 | CBS032004 (CD1) | 2 |
| Autobahn Raser Das Spiel | CBS052005DVD | 1 |
| Autobahn Raser Spiel zum Film | CBS052005DVD | 1 |
| Autobahn Raser W | CBS082005DVD | 1 |
| Autobahnraser 3 | CBS122002 | 1 |
| Aw Nuts | CBS092005DVD | 1 |
| Axe Snake Peel | CBS072005DVD | 1 |
| Azteca | CBS122008DVD | 1 |
| Backgammon XXL | CBS072006DVD | 1 |
| Bagger Simulator | CBS102008DVD | 1 |
| Baldur's Gate | CBS122008DVD | 1 |
| Baldur's Gate - Compilation | CBS122008DVDGold | 1 |
| Baldur's Gate 2 - Schatten von Amn | CBS122008DVDGold | 1 |
| Baldur's Gate 2 - Thron des Bhaal | CBS122008DVDGold | 1 |
| Baldur's Gate Legenden der Schwertküste | CBS122008DVD | 1 |
| Baldurs Gate | CBS122008DVD | 1 |
| Baldurs Gate Legendender Schwertkste | CBS122008DVD | 1 |
| Ballerburg | CBS032004 (CD1) | 2 |
| Bang! Gunship Elite | CBS122001 | 1 |
| Baphotmets Fluch Der Engeldes Todes | CBS102006DVD | 1 |
| Battle Lord | CBS092006DVD | 1 |
| Battle Mages | CBS092005DVD | 1 |
| Battle Realms | CBS042004 | 1 |
| Battlecruiser Millenium | CBS092005DVD | 1 |
| Battlefield | CBS072006DVD | 3 |
| Battlefield 2 | CBS022005DVD | 3 |
| Battlefield 2 Special Forces | CBS022006DVD | 1 |
| Battlefield 2 v 1 | CBS112005DVD | 1 |
| Battlefield 2 v 1 12 | CBS022006DVD | 1 |
| Battlefield 2142 v 1 | CBS092008DVD | 1 |
| Battlefield Toolkit | CBS092006DVDGOLD | 1 |
| Battlefield Vietnam | CBS112004DVD | 1 |
| Battlefield Vietnam v 1 | CBS032005DVD | 1 |
| Battlefield2142v150 | CBS092008DVD | 1 |
| Battlefieldv | CBS072006DVD | 3 |
| Battlestation Pacific | CBS072009DVDGold | 1 |
| Beach King Stunt Raser | CBS032005DVD | 1 |
| Biathlon 2006 | CBS022006DVD | 1 |
| Big Pizza Ski Challenge 09 Deutschland Edition | CBS022009DVD | 1 |
| Bike Flyter | CBS092001 | 1 |
| Bit Defender Free10 | CBS052008DVD | 1 |
| Black and White 2 | CBS082005DVD | 1 |
| Black Mirror Derdunkle Spiegelder Seele | CBS062006DVD | 1 |
| Black White | CBS062006DVD | 1 |
| Blazing Angels Squadrons Of WWv | CBS072006DVD | 1 |
| Blazing Angels Squadronsof WW | CBS062006DVD | 1 |
| Blazing Angels Squadronsof WWv | CBS092006DVD | 1 |
| Blitzkrieg 2 | CBS122005DVD | 1 |
| Blitzkrieg 2 v | CBS032006DVD | 1 |
| Blitzkrieg 2 v 1 | CBS012006DVD | 1 |
| Blitzkrieg Rolling Thunder | CBS042005DVD | 1 |
| Blitzkriegv | CBS082006DVD | 1 |
| Bloodmoon | CBS092008DVDGold | 1 |
| Boiling Point | CBS092005DVD | 1 |
| Boiling Point Road to Hell | CBS072005DVD | 1 |
| Boiling Point Roadto Hell | CBS032007DVDGold | 1 |
| Bomberman Act Zero | CBS112006DVD | 1 |
| Bookof Unwritten Tales | CBS072009DVDGold | 1 |
| Bounci | CBS022006DVD | 1 |
| Bounci x Dream | CBS042006DVD | 1 |
| Breakball | CBS082006DVD | 1 |
| Breed | CBS052006DVD | 1 |
| Bricks from above | CBS112008DVD | 1 |
| Bridge Builder | CBS032005DVD | 1 |
| Brothersin Arms Earnedin Bloodv | CBS072006DVD | 1 |
| Bruno Das Spiel | CBS102006DVD | 1 |
| Burn In Test XPVista Version | CBS092008DVD | 1 |
| Burnout Revenge | CBS112005DVD | 1 |
| Caesar | CBS102006DVDGOLD | 2 |
| Call of Duty 4 - Modern Warfare | CBS112008DVD | 1 |
| Callof Duty4 Modern Warfarev16 | CBS092008DVD | 1 |
| Callof Dutyv | CBS072006DVD | 2 |
| camera lock ax | CBS012005DVD | 1 |
| Captain Delta und die Quelle von Argos | CBS042008DVD | 1 |
| Captain Deltaunddie Quellevon Argos | CBS042008DVD | 1 |
| Cars Autoswiewir | CBS092006DVD | 1 |
| Castle Fight | CBS112009DVDGold | 1 |
| Castle Strike | CBS062006DVD | 1 |
| Castrol Honda Super Bike | CBS072000 | 1 |
| Catch 'em | CBS042008DVD | 1 |
| Catchem | CBS042008DVD | 1 |
| CBSSpezial | CBS112008DVD | 1 |
| Ccleaner | CBS032008DVD | 1 |
| Championsheep Rally | CBS082006DVD | 1 |
| Chaos League Sudden Death | CBS092005DVD | 1 |
| Chaos League Sudden Death v 2 | CBS042006DVD | 1 |
| CHAT ROOM | CBS012005DVD | 1 |
| Chicken Shoot | CBS022005DVD | 1 |
| Chicken Shoot 2 | CBS072005DVD | 1 |
| Children of the Nile | CBS122004DVD | 1 |
| Chk Alternate flip | CBS012005DVD | 1 |
| Chk Linseneffekte | CBS012005DVD | 1 |
| Chk Partikel | CBS012005DVD | 1 |
| Chk Pixelzentrierung | CBS012005DVD | 1 |
| Chk Schatten | CBS012005DVD | 1 |
| Chk Texturen | CBS012005DVD | 1 |
| Chk Tooltips | CBS012005DVD | 1 |
| Christmas Bound | CBS012005DVD | 1 |
| Chrome Specforce | CBS052008DVDGold | 1 |
| Chromehounds | CBS092006DVD | 2 |
| cities online | CBS102009DVD | 1 |
| City Life | CBS032006DVD | 4 |
| City of Villains | CBS012006DVD | 1 |
| Civilization 4 | CBS022006DVD | 1 |
| Civilization 4 Beyond the Sword v 3 | CBS092008DVD | 1 |
| Civilization 4 v | CBS032006DVD | 1 |
| Civilization4 Beyondthe Swordv317 | CBS092008DVD | 1 |
| Civilizationv | CBS072006DVD | 1 |
| Clever | CBS022009DVD | 1 |
| Click Clack XL | CBS092006DVD | 1 |
| Clonk Planet | CBS112005DVD | 1 |
| Club Football 2005 | CBS122004DVD | 1 |
| Clusterball | CBS012001 | 1 |
| Cobian Backup | CBS012009DVD | 1 |
| Code Aktionen | CBS112009DVDGold | 1 |
| Codeaktionen | CBS112009DVD | 1 |
| Codename Panzers | CBS122004DVD | 1 |
| Codename Panzers 2 v 1 | CBS122005DVD | 1 |
| Codename Panzers Ph | CBS082005DVD | 1 |
| Codename Panzers Phase 2 | CBS102005DVD | 1 |
| Codename Panzers Phase 2 v 1 | CBS032008DVD | 1 |
| Codename Panzers Phase2v108 | CBS032008DVD | 1 |
| Codename Panzers v 1 06 | CBS022006DVD | 1 |
| Cold Blood | CBS052005DVD | 1 |
| Cold War | CBS012006DVD | 1 |
| Cold War Crisis 1 | CBS112008DVD | 1 |
| Cold Zero The Last Stand | CBS012005DVD | 1 |
| Colin Mc Rae Rally 2005 | CBS112004DVD | 1 |
| Combat Flight Simulator | CBS032005DVD | 1 |
| Combat Wings Battleof Britain | CBS012007DVD | 1 |
| Command & Conquer - Alarmstufe Rot 3 v 1 | CBS022009DVD | 1 |
| Command & Conquer Alarmstufe Rot 3 | CBS022009DVDGold | 1 |
| Command and Conquer | CBS102008DVD | 1 |
| Command Conquer Dieersten Jahrev | CBS062006DVD | 1 |
| Command Conquer Tiberium Wars | CBS082006DVD | 1 |
| Commandand Conquer | CBS102008DVD | 1 |
| Commandos Hinter feindlichen Linien | CBS082002 | 1 |
| Commandos Strike Force | CBS052006DVD | 1 |
| Comodo Backup | CBS012009DVD | 1 |
| Companyof Heroes | CBS122006DVD | 1 |
| Companyof Heroesv | CBS012007DVD | 1 |
| Conflict Desert Storm | CBS112005DVD | 1 |
| Conflict Global Storm | CBS062006DVD | 1 |
| Coogles | CBS022005DVD | 1 |
| Cossacks 2 | CBS082005DVD | 1 |
| Cossacks 2 Napoleonic Wars | CBS052005DVD | 1 |
| Cossacks 2 v 1 | CBS082005DVD | 1 |
| Cossacks Back to War | CBS022005DVD | 1 |
| Cossacks Battlefor Europe | CBS072006DVD | 1 |
| Cossacks Battlefor Europev | CBS092006DVD | 1 |
| Cossacks European Wars | CBS012004 | 1 |
| CPUCool | CBS122008DVD | 1 |
| Crashday | CBS122004DVD | 3 |
| Crazy Kickers XS | CBS022005DVD | 1 |
| Crazy Machines | CBS122004DVD | 2 |
| Crazy Symbol Sudoku | CBS062006DVD | 1 |
| Creative Sound Blaster Audigy Serie v 2 12 | CBS032008DVD | 1 |
| Creature Conflict | CBS122005DVD | 1 |
| Crillion | CBS042005DVD | 1 |
| Cross Racing Championship | CBS042005DVD | 2 |
| Crysis Mod SDK 1 | CBS052008DVD | 2 |
| Crysis Mod SDK10 | CBS052008DVD | 1 |
| Crysis Mod SDK12 | CBS062008DVD | 1 |
| Crysis v 1 | CBS042008DVD | 1 |
| Crysisv11 | CBS042008DVD | 1 |
| CSI Eindeutige Beweise | CBS052008DVD | 1 |
| CSICrime Scene Investigation Mordin Dimensionen | CBS072006DVD | 1 |
| CSIEindeutige Beweise | CBS052008DVD | 1 |
| CYCEK NAD NEW GAME | CBS012005DVD | 1 |
| Daemonica | CBS082006DVD | 1 |
| Dame XXL | CBS062006DVD | 1 |
| Dark Age of Camelot | CBS052005DVD | 2 |
| Dark Age of Camelot + Shrouded Isles | CBS092005DVD | 1 |
| Dark Horizon | CBS012009DVD | 1 |
| Dark Project Der Meisterdieb | CBS012002 | 1 |
| Dark Quiz | CBS022005DVD | 1 |
| Darkstar One | CBS062006DVD | 2 |
| Darkstar Onev | CBS112006DVD | 1 |
| Das Ausbildungscamp | CBS012005DVD | 1 |
| Das Bergwerk | CBS012005DVD | 1 |
| Das chinesische Viertel | CBS012005DVD | 1 |
| Das Eulemberg Experiment | CBS112006DVD | 1 |
| Das Geheimlabor | CBS012005DVD | 1 |
| Das Geheimnis der vergessenen Höhle | CBS092005DVD | 1 |
| Das haessliche Entlein | CBS082005DVD | 1 |
| Das Hafenviertel | CBS012005DVD | 1 |
| Das Schwarze Auge - Drakensang | CBS112008DVDGold | 2 |
| Das Vermächtnis - Testament of Sin | CBS022009DVD | 1 |
| Dead or Alive 4 | CBS122005DVD | 1 |
| Dead Reefs | CBS092006DVD | 1 |
| Deador Alive | CBS082006DVD | 1 |
| deepolis online | CBS072009DVD | 1 |
| Delta Force Xtreme | CBS092005DVD | 1 |
| Demo Shield Launch | CBS112005DVD | 2 |
| demo spreng | CBS112009DVD | 1 |
| Der Bauernhof | CBS122008DVDGold | 1 |
| Der Bunker | CBS012005DVD | 1 |
| Der Fluch der Zwerge 1 | CBS112008DVD | 1 |
| Der Fluch des Goldes XS | CBS032005DVD | 1 |
| Der Herr der Ringe | CBS032006DVD | 1 |
| Der Herr der Ringe Die Schlacht um Mittelerde 2 | CBS042006DVD | 1 |
| Der Herrder Ringe Die Schlachtum Mittelerde | CBS052006DVD | 1 |
| Der Herrder Ringe Die Schlachtum Mittelerdev | CBS062006DVD | 2 |
| Der Herrder Ringe Online | CBS082006DVD | 1 |
| Der Hobbit v 1 | CBS012005DVD | 1 |
| Der Industriegigant | CBS072001 | 1 |
| Der Pate | CBS052005DVD | 2 |
| Der Trakt | CBS012005DVD | 1 |
| Der Verkehrsgigant Gold | CBS092002 | 1 |
| Der Wohnwagen | CBS012005DVD | 1 |
| Desperados Coopers Revenge | CBS072006DVD | 1 |
| Desperados Coopers Revengev | CBS092006DVD | 1 |
| Destroy All Humans | CBS102006DVD | 1 |
| Devil Kings | CBS022006DVD | 1 |
| Devil May Cry 3 | CBS032005DVD | 1 |
| Devil May Cry4 | CBS092008DVDGold | 1 |
| Diablo Spezial | CBS092008DVDGold | 1 |
| Diablo3 Spezial | CBS092008DVDGold | 1 |
| Diamantenfee | CBS012009DVD | 1 |
| Diamantenfee 2 | CBS072009DVD | 1 |
| Die Chroniken von Narnia | CBS112005DVD | 2 |
| Die drei Musketiere | CBS022006DVD | 1 |
| Die Fischverladestelle | CBS012005DVD | 1 |
| Die Gilde | CBS112006DVD | 2 |
| Die Gilde 2 | CBS112005DVD | 1 |
| Die Hazienda | CBS012005DVD | 1 |
| Die Kieselsteiner | CBS072006DVD | 1 |
| Die Kunst des Mordens Geheimakte FBI | CBS042008DVD | 1 |
| Die Kunstdes Mordens Geheimakte FBI | CBS042008DVD | 2 |
| Die Legenden und Märchen von Ash'kale 1 | CBS112008DVD | 1 |
| Die Lemuren | CBS102008DVD | 1 |
| Die Metrostation | CBS012005DVD | 1 |
| Die Rache der Sith | CBS022005DVD | 1 |
| Die Rmer | CBS092006DVD | 1 |
| Die Schalendes Zorns | CBS102006DVD | 1 |
| Die Schlacht um Mittelerde | CBS032005DVD | 1 |
| Die Schlacht um Mittelerde 2 | CBS112005DVD | 1 |
| Die Siedler | CBS122004DVD | 3 |
| Die Siedler 4 | CBS012005DVD | 1 |
| Die Siedler Aufbruch der Kulturen | CBS012009DVDSonder | 1 |
| Die Siedler Das Erbe der Könige | CBS102008DVDGold | 1 |
| Die Siedler Dienchste Generation | CBS092006DVD | 1 |
| Die Siedler Dienchste Generationv | CBS012007DVD | 1 |
| Die Siedler Hiebe für Diebe | CBS012001 | 1 |
| Die Siedler6 Aufstiegeines Knigreichsv15 | CBS062008DVD | 1 |
| Die Sims 2 Open for Business | CBS042006DVD | 1 |
| Die Sims 2 v | CBS032006DVD | 1 |
| Die Sims 2 v 1 0 0 | CBS032005DVD | 2 |
| Die Sims 2 v 1 000 | CBS042005DVD | 1 |
| Die Sims 2 Wilde Campus J | CBS042005DVD | 1 |
| Die Sims Haustiere | CBS102006DVD | 1 |
| Die Sims Nightlifev | CBS052006DVD | 1 |
| Die Sims Openfor Businessv | CBS062006DVD | 1 |
| Die Spedition | CBS012005DVD | 1 |
| Die Unglaublichen | CBS022005DVD | 1 |
| Die Völker | CBS052001 | 1 |
| Dikowsk, Rußland | CBS012005DVD | 1 |
| Dino Island | CBS122004DVD | 1 |
| Dirty Split | CBS102008DVD | 1 |
| Disk Defrag | CBS032008DVD | 1 |
| Diverse Hintergrnde | CBS082006DVD | 1 |
| Divine Divinity | CBS102005DVD | 1 |
| Divx 5 | CBS112004DVD | 2 |
| Divx 5 2 | CBS012005DVD | 11 |
| Divx 5 2 1 | CBS032006DVD | 1 |
| Divx 6 Play | CBS092005DVD | 2 |
| Divx 6 Play (XP) | CBS102005DVD | 6 |
| Divx ME | CBS052006DVD | 9 |
| Divx Play XP | CBS052006DVD | 8 |
| Dont Angry 2 | CBS012006DVD | 1 |
| Doom 3 Z Hunter 1 | CBS112008DVD | 1 |
| Double Crossfire | CBS062005DVD | 1 |
| Dove | CBS052001 | 1 |
| Doxan | CBS122008DVD | 1 |
| Dracula Origin | CBS092008DVDGold | 1 |
| Dracula Twins | CBS012007DVD | 1 |
| Dragonshard | CBS032005DVD | 3 |
| Dragonshard v 1 1 | CBS122005DVD | 1 |
| Dragonshardv | CBS052006DVD | 1 |
| Drakensang | CBS072009DVD | 1 |
| Dream Pinball DTwo Worlds | CBS102006DVD | 1 |
| Dreamfall The Longest Journey | CBS092005DVD | 2 |
| Dreamlords - The Re Awakening | CBS102008DVD | 1 |
| Drive Image XML | CBS012009DVD | 1 |
| DSL Manager | CBS042008DVD | 1 |
| DSLManager | CBS042008DVD | 1 |
| Dungeon Lords | CBS012005DVD | 3 |
| dungeon quest | CBS082009DVD | 1 |
| Dungeon Siege 2 | CBS112005DVD | 1 |
| Dungeon Siege 2 v 2 | CBS122005DVD | 1 |
| Dungeons Dragons Online | CBS012006DVD | 1 |
| dzial 1 | CBS012005DVD | 1 |
| dzial 2 | CBS012005DVD | 1 |
| dzial 3 | CBS012005DVD | 1 |
| dzial 4 | CBS012005DVD | 1 |
| dzial 5 | CBS012005DVD | 1 |
| Earth 2150 Blue Planet | CBS062005DVD | 1 |
| Earth 2150 Lost Souls | CBS062005DVD | 1 |
| Earth 2150 Moon Project | CBS062005DVD | 1 |
| Earth 2160 | CBS122004DVD | 2 |
| Easy BCD 1 7 | CBS032008DVD | 1 |
| Easy BCD171 | CBS032008DVD | 1 |
| Easytoolz | CBS052008DVD | 2 |
| Easytoolz 2 | CBS092008DVD | 9 |
| Easytoolz22 | CBS092008DVD | 9 |
| Edna bricht aus | CBS092008DVD | 1 |
| Ednabrichtaus | CBS092008DVD | 1 |
| El Coro, Mexiko | CBS012005DVD | 1 |
| Elveon | CBS112006DVD | 1 |
| Emergency 2 | CBS052004 | 1 |
| Emergency 3 | CBS022005DVD | 1 |
| Emergency Global Fighters For Life | CBS072006DVD | 1 |
| Emergency Global Fightersfor Life | CBS062006DVD | 1 |
| Empire Earth 2 | CBS052005DVD | 1 |
| Empire Earth 3 | CBS022008DVD | 1 |
| Empire Earth3 | CBS022008DVD | 1 |
| Empires Die Neuzeit | CBS112004DVD | 1 |
| Enchanted Arms | CBS092006DVD | 2 |
| Enemy Territory Quake Wars | CBS042008DVD | 2 |
| Enemy Territory Quake Wars v 1 | CBS042008DVD | 1 |
| Enemy Territory Quake Warsv14 | CBS042008DVD | 1 |
| Enigma | CBS092008DVD | 1 |
| Enigma Rising Tide | CBS032005DVD | 1 |
| Enthusia Pro | CBS032005DVD | 1 |
| Eragon | CBS012007DVD | 1 |
| Eragonfilm | CBS012007DVD | 1 |
| Erbe der Könige Demo | CBS032005DVD | 1 |
| ERFAHRUNG display | CBS012005DVD | 1 |
| Esculli la llengua del | CBS052010DVDGold | 1 |
| Eternal Silence 3 | CBS112008DVD | 1 |
| Europa Raser | CBS022006DVD | 1 |
| EVEOnline The Second Genesis | CBS012007DVD | 1 |
| Everest Ultimate Edition | CBS042008DVD | 1 |
| Everquest 2 | CBS022005DVD | 1 |
| Everquest 2 B | CBS062005DVD | 1 |
| Everquest Echoes Of Faydwer | CBS112006DVD | 1 |
| Everquest Kingdomof Sky | CBS052006DVD | 1 |
| Evil Genius | CBS112004DVD | 1 |
| Evochron Alliance | CBS102006DVDGOLD | 1 |
| Evolution GT | CBS072006DVD | 1 |
| Experience112 | CBS042008DVD | 1 |
| Extreme Tux Racer | CBS052008DVD | 1 |
| Faces of War | CBS042006DVD | 1 |
| Facesof War | CBS092006DVDGOLD | 1 |
| FAESuper Hornet | CBS012007DVD | 1 |
| Fahrenheit | CBS092005DVD | 2 |
| Fahrenheit v 1 | CBS012006DVD | 1 |
| Falcon 4 0 Allied Force v 1 0 | CBS042006DVD | 1 |
| Fallobst Arcade | CBS042005DVD | 1 |
| Far Cry Instincts | CBS082005DVD | 1 |
| Far Cry Instincts Predator Technologie | CBS052006DVD | 1 |
| Far Cryv | CBS012007DVD | 1 |
| Fast Lane Carnage | CBS022006DVD | 1 |
| Fear v 1 02 | CBS022006DVD | 1 |
| FEARv | CBS092006DVD | 3 |
| Fette Sau XS | CBS112004DVD | 1 |
| Field Ops | CBS102006DVD | 1 |
| Fiesta Online | CBS092008DVDGold | 2 |
| FIFA Football 2005 | CBS122004DVD | 1 |
| FIFAFuball Weltmeisterschaft | CBS062006DVD | 2 |
| Fight Night Round 3 | CBS032006DVD | 1 |
| Filme | CBS032007DVDGold | 1 |
| Fire Department | CBS112004DVD | 2 |
| Fire Department 2 | CBS012005DVD | 3 |
| Flat Out | CBS022005DVD | 2 |
| Flatout | CBS112004DVD | 2 |
| Flight Gear | CBS052008DVD | 1 |
| flip mysz inv | CBS012005DVD | 1 |
| Football Manager 2005 | CBS032005DVD | 1 |
| Football Manager 2006 Gold | CBS022006DVD | 1 |
| Ford Racing 3 | CBS042005DVD | 1 |
| Forsaken | CBS112001 | 1 |
| Fraps | CBS042006DVD | 3 |
| Free Civ | CBS102008DVD | 1 |
| Free Commander | CBS042008DVD | 1 |
| Freedom Force | CBS012007DVD | 1 |
| Freespace | CBS082006DVDGOLD | 1 |
| French Street Racing | CBS092008DVD | 1 |
| Fritz | CBS102003 | 1 |
| Fritz 7 SE | CBS082005DVD | 1 |
| Fritz 9 SE | CBS112008DVD | 1 |
| Frontlines Fuelof War | CBS012007DVD | 1 |
| Frontlines Fuelof Warv102 | CBS062008DVD | 1 |
| Frontlines Fuelof Warv110 | CBS092008DVD | 1 |
| Fuball Manager | CBS012007DVDGOLD | 1 |
| Fuball Manager2008v802 | CBS062008DVD | 1 |
| Full Auto | CBS032006DVD | 1 |
| Full Auto Battlelines | CBS012007DVD | 1 |
| Full Spectrum Warrior | CBS012005DVD | 1 |
| Full Spectrum Warrior Ten Hammers | CBS062006DVD | 1 |
| Funk Flitzer | CBS022000 | 1 |
| Fußball Manager 09 | CBS022009DVD | 1 |
| Fussball Manager 2006 v | CBS032006DVD | 1 |
| Fußball Manager 2008 v 8 0 | CBS062008DVD | 1 |
| Fussball Managerv | CBS052006DVD | 1 |
| Galactic Civilzations Dread Lordsv | CBS112006DVD | 1 |
| Game Tycoon 1 | CBS082005DVD | 1 |
| Gammakorrektur | CBS012005DVD | 1 |
| Gangsters | CBS052002 | 1 |
| Garry die Schmeißfliege | CBS052005DVD | 1 |
| Geheimakte Tunguska | CBS102006DVDGOLD | 1 |
| Genius Task Force Biologie | CBS072005DVD | 1 |
| Gentleman | CBS072005DVD | 1 |
| Ghost Recon Advanced Tactical Center | CBS092006DVDGOLD | 1 |
| Gigabyte Easy Tune5 Pro | CBS122008DVD | 1 |
| Ging Gong Boxen | CBS122005DVD | 1 |
| Giropay | CBS052006DVD | 1 |
| Go Around Showdown | CBS032005DVD | 1 |
| Gods Landsof Infinity | CBS092006DVD | 1 |
| Goin Downtown | CBS092008DVDGold | 1 |
| Goin Downtown v 1 | CBS102008DVD | 1 |
| Goin Downtownv11 | CBS102008DVD | 1 |
| Goldboxer | CBS072006DVD | 1 |
| Gooka | CBS012005DVD | 1 |
| Gotcha! | CBS112004DVD | 1 |
| Gothic | CBS082006DVD | 1 |
| Gothic 3 | CBS082005DVD | 2 |
| Gothicv | CBS012007DVD | 1 |
| Grand Theft Auto | CBS012005DVD | 1 |
| Gratisaktion | CBS112009DVD | 1 |
| grayout grenade | CBS012005DVD | 1 |
| grayout gun | CBS012005DVD | 1 |
| Green Game | CBS072005DVD | 1 |
| grenade name | CBS012005DVD | 1 |
| Ground Control | CBS062003 | 1 |
| GSRGerman Street Racing | CBS122006DVDGOLD | 1 |
| GT Legends | CBS112005DVD | 1 |
| GTA San Andreas | CBS122004DVD | 1 |
| GTA San Andreas v 1 | CBS112005DVD | 1 |
| GTIRacing | CBS072006DVD | 1 |
| GTR FIA GT Racing Game | CBS012005DVD | 1 |
| GTR Fia GT Racing Game 1 | CBS082005DVD | 1 |
| GTRFIAGTRacing Game | CBS102006DVD | 1 |
| Guild Wars | CBS072005DVD | 1 |
| Guild Wars Factions | CBS072006DVD | 2 |
| Guild Wars Nightfall | CBS112006DVD | 2 |
| Guinness World Records 2005 | CBS042006DVD | 1 |
| Gunship Apocalypse | CBS012007DVD | 1 |
| Half Life 2 | CBS112004DVD | 1 |
| Half Life Episode One | CBS072006DVD | 1 |
| Half Life Episode Two | CBS092006DVDGOLD | 2 |
| Half Life Portal | CBS102006DVD | 1 |
| Halo 2 | CBS012005DVD | 2 |
| Halo Kampf um die Zukunft | CBS122004DVD | 1 |
| Hamburger Weihnachtsreise | CBS012006DVD | 1 |
| Hammer und Sichel | CBS032006DVD | 1 |
| Hank XS | CBS092005DVD | 1 |
| Happy Feet | CBS012007DVD | 1 |
| Happy Pingu | CBS012009DVD | 1 |
| Harry Potter Bonusmaterial | CBS122005DVD | 1 |
| Harry Potter u | CBS122005DVD | 1 |
| Haunted House | CBS122006DVD | 1 |
| HDCleaner | CBS042008DVD | 1 |
| health digit | CBS012005DVD | 1 |
| Heimspiel | CBS082006DVD | 1 |
| Heimspiel Eishockeymanager | CBS032007DVDGold | 1 |
| Hell Copter | CBS121999 | 1 |
| Hello Kitty Roller Rescue | CBS022006DVD | 1 |
| Heroes of Annihilated Empires | CBS032006DVD | 1 |
| Heroes of Might and Magic 5 | CBS082005DVD | 1 |
| Heroes of the Pacific | CBS112005DVD | 1 |
| Heroesof Annihilated Empires | CBS072006DVD | 1 |
| Heroesof Might Magicv | CBS092006DVD | 1 |
| Heroesof Mightand Magic | CBS072006DVD | 1 |
| Herr der Pilze | CBS022001 | 1 |
| Hidden & Dangerous 2 | CBS032005DVD | 1 |
| Highland Warriors | CBS022006DVD | 1 |
| Himmel und Huhn | CBS042006DVD | 1 |
| Hitman Blood Moneyv | CBS102006DVD | 1 |
| Hui Buh Das Schlossgespenstunddie Geisterjger | CBS102006DVD | 1 |
| Hyper Snap | CBS102006DVD | 1 |
| Ice Age Jetzttauts | CBS062006DVD | 1 |
| IKK Direkt Mountainbike Challenge 08 | CBS112008DVD | 1 |
| ikonka na zakladce 1 naboj | CBS012005DVD | 1 |
| ikonka na zakladce 1 pistolet | CBS012005DVD | 1 |
| ikonka na zakladce 2 karabin | CBS012005DVD | 1 |
| ikonka na zakladce 3 naboj | CBS012005DVD | 1 |
| ikonka na zakladce 4 luneta | CBS012005DVD | 1 |
| ILSturmovik Forgotten Battles | CBS112006DVD | 1 |
| Immortal Cities Kinder des Nils v 1 3 0 | CBS102008DVD | 1 |
| Immortal Cities Kinderdes Nilsv11 | CBS102008DVD | 1 |
| Imperial Glory | CBS112004DVD | 2 |
| Imperium Romanum | CBS042008DVD | 2 |
| Imperium Romanum Kopierschutz | CBS052008DVD | 1 |
| Imperium Romanum v 1 | CBS062008DVD | 1 |
| Imperium Romanumv102 | CBS062008DVD | 1 |
| In 80 Tagen um die Welt | CBS022006DVD | 1 |
| Incadia | CBS062005DVD | 1 |
| increase stack undr mouse | CBS012005DVD | 1 |
| Indeo 5 | CBS062005DVD | 1 |
| Indiana Jonesunddas Knigreichdes Kristallschdels | CBS052008DVDGold | 1 |
| Industrie Gigant 2 | CBS062004 | 1 |
| inv Load parent | CBS012005DVD | 1 |
| Invasion Repel and Rebuild | CBS032005DVD | 1 |
| Iron Man | CBS092008DVDGold | 2 |
| Iron Man v 1 | CBS092008DVD | 1 |
| Iron Manv11 | CBS092008DVD | 1 |
| Izberite jezik za pripravo | CBS052010DVDGold | 1 |
| Jack Keaneandthe Dokktors Island | CBS082006DVD | 1 |
| Jacomo's Brick Mountain | CBS022005DVD | 1 |
| Jacomo's Castle | CBS032005DVD | 1 |
| Jade Empire | CBS072005DVD | 1 |
| Jagdfieber | CBS012007DVD | 1 |
| Jagged Alliance Wildfire | CBS072006DVD | 1 |
| Jeithonas | CBS062008DVD | 1 |
| John Woo Presents Stranglehold | CBS012007DVD | 1 |
| John Woos Stranglehold | CBS062006DVD | 1 |
| Joint Task Force | CBS042006DVD | 1 |
| Juiced | CBS072005DVD | 2 |
| Juiced Hot Import Nights | CBS022008DVDGold | 1 |
| Juiced v 1 01 | CBS122005DVD | 1 |
| Jumping Jokers | CBS092001 | 1 |
| Just Cause | CBS102006DVD | 2 |
| K Racer | CBS052001 | 1 |
| Kakuro XXL | CBS072006DVD | 1 |
| Kameo Elements of Power | CBS022006DVD | 1 |
| Kao the Kangaroo Round 2 | CBS042006DVD | 1 |
| Karomatix | CBS122005DVD | 1 |
| Kaufzeit | CBS012005DVD | 1 |
| Keepsake | CBS022006DVD | 2 |
| Keepsake v | CBS032006DVD | 1 |
| Keepsakev | CBS062006DVD | 1 |
| Kiki the Nanobot | CBS032006DVD | 1 |
| Kinder des Nils v 1 | CBS052005DVD | 1 |
| King of the Road | CBS122005DVD | 1 |
| King's Bounty - The Legend | CBS022009DVD | 1 |
| King's Quest 7 | CBS062000 | 1 |
| Kinofilm | CBS062008DVD | 1 |
| Knight | CBS122006DVD | 1 |
| Knight Rider The Game | CBS052006DVD | 2 |
| Knight Shift | CBS082005DVD | 1 |
| Knights of Honor | CBS122004DVD | 2 |
| Knights of the Old Republic 2 | CBS052005DVD | 1 |
| Knightshift | CBS082005DVD | 1 |
| Knightsofthe Temple | CBS062006DVD | 1 |
| Know How | CBS072010DVD | 1 |
| Kochmeister Pfanne 2 XS | CBS012005DVD | 1 |
| kompas bots | CBS012005DVD | 1 |
| kompas busola | CBS012005DVD | 1 |
| kompas damage | CBS012005DVD | 1 |
| Kransimulator 2009 | CBS022009DVD | 1 |
| kreska 1 | CBS012005DVD | 1 |
| kreska 10 | CBS012005DVD | 1 |
| kreska 11 | CBS012005DVD | 1 |
| kreska 2 | CBS012005DVD | 1 |
| kreska 3 | CBS012005DVD | 1 |
| kreska 4 | CBS012005DVD | 1 |
| kreska 5 | CBS012005DVD | 1 |
| kreska 6 | CBS012005DVD | 1 |
| kreska 7 | CBS012005DVD | 1 |
| kreska 8 | CBS012005DVD | 1 |
| kreska 9 | CBS012005DVD | 1 |
| kreska na prawym shopie | CBS012005DVD | 1 |
| kreska na srodkowym oknie nizsza | CBS012005DVD | 1 |
| kreska na srodkowym oknie wyzsza | CBS012005DVD | 1 |
| Kult Heretic Kingdoms | CBS122004DVD | 1 |
| Kult Heretic Kingdoms v 1 | CBS012005DVD | 2 |
| Kumoon | CBS022006DVD | 1 |
| LANoire | CBS012007DVD | 1 |
| Largo Winch | CBS112004DVD | 1 |
| Larry Cannibal Attack | CBS032006DVD | 1 |
| Larry Cannibal Crush | CBS082005DVD | 1 |
| Larry Jungle Smash | CBS042005DVD | 1 |
| Larry Super Eggomania | CBS052005DVD | 1 |
| Larry's Grand Slam Tennis | CBS092005DVD | 1 |
| Last Chaos | CBS042008DVD | 1 |
| LCD panel 1 | CBS012005DVD | 1 |
| LCD ramka lewa | CBS012005DVD | 1 |
| LCD ramka prawa | CBS012005DVD | 1 |
| LEFT ARROW | CBS012005DVD | 1 |
| Legacy of Kain Defiance | CBS012009DVDSonder | 1 |
| Legacy of Kain Soul Reaver | CBS022002 | 1 |
| Legend Handof Godv102 | CBS042008DVD | 1 |
| Lego Batman | CBS012009DVDGold | 1 |
| Lego Indiana Jones Die legendären Abenteuer | CBS012009DVDSonder | 1 |
| Lego Star Wars | CBS082005DVD | 1 |
| Lego Star Wars Dieklassische Trilogie | CBS112006DVD | 1 |
| Leisure Suit Larry | CBS012005DVD | 1 |
| Lemony Snicket | CBS032005DVD | 1 |
| Level R | CBS092008DVD | 2 |
| light digit | CBS012005DVD | 1 |
| Lineage Oathof Blood Chronicle | CBS112006DVD | 1 |
| Linseneffekte | CBS012005DVD | 1 |
| Live for Speed | CBS112005DVD | 1 |
| Loco Mania | CBS052006DVD | 1 |
| Loesung | CBS102008DVD | 2 |
| Loesungsbuecher | CBS102008DVD | 11 |
| Logistik Master | CBS032008DVD | 1 |
| Loki v 1 0 8 | CBS052008DVD | 1 |
| Lokiv1082 | CBS052008DVD | 1 |
| London Racer | CBS062006DVD | 1 |
| Lost Empire Immortals | CBS062008DVDGold | 1 |
| Lost Magic | CBS072006DVD | 1 |
| Lost Planet | CBS032006DVD | 3 |
| Lucky Luke Go West | CBS042008DVD | 1 |
| Lumines | CBS102006DVD | 1 |
| Mad Tracks | CBS042006DVD | 1 |
| Madagascar 2 | CBS012009DVD | 1 |
| Mapauswahl | CBS012005DVD | 1 |
| Mapzeit | CBS012005DVD | 1 |
| Marine Park Empire | CBS102006DVD | 1 |
| Mario Power Tennis | CBS042005DVD | 1 |
| Marvel Ultimate Alliance | CBS102006DVD | 1 |
| Mashed | CBS102005DVD | 1 |
| Maximale Anzahl der NPCs | CBS012005DVD | 1 |
| Mc Afee Avert Stinger | CBS052008DVD | 1 |
| Mc Afee Rootkit Detective | CBS052008DVD | 1 |
| MDK | CBS032001 | 1 |
| Medalof Honor Airbornev13 | CBS062008DVD | 1 |
| Medieval Lords | CBS112004DVD | 2 |
| Medieval Total War | CBS122006DVD | 1 |
| Meistertrainer | CBS042002 | 1 |
| Mercedes CLC Dream - Test Drive | CBS022009DVD | 1 |
| Metal Gear Solid 4 | CBS012006DVD | 1 |
| Metal Gear Solid Guns of the Patriots | CBS102008DVDGold | 1 |
| Metal Gear Solid Gunsofthe Patriots | CBS092006DVD | 1 |
| Metin | CBS032007DVDGold | 1 |
| Metroid Prime 2 Echoes | CBS022005DVD | 1 |
| Michael Schumacher World Tour Kart | CBS112006DVD | 1 |
| Micro Machines V | CBS092006DVD | 1 |
| Microsoft Combat Flight Simulator | CBS062008DVDGold | 1 |
| Microsoft Flight Simulator 98 | CBS122004DVD | 1 |
| Microsoft Flight Simulator X | CBS102006DVD | 1 |
| Midnight Club 3 | CBS122004DVD | 1 |
| Midnight Club 3 Dub Edition | CBS062005DVD | 1 |
| Midnight Nowhere | CBS032006DVD | 1 |
| Mighty Jack Hammer | CBS112004DVD | 1 |
| Mini Golf Shot | CBS092006DVD | 1 |
| minus Details | CBS012005DVD | 1 |
| minus GEWEHRE | CBS012005DVD | 1 |
| minus KAMPF | CBS012005DVD | 1 |
| minus KRAFT | CBS012005DVD | 1 |
| minus MACHINENPISTOLEN | CBS012005DVD | 1 |
| minus NAHKAMPF | CBS012005DVD | 1 |
| minus PISTOLEN | CBS012005DVD | 1 |
| minus SCHOTTFLINTEN | CBS012005DVD | 1 |
| minus Schwierigkeitsgrad | CBS012005DVD | 1 |
| minus TARNUNG | CBS012005DVD | 1 |
| minus TECHNIK | CBS012005DVD | 1 |
| Mobility 1 | CBS032001 | 1 |
| Monsterz | CBS092008DVD | 1 |
| Moorhuhn Action Im Anflug | CBS092006DVD | 1 |
| Moorhuhn Atlantis | CBS102008DVD | 1 |
| Moorhuhn Invasion | CBS112005DVD | 1 |
| Moorhuhn Piraten | CBS102006DVD | 2 |
| Moorhuhn Schatzjaeger | CBS012006DVD | 1 |
| Moorhuhn Soccer | CBS022008DVD | 1 |
| Moorhuhn Wanted | CBS122004DVD | 1 |
| Moorhuhn Wanted XS | CBS112004DVD | 1 |
| Moto GP | CBS072006DVD | 1 |
| Moto GP 08 | CBS022009DVD | 1 |
| Moto GP URT 3 | CBS102005DVD | 1 |
| MSWTK 2004 | CBS112006DVD | 1 |
| MTX Mototrax | CBS032005DVD | 1 |
| Muzzle | CBS092005DVD | 2 |
| My Gamers Cam | CBS062008DVD | 1 |
| Myst 5 End of Ages | CBS112005DVD | 1 |
| Myst Exile | CBS012007DVDGOLD | 1 |
| mysterious void | CBS012005DVD | 1 |
| Mystery Island | CBS042000 | 1 |
| na ziemie | CBS012005DVD | 1 |
| Napoleon | CBS032006DVD | 1 |
| Navy Field | CBS042008DVD | 1 |
| Need for Speed Carbon v 1 | CBS032008DVD | 1 |
| Need for Speed Most Wanted | CBS122005DVD | 2 |
| Need for Speed Most Wanted v | CBS032006DVD | 1 |
| Need for Speed Pro Street | CBS052008DVD | 1 |
| Needfor Speed Carbon | CBS092006DVDGOLD | 2 |
| Needfor Speed Carbonv14 | CBS032008DVD | 1 |
| Needfor Speed Pro Street | CBS052008DVD | 1 |
| Neocron 2 Evolution v | CBS032006DVD | 1 |
| Neocron Arcade | CBS042006DVD | 1 |
| Neosteam | CBS072009DVD | 1 |
| Nero 6 Reloaded (Demo) | CBS072005DVD | 1 |
| NET Framework 1 | CBS082005DVD | 2 |
| NET Framework 2 | CBS022008DVD | 16 |
| Net Quartett | CBS062006DVD | 1 |
| NETFramework | CBS052006DVD | 9 |
| NETFramework20 | CBS022008DVD | 16 |
| NEUES SPIEL | CBS012005DVD | 1 |
| Neuro Hunter | CBS032006DVD | 1 |
| Neverwinter Nights v 1 | CBS032005DVD | 2 |
| Neverwinter Nightsv | CBS112006DVD | 1 |
| Nexus The Jupiter Incident | CBS012005DVD | 1 |
| NFS Underground 2 | CBS012005DVD | 2 |
| NFS Underground 2 v 1 | CBS022005DVD | 1 |
| NHL08 Vista | CBS032008DVD | 1 |
| Nibiru Der Bote der Götter | CBS042005DVD | 2 |
| Nice 2 | CBS042001 | 1 |
| NIVEA FOR MEN Football Mania | CBS042006DVD | 1 |
| Nivea Maennersache Computerspiel | CBS102005DVD | 1 |
| Nivea Maennersache Spot | CBS102005DVD | 1 |
| Nostradamus Die letzte Prophezeihung | CBS052008DVD | 1 |
| Nostradamus Dieletzte Prophezeihung | CBS052008DVD | 1 |
| num of grenades left | CBS012005DVD | 1 |
| Obscure | CBS112004DVD | 2 |
| Obulis | CBS092008DVD | 1 |
| Ocean Diver | CBS012009DVD | 1 |
| Oddworld Abe's Oddysee | CBS022001 | 1 |
| Oddworld Strangers Vergelt | CBS052005DVD | 1 |
| Oktoberfest Zapfer | CBS062001 | 1 |
| Onimusha Demon Siege | CBS052006DVD | 1 |
| Onimusha Demon Siegev | CBS062006DVD | 1 |
| Online Spiel | CBS092005DVD | 5 |
| onlineangebote gamesload | CBS082009DVD | 1 |
| onlineangebote metaboli | CBS092009DVD | 1 |
| onlineangebote small | CBS082009DVD | 2 |
| Onlinespiel | CBS102008DVD | 3 |
| onlinespiel drachen | CBS102009DVD | 1 |
| Opaque Composition | CBS022006DVD | 1 |
| Ottifanten Ostfriesen Lemminge in Not | CBS042006DVD | 1 |
| Ottifanten Ostfriesen Pinball | CBS012006DVD | 1 |
| Outlaw Golf 2 | CBS122004DVD | 1 |
| Over GFighters | CBS102006DVD | 1 |
| Pacific Fighters | CBS122004DVD | 1 |
| Pacific Fighters Strategiebuch | CBS042008DVDGold | 1 |
| Pacific Storm | CBS082006DVD | 1 |
| Pacific Storm v 1 | CBS032008DVD | 1 |
| Pacific Stormv14 | CBS032008DVD | 1 |
| Panzer Elite Action | CBS032006DVD | 1 |
| Panzer Elite Action Dunesof War | CBS102006DVD | 1 |
| Papierkrieg | CBS062006DVD | 1 |
| Paradise | CBS072006DVD | 2 |
| Paraworld | CBS062006DVD | 3 |
| Paraworldfilm | CBS112006DVD | 1 |
| Paraworldv | CBS012007DVD | 1 |
| Parent Follow Mouse | CBS012005DVD | 1 |
| parent keymapper | CBS012005DVD | 1 |
| Parent lewego shopa | CBS012005DVD | 1 |
| Parent New GB | CBS012005DVD | 1 |
| Parent prawego shopa | CBS012005DVD | 1 |
| parent profile | CBS012005DVD | 1 |
| parent single | CBS012005DVD | 1 |
| Parent srodkowego shopa | CBS012005DVD | 1 |
| Parent testowy | CBS012005DVD | 1 |
| Pariah | CBS022005DVD | 1 |
| Pariah v 1 | CBS082005DVD | 2 |
| Pathologic | CBS082006DVD | 1 |
| Patrizier 2 Gold | CBS022004 | 1 |
| PDC World Championship Darts 2008 | CBS052008DVD | 1 |
| PDCWorld Championship Darts2008 | CBS052008DVD | 1 |
| PEBuilder | CBS092006DVD | 1 |
| Penumbra Black Plague | CBS052008DVDGold | 2 |
| Penumbra Black Plague v 1 0 | CBS062008DVD | 1 |
| Penumbra Black Plaguev101 | CBS062008DVD | 1 |
| Performance Test | CBS092008DVD | 1 |
| Personal Backup | CBS012009DVD | 1 |
| Peter Jacksons King Kong | CBS112005DVD | 2 |
| Pilih bahasa yang akan dipakai | CBS052010DVDGold | 1 |
| Pilot Down | CBS112005DVD | 1 |
| Pined Pipe Mania | CBS112005DVD | 1 |
| Ping Cosmic Downhill | CBS022005DVD | 1 |
| Ping Flipper | CBS112004DVD | 1 |
| Ping Man | CBS052005DVD | 1 |
| Ping Pirate | CBS042005DVD | 1 |
| Ping Plantophobia | CBS062005DVD | 1 |
| Pings Basketball | CBS122004DVD | 1 |
| Pipemania | CBS122008DVD | 1 |
| Piraten Herrscher der Karibik v 1 1 0 | CBS042006DVD | 1 |
| Pixelzentrierung | CBS012005DVD | 1 |
| Pizza Connection 2 | CBS012003 | 1 |
| Pizza Syndicate | CBS092001 | 1 |
| Platt! | CBS092001 | 1 |
| Playboy The Mansion | CBS042005DVD | 2 |
| plus Details | CBS012005DVD | 1 |
| plus GEWEHRE | CBS012005DVD | 1 |
| plus KAMPF | CBS012005DVD | 1 |
| plus KRAFT | CBS012005DVD | 1 |
| plus MACHINENPISTOLEN | CBS012005DVD | 1 |
| plus NAHKAMPF | CBS012005DVD | 1 |
| plus PISTOLEN | CBS012005DVD | 1 |
| plus SCHOTTFLINTEN | CBS012005DVD | 1 |
| plus Schwierigkeitsgrad | CBS012005DVD | 1 |
| plus TARNUNG | CBS012005DVD | 1 |
| plus TECHNIK | CBS012005DVD | 1 |
| poczatek ramki | CBS012005DVD | 1 |
| Poker Academy | CBS112008DVD | 1 |
| Pony Ranch | CBS032008DVD | 1 |
| Port Royale 2 | CBS112004DVD | 1 |
| Ports of Call Deluxe 2008 | CBS062008DVD | 1 |
| Portsof Call Deluxe2008 | CBS062008DVD | 1 |
| Power Manga | CBS052008DVDGold | 1 |
| Power Scout | CBS012005DVD | 1 |
| Premium Skatde Luxe | CBS052006DVD | 1 |
| Preyv | CBS112006DVD | 2 |
| Prime Time Der Fernsehmanager | CBS062006DVD | 1 |
| Prince of Persia | CBS012005DVD | 2 |
| Prince of Persia 3 | CBS082005DVD | 1 |
| Prince of Persia Warrior Within | CBS112008DVDGold | 1 |
| Pro Evolution Soccer | CBS092006DVD | 1 |
| Pro Evolution Soccer 2009 v 1 | CBS022009DVD | 1 |
| Pro Evolution Soccer 4 | CBS022005DVD | 1 |
| Pro Evolution Soccer 4 v 1 | CBS032005DVD | 1 |
| Pro Evolution Soccer 5 | CBS122005DVD | 1 |
| Pro Evolution Soccer2009 | CBS122008DVD | 1 |
| Pro Pinball Timeshock | CBS032005DVD | 1 |
| Pro Stroke Golf World Tour | CBS112006DVD | 1 |
| Profi Ecke | CBS102008DVD | 1 |
| progress aim | CBS012005DVD | 1 |
| progress armor | CBS012005DVD | 1 |
| progress life | CBS012005DVD | 1 |
| progress lightning | CBS012005DVD | 1 |
| progress noise | CBS012005DVD | 1 |
| progress stamina | CBS012005DVD | 1 |
| progress weap health | CBS012005DVD | 1 |
| Project Freedom | CBS082006DVD | 1 |
| Project Gotham Racing 3 | CBS112005DVD | 1 |
| Project Nomads | CBS092004DVD | 1 |
| Project Snowblind | CBS032005DVD | 3 |
| Psychotoxic | CBS122004DVD | 1 |
| Pulleralarm | CBS092000 | 2 |
| PUNKTE display | CBS012005DVD | 1 |
| Punktelimit | CBS012005DVD | 1 |
| Pure Pinball | CBS052005DVD | 1 |
| Puzzle | CBS082006DVD | 1 |
| Pyro Tycoon | CBS032005DVD | 1 |
| Quake 4 v 1 04 | CBS022006DVD | 1 |
| Quake SDK | CBS102006DVDGOLD | 1 |
| Quakev | CBS072006DVD | 2 |
| Racing Simulation 2 | CBS102002 | 1 |
| Radsport Manager 2003 2004 | CBS102005DVD | 1 |
| Radsport Manager Pro Le Tourde France | CBS092006DVD | 1 |
| Radsport Manager Pro Le Tourde Francev | CBS102006DVD | 1 |
| Radsport Manager Pro Saison 05 06 | CBS092005DVD | 1 |
| Ragdoll Kung Fu | CBS082006DVD | 1 |
| rageclaw online | CBS092009DVD | 1 |
| Ragnarok | CBS122004DVD | 1 |
| Rail Simulator | CBS022008DVDGold | 1 |
| Rail Simulator Upgrade Mk1 | CBS052008DVD | 1 |
| Railroad Pioneer | CBS042006DVD | 1 |
| Railroad Tycoon 2 | CBS032003 | 1 |
| Rainbow Six 4 Lockdown | CBS062005DVD | 1 |
| Rainbow Six Covert Ops E | CBS042005DVD | 1 |
| Rainbow Six Lockdown | CBS032005DVD | 2 |
| Rainbow Six Vegas 2 v 1 | CBS102008DVD | 1 |
| Rainbow Six Vegas2v103 | CBS102008DVD | 1 |
| ramka niska | CBS012005DVD | 1 |
| ramka wstanie | CBS012005DVD | 1 |
| ramka wysoka | CBS012005DVD | 1 |
| ramka wysoka po raz 2 | CBS012005DVD | 1 |
| Rayman Raving Rabbids | CBS092006DVDGOLD | 1 |
| RC Cars | CBS122004DVD | 1 |
| Reg Cleaner | CBS032008DVD | 1 |
| Regnum Online | CBS112009DVDGold | 1 |
| Reise zum Zentrum d | CBS112005DVD | 1 |
| release camera | CBS012005DVD | 1 |
| Renny Claus | CBS012006DVD | 1 |
| Reprobates Insel der Verdammten | CBS022008DVD | 1 |
| Reprobates Insel der Verdammten v 1 3 | CBS102008DVD | 1 |
| Reprobates Inselder Verdammten | CBS022008DVD | 1 |
| Reprobates Inselder Verdammtenv133 | CBS102008DVD | 1 |
| Republic Commando | CBS052005DVD | 1 |
| reserved for progress copy | CBS012005DVD | 1 |
| reserved for status bar | CBS012005DVD | 1 |
| reserved for statusbar | CBS012005DVD | 1 |
| Restricted Area | CBS112004DVD | 2 |
| Restricted Area 1 | CBS022005DVD | 1 |
| Restricted Area v 1 | CBS012005DVD | 1 |
| Rettunghelicopter 112 | CBS072005DVD | 1 |
| RF Online | CBS042006DVD | 1 |
| Richard Burns Rally v 1 | CBS022005DVD | 1 |
| Ridge Racer 6 | CBS022006DVD | 1 |
| RIGHT ARROW | CBS012005DVD | 1 |
| Rise Fall | CBS062006DVD | 1 |
| Rise Fall Civilizationsat War | CBS052006DVD | 1 |
| Rise Fall Civilizationsat Warv | CBS092006DVD | 1 |
| Riseof Nations Riseof Legends | CBS052006DVD | 2 |
| Rising Kingdoms | CBS082005DVD | 1 |
| Rising Kingdoms v 1 | CBS042006DVD | 1 |
| Robo Rumble | CBS102000 | 1 |
| Rockstar Gamesprsentiert Tischtennis | CBS072006DVD | 1 |
| Rollercoaster Tycoon | CBS102004DVD | 1 |
| Rollercoaster Tycoon 3 | CBS012005DVD | 1 |
| Rollercoaster Tycoon 3 v 1 | CBS022005DVD | 1 |
| Rollercoaster Tycoon 3 Wild | CBS022006DVD | 1 |
| Romance of the Three Kingdoms 11 | CBS112008DVD | 1 |
| Romanceofthe Three Kingdoms | CBS112008DVD | 1 |
| Rome Barbarian Invasion | CBS112005DVD | 1 |
| Rome Total War Alexander | CBS092006DVD | 1 |
| Rome Total War Barbarian Invasion v | CBS032006DVD | 1 |
| Rome Total War v 1 | CBS052005DVD | 1 |
| Rosso Rabbitin Trouble | CBS052006DVD | 1 |
| RPM Tuning | CBS082005DVD | 1 |
| RTL Winter Sports 2008 The Ultimate Challenge | CBS022008DVD | 2 |
| RTLBiathlon2008 | CBS022008DVD | 1 |
| RTLRacing Team Manager | CBS052008DVDGold | 1 |
| RTLSkispringen | CBS012007DVD | 1 |
| RTLWinter Sports2008 The Ultimate Challenge | CBS022008DVD | 1 |
| Runaway 2 | CBS022006DVD | 1 |
| Runaway The Dreamofthe Turtle | CBS032007DVDGold | 1 |
| Rundenlimit | CBS012005DVD | 1 |
| Rundenzeit | CBS012005DVD | 1 |
| Runesof Magic | CBS082009DVD | 1 |
| Rush for Berlin | CBS092005DVD | 1 |
| Rushfor Berlin | CBS082006DVD | 1 |
| Rushfor Berlinv | CBS092006DVD | 2 |
| Rückkehr zur Insel | CBS022005DVD | 1 |
| Sacred | CBS122004DVD | 1 |
| Sacred 2 - Fallen Angel | CBS122008DVDGold | 1 |
| Saint's Row | CBS092005DVD | 1 |
| Santa Claus in Trouble | CBS012005DVD | 1 |
| Santa Clausin Trouble Gold | CBS012007DVD | 1 |
| Sataan | CBS122004DVD | 1 |
| Sataan Das Spiel v 1 | CBS042005DVD | 1 |
| Savage ATortured Soul | CBS062008DVDGold | 1 |
| Save Kolchez'a 21:22:22 2002 10 22 | CBS012005DVD | 1 |
| Schatten | CBS012005DVD | 1 |
| Schiff Simulator | CBS092006DVD | 1 |
| Schiffe versenken | CBS102005DVD | 1 |
| Schlacht um Mittelerde 1 | CBS082005DVD | 1 |
| Schnappi Das kl | CBS062005DVD | 1 |
| Schnappi Das kleine Krokodil XS | CBS052005DVD | 1 |
| Schwierigkeitsgrad | CBS012005DVD | 1 |
| Scorched 3 D | CBS122004DVD | 1 |
| Scrapland | CBS032005DVD | 2 |
| Scratches | CBS042005DVD | 2 |
| Sea Wolves | CBS072005DVD | 1 |
| Second Sight | CBS012005DVD | 1 |
| Sensible Soccer | CBS092006DVD | 1 |
| Sentinel Verborg | CBS032005DVD | 1 |
| Serious Sam 2 | CBS092005DVD | 1 |
| Shade Zorn der Engel | CBS012005DVD | 1 |
| Shadow Company | CBS032002 | 1 |
| Shadow Man | CBS072002 | 1 |
| Shadow Ops Red Mercury | CBS042005DVD | 1 |
| Shadowgrounds | CBS012006DVD | 1 |
| Shadowgrounds Leveleditor | CBS102006DVDGOLD | 1 |
| Sheep | CBS072004(CD1) | 2 |
| Sherlock Holmes | CBS012005DVD | 1 |
| Sherlock Holmes - Die Spur der Erwachten - Remastered Edition | CBS022009DVD | 1 |
| Sherlock Holmes Das Geheimnisdessilbernen Ohrrings | CBS012007DVD | 1 |
| Shoot the Roach | CBS052005DVD | 1 |
| shop basket | CBS012005DVD | 1 |
| shop client | CBS012005DVD | 1 |
| shop vendor | CBS012005DVD | 1 |
| Shot Online | CBS022008DVD | 2 |
| Show Athletics | CBS012005DVD | 1 |
| Show GEWEHRE | CBS012005DVD | 1 |
| Show GEWEHRExp Needed | CBS012005DVD | 1 |
| Show KAMPF | CBS012005DVD | 1 |
| Show KAMPFExp Needed | CBS012005DVD | 1 |
| Show KRAFTExp Needed | CBS012005DVD | 1 |
| Show MACHINENPISTOLEN | CBS012005DVD | 1 |
| Show MACHINENPISTOLENxp Needed | CBS012005DVD | 1 |
| Show NAHKAMPF | CBS012005DVD | 1 |
| Show NAHKAMPFExp Needed | CBS012005DVD | 1 |
| Show PISTOLEN | CBS012005DVD | 1 |
| Show PISTOLENExp Needed | CBS012005DVD | 1 |
| Show SCHOTTFLINTEN | CBS012005DVD | 1 |
| Show SCHOTTFLINTENxp Needed | CBS012005DVD | 1 |
| Show TARNUNG | CBS012005DVD | 1 |
| Show TARNUNGExp Needed | CBS012005DVD | 1 |
| Show TECHNIK | CBS012005DVD | 1 |
| Show TECHNIKxp Needed | CBS012005DVD | 1 |
| Sid Meier's Civilization 4 - Fall from Heaven 2 0 | CBS112008DVD | 1 |
| Sid Meier's Pirates! | CBS112004DVD | 3 |
| Sid Meiers Railroads | CBS012007DVDGOLD | 1 |
| Siedler Das Erbe der Könige | CBS112004DVD | 1 |
| Siege of Avalon | CBS072001 | 1 |
| silencer 0 | CBS012005DVD | 1 |
| silencer 1 | CBS012005DVD | 1 |
| silencer 2 | CBS012005DVD | 1 |
| Silent Hunter 3 | CBS042005DVD | 2 |
| Silent Hunter 3 v 1 | CBS062005DVD | 2 |
| Silver Wings | CBS092006DVD | 1 |
| Silverfall Wchterder Elemente | CBS042008DVDGold | 1 |
| Sim City Societies | CBS092008DVDGold | 1 |
| Sim City Societies v 1 02 | CBS062008DVD | 1 |
| Sim City Societiesv102119 | CBS062008DVD | 1 |
| Singles 2 Wilde Zeiten | CBS082005DVD | 1 |
| Singles Flirt up your Life | CBS022006DVD | 1 |
| Singlesv | CBS012007DVD | 1 |
| Sini Star Unleashed | CBS082000 | 1 |
| Sinking Island Mord im Paradies | CBS022008DVD | 1 |
| Sinking Island Mordim Paradies | CBS022008DVD | 1 |
| Sinsofa Solar Empire | CBS092008DVD | 1 |
| Ski Alpin 2006 mit Bode Miller | CBS032006DVD | 1 |
| Ski Alpin Racing Bode Millervs Hermann Maier | CBS012007DVD | 1 |
| Ski Xtreme | CBS012007DVD | 1 |
| Skisprung Wintercup 2005 | CBS042005DVD | 1 |
| Skype | CBS052006DVD | 1 |
| Skype 3 | CBS022008DVD | 11 |
| Skype 4 | CBS062009DVD | 4 |
| Skype35 | CBS022008DVD | 4 |
| Skype36 | CBS062008DVD | 1 |
| Skype38 | CBS092008DVD | 6 |
| Skype4 | CBS062009DVD | 4 |
| Sldner Marine Corpsv | CBS102006DVD | 1 |
| slider Gammakorrekteur | CBS012005DVD | 1 |
| slider Music | CBS012005DVD | 1 |
| slider Sfx | CBS012005DVD | 1 |
| Slowdown | CBS042005DVD | 1 |
| Smash Online | CBS112008DVD | 1 |
| Smashonline | CBS032008DVDGold | 1 |
| Snow Bomb Battle | CBS012005DVD | 1 |
| So Blonde | CBS062008DVD | 1 |
| Soeldner Secret Wars | CBS122004DVD | 1 |
| Solitaire | CBS022005DVD | 1 |
| Sonic Heroes | CBS012005DVD | 2 |
| Sonic Riders | CBS012007DVD | 1 |
| sound digit | CBS012005DVD | 1 |
| Space Corps Armageddon | CBS112004DVD | 1 |
| Space Hockey | CBS062001 | 1 |
| Space Pong | CBS092005DVD | 1 |
| Space Rangers | CBS082006DVD | 1 |
| Space Siege | CBS102008DVD | 1 |
| Spaceforce Captains | CBS052008DVD | 1 |
| Speed Bowling | CBS122004DVD | 1 |
| Speed Darting | CBS072005DVD | 1 |
| Speedball 2 Tournament | CBS042008DVD | 1 |
| Speedball2 Tournament | CBS042008DVD | 1 |
| Speedblox | CBS012007DVD | 1 |
| Speedpasch | CBS092006DVD | 1 |
| Speedpyramid | CBS112006DVD | 1 |
| Spellforce 2 | CBS022006DVD | 1 |
| Spellforce 2 Shadow Wars | CBS022009DVDGold | 1 |
| Spellforce Shadow Wars | CBS062006DVD | 1 |
| Spezial | CBS012006DVD | 1 |
| SPIEL BEENDEN | CBS012005DVD | 1 |
| SPIEL FORTSETZEN | CBS012005DVD | 1 |
| SPIEL VERLASSEN | CBS012005DVD | 1 |
| Spielfigur | CBS012005DVD | 1 |
| SPIELSTAND LADEN | CBS012005DVD | 1 |
| SPIELSTAND SPEICHERN | CBS012005DVD | 1 |
| Splinter Cell Chaos Theory | CBS112004DVD | 2 |
| Splinter Cell DVD | CBS092006DVDGOLD | 1 |
| Splinter Cell's Chaos Theory | CBS022010DVDGold | 1 |
| Spore | CBS082006DVD | 1 |
| Spore Labor Kreaturen Designer | CBS092008DVD | 2 |
| Spy Bot Search & Destroy | CBS092005DVD | 1 |
| Spybot Search Destroy | CBS012007DVD | 2 |
| Stalker Shadowof Chernobylv10005 | CBS022008DVD | 1 |
| STALKERv10003v10004v10005 | CBS032008DVD | 1 |
| stamina digit | CBS012005DVD | 1 |
| Star Force Vista Update | CBS032008DVD | 1 |
| Star Wars | CBS032006DVD | 1 |
| Star Wars Battlefront v 1 | CBS012005DVD | 1 |
| Star Wars Battlefrontv | CBS052006DVD | 1 |
| Star Wars Empireat War Forcesof Corruption | CBS012007DVDGOLD | 1 |
| Star Wars Empireat War Leveleditor | CBS092006DVDGOLD | 1 |
| Star Wars Empireat Warv | CBS052006DVD | 4 |
| Star Wars Rep | CBS032005DVD | 1 |
| Star Wars Republic Com | CBS042005DVD | 1 |
| Star Wolves | CBS082005DVD | 2 |
| Starship Troopers | CBS012006DVD | 2 |
| Starship Troopers v 3 2 | CBS012006DVD | 1 |
| Starsky & Hutch | CBS092005DVD | 1 |
| Startgeld | CBS012005DVD | 1 |
| Startzeit | CBS012005DVD | 1 |
| Steel Saviour | CBS122004DVD | 2 |
| Still Life | CBS042005DVD | 2 |
| Still Life Special Edition | CBS102008DVD | 1 |
| Still Life2 | CBS072009DVDGold | 1 |
| Stolen | CBS032005DVD | 1 |
| Stolen v | CBS082005DVD | 1 |
| Stone Age 2 | CBS122008DVDGold | 1 |
| Stonechecker 3 | CBS102005DVD | 1 |
| Stranger | CBS052008DVD | 1 |
| Strategic Command | CBS082006DVD | 1 |
| Strategic Commandv | CBS102006DVD | 1 |
| Stronghold 2 | CBS012005DVD | 2 |
| Stronghold 2 v 1 31 | CBS022006DVD | 1 |
| Stronghold Crusader Extreme | CBS092008DVDGold | 1 |
| Stronghold Legendsv | CBS012007DVD | 1 |
| Sudden Strike | CBS092006DVD | 1 |
| Sudden Strike 2 | CBS122005DVD | 1 |
| Sudden Strike 3 Arms for Victory v 1 | CBS052008DVD | 1 |
| Sudden Strike3 Armsfor Victory Ardennen Offensive | CBS092008DVDGold | 1 |
| Sudden Strike3 Armsfor Victoryv131 | CBS052008DVD | 1 |
| Sudeki | CBS122006DVD | 1 |
| Sudoku | CBS052006DVD | 1 |
| Summer Athletics | CBS102008DVDGold | 1 |
| Sunrise The Game | CBS042008DVDGold | 1 |
| Super Tux Kart | CBS062008DVD | 1 |
| Supreme Ruler2020 | CBS092008DVD | 1 |
| Surf Attack | CBS122004DVD | 1 |
| Surfive | CBS082001 | 1 |
| Suzuki Alstare Extreme Racing | CBS022003 | 1 |
| Sven kommt | CBS122005DVD | 1 |
| SWAT 4 | CBS052005DVD | 1 |
| Swat 4 The Stetchkov Syndicate | CBS042006DVD | 1 |
| Sweet Sour | CBS012006DVD | 1 |
| Swordofthe Stars | CBS102006DVDGOLD | 1 |
| T Main Window Window Title | CBS042010DVD | 1 |
| T Update Window Window Title | CBS042010DVD | 1 |
| Tabellen | CBS012009DVDSonder | 1 |
| Tabula Rasa | CBS092006DVD | 1 |
| TAKE ALL | CBS012005DVD | 1 |
| Take Command Second Manassasv | CBS102006DVD | 1 |
| Taleofa Hero | CBS062008DVD | 1 |
| Taxi 3 Extreme Rush | CBS082005DVD | 1 |
| Taxi Raser | CBS092006DVD | 1 |
| tcp optimizer | CBS082009DVD | 1 |
| TEAM A | CBS012005DVD | 1 |
| TEAM B | CBS012005DVD | 1 |
| Team Fortress | CBS102006DVD | 1 |
| Team Hawaii Eifel Run | CBS072005DVD | 1 |
| Team Speak 2 | CBS062008DVD | 3 |
| Team Speak2 | CBS062008DVD | 3 |
| Teamauswahl | CBS012005DVD | 1 |
| Tell Das Spielzum Film | CBS022008DVDGold | 1 |
| Tennis Power Ball | CBS032006DVD | 1 |
| Test Drive Unlimited | CBS012006DVD | 2 |
| test nowego buttona styl 2 | CBS012005DVD | 1 |
| Testabellen | CBS012009DVDSonder | 1 |
| Thandor Die Invasion | CBS062001 | 1 |
| The Bard's Tale | CBS062005DVD | 1 |
| The Chronicles of Riddick | CBS032005DVD | 1 |
| The Cleaner v5 | CBS052008DVD | 1 |
| The Elder Scrolls 4 Oblivion | CBS092005DVD | 1 |
| The Elder Scrolls Construction Set | CBS092008DVDGold | 1 |
| The Elder Scrolls Oblivion | CBS062006DVD | 1 |
| The Elder Scrolls Oblivionv | CBS112006DVD | 1 |
| The Elder Scrolls3 Morrowind Gameofthe Year Edition | CBS092008DVDGold | 1 |
| The Fall Last Days of Gaia | CBS022005DVD | 1 |
| The Fall Last Daysof Gaiav | CBS082006DVD | 1 |
| The Italian Job | CBS112005DVD | 1 |
| The Legend of Zelda | CBS012005DVD | 1 |
| The Longest Journey Special Edition | CBS032008DVD | 1 |
| The Matrix Online | CBS072005DVD | 1 |
| The Moment of Silence | CBS112004DVD | 2 |
| The Momentof Silence | CBS122006DVDGOLD | 1 |
| The Movies | CBS082005DVD | 3 |
| The Movies v | CBS032006DVD | 1 |
| The Outfit | CBS042006DVD | 1 |
| The Partners | CBS122004DVD | 1 |
| The Regiment | CBS042006DVD | 1 |
| The Sagaof Ryzom | CBS092006DVDGOLD | 1 |
| The Westerner | CBS032006DVD | 1 |
| The Witcher | CBS112005DVD | 2 |
| The Witcher v 1 | CBS062008DVD | 1 |
| The Witcher v 1 2 | CBS042008DVD | 1 |
| Theseus Returnofthe Hero | CBS052006DVD | 1 |
| Thirsty Punk | CBS052005DVD | 1 |
| Thunder Brigade | CBS062000 | 1 |
| Tiger Woods PGA Tour 2005 | CBS112004DVD | 1 |
| Timanfaya Verschollen in den Feuerbergen | CBS062008DVD | 1 |
| Timanfaya Verscholleninden Feuerbergen | CBS062008DVD | 1 |
| Time Shift v 1 | CBS022008DVD | 1 |
| Time Shiftv12 | CBS022008DVD | 1 |
| Timeshift | CBS042006DVD | 1 |
| Tips einblenden | CBS012005DVD | 1 |
| Tischfuball | CBS082006DVD | 1 |
| Titan Quest | CBS042006DVD | 1 |
| Titan Quest Sprach | CBS012007DVD | 1 |
| Titan Questv | CBS102006DVD | 1 |
| Tom Clancy's Ghost Recon 2 | CBS022005DVD | 1 |
| Tom Clancy's Splinter Cell Chaos Theory | CBS022010DVDGold | 1 |
| Tom Clancys Ghost Recon Advanced Warfighter | CBS052006DVD | 3 |
| Tom Clancys Ghost Recon Advanced Warfighterv | CBS082006DVD | 3 |
| Tom Clancys Rainbow Six Vegas | CBS092006DVDGOLD | 2 |
| Tom Clancys Splinter Cell | CBS092006DVDGOLD | 1 |
| Tom Clancys Splinter Cell Double Agent | CBS052006DVD | 1 |
| Tomb Raider | CBS062006DVD | 1 |
| Tomb Raider - Underworld | CBS012009DVDGold | 1 |
| Tomb Raider 2 | CBS082001 | 1 |
| Tomb Raider 3 | CBS112002 | 1 |
| Tomb Raider 4 The Last Revelation | CBS092003 | 1 |
| Tomb Raider Legend | CBS082005DVD | 1 |
| Tomb Raider Legend Spieltricks | CBS052006DVD | 1 |
| Tomb Raider Legendv | CBS072006DVD | 2 |
| Tony Hawk Underground 2 | CBS112004DVD | 1 |
| Tony Hawks Project | CBS092006DVD | 2 |
| tooltip handler for : ARMOR | CBS012005DVD | 1 |
| tooltip handler for : HEALTH | CBS012005DVD | 1 |
| tooltip handler for : LIGHTLEVEL | CBS012005DVD | 1 |
| tooltip handler for : SOUNDLEVEL | CBS012005DVD | 1 |
| tooltip handler for : STAMINA | CBS012005DVD | 1 |
| Top Spin | CBS112004DVD | 1 |
| Topdemos | CBS052008DVD | 4 |
| Torus Trooper | CBS062005DVD | 1 |
| Total Overdose | CBS062005DVD | 1 |
| Toucan | CBS012009DVD | 1 |
| Trackmania Nations | CBS042006DVD | 1 |
| Trackmania Nations ESWC | CBS052006DVD | 1 |
| Trackmania Orig Ext Ver | CBS012006DVD | 1 |
| Trackmania Sunrise | CBS072005DVD | 1 |
| Trackmania Sunrise Ex Upgr | CBS022006DVD | 1 |
| Trackmania v 1 50 1 | CBS032008DVD | 1 |
| Trackmaniav150152 | CBS032008DVD | 1 |
| Trainz Railroad Sim | CBS032005DVD | 2 |
| transaction value | CBS012005DVD | 1 |
| Treasure Island | CBS052008DVDGold | 1 |
| Treasure Island v 1 | CBS102008DVD | 1 |
| Treasure Islandv1002 | CBS102008DVD | 1 |
| Tribal Trouble | CBS022006DVD | 1 |
| Tribes Vengeance | CBS122004DVD | 2 |
| Tribunal | CBS092008DVDGold | 1 |
| Tube Twist | CBS052006DVD | 1 |
| Turbo Strauß | CBS022005DVD | 1 |
| Turok 2 | CBS042003 | 1 |
| Tweak VI | CBS032008DVD | 1 |
| Tycoon City New York | CBS042006DVD | 1 |
| Tycoon City New Yorkv | CBS062006DVD | 1 |
| UEFA Championsleague | CBS052005DVD | 1 |
| UEFAEuro | CBS062008DVDGold | 1 |
| UFO Aftershock | CBS032006DVD | 1 |
| Uli Stein 3 D Mahjongg | CBS072005DVD | 1 |
| Uli Stein Steinschlag | CBS062005DVD | 1 |
| Undercover Operation Wintersonne | CBS122006DVD | 1 |
| Undercover Operation Wstensonne | CBS072006DVD | 1 |
| Universeat War Angriffsziel Erde | CBS022008DVDGold | 1 |
| Unreal Tourn 2004 v | CBS062005DVD | 1 |
| Unreal Tournament 2004 | CBS122004DVD | 1 |
| Unreal Tournament 3 v 1 | CBS052008DVD | 1 |
| Unreal Tournament3v12 | CBS052008DVD | 1 |
| Uprising 2 | CBS112000 | 1 |
| Urlaubsraser | CBS052003 | 1 |
| USA Racer | CBS102003 | 1 |
| Valitse asennuskieli | CBS052010DVDGold | 1 |
| Vampirjagd | CBS092000 | 2 |
| Velaya - Geschichte einer Kriegerin 1 | CBS112008DVD | 1 |
| Verliebt in Berlin | CBS022006DVD | 1 |
| Videotippszu Anno | CBS102006DVDGOLD | 1 |
| Virtual Skipper | CBS052006DVD | 1 |
| Vista Boot PRO 3 3 | CBS032008DVD | 1 |
| Vista Boot PRO330 | CBS032008DVD | 1 |
| Vista Tuning | CBS042008DVD | 1 |
| Vivisector | CBS012006DVD | 1 |
| Vogelpiraten | CBS022009DVD | 1 |
| Vyberte jazyk | CBS052010DVDGold | 1 |
| Vyrox | CBS032005DVD | 1 |
| Waldmeister Sause Edelweiß | CBS012005DVD | 1 |
| Wall EDer Letzterumtdie Erdeauf | CBS062008DVD | 2 |
| Wallace Gromit | CBS012006DVD | 1 |
| War Front | CBS122005DVD | 1 |
| War Front Turning Point | CBS082006DVD | 2 |
| War Leaders Clashof Nationsv101 | CBS062008DVD | 1 |
| War World Tactical Combat | CBS052006DVD | 1 |
| Warcraft The Frozen Throne v 1 | CBS052008DVD | 1 |
| Warcraft The Frozen Thronev121b | CBS052008DVD | 1 |
| Warcraft3 Reignof Chaosv121b | CBS052008DVD | 1 |
| Warhammer 40000 | CBS012005DVD | 1 |
| Warhammer Dawnof War Dark Crusade | CBS092006DVD | 2 |
| Warhammer Dawnof War Soulstorm | CBS042008DVDGold | 1 |
| Warhammer Markof Chaos | CBS092006DVD | 1 |
| Warhammer Online Ageof Reckoning | CBS102006DVD | 1 |
| Warhammer Winter Assault | CBS012006DVD | 1 |
| Warhammer40000 Dawnof War2 | CBS072009DVDGold | 1 |
| Waron Terror Lsungsbuch | CBS022008DVDGold | 1 |
| Wchterder Nacht | CBS072006DVD | 2 |
| weapon jammed | CBS012005DVD | 1 |
| weapon name | CBS012005DVD | 1 |
| weapon status digit | CBS012005DVD | 1 |
| weapon unuseable | CBS012005DVD | 1 |
| WEBDESmart Surfer | CBS102006DVD | 8 |
| Werbung | CBS072005DVD | 12 |
| Werner Flitzkacke Alarm | CBS082006DVD | 1 |
| Wespenjagd 2 | CBS092001 | 1 |
| Wettendass Das DVDSpiel | CBS012007DVDGOLD | 1 |
| Wickie Ylvi ist entführt | CBS012009DVDSonder | 1 |
| Wikingerhelden | CBS112009DVDGold | 1 |
| Wild Life Park 2 | CBS022009DVD | 1 |
| Wildlife Park | CBS012006DVD | 3 |
| Win Expert | CBS042008DVD | 1 |
| Windchaser | CBS062008DVD | 1 |
| Wings of Wars | CBS122004DVD | 1 |
| Winpatrol2007 | CBS052008DVD | 1 |
| Winterschlachtinden Ardennen | CBS092006DVD | 1 |
| World Challenge | CBS082005DVD | 1 |
| World Champion Billard Featuring Gustavo Zito | CBS052006DVD | 1 |
| World Conflict | CBS052006DVD | 1 |
| World of Warcraft | CBS112004DVD | 3 |
| World Poker Championship 2 Final Table Showdown | CBS062008DVD | 1 |
| World Poker Championship2 Final Table Showdown | CBS062008DVD | 1 |
| World Racing | CBS062005DVD | 1 |
| World Racing 2 | CBS042005DVD | 3 |
| World War 2 Pacific Heroes | CBS072006DVD | 1 |
| World War Pacific Heroes | CBS072006DVD | 1 |
| Worldin Conflict | CBS012007DVD | 1 |
| Worldin Conflict Mod Kit | CBS042008DVD | 1 |
| Worldin Conflictv1006 | CBS052008DVD | 1 |
| Worldin Conflictv1009 | CBS102008DVD | 1 |
| Worldof Qin Collectors Edition | CBS102006DVDGOLD | 1 |
| Worldof Warcraftv | CBS092006DVD | 2 |
| Worms 4 Mayhem | CBS092005DVD | 1 |
| Worms Forts Unter Belager | CBS042005DVD | 1 |
| Wuchtel mit der Zauberfuchtel | CBS102005DVD | 1 |
| X Beyond the frontier | CBS102001 | 1 |
| X Blades | CBS072009DVD | 1 |
| X Mas Hockey | CBS012005DVD | 1 |
| X Men Legends 2 | CBS032006DVD | 1 |
| X2 Die Bedrohung | CBS042006DVD | 1 |
| X2 Die Rueckkehr | CBS012005DVD | 1 |
| X3 Reunion | CBS092005DVD | 2 |
| X3 Reunion v 1 2 01 | CBS022006DVD | 1 |
| Xfire | CBS102006DVD | 2 |
| XMen The Official Game | CBS092006DVD | 1 |
| Xpand Rally | CBS122004DVD | 1 |
| XReunion | CBS052006DVD | 2 |
| XReunionv | CBS062006DVD | 3 |
| XSki Alpin2005 | CBS032005DVD | 1 |
| Yahoo Messenger | CBS092008DVD | 1 |
| Yapala, Guatemala | CBS012005DVD | 1 |
| Yeti Sports Classic | CBS122005DVD | 1 |
| Yeti Sports Deluxe | CBS122005DVD | 1 |
| Z DBackup | CBS012009DVD | 1 |
| z ziemi | CBS012005DVD | 1 |
| Zeus Herrscher des Olymp | CBS122003 (CD1) | 2 |
| Zoo Empire | CBS112004DVD | 2 |
| Zoo Empire CBSVersionv | CBS112006DVD | 1 |
| Zoo Empire Tier Memory | CBS122004DVD | 1 |
| Zoo Empirev | CBS052006DVD | 1 |
| Zoo Tycoon 2 | CBS032005DVD | 1 |
| Zoo Tycoon 2 En Species | CBS022006DVD | 1 |
| Zoo Tycoon 2 v 20 11 00 | CBS042005DVD | 1 |
| Zosso Bowling | CBS072001 | 1 |
| Zweistein | CBS102008DVD | 1 |
| Zwlfzehn | CBS082006DVD | 1 |

</details>
