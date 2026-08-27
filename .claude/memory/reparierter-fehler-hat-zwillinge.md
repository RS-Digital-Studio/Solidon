---
name: reparierter-fehler-hat-zwillinge
description: "Wer einen Fehler behebt, sucht seine Geschwister — der Gesamtreview vom 25.08.2026 fand denselben behobenen Fehler fünffach unbehoben an Nachbarstellen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 16dae8e9-6992-47e8-9e0f-c3edfb514eea
  modified: 2026-08-25T13:08:25.694Z
---

**Der Gesamtreview vom 25.08.2026 (~180 Befunde, ~30 hoch; der Bericht
liegt seit ff7eaaae nur noch in der Git-History)
zeigte ein tragendes Muster: Ein reparierter Fehler hat unreparierte
Zwillinge.** Fünf der schwersten Befunde waren exakt der Fehler, der an einer
Nachbarstelle schon einmal behoben und dort sogar im Docstring dokumentiert
war:

- `drill` bekam `anchor="mouth"` gegen „bohrt ab der Mitte" — `countersink`
  und `plug_hole` nicht.
- `sketch_extrude`/`loft` lesen die Zeichenebene seit einem dokumentierten
  Fix — `sketch_pocket`/`sketch_sweep` nicht.
- `ValueField` fängt Ausdrücke in float-Feldern (Docstring beschreibt den
  alten Absturz) — der int-Zwilling stürzt weiter.
- `_on_split_busy` blendet den Abbrechen-Knopf richtig aus — `_on_agent_busy`
  hat den alten Fehler.
- `write_plan` wandelt `OSError` in einen Satz — `write_assembly` daneben
  nicht.

**Fall sechs, und er verschärft die Regel (25.08. abends):** `moved_features`
bekam beim C-Paket `dataclasses.replace` gegen die Fünf-von-sieben-Handkopie,
samt warnendem Kommentar — und 150 Zeilen weiter oben in **derselben Datei**
stand die zweite Handkopie (`apply_mapping`) und blieb. Unsichtbar, weil die
zwei verlorenen Felder bei erkannten Merkmalen bis dahin immer leer waren;
messbar erst, als ce's created_by-Tor ihnen Inhalt gab. Sechs Merkmale mit
Erzeuger hinein, null heraus.

**Why:** Ein Fix wird dort gemacht, wo der Fund war, und der Docstring
dokumentiert die Lehre — aber niemand fragt, wo dieselbe Konstruktion noch
steht. Die Lehre reist nicht von selbst zu den Geschwistern.

**How to apply:** Nach jedem behobenen Fehler die Geschwister suchen, bevor
der Commit fertig ist: grep nach dem Muster (dieselbe API, derselbe
Signalname, dieselbe Vorbelegungsquelle) — **zuerst in derselben Datei**,
denn dort wohnen Zwillinge am dichtesten und werden am sichersten übersehen, und jede Fundstelle entweder
mitfixen oder im Commit benennen, warum sie nicht betroffen ist. Beim Review
umgekehrt: Wo ein Docstring einen behobenen Fehler beschreibt, ist die
Nachbarschaft der erste Ort zum Suchen.

Verwandt: [[was-die-suite-nicht-findet]], [[eine-kette-endet-am-letzten-glied]],
[[sollwert-aus-dem-pruefling]].
