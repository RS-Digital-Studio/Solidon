# P1.6 — festzuziehender Anschluss vor der Umsetzung

Nur Vorbereitung während des eingefrorenen P1.2/P1.3-Entwicklungstors.
Die Produktumsetzung beginnt nach dessen grünen Commits. Grundlage sind
p16-deviation-plan.md, p16-extrema-plan.md und die lesenden Anschlussreviews.

## Abgeleitete Trägerdaten

- Ein enges `SurfacePatch` am bestehenden `Feature.surface_patches`, als
  letztes optionales Feld mit leerer Vorgabe. Keine weitere semantische ID.
- Art: plane, cylinder, cone, sphere, torus. Ebenen gehören dazu, wenn ihre
  vorhandene Erkennung einen Ebenenpunkt und eine Normale tatsächlich belegt.
  Ein flacher Körper soll nicht allein mangels Rundung vollständig unbekannt
  erscheinen. Deklarierte Bausteinmaße begründen noch keinen Träger.
- Parameter, ursprüngliche Dreiecksindizes, tatsächliche Quelle. Native
  Originalträger heißen native, eingepasste Rundträger fit; eine aus den
  tatsächlichen planaren Facetten bestimmte Ebene darf facets heißen.
  Die Karte behauptet damit kein ursprüngliches Konstruktionsmaß.
- Durchmesser, Achse, Mitte und Kegelwinkel behalten die vorhandene Bedeutung.
  Der Kegel verwendet ausschließlich seine belegte Nappe. Jeder Hersteller
  des Datums übernimmt die vorhandene Lösung; kein Kartenaufruf passt neu ein.
- Semantisches Zusammenfassen übernimmt einzelne Teilträger, ohne deren
  Parameter zu mitteln. Lokale Erkennung und Neuindizierung führen jeden
  Patch über dieselbe belegte Zuordnung. Mehrdeutige Überdeckungen sind unbekannt.
- Transformation und Cache folgen dem vorhandenen Featureweg. Eine veränderte
  Form ohne nachgewiesene Formerhaltung invalidiert den Träger. Keine neue
  Projektgeometrie, deshalb nur die nächste Ergebnis-Cacheversion.

## Kartenrechnung und Oberfläche

- Physischer Wert: größter Abstand im ausgefüllten Originaldreieck zum
  zugeordneten analytischen Träger. Die direkten ebenen, zylindrischen und
  kugeligen Fälle sowie die hergeleiteten Kegel-/Torus-Extrema teilen einen
  Kernrechner. Keine Oberflächenrekonstruktion und keine freie Fitoptimierung.
- Ein Rechenintervall gehört zur numerischen Bestimmung dieses Abstands.
  Es ist getrennt von Nennmaßunsicherheit, Materialspiel und Rasterweite.
  Ein konservativer oberer Wert muss als solcher bezeichnet sein; normale
  Anzeigerundung darf ihn nicht nach unten ziehen.
- Vor Implementierung des Rechners konkrete Ergebnisfelder festlegen:
  AnalysisMap braucht gegebenenfalls eine benannte numerische Fehlergrenze
  und den tatsächlichen Zeugenpunkt samt Dreiecksbezug. Bestehendes resolution
  bleibt Rasterweite. Keine zweite eigenständige Kartencachesammlung.
- Vollständig unbekannte Werte zeigen keinen gemessenen Nullbereich. Ein
  nativer Körper erklärt, dass die Facetten seiner Anzeige geprüft werden.
  Fehlende Teilflächen bleiben als solche gezählt und erklärt.
- Auswahl und leichter Info-Befund öffnen denselben vorhandenen asynchronen
  Kartenweg. Der Befund darf noch keine unberechnete Zahlenbehauptung tragen.
  Karte, Körper, Dokumentstand und wartender Berichtsklick bleiben gebunden.
- Gemeinsamer Fortschritts-/Abbruchknopf, eindeutige Ortsmarke nach gültigem
  Ergebnis und Schutz vor späten Antworten gehören zum Kundenweg.
  Ganze Fensterdateien und Leistung werden ausschließlich beim Release geprüft.

## Zuständigkeiten für das folgende Paket

Root führt den zentralen Vertrag, Cacheversion und unabhängigen Review.
Die endgültige Dateiverteilung folgt dem Träger-Anschlussplan; Kernrechnung,
Veröffentlichung/Nachführung und UI-Anschluss dürfen getrennt bearbeitet
werden, nachdem ihre gemeinsamen Felder feststehen. Kein Agent beginnt die
Produktänderung während des noch laufenden vorigen Entwicklungstors.

## Konkrete Datennamen für die Umsetzung

Der Träger bleibt ein kleiner Datensatz in `core/types.py`, ohne Kernimport:

```python
SurfaceKind = Literal["plane", "cylinder", "cone", "sphere", "torus"]
SurfaceSource = Literal["native", "facets", "fit"]

@dataclass(frozen=True, slots=True)
class SurfacePatch:
    kind: SurfaceKind
    params: Mapping[str, float | Vec3]
    face_indices: tuple[int, ...]
    source: SurfaceSource
```

`Feature.surface_patches: tuple[SurfacePatch, ...] = ()` folgt ganz am Ende.
Die expliziten Schlüssel sind:

| Art | Parameter |
|---|---|
| plane | `centre`, `axis` (Ebenenpunkt, normierte Normale) |
| cylinder | `centre`, `axis`, `radius` |
| cone | `apex`, `axis`, `half_angle` (Radiant, gerichtete Nappe) |
| sphere | `centre`, `radius` |
| torus | `centre`, `axis`, `ring_radius`, `tube_radius` |

Damit hängen die tatsächlichen Träger nicht von semantischen Auswahlmitten,
dem Öffnungswinkeltext oder Durchmesserbezeichnungen ab. Die Validierung
prüft Schlüssel, endliche Zahlen, positive Radien, gültige Winkel/Nappe und
die zugehörigen Indizes; boolesche Zahlen und Ersatzachsen sind ungültig.
Der vorhandene Ringtorusweg bleibt bei `ring_radius > tube_radius > 0`.
Keine beliebigen neuen Art-/Parameterschemata oder Quelltextwerte.

Gemeinsame rein geometrische Datenhelfer erhalten einen eng begrenzten Ort
unter `perceive`: validieren, Ebenenträger aus vorhandenen Facetten belegen,
beschneiden/umindizieren und bewiesen formerhaltend transformieren. Das neue
kleine Modul ist gemeinsam genutzte Trägerlogik, kein weiteres Register oder
Erkennungssystem. Native Träger werden weiterhin unter `brep` gelesen.

Der Kartenrechner gibt konservative **obere** Facettenwerte aus. Für die
zusätzliche numerische Auskunft reichen optionale Felder am bestehenden
`AnalysisMap`: `maximum_interval` (untere/obere Grenze des globalen Maximums),
`numerical_error` (größte verbleibende Breite einer bekannten Facette),
`witness_point`, `witness_face` und `witness_distance`. Der Zeugenabstand ist
eine nach unten begrenzte tatsächliche Punktdistanz; die globale Obergrenze
ist ausdrücklich kein am Zeugen erreichter Wert. Keine zweite Reihe aller
unteren Facettenwerte speichern. Die gemeinsame numerische Rückgabe wird
vor der Umsetzung mit der unabhängigen Extremwertdurchsicht abgeglichen.

`maximum_interval` und `numerical_error` sind ausschließlich numerische
Auskunft der Kartenrechnung, weder Fertigungsspiel noch Nennmaßfehler.
Unbekannte Dreiecke zählen nicht als Null und nicht zur numerischen Breite.
Fehlt jeder Nachweis, bleiben Intervall und Zeuge leer. Die Kartenoberfläche
benennt die obere Schranke und die bekannte Abdeckung; keine Anzeige eines
genauen Nullwerts aus bloßer Rundung.
