# Konstruktionsrichtwerte für FDM

Für 0,4-mm-Düse auf dem Elegoo Centauri Carbon 2. **Alles hier sind
Richtwerte**, keine Normmaße: sie hängen von Material, Temperatur, Schichthöhe
und Geometrie ab. Wo es auf eine Passung ankommt, ersetzt ein Prüfstück jede
Tabelle.

## Wandstärken

Eine Wand wird aus ganzen Extrusionsbahnen gebaut. Krumme Wandstärken lässt der
Slicer entweder auffüllen oder er lässt eine Lücke — beides ist schwächer als
eine Wand, die aufgeht.

| Zweck | Richtwert |
|---|---|
| dünnste sinnvolle Wand | ~0,8 mm (2 Bahnen) |
| tragende Wand | 1,6–2,4 mm (4–6 Bahnen) |
| wasserdichte Wand | mindestens 4 Perimeter, dazu 5 Boden-/Deckschichten |
| Rippen und Gussets | 2 Bahnen, dafür hoch statt dick |

Unter etwa 1 mm bleibt jede Struktur fragil — das gilt auch für das, was
Solidon selbst erzeugt.

## Überhänge und Brücken

- Bis etwa **45°** gegen die Senkrechte druckt sich ein Überhang ohne Stütze.
- Darüber: Fase oder Verrundung ist fast immer billiger als Stützmaterial —
  eine 45°-Fase unter einer Bohrung macht sie stützfrei druckbar.
- Waagerechte Brücken über kurze Weiten gehen; die Unterseite wird rauh.
- Ein Loch, das waagerecht gebohrt ist, wird oben leicht oval. Wo das stört:
  als Tropfenform oder Sechseck konstruieren.

## Passungen

Spiel je Fügepartner, **auf den Durchmesser bezogen**:

| Art | Richtwert Spiel |
|---|---|
| beweglich, leichtgängig (Scharnierstift) | 0,3–0,5 mm |
| beweglich, geführt | 0,2–0,3 mm |
| Steckpassung von Hand fügbar | 0,15–0,25 mm |
| Presspassung, dauerhaft | 0,0–0,1 mm |

PETG und ASA schrumpfen stärker als PLA — dort eher an das obere Ende gehen.
TPU verzeiht Spiel kaum, es klemmt.

**Elefantenfuß**: die erste Schicht wird breiter gedrückt. Bei Passungen an der
Unterseite eine Fase von 0,4–0,6 mm vorsehen oder im Slicer kompensieren.

## Schrauben und Muttern

- **Durchgangsloch**: Nenndurchmesser + 0,4–0,6 mm (M3 → ~3,4 mm, M4 → ~4,4 mm)
- **Gewinde direkt ins Material** (selbstschneidend): etwa Kerndurchmesser,
  hält für wenige Montagen — nichts, was oft auf- und zugeht
- **Heat-Set-Einpressbuchse**: die bessere Lösung für alles, was mehrfach
  geöffnet wird. Lochdurchmesser nach Herstellerangabe der Buchse, mit
  Einführfase
- **Mutternfalle**: Schlüsselweite + 0,2–0,3 mm, Tiefe = Mutterhöhe + 0,2 mm.
  Von der Seite eingeschoben braucht sie einen Anschlag, von unten eine
  Abdeckung
- Kopfsenkung nach Kopfform; über einer Senkung braucht es keine Stütze, wenn
  der Winkel unter 45° bleibt

## Gewinde am Bauteil

Gedruckte Gewinde brauchen Flankenspiel — beide Teile für sich sauber zu
konstruieren reicht nicht. Steigung nicht zu fein wählen (unter etwa 1,5 mm
wird es bei 0,2 mm Schichthöhe unsauber), lieber ein grobes Trapez- oder
Rundgewinde. Immer als Paar prüfen: die Differenz aus Außen- und Innengewinde
muss über die volle Länge Luft lassen.

## Festigkeit

Die Schichtebene ist die Schwachstelle. Ein Teil bricht dort, wo Zug quer zu
den Schichten steht — nicht dort, wo es am dünnsten ist.

- Belastungsrichtung in die Schichtebene legen, nicht quer dazu
- Kerben und scharfe Innenecken vermeiden: verrunden, wo Kraft fließt
- Gyroid-Infill 20–30 % trägt in alle Richtungen gleich
- Mehr Perimeter bringen mehr als mehr Infill

## Dichtheit

- 4 Perimeter, 5 Boden-/Deckschichten, keine Nähte über die Dichtfläche legen
- Dichtung über eine **TPU-Einlage in einer umlaufenden Nut**, verschraubt —
  nicht geklebt
- PEI-Flüssigkleber ist Betthaftung, kein Bauteilkleber
- Einteilig gedruckte Behälter bleiben ohne Nachbehandlung selten dicht

## Toleranzen, die man nicht wegkonstruiert

Warping bei ASA und PETG zieht lange, flache Teile an den Ecken hoch. Große
Bodenflächen brauchen Anbindung; ein Teil, das 200 mm lang ist, ist nach dem
Abkühlen nicht exakt 200 mm lang. Wo ein Maß auf ±0,1 mm ankommt, gehört ein
Prüfstück gedruckt und gemessen, bevor das Teil entsteht.
