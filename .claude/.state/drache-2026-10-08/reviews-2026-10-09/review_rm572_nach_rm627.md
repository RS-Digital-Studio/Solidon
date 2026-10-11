# Nachprüfung RM-572 und Review RM-627 (F:\sl-befund, befund/kleine-ueberhaenge bis 88f6dcfa6)

Agent solidon3d-review, 09.10.2026 nachts. Rechner durchgehend zu 100 % ausgelastet (32 logische
Kerne, rund 100 Python-Prozesse anderer Sitzungen), Zeiten sind CPU-Zeit. Sonden im Scratchpad der
Sitzung unter `rv627/` (`probe_band.py`, `probe_real.py`, `probe_spans_cost.py`, `probe_warm.py`,
`probe_fixidee.py`, `probe_matrix.py`, `mutant627.py`); der alte Weg aus e638cbab9 ist dort wörtlich
nachgebaut und läuft auf demselben Schnitt. Im Baum nichts geändert.

## RM-572 — Urteil: kann rein

Alle sechs Befunde des ersten Reviews sind behoben, am Code und mit Tests belegt:

1. (schwer) `findings.py:467` fragt `worth_support(need.patch, need.overhang)`. Inselstücke
   (`_on_island`, Z. 528–535, dieselbe Regel wie `overhang_findings` Z. 403), Kanaldecken und Ränder
   (Z. 471) zählen weder in Fläche noch Ort; mit Inselstücken wird der Weg ohne sie neu gefragt
   (Z. 491–508), danach mehr als 100 mm² verlangt (Z. 509). Würfel 12/20 mm nur Insel, zwei Brücken
   nur `long_bridge`, Kinn mit Insel behält das Feld — über `print_findings`.
2. (mittel) Bedarfsfrage nur unter der Bedingung der Lagensuche (`findings.py:232–236`), Test mit
   verweigerter `support_need`; das Archiv nennt die Zahlen.
3. (mittel) Anschluss über `print_findings`: Ort im Kinngrundriss, y gegen die Höhe der Unterseite,
   `map_for == "overhang"`, Gegenfälle aus 1.
4.–6. (leicht) Ränder im Ort ausgenommen (Kragentest), fr „surplombs“, it „sbalzi“ in Katalog und
   Changelog, Begründung nachgezogen.

Gegenprobe Drache (`obj3.stl`, generic-220/PLA, 45°): Befund bei z 102,75 mit 630,6 mm² an
(−4,80; −4,85), wie im Archiv, 0,06 s CPU. Die Docstring-Zahlen 23,7 und 1 492 mm² nachgerechnet:
23,8 und 1 492,5. Kein neuer Befund. Beobachtung ohne Befund: Ein Steg über 25 mm mit 0,6 mm
schräger Unterseite bekommt `small_overhangs` und `long_bridge` an derselben Stelle — dasselbe Paar
wie `large_overhang` und `long_bridge` bei flacher Unterseite (`probe_schraegsteg.py`).

## RM-627 — Urteil: nicht

### Mittel

1. **Ein Rand, der über eine Schrägflanke mit einem anderen Stück zusammenhängt, zählt weiter als
   lange Brücke** (`analysis.py:2610–2611`, gerufen von `span_beside` Z. 3447–3452; ebenso
   `open_bridge_width`). `touching` wählt freie Flächen (Schicht minus Schicht darunter um 0,05 mm),
   nicht Stücke. Eine Flanke zwischen etwa 14° und 45° legt je Schicht ein Band frei (Versatz über
   0,05, unter der Zugabe von 0,2 mm, also kein Überhangstück), das alle Stücke daran zu einer freien
   Fläche verbindet; deren Kerne werden danach einzeln gemessen, der des Rands mit. Beleg
   `probe_band.py` A1: Wand mit zwei Flanken unter 30°, Konsole 2,5 mm (Rand) und an der
   Nachbarflanke ein Sporn 6 mm (8,8 mm²): `bridge_width` 40,1, `span_beside` 40,1; Rat
   `support.style=auto`, Bericht `slice.long_bridge` 40,1 mm, Ort (−21,2; 3,5) an der Flanke.
   Dieselbe Konsole mit dem Sporn an der senkrechten Wand (A4) oder an einer Säule (A0, A3): 6,1 mm,
   keine Stützen, keine Warnung. Regel (`druckrat.md:72–75`, „je Stück, nicht je Schicht“) und
   Changelog versprechen mehr, als der Code hält. Im Korpus kein Fall (siehe 4).
   Fix: Mit `touching` in `_bridge_width` zusätzlich nur die Kerne messen, die `touching` berühren
   (Zweig ohne Löcher, Z. 2643–2646). Ein Kern liegt in genau einem Überhangstück — jeder seiner
   Punkte ist mindestens `bridge_from/2 + 0,05` mm von der Schicht darunter, bei 0,2-mm-Schichten
   jenseits der Zugabe —, damit ist es „je Stück“. Im Prozess gegengeprüft (`probe_fixidee.py`): A1 6,2 mm, kein Stützbedarf, keine
   Warnung; A0, A3, B, C1, C2, D3, D4 unverändert. Den Ort der Warnung an den gemessenen Kern legen.
   Test mit der Flankenwand aus A1.

2. **`tools/matrix_unit.py:702` liest das entfernte `need.quiet_layers`.** `support_ways` wirft
   `AttributeError: 'SupportNeed' object has no attribute 'quiet_layers'` (`probe_matrix.py`, am Zweig
   nachgestellt). `matrix_unit.py:1499–1504` fängt es, schreibt `advice_error` und setzt `taken = None`:
   Die Matrix der Gesamtprüfung verliert in jeder Kombination „vorschlaege“ und „stuetzen_auto“, und
   die Tabelle „Stützbedarf gegen das Urteil des Slicers“ (`matrix_report.py:430–470`) bleibt leer.
   mypy prüft nur `app` (`pyproject.toml:285`), kein Test ruft `support_ways`; das Archiv sagt das
   Gegenteil (`ROADMAP-ARCHIV.md:27353`, „sie hatten keinen Leser mehr“).
   Fix: Brückenliste mit `span_beside(result, index, need.model.channels | ledges(result))`, Schlüssel
   `bridges_over` und `bridge_max` bleiben; Test in `test_delivery_matrix_review.py` über
   `_load_module`, der `support_ways` an einem kleinen Schnitt ruft; Archivsatz berichtigen.

3. **Der Prüfbericht misst bei jedem Lauf Brückenweiten neu, ohne dass sich im Korpus etwas ändert**
   (`advise.py:2434`, `analysis.py:3447`). `LayerInfo.bridge_width` kommt einmal aus dem Schnitt;
   `span_beside` misst jede spannende Schicht mit Rand erneut, ungemerkt und ohne Abbruch
   (`located_warnings` hat kein `cancelled`), und der Bericht läuft nach jeder Auswertung
   (`print_findings_flow.py:3`). Waschschüssel (`washing bowl v1.stl`, 215 074 Dreiecke, C2/PLA):
   `_from_spans` 2,5–3,1 s statt 0,00 s, davon 2,78 s eine Schicht (265, 76,2 mm, Weite unverändert);
   der warme Prüfbericht im Wechsel 4,06/4,08 s statt 1,80/1,25 s CPU mit gleichen Befunden
   (`probe_warm.py`). Drache 0,34 s (45°) bzw. 0,45 s (C2, 60°) statt 0,02 s; Eiffelturm 0 (alle sechs
   spannenden Schichten nur Ränder und Kanaldecken). Im Stützbedarf selbst kostet es an diesen
   Modellen nichts, Inseln und Flächenweg kürzen `any` vorher ab.
   Fix: die Antwort je Schnitt merken wie `ledges` und `model_support` (Identität von
   `result.layers`, Menge `quiet`), danach die Waschschüssel erneut messen.

### Leicht

4. **Beleg im Commit und Lücke im Archiv.** 88f6dcfa6: „An Eiffelturm, Becher, Waschschüssel und
   Datei-Schnitt ändert sich nichts.“ Drei der vier Schnitte (`rm571fix/becher60.pkl`,
   `schuessel60.pkl`, `datei60.pkl`) sind mit `detail="support"` geschnitten und tragen auf keiner
   Schicht eine Brückenweite (`pkl_bruecken.txt`: 0 von 300, 575, 1 000) — dort konnte sich nichts
   ändern. Nachgeholt mit vollem Schnitt (`probe_real.py`, C2/PLA): 39 Körper aus 20 Korpusdateien und
   der Drache in zwei Profilen, 41 Läufe, 7 mit spannender Schicht, 4 davon gemischt; Stützbedarf und
   Brückenweite an keinem geändert; nur am Arbeitsplattenreiniger (`countercleaner.3mf`) wandert der
   Ort der Warnung (23,1 mm, z 0,35) vom Rand (73,6; 51,3) an das gemessene Stück (11,8; −34,9) — eine
   Verbesserung. Die Begründung „Kein Slicerlauf“ (`ROADMAP-ARCHIV.md:27361`) nennt nur Ränder; der Rat
   ändert sich auch, wo eine Kanaldecke neben einem kurzen Steg liegt (D3: Tunnel 20 mm und Steg über
   12 mm auf dem Bett, vorher Stützen, jetzt keine — folgerichtig zur Kanalregel).
   Fix: Archivabschnitt RM-627 um Korpusbeleg und Kanalfall ergänzen.

5. **Changelog gegen v0.5.3** (`changelog/de.md:110`, en:85, es:86, fr:86, it:85, pt:85). Der Punkt
   beschränkt sich auf „neben einem anderen Überhang“. In v0.5.3 gab es keine Ränder (`ledges` fehlt,
   `_from_spans` warnte an jeder Schicht über 15 mm): Der Kunde sah die Warnung auch an der Konsole
   allein, und der Abschnitt 0.6.0 sagt nirgends, dass das vorbei ist.
   Fix: „Ein schmaler Rand, der sich selbst trägt, gilt nicht mehr als lange Brücke, auch neben einem
   anderen Überhang. …“ in allen sechs Sprachen (de 191 Zeichen). Längen jetzt de 185, en 178, es 157,
   fr 178, it 167, pt 167, `test_changelog.py` grün.

6. **Begründung nicht nachgezogen** (`konzepte/begruendungen/regel-druckrat.md:447–449`): „Eine
   Schicht, deren Überhang nur aus Rändern besteht, spannt deshalb wirklich keine Brücke … Rat und
   Bericht schweigen dort gleich“ beschreibt den schichtweisen Stand; der Anlass von RM-627 (Kinn mit
   Kragen 46,2 mm, U-Kragen mit Sporn) fehlt unter der Überschrift, auf die `druckrat.md:9–11`
   verweist. Fix: zwei Sätze dort.

### Bestätigt

- `span_beside` ist nie größer als `bridge_width` (Teilmenge der freien Flächen): Rat und Bericht
  können nur Stützen und Warnungen verlieren, keine neuen bekommen. Brücke neben Rändern (C1: zwei
  Wände mit Konsolen, Steg 3 mm über 20 mm daneben): 19,9 mm am Steg (16,0; 0,0) statt 30,1 an der
  Konsole. Nur Ränder und ein Sporn (C2): keine Stützen, keine Warnung. Kanaldecke neben echter
  Brücke: Steg über 20 mm verlangt weiter Stützen (D4); die Warnung zeigt dort auf die Kanaldecke
  (gleiche Weite 19,9 mm), weil der Bericht nur Ränder ausnimmt — vorbestehend. Brücke, die an den Rand grenzt
  (B, T aus Konsole und Steg): ein Stück, kein Rand, unverändert 44,7 mm — die Diagonale des T statt
  der 20 mm des Stegs, vorbestehend (`_supported_span` ohne beidseitig getragene Richtung). Mehrere
  Stücke je Schicht: Drache Schicht 326 mit 15 Stücken, die 15,4 mm kommen aus dem übrigen Stück
  (8,5 mm²), richtig (`probe_schicht.py`).
- Gegenproben nachgefahren (`mutant627.py`): Schichtweite statt `span_beside` macht alle drei
  Rändertests rot, der Ort ohne Flächenwahl den Brückentest. Sollwerte aus der Konstruktion.
- Regeln 1, 6, 7, 14, 17, 20, 22 am Diff eingehalten. ruff und Format grün. Gezielt gefahren:
  `test_slice_findings.py` 160, `test_print_findings.py` 18, `test_advise.py` 98, `test_changelog.py`
  48 (+1 übersprungen), `test_directory_docs.py` 13 (+3), `test_language_rules.py` 467 — alle grün.
- **Slicerlauf nicht nötig.** An keinem Korpuskörper ändert sich der Stützbedarf, also auch keine
  Übergabe. Wo er sich ändert (gebaute Körper), fällt der Rat auf das Herstellerprofil ohne Stützen
  zurück; dass Ränder ohne Stütze drucken, belegt RM-582 mit vier Slicern, für Kanaldecken bis
  `CHANNEL_WIDTH` gilt die Kanalregel. Ein Slicerlauf zeigte nur den Slicer ohne Stützen.

### Zeitüberschreitungen in `test_kernel_process.py`: Last

Die Datei allein am Zweig unter 100 % Last: 149 grün in 401 s (`t_kernel1.txt`). Dieselbe
Zeitüberschreitung `test_a_job_gives_the_same_bytes_in_the_helper_as_here[voxel]` steht in den
Torläufen zweier anderer Zweige (Scratchpad der Sitzung, `tor_583c.txt:653`, `tor_622d.txt:581`).
Der Zweig berührt weder
`kernel_process` noch `kernel_jobs`, und `kernel_jobs` importiert nichts aus `app.core.slice`. Der
zweite Fehler (`…ours_stay[ohne]`, `warm_up()` False) folgte auf demselben Arbeiter gw1; sein
Hilfsprozess starb beim Schreiben in ein `tmp_path`, das nicht mehr bestand (`pytest-36726` ist
gelöscht, ältere Basisordner bestehen noch) — das passt zu parallelen pytest-Läufen anderer Sitzungen.

### Nebenbefunde (nicht vom Zweig)

- Der Bericht warnt an einer Kanaldecke „Ein Übergang unter 45 Grad oder eine Stütze hilft“
  (D0: Tunnel 20 mm allein, `slice.long_bridge` 19,9 mm), wo der Rat bewusst keine Stütze verlangt und
  die Kanalsperre vorschlägt; seit v0.5.3 so. Ins Register, wenn es anders gewollt ist.
- `support_need` fragt `model_support` weiter ohne `cancelled` (`advise.py:878`), wie im ersten
  Review genannt; am Drachen (45°) 445,7 s CPU.

## Urteil

- **RM-572: kann rein.**
- **RM-627: nicht** — Befunde 1 bis 3 vorher beheben, 4 bis 6 mit erledigen.
