# Gebietsbericht: Wahrnehmung und Wissen

Grundlage: `AGENTS.md`, `.claude/rules/bausteine.md`, `kern.md`, `schichtanalyse.md`, Bauplan §15/§21/§24/§29/§38/§39. Messungen mit `.venv`, Skripte unter `review-wissen\`. Register gegengelesen — keiner der Befunde steht dort.

## Hoch

### 1 [hoch] Die Mutternfalle schneidet keine Mutterntasche — nur ihr Schraubenloch — VERIFIZIERT
`knowledge/parts/fasteners.py:378-387` — `shapes.hexagon`/`shapes.box` bauen von z=0 nach oben; der Bausteinursprung sitzt auf der Fläche, darüber ist Luft (§24.1 `MOUTH_AT_ORIGIN`). Sechskanttasche und Einschubschlitz liegen außerhalb des Materials; abgetragen wird nur das Schraubenloch (als einziges nach unten gebaut).

Gemessen (Quader 40×30×10, PLA, `face_top`): `screw_hole=True` → 90,53 mm³ (exakt das Durchgangsloch); `screw_hole=False` → 0,00 mm³ + `boolean.without_effect`. Tasche müsste 70,34 mm³ beitragen, Schlitz ~171. Bei `direction="bottom"` 35,17 mm³ (was die Drehung zufällig ins Material dreht). Die Teilwirkung des Lochs tarnt den Ausfall; `test_parts.py:607` misst den Rohkörper, nicht das Ergebnis am Träger.

Siebter Zwilling derselben Sache (dowel, snap_connector, magnet_pocket/keyhole/cable_gland, printed_thread) — `nut_trap` steht in derselben Datei wie `printed_thread` und trägt als einziger subtraktiver Baustein keinen der `MOUTH_AT_ORIGIN`-Einträge.

**Fix:** Tasche und Kanal von der Mündung nach unten (`-height`), `bore(...)` nachziehen; Schaft bleibt durchgehend. `PartChange` v6, `LIBRARY_VERSION` erhöhen, Test am Ergebnis am Träger.

### 2 [hoch] `screw_hole`: die Kopffreiheit tut nichts — VERIFIZIERT
`fasteners.py:160-162` — `shapes.cylinder` steht auf z=0 und wächst nach oben; die Kopffreiheit liegt über der Mündung, wird nirgends verschoben. Gemessen (M3, `face_top`): `head_room=0,0` und `=5,0` je 101,83 mm³ (Senkung an), je 90,53 (aus) — identisch, ohne Meldung. Der Kopf steht danach vor. **Fix:** Aussparung `0→-head_room`, Senkung+Schaft um `head_room` tiefer; Version + Test gegen π·(countersink/2)²·5.

## Mittel

### 3 [mittel] Bausteinbohrungen bekommen die Materialkompensation nicht — VERIFIZIERT
`fasteners.py:138`, `:392`, `mounting.py:287`, `:421-422` — überall `screw.clearance` roh. Regelsammlung `holes_oversize` und der Dateikopf versprechen die Materialtoleranz aus dem Profil; sie wird nicht aufgelegt. Gemessen (Nennweite 3,40): `drill_hole` → 3,543 (PLA)/3,593 (PETG)/3,693 (TPU), `insert_screw_hole(M3)` → immer 3,400. Zwei Wege, zwei Ergebnisse; nach Kalibrierung §28.3 rechnet nur `drill_hole` mit den gemessenen Werten. **Fix:** zweite Zuordnung `HOLE_FIELD → material.hole_compensation` über `ops._part_values`, Regel an eine Stelle; Versionen erhöhen.

### 4 [mittel] Zwei Merkmalszentren liegen gespiegelt außerhalb ihres Körpers — VERIFIZIERT
`mechanics.py:186-192` (`latch.ramp_1`), `:111-116` (`snap_fit.hook_1`) — Körper mit `turned(...,180°,(1,0,0))` umgeklappt, Merkmalsangabe nicht mitgedreht. Gemessen: `latch` Körper y=[-1,0]; `ramp_1 centre=(0,+0,5,1,5)` außerhalb; `snap_fit hook_1 centre` außerhalb. `_anchor`/`_direction_of` lesen genau dieses `centre`/diese Normale → Anbau um `2·depth` daneben, falsche Seite. **Fix:** Zentren/Normalen korrigieren; Test: jedes Merkmalszentrum im Hüllquader seines Körpers.

### 5 [mittel] Temperaturdeckelung ist still — Docstring behauptet das Gegenteil — VERIFIZIERT
`knowledge/print_settings.py:226-242`, `slice/advise.py:324-336,184-185` — `_temperatures` sagt „advise sagt es auch"; tut es nicht. **Bett:** keine Regel zur Bettdeckelung; Bambu A1 mini (max 80) + ABS/ASA (will 100) → Vorschlagsliste leer, ABS löst sich. **Düse:** Regel feuert gegen bereits gedeckelten Wert, `_merged` wirft wirkungslose Vorschläge weg. **Kammer:** Zweig unerreichbar, weil `resolve` `chamber` schon auf 0 gesetzt hat. 22/96 Kombinationen werden gedeckelt. **Fix:** `resolve` gibt Gekapptes zurück, `warnings_for` macht daraus einen `Finding` (kein `SettingAdvice` — es gibt keinen Wert, der es behebt); Docstring mitkorrigieren.

### 6 [mittel] `to_scad()` ist gebaut, getestet und von nirgendwo erreichbar — VERIFIZIERT
`knowledge/parts/scad.py:31` — außerhalb der Datei nur ein Kommentar in `recipe.py:32`; Aufrufer nur im Test. Kein Menü, kein Katalogknopf, kein CLI. AGENTS.md-Checkliste Punkt 4 und Bauplan §24 verlangen es, `ROADMAP.md:391` hakt es ab — Testart „Anschluss" (die Anwendung tut es, nicht der Cache). Zweitens ruft `to_scad` `spec.fn(values)` ohne Herkunftsprüfung — ein Rezept liefe durch (bausteine.md: „für Rezepte gibt es to_scad nicht — benannt, nicht umgangen"). **Fix:** Katalogeintrag „Als OpenSCAD speichern", `if spec.build_with_profile: raise` mit Handlungsvorschlag; sonst Registerpunkt wieder öffnen.

### 7 [mittel] Zwei Bausteine liefern Merkmale, die sie nicht deklarieren — VERIFIZIERT
`mechanics.py:500` (`snap_connector`, deklariert `arm,catch`, liefert im Pin-Fall `hook`), `testbodies.py:100` (`fit_ladder`, deklariert `pin,bore`, liefert `face`). `PartSpec.features` ist der Provenienz-Vertrag (§24.1), den `find_part` dem Agenten nennt; `_check` prüft nur Nichtleere. **Fix:** Deklarationen ergänzen, Test über die Ecken (Ergebnis-Stämme ⊆ deklariert).

## Gering

- **8** Vier `face`-Merkmalszentren in Körpermitte statt auf der Fläche (`structure.py:602,185-187,266-273`, `mechanics.py:110`); im Hüllquader, aber wirken über `_anchor`/`feature_vector`. Test: Zentrum ≤ Facettenbreite von der Oberfläche.
- **9** `Insert.outer == hole` bei allen sechs Buchsen (`data/standards.toml:197-237`) — nachweislich falsch (Kommentar sagt es selbst), heute nur nicht gelesen, aber öffentlich für Agent/Rezept/künftige Bausteine. Fix: Feld weglassen oder nachmessen. (Alle anderen Normmaße stichprobengeprüft korrekt.)
- **10** Steckbrief nennt das Material auch ohne Abweichung (`perceive/digest.py:190-193`) — Kommentar beschreibt eine Bedingung, die im Code fehlt.
- **11** `LIBRARY_VERSION` steht auf 6, Kommentar erklärt bis 4 (`parts/registry.py:445-451`); §24.4. Fix: aus `PartChange` ableiten.
- **12** `profile_tongue`: Kopfhöhe darf über die Kammertiefe hinaus (`structure.py:314-325,361`), wird nicht gekappt (anders als `lead_in`/`foot`); baubare Feder, die nicht in die Nut geht. Fix: `min(...)`.

## Geprüft und in Ordnung
Stabile IDs über translate/rotate (9 Kennungen erhalten); Bohrungserkennung durch/sackloch inkl. Bodenfläche; Mehrdeutigkeit hält an (Rivalenlogik, `AMBIGUITY_FLOOR`, `resolve→None`); `auto:`-Auflösung aller FitKind + ValidationError-Liste; Normteiltabelle (ISO 4762/4032/273/7089, Kernlöcher, Steigungen, Lager, Magnete) durchweg korrekt; `print_settings` 96 Kombinationen lückenlos + `material_without_profile`; alle 23 Bausteine wasserdicht/positiv/richtungsrichtig (bis auf nut_trap/head_room); Kerngrenze (kein Qt/eval/exec/pickle), `user.py` über importlib mit Abdruck; Rezepte (`capture` weist Leeres ab, `travelling_parts` filtert `source==user`, `check.py` warnt vor Quelltext).

**Kann das so rein: nein** — die beiden hohen Befunde sind stille Totalausfälle zugesagter Funktionen im meistgenutzten Baustein-Bereich; je `PartChange`, erhöhte `LIBRARY_VERSION` und Test am Träger.
