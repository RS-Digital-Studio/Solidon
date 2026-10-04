---
description: "Der Kern ohne Qt — Grenze nach oben, Absagen, plattformgleiche Rechnung, stabile Merkmalsnummern, teure Bibliotheksaufrufe, Fehler, Transaktionen, Lizenzgrenze, externe Programme, gebaute Maße"
paths:
  - "app/core/**/*.py"
---

# Regeln für den Kern

Gilt zusätzlich zu `AGENTS.md`; das Warum steht unter denselben Überschriften
in `konzepte/begruendungen/regel-kern.md`.

## Grenze nach oben

Regel 1 und der `OpContext` als einzige Tür gelten ohne Ausnahme — kein
`PySide6`, auch kein `print`, kein `input`, kein Logger, der etwas anzeigt,
kein globales Objekt.
`tests/test_core_isolation.py` importiert `app.core` ohne Qt. Mehrdeutigkeit
geht über `ctx.ask` (Regel 21).

## Eine ohne Wahl geschlossene Frage sagt der Frage ab, nicht der Rechnung

- Die Sitzung meldet sie als `errors.QuestionDeclined` (Unterklasse von
  `OperationCancelled`); `_WatchedAsk` macht daraus einen Befund am fragenden
  Schritt mit Weg zurück, die Verweisprüfung lässt den Verweis stehen. Wer
  außerhalb eines Schritts fragt, entscheidet dasselbe ausdrücklich — ein
  stiller Abbruch ohne Satz ist keine Antwort.
- **Eine optionale Frage ist kein Hindernis.** Nach der Frage vor der langen
  Vollerkennung (§21.1) lädt `QuestionDeclined` begrenzt erkannt weiter, ein
  echter `OperationCancelled` beendet den Auftrag; `UserError` aus `ask`
  (niemand zu fragen) lädt wie nach einer Absage und hält nichts fest. Jede
  neue optionale Frage bekommt denselben Rückweg.
- **Die Wahl gilt dem Körper** (`evaluate._BodyRecognition`): Nach Zustimmung
  erkennen Folgeschritte ohne Frage vollständig, nach einer Absage oberhalb
  der automatischen Grenze örtlich, darunter von selbst.
- **Ein Speicherfehler kostet die Erkennung, nie den Schritt**
  (`local.ran_out_of_memory`): kein neuer Versuch an Folgeschritten mit
  mindestens so vielen Dreiecken, am selben Netz nicht im selben Prozess. Den
  Merker leert nur eine neue Entscheidung — eine Antwort in diesem Lauf,
  *Alle Merkmale erkennen*, `recognize`, ein Projektwechsel
  (`local.forget_out_of_memory`) —, keine Absage, die wegen eines Abbruchs den
  Ladeschritt nie erreichte. Die Absage aus einem Speicherfehler trägt
  `out_of_memory` im Eintrag, geht wie eine Antwort sofort an den Aufrufer,
  ihr Befund bleibt in jedem Lauf eine Warnung.
- **Zurückgenommen wird nur, was am Ladeschritt steht**
  (`history.recognition_reopenable`, gefragt von Befundsatz, Berichtsknopf und
  `History.reopen_recognition`); was erst danach über die Grenze wuchs, hat
  keine Wahl und keinen Rückweg.
- **Mehrere große Körper eines Imports: eine Frage mit der Summe.** Die
  Antwort steht sofort fest (`on_recognition_answer`), nicht erst mit dem
  Ergebnis; eine gespeicherte Zustimmung wird gemeldet, sobald sie die lange
  Erkennung startet — unmittelbar vor `detect`, nach dem Übertrag auf ein
  bewegtes Netz, nur ohne Treffer im Merker, nicht bei jeder Auswertung.

## Zahlen

Regeln 6, 7 und 9 gelten wörtlich; die Griffe sind `units.is_close`/`is_zero`
statt `==`, `auto:<material>` und `ctx.seed` mit `deterministic=False` — ohne
beides ist eine randomisierte Prozedur falsch, auch wenn sie funktioniert.

Text, den der Kern **fertig** ausliefert (eine Frage über `ctx.ask`), schreibt
Zahlen wie die Oberfläche: `format_decimal` bzw. `decimal_separator()` und
Längen in `app.i18n.display_unit()` — sonst liest der Kunde „177.80 mm“ in
einem auf Zoll gestellten deutschen Fenster (`unit_question`).

Eine Zahl als **Platzhalterwert** eines Satzes (`_("… unter {largest}", largest=…)`)
geht als `format_length`/`format_volume`/`format_area` (sie liefern eine
`app.i18n.Figure`) oder als `float` hinein, nie selbst mit Punkt formatiert:
Nur so bekommt sie beim Übersetzen das Dezimalzeichen der Sprache. Texte
bleiben unangetastet — „Snapmaker 2.0“ ist ein Name.

## Dieselbe Datei, dasselbe Teil — auf jeder Maschine

Was zu Geometrie wird oder zwischen Lagen, Flächen oder Kandidaten
entscheidet, rechnet ohne Wege, deren letzte Stelle an der Plattform hängt:

- kein BLAS (`np.dot`, `@`, `inner`, `vdot`, `tensordot`, `np.linalg.norm`
  ohne Achse), kein `np.einsum` (FMA auf ARM), kein LAPACK (`svd`, `eigh`,
  `eig`, `lstsq`, `solve`, `inv`, `det`) — auch nicht für das Vorzeichen
  eines Eigen- oder Singulärvektors;
- keine Winkel- und Exponentialfunktion aus NumPy oder `math` (Winkel über
  `units.exact_cos`/`exact_sin`), kein `x ** 2` (Plattform-`pow`) — `x * x`;
- Zufall nur aus Rohbits (`Generator.random`, `integers`), nie `normal` oder
  andere Verteilungen über `exp`/`log`;
- keine Summe, deren Folge an der Zahl der Arbeiter hängt: Schichten und
  Teile in fester Folge verrechnen (`analysis._support_volume`).

Ersatzwerkzeuge: `app/core/geom/CLAUDE.md` („Plattformgleich gerechnet"). Ein
neuer Weg zu Geometrie kommt in `tests/test_platform_identity.py` (`_WAYS`),
der jede Rechnung um ein ULP verrauscht und den BLAS-Kern tauscht; der
Fingerabdruck darf sich nicht rühren. Anzeige, Berichtsmessung und exakt
nachgeprüfte Vorauswahlen dürfen schnell rechnen — der Kommentar sagt, warum;
ebenso ein sicheres Nein mit Abstand und Schattenlauf (`schichtanalyse.md`,
„Ein Löserlauf entfällt nur mit dem Nein des Stapels“).

## Eine Merkmalsnummer kommt aus dem Körper, nie aus der Reihenfolge

Sie ist eine Provenienz-ID (§21.2); Passungen und Operationen hängen an ihr.

- **Nummeriert wird über `perceive.features.numbering_order`** (nach der Mitte
  Maß, Länge, Lage, Ecken; Einzelne wie nach der gerundeten Mitte), nie über
  eine eigene Sortierung nach der gerundeten Mitte — konzentrische Rundungen
  erben dort die Folge der Flecken.
- **Summen einer Einpassung laufen in der Ordnung des Körpers**
  (`perceive.features.in_body_order`: Flecken, Stücke, Zusammenlegungen);
  ihre Folge entscheidet an der Kippe eines Fits.
- **Diese Ordnung ist nicht drehfest — keine Wahl hängt an ihr**: Flecken
  nach Größe (`_in_size_order`), Zusammenlegen bis keine zwei Gruppen mehr
  zusammengehören und in beide Richtungen gerechtfertigt
  (`_joined_until_stable`), Punktauswahl ohne Ringanfang (`_simplified_ring`
  statt Douglas-Peucker).
- **Unter `perceive.features.MIN_ROUND_ARC` ist eine Rundform eine Kante**, an
  beiden Kernen (Entscheidung Robert); jede neue Rundform fragt dieselbe Zahl.
- **Zwillinge behalten ihren Namen nach der Lage ihrer Oberfläche**
  (`schichtanalyse.md`, „Stabile IDs“): Jeder Weg, der alte Merkmale neuen
  zuordnet — die Auswertung an beiden Kernen, jeder exakte Neubau in
  `geom/prepare_ops.py`, der Baustein am exakten Träger —, entscheidet sie
  nach `match` über `perceive.matching.settled_twins`; sonst heißen zwei
  gleiche Rundungen nach jeder Kopie anders.

## Was je Aufruf teuer ist, gehört nicht in eine Schleife über Flecken

Die Regel gilt der Bibliothek, nicht dem Verzeichnis, in dem sie auffiel. In
`app/ui` wird keine Geometrie gerechnet; die Ansicht fragt den Kern.

- **`scipy.spatial.ConvexHull`** legt je Aufruf eine Temporärdatei an. Ebene
  Hüllen über GEOS (`MultiPoint(punkte).convex_hull`; für die
  Schattenprojektion `geom.mesh.planar_outline`, wie `hull_planes`); GEOS gibt
  bei entartetem Eingang Strecke oder Punkt statt `QhullError`, sein Ring
  läuft andersherum, eine Ausgleichsrechnung danach summiert anders.
  `geom/mesh.py` und `geom/orient.py` fragen einmal je Körper und behalten
  Qhull.
- **Kein `np.unique(…, axis=0)` an Kanten oder Ecken in einer Schleife** — es
  sortiert Zeilen als Strukturen. Kanten über
  `geom.mesh.unique_edges` (Nummer `a·n + b`, gleiche Reihenfolge, Zähler und
  Rückabbildung auf Wunsch), Ecken über `perceive.features.vertex_rank`
  (einmal je Körper, im Netzcache), dann `np.unique` über Nummern;
  Zellnummern ebenso (`mesh_ops._clustered_once`). Einmal je Körper
  (`geom/repair.py`, `geom/orient.py`) bleibt `axis=0` erlaubt; exakt
  deckungsgleiche Ecken sucht man trotzdem über `vertex_rank`.
- **Auswahlen aus `body.faces`/`body.vertices` in einer Schleife gehen über
  `np.asarray`**:
  Jede Ansicht eines `TrackedArray`, auch `body.faces[fleck]`, macht die
  Prüfsumme ungültig (`TrackedArray.__array_finalize__`), und der nächste
  gemerkte Wert (`body.area_faces`, `face_normals`) rechnet neu. Also
  `np.asarray(body.faces)[…]`; gemerkte Werte selbst (`body.area_faces[…]`)
  sind nicht betroffen.
  `test_recognition_selects_triangles_and_corners_through_plain_arrays` hält
  `perceive` frei davon.

## Ein Kernaufruf an einem ganzen Körper rechnet im Hilfsprozess

`manifold3d` hält den GIL in jedem Aufruf (Aufbau aus `Mesh64`, `simplify`,
`refine_to_length`, Boolesche, `decompose`, `to_mesh64`); ein Arbeiterfaden, der
ihn ruft, hält das Fenster an (RM-212).

- **Jeder `manifold3d`-Aufruf an einem Körper, der groß sein kann, ist eine
  Rechnung in `geom/kernel_jobs.py` und läuft über `kernel_process.run`** —
  ebenso jede andere Bibliothek, die an ganzen Körpern den GIL hält
  (`scipy.sparse.csgraph` in `mesh.face_components`) —
  unter `OFFLOAD_ABOVE` Dreiecken und im Hauptfaden hier, sonst im
  Hilfsprozess. Eine neue Rechnung steht in `JOBS` und bekommt ihren Fall in
  `tests/test_kernel_process.py` (Bitgleichheit).
- **Eine Rechnung kennt nur Felder und Zahlen**: kein Import aus dem Kern,
  Grenzen als Zahl vom Aufrufer (sonst gilt ein Umstellen im Test nicht im
  Hilfsprozess), eigene zusammenhängende Ausgabefelder, nie ein Körper des
  Kerns. Verschweißen, Slots und Befunde bleiben beim Aufrufer.
- **Eine Rechnung ruft kein BLAS** (kein `@`, `dot`, `einsum`, `linalg` außer
  einer Norm entlang einer Achse): Der Hilfsprozess startet mit einem
  BLAS-Faden (`HELPER_ENVIRONMENT`, spart je Bibliothek einen Puffer je
  Rechenkern), und über BLAS hinge das Ergebnis an der Fadenzahl.
  `test_the_jobs_call_no_blas` hält es.
- **Eine Rechnung lädt zurückgestellt nichts nach**: Was sie an Modulen
  braucht, steht in `kernel_jobs.PREPARATIONS` und lädt vorher in normaler
  Klasse — unter Windows verhungert ein Import eine Klasse tiefer auf
  ausgelasteten Kernen (RM-380). `test_a_job_gives_the_same_bytes_in_the_helper_as_here`
  misst es je Rechnung im Hilfsprozess.
- **Das Gewicht ist die größte Dreieckszahl der Rechnung**, bei einer
  Verfeinerung die erwartete des Ergebnisses.
- **Ein voller Datenträger pausiert, er schaltet nicht ab** (RM-436): ENOSPC
  beim Transfer rechnet für `FULL_DISK_PAUSE_SECONDS` im Prozess, danach nimmt
  die nächste große Rechnung den Hilfsprozess wieder. Jede Rechnung, die deshalb
  im Prozess lief, hinterlässt ihrem Faden einen Hinweis (`take_notice`); die
  Auswertung meldet ihn am Schritt als `kernel.disk_full`, nie im Ergebniscache.
- **Der Abbruch reicht als Token hinein** und beendet den Hilfsprozess; wer um
  einen Aufruf breit fängt (`except Exception`), lässt
  `kernel_process.NOT_A_KERNEL_FAILURE` durch — Abbruch und verlorenen
  Hilfsprozess —, sonst nimmt eine Rückfallkette still die nächste Stufe.
  Ein toter Hilfsprozess ist `KernelHelperLostError` (Regel 17); einer, der
  stumm bleibt oder eine Rechnung nicht übernehmen oder übergeben kann, ein
  Rückfall in den Prozess. Fehlt dafür Speicher, kommt `MemoryError` wie aus
  dem Prozess (Windows meldet ihn am gemeinsamen Speicher als `OSError`).
- **Die Seite des Hilfsprozesses lässt nichts entweichen** (`serve`): Im
  Windows-Fensterpaket ist `sys.stderr` `None`, und eine Ausnahme dort öffnete
  ein Traceback-Fenster von PyInstaller.
- **Millionen Werte werden stückweise zu Python-Zahlen**
  (`geom.mesh.python_values`), nie in einem `tolist`, `tuple`, `sorted` oder
  `repr` am Stück — jeder davon ist ein C-Aufruf unter dem GIL, und nach
  *Kanten verfeinern* trägt eine Fläche Millionen Dreiecksnummern. Zahlenreihen
  in einen Hash gehen als `array("q", …)`, nicht als Text.
- **Ein Hauptmodul, das den Kern nebenläufig ruft, rechnet nur unter
  `__main__`** — der Hilfsprozess lädt es noch einmal (`spawn`); im Paket ruft
  `app/ui/app.py` zuerst `freeze_support()`.

## Eine neue gemerkte Frage wird geteilt oder gebunden — ausdrücklich

Eine Kopie für einen Nebenfaden (`copy_with_answers`) liest vom Original nur
Antworten aus `SHARED_ANSWERS`. Jede neue Frage in `features.remembered` steht
in genau einer Menge: geteilt bei Zahl, schreibgeschütztem Feld, Menge oder
Fit; gebunden (`BODY_BOUND_ANSWERS`), wenn sie beim Lesen etwas nachbaut
(Netz mit trägem Cache, Suchbaum, vorbereitete GEOS-Fläche,
`cached_property`). Ohne Eintrag gilt sie als gebunden — sicher, an der Kopie
langsam; `test_every_remembered_question_is_either_shared_or_bound` verlangt
ihn. Eine Antwort, die ein Körper ist, steht zusätzlich in
`DERIVED_BODY_ANSWERS`.

## Eine örtliche Frage ist dieselbe Frage wie die am ganzen Körper

`local.detect_known` fragt an Ausschnitten (`features.face_radii_at`,
`curvature_jumps_at`, `_surface_owners_near`) bitgleich und mit derselben
Zerlegung wie die Ganzkörperfassungen (`face_radii`, `curvature_jumps`,
`_surface_owners`). **Wer eine ändert, ändert die andere mit**: gemeinsam
stehen `_jumps_between`, `_piece_filling`, `_rim_of`, `_closing_set`;
gespiegelt `_closed_by_notches`/`_without_notches` und `_near_surfaces`/
`_large_facet_faces_read` mit `_surface_owners_read`.
`tests/test_local_detection.py::test_the_spot_reads_the_same_radii_jumps_and_surfaces_as_the_whole_body`
vergleicht beide an Korpusnetzen, ungeteilt und nach *Kanten verfeinern*.

## Über die Körpergrenze merkt sich nur, wer außer seiner Lesung nichts liest

Die Vollerkennung nach jedem Schritt (§21.1) bleibt; ein bitgleich gelesener
Fleck bekommt auch an einem neuen Körper dieselbe Antwort
(`features._by_geometry`). Schlüssel: der Abdruck der Stützpunktlesung
(`_SurfaceSupport.digest`: jedes Feld, die Dreiecke des Flecks), die Zahlen,
die die Frage sonst vom Körper liest (Toleranz aus seiner Diagonale,
geprüfter Fit), die Löserbudgets. **Kein Toleranzvergleich** — eine Normale,
die in der letzten Stelle abweicht, ist eine andere Frage.

- **Eine Frage in `GEOMETRY_KEYED_ANSWERS` liest den Körper nur über ihre
  Lesung und Zahlen ihres Aufrufers** (Toleranz als Argument, in Rechnung und
  Schlüssel): Normalen und Flächen des Flecks sind Felder der Lesung, Mitten
  folgen aus den Dreiecken, Ecken in Nummernfolge gehen nur in Minimum oder
  Maximum ein. Die Antwort ist unveränderlich (Fit, Wahrheitswert), nie eine
  Dreiecksnummer;
  `tests/test_features.py::test_every_question_across_bodies_is_named_and_shared`
  verlangt den Eintrag.
- Grenze wie jede kleine Frage (`CACHE_LIMIT_PER_QUESTION`), Lebensdauer wie
  der Merker je Körper: Die Antwort gehört den Abstammungen, die sie rechneten
  oder lasen, und geht mit der letzten; `forget_cache` leert auch sie.
- Treffen kann sie nur bei derselben Darstellung (Eckenfolge, Reihenfolge der
  Ecken); deshalb legt eine Boolesche Ungeschnittenes zurück
  (`attributes.in_source_layout`, `operationen.md`).

## Fehler

Regel 17 im Kern: Jede Ausnahme erbt von `AppError` und trägt
`suggestions: list[Action]` — anklickbare Handlungen: was nicht ging, warum,
was jetzt geht (§2.7, §33.1; `tests/test_errors.py`). `UserError`
(korrigierbar), `GeometryError` (mit Vorschlag), `ExternalToolError`
(Hinweis auf die Einstellung), `InternalError` (Fehlerbericht): Ein
Programmfehler sieht nie wie ein Bedienfehler aus, und umgekehrt.

**Ein Befund, der sagt, was ein Schritt mit seinem Wert getan hat, öffnet
diesen Schritt** (RM-374): `suggestions=(errors.CHANGE_…,)` mit der Kennung
`change_step`, das Feld in `values["field"]`, eingetragen in
`MEINT_DEN_SCHRITT` (`tests/test_finding_ways.py`). Ändert sich ein Befund
einer Operation, steigt ihre `cache_version` — der Plattencache gäbe ihn sonst
alt zurück.

Ins Protokoll gehen Kennzahlen, nie Geometriedaten; hinaus nur, wenn der
Nutzer es selbst anhängt (§33.2) — sonst wäre es Telemetrie. **Der einzige Weg
hinaus ist `support.send()`** (`app/core/support.py`), und die Grenze zur
Telemetrie liegt beim Auslöser: ein Knopf, davor eine Vorschau der ganzen
Sendung; `tests/test_support.py` zählt genau einen Aufrufer. Was per
Zeitgeber, Fehlerpfad oder Start selbst sendet, ist ein Verstoß, gleich wie
begründet; `app/core/report.py` schreibt nur einen Ordner und kennt kein
`urlopen`.

### Ein Zeitlimit ist keine Frist

`opener.open(request, timeout=…)` begrenzt die einzelne Leseoperation, nicht
die Gesamtdauer: **Wer ein `…open(request, timeout=…)` schreibt, ruft daneben
`http.apply_header_deadline(opener, deadline)`** — je Funktion über `app/` und
`tools/` geprüft von
`tests/test_hard_rules.py::test_every_network_call_puts_its_headers_under_a_deadline`.
**Der Öffner gehört dem einzelnen Aufruf** — die Frist steckt in seiner
Antwortklasse, ein geteilter trüge für immer die des ersten. Wer einen
geteilten auflöst, prüft vorher, wer ihn in der Suite patcht: Ein verfehlter
Testzugang geht ins echte Netz und fällt in einem fremden Test auf.

## Auswertung

`OpContext.scene` ist nur lesend (Regel 3). Zweimal auswerten ist identisch;
eine geänderte Objektzahl hält die Auswertung an, statt still
weiterzurechnen.

## Am Dokument wird nie vorbei geschrieben

Jede Änderung am Dokument ist eine Transaktion, auch ohne Operation:
Parameter, Passungen, Drucker und Material reisen als `DocumentChange`
(§15.5) über `History.apply(..., changes=...)`, `undo`/`redo` spielen sie
zurück und vor, die Vorher-Seite baut `change_for()`. Ein
`document.parameters[...] = ...` ist nicht rücknehmbar, gilt nicht als
Änderung und ist beim Schließen weg.

- **Einen Schritt nachträglich ändern** (Parameter, Eingänge, Zwilling im
  anderen Kern): Die Transaktion trägt beide Fassungen
  (`DocumentState.edited_ops`, `History._swap_operation`); Kennung und Platz
  bleiben, der Verlauf wächst nicht (§15.4), `restore` legt in beide
  Richtungen zurück. Neue Änderungswege gehen durch `_swap_operation`; „kein
  zweiter Schritt" misst die Schrittliste, nie die Transaktionszahl. Mehrere
  Schritte zusammen in **einer** Transaktion (`_swap_operations`), damit
  `History.use_part_states` jeden Einsatz desselben Bausteins umstellt.
- **Den Verlauf umbauen** (Einfügen, Verschieben, Aus- und Einschalten):
  `History.plan_*` plant, `scene.revision.revise` rechnet isoliert,
  `revision.commit` übernimmt als eine Transaktion. Nie `document.ops`
  umsortieren oder `Operation.suppressed` von Hand setzen — die Kennung ist
  die Reihenfolge, ein Verweis zielte sonst still auf ein anderes Merkmal
  (§21.3). Ein ungültiger Vorschlag ändert nichts; ein Plan über einem
  inzwischen geänderten Dokument wird abgesagt (`RevisionPlan.mark`), nicht
  nachgebessert.
- **Ein Ablauf ist ein Rückgängig-Schritt** (§15.5): Was der Kunde mit einem
  Klick auslöst — Erzeugen, eine Sammelzeile je Körper —, wird **eine**
  Transaktion, deren Schritte einzeln im Verlauf stehen; sonst nimmt ein
  Strg+Z ein Drittel zurück. Folgeschritte am neuen Körper nennen ihn über
  `History.next_object_id`, mehrere `apply` der Oberfläche sammelt
  `Session.one_step`.
- **Die Grenze ist die Auswertung**: Was sie beeinflusst, gehört in die
  Transaktion; Druckeinstellungen (reisen zum Slicer) und Sichtbarkeit
  (gehört der Ansicht) nicht.

## Die Lizenzgrenze

Was das Dokument ändert oder ein Ergebnis herausgibt, ruft
`activation.require(<handlung>)`, was nur liest, nie (Konzept §2 C): CHANGE in
den Schreibwegen von `History`, EXPORT in `export/writer.py`, SLICER in
`export/handover.py`, CHAT in `agent/session.py`. Jeder öffentliche Einstieg
holt den Zustand selbst und wirft selbst (H3), auch Reparieren, Zerlegen und
Neuzählen mit erneutem Versuch. Eine **neue** schreibende oder herausgebende
Stelle ohne bestehende Grenze bekommt eigenen `require` und einen Fall in
`tests/test_licence_boundary.py` in beide Richtungen (gesperrt lehnt ab,
lesend läuft weiter).

- **Die Oberfläche graut nur aus, sie ist nie die Hürde.** Kein Schalter,
  keine Umgebungsvariable, keine Freigabedatei; die Suite patcht
  `activation._cached`.
- Die vier Grenzdateien umbenennen oder verschieben heißt
  `integrity.BOUNDARY_FILES` und die PyInstaller-Spec nachziehen
  (`tests/test_licence_build.py`). Das Manifest deckt genau diese vier; eine
  Änderung an `activation/` selbst macht es nicht ungültig
  (`integrity.boundary_hashes()` sagt es in einer Sekunde).
- **Die Testphase ist eine harte Grenze, keine Erinnerung** (Entscheidung
  Robert): Marker doppelt (`trial.json` im Einstellungs-, `activation.state`
  im Datenordner), HMAC-unterschrieben über seine Tage; zusammengeführt
  gewinnen der frühere erste Start und der spätere gesehene Tag. Einen Ort zu
  löschen oder zu editieren wirkt nicht, eine falsche Unterschrift beendet die
  Frist; sind beide gelöscht, beginnt sie neu — die bewusste Restgrenze (§2:
  ohne Netz, ohne Konto).
  Uhr-Deckel: Rückwärtsschutz (höchster gesehener Tag), Horizont (ein Jahr),
  Untergrenze Auslieferungstag; eine Uhr vor der Auslieferung wird nicht
  festgeschrieben, der Zukunftsdeckel feuert nur bei glaubwürdiger Uhr.
- **Antworten auf Fragen der Auswertung sind Lesen**: `History.record_answers`,
  `record_matches` (Einheit, Merkmalszuordnung) und `reopen_recognition`
  (Erkennungswahl am Ladeschritt) laufen ohne `require` — sonst sperrte es das
  Öffnen einer Datei mit offener Rückfrage; `tests/test_licence_boundary.py`
  hält alle drei als frei fest.

## Pfade

Keine absoluten Pfade in Projektdateien (Regel 12); Nutzerverzeichnisse aus
`app.core.paths`, das die Suite umbiegt (§38).

## Externe Programme: installieren heißt nicht finden

Wer einen Installationsweg dazunimmt, sorgt dafür, dass Solidon findet, was es
gerade installiert hat (`app/core/discover.py`):

- Flatpak-Startprogramme liegen unter der Anwendungskennung
  (`com.orcaslicer.OrcaSlicer`), ohne PATH — verglichen wird über
  `plain_name` (klein, ohne Trenner).
- Homebrew-Casks legen das Binary in `<Name>.app/Contents/MacOS/<Name>`; was
  in `parts_for()` fehlt, wird nicht gefunden.
- Ein Flatpak hat sein eigenes `/tmp`: `workspace_for` legt den Arbeitsordner
  eingesperrter Programme unter `$HOME` (`--filesystem=home`, nachgelesen im
  Flathub-Manifest). Für ein weiteres Programm dort nachlesen, was es lesen
  darf.

### Im eigenen Flatpak sieht der Rechner anders aus

Von innen fehlen PATH und Installationsordner des Rechners, `subprocess`
startet im Sandkasten, `is_dir()`/`is_file()` auf Host-Pfade sagt nein (ohne
Cura-Definition aus `install_root` startet CuraEngine nicht), und
`XDG_CONFIG_HOME`/`XDG_CACHE_HOME` zeigen in den Sandkasten —
`--filesystem=home` nimmt `~/.var` aus, der Austauschordner wäre für den
Slicer unsichtbar. Deshalb: **Jeder neue Startpfad bekommt `discover.on_host`
davor** (`flatpak-spawn --host`), **und mit XDG ist im Flatpak der Rechner
gemeint** (`config_home`, `exchange_dir`). Ein Modul, das eine Falle richtig
benennt, ist gegen sie nicht immun.

### Was auf einer Plattform gilt, ist keine Zusage

**Eine Plattformkette ist eine Funktion mit der Plattform als Parameter**,
kein `sys.platform` im Rumpf (`parts_for`, `guesses_for`, `config_home`,
`cursors.system_size`): Ein Zweig, den nur ein Mac sieht, wird nirgends
geprüft, und `mypy` meldet `sys.platform`-Ketten auf den anderen Maschinen
als `unreachable`, was die Linux-CI nie sieht. Prüfen mit
`mypy --platform linux|darwin|win32`.

Braucht ein Programm mehr als Installation, ist das eine Eigenschaft der
Sache: `Requirement.follow_up` benennt den zweiten Schritt, und
`ComfyBackend.readiness` unterscheidet vier Lagen statt eines Wahrheitswerts
— „läuft es" ist nicht „kann es das".

## Einrichten heißt nicht laufen

Ein Einrichtungsschritt, der Fertigsein behauptet, ist schlechter als keiner.

- **Am Ende nachsehen, die billige Prüfung zuerst**: `comfy_setup.nodes_load`
  lädt die Knoten im Python von ComfyUI — zwei Sekunden, vor dem
  7,5-GB-Download.
- **Den ganzen Ablauf prüfen**, nicht einen Knoten daraus; `missing_nodes`
  nennt die Namen (Regel 17).
- **Eine Paketliste gegen eine Installation prüfen, die nichts hat.**
- **Ein fremdes Programm notiert, wo es liegt** (ComfyUI Desktop, auch einen
  selbst gewählten Ordner): diese Datei tolerant lesen, raten zuletzt.
- **Fehler des fremden Programms durchreichen, nicht auswarten**:
  `status_str: "error"` beendet den Auftrag; der Grund aus dem Verlauf reist
  unübersetzt mit.
- **Ein Zeitlimit gilt dem Hängen, nicht der Langsamkeit**: Gewartet wird,
  solange der Auftrag in der Warteschlange steht; eine harte Obergrenze fängt
  nur die Schlange, die lügt.

## Die Lizenz kann in einer Datendatei stecken

Regel 15 gilt auch für Datendateien: Wer eine anlegt, die einen fremden
Knoten, ein Modell oder Programm benennt (etwa einen ComfyUI-Ablauf), stellt
dort die Lizenzfrage — die Prüfung über `pyproject.toml` sieht sie nicht;
`tests/` prüft die Namen im Ablauf. Zuerst fragen, ob das Zielprogramm es
selbst kann.

## Eine Zahl, die je nach Wahl anderes misst, bekommt je Bedeutung ein Feld

*Abschneiden* misst die `position` auf der Achse und den `offset` von Fläche,
Kante oder Punkten (RM-400): Ein gemeinsames Feld behielt beim Umschalten einen
Wert, der dort etwas anderes hieß. Eine Ebene aus Punkten richtet ihre Normale
aus (`prepare_ops._upward`), damit „Kleinere Seite“ nicht an der Klickfolge hängt.

## Ein erzeugtes Merkmal nennt, was gebaut ist

Ein Erzeuger nennt das gebaute Maß, wie die Erkennung es an einem eingelesenen
Teil mäße; ein Nennmaß steht daneben (`nominal` am gedruckten Gewinde,
`fasteners._thread_feature`; das Kappengewinde des Drehdeckels). Passungen
prüfen gebaut gegen gebaut, sonst meldet ein frisch gebautes Paar „0,00 mm“.
Das Soll einer Gewindepassung ist die Summe ihrer Hälften
(`fits._thread_wanted`): eine gedruckte trägt das Spiel ihres Materials, sonst
das Loch die Lochkorrektur; `target(as_stated=True)` gilt zwei Gewinden ohne
Spiel daneben, wie *Merkmal ändern* sie setzt.
