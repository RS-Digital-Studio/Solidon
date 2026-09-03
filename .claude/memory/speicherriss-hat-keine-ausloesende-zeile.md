---
name: speicherriss-hat-keine-ausloesende-zeile
description: Zwei belanglose Instanzattribute rissen eine Testdatei; fünf Proben an der auslösenden Zeile blieben alle rot und schlossen nichts aus.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1b79d3f9-e57d-4e8a-ac31-2b25393cae9e
  modified: 2026-09-03T12:53:31.406Z
---

Bei einem speicherabhängigen Riss ist die auslösende Zeile **nie** die Ursache
— und deshalb bleibt jede Probe an ihr rot, ohne etwas auszuschließen.

Gemessen am 03.09.2026 an `tests/test_viewport_decisions.py`, drei Läufe je
Zeile:

| Stand | Ergebnis |
|---|---|
| HEAD + **1** belangloses Attribut (leeres dict) | 142 passed |
| HEAD + **2** belanglose Attribute | Riss bei 28 von 148, `0xC0000374` |
| HEAD + **310** belanglose Kommentarzeilen | 142 passed |

Inhalt und Dateigröße sind damit ausgeschlossen, die **Objektgröße** belegt.
Ich hatte drei Wörterbücher am `Viewport` ergänzt und danach drei Stunden im
eigenen Code gesucht: fünf Einzelproben, alle rot, keine sagte etwas.

**Why:** Man prüft die Zeile, die den Riss sichtbar gemacht hat, weil sie die
einzige Änderung ist. Sie ist aber nur der Tropfen — die Ursache ist eine
Anhäufung, die sowieso an der Kante stand. Jede Probe an der Zeile lässt die
Anhäufung stehen und bleibt deshalb rot. Fünf rote Proben in Folge fühlen sich
wie Eingrenzung an und sind reine Bestätigung derselben falschen Frage
([[bestaetigung-verstaerkt-die-fehlannahme]]).

**How to apply:** Bei einem Riss nach einer harmlosen Änderung **zuerst** die
Bauart prüfen, nicht den Inhalt: Dieselbe Menge *belangloser* Attribute
einbauen (leere dicts genügen) und daneben dieselbe Menge Kommentarzeilen.
Reißt das Belanglose auch, gehört der Fund nicht der eigenen Zeile. Erst dann
die Ursache suchen — hier: Die Tests erzeugen ihre Ansichten lokal und geben
sie nie frei, bis ein Test `gc.collect` ruft und sie **alle auf einmal**
sterben. Ein Sammellauf nach jedem Test löst sie einzeln auf (148 passed, Preis
2,3 → 8,7 s).

**Und dieselbe Signatur hat zwei Ursachen.** `tests/test_widget_lifetime.py`
reißt an derselben Stelle, mit demselben Code und demselben Rahmen
(`gc.collect`, `test_a_released_widget_is_actually_released`) — und zwar auch
mit unverändertem `viewport.py`. Dort hilft die Fixture nicht. Wer den zweiten
Fall für den ersten hält, baut ein Aufräumen ein, das nichts tut, und hält das
Problem danach für gelöst ([[benannte-falle-schuetzt-nicht]]).

Das ist die Fassung von [[absturz-frame-ist-die-naechste-allokation]] eine
Ebene höher: Dort wandert der *Stapelrahmen*, hier wandert die *Änderung*, an
der man sucht. Verwandt: [[native-bibliotheken-speicher]],
[[fuenf-tests-eine-lage]] — fünf Proben quer zur Achse sind eine.
