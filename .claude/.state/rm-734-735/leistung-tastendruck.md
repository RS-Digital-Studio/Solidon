# Tastendruck in der Suche — Palette gegen Suchfeld (RM-735, C4)

Vorgabe aus dem Ablauf (`bedienlogik`, C4): Zeilen faul beim ersten Zeichen,
verworfen bei `set_context`; jeder Tastendruck unter 0,2 s, gemessen vorher
und nachher.

**Messweg.** Gebautes Hauptfenster offscreen, 1600 × 1000, Körper
`tests/data/meshes/clean_figure.stl` geladen und gewählt wie nach einem
Klick; gewartet, bis Auswertung und Berichtsanalyse ruhen, dann zwei Sekunden
Ereignisse. Fünf Wörter Zeichen für Zeichen („verrunden“, „bohrung“,
„boolesch“, „speichern“, „qqq“), gemessen `setText` samt Abarbeiten der
Ereignisse. Je Fassung zwei Läufe zu drei Durchgängen, Fassungen im Wechsel.
Vorher: Befehlspalette am Stand `d2f8d4916` (0.6.0), geöffnet wie
`open_palette` ohne `exec`. Nachher: Suchfeld nach `action_function_search`.
Sonde: `sonden/sonde_tastendruck.py <baum> <palette|feld|feld-frueh>
<ausgabe>`, Auswertung `sonden/taste_auswerten.py <ordner> <name>=<datei>,…`.

| Fassung | Öffnen (Median / max) | 1. Zeichen | übrige Zeichen | „qqq“ |
|---|---|---|---|---|
| Palette, vorher | 30,5 / 35,3 ms | 10,3 / 18,0 ms | 3,7 / 10,8 ms | 8,5 / 10,8 ms |
| Suchfeld, erster Stand | 1,8 / 4,6 ms | 35,3 / 42,0 ms | 8,1 / 32,6 ms | 30,1 / 31,7 ms |
| nach dem Kurzwortfix | 1,6 / 4,5 ms | 35,3 / 37,6 ms | 7,6 / 31,5 ms | 6,0 / 9,3 ms |
| mit Umbruchmerker | 3,4 / 4,5 ms | 34,2 / 43,1 ms | 6,7 / 22,7 ms | 5,8 / 8,1 ms |

**Gehalten:** Kein Tastendruck braucht mehr als 43 ms; die Grenze ist 200 ms.
Das erste Zeichen baut die Zeilen (Freigabe aller 189 Operationen und der
Fensterbefehle) und kostet so viel wie Öffnen und erstes Zeichen der Palette
zusammen.

**Zwei Funde aus der Messung, beide behoben.** „qqq“ fand alle 273 Zeilen,
weil die Stammrunde ohne ein Wort ab vier Zeichen leer und damit wahr war —
ein Fehler aus der Palette, kein Leistungsthema; mit dem Fix fällt „qqq“ von
30 auf 6 ms. Und Qt fragt die Höhe jeder Trefferzeile je Tastendruck rund
zehnmal ab; der Zeilenzeichner merkt sich den Umbruch je Breite, Schrift und
Text (Höchstwert 31,5 → 22,7 ms).

**Unter Last.** Ohne Warten auf die Berichtsanalyse des eben geladenen
Körpers liefen deren Arbeitsfäden mit: Palette übrige bis 74,7 ms, Suchfeld
bis 178,6 ms — beide unter der Grenze, aber das ist eine Messung der
Analyse, nicht der Suche.

**Die ruhende Karte.** Während des Suchens rechnete `_filter` die Gruppen
der Karte mit, obwohl die Trefferliste sie verdeckt. Der frühe Ausstieg
bleibt in derselben Methode, das Leeren des Felds rechnet die Karte für die
Auswahl von dann. Am Tastendruck war er nicht messbar (Maschine in diesem
Fenster doppelt so langsam: Median 14,9 gegen 16,1 ms, Rauschen), also
gezielt: `_filter` allein im gebauten Fenster, beide Fassungen im Wechsel
aus demselben Ausgangszustand, 720 Paare. Gepaart im Median 0,42 ms und im
Mittel 0,6 ms weniger, schneller in 394 von 720 (Vorzeichentest z ≈ 2,5);
die Treffer gleich. Klein, aber belegt, also umgesetzt. Ein Test hält fest,
dass ein Stufenwechsel während der Suche nach dem Leeren dieselbe Karte
zeigt wie eine frische; gegen eine Fassung ohne Nachrechnung beim Leeren
fiel er. Sonde: `sonden/sonde_filter.py <baum> <ausgabe>`.
