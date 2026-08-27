---
name: lizenzmanifest-nach-grenzdatei-neu-bauen
description: "Ändert man eine der vier Lizenz-Grenzdateien, wird das lokale Manifest stale und test_packaging rot — neu bauen, nicht wegdrücken."
metadata: 
  node_type: memory
  type: project
  originSessionId: b43adab7-a91f-43ef-8700-07b9bf1ece41
  modified: 2026-08-26T04:48:49.614Z
---

Wer eine der vier Lizenz-Grenzdateien ändert (`scene/history.py`,
`export/writer.py`, `export/handover.py`, `agent/session.py`), macht das lokale
Lizenzmanifest stale: `tests/test_packaging.py::test_a_manifest_that_no_longer_covers_the_boundary_files_stops_the_build`
wird rot mit „Das Manifest deckt diese Datei(en) nicht mehr: …". Das Manifest
hasht den **Inhalt** der Grenzdateien; ein geänderter Inhalt passt nicht mehr
zum alten Hash.

**Neu bauen ist der saubere Weg, nicht löschen.** `python tools/build_licence_module.py`
kompiliert das Prüfmodul (Cython, braucht MSVC — siehe [[msvc-erkennung-vs18]],
also über `vcvars64.bat` + `DISTUTILS_USE_SDK=1`, am robustesten aus einer
Batch-Datei via PowerShell `cmd.exe /c <bat>`; Git Bash verschluckt das `/c`).
Der Seed ist je Bau **zufällig** und wird verworfen — Modul und Manifest sind
ein Paar, das Manifest lässt sich nicht isoliert neu signieren, `main()` muss
ganz laufen.

**Es ist ein gitignoriertes je-Baum-Artefakt** (`packaging/build/`,
`.gitignore:16`), kein Repo-Fehler: Nichts zu committen, der eigene Neubau
grünt nur den eigenen Baum, jede parallele Sitzung hat ihr eigenes stale
Manifest. Der frische Klon hat gar keins → der Test **überspringt** (`skip`),
deshalb ist die CI grün. Der echte Paketbau ruft das Werkzeug ohnehin und
erzeugt ein frisches, deckendes Manifest — es wird kein gesperrtes Paket
ausgeliefert.

**Why:** Am 25./26.08.2026 zweimal falsch eingeordnet: erst als „nur lokales
Artefakt, also löschen und überspringen" — das drückt den Wächter weg, statt
ihn zu erfüllen. Eine zweite Sitzung fand denselben Punkt in ihrem frischen Tor
reproduzierbar rot (history.py **und** session.py, zwei Grenzdateien von zwei
Sitzungen zugleich).

**How to apply:** Nach jeder Änderung an einer der vier Grenzdateien das
Lizenzmodul neu bauen. Rot heißt hier nicht „Repo kaputt", aber auch nicht
„ignorieren" — es heißt „dein lokales Manifest ist alt". Verwandt:
[[reparierter-fehler-hat-zwillinge]] (die zwei stale Dateien kamen aus zwei
verschiedenen Fixes an Nachbarstellen).
