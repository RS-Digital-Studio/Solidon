# Strang B — Bericht (HB-11, HB-9)

Arbeitsbaum `F:\3D Druck.handbuch-texte`, Zweig `handbuch-texte`, abgezweigt
von `handbuch-umbau` am Stand `8fa13081f`. Wird während der Arbeit
fortgeschrieben.

## Stand

- HB-11: fertig, committet und gepusht (`b9349f78b`).
- HB-9: fertig, committet und gepusht (`14f862070`, `1363c4f90`, `fb61a5ef7`, `b941dfa61`).
- Nachtrag (Entscheidung Koordinator/Release-Sitzung): Italienisch auf „tu“ — fertig (`a4f6a104c`).
- Durchsicht der Release-Sitzung behoben (`afd65683f`), siehe Abschnitt unten.
- Zweig `handbuch-texte` ist auf der Gegenstelle, Endstand `afd65683f`, bereit zum Merge in `handbuch-umbau`. Nach dem Merge `python -m app.i18n.extract` fahren (alte Schlüssel der 27 Seiten fallen dann aus den Katalogen von Strang A).
- Kein Tor-Befund wegen des i9: alle sechs gepinnten Läufe grün, kein Test musste wiederholt werden.

## Durchsicht der Release-Sitzung — Befunde behoben

**Deutsch (Teil 1):**

1. `what` und `parts` nennen den Baustein wie der Katalog,
   *Heat-Set-Einpressbuchse* (`fasteners.py`); die Übersetzungen trugen den
   Katalognamen schon (Heat-set insert, Inserto termofijado, Insert à chaud,
   Inserto a caldo, Bucha de inserção a quente).
2. `history`: „fragt Solidon hier als einzige Stelle im Verlauf nach“ —
   Regel 19 hat zwei Ausnahmen, der Import oberhalb der Merkmalsgrenze fragt
   auch. In fünf Sprachen nachgezogen.
3. `trouble`: Der Abschnitt „„Das Modell ist nicht geschlossen.““ ist ersetzt
   durch **Das Modell ist offen.**, gegen den Code geschrieben:
   - Beim Einlesen repariert Solidon, was sicher geht; der Prüfbericht nennt
     es: „Ein Loch wurde geschlossen.“ (`repair.holes_filled`,
     `geom/repair.py`).
   - Eine große Öffnung bekommt eine neue Fläche, darunter *Stelle zeigen* und
     *Offen lassen* (`repair.wide_hole_filled`).
   - Was offen bleibt: „Eine offene Stelle ließ sich nicht sicher schließen.“
     mit *Stellen zeigen* (`repair.still_open`, Knopf aus
     `ui/panels.py`); bei mehreren Stellen „{holes} offene Stellen …“.
   - Zur Einordnung: „Das Modell ist nicht geschlossen.“ gibt es im Code
     (`ingest/loader.py:1299`, `ingest.not_watertight`), aber nur, wenn beim
     Laden „Offene Stellen schließen“ abgeschaltet ist; für den Normalfall war
     das Zitat also falsch. *Reparieren* im Prüfbericht als Weg für kleine
     Löcher ist gestrichen.
   - Andere Befunde tragen ihre Reparatur als Knopf: im Absatz „Vereinigen
     oder Abziehen scheitert“ jetzt „Teile des Modells überschneiden sich.“
     mit *Überschneidungen auflösen* (`repair.self_intersections_detected`).
   Alle Zitate sind wörtliche Katalogtexte; die Übersetzungen zitieren die
   Katalogübersetzungen (von `test_wording` geprüft).

**Übersetzungen (Teil 2):** 41 von 42 Befunden übernommen, wörtlich wie
vorgeschlagen (en 7, es 11, fr 6, it 12, pt 5). Die Titel „Die vier Wege“
(Befund 29 fr, 37 it) sind Katalogeinträge außerhalb der Seitentexte und
direkt berichtigt.

**Nicht übernommen: Befund 30** (fr, exchange, „ni l’auteur“ → gerader
Apostroph). Der Satz „Ni le fichier, ni l’auteur, ni la licence, ni la
provenance ne sont transmis à RS Digital.“ steht mit typografischem Apostroph
wörtlich in `test_manual::test_the_exchange_manual_describes_only_local_files`
(Marker `rendered`, läuft beim Release) und wird dort gegen Seite und Website
geprüft. Mit geradem Apostroph wäre der Release-Test rot. Wer den Apostroph
angleichen will, ändert Test und Satz zusammen.

Die Nebenbefunde a bis e sind nicht angefasst.

**Zählung nach der Durchsicht:** 9 861 Wörter (Schwelle 9 884, vorher 9 817):
`trouble` 555 → 597, `history` 299 → 301, `what` und `parts` unverändert.
Suche unverändert: 42 von 50 ganz oben, 50 unter den ersten drei.

## HB-11 — Wächter für Wege im Text

Test `tests/test_manual.py::test_a_way_in_a_written_page_is_the_one_the_interface_shows`,
je Sprache aus `available_languages()`. Geprüft an jeder geschriebenen Seite
(alle nicht erzeugten Seiten außer den Bildanleitungen, deren Wege
`test_guides` prüft):

- kein Pfeil außerhalb eines ausgezeichneten Wegs (`*A → B*`, `**A → B**`),
- jedes Glied ist ein Katalogtext (ohne `…` und Satzpunkt verglichen),
- der Weg beginnt an einem Menü der Leiste (die vier festen aus
  `self._menu(tr(…))` im Quelltext des Hauptfensters, dazu die
  Registergruppen mit `in_the_menu_bar`),
- die Übersetzung hat gleich viele Wege je Seite und jedes Glied heißt, wie
  der Katalog das deutsche Glied übersetzt,
- endet der Weg auf einer Operation, ist er `registry.surfaces.menu_path`.

**Funde heute** (behoben in den Katalogen): Italienisch
*Modifica → Calibra materiale* statt *Calibra il materiale* (Seiten
`tolerances`, `variants`), Portugiesisch *Editar → Calibrar o material* statt
*Calibrar material* (`variants`). Deutsch, Englisch, Spanisch, Französisch
waren sauber.

**Gegenprobe** (`scratchpad/gegenprobe.sh`, jede Mutation danach
zurückgelegt, `git status` danach nur die eigenen drei Dateien):

| Mutation | Ergebnis |
|---|---|
| 1. Menüeintrag „Drucken vorbereiten …“ umbenannt (Schlüssel aus `en.json` entfernt, wie nach dem Einsammler) | rot: de, en — „['Drucken vorbereiten'] ist kein Text der Oberfläche“ (Seiten `print`, `start`) |
| 2. Italienische Übersetzung von „Bausteinkatalog …“ umbenannt | rot: it — „*File → Catalogo dei blocchi* heißt nicht wie *Datei → Bausteinkatalog*“ (drei Seiten) |
| 3. Falscher Weg zu einer Operation: *Erzeugen → Bausteine → Organizer anlegen* | rot: alle sechs — de: „ist nicht der Menüweg 'Erzeugen → Grundformen → Organizer anlegen'“ |
| 4. Weg über ein Menü, das es nicht gibt: *Bausteine → Material kalibrieren* | rot: alle sechs — de: „beginnt an keinem Menü der Leiste“ |
| 5. Weg ohne Auszeichnung | rot: alle sechs — de: „ein Pfeil steht außerhalb eines ausgezeichneten Wegs“ |

**Grenze, bewusst:** Ein Eintrag, der keine Operation ist, unter einem
falschen, aber vorhandenen Menü (*Bearbeiten → Drucken vorbereiten*) bleibt
hier grün — welcher Eintrag unter welchem Menü steht, weiß nur das gebaute
Fenster. Das prüft `test_wording::test_every_menu_path_in_the_texts_exists_in_the_menu_bar`
beim Release am Deutschen, und jede Übersetzung muss hier Glied für Glied dem
Deutschen folgen. Im Docstring des Tests steht das.

## Tor und Commits

| Commit | Inhalt | Tor (gepinnt, FFFFF0FF) | ruff | format | mypy |
|---|---|---|---|---|---|
| `b9349f78b` | HB-11: Test, Funde it/pt, §9 HB-11 | Exit 0, 17921 passed, 59 skipped, Läufe mit Fehler 0 | 0 | 0 (1042 Dateien) | 0 (330 Dateien) |
| `afd65683f` | Durchsicht Release-Sitzung: drei deutsche Befunde, 41 von 42 Übersetzungsbefunden, Titel fr/it, Nachweis und §9 nachgezählt | Exit 0, 17921 passed, 59 skipped, Läufe mit Fehler 0 (13:45) | 0 | 0 (1043) | 0 (330) |
| `a4f6a104c` | Italienisch auf „tu“: 19 der 27 HB-9-Seiten, 59 Stellen | Exit 0, 17921 passed, 59 skipped, Läufe mit Fehler 0 (21:12 unter Last) | 0 | 0 (1043) | 0 (330) |
| `b941dfa61` | HB-9 Abschluss: chat, generating, extras, remote, activation, trouble; Nachkürzung window, features, sketch; Suchkorrektur; Nachweis `kuerzung.md`; §9 HB-9; Ausnahme in `test_wording` ausgetragen | Exit 0, 17921 passed, 59 skipped, Läufe mit Fehler 0 | 0 | 0 (1043) | 0 (330) |
| `fb61a5ef7` | HB-9 Teil 3: sculpting, own-parts, exchange, print, resin, export, splitting, surfaces, labels (3753 → 2600) | Exit 0, 17921 passed, 59 skipped, Läufe mit Fehler 0 (15:21 Laufzeit) | 0 | 0 (1042) | 0 (330) |
| `1363c4f90` | HB-9 Teil 2: features, sketch, parameters, tolerances, variants, parts (5110 → 3443) | Exit 0, 17921 passed, 59 skipped, Läufe mit Fehler 0 | 0 | 0 (1042) | 0 (330) |
| `14f862070` | HB-9 Teil 1: what, window, ways, history, moving, looking (2947 → 2014 Wörter) | Exit 0, 17921 passed, 59 skipped, Läufe mit Fehler 0 — gefahren, bevor auf `what` fünf Bausteinnamen in den Katalogwerten angeglichen wurden; danach 295 Handbuch- und Übersetzungstests grün | 0 | 0 (1042) | 0 (330), nach dem Commit gefahren |

## HB-9 — Kürzung

27 Seiten, alle aus `manual.INTRODUCTION` außer `start` und `glossary`.
Gezählt wie Konzept §1.1 (Kurzfassung und Text, Token mit Buchstabe oder
Ziffer, ohne Bildverweise, von Seitenverweisen der Titel). Vorher am Stand
`8fa13081f`.

| Seite | vorher | nachher | Änderung |
|---|---:|---:|---:|
| `what` | 180 | 156 | −13 % |
| `window` | 830 | 533 | −36 % |
| `looking` | 505 | 308 | −39 % |
| `features` | 2 029 | 1 221 | −40 % |
| `moving` | 834 | 515 | −38 % |
| `sketch` | 1 427 | 892 | −37 % |
| `ways` | 212 | 170 | −20 % |
| `sculpting` | 368 | 259 | −30 % |
| `history` | 386 | 301 | −22 % |
| `parameters` | 388 | 269 | −31 % |
| `tolerances` | 299 | 222 | −26 % |
| `parts` | 752 | 565 | −25 % |
| `own-parts` | 592 | 374 | −37 % |
| `exchange` | 391 | 259 | −34 % |
| `print` | 546 | 436 | −20 % |
| `resin` | 193 | 151 | −22 % |
| `export` | 420 | 283 | −33 % |
| `splitting` | 553 | 364 | −34 % |
| `variants` | 215 | 186 | −13 % |
| `chat` | 298 | 182 | −39 % |
| `generating` | 299 | 187 | −37 % |
| `extras` | 1 038 | 591 | −43 % |
| `surfaces` | 339 | 245 | −28 % |
| `labels` | 351 | 242 | −31 % |
| `remote` | 210 | 146 | −30 % |
| `activation` | 282 | 207 | −27 % |
| `trouble` | 890 | 597 | −33 % |
| **zusammen** | **14 827** | **9 861** | **−33,5 %** |

Schwelle ein Drittel: 9 884 Wörter; nach der Durchsicht beträgt der Abstand 23 Wörter (vorher 67). Was wohin
wanderte, steht Seite für Seite im Nachweis
`konzepte/nachweise-handbuch-2026-09/kuerzung.md`.

Wichtigste Punkte:

- **`remote` widerspricht `remote-tools` nicht mehr:** Der Satz „Eine eigene
  Schnittstellenliste gibt es deshalb nicht“ ist durch einen Verweis auf
  *Die Werkzeuge der Fernsteuerung* ersetzt; MCP und Claude Code sind in
  einem Satz erklärt. `remote-tools` bleibt, wo es ist.
- **Entwicklersicht entfernt:** §26.4 (`chat`), §2.2 (`generating`), „Bis zur
  Fassung 0.3.5“ und „296 von 1130 Einträgen“ (`features`), Token-Messung
  auf Intel Arc (`extras`), „Fassung“ → „Version“ (`what`, `activation`,
  `own-parts`).
- **Doppeltes einmal:** Prüfkörper nur noch auf `variants`, Teilen und
  Verstiften nur noch auf `splitting`, Schichtanalyse-Bild nur noch auf
  `looking`; Klickwege zeigen auf die fünf Anleitungen (Verweise
  `manual:window-overview`, `print-a-model`, `drill-a-hole`, `first-part`).
- **Berichtigt beim Lesen:** Das Auswahlfenster leert sich ohne Auswahl nicht
  (es zeigt die Handlungen für alle Körper); der Abstand zweier Merkmale steht
  als Zeilen *Abstand*, *in X/Y/Z*, nicht als erfundene Zeichenkette; der
  Knopf heißt *Filament abziehen …*; Platzhalter im Namensmuster stehen in
  geschweiften Klammern.
- **Übersetzung:** Jede Seite in fünf Sprachen als Ganzes neu, jeder
  hervorgehobene Name gegen den Katalog geprüft (eigenes Prüfskript
  `namen.py`, 0 Befunde), Genus der Bausteinnamen nach Katalog
  (Bausteintitel wie *Pestaña de retención*, *Ergot d'encliquetage*).
- **Suche:** vorher/nachher an den 50 Kundensuchen gemessen (Wegwerf-
  Arbeitsbaum am Ausgangsstand, danach entfernt): ganz oben 42 → 42, unter
  den ersten drei 49 → 50. Die erste Kürzung hatte fünf Suchen einen Rang
  gekostet; behoben über Kurzfassungen (`extras`, `variants`) und zwei
  Wörter zurück in den Text (`moving`, `export`). `CUSTOMER_WORDS`
  unverändert.
- **Tests:** keiner gelockert. In `test_wording` fiel eine Ausnahme weg
  (Designerwort „normal“ in der alten englischen `trouble`-Seite), das ist
  eine Verschärfung. `test_translations::test_french_range_check_warns_for_any_failed_corner`
  verlangte einen französischen Satz; das Deutsche sagt es jetzt ebenso
  ausdrücklich („auch nur an einer Ecke“).

## Offen oder zweifelhaft

- **HB-11 prüft nicht, ob ein Eintrag ohne Operation unter genau diesem Menü
  steht** (*Bearbeiten → Drucken vorbereiten* bliebe grün). Das kann nur das
  gebaute Fenster; `test_wording` tut es beim Release am Deutschen.
- **Knapper Abstand zur Drittel-Schwelle** (nach der Durchsicht 23 Wörter). Wer beim
  Zusammenführen Sätze in diese Seiten zurückholt, sollte nachzählen
  (`kuerzung.md` beschreibt die Zählung).
- **Zerbrechlicher Test:** `test_translations::test_italian_sculpt_manual_names_the_actual_modify_menu`
  sucht die Formen-Seite als ersten Katalogschlüssel, der mit „Manche Formen
  lassen sich“ beginnt; ein Tourtext beginnt genauso. Er war nur grün, weil
  die Seite alphabetisch vorn steht. Der erste Satz von `sculpting` ist
  deshalb so gebaut, dass das weiter gilt; der Test selbst ist unverändert.
- **Zusammenführen der Kataloge:** Strang A führt die alten Schlüssel dieser
  27 Seiten noch. Nach dem Merge `python -m app.i18n.extract` fahren, damit
  sie hinausfallen, und den Diff der Kataloge lesen.
- **Nicht umgesetzt, weil außerhalb des Auftrags** (Gliederung gehört Strang
  A): Empfehlungen aus `leserblick.md` wie `extras` in drei Seiten teilen oder
  `trouble` mit Sprungmarken.
- **Italienisch auf „tu“** (Entscheidung Koordinator mit der
  Release-Sitzung): Alle 27 in HB-9 neu übersetzten italienischen Seiten
  sprechen jetzt durchgehend „tu“ (Imperativ 2. Person Singular, tuo/tua,
  puoi), wie Oberfläche und Anleitungen; 19 Seiten hatten „voi“-Formen, 59
  Stellen umgestellt. Nicht angefasst: `start`, `glossary`, die
  3D-Maus-Seite und alle „voi“-Einträge außerhalb dieser Seiten — die
  übernimmt die Release-Sitzung.
