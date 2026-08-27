# Gebietsbericht: Skizze und B-Rep (`app/core/sketch/`, `app/core/brep/`)

Gegen `AGENTS.md`, `kern.md`, `zeichenflaeche.md`, Bauplan §30.1/§30. OpenCASCADE auf dieser Maschine da. Sechs Testdateien vorher grün (215 passed). Keiner im Register.

## Hoch

### 1 [hoch] Ein Loch, das andersherum gezeichnet wurde, verschwindet still — und der Körper wird größer — VERIFIZIERT
`brep/profiles.py:141` — `_face` dreht jeden Lochring bedingungslos um (`.Reversed()`); stimmt nur bei gleichem Drehsinn. Läuft der Innenring andersherum, gilt er als zweite Außenkontur und wird addiert. Gemessen (40×40 mit Loch 20×20, Soll 6000): CCW/CW und CW/CCW → 10000, ohne Befund. Betrifft `sketch_extrude`, `sketch_revolve`, `sketch_sweep`. In der Zeichenfläche gibt es kein Rechteckwerkzeug — der Drehsinn ist reiner Zufall der Klickreihenfolge. **Fix:** Drehsinn im Kern normalisieren (`_signed_area` neben `_area`, jede Kette kanonisch drehen); dann steht `_face`s `Reversed()` auf einer Zusage.

### 2 [hoch] Zwei Umrisse, die sich kreuzen, ergeben einen Körper mit undichtem Netz — ohne ein Wort — VERIFIZIERT
`sketch/profile.py:140`, `:195` — `_crosses_itself` prüft jede Kette gegen sich selbst, nie Kette gegen Kette. Gemessen: zwei überlappende Löcher Ø20 → Volumen 4858 statt 5472, `is_closed=True`, `is_watertight=False`, keine Befunde; Loch über die Plattenkante hinaus → ebenso. Geht in STL-Export und Schichtanalyse. **Fix:** `regions_of` auf Paare erweitern (`combinations(bearing,2)`); `_created` gibt bei `is_watertight=False` einen Befund (kein Fehler) aus.

### 3 [hoch] „Tasche schneiden" verliert jedes gezeichnete Loch — die Insel wird mit weggefräst — VERIFIZIERT
`sketch/profile.py:295` (Aufruf `ops.py:463`) — `shifted()` baut `Profile(...)` ohne `holes=`; die Schwester `scaled()` (`:570`) nimmt sie mit. `sketch_pocket` schickt jede Region durch `shifted`, auch bei x=y=0 (immer). Gemessen: Ringtasche mit Insel Ø10×5 → 30000 statt 30392,7 (Insel weg), keine Befunde. Zwilling des Loft-Fixes `6d41369a`. **Fix:** in `shifted` beide Zweige um `holes=...` ergänzen; Geometrietest daneben.

### 4 [hoch] `feature:face_N` ist eine Positionsnummer, keine stabile ID — die Skizzenebene springt auf eine andere Fläche — VERIFIZIERT
`brep/features.py:71`, gelesen von `sketch/planes.py:135` — `features_of` vergibt IDs in der Reihenfolge von `MapShapes_s`; für B-Rep greift keine Zuordnungsschicht (`evaluate.py:678` steigt vor der Merkmalszuordnung aus). Gemessen: `face_6` des Quaders = Deckel; nach einer Bohrung = +X-Seitenwand. Ende-zu-Ende: Aufsatz auf dem Deckel wird nach einer Bohrung quer aus der Seitenwand. Auslöser ist jeder Schritt, der die Flächenzahl ändert (auch Bohrung durch↔blind). Betrifft alle fünf Skizzen-Ops mit Flächenebene, `up_to`, `sketch_pocket`. **Fix:** IDs an Geometrie hängen (Schwerpunkt+Normale) wie `brep/edit.py` für Kanten fordert; Sofortmaßnahme: `planes.frame_for` gleicht Schwerpunkt/Normale ab und meldet statt zu raten (Regel 21).

### 5 [hoch] „Verlängern" kürzt die Linie um die Hälfte — VERIFIZIERT
`sketch/edit.py:240` — `(_parameter_on(line,point) > 1.0) == towards_end`; für `towards_end=False` ist die Bedingung `t<=1.0`, schließt jede innere Kreuzung ein. Gemessen: Linie (0,0)–(10,0), Querlinie bei x=5, Klick (2,0) → extend liefert (5,0)–(10,0). Umkehrung des D-4-Fixes (`crossings_on`). **Fix:** Richtung explizit prüfen (`above = t>1`, `below = t<0`); `_reachable`-Toleranz (`edit.py:403`) steht nur an einem Ende, mitziehen.

### 6 [hoch] Der Löser meldet einen Widerspruch, wo keiner ist: zwei deckungsgleiche Punkte mit einem Maß — VERIFIZIERT
`sketch/solver.py:94` — `_unit` sichert die Länge gegen null, die Richtung nicht; bei dx=dy=0 kommt `(0,0)`, Gradient exakt null, `least_squares` findet keine Abstiegsrichtung → `SketchConflictError`. Gemessen: Linie Länge null + Maß 10 → Konflikt(0,1); zwei Punkte am selben Ort + Maß → Konflikt. Erreichbar durch zwei Klicks auf denselben Rasterpunkt. **Fix:** in `_unit` bei entarteter Länge eine feste deterministische Richtung (+X) liefern.

## Mittel
- **7** `sketch_revolve` nimmt die Zeichenebene entgegen und benutzt sie nicht (`ops.py:615`, liest immer `_lift_xz`); `feature:face_1` in leerer Szene bleibt stumm. VERIFIZIERT. Fix: `_plane_of` lesen, alles außer `plane:xz` ablehnen wie `sketch_sweep`.
- **8** Umschließungs-Näherung tastet einen Bogen mit einem Punkt ab (`profile.py:186`, `_nested`); zweibögige Kreiskontur 2r² statt πr² → Loch fällt raus. VERIFIZIERT (Ring 691 statt volle Scheibe 2262). Fix: `_outline` über `_flat_curve`/`_along_arc` abtasten.
- **9** Das gemeldete Bedingungspaar nennt eine Bedingung mit Restfehler null (`solver.py:512`); Dialog bietet „Zweite Bedingung entfernen" für eine gute Bedingung → danach unterbestimmt. VERIFIZIERT. Fix: nur Bedingungen über `_TOL` aufnehmen.
- **10** Mesh-Bohrung und B-Rep-Bohrung bohren bei Vorgabe in entgegengesetzte Richtungen (`brep/edit.py:294` `>` gegen `geom/prepare.py` `>=`), zwei Schwellen am Mittelpunkt; `MENU_TWINS` wäre kein Umschalten. VERIFIZIERT (Schwerpunkt +0,028 gegen −0,028). Fix: `edit.bore` `into_the_body` benutzen (Signatur auf `BoundingBox`).
- **11** Zehn Geometriefehler des exakten Kerns bieten „Reparieren"/„Stellen zeigen" an, beide tun nichts (`brep/profiles.py:873`, erbt `(REPAIR_AND_RETRY, SHOW_LOCATIONS, CANCEL)`; an einem B-Rep gibt es weder Defektkarte noch Mesh-Reparatur). `brep/edit.py:180` hat genau das für Verrundung/Fase behoben. Fix: `_finished` um `(CORRECT_INPUT, CANCEL)` ergänzen, drei nackte `GeometryError` mitziehen.

## Gering
- **12** „Mitte der Tasche in Y" verschiebt auf `plane:xz` in Z (`ops.py:396`, Zeichenebenen- vs Weltkoordinaten); Titel/`doc` falsch. Umschreiben.
- **13** `edit.project` fällt bei Flächenebene ohne Rahmen still auf XY zurück (`edit.py:474`), Regel 21; öffentliche Funktion rät. Anhalten.
- **14** Geschlossene Kreiskante zählt immer als „waagerecht" (`brep/edit.py:96`, `span=(0,0,0)`); `fillet_edges("horizontal")` verrundet senkrechte Bohrungsmündungen mit. `closed`-Feld einführen.
- **15** Rotationskörper aus Vieleck steht nicht auf Z=0 (`ops.py:623`, `rise=length/2` beim Vieleck falsch); schwebt 1,34 mm. `rise` aus `bounds_of(profile)`.
- **16** `trim`-Docstring beschreibt ein Verhalten, das der Code nicht hat (`edit.py:171`). Umschreiben.
- **17** Zwei weitere Doppelungen ohne Test dazwischen: `edit.BASE_PLANES` (dritte Grundebenen-Tabelle, ungesichert); `profiles.bounds` ohne `SetGap(0.0)` (heute nicht messbar, aber ungehärtet). Nachziehen.

## Geprüft und in Ordnung
Serialisierung verlustfrei/textstabil (Hilfsgeometrie, Referenzmaß, Spline, `feature:`-Ebene, Ausdrücke; nicht-endliche Zahlen/zu tiefe Verschachtelung abgewiesen); Ebenenrechnung (`to_world`/`to_plane` exakt invers, rechtshändig, `ray_hit` normiert, `height_to` lehnt parallel/rückwärtig ab); Löser-Ableitungen analytisch gegen zentrale Differenzen; Löcher in extrude/revolve/sweep/loft bei gleichsinniger Zeichnung exakt (Guldin/Kegelstumpf); Abmeldung ohne OpenCASCADE (`BRepUnavailable`, kein Absturz, Regel 1/§36); Regel 6/9/10 im Gebiet.

**Kann das so rein: nein** — sechs hohe Befunde erzeugen still falsche/kaputte Geometrie, vier (1,2,3,5) sind Zwillinge bereits behobener Nachbarfehler.
