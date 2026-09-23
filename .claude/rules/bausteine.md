---
description: "Bausteinbibliothek, Normteiltabelle und Regelsammlung — die Lage abgezogener und aufgesetzter Bausteine, die Bereichsprüfung von Hand, parts_version"
paths:
  - "app/core/knowledge/**/*.py"
  - "app/core/counterpart.py"
---

# Regeln für Bausteine, Normteile und Regelsammlung

Der Grundsatz aus §24: **Der Agent setzt geprüfte Bausteine zusammen, statt
Geometrie zu erfinden.** Was hier liegt, ist der Vorrat, aus dem er schöpft —
und damit Teil des Rechenwegs, nicht bloß Beiwerk.

## Bausteine

- `@register_part(...)` mit `params`, `features`, `preview`, `doc`.
- Gebaut wird als **Formbeschreibung** über `shapes` und `build`, gerechnet je
  Kern: am Netzträger gegen **`manifold3d`** im eigenen Prozess, am exakten
  Träger über die Zwillinge in `exact.py` (P2.7). Damit hängt `insert_part`
  an keiner Installation und bleibt testbar — die Entscheidung fiel gegen
  OpenSCAD als Rechenweg, und seit dessen Ausbau (26.08.2026) gibt es die
  Alternative gar nicht mehr.
- **Ein Baustein fasst kein Netz an, ohne es zu sagen.** `.raw`, eine
  Dreiecksmessung, eine Netzoperation stehen hinter `shapes.mesh_only`, und
  ein Baustein mit so einer Stelle steht nicht in `ops.EXACT_PARTS`. Eine
  Gruppe gilt als exakt angeschlossen, wenn ihre Zeilen in der
  Paritätstabelle `KEEP` tragen und `tests/test_exact_parts.py` je Baustein
  Volumen gegen Analytik, Richtung, Merkmale und STEP-Rundreise belegt.
- **Kern und Gang eines Gewindes werden exakt nie vereinigt.** Die
  Vereinigung eines gesweepten Gangs mit dem Kern verschluckt den Gang still,
  und welche Fuzzy-Stufe ihn rettet, wechselt von Größe zu Größe (an zwei von
  achtzehn Rastergrößen keine). `build.threaded` liefert deshalb am exakten
  Kern einen genähten Körper (`exact.threaded` über `profiles.helical_thread`);
  wer ein Gewinde anders zusammensetzt, misst das
  Volumen gegen die Analytik, nicht gegen „gültig und geschlossen" — der
  nackte Kern ist beides.
- Benannte Features zurückgeben (`bore`, `chamfer`, …) — das sind die
  Provenienz-IDs, an denen später Ops und Passungen ansetzen.
- `to_scad()` bleibt als Ausgabeformat erhalten.
- Vorschaubild wird **gerendert**, nicht von Hand gepflegt.
- Maße von Normteilen kommen aus der Tabelle, nie hart in den Baustein.
  „Loch für M4-Einpressmutter" ist ein Nachschlagewert.

## Ein abgezogener Baustein liegt unter seiner Mündung

Der Ursprung ist die Fläche, auf die geklickt wurde; was abgetragen wird, liegt
**darunter** (§24.1). Nach oben gebaut steht der Körper vollständig neben dem
Bauteil und nimmt nichts weg — zweimal geschehen, bei der Passbohrung und der
Rasttasche, und beide Male sagte der Docstring es längst.

**Verschieben genügt dabei nicht überall.** Eine Bohrung ist bis auf ihre Fase
drehsymmetrisch; sie um ihre Tiefe nach unten zu schieben ist richtig, solange
die Fase eigens an die Mündung gesetzt wird. Ein Körper mit einem Oben und
einem Unten — eine Rastkante, ein Schwalbenschwanz, jede Sperrfläche — kippt
dabei um: Die Kante landet am tiefen Ende, wo der Haken erst hinkommt, statt
zwischen Mündung und Haken zu stehen. Gebaut wird dann **von der Mündung nach
unten, Stück für Stück**, nicht als Ganzes verschoben.

Und die Prüfung dazu misst die **Richtung**, nicht nur die Berührung: Zwei
Volumen, die sich treffen, treffen sich am falschen Ende genauso. Was der Test
sagen muss, ist, an welchem Ende die Sperrfläche sitzt.

## Ein aufgesetzter Baustein beginnt bei null

Der Ursprung ist die Fläche, und `ops._place` senkt den Baustein um
`BOOLEAN_OVERLAP` hinein — mehr nicht. Was **über** null beginnt, schwebt:
Die Profilklemmschale begann bei der Bundhöhe der Einlage, weil ihr Rahmen
schon den montierten Zustand des Paares beschrieb, und als Einzelbaustein auf
einer Fläche stand sie 1,5 mm darüber, zwei Komponenten statt einer
(16.09.2026). Der Freiraum war richtig und stand am falschen Ort.

**Was ein Paar an Versatz braucht, setzt der Weg, der das Paar baut** —
`profile_clamp_ops` gibt `build_shell` die Bundhöhe als `lift`, die Schale
selbst kennt das Maß nicht mehr. Ein Feld, das nur die Lage im Paar
beschreibt, ist kein Maß des Bausteins (oberflaeche.md: „Ein Feld ohne
Wirkung steht nicht da"). Die Prüfung dazu ist die generische
(`test_an_added_part_has_the_component_count_it_declares`): Ein aufgesetzter
Baustein verbindet sich mit seinem Träger, und ein Rahmen, der das nicht
hergibt, gehört nicht in den Katalog.

## Was vereinigt wird, kann nur weiter werden

Ein Baustein ist **ein** Körper, und seine Teile entstehen mit `union`. Wer
darin etwas *verengen* will, kann es nicht dazulegen: Die Haltelippe der
Magnettasche stand als eigener Kegel neben dem Taschenzylinder, wurde mit ihm
vereinigt und verschwand darin. Das Werkzeug war über die ganze Höhe
zylindrisch, und die Lippe hielt in keiner Einstellung etwas fest — auch nicht
bei `play = 0`, wo die Rechnung darüber noch stimmte.

Eine Verengung entsteht, indem der Körper an dieser Stelle **fehlt**: Der
Zylinder endet unter der Lippe, und die letzten Zehntel übernimmt ein Kegel mit
dem engeren Maß. Wer eine Einführschräge baut, prüft dasselbe andersherum — sie
muss die Mündung weiten, und ein Schaft mit dem schmalen Kegeldurchmesser
verengt stattdessen den Sitz (Fußtasche, derselbe Tag).

**Und die Prüfung dazu misst an der engsten Stelle.** Ein Querschnitt durch die
Mitte eines Kegels zeigt den Mittelwert; die erste Messung tat das und meldete
„hält nicht" für einen Stand, der hielt.

## Zwei Fehler übereinander zeigen eine harmlose Zahl

Dreimal an einem Tag lagen zwei Fehler so, dass sie einander zudeckten:

* Die Einführfase der Einpressbuchse rechnete `(outer - hole) / 2 + 0,3`, und in
  der Tabelle stand bei allen sechs Größen zweimal die Bohrung. Die Fase war
  konstant 0,3 mm — eine plausible Zahl, aus einer Formel, die nichts rechnete.
* Die Haltelippe verengte um feste 0,2 mm gegen ein Profilspiel von 0,20 bis
  0,35 **und** wurde vereinigt statt abgezogen. Beide Fehler zeigten dieselbe
  Öffnung: so weit wie die Tasche.
* Der Lochwand-Einhänger baute Rechtecke in ein Langloch **und** ließ 0,25 mm
  Sinkweg. Der gebaute Körper war wasserdicht, einteilig und maß in jeder
  Richtung, was er sollte.

Daraus folgt nichts über das Suchen, sondern etwas übers Glauben: **Eine Zahl,
die stimmen könnte, ist kein Beleg.** Wer einen Fehler behoben hat, misst
nach — und zwar das, was der Baustein dem Kunden verspricht, nicht das, was die
Formel ausrechnet.

## Ein Maß, das aus einem fremden Maß folgt, ist ein Fehler in Wartestellung

Der Schnappverbinder hat es vorgemacht: Seine Armlänge kam aus der
Einbindetiefe eines **Passstifts** (`1,5 mal Ø`), und der Durchmesser ist
12 Prozent der Nahtbreite. Beide Regeln sind für sich richtig — ein Stift ist
so tief eingebunden, wie er dick ist, das ist Scherfestigkeit —, und
zusammengekettet ergaben sie eine Bedingung, die niemand aufgeschrieben hätte:
Ein Federarm hätte eine Naht von 44 mm gebraucht. Gemessen fiel jede
gewöhnliche Naht auf runde Stifte zurück, dokumentiert und freundlich, und das
Werkzeug griff nie.

Wer ein Maß aus einem anderen ableitet, prüft deshalb, ob es **dieselbe Frage**
beantwortet. Federweg ist nicht Scherfestigkeit; die Zahl kommt vom Körper, in
dem der Arm sitzt, nicht vom Stift daneben. Und wer eine Rückfallregel baut,
misst einmal nach, wann sie greift: Eine, die immer greift, ist keine
Rückfallregel, sondern die Regel.

## Test über den ganzen Bereich — mit Nachweis, nicht bei jedem Lauf

Jeder Baustein wird über seinen Parameterbereich durchgerechnet: wasserdicht,
Mindestwandstärke eingehalten, keine Selbstdurchdringung an den Grenzen,
Features korrekt benannt.

**Der Lauf über alle Bausteine ist am 03.09.2026 aus der Suite gefallen**
(Entscheidung Robert). Er kostete damals rund eine Minute je Baustein, fast
alles in der Selbstdurchdringung, und machte aus einem Torlauf von Minuten
einen von einer halben Stunde. **Seit dem 22.09.2026 steht dahinter ein
Nachweis:** `tools/check_part_ranges.py` fährt den Bereichstest je Baustein in
einem eigenen Prozess und schreibt das Ergebnis nach
`data/part_ranges.toml` — mit dem Abdruck des Stands, gegen den gefahren
wurde (`parts/range_proof.py`). Dazwischen lagen drei Wochen, in denen der
Katalog für mitgelieferte Bausteine „in der Suite geprüft" annahm, und acht
Bausteine nie gefahren waren. Was gilt:

* **Ein Baustein ändern heißt, seinen Nachweis erneuern.**
  `test_every_shipped_part_carries_a_current_range_proof` rechnet nichts; er
  vergleicht die Datei mit dem Abdruck jedes Bausteins und wird rot, sobald
  Bausteindatei, gemeinsame Formen, Formmodule aus `geom`, Normteiltabelle,
  Prüfung, Parameterschema oder Bezugsprofil sich ändern.
  `python tools/check_part_ranges.py` fährt dann genau die, die nicht mehr
  passen (`--all` alle, `--check` nur vergleichen).
* **Der Katalog sagt „über den ganzen Maßbereich geprüft" nur, wo der
  Nachweis passt**, sonst die Warnung — für mitgelieferte Bausteine wie für
  eigene (§24.5).
* **Der Netzkern steht nicht im Abdruck** (Boolesche Kette, Netzhülle): Eine
  Änderung dort veraltete sonst alle Nachweise zugleich. Deshalb fährt der
  Release-Schritt „Bausteinnachweis" (`auslieferung.md`) den Lauf frisch.
* **Die Prüflogik selbst** steht weiter unter Test — Eckenberechnung, die
  kartesischen Grenzen, Wandmessung, Selbstdurchdringung (`test_parts.py`,
  `test_self_intersections.py`).
* **Der Bereichstest läuft auch in der Anwendung**: `range_check.check` hängt
  am Rezeptdialog, ein Kunde bekommt ihn für eigene Rezepte zu sehen.

**Ein Maß ohne Obergrenze ist ein Bereich ohne Rand.** Der Bereichstest fährt
von einem Feld ohne `maximum` nur die Untergrenze; der Überhangfächer lief so
bis zum 22.09.2026 nie mit breiten oder langen Stufen. Jedes Längenmaß eines
Bausteins trägt beide Grenzen. Ausgenommen sind Winkel und Versatz der
Trennebene an den Profilklemmen: Sie sind durch die Zeichnung begrenzt, nicht
durch eine Zahl, und das Klemmenpaar grenzt sie ein.

## Ein Gewindepaar wird als Paar geprüft

Dass Schraube und Mutter je für sich wasserdicht und einteilig sind, sagt
nichts darüber, ob sie zusammengehen. Geprüft wird die Überdeckung der beiden
Körper in Phase — beide Gänge beginnen an ihrem unteren Ende bei Winkel null
— über den ganzen Weg, vom Eintritt an der Spitze bis unter den Kopf
(`test_a_printed_screw_turns_through_its_printed_nut`). Bis zum 22.09.2026
begann der Netzgang genau am unteren Ende, und an der Unterseite jeder Mutter
stand ein Umlauf Material im Gang: bei M8 und 0,2 mm Spiel 2,3 mm³
Überdeckung, während beide Teile jeden Einzeltest bestanden. Der exakte
Zwilling hatte den Vorlauf von einem Umlauf schon; `build.threaded` baut ihn
seitdem auch am Netz.

## Was eine Richtung hat, wird an ihr gemessen

Rastnase und Schnapphaken standen bis zum 22.09.2026 verkehrt herum — die
Nase auf ihrer Spitze, der Haken mit der Schräge zum Fuß —, und keine
Kennzahl sah es: Volumen, Wasserdichtheit und Hülle stimmten. Ein Baustein
mit Anlaufschräge und Haltefläche wird deshalb an einem Querschnitt geprüft,
der sagt, **wo** die Schräge liegt; eine Nase zusätzlich an der Fläche, auf
der sie aufliegt. Und was abtragend gemeint ist, sagt es seinem Schalter
(`subtractive_on`), sonst wird die Aussparung vereinigt.

## Version

Ändert sich ein Maß an einem bestehenden Baustein, rechnet ein altes Projekt
sonst still anders:

1. `parts_version` erhöhen
2. Änderungsverlauf ergänzen: was, wann, warum, mit Auswirkung auf die Maße
3. Beim Öffnen meldet die Anwendung die *benutzten* geänderten Bausteine, mit
   der Wahl zwischen neu rechnen und altem Stand

## Eigene Bausteine sind kein Plugin-System

Aus `<Nutzerdaten>/parts/*.py`, beim Start eingelesen, im Katalog
gekennzeichnet. Eine **`.py` reist nie in Projektdateien mit** (Regel 13 in
der Fassung vom 24.08.2026: die Regel schützt vor ausführbarem Code): fehlt
eine, hält die Auswertung an und meldet, was fehlt. Sie erweitern die
Bibliothek, nicht die Anwendung — keine neuen Ops, kein Zugriff auf den Stack.

## Ein Rezept ist der eigene Baustein ohne Python

Seit dem 25.08.2026 gebaut (`parts/recipe.py`, Konzept Befestigungssysteme
§16–§19): ein Ausschnitt des Op-Stapels plus die Beschreibung seiner
Parameter, als Daten in `<Nutzerdaten>/parts/recipes/*.json`. Was dabei gilt:

- **Der Dokument-Ausschnitt reist als Dokument** (`scene.serialise`) und erbt
  dessen Migrationen; die Hülle trägt ihre eigene `FORMAT_VERSION`.
- **Die Version ist der Hash** über die kanonischen Daten (§24.4). Der
  Bereichstest-Bericht hängt am Rezept, aber **außerhalb** des Hashes —
  Prüfen macht aus dem Rezept kein anderes. **Der Name steckt im Hash:** Wer
  einen mitgereisten Stand (`<name>_travelled`) mit dem gespeicherten Abdruck
  vergleicht, vergleicht ihn unter dem Namen im Stapel
  (`check.saved_states`), sonst findet er nie den Stand, den die Datei
  mitgebracht hat.
- **Eine Wahl nur, wo es einen alten Stand gibt** (§24.4, RM-138). Der
  gespeicherte Stand eines Rezepts reist mit und lässt sich wählen; für die
  Bibliothek und eigene `.py` ist der neue Stand eine Migration, und der
  Befund sagt das, statt einen Knopf ohne Wirkung anzubieten.
- **Ausgewertet wird mit dem Auswerter der Szene** (`recipe.build`): dieselbe
  Rückfallkette, dieselben `auto:`-Toleranzen, dieselbe §32-Quelltextprüfung.
  Beim Einsetzen läuft `build_with_profile` mit dem Profil des Dokuments
  (`ops.insert` bevorzugt es); `fn` mit dem Standardprofil trägt Vorschau und
  Bereichstest.
- **Genau ein Körper, benannte Merkmale** — beides wird beim `capture`
  abgewiesen, nicht später halb gebaut (Konzept §18a/§18d).
- **Der Bereichstest läuft in der Anwendung** (`parts/range_check.py`, §24.3):
  dieselben Ecken wie in der Suite, mit Fortschritt und Abbruch; das Ergebnis
  steht als `PartSpec.range_passed` am Katalogeintrag (§24.5 verlangt den
  Warnhinweis, kein Verbot).
- **`travelling_parts` warnt weiter nur vor `.py`s** — ein Rezept reist als
  Daten; sein `source` ist `recipe`, nicht `user`. Gekennzeichnet wird es
  trotzdem: **`own` heißt „gehört dem Kunden"** und umfasst seit dem
  25.08.2026 beide Gestalten (§24.5 will die Kennzeichnung im Katalog) — wer
  nur die `.py`-Gestalt meint, fragt `source == "user"`, nicht `own`.
- **`to_scad()` gibt es für Rezepte nicht** — benannt, nicht umgangen
  (Konzept §18e).
- **Der Weg zurück ist `recipe.draft`** (RM-147 E6, 09.09.2026): Aus dem
  Ausschnitt wird wieder ein Projekt, aus den Payloads wieder Projektquellen,
  und beides als **Kopie** — der Katalogeintrag hält sein Dokument als
  lebendes Objekt, und ein Entwurf, der darauf zeigt, ändert den Baustein
  schon beim Bearbeiten. Der Entwurf hat keinen Dateipfad; was aus ihm wird,
  entscheidet der Rezeptdialog. **Beilagen müssen im Katalog stehen** — sie
  werden sonst nur von einem privaten Register aufgelöst, das ein Dokument im
  Fenster nicht hat, und der Entwurf hielte an einer Stelle an, die mit der
  Arbeit des Kunden nichts zu tun hat.
  Ein gleicher Name genügt nicht als Versionsbindung: Abweichende eingebettete
  Fassungen stehen als mitgereiste Einträge neben dem lokalen Stand. Der
  Entwurf verweist einschließlich seiner Undo-Seiten darauf; verschachtelte
  Beilagen reisen mit ihrem jeweiligen Unterbaustein weiter.
- **Ein eingelesenes Rezept bleibt eingelesen, auch bearbeitet.** Die Quittung
  (`ImportedOrigin`) belegt die **Reise** und nicht den Inhalt; `capture` nimmt
  sie deshalb entgegen und reicht sie durch. Ohne das machte `_catalog_source`
  beim nächsten Start aus fremder Arbeit still eigene — §32 will das Gegenteil.
  Wer beim Speichern einen anderen Namen wählt, legt einen **zweiten**
  Baustein an, und der ist seiner: Dann bleibt die Quittung weg.

## Ein Paar ist zwei Bausteine und eine Passung

`app/core/counterpart.py` setzt beide Hälften einer Verbindung als **einen**
Schritt (RM-147 E1). Drei Dinge daran sind verbindlich:

- **Es ist ein Ablauf und keine Operation**, aus demselben Grund wie bei
  `lid_flow` und `split`: Eine Op bekommt ihre Szene nur lesend (Regel 3), und
  die Auswertung ist eine reine Funktion (§15.1) — sie darf keine Passung ins
  Dokument schreiben, sonst käme bei jedem Neurechnen eine dazu. Die Passung
  reist als `DocumentChange` in derselben Transaktion (§15.5), und ein Undo
  nimmt Geometrie und Passung zusammen.
- **Die Merkmalskennung wird gelesen, nicht vorausgesagt.** Sie entsteht erst
  bei der Auswertung (`evaluate._renamed`), und `_renamed` hängt an den ganzen
  Namen an: Das zweite Paar am selben Körper heißt `dowel_pin_1_2` und nicht
  `dowel_pin_2`. Deshalb sind es zwei Aufrufe — `apply_counterpart` legt die
  Geometrie an, `attach_fit` liest die Namen aus der gerechneten Szene. Eine
  vorher hingeschriebene Kennung ist eine Vermutung, und eine Passung darauf
  geht still ins Leere.
- **Wer ein viertes Paar dazunimmt, prüft dreierlei:** dass beide Bausteine die
  genannten Merkmale wirklich führen (`PartSpec.features`), dass die
  gemeinsamen Parameter in **beiden** Schemata gleich heißen (`params.spec()`),
  und dass die Passungsart die Sache trifft. Die ersten beiden hält
  `tests/test_counterpart.py` gegen die Bibliothek — die erste Fassung der
  Tabelle war geraten, und `printed_screw` kennt kein `diameter`, sondern
  `size` und `play`.

## Normteiltabelle

Zahlen sind frei verwendbar, Normtexte und Normtabellen nicht. Werte aus frei
zugänglichen Herstellerangaben zusammentragen, keine Normblätter abschreiben —
und die Herkunft im Kommentar nennen.

## Regelsammlung

Eine Änderung an `rules/` ist ein Eingriff in das Verhalten des Agenten:
Eintrag mit Datum und Anlass, Version erhöhen, Agenten-Suite vorher und
nachher laufen lassen, beide Ergebnisse festhalten. **Verschlechtert sich die
Quote, wird die Regel zurückgenommen** — nicht trotzdem behalten.
