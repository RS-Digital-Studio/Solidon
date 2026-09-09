---
name: mehrsitzungs-setup-ist-ausgebaut
description: "Robert am 09.09.2026: alles zu parallelen Sitzungen raus — Sitzungsbrett, Torschloss, Worktree-Weg, privater Index. Nicht erneut vorschlagen."
metadata:
  type: feedback
---

Am 09.09.2026 hat Robert gesagt, das Claude-Code- und Codex-Setup sei zu
kompliziert, und angewiesen, **alles auszubauen, was mit mehreren Sitzungen zu
tun hat**. Gefallen sind an dem Tag:

- `tools/session_board.py` (das Sitzungsbrett) samt Statusleiste und
  `SessionEnd`-Hook, der das Gebiet wieder freigab
- `tools/gate_lock.py` (das Schloss, das nur einen Testlauf gleichzeitig
  zuließ) — `/pruefen` fährt die Läufe seitdem direkt
- `tools/to_main.py` (der Weg vom eigenen Worktree-Branch nach `main`)
- der private Index (`GIT_INDEX_FILE`, `git commit -o`) im `liefern`-Skill
  samt `references/git-fehlerfaelle.md`; der Lieferweg ist jetzt ein
  gewöhnlicher Commit mit genannten Pfaden
- der Nachbarhinweis im Sitzungsstart, der Commit-Hinweis „sag es den
  anderen", `/.claude/worktrees/` in `.gitignore`, `in_a_worktree()` in
  `check_env.py`
- 32 Erinnerungen und der offene Punkt RM-027, die es nur wegen des geteilten
  Baums gab

**Why:** Das Setup war über Wochen um die Annahme herum gewachsen, dass zwei
bis vier Sitzungen gleichzeitig in einem Arbeitsbaum stehen. Jede einzelne
Vorsichtsmaßnahme war begründet — zusammen kosteten sie vor jedem Commit und
vor jeder Messung mehr Aufmerksamkeit als die Arbeit selbst.

**How to apply:**

- **Nicht erneut vorschlagen.** Weder das Brett noch das Schloss noch den
  privaten Index — auch nicht in kleinerer Form. Dieselbe Lage wie bei
  [[rechtemodus-bleibt-bypass]].
- **Was vom Wissen bleibt, steht ohne Sitzungsbezug da:** gegen **HEAD**
  vergleichen statt gegen den Index, genaue Pfade statt `git add .`, den
  `--stat` vor dem Commit lesen, und Fremdlast bei einem roten Leistungstest
  gegen die Maschine prüfen ([[leistungstests-fremdlast]]).
- **Trifft man doch fremde Arbeit im Baum** — eine andere Sitzung, ein
  liegengebliebener Zwischenstand —, gilt weiter: nicht anfassen, nicht
  mitcommitten, im Bericht nennen. Der Nachweis, dass ein roter Lauf nicht der
  eigene Fehler ist, geht über einen Worktree auf HEAD mit **nur den eigenen**
  Dateien darin.
- Die Geschichte steht in `ROADMAP-ARCHIV.md` und der Git-History; sie wird
  nicht zurückgeholt.
