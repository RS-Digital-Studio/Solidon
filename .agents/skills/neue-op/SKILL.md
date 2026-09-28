---
name: neue-op
description: >
  Führt durch das vollständige Anlegen einer neuen Operation in Solidon:
  Registereintrag, Parameterschema, Umsetzung an Netz- und exaktem Kern,
  Rückfallkette, Geometrietest gegen den Korpus und Übersetzungen in jedem
  Katalog aus app/i18n/locales/. Anleitung für die Sitzung selbst; eine
  bestehende Op ändern oder die Arbeit abgeschlossen delegieren: Agent
  solidon3d-op.
argument-hint: "[was die Operation tun soll]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Neue Operation: Angaben aus der aktuellen Anfrage

Die Checkliste „neue Operation“ aus `AGENTS.md` gilt vollständig, die Regeln
in `.claude/rules/operationen.md` und `.claude/rules/grenzen.md` ebenso. Hier
steht, was je Schritt dazugehört.

## Vorher klären

1. **Gibt es sie schon?** Register, `app/core/geom/` und den
   Operationskatalog in Bauplan §25 durchsehen. Eine vorhandene Op zu
   erweitern ist fast immer besser als eine neue daneben.
2. **Wohin gehört sie?** Kategorie und Vertrag über `.agents/skills/bauplan/SKILL.md` (§10, §25) und
   das aktuelle Register. Passt sie in keine Kategorie, erst die
   Produktentscheidung klären; jede Op kostet einen Menüeintrag, und die
   Menüs haben Grenzen.
3. **Was ist mehrdeutig?** Jetzt fragen, nicht später raten (Regel 21).

Dann zwei bestehende Ops desselben Gebiets und die aktuelle Signatur von
`register_op` in `app/core/registry/registry.py` lesen. Die Felder der
Checkliste sind nur die Grundfelder: `requires_kind`, `reads_other_bodies`,
`reads_process`, `touches_features`, `material_params` und `cache_version`
bewusst setzen oder bewusst weglassen. Aufrufer und Einstiege bestimmen — Menü, Auswahlfenster am
Merkmal, Befehlspalette, Agent, Kommandozeile.

## Je Schritt

- **Registereintrag:** das Kürzel gegen das Register prüfen; Dubletten fallen
  im Konsistenztest auf.
- **Parameterschema:** vorn zwei bis drei Werte, alles andere hinten.
  Fertigungsspiel über das Materialprofil, numerische Grenzen aus dem
  zuständigen Kern, keine Streuzahl. Jeder `doc`-Satz sagt, was der Wert
  bewirkt.
- **Test zuerst:** erwartete Kennzahlen gegen eine Datei aus `tests/data/`
  oder einen analytischen Körper; der Test ist rot, bevor die Umsetzung steht.
- **Umsetzung** als `OpFn` im zuständigen Kern. Netz und exakten Körper
  ausdrücklich bedienen und testen, keinen exakten Körper still umwandeln.
  Boolesches am Netz über die vorhandene Rückfallkette, die erreichte Stufe in
  `solver`. Szene und Eingangsobjekte bleiben nur lesend.
- **Qualitätsstufen:** Entwurf nutzt `DRAFT_CHAIN` aus
  `app/core/geom/boolean.py`. Abbruch und Fortschritt über den Kontext, soweit
  die Rechnung dauern kann.
- **Befunde** als `findings`; jeder Fehlerpfad trägt einen Handlungsvorschlag.
- **Texte** über `tr()` in der deutschen Quelle und in jedem Katalog.

## Abschluss

Geometrie-Nachweise nach `.agents/skills/geometry-review/SKILL.md`, auch am echten Modell. Die
betroffenen Tests über `.agents/skills/pruefen/SKILL.md` mit den Dateipfaden; das Entwicklungstor vor
dem Commit. Melden: Name, Kategorie, Parameter vorn und hinten, welche Tests
sie decken, beide Kerne, und was die Oberfläche braucht (Auswahlfenster am
Merkmal, Kürzel, Katalogeintrag). Fehlt die Op im Bauplan-Katalog, das sagen —
den Bauplan ändert nur eine Ansage von Robert.
