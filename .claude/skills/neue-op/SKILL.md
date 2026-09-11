---
name: neue-op
description: >
  Führt durch das vollständige Anlegen einer neuen Operation in Solidon:
  Registereintrag, Parameterschema, Umsetzung gegen manifold3d/trimesh,
  Rückfallkette, Geometrietest gegen den Korpus und Übersetzungen in jedem
  Katalog aus app/i18n/locales/.
argument-hint: "[was die Operation tun soll]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Neue Operation: $ARGUMENTS

## Vorher klären

1. **Gibt es sie schon?** Register durchsehen, `app/core/geom/` und den
   Operationskatalog in Bauplan §25. Eine vorhandene Op zu erweitern ist fast
   immer besser als eine neue daneben.
2. **Wohin gehört sie?** Kategorie und Vertrag über `/bauplan` in §25 und
   dem aktuellen Register nachsehen. Passt sie in keine bestehende Kategorie,
   die Produktentscheidung klären, bevor eine neue Kategorie entsteht.
3. **Was ist mehrdeutig?** Jetzt fragen, nicht später raten (Regel 21).

Zwei bestehende Ops im selben Gebiet und die aktuelle Signatur von
`register_op` in `app/core/registry/registry.py` lesen. Die Grundfelder unten
ersetzen keine Prüfung zusätzlicher Verträge wie `reads_other_bodies`,
`touches_features`, `requires_kind` oder der Cache-Versionierung. Auch die
betroffenen Aufrufer und Menü-/Agenteneinstiege bestimmen.

## Die acht Schritte

1. **Registereintrag** — `name`, `title`, `category`, `params`, `reversible`,
   `consumes`/`produces`, `applies_to`, `deterministic`, `doc`, optional
   `shortcut`. Kürzel gegen das Register prüfen.
2. **Parameterschema** — Grenzen, Einheiten, Vorgaben, Zuordnung zu Vorderseite
   oder „Weitere Einstellungen". Vorn zwei bis drei Werte. Fertigungsspiel
   über das Materialprofil; numerische Grenzen aus dem zuständigen Kern,
   nicht als zusätzliche Streuzahl. Jeder `doc`-Satz erklärt die Wirkung.
3. **Test zuerst** — erwartete Kennzahlen gegen eine Datei aus `tests/data/`.
   Bei Geometrie ist das keine Formsache, sondern die Reihenfolge.
4. **Umsetzung** als `OpFn` im zuständigen Geometriekern. Unterstützte Mesh-
   und B-Rep-Pfade ausdrücklich bedienen und testen; keine stille Umwandlung
   exakter Körper. Mesh-Boolesches über die vorhandene Rückfallkette,
   erreichte Stufe in `solver`. Szene und Eingangsobjekte bleiben nur lesend.
5. **Zufall** — Startwert aus `ctx.seed`, `deterministic=False`.
6. **Beide Qualitätsstufen** über `ctx.quality`; für Mesh-Boolesches gilt
   `DRAFT_CHAIN` aus `app/core/geom/boolean.py`. Abbruch und Fortschritt über
   den Kontext berücksichtigen, soweit die Berechnung das erfordert.
7. **Befunde** als `findings` zurückgeben, nicht selbst protokollieren. Jeder
   Fehlerpfad trägt einen Handlungsvorschlag.
8. **Texte** über `tr()` — deutsche Quelle, und jeder Katalog aus
   `app/i18n/locales/` zieht nach.

## Abschluss

Für Geometrie-Nachweise `/geometry-review` verwenden. `/pruefen` mit den
betroffenen Dateien ausführen; das vollständige Tor erst vor einem Commit.
Danach melden: Name, Kategorie, Parameter, welche Tests sie decken,
und ob die Oberfläche etwas braucht (Kontextmenü am Feature, Kürzel,
Katalogeintrag). Ist die Op im Bauplan-Katalog noch nicht genannt, sag das —
dann gehört sie dort ergänzt, bevor sie als fertig gilt.
