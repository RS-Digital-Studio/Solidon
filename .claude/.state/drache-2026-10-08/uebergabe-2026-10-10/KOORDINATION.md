# Koordination „Einstellungen nach dem Modell“ ab 10.10.2026

## 11.10. ~13:20 — Auftrag „Konzept Codestruktur“ (andere Sitzung für Robert, Abgabe 15:30)
Nur Konzept. Entwurf `output/konsolidierung-2026-10-07/konzept-codestruktur.md` (die andere Sitzung
legt es später als `konzepte/konzept-codestruktur-2026-10.md` ab). Gemessen am detached Worktree
`F:\tmp-agenten\struktur\baum` (welle5 `f850ef25c`), Rohzahlen `F:\tmp-agenten\struktur\*.md`.
13:21 Prüfung läuft: `konzept`-Agent (Zuschnitt, Regeln) und `solidon3d-review` (Patch-Risiko,
Mixins, Pfadbindungen), Berichte bis ~13:55; dann einarbeiten, Pfad melden, `baum` abbauen.
13:45 Beide Berichte da (`berichte-2026-10-10/codestruktur-pruefung-konzept.md`, `…-review.md`,
je vier schwere Funde), eingearbeitet. Robert: Verbesserungen bei der Gelegenheit als Funde in
eigener Konzeptdatei → `output/konsolidierung-2026-10-07/konzept-codestruktur-funde.md`
(CS-1–CS-14; Ablage später `konzepte/konzept-codestruktur-funde-2026-10.md`). 13:48 Nachprüfung
läuft, Bericht bis ~14:10.
14:01 **ABGEGEBEN**: Nachprüfung ohne schwere Funde (`codestruktur-nachpruefung.md`), M-1–M-6 und
L-1–L-12 eingearbeitet, Pfade gemeldet. Die andere Sitzung legt beide Dateien nach welle5 → main
ab, trägt CS-2/3/6/9/10/11/12/13 ins Register (RM-722 ff.) und legt Robert die vier Fragen aus
Abschnitt 7 vor. Messbaum `struktur/baum` abgebaut; Messdaten und Prüfskripte (in den Berichten
noch als `F:\tmp-agenten\struktur\…` genannt) jetzt unter
`F:\claude-scratch-archiv\F--3D-Druck\codestruktur-2026-10-11\struktur\`.

## 11.10. 11:46 — Nachauftrag „O-Wände“ (andere Sitzung, Robert: Kapazität vorhanden)
*Text aufbringen*: runde Wände eines „O“ fehlen im Objektbaum (`features.detect_curved_faces`,
Schwelle 1 % der Körperfläche). Zweig `fix/o-waende` von welle5 `e3f0c9dc9`, Worktree
`F:\sl-o-waende`; Bauagent „owand“ bis 12:40 (Bericht `berichte-2026-10-10/owand.md`), Review bis
13:15, Landung mit `land.sh fix/o-waende <meldung> welle5` bis 13:45, Spitze melden. Wackelt es:
bis 13:15 der anderen Sitzung sagen. Wache um ~12:12.
12:12 Fix `f391a14d0`; 12:28 Review „nicht“: S1 (örtlich ≠ voll bei scharf angrenzenden gerundeten
Flecken), M2 (örtliche Frage über den ganzen Körper), M1, L1, L2 → owand bis 13:05, dann
Nachprüfung; Entscheidung landen/Register um 13:15 an die andere Sitzung.
12:46 Fixrunde fertig `b06c2b162` (voll = örtlich an Linse/Fase, örtliche Frage 4,8 Mio. Dreiecke
~30–90 ms statt 390–500, Korpus nur Schriftwände) → Nachprüfung rvowand bis 13:20.
12:51 Nachprüfung **kann landen**; N1–N5 leicht → owand bis 13:20, dann landen (sonst b06c2b162).
13:01 **GELANDET in welle5 als `3469bbdef`** (N1–N5 behoben `63dcfc4ac`), gemeldet.
**ABGEBAUT** nach main `ee6b810fe` (welle5 samt O-Wänden): Worktree `F:\sl-o-waende`, Zweig
`fix/o-waende` lokal und origin (vorher Vorfahr von origin/main geprüft); `owand`, `rvowand` nach
`F:\claude-scratch-archiv\F--3D-Druck\o-waende-2026-10-11\`.

## 11.10. ~09:55 — ABGESCHLOSSEN
main = `732bde46d` (welle4 mit allen Landungen dieser Sitzung, Schlusstor 27 946 passed). Abgebaut:
23 Worktrees und 24 Zweige (lokal und origin, je vorher auf main und sauber geprüft). Scratch
`b00d64ab…` und `78c2d72e…` sowie meine `F:\tmp-agenten`-Ablagen nach
`F:\claude-scratch-archiv\F--3D-Druck\` verschoben (pytest-Reste entfernt); C: 25,7 GB frei.
**Offen nur:** die Prüfberichte dieser Ablage (`berichte-2026-10-10/`, `reviews-2026-10-09|10/`,
`uebergabe-2026-10-10/`) nach dem Release mit einem Aktenzweig versionieren — vorher die
gleichlautenden unversionierten Kopien im Hauptbaum entfernen. Probedrucke für Robert: RM-703,
RM-717. welle4/welle5 gehören der Sitzung „Koordination 0.6.0 Übergabe“.

**07:54:** Teil-2-Fixe **GELANDET als `8e13b452e`** (T2-G1, G2, M1; 6857 + Fenster grün), gemeldet.
Von mir nichts mehr; Abbau nach „main steht, CI durch“.
**07:36:** Integrationsreview Teil 2: kann nach main nach T2-M1 (0.5-Rückfrage nur bis zur ersten
si1-Buchung, zurückgenommene zählen nicht — umsetzen, RM-720 anpassen), T2-G1 (RM-701 ins Register),
T2-G2 (`_SAVED_IRONING` eine Quelle). rm706 auf `fix/integration-t2` (F:\sl-t2, von `7b5d9599f`),
fertig 08:15, Landung bis 08:40; sonst G1+G2 allein, M1 → 0.6.1.
**07:30:** Andere Sitzung: Integrationsreview Teil 2 über `1ec8d5eee..8992d0810` läuft; danach
Bereichsnachweis-Commit, Platzierung (bis 08:15), Schlusstor, main. Sie meldet „main steht, CI
durch“ → dann Abbau meiner Worktrees (`liste-0830.md`). Funde aus dem Integrationsreview in
meinem Gebiet übernehme ich.
**07:20:** RM-585 **GELANDET `8992d0810`** (gezielte Nachprüfung kann landen; Merge-Konflikte ROADMAP
(beide Punkte archiviert), advise-Importe, Slice-Karte vereint; RM-721 eingetragen; 5636 passed).
**Liste gesendet — von mir nichts mehr nach welle4.** Offen nur: Abbau nach main (`liste-0830.md`).
**07:15:** Akten-Agent hing (seit 05:53 keine Ausgabe) → gestoppt, Register selbst eingetragen:
**GELANDET `c86a04eb8`** (RM-700, 702, 703, 708–720; 719 passed). Gemeldet.
**07:00:** rv585n2 war seit 05:04 tot (kein Prozess) → gestoppt; neuer Prüfer rv585z, Urteil bis 07:55,
dann (falls ok) welle4 hinein, Pflichtliste, landen vor 08:30; sonst RM-585 auf dem Zweig (0.6.1).
**06:58 (Uhr):** Stufe 2 Altbuchungen **GELANDET als `81b6ac793`**, gemeldet. (Meine Zeitstempel
07:10/07:15 oben lagen ~20 min zu spät.) Offen: RM-585 (rv585n2 gezielt), Akten (Register RM-700ff),
Liste 08:30.
**07:15 Absprache:** Stufe 2 ~07:40 landen, kein eigenes zweites Tor; die andere Sitzung fährt nach dem
Schnitt **ein** volles Schlusstor auf welle4 + Integrationsreview Teil 2 über alles seit `1ec8d5eee`.
Am Merge weiter die Pflichtliste der Baumleser fahren.
**07:10:** Nachprüfung Stufe 2: **kann landen**; N1 Test, N2 → Satz in Regel, RM-720 (0.6.1). rm706 bis
07:35, dann landen und der anderen Sitzung melden (kurzes zweites Tor). RM-720 ins Register (akten).
**06:55:** Stufe 2 fertig `2e549dc94` („si1-“-Kennung ab RM-706, Rückfrage nur 0.5, M2-Wege bis auf
V4 Grenze) → Nachprüfung rvalt bis 08:10 → bei „kann landen“ landen + andere Sitzung fährt kurzes Tor.
**06:33:** Stufe 1 Altbuchungen **GELANDET als `86a8fb3fa`** (eigener Zweig `fix/altbuchung-stufe1` =
`dc7885128` + welle4 `c21ce8fb3`; 3786 + 84 Fenster passed), gemeldet. Stufe 2 läuft auf
`fix/altbuchung-rueckfrage` (muss welle4 `86a8fb3fa` mergen).
**06:25 Absprache:** Stufe 1 landet **bis 07:00** auf welle4 (Schlusstor der anderen Sitzung ab ~07:30
soll sie enthalten). Stufe 2 nur bei „kann landen“ bis 08:15 → zweites kurzes Tor dort. Sonst bleibt
Stufe 1, M2-Rest als Registerpunkt mit klarem Changelog-Satz.
**06:20:** Review M1-Fix: nicht so — M1 Rückfrage auch für 0.6.0-Buchungen, M2 sechs Doppelabzugswege
(vorbestehend), L1–L3. Plan: Stufe 1 (b, sicher, landbar ohne Prüfung) bis 06:50, Stufe 2 (a + M2)
bis 07:30 → Nachprüfung durch rvalt bis 08:15 → sonst Stufe 1 landen. Andere Sitzung informiert.
**05:55 (Uhr korrigiert):** Liste für 08:30 als Entwurf `liste-0830.md`; neue Nummern RM-708–719
vergeben. Agent „akten“ trägt RM-700, 702, 703, 708–719 ins Register ein (`akten/register-rm7xx`,
F:/sl-akten) bis 07:15 → kurze Durchsicht, landen. Prüfberichte versionieren erst nach dem Release.
**06:15:** M1-Fix fertig `3d9b32e54` (Rückfrage statt stiller Doppelabzug; Sonde 2/11/0 statt 2/0/11;
G1 zusammengelegt) → enges Review rvalt bis 07:20 → welle4 hinein → landen ~07:45. Zwischenmeldung
an die andere Sitzung gesendet (Weg b nicht nötig).
**05:55:** RM-629 **GELANDET als `b3505824d`** (5474 passed Exit 0 am Endstand), gemeldet.
**05:30 DRINGEND M1 (Integrationsreview andere Sitzung):** Seit E erkennt das Lager 0.5.3-Buchungen
nur 3/13 (Netzbits umgeordnet). Weg (a): frühere Buchung mit Rückfrage, nie still. + G1 (zwei
Changelog-Punkte „Neu in den Druckeinstellungen“ zusammenlegen). rm706 auf `fix/altbuchung-rueckfrage`
(F:\sl-altbuchung, von `a00816a0e`) bis 07:15; Zwischenmeldung an die andere Sitzung bis 07:00,
sonst Weg (b). RM-629: rm629b war seit 02:34 tot → gestoppt, ich übernehme: gestagten Merge
committet `6d3c4073b`, welle4 `a99f848c0` gemergt `ef166d0f6` (Konflikte Archiv + Slice-Karte
vereint), Prüflauf läuft, dann landen.
**05:35:** Tunnel-Fix **GELANDET als `a99f848c0`**, gemeldet. Worktree `F:/sl-tunnel` nach main abbauen.
**05:20:** F Teil 2: **kann landen** (gemeldet; T2-1 G; neuer Punkt außerhalb F: Weich verschmelzen
dreht Hohlraum nach außen, seit v0.5.3). Worktree F:\sl-f-nach abgebaut.
**05:10:** RM-588 **GELANDET als `bc8595595`** (Format 52, Beispiele neu, nach Merge welle4
`1ec8d5eee` 5280 passed Exit 0), gemeldet samt Spitze für make_examples.
**04:50:** Review Tunnel: landbar mit Fund 1 (Baumstil im Herstellerprozess, Prusa XL 1,14 m) + Test,
ohne Nachprüfung; L2–L7, Changelog als Behebung (Orca/Creality „auto“ seit v0.5.3) → rmtun bis 06:30.
**04:45:** RM-585 Z1–Z3 behoben `249dbfe57` (welle4 `4c135723a`); offen: grenuttags-Sperre 2464 → 0,
Waschschüssel kleiner → gezielte Nachprüfung rv585n2 bis 06:45. `test_parts` Bereichsnachweis „stale“
ist welle4-weit rot (gemeinsamer Lauf). welle4 = `1ec8d5eee` (Chat-Nachtrag).
**04:40:** F Teil 2 der Nachprüfung gestartet (rvfn fortgesetzt, F:\sl-f-nach auf `3410032b6`),
Urteil bis 06:15 → sofort an die andere Sitzung (sie landet F). Danach Worktree F:\sl-f-nach abbauen.
**04:20:** Tunnel-Fix fertig `d3abc9ae9` (welle4 `4c135723a` drin): `snug` als Objektwert an Teilen
mit Sperrkörper und Gitter (Orca-Familie, Prusa), Tunnel ~1 m → 0,01 m, Deckel 100 % → Review rvtun
bis 06:00. RM-588 Fixrunde fertig `fdd07f1d5`, Fix-Diff durchgesehen (ok) → Merge welle4
`4c135723a` mit neu erzeugten Beispielen bis 05:15, dann landen. RM-629 Winkelfix `fdd1818d9`,
Merge welle4 läuft.
**04:00:** welle4 = `4c135723a` (Intel, E, GEW, Agentlog, Abbruch gelandet). Bereichsnachweis läuft
seit 03:55 auf `b41e0e51a` (F:\sl-nachweis, 6 Prozesse) — Abdruckdateien weiter tabu. Vor jeder
Landung welle4 hinein.
**03:50:** Nachprüfung 2 RM-585: **nicht** — Z1 schwer (gekrümmte einseitige Streifen gelten als
gefasst, Halbkuppel-Nische R 12 ohne Stütze, welle4 12,9 m), Z2/Z3 leicht; N1–N7 halten, Korpus
(grenuttags, obj_15) unkritisch. rm585b fortgesetzt bis 05:30 → gezielte Nachprüfung durch rv585n2
(Verlauf fortsetzen) bis ~06:45 → landen bis 08:30, sonst RM-585 auf dem Zweig (0.6.1).
**03:15 Bereichsnachweis:** andere Sitzung startet nach GEW (~04:00) einen gemeinsamen Lauf auf
welle4 (3,5 h). Danach darf keine Landung Abdruckdateien ändern: geom/contours, intersections,
lathe, transform, prepare, seal; knowledge/standards.py + data/standards.toml; knowledge/parts/*;
brep/profiles.py. Meine Zweige (RM-588, 585, 629, Tunnel) berühren keine — vor jeder Landung erneut
prüfen (`git diff --name-only origin/welle4...<zweig>`), Agenten informiert. welle4 = `fdff3bb8f` (+E).
**03:10:** Review RM-588: S1 (test_value_labels rot durch `filament_usage.py:909`, Fix im Prüfbaum
belegt), L1–L5 → nach S1 landbar ohne Nachprüfung; rm588 fortgesetzt bis 05:00. Formatschritt hält
(89 alte Dateien wie welle4, Beispiele nur Formatnummer), Abdruck 6/6. `test_value_labels.py` in
die Pflichtliste.
**03:00:** C: wieder 6,9 GB frei (andere Sitzung hat ihren Vorsitzungs-Scratch 182c0fee nach
`F:\claude-scratch-archiv\F--3D-Druck\` verschoben). Meine Scratch-Ordner b00d64ab/78c2d72e nach dem
Schnitt ebenso dorthin verschieben (robocopy /MOVE), nicht vorher — Prüfer lesen Sonden daraus.
**02:45:** RM-588 fertig `4243682c3` (Format 52: `shell.ironing` "none"/"topmost"/"top_surfaces",
Migration 51→52 + Korrektur 35→36, Beispiele neu, Abdruck 7/7, acht Slicer belegt) → Review rv588 bis
05:00. RM-585 N4-Wächter `5a33fc8ad`. **C: fast voll (2,2 GB)** — Agenten auf TEMP/TMP und pytest
`--basetemp` unter `F:\tmp-agenten\<kürzel>` umgestellt, andere Sitzung informiert.
**02:30:** RM-585 Fixrunde fertig `c8e42e34a` (welle4 `a72079433` drin; N2 sichere Seite, Eiffel frei,
15°/60° am Kundenweg zu; `CANTILEVER_LAYERS` bleibt für feine Schichten). Nachprüfung rv585n2 läuft
(Urteil 04:30; Schwerpunkt: zwei Korpusmodelle mit geschrumpfter Kanalsperre im Slicer), parallel
N4-Wächter durch rm585b. welle4 = `a72079433` (+ Intel-Mac-Fix).
**02:35:** `fix/welle4-baumleser` **GELANDET als `c0a554949`** (Kurzreview kann landen, N1/N2 behoben),
gemeldet — welle4 grün an den Baumlesern. RM-629: A/B/C/Unterlagen fertig `30ade10de`; mein Fund:
kern.md-Verstoß (math.cos/atan/tan in `_shaft_step`, zwei Konstanten, `overhang_angle`) → rm629b
fixt + welle4 `c0a554949` hinein bis 03:15, dann Durchsicht durch mich, landen.

## 11.10. ~02:00 — Limit zurückgesetzt, Sitzung läuft weiter
Alle fünf Agenten waren ~01:00 am Limit abgebrochen; mit Verlauf fortgesetzt: rvw4 (Frist 02:40),
rm629b (03:00), rm585b (04:00, 53 Dateien ungesichert beim Abbruch), rm588 (04:00, Format 52
committet `208030f2c`), rmtun (04:30). welle4 = `bb269dc54` (+ fix/http-frist-zaehlen); in
`fix/welle4-baumleser` gemergt → `e79410c55`, Prüflauf läuft. Andere Sitzung: F-Umbau bis 06:00,
dann Teil 2 bei uns; gemeinsamer Bereichsnachweis startet dort nach E und GEW.

## 11.10. ~00:50 — ÜBERGABE (Nutzungslimit dieser Sitzung erreicht)
Gelandet auf welle4: RM-586 `2c7fa2b91`, RM-706 `1e4dec783`, RM-584-Nachtrag `3d782213e` (alle der
anderen Sitzung gemeldet). Offen, in dieser Reihenfolge prüfen (Berichte unter `berichte-2026-10-10/`,
Reviews unter `reviews-2026-10-10/`; Agenten liefen beim Abbruch weiter, Stand liegt in den Zweigen):
1. `fix/welle4-baumleser` `bddfd5fc1` (Worktree `F:/sl-w4fix`, welle4 ROT bis dahin): Kurzreview
   `review_welle4_baumleser.md` lesen → origin/welle4 hinein (Pflichtliste + edge_binding,
   filament_usage_stored_inputs, filament_workflow mit Fenster) → `land.sh` → Spitze an
   „Koordination 0.6.0 Übergabe“ melden (die will sie selbst nicht landen). Danach Worktree abbauen.
2. RM-629 `einstellungen/schacht-rm629` (`F:/sl-schacht`): Fixe A, B, C (Bauplan §9 mit Ansage),
   Unterlagen → landbar ohne weitere Prüfung; Diff durchsehen, landen.
3. RM-588 `einstellungen/naht-rm588` (`F:/sl-naht`): Bügeln als Auswahl, **Format 52** → Review →
   landen; danach der anderen Sitzung die welle4-Spitze mit neuen Beispielen melden.
4. RM-585 `einstellungen/boegen-rm585` (`F:/sl-boegen`): Fixrunde N1–N7 → Nachprüfung → landen.
5. `fix/tunnel-gitter` (`F:/sl-tunnel`): Gitterstütze im gesperrten Tunnel (Regression auf main) →
   Review → landen.
6. Nachprüfung F Teil 2 (Worktree `F:/sl-f-nach`, Bericht `output/konsolidierung-2026-10-07/
   review-f-nach.md`), sobald die andere Sitzung die Umbau-Spitze meldet (~05:00).
7. 08:30 Liste an die andere Sitzung; keine Landung nach 09:00. Neue Punkte für die Liste (RM-708 ff.):
   kleine Kuppen < R 9 mm (RM-586 F8), Bambu-Lagenzähler im G-Code-Leser, `overrides_unreachable`
   am XL 2T falsch (seit v0.2.1), Orca „Gitter → Baum“-Zeile schlägt Vorhandenes vor (Weg 2),
   Kreis folgt der Achse / gekrümmte Wendel (RM-629), Zickzack +0,4 s, shapely ≥ 2.1, Bügel-
   Zeitanteil im Grund, Kumiko als Figur, Druckzeitschätzung 17–124 s CPU.

## 10.10. ~21:15 — neue Sitzung „Welle4 Einstellungen nach Modell“ (Vorsitzung zu Ende)
Robert (Auftrag ~21:00): **Schnitt welle4 11.10. 09:00, Liste gegen 08:30** an die andere Sitzung
(heißt jetzt „Koordination 0.6.0 Übergabe“; die schrieb 06:00/05:30 — Rückfrage gestellt). Alle
Agenten der Vorsitzung waren ~20:58 abgerissen (keine Python-Prozesse); neu gestartet, alte IDs
ungültig. Scratch bleibt `b00d64ab…\scratchpad\<kürzel>\`.

| Kürzel | Art | Worktree / Zweig | Stand beim Neustart | Frist |
|---|---|---|---|---|
| rv586 | Review RM-586 | sl-schichten `ff4e31e47` | **fertig 21:45: „nicht“** — F1 schwer (Prusa-Wischturm), F2/F7 mittel, F3–F10 leicht → Nachprüfung nötig | — |
| rm586b | Fixe RM-586 F1–F10, Changelog → 0.6.0 | sl-schichten | **fertig 22:35 `fb289a8bc`** (welle4 `02213548a` drin); offen als neue Punkte: kleine Kuppen < R 9 mm (F8), Bambu-Lagenzähler im G-Code-Leser | — |
| rv586n | Nachprüfung RM-586 | sl-schichten `fb289a8bc` | **fertig 23:15: kann landen nach N1–N5 (leicht) ohne weitere Prüfung**; neuer Punkt außerhalb: `slicer.overrides_unreachable` am XL 2T falsch (seit v0.2.1) | — |
| rm586b (fortgesetzt) | N1–N5, welle4 | sl-schichten | fertig `da91135f5`, **GELANDET ~23:40 als `2c7fa2b91`** auf welle4, gemeldet | — |
| rm706 | Bau RM-706 | sl-rm706 | **fertig 21:25 `35aef0b10`** (welle4 drin, 4895 grün) | — |
| rv706 | Review RM-706 | sl-rm706 `35aef0b10` | **fertig 21:55: „nicht“** — S1 schwer (Kalibrierung fehlt im Abdruck), M1 (matches), M2 (eigener Prozess), L1–L5; Probemerge Sparen sauber (0 Abweichungen) → Nachprüfung nötig | — |
| rm706 (fortgesetzt) | Fixe S1, M1, M2, L1–L5 | sl-rm706 | **fertig 22:58 `29de72b5d`** (welle4 `ac244486b` drin, 29/29 Mutationen rot, L5 594→141 ms) | — |
| rv706 (fortgesetzt) | Nachprüfung RM-706 | sl-rm706 `29de72b5d` | **fertig 23:20: kann landen nach N1 (mittel: absoluter Profilpfad, Creality-Versionsordner) + N2 (leicht) ohne weitere Prüfung** | — |
| rm706 (2. Fortsetzung) | N1, N2, welle4 | sl-rm706 | fertig `488dd4528`, **GELANDET ~23:50 als `1e4dec783`** auf welle4, gemeldet | — |
| rm629b | Fixe RM-629 | sl-schacht | **fertig 23:10 `0463b5046`** (F6 mit Ellipse, F2 `SliceResult.overhang_angle`, welle4 `ac244486b` drin; Zickzack 0,50→0,88 s CPU) | — |
| rv629n | Nachprüfung RM-629 | sl-schacht `0463b5046` | gestartet 23:13 | 02:30 |
| rm585b | Fixe RM-585 | sl-boegen `acc6283d5` | nichts geändert; N2: sichere Seite (Kragarm ≤ 1 Bahnbreite, Richtung neu_fix6) | 03:30 |
| rm588 | Abschluss RM-588 | sl-naht | **gebaut 23:55**, acht Slicer belegt, welle4 `1e4dec783` drin; rot: `test_every_group_holds_one_subject` (shell 16 > 15,4 mit RM-586) | — |
| rm588 (fortgesetzt) | **Entscheidung (a)**: `shell.ironing` als Auswahl aus/oberste/alle, `ironing_topmost` entfällt, **Format 52** (an andere Sitzung gemeldet), Abdruck stabil halten | sl-naht | 00:00 | 03:30 → Review |
| rm584n | Nachtrag RM-584 (L1, Cura-Spitzenluft) | sl-stil2 | **fertig 22:05 `9907dab53`** (welle4 `02213548a` drin; Cura-Fehlrat belegt + behoben `advise.on_the_plate`; kein Changelog) | — |
| rv584t | Review Nachtrag | sl-stil2 `9907dab53` | **fertig 22:55: nach M1 landbar ohne Nachprüfung**; L1–L4 leicht; Altfall Cura „Baum→Gitter abgelehnt“ | — |
| rm584n (fortgesetzt) | M1, L1–L4, Altfall | sl-stil2 | **fertig 23:19 `3370bf34b`** (welle4 `ac244486b` drin) | — |
| rv584t (fortgesetzt) | enge Durchsicht `cd45ca608`+`f48592b75` | sl-stil2 | **fertig 23:50: landbar**; meine Frage kein Fund; N1 leicht (3,5 s unnötige Neufrage), Altfall Trennschichtzeilen nach „Aus → Gitter“ abgelehnt | — |
| rm584n (3. Fortsetzung) | N1, Altfall, welle4 | sl-stil2 | **fertig `3e47bc61a`** (welle4 `1e4dec783` drin); Altfall-Fix wirkt über Cura hinaus → | — |
| rv584t (3.) | enge Durchsicht `ec301ddea` + Merge, ElegooSlicer alt/neu | sl-stil2 | **fertig 00:15: nein** — M2 (Orca-Regression), L5; Altfall Orca → nach M2 landbar ohne Nachprüfung | — |
| rm584n (4. Fortsetzung) | M2, L5 | sl-stil2 | fertig `b53adf895`, **GELANDET 00:40 als `3d782213e`**, gemeldet. Altfall Orca (Zeile „Gitter → Baum“ schlägt vor, was die Datei schon tut) → **neuer Punkt 0.6.1, Weg 2** | — |
| rvw4 | Kurzreview `fix/welle4-baumleser` `bddfd5fc1` (meine Reparatur der Baumleser) | sl-w4fix | 00:35 → dann welle4 hinein, landen, melden | 01:30 |
| rmtun | Fix: Gitterstütze im gesperrten Tunnel (Elegoo 1,08 m seit RM-584 „grid“, auf main) | sl-tunnel, `fix/tunnel-gitter` von `3d782213e` | 00:48 | 04:00 → Review |
| rvfn | Nachprüfung F Teil 1 | sl-f-nach | **fertig 00:35: kann landen vorbehaltlich Teil 2**; N1 (M) √2 nur eben, N2–N5 (G) → an F-Agent der anderen Sitzung | Teil 2 nach Umbau (~05:00) |
| rv629n | Nachprüfung RM-629 | sl-schacht | **fertig 00:30: landbar mit Fix A** (Y-Ast/Fischgrät), B, C (Bauplan §9 mit Ansage), Unterlagen → rm629b fortgesetzt bis 02:15 | — |

Dazu ich selbst: CI-Fund main (Linux, `test_ui_export.py::test_the_3mf_export_reads_the_slicer_stock_in_one_pass`,
Lager mehrfach gelesen) — Ursache im Test (`get_ident` unter Linux wiederverwendet), Fix
`fix/export-einmal-lesen` `2e4b54489` (Worktree `F:/sl-ci-export`), an die andere Sitzung
gemeldet 21:20; sie merged ihn in `fix/ci-mapfile` (ihr Review prüft ihn mit) und löscht den
Zweig nach der Landung; mein Worktree ist abgebaut.
Neue RM-Nummern ab RM-708.

**00:10 Robert: „F machen wir auch noch in 0.6.0 alles“** — RM-671 (claude/lauf-f, Paket der
anderen Sitzung) doch in 0.6.0; an die andere Sitzung weitergegeben, zwei Agentenplätze angeboten.
Sie gab mir die **Nachprüfung F Teil 1** (H1, H2, M1–M3, G1–G4, Druckgleich; nicht Laufzeit/
`mesh_edits`/`uniform`, das baut ihr Agent in `F:\solidon-claude-f` um, Ziel 05:00 → Teil 2 über
den Umbau-Diff mit demselben Prüfer). Prüfer rvfn gestartet 00:15, eigener Worktree `F:\sl-f-nach`
(detached `81d718fbd`, nach Teil 2 abbauen), Bericht `output\konsolidierung-2026-10-07\review-f-nach.md`,
Urteil Teil 1 bis 02:30 → an die andere Sitzung melden.
**00:05 Format:** 52 = RM-588 (bestätigt). Andere Sitzung: Intel-Mac nur CACHE_FORMAT 55 (auf
welle4); E/GEW ggf. 53/54 auf 52 aufbauend, Bescheid vor make_examples. Nach Landung RM-588 der
anderen Sitzung die welle4-Spitze mit neu erzeugten Beispielen melden. F (RM-671) nicht in 0.6.0.
**22:15 Schnitt bestätigt: spätestens 09:00, Liste 08:30** (Robert „Ja alles sauber“ an die andere
Sitzung); keine Landung nach 09:00. Fristen rm629b 02:30 / rm585b 03:30 wieder wie ursprünglich.
**22:10:** welle4 = `02213548a` (main `1fc9a1a5b` mit den CI-Fixen inkl. `fix/export-einmal-lesen` hinein).
**21:55:** welle4 = `506ca0755` mit **Sparen (RM-698)** — vor RM-706 gelandet. Laut Entwurf
nur verlustfreie Stufen (keine float32-Ecken), Netzbits gleich; rv706 prüft am Probemerge, ob
der Vorabdruck aus Cache/schlankem Eintrag gleich bleibt (Beispielsonde 0.5.3). `fix/ci-mapfile`
geht ~22:10 nach main, welle4 zieht die andere Sitzung nach → jeder Zweig vor dem Landen
erneut `origin/welle4` hinein.

**21:20 andere Sitzung:** ihr Auftrag von Robert sagt Schnitt **06:00**, Liste 05:30; sie fragt
Robert. Bis zur Antwort gilt 06:00 → Fristen rm629b (01:30) und rm585b (02:30) vorgezogen.

## 10.10. ~20:45 — welle4 GEHT AUCH IN 0.6.0 (Robert ~20:40, abgestimmt)
**Schnitt welle4 morgen 06:00.** Bis dahin mit Review + Nachprüfung auf welle4, was fertig wird;
Changelog unter `## 0.6.0`; Format ab 52; gegen **05:30 Liste an „Alles fertig“**, was noch kommt.
Danach: Schlusstor, Integrationsreview, main ~08:00, CI ~09:30, Signieren 14:00. Was um 06:00 nicht
geprüft ist, bleibt auf seinem Zweig (0.6.1). Höchstens 6 Agenten (andere Sitzung ~4).

RM-586 Bau fertig `ff4e31e47` (Changelog fälschlich unter 0.6.1 → in Fixrunde nach 0.6.0) → Review
rv586 läuft (Urteil bis 01:00).
Agenten welle4 (Bau): rm586 a859152b57c5fb8d6 (F:/sl-schichten, fertig), rm706 afdbea25370b07f51
(F:/sl-rm706), rm629b aa8b0b9e37fbfab29 (F:/sl-schacht), rm585b a347d04e0f42e9a55 (F:/sl-boegen),
rm588 a550bbac58b16fc0f (F:/sl-naht), rm584n abc6c09b04e781980 (F:/sl-stil2, Zweig
einstellungen/stuetzstil-nachtrag, bis 01:00). Danach je Bau: Review (bzw. Nachprüfung bei 629/585) → Fix → ggf. Nachprüfung → landen
mit `land.sh` (Ziel welle4).

## 10.10. ~20:30 — main steht (welle3 als e734a0b44), welle4 angelegt (aus main, Worktree F:/sl-welle4
gehört „Alles fertig“). Meine welle4-Zweige: vor dem Landen origin/welle4 hinein, landen mit
`land.sh <zweig> <meldung> [ziel]` — Ziel jetzt Parameter, Vorgabe welle4, welle3 wird abgewiesen. Unversionierte Akten im Hauptbaum (54 Dateien) kollidieren derzeit nicht; beim
Aktenzweig die bytegleichen Kopien im Hauptbaum entfernen und vorher Bescheid geben.

## STAND 10.10. ~19:50 — welle3 von mir GESCHLOSSEN

Letzte Landung RM-628 `80d623957`. „welle3 geschlossen“ an „Alles fertig“ gemeldet; die macht Tor,
Integrationsreview Teil 2, welle3→main, CI; Robert macht die Release-Schritte (Signieren ~11.10. 14:00).
Beispielsonde am fertigen welle3: Netze 19/21, Buchungen 11/12 (nur gehaeuse-mit-bausteinen, bewusst).
Nutzungslimit fast erreicht — **nichts Neues starten, bis es zurückgesetzt ist.**

**Robert ~19:55: „noch nicht am Limit, mach weiter“** → höchstens 2 Agenten auf welle4-Zweigen
(andere Sitzung informiert, hält bei Bedarf an): RM-586 fortgesetzt (a859152b57c5fb8d6,
F:/sl-schichten), RM-706 neu (afdbea25370b07f51, F:/sl-rm706, Zweig
einstellungen/abdruck-eingaenge-rm706 von welle3 80d623957).

**Nächste Schritte (welle4, nach der Pause, welle4 legt „Alles fertig“ von main an):**
1. Fixaufträge aus den Reviews: RM-629 (`review_rm629.md`: F1 Fix 1b fertig, F6 Entwurf, F3 Register),
   RM-585 (`review_rm585_nach.md`: N1 Einzeiler `neu_fix8`, N2 Grenze 11–17° → Probedruck
   Pultdecke 12°/Haut 15° in 20 mm für Robert, N3 Drachen-Flügeltasche, N4–N7).
2. Bau: RM-586 (`F:/sl-schichten`, Arbeit im Worktree), RM-588 (`F:/sl-naht`), RM-706 (Abdruck aus
   gespeicherten Eingängen, vor RM-698!), RM-707-Rest L3/N1 (Spulendialog belegt fremdes Material
   mit Projektwerten vor), RM-626, RM-191, RM-700 (support_need-Leistung), RM-701 (Brückenweite Ring),
   RM-702 (Cura-Drucker mit eigenem Ausgleich), RM-704-Rest (Wände an Gliedern, Spitze Prusa/Cura,
   Kinn an Druck 4 prüfen), RM-584-Rest.
3. Aktenzweig: Register RM-700–707 eintragen (gegen origin/main prüfen), Prüfberichte unter
   `.claude/.state/drache-2026-10-08/{reviews-2026-10-09,reviews-2026-10-10,berichte-2026-10-10,
   uebergabe-2026-10-10}` versionieren; im Hauptbaum danach die gleichlautenden unversionierten
   Kopien entfernen.
4. Nach main: Worktrees/Zweige der gelandeten Punkte abbauen (sl-befund, sl-kontakt, sl-stil,
   solidon-claude-a, solidon-claude-e, sl-drache3, sl-loecher, sl-abdruck, sl-kanaltext, sl-cura,
   sl-bruecken, sl-bruecken-teil) — vorher `git merge-base --is-ancestor <zweig> origin/main`.

## JETZT (10.10. ~17:00, veraltet) — bei Verdichtung/Neustart hier weiter

Neue Sitzung: Agenten-IDs unten gelten dort nicht — abgebrochene Prüfer/Bauagenten
neu starten mit Verweis auf ihren Bericht (`../berichte-2026-10-10/`, `../reviews-2026-10-10/`) und
den Worktree; der Stand liegt in den Zweigen (alles gepusht).

Schnitt welle3 für 0.6.0 **heute 22:00**; welle3 = fcac08701 (D + Bereichsnachweis 50/50; alle
Pakete der anderen Sitzung drin). Nutzungslimit knapp — höchstens 2–3 Prüfer, nur für
Punkte, die bis 22:00 landen; Reserve für Tor/Integrationsreview/CI der anderen Sitzung. Landen nur mit `land.sh <zweig> <meldung>` (Zweig muss origin/welle3 enthalten —
vorher hineinmergen, gezielte Tests + test_shared_constants/test_language_rules/
test_registry_consistency/test_text_length/test_advise, ruff/format/mypy). Je Landung der
anderen Sitzung kurz Bescheid (SendMessage an „Übergabe Koordination 2026-10-07“).

Gelandet: RM-571, 624, 584 T2, 572+627, Kanaltext-Fix, 670, 704, Grundtext-Fix, 589,
705+707 (`a8e7b00d3`), **587 (`277a84ff9`)**. Offen für 0.6.0 nur noch RM-628: Wackeltest-Ursache
lag in welle3 (Druckersuche liest Cache, Windows sperrt Löschen), behoben in `1f7652520`
(`paths.read_text_shared`, FILE_SHARE_DELETE) → Kurzreview: M1 (ctypes je Aufruf neu, +16–31 %),
L1, L2, N1, N2 → Fixes durch a3fd9d255141f5563 bis 20:45, welle3 b6f30541d hinein → M1 selbst
nachprüfen (Zähltest + Kosten) → landen vor 22:00; sonst RM-628 → welle4 und der Fix allein?
(nein: Fix gehört zum Zweig; dann melden, dass welle3 den Wackeltest behält).
→ welle4: RM-629, RM-585 (beide mit Befunden), RM-586, RM-588, RM-706, neue Punkte.

Offen für 0.6.0 (Prüfer nach Limit fortgesetzt):
1. RM-628 `F:/sl-cura` `9d5790b8e` (L-1/L-2 behoben, welle3 a8e7b00d3 hinein, Tests grün) — aber
   Fenstertest `test_after_a_cleared_cache_a_new_search_brings_curas_printers_back` wackelt nur mit
   RM-628 (WinError 32, 2/4 rot; welle3 allein 5/5 grün) → Agent a3fd9d255141f5563 sucht die
   offene Datei, Fix im Produktcode bis 20:00 → dann landen; sonst RM-628 → welle4.
2. ~~RM-705 + RM-707~~ gelandet `a8e7b00d3`. Offen welle4: L3 + N1 (Spulendialog belegt fremdes
   Material mit Projektwerten vor, seit 0.5.3), RM-706.
3. ~~RM-587~~ gelandet `277a84ff9`.
   Wackeltest `test_after_a_cleared_cache_a_new_search_brings_curas_printers_back` (WinError 32)
   auch auf RM-587 gesehen → wohl in welle3 (RM-670-Merker/Hintergrundsuche); RM-628-Agent sucht.
4. Vor 22:00: Beispielsonde am fertigen welle3 (Abschnitt „Vor dem Schnitt“ unten), Ergebnis an die
   andere Sitzung; dann „von mir nichts mehr“ melden.
5. Danach (welle4): Fixaufträge RM-629/585, RM-586, RM-588, RM-706, RM-626, RM-191, RM-700–702,
   Aktenzweig (Register RM-700ff, Prüfberichte versionieren), Abbau gelandeter Worktrees nach main.
Robert: Fortsetzung ab 16:00; Rückfragen erst wieder ab 11.10. 12:00, Signieren ~14:00.

Übergabe: `UEBERGABE.md` daneben. Agentenregeln: `AUFTRAG.md` daneben. Berichte der Bauagenten:
`../berichte-2026-10-10/<kürzel>.md`, Reviews: `../reviews-2026-10-10/review_<…>.md`.

Landung: nichts nach main/welle2, bis „Alles fertig“ (Sitzung „Übergabe Koordination 2026-10-07“)
„main steht“ und „welle3 angelegt“ meldet. Dann je Zweig: `origin/welle3` hinein (Kataloge nach
Schlüssel, ROADMAP/Archiv beide Seiten), betroffene Tests, `--no-ff` nach welle3, Push.
Reihenfolge: RM-571 zuerst; RM-624 vor RM-628 (Kontakttest muss nach RM-628 stimmen).
Neue RM-Nummern: **RM-700 bis RM-749** gehören dieser Sitzung („Alles fertig“ hat 692–699 und
750–799). Bis jetzt keine vergeben.

**10.10. nachts:** main = `a09d3a728` (welle2 gelandet), welle3 angelegt, Worktree `F:/sl-welle3`
gehört „Alles fertig“ — nicht darin arbeiten. Landen mit `land.sh <zweig> <meldung>` (daneben):
baut den `--no-ff`-Merge aus dem Baum des Zweigs, prüft Basis, Eltern und Baum, pusht nach welle3.
Danach der anderen Sitzung kurz Bescheid. Vier welle2-Zweige und `F:/sl-welle2` abgebaut.
RM-191 (Prusa) frei, frischer Zweig von welle3; RM-674 macht „Alles fertig“ nach RM-670.

| Gelandet auf welle3 | Merge | Zweig |
|---|---|---|
| RM-571 | `83519de44` | claude/lauf-a `c9c1b03cd` (Abbau nach main) |
| RM-624 | `be05705d6` | tests/kontakt-slicertest `0792f679c` (Abbau nach main) |
| RM-572 + RM-627 | `c4b6f3afa` | befund/kleine-ueberhaenge `4cba3d858` (Abbau nach main) |
| RM-589 (Bohrungen/Fuß) | `997ce9fcd` | einstellungen/loecher-rm589, Worktree F:/sl-loecher (Abbau nach main) |
| Fix Grundtext-Länge (RM-704) | `6cd271272` | fix/grund-laenge, Worktree F:/sl-kanaltext |
| RM-704 (Drache, Baumspitze) | `3fb648ffb` | einstellungen/drache-druck3 `1c0bf19e3`, Worktree F:/sl-drache3 (Abbau nach main) |
| RM-670 | `d1cc82ef0` | claude/lauf-e `e7d0e5a94`+Merge (Abbau nach main; Worktree F:/solidon-claude-e) |
| Fix Kanaltext-Länge (RM-627) | `a97c63add` | fix/kanal-text-laenge, Worktree F:/sl-kanaltext (Abbau nach main) |
| RM-584 T2 | `74788e63a` | einstellungen/stuetzstil `bd0def192` (Abbau nach main); Nachtrag L + Cura-Spitzenluft offen |

**10.10. nach 03:10:** Limit zurückgesetzt; rm586, rm670, rm585, rm589b, rm587 fortgesetzt,
rm627c neu (`a362d855272850750`). Woche bei 27 % (Rücksetzung 11.10. 19:00) → höchstens 6 Agenten.

**Limit:** 5-Stunden-Fenster am 10.10. ~00:35 bei 70 %, Rücksetzung 03:10 Ortszeit. Bricht ein Agent
am Limit ab: nach der Rücksetzung `SendMessage` an seine ID („weiter, Stand im Bericht und im
Zweig“) — er setzt mit seinem Verlauf fort; vorher `git status`/`git log` im Worktree lesen und
geänderte Python-Dateien mit `py_compile` prüfen.

**Drache Druck 3 (10.10. ~04:00, Robert):** Aus Übergabe `output/drache-2026-10-10/robert/Drache.3mf`
(09.10. 19:37, gedruckt 8h31m) Spitzen gut, Kinnunterseite faserig/durchhängend (Druck 2 war dort
gut), ein Vorderbein brach beim Stützenentfernen. Unterschied zu Druck 2: volle Elegoo-Grundlage
statt Orca-Vorgaben (Astabstand 2 statt 1, Winkel 45 statt 40, XY 0,35 statt 0,5, Wände 2 statt 3)
und oben/unten 0,4. Robert: „passe es gleich an, dann schaffen wir einen Druck noch“ → Agent
drache3 (`ae7da00730f76865c`): zuerst Matrix + druckfertiges `output/drache-2026-10-10/Drache-druck4.3mf`,
dann Solidon-Fix auf `einstellungen/drache-druck3` (F:/sl-drache3), Nummer **RM-704**.

**10.10. 05:11 Druckdatei 4 geliefert** (V12: Spitze 1,2 mm + 3 Wände, oben/unten 0,4 bleiben;
9:13 h, 182 g): `output/drache-2026-10-10/Drache-druck4.3mf` + `.gcode`; Ursache Kinn = oben 0,4
ohne Trennschicht, Bein = 2 statt 3 Wände (Bericht `berichte-2026-10-10/drache3.md`). Robert druckt
seit 04:29 einen Wiederholungsdruck der Übergabe von 19:37 (byte-gleich). Datei 4 ist für den
nächsten Druck; Alternative V18 (oben 0,2) besser am Kinn, aber Stachelreste kämen zurück.

**10.10. ~08:40:** zweites Limit überstanden; fortgesetzt drache3 (Teil B), rm670c, rm628b, rm589b,
rm585. RM-586 ruht (Arbeit im Worktree gesichert). Woche 54 % → höchstens 5 Agenten.

**SCHNITT welle3 HEUTE 22:00** (Robert, 10.10. 10:15; vorher 16:00). Rückfragen an Robert erst wieder ab
11.10. 12:00, Signieren 11.10. ~14:00, Fortsetzung ab 16:00. Bis 22:00 nach
welle3, was nachgeprüft ist: RM-704, RM-589, RM-585, RM-628, dazu RM-587 (Fix läuft, fertig bis
17:30 → Nachprüfung) und RM-629 (Review). RM-586, RM-588, neue Punkte → welle4. Nach
„welle3 geschlossen“ nichts mehr. Rückfragen an Robert bis morgen 12:00 nicht möglich.

**0.6.0 = welle3 (Robert, 10.10. ~09:50):** Schnitt durch „Alles fertig“ heute Nacht (nach L3, I, D,
Tor, Integrationsreview, CI). Bis dahin lande ich, was fertig und nachgeprüft ist: fest RM-670,
RM-704; dann RM-589, RM-585, RM-628; wenn es reicht RM-587, RM-629. RM-586, RM-588 und neue Punkte
→ welle4 (legt „Alles fertig“ nach dem Schnitt von main an). Nach „welle3 geschlossen“ nichts mehr
nach welle3. Nutzungslimit gemeinsam: höchstens 5 Agenten, Reserve für den Release-Weg der anderen
Sitzung; wird es knapp, zuerst RM-587/RM-629 zurückstellen. Release-Schritte (Handbuch, Bilder,
Version, Tag, Website) macht Robert.

## Agenten (Sitzung b00d64ab, gestartet 10.10. nachts)

| Kürzel | Art | Zweig / Worktree | Agent-ID | Stand |
|---|---|---|---|---|
| drache3 | RM-704 Teil A+B | einstellungen/drache-druck3 / F:/sl-drache3 | ae7da00730f76865c | fertig `917b49bbe` (Spitze 1,13 mm, Orca-Familie); Wände an Gliedern → welle4 |
| rv704 | Review RM-704, Urteil bis 13:30 | einstellungen/drache-druck3 | a81ced7b3b9147cf4 | fertig: kann landen nach M1–M3 (+L1, L3), kurze Nachprüfung über Fix-Diff; kein Formatschritt |
| drache3 (fortgesetzt) | Fixes M1–M3, L1, L3 bis 14:30 | einstellungen/drache-druck3 | ae7da00730f76865c | fertig `ddea0dd43`, Merge welle3 `076965bfe` |
| rv704n | kurze Nachprüfung Fix-Diff RM-704 | einstellungen/drache-druck3 | af88334fbcbe134f1 | fertig: nach N1 (Changelog/Grund nur Unterseiten) landbar ohne weitere Prüfung; N2–N4 leicht |
| drache3 (2. Fortsetzung) | N1–N4, welle3, dann ich lande | einstellungen/drache-druck3 | ae7da00730f76865c | läuft |

Neue Punkte aus Review RM-704: **RM-705** Abdruck der Verbrauchsbuchung ändert sich mit jedem neuen
Feld (welle3 betroffen, muss in 0.6.0 — übernommen: Zweig `fix/verbrauch-abdruck`, Worktree
`F:/sl-abdruck`, Agent rm705 `ab906639e11c65070` fertig `85ae9583a`; Review rv705 läuft, Urteil bis 18:00);
Orca-Plattenwerte laufen nicht durch `NOT_TAKEN_BY_PROGRAM` (Bambu bekommt fremde Schlüssel).
| rm627 | Bau: Reviewbefunde RM-627 | befund/kleine-ueberhaenge / F:/sl-befund | a97946db569a0a31b | fertig `0d165ce42` |
| rv627n | Nachprüfung RM-627 | befund/kleine-ueberhaenge / F:/sl-befund | af6f17b149bc25349 | fertig: **kann landen** (`review_rm627_nach.md`); vor dem Landen L1–L3 beheben + welle3 (mit RM-584!) hinein → Agent rm627c nach der Rücksetzung |
| rv584n | gezielte Nachprüfung N1/N2 (letzte Runde) | einstellungen/stuetzstil / F:/sl-stil | ad832bd3ca33fe901 | fertig, **gelandet** `74788e63a`: kann landen (`review_rm584_n1n2.md`); Rest: L (Feld fasst gleiche Werte nicht zusammen, `print_settings_dialog.py:7495`), Hinweis (Cura: Baum→Gitter-Zusammenführung, Spitzenluft fragt weiter mit Baum, `advise.py:1458/1118`) → Nachtragszweig nach dem Landen |
| rm584 | Bau: N1–N10 RM-584 T2 | einstellungen/stuetzstil / F:/sl-stil | a95d9708e3e2a75cc | fertig `c533f04a5`; welle3 hinein `89ac1ca6c` (5 312 + 327 grün, ruff/format/mypy) → gezielte Nachprüfung N1/N2 (wartet auf freien Platz) |
| rm670 | Bau: Zwischenstand, Messung, Abnahme | claude/lauf-e / F:/solidon-claude-e | ac98869857bd90714 | fertig `409c205d2`, archiviert; neue Punkte: 3MF-Geometrieschreiber langsam (Halter 1,58 von 2,7 s), Merker je Ordner, Vorwahl ohne gemerkte Maschine (RM-623/672) |
| rv670n | gezielte Nachprüfung (N1–N3 + `_once_per_stock`) | claude/lauf-e | a63ead5f806f6ce9c | fertig: **kann landen** (`review_rm670_n2.md`), L1–L3 vor dem Merge |
| rm670c | Bau: L1–L3, welle3 hinein | claude/lauf-e / F:/solidon-claude-e | a8fc9fc629da2b217 | läuft → danach landen, „Alles fertig“ Bescheid (RM-674) |
| rm628 | Bau: Cura-Rundung fertig, Slicertest | einstellungen/cura-rundung-rm628 / F:/sl-cura | abcaa9d88c5f0ddfa | fertig `0ca808f9b`; Patch für RM-624-Zusammenführung: `scratchpad/rm628/rm624_cura_patch.diff` (beim Merge welle3 anwenden, Registerzeile RM-628 aus RM-624 entfernen) |
| rv628 | Review RM-628 (+ Patch) | einstellungen/cura-rundung-rm628 / F:/sl-cura | af3cc54bcb55e39d9 | fertig: „nicht“ — S1 schwer (Cura-Fenster ohne Unterseite), M1–M3, L1–L5, Patch veraltet → Nachprüfung nötig |
| rm586 | Bau: feine Schichten fertig, alle Familien, welle3 hinein | einstellungen/schichten-rm586 / F:/sl-schichten | a859152b57c5fb8d6 | läuft → Review |
| rv624n | Nachprüfung RM-624 | tests/kontakt-slicertest / F:/sl-kontakt | a17d0d43668dfdbd7 | fertig: „nicht“, nach M1+L1 ohne weitere Prüfung landbar (`review_rm624_nach.md`) |
| rm624 | Bau: welle3 hinein, M1, L1 | tests/kontakt-slicertest / F:/sl-kontakt | a58e9d8adc16987f6 | fertig `0792f679c`, gelandet |
| rv585 | Review RM-585 | einstellungen/boegen-rm585 / F:/sl-boegen | a1f48011bf1f226f6 | fertig: „nicht“, S1 schwer (flache Decken als Bogen), M1, M2 → Nachprüfung nötig |
| rm585 | Bau: S1 (+Zwilling `_Ceilings.closes`), M1, M2, L1–L3, welle3 hinein | einstellungen/boegen-rm585 / F:/sl-boegen | af1aeaa2063d7e084 | fertig `acc6283d5` (neue Grenze `CANTILEVER_LAYERS`, Drachensperre 29 Säulen) |
| rv585n | Nachprüfung RM-585, Urteil bis 14:15 | einstellungen/boegen-rm585 | a98950331e17cad56 | fertig: „nicht“ — N1 schwer (`_held_twice` ohne Spannweitengrenze, Kumiko 81 mm frei; Fix eine Zeile `neu_fix8`), N2 schwer (Decken 11,3–17° entwarnt, braucht Entscheidung/Probedruck Pultdecke 12°, Haut 15° in 20 mm), N3 mittel (Drache 45° Flügeltasche verliert Sperre), N4–N7 leicht. **Entscheidung (ich): RM-585 → welle4**; ohne RM-585 Bögen mit Stütze wie bisher |
| rm589 | Bau: S1, M1–M3, L1–L6, Slicertest alle | einstellungen/loecher-rm589 / F:/sl-loecher | adca94d83002b1a85 | fertig `74f87bdef` |
| rv589n | Nachprüfung RM-589 | einstellungen/loecher-rm589 / F:/sl-loecher | aef57632a48a60400 | fertig: „nicht“ — N1 schwer (Anordnen vererbt Ausgleich der Nachbarn), N2–N4 mittel, N5–N10 leicht (`review_rm589_nach.md`) |
| rm589b | Bau: N1–N10, welle3 hinein | einstellungen/loecher-rm589 / F:/sl-loecher | a5d60e7b66a815683 | fertig `69f1cdd98`; neue Punkte (gekippter Fuß, Deckel erbt Fuß, Gegenform-Achse, Rastnasen-Merkmal …) im Bericht |
| rv589s | enge Schlussprüfung (N1/N2/N3/Tore) — Ausnahme zur Zwei-Runden-Regel (schwerer Neufund), Robert nennen | einstellungen/loecher-rm589 | a459bd1fb61e82c13 | fertig: „nicht“ — S1 mittel (Fuß nach Herkunft statt Lage), S2, S3 leicht; N1–N3 sonst gut, kein Formatschritt nötig |
| rm589c | Bau: S1–S3, welle3 hinein, bis 15:30 | einstellungen/loecher-rm589 / F:/sl-loecher | a927083f2218bd842 | fertig `971b05eaa` |
| rv589k | kurze Kontrolle Fuß (S1–S3) | einstellungen/loecher-rm589 | a123a0693f452f70a | fertig: S1–S3 gut, K1 leicht (Band nach Abschneiden/Zurückdrehen nicht am Bett) → Fix ohne neue Runde |
| rm589c (fortgesetzt) | K1, welle3, bis 18:30 | einstellungen/loecher-rm589 | a927083f2218bd842 | läuft → landen |
| rm587 | Bau: je Teil fertig, acht Programme, teil→rm587, welle3 hinein | einstellungen/bruecken-rm587(-teil) / F:/sl-bruecken(-teil) | a576b2efe7abe86d0 | fertig `31788ce82` (welle3 `aff70cb91` drin) |
| rv587 | Review RM-587 über beides | einstellungen/bruecken-rm587 / F:/sl-bruecken | a770dabd930bb6038 | fertig: „nicht“ — M1–M4 mittel, L1–L3 → Nachprüfung nötig |
| rm587b | Bau: M1–M4, L1–L3, welle3 hinein, bis 17:30 | einstellungen/bruecken-rm587 / F:/sl-bruecken | a8a8ff1ef511e8132 | fertig `641fb064a` |
| rv587n | Nachprüfung RM-587, Urteil bis 18:30 | einstellungen/bruecken-rm587 | (Agent-Liste) | läuft |
| rv629 | Review RM-629, Urteil bis 15:30 | einstellungen/schacht-rm629 / F:/sl-schacht | a1f43c521604fac69 | fertig: „nicht“ — F1 mittel (Kreis kriecht an leicht geneigter Wand, Fix 1b fertig), F6 mittel (schräger Schlitz mit waagerechter Weite → falsch offen, braucht Entwurf), F3 mittel (Knick/Engstelle abseits der Wand gesperrt, keine Regression), F2/F4/F5 leicht. **Entscheidung (ich, ohne Rückfrage): RM-629 → welle4**, ohne RM-629 bleiben schräge Schächte gesperrt wie bisher (sichere Seite) |

Robert 10.10. ~10:25: Fortsetzung um 16:00; bis dahin alles
weiterführen; „Alles fertig“ übernimmt danach Tor, Review, welle3→main, CI.
| rm628b | Bau: welle3+Kontakttest Cura, S1, M1–M3, L1–L5 | einstellungen/cura-rundung-rm628 / F:/sl-cura | a3fd9d255141f5563 | fertig `c9683c3d4` |
| rv628n | Nachprüfung RM-628, Urteil bis 19:00 | einstellungen/cura-rundung-rm628 | aa0709a6d582c068e | fertig: nach M-a (Trennschicht erreicht Cura-Fenster nicht) landbar nach Durchsicht nur dieser Änderung; L-a–L-e leicht |
| rm628b (fortgesetzt) | M-a, L-a–L-e bis 17:00 | einstellungen/cura-rundung-rm628 | a3fd9d255141f5563 | fertig `df5eb90df` |
| rv628d | Durchsicht M-a | einstellungen/cura-rundung-rm628 | (Agent-Liste) | läuft → landen |
| rm629 | Bau: Schacht je Schicht fertig | einstellungen/schacht-rm629 / F:/sl-schacht | af24ba6d6cfc988c5 | fertig `a675390e6` → Review (wartet); Grenze „Lippe im schrägen Schacht sperrt“ im Review bewerten |

`F:/sl-schichten/t1.txt` gelöscht (Testausgabe).

## Neue Punkte (Nummern ab RM-700, noch nicht im Register — mit einem Aktenzweig auf welle3 eintragen)

Vergeben (10.10.): **RM-707** Spulenwerte aus 0.5.3 ändern nach dem Update still den Druck
(fehlende Felder → Dataclass-Vorgabe → Abweichung an den Slicer) — 0.6.0, im Zweig von RM-705;
**RM-705** Verbrauchsabdruck (0.6.0; Review: kann landen nach M1/M2; Fixes + RM-707 fertig
`a33b58a19`; Review RM-707 + Nachprüfung RM-705 läuft, Urteil bis 17:30); **RM-706** Geometrieteil des Abdrucks aus
gespeicherten Eingängen statt ausgewertetem Netz, alter Weg als Altabdruck, Wächter gegen
umsortierte Dreiecksfolge — welle4, **muss vor RM-698 (Sparen) landen**.

Vergeben (10.10. nachts):
- **RM-700** Leistung `support_need`/Kanalfrage: Säulenabstieg je Stück, Clipper gegen ganze Schicht
  (Hüllbox-Zuschnitt gemessen: Drache 45° 18,1 → 8,2 s, bitgleich; festes Raster je Schicht
  sollte mehr bringen), Merkerkapazität `_ANSWERS_KEPT = 4` reicht im kalten Fall (> 8 Körper)
  nicht (RM-627 L1)
- **RM-701** Brückenweite bei geschlossenen Ringen falsch (`analysis.py:2659–2661`, seit v0.3.0):
  Wand mit Flanke ringsum + Steg 20 mm → 0 (keine Stütze); Rohr mit ausgestellter Wand + Sporn →
  39,3 mm (falsche Stütze). Aus Nachprüfung RM-627.
- **RM-702** Cura-Drucker mit eigenem Ausgleich (s. u.)
- **RM-703** Druckprobe für Robert: Cura Baum gegen normale Stütze unter flachem Hut (s. u.)

Noch ohne Nummer:

- Cura-Drucker mit eigenem Ausgleich: 75 Cura-Definitionen außerhalb von Solidons Druckern setzen
  `xy_offset_layer_0`/`hole_xy_offset`; Dialog zeigt 0, kein Rat. Wert aus der Kette lesen wie
  `manufacturer.cura_fan_curve` (aus RM-589).
- `support_need` braucht Minuten (Eiffelturm 171–182 s, Drache 463–474 s CPU), vor allem
  Säulenabstieg in `_model_support` (`_material_cross` je Stück, 17 099 Aufrufe); die Kanalfrage
  je Säule rechnet Clipper-Differenzen gegen die ganze Schicht (am Drachen 18 von 22 s für ein
  Stück) — Fix: Schicht je Säule auf ihre Hüllbox zuschneiden, bitgleich (aus Review RM-585 und
  RM-627). Erst nach RM-584/RM-627 (gleiche Stelle), vor oder mit RM-626.
- Druckprobe für Robert: Cura Baum gegen normale Stütze unter flachem Hut (aus RM-584).
- Prüfberichte unter `.claude/.state/drache-2026-10-08/reviews-2026-10-09|10/` und
  `berichte-2026-10-10/` sind unversioniert, das Archiv verweist darauf → am Ende mit einem
  Aktenzweig auf welle3 versionieren; im Hauptbaum dann die gleichlautenden unversionierten
  Kopien entfernen (sonst hält der Merge im Hauptbaum an).

## Warteschlange

**Vor dem Schnitt 22:00 selbst fahren:** Beispielsonde aus Review RM-705 (N2) an einer Kopie von
origin/welle3: `sonde.py <kopie> beispiele …` (scratchpad\rv705\, Pfade mit `/`), Prüfsummen gegen
`beisp\ergebnis.k053.beispiele.json` — jede Abweichung außer `gehaeuse-mit-bausteinen` ist ein
Bruch der Verbrauchswiedererkennung gegen 0.5.3 → „Alles fertig“ melden.
Werkzeug fertig: `koord/beisp_vergleich.py <ergebnis.k053.json> <ergebnis.neu.json>`. Lauf 10.10.
nachmittags: welle3 `997ce9fcd` 19/21 Körper gleich (nur gehaeuse-mit-bausteinen anders), Abdrücke
0/12 (RM-705 fehlt noch); RM-705-Zweig `a33b58a19`: 11/12 gleich (nur gehaeuse). Nach Landung von
RM-705 am fertigen welle3 wiederholen.

Nach der Limit-Rücksetzung (03:10), in dieser Reihenfolge:
0. rm627c: welle3 in befund/kleine-ueberhaenge (Konflikte mit RM-584 in analysis/advise), L1–L3 aus
   `review_rm627_nach.md` (L1: Archivsatz + Merkerzahl; L2: zwei Abbruchtests mit Zähler-Token;
   L3: Docstring `_from_spans`), betroffene Tests → landen (RM-572 + RM-627)
1. rm628b (Auftrag `auftrag-rm628b.md`)
2. Review RM-629 (`a675390e6`, Grenze „Lippe im schrägen Schacht“ bewerten)
3. RM-584-Nachtrag, frischer Zweig von welle3: L aus `review_rm584_n1n2.md` (Feld fasst gleiche
   Werte zusammen) und Hinweis Cura-Spitzenluft nach Baum→Gitter (am Drachen neben dem Pilz messen)
4. RM-588 (F:/sl-naht): Druckzeittests fertig → Review
5. RM-191 (frischer Zweig von welle3): Prusa ohne Herstellerbündel Wandzahl und
   `extra_perimeters = 0`, dann prusa:CC2 gegen elegoo:CC2 (Register sagt noch „In Arbeit: Claude,
   Worktree F:/solidon-claude-c“ — der existiert nicht mehr)
6. RM-626 (frischer Zweig von welle3, nach RM-627 auf welle3 — alle drei ändern `_model_support`)
7. Leistung `support_need`/Kanalfrage (neue Nummer), nach RM-626
8. RM-584-Rest (Fuß hoher Bäume, Spitzenabstand PETG/ASA/ABS, Schwelle)
- Danach: Nachprüfung RM-670 (nach Bau), Nachprüfung RM-585, RM-628; enge Prüfung RM-589; Review
  RM-586, RM-587
