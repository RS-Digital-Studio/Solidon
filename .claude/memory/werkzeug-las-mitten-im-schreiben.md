---
name: werkzeug-las-mitten-im-schreiben
description: "Ein Befund über eine fremde Datei kann ein Lesen mitten in deren Schreibvorgang sein — der Diff verrät es, bevor eine Gegenmessung nötig wird."
metadata:
  node_type: memory
  type: feedback
  originSessionId: f37d7a68-f87d-4034-ac69-fe8f1cab6525
  modified: 2026-09-04T15:41:22.115Z
---

Im geteilten Baum ist ein Schreibvorgang kein Zeitpunkt, sondern ein Zeitraum.
Werkzeuge, die nach jedem Befehl automatisch laufen (Hooks, Wächter), treffen
ihn irgendwann — und ein halb geschriebener Python-File ist nicht nur
unformatiert, er ist syntaktisch kaputt. Der Befund ist echt gemessen und
trotzdem über nichts.

Am 04.09.2026 meldete ein Format-Hook `tools/make_video.py` zweimal als
unformatiert. Nachgemessen drei Minuten später: Exit 0, und der **Zeitstempel
der Datei war unverändert** — niemand hatte nachformatiert, sie war die ganze
Zeit in Ordnung.

**Woran man es erkennt, ohne nachzumessen** — beides kann ein Formatierer nicht
erzeugen:

- eine Zeile, die als `-` **und** `+` mit identischem Text erscheint
- ein Diff, der mitten in einem Ausdruck abbricht, mit langen reinen `-`-Blöcken

**Why:** An einem Tag gaben drei Sitzungen einander fremde Befunde weiter, die
beim Nachmessen weg waren. Jeder kostet eine Nachricht und eine Gegenmessung —
und wer den zweiten für echt hält, sucht die Ursache in seiner eigenen Datei.

**How to apply:** Vor dem Weitergeben eines Befunds über eine **fremde** Datei
den Zeitstempel gegen die aktuelle Uhrzeit halten und einmal selbst messen. Ist
der Zeitstempel Sekunden alt, war es das Schreibfenster. Und beim Empfangen
eines solchen Befunds gilt dasselbe in der anderen Richtung: erst messen, dann
den eigenen Lauf verwerfen.

Verwandt: [[parallele-sitzung-im-arbeitsbaum]], [[fremder-zwischenstand-statt-repository]],
[[fremde-erklaerung-altert-mit]], [[temp-dateien-sind-maschinenweit]].
