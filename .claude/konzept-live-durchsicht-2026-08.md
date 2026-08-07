# Konzept — was die Live-Durchsicht gegen Fusion und den ElegooSlicer ergeben hat

Datum: 5. August 2026. Geprüft wurde die laufende Anwendung gegen die beiden
Programme, die auf dieser Maschine installiert sind und die Roberts Arbeit
tatsächlich einrahmen: **Autodesk Fusion 2704.1.36** als Maßstab fürs
Konstruieren und **ElegooSlicer 1.5.3.4** als Empfänger des Ergebnisses.
Nicht die Suite, nicht der Quelltext — die Programme selbst, mit Zahlen aus
beiden.

Ausgangslage: `pytest -m "not performance"` grün, 2756 Tests in 267 s.

Bezug: Bauplan §11 (Zahlen), §17 (Eingangsstufe), §21 (Wahrnehmung), §25
(Operationen), §28 (Rückkopplung), §29 (Export und Übergabe), §30 (zweiter
Kern), §2.7 (Fehler als Vorschlag), §18.5 (Kontextmenü am Merkmal),
AGENTS.md Regel 6, 14, 17.

---

## 1. Was die Prüfung getragen hat

Damit die Befundliste nicht falsch gelesen wird — drei Dinge sind stärker,
als sie im Repository klingen:

**Der STEP-Weg ist bitgenau.** Ein exakter Zylinder Ø 50 × 40 aus Solidon,
in Fusion geladen:

| | Formel | Solidon | Fusion |
|---|---|---|---|
| Volumen | 78539,81634 mm³ | 78539,81634 | 78539,81634 |
| Fläche | 10210,17612 mm² | 10210,17612 | 10210,17612 |
| Flächen | 3 | 3 | 3 |

Fünfzehn übereinstimmende Stellen, und der Rückweg (Fusion-STEP in Solidon)
ebenso: 2010,619298 mm³ auf beiden Seiten, Bohrung erkannt, Durchmesser und
Achse richtig. Der zweite Kern aus §30 hält, was er verspricht.

**Die Slicer-Übergabe kommt vollständig an.** Ein echter Lauf gegen
ElegooSlicer 1.5.3.4 — eine Fassung neuer als die, gegen die die Tabelle
gebaut wurde — meldet **null** übergangene Einstellungen. Die Profilzuordnung
trifft ohne Zutun: `Elegoo Centauri Carbon 2 0.4 nozzle`, `0.20mm Standard
@Elegoo CC2 0.4 nozzle`, `Elegoo PETG @ECC2`, aus 9849 gelesenen Profilen in
einer Sekunde. Düse 240, Bett 80, Füllung 15 %, drei Wände, Arachne: alles
steht im G-Code. Die achtzehn Werte, die im falschen Profil lagen, sind
wirklich zu Hause.

**Der ganze Weg läuft aus der Oberfläche.** Strg+P, Slicen, 0,8 Sekunden,
„Druckzeit: 37 min · Material: 10,0 g · Schichten: 55", Druckdatei speicherbar,
vier Hinweise im Prüfbericht. Das ist der Weg, für den es Solidon gibt.

---

## 2. Die Befunde

Fünfzehn Funde, geordnet nach dem, was sie kosten. Jeder ist gemessen, keiner
erschlossen.

### A. Zahlen, die stillschweigend falsch sind

Diese drei wiegen am schwersten: sie erzeugen kein Fehlerbild, sie erzeugen
ein falsches Teil.

#### A1 — Der Hüllquader eines exakten Körpers kommt aus seinen Dreiecken

`Solid.bounds` gibt `self.mesh.bounds` zurück, also den Hüllquader der
Tessellation. Gemessen über vier Größen:

| Soll | gemessen X | gemessen Y | Fehler |
|---|---|---|---|
| 6 mm | 6,0000 | 5,9832 | 0,017 |
| 20 mm | 19,9756 | 19,9878 | 0,024 |
| 50 mm | 49,9755 | 49,9878 | 0,025 |
| 120 mm | 119,9751 | 119,9875 | 0,025 |

Der Fehler ist **absolut konstant** bei rund 0,025 mm — die halbe
`DEFLECTION` von 0,05 mm — und wird prozentual umso schlimmer, je kleiner das
Maß. Fusion misst denselben Körper mit „Radius: 25.00 mm".

Das ist kein Anzeigefehler. Auf `bounds` beruhen: die Maße im Objektbaum und
in der Kopfzeile, die Bauraumprüfung, `arrange_bed`, `check_adhesion_clearance`,
`advise.for_part` (Standfläche und Schlankheit entscheiden über den Brim), die
Passungsprüfung. Ein Zapfen Ø 6, der 5,983 misst, hat gegen eine
Materialtoleranz von 0,25 mm ein Zehntel seines Spiels verloren, bevor irgendwer
gedruckt hat. Regel 6 sagt: der Kern rechnet in doppelter Genauigkeit, gerundet
wird nur in der Anzeige. Hier rundet die Anzeige nicht, hier rechnet der Kern
falsch.

**Fix:** `Solid.bounds` über `BRepBndLib.Add_s` aus der Form statt aus den
Dreiecken. Der Weg ist kurz, der Test ist ein Zylinder mit Ø 50, dessen
Hüllquader auf `EPS_GEOM` genau stimmen muss.

#### A2 — Die angeklickte Fläche ist die Mitte des Werkzeugs, nicht sein Anfang

`drill` legt den Schnittzylinder mittig auf `position`
(`trimesh.creation.cylinder` steht auf dem Ursprung zentriert). Die Doku sagt
das auch — „Mitte der Bohrung im Koordinatensystem des Objekts". Nur trägt
`take_point` den angeklickten Punkt eins zu eins ein, und angeklickt wird eine
**Oberfläche**. Gemessen an einer Platte 60 × 60 × 20, Klick auf die Oberseite:

| Handlung | abgetragen | erwartet |
|---|---|---|
| Bohrung Ø 6, Tiefe 10 | 150,8 mm³ | 301,9 mm³ (halb so tief) |
| Bohrung Ø 6, Tiefe 0 („bohrt durch") | 301,9 mm³ | 602,1 mm³ (**bohrt nicht durch**) |
| Schraubenloch M4, Tiefe 10 | 185,8 mm³ | rund das Doppelte |
| Einpressbuchse M4 | 212,0 mm³ | rund das Doppelte |
| Mutternfalle M4 | 232,7 mm³ | rund das Doppelte |
| **Magnettasche 6 × 3** | **0,0 mm³** | eine Tasche |

Die Zeile, die den Ausschlag gibt, ist die zweite: der `doc`-Satz des
Parameters lautet „Null bohrt durch das ganze Teil", und mit der Position, die
ein Klick liefert, tut sie das nicht. Der Rest ist die Passungsfrage: eine
Einpressbuchse in einem 10 mm zu flachen Sackloch sitzt nicht.

In Fusion ist der angeklickte Punkt der **Anfang** der Bohrung, und die Tiefe
läuft ins Material. Das ist nicht Geschmack, das ist die Erwartung jedes
Nutzers, der schon einmal gebohrt hat.

**Fix:** Position ist die Mündung, Richtung ist ins Material (gegen die
Flächennormale), `depth=0` heißt „von der Mündung durch". Betrifft `drill`,
`countersink` und die sieben Bausteine, die darauf aufsetzen. Alte Dateien
meinen die Mittenlage: Formatversion erhöhen und beim Öffnen umrechnen (halbe
Tiefe addieren) — nicht stillschweigend, sondern als Migration mit Beispieldatei
nach der Checkliste in `AGENTS.md`.

> **Erledigt.** Zwei Hälften, und die zweite fiel kleiner aus als hier
> geschätzt.
>
> *Die Bausteine:* alle sechzehn nachgemessen. Dreizehn hielten die Konvention
> schon (abziehend baut unter dem Ursprung), drei brachen sie —
> `magnet_pocket`, `keyhole`, `cable_gland`. Sie bauen jetzt nach unten,
> `keyhole` nicht mehr quer in Y. Die Bibliothek steht auf Version 2, der
> Änderungseintrag `MOUTH_AT_ORIGIN` sagt, was das für alte Projekte heißt.
> Der neue Test misst nicht Koordinaten, sondern Wirkung: jeder abziehende
> Baustein auf die Oberseite einer Platte gesetzt, danach muss sie leichter
> sein. Die drei trugen vorher 0,0 / 0,0 / 0,2 mm³ ab, jetzt 150 / 343 / 309.
>
> *Die Bohrung:* nur `drill` saß mittig. `countersink` verankerte schon an der
> Mündung, `plug` füllt und darf mittig bleiben. `drill` bekam `anchor` mit den
> Werten `mouth` (Vorgabe) und `centre`; die Richtung ins Material entscheidet
> die Hälfte des Hüllquaders, damit auch eine von unten angeklickte Fläche
> stimmt. Umgerechnet wird nichts: eine durchgehende Bohrung geht in beiden
> Fällen durch, und für eine begrenzte trägt die Migration 6 → 7 den alten
> Bezugspunkt ein. `tests/data/projects/drilled_v6.p3d` beweist es an einem
> Volumen — 31 276,89 mm³ vorher wie nachher, gegen 31 231,74 mm³ mit der
> neuen Bedeutung.

#### A3 — Eine Operation, die nichts abgetragen hat, schweigt

Die Magnettasche oben trifft den Körper nicht und meldet nichts: keine
Ausnahme, kein Befund, kein Hinweis in der Statusleiste. Dieselbe Tasche 80 mm
neben dem Teil verhält sich genauso. Der Nutzer sieht ein unverändertes Modell
und einen Verlaufseintrag, der behauptet, es sei etwas geschehen.

Regel 17 verlangt für jede Ausnahme einen Handlungsvorschlag. Hier gibt es
nicht einmal eine Ausnahme — der stille Fehlschlag steht unterhalb dessen, was
die Regel überhaupt erfasst.

**Fix:** Jede abtragende Operation vergleicht das Volumen vorher und nachher.
Ändert es sich um weniger als `EPS_GEOM`, entsteht ein Befund mit Vorschlägen
(„Werkzeug liegt außerhalb des Körpers", „an einer Fläche ausrichten",
„Position prüfen"). Ein Test je Sorte, mit einer Position weit daneben.

### B. Der Weg zur Platte

#### B1 — Solidons Anordnung erreicht den Slicer nicht

Zwei Läufe, dieselbe Szene: einmal in Solidons Koordinaten (Mitte bei null),
einmal in Bettkoordinaten verschoben. Der G-Code ist **beide Male identisch** —
Behälter (137,83 / 136,33), Deckel (108,19 / 106,69). Der Slicer wirft die
Anordnung weg und legt selbst.

Der Gegenbeweis mit `--arrange 0` und Bettkoordinaten:

| | Solidon ordnet an | im G-Code |
|---|---|---|
| Behälter | 30,00 / 30,00 | 30,00 / 28,50 |
| Deckel | 75,00 / 20,00 | 75,00 / 18,50 |

Auf ein Zehntel, der Versatz von 1,5 mm in Y ist der Bettursprung der Maschine.
Der Schalter existiert im installierten Programm (`arrange`, `ensure_on_bed`,
`orient` stehen in seiner Bibliothek).

Damit ist alles, was Solidon über die Platte weiß, für den Slicer-Weg
folgenlos: `arrange_bed`, der Haftungsrand aus `check_adhesion_clearance`,
`plates_by_material`, die Plattennummer am Objekt. Der offene Roadmap-Punkt
„Anordnung und Plattenhaftung zusammenbringen" hätte, so gelöst wie geplant,
nichts geändert — er hätte einen Abstand berechnet, der nie ankommt.

**Fix:** drei Schritte, in dieser Reihenfolge. (1) Der 3MF-Export schreibt
Bettkoordinaten statt Modellkoordinaten — die Umrechnung ist der halbe
Bauraum aus dem Druckerprofil. (2) `handover._command` übergibt `--arrange 0`
für die Orca-Familie. (3) Danach erst der Haftungsrand in `arrange_bed`, denn
jetzt hat er eine Wirkung. Prüfbar mit genau der Messung oben: Positionen aus
dem G-Code gegen die Positionen im Dokument, Toleranz eine Linienbreite.

#### B2 — Solidons „unbekannt" wird im Slicer zu „kostenlos"

`FilamentSettings.cost_per_kg` ist 0 mit dem Kommentar „0 heißt unbekannt,
nicht kostenlos — die Kostenschätzung schweigt dann". Übergeben wird die Null
trotzdem, und sie überschreibt im Filamentprofil des Herstellers die 30 €/kg;
im G-Code steht `filament_cost = 0`. Solidons Nicht-Aussage wird zur Aussage
des Slicers.

Systematisch geprüft (alle geschriebenen Nullen gegen den aufgelösten
Herstellerbestand): es ist der einzige Fall. `brim_width = 0` ist gewollt und
richtig, weil Skirt eingestellt ist.

**Fix:** Werte, deren Null „unbekannt" heißt, werden nicht geschrieben. Das ist
dieselbe Unterscheidung, die `profile_differences` für `nil` schon trifft — sie
gehört auf die Schreibseite. Ein Eintragsfeld in `slicer_keys.Entry`
(`omit_when`), keine Sonderbehandlung im Aufrufer.

#### B3 — Keine Operation legt eine Passung an

`create_lid` baut den Deckel mit dem Spiel aus dem Materialprofil (gemessen:
0,25 mm) — und trägt keinen `Fit` ins Dokument. Passungen entstehen nur an drei
Stellen: im Agenten, beim Verstiften und über einen Dialog.

Die Folge steht in `advise._from_fits`: genaue Außenwand, 2000 mm/s² und das
Bügeln der Gleitfläche greifen nur, wenn `has_fits` wahr ist. Ein Deckel, den
die dafür gebaute Operation erzeugt hat, wird also ohne die Einstellungen
gedruckt, die es für Deckel gibt. Im Live-Lauf: Vorschläge = 0.

**Fix:** Operationen, die eine Passung *herstellen*, geben sie als
`DocumentChange` mit — `create_lid`, `screw_lid`, `insert_snap_fit`,
`insert_dowel`, `insert_magnet_pocket`, `insert_heatset_m4`, `insert_nut_trap`.
Das Dokument erfährt damit, was die Geometrie längst weiß. `History.apply`
nimmt `changes` bereits entgegen; die Ops müssen sie nur füllen dürfen (§15.5).

#### B4 — Die Gegenprobe vergleicht nur das Stützvolumen

Der Live-Lauf: Solidons Schätzung **12 g / 46 min**, der G-Code **10,0 g /
37 min**. Das sind −17 % und −20 %. Der Prüfbericht meldet vier Hinweise, keine
Warnung.

`gcode.compare` hat die 15-%-Schwelle und wird an genau einer Stelle gerufen —
`main_window.py:1642`, für das Stützvolumen. Zeit und Material laufen als
`gcode.print_time` und `gcode.material` als reine Auskunft durch, ohne je gegen
die Schätzung gehalten zu werden. §28.2 meint beides.

**Fix:** dieselbe Gegenprobe für Druckzeit und Materialverbrauch. Beide Zahlen
bleiben stehen, beide behalten ihre Herkunft (Regel 14) — was fehlt, ist der
Satz, dass sie sich widersprechen. Und genau dieser Satz ist der Hinweis, dass
`slice/estimate.py` Arbeit braucht.

#### B5 — `arrange_bed` ohne Eingaben hält das Dokument an

Aufgerufen ohne Eingabeobjekte plant `History._outputs_for` einen Ausgang
(`produces == VARIABLE and not draft.inputs`), die Operation liefert keinen, und
die Auswertung bricht mit `evaluate.object_count` ab. Alles nach dieser
Operation wird nicht mehr gerechnet.

`test_arranging_without_inputs_changes_nothing` deckt das zu: er prüft, dass
sich die Positionen nicht geändert haben — was auch für eine abgebrochene
Auswertung gilt. `result.complete` fragt er nicht ab. Das Fenster reicht über
`inputs_for` immer die ganze Szene herein; über Kommandozeile, Agent und MCP ist
der Aufruf ohne Eingaben einen Tippfehler entfernt.

**Fix:** eine Operation mit `takes_whole_scene` und leerer Eingabeliste bekommt
keine Ausgänge geplant; der bestehende Test wird um `assert result.complete`
ergänzt.

### C. Sehen und Zeigen

#### C1 — Im Viewport lässt sich nichts anklicken

Live geprüft, zweimal, mit Vorbewegung des Zeigers: Linksklick auf den Körper →
Statusleiste bleibt „Keine Auswahl", keine Hervorhebung, kein Eintrag im
Objektbaum. Rechtsklick auf dieselbe Fläche → kein Kontextmenü. Mausrad zoomt,
Rechtsziehen dreht — die Maus kommt also an.

Die Ursache steht im Quelltext: gepickt wird mit `vtkPointPicker`, sowohl in
`_world_at` als auch über `enable_point_picking(picker="point")`. Ein
Punktpicker trifft **Eckpunkte**, nicht Flächen. Der Halter aus dem Beispiel hat
acht davon; ein Klick in die Mitte einer Fläche trifft keinen und liefert
nichts. Der Docstring von `_enable_picking` beschreibt die Reparatur des
Vorgänger-Fehlers („ein Klick auf einen Körper tat nichts") — die Verdrahtung
ist seither richtig, das Werkzeug ist es nicht.

Was daran hängt: Auswahl, Kontextmenü am Merkmal (§18.5, der Kern von Weg 1),
Messen, Bemalen, das Eintragen einer Fläche in einen Dialog. Das Handbuch
beschreibt alles davon.

**Fix:** `vtkCellPicker` mit gesetzter Toleranz statt `vtkPointPicker`, an
beiden Stellen. Prüfbar ohne Fenster wird es nicht — der Test ist ein Klick auf
die Mitte einer Fläche in einem sichtbaren Fenster, und er gehört in die Liste
der Dinge, die von Hand geprüft werden, weil offscreen kein Plotter existiert.

#### C2 — Ein Zylinder hat einundfünfzig Flächen

Der Netz-Prüfkörper (Ø 50, 48 Segmente, eine Bohrung) trägt nach der
Wahrnehmung 51 Merkmale der Art `face` und eines der Art `hole`. Fusion zeigt
für denselben Körper drei Flächen. Die Bohrung wird richtig erkannt (Ø 8,1844 —
die kompensierten 8,2 — Tiefe 20,01, `through: False`, was A2 unabhängig
bestätigt).

Für die Bedienung heißt das: „auf die Fläche zeigen" meint in Fusion eine
Fläche und in Solidon eine Facette. Ein Merkmalsbaum mit `face_1` bis
`face_51` ist keine Auswahl, sondern eine Liste.

**Fix:** benachbarte Facetten mit gleicher Normale (eben) oder gemeinsamer
Achse (zylindrisch) zu einem Merkmal zusammenfassen, bevor IDs vergeben werden.
Das ist Arbeit an `perceive/features.py` und hat Folgen für die ID-Stabilität —
also mit dem Zuordnungstest zusammen zu machen, nicht nebenbei.

> **Erledigt.** Kleiner als befürchtet, weil die Zylindererkennung schon da war
> — sie kam nur nie zum Zug. Ein Mantelstreifen hatte 3,4 Prozent der größten
> Fläche und galt damit als eben. Die Trennlinie steht jetzt an der Naht
> zwischen zwei Dreiecken: koplanar ist dieselbe Fläche, ein deutlicher Knick
> ist eine Kante, alles dazwischen ist eine Rundung. Bei dreißig Grad, also ab
> zwölf Segmenten — ein Achteck-Prisma behält seine acht Seiten.
>
> Zylinder mit Bohrung: **4 Merkmale statt 51** (Deckel, Boden, Mantel als
> `pin`, Bohrung). Würfel 6, Platte mit Stift 7, Achteck 10, Kugel keines. Die
> Zuordnung blieb unberührt — die 2809 Tests laufen durch.

#### C3 — Ein Rundstab meldet sich als Bohrung

Der Fusion-Zylinder Ø 8 × 40 kommt in Solidon als
`hole {diameter: 8.0, depth: 40.0}` an. `brep/features.py:_describe` macht aus
jeder geschlossenen Zylinderfläche ein `hole`, ohne zu prüfen, auf welcher Seite
das Material liegt. Jeder Zapfen, jede Säule, jeder Dom ist damit eine Bohrung.

**Fix:** die Orientierung der Fläche auswerten (`TopAbs_REVERSED` bzw. die
Richtung der Normalen zur Achse) und zwischen `hole` und `boss` unterscheiden.
Ein Vokabular für den zweiten Fall gibt es in §21 noch nicht — er gehört
zuerst in Bauplan §4.2, dann in den Code.

#### C4 — Die Skizzenleiste liegt unter den Fenstern

Im Skizzenmodus laufen Werkzeugleiste und Zwangsbedingungszeile über die volle
Fensterbreite und verschwinden links unter dem Objekte-Bereich, rechts unter
dem Prüfbericht. Betroffen sind die **ersten** Werkzeuge — dort stehen Linie
und Rechteck, also das, womit jede Skizze anfängt. Bei 1296 px Breite wie bei
1900 px, es ist kein Platzproblem, sondern die Stapelreihenfolge.

Die Kürzel selbst stimmen: `R` zeichnet ein Rechteck, die Bemaßung erscheint,
die Statuszeile meldet „Bestimmt — alle Freiheitsgrade sind vergeben". Wer aus
Fusion kommt, findet also die Tasten, aber nicht die Knöpfe.

**Fix:** Die Leiste gehört in den Viewport-Bereich zwischen die Panels, nicht
über das ganze Fenster. Prüfbar über die Geometrie der Widgets, ohne Bild.

#### C5 — Der Ersteinrichtungsdialog fragt den gefundenen Slicer nicht

Der Dialog meldet „gefunden: Slicer" und schlägt im selben Fenster „Allgemeiner
FDM-Drucker 220 mm" und PLA vor. Der Profilbestand des gefundenen Slicers weiß
zu diesem Zeitpunkt, welche Maschine eingestellt ist; `slicer_profiles.match`
ordnet in die andere Richtung bereits zu.

**Fix:** Beim ersten Start aus dem Slicer-Bestand vorbelegen — die zuletzt dort
gewählte Maschine auf Solidons Druckerprofil abbilden und, wo der Name trifft,
vorschlagen. Trifft nichts, bleibt der allgemeine Drucker stehen; eine falsche
Vorauswahl wäre schlimmer (dieselbe Regel, die `slicer_profiles.match` schon
befolgt).

#### C6 — Der Name des Teils reist nicht ins STEP

In Fusion heißt das importierte Teil „Körper1"; der STEP-Header nennt „Open
CASCADE STEP translator 7.9 1". Der Objektname aus Solidon steht nirgends. Fürs
3MF war das schon einmal ein Fund („Object 1, Object 2") und ist behoben; STEP
hat dieselbe Lücke.

**Fix:** `PRODUCT`-Name beim Schreiben setzen (`STEPControl_Writer` über
`Interface_Static` bzw. den Namen an der Form). Prüfbar ohne Fusion: die
geschriebene Datei enthält den Objektnamen.

#### C7 — Von der Aushöhlung zum Deckel fehlt ein Schritt

`hollow_object` erzeugt einen geschlossenen Hohlraum. `create_lid` verlangt eine
Öffnung und meldet sonst sauber „Der Körper ist auf dieser Höhe massiv — es
gibt nichts zu verschließen", mit Vorschlägen. Der Weg zur Dose führt trotzdem
über zwei Zylinder und `subtract_objects` — das ist der Weg, den ein
CAD-Anwender kennt, aber nicht der, den die Bausteine nahelegen.

**Fix:** `hollow_object` bekommt einen Parameter „oben öffnen" (Fläche oder
Höhe), oder der Katalog bekommt einen Baustein „Behälter". Kein großer Eingriff,
aber er entscheidet darüber, ob „Dose mit Deckel" ein Zweiklick-Weg ist.

> **Erledigt** als Schalter, nicht als Baustein. Das Werkzeug kommt aus dem
> Raster, das für den Hohlraum ohnehin entsteht: sein oberster Querschnitt,
> nach oben durchgezogen. Der oberste und nicht die Vereinigung aller — eine
> Dose soll ihre Decke verlieren, nicht ihre Schulter. Die Entlüftung entfällt
> dabei, denn eine offene Dose ist ihre eigene. Der Test sind beide Schritte
> zusammen: aushöhlen, öffnen, und `create_lid` findet die Öffnung.

---

## 3. Reihenfolge

Vier Pakete. Jedes ist so geschnitten, dass die Suite danach grün sein kann.

**Paket 1 — Maße, die stimmen.** A1, A3, C6.
Der exakte Hüllquader, der laute Fehlschlag, der Name im STEP. Zusammen, weil
alle drei klein sind und alle drei an derselben Stelle wehtun: eine Zahl, der
man ansieht, dass sie stimmt.
*Abnahme:* Hüllquader eines Ø-50-Zylinders auf `EPS_GEOM`; eine danebenliegende
Magnettasche erzeugt einen Befund mit Vorschlag; der Objektname steht in der
STEP-Datei.

**Paket 2 — Die Platte.** B1, B2, B5, danach der offene Roadmap-Punkt zum
Haftungsrand. **Erledigt am 05.08.2026.**
*Abnahme:* die Positionen im G-Code stimmen mit denen im Dokument überein
(Toleranz eine Linienbreite, Bettursprung abgezogen); `filament_cost` steht im
G-Code auf dem Wert des Herstellerprofils; `arrange_bed` ohne Eingaben lässt die
Auswertung vollständig.
*Gemessen:* drei Teile, Abweichung **0,00 mm** in X und Y nach Abzug des
`extruder_offset` von 1,5 mm, den der Slicer selbst einrechnet — ohne die
Änderung waren es bis 110 mm. Der Preis wird nicht mehr geschrieben, wenn er
unbekannt ist. Die Auswertung läuft durch. Einzelheiten am Ende der
`ROADMAP.md`.

**Paket 3 — Zeigen und Auswählen.** C1, C4, dann C2.
Der Flächenpicker zuerst — er schaltet Auswahl, Kontextmenü, Messen und
Flächenübernahme auf einmal frei. Die Skizzenleiste danach, weil sie eine
Stunde ist. C2 (Facetten zusammenfassen) zuletzt, weil es die ID-Stabilität
berührt.
*Abnahme:* Ein Klick in die Mitte einer Fläche wählt den Körper aus, ein
Rechtsklick öffnet das Menü; im Skizzenmodus ist der erste Knopf der Leiste
sichtbar und anklickbar; ein Zylinder trägt drei Flächenmerkmale statt
einundfünfzig.

**Paket 4 — Was das Teil verlangt.** B3, B4, C3, C5, C7.
Die Passung ins Dokument, die vollständige Gegenprobe, `boss` neben `hole`, die
Vorbelegung aus dem Slicer, der Weg zur Dose.
*Abnahme:* ein Deckel aus `create_lid` erzeugt eine Passung, und `advise`
schlägt daraufhin die genaue Außenwand vor; eine Abweichung über 15 % zwischen
Schätzung und G-Code erscheint als Warnung im Prüfbericht.

**A2 steht bewusst außerhalb der Pakete.** Die Bohrposition zu drehen ist die
einzige Änderung hier, die bestehende Projektdateien anders rechnen lässt. Sie
braucht ihre eigene Runde: Formatversion, Migration, Beispieldatei, und einen
Durchgang durch alle sieben Bausteine, die darauf aufsetzen. Sie ist aber auch
der Fund mit den handfestesten Folgen — eine Einpressbuchse in einem halb so
tiefen Loch ist ein weggeworfener Druck.

---

## 4. Was nicht gebaut wird

* **Kein eigenes Anordnen im Slicer-Format.** Solidon schreibt seine
  Positionen und schaltet das Anordnen des Slicers ab; die Plattendaten der
  Orca-Familie (`plate`-Blöcke in `model_settings.config`) nachzubauen hieße,
  ein fremdes internes Format zu pflegen. Kommen die Koordinaten an, ist die
  Frage beantwortet.
* **Kein Skizzenobjekt im Dokument.** Fusion führt Skizzen als eigene
  Gegenstände, die mehrere Features speisen. Das wäre ein zweiter
  Abhängigkeitsgraph neben dem Op-Stack — im Konzept zu P15 aus demselben Grund
  schon einmal abgelehnt. Wer denselben Umriss zweimal braucht, dupliziert die
  Operation.
* **Keine feinere Tessellation als Antwort auf A1.** `DEFLECTION` kleiner zu
  setzen macht den Fehler kleiner und die Anzeige langsamer, ohne ihn zu
  beheben. Der Hüllquader kommt aus der Form oder er ist falsch.
* **Kein Bildvergleichstest für C1 und C4.** Was ein Bild hier zeigen würde,
  zeigt die Geometrie der Widgets und der Rückgabewert des Pickers billiger und
  ohne Zeichensatz-Abhängigkeit.

---

## 5. Anhang: wie gemessen wurde

Alle Zahlen stammen aus Läufen auf dieser Maschine am 5. August 2026.

* **Slicer:** `C:\Program Files\ElegooSlicer\elegoo-slicer.exe`, 1.5.3.4.
  Gerufen über `handover.slice_model` mit den Profilen aus
  `slicer_profiles.match`, Testkörper eine Dose mit Deckel (Ø 50 × 40, Wand 2,
  Deckel mit Kragen) und ein Zylinderpaar. Positionen aus dem G-Code über die
  `; printing object`-Marken und die Extrusionsbewegungen dazwischen.
* **Fusion:** 2704.1.36, gemessen über ein Add-In, das STEP und STL lädt,
  Volumen, Fläche, Flächenzahl und Hüllquader ausliest und einen eigenen Körper
  zurückexportiert. Das Add-In ist nach der Messung wieder entfernt worden.
* **Solidon:** aus dem Arbeitsbaum, `.venv`, ohne Änderungen am Code. Die
  Oberfläche wurde mit echter Maus und Tastatur bedient (synthetische Eingaben
  auf Fensterebene), die Bilder sind Aufnahmen des laufenden Fensters.
