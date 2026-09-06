---
name: drei-wege-check-ist-kein-enthaltensein
description: "`git apply --check --3way` sagt „passt“ auch für Hunks, deren Inhalt längst in anderer Form im Baum steht — ob etwas fehlt, misst man an Namen, Markern und Testfunktionen, nicht am Patch."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 604362f2-7546-4f58-8ac6-a717d093adc0
  modified: 2026-09-06T15:40:42.842Z
---

Am 06.09.2026 lagen 33 Einzelpatches eines Codex-Worktrees vor, gerechnet
gegen die Basis `782f98bb`. Gegen den Landungsstand gemessen meldete
`git apply --check -R` für acht „drin“, `git apply --check --3way` für 24
„fehlt, passt“. Die 24 sahen nach einer halben Stunde Handarbeit aus. Tatsächlich
fehlte **nichts**: `primitive_local_tool`, `cavity_chain_state_at`,
`_manifold_decimation`, die `format_area`-Schranke, alle zehn Testfunktionen
und alle Doku-Sätze standen im Baum — in neuerer Form, über einen anderen
Weg gelandet (der Review-Worktree hatte die Patches aufgenommen und war
gemergt worden). Der Drei-Wege-Check fand nur die alten Kontextzeilen nicht
mehr und hätte beim echten Anwenden Dubletten erzeugt.

**Why:** Ein Patch beschreibt eine *Textänderung gegen eine Basis*. Ob das
*Wissen* dahinter im Baum ist, steht nicht im Patch — sobald der Baum den
Inhalt anders formuliert trägt, greift weder der Rückwärts- noch der
Vorwärts-Check, und „passt per 3-Wege“ heißt nur: Git findet Zeilen, an die
es die Hunks hängen könnte.

**How to apply:** Vor dem Anwenden fremder Patches, deren Basis alt ist, je
Patch drei billige Fragen an den **Baum** stellen: (1) Stehen die neuen
Bezeichner (`def`/`class`/Konstanten aus den `+`-Zeilen) schon da? `grep -c`.
(2) Existieren die neuen Testfunktionen namentlich? (3) Sind neue Dateien
byteweise gleich (`cmp`)? Erst was dann noch fehlt, ist Handarbeit. Und
ungetrackte Dateien eines Worktrees fehlen in `git diff <basis>` ganz —
`git ls-files -o --exclude-standard` daneben legen, sonst sieht eine
Patchliste vollständig aus, die 22 neue Dateien nicht kennt.

Verwandt: [[probe-worktree-altert]] (ein Diff gegen einen weitergewanderten
Baum nimmt Fremdes zurück), [[exakte-passung-ist-kein-beweis]].
