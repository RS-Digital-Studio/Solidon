# Bau „zeichnenbau" — Etappe 1: Z0 und Z1 aus der Bedienabnahme Zeichnen

Arbeitsbaum `F:\3D Druck.review-050\wt-zeichnenbau`, Basis `0367d202`.
Grundlage: `reports/zeichnen-bedienung.md` (Abschnitte 7 und 8), Auftrag
Robert 23.09.2026.

**Stand: fertig** — Etappe 1 (Z0, Z1) gebaut und geprüft, Patch liegt bei.

## Gelesen

AGENTS.md, CLAUDE.md, AUFTRAG-BAU.md, Bericht zeichnen-bedienung.md
vollständig, `.claude/rules/zeichenflaeche.md` vollständig,
`app/core/sketch/CLAUDE.md`, `app/ui/CLAUDE.md` (Skizzenteile), Erinnerungen
aus der Pflichtliste.

## Bauschritt 1 — Kern (Z0 F1–F3, Z1 E4)

**F3 Verrunden/Fase strecken ein bemaßtes Rechteck — vollständige Lösung
gebaut, nicht die Zwischenlösung.** „Punkt auf Linie" gibt es im Löser nicht
(`solver._CONSTRAINT_TARGETS`), aber die Kollinearität lässt sich ohne neue
Bedingungsart sagen: `parallel(fern, gekürzt, fern, Hilfspunkt)` — zwei
Strecken vom selben fernen Ende, parallel, heißt „auf derselben Geraden".
`edit._held_by_the_virtual_corner` legt die alte Ecke als Hilfspunkt
(Konstruktionspunkt) an, hält ihn auf beiden verlängerten Schenkeln und hängt
alles, was am Eckende hing (Seitenmaß, Deckung mit Drittem, Festpunkt), an ihn
um; nur Richtungsbedingungen der ganzen Linie (waagerecht, parallel …) bleiben
am Reststück. Freiheitsgrade unverändert (zwei Koordinaten, zwei Gleichungen).
Liegt ein Schenkel achsparallel, nimmt `_on_the_leg` die lineare Achse statt
`parallel` — gemessen: `parallel` schob beim Ziehen einer **unbemaßten** Seite
die freie Gegenseite um 1,9 µm je 10 mm Zug (Krümmung der Einheitsvektoren),
die Achsgleichung bleibt unter 10⁻⁸ wie vorher. Die Fase misst jetzt, wie
getippt, von der alten Ecke aus (Maß + gleich lang) und ist damit bestimmt —
vorher blieb ihr Winkel frei („Noch ein Maß fehlt").
Gegenprobe am alten Stand (`git show HEAD:…edit.py`, Sonde im Scratchpad):
Hülle (0|−3,18)–(80|51,82) mit Rundung, (0,29|−2,14)–(80,29|50,71) mit Fase;
neu (0|0)–(80|50) für beide, alle vier Ecken (Test
`test_breaking_a_corner_keeps_a_typed_rectangle_at_its_size`, 8 Fälle).

**F2 Tasche auf außermittiger Fläche.** `sketch_pocket` verschiebt eine
gezeichnete Kontur nicht mehr um X/Y (die Felder gelten nur der Grundform);
`cache_version` erhöht. Der bestehende Test
`test_a_drawn_sketch_cuts_a_pocket_where_x_and_y_say` hielt das alte
Verhalten ausdrücklich fest („x und y verschieben auch den gezeichneten
Umriss") — umgeschrieben auf `…_keeps_its_place_whatever_x_and_y_say`.
Neue Tests exakt und Netz (Quader mit Mitte bei (50|30), Fläche als Merkmal):
600 mm³ ± 0,5 %, vorher 0,0.
**Hinweis Dateiverträglichkeit:** Ein gespeichertes Projekt mit Zeichnung
**und** X/Y ≠ 0 rechnet jetzt am Ort der Zeichnung. Solche Schritte konnten
nur durch den Fehler entstehen (die Felder standen verdeckt hinter „Weitere
Einstellungen" und wurden aus der Auswahl befüllt); keine Formatmigration.

**F1 Hochziehen auf der gewählten Fläche.** Kern: `_is_the_drawing_face` —
nennt „Bis zur Fläche" die Zeichenfläche selbst, kommt eine eigene Absage
(`constraint="drawing_face"`, Handlung „Die Höhe wieder als Zahl eintragen")
statt „liegt hinter der Skizze". Die Oberfläche trägt sie ohnehin nicht mehr
ein (Bauschritt 2).

**E4 „anfügen" — neue Operation `sketch_join` („An Körper anfügen").**
Eingang wie `sketch_pocket` (`consumes=1`), dieselben Felder wie das
Hochziehen (gemeinsame Basis `RaisedOutlineParams`, ohne Namen), exakt über
die OCC-Vereinigung, am Netz über die Rückfallkette mit `BOOLEAN_OVERLAP` in
den Körper hinein. Befunde: `sketch.join_apart` (über `fell_apart`, wenn der
Umriss den Körper nicht berührt, mit Weg „Grundform hochziehen") und
`boolean.without_effect` (Vereinigung ohne Zuwachs). `caveat` gesetzt. Steht
in der Variantengruppe „Aus Skizze erzeugen …" direkt nach dem Hochziehen —
kostet keine Menüzeile. Tests: exakt +π·16·10 auf 10⁻⁶, Netz an
außermittiger Fläche ± 0,5 %, ein Stück, Name und Kennung bleiben;
Paritätsfall in `test_exact_body_parity` (beide Kerne).
Zahlen nachgezogen: 137 Operationen, 1258 Parameter, 37 mit `caveat`,
148 Werkzeuge (`grenzen.md`, `oberflaeche.md`, `agentenschicht.md`,
`test_registry_consistency._ZAHLWORT`).
**Offen: `llm.PROMPT_TOOL_COUNT`** verlangt eine neue Tokenzählung gegen
qwen3:14b (`tools/measure_local_model.py --count-tokens`). Ollama läuft,
qwen3:14b ist aber gerade von einer anderen Sitzung geladen; das Werkzeug
entlädt am Ende (`keep_alive 0`) und würde deren Lauf stören. Siehe Schluss.

## Bauschritt 2 — Oberfläche (Z0 E2/B3/E9/R5, Z1 vollständig)

- **E2 „Die Artenliste unter *Fertig* geht nie auf" — Ursache eingegrenzt.**
  Gemessen mit echter Maus (`SendInput`, Sonde `f3_menue_echt.py`, ohne
  Sandbox): Das Menü **geht auf** und bleibt offen, Esc schließt es ohne
  Dialog. Mit `QTest.mousePress/mouseRelease` (Sonde `f2_menue_zeit.py`)
  dagegen: Menü nach dem Drücken offen (40 ms, 100 ms), das Loslassen geht an
  den **Knopf**, `clicked` → `finish_sketch` → Dialog der Vorgabe, das Menü
  schließt (Stapel in der Sonde belegt). Ursache also: Ein Knopf trug zwei
  Bedeutungen (`setMenu` **und** `clicked`); welche galt, entschied die
  Zustellung des Loslassens — echte Maus: Menü; Eingabetaste, `QTest`,
  Barrierefreiheit (`click()`): Dialog. Die Abnahme sah den zweiten Weg.
  Behoben nach dem Grundsatz des Berichts: *Fertig* ist ein Knopf ohne Menü,
  die übrigen Arten hängen an einem eigenen Knopf *Mehr* (ohne `clicked`).
  Die Liste blendet aus, was als Knopf daneben steht.
- **B3** Beim Betreten wird die Statuszeile geleert (`_clear_the_status_line`).
- **E9** Die Karte im Bild spricht nur vom Abtragen, wenn es ein Ziel gibt.
- **R5 (Entscheidung Robert 4)** Escape: Kette → Werkzeug → Auswahl → Satz
  „Zum Verlassen: Fertig oder Verwerfen." Verwirft nie. Statuszeile sagt
  „Freies Zeichnen. Fertig übernimmt die Zeichnung."
- **F1/F2 in der Oberfläche** `run_operation` übernimmt mit Zeichnung nichts
  aus `_from_selection` (`_carries_a_drawing`); der Dialog leert ein
  „Bis zur Fläche", das auf der Zeichenfläche liegt
  (`OperationDialog._release_the_drawing_face`, für den Weg „Zeichnen …" aus
  dem Dialog heraus).
- **Z1** komplett nach Abschnitt 7: Zielauflösung (genannt → Schritt →
  Fläche → eine Auswahl → neu; mehrere → Frage in der Leiste), Nachbarn
  standardmäßig **ausgeblendet** (`Viewport.set_sketch_focus`, eigene Regel
  neben `_hidden`), *Nachbarn zeigen* (Knopf, Taste N) durchscheinend 8 %,
  ohne Kanten, nicht anklickbar; Feld *Ziel* in der Leiste (nachträglich
  wählbar); Ebenenfeld/Projizieren/Flächenkontur nur Zielkörper (≤ 8 Flächen,
  gewählte immer dabei); fünfte Ebenenkarte „Oberseite von …"; Hochziehen =
  *An Körper anfügen* am Ziel, sonst neu; Abtragen nur mit Ziel; Fertig über
  dem Ziel = Tasche; Sicht beim Verlassen zurück (Platte, Werkzeug,
  Explosion, Darstellung, Projektion); Ziel verschwindet → Zeichnung bleibt,
  Satz, Fertig = neu; B2/S2 zwei Zeilen im Auswahlfenster jeder ebenen Fläche;
  E6 „Zeichnung weiterverwenden" im Verlauf (Entscheidung Robert 2).
- **Abgelöste Entscheidung:** Robert 30.08.2026 („in Fusion wählt man vor dem
  Abtragen keinen Körper aus", Suche nach dem Körper unter der Zeichnung über
  Hüllquader) ist durch Roberts Vorgabe vom 23.09.2026 ersetzt. Die Lage
  entscheidet nur noch die Art (Tasche/anfügen) **am Zielkörper**. Vier
  Fenstertests, die das alte Verhalten festhielten, sind umgeschrieben
  (`test_sketch_editor`, `test_field_ui`, `test_ui`), dazu drei zum Escape.

## Abnahme an echten Modellen (Sonden `z0_abnahme.py`, `z0c_platte.py`, `z1_ziel.py`)

| Fall | Modell / Kern | Soll | gemessen |
|---|---|---|---|
| F1 anfügen (Hochziehen) | build_tray_v3.step Fläche 236, exakt | π·16·10 = 502,65 ± 0,5 % | 502,6548, kein Fehler |
| F1 neuer Körper (Mehr → Grundform hochziehen) | dto. | 502,65 | 502,6548 |
| F2 Tasche 20 × 10 × 3 | dto. | 600 ± 0,5 % | 600,0000, keine Warnung |
| F1 anfügen | build_tray_v3 nach „Als Netz", Netz | 502,65 | 502,0171 (−0,13 %) |
| F2 Tasche | dto. | 600 | 600,0000 |
| F1 anfügen | broomholdervcd_d35mm.stl Fläche 3, Netz | 502,65 | 502,2376 (−0,08 %) |
| F1 neuer Körper | dto. | 502,65 | 502,6548 |
| F2 Tasche | dto. | **285,24** (siehe unten) | 285,2395, keine Warnung |
| F3 Rundung R 5 / Fase 5 / Klick-R 2 | Platte 80 × 50 im Fenster | Hülle (0\|0)–(80\|50) auf 10⁻⁶ | alle drei (0,0,80,50); Dialog Länge 80, Breite 50; Körper 80 × 50 × 4 ab (0\|0) |
| E2 | Fenster, `QTest` Drücken/Loslassen | eine Handlung | *Fertig* [True], *Mehr* [] |

**Sollwert am Besenhalter berichtigt:** Die Abnahme nannte 600 mm³ auch für
Fläche 3 des Besenhalters. Unter einem Rechteck 20 × 10 um deren Mitte liegen
aber nur **285,24 mm³** Material (die Fläche ist 636 mm² groß und schmal; der
Rest des Rechtecks liegt über der Clipöffnung) — unabhängig gerechnet mit
manifold3d am selben Netz (Sonde `broom2` im Scratchpad), und der Kern trifft
genau diese Zahl. Vorher 0,0 (ins Leere). Die Abnahme ist damit „trägt genau
das Material unter dem Umriss ab"; 600 gilt an der Druckschale, wo der Boden
voll ist.

Z1-Sonde `z1_ziel.py` (drei Körper, Clip/Keil exakt, Stift Netz): 45 Prüfungen
grün — Ebenenfeld 11 Einträge, nur Clip; Keil/Stift kein Klickziel; Projizieren
1 Körper; Nachbarn ein/aus; Anfügen an Clip +500,0000 mm³ (10 × 10 × 5);
ohne Auswahl vier Körper, alte unverändert; zwei gewählt → Frage mit „Clip,
Keil, Neuer Körper"; Keil per Fernsteuerung gelöscht → Satz, Ziel neu;
Weiterverwenden → Ziel Clip, kein Schritt gebunden.

## Tokenzählung für das lokale Modell

Die neue Operation ist ein Werkzeug mehr für den Agenten. Gezählt mit
`tools/measure_local_model.py --count-tokens` (qwen3:14b, `num_ctx` 32 768;
Ollama war frei, keine fremde Sitzung geladen): **28 040 Token bei 148
Werkzeugen** (vorher 27 293 bei 147), +747 Token, 85,6 % des Fensters, 4 728
Token Rest (vorher 5 475). `llm.PROMPT_TOKENS`/`PROMPT_TOOL_COUNT`, die Sätze
in `context.py`, `agentenschicht.md` und `test_agent.py` nachgezogen.
`CONDENSE_ABOVE_CHARS` (10 000 Zeichen, etwa 3 000 Token) passt weiter hinein;
der Rest für Verlauf und Antwort wird knapper — Hinweis für RM-185.

## Bildbelege (selbst angesehen, sichtbares Fenster 3413 × 1369, `zb_bilder.py`)

Unter `F:\3D Druck.review-050\sonden\zeichnenbau\`:

| Datei | Zeigt |
|---|---|
| `zb_01_ziel_platte_karten.png` | Platte gewählt → *Zeichnen*: nur die Platte im Bild, Karten mit „Oberseite von Platte" vorn, Leiste „Ziel: Platte · Nachbarn zeigen · … · Mehr · Fertig · Verwerfen" |
| `zb_02_nachbarn_gezeigt.png` | *Nachbarn zeigen*: Keil und Stift leise, ohne Kanten |
| `zb_03_rechteck_auf_der_platte.png` | Rechteck auf der Oberseite, *Hochziehen*/*Abtragen* frei |
| `zb_04_mehr_liste.png` | Liste unter *Mehr* — ohne die Knöpfe daneben (Anfügen, Tasche) |
| `zb_05_anfuegen_vorschau.png`, `zb_05b_dialog_anfuegen.png` | Dialog „An Körper anfügen" mit Wann-nicht-Zeile, Vorschau blau auf der Platte |
| `zb_06_angefuegt_ein_koerper.png` | danach: ein Körper, Verlauf „4 An Körper anfügen" |
| `zb_07_neu_zeichnen_leer.png` | nichts gewählt: alle Körper weg, kein *Abtragen*, nur Grundebenen |
| `zb_08_frage_welcher_koerper.png` | zwei gewählt: „An welchem Körper zeichnen? Platte · Keil · Neuer Körper" |
| `zb_09_flaeche_hier_zeichnen.png` | Auswahlfenster einer Fläche: *Hier zeichnen*, *Loch oder Aussparung zeichnen …* |
| `zb_10_verlauf_weiterverwenden.png` | Verlauf-Kontextmenü mit *Zeichnung weiterverwenden* |
| `zb_11_escape_verwirft_nicht.png` | viermal Esc: Zeichnung steht, Zeile „Zum Verlassen: Fertig oder Verwerfen." |

Beim Ansehen gefunden und behoben: *Nachbarn zeigen* eingerastet sah im
dunklen Thema aus wie vorher — der Knopf heißt eingeschaltet jetzt „Nachbarn
ausblenden" (Regel 18). Die Aufnahmen entstanden vor dieser Änderung.

## Tests

- **Neu ohne Fenster:** `test_sketch_edit` (Rechteck 80 × 50 an allen vier
  Ecken × Rundung/Fase = 8 Fälle, bestimmte Fase, Umhängen an den
  Hilfspunkt, schräge Ecke), `test_sketch_ops` (Tasche außermittig exakt,
  Zeichenfläche als Ziel, Anfügen exakt, Anfügen daneben), `test_sketch_solid`
  (Tasche und Anfügen am Netz außermittig), `test_exact_body_parity` (Fall
  `sketch_join`, beide Kerne), `test_sketch_target` (zwei Fälle ohne
  Fenster). Gegenproben: F3 am alten `edit.py` 80 × 55; F1/F2 rot vor der
  Umsetzung (`target_behind` statt `drawing_face`; 0,0 statt 600).
- **Neu mit Fenster (Release):** `tests/test_sketch_target.py`, 12 Fälle —
  Zielkörper allein, Nachbarn, neu zeichnen, Anfügen, Frage, verlorenes Ziel,
  Sicht zurück, Escape, *Fertig* mit `QTest` Drücken/Loslassen, B3,
  Auswahlfenster, Weiterverwenden. Nicht gefahren (Auftrag); dieselben
  Abläufe liefen als Sonden am gebauten Fenster grün.
- **Angepasst (Fenster):** `test_sketch_editor` (Liste → *Mehr*, Körper unter
  der Zeichnung → Zielkörper, Escape), `test_field_ui` (2), `test_ui` (1).
- **Entwicklungstor** (`tore/tor-zeichnenbau.txt`): 16 038 bestanden, 12 rot,
  Exit 1. Davon meins und behoben: `test_translations` ×5 (neun abgelöste
  Katalogtexte standen noch), `test_agent` (Tokenzählung, s. o.) — Nachlauf
  dieser Dateien plus `test_registry_consistency` und `test_sketch_target`
  grün, Exit 0. **Nicht meins, am Stand 0367d202 schon rot:** `test_parts`
  Bereichsnachweis (bekannt); `test_examples` („zu-gross-automatisch-teilen":
  `tools/make_examples.py:682` ruft `apply_planned(…, profile)` mit vier
  Positionsargumenten, die Funktion nimmt seit `pins=` drei); `test_licences`,
  `test_licence_notices`, `test_sbom` (vtk fehlt in der geteilten `.venv`,
  vermutlich durch den VTK-Ausbau); `test_value_labels` (`files` aus
  `archive.py`).
- `ruff check .` 0, `ruff format --check .` 0, `mypy` 0 (314 Dateien).

## Was sich für den Kunden ändert

- Auf einer gewählten Fläche hochziehen **geht** — vorher hielt es immer an.
  Der Zapfen wird Teil des Körpers: ein Schritt, ein Körper.
- Eine Tasche auf einer Fläche, deren Mitte nicht im Weltursprung liegt,
  schneidet **dort, wo gezeichnet** — vorher ins Leere.
- Verrunden und Fase an einem bemaßten Rechteck lassen es 80 × 50 — vorher
  wurde es 80 × 55. Die Fase ist danach vollständig bestimmt; die alte Ecke
  steht als Hilfspunkt da und lässt sich ziehen.
- *Fertig* tut bei jedem Klick dasselbe; die übrigen Arten stehen unter
  *Mehr*.
- Beim Zeichnen sieht man **nur den gewählten Körper**; ohne Auswahl zeichnet
  man einen neuen, und alle anderen sind weg. *Nachbarn zeigen* (N) holt sie
  leise zurück, zum Ausrichten, anklicken lassen sie sich nicht. Das
  Ebenenfeld zeigt höchstens acht Flächen des Ziels statt 41 bis 234 aller
  Körper, und die Oberseite des Ziels steht als erste Karte da.
- Mit mehreren gewählten Körpern fragt die Leiste, an welchem gezeichnet
  wird; das Ziel lässt sich in der Leiste jederzeit wechseln.
- Escape wirft keine Zeichnung mehr weg.
- Im Auswahlfenster einer Fläche: *Hier zeichnen*, *Loch oder Aussparung
  zeichnen …*. Im Verlauf: *Zeichnung weiterverwenden*.
- Nach dem Zeichnen ist die Ansicht wie vorher (Platte, Explosion, Werkzeug,
  Darstellung).

## Klickzahlen vorher/nachher je Kundenaufgabe

Gezählt wie im Bericht (K Klick, T Taste, ? ratlos); „vorher" aus der
Abnahme, „nachher" am heutigen Stand entlang der Sonden.

| Aufgabe | vorher | Ergebnis vorher | nachher | Ergebnis nachher | Rest für Etappe 2 |
|---|---|---|---|---|---|
| **A** Platte 80 × 50 × 4, 4 × Ø 4, Langloch, Ecke R 5 | 15 K, 17 T, 1 ? | falsch (80 × 55) | 15 K, 17 T, 1 ? | **richtig** (80 × 50 × 4) | Lochabstände als Maß (Z3), Fokus Höhe (Z2) |
| **B** Aussparung 20 × 10 × 3 mittig auf Besenhalter | 7 K, 9 T, 1 ? | falsch (ins Leere) | 6 K, 9 T, 1 ? (Fläche → *Loch oder Aussparung zeichnen …* → R, Klick, 20 Tab 10 Enter → *Fertig* → Tiefe → OK) | **richtig** (genau das Material darunter) | Flächenmitte als Fangpunkt/Mittelpunkt-Rechteck (Z3/Z5): −1 ?; Fokus auf Tiefe (Z2): −1 K |
| B ändern 20 → 25 | 3 K, 2 T, 1 W | streckt auch die Breite | unverändert | unverändert | R2 (Z2) |
| **C** Profil drehen, 5 mm verschieben | 7 K, 10 T, 1 ?; 9 K | richtig | 7 K, 10 T (*Mehr* → Rotationskörper statt Liste an *Fertig*; gleich viele) | richtig | Achse (Z2/E8), Verschieben (Z4) |
| **D** L-Profil 40, dann 60, dann halbieren | 13 K, 6 T | richtig | unverändert | richtig | Z2/Z3 |
| Zapfen Ø 8 × 10 auf Fläche eines Teils (F1/E4) | **Sackgasse**; mit Umweg 6 K, 5 T + „Bis zur Fläche" leeren (3 K) + beide wählen, Vereinigen (etwa 4 K) | zwei Körper | **6 K, 5 T** | ein Körper, ein Schritt | Palette statt Dialog (Z2): −2 K |
| Zeichnen an einem von drei Teilen | Ebene aus 98 Einträgen suchen | alle Körper im Bild, Projizieren 242 Elemente | Teil wählen, *Zeichnen*, Karte „Oberseite" (3 K) | nur das Teil, ≤ 12 Einträge | — |
| Innenkontur einer schon hochgezogenen Zeichnung als Tasche (E6) | neu zeichnen | — | Rechtsklick Schritt, *Zeichnung weiterverwenden* (2 K), Außenkontur löschen, *Abtragen*, Tiefe, OK | ohne Neuzeichnen | Rahmenauswahl (Z4) |
| Versehentlich 3 × Esc | Zeichnung weg (Strg+Z holt sie, solange nichts anderes geschah) | — | nichts geht verloren | — | — |

## Berührungspunkte mit dem parallelen Bau P6.6 (`wt-p66`)

- `app/core/sketch/edit.py`: `fillet` und `chamfer` umgebaut; neu
  `_collapsed`, `_held_by_the_virtual_corner`, `_on_the_leg`;
  `_without_corner_joint` entfällt. Kommt mit P6.6b „Punkt auf Linie", kann
  `_on_the_leg` statt `parallel` diese Art nehmen — dieselbe Stelle, eine
  Zeile.
- `app/ui/sketch_editor.py`: **nicht angefasst.** Werkzeugleiste der
  Zeichenfläche ebenso; die neuen Knöpfe stehen in der Leiste des
  Hauptfensters (`sketch_bar`).
- `tests/test_sketch_edit.py`: vier Verrundungs-/Fasentests angepasst (fünf →
  sechs Elemente, Fasenmaß vom Hilfspunkt).
- `tests/test_sketch_editor.py`: Escape-, Listen- und
  Körper-unter-der-Zeichnung-Tests angepasst.
- **Zählungen kollidieren bei der Übernahme sicher:** Operationen 137,
  Parameter 1258, `caveat` 37, Werkzeuge 148, `PROMPT_TOKENS` 28 040. Im
  Hauptbaum stehen gerade Merge-Konflikte an genau diesen Stellen
  (`_ZAHLWORT` mit „siebenunddreißig/achtunddreißig", `llm.py`,
  `sketch/ops.py`), P6.5/P6.6 fügen ebenfalls Operationen hinzu. Nach der
  Übernahme neu zählen und die Tokenzählung einmal für den Endstand fahren.

## Fragen an Robert

1. **Abtragen ohne Auswahl.** Ihre Vorgabe vom 23.09. ersetzt die vom 30.08.
   („in Fusion wählt man vor dem Abtragen keinen Körper aus"). Wer ohne
   Auswahl über einem Teil zeichnet, sieht das Teil nicht mehr und bekommt
   bei *Fertig* einen neuen Körper; an ein Teil kommt er über das Feld *Ziel*
   der Leiste. **Empfehlung: so lassen** — eine klare Regel, und das Feld
   nennt den Weg. Alternative: bei geschlossenem Umriss über einem
   ausgeblendeten Körper eine Zeile „Über Keil gezeichnet — daran?" mit *Ja*
   (Bericht 7.2); kostet eine weitere Textstelle im Modus.
2. **Deckkraft der Nachbarn** 8 % (Zielkörper 16 %). In `zb_02` erkennbar,
   aber leise; bitte am eigenen Schirm ansehen.
3. **Bauplan:** keine Änderung nötig. Ergänzung für §30.1 als Vorschlag:
   „*Zeichnung weiterverwenden* kopiert den Text in einen neuen Schritt; eine
   Skizze, auf die mehrere Schritte verweisen, gibt es nicht."

## Vorschlag Etappe 2 (Z2–Z6), Reihenfolge

1. **Z2 Erstellen im Bild** zuerst — der größte Klickgewinn und Ihre
   Entscheidung 5: Palette am Umriss statt Dialog (Höhe/Tiefe mit Umschalter
   „Maß · bis Fläche · durch alles", Richtung samt beidseitig, Ergebnis
   neu/anfügen/abziehen — `sketch_join` ist dafür schon da), Fokus im
   Zahlenfeld; Dialog mit Zeichnung ohne Grundform/Länge/Breite (E3), R1
   (Skizze direkt öffnen, *Fertig* ohne zweiten Dialog), R4 (Höhe am Körper
   ändert den Schritt), E7 (Umriss anklicken statt Region-Nummer). E8
   Drehachse **gemeinsam mit P6.5** (eine Achswahl für Drehen und Schnitt
   durch Drehen).
2. **Z3 Bemaßen und Fang**, sobald P6.6b die Bedingungsarten liefert:
   Bemaßen-Werkzeug (W1), Ursprung/Flächenmitte als Fangpunkt (W5 — nimmt das
   verbliebene „?" aus Aufgabe B), Maß im Bild bearbeiten (R3), freie
   Elemente gestrichelt (W6). Danach `_on_the_leg` auf „Punkt auf Linie".
3. **Z4 Auswählen, Verschieben, Drehen** mit Ihrer Entscheidung 3
   (Links-Ziehen zeichnet, Mitteltaste/Leertaste verschiebt): Rahmen, Strg+A,
   Verschieben/Drehen mit Zahl, Spiegeln an Linie, Rechtsklick nach Lage
   (Q1), Trimmen als Zug.
4. **Z5 Werkzeuge** zusammen mit P6.6a (gleiche Leiste, 900-Punkte-Grenze):
   Mittelpunkt-Rechteck, tangentialer Bogen, 3-Punkt-Kreis, P = Projizieren
   (Entscheidung 6).
5. **Z6 Ansicht und Texte** zuletzt, weil es alles davor beschreibt:
   Einpassen nach dem ersten Umriss (W4), Aufschneiden (V1), Draufsicht auf
   jede Ebene (V2), ein Textort (V3), Perspektive gesperrt (V4), Fachwörter
   (Q4), Startbildschirm „Neu zeichnen" (B1), Menüumbenennungen (E6), dann
   die Handbuchseite „Zeichnen" einmal neu.

## Registersätze (Vorschlag)

- „RM-neu (Zeichnen Z0/Z1, Robert 23.09.2026): gebaut in `zeichnenbau` —
  F1–F3 behoben (Hochziehen auf Fläche, Tasche außermittig, Verrunden/Fase mit
  virtueller Ecke), *Fertig* ohne Menü (*Mehr*), Escape verwirft nicht, neue
  Op `sketch_join`, Zeichnen gilt einem Körper (Nachbarn ausgeblendet,
  *Nachbarn zeigen*), Auswahlfenster *Hier zeichnen*/*Aussparung*,
  *Zeichnung weiterverwenden*. Offen: Etappe 2 (Z2–Z6)."
- „Nicht aus zeichnenbau, am Stand 0367d202 rot: `tools/make_examples.py:682`
  ruft `apply_planned` mit vier Positionsargumenten (seit `pins=`)."

## Dateien

- Bericht: `F:\3D Druck.review-050\reports\zeichnenbau.md`
- Patch: `F:\3D Druck.review-050\reports\zeichnenbau.patch`
- Tor: `F:\3D Druck.review-050\tore\tor-zeichnenbau.txt`
- Sonden und Bilder: `F:\3D Druck.review-050\sonden\zeichnenbau\`
