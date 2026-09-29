# Review: Auto Split findet bei 60 Grad wieder eine stehende Lage

Zweig `origin/autosplit-lagen-051`, Endcommit `55f4cb358`, Basis `7351ff5e5`
(= `origin/main`). Bericht des Fix-Agenten: `reports/autosplit-lagen.md`.

**Urteil: mergebar — ja.** Kein blockierender Fund. Der Fix hält den Vertrag
von `best_of` (erst der Stand, dann das Stützvolumen), lässt jeden anderen
Aufrufer unverändert und rechnet deterministisch. Die neuen Tests sind ohne
Fix rot, ruff, format und mypy (Windows, Linux, Darwin) sind grün. An 114
gestreckten Korpusmodellen sinken die Nahtpreise „unbekannt, weil eine Hälfte
nicht steht“ von 53 auf 23. Die Naht ändert sich an zwei Modellen, beide
kosten nach voller Auswertung nicht mehr.

Zwei Funde mittlerer Schwere begrenzen, was der Fix erreicht, ohne etwas
schlechter zu machen als `origin/main`. F1: Die Ersatzlage wird nach der
Heuristik gewählt statt nach der Stützschätzung, die Preise liegen dadurch an
echten Nähten 1,4- bis 39-fach zu hoch. F2: Die Schranke der Standprüfung
verwirft Lagen, die das Urteil annimmt; ein Ring behält darum jede Naht
„unbekannt“, obwohl seine Hälften flach auf gut 600 mm² stehen. Beide lassen
sich mit einer kleinen Änderung am Ersatzlauf beheben. Dazu kommt F3, der Kugeltest zurück
auf 4. Passt das nicht mehr vor den Tag, gehören F1 und F2 ins Register.

## Umfang

**Gelesen:** der ganze Diff (6 Dateien); in `geom/orient.py`
`ranked_orientations`, `evaluate_directions`, `candidates`, `fitting_transform`,
`orient_for_print`; in `slice/orientation.py` `judge`, `_carried`, `_contact`,
`stands`, `best_of`, `best_face_candidate`, `_stands_on`, `search`; in
`geom/autosplit.py` `_best_by_support`, `_support_after_cut`, `_cut_in_two`,
`find_plane`; `prepare_ops._the_way_out_of` und `orient_for_print_op`;
`split.plan_split`; die Tests des Gebiets; die Regeln `schichtanalyse.md`,
`tests.md`, `zwillinge.md`; die Begründungsdatei; Bauplan §22.3 und §28.2 (§9
nennt keine dieser Funktionen).

**Ausgeführt:** Arbeitsbaum `wt-revlagen` auf `55f4cb358`, Vergleichsbaum
`wt-revlagen-basis` auf `7351ff5e5`, beide mit dem nativen `_chain` aus dem
Hauptbaum, gebunden `FFFFF0FF`. Die Protokolle liegen in
`laeufe/revlagen-*.txt`, die Sonden und die Rohdaten der Nahtsonde in
`sonden/review-lagen/` (Aufruf aus der Wurzel eines Arbeitsbaums). Beide
Arbeitsbäume sind wieder entfernt.

| Lauf | Ergebnis |
|---|---|
| `test_orientation_search`, `test_autosplit`, `test_orient`, `test_build_area`, `test_platform_identity`, `test_geometry_review`, `test_prepare` (ohne Fenster, Leistung, Erzeugnis, `-n 6`) | 619 von 619 gesammelten bestanden, Exit 0 |
| `test_directory_docs`, `test_language_rules`, `test_shared_constants` | 421 bestanden, 3 übersprungen, Exit 0 |
| mypy ohne Plattform, `--platform linux`, `--platform darwin` | je „no issues found in 333 source files“ |
| ruff check, ruff format --check | grün |
| Gegenprobe: die Testdateien des Fixes gegen den Code der Basis | rot: der synthetische Test (Parameter fehlt), `…pose_on_the_pin[60.0]` (gewählte Lage steht nicht), `test_a_half_that_cannot_stand…` (`isfinite` falsch); grün: `[45.0]` und der Kugeltest |
| Nahtsonde: 114 Korpusmodelle, `find_plane` an Basis und Fix | Abschnitt „Nahtwahl am Korpus“ |

Den Leistungstest selbst habe ich nicht gefahren: Neben mir liefen
`make_guides` der Release-Sitzung und der Treiber der Gesamtprüfung. Statt der
Budgetzeit habe ich den Anteil der Standprüfung am selben Ablauf gemessen
(Frage 5).

## Die fünf Fragen

### 1. Richtigkeit

**Die Verdrängung.** Ersetzt wird nur Platz 3, und nur, wenn keiner der drei
vorderen `_stands_on` besteht. Steht keiner von ihnen nach dem Urteil, gewinnt
danach die Ersatzlage in `best_of`, weil der Stand vor dem Stützvolumen
kommt. Das ist der Vertrag, kein Verlust. Eine bessere Lage kann nur
verdrängt werden, wenn eine der drei nach dem Urteil steht und `_stands_on`
das wegen seiner Schranke nicht erkennt (F2). Am Korpus kommt das an 1 von
254 Hälften vor (obj_6 Bayrak Direği, A), dort ohne Schaden. Die größere
Lücke liegt woanders: Die Ersatzlage ist die erste stehende **nach der
Heuristik**, nicht die billigste stehende (F1).

**Standprüfung gegen Urteil.** Aus `_stands_on` wahr folgt, dass das Urteil
steht, ohne Ausnahme. Es ist dasselbe Netz, dieselbe Drehung
(`rotation_to_down`), dieselbe Aufstandshöhe (`layer_height / 2` des Druckers,
wie `best_face_candidate` sie an `judge` gibt), derselbe `_contact`, dasselbe
`_carried` mit derselben Linienbreite und derselbe Vergleich wie in `stands`.
`_carried` ist wörtlich aus `judge` gezogen, `judge` rechnet unverändert. In
den Sonden, die beides ausgeben (Bayrak, Balken), stand das Urteil überall
dort, wo `_stands_on` wahr war; am Korpus des Fix-Agenten stand jede
Ersatzlage. Eine Lage, die das Urteil verwirft, bekommt den Platz also nie.

Die Umkehrung gilt nicht. Die Schranke `footprint < floor` misst die
Heuristik: Dreiecke, die fast genau nach unten zeigen. Das Urteil misst den
Querschnitt in halber Schichthöhe. Auf einer Rundung fallen beide
auseinander, der Ring und die liegende Stange in F2 sind die Belege. Das Ziel
„nichts gewonnen“ tritt also nicht ein, wohl aber verschenkte Treffer.

**Determinismus:** gegeben. Die Rangfolge ist vollständig bestimmt, und
`_contact` ist dieselbe Rechnung wie im Urteil (grobe Auswahl mit Toleranz,
exakte Bewegung). Die Entscheidung an der Schwelle `footing >= floor` hängt
genauso am letzten Bit wie in `best_of`. Das ist keine neue Klasse von
Risiko, nur eine Stelle mehr, an der sie zählt (RM-187).

### 2. Testanpassung

**Der neue Preis ist plausibel.** Mit Stiften an B steht die Hälfte auf ihrem
fernen Ende (Richtung +X, Auflage 144 mm², davon 134,1 mm² tragend, 210 mm
hoch). Alle liegenden Lagen ruhen auf einem Deckenende, der Schwerpunkt liegt
daneben; auf der Schnittfläche stehen die Stifte. Aus den Maßen von
`crossed_overhangs()` überschlagen hängen 616 mm² (Pfosten und Decke
aufrecht) in 197,5 mm Höhe und 688 mm² (seitlich) in 193 mm Höhe. Als Säulen
gerechnet sind das rund 250 700 mm³, abzüglich des selbsttragenden Saums
entlang des Balkens bei 60 Grad (tan 60° ≈ 1,73 mm je Millimeterschicht)
etwa 230 000 mm³. Gemessen wurden 238 325 mm³, dazwischen. Gegenüber der
Naht x = 3,25 (3 620,5 mm³) ist das 66-mal so viel. An der Basis kostete
dieselbe Naht „unbekannt“: B lag auf (−0,343, −0,859, −0,380) mit 0,1 mm²
Auflage.

**Die Aussage bleibt erhalten.** Den Satz „eine Lage, die nicht steht, ist
kein Preis“ trägt jetzt der zweite Teil über eine untergeschobene Lage
(2 988 mm³ auf 1,4 mm²). `autosplit` importiert `best_face_candidate` auf
Modulebene, der Patch greift also. Der erste Teil sichert etwas Neues zu:
dass B an dieser Naht steht und ehrlich teuer ist. Zwei Aussagen in einem
Test sind hier in Ordnung. Die Mängel stehen in F4: Der Faktor 10 hat keine
Herkunft, und „202 mm hoch“ stimmt nicht.

### 3. Aufrufer

**Die Vorgabe `None` ändert nichts.** Die Schleife ruft dieselben
Abbruchprüfungen und dieselben `fitting_transform` in derselben Folge und
liefert dieselbe Liste. Der Ausstieg nach dem letzten Platz rückt nur an den
Anfang der nächsten Runde, vor jeden Aufruf. Ohne Grenze wird nie
abgebrochen, wie vorher.

| Aufrufer | Aufruf | unverändert |
|---|---|---|
| `orient_for_print` | ohne `limit`, ohne `standing` | ja |
| `prepare_ops._the_way_out_of` (Splitprüfung) | `limit=1`, ohne `standing` | ja |
| `slice.orientation.search` | nutzt `evaluate_directions`, nicht `ranked_orientations`; `judge` rechnet gleich | ja |
| `best_face_candidate` → `autosplit._support_after_cut` | mit `standing` | beabsichtigt geändert |
| Tests (`test_orient`, `test_build_area`, Attrappen mit `**_kwargs`) | ohne `standing` | ja, grün |

Gespeicherte Projekte rechnen nicht neu: `split.plan_split` legt Achse,
Position, Stiftseite und Verbinderform als `split_pinned`/`split_line` in den
Verlauf. Anders teilt nur, wer Auto Split neu startet.

**`orient_for_print` ist ein eigener Punkt, kein Fehler dieses Fixes und
auch kein Rückschritt aus 0.5.1.** Der schnelle Weg („Gründlich suchen“ aus,
Vorgabe an) nimmt den ersten Platz der Heuristik ohne Standprüfung. Sonde
über 126 Korpusmodelle (`laeufe/revlagen-sonde-schnell.txt`): Bei 45 Grad
steht der erste Platz an 14 nicht, bei 60 Grad an 13. Ein Modell kippt
(clean_figure.stl steht bei 45, nicht bei 60). Den Prüfkörper des Fixes
stellt der schnelle Weg bei beiden Grenzen auf die Ellipsoidspitze (2,4 mm²
tragend). Empfehlung: ein Punkt im Register, Priorität „falsches Ergebnis in
einem gewählten Modus“. Der Weg ist mit diesem Fix schon da,
`ranked_orientations(limit=1, standing=…)`; dafür braucht `orient_for_print`
das Profil (`smallest_first_layer` hängt nur am Drucker).

### 4. Regel `schichtanalyse.md`

**Es ging kein Wissen verloren.** Beide gestrichenen Begründungen stehen unter
derselben Überschrift in `konzepte/begruendungen/regel-schichtanalyse.md`,
Zeilen 480–495: der 2 mm breite Rand des Gitterbechers (5 gegen 594 mm²) und
„an einem Gitter zeigt in jeder Lage die Hälfte nach unten — jede liegende
Lage stand vor der stehenden“. Die verallgemeinerte Fassung „weil die
Heuristik liegende Lagen vor stehende reiht“ stimmt allgemein, denn `score`
straft die Höhe mit dem Faktor 10. Die Regel verweist im Kopf auf die
Begründungsdatei. Die Datei hat 30 712 von 30 720 Byte, also 8 Byte Luft: Wer
als Nächstes etwas ergänzt, muss vorher etwas verschieben.

### 5. Leistung

| Messung | Ergebnis |
|---|---|
| Ablauf des Leistungstests nachgebaut (`sonde_review_leistungsanteil.py`, `F0FF`, unter Fremdlast) | `find_plane` 14,25 s, 36 Schichtbewertungen, Naht x = 0 symmetrisch; Standprüfung 355 Aufrufe an 12 Teilen, 12 stehend, **0,84 s = 5,9 %** |
| Korpus, 254 Hälften, 60 Grad (`laeufe/revlagen-sonde-kosten.txt`) | Mehrzeit der Vorauswahl je Hälfte Median 1,5 ms, höchstens 204 ms (obj_10 Golf Başlığı A, 55 452 Dreiecke, 5 Auflagen); zusammen +1,19 s zu 7,85 s |
| Korpus, Resin (`generic-resin-130`, `laeufe/revlagen-sonde-kosten-resin.txt`) | Median 1,0 ms, höchstens 361 ms (kumiko B, 90 Auflagen), bis 140 Auflagen je Hälfte (xobj_3 Gövde78 A); zusammen +2,25 s zu 8,37 s |

14,4–14,8 s sind glaubhaft; mein Lauf unter Fremdlast kam auf 14,25 s. Das
Budget liegt bei 20 s, die Marke im Hauptbaum bei 15,03 s (Median der letzten
fünf), die Schwelle damit bei 18,8 s. Die Aussage des Berichts „die
Standprüfung kostet rund 0,5 s (3 %)“ vergleicht zwei verschiedene Arbeiten,
denn bei 45 Grad werden andere Lagen geschnitten. Die Prüfung selbst kostet
0,84 s.

**Andere Wege zahlen nichts.** Ohne `standing` ist die Schleife dieselbe, und
`judge` kostet einen Funktionsaufruf mehr. Bei Resin ist `smallest_first_layer`
null, die Schranke greift dort nie. Das bleibt begrenzt, widerspricht aber dem
Docstring (F5). Die Resin-Zahlen sind zugleich der Anhalt dafür, was ein
Ersatzlauf ohne Schranke kostet (F2).

## Kundensicht

Vorher liefen an 60-Grad-Druckern (CC2 und die meisten Elegoo-, Bambu- und
Creality-Profile) viele Nähte mit „unbekannt“ in die Nahtwahl. Auto Split
wählte dann nach der Güte des Schnitts, ohne auf die Stützen zu achten. Jetzt
achtet es wieder darauf. Neue Texte und neue Zustände gibt es nicht. Wer Auto
Split neu startet, bekommt an einzelnen Modellen eine andere Naht (in der
Nahtsonde 2 von 114), bisher ohne mehr Stützen. Mit F1 und F2 behoben stimmt
auch die Rangfolge der Nähte, und runde Teile wie ein Ring bekommen
überhaupt einen Preis.

## Funde nach Schwere

### F1 — mittel — Der freie Platz geht an die erste stehende Lage der Heuristik, nicht an die billige

**Stelle:** `app/core/geom/orient.py:444-465`. Der Ersatz nimmt die erste Lage
in der Reihenfolge `ranked`, die `standing` besteht und passt. Aufgerufen aus
`app/core/slice/orientation.py:492-499`.

**Beleg:** `sonde_review_ersatzwahl.py` (`laeufe/revlagen-sonde-ersatzwahl.txt`)
und `sonde_review_lagen.py haelfte` (`laeufe/revlagen-sonde-haelfte.txt`).
Alle Lagen, die `_stands_on` bestehen, wurden echt geschnitten:

| Hälfte | Wahl des Fixes | kleinste Schätzung `Orientation.support` | billigste stehende |
|---|---|---|---|
| Balken x = −2, Stifte an A (B mit Löchern), 60° | Rang 6 (fernes Ende), 238 325 mm³ | Rang 7 (Schnittfläche), 6 310 | Rang 7, 6 310 |
| ma-mi-ya A, 60° | Rang 6, 13 675 | Rang 13, 2 212 | Rang 14, 2 211 |
| ma-mi-ya B, 60° | Rang 6, 13 615 | Rang 12, 2 117 | Rang 13, 2 117 |
| mini-pot-cover A / B, 60° | 202 / 198 | 193 / 187 | 183 / 186 |
| die übrigen fünf geänderten Hälften | gleiche Lage | gleiche Lage | gleiche Lage |

Am Balken kennt die Schätzung den Unterschied schon: 254 883 gegen 6 419 mm³.
Die Heuristik reiht das ferne Ende (−3 038,2) knapp vor die Schnittfläche
(−3 053,9), weil die Löcher Auflage kosten. Wie hoch die Decken hängen, sieht
sie nicht.

An den beiden Nähten, die sich in der Nahtsonde ändern, habe ich die Preise
mit allen Kandidaten je Teil nachgerechnet
(`laeufe/revlagen-sonde-clean-figure.txt`, `…-mamiya.txt`):

| Modell (gestreckt) | Naht | Preis mit drei Lagen (Fix) | mit allen Kandidaten |
|---|---|---|---|
| clean_figure.stl | Basis z = 204,8, Stifte an A | 298 291 mm³ | 57 942 |
| clean_figure.stl | Fix z = 201,6, Stifte an B | 81 192 | 56 708 |
| ma-mi-ya | Basis x = 718,20, Stifte an A | 2 437 057 | 63 010 |
| ma-mi-ya | Fix x = 715,25, Stifte an A | 1 568 798 | 63 010 |

Beide Wahlen gingen gut aus, denn die vollen Preise liegen innerhalb der fünf
Prozent. Entschieden wurde aber über Zahlen, die 1,4- bis 39-fach zu hoch
waren.

**Warum es zählt:** Der Preis einer Naht ist jetzt endlich, aber nur eine
obere Schranke. `_best_by_support` vergleicht solche Schranken zwischen
Nähten; hängen zwei Nähte am freien Platz, kann die in Wahrheit teurere
gewinnen. An der Basis entschied dort die Nahtgüte allein. Das ist der eine
Fall, in dem der Fix schlechter wählen kann als `origin/main`; beobachtet
habe ich ihn nicht. §28.2 verlangt begründete Finalisten, und genau diese
Schwäche der Heuristik ist im Haus bekannt: RM-190, `_least_support` in
`search`, `Orientation.support`.

**Fix:** Unter den Lagen hinter der Grenze, die `standing` bestehen und
passen, die mit der kleinsten Schätzung `Orientation.support` nehmen
(Gleichstand nach Richtung), zum Beispiel den Ersatzlauf über
`sorted(rest, key=lambda e: (e.support, e.direction))`. In allen Zeilen der
ersten Tabelle ist diese Wahl mindestens so gut wie die des Fixes. Test am
Balken: Naht x = −2, Stifte an A. Hälfte B steht dann auf der Schnittfläche,
und ihr Preis bleibt unter 616 mm² · 2,5 mm + 688 mm² · 7 mm (Deckenflächen
und Abstände aus `crossed_overhangs()`) zuzüglich der Lochdecken; heute sind
es 238 325 mm³. Der Leistungstest und der Stifttest bleiben gleich, denn dort
steht nur eine Lage.

### F2 — mittel — Die Schranke der Standprüfung verwirft Lagen, die das Urteil annimmt

**Stelle:** `app/core/slice/orientation.py:522-541` (Docstring 523–529,
Schranke 535, Aufstandshöhe 532);
`konzepte/begruendungen/regel-schichtanalyse.md:517-520`.

**Beleg 1, der freie Platz findet nichts** (`laeufe/revlagen-sonde-rest.txt`).
Von den Nähten, die mit dem Fix weiter „unbekannt“ kosten, habe ich jede mit
allen Kandidaten je Teil nachgerechnet, alle 23. An torus_ring.stl kosten
alle sechs Preise (drei Nähte, beide Stiftseiten) „unbekannt“, dabei liegt die
Hälfte flach (±Z) auf 609 bis 622 mm² tragender Auflage, Preis 8 282 bis
8 375 mm³. An xobj_3 Gövde78 fehlt eine Lage mit 18,3 mm² (Preis
51 171 mm³). Beide
scheitern an der Schranke: Auf einer Rundung liegt kaum ein Dreieck, das
fast genau nach unten zeigt. Die übrigen acht Modelle haben wirklich keine
stehende Lage.

**Beleg 2, der freie Platz verdrängt eine stehende Lage.** An obj_6 Bayrak
Direği, Hälfte A, tragen die acht ersten Lagen 15,94 mm² geschätzte Auflage,
also weniger als 17,64 mm². Nach dem Urteil stehen sie aber auf 58,3 mm²
(`laeufe/revlagen-sonde-bayrak.txt`). `seeking` bleibt wahr, und Platz 3 geht
bei 45 wie bei 60 Grad an Rang 69. Hier ohne Schaden (45°: 19,3 → 0,0 mm³;
60°: gleich), im Korpus einmal unter 254 Hälften.

**Warum es zählt:** Der Docstring verspricht das Urteil von `stands`, die
Begründung verspricht für den liegenden Zylinder „seine Vorauswahl bleibt,
wie sie war“. Beides trifft nicht zu. Der Ring ist das Teil, das man flach
druckt, und bekommt an 60-Grad-Druckern weiter keinen Preis. Dazu sind
Aufstandshöhe und Vergleich zweimal hergeleitet (`best_face_candidate`
Zeile 502 und `stands` einerseits, `_stands_on` Zeile 532 und 539
andererseits), und kein Test lässt beide dieselbe Frage gleich beantworten
(`zwillinge.md`, gewollter Zwilling). Ändert jemand die Höhe an einer Stelle,
verfällt der freie Platz still.

**Fix:** Die Schranke streichen und den Ersatzlauf nach der Schätzung ordnen
(F1). Die billigen Lagen stehen dann vorn, und die erste, die steht, beendet
den Lauf. Dann prüft der Platz dasselbe wie das Urteil, und für die vorderen
drei gilt: Er verdrängt nie eine Lage, die das Urteil annimmt. Bayrak A
verliert dabei seine zufällige Verbesserung bei 45 Grad. Was ein Lauf ohne
Schranke kostet, zeigt Resin (Frage 5): höchstens 140 Auflagen und 0,36 s je
Hälfte. Das sollte am Leistungstest und am Korpus nachgemessen werden. Wer
die Schranke behält, schreibt Docstring und Begründung ehrlich („ebene
Auflage bevorzugt; runde Teile bleiben unbekannt“). In beiden Fällen gehört
die Aufstandshöhe an eine Stelle (an `_stands_on` übergeben), und ein Test
dazu: für jede Lage einer Hälfte `_stands_on(e) == stands(judge(…))`, mit dem
Ring als Fall.

### F3 — niedrig — Kugeltest ohne Anlass geändert

**Stelle:** `tests/test_orientation_search.py:618`, `icosphere(subdivisions=4)`
wurde zu `5`.

**Beleg:** Weder Commit noch Bericht nennen die Änderung. Mit 4 besteht der
Test an Basis und Fix gleich (Sonde `kugel`: 13,3 mm² < 17,64,
`orient.no_footing` gemeldet). 20 480 Dreiecke liegen über `SEARCH_TRIANGLES`
(20 000). Der Test fährt jetzt also den Weg über das Ersatznetz
(`search_proxy`, `footing_mesh`), den er vorher nicht fuhr: Was er abdeckt,
hat sich still geändert. `_half_with_pin` trägt dieselbe Zeichenkette,
vermutlich ist die Zeile bei einer Ersetzung mitgekommen.

**Fix:** zurück auf 4.

### F4 — niedrig — Testanpassung: Sollwert ohne Herkunft, falsche Zahl, Voraussetzung über die Schranke

- `tests/test_autosplit.py:2529`: Der Faktor 10 hat keine Herleitung
  (`tests.md`: „Ein Sollwert trägt seine Herkunft“). Aus der Konstruktion
  lässt sie sich geben: Beide Decken (je 45 × 6 mm) haben in der aufrechten
  Lage kein Material unter sich und hängen über 190 mm hoch. Als Formel etwa
  `upright > 2 * 45.0 * 6.0 * 190.0`.
- `tests/test_autosplit.py:2510`: „202 mm hoch“. Mit Stiften steht die Hälfte
  210 mm hoch (x −10 … 200), die Überhänge hängen bei 193 bis 197,5 mm. 202 ist
  die Länge ohne Stifte.
- `tests/test_orientation_search.py:457-461`: Die Voraussetzung „vorn steht
  bei 60 Grad keine Lage“ wird über die geschätzte Auflage geprüft, also über
  die Schranke des Codes, nicht über das Urteil. Bayrak A zeigt, dass beides
  auseinanderfällt. Besser: `not any(stands(judge(…)))` über die drei.

### F5 — niedrig — Sätze und Zahlen in Docstrings und Begründung

- `app/core/geom/orient.py:417-419`: „62 Lagen auf einer Kante“. Unter den 62
  davor liegen auch liegende Lagen mit 22 bis 47 mm², die rollen
  (`laeufe/sonde-stehend-vor-x.txt`).
- `app/core/slice/orientation.py:488-490` („jede Naht“) und Begründung
  Zeile 499 („eine Naht, an der kein Teil steht“): Schon eine Hälfte ohne
  stehende Lage macht die Naht unbekannt (`_support_after_cut` bricht an der
  ersten ab), und es traf nicht jede Naht.
- `app/core/slice/orientation.py:528-529` „bleibt billig, auch wenn keine
  steht“: Bei Resin stimmt das nicht, dort ist die Grenze null und die
  Schranke greift nie (Zahlen in Frage 5). Entfällt mit F2.

## Nahtwahl am Korpus: Basis gegen Fix

`sonde_review_naht.py`, Protokolle `laeufe/revlagen-naht-basis.txt` und
`…-fix.txt`. 114 Modelle aus `tests/data/meshes` und `F:\3D Dateien` (größter
Körper bis 60 000 Dreiecke). Die längste Achse ist auf 1,6 Bauräume des CC2
gestreckt, die übrigen auf höchstens 0,75, wie beim gestreckten Körper des
Leistungstests. Dann lief `autosplit.find_plane` mit PETG (60 Grad), je Stand
ein eigener Prozess.

| Nahtpreise | Basis | Fix |
|---|---|---|
| endlich | 512 | 542 |
| „unbekannt“: eine Hälfte steht nicht | 53 | 23 |
| „unbekannt“: eine Hälfte passt nicht | 3 | 3 |
| „unbekannt“: Schnitt oder Stift | 8 | 8 |
| Modelle, an denen jede Naht „unbekannt“ kostet | 6 | 2 |

Die Naht ändert sich an zwei Modellen (clean_figure, ma-mi-ya). Nach voller
Auswertung kostet keine von ihnen mehr (Tabelle in F1). An fünf weiteren
Modellen ändern sich nur Preise. Von den 23 verbliebenen „unbekannt“ hätten
sieben mit allen Kandidaten eine stehende Lage (torus_ring sechs, xobj_3
Gövde78 eins, F2). Die übrigen 16 haben keine.

## Mitgefunden, nicht vom Prüfling

- `app/core/geom/autosplit.py:1753-1755`: Die Zahlen im Docstring von
  `_best_by_support` („an A 242 402, an B 23 883; x = 3,25: 3 754 gegen
  3 298“) stimmen weder an der Basis (x = −2 unbekannt/unbekannt, x = 3,25
  3 620,5/4 255,4) noch mit dem Fix (238 338/238 325; 3 620,5/4 255,4).
  `autosplit.py:1936` nennt x = −6,5, der Test x = −2. Der Fix ändert genau
  die Preise bei x = −2; wer F1 angeht, zieht die Zahlen mit.
- `orient_for_print` ohne Standprüfung: Frage 3, ein Punkt fürs Register.

Kann das so rein: **ja**. F1, F2 und F3 sollten gleich danach folgen, am
besten noch vor dem Tag.

---

## Nachtrag 5488ac402

Ein Commit über `55f4cb358`, derselbe Zweig. Arbeitsbäume `wt-revlagen2`
(`5488ac402`) und `wt-revlagen2-vorher` (`55f4cb358`, altes `_contact`), beide
mit nativem `_chain`, gebunden wie oben. Protokolle `laeufe/revlagen2-*.txt`,
Sonden in `sonden/review-lagen/`.

**Urteil: mergebar — ja.** F1 bis F5 sind behoben, nichts ist blockierend.
Das neue `_contact` liefert bitgenau dasselbe wie das alte, bewiesen durch
die Konstruktion und gemessen: 59 019 Vergleiche an Aufstandsfläche und
Schwerpunkt, dazu 800 Läufe der reinen Auswahl mit Grenzwerten, kein
Unterschied. *Druckoptimal ausrichten* gibt an 114
Korpusmodellen bitgleiche Ergebnisse. Einen Test, der altes und neues
`_contact` gegeneinander hält, bringt der Commit nicht mit (N1, niedrig).
Neu gesehen, aber kein Rückschritt: Die Preise bleiben ungleich genau, wenn
schon eine der drei vorderen Lagen steht (N2, fürs Register).

### Ausgeführt

| Lauf | Ergebnis |
|---|---|
| 13 Testdateien: die sieben von oben, dazu `test_whole_scene_ops`, `test_exact_body_parity`, `test_print_findings`, `test_directory_docs`, `test_language_rules`, `test_shared_constants` (ohne Fenster, Leistung, Erzeugnis) | 1 316 bestanden, 3 übersprungen, von 1 319 gesammelten; Exit 0 |
| mypy ohne Plattform, `--platform linux`, `--platform darwin` | je „no issues found in 333 source files“ |
| ruff check, ruff format --check | grün |
| Gegenprobe: neue Testdateien gegen den Code von `55f4cb358` | rot: `…goes_to_the_cheapest_pose_that_stands` (238 338 > 6 356), `…flat_ring…[False]` und `[True]` (unbekannt), `…same_question_as_the_judgement` (Signatur), `…keeps_its_last_place…` (Platz 3 ist (1, 0, 0) statt (0, 0, −1)) |
| Gegenprobe: Schranke `footprint < floor` in 5488ac402 wieder eingesetzt (`sonde_review_schranke.py`) | Zwillingstest und beide Ringtests rot, ohne Schranke grün |

### `_contact` — ist die Gleichheit belegt?

**Durch die Konstruktion: ja.** Alt galt `min(Ecken) <= h + 2e` und
`max(Ecken) >= h − 2e`. Neu gilt „eine Ecke <= h + 2e“, danach dasselbe
`max` über dieselben drei Werte. Für Gleitkommazahlen ist `min <= t` genau
„mindestens eine Ecke <= t“, auch mit ±inf. Mit NaN ist `max` NaN, der
Vergleich falsch, und das Dreieck fällt wie vorher heraus. `np.flatnonzero`
und `near[…]` liefern dieselben Indizes in derselben aufsteigenden Folge wie
die alte Maske. Damit sind `faces[crossing]`, `np.unique`, das Band und der
Schnitt dieselben; der Rest der Funktion ist unverändert.

**Gemessen** (`sonde_review_contact.py`, das alte `_contact` wörtlich aus
`55f4cb358`, verglichen WKB der Fläche und Bytes des Schwerpunkts):

| Prüfung | Fälle | verschieden |
|---|---|---|
| reine Auswahl: Ecken genau auf h, h ± 2·EPS_GEOM, je eine Stelle daneben, h ± 1e-12, NaN, ±inf, ±1e300, Dreiecke mit zwei oder drei gleichen Ecken, Werte im Rauschen um h | 800 Durchläufe zu je 5 000 Dreiecken | 0 |
| gebaute Körper: Stufe genau in der Aufstandsebene, an h ± 2e und eine Stelle daneben, h + 1e-12; Platte um 0,001° gekippt; Pyramide mit Spitze genau auf h; Kugel; Zylinder; je alle Kandidatenrichtungen, Höhen 0,1 / 0,025 / 0,5 mm | 1 092 | 0 |
| Korpus `tests/data/meshes` und `F:\3D Dateien`, 131 Körper bis 150 000 Dreiecke, alle Kandidatenrichtungen, drei Höhen | 57 927 | 0 |

Zeit derselben Aufrufe: alt 115,4 s, neu 48,9 s.

**Ende zu Ende** (`sonde_review_suche.py`, `vergleich_suche.py`): `search`
mit CC2/PETG, `count=40`, an 114 Modellen in beiden Bäumen. Verglichen wurden
Richtung, Stützvolumen, erste Schicht, Höhe, Stand, tragende Auflage (alles
als `float.hex`), dazu Ausgangslage, Zahl der Schnitte, Hash der Matrix und
die Befunde samt Werten. Kein Modell weicht ab. `stays` läuft darin mit.

**Exakter Kern:** `_contact` sieht nur `MeshData`. Ein B-Rep-Körper kommt als
Netz an (`as_mesh_data(entry.mesh)` in `orient_for_print_op`), einen eigenen
Weg gibt es nicht. `_contact` wird nur in `orientation.py` gerufen (`judge`,
`_stands_on`).

**N1 — niedrig — kein bleibender Gegentest.**
`test_the_free_place_asks_the_same_question_as_the_judgement` hält
`_stands_on` gegen `judge`, beide mit dem neuen `_contact`. Die Umstellung
selbst sichert kein Test. Die Gleichheit ist bewiesen, deshalb blockiert das
nicht. Empfehlung: ein kleiner Test mit der Stufe genau auf h, h ± 2e und
eine Stelle daneben. Er vergleicht die Aufstandsfläche mit einer
Brute-Force-Auswahl (min/max je Dreieck) und hält damit die Semantik der
Toleranz fest, nicht den alten Code.

### F1 bis F5

- **F1 behoben.** Der Ersatzlauf sortiert nach `(support, direction)`
  (`orient.py:459-474`). Am Balken bei x = −2 mit Stiften an A steht B jetzt
  auf (−0,996, 0, 0,086) und kostet 5 099 mm³, die Naht 5 111,6
  (`laeufe/revlagen2-sonde-balken.txt`). Das ist eine um 4,9° gekippte Lage
  auf 42 mm² tragender Auflage, billiger als flach auf der Schnittfläche
  (6 310). `stands` erlaubt sie, dieselbe Regel wie in `search`.
- **F2 behoben.** Die Schranke ist weg. `_stands_on` fragt `stands` selbst,
  die Aufstandshöhe kommt einmal aus `best_face_candidate`
  (`orientation.py:496-503`, `526-543`). Die drei vorderen Plätze werden ohne Schranke
  geprüft, der Platz verdrängt also keine Lage mehr, die das Urteil annimmt
  (Korpus: 0 von 254 Hälften, vorher 1). Der Zwillingstest steht, und er ist
  mit Schranke rot.
- **F3 behoben.** Kugel wieder `subdivisions=4`.
- **F4 behoben.** Hälfte B steht mit 210 mm im Docstring. Die Grenze
  `2 * (45.0 * 6.0) * 190.0` = 102 600 ist aus der Konstruktion hergeleitet
  und trägt: Beide Decken haben in der aufrechten Lage nichts unter sich
  (Decke aufrecht z 35–41, seitlich y 35–41, der Balken bei |y| ≤ 6, z ≤ 12)
  und hängen bei 193 bzw. 197,5 mm. Gemessen 238 325. Die Voraussetzung im
  Stifttest fragt jetzt `stands(judge(…))`.
- **F5 behoben**, die Docstrings stimmen. Die Zahlen in `_best_by_support`
  (`autosplit.py:1753-1755`) stimmen jetzt auch: 5 112 / 238 325 und
  3 620 / 4 255, gemessen 5 111,6 / 238 325,4 und 3 620,5 / 4 255,4.
  `autosplit.py:1936` nennt weiter x = −6,5 (alt, nicht vom Prüfling).

### `test_real_support_moves_the_seam_between_crossed_overhangs`

**Die neue Grenze `1 − SUPPORT_TIE` ist die richtige Aussage.** Genau unter
dieser Grenze schlägt in `_best_by_support` eine Naht die besser bewertete
(`support < best − max(best, support) · SUPPORT_TIE`). Zusammen mit
`candidate.position > 2.0` heißt der Test also: Das Stützvolumen hat
entschieden, und die Naht ist gewandert. Die alte 0,5 war nie hergeleitet und
hielt nur, solange die Mitte zu teuer bepreist war.

| Stand | Mitte x = −3,25 | gewählt x = 3,25 | Verhältnis |
|---|---|---|---|
| `55f4cb358`, drei Lagen | 8 097,4 | 3 584,9 | 0,443 |
| `5488ac402`, drei Lagen | 5 275,5 | 3 584,9 | 0,680 |
| alle Kandidaten je Teil | 5 275,5 | 571,0 | 0,108 |

Zur Grenze 0,95 bleibt reichlich Abstand. Der Kommentar „lag ihr Preis um
Größenordnungen darüber“ trifft auf `55f4cb358` nicht zu (1,5-fach), nur auf
die Basis (unbekannt). Das ist ein Satz, kein Fund.

### N2 — niedrig, fürs Register: Der freie Platz greift nur, wenn vorn keine Lage steht

Steht eine der drei Lagen der Heuristik, bleibt es bei ihnen, auch wenn diese
Lage teuer ist. Die Hälften der gewählten Naht oben kosten mit drei Lagen
3 585, mit allen Kandidaten 571 mm³. Nähte, die den freien Platz brauchen,
bekommen dagegen die billigste stehende Lage nach der Schätzung. Zwei Nähte
werden damit ungleich genau bepreist, und das begünstigt die, deren Hälften
vorn nicht stehen. Nahtsonde an 114 Modellen, `5488ac402` gegen die Basis
(`laeufe/revlagen2-naht.txt`, Nachrechnung `laeufe/revlagen2-zwei-*.txt`;
bei „z =“ im Protokoll steht die Achse aus dem Aufruf):

| Modell (gestreckt) | Wahl Basis → 5488ac402 | Preis drei Lagen | Preis alle Kandidaten |
|---|---|---|---|
| mini-pot-cover-x1 | x = −49,41 → −52,36, Stifte an A | 159 610 → 79 117 | 53 003 → 51 088 |
| clean_figure | z = 204,8: Stifte an A → an B | 62 722 → 55 886 | 57 942 → 55 967 |
| ma-mi-ya | x = 718,20: Stifte an A → an B | 1 679 711 → 63 064 | 63 010 → 63 010 |

In allen drei Fällen braucht die neue Wahl gleich viel oder weniger Stütze
(−3,6 %, −3,4 %, ±0). Nach den vollen Preisen hätte aber jedes Mal die
Fünf-Prozent-Grenze die alte Wahl gehalten. Entschieden wurde über Zahlen bis
zum 26,7-Fachen. Ein Rückschritt ist das nicht; an der Basis waren alle drei
Nähte „unbekannt“. Vorschlag für nach 0.5.1: Die billigste stehende Lage nach
der Schätzung bekommt den dritten Platz auch dann, wenn vorn eine steht, aber
teurer geschätzt wird. Das kostet keinen zusätzlichen Schnitt. Übrige Zahlen
der Sonde: „unbekannt, Hälfte steht nicht“ 53 → 16 (mit `55f4cb358` 23),
Modelle mit nur unbekannten Nähten 6 → 1.

### Leistung

| Messung | `55f4cb358` | `5488ac402` |
|---|---|---|
| Ablauf des Leistungstests nachgebaut, `F0FF`, im Wechsel, zwei Runden (`revlagen2-sonde-anteil-*`) | 14,60 / 14,98 s; Standprüfung 355 Aufrufe, 0,87 s | 15,38 / 15,98 s; 394 Aufrufe, 1,20–1,22 s (7,8 %); 36 Schichtbewertungen, Naht x = 0 symmetrisch |
| Korpus, 254 Hälften, 60°: Mehrzeit der Vorauswahl (`revlagen2-sonde-kosten.txt`) | zusammen +1,19 s, höchstens 204 ms | zusammen +2,99 s, Median 1,5 ms, höchstens 821 ms (obj_17_Cylinder_A_A B, 5 036 Dreiecke, 213 Prüfungen, weil keine Lage steht) |
| `find_plane` an obj_12_Cylinder_A_A (gestreckt), `F0FF`, allein | 26,19 s | 25,45 s |

Die 15,1–15,9 s des Agenten passen, gegenüber `55f4cb358` sind es
+0,8–1,0 s. Budget 20 s, die Schwelle über der Marke des Hauptbaums
(15,03 s) liegt bei 18,8 s. Nachmessen soll ohnehin die Release-Sitzung nach
dem Merge. Wo keine Lage steht, prüft der Ersatzlauf ohne Schranke jede
übrige Lage, bis 0,9 s je Hälfte. Das bleibt begrenzt; an obj_12_Cylinder
fiel es nicht ins Gewicht. Die Zeiten der Nahtsonde (730 gegen 528 s) taugen
nicht als Vergleich: Der Lauf auf `5488ac402` lief neben drei anderen Sonden,
die Einzelmessung oben zeigt keinen Unterschied. Das schnellere `_contact`
macht auch `judge` auf allen Wegen schneller.

Kann `5488ac402` so rein: **ja**.
