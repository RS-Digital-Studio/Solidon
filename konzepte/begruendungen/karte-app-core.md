# Begründungen zu `app/core/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, Datenfluss,
> Einstiege und Muster verdichtet wurde. Die Karte steht dort; hier stehen die
> ausführlichen Fassungen der verdichteten Absätze, das Warum und die Anlässe
> ihres Tages — wörtlich, gegliedert nach den Überschriften der Karte. *Früher
> unter …* nennt die Stelle der alten Karte.

## Die Module direkt hier

*Früher unter „Die Module direkt hier“.*

| Datei | Rolle |
|---|---|
| `types.py` | Die Verträge (§9): `Mesh`, `Scene`, `SceneObject`, `OpContext`, `OpResult`, `Feature`, `Profile`. Signaturen stehen fest, bevor ein Modul entsteht. Dazu die zwei Fragen, die an einem Merkmal nur einmal beantwortet werden: `is_a_cavity` und `thread_is_left_handed` (belegt links heißt gesetzt, nativ gelesen oder am Netz an den Kanten gemessen; die Schätzung des Spektrums, `fit`, sperrt nicht) |
| `build_area.py` | Tatsächliche Druckkontur, Sperrzonen, Druckhöhe und Auftragsrand für Anordnung, Orientierung und Ausgabe (§29); die Projektion eines geschlossenen Netzes kommt aus seinen Umrisskanten statt aus der Vereinigung aller Dreiecke |
| `errors.py` | Die Ausnahmen-Hierarchie (§33.1). Jede trägt mindestens eine `Action` — ein Fehler endet nie mit „fehlgeschlagen" |
| `units.py` | Millimeter, doppelte Genauigkeit, die drei benannten Toleranzen (§11). Fließkommavergleich über `is_close`/`is_zero`, nie mit `==`. **Und die Winkelfunktionen, die auf jeder Maschine dieselbe Zahl geben** — `circle_point`, `inscribed_ratio`, `exact_cos`/`exact_sin` und ihre Gradgeschwister, gerechnet über `decimal` (RM-187) |
| `expressions.py` | Parameterausdrücke über den **eigenen** Auswerter (§13, §32) — es gibt kein `eval` |
| `filament_usage.py` | Ausgabeumfang und Verbrauchsbedarf (§20, §29): stabile Vorbereitungsfingerabdrücke, explizite Spulenbindungen und werkzeugweise G-Code-Mengen; das Journal schreibt `knowledge/filaments.py` |

Bei gebundenen externen Filamentprofilen gelten Dichte und Durchmesser ohne
belegten Snapshot als unbekannt. Ein ausdrücklicher Filament-Override liefert
beide Kennwerte; direkte G-Code-Grammwerte benötigen keine Umrechnung.
Zusätzliche Werkzeuge des Slicers erhalten eigene ungebundene Bedarfzeilen.
Eine Werkzeugnummer beweist weder eine Materialart noch eine lokale Spule;
fehlende Einzelmengen bleiben auch bei bekannter Gesamtsumme unbekannt.

`filament_usage.costs_for` berechnet aus übergebenen Buchungspositionen und
Spulendaten ungerundete Kosten je Währung, ohne selbst Dateien zu lesen.
Fehlt ein nötiger Einzelwert, bleibt die gesamte Auswahl unbekannt. Ein
gespeicherter Nullpreis bleibt von fehlenden Preisangaben unterscheidbar.

Flächen- und Volumenanzeigen bewahren kleine Nichtnullwerte: Unter einem
Quadrat- beziehungsweise Kubikmillimeter wächst die Zahl der Nachkommastellen,
unter der Anzeigegrenze steht eine Schranke mit Vorzeichen statt null.
Die gemeinsame private Formatierung gilt ebenso in Zoll. Dies betrifft nur
den Text; Geometrie und Kennzahlen behalten ihre ungerundeten Werte.

`units.format_length_bound` formatiert numerische Längenschranken gerichtet:
untere Grenzen nach unten, obere nach oben, bereits bei der Umrechnung der
Anzeigeeinheit. Kleine Nichtnullwerte bleiben gegebenenfalls wissenschaftlich
lesbar. Diese Anzeige verändert weder die Rechnung noch ihre Toleranz;
`ui.labels.length_bound` ergänzt nur die sprachabhängige Zahlenschreibweise.

`paths.py` (wo Nutzerdaten liegen, §38 — und der kanonische Pfad hinter
einem offenen Handle: `opened_path`, geteilt von `scene/project` und
`updates`, weil beide daran eine Sicherheitsfrage hängen) · `discover.py` (installierte Programme
finden, die nicht im PATH stehen) · `install.py` (Fehlendes aus der Anwendung
heraus nachinstallieren, §36) · `network.py` (CA-Satz für macOS und Pakete ohne nutzbaren Vertrauensspeicher, etwa Flatpak) ·
`tools.py` (externe Programme) · `log.py`
(lokales Protokoll, §33.2)

`log.install_crash_logging()` wird ausdrücklich beim Prozessstart aufgerufen,
nicht beim Modulimport. `faulthandler` hält einen eigenen rohen Deskriptor bis
zum Prozessende; Logger-Rotation, Qt-Ende und Python-Abbau schließen ihn nicht.
Unbehandelte Haupt- und Nebenfadenfehler benutzen mit der CLI denselben
redigierten Bericht aus `report.exception_report()`, ohne Quellzeilen oder
lokale Variablen; der Fehlerbericht aus dem Fenster nimmt `report.crash_detail()`.
`log.redact_user_paths` setzt dabei für den Nutzerordner `~` (Stapel,
Ausnahmetext, Protokollanhang in `diagnostic_attachments`) — eine Installation
für den eigenen Nutzer liegt darunter (RM-231). Versionsauskunft liest geladene Module und Paketmetadaten,
ohne im Fehlerpfad native Bibliotheken nachzuladen.

Absturzdateien liegen unter den lokalen Protokollen. `paths.lock_file()` ist
die gemeinsame Lebensdauersperre für Wiederherstellung und Absturzprotokoll:
fünf beendete Läufe mit Absturz und zwei mit nur Abgefangenem bleiben
erhalten, lebende Prozesse bleiben unangetastet. Getrennt gezählt, weil ein
Grafiktreiber, der in jedem Lauf eine überlebte Ausnahme wirft, sonst jeden
Absturz verdrängte.
Leere beendete Dateien werden entfernt und sind kein Absturznachweis. Die
automatischen Berichte bleiben je Lauf auf fünf begrenzt; bewusst abgelegte
Berichte werden nicht aufgeräumt. `report.diagnostic_attachments()` erzeugt
einen begrenzten, unveränderlichen Schnappschuss aus normalem Protokoll,
vorhandenen Absturzstapeln und abgefangenen Ausnahmen (`abgefangen.txt`); die
Dateinamen stehen einmal in `log.REPORT_FILES`, weil drei Listen
auseinanderliefen und ein Anhang jeden Berichtsordner festhielt. Nach dem
geordneten Ende gilt eine Ausnahme nur als überlebt, wenn der Vermerk ihren
Faden nennt: den Faden des Endes oder einen, der da schon beendet war. Ein
noch laufender Faden zählt als Absturz — lieber ein falscher als ein
verlorener, denn ein sterbender Nebenfaden schreibt, während Windows den
Prozess noch nicht beendet hat. Versand bleibt ausschließlich eine
Nutzerhandlung.

Die Programmsuche bietet dieselben Quellen in Einzahl und Mehrzahl:
Windows-App-Paths, Flatpak-Exporte, Installationsordner, AppImages und den
Host-PATH. `find_programs()` sammelt jede passende Installation, während
`find_program()` beim ersten Treffer anhält. Gewählte Pfade werden gemeinsam
geprüft; dazu zählen auch macOS-App-Bundles und außerhalb des eigenen
Flatpak-Sandkastens liegende Host-Pfade. Erst nach dem Sammeln werden doppelte
Pfade und Startprogramme derselben Installation zusammengeführt. Jede
AppImage-Datei zählt dabei als eigene Installation, auch bei mehreren
Versionen im selben Ordner.

**Und die Kennung eines erzeugten Merkmals wird gelesen, nicht vorausgesagt.**
Sie entsteht bei der Auswertung (`evaluate._with_features` über
`perceive.matching.apply_mapping`), nicht beim Anlegen des
Schritts. Deshalb sind es dort zwei Aufrufe: `apply_counterpart` legt die
Geometrie an, `attach_fit` liest die Namen aus der gerechneten Szene und hängt
die Passung an dieselbe Transaktion.
**Und ein Gewinde bringt seine Hälfte mit** (P2.6, Entscheidung 15): Die
drei Paare setzen beide Hälften neu; ein eingelesener Bolzen oder ein
gedrucktes Gewinde hat seine schon. `thread_counterpart_draft` macht aus dem
vorhandenen Gewinde den einen Schritt — das gegengleiche Bausteingewinde am
anderen Teil, im **Tabellenmaß**, wo es eines trifft, sonst im eigenen Maß
(`thread_values_for`, Grenze `THREAD_SIZE_REACH` gegen die Normteiltabelle;
ein Gewinde Ø 6,4 mit Steigung 1,1 wird nicht still zu M6, sondern bekommt ein
Gegenstück Ø 6,4 × 1,1; bis zum 06.10.2026 nannte es die nächste Größe) —,
`apply_thread_counterpart` legt ihn an, `attach_thread_fit` hängt die
Gewindepassung zwischen dem vorhandenen und dem neuen an dieselbe
Transaktion. `_made_feature` nimmt dabei das **erzeugte** Merkmal des
Schritts, nicht das daneben erkannte: Am Netz liest die Erkennung über
denselben Gängen ein zweites, gemessenes Gewinde mit demselben Stamm.
Dieser Schritt muss beim Nachtragen weiterhin der letzte sein. Ein inzwischen
geänderter Verlauf bleibt unangetastet und bekommt einen erklärenden Befund.

`updates.py` (fragen, holen, prüfen, einspielen — angestoßen wird nur auf
Klick; **wie** eingespielt wird, entscheidet `install_kind()` und nicht die
Plattform) ·
`changes.py` (was neu ist) · `report.py` (Fehlerbericht als Ordner: schreibt,
sendet nie) · `support.py` (**der einzige Weg hinaus**, an einem Knopf) ·
`feedback.py` · `licence_service.py` (Online-Aktivierung und -Abmeldung, nur
nach ausdrücklichem Klick; der Freischaltzustand selbst bleibt vollständig
lokal)

`feedback.py` speichert unter `versions[branding.APP_VERSION]` in
`feedback.json` die aktive Nutzungszeit und den Einladungsstand. Jede
Demo-Version fragt nach 15 aktiven Minuten genau einmal, auch über Neustarts
hinweg. Antwort, Absage und bereits gezeigte Einladung gelten nur für diese
Version; der frühere globale Stand wird nicht übernommen. Bekannte Versionen
behalten ihren Stand auch beim Zurückwechseln. Im selben Versionsstand stehen
`deliveries` (erfolgreiche Exporte und Slicer-Starts, gezählt bis drei) und
`support_invited`: Die Einladung zur Unterstützung erscheint je Version einmal
nach dem dritten Erfolg, in Demo und Kaufversion gleich (`support_due`).

## Zwei Muster, die überall wiederkehren

*Früher unter „Zwei Muster, die überall wiederkehren“.*

**Und der Deadlock hat einen Grund, den die Karte lange nicht nannte: die
Pakete hängen im Kreis.** Acht der vierzehn Unterpakete stehen
in **einem** Kreis über eifrige Importe — `brep`, `geom`,
`ingest`, `knowledge`, `perceive`, `scene`, `sketch`, `slice`, mit `geom` als
Nabe. Weitere Kanten sind bewusst träge, also in eine Funktion gelegt,
damit sie den Kreis beim Import nicht schließen.
`tests/test_core_package_direction.py` friert diesen Stand ein — jede eifrige
und jede träge Kante einzeln aufgeführt; wie viele es sind, sagt der Test und
nicht diese Karte, denn die Zahl hier war zweimal hintereinander veraltet.
Eine neue Kante ist damit eine
Entscheidung und keine stille Zeile, eine abgebaute verschwindet auch aus der
Liste, und ein Paket, das neu in den Kreis gerät, macht den Lauf rot.


## Verbrauchskennung mit unbekannten früheren Werten

Ein additiv gespeicherter Druckwert darf einen unveränderten alten Druck nicht
automatisch zu einem weiteren Lagerabzug machen. `filament_usage.prepare`
lässt `adhesion.raft_gap` im Fingerabdruck weg, wenn der Wert unbekannt oder
der Raft durch eine ausdrückliche andere Haftungswahl sicher ausgeschaltet ist.
Eine automatische Haftungsart ist kein solcher Nachweis. Ein wirksamer
numerischer Raftwert bleibt Bestandteil der neuen Kennung.

`UsageRequest.legacy_fingerprint` trägt zusätzlich eine mögliche alte Kennung
ohne Raftwert. Sie belegt keine Gleichheit: Der frühere Abstand ist aus dem
alten Hash nicht rekonstruierbar. Sie wird weder als Alias ins Journal
geschrieben noch zur Umbindung oder Korrektur einer alten Buchung verwendet.
Eine vorhandene exakte neue Historie hat Vorrang, einschließlich ihrer
zurückgenommenen Vorgänge. Sonst verhindert eine passende alte Historie die
automatische Buchung und verlangt eine ausdrückliche Entscheidung.

Der automatische Buchungsweg übergibt neue und mögliche alte Historie aus
derselben Momentaufnahme als `expected_history` an `filaments.book`. Dessen
atomare Prüfung ist in der Langkarte von `app/core/knowledge/` beschrieben.
So kann eine konkurrierende Buchung zwischen Vorschlag und Schreiben keinen
zusätzlichen Abzug auslösen. Weder Journalformat noch gespeicherte
Vorgangskennungen ändern sich dafür.

## `paths.read_text_shared`: Lesen ohne Löschsperre

Unter Windows sperrt ein gewöhnlich geöffneter Lesegriff die Datei gegen Löschen
(kein `FILE_SHARE_DELETE`). Die Druckersuche (`first_run`, `discover_printers`)
liest Curas Definitionen aus der Kopie im Nutzer-Cache; leerte der Kunde oder ein
Aufräumprogramm den Cache in diesem Moment, scheiterte das Löschen mit WinError 32
(Fenstertest `test_after_a_cleared_cache_a_new_search_brings_curas_printers_back`,
unter Last zeitweise rot, 10.10.2026). `slicer_profiles` (JSON, INI, Material-XML
über `read_bytes_shared`) und `appimage` lesen ihre Dateien deshalb mit geteiltem
Löschen: Die Datei verschwindet, der Lesende behält seinen Griff bis zum Ende.
`kernel32` und der Prototyp von `CreateFileW` entstehen einmal je Prozess
(`_shared_kernel`); je Aufruf angelegt kostete das die kalte Druckersuche 16 bis
31 %. Belegt mit verlangsamtem Lesen: gewöhnliches Öffnen drei
von drei Läufen rot, geteiltes drei von drei grün.
