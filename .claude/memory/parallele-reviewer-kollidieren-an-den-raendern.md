---
name: parallele-reviewer-kollidieren-an-den-raendern
description: "Elf parallele Review-Agenten mit disjunkten Gebieten kollidieren trotzdem an vier Stellen — Kataloge, Beschriftungen, test_errors-Listen, derselbe Fund zweimal; die Übernahme braucht eine Reihenfolge und einen Nachlauf."
metadata: 
  node_type: memory
  type: project
  originSessionId: 49da6b80-5991-4fc3-a51f-b6e09a938d38
  modified: 2026-09-13T04:28:06.438Z
---

Durchsicht v0.4.1 (13.09.2026): 402 Commits, elf Reviewer je Gebiet in
eigenen Worktrees, Patches nacheinander in den Hauptbaum übernommen.
Disjunkte Dateien reichten nicht — vier Kollisionen, alle an Rändern, die
kein Gebiet allein besitzt:

- **Kataloge (`app/i18n/locales/*.json`)**: fünf Gebiete schreiben hinein.
  Ein Patch passt nur, wenn die Zeilen sortiert eingefügt und die Datei
  vorher auf LF steht; die andere Sitzung hatte CRLF hinterlassen, und
  `git apply` scheiterte an jeder Zeile. Normalisieren, dann hunkweise.
- **Beschriftungen (`app/ui/labels.py`)**: zwei Reviewer gaben demselben
  Schlüssel verschiedene Wörter („Kantenkennung"/„Kantenschlüssel"), ein
  dritter verlegte die Quelle (`mark`) ins Protokoll — der Eintrag des
  zweiten war danach **tot**, und `test_the_dictionary_carries_nothing_dead`
  wurde erst nach der Zusammenführung rot. Nach jedem Katalog- oder
  Beschriftungspatch `test_value_labels` und `test_translations` fahren.
- **Listen in Tests (`tests/test_errors.py::_NOT_A_RANGE`)**: vier Reviewer
  trugen dieselben drei Beschränkungen ein, die andere Sitzung auch. Der
  erste gewinnt, die übrigen Hunks werden ausgelassen (`--exclude`).
- **Derselbe Fund zweimal**: Leistung (P) und Erkennung (A2) fanden die
  Temporärdateien, P und Viewport (D) das fehlende Aufwärmen. Der bessere
  Fix (D: nur bei neuer Geometrie) ersetzt den ersten — dafür den ersten
  Patch hunkweise zurücknehmen (`git apply -R` auf den Teilpatch), nie die
  Datei zurücksetzen.

**Und der Torlauf misst einen Zeitpunkt**: Ein Testlauf, der vor einem
Patch startete und danach die Datei von der Platte las, meldete
„`bead_edges` nimmt kein `cancelled`" — Signaturen aus dem alten Prozess,
Aufrufe aus der neuen Datei. Nachlauf allein: grün. Nach dem letzten Patch
alles noch einmal, was zwischendurch lief.

**Why:** Die Gebietsgrenzen folgen den Modulen, die Kollisionen den
Querschnitten (Sprache, Fehlerliste, Beschriftung). Wer das nicht einplant,
übernimmt Patches, die je für sich grün sind und zusammen rot.

**How to apply:** Reihenfolge Kern → Export → Doku → Dialoge → Fenster →
Viewport, je Patch `--exclude` für Dateien, die die andere Sitzung oder ein
früherer Patch schon hat; Kataloge per Skript sortiert einfügen; nach dem
letzten Patch `test_value_labels`, `test_translations`, `test_errors`,
`test_registry_consistency` und die Fensterdateien getrennt. Agent-Worktrees
über `isolation: worktree` scheitern, sobald eine fremde Sitzung im
Hauptbaum schreibt („git identity could not be verified") — dann
`git worktree add --detach <scratch>/wt-X HEAD` von Hand und dem Agenten
den Pfad in jeden Befehl geben. Siehe [[zweite-sitzung-im-selben-baum]] und
[[agent-edits-schreiben-crlf]].
