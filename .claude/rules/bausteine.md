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
  über die Zwillinge in `exact.py`. So hängen die Baustein-Operationen
  (`insert_*`/`create_*`, `ops.creation_name`) an keiner Installation und
  bleiben testbar; einen Rechenweg über OpenSCAD gibt es nicht.
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
- **Eine Vorlage (`template`) entsteht wie ein Grundkörper exakt, wo der Kern
  da ist** (`ops._creates_exactly`) — sie ist der Anfang einer Konstruktion. Die
  übrigen Erzeuger bauen am Netz, wie ihre gespeicherten Schritte immer
  rechneten.
- **Das eingetragene Maß ist das Maß**: Eine Befestigung richtet sich nach der
  Breite (zwei Schlüssellöcher oder eines mittig, `holders._keyholes`), statt
  den Halter über sein Maß hinaus zu verbreitern.
- **Die Grenze eines Bausteins, den eine Operation intern baut, ist nie ihr
  Satz**: Sie prüft sie vorher und sagt mit eigenem Satz, was hilft — der Stift
  an einem zu kurzen Gewinde nimmt die kürzeste druckbare Länge oder öffnet den
  Gewindeschritt (`lid_hinge._printable_thread`, `change_creating_step`); die
  rohe Grenze nannte ein Feld, dessen eigene Grenze passte.

## Ein Baustein in einer Bohrung misst sich an ihrer Wand

Sitzt ein Baustein für Bohrungen in einer (ihre Achse durch seine Mündung,
`ops._seated_bore`), ist ihre Öffnung kein Rand der Fläche — die Randprüfung
lässt sie aus. Ob er wirkt, sagt sein Radius gegen ihren, nicht das abgetragene
Volumen: In einem Sackloch schneidet ein zu enges Gewinde nur unter dem Boden.
Erreicht er die Wand nicht, meldet er `parts.bore_too_wide` mit dem Satz aus
`at_hole_advice` und *Größe ändern*.

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

## Was für sich ein Teil ist, steht frei

`standalone` sagt der Baustein selbst, die eine Quelle für Katalog,
Erzeuger und Agent: gesetzt, wo er ohne Träger seine Aufgabe erfüllt
(Kabelclip, Rippe, Standfuß, Mutter), nicht, wo er nur am Träger wirkt
(Rastnase, Federarm, Lasche, Auge, Nutfeder, Lochwand-Haken) oder nur
abträgt — Letzteres weist das Register ab. **Eine gewählte Stelle, an die er
gehört, setzt an, ein gewählter Körper nicht** (`ops.catalog_operation`): Jeder Erzeuger wählt
seinen Körper, und der zweite Clip hinge sonst am ersten. Ohne Träger gibt es
nur die aufgesetzte Form; eine abtragende Wahl muss genau ihre Vorgabe als
aufgesetzte Form übrig lassen, und kein Feld darf an ihr hängen. Seine
Unterseite liegt auf der Ebene seines Ursprungs (`_on_its_own_bed`); **nur
ohne Richtung und mit Achse Z ist das das Bett**, und ein Mündungsbaustein
steht dann kopfüber. Mit Achse X oder einer Richtung dreht diese Ebene mit,
wie bei jedem Erzeuger zuvor; aufs Bett bringt ihn *Auf das Bett setzen*. Ein alter Erzeugerschritt rechnet gleich, samt Flächenkennungen
(`test_every_creator_keeps_its_old_placement`). Aus dem Katalog kommt er auf
eine freie Stelle der Platte (`ops.free_spot_for`).
`test_every_standalone_part_makes_a_watertight_body_without_a_selection`
prüft jeden.

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
- **Zwei Grenzen, je nach Herkunft** (`range_check.corner_limit`): Ein
  eigener Baustein des Kunden prüft bis `MAX_CORNERS` (512), auf seinem
  Rechner, und der Dialog nennt vorher Kombinationen und geschätzte Dauer. Die
  mitgelieferte Bibliothek prüft bis `LIBRARY_MAX_CORNERS` (4096), einmal bei
  uns; die Grenze richtet sich nach der Rechenzeit des Nachweises (Begründung
  am Wert). Darüber lehnt der Bereichstest ab, bevor er rechnet. Eine Vorlage
  mit vielen Formen bleibt ein Baustein je Form, wo der Kunde sie im Katalog
  am Bild erkennt (`holders.py`), nicht der Grenze wegen.
- **Ein Feld ohne Wirkung zählt keine Ecken**: Wo die Bedingung eines Feldes
  (`depends_on`) in einer Ecke nicht erfüllt ist, steht es dort auf seiner
  Vorgabe (`range_check.corners`). Das setzt voraus, dass der Baustein den
  Wert dann wirklich verwirft; wer ein verstecktes Feld trotzdem liest, bricht
  den Vertrag und den Nachweis zugleich.
- **Eine Größenreihe nimmt, was die Tabelle hergibt** (RM-578, Robert: „wenn
  wir mehr liefern können, wollen wir das“): Wandhalter und Halterlaschen
  M2–M64, Klemmschale M3–M64, Rohrschelle M3–M64 (soweit Mutter und Scheibe in
  der Tabelle stehen), die Befestigungsbausteine alle und ein eigenes Maß. Wo
  eine große Größe an einem kleinen Teil nicht trägt, sagt der Bau es mit
  Vorschlag (`feasible`, etwa `_clamp_reason`, `_shell_reason`), statt sie zu
  verbieten. Begrenzt bleibt nur, was die Wand nicht trägt: der
  Stangenverbinder bei M5, weil die Schraube ihr Gewinde in die dünne Hülse
  schneidet.
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

**Ein Gewinde endet nicht an der Tabelle.** Passt keine Größe, nimmt es ein
eigenes Maß (`fasteners.CUSTOM_SIZE`), dessen Kernloch die Bohrung ist — der
Gangfuß des Druckprofils, kein ISO-Kernloch, und der Satz über dem Dialog sagt
das. Jeder Gewindeweg — Baustein, *Schraube erstellen*, *Drehdeckel
erzeugen*, Gegenstück — teilt die Grenzen `units.SMALLEST_THREAD`,
`LARGEST_THREAD`, `FINEST_PITCH` und `COARSEST_PITCH` sowie den Kernanteil
`THREAD_MIN_CORE_SHARE` (Bausteine über `fasteners.thread_problem`);
benannte Ausnahmen sind der Drehdeckel (Steigung ab 1 mm, Hals null heißt
automatisch). `test_every_thread_path_shares_the_same_limits` hält das. Am
Netz kommen die Sehnen je Umlauf aus
`shapes.turn_segments` (Drehdeckel: `lid.turn_sections`); eine eigene Zahl
dafür ist ein Zwilling. Der Netzkern überdeckt den Gang auch in der
Sehnenmitte um `BOOLEAN_OVERLAP` (`build._core_segments`), und der Gang läuft
über ganze Umläufe, bevor der Schnittzylinder kürzt; sonst bleiben ab M12
Splitter im Gang, und Schraube und Mutter überdecken sich. Wo ein Bau ablehnt,
erklärt der Baustein es über `feasible` aus derselben Regel
(`fasteners.thread_problem`). Ein Innengewinde in einer Bohrung sagt, wenn es
sie aufbohrt (`PartSpec.at_hole_check`, `parts.bore_widened`), und misst die
Wand nach außen selbst, mit Strahlen am Träger vor dem Schnitt längs seiner
Strecke ab der Mündung (`parts.thread_thin_wall`) — an einem Rohr ist die
Außenwand kein Merkmal, und die Prüfung am Endstand sähe sie nicht. Beide
Befunde können zugleich gelten, und ihr Knopf öffnet das Feld, das das Maß
trägt. Am Endstand misst die Auswertung die Wand wie um jede Bohrung
(`relations._measured` liest `length`, `is_a_cavity` liest `internal`; ein
Außengewinde zählt mit seinem Kern, nicht mit der Spitze des Gangs).

**Eine Schraube endet auch nicht an der Tabelle.** Schraubenloch,
Mutternfalle, Schraube und Mutter nehmen `CUSTOM_SIZE` mit Nenndurchmesser;
Löcher, Kopf, Mutter und Scheibe leitet `standards.derived_screw`/
`derived_nut`/`derived_washer` aus der Reihe ab (zwischen zwei Größen linear,
jenseits im Verhältnis der Randgröße), und der Befund `parts.derived_size`
nennt das Ergebnis abgeleitet. Eine Einpressbuchse mit eigenem Maß nimmt
Bohrung und Länge aus dem Datenblatt des Kunden; ihr Außendurchmesser
steht nicht da, weil nur das Loch gebaut wird.

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
Daten in `<Nutzerdaten>/parts/recipes/*.json` (`parts/recipe.py`,
`konzepte/archiv/konzept-befestigungssysteme-2026-08.md` §16–§19):

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
- **Ein Rezept ist genau ein Körper und steht deshalb für sich** (RM-574):
  `register` gibt ihm `standalone` und einen Erzeuger `create_<name>`, der
  Katalog setzt es ohne passende Stelle als eigenen Körper. Wer ein Rezept
  bindet, ersetzt, entfernt oder als Beilage auflöst, nimmt die Operationen,
  die ihm gehören (`ops.operation_names`, gefragt **vor** dem Abmelden des
  Katalogeintrags) — nie alles, was nach ihm heißt: Ein Anhang „box“ nähme
  sonst den Quader mit. **Namensschutz:** Gehört
  `create_<name>` einer anderen Operation (`create_box`), bleibt es beim
  Einsetzen, und ein neuer Baustein dieses Namens wird beim Speichern
  abgewiesen (`recipe.reserved_name`); auch Beilagenfolge und Entwurf lesen
  diesen Namen dann nicht als Rezept (`_recipe_creator`).
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
die Herkunft je Spalte im Kommentar nennen (§24.2). Händler- und
Nachschlageseiten, die diese Werte frei zeigen, zählen dazu, wenn eine
Stichprobe sie gegen eine zweite Quelle hält (`test_table_values_match_their_published_source`);
eine abgeschriebene Normtabelle bleibt draußen. Jede Zeile der metrischen Reihe rechnet
`tests/test_standards.py` gegen eine zweite Herleitung nach (Verhältnisse der
Normen, Scheibenbohrung gleich feinem Durchgangsloch), und der Stand einer
früheren Tabellenversion steht dort fest: Ein bestehender Wert ändert sich nur
mit `LIBRARY_VERSION` und `PartChange`. Mutter und Scheibe gehören zu einer
Schraube der Tabelle (`known_screw`), weil das eigene Maß von ihrem Nennmaß
aus ableitet. Nennt keine Quelle einen Wert (Senkkopf über M24, M18, M22),
steht er nach derselben Ableitungsregel gerechnet und gekennzeichnet in der
Zeile (`countersink_derived`), und der Baustein sagt es am Ergebnis — eine
Regel wie 2·d statt des Normwerts sieht der Kunde nicht. Ein abgeleiteter
Sechskant nimmt die nächste Schlüsselweite der Reihe `wrenches` (ISO 272),
sonst gäbe es keinen Schlüssel dafür; `headless` nennt Nennmaße, an denen nur
der Kopf abgeleitet ist (M60). Ein eigenes Gewindemaß innerhalb von
`THREAD_SIZE_REACH` neben einer Tabellengröße ist diese — eine Grenze für
Vorwahl und Gegenstück (`standards.thread_size_near`), sonst stünde „kein
Normgewinde“ über einer Normgröße.

## Regelsammlung

Eine Änderung an `rules/` ist ein Eingriff in das Verhalten des Agenten; es
gilt die Checkliste „Regelsammlung ändern" in `AGENTS.md` — verschlechtert
sich die Quote, wird die Regel zurückgenommen, nicht trotzdem behalten.
