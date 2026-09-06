# V7: Darstellungsbefunde und abgegrenzte Gegenproben

Diese Notiz zählt nur Fälle mit `complete=true`, `closed=true`, tatsächlichem
Prozess-Exit 0 und gleichem `run_id` als abgeschlossene Abnahme. Die Quelle
dieser Bilder ist `final-source-v7`. Sie wird durch diese Arbeit nicht geändert.
VTK/18 und VTK/19 haben Exit 3221225477 (0xC0000005) und sind ausdrücklich
keine abgeschlossenen finalen Sichtprüfungen.

## Material, Licht und Körperkanten

Datei 01 (`drill-holder.3mf`), beide Renderer abgeschlossen:

- `final/vtk/file-01/theme-light.png` und `feature-00-hole.png`: unterbrochene
  helle/dunkle Bögen um mehrere obere Bohrungsränder, körnige Schattierung auf
  Körper und Bett. Die jeweils gleichnamigen GFX-Bilder zeigen glattere,
  durchgängigere Ränder und eine ruhigere Fläche.
- `final/vtk/file-01/analysis-overhang.png` zeigt weniger gestörte Ringe und
  keine entsprechende Bettkörnung. Dieser Pfad deaktiviert AO **und**
  Hüllenschatten und ändert Körperfarben. Er beweist keine einzelne Ursache.
- `final/gfx/file-01/mode-transparent.png` und das VTK-Gegenbild: die große
  orange vordere Fläche ist geschlossen; keine verstreuten schwarzen
  Mikrodreieckslücken sichtbar. `feature-03-face.png` markiert eine verdeckte
  Rückfläche; fehlendes Orange an der Vorderseite ist dabei kein Fehler.
- GFX `theme-light.png` in Originalauflösung: der kleine Beschriftungstext
  wirkt an einzelnen Glyphenkanten unruhiger als Qt-Text. Inhalt und Maße
  bleiben lesbar; daraus allein folgt weder Schriftverlust noch eine
  belastbare Fehlergrenze. Kein neuer optischer Patch aus diesem Eindruck.

Datei 13 (`tree_with_tray_stl.stl`), beide Renderer abgeschlossen:

- `final/vtk/file-13/theme-light.png`: deutlich wellige Bänder über Stamm,
  Ästen und Teller, breite horizontale Streifen auf dem sichtbaren Bett,
  unterbrochene dunkle Bögen an der Tellerkante. Das GFX-Gegenbild ist an
  diesen Stellen glatt. Dieser zweite Körper stärkt den Darstellungsbefund.
- Alte Konturstücke während des Körperzugs sind separat im Viewport
  eingegrenzt: `_edge_actors` folgten der Vorschau von `_actors` nicht.
  Zuständig ist der Viewport-Worker; das ist kein unspezifischer GFX-Netzfehler.

Datei 18 (`countercleaner.3mf`), nur GFX abgeschlossen:

- `final/gfx/file-18/theme-light.png`: ruhig schattierte große Flächen und
  klare Umrisse. `feature-03-face.png`: großflächige orange Markierung ohne
  das früher über die Fläche verstreute schwarze Sprenkelmuster. Kleine
  dunkle Stücke nahe dem Griff-/Flächenrand bleiben aus dem Einzelbild nicht
  eindeutig einer Ursache zuzuordnen. Die semantischen Klickabweichungen
  werden unabhängig von dieser Bildaussage ausgewertet.

Datei 19 (`carpet-corner-clip.step`), nur GFX abgeschlossen:

- `final/gfx/file-19/theme-light.png`, `feature-02-hole.png` und
  `feature-01-fillet.png`: durchgängige sichtbare Rundkanten, geschlossene
  Flächen und lesbare Maßtexte. Die Bohrungsmarkierung ist innen sichtbar;
  die verdeckte Verrundung trägt ihren Anker. Keine belegte neue Renderlücke.
- Der Körper liegt laut Prüfbericht 4,95 mm unter dem Bett; die dort
  durchscheinend gezeigte Geometrie gehört zu diesem Zustand. Das Bild ist
  deshalb kein Beleg für eine unbeabsichtigte doppelte Körperdarstellung.

## Statische Ursachenabgrenzung

Die Zeilen beziehen sich auf die eingefrorene V7-Quelle.

1. `vtk_renderer.py:1051`: VTK-SSAO mit 128 Stichproben und Blur;
   `viewport.py:1240–1250`: Radius 2 mm, Bias 0,01 mm. Der vorhandene Kommentar
   benennt bereits Selbstverdeckung/Streifen bei zu kleinem Bias. Das ist
   ein plausibler Zusammenhang, keine nachgemessene Ursache dieses Bilds.
2. `viewport.py:5108`: explizite Körperkanten entstehen ausschließlich im
   Modus `solid`, ohne `keep_in_front`. `vtk_renderer.py:add_lines` setzt
   den Polygonversatz nur bei `keep_in_front`. Normale koplanare Körperkanten
   besitzen daher keinen eigenen lokalen Tiefenbias. GFX hat diesen bereits.
   Eine spätere Korrektur muss Verdeckung erhalten, kein pauschales Vorziehen.
3. Doppelte Kanten sind im normalen Modus nicht der offensichtliche Pfad:
   VTK-`EdgeVisibility` gehört zu `solid_edges`, explizite Featurekanten
   ausschließlich zu `solid`.
4. `viewport.py:_place_shadows`: zusätzliche flache Hüllenschatten, Lift
   0,05 mm, Alpha im hellen Thema 0,03; das Bett liegt 0,2 mm tiefer. Breite
   polygonale Bodenschatten dürfen nicht pauschal AO zugeschrieben werden.

`vtk_visual_ab.py` öffnet das
gespeicherte Drillholder-Projekt aus einer manifestgeprüften Quelle und
zeichnet mit gleicher Kamera: Original, nur AO aus, nur Körperkanten aus,
nur Hüllenschatten aus, AO und Körperkanten aus, Original wiederhergestellt.
Native Fensterbilder, Sichtbarkeitslisten, Kamera, Quellen-/Projekt-SHA,
Schließstatus und der tatsächliche Prozessausgang bleiben im Ergebnis.

### Abgeschlossene VTK-A/B-Gegenprobe

`vtk-visual-ab-v7-2/result.json`: `complete=true`, `closed=true`, Quelle und
Projekt unverändert; Elternprozess Exit 0, rund 21 Sekunden. Gleiche Kamera,
Projektion und Canvasgröße 1600 × 897 in allen sechs Aufnahmen. Ein erster
Versuch (`vtk-visual-ab-v7`) endete kontrolliert mit Exit 1 vor den Bildern:
V7 hält Kanten noch als Liste, der Hauptbaum bereits als Dict. Der private
Helfer unterstützt nun beide Containerformen; der Fehlversuch bleibt erhalten.

- `02-only-ao-off.png`: Bettkörnung/-streifen verschwinden; Bohrungsringe
  werden durchgängig. Ein Körperkantenaktor und sämtliche 69 Hüllenschatten
  bleiben dabei aktiv. Der Hintergrundverlauf wird sichtbar.
- `03-only-edges-off.png`: Konturlinien verschwinden, Körnung und Bettstreifen
  bleiben bestehen. `04-only-shadows-off.png`: ebenfalls weiter gestörtes Bild.
- `05-ao-and-edges-off.png`: erwartungsgemäß glatte Flächen ohne Konturlinien.
- `01-original.png` und `06-original-restored.png` sind bytegleich:
  SHA-256 `9eb724386f3562cfabb461b88ef23f4ca7d0f9784f7e5a16f3ea7745f9005d51`.

Damit ist für diese Aufnahme der SSAO-Pfad als Ursache eingegrenzt.
Ein isolierter Kantenbiasfehler oder Hüllenschattenfehler erklärt das Muster
nicht. Ein neuer VTK-Linienbias wird aus dieser Aufnahme nicht abgeleitet.
Unter AO ist zusätzlich der Hintergrundverlauf verloren. Es wurde keine
GPU-Leistung gemessen und kein VTK-Produktcode dafür verändert.

### Nachfolgende Pass-/Bias-Gegenprobe

`vtk-ssao-pass-v7/process.json` belegt Run
`8e48fe5614bd4178973b528661990084`, tatsächlichen Exit 0 nach 21,7 Sekunden
unter dem gemeinsamen Gate. Der V7-Stand und das gespeicherte Projekt sind
vorher/nachher identisch gehasht; `complete` und `closed` sind wahr. Alle
sieben Bilder verwenden dieselbe Kamera und Projektion. Der eigene Pass
gibt seine Ressourcen vor dem Schließen im noch aktiven Kontext frei.

| Bild | Sichtbarer Unterschied |
|---|---|
| `01-built-in-original.png` | Korn, Bettstreifen und verlorener Verlauf reproduziert |
| `02-built-in-precision-bias.png` | Bias 0,5 mm beseitigt Korn/Bettstreifen; Verlauf bleibt einfarbig |
| `03-explicit-original-bias.png` | Innerer Kamerapass stellt den Verlauf wieder her; Korn/Bettstreifen bleiben |
| `04-explicit-precision-bias.png` | Beide belegten Verbesserungen gemeinsam, Vertiefungs- und Kontaktdunkelheit bleibt |
| `05-explicit-double-precision-bias.png` | Bias 1 mm bringt an den verbleibenden Konturen keine klare Verbesserung |
| `06-only-ao-off.png` | Saubere Konturen als Referenz ohne Verdeckungseffekt |
| `07-built-in-original-restored.png` | Bytegleich mit 01 und dessen oben genanntem SHA-256 |

**Offen:** Die Bohrungs- und Schriftkanten wirken in 04 weiterhin deutlich
ausgefranst gegenüber 06. Dies ist weder durch den neuen Pass noch durch
Biasverdopplung behoben. Linien im AO-Geometriepuffer und dessen
Rasterbedingungen werden getrennt eingegrenzt. Kantenversatz oder
pauschales Vornezeichnen wurden nicht daraus abgeleitet.

Die unabhängige statische Gegenprüfung grenzt den Kandidaten ein:
`_draw_feature_edges` liefert koplanare `vtkPolyData`-Linien ohne
Punktnormalen, Beleuchtung oder Polygonoffset. Sie nehmen am deckenden
AO-Pfad teil. `vtkSSAOPass::PostReplaceShaderValues` schreibt bei fehlendem
`normalVCVSOutput` eine Nullposition und Nullnormale (9.6.2, Zeilen 631–632);
`RenderSSAO` prüft deren Gültigkeitsalpha nicht. Ob genau diese Variante für
die Produktlinien kompiliert ist, bleibt ungeprüft. Der AO-Puffer verwendet
außerdem gewöhnliche `Allocate2D`-Texturen ohne Multisampling; daraus wird
allein keine bewiesene Ursache abgeleitet. `vtk_visual_ab.py --ssao-edge-probe`
bereitet eine getrennte Kanten-ein/aus-Gegenprobe im neuen Pass vor und ist
zu diesem Berichtspunkt noch nicht ausgeführt.

VTK 9.6.2 legt den Kamerapositionspuffer auf RGBA16F fest. Bei der gemessenen
Fernebene 901,66 mm ist die Abstandsstufe 0,5 mm; der ursprüngliche Bias
0,01 mm liegt darunter. Ein `CameraPass` innerhalb des SSAO-Delegaten
zeichnet dagegen den Verlauf direkt in dessen Farbpuffer. Das sind zwei
getrennte, im A/B einzeln belegte Ursachen. VTK 9.7.0 hat ebenfalls keine
öffentliche Formatwahl für diesen Positionspuffer
([Header](https://raw.githubusercontent.com/Kitware/VTK/v9.7.0/Rendering/OpenGL2/vtkSSAOPass.h),
[Implementierung](https://raw.githubusercontent.com/Kitware/VTK/v9.7.0/Rendering/OpenGL2/vtkSSAOPass.cxx)).
Die begrenzte Pass-/Biasintegration liegt danach im Hauptbaum; ihre neuen
Bildregressionen sind zu diesem Berichtspunkt noch nicht ausgeführt.

## GFX: Beschriftungskosten aus vorhandenen Daten

Die Navigation misst die Zeit bis zum abgeschlossenen Bild inklusive
CPU-Arbeit und Synchronisationsaufwand, keine isolierte GPU-Zeit und keine
physische Bildschirmabtastung. 40 Navigations- und 12 Beschriftungsbilder
sind kurze Stichproben, kein Langzeitbudget.

| V7-Fall | Navigation Median / p95 ms | Alle Merkmalslabels Median / p95 ms |
|---|---:|---:|
| Drillholder GFX | 13,34 / 14,44 | 38,86 / 53,10 |
| Drillholder VTK | 13,11 / 16,30 | 19,69 / 23,91 |
| Baum GFX | 7,30 / 9,85 | 12,94 / 16,06 |
| Baum VTK | 11,91 / 14,71 | 13,87 / 15,81 |
| Countercleaner GFX | 7,93 / 10,55 | 23,02 / 34,76 |
| Carpet-corner-clip GFX | 39,88 / 41,78 | 60,68 / 68,81 |

Der STEP-Fall braucht im Modus `solid` 40,50 ms, `wireframe` 43,12 ms,
in den Analysekarten ohne AO etwa 37 ms, `transparent` dagegen 8,96 ms.
Das ist ein eigener Leistungsbefund neben den Beschriftungskosten; die
Ursache ist noch nicht profiliert. Seine Navigationsmessung protokolliert
rund 12,17 % geschätzte CPU-Hintergrundlast über 32 logische Prozessoren.

Der Drillholder trägt 157 Kandidaten/Marker gegen 21 beim separat profilierten
Peg, also rund 7,5-mal so viele Ankerprojektionen. Im vorhandenen
Gestenprotokoll sind 17–19 sichtbare Texte mit 352–392 Zeichen protokolliert;
beim Peg-Orbit waren es 11–13 Texte mit 242–297 Zeichen. Gesten- und
Orbitzustände sind nicht identisch. Der Vollprobelauf protokolliert keine
GFX-Buildanzahl je Orbitbild; daraus wird keine solche Anzahl erfunden.

Konkreter statischer Anschluss: `GfxRenderer._sync_camera` rief bei jeder
Projektion `Camera.set_view_size` auf. In der installierten pygfx-Version
invalidiert dieser Aufruf die Kameramatrizen auch bei gleicher Größe. Der
enge Guard im Hauptbaum synchronisiert nur geänderte Größen; Bewegungen
und Projektionsänderungen bleiben pygfx-eigene Invalidierungen. Der gesamte
GFX-Regressionstest ist danach mit 38 Tests in 3,14 Sekunden und tatsächlichem
Exit 0 grün; Ruff, Format, mypy und Diffprüfung ebenfalls. Eine neue
Leistungsmessung dieses Guards steht noch aus.

## VTK/Counter: abweichende Zielzelle

Im abgebrochenen VTK/18-Lauf ist der semantische Befund vor dem Abbruch
protokolliert, aber der Gesamtfall ist nicht abgeschlossen. Pixel (676,499):
CPU-Originalzelle 44330 (`face_6`, baryzentrischer Randabstand 0,327) gegen
VTK-Zelle 185790 (`face_2`). Oracle und Pick verwenden identisch
`display_to_world`/`_flip(y)=height−1−y`; ein einseitiger y-Versatz ist im
Adaptercode nicht belegt.

Die Produkttoleranz 0,005 wird direkt an `vtkCellPicker` übergeben. VTK rechnet
sie in einen Weltabstand um und gibt diesen an den Dreiecksschnitt weiter;
die Wahl bevorzugt nahe Kandidaten innerhalb der Toleranz. Eine knapp
verfehlte Vorderwand kann deshalb vor der exakten hinteren Fläche gewinnen.
Der große baryzentrische Innenabstand der hinteren Fläche schließt diesen
Fall nicht aus. Nächster enger Nachweis: derselbe Zustand und Pixel mit
Toleranz 0 sowie 0,005, Rückprojektion beider Treffer, Originalstrahl.
Quelle: [vtkPicker.cxx, VTK 9.6.2](https://github.com/Kitware/VTK/blob/v9.6.2/Rendering/Core/vtkPicker.cxx#L455),
[vtkCellPicker.cxx, VTK 9.6.2](https://github.com/Kitware/VTK/blob/v9.6.2/Rendering/Core/vtkCellPicker.cxx#L649).
