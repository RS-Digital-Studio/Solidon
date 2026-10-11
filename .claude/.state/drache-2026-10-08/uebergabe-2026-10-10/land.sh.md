# land.sh

Abgelegt als Markdown, damit die Akte keine CI auslöst.

```bash
#!/usr/bin/env bash
# Landet einen Zweig per --no-ff-Merge auf dem Integrationszweig, ohne den Worktree der
# anderen Sitzung zu berühren. Aufruf: land.sh <zweig> <meldungsdatei> [<ziel>]
# <ziel> ist der Integrationszweig (Vorgabe welle4; welle3 ist seit 10.10. geschlossen).
# Der Zweig muss origin/<ziel> schon enthalten (vorher hineinmergen und prüfen).
set -euo pipefail
zweig="$1"
meldung="$2"
ziel="${3:-welle4}"
if [ "$ziel" = "welle3" ]; then
  echo "ABBRUCH: welle3 ist für 0.6.0 geschlossen" >&2
  exit 6
fi
cd "/f/3D Druck"
git fetch -q origin
basis=$(git rev-parse --verify "origin/$ziel")
spitze=$(git rev-parse --verify "origin/$zweig")
lokal=$(git rev-parse --verify "$zweig")
if [ "$spitze" != "$lokal" ]; then
  echo "ABBRUCH: $zweig lokal $lokal ungleich origin $spitze" >&2
  exit 2
fi
if ! git merge-base --is-ancestor "$basis" "$spitze"; then
  echo "ABBRUCH: origin/$ziel ($basis) ist nicht in $zweig — erst hineinmergen" >&2
  exit 3
fi
m=$(git commit-tree "$spitze^{tree}" -p "$basis" -p "$spitze" -F "$meldung")
if [ -z "$m" ] || [ "$(git rev-parse "$m^1")" != "$basis" ] || [ "$(git rev-parse "$m^2")" != "$spitze" ]; then
  echo "ABBRUCH: Merge-Commit '$m' falsch gebaut" >&2
  exit 4
fi
if [ -n "$(git diff --name-only "$spitze" "$m")" ]; then
  echo "ABBRUCH: Baum des Merges weicht vom Zweig ab" >&2
  exit 5
fi
git push origin "$m:refs/heads/$ziel"
echo "GELANDET: $zweig als $m auf $ziel (Basis $basis)"
```
