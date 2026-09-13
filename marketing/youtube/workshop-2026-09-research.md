# YouTube-Werkstattserie: Recherche und Aussagegrenzen

Stand und Abrufdatum: **13.09.2026**. Produktionsentwurf für fünf Langvideos
und fünf Shorts, jeweils in Deutsch und Englisch. Die Termine unten sind
geplant; diese Datei bestätigt keine Einplanung oder Veröffentlichung in YouTube.
Die Metadaten stehen in [workshop-2026-09-copy.json](workshop-2026-09-copy.json).
Vor der Veröffentlichung werden die Aussagen mit den fertigen Filmen abgeglichen.

## Festgelegte Themen und Termine

| Story-ID | Langvideo DE + EN | Short DE + EN | Schwerpunkt im Film | Suchgrundlage |
|---|---|---|---|---|
| `bohrung-anpassen` | 15.09.2026 | 16.09.2026 | Vorhandene STL-Bohrungen im Durchmesser und Abstand ändern; Außenmaße erhalten | Direkte Signale für „STL bearbeiten“ und „edit STL“; die konkrete Bohrungsfrage ist eine Ableitung |
| `stl-varianten` | 17.09.2026 | 18.09.2026 | Benanntes Lochmaß an einer importierten STL nachträglich ändern; Solidon-Projekt speichern und wieder öffnen | Direkte Signale für STL-Bearbeitung und Größenänderung; Interesse an benannten Varianten ist eine Hypothese |
| `langloch` | 19.09.2026 | 20.09.2026 | Eine vorhandene Bohrung zum Langloch machen; Länge und Richtung zeigen | Breites Suchthema STL-Bearbeitung; spezielle Nachfrage nach Langlöchern nicht belegt |
| `stl-kanten` | 21.09.2026 | 22.09.2026 | Senkrechte und obere Kantengruppen verrunden beziehungsweise fasen | Breites Suchthema STL-Bearbeitung; direkte Suchsignale für STL-Verrundungen schwach |
| `gegenstuecke` | 23.09.2026 | 24.09.2026 | Stift und Gegenloch gemeinsam auf zwei importierten STL-Teilen anlegen | Direkte Signale für „3d print fit“ und „3d print tolerance“; genaue Paar-Funktion ist die Produktantwort |

Die Reihenfolge verbindet nachgewiesene Suchfamilien mit anschaulichen
Solidon-Funktionen. Sie ist **keine Rangliste gemessener Suchvolumina**.
Das früh erwogene Thema „Fügeweg prüfen“ bleibt eine mögliche spätere Folge
und gehört nicht zu diesen fünf Filmen.

## Was die Nachfragebelege leisten

Erhoben wurden öffentliche Autocomplete-Antworten über Googles
Vorschlagsendpunkt mit `client=firefox` und `ds=yt`. Die Abfragen verwendeten
`hl=de&gl=DE` beziehungsweise `hl=en&gl=US`, ohne angemeldetes Nutzerkonto.
Die Antworten wurden am 13.09.2026 direkt per HTTP gelesen. Die URLs liefern
bei erneutem Abruf den dann aktuellen Stand, nicht zwingend diesen Snapshot.

Die Antworten belegen Suchformulierungen und Themenfamilien. Sie liefern
keine monatlichen Suchzahlen, keine Zielgruppenprognose und kein gesichertes
„am häufigsten gesucht“. Laut [Google Trends: Datengrundlage und
Autocomplete](https://support.google.com/trends/answer/4365533) ist
Autocomplete wegen seiner Auswahl und Filterung keine verlässliche Rangliste
der beliebtesten Begriffe. Google Trends stellt seinerseits normalisiertes
relatives Interesse dar, keine absoluten Suchvolumina.

Ein Vergleich über Google Trends mit Deutschland, YouTube-Suche und den
letzten zwölf Monaten wurde versucht. Der Endpunkt antwortete **HTTP 429**.
Daraus wurden keine Zahlen, Kurven oder Trendbehauptungen abgeleitet.

### Suchabfragen mit erhaltenem Antwort-Snapshot

Die folgenden Listen sind die bei den jeweiligen Abfragen zurückgegebenen
Vorschläge in ihrer damaligen Reihenfolge. Das sind Daten; die anschließende
Themenwahl ist redaktionelle Auswertung. Unpassende Vorschläge bleiben im
Snapshot stehen, damit schwache Ergebnisse sichtbar bleiben.

**DE: `stl `** — [direkte Abfrage](https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=de&gl=DE&q=stl+)

```json
["stl dateien bearbeiten", "stl datei in fusion 360 bearbeiten", "stl in freecad bearbeiten", "stl datei erstellen", "stl in fusion 360 bearbeiten", "stl crew", "stl bearbeiten", "stl in blender bearbeiten", "stl ocarina", "stl to step"]
```

**DE: `stl bearbeiten`** — [direkte Abfrage](https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=de&gl=DE&q=stl+bearbeiten)

```json
["stl bearbeiten", "stl bearbeiten fusion 360", "stl bearbeiten freecad", "stl bearbeiten blender", "stl bearbeiten fusion", "stl dateien bearbeiten", "blender stl bearbeiten deutsch", "onshape stl bearbeiten", "tinkercad stl bearbeiten", "meshmixer stl bearbeiten"]
```

**EN: `edit stl`** — [direkte Abfrage](https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=en&gl=US&q=edit+stl)

```json
["edit stl file in fusion 360", "edit stl files", "edit stl file in fusion 360 free", "edit stl", "edit stl in blender", "edit stl in freecad", "edit stl file in tinkercad", "edit stl file in solidworks", "edit stl in onshape", "edit stl in solidworks"]
```

**EN: `resize stl `** — [direkte Abfrage](https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=en&gl=US&q=resize+stl+)

```json
["resize stl file", "how to resize stl", "freecad resize stl", "how to resize stl in blender", "how to resize stl in fusion 360", "resize photopea", "resize svg", "resize pictures", "resize in gimp"]
```

**EN: `stl to cad`** — [direkte Abfrage](https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=en&gl=US&q=stl+to+cad)

```json
["stl to cad", "stl to cad solidworks", "stl to cad model", "stl to cad fusion 360", "convert stl to cad", "freecad stl to step", "how to convert stl to cad file", "fusion stl to cad"]
```

**EN: `3d print tolerance`** — [direkte Abfrage](https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=en&gl=US&q=3d+print+tolerance)

```json
["3d print tolerance", "3d print tolerance test", "3d print tolerance for tight fit", "3d printer tolerance calibration", "3d print hole tolerance", "improve 3d printer tolerance"]
```

**EN: `3d print fit `** — [direkte Abfrage](https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=en&gl=US&q=3d+print+fit+)

```json
["3d print fit tolerance", "3d print fit", "3d printer fitting", "3d print snap fit", "3d print press fit", "3d print snap fit joints", "3d print snap fit lid", "3d print snap fit box", "3d print snap fit fusion 360", "3d printed friction fit"]
```

**DE: `stl loch `** — [direkte Abfrage](https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=de&gl=DE&q=stl+loch+)

```json
["stl reparieren", "stl glätten", "stl schneiden"]
```

**DE: `stl verrunden `** — [direkte Abfrage](https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=de&gl=DE&q=stl+verrunden+)

```json
["stl reparieren", "stl glätten", "stl schneiden", "stellschrauben für lattung"]
```

**EN: `stl fillet `** — [direkte Abfrage](https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=en&gl=US&q=stl+fillet+)

```json
["stl fix", "stl cad"]
```

### Redaktionelle Ableitung

„STL bearbeiten“ beziehungsweise „edit STL“ steht vorn in den Titeln, wo es
zum Thema passt. Die konkrete Lösung folgt danach: Bohrung, benanntes Maß,
Langloch oder Kanten. Die Ergebnisse zu CAD und STEP zeigen ebenfalls
Interesse an weiterbearbeitbaren Dateien. Diese Serie zeigt aber keine
Wiederherstellung der ursprünglichen CAD-Konstruktion und verspricht keine
STL-zu-STEP-Konvertierung. Das gespeicherte Solidon-Projekt ist ausdrücklich
von einem exportierten STL zu unterscheiden.

Für Gegenstücke dienen „3d print fit“ und „3d print tolerance“ als nahe
Suchfamilien. Daraus folgt keine belegte Nachfrage nach genau Solidons
Paar-Dialog. Die gute Eignung von Langloch, Kantengruppen und benannten
Varianten als Filmthemen ist eine begründete Hypothese über anschauliche
Kundenprobleme, keine gemessene Suchspitze.

## Konkurrenz: was Primärquellen tatsächlich bestätigen

Abruf aller Quellen: 13.09.2026. Es fand kein vollständiger Vergleichstest
der Anwendungen statt. Eine in diesen Seiten nicht beschriebene Funktion
gilt dadurch nicht als fehlend.

| Anwendung | Bestätigter Funktionsweg | Folgerung für unsere Aussagen |
|---|---|---|
| Autodesk Fusion | [Direct Edit](https://help.autodesk.com/cloudhelp/ENU/Fusion-Mesh/files/MESH-DIRECT-EDIT.htm) erlaubt lokale Meshänderungen. Einzeländerungen innerhalb dieses Bereichs werden nicht separat in der Timeline festgehalten. [Convert Mesh](https://help.autodesk.com/cloudhelp/ENU/Fusion-Mesh/files/MESH-CONVERT-TO-SOLID.htm) beschreibt die prismatische Ableitung von Merkmalen aus Flächengruppen. | Keine Behauptung, Fusion könne STL grundsätzlich nicht bearbeiten oder Merkmale nicht ableiten. Solidons tatsächlich gezeigten Auswahl- und Maßänderungsweg erklären. |
| Blender | Der [Boolean Modifier](https://docs.blender.org/manual/en/dev/modeling/modifiers/generate/booleans.html) bearbeitet Netze durch boolesche Operationen. Der [Bevel Modifier](https://docs.blender.org/manual/id/4.5/modeling/modifiers/generate/bevel.html) rundet Meshkanten als nichtdestruktiver Modifier. | STL-Verrundung und nichtdestruktive Bearbeitung sind für sich keine belegten Alleinstellungsmerkmale. |
| Tinkercad | Das offizielle [Glossar](https://ibles-content.tinkercad.com/FBX/OHOS/J8AGQTIY/FBXOHOSJ8AGQTIY.pdf) beschreibt STL-Import. [Creating Holes](https://www.tinkercad.com/learn/overview/OM50MYLL1W5N54A?collectionId=undefined&type=TKCD) beschreibt Materialabtrag mit Lochformen. | Nicht behaupten, andere einfache Anwendungen könnten keine STL ändern oder Löcher schneiden. |
| FreeCAD | Die offizielle [Dokumentationskopie zu Part ShapeFromMesh](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Part_ShapeFromMesh.md) beschreibt Mesh → Shape, weitere Änderungen und optional Solid. Die Kopie ist archiviert; die Wiki-Seite blockierte den Abruf. | Der dokumentierte Bearbeitungsweg ist belegt. Keine Aussage über heute fehlende Funktionen oder den aktuell kürzesten UI-Pfad. |

Die belastbare Aussage über Solidon lautet für einen erfolgreich gefilmten
Fall: **„Ich öffne die STL, wähle die erkannte Bohrung und ändere ihr Maß.“**
Für die Variantenfolge: **„Ich speichere die Bearbeitung mit ihrem benannten
Maß im Solidon-Projekt und öffne sie wieder.“** Für das Paar:
**„Ich gebe die gemeinsamen Maße einmal ein und lege Stift und Gegenloch
zusammen an.“**

„Das kann keine andere App“, „die einzige Software“, „jede STL vollständig
parametrisch“ und „passt garantiert beim ersten Druck“ sind nicht belegt und
stehen nicht in den Metadaten.

## Version und Grenzen des gezeigten Kundenpfads

Die öffentliche [Versionsdatei](https://solidon3d.de/version.json) wurde von
der Hauptsitzung am 13.09.2026 per `Invoke-RestMethod` geprüft und meldete
**0.4.0**. Die lokale [Versionsdatei](../../website/version.json) bestätigt
denselben Stand. Alle vorgesehenen Aufnahmen zeigen die
**Entwicklungsoberfläche 0.4.1**, einschließlich der neu gruppierten
Handlungen rechts. Deshalb steht der Vorschauhinweis in jeder langen und
kurzen Beschreibung. Die Langlochfolge benennt die Vorschau zusätzlich in
beiden Videotiteln. Ein Veröffentlichungstermin für 0.4.1 wird nicht versprochen.

Die lokalen [Neuerungen](../../changelog/de.md) beschreiben für 0.4.1 die
nachträgliche Umwandlung erkannter Bohrungen zu Langlöchern sowie Länge und
Richtung; für 0.4.0 die gemeinsame Anlage von Gegenstücken. Die ältere
Merkmalsbearbeitung beschreibt das Ändern gemessener Werte an importierten
Teilen. Das sind Funktionsbelege, noch keine Abnahme der hier geplanten Filme.

- `bohrung-anpassen`: Durchmesser und Lochabstand werden verändert. Die
  Außenmaße müssen in der Aufnahme und ihrer Prüfung erhalten bleiben.
  Eine einzelne Rücknahme nimmt den zuletzt ausgeführten Schritt zurück;
  nicht behaupten, sie nehme automatisch die ganze Folge zurück.
- `stl-varianten`: Das Lochmaß wird als benannter Projektparameter sichtbar
  angelegt und in der Änderung benutzt. Speichern und erneutes Öffnen müssen
  über die App erfolgen. Der Erhalt des Parameters gilt für die
  Solidon-Projektdatei; eine STL trägt diese Bearbeitungsgeschichte nicht.
- `langloch`: Vorhandene einfache Bohrung ohne Senkung verwenden. Der
  [Geometrievertrag](../../app/core/geom/CLAUDE.md) schließt das nachträgliche
  Ziehen einer Bohrung mit angehängter Senkung aus. Länge und Richtung
  müssen im echten Dialog oder sichtbaren Editor vorkommen.
- `stl-kanten`: Ausschließlich die im Kundenpfad verfügbaren Gruppen
  **senkrecht** und **oben** zeigen. Einzelne Meshkanten sind im verwendeten
  UI-Pfad derzeit nicht auswählbar. Deshalb keine Einzelkantenauswahl
  ankündigen, simulieren oder aus dem allgemeinen Changelog ableiten.
- `gegenstuecke`: Beide STL-Dateien öffnen und die Paarfunktion über die
  echte App benutzen. Das gemeinsame Anlegen und Zurücknehmen am Modell
  belegen. Eine druckabhängige Passung ist kein garantierter Druckerfolg.

## Übergabe an die Produktion

Website-Link steht je Sprache in der ersten Beschreibungszeile. Deutsche
Texte sind in persönlicher Ich-Form; englische Texte ebenfalls persönlich.
Je Beschreibung höchstens drei Hashtags. Keine Kapitelzeiten, Laufzeiten,
Klickzahlen oder garantierten Ergebnisse wurden erfunden. Die tatsächlichen
Kapitel ergänzt die Hauptsitzung aus den fertigen Aufnahmen.

Lesbare Dialoge, sichtbare Auswahl, Vorschau, Übernahme und ein ruhiger Blick
auf das Ergebnis gehören in den Film. Die Titel und Beschreibungen sind vor
der Einplanung erneut gegen diesen tatsächlich aufgenommenen Ablauf zu
lesen. Ein Entwurf, ein Quelltextpfad oder eine grüne Geometrieprüfung allein
ersetzt die sichtbare Durchführung nicht.
