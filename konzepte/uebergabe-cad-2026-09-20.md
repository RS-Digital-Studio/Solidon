# Übergabe der CAD-Umsetzung – 20. September 2026

> Übergabestand der bisherigen Hauptsession nach P1.4c.1. Der Gesamtauftrag
> ist nicht abgeschlossen. Verbindlicher Arbeitsstand: `ROADMAP.md`, RM-188.
> Diese Datei erläutert den Stand und die nächste sichere Anschlussstelle;
> sie eröffnet keine zweite Arbeitsliste. Prüfungen von Fenstern, Leistung
> und installierten Paketen sind ausdrücklich keine bestandene Abnahme.

## 1. Auftrag, Arbeitsgrenze und Einstieg

Robert hat die vollständige, gründliche Umsetzung der vier CAD-Dokumente
beauftragt, mit besonderem Augenmerk auf Zwillinge und Oberfläche:

- `konzept-bedienung.md`
- `recherche-cad-paritaet-2026-09.md`
- `konzept-vollwertiges-cad-2026-09.md`
- `durchsicht-cad-konzepte-2026-09.md`

Die ursprüngliche reine Planungsphase wurde mehrfach zur Umsetzung freigegeben.
Abgeschlossene Einheiten werden selbstständig logisch getrennt committet und
gepusht. Die letzte Anweisung an die bisherige Hauptsession ist: den laufenden
Punkt P1.4c.1 schließen, alles zur Übernahme aufschreiben und danach keinen
weiteren Punkt beginnen. Die neue Session übernimmt den verbleibenden Auftrag.

Arbeitsbaum: `F:/3D Druck`, Branch `main`. Interpreter:
`F:/3D Druck/.venv/Scripts/python.exe` (CPython 3.14.7, vorhandenes OCP 8).
Zuerst `AGENTS.md`, `CLAUDE.md`, die jeweiligen Bereichskarten und passenden
`.claude/rules/` lesen. Bauplan vor Konzept; Konzeptstatus kann veraltet sein.
Entscheidend sind aktueller Code, RM-188 und die Belege des jeweiligen Standes.

**Grenzen des gemeinsamen Baums:**

- `website/` bleibt unangetastet. Die parallele Veröffentlichung 0.4.4 lief
  vom Tag-Commit; Produktänderungen auf `main` waren ausdrücklich freigegeben.
  Die zeitweilige Website-Zuständigkeit wurde dieser Session nicht aufgehoben.
- Keine Worktrees, Resets, Reverts, erzwungenen Pushes oder Massen-Stagings.
  Eigene Pfade ausdrücklich nennen; bei paralleler Arbeit privaten Git-Index
  benutzen und Hauptindex ohne Arbeitsbaumänderung synchronisieren.
- P2.5 gehört derzeit einer anderen Session. Ihr Ordner ist
  `konzepte/nachweise-cad-p2-5/`; Dateien und etwaige Commits nicht übernehmen,
  überschreiben oder als eigene erledigte Integration ausgeben.
  Während des abschließenden Tors kam außerdem ein fremder P2.5-Nachtrag in
  `.claude/memory/voraussetzung-im-namen-statt-hergestellt.md` hinzu. Auch
  dieser gehört nicht zum eigenen Commitumfang und bleibt erhalten.
- **Fensterdateien und Leistungsprüfungen ausschließlich beim Release.** Das
  gilt dauerhaft, auch für betroffene Teilmengen und Offscreen-Aufrufe. Die
  Regel ist in AGENTS, CLAUDE, Prüfskill, Werkzeugen und Hook verankert.
- Kein Release beauftragt: kein Versionswechsel, Paketbau, Bilder-/Handbuchlauf,
  Upload oder Lizenzmanifest-Neubau. Eine notwendige Projektformatmigration
  ist hiervon unabhängig und erhält ihren eigenen Nachweis.

Zum Einstieg `git status --short`, `git diff HEAD`, `git log` und die Beziehung
zu `origin/main` prüfen. `tools/session_board.py`, das ein älterer gemeinsamer
Prüfskill erwähnt, existiert hier nicht; nicht als Arbeitsvoraussetzung behandeln.

## 2. Abschluss dieser Einheit

Ausgangscommit: `859b75e0ee0d081c8339313757666ac674d845b1`.
Produktcommit: **`875c403341bdf89544723f4b75cfe5d90ee5e588`**. Genau 15 eigene Produkt-/Test-/Katalogpfade;
die Übergabe samt ROADMAP- und Indexverweis folgt als getrennter Dokucommit.

Gemeinsames Entwicklungstor am eingefrorenen Stand von **981 relevanten
Dateien**: **13.025 bestanden, 26 übersprungen, 527.18 s**;
Suite und übergeordneter Prozess Exit **0**, Ruff/Format/mypy jeweils **0**.
Ruff prüfte den ganzen Baum; Format meldete 1138 Dateien, mypy 303 Quelldateien.
Protokolle, vier Ausgänge, Snapshot, vollständiger eigener Diff und private
Commitpfade: `C:/Users/rober/AppData/Local/Temp/solidon-cad-native-faces-final-66ffb8dac3bd4ad6ab40a9479030ab33/`.

Gezielte Nachweise: 41 neue Kernelfälle und 13 neue Verbraucherfälle grün;
447 Verbraucherregressionen sowie sieben bestehende Rundungsfälle jeweils
Exit 0. Der zusätzliche 639er-Kernlauf war ebenfalls grün, importierte aber
vor dem letzten Endkopie-Abbruchfix. Dessen Endstand belegen der anschließende
41er-Lauf und das obige vollständige Entwicklungstor. Kernelprotokolle:
`C:/Users/rober/AppData/Local/Temp/solidon-p14c-face-kernel-green-1789905229636/`;
Verbraucherprotokolle:
`C:/Users/rober/AppData/Local/Temp/solidon-p14c-consumer-green-684fa2a707524b2bb2fc42a92a054a77/`.

Eine zusätzliche Gegenprobe war vor dem Endkopie-Fix 1 rot/3 grün; sie bleibt
als `result-copy-red.txt` erhalten. Im Verbraucher-Testentwurf wurde nur die
erwartete Fehlerklasse für leere Auswahl von GeometryError zu der gemeinsamen
ValidationError präzisiert; Ablehnung, Handlungsvorschläge und unveränderte
Originalbytes bleiben geprüft. Ein zwischenzeitlicher mypy-Typbefund und eine
zu lange Testdocstring wurden vor dem finalen Tor korrigiert.

**Nicht ausgeführt:** Fensterdateien, Leistungsprüfungen, installierte Pakete,
neuer Releasebau und Veröffentlichung. `test_calibration.py` wurde vom
betroffenen Runner vollständig als Fensterdatei zurückgestellt. Der reine
Katalogeinsammler meldete 5917 Quellen, in allen fünf Sprachen null offene
Übersetzungen. Der unabhängige lesende Review fand keinen konkreten Blocker.


**P1.4c.1 verbindet die tatsächliche aktuelle Vollflächenauswahl:**

- `Solid.checked_face_indices()` prüft eine nichtleere Auswahl ganzer aktueller
  nativer Flächen. Boolesche, nichtganzzahlige und ungültige Indizes werden
  abgewiesen; gültige werden eindeutig sortiert. Der Helfer verändert weder
  Eingabe noch deren Tessellationscache.
- `profiles.push_faces(..., selected_faces=...)` arbeitet an genau diesen
  Flächen und mit deren tatsächlichen Normalen. Eine veraltete Mitte oder
  Suchrichtung darf keine andere Stufe wählen.
- `edit.unround(..., selected_faces=...)` entfernt genau eine vollständige
  aktuelle Zylinderfläche mit dem bisherigen Radius. Leere, mehrteilige oder
  unpassende Auswahlen lösen keine Ersatzsuche aus.
- Beide Wege verwenden die vorhandene private `replace(solid)`-Kopie und
  ihre echte `_copied_faces`-Abbildung. Keine zweite Kopierbibliothek, keine
  Annahme gleicher Besuchsreihenfolge.
- `geom/face_ops._on_a_solid` und der Entfernen-Zweig von
  `geom/prepare_ops._exact_fillet` lesen das Merkmal am aktuellen Eingangsobjekt
  und binden dessen vollständige Originaldreiecke mit
  `complete_faces_of_triangles()` an native Flächen.
- `selected_faces=None` erhält den älteren unbenannten Suchmodus. Explizit
  leer oder ungültig ist ein Fehler. `reround` bleibt unverändert und ist
  ausdrücklich noch nicht als sichere native Neuwahl abgeschlossen.
- `push_face` und `remove_feature`: `cache_version` jeweils 3→4. Keine neue
  Abhängigkeit, kein neuer Projektdatenträger; Projektformat bleibt 27,
  allgemeines Cacheformat 20. Zwei neue Texte in allen fünf Katalogen.

**Eigene Produktpfade dieser Einheit:**

```
app/core/brep/{kernel,profiles,edit}.py
app/core/brep/CLAUDE.md
app/core/geom/{face_ops,prepare_ops}.py
app/core/geom/CLAUDE.md
app/i18n/locales/{en,es,fr,it,pt}.json
tests/test_solid_ownership.py
tests/test_prepare.py
tests/test_mesh_faces.py
```

Die Gegenprobe vor der Korrektur ergab 39 neue Kernel-Fälle mit fehlender API
und 11 fehlgeschlagene von 13 Verbraucherfällen. Zwei gültige Entfernenfälle
bestanden schon vorher. Veraltete Mittelpunkte entfernten die jeweils falsche
Rundung; die gerichtete Volumendifferenz betrug 2,146018366 mm³. Der Versatz
ließ die gewählte niedrige Stufe bei 10 statt 15 mm. Alle acht ungültigen
Verbraucherauswahlen lieferten bisher Geometrie statt einer Ablehnung.

Kernel-Rotbeleg:
`C:/Users/rober/AppData/Local/Temp/solidon-p14c-face-kernel-red-1789904734472/`.
Verbraucher-Rotbeleg:
`C:/Users/rober/AppData/Local/Temp/solidon-p14c-consumer-red-ef960ac523b14a8cafa2382bb82c33d4/`.
Diese Läufe bleiben rot und werden durch die späteren grünen Läufe nicht
rückwirkend umgedeutet. Die Fehlerfälle prüfen echte Körper, gerichtete
Differenzen und Materialpunkte; gleiche Volumina allein würden die falsche
Stufe nicht erkennen. Numerisch gültige Indizes allein beweisen keinen
Eigentümer: Der Beleg entsteht am aktuellen SceneObject und dessen Trägern.

## 3. Bereits vorhandener CAD-Stand

Die folgenden Angaben sind ein Übergabeauszug; die vollständigen Belege und
verbleibenden Paketgrenzen stehen unter RM-188. „Implementiert“ heißt hier
Entwicklungsumfang, nicht bestandene Fenster-, Leistungs- oder Paketabnahme.

| Paket | Stand und maßgebliche Commits |
|---|---|
| P0.0 | Gemeinsame Merkmalsnachführung bei Spiegelung, Skalierung und Mustern; `cfc5e303`. Die damaligen zwei nativen Kundenwege liefen vor der neuen Release-Regel. |
| P0.1 / P0.2 | Bediengrundlagen und gemeinsame Schutzprüfung von Auftrag, Dokumentstand, Auswahl und gezeichneter Vorschau; `064e3095`, `77223ccb`. Fensterabnahme offen. |
| P0.3 | Erster gemeinsamer Bohrungsmaßeditor für beide Zwillinge, gebundener Entwurf und historische Originalmaße; `852de666`, `1fc131a6`. Andere Felder, Griffe, Gruppen und die vollständige Merkmalsbedienung offen. |
| P0.4 | Belegte Außen-/Innenkanten, Mitten und Langlochachsen bei Platzierungsmaßen; `102d4bf7`. Vollständige Achsen-/Symmetrieparität mit P1.5, dauerhafte Bezüge mit P3.2 offen. |
| P0.5 / P0.6 | Werkzeugauswahl in Konzept §13.8.1 entschieden. Vorhandene Bibliotheken/Cython zuerst; keine zusätzliche Infrastruktur ohne belegten Bedarf. Fachliche Sonden bleiben Aufgaben der jeweiligen Pakete. |
| P0.7 | Lokaler Absturzschutz, Klartextquittung am Handlungsort und gemeinsames Aufsetzen importierter Gruppen; `7aaa993d`, `b9b96a91`, `47023b53`. Neue Fensterfälle vorbereitet, Ausführung offen. |
| P1.1 | Belegte Konturmaße und echte Grenzen für Zylinder/Langlöcher; `db7d1a5c`. |
| P1.2 | Kegel-/Kugel-/Torusfits aus belegten Punkten, Originalauswahl, Herkunft und Lebenslauf; `851f913a`. |
| P1.3 | Unabhängige Körperproben radialer und bündiger Passungen; `eeadc09b`, `912789f7`. |
| P1.6 | Belegte Formabweichung ganzer Originaldreiecke, unbekannte Bereiche, Zeugen und gemeinsamer Kartenweg; `5d451fe7`. |
| P1.4a / P1.4b | Räumliche Vorauswahl und Abbruch `d483e1477`; vollständige konkurrierende Gruppenentscheidungen und Folgecache `fe17cd3bc`. P1.4 bleibt insgesamt offen. |
| P2.1 | Exakte affine Transformation und ursprüngliche Handlungsmatrix; `77223ccb`. Die später fortgeschriebene Matrix erfasst 133 Ops in 229 Prüfungen. Installierte Plattformen offen. |
| P2.2 | Filamente bleiben am exakten Körper und an nativen Teilungsgrenzen; `3df89b8e`. |
| P2.3 | Analytische Ebenen/Zylinder aus NURBS `3bdaa788`; Innenräume `a85cc872`; native/rationale Ringe `93979914`; Kugeln `851f913a`. Vollständige Träger-/Teilflächen-/Semantikparität offen. |
| P2.5 | Externe Nachweissession, laut Robert fast fertig. Abschlussbericht und Produktintegration getrennt behandeln; siehe Abschnitt 6. |
| P2.7 | Nachweise `69efc1cdf`, Registeranschluss `469ef4e92`; Produktionsintegration offen. |

Noch offen: P1.5; P2.4/P2.6/P2.8; P3.1–P3.5; P4.0–P4.3; P6.1–P6.7;
P7.1–P7.4; P5.1–P5.3 und die oben benannten Restanschlüsse. Ihre vollständigen
Unterfälle stehen in Konzept §13.2 und RM-188; keine davon entfallen durch
P1.4c.1. Die im Konzept vorgeschlagenen Werkzeuge sind keine automatisch
genehmigten neuen Abhängigkeiten. Lizenz- und Reproduktionsregeln gelten weiter.

## 4. P1.4b verstehen, bevor P1.4c fortgesetzt wird

`matching.py` hält konkurrierende Zielansprüche und gleichwertige globale
Zuordnungen gemeinsam offen. Deterministische Sortierung beweist keine
Eindeutigkeit. Die konservative U−L-Klammer, SCC-Zyklen und freie Endpfade
erhalten auch den dichten/symmetrischen Fall. `require_injective()` schützt
die Übernahme von Namen und Erzeugerherkunft.

`perceive/match_records.py` ist der gemeinsame reine Vertragsprüfer;
`match_decisions.py` berechnet Konfliktgruppen, Fingerabdrücke und vollständige
Wiedererkennung. Keine zweite Gruppen-/Fingerabdrucklogik hinzufügen.

`Operation.matches` speichert vollständige körperbezogene Gruppen samt
Kandidaten, allen Ansprüchen und Entscheidungen. Eine Entscheidung ist ein
Kandidatenindex oder ausdrückliches `not_carried`. Der Schlüssel enthält
ObjectId und sortierte alte IDs. Ein Kandidat darf nur einmal übernommen
werden; auch nicht gewählte feste Ziele gehören zur Prüfung. Wiederverwendung
verlangt den ganzen Kandidatensatz und dieselben Ansprüche. Ungültige Rivalen
werden nicht einfach ignoriert.

Im Fingerabdruck ist nur die Position normalisiert. Das historisch
`diameter` genannte Feld bleibt das rohe siebte Merkmalsmaß (`vector[6]`),
bei Ebenen also eine Fläche. Es jetzt global als normierten Durchmesser
umzudeuten würde gespeicherte Antworten und Wiedererkennung verändern.

**Format 27:** Alte nichtleere Antworten sind unverändert unter `legacy`
eingehängt, einschließlich historischer Maßfassungen. Alte Projekte werden
nicht mit erfundenen Antworten ergänzt. History und Serializer kopieren die
tiefen Gruppen; Undo/Redo erhalten den Antwortsatz der jeweiligen Maßfassung.
Ausgabeverlust entfernt die ganze körpergebundene Gruppe, ohne sie umzubinden.

`evaluate` veröffentlicht Antworten, Zuordnung und Befunde erst vollständig
über alle Gruppen und Ausgaben. Gespeicherte gültige Entscheidungen werden
auch ohne aktuell nachfolgende Referenz wiederhergestellt, damit Undo einer
Folgeoperation keine bereits bestätigte Identität verliert.

**Cacheformat 20:** Der Rohproduzent bleibt über `operation_hash` cachebar;
`matches` ist dort absichtlich nicht Teil des Schlüssels. Dagegen enthält der
nachfolgende `object_hash(..., features=...)` alle tatsächlich gebundenen
aktuellen Merkmale über den gemeinsamen Featurecodec. Eine geänderte Wahl
entwertet die Folgeoperation auch bei warmem Produzentencache. Nicht wieder
auf reine Geometrie- oder Namenshashes verkürzen.

**Gemeinsamer Frageweg:** `Session.announce_question` → fadenlokaler Kontext →
`AskRequest` → `MainWindow._on_ask` → `AskDialog`. Die Vorschau enthält echte
Ausgabegeometrie, verändert keinen Dokumentstand und wird vor der Antwort
wiederhergestellt. `sceneApplied` sperrt Annahme bis zur aufgebauten Ansicht.
Generation und Workerzugehörigkeit verhindern alte Antworten nach Projekt-
oder Auftragswechsel; `questionInvalidated` löst wartende Fragen beim Abbruch.
Dieser UI-Anschluss und seine 24 neuen parametrisierten Fensterfälle sind
vorbereitet/statisch geprüft, **nicht als Fensterlauf abgenommen**.

P1.4b-Endstand `859b75e0e` (Produkt `fe17cd3bc`, getrennte Manifestprüfung
`930ccbbc5`) wurde gepusht. Gemeinsames Entwicklungstor: 12.971 bestanden,
26 übersprungen, 520,31 s, Suite/Ruff/Format/mypy jeweils Exit 0;
981 relevante Dateien eingefroren. ROADMAP-Nachlauf 152 bestanden, Exit 0.
Belege: `C:/Users/rober/AppData/Local/Temp/solidon-cad-competition-final-789c0cf656654dc395e84d2ce8513a4d/`.

Die Manifestkorrektur prüft den echten Installerprüfer an isolierten aktuellen
Prüfsummen. Bestehende Releaseartefakte wurden nicht geändert. Die echte
Paketsperre gegen ein veraltetes Manifest bleibt erhalten; das Manifest wird
vor dem Releasebau neu erzeugt, nicht nach jeder Entwicklungsänderung.

## 5. Konkreter nächster Anschluss: Rest von P1.4c

Diese Reihenfolge ist aus drei unabhängigen Reviews präzisiert; sie ist ein
Umsetzungsvorschlag für den offenen RM-188-Anschluss, **kein bereits bestehender
Vertrag**. Vor jedem Schritt aktuelle Signaturen und Verbraucher prüfen.

### 5.1 Native Referenzen nach tatsächlichen Übergängen absichern

Heute sperrt `evaluate._with_features` native referenzierte Mehrdeutigkeit
nur unter seinen bisherigen Grenzen. Verlorene, ungeprüfte oder gleichlautend
neu vergebene Namen sind damit nicht allgemein abgesichert. `touches_features`
ist kein Identitätserhaltungsflag: `push_face` und `draft_faces` setzen es nicht,
obwohl sie native Geometrie neu bauen. `orphans._resolves` prüft bisher nur
Namensexistenz und kann ein neues fremdes `face_1` irrtümlich für den alten
Bezug halten. Beide Grenzen gemeinsam bearbeiten.

Gewollte große Bohrungsänderungen müssen dabei funktionieren:
`prepare_ops._preserved_exact_features` kennt über `_expected_bore`,
`_bore_match_id` und `_resized_bore_floor` die tatsächliche Änderungsabsicht.
Sie darf im allgemeinen Auswerter weder aus dem Op-Namen noch aus gleicher
ID, Provenienz oder `created_by` neu erraten werden.

Geprüfter Vorschlag: ein kleines unveränderliches Ergebnispaar
`FeatureContinuation(source: FeatureRef, target: FeatureId)`, pro Ausgabe
ordinal zugeordnet, auf `OpResult` und vollständig im `CachedResult`/Diskcodec
transportieren. Nur tatsächlich freigegebene eindeutige Produzentenpaare
ausstellen. Quellenkörper, Zielausgabe, Existenz und Injektivität validieren.
Wie `transform` ist dies abgeleitete Rechenauskunft, keine Projektpersistenz.
Bei Einführung des tatsächlichen neuen Cachefelds Cacheformat erhöhen;
alte Rohcaches dürfen den Beleg nicht verlieren oder nacherfinden.

Benötigte alte Referenzen nach jedem tatsächlichen nativen Übergang prüfen,
auch nach Cachetreffern. Durchreich-/Transformationsbelege nur verwenden,
wenn die tatsächlichen Träger und ihre vollständige Abbildung belegt sind.
`carried_face_slots` beweist allein Filamente, keine Merkmalsidentität.
Budgetüberschreitung oder ausgelassene Zuordnung bedeutet unbekannt, nicht gültig.

Referenzlebensdauer berücksichtigen: Die über das ganze Dokument gesammelten
`referenced_features` enthalten auch frühere Verbraucher. Eine später bewusst
entfernte Fläche darf nicht allein wegen ihrer früheren Verwendung blockieren.
Den zeitlichen Vertrag von `orphans.pending_references` und die tatsächlich
noch folgenden Verbraucher/aktiven Endpassungen verwenden.

Ungesicherte körperqualifizierte Bezüge atomar vor Ausgabeübernahme anhalten.
Den Sperrzustand strukturiert an Orphans weitergeben; Namensexistenz und erneute
Auswahl gegen die alte Szene dürfen ihn nicht heilen. Eine erste sichere
Sperrstufe ist unabhängig vom späteren Neuwahldialog möglich und soll ihre
noch fehlende Reparaturmöglichkeit ehrlich benennen.

Dateieinstieg: `core/types.py`, `scene/{evaluate,orphans,cache}.py`, der
vorhandene Produzentenpfad in `geom/prepare_ops.py`, minimale Weitergabe in
`ui/session.py`; passende bestehende Tests und Bereichskarten.

### 5.2 Native Merkmalsgruppen wieder wählen und speichern

P1.4b-Atomizität, Gruppenvalidierung, tatsächliche Vorschau und gemeinsame
Fingerabdrücke erweitern. Native Gruppen benötigen eine eigene Domäne und
einen engen Erzeugerscope. Netzantworten dürfen native Konkurrenz weiterhin
nicht freigeben. Vollständige aktuelle Auswahl und eindeutig wiedererkannte
Kandidaten bleiben zusätzliche Bedingungen.

Für native Ausgaben ist als Scope der rohe Erzeugerschlüssel plus Ausgabeindex
vorgesehen, zusammen mit Körper und Anspruchssatz. Nicht den erst nach der
Aliaswahl gebildeten `object_hash` einsetzen: Dieser enthält die Entscheidung
selbst. Bei eingangsgebundenen Kanten muss auch der History-Besitzfilter nach
Domäne unterscheiden; sein jetziger Filter ausschließlich über `outputs`
genügt dann nicht. Scope allein beweist keine gleiche Topologie oder Trimmung.

Hier ist **Format 28 mit eigener Migration 27→28** vorgesehen. Alte Antworten
unverändert erhalten, keine neuen Zustimmungen/Scopes erfinden. Den vorhandenen
tiefen Serializer und die Maßfassungsbindung der Historie wiederverwenden.
Die endgültige Feldstruktur vor Umsetzung festlegen. Projektformatänderung
allein verlangt keine sachlich unbegründete neue Cacheformatnummer.

Erst sichere tatsächliche Verbraucher zur Neuwahl freigeben. P1.4c.1 erledigt
Versatz und Entfernen; ein Radiuswechsel ist deshalb noch nicht automatisch
sicher. Auswahlgültigkeit, verworfene/reservierte Namen, Körperaufteilung,
Skizzen-/Passungsbezüge und alle Ausgaben gehören zum gemeinsamen Anschluss.

### 5.3 Kantenbindung und Radiuswechsel getrennt abschließen

Kanten werden innerhalb der Operation verbraucht, bevor der interne
nachgelagerte `FeatureQuestionContext` für Ausgaben existiert. Nötig ist eine
gemeinsame Vorbindung registrierter `edges`-Eingänge **vor `cache.get`**.
Verschiedene bestätigte aktuelle Kanten müssen den Verbraucherschlüssel
unterscheiden; der P1.4b-Ausgabehash löst diese Eingangsgrenze nicht.

Eindeutig neu gewählte dauerhafte Schlüssel können den bestehenden
`OpResult.answered`-Parameterweg verwenden. Echte Schlüsselkollisionen brauchen
getrennte Fragetoken und körper-/feldgebundene Antworten. Keinen bestätigten
kollidierenden Schlüssel danach nochmals im Kernel auflösen. `Operation`
hat kein bereits vorhandenes allgemeines `answers`-Feld.

Äußeren Fragekanal für Feature- und Kantenziele typisieren; der interne
Ausgabeadapter kann schmal bleiben. Vorhandene Linienabtastung und Beschriftung
aus `EdgeInfo`/`MeshEdge`, `edge_points`, `edge_label` wiederverwenden. Native
Handles und flüchtige Indizes gehören weder in die UI-Nachricht noch in die
Projektdatei. `_edge_names`, `_edge_info` und `select_edge(key)` verschlucken
Kollisionen; Fragekandidaten benötigen die eigenen Token in derselben
Kandidatenverwaltung. Kein paralleler Rückfragedialog.

`reround` hat zwei noch unsichere Übergänge: Suche der Rundungsfläche über
Mitte/Radius, danach Auswahl einer scharfen Kante nach Abstand zur alten Mitte.
Die aktuelle Filamenthistorie und verfügbare `Modified`/`Generated`-Methoden
beweisen nicht die Zuordnung entfernte Rundung → neue scharfe Kante.
Zuerst reale Gegenprobe an mehreren benachbarten Rundungen: gewählte Fläche,
echte Randnachbarn, Builderhistorie, gemeinsame Ergebnisränder, unveränderte
Quellenbytes. Nur einen vollständig eindeutigen Beleg verwenden; andernfalls
an der tatsächlichen scharfen Zwischenform ausdrücklich neu wählen.
Der erste `radial_rounding`-Zweig benötigt ebenfalls die direkte Auswahl.
Eine Kantenkopierabbildung muss die vorhandene native Kopierprimitive erweitern,
nicht unabhängig von ihr entstehen.

Gemeinsame Abnahme: kalt/warm/neue Plattencacheinstanz, Save/load, Undo/Redo,
Maß-/Kern-/Scopewechsel, mehrere Ein-/Ausgabekörper, Gruppenabbruch und der
gemeinsame Agentenweg. Bei Verlust kein Teiloutput und kein halber Antwortsatz.
**`FEATURE_LIMIT_COUNT` bleibt 1000**, bis der gesonderte Release-Leistungsnachweis
eine Änderung trägt. Direkte 1056-Flächen-Testprojekte sind keine Freigabe
einer erhöhten Produktionsgrenze.

### 5.4 Danach P1.5

Vorliegende Anschlussbefunde: Unterschiede zwischen kleinem echtem Netzmerkmal
(`MIN_FACE_AREA=4`) und nativer Grenze; Teilträger dürfen nicht von zufälliger
Dreiecksunterteilung abhängen; Senkungen an Langlöchern und zusammengesetzte
Rundmerkmale; Vollumlauf-/Teilbogenklassifikation; gemeinsame Beziehungen bis
in Steckbrief, Agent und Viewport. Keine reine Umbenennung unabhängiger
Erkenner. Der gemeinsame Vertrag muss Träger, Innen/Außen, Nachbarschaft,
Teilabdeckung, Maßquelle und Unsicherheit bewahren.

## 6. Externe P2.5- und P2.7-Arbeit

**P2.5:** Robert meldet „fast fertig“. Die beauftragte externe Zuständigkeit
umfasst ausschließlich den Nachweisordner. Auftrag: Steigung importierter
STEP-/B-Spline-Gewinde geometrisch erkennen, ohne Erzeugerwissen; Innen/Außen,
Händigkeit, Achse, Gangzahl, Teilgewinde, unvollständige Flanken, gedrehte und
neu parametrisierte Flächen sowie Gegenformen prüfen. Vorhandene OCCT-/NumPy-
Werkzeuge zuerst; keine neue Produktabhängigkeit. Quellcode, Tests, ROADMAP,
Regeln und Website waren nicht Teil dieses externen Arbeitsauftrags.

Letzter gelesener Übergabesnapshot: Der externe README-Bericht liegt ohne sichtbaren Vorlagenplatzhalter vor. Für diesen Ordner ist noch kein Git-Commit vorhanden. Der Ordner enthält weiterhin lokale Änderungen bzw. untracked Dateien. Das ist eine Bestandsaufnahme, keine technische Abnahme seiner Prototypen.

Die Inventur seines laufenden Berichts nennt zusätzlich stillen Gangverlust bei halbzahligen Längen (Überschneidung mit P2.7), falsche tessellationsabhängige Gangtiefe am Netz, Steigungsquellen/Passung und den Merkmals-/Nenndurchmesservertrag. Innen-Nenn-Ø und beide gemessenen Radien getrennt halten. Gemeinsame Fehler gemeinsam beheben; Gegenstück und Normgrößenvorschlag bleiben P2.6. Zum gelesenen Zwischenstand waren fremdes Hersteller-STEP, mindestens drei Gänge, links/mehrgängig innen sowie konische und kantenlos tangential modellierte Gewinde noch offen. Diese Grenzen am finalen Bericht erneut prüfen.


Zur Übernahme Bericht, tatsächliche Prozessausgänge und Commit prüfen. Eine
Machbarkeitssonde wird nicht ungeprüft in `app/` kopiert und erledigt nicht
automatisch P2.5/P2.6. Parameter einer B-Spline-Kurve sind keine physische
Gewindesteigung. Die nächste fachliche Integration muss den gemeinsamen
Merkmalsvertrag, Originalträger, Cache und Verbraucher erreichen.

**P2.7:** `konzepte/nachweise-cad-p2-7/README.md` und Bericht sind bereits
committet. Elf Sonden, 568 Zusicherungen, alle Prozesse Exit 0 am Stand
`1cf405496`; es konvertieren alle 35 `insert_`-Pfade und zehn `create_`-Pfade.
Die ursprüngliche Zahl 31 war eine unvollständige Stichprobe, kein Endumfang.
Jede Bausteinform ist auf dem vorhandenen exakten Kern nachgestellt,
Konturversatz und Helix-Gang sind prototypisch belegt. Ziel bleibt eine
gemeinsame Formbeschreibung mit zwei Auswertern, keine 35 Funktionskopien.

Vier Integrationsbefunde nicht verlieren:

1. Kern + Gang ohne Fuzzy-Toleranz kann den Gang still verlieren.
2. Fuzzy vereint den Senkkopf, doch STEP kommt ungültig/als Compound zurück.
3. Fuzzy-Wiederholungen auf denselben Eingaben rissen nativ mit Exit 139 ab
   (3/3); private Kopien verhinderten diesen beobachteten Abriss.
4. Nach exaktem Schnitt müssen Trägermerkmale fortgeführt werden, bloße
   Neuerkennung erhält sie nicht. Neue Namen führten in der Sonde zum falschen
   zweiten Ziel. Ebenso ist bloßes Kopieren von `source.features` kein
   allgemeingültiger Beleg für die aktuellen Träger; P1.4c/P1.5 schließen
   diesen Vertrag.

Produktionsanschluss, gemeinsame Parameter-/Maßbeschreibung, Versionierung,
Attribute, Passungen, Parameterbereiche und integrierter Kundenweg bleiben
offen. Vor P2.8 muss die gesamte P2-Handlungsmatrix grün sein; Nachweise zu
P2.5/P2.7 rechtfertigen kein vorzeitiges Entfernen der Kernwahl-Haken.

## 7. Prüfablauf, Belege und lokale Werkbank

Geometrie zuerst mit unabhängigem Soll rot nachstellen, dann korrigieren;
betroffene Kernfälle je Schritt, gemeinsames Entwicklungstor vor Commit.
Nicht einfach direkte Pytest-Aufrufe aus alten Notizen kopieren, wenn sie
Fensterdateien umgehen würden. Die aktuellen Werkzeuge klassifizieren ganze
Dateien über Fixturegraph und `windowed`-Marker.

```powershell
& .venv/Scripts/python.exe tools/affected_tests.py tests/test_solid_ownership.py tests/test_prepare.py tests/test_mesh_faces.py --run
$cadTestExit = $LASTEXITCODE
& .venv/Scripts/python.exe -m ruff check .
$cadRuffExit = $LASTEXITCODE
& .venv/Scripts/python.exe -m ruff format --check .
$cadFormatExit = $LASTEXITCODE
& .venv/Scripts/python.exe -m mypy
$cadMypyExit = $LASTEXITCODE
$env:SUITE_PYTHON = 'F:/3D Druck/.venv/Scripts/python.exe'
& 'C:/Program Files/Git/bin/bash.exe' '.claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh'
$cadSuiteExit = $LASTEXITCODE
```

Für echte Läufe jeden Aufruf in eine eigene Datei umleiten und den jeweiligen
nativen Exit unmittelbar sichern. Kein `tail`, `Tee` oder abschließendes
`echo` als Erfolgsbeweis. Ein nativer Abriss bleibt auch nach grünen Assertions
ein Fehllauf. Vollständige bereits grüne Nachweise nur bei unverändertem
relevantem Stand wiederverwenden; reine Abschlussdoku benötigt kein zweites
komplettes Geometrietor.

Die bisherige Werkbank liegt lokal, überwiegend **untracked**, unter
`.claude/.state/cad-durchsicht-2026-09-19/`. Sie wurde absichtlich nicht pauschal
eingecheckt. Diese Übergabe enthält die tragenden Entscheidungen auch ohne sie.
Zusätzliche Detailquellen für dieselbe Maschine:

| Lokale Datei | Nutzen und Grenze |
|---|---|
| `p14b-published.json`, `p14b-root-integration.md` | Nachweise und Commit-/Push-Stand von P1.4b. |
| `p14b-contract-review.md`, `p14b-answer-contract.md` | Historische Herleitung der Konkurrenz und des Antwortformats; damalige Zeilennummern/Formatstände nicht als aktuell übernehmen. |
| `p16-extrema-review.md`, `p16-deviation-implementation.md` | Herleitung und numerische Zertifizierung der Formabweichung; tragende Invarianten unten. |
| `p14c-implementation-order.md` | Zusammengeführte Reihenfolge; Abschnitt 1 jetzt abgeschlossen, kein neuer Auftrag. |
| `p14c-native-reference-plan.md` | Ursprünglicher Vorschlag, nur zusammen mit den drei nachfolgenden Korrekturen lesen. |
| `p14c-ui-kernel-review.md` | Tatsächliche Verbraucher, gemeinsamer Frageweg und fehlender Radiusübergang. |
| `p14c-persistence-review.md` | Domänen-/Scopegrenzen, Migration und Kanten-Eingangscache. |
| `p14c-evaluation-boundary.md` | Aliasbeleg, Lebensdauer, Orphans und kleinste sichere Sperrstufe. |
| `p15-entry-plan.md`, `p15-consumer-review.md`, `p15-geometry-review.md` | Bereits gelesene P1.5-Anschlussfragen, noch keine Umsetzung. |
| `prompt-parallel-p2-5.md` | Exakter externe Nachweisauftrag und Eigentumsgrenze. |
| `prepare_native_face_gate.py`, `stage_spatial_scope.py` | Lokale explizite Pfadlisten und privaten Index vorbereiten. Nicht unverändert für neue Pakete verwenden. |
| `current-development-gate.txt`, `next-development-gate.txt` | Zeigen den zuletzt dokumentierten Protokollordner; Dateien/Hashes live prüfen. |

Temp-Verzeichnisse sind lokale Rohbelege und können später fehlen. Die
maßgeblichen Ergebnisse und Grenzen stehen deshalb in dieser Datei und
RM-188; ausführbare Regressionen stehen im Git-Commit. Neue Session muss
keine alten erfolgreichen Tore wiederholen, nur um einen Temp-Ordner zu ersetzen.

### Erhaltenswerte Herleitungen aus den lokalen Reviews

Die globale Konkurrenzprüfung in P1.4b ist notwendig, weil ein strikt
billigstes Zeilen-/Spaltenpaar trotzdem Teil zweier gleichwertiger ganzer
Zuordnungen sein kann. Konkretes Gegenbeispiel als Kostenmatrix:
`[[0, 0.5], [0.5, 1.0]]`; beide Permutationen kosten 1. Eine reine lokale
Rivalengrenze `1.25*c + 0.05` kann dies nicht freigeben. Beim Öffnen eines
bisher festen Besitzers müssen außerdem dessen weitere Ansprüche bis zum
vollständigen Abschluss verfolgt werden. Die U−L-Kostenhülle verkleinert den
Graphen konservativ, beweist aber nicht die Gleichwertigkeit jeder ihrer
Kanten. Diese Unterschiede stehen in den Produktionsregressionen; keine
lokale „Optimierung“ darf daraus wieder automatische Identität machen.

`geom/deviation.py:deviation_bounds` liefert für jedes ausgefüllte
Originaldreieck eine Klammer `L <= max_T Abstand <= U` und einen tatsächlichen
baryzentrischen Zeugen. Gemessen wird zum gespeicherten **unbeschnittenen**
analytischen Träger, nicht zu einem getrimmten B-Rep-Rand. `epsilon_mm` ist
numerisches Rechenziel, keine Materialtoleranz. Der Zeuge bezeichnet die
exakte reelle Kombination der ursprünglichen Float-Ecken; seine Zugehörigkeit
wird rational geprüft. Ein gerundet dargestellter Punkt ersetzt ihn nicht.

Die Arithmetik schließt alle Zwischenschritte gerichtet ein, einschließlich
Wurzeln, Achsrahmen und Kegelwinkeln; eine pauschale ULP-Hülle um das Endergebnis
ist kein Ersatz. Eine gültige globale Lipschitz-Obergrenze bleibt bei
ungeklärter engerer Kandidatenrechnung erhalten. Breite endliche Klammer
heißt `converged=False`, fehlende sichere endliche Grenze heißt unbekannt.

Beim gerichteten Kegel mit `s=sin(alpha)`, `c=cos(alpha)`,
`H=s*z-c*rho`, `t=s*rho+c*z` ist der Oberflächenabstand
`sqrt(H²+min(t,0)²)`; das erhält die richtige Nappe hinter der Spitze.
Beim Ringtorus gilt `R>r>0`, `F=(rho-R)²+z²`,
`d=abs(sqrt(F)-r)`. Kanten, beide Meridianhalbebenen, Mittelkreisschnitte
und Achse decken die möglichen Extrema; nur bewiesene Außenlage darf
Kandidaten entfernen. Horn-/Spindeltori sind damit nicht mitbewiesen.
Exakte Entartung/Koplanarität kommt aus Originalfloats mit `Fraction`.
Der Toruskantenhaushalt gilt für den gesamten Aufruf (256 Intervalle),
nicht neu je Dreieck; nach Verbrauch bleiben die gültigen breiteren Grenzen.
Raster oder SLSQP-Sonden allein beweisen diese Vollständigkeit nicht.

## 8. Starttext für die übernehmende Session

> Übernimm die vollständige weitere CAD-Umsetzung in `F:/3D Druck`.
> Lies zuerst `konzepte/uebergabe-cad-2026-09-20.md`, die aktuellen Regeln und
> RM-188 in ROADMAP. P1.4c.1 ist der abgeschlossene Übergabepunkt; beginne mit
> der belegten nativen Referenzfortführung und dem sicheren Halt aus Abschnitt
> 5.1. Prüfe vorher HEAD, eigenen Diff und die inzwischen extern fertiggestellten
> P2.5-Nachweise. Verwechsle Nachweise von P2.5/P2.7 nicht mit ihrer noch offenen
> Produktintegration. Arbeite bestehende Pfade und Zwillinge vollständig weiter,
> ohne Funktionen oder UI-Wege zu duplizieren. Schließe Einheiten mit betroffenen
> Kernprüfungen, Entwicklungstor, explizitem Commit und Push ab. Fensterdateien
> und Leistung ausschließlich beim Release; `website/` und fremde Arbeit in
> Ruhe lassen. Der Auftrag bleibt bis zum vollständigen CAD-Anschluss bestehen.
