# RM-252: Keine Meldung an Elegoo oder OrcaSlicer — der Absturz ist nicht belegt

Stand 28.09.2026. Nachstellung: `nachstellung.py`, Ausgabe `nachstellung.out`.

## Was im Register stand

„Das Originalprojekt stürzt auch ohne Solidon ab, sobald `enable_support = 1` und
`support_type = normal(auto)` gesetzt sind (Rückgabe `0xC0000409`)." Belegt werden
sollte das mit `F:\3D Druck.review-051\sonden\druck\besteck_bisekt.out`.

## Was die Bisektion wirklich zeigt

`besteck_bisekt.py` ging von **Solidons Übergabe-3MF** aus (Solidons Netz, Solidons
Objektwerte) und setzte nur Schlüssel in `project_settings.config` auf die Werte des
Originals zurück. Die „kleinste Menge" aus zwei Schlüsseln gilt also für Solidons Datei,
nicht für das Originalprojekt.

## Nachgestellt am Originalprojekt

`F:\3D Dateien\Modern++Cutlery+Organizer+with+Divider.3mf`, nur gelesen, je eine Kopie:

| Fall | ElegooSlicer 1.5.3.4 | OrcaSlicer 2.4.2 |
|---|---|---|
| wie es ist (Stützen aus, `tree(auto)`) | Rückgabe 0, G-Code | liest das Projekt nicht (`CLI::run found error`) |
| `enable_support = 1` | Rückgabe 0, G-Code | liest das Projekt nicht |
| `enable_support = 1`, `support_type = normal(auto)` | **Rückgabe 0, G-Code** | liest das Projekt nicht |

Das Originalprojekt stürzt nicht ab. OrcaSlicer taugt an diesem Elegoo-Projekt nicht als
Gegenprobe.

## Was bleibt

Aus den Läufen vom 26.09.2026 (`besteck_absturz2.out`, `besteck_absturz3.out`): Mit dem
**rohen Netz** der Datei läuft Solidons Übergabe mit Gitterstützen durch (908 min, 670 m
Stütze); mit **Solidons aufbereitetem Netz** (gleiche Dreieckzahl 59 744, dicht, fünf
Schalen) scheitert derselbe Lauf. Offen ist, was an Solidons Netz den Slicer abstürzen
lässt: ein Fehler Solidons oder einer des Slicers, den Solidon auslöst. Erst wenn das
geklärt ist, gibt es etwas zu melden — mit einer Datei, die der Hersteller nachfahren
kann (Lizenz des Modells vorher prüfen).

Nach Roberts Reihenfolge gehört das hinter 0.5.1. Der Registereintrag RM-252 ist im Zweig
`uebergabe-gesamtpruefung` berichtigt.
