#!/usr/bin/env bash
# Ausrichten über den Minigolf-Satz, alt (3018613e6) gegen neu (Arbeitsbaum)
# im Wechsel, zweimal. Gebunden aufrufen:
#   cmd //c "start /b /wait /affinity FF bash minigolf_wechsel.sh"
py="/f/3D Druck/.venv/Scripts/python.exe"
probe="C:/Users/rober/AppData/Local/Temp/claude/F--3D-Druck/d53049d8-8567-40fb-bb95-f784e37acda5/scratchpad/minigolf_wechsel.py"
out="/f/3D Druck/output/review/gesamt-2026-09-27"
old="F:/3D Druck/.claude/worktrees/stand-3018613e6"
new="F:/3D Druck.gesamtfix"
export PYTHONUTF8=1
for round in 1 2; do
  "$py" "$probe" "$old" "$out/minigolf-alt-$round.txt" > "$out/minigolf-alt-$round.log" 2>&1
  echo "ALT-$round-EXIT=$?" >> "$out/minigolf-wechsel.exit"
  "$py" "$probe" "$new" "$out/minigolf-neu-$round.txt" > "$out/minigolf-neu-$round.log" 2>&1
  echo "NEU-$round-EXIT=$?" >> "$out/minigolf-wechsel.exit"
done
echo "ENDE $(date +%H:%M:%S)" >> "$out/minigolf-wechsel.exit"
