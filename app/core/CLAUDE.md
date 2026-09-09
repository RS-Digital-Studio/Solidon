# `app/core/` — der kopflose Kern

Alles, was rechnet, nichts, was zeichnet. Der Kern muss auf einem Rechner ohne
installiertes Qt importierbar bleiben.

Die Regeln dieses Gebiets stehen in `.claude/rules/kern.md` und laden sich
selbst. Hier steht, **was wo liegt**.

## Die Unterpakete

| Paket | Beantwortet |
|---|---|
| `registry/` | Was kann die Anwendung? Das Register (§10) ist die eine Deklaration, aus der Menü, Dialog, Kommandozeile und Agentenwerkzeug entstehen |
| `scene/` | Was ist gerade offen? Szene, Op-Stapel, Auswertung, Projektdatei, Migrationen, Cache (§12–§16) |
| `geom/` | Wie entsteht Geometrie? Die Operationen gegen `manifold3d`/`trimesh`, die Boolesche Rückfallkette (§17.2, §25) |
| `sketch/` | 2D mit Zwangsbedingungen — Löser, Profile, Ebenen (§30.1) |
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
| `types.py` | Die Verträge (§9): `Mesh`, `Scene`, `SceneObject`, `OpContext`, `OpResult`, `Feature`, `Profile`. Signaturen stehen fest, bevor ein Modul entsteht |
| `build_area.py` | Tatsächliche Druckkontur, Sperrzonen, Druckhöhe und Auftragsrand für Anordnung, Orientierung und Ausgabe (§29) |
| `errors.py` | Die Ausnahmen-Hierarchie (§33.1). Jede trägt mindestens eine `Action` — ein Fehler endet nie mit „fehlgeschlagen" |
| `units.py` | Millimeter, doppelte Genauigkeit, die drei benannten Toleranzen (§11). Fließkommavergleich über `is_close`/`is_zero`, nie mit `==` |
| `expressions.py` | Parameterausdrücke über den **eigenen** Auswerter (§13, §32) — es gibt kein `eval` |
| `filament_usage.py` | Ausgabeumfang und Verbrauchsbedarf (§20, §29): stabile Vorbereitungsfingerabdrücke, explizite Spulenbindungen und werkzeugweise G-Code-Mengen; das Journal schreibt `knowledge/filaments.py` |

Bei gebundenen externen Filamentprofilen gelten Dichte und Durchmesser ohne
belegten Snapshot als unbekannt. Ein ausdrücklicher Filament-Override liefert
beide Kennwerte; direkte G-Code-Grammwerte benötigen keine Umrechnung.
Zusätzliche Werkzeuge des Slicers erhalten eigene ungebundene Bedarfzeilen.
Eine Werkzeugnummer beweist weder eine Materialart noch eine lokale Spule;
fehlende Einzelmengen bleiben auch bei bekannter Gesamtsumme unbekannt.

Flächen- und Volumenanzeigen bewahren kleine Nichtnullwerte: Unter einem
Quadrat- beziehungsweise Kubikmillimeter wächst die Zahl der Nachkommastellen,
unter der Anzeigegrenze steht eine Schranke mit Vorzeichen statt null.
Die gemeinsame private Formatierung gilt ebenso in Zoll. Dies betrifft nur
den Text; Geometrie und Kennzahlen behalten ihre ungerundeten Werte.

**Umgebung und Nutzerdaten:**

`paths.py` (wo Nutzerdaten liegen, §38) · `discover.py` (installierte Programme
finden, die nicht im PATH stehen) · `install.py` (Fehlendes aus der Anwendung
heraus nachinstallieren, §36) · `network.py` (CA-Satz für macOS und Pakete ohne nutzbaren Vertrauensspeicher, etwa Flatpak) ·
`tools.py` (externe Programme) · `log.py`
(lokales Protokoll, §33.2)

**Abläufe, die mehrere Operationen bündeln:**

`lid_flow.py` (Deckel erzeugen) · `split.py` (Auto Split als eine Transaktion)
· `generate.py` (Weg 3: Text oder Bild zu einem Körper) · `counterpart.py`
(beide Hälften einer Verbindung auf zwei Körpern)

**Warum ein Ablauf und keine Operation**, bei allen vieren aus demselben
Grund: Eine Op bekommt ihre Szene nur lesend (Regel 3), und die Auswertung ist
eine reine Funktion (§15.1) — sie darf keine Passung und keinen Parameter ins
Dokument schreiben, sonst käme bei jedem Neurechnen einer dazu. Der Ablauf legt
seine Schritte in **eine** Transaktion, und was kein Schritt ist, reist als
`DocumentChange` in derselben mit (§15.5). Bei `counterpart.py` sind das zwei
Bausteinschritte und die Passung dazwischen; ein Undo nimmt alles drei.

**Und die Kennung eines erzeugten Merkmals wird gelesen, nicht vorausgesagt.**
Sie entsteht bei der Auswertung (`evaluate._renamed`), nicht beim Anlegen des
Schritts. Deshalb sind es dort zwei Aufrufe: `apply_counterpart` legt die
Geometrie an, `attach_fit` liest die Namen aus der gerechneten Szene und hängt
die Passung an dieselbe Transaktion.

**Dokumentation, ohne Qt gezeichnet:**

`manual.py` (Handbuch: geschriebene Seiten plus Referenz aus dem Register) ·
`figures.py` (Abbildungskatalog) · `drawing.py` (SVG: Maßlinien, Schemata,
Netzprojektion) · `markup.py` (Markdown → HTML, nur die selbst erzeugte
Teilmenge) · `examples.py` · `tour.py`

**Kundenkontakt — der Weg hinaus:**

`updates.py` (fragen, holen, prüfen, einspielen — angestoßen wird nur auf
Klick; **wie** eingespielt wird, entscheidet `install_kind()` und nicht die
Plattform) ·
`changes.py` (was neu ist) · `report.py` (Fehlerbericht als Ordner: schreibt,
sendet nie) · `support.py` (**der einzige Weg hinaus**, an einem Knopf) ·
`feedback.py` · `licence_service.py` (Online-Aktivierung und -Abmeldung, nur
nach ausdrücklichem Klick; der Freischaltzustand selbst bleibt vollständig
lokal)

**Technik:** `bootstrap.py` füllt das Register · `lazy.py` verhindert
Import-Deadlocks zwischen Kernpaketen (siehe unten) · `deferred.py` hält
`trimesh`/`scipy`/`networkx` bis zum ersten wirklichen Rechenschritt aus dem
Kundenstart heraus

## Zwei Muster, die überall wiederkehren

**1. Lazy-Import in den Paket-`__init__.py`.** `scene`, `registry`, `agent`,
`brep` exportieren ihre Namen über ein `_EXPORTS`-Wörterbuch und
`app.core.lazy.install()`. Der Grund ist kein Startzeitgewinn, sondern ein
Deadlock: Zwei Threads, die gleichzeitig importieren, verklemmen sich sonst
über die Modul-Locks. Wer einen Namen hinzufügt, trägt ihn an **drei** Stellen
ein — `TYPE_CHECKING`-Block, `_EXPORTS`, `__all__`.
`tests/test_lazy_exports.py` hält die drei zusammen und prüft, dass jeder
Eintrag auf ein Untermodul und ein Attribut zeigt, das es gibt.

**Und der Deadlock hat einen Grund, den die Karte lange nicht nannte: die
Pakete hängen im Kreis.** Gemessen am 07.09.2026 stehen acht der dreizehn
Unterpakete in **einem** Kreis über eifrige Importe — `brep`, `geom`,
`ingest`, `knowledge`, `perceive`, `scene`, `sketch`, `slice`, mit `geom` als
Nabe. Dreizehn weitere Kanten sind bewusst träge, also in eine Funktion gelegt,
damit sie den Kreis beim Import nicht schließen.
`tests/test_core_package_direction.py` friert diesen Stand ein: 47 eifrige und
13 träge Kanten, jede einzeln aufgeführt. Eine neue Kante ist damit eine
Entscheidung und keine stille Zeile, eine abgebaute verschwindet auch aus der
Liste, und ein Paket, das neu in den Kreis gerät, macht den Lauf rot.

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

Kein globales Objekt, kein Logger, der etwas anzeigt, kein Dialog. Was eine
Operation zurückgibt, ist ein `OpResult` — nie eine veränderte Eingabe.

## Grenzen

- **Kein `PySide6`, kein Qt, kein `print`, kein `input`.**
- **Keine Zahlenkonstante für Toleranzen** — Verweis ins Materialprofil
  (`auto:<material>`).
- **Kein `eval`, kein fremder Quelltext** (Regeln 10 und 11).
- **Keine absoluten Pfade** in Projektdateien.
