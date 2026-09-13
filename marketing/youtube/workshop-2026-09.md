# YouTube-Produktion: STL passend machen

Produktionsauftrag (Robert, 13.09.2026): zehn Tage mit fünf Tutorials und fünf
ergänzenden Shorts, jedes Thema auf Deutsch und Englisch, verständlich für
Neueinsteiger und auf Reichweite getrimmt. Die Termine unten sind der lokale
Anschlussplan; ob sie in YouTube Studio stehen, sagt der Abschnitt
„Stand" am Ende.

## Kalender

Alle Zeiten Europe/Berlin. Beide Sprachen erscheinen zusammen, Tutorials um
12:00 Uhr, Shorts am folgenden Tag um 18:00 Uhr. Der vorherige lokale
[Veröffentlichungsplan](publication-plan-2026-09.md) nennt den 14. September
als letzten bereits eingeplanten Short-Tag.

| Datum | Format | Thema | Produktionskennung |
|---|---|---|---|
| 15.09.2026 | Tutorial DE + EN | Löcher vergrößern und verschieben, ohne neu zu zeichnen | `bohrung-anpassen` |
| 16.09.2026 | Short DE + EN | STL passt fast? Löcher ändern, Teil behalten | `bohrung-anpassen` |
| 17.09.2026 | Tutorial DE + EN | Eine Zahl ändern, beide Löcher folgen (benannte Maße) | `stl-varianten` |
| 18.09.2026 | Short DE + EN | Eine STL, zwei Zahlen, neue Variante | `stl-varianten` |
| 19.09.2026 | Tutorial DE + EN | Vorschau: aus einem Loch wird ein Langloch | `langloch` |
| 20.09.2026 | Short DE + EN | Schraube soll verstellbar sein? Loch zum Langloch | `langloch` |
| 21.09.2026 | Tutorial DE + EN | Kanten abrunden und anfasen, direkt am fertigen Modell | `stl-kanten` |
| 22.09.2026 | Short DE + EN | Scharfe Kanten an der STL? Abrunden statt neu zeichnen | `stl-kanten` |
| 23.09.2026 | Tutorial DE + EN | Zwei Teile zusammenstecken: Stift und Loch in einem Schritt | `gegenstuecke` |
| 24.09.2026 | Short DE + EN | Zwei Teile verbinden: Stift und Loch in einem Schritt | `gegenstuecke` |

## Der gezeigte Weg

**Der einfache Kundenweg, nicht die Befehlspalette** (Robert, 13.09.2026).
Die erste Fassung der Aufnahmen (Codex, Nacht auf den 13.09.) öffnete jede
Operation über Bearbeiten → Befehlspalette → Suche → Enter. Das ist ein
Weg, den ein Kunde nicht nimmt. Seitdem zeigen die Filme:

| Handlung | Weg im Film |
|---|---|
| Bohrung ändern, Langloch | Loch anklicken → Karte rechts: Zahl tippen → Knopf *Übernehmen* unten |
| Verrunden, Fase, Fügeweg prüfen | Teil anklicken → Handlungsliste rechts → Dialog |
| Verschieben | Werkzeugleiste unten *Bewegen* → X tippen → Enter |
| Benanntes Maß in einen Schritt | Doppelklick auf den Schritt im Verlauf → *fx* am Feld → `@name` |
| Gegenstücke | Menü *Gegenstücke setzen* (der Dialog gehört dem Menü) |
| Rückgängig, Speichern, Öffnen | Menü, wie bisher |

**Kamera:** Nach jeder Änderung eine Nahaufnahme auf das Detail (Blickpunkt
auf die Bohrung, die Ecke, den Stift; 60 bis 130 mm Abstand, so dass der Rand
des Teils mit im Bild steht) und eine kurze Kamerafahrt um den Punkt. Nach dem
Import und am Ende eine Fahrt um das ganze Teil. Die Shorts nehmen dieselben
Nahaufnahmen (`shot(..., focus=...)`).

Die Suchfragen bestimmen den Einstieg, der konkrete App-Ablauf liefert den
Beleg. Die [Recherche](workshop-2026-09-research.md) trennt echte Suchsignale
von Vermutungen. Eine weltweite Alleinstellung wird nicht behauptet.

Komplexe Werte und Ergebnisse bekommen längere Lesedauer als ein einfacher
Klick (7 bis 13 Sekunden). Die Shorts verdichten jeweils einen Nutzen. Musik
wird wie in den bisherigen Filmen lokal erzeugt. Es gibt keinen Sprecher.

## Texte

Titel, Beschreibungen und Tags stehen in
[workshop-2026-09-copy.json](workshop-2026-09-copy.json). Sie sind für
Neueinsteiger geschrieben: zuerst das Problem („Löcher passen nicht?"), dann
die Lösung, „STL bearbeiten" / „edit STL" als Suchwort vorn, Demo-Link,
Hinweis auf die Einsteiger-Playlist, Vorschau-Hinweis auf 0.4.1, drei
Hashtags, zehn bis zwölf Tags. Keine Fremdmarken in Titeln oder Tags.
Kapitel ergänzt der Prüfer aus den wirklich aufgenommenen Zeitpunkten.

## Versionsbezug

Am 13.09.2026 lieferte die öffentliche `https://solidon3d.de/version.json`
Version 0.4.0. Der Arbeitsstand enthält 0.4.1 einschließlich der neu
gruppierten Handlungskarte. Deshalb sind die Aufnahmen als Entwicklungsvorschau
auf 0.4.1 gekennzeichnet. Ein Release-Termin wird nicht versprochen.

## Dateien und Abnahme

Ausgabeordner: `marketing/video/workshop-2026-09/`, je Thema und Sprache ein
Unterordner mit Langfilm, Short, Titelbild, Schnittplänen und Belegen.
`verify_production.py` dort ist das lokale Tor: 20 Dateien, Zeitleisten,
Geometriebelege, unabhängig nachgemessene STL-Querschnitte, Uploadtexte mit
Kapiteln (`*.upload.txt`).

Ein Film gilt erst als fertig, wenn der Aufnahmeprozess sauber beendet wurde,
der gezeigte Modellzustand geprüft ist und die MP4 Bildgröße, Bildrate, Tonspur
und Dauer erfüllt. Erstellung und YouTube-Veröffentlichung bleiben getrennte
Angaben.

## Offener Produktbefund aus dieser Produktion

Die Ergebnis-STLs nach `resize_hole`/`move_feature` und nach
`fillet_edges`/`chamfer_edges` gegen ein eingelesenes STL sind per Index
geschlossen, nach dem Verschweißen (Slicer, eigener Import) aber nicht mehr —
Solidon meldet beim Wiederöffnen „Das Modell ist nicht geschlossen". Diagnose
und Fixvorschlag (zwei Stellen: Ausgang von `boolean._kernel` verschweißen,
`edges.rounding_tool` mit `flank_overlap=BOOLEAN_OVERLAP`) stehen im Register
von `ROADMAP.md`. Im Film ist davon nichts zu sehen; die beigelegten
Beispiel-STLs werden nach dem Fix neu exportiert.

## Stand

Wird am Ende der Produktion fortgeschrieben: Aufnahmen, Kodierung, Prüfer,
Upload und Terminierung je Datei.
