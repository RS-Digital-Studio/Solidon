# Oberflächendurchsicht 19.08.2026 — angehalten, Stand zum Weitermachen

Auftrag: alles gründlich durchgehen mit Blick auf Bedienbarkeit, Funktionen,
Übersichtlichkeit und modernes Aussehen — **auch das, was schon einmal
kontrolliert wurde**. Alle Funde beheben, egal wie klein. Randbedingung:
**morgen, am 20.08.2026, soll die Demo auf der Webseite bereitstehen.**

Zwei Vorgaben, die unterwegs dazukamen: **mit Workflows arbeiten**, und **die
Gegenprüfung auslassen** — die Funde kommen roh, geprüft wird beim Beheben am
Code.

---

## ⚠ Zuerst lesen: drei Tests sind rot

Von meiner eigenen Änderung, bekannt und eingegrenzt. Der Basislauf **vor** der
Arbeit war grün (`pytest -m "not performance"`, exit 0).

`reset_camera` passt jetzt mit Luft ein (`CAMERA_MARGIN`, `with_margin`) und
rechnet den Bauraum für die leere Szene **selbst**, statt pyvista alle Aktoren
suchen zu lassen. Drei Tests in `tests/test_analysis_ui.py` prüfen genau den
alten Mechanismus:

| Test | erwartet heute | müsste erwarten |
|---|---|---|
| `test_fitting_tells_pyvista_that_it_is_done:841` | `fitted_to == [viewport._object_bounds()]` | `[with_margin(viewport._object_bounds())]` |
| `test_an_empty_scene_still_fits_on_something:854` | `fitted_to == [None]` | `[with_margin(viewport._volume_bounds())]` |
| `test_a_new_project_puts_the_build_volume_in_the_picture:882` | `fitted_to == [None]` | dasselbe |

Das ist keine Regression, sondern die Absicht der Änderung: `bounds=None` hieß
„pyvista passt auf alle Aktoren ein", und genau das war der Grund, dass die
Platte hinter der Werkzeugzeile verschwand. **Erster Schritt beim
Weitermachen:** die drei Zusicherungen nachziehen, dann
`pytest -m "not performance"` ganz durchlaufen lassen.

**Fremde Änderungen im Baum:** `konzept-*.md` (fünf Dateien) sind **nicht von
mir** — die stammen aus der parallel laufenden Konzeptdurchsicht
(`.claude/.state/konzept-durchsicht-2026-08-19/`, Punkt B „Redaktion je
Datei"). Nicht anfassen, nicht mitcommitten.

---

## Behoben, jeder mit Test und Messung

| Fund | Änderung | Beleg |
|---|---|---|
| Raster der Zeichenfläche unsichtbar (Kontrast 1,02) | `grid_minor`/`grid_major` in `THEMES`, als `Midlight`/`Mid` in die Palette; im Zeichnen ohne Alpha, **ohne Kantenglättung, auf halbe Pixel gelegt** | gemessen am gerenderten Bild: dunkel **1,60/2,59**, hell **1,35/2,00**, scharfe Einzelpixel-Linien statt zweier halber Spalten |
| Gesperrter Regler trug den vollen Akzent | `Disabled`-Gruppe bekommt `Highlight` | Regler: **404 → 0** bernsteinartige Punkte |
| Gesperrter Fortschrittsbalken ebenso | `QProgressBar::chunk:disabled` im Stylesheet — die Palette allein reicht nicht, ein Stylesheet gewinnt gegen sie | Balken: **2998 → 0** (dunkel), **3001 → 0** (hell) |
| „0" der Plattenskala lag in der Ecke, Zahlen ohne Vorzeichen | `bed_scale` gibt je Kante eine eigene, vorzeichenbehaftete Skala | im Bild nachgesehen: −100 … 0 … 100, Null in der Kantenmitte |
| Kamera passte ohne Luft ein | `CAMERA_MARGIN = 0.12`, `with_margin`, leere Szene über `_volume_bounds` | Quader berührt den Bildrand nicht mehr, Platte vollständig im Bild |
| Vier Werkzeuge öffneten untätig | `Tool.start`, in `activate()` beim Öffnen gerufen; Schnitt → Z, Messen → Abstand, Bewegen → Gizmo an. *Analyse* bewusst nicht (eine Karte kostet Rechenzeit, ihr Hinweis sagt „Karte wählen") | — |
| Tour kürzte vier von fünf Schritten | `set_wrapped(True)` für alle; der Bereich liegt in einer `QScrollArea` | — |
| „2 × Teile" | Malzeichen weg | — |
| Handbuchbild zeigte 200 Punkte Totraum, den es nicht gibt | `prepared(..., fit_height=True)` in `make_figures` | Dialoge sind 143–427 Punkte hoch, gemessen |
| Qts Sprachkataloge fehlten im Paket | sechs `qtbase_*.qm` in `datas`, Sprachen aus dem Katalogverzeichnis, `de` dazu, mit Varianten gesucht (`pt` liegt nur als `pt_BR` vor) | zwei neue Tests in `test_packaging.py` |

Neue Tests: `test_the_drawing_grid_is_visible_without_shouting`,
`test_the_grid_reaches_the_canvas_through_the_palette`,
`test_a_locked_surface_loses_the_accent_too`,
`test_a_locked_progress_bar_gives_up_the_accent` (Referenzvergleich am Bild),
`test_the_bed_scale_signs_its_numbers_and_puts_zero_in_the_middle`,
`test_what_is_fitted_gets_air_around_it`,
`test_the_package_carries_qts_own_catalogues`,
`test_qt_has_a_catalogue_for_every_language_we_offer`.

---

## Die Funde der Durchsicht — 234 Stück, roh

In `durchsicht-teilergebnisse.json`. **Ungeprüft**: jeder ist vor dem Beheben
einmal am Code zu halten. Erfahrungswert: etwa jeder fünfte stirbt daran, und
zwei meiner eigenen sind es auch (siehe `befunde/eigene-funde.md`, Abschnitt
„Zwei Behauptungen, die an der Gegenprüfung gestorben sind").

**Erster Lauf (`wf_8bc868ec-2aa`), 176 Funde aus 11 Läufen / 8 Gebieten** —
Texte (3×), Entdeckbarkeit (2×), Dialoge (2×), Startbildschirm, Hauptfenster,
Demo-Reife, Designsystem. Mehrfach gefahrene Gebiete: die vollständigere
Fassung nehmen.

**Zweiter Lauf (`wf_383919eb-f13`), 58 Funde aus 3 Gebieten** — Kommandozeile
(24), Beispielprojekte (20), Tastenkürzel (14).

**Noch offen, nie gelaufen:** `druckdialog` · `chat` · `skizze` · `viewport` ·
`webseite` · `barrierefreiheit` · `wartezeit` (erster Lauf) und `handbuch`
(zweiter Lauf). Beide Skripte liegen in `workflow-skripte/` und sind ohne
Prüfstufe; die Gebietsliste `AREAS` auf die offenen kürzen und starten.

---

## Meine eigenen Funde

`befunde/eigene-funde.md` — an der laufenden Oberfläche gemessen, nicht aus dem
Code geschlossen. Zehn große, ein Dutzend kleine, dazu die zwei Fehlalarme mit
ihrer Ursache. **Zehn davon sind jetzt behoben** (Tabelle oben); offen bleiben
aus dieser Mappe:

* Katalog zeigt 4 von 19 Bausteinen (Kachel 164×190 für ein 96er Bild)
* leerer Chat: 350 Punkte Loch, Beispiele darunter
* Generierungsdialog sagt, was fehlt, und bietet nichts an
* Prüfbericht ohne Befunde: Suchfeld, Filter, leerer Kasten
* Statuszeile: Gewicht und Druckzeit ohne Bezeichnung neben dem Demo-Hinweis
* Bemalen zeigt „Slot 1" statt der Farbe
* Trennen-Bereich mit 130 Punkten Totraum
* Druckdialog: leerer Rahmen unter „Weitere Einstellungen", gesperrte Gruppe
  „Profile des Slicers", Ankreuzfeld statt Dreieck
* Typografie-Skala in 21 von 30 Oberflächendateien nie benutzt
* Skizzenleiste: rohe Punktnummern „(1, 2)", Maße ohne Einheit, zwei
  unbeschriftete Zahlenfelder
* `BaseParams.fields()` bricht bei einer Operation ohne Parameterklasse

## Aufnahmen

47 Dateien plus die Nachher-Bilder in `aufnahmen/`, dazu die Skripte. Für jede
weitere Aufnahme: `QScreen.grabWindow(window.winId())` statt `QWidget.grab`
(OpenGL), und `load_operations()` vor `build_application()`.

## Angehaltene Läufe

| Lauf | Run-ID | Stand |
|---|---|---|
| Breite Durchsicht, ohne Prüfstufe | `wf_8bc868ec-2aa` | 8 von 14 Gebieten gesichert |
| Zweite Durchsicht, ohne Prüfstufe | `wf_383919eb-f13` | 3 von 4 Gebieten gesichert |

`resumeFromRunId` geht nur in derselben Sitzung; sonst die Skripte neu starten.

## Die Demo für morgen

Unverändert die Kette aus der ersten Fassung dieser Datei — und sie hängt nicht
an der Oberfläche:

1. Die Webseite steht auf Vorankündigung: **20 mailto-Stellen in sechs
   Sprachen** (`website/index.html` fünfmal, je dreimal in `en es fr it pt`).
2. Es gibt **keine gebaute Datei**. Lokal fehlen PyInstaller (in keinem Extra
   von `pyproject.toml`), Inno Setup 6 und `packaging/build` mit dem
   kompilierten Prüfmodul.
3. Der CI-Paketjob hat `needs: suite` und kommt hinter der roten Linux-Suite
   nicht heran. Ansatzpunkt: die CI sucht Fensterdateien mit
   `grep -l "MainWindow"`, aber **acht Dateien bauen einen `Viewport`, ohne
   `MainWindow` zu nennen** und laufen im großen Stapel mit — und der Absturz
   hängt laut Kommentar an der Zahl der VTK-Fenster je Prozess.
4. Qts Sprachkataloge im Paket sind **erledigt** (siehe oben).

Entscheidungen, die dem Menschen gehören: PyInstaller und Inno Setup 6
installieren, einen Tag setzen, unsigniert veröffentlichen.
