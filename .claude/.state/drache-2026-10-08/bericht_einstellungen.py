"""Bericht: was jeder Slicer für den Drachen wirklich druckt (Variante „vorschlaege“).

Aufruf: python bericht_einstellungen.py <matrix-ordner> <einstellungen.json> <bericht.md>

Liest die Matrixergebnisse (Profilkette, Abweichungen vom Hersteller, Vorschläge)
und die gemessenen Werte aus ``einstellungen.py`` und schreibt eine Tabelle.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

matrix = json.loads(next(Path(sys.argv[1]).glob("*.json")).read_text(encoding="utf-8"))
measured = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
out = Path(sys.argv[3])


def speeds(values: dict) -> str:
    parts = []
    for name in ("Außenwand", "Innenwand", "Füllung", "Vollfläche", "Stütze", "Brücke"):
        if values.get(name):
            parts.append(f"{name} {values[name][0]:g}")
    return ", ".join(parts)


#: Je Familie die Schlüssel für Art, Abstand oben, Abstand unten, Kontaktlagen, XY.
SUPPORT_KEYS = (
    ("support_type", "support_style", "support_material_style", "support_structure"),
    ("support_top_z_distance", "support_material_contact_distance", "support_top_distance"),
    (
        "support_bottom_z_distance",
        "support_material_bottom_contact_distance",
        "support_bottom_distance",
    ),
    ("support_interface_top_layers", "support_material_interface_layers", "support_roof_height"),
    ("support_object_xy_distance", "support_material_xy_spacing", "support_xy_distance"),
)


def support_text(config: dict) -> str:
    parts = []
    for names in SUPPORT_KEYS:
        found = [config[name] for name in names if config.get(name) not in (None, "")]
        parts.append("/".join(found) if found else "–")
    return " · ".join(parts)


rows = [
    "| Slicer · Drucker | Profil des Herstellers | Düse °C | Bett °C | Lüfter Schicht 1–4 / später % "
    "| Tempo mm/s (Median) | Beschl. mm/s² | Rückzug mm @ mm/s | Abweichung vom Hersteller "
    "| Solidons Vorschläge | Stützart · Abstand oben/unten · Kontaktlagen · XY | Zeit | Stütze m |",
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
]
for combo in matrix["combos"]:
    key = f"{combo['slicer']}"
    run = (combo.get("variants") or {}).get("vorschlaege", [{}])[0]
    seen = measured.get(key, {}).get("measured", {})
    chain = run.get("chain") or {}
    differences = chain.get("differences") or {}
    console = chain.get("console") or {}
    deviation = ", ".join(f"{name} {old}→{new}" for name, (_where, old, new) in differences.items())
    if console:
        deviation += " (Konsole: " + ", ".join(console) + ")"
    if not chain:
        deviation = "keine Herstellerkette — Solidons Satz"
    profile = " / ".join(str(combo.get(name) or "–") for name in ("machine", "process", "filament"))
    advice = ", ".join(f"{path}={value}" for path, value, *_rest in combo.get("advice", []))
    retract = seen.get("retraction_mm_mm_s") or []
    retraction = f"{retract[0][0][0]:g} @ {retract[0][0][1]:g}" if retract else "–"
    fans = seen.get("fan_layers_1_4") or []
    later = seen.get("fan_later_min_max")
    fan_text = "/".join("–" if value is None else f"{value:g}" for value in fans)
    if later:
        fan_text += f" · {later[0]:g}–{later[1]:g}"
    nozzle = seen.get("nozzle_first") or []
    nozzle_later = seen.get("nozzle_later") or []
    nozzle_text = "/".join(f"{value:g}" for value in nozzle)
    if nozzle_later:
        nozzle_text += " → " + "/".join(f"{value:g}" for value in nozzle_later)
    accel = ", ".join(f"{value:g}" for value in (seen.get("accelerations") or [])[:3])
    rows.append(
        f"| {combo['slicer']} · {combo['printer']} | {profile} | {nozzle_text} | "
        f"{'/'.join(f'{v:g}' for v in (seen.get('bed') or []))} | {fan_text} | "
        f"{speeds(seen.get('speed_mm_s_median_p90') or {})} | {accel} | {retraction} | "
        f"{deviation or 'keine'} | {advice} | {support_text(measured.get(key, {}).get('config', {}))} | {run.get('print_minutes', 0) / 60:.1f} h | "
        f"{run.get('support_m', 0):.0f} |"
    )
out.write_text("\n".join(rows) + "\n", encoding="utf-8")
print("\n".join(rows))
