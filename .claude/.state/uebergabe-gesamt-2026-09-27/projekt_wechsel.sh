#!/usr/bin/env bash
# Roberts Minigolf-Projekt ohne Merkmalserkennung, alt (3018613e6) gegen neu
# (Arbeitsbaum) im Wechsel, zweimal. Gebunden aufrufen:
#   cmd //c "start /b /wait /affinity FF bash projekt_wechsel.sh"
py="/f/3D Druck/.venv/Scripts/python.exe"
probe="C:/Users/rober/AppData/Local/Temp/claude/F--3D-Druck/d53049d8-8567-40fb-bb95-f784e37acda5/scratchpad/projekt_ausrichten.py"
out="/f/3D Druck/output/review/gesamt-2026-09-27"
old="F:/3D Druck/.claude/worktrees/stand-3018613e6"
new="F:/3D Druck.gesamtfix"
export PYTHONUTF8=1
rm -f "$out/projekt-wechsel.exit"
for round in 1 2; do
  "$py" "$probe" "$old" "$out/projekt-alt-$round.txt" > "$out/projekt-alt-$round.log" 2>&1
  echo "ALT-$round-EXIT=$?" >> "$out/projekt-wechsel.exit"
  "$py" "$probe" "$new" "$out/projekt-neu-$round.txt" > "$out/projekt-neu-$round.log" 2>&1
  echo "NEU-$round-EXIT=$?" >> "$out/projekt-wechsel.exit"
done
echo "ENDE $(date +%H:%M:%S)" >> "$out/projekt-wechsel.exit"
