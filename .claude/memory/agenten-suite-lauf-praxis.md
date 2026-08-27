---
name: agenten-suite-lauf-praxis
description: "Der volle Suite-Lauf gegen qwen3:14b dauert ~1,5 h und puffert seine Ausgabe bis zum Prozessende — Zwischenstände sind nicht ablesbar."
metadata: 
  node_type: memory
  type: project
  originSessionId: 6b787794-e6cb-412f-90b5-37670d6da3f6
  modified: 2026-08-08T16:34:47.995Z
---

Der Modelllauf `tools/run_agent_suite.py --backend ollama` (39 Fälle,
qwen3:14b) brauchte am 08.08.2026 rund anderthalb Stunden. Bei Umleitung in
eine Datei puffert Python blockweise: die Datei bleibt bis zum Ende fast
leer, ein Zwischenstand ist nicht ablesbar. Exit-Code 1 heißt nur „nicht
alle Fälle gut beantwortet", nicht Fehlschlag.

**Why:** Wer den Lauf startet und nach 30 Minuten eine leere Ausgabedatei
sieht, hält ihn fälschlich für hängend — und parallel laufende schwere
pytest-Läufe sterben unter der Ollama-Last häufiger am bekannten nativen
Abriss (Familie [[rtree-abstuerze-im-langen-lauf]]).

**How to apply:** Im Hintergrund starten und auf die Fertig-Meldung warten
statt zu pollen; für Live-Fortschritt `python -u` verwenden. Während des
Laufs die volle pytest-Suite nur mit Wiederholungsbereitschaft fahren.
