# Übergabe „Einstellungen nach dem Modell“ — Stand 09.10.2026, ~22:15

Robert hat pausiert; weiter in einer neuen Sitzung. Alle Zweige sind gepusht
(`origin/<zweig>` = lokal), Zwischenstände als Commit „Zwischenstand: …“ gesichert
— sie sind **ungeprüft** und dürfen so nicht landen. Kein Agent, kein Prozess läuft
mehr. Review-Berichte: `.claude/.state/drache-2026-10-08/reviews-2026-10-09/`.

## Landungsweg (abgesprochen mit Sitzung „Alles fertig“)

- welle2 = `0a1920b10`, fertig geprüft, enthält RM-583, RM-622, RM-623 und die
  Baumspitzen. Fehlt: volles Tor auf diesem Stand und Merge nach main — macht
  „Alles fertig“ (Übergabe `output/konsolidierung-2026-10-07/KOORDINATION.md`, letzter
  Abschnitt). **Nichts nach main, nichts nach welle2 pushen**, bis „main steht“ und
  „welle3 angelegt“ gemeldet sind.
- Danach je fertigem, nachgeprüftem Zweig: `origin/welle3` hineinmergen (Kataloge nach
  Schlüssel, ROADMAP/Archiv beide Seiten behalten), betroffene Tests fahren, selbst
  `git merge --no-ff` nach welle3, pushen. Volles Tor und welle3 → main macht „Alles
  fertig“ gebündelt (jeder main-Push startet die ganze CI).
- Nach main: Zweige `einstellungen/stuetzabstand`, `einstellungen/turmabstand`,
  `einstellungen/baumspitzen`, `slicer/fenstergrundlage` lokal und auf origin löschen;
  Worktree `F:/sl-welle2` abbauen.
- RM-191 (Prusa, `handover.py`) ist nach welle3 frei für mich (claude/integration ist fertig).

## Vorgaben Roberts (gelten)

- Kein volles Tor auf Zweigen: nur betroffene Testdateien (Fenstertests je Datei mit
  `-m "(windowed or rendering) and not performance and not rendered"`) plus ruff check,
  ruff format --check, mypy. Meldet `affected_tests.py` „die Suite“, gezielt wählen.
- Keine CI auf Zweigen. Agenten: kein `python -` mit Heredoc (hängt), deutsche Texte nur
  über Edit/Write, Slicerkerne pinnen (FFFFF0FF).
- Beheben statt notieren; Review vor jedem Landen, Nachprüfung bei mehreren
  mittleren/schweren Befunden.

## Je Punkt

| Punkt | Zweig / Worktree | Stand | Nächster Schritt |
|---|---|---|---|
| RM-571 Schlitz im Deckel | `claude/lauf-a` / `F:/solidon-claude-a` | `219360698`, fertig, nachgeprüft (`review_rm571_nach.md`: N1–N6 behoben, ohne weitere Nachprüfung landbar) | als Erstes nach welle3 |
| RM-629 schräger Schacht | `einstellungen/schacht-rm629` / `F:/sl-schacht` (auf RM-571) | `a6654858b` Zwischenstand: Schachtprüfung Schicht für Schicht begonnen, Aufruf in `_channel_space` offen | fertig bauen (Auftrag: Kreis CHANNEL_WIDTH je Schicht durchschiebbar, Tests geneigt 20°/30°, Zickzack, Engstelle, Gegenprobe, CPU-Zeit Becher 0,28 s halten), Review |
| RM-670 Slicerbestand einmal lesen | `claude/lauf-e` / `F:/solidon-claude-e` | `786ff615f` behebt alle Funde der Nachprüfung (`review_rm670_nach.md`), dann `57850bbe1` Zwischenstand: base_settings/machine_model je Lesedurchgang einmal | Zwischenstand fertig bauen und messen (zweiter Export < 0,5 s CPU, Datei byte-gleich, Zähltest), Registereintrag RM-670 bereinigen, Abnahme Orca/Prusa/Cura am echten Bestand; dann Nachprüfung (N1–N3 waren mittel) |
| RM-584 Teil 2 Stützstil | `einstellungen/stuetzstil` / `F:/sl-stil` | `b89d942e7` alle 17 Erstbefunde behoben; Nachprüfung `review_rm584_teil2_nach.md`: N1, N2 mittel, N3–N10 leicht; `1c902c368` Zwischenstand: Kern grün, offen combine-Fix für Cura (N1) und ein RM-622-Test | N1–N10 fertig beheben, dann gezielte Nachprüfung N1/N2 |
| RM-572 kleine Überhänge | `befund/kleine-ueberhaenge` / `F:/sl-befund` | RM-572 kann rein (`review_rm572_nach_rm627.md`) | — |
| RM-627 Rand ≠ Brücke | dieselbe Zweig/Worktree, `88f6dcfa6` | Review: nicht — 3 mittel (Schrägflanke 40 statt 6 mm, `tools/matrix_unit.py:702` liest `need.quiet_layers`, Kosten von `span_beside` ohne Merker), 3 leicht, 2 Nebenbefunde (Bericht „eine Stütze hilft“ an Kanaldecke; `model_support` ohne `cancelled`) | alles beheben (Auftrag stand, noch nicht begonnen), Nachprüfung; dann Zweig samt RM-572 landen |
| RM-624 Kontakttest | `tests/kontakt-slicertest` / `F:/sl-kontakt` | `e5533f2ce` alle Erstbefunde behoben, 12 echte Slicerfälle grün | Nachprüfung (abgebrochen, neu starten); dabei klären, wie der Test Cura (rundet auf, RM-628) erwartet |
| RM-628 Cura rundet auf | `einstellungen/cura-rundung-rm628` / `F:/sl-cura` | `8c2c381e8` Zwischenstand: Rundungsmodell je Familie/Stil/Seite gebaut (`printed_gap`, `gap_rounding`), offen Archiv und Changelog | fertig bauen, Slicertest Cura Gitter/Baum oben/unten, Review |
| RM-589 Bohrungen/Fuß | `einstellungen/loecher-rm589` / `F:/sl-loecher` | `e8c785abd` umgesetzt; Review `review_rm589.md`: nicht — S1 (ungefragtes Schreiben ohne Herstellerprofil, wie Lüfterkurve lösen), M1 kalibriertes Material, M2 `allowances_for` zählt falsch, M3 Fenstertest, L1–L6 (u. a. SuperSlicer `first_layer_size_compensation`); `b202dc682` Zwischenstand: Modelltest fertig, Fenstertest (M3) als Nächstes | fertig beheben, Slicertest alle Programme, Nachprüfung |
| RM-587 Brücken/Überhänge | `einstellungen/bruecken-rm587` / `F:/sl-bruecken` | `badc464f9` umgesetzt; Review abgebrochen (neu starten) | Robert: **vor dem Landen je Teil schreiben** → Zweig `einstellungen/bruecken-rm587-teil` / `F:/sl-bruecken-teil`, `605e25aec` Zwischenstand (Slicertest 3/3 grün, offen Wirkungsnachweis in allen acht Programmen); danach in bruecken-rm587 zusammenführen, Review über beides |
| RM-585 Bögen | `einstellungen/boegen-rm585` / `F:/sl-boegen` | `d176bc5ca` fertig (Eiffelturm ohne Stütze, Elegoo 216 m → 0 m) | Review (abgebrochen, neu starten; Schwerpunkt falsche Entwarnung: Spitzbogen, Loch im Scheitel, Bein auf Überhang) |
| RM-586 feine Schichten | `einstellungen/schichten-rm586` / `F:/sl-schichten` | `26713c316` Zwischenstand: `app/core/slice/fine_layers.py` + Anbindung, offen Changelog, Messung in allen Familien | fertig bauen, Review; `F:/sl-schichten/t1.txt` ist Testausgabe, löschen |
| RM-588 Naht/Bügeln | `einstellungen/naht-rm588` / `F:/sl-naht` | `58afc8b56` Zwischenstand: Druckzeittests in Arbeit; Messskripte unversioniert in `F:/sl-naht/.claude/.state/naht-2026-10-09/`, Ausgaben in `F:/sl-naht-mess` | fertig bauen, Review |
| RM-626 Inseln und Kanaldecke | — | Abnahme im Register (ROADMAP.md auf claude/lauf-a) | erst nach RM-571 und RM-584 in welle3 (beide ändern `_model_support`/`descend`; `lowest`/`on_bed` aus RM-584 übernehmen), frischer Zweig von welle3 |
| RM-584-Rest | — | nicht begonnen: Fuß hoher Bäume, Spitzenabstand PETG/ASA/ABS, Schwelle | nach welle3 |

Nummern: meine RM-580–589 und RM-620–629 sind alle belegt; neue mit „Alles fertig“
abstimmen (deren Zählung ab RM-692).

## Drache

Robert druckt selbst aus dem welle2-Stand mit Abstand oben und unten 0,4 mm
(Rat „Feine Spitzen brauchen mehr Luft über den Baumstützen.“). Befund und Messung:
`output/drache-2026-10-09/rueckstaende/bericht.md`. Ein Druck, der 0,4 bestätigt,
steht aus.
