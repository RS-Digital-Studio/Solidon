---
name: patchuebernahme-in-den-geteilten-baum
description: "Patches aus Agent-Worktrees in einen Baum übernehmen, in dem vier Sitzungen ungestaged schreiben: git apply -3 scheitert an jeder schmutzigen Datei und bricht ganz ab; Kataloge und Changelog per Schlüssel- und Ankerskript; fremde Werkzeuge schreiben ganze Dateien als CRLF, grep -c '\\r' zählt falsch."
metadata: 
  node_type: memory
  type: project
  originSessionId: 49da6b80-5991-4fc3-a51f-b6e09a938d38
  modified: 2026-09-14T16:31:27.944Z
---

Abarbeitung vom 14.09.2026: sechs Pakete (W1–W9) aus eigenen Worktrees in
`F:\3D Druck` übernommen, während vier andere Sitzungen dort ungestaged
arbeiteten. Was dabei zuschnappte:

- **`git apply -3` verlangt, dass die Datei im Arbeitsbaum dem Index
  entspricht** („does not match index"). Trifft der Patch eine Datei, die
  eine andere Sitzung — oder das eigene vorige Paket — ungestaged geändert
  hat, bricht der *ganze* Aufruf ab, auch für die sauberen Dateien (W7:
  Exit 1 wegen `session.py`, nichts angewendet). Weg: die schmutzigen
  Dateien mit `--exclude` aus dem 3-Wege-Lauf nehmen, danach je Datei
  `git apply --include=<datei>` ohne `-3` (Kontext reicht meist), und
  `git reset -q` hinterher, weil `-3` in den geteilten Index schreibt.
- **Kataloge und Changelog nie per Patch**, sobald jemand anderes darin
  schreibt: `kataloge_aus_patch.py` liest die `-`/`+`-Zeilen je Sprache aus
  dem Patch und fügt nach Schlüssel sortiert ein; `changelog_aus_patch.py`
  setzt die `+`-Zeile hinter die Kontextzeile davor, sonst vor `## 0.4.1`.
  Ein `os.replace` auf eine Datei, die ein anderer Prozess gerade hält,
  wirft `PermissionError` — sechsmal mit wachsender Pause wiederholen.
- **Fremde Werkzeuge schreiben ganze Dateien als CRLF** (viewport.py mit
  14 865 Zeilen, main_window.py 16 401, panels.py 6 105). `grep -c $'\r'`
  meldete dafür 0; zählen mit `read_bytes().count(b'\r\n')` und vor jedem
  Testlauf normalisieren — das ändert für git nichts, für `git apply` viel.
- **Wer im geteilten Baum rote Tests sieht, misst erst am sauberen HEAD
  in einem Worktree** (`git worktree add --detach`), dann HEAD plus eigene
  Patches, dann fremde Arbeitskopien einzeln hineinkopiert. So waren die
  Heap-Abrisse in `test_filament_picker` (0xc0000374) und zwei rote
  `test_ui`-Tests einem fremden Hunk zuzuordnen, nicht den eigenen Paketen.
- **Ein Peer, der „Blob aus HEAD plus meine Zeilen" in den Arbeitsbaum
  schreibt, löscht fremde ungestagete Hunks.** Vorher abstimmen: Zeilen in
  die vorhandene Arbeitskopie einfügen, den Blob nur für den privaten Index
  bauen.

**Why:** Ein Worktree je Paket hält die Agenten auseinander, die Übernahme
trifft aber immer den einen Baum, in dem alle anderen gerade schreiben.

**How to apply:** Vor der Übernahme `git status --short` gegen die
Patchdateien schneiden (`comm -12`), die Schnittmenge gesondert behandeln,
nach jedem Paket CRLF binär zählen und die betroffenen Fensterdateien
getrennt fahren. Siehe [[parallele-reviewer-kollidieren-an-den-raendern]],
[[zweite-sitzung-im-selben-baum]] und [[agent-edits-schreiben-crlf]].
