---
description: "Der Kern ohne Qt — die Grenze nach oben, Zahlen in Millimeter, Fehler mit Handlungsvorschlag, Auswertung, Lizenz- und Pfadgrenzen"
paths:
  - "app/core/**/*.py"
---

# Regeln für den Kern

Der Kern ist der Teil, der ohne Fenster funktioniert. Alles hier gilt
zusätzlich zu `AGENTS.md`.

## Grenze nach oben

- **Kein `PySide6`, kein Qt, kein `print`, kein `input`.**
  `tests/test_core_isolation.py` importiert `app.core` ohne installiertes Qt.
- Kommunikation nach außen ausschließlich über den `OpContext`:
  `ctx.progress`, `ctx.ask`, `ctx.cancelled`, `ctx.quality`, `ctx.seed`.
  Keine globalen Objekte, kein Logger, der etwas anzeigt, kein Dialog.
- **Fragen statt raten** (Regel 21): Mehrdeutigkeit geht über `ctx.ask`.
  Der Kern entscheidet nicht für den Nutzer.
- **Eine ohne Wahl geschlossene Frage sagt der Frage ab, nicht der
  Rechnung.** Die Sitzung meldet sie als `errors.QuestionDeclined`
  (Unterklasse von `OperationCancelled`); in der Auswertung wird daraus über
  `_WatchedAsk` ein Befund am fragenden Schritt mit Weg zurück, die
  Verweisprüfung lässt den Verweis stehen. Wer eine neue Frage außerhalb
  eines Schritts stellt, entscheidet dasselbe ausdrücklich — ein stiller
  Abbruch ohne Satz ist keine Antwort (RM-024).
  Die optionale Vollerkennung großer Importe (§21.1) hat einen ausdrücklichen
  Fortsetzungsweg: `QuestionDeclined` lädt mit begrenzter Erkennung weiter.
  Ein echter `OperationCancelled` beendet weiterhin den laufenden Auftrag.
  **Eine optionale Frage ist kein Hindernis:** Wer niemanden fragen kann
  (`UserError` aus `ask` — die Vorgabe ohne Dialog, die Kommandozeile ohne
  Eingabe), lädt wie nach einer Absage und hält nichts fest. Wer eine weitere
  optionale Frage baut, gibt ihr denselben Rückweg; sonst hält ein Import an,
  der vorher durchlief.
  **Die Wahl gilt dem Körper, nicht dem Netz** (`evaluate._BodyRecognition`):
  Jeder Folgeschritt eines bestätigten Körpers erkennt ohne neue Frage
  vollständig nach; nach einer Absage erkennt er oberhalb der automatischen
  Grenze örtlich nach, darunter wieder von selbst. Ist die Vollerkennung am
  Arbeitsspeicher gescheitert, versucht es kein Folgeschritt mit mindestens so
  vielen Dreiecken noch einmal, und dasselbe Netz nicht im selben Prozess
  (`local.ran_out_of_memory`): Ein Speicherfehler kostet die Erkennung, nie
  den Schritt. **Außer jemand hat neu entschieden:** Nach einer Antwort in
  diesem Lauf gilt der Merker nicht, und *Alle Merkmale erkennen*,
  `recognize` wie ein Projektwechsel leeren ihn
  (`local.forget_out_of_memory`). Eine fehlende Wahl allein ist keine
  Entscheidung: Kam die Absage nicht am Ladeschritt an, weil der Lauf
  abbrach, bleibt es beim Merker. Die Absage aus einem Speicherfehler trägt
  ihren Grund (`out_of_memory` im Eintrag), geht wie eine Antwort sofort an
  den Aufrufer, und der Befund bleibt in jedem Lauf eine Warnung.
  **Zurückgenommen wird nur, was am Ladeschritt steht**
  (`history.recognition_reopenable`): Satz im Befund, Knopf im Bericht und
  `History.reopen_recognition` fragen dasselbe — ein Körper, der erst nach
  dem Laden über die Grenze wuchs, hat keine Wahl und bekommt keinen Rückweg.
  Mehrere große Körper eines Imports bekommen **eine** Frage mit der Summe;
  die Antwort steht sofort fest (`on_recognition_answer`), nicht erst mit dem
  Ergebnis, und gemeldet wird auch eine gespeicherte Zustimmung, sobald sie
  die lange Erkennung startet — unmittelbar vor `detect`, nach dem Übertrag
  auf ein bewegtes Netz und nur ohne Treffer im Merker, nicht bei jeder
  Auswertung.

## Zahlen

- Millimeter und `float` (doppelte Genauigkeit). Gerundet wird in der Anzeige,
  nie im Kern.
- Kein `==` auf Fließkomma. Toleranzen kommen aus dem Materialprofil
  (`auto:<material>`), nicht als Zahl in den Code.
- Jede randomisierte Prozedur nimmt `ctx.seed` und trägt `deterministic=False`.
  Ohne beides ist sie falsch, auch wenn sie funktioniert.

## Dieselbe Datei, dasselbe Teil — auf jeder Maschine (RM-187)

Was zu Geometrie wird oder zwischen Lagen, Flächen oder Kandidaten
entscheidet, rechnet **ohne** Wege, deren letzte Stelle an der Plattform
hängt:

- kein BLAS: `np.dot`, `@`, `inner`, `vdot`, `tensordot`, `np.linalg.norm`
  ohne Achse; `np.einsum` nicht (FMA auf ARM);
- kein LAPACK: `svd`, `eigh`, `eig`, `lstsq`, `solve`, `inv`, `det` — dort
  auch das Vorzeichen eines Eigen- oder Singulärvektors nicht;
- keine Winkel- und Exponentialfunktion aus NumPy oder `math`;
- kein `x ** 2` (Pythons Potenz ruft `pow` der Plattform) — `x * x`;
- Zufall nur aus den Rohbits des Generators (`Generator.random`,
  `integers`), nie `normal` oder andere Verteilungen über `exp`/`log`.

Die Ersatzwerkzeuge stehen in `app/core/geom/CLAUDE.md` (Tabelle
„Plattformgleich gerechnet"). Wer einen neuen Weg baut, der am Ende
Geometrie ergibt, nimmt ihn in `tests/test_platform_identity.py` (`_WAYS`)
auf: Der Test verrauscht jede dieser Rechnungen um ein ULP und tauscht den
BLAS-Kern, und der Fingerabdruck darf sich nicht rühren. Anzeige, Messung
für den Bericht und Vorauswahlen, deren Ergebnis danach exakt nachgeprüft
wird, dürfen schnell rechnen — der Kommentar sagt dann, warum.

## Eine Merkmalsnummer kommt aus dem Körper, nie aus der Reihenfolge

Die Nummer eines erkannten Merkmals ist eine Provenienz-ID (§21.2): Passungen
und Operationen hängen an ihr. Zwei Regeln halten sie fest:

- **Jede Nummerierung geht über `perceive.features.numbering_order`.** Keine
  eigene Sortierung nach der gerundeten Mitte: Bei konzentrischen Rundungen
  ist sie unentschieden, und die stabile Sortierung erbt dann die Folge der
  Flecken (RM-211: zwei Rundungen eines gebogenen Winkels tauschten ihre
  Namen, sobald die Dreiecke rückwärts im Netz standen). Die Regel fragt
  nach der Mitte Maß, Länge, Lage und Ecken, und wer allein steht, steht wie
  nach der gerundeten Mitte.
- **Was eine Einpassung summiert, kommt in der Ordnung des Körpers**
  (`perceive.features.in_body_order`): Flecken, Stücke und
  Zusammenlegungen. Die Summenfolge verschiebt die letzte Stelle, und an der
  Kippe eines Fits entscheidet sie. Mit umgekehrter Dreiecksfolge lieferten
  12 von 101 Korpuskörpern andere Merkmale (22.09.2026), danach keiner.
- **Diese Ordnung folgt den Koordinaten und ist nicht drehfest — keine Wahl
  darf deshalb an ihr hängen** (RM-210). Die Erkennung fragt ihre Flecken
  nach Größe (`_in_size_order`); eine Zusammenlegung läuft bis keine zwei
  Gruppen mehr zusammengehören (`_joined_until_stable`) und rechtfertigt
  sich in beide Richtungen; eine Auswahl von Punkten beginnt nicht an einem
  Ringanfang (`_simplified_ring` statt Douglas-Peucker).
- **Unter `perceive.features.MIN_ROUND_ARC` ist eine Rundform eine Kante**,
  an beiden Kernen (Entscheidung Robert, 23.09.2026). Wer eine neue Rundform
  meldet, fragt dieselbe Zahl.

## `scipy.spatial.ConvexHull` gehört nicht in eine Schleife über Flecken

Der Qhull-Wrapper legt **je Aufruf eine Temporärdatei** an (`tempfile.mkstemp`
für den Meldungsstrom). Einmal je Körper ist das nichts; einmal je Fleck ist es
eine Dateisystemoperation mitten in einer Geometrierechnung, und die kostet
nicht das, was sie im Leerlauf kostet: An einer Platte mit 64 verrundeten
Taschen rief `perceive.features.radial_cylinder` sie 256-mal je Erkennung —
gemessen 0,30 ms allein, 60 ms im Lauf, zusammen 15,4 s in `nt.open` und
`detect` bei 8382 statt 1272 ms (12.09.2026).

Für eine ebene Hülle nimmt der Kern deshalb GEOS: `MultiPoint(punkte).convex_hull`.
Gemessen an 73 Flecken des Korpus: gleiche Umrisse, gleiche Radien, gleiche
Rundungsfehler, 1439,6 ms gegen 3,8 ms. Zwei Unterschiede gehören dazu — GEOS
gibt bei entartetem Eingang eine Strecke oder einen Punkt zurück statt
`QhullError` zu werfen, und sein Ring läuft andersherum. Die Punktmenge ist
dieselbe; wer danach eine Ausgleichsrechnung anschließt, bekommt die letzten
Bits einer Summe in anderer Reihenfolge.

`geom/mesh.py` und `geom/orient.py` dürfen Qhull behalten: Sie fragen einmal je
Körper.

## `np.unique(…, axis=0)` an Kanten oder Ecken gehört nicht in eine Schleife

Dieselbe Bauart wie oben, eine Bibliothek weiter: `np.unique` über eine Achse
sortiert Zeilen als Strukturen und ist an 180 000 Kanten viermal langsamer
als dieselbe Frage an einer Zahl je Kante (gemessen am 22.09.2026: 70 gegen
16 ms). Die Randringe der Merkmalsketten stellten sie je Facette, und an der
unterteilten Lochplatte kostete jeder Szenenaufbau des Objektbaums 0,4 s
allein damit; die Fleckenlesung sortierte je Fleck ihre Ecken als Zeilen.

Für Kanten nimmt der Kern `geom.mesh.unique_edges` (Kantennummer `a·n + b`,
gleiche Reihenfolge, Zähler und Rückabbildung auf Wunsch); für Ecken eine
einmal je Körper gebildete Punktnummer (`perceive.features.vertex_rank`,
im Cache des Netzes) und danach nur noch `np.unique` über Nummern. Wer eine
Zellnummer aus Koordinaten bildet (`mesh_ops._clustered_once`), macht
dasselbe. Einmal je Körper — `geom/repair.py`, `geom/orient.py` — bleibt
`axis=0` in Ordnung; **wer exakt deckungsgleiche Ecken sucht, fragt trotzdem
`vertex_rank`** — dieselbe Nummerierung, fünfmal so schnell, und nach dem
ersten Leser umsonst (die Platzierungsnachbarschaft sortierte sie ein
drittes Mal, RM-232).

**Und die Regel gilt eine Ebene höher genauso** (16.09.2026). Die
Schattenprojektion der Ansicht rechnete ihre ebene Hülle selbst über
`scipy.spatial.ConvexHull` — je Körper, je Hüllstück und je Auffangfläche, an
`1-24+scale+polebarn.3mf` mit 89 Körpern **3541-mal für eine einzige
Kamerageste**: 1843 ms, davon 1679 in der Hülle und 635 im Anlegen der
Temporärdateien (Robert: „nach jedem kameraverschieben hängt es erstmal").
`geom.mesh.planar_outline` rechnet sie jetzt über GEOS, die Ansicht fragt nur
noch — dieselbe Grenze wie bei `hull_planes`: In `app/ui` wird keine Geometrie
gerechnet. Danach 199 ms, mit den zwei Änderungen daneben 126 ms.

Die allgemeine Form, weil dieselbe Falle zweimal an verschiedenen Orten stand:
**Eine Regel über eine Bibliothek gilt der Bibliothek, nicht dem Verzeichnis,
in dem sie zuerst auffiel.**

## Eine neue gemerkte Frage wird geteilt oder gebunden — ausdrücklich

`features.remembered` legt jede Antwort unter ihrer Frage ab. Eine Kopie für
einen Nebenfaden (`copy_with_answers`) liest die Antworten ihres Originals —
aber nur die aus `SHARED_ANSWERS`. Wer eine neue Frage merkt, trägt ihren
Namen in genau eine der beiden Mengen ein: geteilt, wenn die Antwort eine Zahl,
ein schreibgeschütztes Feld, eine Menge oder ein Fit ist; gebunden
(`BODY_BOUND_ANSWERS`), wenn sie beim Lesen etwas nachbaut — ein Netz mit
trägem Cache, einen Suchbaum, eine vorbereitete GEOS-Fläche, ein
`cached_property`. Ohne Eintrag gilt sie als gebunden und ist sicher, nur
langsam an der Kopie; `test_every_remembered_question_is_either_shared_or_bound`
verlangt den Eintrag. Eine Antwort, die selbst ein Körper ist, steht zusätzlich
in `DERIVED_BODY_ANSWERS`.

## Eine Auswahl aus `body.faces` oder `body.vertices` in einer Schleife geht über `np.asarray`

trimesh hält Ecken und Dreiecke als `TrackedArray`, und **jede** Ansicht
daraus — auch eine bloße Auswahl `body.faces[fleck]` — erklärt die Prüfsumme
des Netzes für ungültig (`TrackedArray.__array_finalize__`). Der nächste
gemerkte Wert (`body.area_faces`, `face_normals`, …) rechnet sie neu: an
4,5 Millionen Dreiecken 34 ms für die Dreiecke, 17 ms für die Ecken — je
Zugriff. In einer Schleife über Flecken wird daraus Minuten: Die Vorschau von
*Kanten verfeinern* auf 0,04 mm am Spielwürfel stand über zehn Minuten in
`perceive.features._area_and_reach` (Durchsicht 0.5.1, Stapelabzug). Wer in
einer Schleife auswählt, nimmt `np.asarray(body.faces)[…]` — eine Ansicht der
Grundklasse, die nichts verfolgt; die gemerkten Werte selbst
(`body.area_faces[…]`) sind davon nicht betroffen. In `perceive` steht keine
solche Auswahl mehr; `test_recognition_selects_triangles_and_corners_through_plain_arrays`
hält den Stand.

## Eine örtliche Frage ist dieselbe Frage wie die am ganzen Körper

Die Nachmessung (`local.detect_known`) fragt Radien, Krümmungssprünge und die
Flächenzuordnung nur an ihren Ausschnitten (`features.face_radii_at`,
`curvature_jumps_at`, `_surface_owners_near`). Jede dieser Fragen hat ihre
Ganzkörperfassung (`face_radii`, `curvature_jumps`, `_surface_owners`), und
beide rechnen mit denselben Schritten an denselben Zahlen — die Antwort ist
bitgleich, die Zuordnung dieselbe Zerlegung. **Wer eine der beiden ändert,
ändert die andere mit**: Gemeinsame Teile stehen einmal da (`_jumps_between`,
`_piece_filling`, `_rim_of`, `_closing_set`), der Rest ist gespiegelt
(`_closed_by_notches` zu `_without_notches`, `_near_surfaces` zu
`_large_facet_faces_read` und `_surface_owners_read`).
`tests/test_local_detection.py::test_the_spot_reads_the_same_radii_jumps_and_surfaces_as_the_whole_body`
vergleicht beide an Korpusnetzen, ungeteilt und nach *Kanten verfeinern*.

## Fehler

Jede Ausnahme erbt von `AppError` und trägt `suggestions: list[Action]` —
anklickbare Handlungen, keine Prosa. Ein Fehler endet nie mit
„fehlgeschlagen", sondern nennt: was nicht ging, warum, was jetzt möglich ist
(§2.7, §33.1).

Die Hierarchie unterscheidet Bedienfehler von Programmfehlern:
`UserError` (korrigierbar), `GeometryError` (mit Vorschlag),
`ExternalToolError` (Hinweis auf die Einstellung), `InternalError`
(Fehlerbericht). Ein Programmfehler darf nie wie ein Bedienfehler aussehen —
und umgekehrt. `tests/test_errors.py` prüft, dass jede Ausnahme einen
Vorschlag trägt.

Ins Protokoll gehen Kennzahlen, nie Geometriedaten. Das Protokoll verlässt den
Rechner nur, wenn der Nutzer es selbst anhängt (§33.2) — alles andere wäre die
verbotene Telemetrie.

**Es gibt genau einen Weg hinaus, und der heißt `support.send()`**
(`app/core/support.py`). Die Grenze zur Telemetrie liegt beim Auslöser: Der
Versand hängt an einem Knopf, vorher steht die vollständige Sendung in einer
Vorschau, und `tests/test_support.py` zählt die Aufrufer — genau einer. Ein
Zeitgeber, ein Fehlerpfad oder ein Startaufruf, der selbst sendet, ist ein
Verstoß, gleich wie freundlich er begründet wird. `app/core/report.py`
schreibt weiter nur einen Ordner und darf kein `urlopen` kennen.

### Ein Zeitlimit ist keine Frist

`opener.open(request, timeout=…)` begrenzt die **einzelne Leseoperation**,
nicht die Gesamtdauer. Ein Gegenüber, das seine Kopfzeilen byteweise mit
Pausen knapp unterhalb des Limits schickt, hält die Verbindung beliebig lange
offen, ohne es je zu verletzen — gemessen am 10.09.2026: eine volle Sekunde
für Statuszeile und Kopfzeilen bei einem Zeitlimit von fünfzig Millisekunden,
und die Antwort kam mit 200 zurück.

**Wer ein `…open(request, timeout=…)` schreibt, ruft daneben
`http.apply_header_deadline(opener, deadline)`** —
`tests/test_hard_rules.py::test_every_network_call_puts_its_headers_under_a_deadline`
prüft das je Funktion über `app/` und `tools/`. Zehn Stellen waren es beim
Anschließen, und keine davon war falsch geschrieben; jede hatte nur eine
Zusage nicht mitgenommen, die es anderswo schon gab.

**Der Öffner gehört dem einzelnen Aufruf.** Die Frist steckt in der
Antwortklasse, die dieser Aufruf erzeugt — ein modulweit geteilter Öffner
trüge nach dem ersten Aufruf für immer dessen Frist. Wer einen solchen
auflöst, sieht vorher nach, **wer ihn in der Suite patcht**: Ein verfehlter
Testzugang schickt den Test ins echte Netz, und das fällt als Fehler in einem
ganz anderen Test auf.

## Auswertung

`OpContext.scene` ist nur lesend. Ops erzeugen Objekte, sie ändern keine.
Zweimal auswerten muss identisch sein; ändert sich die Objektzahl, hält die
Auswertung an, statt still weiterzurechnen.

## Am Dokument wird nie vorbei geschrieben

Alles, was das Dokument ändert, geht durch eine Transaktion — auch das, was
keine Operation ist. Parameter, Passungen, Drucker und Material reisen als
`DocumentChange` mit (§15.5); `History.apply(..., changes=...)` nimmt sie
entgegen, `undo` und `redo` spielen sie zurück und vor. Die Vorher-Seite baut
`change_for()` aus dem Dokument — wer sie selbst zusammensucht, vergisst einen
Fall.

**Auch das nachträgliche Ändern eines Schritts** — andere Parameter, andere
Eingänge, der Zwilling im anderen Rechenkern. Die drei `change_*`-Methoden
schrieben lange direkt in `document.ops`: Der alte Stand war nach dem
Speichern unwiederbringlich, und Strg+Z traf einen anderen Schritt. Seit
Format v12 trägt die Transaktion beide **Fassungen** des Schritts
(`DocumentState.edited_ops`, `History._swap_operation`): Kennung und Platz
bleiben, der Verlauf wächst um keinen Schritt (§15.4), und `restore` legt
die Fassung in beide Richtungen zurück. Wer einen weiteren Änderungsweg baut,
geht durch `_swap_operation` — und misst „kein zweiter Schritt" an der
Schrittliste, nie an der Transaktionszahl: Genau diese Verwechslung hatte
einen Test die Nicht-Rücknehmbarkeit festschreiben lassen. Wechseln mehrere
Schritte zusammen, dann in **einer** Transaktion (`_swap_operations`): der
gespeicherte Bausteinstand (`History.use_part_states`, RM-138) stellt jeden
Einsatz desselben Bausteins um, und ein halb umgestelltes Projekt rechnete
mit zwei Ständen nebeneinander.

Wer stattdessen `document.parameters[...] = ...` schreibt, baut den Fehler
nach, der hier zweimal steckte: die Änderung ist nicht rücknehmbar, sie gilt
nicht als Änderung, und beim Schließen ist sie weg.

**Auch der Umbau des Verlaufs** — Einfügen, Verschieben, Aus- und Einschalten
(RM-188 P7). `History.plan_*` plant, `scene.revision.revise` rechnet den
Vorschlag isoliert, `revision.commit` übernimmt ihn als eine Transaktion.
Niemand sortiert `document.ops` um oder setzt `Operation.suppressed` von
Hand: Die Kennung ist die Reihenfolge, und ein Verweis, dessen Merkmal danach
anders heißt, zielte still auf ein anderes (§21.3). Ein ungültiger Vorschlag
ändert nichts; ein Plan, unter dem sich das Dokument geändert hat, wird
abgesagt (`RevisionPlan.mark`), nicht nachgebessert.

Die Grenze verläuft an der Auswertung: was sie beeinflusst, gehört in die
Transaktion. Druckeinstellungen und Sichtbarkeit tun das nicht — die
Einstellungen reisen zum Slicer, die Sichtbarkeit gehört der Ansicht.

## Die Lizenzgrenze

Was das Dokument ändert oder ein Ergebnis herausgibt, ruft
`activation.require(<handlung>)` — was nur liest, nie (Konzept §2 C). Die
Schreibwege in `History` verlangen CHANGE, `export/writer.py` EXPORT,
`export/handover.py` SLICER und `agent/session.py` CHAT. Jeder öffentliche
Einstieg holt den Zustand selbst und wirft selbst (H3); das gilt auch für
Reparieren, Zerlegen und Neuzählen mit erneutem Versuch. Eine **neue** Stelle,
die schreibt oder herausgibt, ohne durch eine bestehende Grenze zu gehen,
braucht ihren eigenen `require`-Aufruf — und einen Fall in
`tests/test_licence_boundary.py`, in
beide Richtungen: gesperrt lehnt ab, lesend läuft weiter.

Die Oberfläche graut nur vorher aus, sie ist nie die Hürde. Kein Schalter,
keine Umgebungsvariable, keine Freigabedatei — die Suite patcht
`activation._cached` über monkeypatch. Wer eine der vier Grenzdateien
umbenennt oder verschiebt, zieht `integrity.BOUNDARY_FILES` und die
PyInstaller-Spec nach (`tests/test_licence_build.py` hält beide zusammen).
Das Manifest deckt **genau diese vier** — eine Änderung an `activation/`
selbst macht es nicht ungültig (am 26.08.2026 zweimal falsch zugeschrieben;
`integrity.boundary_hashes()` antwortet in einer Sekunde).

**Die Testphase ist eine harte Grenze, keine Erinnerung** (Entscheidung
Robert, 26.08.2026). Der Marker liegt doppelt (`trial.json` im
Einstellungs-, `activation.state` im Datenordner), trägt eine HMAC-Unterschrift
über seine Tage, und die Zusammenführung lässt den früheren ersten Start und
den späteren gesehenen Tag gewinnen: Löschen oder Editieren **eines** Ortes
ist wirkungslos, ein angefasster Marker (falsche Unterschrift) beendet die
Frist. Wer beide Orte löscht, beginnt neu — das ist die bewusste Restgrenze,
denn die Alternative wäre ein Konto oder ein Server, und §2 sagt „ohne Netz,
ohne Konto" zu. Ein **Aktivierungsserver** ist entschieden und wird als
Konzept ausgearbeitet, bevor er gebaut wird. Vier Uhr-Deckel halten die
Zählung: Rückwärtsschutz (höchster gesehener Tag), Horizont (ein Jahr),
Untergrenze Auslieferungstag, und eine Uhr **vor** der Auslieferung wird gar
nicht erst festgeschrieben — sie ist beweisbar falsch, und der Zukunftsdeckel
feuert nur bei glaubwürdiger Uhr, sonst zerstörte ein Uhr-Rücksprung einen
echten Marker.

**Antworten auf Fragen der Auswertung sind Lesen, keine Änderung.**
`History.record_answers` und `record_matches` laufen ohne `require` — mit
Absicht: Sie schreiben nur fest, was die Auswertung selbst erfragt hat
(Einheit, Merkmalszuordnung), und ein `require` dort sperrte das **Öffnen**
einer Datei mit offener Rückfrage. Dasselbe gilt für `reopen_recognition`:
Es nimmt nur eine solche Antwort zurück (die Erkennungswahl am Ladeschritt),
damit die Frage wiederkommt. `tests/test_licence_boundary.py` nagelt alle
drei ausdrücklich als frei fest, damit die Entscheidung beim nächsten Audit
nicht wieder als Lücke aufgeht.

## Pfade

Keine absoluten Pfade in Projektdateien. Nutzerverzeichnisse kommen aus
`app.core.paths` — die Suite biegt sie um, damit ein Testlauf nichts im Profil
des Entwicklers hinterlässt (§38).

## Externe Programme: installieren heißt nicht finden

Wer einen Installationsweg dazunimmt, nimmt zwei Aufgaben dazu. Die zweite ist
die, die vergessen wird: **Solidon muss finden, was es gerade installiert
hat.** Sonst läuft der Knopf durch, und die Zeile daneben sagt weiter „nicht
gefunden" — die schlechteste aller Antworten, weil sie den Nutzer an seiner
eigenen Handlung zweifeln lässt.

Zweimal danebengegangen, beide Fälle stehen in `app/core/discover.py`:

* **Flatpak** legt seine Startprogramme unter der Anwendungskennung ab
  (`com.orcaslicer.OrcaSlicer`) und setzt den PATH ausdrücklich **nicht**. Weder
  `shutil.which` noch ein Durchgang durch `/opt` findet das. Verglichen wird
  deshalb über `plain_name` — klein, ohne Trenner —, damit „orca-slicer",
  „OrcaSlicer" und das letzte Stück der Kennung derselbe Name sind.
* **Homebrew-Casks** legen das Binary in `<Name>.app/Contents/MacOS/<Name>`.
  Was in `parts_for()` fehlt, wird nicht gefunden.

Und die dritte Aufgabe kommt bei Sandboxen dazu: **Ein Flatpak hat sein
eigenes `/tmp`.** Ein Arbeitsordner aus `tempfile` ist für es unsichtbar; der
Aufruf kommt an, und das Programm findet die Datei nicht. `workspace_for` legt
ihn für eingesperrte Programme unter `$HOME`, weil die Pakete
`--filesystem=home` freigeben — **nachgelesen im Flathub-Manifest**, nicht
angenommen. Wer ein weiteres Programm dazunimmt, sieht dort nach, welche
Verzeichnisse es überhaupt lesen darf.

### Und die vierte: Wir sind selbst einer

Die drei Absätze oben sprechen über **fremde** Sandkästen. Sie waren
vollständig, genau und blind für den Fall, der am 27.08.2026 aufgeschlagen
ist: Solidon wird als Flatpak ausgeliefert. Von innen sieht der Rechner anders
aus, und zwar an mehr Stellen, als eine Aufzählung vermuten lässt:

| Was von innen anders ist | Folge, wenn man es nicht weiß |
|---|---|
| Der PATH und die Installationsordner des Rechners fehlen | Kein Slicer wird gefunden, obwohl einer läuft |
| `subprocess` startet **im** Sandkasten | Das Programm gibt es dort nicht — `on_host` legt `flatpak-spawn --host` davor |
| `is_dir()`/`is_file()` auf einen Host-Pfad sagt nein | `install_root` fand keine Cura-Definition, und ohne `-j` startet CuraEngine gar nicht |
| `XDG_CONFIG_HOME` zeigt in den eigenen Sandkasten | Die Profile eines fremden Slicers liegen nie dort |
| `XDG_CACHE_HOME` auch — und `--filesystem=home` nimmt `~/.var` **aus** | Der Austauschordner liegt in `$HOME` und ist für den Slicer trotzdem unsichtbar |

Zwei Sätze für alles davon:

* **Wer einen neuen Startpfad baut, legt `discover.on_host` davor** — vier
  Stellen liefen ohne ihn weiter, nachdem die fünfte repariert war.
* **Im Flatpak gilt die XDG-Variable nicht, gemeint ist der Rechner.**
  `config_home` und `exchange_dir` sagen beide genau das, und sie sind an
  einem Tag unabhängig voneinander entstanden.

Der Grund, warum das lange stehen konnte, gehört dazu, weil er
wiederkommt:

> **Ein Modul, das eine Falle richtig benennt, ist gegen sie nicht immun.**

`discover.py` beschrieb die Flatpak-Falle über zwanzig Zeilen und zählte sich
selbst nicht mit. `find_program` schrieb in seinen Docstring, eine falsche
Auskunft sei teurer als keine, und meldete zwanzig Zeilen später einen
eingetragenen Host-Pfad als verschwunden. Der Satz liest sich als Beleg, dass
jemand nachgedacht hat — und genau deshalb prüft die Stelle niemand ein
zweites Mal. Siehe `.claude/memory/benannte-falle-schuetzt-nicht.md`.

### Was auf einer Plattform gilt, ist keine Zusage

Dieselbe Durchsicht hat fünf Stellen gefunden, an denen Linux oder macOS
weniger konnten als Windows — Zeigergröße, Slicer-Profile, ComfyUI-Rateorte,
AppImages, die Zeichenkodierung von Prozessausgaben. Keine war eine
Entscheidung; alle fünf waren dort entstanden, wo entwickelt wird.

**Eine Plattformkette gehört deshalb in eine Funktion mit der Plattform als
Parameter**, nicht als `sys.platform` in den Rumpf. `parts_for`,
`guesses_for`, `config_home` und `cursors.system_size` machen es so, und der
Grund ist nicht Stil:

* Ein Zweig, den nur ein Mac sehen kann, **wird nirgends geprüft**.
* `mypy` prüft die Plattform, auf der es läuft. Eine Kette aus
  `sys.platform`-Vergleichen ist auf zwei von drei Maschinen tot und wird
  dort als `unreachable` gemeldet — die Linux-CI sieht das nie. Am 27.08.2026
  war ein Commit auf drei Windows-Maschinen rot und auf dem Bauserver grün.

Wer eine solche Funktion schreibt, prüft mit
`mypy --platform linux|darwin|win32` nach; das kostet drei Läufe und fängt
genau den Fall, den ein grüner CI-Lauf nicht zurückholt.

Und wo ein Programm **mehr als Installation** braucht, ist das eine Eigenschaft
der Sache und kein Sonderfall der Oberfläche: `Requirement.follow_up` benennt
den zweiten Schritt, und die Prüfung „läuft es" ist dann nicht dieselbe wie
„kann es das" — `ComfyBackend.readiness` unterscheidet vier Lagen, wo vorher
ein Wahrheitswert stand.

## Einrichten heißt nicht laufen

Die Stufe darüber, und sie ist beim ersten echten Lauf des Bildwegs
aufgefallen (21.08.2026). Ein Einrichtungsschritt, der **behauptet**, fertig zu
sein, ist schlechter als keiner: Der Kunde geht weiter und scheitert an einer
Stelle, die nichts mit der Einrichtung zu tun zu haben scheint.

- **Am Ende wird nachgesehen, nicht behauptet.** `comfy_setup.nodes_load` lädt
  die Knoten im Python **von ComfyUI** — nur dort steht, was ComfyUI hat. Zwei
  Sekunden, und sie stehen **vor** dem 7,5-GB-Download: Ein fehlendes Paket
  nach zwei Sekunden zu melden ist mehr wert als nach einer halben Stunde.
  Genau dieser Schritt hat einen selbstgemachten Fehler gefangen, der die
  Knotensammlung als Ganzes ausfallen ließ.
- **Wer prüft, prüft den ganzen Ablauf.** `readiness` fragte den Knoten aus
  unserer eigenen Sammlung — der lag vor, also stand „Bereit" da, und
  abgeschickt scheiterte der Auftrag an einem anderen Knoten desselben
  Ablaufs. `missing_nodes` nennt die Namen; „ein Knoten fehlt" schickt
  niemanden weiter (Regel 17).
- **Eine Paketliste ist an dem Rechner gemessen, auf dem sie entstand.** Sie
  nannte drei, und auf einem frischen ComfyUI fehlten sechs — die übrigen
  hatten andere Knoten mitgebracht. Wer eine solche Liste schreibt, prüft sie
  gegen eine Installation, die *nichts* hat.
- **Ein fremdes Programm notiert, wo es liegt.** Raten ist der letzte Ausweg,
  nicht der erste: ComfyUI Desktop schreibt seinen Installationsordner in eine
  eigene Datei, samt einem selbst gewählten. Gelesen wird sie tolerant — sie
  gehört jemand anderem, ihr Aufbau ist nirgends zugesagt.
- **Ein Fehler des fremden Programms wird durchgereicht, nicht ausgewartet.**
  ComfyUI beendet einen Auftrag mit `status_str: "error"` und schreibt den
  Grund in den Verlauf. Wer nur fragt, ob Ausgaben da sind, wartet zehn
  Minuten auf einen toten Auftrag und sagt dann „Zeitlimit". Der Satz des
  fremden Programms reist unübersetzt mit — er ist genauer als jede
  Umschreibung, und wer damit zum Support geht, bringt die Zeile mit.
- **Ein Zeitlimit gilt dem Hängen, nicht der Langsamkeit.** Zehn Minuten waren
  an einer RTX 4080 gemessen. Solange der Auftrag in der Warteschlange des
  fremden Programms steht, wird gewartet; eine harte Obergrenze fängt nur den
  Fall, dass die Schlange lügt.

## Die Lizenz kann in einer Datendatei stecken

Regel 15 sagt „keine GPL-Abhängigkeit", und die Lizenzprüfung liest
`pyproject.toml`. Ein mitgelieferter **ComfyUI-Ablauf** ist keine Abhängigkeit
in diesem Sinn und verlangt trotzdem fremden Code: Beide Abläufe sprachen
`RMBG` aus `ComfyUI-RMBG` an — GPL-3.0. Damit verlangte Solidon vom Kunden eine
GPL-Installation, damit Weg 3 läuft, und keine Prüfung hatte das gesehen.

Wer eine Datendatei anlegt, die einen fremden Knoten, ein fremdes Modell oder
ein fremdes Programm benennt, stellt die Lizenzfrage dort — `tests/`
prüft die Namen im Ablauf, nicht eine Liste daneben. Und die erste Frage ist,
ob das Zielprogramm es **selbst** kann: ComfyUI kann freistellen, seit 0.33,
mit Gewichten unter MIT. Damit fiel neben der Lizenz auch ein
Installationsschritt weg.
