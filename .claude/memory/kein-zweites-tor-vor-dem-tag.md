---
name: kein-zweites-tor-vor-dem-tag
description: "Robert, 19.09.2026: Das Tor läuft vor den Commits; nach Versionssprung und Erzeugen (Bilder, Handbuch, SEO) kommt kein zweiter voller Lauf mehr — der Tag geht direkt, die CI fährt die Suiten am Tag ohnehin."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 30dcb733-80d9-4e45-9aed-0d6e20865d98
  modified: 2026-09-19T19:01:17.410Z
---

Beim Release 0.4.4 stand der Plan: Tor → Commits → Bump und Erzeugen → **noch
ein Tor** → Tag. Robert: „den tor vorm tag kannst du dir sparen".

**Why:** Der Tag-Bau in `.github/workflows/build.yml` fährt alle Suiten auf
drei Plattformen; ein lokaler Lauf über denselben Stand misst dasselbe noch
einmal und kostet eine halbe Stunde, in der nichts anderes im Baum passieren
darf. Was Bump und Erzeuger anfassen, prüfen die schnellen Wächter direkt
(`test_toolchain`, `test_changelog`, `test_website`, `test_wording`,
`test_manual`) — die reichen als Vorprüfung.

**How to apply:** Vor den Commits das volle Tor (`suite-getrennt.sh` +
`-m performance` + ruff + format + mypy). Nach `bump_version.py` und den
Erzeugern nur die betroffenen Wächter fahren, committen, taggen, und den
CI-Lauf mit `gh run watch <id> --exit-status` als Nachweis nehmen. Siehe
[[version-vor-jedem-bau-erhoehen]], [[release-weg-0-4-1-gemessen]].
