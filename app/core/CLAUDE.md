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
| `errors.py` | Die Ausnahmen-Hierarchie (§33.1). Jede trägt mindestens eine `Action` — ein Fehler endet nie mit „fehlgeschlagen" |
| `units.py` | Millimeter, doppelte Genauigkeit, die drei benannten Toleranzen (§11). Fließkommavergleich über `is_close`/`is_zero`, nie mit `==` |
| `expressions.py` | Parameterausdrücke über den **eigenen** Auswerter (§13, §32) — es gibt kein `eval` |

**Umgebung und Nutzerdaten:**

`paths.py` (wo Nutzerdaten liegen, §38) · `discover.py` (installierte Programme
finden, die nicht im PATH stehen) · `install.py` (Fehlendes aus der Anwendung
heraus nachinstallieren, §36) · `network.py` (CA-Satz im macOS-Paket) ·
`tools.py` (externe Programme) · `log.py`
(lokales Protokoll, §33.2)

**Abläufe, die mehrere Operationen bündeln:**

`lid_flow.py` (Deckel erzeugen) · `split.py` (Auto Split als eine Transaktion)
· `generate.py` (Weg 3: Text oder Bild zu einem Körper)

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

**Technik:** `bootstrap.py` füllt das Register · `lazy.py` siehe unten

## Zwei Muster, die überall wiederkehren

**1. Lazy-Import in den Paket-`__init__.py`.** `scene`, `registry`, `agent`,
`brep` exportieren ihre Namen über ein `_EXPORTS`-Wörterbuch und
`app.core.lazy.install()`. Der Grund ist kein Startzeitgewinn, sondern ein
Deadlock: Zwei Threads, die gleichzeitig importieren, verklemmen sich sonst
über die Modul-Locks. Wer einen Namen hinzufügt, trägt ihn an **drei** Stellen
ein — `TYPE_CHECKING`-Block, `_EXPORTS`, `__all__`.

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
