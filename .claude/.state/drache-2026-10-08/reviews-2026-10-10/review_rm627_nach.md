# Nachprüfung RM-627 (F:\sl-befund, befund/kleine-ueberhaenge bis 0d165ce42)

Agent solidon3d-review, 10.10.2026. Gegenstand sind die Behebungen `c2eaf3105`, `eae68b550`,
`a179d8188`, `9128d0995` und `0d165ce42` auf `88f6dcfa6`. Grundlage: das Erstreview
`reviews-2026-10-09/review_rm572_nach_rm627.md` und der Bericht des Bauagenten
`berichte-2026-10-10/rm627.md`. Den Diff `88f6dcfa6..0d165ce42` (21 Dateien, +712/−69) habe ich
ganz gelesen.

Die Sonden liegen im Scratchpad der Sitzung unter `rv627n/`. Alter und neuer Stand sind dort per
`git archive` ausgepackt (`alt`, `neu`), beide mit dem übersetzten Schichtkern `_chain` des
Hauptklons. Der Worktree hat keinen eigenen, deshalb liefen die Zahlen des Bauagenten auf dem
NumPy-Rückfall. Gegenproben habe ich in der Kopie `mut` gefahren, den Zuschnittversuch in `clip`.
Im Worktree ist nichts geändert, `git status` ist leer. Zeiten sind CPU-Zeit des Prozesses,
gepinnt auf 0xFFFFF0FF, Wanduhr nur genannt. Die Maschine war voll belegt.

## Erstbefunde: alle behoben

| Erstbefund | Stand | Beleg |
|---|---|---|
| 1 mittel: Flanke verbindet Rand und Sporn | behoben | A1 6,2 mm statt 40,1, kein Rat und kein Bericht (`band_neu.txt`). Flanken an zwei Seiten mit Konsole und Steg 20 mm: 20,0 mm am Steg (−31,1; 0,0), alt 40,1 an der Konsole (G2, `flanke_*.txt`). Gegenprobe ohne Kernfilter macht 3 Tests rot (M1). |
| 2 mittel: `support_ways` las `quiet_layers` | behoben | Test über `_load_module`; ohne Ränder in `quiet` rot (M11) |
| 3 mittel: `span_beside` ungemerkt, ohne Abbruch | behoben bis vier Körper | Merker je Schnitt, Schicht und Auswahl; Abkürzung `whole`. Schlüssel ohne Auswahl rot (M2), `whole` immer oder nie rot (M3, M4). Ab fünf Körpern siehe L1. |
| 4 leicht: Korpusbeleg | behoben | Stichprobe mit der Sonde des Bauagenten (Arbeitsplattenreiniger, Wedge-Lock, Minigolfbahn, Bohrmaschinenhalter): gleich `real_text.jsonl`. Gegen `real_korpus.jsonl` kommt nur der neue Kanalmerker dazu (Minigolfbahn ja). |
| 5 leicht: Changelog gegen v0.5.3 | behoben, stimmt | v0.5.3 kennt keine Ränder; `_may_need_support` zählte jede Schicht über 15 mm außer Kanalschichten, `_from_spans` warnte mit „oder eine Stütze hilft“ auch über Kanälen (`git show v0.5.3`). Beide Punkte sind zu Recht als Behebung formuliert. Die Längen hält `test_changelog` grün. |
| 6 leicht: Begründung | behoben | `regel-druckrat.md` unter „Ränder tragen sich selbst“ und „Eine Decke im Kanal“ |
| Neben 1: „oder eine Stütze“ über einem Kanal | behoben | Kanaltext; D2 und D4 zeigen jetzt auf den Steg (45; 0); Minigolfbahn mit Kanaltext; drei Gegenproben rot (M8, M12, M13) |
| Neben 2: Kanalfrage ohne Abbruch | behoben | 2 008 Abfragen am Drachen (60°), längster Abstand 0,39 s Wand; Abbruch nach 0, 1, 3, 10 oder 40 Abfragen wirft und merkt nichts, der zweite Lauf ist gleich (`merker_neu.txt`). Alle neuen Abfragen entfernt: rot (M5). |

## Neuer Code

- **`_widest_bridge`, falsch negativ?** Nein, nicht durch den Kernfilter. Ein Kern liegt
  wenigstens `bridge_from/2 + 0,05` von der Schicht darunter, also in genau einem
  Überhangstück. Gefiltert wird nur, was in Rand- oder Kanalstücken liegt. Eine echte Brücke
  neben einem Rand bleibt gemeldet: gerade Wand 19,9 mm, zwei Flanken 20,0 mm, Steg neben dem
  Tunnel 20 mm am Steg, B unverändert 44,7. Ob der Rat die Brücke auf dem Modell sieht
  (`open_bridge_width`), ist alt und neu gleich: Wedge-Lock Set 25,607, Base 26,121,
  Waschschüssel 55,702, Drache 60° 15,380, Arbeitsplattenreiniger 0 (`offen.txt`). Falsch
  negativ ist der **Lochzweig**, und das schon seit v0.3.0, siehe N1.
- **Merker in `span_beside`.** Der Schlüssel ist (Schichttupel, Schicht, Auswahl der eigenen
  Stücke) und damit vollständig. `bridge_from` hängt am Schichttupel; kein `replace` auf
  `SliceResult` teilt Schichten (grep). Fäden: 24 gleichzeitig in drei Runden, Antworten gleich
  der ungemerkten Messung `_measured_beside`, keine Fehler, höchstens vier Plätze. Mit und ohne
  Merker bitgleich. Gemessen wird außerhalb des Schlosses, eingetragen erst nach vollständiger
  Messung.
- **`cancelled` bis `_model_support`** wirkt und hinterlässt keinen halben Zustand (oben).
  `span_spot` misst im Ort des Kanalfalls ungemerkt und ohne Abbruch. Das ist eine Messung je
  Bericht, ohne Befund.
- **Kanaltext mit `_may_span`.** Ein ungefragtes Stück als offen zu zählen ist richtig. Weite und
  Hüllbox der Spanne liegen im um `bridge_from` erweiterten Hüllrechteck des Stücks, also trägt
  ein ungefragtes Stück keine Spanne über 15 mm. Es ändert weder die Kanalentscheidung noch Ort
  oder Weite. Kerne verschiedener Stücke verschmelzen nicht. Eine Spanne aus dem Lochzweig kann
  größer sein als jedes Stück; dann fällt der Text auf den alten zurück, also auf der sicheren
  Seite. Die Schleife bricht ab, sobald keine Schicht die beste Weite mehr übertreffen kann
  (Weite fällt nur). An einer Rampe mit 26 und 50 spannenden Schichten stellte der Bericht je
  eine Kanalfrage, 0,12 bzw. 0,16 s (`rampe.txt`).
- **`matrix_unit.support_ways`** zählt wie der Stützbedarf. Die Randfrage stellt es nur, wo etwas
  spannt, und die Kanaldecken kommen aus `need.model`. Das passt, weil `asked` falsch nur ist,
  wenn keine Schicht über 15 mm spannt.
- **Regeln** 1, 6 (keine `==` auf Fließkomma im Kern; `is_close` in `channel_pieces`), 7, 14,
  17 (beide Texte mit *Stützbedarf zeigen*), 20 (Text über `_()`, fünf Kataloge), 21 und 22 sind
  am Diff eingehalten. Bezeichner sind englisch, Kommentare deutsch mit Umlauten.

## Leistung (Regel „gebündelt rechnen“)

**Wann läuft der kalte Fall im Kundenweg?** `print_findings` fragt `support_need` nur bei
höchstens acht Körpern und ab 1 cm³ Stützraum (`findings.py:197, 232–236`). Sonst stellt
`_from_spans` die enge Kanalfrage selbst (`channel_pieces` → `model_support(only=…)`). Das
betrifft jeden Körper mit einer Schicht über 15 mm ohne Ränder und einem Stück, das weiter
spannen kann. Der Bericht läuft nach jeder Auswertung in einem Arbeitsfaden
(`print_findings_flow.py`) und ist abbrechbar. Die Wartezeit auf den Abbruch liegt unter 0,4 s.

| Messung (Wechsel alt/neu, CPU) | alt `88f6dcfa6` | neu `0d165ce42` |
|---|---|---|
| Drache 45°, `_from_spans` kalt | 2,69 / 2,78 s | 20,69 / 20,42 s (Kanalfrage 17,9 / 17,6 s, ein Stück) |
| Drache 60° (CC2), `_from_spans` kalt | 0,30 / 0,34 s | 7,05 / 7,02 s (Kanalfrage 6,7 / 6,7 s) |
| Schachsatz Wizard Tower, 10 Körper (zwei Kopien), Bericht ganz kalt | 118,9 s | 116,5 s (Brückenbefund 0,00 s, keine Kanalfrage: keine Figur spannt) |
| derselbe, Bericht nach derselben Auswertung | 0,8 s | 0,8 s |
| Wedge-Lock (Set), 419 mm³ Stützraum (kalter Weg), Bericht kalt | 0,34 / 0,34 s | 0,45 / 0,41 s (eine Kanalfrage, 0,02 s) |
| Minigolfbahn `obj_1_Birleştir`, 2 846 mm³, Bericht kalt | 11,7 / 12,2 s | 11,9 / 11,0 s (Kanalfrage aus dem Merker, Kanaltext) |

Befunde, Weite, Höhe und Schichtzahl sind gleich. Der Ort am Drachen wandert von (41,24; 15,24)
nach (39,37; 21,37); bei 45° kommt der Kanaltext. §31 hat für den Prüfbericht keinen Zielwert.
Ein Budget ist damit nicht verletzt, der Hauptfaden ist nicht betroffen.

**Bündelnder Fix, gemessen** (`clip.txt`). Der Abstieg in `_model_support.descend` zieht jede
Säule Schicht für Schicht von der ganzen Schicht darunter ab. Die enge Frage für (326, 4) fragt
die ganze Decke, 108 Säulen über 326 Schichten. Im Versuch habe ich je Säule die Schicht auf ihre
Hüllbox plus 1 mm zugeschnitten (`shapely.clip_by_rect` auf `_shared`, dann `_material_cross`,
dann die Differenz). Ergebnis: Drache 45° 18,1 → 8,2 / 8,4 s, Drache 60° 6,4 → 2,7 / 2,6 s.
Kanäle, Kanalfläche, offene Stücke und Säulen sind bitgleich (`13.82804634106725`,
`0.01705993044339671`). Den Rest kostet der Zuschnitt der ganzen Schicht je Säule. Ein festes
Raster je Schicht (Fenster wie `analysis.py:2008`) wird nur einmal geschnitten, und die Rechtecke
hängen nur an der Säule. Damit bleiben enge und volle Frage bitgleich, und es sollte deutlich mehr
bringen. Derselbe Abstieg kostet `support_need` am Drachen 446–472 s. Der Fix gehört deshalb in
den schon gemeldeten neuen Punkt (KOORDINATION: „`support_need` braucht Minuten … Säulenabstieg“,
nach RM-626/RM-584), nicht in diesen Zweig.

## Befunde

### Leicht

**L1. Im kalten Weg wiederholt sich die Kanalfrage nach jeder Auswertung.**
`analysis.py:3649` (`_ANSWERS_KEPT = 4`), gerufen über `channel_pieces` (`analysis.py:3627–3643`)
aus `advise.py:2465`.

- *Was falsch ist:* Der kalte Weg setzt mehr als acht Körper voraus, der Merker hält vier
  Antworten. Jeder weitere Körper mit spannender Schicht legt eine enge Antwort ab und verdrängt
  den Drachen.
- *Beleg:* Drache (60°) und acht Wedge-Locks, `located_warnings` in zwei Runden: Runde 1 6,5 s,
  Runde 2 wieder 6,4 s, je neun Kanalfragen, eine davon der Drache. Mit drei Wedge-Locks kostet
  Runde 2 0,2 s ohne Kanalfrage (`verdraengt.txt`). Bei 45° wären es rund 18 s je Auswertung
  statt 2,7 s. Dieselbe Grenze trifft `_BESIDE` (Erstbefund 3) ab fünf Körpern mit Rand auf einer
  spannenden Schicht. Die enge Randfrage wird ohnehin nie gemerkt, das kostet alt und neu
  2,7 s (45°).
- *Warum es nicht schwerer wiegt:* Es läuft im Arbeitsfaden, ist binnen 0,4 s abbrechbar, und
  §31 nennt keinen Zielwert. Betroffen sind nur große Körper in Szenen mit mehr als acht Körpern;
  Schachsatz, Wedge-Lock und Minigolfbahn zeigen nichts. Der eigentliche Hebel ist der Abstieg in
  fremdem Gebiet (siehe oben).
- *Fix:*
  1. Messwerte und die Wiederholung im kalten Weg in den gemeldeten neuen Punkt zum Säulenabstieg
     aufnehmen (Zuschnitt je Säule gemessen 2,2–2,4×, bitgleich; Raster je Schicht als Ziel).
  2. Den Archivsatz „Kalt am Drachen 45° 21 statt 3 s“ (`ROADMAP-ARCHIV.md`, RM-627, Abschnitt
     *Kanaldecke*) ergänzen: Bei mehr als vier solchen Körpern zahlt jeder Bericht das erneut.

**L2. Der Abbruch im Bericht ist ungetestet.**
`advise.py:2441`, `advise.py:2472`, `analysis.py:3523`, `analysis.py:4236`.

- *Beleg:* Die Gegenproben bleiben grün (`mut.txt`, je 58 von 58):
  - M6: `channel_pieces(…, cancelled=None)` im Bericht;
  - M6b: `span_beside` im Bericht ohne `cancelled`;
  - M14: eine abgebrochene `span_beside`-Messung wird als 0 gemerkt;
  - M5b: der Abstieg ohne Abfrage. Der einzige Test bricht dann in der Kreisfrage ab, nach dem
    teuren Abstieg (am Drachen bis 18 s).
- Das Verhalten stimmt nach Sonde, nur hält es kein Test fest.
- *Fix:* Zwei Tests. Erstens Tunnel mit gemerkter voller Randfrage, Token bricht nach *k*
  Abfragen ab: `located_warnings` wirft, kein Eintrag in `_ANSWERS` oder `_BESIDE`. Zweitens
  Flankenwand mit Konsole und Steg: `span_beside(…, cancelled=abgebrochen)` wirft und merkt den
  Schlüssel nicht. Für den Abstieg ein Zähler-Token, das in `descend` vor der Kreisfrage
  abbricht.

**L3. Der Docstring von `_from_spans` ist veraltet** (`advise.py:2406–2419`).

- *Was falsch ist:* Er sagt noch „Was hilft, ist die Geometrie … oder eine Stütze. Beides
  entscheidet der Nutzer“ und „Jetzt ist es die Mitte der größten freien Fläche dieser Schicht“.
  Über einem Kanal rät der Befund jetzt nur zum Übergang. Der Ort liegt an der gemessenen Brücke
  (`_bridge_place`, `span_spot`), sonst an der größten freien Fläche, die ein übriges Stück
  berührt.
- *Fix:* Zwei Sätze nachziehen.

### Nebenbefund (nicht vom Zweig, seit v0.3.0, mittel), neuer Punkt

**N1. Der Lochzweig der Brückenmessung misst bei geschlossenen Ringen falsch, in beide
Richtungen.**
`analysis.py:2659–2661` (`holes` → `spans = [hole.difference(supported) …]`), eingeführt mit
`11d3f0698`, enthalten ab v0.3.0. Beleg `flanke_*.txt`, `hohl_*.txt`, alt und neu gleich:

- **Falsch negativ.** Eine Wand mit Flanke ringsum (30°, das freie Band ist geschlossen) und ein
  Steg 3 mm über 20 mm an der Flanke ergeben `bridge_width` 0,0. Es gibt keinen Stützbedarf,
  keine Warnung und keinen Rat, mit und ohne Konsole (G3, G4). Dieselbe Wand mit Flanken an zwei
  Seiten ergibt 20,0 mm, Stützen und Warnung (G6). Grund: Die freie Fläche hat ein Loch, und
  gemessen wird nur das Loch abzüglich `supported`, also nichts. Der Steg wird nie gemessen.
- **Falsch positiv.** Ein Rohr (außen 50, innen 40 mm) mit Flanke 30° außen und einem Sporn von
  6 mm ergibt `bridge_width` 39,3 mm, also den Hohlraum. Die Folge sind Stützbedarf, der Bericht
  „Hier spannt eine Decke frei“ mit 39,3 mm am Sporn und der Rat `support.style=auto` (H5). Ohne
  Flanke (H2) und ohne Sporn (H4) bleibt alles still. Grund: Das Loch des Bandes umfasst Wand und
  Hohlraum; der Hohlraum ist Luft auf jeder Schicht und wird trotzdem als Brücke gemessen.
- **Zum Zweig:** Der Kernfilter von RM-627 gilt nur im Zweig ohne Loch. Der Docstring von
  `_widest_bridge` („Je Kern … Ein Kern liegt dagegen ganz in einem Überhangstück“) gilt dort
  nicht. In den spannenden Schichten der echten Schnitte (Waschschüssel, Arbeitsplattenreiniger,
  Drache) kam der Lochzweig nicht vor (`ring*.txt`). Becher, Vasen und Töpfe mit
  ausgestellter Wand sind aber genau diese Form.
- **Vorschlag neuer Punkt:** Den Lochzweig nur dort messen, wo der Innenrand des Rings frei ist
  (Schulter über einer Öffnung). Liegt er an `supported`, wird die Fläche wie ohne Loch je Kern
  gemessen. Kerne ohne eigenes Loch zusätzlich messen. Tests:
  - G4 meldet 20 mm;
  - H5 meldet nur den Sporn (unter 15 mm, also nichts);
  - Gewürzbehälter und Pilz bleiben unverändert.

### Beobachtungen ohne Befund

- Bei Schnitten ohne gemerkte volle Kanalfrage fragt der Bericht je untersuchter Schicht eine
  eigene enge Kanalfrage, und jede rechnet die ganze Decke. An echten Modellen und an der Rampe
  blieb es bei einer Frage, weil die Schleife früh abbricht.
- Drache 45° bekommt jetzt den Kanaltext an der Tasche (326, 4). Das passt zum Rat, der die
  Tasche als Kanal sperrt. Das Archiv nennt den Kanaltext nur für die Minigolfbahn, weil der
  Korpus mit CC2/60° lief.

## Läufe

- Unterlagen: `test_translations`, `test_wording`, `test_changelog`, `test_directory_docs`,
  `test_roadmap`, `test_language_rules` im Worktree (ohne Cache, ohne Bytecode): 796 passed,
  4 skipped, Exit 0 (`t_docs.txt`).
- Code: `test_slice_findings`, `test_print_findings`, `test_advise`,
  `test_delivery_matrix_review`, `test_slice`, `test_orientation_search`, `test_print_settings`,
  `test_maps`, `test_estimate`, `test_facts`, `test_geometry_findings` am Stand `neu` mit
  `_chain`, `-n 3`, ohne Fenster: 1 536 passed, 4 skipped, Exit 0 (`t_code.txt`). Laut
  `affected_tests.py` ist das die Suite, daher gezielt gewählt.
- Gegenproben (`mutant.py`, 58 ausgewählte Tests): rot sind M1, M2, M3, M4, M5, M7, M8, M9, M10,
  M11, M12, M13; grün bleiben M5b, M6, M6b, M14 (L2). Alle Läufe Exit 0.
- Sonden mit Exit 0: `band_neu.txt`, `flanke_alt/neu.txt`, `hohl_alt/neu.txt`, `merker_neu.txt`,
  `offen.txt`, `kalt_drache.txt`, `schach.txt`, `klein.txt`, `clip.txt`, `verdraengt.txt`,
  `rampe.txt`, `korpus_stich.txt`.
- Der Fall `test_every_manual_paragraph_reaches_the_generated_page` war nicht in der Auswahl
  (`rendered` abgewählt).

## Urteil

**Kann landen.** Alle drei mittleren und drei leichten Erstbefunde sowie beide Nebenbefunde sind
behoben, am Code und mit eigener Gegenprobe belegt. Der neue Code hält seinen Vertrag; Merker,
Fäden und Abbruch sind sauber. L1 bis L3 sind leicht: L2 und L3 gehen ohne weitere Prüfung mit,
L1 als Zahl in den gemeldeten Punkt zum Säulenabstieg. N1 ist ein eigener neuer Punkt aus der
Zeit vor dem Zweig.
