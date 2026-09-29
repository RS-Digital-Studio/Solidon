"""Fasst die Ergebnisse der Gesamtprüfung zu einem Bericht zusammen.

Aufruf: python bericht.py <ergebnisordner> [<ergebnisordner> …] > bericht.md

Jede Kombination aus Modell, Slicer und Drucker bekommt einen Zustand:

``ok``            Druckdatei entstanden, nichts Bedeutsames aufgefallen
``Befund``        Druckdatei entstanden, aber etwas fällt auf (Liste)
``passt nicht``   ein Teil ist größer als der Bauraum — die Übergabe sagt es
``nur Fenster``   Creality Print rechnet über die Konsole keine 3MF (RM-164)
``kein Druck``    die Übergabe scheiterte aus einem anderen Grund
``kein Profil``   der Slicer führt diesen Drucker nicht
"""
# ruff: noqa: E501

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SLICER_ORDER = ["elegoo", "bambu", "creality", "orca", "prusa", "cura"]
#: Befunde, die nicht Solidon gelten.
FOREIGN = ("wie Hersteller", "nur im Fenster")


def state_of(entry: dict[str, Any]) -> tuple[str, list[str]]:
    if entry.get("skip"):
        return "kein Profil", []
    if entry.get("error"):
        return "kein Druck", [entry["error"][:120]]
    runs = entry.get("variants", {}).get("standard", [])
    if not runs:
        return "kein Druck", ["keine Läufe"]
    details = " ".join(str(r.get("detail", "")) for r in runs)
    if any(not r.get("ok") for r in runs):
        if "größer als der Bauraum" in details or "außerhalb seines Bauraums" in details:
            return "passt nicht", []
        if "nur in seinem Fenster" in details:
            flags = [f for r in runs for f in r.get("flags", []) if not f.startswith(FOREIGN)]
            return "nur Fenster", flags
        return "kein Druck", [str(r.get("title") or r.get("error"))[:80] for r in runs if not r.get("ok")]
    flags = sorted(
        {
            f"{variant}: {flag}" if variant != "standard" else flag
            for variant, variant_runs in entry.get("variants", {}).items()
            for r in variant_runs
            for flag in r.get("flags", [])
            if not flag.startswith(FOREIGN)
        }
    )
    return ("Befund" if flags else "ok"), flags


def main() -> int:
    results: list[dict[str, Any]] = []
    for folder in sys.argv[1:]:
        for path in sorted(Path(folder).glob("*.json")):
            try:
                results.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
    lines: list[str] = ["# Gesamtprüfung der Übergabe", ""]
    done = sum(1 for r in results if r.get("done"))
    lines.append(f"{len(results)} Modelle gelesen, {done} vollständig.")
    lines.append("")

    # --- Übersicht je Slicer und Drucker ---------------------------------------
    grid: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for result in results:
        for entry in result.get("combos", []):
            if not entry.get("complete"):
                continue
            state, _flags = state_of(entry)
            grid[(entry["slicer"], entry["printer"])][state] += 1
    lines += ["## Je Slicer und Drucker", "", "| Slicer | Drucker | ok | Befund | passt nicht | nur Fenster | kein Druck | kein Profil |", "|---|---|---|---|---|---|---|---|"]
    for (slicer, printer), counts in sorted(grid.items(), key=lambda item: (SLICER_ORDER.index(item[0][0]) if item[0][0] in SLICER_ORDER else 9, item[0][1])):
        lines.append(
            f"| {slicer} | {printer} | {counts['ok']} | {counts['Befund']} | {counts['passt nicht']} | {counts['nur Fenster']} | {counts['kein Druck']} | {counts['kein Profil']} |"
        )
    lines.append("")

    # --- Befunde nach Art ----------------------------------------------------------
    kinds: dict[str, list[str]] = defaultdict(list)
    for result in results:
        model = Path(result.get("model", "?")).name
        for entry in result.get("combos", []):
            if not entry.get("complete"):
                continue
            state, flags = state_of(entry)
            for flag in flags:
                kind = flag.split("(")[0].split(":")[0 if not flag.startswith(("vorschlaege", "stuetzen_auto")) else 1].strip()
                kinds[kind].append(f"{model} · {entry['slicer']} · {entry['printer']} · {flag}")
            if state == "kein Druck":
                kinds["kein Druck"].append(f"{model} · {entry['slicer']} · {entry['printer']} · {'; '.join(flags)}")
    lines += ["## Befunde nach Art", ""]
    for kind, items in sorted(kinds.items(), key=lambda item: -len(item[1])):
        lines.append(f"### {kind} ({len(items)})")
        lines.append("")
        lines += [f"- {item}" for item in items[:40]]
        if len(items) > 40:
            lines.append(f"- … und {len(items) - 40} weitere")
        lines.append("")

    # --- Abweichungen von der Herstellerkette ---------------------------------------------
    keys: dict[str, set[str]] = defaultdict(set)
    console: dict[str, set[str]] = defaultdict(set)
    for result in results:
        for entry in result.get("combos", []):
            for run in entry.get("variants", {}).get("standard", []):
                chain = run.get("chain") or run.get("chain_project") or {}
                for key, (kind, wanted, found) in (chain.get("differences") or {}).items():
                    keys[key].add(f"{entry['slicer']}/{entry['printer']}: {wanted} → {found}")
                for key in chain.get("console") or {}:
                    console[key].add(f"{entry['slicer']}/{entry['printer']}")
    lines += ["## Standardlauf gegen die Herstellerkette", "", "Schlüssel, die Solidons Konsolenlauf ohne Vorschläge anders druckt, als die aufgelöste Kette des Herstellers sagt.", ""]
    if not keys:
        lines.append("Keine Abweichung.")
    for key, where in sorted(keys.items(), key=lambda item: -len(item[1])):
        lines.append(f"- `{key}` ({len(where)}): " + "; ".join(sorted(where)[:6]) + (" …" if len(where) > 6 else ""))
    lines += ["", "Von der Konsole selbst gesetzt (nicht Solidon): " + ", ".join(f"`{k}` ({len(v)})" for k, v in sorted(console.items())), ""]

    # --- Vorschläge ---------------------------------------------------------------------------
    advice: Counter[str] = Counter()
    hidden: Counter[str] = Counter()
    for result in results:
        for entry in result.get("combos", []):
            for path, value, _reason in entry.get("advice", []):
                advice[f"{path} = {value}"] += 1
            for path, value, _reason in entry.get("advice_hidden", []):
                hidden[path] += 1
    lines += ["## Vorschläge", "", "| Vorschlag | Anzahl |", "|---|---|"]
    lines += [f"| `{key}` | {count} |" for key, count in advice.most_common(40)]
    lines += ["", "Nicht angeboten, weil der Slicer ihn nicht nimmt oder selbst deckelt: " + ", ".join(f"`{k}` ({v})" for k, v in hidden.most_common()), ""]

    # --- Schmale Stege ------------------------------------------------------------------------
    lines += ["## Schmale Stege in der ersten Schicht", "", "| Modell | Anteil < 3 mm | Tempo Schicht 1 (Median je Slicer) |", "|---|---|---|"]
    rows = []
    for result in results:
        narrow = (result.get("narrow") or {}).get("narrow_share", {}).get("r1.5")
        if narrow is None:
            continue
        speeds = []
        for entry in result.get("combos", []):
            for run in entry.get("variants", {}).get("standard", []):
                fast = [v["median"] for k, v in (run.get("first_layer_speeds") or {}).items() if k not in ("rim", "support", "other")]
                if fast:
                    speeds.append(f"{entry['slicer']}/{entry['printer']} {max(fast):.0f}")
        rows.append((narrow, Path(result.get("model", "?")).name, speeds))
    for narrow, model, speeds in sorted(rows, key=lambda row: -row[0])[:60]:
        lines.append(f"| {model} | {narrow:.0%} | {', '.join(speeds[:6])} |")
    lines.append("")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
