---
description: "Bausteinbibliothek, Normteiltabelle und Regelsammlung — Formbeschreibung je Kern, Lage abgezogener und aufgesetzter Bausteine, Bereichsnachweis, Bibliotheksversion, Rezepte und Paare"
paths:
  - "app/core/knowledge/**/*.py"
  - "app/core/counterpart.py"
---

# Regeln für Bausteine, Normteile und Regelsammlung

**Der Agent setzt geprüfte Bausteine zusammen, statt Geometrie zu erfinden**
(§24) — der Vorrat hier ist Teil des Rechenwegs. Die Checkliste „neuer
Baustein" in `AGENTS.md` gilt (`@register_part(...)` ohne Vorschau-Argument,
benannte Features wie `bore` und `chamfer` als Provenienz-IDs, `to_scad()` als
Ausgabeformat, Normteilmaße aus der Tabelle, Vorschaubild gerendert von
`parts/preview.py`); hier steht, was darüber hinausgeht. Das Warum steht unter denselben Überschriften in
`konzepte/begruendungen/regel-bausteine.md`.

## Bausteine

- **Gebaut wird als Formbeschreibung** über `shapes` und `build`, gerechnet je
  Kern: am Netzträger gegen `manifold3d` im eigenen Prozess, am exakten Träger
  über die Zwillinge in `exact.py`. So hängt `insert_part` an keiner
  Installation und bleibt testbar; einen Rechenweg über OpenSCAD gibt es
  nicht.
- **Ein Baustein fasst kein Netz an, ohne es zu sagen**: `.raw`, eine
  Dreiecksmessung, eine Netzoperation stehen hinter `shapes.mesh_only`, und
  ein solcher Baustein steht nicht in `ops.EXACT_PARTS`. Eine Gruppe gilt als
  exakt angeschlossen, wenn ihre Zeilen in der Paritätstabelle `KEEP` tragen
  und `tests/test_exact_parts.py` je Baustein Volumen gegen Analytik,
  Richtung, Merkmale und STEP-Rundreise belegt.
- **Kern und Gang eines Gewindes werden exakt nie vereinigt** — die
  Vereinigung verschluckt den Gang still. `build.threaded` liefert am exakten
  Kern einen genähten Körper (`exact.threaded` über `profiles.helical_thread`);
  wer ein Gewinde anders zusammensetzt, misst das Volumen gegen die Analytik,
  nicht gegen „gültig und geschlossen" — der nackte Kern ist beides.
- „Loch für M4-Einpressmutter" ist ein Nachschlagewert in der Normteiltabelle,
  nie eine Zahl im Baustein.

## Ein abgezogener Baustein liegt unter seiner Mündung

Der Ursprung ist die Fläche, auf die geklickt wurde; was abgetragen wird,
liegt **darunter** (§24.1). Nach oben gebaut steht der Körper neben dem
Bauteil und nimmt nichts weg.

- **Verschieben genügt nicht überall.** Eine drehsymmetrische Bohrung darf um
  ihre Tiefe nach unten, wenn die Fase eigens an die Mündung gesetzt wird. Ein
  Körper mit Oben und Unten — Rastkante, Schwalbenschwanz, jede Sperrfläche —
  wird **von der Mündung nach unten, Stück für Stück** gebaut; als Ganzes
  verschoben kippt er um.
- **Die Prüfung misst die Richtung**, nicht nur die Berührung: Sie sagt, an
  welchem Ende die Sperrfläche sitzt.
- **Schräg zur Fläche gesetzt, öffnet er trotzdem bis über sie.** Die Richtung
  bleibt Eingabe; angehoben wird der Deckel der Öffnung
  (`ops._opened_to_the_face`) bis über die **Ebene der Fläche am
  Ansatzpunkt**, nicht durch den Körper — Strahlen durch alles zögen eine
  Tasche neben einer Wand durch die Wand. Ein Ansatzpunkt tief im Körper
  bleibt ein eingeschlossener Hohlraum.
- **Eine Haltelippe unter der Mündung erklärt sich** (`retaining_lip`,
  `RetainingLip`: Wort, Höhe, Umriss). Schräg gesetzt liegt die Fläche auf der
  tiefen Seite unter der Mündung; wo sie am Umriss tiefer liegt als die Lippe
  reicht, meldet die Operation `parts.lip_on_a_slant` mit *Eingabe
  korrigieren* — die Grenze kommt aus Höhe und Umriss, nicht aus einer
  Gradzahl.

## Ein lösbares Teil ist kein Zerfall

Schraube, Mutter und separate Dichtung (`separate_from_host`) liegen gewollt
als eigene Teile neben ihrem Träger. Die Auskunft kommt aus dem Baustein und
reist über `OperationSpec.leaves_separate_parts` zu Auswertung und
Assistentenprüfung — keine Namensliste dort. Zerfällt der **Träger** selbst
(eine Senkung schneidet einen schmalen Streifen durch), sagt es die Operation
mit `feature.body_split`: Nur sie hat Träger und Teil noch getrennt in der
Hand.

**Lösbar heißt auch an Ort und Stelle gedruckt lösbar**: Ein lösbares Teil
hält zu seinem Sitz das ganze Spiel aus dem Materialprofil — Sechskantkopf
und Mutter stehen um das Spiel über der Fläche, die Senkung steht um das Spiel
senkrecht zur Flanke vom Senkkopf ab. Eine Berührungsfläche verschweißt im
Druck, und das Gewinde allein macht kein Teil lösbar.

## Ein aufgesetzter Baustein beginnt bei null

`ops._place` senkt ihn um `BOOLEAN_OVERLAP` in die Fläche, mehr nicht; was
**über** null beginnt, schwebt. **Den Versatz eines Paares setzt der Weg, der
das Paar baut** (`profile_clamp_ops` gibt `build_shell` die Bundhöhe als
`lift`); ein Feld, das nur die Lage im Paar beschreibt, ist kein Maß des
Bausteins (`oberflaeche.md`: „Ein Feld ohne Wirkung steht nicht da").
`test_an_added_part_has_the_component_count_it_declares` prüft generisch: Ein
aufgesetzter Baustein verbindet sich mit seinem Träger, und ein Rahmen, der
das nicht hergibt, gehört nicht in den Katalog.

## Was vereinigt wird, kann nur weiter werden

Ein Baustein ist **ein** Körper, seine Teile entstehen mit `union`. Eine
**Verengung** entsteht, indem der Körper an dieser Stelle **fehlt** — der
Zylinder endet unter der Lippe, die letzten Zehntel übernimmt ein Kegel mit
dem engeren Maß —, nie durch ein dazugelegtes Teil. Eine Einführschräge muss
die Mündung weiten, nicht den Sitz verengen. Gemessen wird an der **engsten
Stelle**, nicht am Mittelwert eines Querschnitts.

## Zwei Fehler übereinander zeigen eine harmlose Zahl

**Eine Zahl, die stimmen könnte, ist kein Beleg.** Wer einen Fehler behoben
hat, misst nach — und zwar, was der Baustein dem Kunden verspricht, nicht was
die Formel ausrechnet.

## Ein Maß, das aus einem fremden Maß folgt, ist ein Fehler in Wartestellung

Wer ein Maß aus einem anderen ableitet, prüft, ob es **dieselbe Frage**
beantwortet — Federweg ist nicht Scherfestigkeit; die Zahl kommt vom Körper,
in dem der Arm sitzt, nicht vom Stift daneben. Wer eine Rückfallregel baut,
misst einmal, wann sie greift: Eine, die immer greift, ist keine
Rückfallregel, sondern die Regel.

## Test über den ganzen Bereich — mit Nachweis, nicht bei jedem Lauf

Jeder Baustein wird über seinen Parameterbereich durchgerechnet:
wasserdicht, Mindestwandstärke, keine Selbstdurchdringung an den Grenzen,
Features korrekt benannt. Der Lauf steht nicht in der Suite (Entscheidung
Robert), sondern hinter einem Nachweis: `tools/check_part_ranges.py` fährt je
Baustein in einem eigenen Prozess und schreibt `data/part_ranges.toml` mit dem
Abdruck des gefahrenen Stands (`parts/range_proof.py`).

- **Einen Baustein ändern heißt, seinen Nachweis erneuern.**
  `test_every_shipped_part_carries_a_current_range_proof` rechnet nichts; er
  vergleicht die Datei mit dem Abdruck jedes Bausteins und wird rot, sobald
  Bausteindatei, gemeinsame Formen, Formmodule aus `geom`, Normteiltabelle,
  Prüfung, Parameterschema oder Bezugsprofil sich ändern.
  `python tools/check_part_ranges.py` fährt genau die unpassenden (`--all`
  alle, `--check` nur vergleichen).
- **Der Katalog sagt „über den ganzen Maßbereich geprüft" nur, wo der
  Nachweis passt**, sonst die Warnung — für mitgelieferte wie eigene
  Bausteine (§24.5).
- **Der Netzkern steht nicht im Abdruck** (Boolesche Kette, Netzhülle) —
  sonst veraltete jede Änderung dort alle Nachweise zugleich. Deshalb fährt
  der Release-Schritt „Bausteinnachweis" (`auslieferung.md`) den Lauf frisch.
- **Die Prüflogik selbst** bleibt unter Test: Eckenberechnung, kartesische
  Grenzen, Wandmessung, Selbstdurchdringung (`test_parts.py`,
  `test_self_intersections.py`).
- **Der Bereichstest läuft auch in der Anwendung**: `range_check.check` hängt
  am Rezeptdialog, ein Kunde sieht ihn für eigene Rezepte.
- **Ein Maß ohne Obergrenze ist ein Bereich ohne Rand**: Ohne `maximum` fährt
  der Test nur die Untergrenze. Jedes Längenmaß eines Bausteins trägt beide
  Grenzen; ausgenommen Winkel und Versatz der Trennebene an den Profilklemmen —
  sie begrenzt die Zeichnung, und das Klemmenpaar grenzt sie ein.

## Ein Gewindepaar wird als Paar geprüft

Einzeln wasserdicht und einteilig sagt nichts darüber, ob Schraube und Mutter
zusammengehen. Geprüft wird die Überdeckung beider Körper in Phase — beide
Gänge beginnen am unteren Ende bei Winkel null — über den ganzen Weg, vom
Eintritt an der Spitze bis unter den Kopf
(`test_a_printed_screw_turns_through_its_printed_nut`). `build.threaded` baut
den Vorlauf von einem Umlauf an beiden Kernen.

## Was eine Richtung hat, wird an ihr gemessen

Volumen, Wasserdichtheit und Hülle sehen eine verkehrt herum gebaute Nase
nicht. Ein Baustein mit Anlaufschräge und Haltefläche wird deshalb an einem
Querschnitt geprüft, der sagt, **wo** die Schräge liegt; eine Nase zusätzlich
an der Fläche, auf der sie aufliegt. Was abtragend gemeint ist, sagt es seinem
Schalter (`subtractive_on`), sonst wird die Aussparung vereinigt.

## Version

Ändert sich ein Maß an einem bestehenden Baustein, rechnet ein altes Projekt
sonst still anders: `LIBRARY_VERSION` (`parts/registry.py`) erhöhen, am
Baustein einen `PartChange` in `changes=` ergänzen — `version`, `date`,
`reason` und den übersetzbaren `effect`, was sich an den Maßen ändert; der
Stand des Bausteins ergibt sich daraus —, danach `tools/make_examples.py`
fahren (§24.4). Beim Öffnen vergleicht `check.py` die Bibliothek mit dem
`parts_version` des Dokuments und nennt je **benutztem** geänderten Baustein
den `effect`-Satz (`parts.change`); eine Wahl zwischen neu und alt gibt es nur,
wo ein alter Stand mitreist (Rezepte, unten).

## Eigene Bausteine sind kein Plugin-System

Aus `<Nutzerdaten>/parts/*.py`, beim Start eingelesen, im Katalog
gekennzeichnet. Eine **`.py` reist nie in einer Projektdatei mit** (Regel 13):
Fehlt eine, hält die Auswertung an und meldet, was fehlt. Sie erweitern die
Bibliothek, nicht die Anwendung — keine neuen Ops, kein Zugriff auf den
Stapel.

## Ein Rezept ist der eigene Baustein ohne Python

Ein Ausschnitt des Op-Stapels plus die Beschreibung seiner Parameter, als
Daten in `<Nutzerdaten>/parts/recipes/*.json` (`parts/recipe.py`, Konzept
Befestigungssysteme §16–§19):

- **Der Dokument-Ausschnitt reist als Dokument** (`scene.serialise`) und erbt
  dessen Migrationen; die Hülle trägt ihre eigene `FORMAT_VERSION`.
- **Die Version ist der Hash** über die kanonischen Daten (§24.4); der
  Bereichstest-Bericht hängt am Rezept, aber **außerhalb** des Hashes —
  Prüfen macht kein anderes Rezept. **Der Name steckt im Hash**: Einen
  mitgereisten Stand (`<name>_travelled`) vergleicht man unter dem Namen im
  Stapel (`check.saved_states`), sonst findet man nie den Stand, den die Datei
  mitgebracht hat.
- **Eine Wahl nur, wo es einen alten Stand gibt** (§24.4): Der gespeicherte
  Stand eines Rezepts reist mit und lässt sich wählen; für die Bibliothek und
  eigene `.py` ist der neue Stand eine Migration, und der Befund sagt das,
  statt einen Knopf ohne Wirkung anzubieten.
- **Ausgewertet wird mit dem Auswerter der Szene** (`recipe.build`): dieselbe
  Rückfallkette, dieselben `auto:`-Toleranzen, dieselbe §32-Quelltextprüfung.
  Beim Einsetzen läuft `build_with_profile` mit dem Profil des Dokuments
  (`ops.insert` bevorzugt es); `fn` mit dem Standardprofil trägt Vorschau und
  Bereichstest.
- **Genau ein Körper, benannte Merkmale** — beides wird beim `capture`
  abgewiesen, nicht später halb gebaut (Konzept §18a/§18d).
- **Der Bereichstest läuft in der Anwendung** (`parts/range_check.py`,
  §24.3): dieselben Ecken wie in der Suite, mit Fortschritt und Abbruch; das
  Ergebnis steht als `PartSpec.range_passed` am Katalogeintrag (§24.5 verlangt
  den Warnhinweis, kein Verbot).
- **`travelling_parts` warnt nur vor `.py`s** — ein Rezept reist als Daten,
  sein `source` ist `recipe`. **`own` heißt „gehört dem Kunden"** und umfasst
  beide Gestalten; wer nur die `.py` meint, fragt `source == "user"`.
- **`to_scad()` gibt es für Rezepte nicht** — benannt, nicht umgangen
  (Konzept §18e).
- **Der Weg zurück ist `recipe.draft`**: Ausschnitt → Projekt, Payloads →
  Projektquellen, beides als **Kopie** — der Katalogeintrag hält sein Dokument
  als lebendes Objekt, ein Entwurf darauf änderte den Baustein schon beim
  Bearbeiten. Der Entwurf hat keinen Dateipfad; was aus ihm wird, entscheidet
  der Rezeptdialog. **Beilagen müssen im Katalog stehen**, sonst löst sie nur
  ein privates Register auf, das ein Dokument im Fenster nicht hat. Ein
  gleicher Name ist keine Versionsbindung: Abweichende eingebettete Fassungen
  stehen als mitgereiste Einträge neben dem lokalen Stand; der Entwurf
  verweist samt Undo-Seiten darauf, verschachtelte Beilagen reisen mit ihrem
  Unterbaustein.
- **Ein eingelesenes Rezept bleibt eingelesen, auch bearbeitet**: Die
  Quittung (`ImportedOrigin`) belegt die **Reise**, nicht den Inhalt; `capture`
  nimmt sie entgegen und reicht sie durch — sonst machte `_catalog_source`
  beim nächsten Start aus fremder Arbeit still eigene (§32). Wer beim
  Speichern einen anderen Namen wählt, legt einen **zweiten**, eigenen
  Baustein an, ohne Quittung.

## Ein Paar ist zwei Bausteine und eine Passung

`app/core/counterpart.py` setzt beide Hälften einer Verbindung als **einen**
Schritt:

- **Ein Ablauf, keine Operation** — wie `lid_flow` und `split`: Eine Op bekommt
  ihre Szene nur lesend (Regel 3), und die Auswertung ist eine reine Funktion
  (§15.1), die keine Passung ins Dokument schreiben darf. Die Passung reist als
  `DocumentChange` in derselben Transaktion (§15.5); ein Undo nimmt Geometrie
  und Passung zusammen.
- **Die Merkmalskennung wird gelesen, nicht vorausgesagt**: Sie entsteht erst
  bei der Auswertung (`evaluate._renamed` hängt an den ganzen Namen an — das
  zweite Paar am selben Körper heißt `dowel_pin_1_2`, nicht `dowel_pin_2`).
  Deshalb zwei Aufrufe: `apply_counterpart` legt die Geometrie an,
  `attach_fit` liest die Namen aus der gerechneten Szene.
- **Wer ein weiteres Paar dazunimmt, prüft dreierlei**: dass beide Bausteine
  die genannten Merkmale führen (`PartSpec.features`), dass die gemeinsamen
  Parameter in **beiden** Schemata gleich heißen (`params.spec()`), und dass
  die Passungsart die Sache trifft. Die ersten beiden hält
  `tests/test_counterpart.py` gegen die Bibliothek.

## Normteiltabelle

Zahlen sind frei verwendbar, Normtexte und Normtabellen nicht: Werte aus frei
zugänglichen Herstellerangaben zusammentragen, keine Normblätter abschreiben,
die Herkunft im Kommentar nennen.

## Regelsammlung

Eine Änderung an `rules/` ist ein Eingriff in das Verhalten des Agenten; es
gilt die Checkliste „Regelsammlung ändern" in `AGENTS.md` — verschlechtert
sich die Quote, wird die Regel zurückgenommen, nicht trotzdem behalten.
