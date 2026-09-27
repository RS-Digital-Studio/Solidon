# `app/core/` — der kopflose Kern

Alles, was rechnet, nichts, was zeichnet: ohne installiertes Qt importierbar
(Regel 1). Einzuhalten sind `.claude/rules/kern.md` und `zwillinge.md`, beide
laden für jede Datei hier; diese Karte sagt, **was wo liegt**. Das Warum:
`konzepte/begruendungen/karte-app-core.md`.

## Die Unterpakete

| Paket | Beantwortet |
|---|---|
| `registry/` | Was kann die Anwendung? Das Register (§10) ist die eine Deklaration, aus der Menü, Dialog, Kommandozeile und Agentenwerkzeug entstehen |
| `scene/` | Was ist gerade offen? Szene, Op-Stapel, Auswertung, Projektdatei, Migrationen, Cache (§12–§16) |
| `geom/` | Wie entsteht Geometrie? Die Operationen gegen `manifold3d`/`trimesh`, die Boolesche Rückfallkette (§17.2, §25) |
| `sketch/` | 2D mit Zwangsbedingungen — Löser, Profile, Ebenen (§30.1) |
| `organizer/` | Maßlich gekoppelte Fächer, Einzelwände, Boden- und Montagebereiche aus einem gespeicherten Teilungsbaum (§13, §25) |
| `brep/` | Der zweite Kern (OpenCASCADE), optional; meldet sich ab, wenn er fehlt (§30) |
| `slice/` | Schichtanalyse und G-Code **lesen**, nie schreiben (§22) |
| `ingest/` | Einlesen, Einheitenerkennung, 3MF als Baugruppe (§17.1) |
| `perceive/` | Merkmalserkennung, stabile IDs, Analysekarten, Steckbrief (§21, §18.4, §23) |
| `knowledge/` | Profile, Normteile, Regelsammlung, Kalibrierung — und `parts/`, die Bausteinbibliothek (§24, §38, §39) |
| `agent/` | Die LLM-Schicht: Kontext, Werkzeuge, Vorschlag als eine Transaktion (§26) |
| `backends/` | LLM und Mesh-Erzeuger — extern, austauschbar, abschaltbar (§27) |
| `export/` | STL/3MF/OBJ/PLY/GLB/STEP, Plattenbelegung und Slicer-Übergabe (§29) |
| `activation/` | Freischaltung: Kaufcode, Geräte-Zertifikat, Demo- und optionale Testfrist |

## Die Module direkt hier

**Verträge und Zahlen** — was alle anderen benutzen:

| Datei | Rolle |
|---|---|
| `types.py` | Die Verträge (§9): `Mesh`, `Scene`, `SceneObject`, `OpContext`, `OpResult`, `Feature`, `Profile` — Signaturen stehen fest, bevor ein Modul entsteht. Die zwei Fragen, die an einem Merkmal nur einmal beantwortet werden: `is_a_cavity` und `thread_is_left_handed` (links heißt gesetzt, nativ gelesen oder an den Kanten gemessen; die Schätzung `fit` sperrt nicht) |
| `units.py` | Millimeter, doppelte Genauigkeit, die drei benannten Toleranzen (§11); `is_close`/`is_zero` statt `==`; Winkelfunktionen, die auf jeder Maschine dieselbe Zahl geben (`circle_point`, `inscribed_ratio`, `exact_cos`/`exact_sin`, über `decimal`); `format_length_bound` formatiert Schranken gerichtet (untere nach unten, obere nach oben) |
| `errors.py` | Die Ausnahmen-Hierarchie (§33.1); jede trägt mindestens eine `Action` |
| `expressions.py` | Parameterausdrücke über den **eigenen** Auswerter (§13, §32) — kein `eval` |
| `build_area.py` | Druckkontur, Sperrzonen, Druckhöhe und Auftragsrand für Anordnung, Orientierung und Ausgabe (§29); die Projektion eines geschlossenen Netzes kommt aus seinen Umrisskanten |
| `filament_usage.py` | Ausgabeumfang und Verbrauchsbedarf (§20, §29): Vorbereitungsfingerabdrücke, Spulenbindungen, werkzeugweise G-Code-Mengen; `costs_for` rechnet Kosten je Währung aus übergebenen Daten. Das Journal schreibt `knowledge/filaments.py` |

- **`Feature.measure_sources`** nennt je Parameter die Wertequelle (`native`,
  `facets`, `fit`, `parameter`); `measure_status(feature, name)` liefert die
  Genauigkeitsauskunft, eine fehlende Quelle bleibt unbekannt — `provenance`,
  Erzeuger und Körperart ersetzen sie nicht. Der Wert steht nur in `params`.
- **`Feature.surface_patches`** trägt analytische Teilträger mit ihren
  ursprünglichen Dreiecksindizes; `SurfacePatch` enthält nur Zahlen, Vektoren,
  Indizes und Quelle, nie native Handles. Eine Maßvorgabe ist kein
  Trägernachweis.
- **Filamentbedarf**: Ohne belegten Snapshot sind Dichte und Durchmesser
  gebundener Profile unbekannt, ein Override liefert beide; zusätzliche
  Werkzeuge des Slicers bekommen eigene ungebundene Zeilen. Eine
  Werkzeugnummer beweist weder Materialart noch Spule; fehlt ein Einzelwert,
  bleiben Menge und Kosten der Auswahl unbekannt, ein gespeicherter Nullpreis
  bleibt unterscheidbar.
- **Anzeige kleiner Werte**: Flächen und Volumina unter einem Quadrat- bzw.
  Kubikmillimeter bekommen mehr Nachkommastellen, unter der Anzeigegrenze eine
  Schranke mit Vorzeichen statt null (auch in Zoll); nur der Text, nie die
  Rechnung. `ui.labels.length_bound` ergänzt nur die Zahlenschreibweise.

**Umgebung, Prozesse, Grenzen nach außen:**

| Datei | Rolle |
|---|---|
| `paths.py` | Wo Nutzerdaten liegen (§38); `opened_path` (kanonischer Pfad hinter einem offenen Handle, für `scene/project` und `updates`); `lock_file()` als Lebensdauersperre für Wiederherstellung und Absturzprotokoll |
| `log.py` | Lokales Protokoll (§33.2); `install_crash_logging()` beim Prozessstart, nie beim Import; `redact_user_paths` setzt `~` für den Nutzerordner |
| `discover.py` · `tools.py` · `install.py` | Installierte Programme außerhalb des PATH finden · externe Programme · Fehlendes aus der Anwendung nachinstallieren (§36) |
| `process.py` · `http.py` · `json_boundary.py` | Sichere Grenze für externe Prozesse (§32; `run_limited` beendet einen Prozess, der nach seinem gemeldeten Ergebnis nicht endet: `finished`, `linger`) · für kleine HTTP-Transporte (`apply_header_deadline`) · für JSON aus fremden Vertrauensräumen |
| `network.py` | CA-Satz für macOS und Pakete ohne nutzbaren Vertrauensspeicher (Flatpak) |

- **Absturz**: `faulthandler` hält einen eigenen rohen Deskriptor bis zum
  Prozessende. Haupt- und Nebenfadenfehler nehmen mit der CLI denselben
  redigierten Bericht (`report.exception_report()`, ohne Quellzeilen und
  lokale Variablen), das Fenster `report.crash_detail()`; die Versionsauskunft
  lädt im Fehlerpfad keine native Bibliothek nach. Fünf beendete Läufe
  bleiben, lebende Prozesse unangetastet, leere Dateien sind kein Beleg;
  automatische Berichte je Lauf höchstens fünf, bewusst abgelegte bleiben.
  `report.diagnostic_attachments()` ist ein begrenzter Schnappschuss —
  versandt wird nur auf Nutzerhandlung.
- **Programmsuche** in Einzahl und Mehrzahl über dieselben Quellen
  (App-Paths, Flatpak-Exporte, Installationsordner, AppImages, Host-PATH):
  `find_programs()` sammelt alle, `find_program()` hält beim ersten Treffer;
  zusammengeführt wird erst nach dem Sammeln, jede AppImage-Datei zählt
  einzeln.

**Abläufe, die mehrere Operationen bündeln** — `lid_flow.py` (Deckel
erzeugen) · `split.py` (Auto Split) · `generate.py` (Weg 3: Text oder Bild zu
einem Körper) · `counterpart.py` (beide Hälften einer Verbindung). Ein Ablauf
statt einer Op, weil eine Op ihre Szene nur liest (Regel 3) und die
Auswertung rein ist (§15.1): Die Schritte gehen in **eine** Transaktion, was
kein Schritt ist, reist als `DocumentChange` mit (§15.5).

- `split.py`: `protected_patches` macht aus den Kennungen in
  `Document.protected` die Punktwolken der Ebenenprüfung (§22.3); `bed_margin`
  ist der Rand beim Anordnen; `apply_planned` hängt Passungen eines im selben
  Lauf erneut geteilten Stücks um (`SplitPlan.connectors`) und schreibt jedem
  Schritt die erste Nummer seiner Stifte in `first_pin`.
- `counterpart.py`: **Die Kennung eines erzeugten Merkmals wird gelesen, nicht
  vorausgesagt** — sie entsteht bei der Auswertung (`evaluate._with_features`
  über `perceive.matching.apply_mapping`). Deshalb zwei Aufrufe:
  `apply_counterpart` legt an, `attach_fit` liest die Namen aus der Szene und
  hängt die Passung an dieselbe Transaktion; ein Undo nimmt alles.
  **Ein Gewinde bringt seine Hälfte mit**: `thread_counterpart_draft` setzt am
  anderen Teil das gegengleiche Bausteingewinde im **Tabellenmaß**
  (`thread_size_for`, Grenze `THREAD_SIZE_REACH` — Ø 6,4 × 1,1 wird nicht still
  M6, sondern nennt die nächste Größe), `apply_thread_counterpart` legt an,
  `attach_thread_fit` hängt die Gewindepassung an. `_made_feature` nimmt das
  **erzeugte** Merkmal, nicht das daneben erkannte zweite; der Schritt bleibt
  beim Nachtragen der letzte, ein geänderter Verlauf bekommt einen Befund.

**Dokumentation, ohne Qt gezeichnet** — `manual.py` (geschriebene Seiten,
Bildanleitungen und Referenz aus dem Register, gegliedert in fünf Teile über
`OUTLINE`; die erste Seite „Wo fange ich an?“ listet die Anleitungen aus
`guides.GUIDES`; `help_for` sagt F1, wo eine Operation erklärt ist;
`spacemouse_access_help`, USB-Regel nur bei bekannter
Hersteller-/Produktkennung) · `manual_search.py` (die Suche im Handbuch:
Rangfolge nach Titel, Kurzfassung, Stichwort und Text, Fundstelle je Seite;
Faltung, Trefferstärke und Kundenwörter aus `registry/search.py`) ·
`guides.py` (Bildanleitungen: Schritte, Sätze und die Namen der Ziele, auf
die ein Bild zeigt, dazu die Operationen, die eine Anleitung lehrt;
aufgenommen beim Release in der echten Oberfläche,
Konzept `konzepte/konzept-handbuch-2026-09.md`) · `figures.py`
(Abbildungskatalog, dazu je Anleitungsschritt ein Bildschirmfoto) ·
`drawing.py` (SVG; lange Beschriftungen umbricht `Canvas.wrapped`, der Text
bleibt vollständig im SVG) · `markup.py` (Markdown → HTML, nur die selbst
erzeugte Teilmenge) · `examples.py` · `tour.py` (Beispielprojekte und Touren).

**Kundenkontakt — der Weg hinaus** — `updates.py` (fragen, holen, prüfen,
einspielen, nur auf Klick; **wie**, entscheidet `install_kind()`, nicht die
Plattform) · `changes.py` (was neu ist) · `report.py` (Fehlerbericht als
Ordner: schreibt, sendet nie) · `support.py` (**der einzige Weg hinaus**, an
einem Knopf) · `licence_service.py` (Aktivierung und Abmeldung, nur nach
ausdrücklichem Klick) · `feedback.py`: Unter `versions[APP_VERSION]` in
`feedback.json` stehen aktive Nutzungszeit und Einladungsstand. Jede
Demo-Version fragt nach 15 aktiven Minuten genau einmal, auch über Neustarts;
Antwort, Absage und gezeigte Einladung gelten nur dieser Version. Dort stehen
auch `deliveries` (Exporte und Slicer-Starts, bis drei) und
`support_invited`: Die Einladung zur Unterstützung kommt je Version einmal nach
dem dritten Erfolg, in Demo und Kaufversion (`support_due`).

**Technik** — `bootstrap.py` füllt das Register · `lazy.py` (siehe unten) ·
`deferred.py` hält `trimesh`/`scipy`/`networkx` bis zum ersten wirklichen
Rechenschritt aus dem Kundenstart heraus.

## Zwei Muster, die überall wiederkehren

**1. Lazy-Import in den Paket-`__init__.py`.** `scene`, `registry`, `agent`,
`brep` exportieren über `_EXPORTS` und `app.core.lazy.install()` — gegen einen
Deadlock: Zwei Threads, die gleichzeitig importieren, verklemmen sich sonst
über die Modul-Locks. Ein neuer Name steht an **drei** Stellen
(`TYPE_CHECKING`-Block, `_EXPORTS`, `__all__`); `tests/test_lazy_exports.py`
hält sie zusammen. Der Grund des Deadlocks: **Acht Unterpakete hängen über
eifrige Importe im Kreis** — `brep`, `geom`, `ingest`, `knowledge`,
`perceive`, `scene`, `sketch`, `slice`, mit `geom` als Nabe; weitere Kanten
sind bewusst träge. `tests/test_core_package_direction.py` friert jede Kante
ein (die Zahl sagt der Test, nicht diese Karte): Eine neue ist eine
Entscheidung, ein Paket, das neu in den Kreis gerät, macht den Lauf rot.

**2. Der `OpContext` ist die einzige Tür nach außen.**

| Feld | Bedeutung |
|---|---|
| `ctx.scene` | **Nur lesend** — Ops erzeugen Objekte, sie ändern keine |
| `ctx.inputs` | Die ausgewählten Objekte |
| `ctx.params` | Validiert gegen das Schema |
| `ctx.profile` | Drucker und Material — **hier stehen die Toleranzen** |
| `ctx.quality` | `draft` oder `fine`: beide Stufen bedienen |
| `ctx.seed` | Bei Zufall Pflicht, dazu `deterministic=False` |
| `ctx.progress` | Fortschritt melden |
| `ctx.ask` | Fragen statt raten (Regel 21) |
| `ctx.cancelled` | Kooperativer Abbruch |
| `ctx.sources` | Zugriff auf die Quelldateien, wenn eine Op sie braucht |

Was eine Operation zurückgibt, ist ein `OpResult`, nie eine veränderte
Eingabe. Die Grenzen des Kerns (kein Qt, kein `print`, keine
Toleranzkonstante, kein `eval`, keine absoluten Pfade) stehen in `AGENTS.md`
und `kern.md`.
