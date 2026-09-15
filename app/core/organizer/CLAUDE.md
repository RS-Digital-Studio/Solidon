# `app/core/organizer/` — reproduzierbare Fachaufteilungen

Der gespeicherte Teilungsbaum beschreibt rechteckige Fächer, Teilungen und
Wiederholungen mit stabilen Kennungen (§13, §24, §25). Er enthält Werte und
Solidon-Maßausdrücke, niemals Quelltext oder freie Geometriegesten.

| Datei | Vertrag |
|---|---|
| `serialize.py` | Geschlossener, begrenzter Parser; unveränderliche Knoten, kanonischer Text und ein Referenzsammler für Cache, Rezepte und Parameteranzeige |
| `layout.py` | Innen-/Außenbezug, lichte Fächer, tatsächliche Wandabschnitte, Modulrahmen und daraus abgeleitete Fußpunkte |
| `build.py` | Gemeinsamer Boolescher Bau; echte Bodenflächen und vorhandene Seiten/Oberkanten der Teilungswände mit stabilen Provenienz-IDs |
| `ops.py` | `create_organizer`, vollständige acht Parameter und Übersetzung desselben Layoutwerts in ein Szenenobjekt |

Innenbezug verlangt passende gemeinsame Maße benachbarter Teilungen. Außenbezug
verteilt den nach festen Wanddicken verbleibenden Raum im Verhältnis der Fachmaße.
Eine niedrige Trennwand endet zwischen Bodenoberseite und Gesamthöhe. Alle
Folgegeometrien benutzen dieselbe `OrganizerLayout`-Antwort; zusätzliche Listen
für Modulnähte oder Fußkoordinaten wären widersprüchliche Quellen.

`layout_references(text, strict=...)` ist der einzige Sammler für verschachtelte
Maße. Beschädigte Daten gelten in der strikten Verwendungsabfrage als unbekannt,
niemals als leer. Der Paketimport registriert keine Operationen.

`wall_heights` speichert gezielte Wandhöhen am vollständigen Instanzpfad. Dadurch
ändert eine Wand in einer Rasterzeile nicht automatisch die anderen Zeilen.
Bei kleinerer Fachzahl bleiben nicht mehr vorhandene Kennungen samt Ausdruck
erhalten und werden als `inactive_heights` sichtbar gemeldet. Beim Wiederherstellen
der Fachzahl gilt die Höhe wieder. Es gibt keine zweite Ausdruckssprache.

Die gerundeten Schneidprofile müssen vollständig innerhalb der Außenkontur
bleiben. Boden- und Wandmerkmale behaupten nur vorhandene Flächen; eine bis zur
Bodenoberseite entfernte Wand erhält keine senkrechten Seiten. Der Boolesche
Solver und seine Befunde reisen im Ergebnis mit.
