---
name: neue-op
description: >
  Führt durch das vollständige Anlegen einer neuen Operation in Solidon:
  Registereintrag, Parameterschema, Umsetzung gegen manifold3d/trimesh,
  Rückfallkette, Verhaltenstest, bei Geometrie ein Korpustest und
  Übersetzungen in allen ausgelieferten Sprachen.
argument-hint: "[was die Operation tun soll]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Neue Operation: $ARGUMENTS

## Vorher klären

1. **Gibt es sie schon?** Register durchsehen, `app/core/geom/` und den
   Operationskatalog in Bauplan §25. Eine vorhandene Op zu erweitern ist fast
   immer besser als eine neue daneben.
2. **Wohin gehört sie?** Kategorie aus §25: Szene, Parameter, Passungen,
   Reparatur, Transformation, Boolesch, Bohrungen, Druckvorbereitung, Import,
   Farbe, Beschriftung, Netz, Varianten. Passt sie in keine, ist das eine
   Frage an Robert, keine eigene Entscheidung.
3. **Was ist mehrdeutig?** Jetzt fragen, nicht später raten (Regel 21).

Zwei bestehende Ops im selben Gebiet lesen, bevor die erste Zeile entsteht.

## Die acht Schritte

1. **Registereintrag** — `name`, `title`, `category`, `params`, `reversible`,
   `consumes`/`produces`, `applies_to`, `deterministic`, `doc`, optional
   `shortcut`. Kürzel gegen das Register prüfen.
2. **Parameterschema** — Grenzen, Einheiten, Vorgaben, Zuordnung zu Vorderseite
   oder „Weitere Einstellungen". Vorn zwei bis drei Werte. Fertigungsspiel als
   Projekt- oder Profilwert (`auto:<material>`), Rechentoleranzen über §11.2.
   Jeder `doc`-Satz sagt, was der Wert bewirkt.
3. **Test zuerst** — jede Op mit Verhaltenstest; bei Geometrie zusätzlich
   erwartete Kennzahlen gegen eine Datei aus `tests/data/`. Das ist keine
   Formsache, sondern die Reihenfolge.
4. **Umsetzung** als `OpFn` gegen `manifold3d`/`trimesh`. Boolesches über die
   Rückfallkette, erreichte Stufe in `solver`.
5. **Zufall** — Startwert aus `ctx.seed`, `deterministic=False`.
6. **Beide Qualitätsstufen** über `ctx.quality`; in Entwurf endet die Kette
   nach Stufe 2.
7. **Befunde** als `findings` zurückgeben, nicht selbst protokollieren. Jeder
   nutzersichtbare `AppError` trägt eine passende Handlung.
8. **Texte** über `tr()` in jedem Katalog aus `app/i18n/locales/`.

## Abschluss

`/pruefen`. Danach melden: Name, Kategorie, Parameter, welche Tests sie decken,
und ob die Oberfläche etwas braucht (Kontextmenü am Feature, Kürzel,
Katalogeintrag). Ist die Op im Bauplan-Katalog noch nicht genannt, sag das —
dann gehört sie dort ergänzt, bevor sie als fertig gilt.
