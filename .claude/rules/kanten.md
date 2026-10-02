---
description: "Kantenoperationen an beiden Kernen — Gruppen nach Lage, gebogene Züge, Bindung an exakte Kanten, Auslassen je Kontur, Zähleinheit, Befunde mit Ort und Weg"
paths:
  - "app/core/geom/edge_ops.py"
  - "app/core/geom/edges.py"
  - "app/core/brep/edit.py"
---

# Regeln für Kantenoperationen

Verrunden, Fase und Wulst an beiden Kernen. Messwerte und Anlässe:
`konzepte/begruendungen/regel-operationen.md`, „Kantengruppen und gebogene Züge“.

## Gruppen und Züge

Nur `edges.choose` fragt die Lage: Strecken nach Richtung, Ränder nur waagerecht
(`edge_lie_of`), ein „Senkrecht“ beschrifteter zu keiner. Ein gebogener Zug wird
durch seine Knoten gezogen (`_swept_tool`, RM-279). Eine Gruppe lässt aus, was
das Maß nicht trägt (`contact_band_limits`, `edges.too_narrow` mit Zahl und
Stelle); trägt keine, sagt sie mit dem größten passenden Maß ab — gefragt an
allen Zügen der Auswahl (`_why_it_does_not_fit`), nicht nur an den belegten.

## Am exakten Körper

- **Gebunden wird je native Kante** (`brep.edit.native_edges_of_segments`), nur
  vollständig abgedeckt: Eine unvollständige verliert ihre Strecken, die übrigen
  Kanten des Zugs bleiben. Ein Stück ohne Kante meldet `edges.unmapped` mit dem
  Weg `MESH_AND_RETRY`; ein Stück auf einer anderswo zu schmalen Kante gehört
  zu `edges.too_narrow`.
- **Gezählt wird in nativen Kanten** (`too_narrow`, `thin_wall`,
  `exact_group_skipped`, `worked`), in Stellen nur ohne Kante — sonst nennt
  derselbe Körper je Fassung eine andere Zahl.
- **Ausgelassen wird je Kontur**: OpenCASCADE setzt eine Rundung über
  tangentiale Kanten fort; eine Kante allein wegzulassen ließe sie gerundet.
  Die Wand prüft `fillet_group` je Kontur vor jedem Bau, auch an fortgesetzten
  Kanten (`edges.thin_wall` statt Absage der ganzen Gruppe).
- **Zuerst fragen, was der Bau sagt**: Fehlkonturen und Fehlecken, ungültige
  Flächen, freie Kanten, offene Dreiecke — über die Historie zur Kontur; dann
  Proben je Kontur ohne Tessellierung, zuletzt je eine Kontur weg bis
  `LEAVE_ONE_OUT_LIMIT`. Grenzen sind Zahlen, keine Zeiten; Fortschritt ab dem
  ersten gescheiterten Bau.
- **Ein Befund je Grund mit allen Umrissen**, ohne Bibliotheksnamen und mit
  Weg; was der exakte Kern nicht baut, bietet das Dreiecksmodell an.
- **Eine Rundung oder Fase legt keine Wendel an**: Trägt der Eingang kein
  Gewinde, liest das Ergebnis keines (`features_of(known_threads=())`) — die
  Lesung kostete am gerundeten Lochbrett über die Hälfte der Auswertung.
