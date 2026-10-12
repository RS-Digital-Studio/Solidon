# Konzept: Funktionsdurchgang über die Oberfläche

Stand: main `ee6b810fe`, 11.10.2026. Auftrag Robert: „ein Konzept zur
Abarbeitung aller Funktionen und zum Testen für dich, alles über die
Bedienoberfläche, zum sauber Abhaken, mit Befund und Optimierung und
Einfachheit sowie Verständlichkeit.“ Nach der Landung von 0.6.1 am 12.10.
nachgezogen in §3, §6, §7 und §9. Geprüft von `bedienlogik` und
`konzept`, dazu eine Nachprüfung; alle Funde sind eingearbeitet (Berichte in
[`nachweise-funktionsdurchgang-2026-10/`](nachweise-funktionsdurchgang-2026-10/README.md)).
Abgelegt am 12.10.2026 nach der Landung von 0.6.1; das Programm ist
[RM-736](../ROADMAP.md#rm-736), die Pakete D0 bis D12 sind RM-737 bis RM-749.

## 1 Ziel

Jede Funktion, die der Kunde bedienen kann, wird einmal vollständig **so
benutzt, wie er sie benutzt** — mit Klick, Tippen und Taste an der Stelle, an
der er sie findet, nicht über den Kern —, nach demselben Prüfschema bewertet
und abgehakt. Jede Zeile endet mit einem Urteil und, wo nötig, Funden, die
behoben werden. Am Ende steht für jede Funktion fest: Sie ist auffindbar, tut,
was sie verspricht, lässt sich zurücknehmen, ist ohne Handbuch zu verstehen,
so einfach, wie sie sein kann, und zeitgemäß gestaltet — innovativ und modern,
aber nie auf Kosten der einfachen Bedienung.

Ehrlich vorweg: Wer den Code kennt, prüft als Experte. Das ist eine strenge
Expertenprüfung mit zählbaren Kriterien, kein Test mit Kunden; die Fragebögen
und Kundenberichte bleiben die zweite Quelle.

## 2 Was es schon gibt

| Vorhanden | Was es leistet | Rolle hier |
|---|---|---|
| `tools/file_acceptance.py` (RM-184), Logik in `tests/test_file_acceptance.py` | je Fall eigener Prozess und eigenes Profil, echtes Fenster, Vorschau, Übernehmen, Rückgängig, Wiederholen mit SHA-256-Netzabdruck, Bild je Schritt, Bericht als JSON und Markdown, Wiederaufnahme | **Grundlage des Prüfstands** — er wird erweitert, kein drittes Fensterwerkzeug. Seine eigenen Abkürzungen (`window.action_undo()`/`action_redo()`, Klick auf `feature_panel._apply`, Wahl über `select_feature`, gesetzte statt getippte Zahl) werden dabei für Datei- und Funktionsfälle auf Eingabeereignisse umgestellt |
| `app/core/guides.py`, `app/ui/guide_targets.py`, `tests/test_guides.py` | ein fester Wortschatz von Zielen und ihre Auflösung zu Widget und Bildschirmort | **die eine Zuordnung** von Namen zu Bedienelementen; wird erweitert (§5) |
| `tools/make_guides.py`, `tools/make_web_images.py` | Wartewege und Startzustände für Bilder | Wartewege übernommen; ihre Abkürzungen (`click()`, `set_value`, `emit`, `session.apply`) nicht, denn sie umgehen die Bedienung |
| `tools/run_ui_audit.py` | alle Projekte und Modelle durch die laufende Oberfläche bis zum Export | bleibt für den Bestand an Dateien |
| Suite, Fenstertests | Verhalten einzelner Wege | jeder Fund wird ein Test |
| Plan und Inventur 0.6.1 (`output/konsolidierung-2026-10-07/vorbereitung-061-boolesch-und-palette.md` und `inventur-061-palette.md`, mit RM-735 abgelegt als `konzepte/konzept-suche-und-palette-2026-10.md` und `konzepte/nachweise-palette-2026-10/`) | 273 Paletteneinträge mit Ort, offscreen gemessen, vor RM-735 | Ausgangspunkt; den Ort misst der Prüfstand neu |
| Skills `ux-review` und `ui-design`, Agent `bedienlogik` | Ablaufaufnahme, Bewertung, Gestaltungsprüfung | **eine Quelle** für die Kriterien: `ux-review` bekommt E und V, `ui-design` bekommt G, Z und I aus §4, das Konzept verweist auf beide |

## 3 Die Funktionsliste

Erzeugt, nicht geschrieben, mit stabilen Kennungen:

| Art | Quelle | Kennung |
|---|---|---|
| Operationen | Register | Registername |
| Fensterbefehle | Menüleiste des Fensters, aus den unübersetzten Quelltexten | Menüpfad, z. B. `Datei/Speichern unter` |
| Bedienflächen | Dialogklassen unter `app/ui/` (`*dialog*.py` und Fenster), Wortschatz der Ziele, `panels.FINDING_ACTIONS`, die Merkmalfenster-Handlungen ohne Operation — erzeugt aus `perceive.actions` und `selection_operations`, heute u. a. *Auf alle N gleichartigen anwenden*, *Bezug ändern*, *Im Bild einstellen* —, Kontextmenü des Verlaufs | fester Name aus dem Wortschatz |

Die Menüzeilen trugen in `window_commands` eine Kennung nach ihrer Lage
(`menu.<n>`) — eine stabile Kennung war das nicht. Seit D0-W heißen sie nach
ihrer deutschen Quelle (`menubar.<slug>`, `guides.menubar_name`), gleich in
jeder Sprache; gelesen wird die Leiste über `guide_targets.menubar_entries`. Die Einstellungen sind eine
Zeile je Abschnitt des Dialogs. Der Bausteinkatalog — 83 Kacheln, dahinter
50 Bausteine — ist **eine** Zeile mit einem Lauf über alle; ihre Texte prüft
Stufe B, ihren Maßbereich hält `check_part_ranges`.

**Startszenen** kommen aus einem Szenenkatalog in `tests/data/`, aus Ops gebaut,
nicht von Hand: je Merkmalsart aus `FEATURE_KINDS` sowie Kante und Kantenzug ein
Körper, an dem sie erkannt wird; jede als exakter und als Netzkörper; zwei
Körper; ein offener, ein mehrteiliger und ein Körper mit Hohlraum; eine Szene,
die über 2 s und eine, die über 10 s rechnet (Referenzmaschine); eine über der
Erkennungsgrenze (§21.1); eine über `COARSE_PREVIEW_ABOVE`. Die Zeile wählt
ihre Szene über eine kleine Tabelle „Anforderung → Szene“ aus `consumes`,
`applies_to` und `requires_kind`.

**Äußere Vorbedingungen** stehen je Zeile als Zustand, und beide Zustände
werden geprüft, denn „fehlt“ ist der Fehlerweg: KI-Modell, ComfyUI, Slicer
(vorhanden, fehlt); Lizenz (Demo, gekauft, abgelaufen) über ein vorbereitetes
Nutzerprofil; Drucker (Filament, Resin). 3D-Maus und zweiter Schirm: nur
Stufe C oder *entfällt* mit Grund.

**Wächter im Tor, ohne Fenster:** Jede Operation hat eine Startszene; rot ist
nur eine neue Anforderung ohne Szene. Jede Dialogklasse hat eine Zeile. Jede
Operation gehört genau einem Paket (Zuordnung in §6). Die Fensterbefehle
entstehen erst mit der Menüleiste am gebauten Fenster (`_build_menus`); sie
zählt der Prüfstand am Fenster in die Liste, und ihre Vollständigkeit hält ein
`rendered`-Test beim Release. Ungeprüfte Zeilen machen das Tor nicht rot —
sonst hinge jede neue Operation an einem Fensterlauf.

## 4 Das Prüfschema

Neunzehn Prüfpunkte. Gemessen wird, was sich messen lässt; was ein Urteil ist,
hat eine Zählgröße und eine Schwelle (Tabellen unten).

| # | Prüfpunkt | Frage | Beleg |
|---|---|---|---|
| 1 | Auffindbar | Wo steht sie (Auswahlpanel und Stufe, Ansicht, Menü, Kürzel)? Findet die Suche sie unter Suchproben **von außen** — das Wort des Slicers, den CAD-Fachbegriff, Wörter aus Fragebögen (z. B. „boolesch“, „subtrahieren“) — unter den ersten drei? | vom Prüfstand gemessener Ort; Suchproben je Zeile vorab festgelegt, nicht aus `CUSTOMER_WORDS` |
| 2 | Weg | Klicks, Pflichteingaben, Entscheidungen, Blickwechsel bis zum Beispielziel der Zeile | E1–E5 |
| 3 | Vorschau | Zeigt sie vor dem Übernehmen, was passiert, und stimmt das? Bei grober Vorschau (ab `COARSE_PREVIEW_ABOVE`) wird der Satz im Vorschauband geprüft, sonst Volumen und Außenmaß gegen das Ergebnis | Bild und Kennzahl |
| 4 | Ergebnis | Tut sie, was Titel und `doc` versprechen? Dieselben Werte über die Kommandozeile ergeben ein druckgleiches Netz (§35, zwei Wege gegeneinander) | Kennzahl gegen Erwartung, Netzabdruck |
| 5 | Rückweg | Strg+Z stellt den Stand vorher genau her, Wiederholen (Strg+Y; unter Linux Strg+Umschalt+Z, auf dem Mac ⌘⇧Z) das Ergebnis; Escape und *Abbrechen* im Dialog verwerfen den Entwurf (§18.11) | Szenenabdruck vor, nach, nach Undo, nach Redo |
| 6 | Rückmeldung und Zeit | Sieht man, dass sie läuft und was sie geändert hat? Bleibt das Fenster bedienbar — größte Lücke im Hauptfaden ≤ 100 ms? Wo §31 ein Budget nennt, liegt sie darin; eine Überschreitung ist ein Verdacht, den `window_bench.py` oder die Leistungstests bestätigen; ohne Budget steht „kein Budget“ | gemessene Zeiten |
| 7 | Fehlerweg | Falsche Auswahl, ungültige Eingabe, Fehler: Sperrgrund, Grenzablehnung, Handlungsvorschlag (Regel 17), jede angebotene Handlung geklickt und wirksam | je ein erzwungener Fehlfall, V5 |
| 8 | Verständlich | ohne Handbuch zu verstehen, für jemanden aus dem Slicer ohne CAD-Kenntnisse | V1–V6 |
| 9 | Sprachen und Darstellung | In allen sechs Sprachen passt jeder sichtbare Text in sein Element (Schriftmaß gegen Breite, gemessen); Anzeigeeinheit Zoll; keine Bedeutung allein über Farbe (Regel 18) | Messung je Sprache; Bilder auf Deutsch im hellen Thema und in der längsten Übersetzung der Zeile, das dunkle Thema als Stichprobe je Dialogart |
| 10 | Tastatur und Zugänglichkeit | per Tastatur erreichbar; Tab-Folge folgt der Lesefolge, gemessen per Tastendruck und `focusWidget()`; kein leerer und kein doppelter `accessibleName`, der Name trägt die Handlung; der Fokus kehrt nach dem Dialog zurück. Bildschirmleser: ungeprüft, so vermerkt | Tab-Kette, Namensliste |
| 11 | Versprechen | Deckt sie, was Website (`website/funktionen.html` und `website/{en,es,fr,it,pt}/`) und die Handbuchstelle (`manual.help_for`) sagen — und sagen beide, was sie kann? | Abgleich |
| 12 | Nachträglich ändern | Öffnen *Diesen Schritt ändern* und ein Doppelklick im Verlauf den Schritt mit seinen Werten, und ändert eine neue Zahl ihn, ohne dass der Verlauf wächst (§2.1)? | Schrittzahl vorher und nachher |
| 13 | Auswahlstufen | ohne Auswahl, ein Körper, mehrere Körper, ein Merkmal, mehrere Merkmale, eine Kante: angeboten, grau mit Grund oder nicht da, wie `grenzen.md` es verlangt | Matrix je Stufe |
| 14 | Abbruch während der Rechnung | kommt über 2 s *Abbrechen*; danach steht der letzte vollständige Stand, ein wartender Klick verfällt (§15.6, `wartezeit.md`) | Abdruck nach Abbruch |
| 15 | Halt und Einfügemarke | bei angehaltener Kette der Grund mit Schrittnummer; bei gesetzter Einfügemarke Ergebnis am Stand davor oder Absage mit *Einfügen beenden* (`fenster.md`) | je ein erzwungener Fall |
| 16 | Projektwechsel | Ein Wechsel während Vorschau, Entwurf oder Rechnung räumt alles ab; nichts Spätes meldet ins neue Projekt | „Öffnen während der Rechnung“ |
| 17 | Agentenweg | Das Agentenwerkzeug nennt denselben Ort (`menu_path` in `tool_schemas()`); ein Undo nimmt einen Vorschlag mit dieser Operation ganz zurück (Regel 16) | Ort offline; der Lauf in der Agenten-Suite |
| 18 | Lizenzzustand | In der Demo und nach Ablauf grau mit Grund, nur Lesendes läuft weiter (`kern.md`, Lizenzgrenze) | zwei Läufe mit vorbereitetem Profil |
| 19 | Gestaltung | Wirkt sie zeitgemäß, ruhig und hochwertig — und bleibt sie dabei einfach? Nutzt sie, was Solidon besser kann, statt eines klassischen Formulars? | G1–G9, Z1–Z7, I1–I6 |

**Szenenabdruck:** Ops, Parameter, Projektparameter, Passungen und der Hash der
Auswertung; Auswahl und Kamera nach einem Undo getrennt notiert.

**Einfachheit** — Maßstab der Slicer-Kunde, Startzustand die passende Auswahl,
Beispielziel je Zeile vorab festgelegt (etwa „Bohrung auf 5 mm“):

| | Zählgröße | Schwelle |
|---|---|---|
| E1 | Klicks bis zum Ergebnis mit den Vorgaben | ≤ 3; am Merkmal ≤ 2 nach der Auswahl |
| E2 | Pflichteingaben bis zum Beispielziel | ≤ 1 bei 90 % der Funktionen; sonst ist die Vorgabe der Fund (§2.4) |
| E3 | Entscheidungen, die Vorwissen verlangen | ≤ 1 |
| E4 | Blickwechsel zwischen Ansicht, rechter Karte, Dialog, Statusleiste, linker Karte | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle |
| E5 | Felder vorn, Wörter über dem ersten Feld | ≤ 3 Felder (höchstens 4); ≤ 25 Wörter, übersetzt ≤ 35 |
| E6 | Nachfragen außerhalb der Ausnahmen von Regel 19 | 0 |
| E7 | Sackgassen: grau ohne Grund, leere Karte ohne Satz, Meldung ohne Handlung | 0 |

**Verständlichkeit:**

| | Zählgröße | Schwelle |
|---|---|---|
| V1 | Wörter der Negativliste im sichtbaren Text (Normale, wasserdicht, Voxel, boolesch, Facette, deterministisch, Mesh, B-Rep, Manifold, Provenienz, Bezeichner, Punktpfade, True/False; `oberflaeche.md`) | 0; ein Wort, das weder auf der Negativ- noch auf einer gepflegten Positivliste aus dem Slicer-Wortschatz steht, braucht einen Satz am Ort. Beide Listen versioniert neben `tests/data/text_patterns.json` |
| V2 | Satzlängen | die Grenzen aus `test_text_length` |
| V3 | Felder mit eigenem Satz (Kurzhilfe und zugängliche Beschreibung) | 100 %; der Satz teilt höchstens die Hälfte seiner Wörter mit dem Titel |
| V4 | Vorhersage: Der Prüfer schreibt vor dem Übernehmen aus Titel, erstem Satz und Vorschau auf, was geschehen wird | Abweichung vom Ergebnis ist ein Fund |
| V5 | Meldungen | jede sagt, was nicht ging, warum und was jetzt; ihre Handlung löst das Problem |
| V6 | Kurzhilfen, die man bis zum Ziel öffnen muss | ≤ 1; nie das Handbuch |

**Gestaltung** — innovativ und modern, aber einfach bedienbar (Robert,
11.10.2026). Maßstab sind die eigenen Gestaltungswerte (`app/ui/theme.py`,
`style.py`, `motion.py`) und der Skill `ui-design`. **Die Grenze:** Ein Fix
oder Vorschlag aus Z oder I (unten) wird nur übernommen, wenn E1–E7 und V1–V6
an derselben Zeile vorher und nachher gemessen nicht schlechter sind, und er
zählt nur, wenn er im gewöhnlichen Weg ohne Handbuch sichtbar wird
(Prüfpunkt 1, V6) — eine Neuerung, die niemand findet, gibt es für den Kunden
nicht.

| | Zählgröße | Schwelle |
|---|---|---|
| G1 | Hauptknöpfe (`make_primary`) und Akzentflächen im Ruhezustand je Fenster | höchstens eine Hauptaktion je Dialog oder Karte, wie `fenster.md` („Der Hauptknopf“: Fenster ohne Handlung und Rückfragen vor dem Verwerfen tragen keine), höchstens ein Akzent je Fenster (wie `test_style` und `test_resting_state`) |
| G2 | Abstände, gemessen an `layout.spacing()` und `contentsMargins()` | jedes ein Vielfaches von `SPACE` (4); innerhalb einer Gruppe einheitlich (`TIGHT`, `NORMAL`, `ROOMY`, `WIDE`) |
| G3 | Ausrichtung | Beschriftungen, Felder und Einheiten einer Gruppe bündig; Werte rechtsbündig mit Einheit |
| G4 | Schrift | nur die vier Stufen aus `LEVELS`; keine fest gesetzte Größe oder Farbe außerhalb der Gestaltungswerte |
| G5 | Zustände: Hover, Fokus, gedrückt, deaktiviert, beschäftigt, Fehler | jeder sichtbar unterscheidbar, mit zweiter Kodierung neben der Farbe; Fokus immer sichtbar |
| G6 | Kontrast von Text und Symbolen gegen ihren Hintergrund | ≥ 4,5 : 1, große Schrift und Symbole ≥ 3 : 1, in hell und dunkel |
| G7 | Symbole | jedes Bedienelement ohne Text hat ein Symbol aus dem eigenen Satz (`icons`) und einen Tooltip mit Name und Kürzel; ein Stil, keine Mischung |
| G8 | Bewegung | Zustandswechsel (Aufklappen, Einblenden, Hervorheben) mit Übergang aus `motion` (110–220 ms), nie länger, abschaltbar; kein Element springt ohne Übergang an eine andere Stelle |
| G9 | Direkt statt Formular | Wo eine Handlung ein Maß oder eine Lage hat, lässt sie sich in der Ansicht greifen und ziehen, mit der Zahl am Zeiger während des Zugs und Live-Vorschau — das, was Solidon besser kann als der Slicer; der Dialog bleibt für die genaue Eingabe |

G1–G8 misst Stufe A an den Widgets (Lage, Größe, Palette, Schrift, Fokus,
Übergänge); G9 und der Gesamteindruck — hochwertig, aufgeräumt, nichts
Überflüssiges — urteilt Stufe B am Bild, mit Begründung und als
Gestaltungsurteil gekennzeichnet, nicht als bewiesener Fehler. Ein G9-Fund ist
höchstens *leicht*: Ein neuer Griff ist ein eigener Registerpunkt mit Hauptweg
nach `grenzen.md` und wird nicht im Paket gebaut — sonst würde der Durchgang
zum Funktionsprogramm.

**Dazu: zeitgemäß und innovativ.** G1–G8 machen eine Oberfläche sauber und
hochwertig, aber noch nicht modern. Zwei weitere Gruppen ergänzen sie:
*zeitgemäß* heißt, dass sie sich anfühlt wie die Werkzeuge, die der Kunde
heute kennt; *innovativ* heißt, dass sie etwas kann, was Slicer, Tinkercad,
Fusion und die Browser-CAD-Werkzeuge nicht können. Beide bleiben im heutigen
Fensteraufbau — kein neuer Arbeitsbereich, keine Umschaltung Einfach/Profi,
kein Befehlsband (Entscheidungen Robert); Neues entsteht über Kontext,
Vorgaben, Vorschau, Aufklappen und Suche.

*Zeitgemäß (Z1, Z2, Z5, Z6 misst Stufe A, Z3 und Z4 urteilt Stufe B, Z7 entsteht in Stufe C):*

| | Zählgröße | Schwelle |
|---|---|---|
| Z1 | Unmittelbarkeit beim Ziehen: Griff, Geist und Zahl am Zeiger, gemessen am Bildzähler des Viewports, auf den Referenzrechner umgerechnet wie §31 | im nächsten gemalten Bild nach dem Eingabeereignis, ≤ 33 ms; die Vorschau selbst hält §2.8 und das Budget aus §31 (Prüfpunkt 6) |
| Z2 | Nicht-modal: `QApplication.activeModalWidget()` nach jeder geprüften Handlung | `None`; ausgenommen nur die Nachfragen nach Regel 19 (Löschen im Verlauf, Vollerkennung), KI- und Druckhinweis, die Speicherfrage und die Dateidialoge des Systems. Erfolg und Hinweis erscheinen nie als Meldungsfenster |
| Z3 | Am Objekt: Nach dem Klick auf die Stelle ist die Handlung ohne Menü und ohne Suche da, als Feld oben im Merkmalfenster oder als Hauptaktion im Reiter *Auswahl* (§2.6); der Rechtsklick führt keine aus (§18.5) | ja je Zeile mit Merkmals- oder Körperbezug |
| Z4 | Leere Zustände führen weiter (ergänzt E7, das den fehlenden Satz zählt) | hat ein leerer Zustand eine nächste Handlung — leere Szene, leerer Verlauf, leeres Lager —, steht sie als Knopf dabei; gewollt leere Karten und ein Prüfbericht ohne Befund ausgenommen |
| Z5 | Rohe Qt-Fenster im Kundenweg: Instanzen von `QMessageBox`, `QInputDialog`, `QColorDialog` | 0, außer `QFileDialog` und den Ausnahmen aus Z2 |
| Z6 | Größen und Skalierungen (Kontrast steht in G6, abgeschnittener Text in Prüfpunkt 9) | bei 1280 × 820 (Startgröße) und 1366 × 728 (Laptop mit Taskleiste) braucht keine Vorderseite eine Rollleiste; Symbole bei 100, 150 und 200 % ohne Unschärfe; hell und dunkel mit denselben Flächen und Akzenten |
| Z7 | Die ersten fünf Minuten (§2.3): vom Start bis zum ersten übernommenen Schritt an einem eigenen Modell | Schritte und Fehlklicks aus dem Protokoll von Stufe C, ohne Handbuch; jeder Fehlklick ist ein Fund |

*Innovativ (urteilt Stufe B, an den genannten Zeilen):*

| | Frage | Schwelle |
|---|---|---|
| I1 | Merkmal statt Dreieck: Zeigt die Ansicht beim Überfahren jeder erkannten Art Name und Maß („Bohrung Ø 5 mm“, §18.5)? Anfassen, wo `REGISTRY.for_feature` etwas führt, prüft G9 | ja an jeder Art, die die Erkennung liefert |
| I2 | Druckfolge im Moment der Handlung: Nennt das Vorschauband neue und behobene Befunde, und sagt es, wo die Druckprüfung entfällt (`wartezeit.md`)? | ja an jeder Zeile mit gerechneter Vorschau; ein Anteil an der Druckzeit ist ein Vorschlag und nennt die Herkunft „Schichtanalyse“ (Regel 14) |
| I3 | Vorschlag statt Suche: Steht ein häufiges Kundenziel nach der Auswahl ohne Suche und ohne Aufklappen da, als Hauptaktion (`quick_names`) oder als Feld oben im Merkmalfenster (`ACTION_ORDER`)? | ≥ 80 % einer vorab festgelegten Liste der häufigsten Kundenziele (§2.2, Fragebögen) |
| I4 | Befund mit Lösung: Wie viele Befundarten (`finding:<code>`) haben eine behebende Handlung (`finding.action:<id>`)? Ob sie wirkt, prüfen Prüfpunkt 7 und V5 | Zahl genannt; jede Art ohne Handlung ist ein Vorschlag |
| I5 | Vorher und nachher: Stand vor dem Schritt und Ausgangsstand (Import oder erster Schritt) mit einem Klick, Differenz mit Muster (§18.7, §19.1) | ja, an der Zeile Vorher/Nachher (D11) |
| I6 | Sagen statt suchen: Die Suchproben aus Prüfpunkt 1, zusätzlich als Frage formuliert („Loch größer machen“) | Treffer unter den ersten drei, ohne Netz; für den Chat gilt Prüfpunkt 17 |

**Bauplanzusagen sind Funde, nicht Vorschläge:** I1 (§18.5), I5 (§18.7) und
der Chatweg zu I6 (§2.6, Regel 16) sagt der Bauplan zu; wo sie fehlen, ist das
ein Fund. Ein Vorschlag ist nur, was darüber hinausgeht. Die Kamera behält ihre
eigene Belegung (§2.9, Entscheidung Robert); „wie im Slicer“ ist dort kein
Maßstab.

**Der Vergleich:** Je Durchgang werden einmal Vergleichsbilder festgelegt
(Programm, Version, Datum, außerhalb des Baums): Bambu Studio oder OrcaSlicer
für den Slicer-Kunden, Tinkercad für den Einsteiger, Shapr3D für direktes
Modellieren. Stufe B urteilt für die Hauptansichten (Hauptfenster,
Merkmalfenster, Auswahlpanel, Druckdialog, Zeichenmodus) je Z3–Z6 besser,
gleich oder schlechter und benennt den Unterschied. Diese Urteile sind als
Gestaltungsurteile gekennzeichnet, mit Bild und Begründung, nicht als
bewiesene Fehler.

**Urteil und Schwere.** Ein Fund ist *schwer* (falsches Ergebnis,
Datenverlust, Sackgasse, nicht auffindbar), *mittel* (Regelverstoß, Umweg,
Fehlerweg ohne Handlung) oder *leicht* (Text, Darstellung). Urteil je Zeile:
*gut*, *gut nach Fix* oder *offen* — *offen* nur mit RM-Nummer. Ein Prüfpunkt,
der nicht gilt, steht als *entfällt* mit einem Grund aus einer geschlossenen
Liste (Operation ohne Rechnung, ohne Auswahlbezug, ohne Dialog, ohne Agenten-
werkzeug, nur Stufe C).

**Gleiche Urteile bei zwei Prüfern:** Je Paket prüft ein zweiter Agent 10 % der
Zeilen unabhängig. Stimmen weniger als 90 % der Urteile je Prüfpunkt überein,
wird das Kriterium geschärft, bevor das Paket weitergeht.

## 5 Wie ich über die Oberfläche teste

**Stufe A — Prüfstand am echten Fenster.** `tools/file_acceptance.py` bekommt
Funktionsfälle neben den Dateifällen; Prozess und Profil je Fall, Abdruck,
Bericht und Wiederaufnahme kommen von dort, die Wartewege aus
`make_web_images`. Die Anwendung startet wie beim Kunden (echte Plattform,
sichtbar auf dem zweiten Schirm, eigenes Nutzerprofil; Startweg wie in
`file_acceptance` und `tools/window_bench.py`). Nur die Startszene entsteht
über `open_path`. **Die geprüfte
Handlung geht über Eingabeereignisse:** an der Stelle, die `area_for` nennt,
muss `QApplication.widgetAt` das Ziel oder eines seiner Kinder liefern — sonst
ist das ein Fund „verdeckt“ —, dann `QTest.mouseClick` oder `keyClicks`; Zahlen
werden getippt. Was so nicht erreichbar ist, wird ein neues Ziel im Wortschatz,
nie ein Zugriff auf private Attribute oder ein Kernaufruf. Stufe A ist ein
Werkzeuglauf im Auftrag wie RM-184, kein Fenstertest.

**Der Wortschatz wird erweitert**, an genau den zwei Stellen, an denen er lebt
(`guides.TARGET_KINDS` und je ein Zweig in `guide_targets`, gehalten von
`test_guides`): `feature:<op>` und `edge:<op>` (Merkmalfenster und
Kantenzeilen), `menu:<objectName>` als Verallgemeinerung von `history:`
(Kontextaktionen tragen den Operationsnamen als `objectName`), `finding:<code>`
und `finding.action:<id>`, `print:<feld>` aus `print_fields.FIELDS`,
`setting:<schlüssel>`, `search` (das Suchfeld des Auswahlpanels nach RM-735),
`handle:<rolle>` für Griffe und Leisten, und für Weg 1 `tree.row:<objekt>`
und `tree.row:<objekt>.<merkmal>`, `history.row:<n>`,
`feature.field:<op>.<feld>` (Feld im Merkmalfenster) und `measure.field:<feld>`
(Maßfeld im Bild). Punkte in der Ansicht liefert `point_for(…)` in
`guide_targets`, gerechnet über `Viewport.display_of`;
`make_video._world_to_window` zieht dorthin. `area_for("operation:…")` nimmt den
sichtbaren Knopf auch ohne Menüaktion (heute haben 90 von 190 Operationen eine
Aktion).

**Stufe B — Bild und Text lesen.** Ein Agent liest Bilder und Textauszug jeder
Zeile und urteilt nach E1–E7, V1–V6, G9, Z3, Z4, I1–I6 und den Prüfpunkten 2, 8,
9, 11 und 19. Die Urteile stehen je Paket in `urteile-<paket>.toml`, jedes mit
Bild und Stelle.

**Stufe C — von Hand am laufenden Fenster**, mit Maus und Tastatur
(Computer-Steuerung), nur für das, was kein Skript kann: Dateidialoge des
Systems, eine Datei aus dem Explorer ins Fenster ziehen, die vier Hauptwege aus
§2.2 einmal am Stück — Schritte und Fehlklicks gezählt, jede Entscheidung nur
aus sichtbarem Text, mit Bild belegt. Geschätzt ein bis drei Stunden. Die
Steuerung übernimmt Roberts Bildschirm; sie braucht seine Freigabe je
Anwendung und ein Zeitfenster. Rechtsziehen für die Kamera und Bilder vom
zweiten Schirm werden vorher an einer Probe gemessen. Nicht in Stufe C: die
3D-Maus (keine HID-Ereignisse; Robert von Hand oder die Tests an
`spacemouse.camera_step`); Weg 3 und Chat nur mit lokal laufendem Generator und
Modell — ein bezahlter Dienst wäre Geld und Roberts Entscheidung.

## 6 Pakete

Jede Operation gehört genau einem Paket, hergeleitet aus dem Register:
`import`, `export` → D1; `primitive`, `parts`, `variants` → D2; `boolean`,
`transform`, `shaping`, `surface` → D3; `holes` → D4; `repair`, `mesh` → D5,
außer den Operationen mit Gestenparameter (`strokes`, `armature`: Formen und
Skelett), die D6 gehören; `sketch` → D7; `scene`, `prepare` → D8; `colour`,
`label`, `fits`, `parameters` → D10. Ein Dialog oder eine Zeile des
Merkmalfensters, die zu genau einer Operation gehört, geht mit ihr in deren
Paket; die Tabelle ordnet nur, was keine eigene Operation hat — Fensterbefehle
und übrige Bedienflächen — nach seinem Bereich. Ohne Ausnahme außer D6:
*Verrunden*, *Fase* und *Fläche versetzen* (`shaping`) prüft D3, auch wenn der
Kunde sie an einer Kante oder Fläche findet; wo er sie findet, misst Prüfpunkt
1 in jedem Paket.

Registerpunkte: das Programm RM-736, die Pakete D0 bis D12 RM-737 bis RM-749,
eingetragen mit der Ablage dieses Konzepts; RM-734 (Boolesche auffindbar) und
RM-735 (Befehlspalette entfernen) gehen voraus.

| Paket | Bereich |
|---|---|
| D0 | Prüfstand, Wortschatz, Funktionsliste, Szenenkatalog, Wächter, Funddatei, Skills `ux-review` und `ui-design` |
| D1 | Datei und Projekt: Startseite, Laden, Speichern, Import samt Konturauswahl, Export, Beispiele, Wiederherstellen, Speicherfrage |
| D2 | Erzeugen: Grundkörper, Bausteinkatalog, Organizer, Text, Bild, KI, Varianten, Nachbauen |
| D3 | Verbinden und Abziehen, Transformation, Formgebung samt Verrunden, Fase und Fläche versetzen |
| D4 | Merkmale: Bohrung, Langloch, Senkung, Gewinde, Muster, erkannte Merkmale ändern und entfernen, örtliche Erkennung |
| D5 | Netz und Reparatur |
| D6 | Weg 4: Formen und Skelett (eigene Leisten, eigenes Rückgängig, eigene Gesten) |
| D7 | Zeichnen und Skizze |
| D8 | Druckvorbereitung: Ausrichten, Teilen, Anordnen, Stützen, Dichtung samt Dichtweg, Prüfbericht samt seinen Handlungen |
| D9 | Druckeinstellungen und Übergabe an den Slicer, Filamentlager |
| D10 | Filament und Farbe, Beschriftung, Passungen, Parameter, Zahlen binden, Gegenstücke, Als Baustein speichern |
| D11 | Ansicht und Bedienung: Kamera, Griffe, Objektbaum, Auswahl, Verlauf und Vorher/Nachher, Karten verschieben, Suche |
| D12 | Rahmen: Einstellungen, Ersteinrichtung, Aktivierung, Update, Handbuch, Tour, Chat, Kürzel, Rückmeldung und Fehlerbericht, KI- und Druckhinweis, Einladungen, Statusleiste, Über-Dialog |

**Reihenfolge nach Kundenwirkung**, wegen Verkaufskandidat am 25.11. und
Start am 01.12.: D0; dann D1, D9 und D8 — Weg 1 bis zum Slicer —; dann D3 und
D4; danach der Rest. Parallel höchstens zwei Pakete.

## 7 Befunde, Optimierung, Abhaken

**Funddatei** wie beim Konzept Codestruktur, bis zum Schluss unter
`.claude/.state/funktionsdurchgang-2026-10/funde.md`: je Fund `FD-<n>`, Art, Schwere,
Funktion, Prüfpunkt, Beleg (Bild, Kennzahl, Schrittfolge), Ursache,
Vorschlag, Wirkung beim Kunden, Stand. Arten: die fünf der Codestruktur —
Leistung, Stabilität, Fehler, Zwillinge, Aufräumen — und drei eigene:
**Einfachheit** (E1–E7), **Verständlichkeit** (V1–V6) und **Gestaltung**
(G1–G9, Z1–Z7, I1–I6).

**Beheben** einfach, an der Wurzel, kein Workaround. Fehler und Stabilität mit
reproduzierendem Test zuerst; Leistung mit Messung vorher und nachher,
druckgleich; Texte in allen sechs Sprachen neu übersetzt, nicht geflickt.
Viele Funde werden eine gemeinsame Wurzel haben (die Durchsicht 0.5.2 fand 86
an 12 Kernfunktionen); die Wurzel wird einmal behoben, die Zeilen verweisen
darauf. Jeder Fix wird mit Stufe A an seiner Zeile nachgeprüft, erst dann *gut
nach Fix*. Kleine Funde in eigenen Commits im Paket, größere als Registerpunkt
mit Verweis auf den Fund.

**Abhakliste:** je Paket `.claude/.state/funktionsdurchgang-2026-10/
abhakliste-<paket>.md`, versioniert, damit sie auf allen drei Maschinen gleich
ist — nur Text; Bilder und Rohdaten liegen außerhalb des Baums (`--out`). Der
Prüfstand erzeugt sie aus seinen Messungen und `urteile-<paket>.toml`; von Hand
wird sie nicht bearbeitet. Eine Datei je Paket, damit zwei parallele Pakete
keine erzeugte Datei mergen müssen. „Offen“ gibt es nur mit RM-Nummer — das
Register bleibt der einzige Ort offener Arbeit. Am Schluss ziehen Funddatei und
Ergebnisse zum Konzept nach `konzepte/`, der Zustandsordner geht.

## 8 Wiederholung

Der erste Durchgang geht über alles. Danach beim Release nur, was sich seit dem
letzten Tag geändert hat: am Registerabdruck der Spezifikation (Parameter,
`doc`, `caveat`; W3 der Codestruktur, kein zweites Werkzeug), an den
Katalogschlüsseln der Zeile oder an den Klassen ihrer Wortschatzziele — nicht
über den Importgraphen, der wegen `main_window.py` alles wählt. Der Lauf ist ein
Schritt in `/erzeugen` und ein `rendered`-Test wie die Handbuchbilder.

## 9 Reihenfolge und Abhängigkeiten

- **RM-735 vor Prüfpunkt 1, RM-734 vor den Booleschen:** Erst ohne Palette ist
  die Erreichbarkeit am richtigen Stand gemessen. Beide sind mit 0.6.1 auf main,
  Bauplan §2.6 und §19.2 sind nachgezogen. Plan und Inventur stehen in §2; die
  Inventur ist zugleich die erste Erreichbarkeitsmessung für D11.
- **Der Prüfstand früh auf main**, damit die Verschiebewerkzeuge der
  Codestruktur (W5) ihn mit umschreiben.
- **Keine Sperre:** Fixe landen wie jede andere Arbeit; die Codestruktur
  erzeugt ihren Schnitt auf jedem Stand neu. Ab deren Schritt 0 gilt für jeden
  Fix die Sperrklinke W1 mit der Ordnungsregel 6 der Codestruktur (3.1): Eine
  gelistete Datei bekommt keine neue Definition, neuer Code geht in ein neues
  Modul. Zeilen in bestehenden Rümpfen bleiben frei; eine neue Handlung am
  Fenster wird eine Komponente nach Codestruktur 3.3 — eine bestehende Methode
  um einen fremden Fall zu verlängern, damit W1 grün bleibt, ist ein Workaround
  (Codestruktur 3.1, Ordnungsregel 9).
- **Fenstertests beim Fix:** „Test zuerst“ heißt bei einem Oberflächenfehler,
  dass der reproduzierende Test ein Fenstertest ist; diese eine Datei läuft
  lokal (Entscheidung Robert, §13).
- **Kapazität:** Codestruktur und Durchgang beginnen beide nach 0.6.0. Die
  Kundenpakete (D0, D1, D9, D8, D3, D4) gehen bis zum 25.11. vor die
  Komponenten von `MainWindow` (Entscheidung Robert, §13).
- **Programmplan (Auftrag Robert, 11.10.2026):** D0, dann Codestruktur Schritt
  0. Bis zum Verkaufskandidaten am 25.11.: D1, D9 und D8 (Weg 1 bis zum
  Slicer), dann die Codestruktur-Schritte 1, 2 und 3, dann D3 und D4.
  Kundenpakete haben Vorrang; wird es eng, werden Codestruktur-Schritte
  gekürzt, nicht die Kundenpakete. Nach dem Start am 01.12.: D2, D5, D6, D7 und
  D10, D11 und D12 jeweils nach den Komponenten der Klassen, die sie berühren
  (`MainWindow`, für D11 auch `Viewport`: Kamera und Griffe).

## 10 Abnahme

- Jede Zeile hat ein Urteil; keine ist „nicht geprüft“, *offen* nur mit
  RM-Nummer, kein FD ohne Commit oder RM.
- Null schwere und null mittlere Funde offen ohne Registerpunkt.
- Je Prüfpunkt eine Gegenprobe des Prüfstands: ein absichtlich kaputter Fall,
  ohne Fenster prüfbar, der rot wird.
- Jeder Fehler- und Stabilitätsfix hat einen Test, der vor dem Fix rot war.
- Sechs Sprachen ohne abgeschnittenen Text.
- G1–G8, Z1, Z2, Z5 und Z6 ohne offenen Fund; jedes Gestaltungsurteil zu G9,
  Z3, Z4 und I1–I6 begründet und am Bild belegt; was der Bauplan zusagt (I1,
  I5, Chatweg zu I6), ist ohne offenen Fund, jedes andere fehlende I-Kriterium
  steht als Vorschlag in der Funddatei.
- Stufe C mit Protokoll: vier Hauptwege und die ersten fünf Minuten (Z7),
  Schritte und Fehlklicks.
- Übereinstimmung der Prüfer ≥ 90 % je Prüfpunkt.
- Konzept, Funddatei und Nachweise in `konzepte/` samt Index; der Wiederholungslauf
  steht in `/erzeugen`.

## 11 Aufwand und Kosten

D0 acht bis zwölf Arbeitstage (Prüfstand auf `file_acceptance`, Wortschatz,
Szenenkatalog, Wächter, Skill). Je Paket die Zeilenspezifikation
(Startszene, Beispielziel, Suchproben, Erwartung) — zum Vergleich braucht
`make_guides` für 15 Anleitungen rund 1 000 Zeilen —, der Lauf und das Lesen.
Zusammen grob acht bis zwölf Wochen einer Sitzung **ohne** die Fixe; die hängen
von den Funden ab. Nach D1 neu geschätzt.

Weitere Kosten: Platz in den Karten (`tools/CLAUDE.md` hat 537 Byte frei,
`app/ui/CLAUDE.md` 603 — die Codestruktur schafft neuen Platz), ein Eintrag in
`RENDERED_TESTS` und `/erzeugen`, die Skills `ux-review` und `ui-design` samt
`sync_agents.py`, `test_interface_limits`, Übersetzungen der Textfixe, Website
und Handbuch über Prüfpunkt 11, und ein gemeinsamer Satz in `AGENTS.md`
(„Arbeitsweise“) für beide Ausnahmen von „Fenster lokal nur beim Release“ —
die der Codestruktur (§7.2 dort) und die aus §13.1 hier —, auf den beide
Konzepte verweisen.

## 12 Abgelehnt

- **Ein drittes Fensterwerkzeug** neben `file_acceptance` und `make_guides`.
- **Die Abkürzungen der Bildwerkzeuge** (`click()` auf verdeckte Knöpfe,
  `set_value`, `emit`, `session.apply`) für die geprüfte Handlung: Sie messen
  nicht, was der Kunde erlebt.
- **Eine eigene Widget-Zuordnung**: wäre ein Zwilling von `guide_targets.py`.
- **Eine Hand-Liste** der Funktionen oder Bedienflächen.
- **Ein Wächter, der ungeprüfte Zeilen rot macht**: bände das Tor an einen
  Fensterlauf.
- **Bilder in allen Sprachen und Themen**: rund 3 600 Läufe; die Textpassung
  wird in jeder Sprache gemessen, Bilder entstehen gezielt.
- **Alles von Hand am Fenster**: zu langsam für 300 Zeilen, nicht wiederholbar.

## 13 Entscheidungen Robert (11.10.2026)

1. **Fenstertest je Fund lokal: ja.** Je Fund läuft die eine reproduzierende
   Fenstertestdatei lokal — vorher rot, nachher grün —; die übrigen
   Fenstertests fährt weiter die CI nach dem Push. Eine Ausnahme von „Fenster
   lokal nur beim Release“ nur für diesen Zweck; sie kommt mit D0 in denselben
   Satz in `AGENTS.md` („Arbeitsweise“) wie die Ausnahme der Codestruktur, und
   `.claude/rules/tests.md` verweist darauf.
2. **Vorrang bis zum 25.11.: ja.** Die Kundenpakete D0, D1, D9, D8, D3 und D4
   gehen vor die Komponenten von `MainWindow` aus dem Programm Codestruktur
   (dort Schritte 4b bis 5); Schritt 0 bis 3 der Codestruktur können daneben
   laufen.
