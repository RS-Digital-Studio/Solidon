# P1.3 — echte Passungsprobe nach den Konturcommits

Lesender Anschlussplan, keine bereits bestandene Implementierung.

## Vertrag

- `scene.fits.check` prüft weiter die benannte Maßbeziehung. Eine geometrische
  Probe darf dieses Fertigungsspiel nicht mit geometrischer Kollisionsfreiheit
  gleichsetzen. Ein Pressmaß enthält absichtlich Überdeckung.
- Getrennte Druckplatten (`SceneObject.plate`) haben keine gemeinsame
  Einbaulage. Ebenso beweist räumliche Trennung auf einer Platte keine passende
  Verbindung. Für eine Lageprobe müssen die beiden ausgewählten radialen
  Merkmale nachweislich dieselbe Achse und einen überlappenden axialen Bereich
  haben; Endlage/Einschubtiefe werden nicht geraten.
- Auch in belegter Lage bleibt das Ergebnis auf diese Lage begrenzt. Weder
  ein vollständiger Montageweg noch Schrumpfung, Rauheit und Elastizität sind
  damit geprüft. Die vorhandene diskrete `check_join_path`-Probe ist kein
  kontinuierlicher Wegbeweis.
- Vorliegende Netze unverändert prüfen. Keine Polygonkorrektur, keine
  geometrieverändernde Reparatur, kein Jitter und kein Voxelrückfall dürfen
  einen fehlgeschlagenen Nachweis in einen grünen verwandeln.

## Vorhandene Wege und zu prüfende Grenzen

- `geom.boolean.boolean("intersection", ..., allow_empty=True,
  stages=("direct",), cancelled=...)` unterscheidet gültige leere Ausgabe
  vom Kernfehler. `shared_volume` tut das nicht zuverlässig: Fehler können
  dort als null erscheinen. Diesen Helfer nicht als Nachweis verwenden.
- Native Körper: `brep.kernel.boolean_builder("intersection", ...)`
  konfiguriert `SetNonDestructive(True)` vor Build. Danach IsDone/Fehler,
  native Ergebnisgültigkeit und Volumen prüfen; eine gültige leere
  Verschneidung ist zulässig. Vor und nach dem nativen Aufruf Abbruch lesen.
- Gemischte Körper: Meshzwilling des nativen Körpers ist eine angenäherte
  Probe und muss so ausgewiesen werden. Keine pauschale Aussage über den
  exakten Träger aus einer gröberen Tessellation.
- `geom.measure.surface_gap` nutzt den vorhandenen vollständigen
  Manifold-Raumindex einschließlich Kante gegen Kante und gibt bei ungültiger
  Übernahme None. Abbruchkontrolle und Suchweite am tatsächlichen Aufrufer
  prüfen. Ein kleinster Abstand allein beschreibt keine vollständige Passung.
- Numerische Volumengrenze fachlich aus Auflösung ableiten; keine
  dimensionswidrige Übernahme von EPS_GEOM als beliebiger Volumengrenze.

## Anschluss

- `fits.check` bekommt optional den bestehenden CancelToken; Weiterleitung
  durch `_check_one` und den geometrischen Prüfweg. Keine Qt-Abhängigkeit.
- `scene.evaluate` veröffentlicht derzeit `progress(1.0)` und die gesammelten
  Cacheeinträge vor `check_fits`. Vollständigkeitsmeldung und Cacheveröffentlichung
  gehören hinter sämtliche abbrechbaren Abschlussprüfungen. Bei Abbruch darf
  auch hier kein Teilcache entstehen.
- Zweiter Aufrufer im Export: `export/writer.py` bei fits_walls. Dort ebenfalls
  Abbruch und dieselben aktuellen Befunde weiterreichen, keine zweite Prüfung.
- `agent/checks` und `perceive/digest` übernehmen seit dem Konturpaket sämtliche
  `fit.*`-Befunde; neue Codes müssen keine zusätzliche Whitelist erhalten.
- Zwei passende Kreismaße plus eine unsichere reale Kontur bleiben als solche
  sichtbar, auch wenn eine einzelne Polygonstellung kollisionsfrei ist.

## Unabhängige Nachweise

1. Innenpolygon Ø30 mit 16 Segmenten und feinerer Stift Ø29,6: reales
   Eindringen trotz passendem Kreisvergleich.
2. Gleichphasige grobe Polygone können zusammenpassen; um 11,25° gedreht
   entsteht eine andere geometrische Aussage bei identischem Durchmesser.
3. Getrennte Platten und auseinander angeordnete Teile: Einbaulage offen.
4. Koaxiale Verbindung mit Boden-/Schulterkollision: vollständige Körper
   berücksichtigen, nicht allein den ausgewählten Mantel.
5. Netz, nativ und gemischt, verschiedene Tessellierung und Unterteilung,
   gemeinsame Rotation/Translation, Quellen vor/nachher unverändert.
6. Offene Netze, ungültiger nativer Körper, Kernfehler und Abbruch liefern
   keinen Kollisionsfreiheitsbeleg. Gewolltes Pressmaß bleibt eine Presspassung.
7. Ein echtes Dokument über Auswertung, Cache, Wiederöffnung, Undo/Redo und
   Export; kein Cache und keine Fertigmeldung bei abgebrochener Probe.

Fensterdateien und Leistungsprüfungen bleiben ausschließlich beim Release.
