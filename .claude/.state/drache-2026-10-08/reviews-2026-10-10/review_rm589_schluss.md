# Schlussprüfung RM-589 — dritte Runde

Prüfling: Worktree `F:\sl-loecher`, Zweig `einstellungen/loecher-rm589`, HEAD
`69f1cdd98` (welle3 bis `a97c63add` enthalten). Nachprüfung
`reviews-2026-10-10/review_rm589_nach.md`, Bericht des Bauagenten
`berichte-2026-10-10/rm589b.md`. Geprüft nur N1, N2, N3 und die Tore (Auftrag). Sonden und
Ausgaben: `scratchpad\rv589s\` (Kopie `mut` = `69f1cdd98` per `git archive`; Slicerläufe mit
umgebogenem `APPDATA`/`LOCALAPPDATA` unter `rv589s\nutzer\`). Am Worktree nichts geändert,
`git status` leer.

## Urteil

**Nicht.** N1 ist für die Nachbarn behoben (Anordnen, Ausrichten, Kopieren, Bohrung und
Passung am Nachbarn, beide Beispiele, OrcaSlicer: B behält 0,380 mm Einzug). N2 ist richtig
hergeleitet und liegt auf der sicheren Seite, N3 braucht keinen Formatschritt, alle Tore
sind grün. Offen bleibt S1: Der Fuß zählt weiter an der Herkunft statt an der Lage. Nach
*Ausrichten*, das den Körper hinlegt, nach waagerechtem *Teilen* (obere Hälfte) und am
*Deckel* bekommt ein Körper ohne eingezogenen Rand am Bett den Rat „Erste Schicht einziehen
→ 0“. Übernommen druckt er am echten OrcaSlicer ohne Einzug (liegender Turm: Schicht 1 nur
0,080 mm schmaler als die Mitte statt 0,380). Auf `main` druckt derselbe Körper richtig.
Nach dem Fix von S1 (dazu S2, S3) reicht eine Nachprüfung von `allowances_for` für den Fuß
mit den neuen Tests.

## Funde

### Mittel

**S1 Der Fuß zählt an der Herkunft, nicht an der Lage: Nach *Ausrichten*, das kippt, nach
waagerechtem *Teilen* und am *Deckel* bekommt ein Körper ohne eingezogenen Rand am Bett den
Rat „Erste Schicht einziehen → 0“.**
`app/core/scene/fits.py:423-425` (`allowances_for`: `FOOT_OP` in den Schritten der Herkunft
genügt), Herkunft aus `_producing` (`fits.py:343-369`: neu entstehende Körper erben alle
Eingänge).

- Sonde `n1b.py` (K1 Max, PETG): Turm 10×10×60 mit *Elefantenfuß ausgleichen*, danach
  *Ausrichten* — der Turm wird hingelegt (Maße 10×60×10, Rahmen-Z (0,−1,0)), Ausgleich
  bleibt `('foot',)`. Der eingezogene Rand liegt jetzt an einer Stirnseite, am Bett liegt eine
  Längsseite ohne Einzug.
- Sonde `n1.py`: *An Ebene teilen* waagerecht (Achse z, 5 mm) — obere Hälfte steht auf der
  Schnittfläche, Ausgleich `('foot',)`, Rat → 0. *Deckel erzeugen* nach dem Fußausgleich —
  Deckel `('foot',)`, Rat → 0. *Drehen* x 90°/180° und *Spiegeln* z — Rahmen-Z (0,−1,0) bzw.
  (0,0,−1), weiter `('foot',)`.
- Am echten Slicer (`turm_slicer.py`, OrcaSlicer 2.4.2, K1 Max, Herstellerprozess Einzug
  0,15, Turm + Fuß + Ausrichten, Rat übernommen wie im Dialog, gepinnt, EXIT=0): Zeile
  „Erste Schicht einziehen 0 — Das Modell zieht den Fuß schon selbst ein.“ für `['T']`,
  Objektwert `elefant_foot_compensation = 0`, Schicht 1 gegen Mitte **0,080 mm** — kein
  Einzug am Bett; mit dem Einzug des Slicers wären es 0,380 mm (B in N1, gleicher Drucker
  und Prozess). Der liegende Turm druckt mit Elefantenfuß.
- Bei der oberen Hälfte eines Teilens mit Stiften liegen die Stiftlöcher genau in dieser
  ersten Schicht. Auf `main` druckt derselbe Körper richtig, weil der Slicer einzieht —
  RM-589 verschlechtert diese Wege.
- *Ausrichten* bietet der Prüfbericht selbst an (`main_window.py:26842`, Handlung der
  Schichtanalyse „andere Lage“), also oft nach dem Fußausgleich.
- Der Bauagent nennt Kippen und Deckel als „neue Punkte“ (`rm589b.md`); das waagerechte
  Teilen ist derselbe Fall. Kein Test deckt einen kippenden oder neu entstehenden Körper
  nach dem Fußausgleich ab.

**Fix:** „foot“ am fertigen Körper entscheiden, im Zweifel Herstellerausgleich (wie N2):
(1) nur, wenn die Z-Spalte des Rahmens nach oben zeigt (`column[2]/norm >= cos(EPS_ANGLE)`,
mit Vorzeichen — gewendet zählt nicht; Annahme wie `_pocket_closes`: beim Einziehen stand
der Körper aufrecht); (2) nur auf der eigenen Linie des Körpers — Schritte an Ort und Stelle
und reine Kopien (`leaves_inputs_unchanged`, etwa *Duplizieren*), nicht über einen Schritt,
der ihn aus einem anderen neu erzeugt (Teilen, Deckel). Genauer wäre ein Merkmal, das
`compensate_first_layer` an das eingezogene Band stempelt und das am fertigen Körper unten
liegen muss (dann `cache_version` des Schritts). Tests am gerechneten Körper: Turm + Ausrichten
→ `()`, Drehen 180° → `()`, Teilen z → untere Hälfte nach (2) `()` oder mit Merkmal `foot`,
obere `()`, Deckel `()`, Kopie weiter `foot`.

### Leicht

**S2 Eine senkrechte Bohrung durch eine schräge, dünne Wand zählt, obwohl keine Schicht sie
umschließt.** `app/core/scene/fits.py:451-488` (`_closes_in_a_layer`). Die Herleitung setzt
voraus, dass die Enden quer zur Achse stehen („Solidons Schritte bohren senkrecht in eine
Fläche“). Das stimmt nicht immer: Eine *Bohrung* mit Achse z in einen gekippten Körper
mündet schräg in den Plattenflächen, und die Merkmalstiefe ist die Achsspanne der Wand
(`prepare_ops.py:2618-2626`, `:2750-2752`). Sonde `n2.py`: Platte 3 mm,
um 60° gekippt, dann senkrecht Ø 6 mit Haken gebohrt: Tiefe 16,05, Urteil „schließt“,
Ausgleich `('holes',)` — der Schnitt (alle 0,05 mm) umschließt das Loch in keiner Schicht
(Streifen 3/sin 60° = 3,46 mm < 6,2 mm). Folge: Rat „Löcher weiten → 0“ ohne Wirkung an
diesem Loch, übernommen verlieren andere, unausgeglichene Löcher des Teils den
Herstellerausgleich. Selten. **Fix:** Wanddicke und Neigung aus den Mündungsebenen
(`_bore_end_planes`, beide Kerne) statt aus Achse und Tiefe, wo es sie gibt:
`d/cos θ_Achse < L_quer/sin θ_Mündung`; sonst wie bisher. Test: gekippte dünne Platte,
danach senkrecht gebohrt → `()`, gegen den Schnitt.

**S3 Der Projektweg von N3 hat keinen Test.** `app/core/knowledge/profiles.py:323-345`
(`_measured`, Zweig `start is None`) und `carry()` (`profiles.py:528-555`). Ein eigenes
Material aus einer älteren Projektdatei (`calibrated = true`, kein `measured`) gilt als ganz
gemessen — richtig und gleich dem bisherigen Verhalten (Sonde `n3.py`: `('clearance',
'elephant_foot', 'hole_compensation', 'press', 'shrinkage')`), aber nur für das mitgelieferte
PETG ist der Altweg geprüft (`test_an_older_calibration_counts_what_left_the_start_value`).
**Fix:** Test über `profiles.carry({"materials": {...}})` ohne und mit `measured`, dazu
Speichern/Öffnen eines Projekts mit eigenem kalibriertem Material (`carried_profiles`
behält `measured`).

## N1 — Herkunft je Körperkennung: für Nachbarn behoben

Sonde `n1.py` (K1 Max, PETG; A mit *Elefantenfuß ausgleichen*, B ohne):

| Schritt danach | A | B / neuer Körper | richtig? |
|---|---|---|---|
| keiner | `foot` | B `()` | ja |
| Anordnen | `foot` | B `()` | ja |
| Ausrichten (Quader bleibt stehen) | `foot` | B `()` | ja |
| Spiegeln x | `foot` | B `()` | ja |
| Kopieren (+ Anordnen) | `foot` | Kopie `foot`, B `()` | ja |
| Bohrung mit Haken an B + Anordnen | `foot` | B `holes` | ja |
| Mutternfalle an A + Anordnen | `holes`, fit_kinds `clearance` | B `()`, fit_kinds `()` | ja (Zwilling mit) |
| Teilen senkrecht (Achse x) | beide Hälften `foot` | – | ja |
| Teilen mit Stiften (+ Anordnen) | Stifthälfte `()` | Lochhälfte `holes` | ja |
| Vereinigen A+B / B+A | `foot` | – | halb: B-Anteil ohne Einzug (Mischfall, kein eigener Fund) |
| Ausrichten, das kippt (Turm, `n1b.py`) | **`foot`** | – | **nein** (S1) |
| Teilen waagerecht | untere `foot` | **obere `foot`** | **nein** (S1) |
| Deckel erzeugen | `foot` | **Deckel `foot`** | **nein** (S1) |
| Drehen 90°/180°, Spiegeln z | **`foot`** | – | **nein** (S1) |

„Verknüpfen“ als *Vereinigen* gelesen (eine Op dieses Namens gibt es nicht).

Ausgelieferte Beispiele (`beispiele.py`, alle zwölf): `aushoehlen-und-teilen.p3d`
Stifthälfte `()`, Lochhälfte `holes` (`bore_1/2`, Erzeuger `split_pinned`, Achse z);
`dose-mit-deckel.p3d` Dose `()` (Kabeldurchführung Achse (1,0,0), Wärmeeinsatz ohne Spiel),
Deckel `()`. Beide richtig; die übrigen ohne Auffälligkeit.

OrcaSlicer 2.4.2 einmal (`anordnen_slicer.py`, K1 Max, Herstellerprozess Einzug 0,15, mit
Anordnen, Rat übernommen, gepinnt, EXIT=0): A `foot`, B `()`; Zeile nennt nur `['A']`;
Objektwert A `elefant_foot_compensation = 0`, B keiner; Schicht 1 gegen Mitte A 0,480 mm,
**B 0,380 mm — B behält den Einzug des Slicers.**

## N2 — Bohrung zählt, wenn `L·cos θ > d·sin θ`

**Herleitung stimmt** für Löcher mit Enden quer zur Achse: Die Wand der Dicke L schneidet
eine waagerechte Ebene als Streifen L/sin θ, der Zylinder Ø d als Ellipse d/cos θ; die
Ellipse passt in mindestens einer Schicht ganz hinein, wenn d/cos θ < L/sin θ. Am
gerechneten Körper gegen den echten Schnitt (`n2.py`, Ø 6 mit Haken = 6,2):

| Fall | Urteil | Schnitt umschließt | Ausgleich |
|---|---|---|---|
| senkrecht, 8 mm | schließt | ja | `holes` |
| waagerecht (Achse x) | nein | nein | `()` |
| Sackloch senkrecht 4 von 8 | schließt | ja | `holes` |
| gebohrt, dann um 30° / 50° gekippt (Grenze 52,2°) | schließt | ja | `holes` |
| gebohrt, dann um 56° gekippt | nein | nein | `()` |
| 4 mm, um 45° gekippt (Grenze 32,8°) | nein | nein | `()` |
| ohne Haken | schließt | ja | `()` |
| dünne Platte gekippt, danach senkrecht gebohrt | schließt | **nein** | **`holes`** (S2) |

Sackloch: Für ein schräges Sackloch gibt es zusätzlich Schichten mit angeschnittener,
geschlossener Restkontur am Grund, die die Formel nicht zählt (hergeleitet, nicht
gemessen) — dort bleibt der Herstellerausgleich, die sichere Seite. Der Test
`test_a_tilted_hole_counts_while_a_layer_closes_around_it` nimmt seinen Sollwert aus dem
Schnitt (trimesh), nicht aus der Formel.

**Die Verhaltensänderung ist die sichere Seite.** Zählt eine Öffnung fälschlich, nimmt der
übernommene Rat allen anderen Löchern des Teils den Herstellerausgleich (Kobra 2 0,02,
Ender-3 V3 KE 0,025 mm je Seite; sie werden um 0,04–0,05 mm enger, ein Stift im
unausgeglichenen Loch kann klemmen). Zählt sie fälschlich nicht, bekommt die Aussparung den
Ausgleich doppelt und wird um denselben Betrag weiter: Eine Rastnasen-Aussparung oder
Schnappverbinder-Tasche mit 0,5–1,5 mm Hinterschnitt rastet weiter, die Passung geht
zusammen. Zu weit ist beim Zusammenbau harmlos, zu eng nicht.

## N3 — `MaterialProfile.measured`

- **Nutzerordner (`materials.toml`):** neuer Schlüssel `measured` (Liste). Rückwärts: Eine
  ältere Datei ohne ihn zählt, was vom mitgelieferten Startwert abweicht (`n3.py`: alle
  Werte gleich Start → `None`; Fuß verschoben → `('elephant_foot',)`), getestet. Ein
  zufällig dem Startwert gleicher Messwert gilt dann als ungemessen; der Rat erscheint
  wieder, braucht einen Klick und kostet übernommen höchstens den Herstellerausgleich —
  die mildere der beiden Fehlrichtungen, kein Fund. Vorwärts: Ältere Fassungen lesen nur
  bekannte Schlüssel (`_material_from_table`, keine Schlüsselliste in `read_table`) und
  übergehen `measured`; schreiben sie die Datei neu, macht ihr `_literal` daraus
  `['clearance', 'elephant_foot']` — gültiges TOML, tomllib liest es zurück (`n3.py`).
- **Projektdatei:** `measured` reist mit einem eigenen Material in
  `carried_profiles.materials.<id>` (`material_definition` → `_as_table` über `asdict`).
  `project._validate` prüft dort nur, dass es Tabellen sind; ältere Fassungen übergehen den
  Schlüssel. Ohne ihn (ältere Datei) gilt jeder eingetragene Wert als gemessen — dieselbe
  Bedeutung wie bisher.
- **`format_version`, Migration, Beispieldatei: nicht nötig.** Kein gespeicherter Wert
  ändert seine Bedeutung (`.claude/rules/dateiformat.md`, „Migration ist Pflicht“), der
  neue Schlüssel ist optional und abwärts lesbar; so sind auch `support_tip_gap` und
  `support_gap_*` ins Materialprofil gekommen (`1ddb4953a`, `adb99b83f`, ohne
  Formatschritt). Fehlt nur der Test des Projektwegs (S3). Sollte Robert den Schritt
  trotzdem wollen: welle3 steht bei Format 51 (Migration 50→51, `example_v51.p3d`), die
  nächste freie Nummer ist **52**.
- **Kalibrierdialog:** schreibt nur eingetragene Felder (`valueChanged` und `textEdited` —
  auch das Neueintippen derselben Zahl zählt), Wand und Überhang mit ihrem Haken
  (`dialogs.py:567-595`). `test_calibration.py` mit Fenster 14 bestanden, darunter
  `test_the_dialog_measures_only_the_fields_that_were_entered` (nur Spiel eingetragen →
  Fußrat bleibt).

## Tore (Kopie von `69f1cdd98`, gepinnt `FFFFF0FF`, `app` aus der Kopie)

| Lauf | Ergebnis |
|---|---|
| `ruff check --no-cache .` | sauber, EXIT=0 |
| `ruff format --no-cache --check .` | 1205 Dateien, EXIT=0 |
| `mypy` (Cache im Scratch) | 374 Dateien, keine Fehler, EXIT=0 |
| `test_text_length.py`, `test_translations.py`, `test_changelog.py` ohne Fenster, `-n 4` | 288 bestanden, 1 übersprungen, EXIT=0 |
| `test_print_settings_ui.py` mit Fenster | 334 bestanden, 109 abgewählt, EXIT=0 |
| `test_calibration.py` ohne Fenster / mit Fenster | 59 bestanden, EXIT=0 / 14 bestanden, EXIT=0 |
| Sonden `n1.py`, `n1b.py`, `n2.py`, `n3.py`, `beispiele.py` | je EXIT=0 |
| OrcaSlicer `anordnen_slicer.py` (mit Anordnen) | EXIT=0 |
| OrcaSlicer `turm_slicer.py` (Turm, Fuß, Ausrichten) | EXIT=0 |

Nicht gelaufen: volles Tor, CI, übrige Slicer (Auftrag: nur prüfen, was genannt ist).
Beim Landen beachten: welle3 ist seit dem Merge in `69f1cdd98` 90 Commits weiter (Format 51);
RM-589 berührt `migrations.py` nicht.

Hinweis zum Ablauf: Ein versehentlicher Aufruf `python -` mit leerem Heredoc (10:30) hing
und wurde nach zwei Minuten per PID beendet (4232, 75304); er hat nichts gelesen oder
geschrieben.
