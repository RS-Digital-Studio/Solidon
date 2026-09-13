---
name: changelog-waechter-nach-dem-versionssprung
description: "test_changelog prüft nur den Abschnitt von APP_VERSION — die Regeln (200 Zeichen, Großbuchstabe, kein „test\") greifen erst nach bump_version"
metadata: 
  node_type: memory
  type: project
  originSessionId: 6535be56-54ec-49cb-8596-f35a930bf28d
  modified: 2026-09-13T15:46:24.175Z
---

`tests/test_changelog.py` hält je Punkt drei Regeln: höchstens **200
Zeichen** (Update-Fenster), **Großbuchstabe am Anfang** (`point[0].isupper()`
— ein Punkt, der mit „ oder « beginnt, fällt durch), und **kein Wort aus der
Testfamilie** (`test`, `prueba`, `prova` … — trifft auch den Baustein
„Prüfstück", en „test piece", es „pieza de prueba"). Geprüft wird nur der
Abschnitt der **aktuellen** `APP_VERSION`.

Am 13.09.2026 war der Test vor `bump_version` grün (er las 0.4.0) und
danach sechsmal rot: 50 neue Punkte für 0.4.1 standen längst darin, und
erst der Versionssprung machte sie zum Prüfling.

**Why:** Wer den Abschnitt vor dem Versionssprung schreibt (so will es
Robert, [[changelog-vor-dem-versionssprung]]), bekommt vom Wächter bis zum
Bautag kein Wort. Und er meldet je Sprache nur den **ersten** Verstoß —
sechs Fehler sahen aus wie sechs Punkte und waren vierzig.

**How to apply:** Neue Punkte vor dem Schreiben selbst zählen: `len(text)
<= 200` je Sprache (Zeichen, nicht Bytes — Umlaute zählen einfach), keine
Anführungszeichen am Anfang (Operationen ohne Zeichen nennen, wie der
Abschnitt es sonst hält), keine Bausteine mit „test" im Namen. Oder
`APP_VERSION` in einer Sonde auf die kommende Fassung setzen und den Test
darüber fahren. Siehe [[texte-altern-mit-ihrer-grenze]].
