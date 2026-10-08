"""Kurzausgabe einer gcode_stuetzen.json mit Lauf, Slicer und Variante je Zeile."""

import json
import sys
from pathlib import Path

for path in sys.argv[1:]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for name, row in data.items():
        parts = Path(name.replace("\\", "/")).parts
        run = parts[0]
        print(
            f"{run:18s} {parts[-4]:28s} {parts[-3]:14s} Anteil {row['supported_share']:.3f}  "
            f"ohne Kanal {row.get('open_share', float('nan')):.3f}  "
            f"ohne Rand {row.get('needed_share', float('nan')):.3f}  "
            f"Stütze {row['support_m']:7.1f} m  Inseln {row['islands_supported']}"
        )
