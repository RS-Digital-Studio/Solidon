---
name: regel-gilt-je-bedienort
description: "Eine Bedienregel, die an einem Ort eingelöst ist, gilt am zweiten Ort noch nicht — „Was aus einem Baustein kam, meint den Baustein" galt im Merkmalfenster, nicht am Griff im Bild; die Sonde vom 14.09.2026 fand den Griff, der ein Schlüsselloch zerriss."
metadata:
  type: feedback
---

Am 14.09.2026 galt „Ein Merkmal aus einem Baustein meint den Baustein" seit
vier Tagen — für die Felder rechts (`part_actions`, `stepChangeRequested`).
Der Griff im Bild wusste davon nichts: `featureMoved` → `move_feature` auf die
Tasche des Schlüssellochs, der Schlitz blieb stehen, zehn Verrundungen
verloren ihre Erkennung. Dazu saß ein Baustein für Bohrungen auf der
Deckfläche statt in der gewählten Bohrung (`_face_to_seat_on` fragte nur nach
Flächen), und `count` war im Merkmalfenster eine Länge in Millimetern.

**Why:** Eine Regel wird dort eingebaut, wo der Befund war. Die anderen
Bedienorte derselben Sache — Griff, Bewegen-Leiste, Doppelklick, Agent — laufen
über eigene Signale und eigene Handler und bleiben beim alten Verhalten, ohne
dass ein Test rot wird. Gefunden wird das nur, wenn man jeden Ort für dieselbe
Sache einmal fährt.

**How to apply:** Bei einer Regel über eine Sache (Baustein, Merkmal, Schritt)
die Bedienorte aufzählen — Felder rechts, Griff im Bild, Leiste, Kontextmenü,
Verlauf, Agent — und je Ort einen Zug messen, bevor die Regel als eingelöst
gilt. Für Bausteine: `probe_parts.py`/`probe_gizmo.py` im Scratchpad fahren
jeden Baustein durch Sitz, Dialogwert, Griff, Einsetzen, Panel und Verlauf
(siehe [[sonde-ueber-alle-operationen]] für die Bauart). Verwandt:
[[zwei-dinge-nur-eines-geprueft]], [[die-halbe-regel-sieht-aus-wie-eine-ganze]].
