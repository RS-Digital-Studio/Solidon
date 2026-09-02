---
name: worktrees-enden-auf-main
description: "Roberts Regel vom 30.08.2026: Am Ende gibt es keine getrennten Worktrees — alles landet auf main."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9c480190-d910-460e-bc5c-c2d37eab6361
  modified: 2026-09-02T12:00:00.000Z
---

Roberts Worte: *„merk dir auch es sollte am ende immer keine getrennten
worktrees geben alles auf main."* Bekräftigt am 02.09.2026, als vier
Korrektur-Agenten in Arbeitsbäumen liefen: *„alles sollte im origin main sein
und kein zusätzlichen worktree geben."* Agenten-Bäume sind deshalb nur
Zwischenablage: Diff nach main holen, Baum sofort entfernen, dann committen.

**Why:** Drei Maschinen, bis zu sechs Sitzungen — jeder Stand, der in einem
Seitenbaum liegt, existiert für alle anderen nicht und altert dort unbemerkt
([[probe-worktree-altert]]). Am 30.08.2026 lagen 25 Worktrees mit 9,4 GB
herum; die Räumung fand nichts, was nur dort lebte — aber erst nach Prüfung
jedes einzelnen. Ein Baum, der sofort nach Gebrauch fällt, braucht diese
Prüfung nie.

**How to apply:**

- Probe- und Mess-Worktrees (Mutationsproben, Gegenmessungen, Alt-Stände)
  sind Wegwerf-Werkzeug: nach Gebrauch `git worktree remove`, spätestens am
  Ende der Arbeitswelle. Nicht „für später" stehen lassen.
- **Vor `remove --force` den Status lesen — als eigenen Befehl.** Am
  30.08.2026 standen `status` und `remove --force` in einer Kette: Der Status
  zeigte drei veränderte Dateien, und der Befehl lief trotzdem, weil er schon
  abgeschickt war. Entwarnung kam erst hinterher (überholte Zwischenstände).
  Dieselbe Kausalitäts-Regel wie in [[commit-o-nimmt-den-dateistand]]: Die
  Antwort muss den Befehl noch ändern können.
- Arbeits-Worktrees (`claude --worktree`) münden per Commit in main und
  werden danach entfernt — kein Stand bleibt dort liegen.
- Am Ende einer Sitzung oder eines Pakets gilt: `git worktree list` zeigt
  nur den Hauptbaum, und alles Gebaute ist auf main (der post-commit-Hook
  pusht es).
- Dauerhafte Seitenzweige mit eigener Arbeit neben main sind derselbe Fall
  in Branch-Gestalt — Arbeit lebt auf main oder gar nicht; ein Archiv-Branch
  für ausdrücklich Abgelehntes ist Roberts Entscheidung, kein Normalfall.
