"""Fasst die Ergebnisse der Gesamtprüfung zu einem Bericht zusammen.

Aufruf: python tools/matrix_report.py <ergebnisordner> [<ergebnisordner> …] > bericht.md

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

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SLICER_ORDER = ["elegoo", "bambu", "creality", "orca", "prusa", "superslicer", "cura"]
#: Befunde, die nicht Solidon gelten.
FOREIGN = ("wie Hersteller", "nur im Fenster")


def _advice_flag(entry: dict[str, Any]) -> str | None:
    """Macht einen Fehler der Vorschlagsberechnung im Bericht sichtbar."""
    advice_error = entry.get("advice_error")
    if isinstance(advice_error, str) and advice_error.strip():
        return f"Vorschläge nicht geprüft: {advice_error.strip()[:120]}"
    return None


def state_of(entry: dict[str, Any]) -> tuple[str, list[str]]:
    skip = str(entry.get("skip") or "")
    if skip.startswith("nicht geprüft"):
        # Kein Körper nach dem Laden (Rückfrage, Ladefehler) ist kein geprüftes
        # Modell (RM-312, ``image_00001_.glb``) und keine fehlende Profilzuordnung.
        return "nicht geprüft", [skip]
    if skip:
        return "kein Profil", []
    advice_flag = _advice_flag(entry)
    if entry.get("error"):
        flags = [entry["error"][:120]]
        if advice_flag:
            flags.append(advice_flag)
        return "kein Druck", flags
    runs = entry.get("variants", {}).get("standard", [])
    if not runs:
        flags = ["keine Läufe"]
        if advice_flag:
            flags.append(advice_flag)
        return "kein Druck", flags
    details = " ".join(str(r.get("detail", "")) for r in runs)
    if any(not r.get("ok") for r in runs):
        if (
            any(r.get("constraint") == "slicer_build_volume" for r in runs)
            or "größer als der Bauraum" in details
            or "außerhalb seines Bauraums" in details
            or "größer als die Druckfläche" in details
            or "höher, als dieser Drucker" in details
        ):
            return "passt nicht", [advice_flag] if advice_flag else []
        if "nur in seinem Fenster" in details:
            flags = [f for r in runs for f in r.get("flags", []) if not f.startswith(FOREIGN)]
            if advice_flag:
                flags.append(advice_flag)
            return "nur Fenster", flags
        flags = [str(r.get("title") or r.get("error"))[:80] for r in runs if not r.get("ok")]
        if advice_flag:
            flags.append(advice_flag)
        return "kein Druck", flags
    flags = sorted(
        {
            f"{variant}: {flag}" if variant != "standard" else flag
            for variant, variant_runs in entry.get("variants", {}).items()
            for r in variant_runs
            for flag in r.get("flags", [])
            if not flag.startswith(FOREIGN)
        }
    )
    if advice_flag:
        flags.append(advice_flag)
        flags.sort()
    return ("Befund" if flags else "ok"), flags


def result_files(folder: Path, *, matrix_run: bool) -> list[Path]:
    """Liest nur das Ergebnisformat, das durch die Laufkennung gebunden ist."""
    return sorted(folder.glob("*/*.json") if matrix_run else folder.glob("*.json"))


def _has_terminal_state(entry: dict[str, Any]) -> bool:
    return any(
        isinstance(entry.get(key), str) and bool(entry[key].strip()) for key in ("skip", "error")
    ) or (
        isinstance(entry.get("variants"), dict)
        and isinstance(entry["variants"].get("standard"), list)
    )


def identity_hash(identity: dict[str, Any]) -> str:
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def expected_models(identity: dict[str, Any]) -> set[tuple[str, str]] | None:
    """Liefert die eindeutigen Modell-/Spezifikationspaare des Laufmanifests."""
    models = identity.get("models")
    if not isinstance(models, list) or not models:
        return None
    expected: set[tuple[str, str]] = set()
    for entry in models:
        if not isinstance(entry, dict):
            return None
        path, spec, digest = entry.get("path"), entry.get("spec"), entry.get("sha256")
        if not all(isinstance(value, str) and value for value in (path, spec, digest)):
            return None
        pair = (path, spec)
        if pair in expected:
            return None
        expected.add(pair)
    return expected


def completed_matrix_run(folder: Path, identity: dict[str, Any]) -> bool:
    """Nur einen vom Treiber erfolgreich abgeschlossenen Lauf auswerten."""
    try:
        status = json.loads((folder / ".matrix-status").read_text(encoding="utf-8"))
    except OSError, ValueError:
        return False
    return (
        isinstance(status, dict)
        and status.get("run_sha256") == identity_hash(identity)
        and status.get("status") == "complete"
    )


def belongs_to_run(data: object, identity: dict[str, Any]) -> bool:
    """Lehnt Resultate ohne passende Lauf- und Kombinationskennung ab."""
    if not isinstance(data, dict):
        return False
    marker = data.get("_matrix_run")
    if not isinstance(marker, dict):
        return False
    if (
        marker.get("run_sha256") != identity_hash(identity)
        or marker.get("code_sha256") != identity.get("code_sha256")
        or marker.get("plan") != identity.get("plan")
        or marker.get("model") != data.get("model")
        or marker.get("spec") != data.get("spec")
        or data.get("code") != identity.get("code_root")
    ):
        return False
    expected_models_set = expected_models(identity)
    if expected_models_set is None:
        return False
    matching_models = [
        entry
        for entry in identity["models"]
        if isinstance(entry, dict)
        and entry.get("path") == marker.get("model")
        and entry.get("spec") == marker.get("spec")
    ]
    if (
        len(matching_models) != 1
        or not isinstance(marker.get("model_sha256"), str)
        or matching_models[0].get("sha256") != marker.get("model_sha256")
    ):
        return False
    expected_by_spec = identity.get("expected_combos")
    if not isinstance(expected_by_spec, dict):
        return False
    expected_rows = expected_by_spec.get(marker.get("spec"))
    if not isinstance(expected_rows, list):
        return False
    expected: set[tuple[str, str]] = set()
    for pair in expected_rows:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(value, str) for value in pair)
        ):
            return False
        expected.add((pair[0], pair[1]))
    if len(expected) != len(expected_rows):
        return False
    rows = data.get("combos")
    if not isinstance(rows, list):
        return False
    found: set[tuple[str, str]] = set()
    all_complete = True
    for row in rows:
        if not isinstance(row, dict):
            return False
        pair = (row.get("slicer"), row.get("printer"))
        if (
            not all(isinstance(value, str) for value in pair)
            or pair not in expected
            or pair in found
            or not isinstance(row.get("complete"), bool)
        ):
            return False
        if row["complete"]:
            if not _has_terminal_state(row):
                return False
        else:
            all_complete = False
        found.add(pair)
    return (
        data.get("done") is True
        and not data.get("load_error")
        and all_complete
        and found == expected
    )


def main() -> int:
    results: list[dict[str, Any]] = []
    ignored = 0
    incomplete_runs = 0
    for folder in sys.argv[1:]:
        root = Path(folder)
        identity_path = root / ".matrix-identity"
        matrix_run = identity_path.exists()
        identity: dict[str, Any] | None = None
        if matrix_run:
            try:
                candidate = json.loads(identity_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise SystemExit(f"Laufkennung in {identity_path} ist unlesbar") from error
            if not isinstance(candidate, dict):
                raise SystemExit(f"Laufkennung in {identity_path} hat kein Objektformat")
            identity = candidate
            ignored += sum(1 for _path in root.glob("*.json"))
            files = result_files(root, matrix_run=True)
            manifest = expected_models(identity)
            if not completed_matrix_run(root, identity) or manifest is None:
                incomplete_runs += 1
                ignored += len(files)
                continue
            accepted: dict[tuple[str, str], dict[str, Any]] = {}
            invalid_run = False
            for path in files:
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except OSError, ValueError:
                    ignored += 1
                    continue
                if not belongs_to_run(data, identity):
                    ignored += 1
                    continue
                pair = (data["model"], data["spec"])
                if pair in accepted:
                    ignored += 1
                    invalid_run = True
                    continue
                accepted[pair] = data
            if invalid_run or accepted.keys() != manifest:
                incomplete_runs += 1
                continue
            results.extend(accepted[pair] for pair in sorted(manifest))
            continue
        else:
            files = result_files(root, matrix_run=False)
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except OSError, ValueError:
                ignored += 1
                continue
            if isinstance(data, dict):
                results.append(data)
            else:
                ignored += 1
    lines: list[str] = ["# Gesamtprüfung der Übergabe", ""]
    done = sum(1 for r in results if r.get("done"))
    lines.append(f"{len(results)} Modelle gelesen, {done} vollständig.")
    if incomplete_runs:
        lines.append(
            f"{incomplete_runs} Matrixläufe nicht abgeschlossen; ihre Ergebnisse wurden ausgelassen."
        )
    if ignored:
        lines.append(
            f"{ignored} Ergebnisdateien mit fehlerhafter oder fremder Laufkennung ausgelassen."
        )
    lines.append("")

    # --- Übersicht je Slicer und Drucker ---------------------------------------
    grid: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for result in results:
        for entry in result.get("combos", []):
            if not entry.get("complete"):
                continue
            state, _flags = state_of(entry)
            grid[(entry["slicer"], entry["printer"])][state] += 1
    lines += [
        "## Je Slicer und Drucker",
        "",
        "| Slicer | Drucker | ok | Befund | passt nicht | nur Fenster | kein Druck | kein Profil | nicht geprüft |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for (slicer, printer), counts in sorted(
        grid.items(),
        key=lambda item: (
            SLICER_ORDER.index(item[0][0]) if item[0][0] in SLICER_ORDER else 9,
            item[0][1],
        ),
    ):
        lines.append(
            f"| {slicer} | {printer} | {counts['ok']} | {counts['Befund']} | {counts['passt nicht']} | {counts['nur Fenster']} | {counts['kein Druck']} | {counts['kein Profil']} | {counts['nicht geprüft']} |"
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
                kind = (
                    flag.split("(")[0]
                    .split(":")[0 if not flag.startswith(("vorschlaege", "stuetzen_auto")) else 1]
                    .strip()
                )
                kinds[kind].append(f"{model} · {entry['slicer']} · {entry['printer']} · {flag}")
            if state == "kein Druck":
                kinds["kein Druck"].append(
                    f"{model} · {entry['slicer']} · {entry['printer']} · {'; '.join(flags)}"
                )
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
                for key, (_kind, wanted, found) in (chain.get("differences") or {}).items():
                    keys[key].add(f"{entry['slicer']}/{entry['printer']}: {wanted} → {found}")
                for key in chain.get("console") or {}:
                    console[key].add(f"{entry['slicer']}/{entry['printer']}")
    lines += [
        "## Standardlauf gegen die Herstellerkette",
        "",
        "Schlüssel, die Solidons Konsolenlauf ohne Vorschläge anders druckt, als die aufgelöste Kette des Herstellers sagt.",
        "",
    ]
    if not keys:
        lines.append("Keine Abweichung.")
    for key, where in sorted(keys.items(), key=lambda item: -len(item[1])):
        lines.append(
            f"- `{key}` ({len(where)}): "
            + "; ".join(sorted(where)[:6])
            + (" …" if len(where) > 6 else "")
        )
    lines += [
        "",
        "Von der Konsole selbst gesetzt (nicht Solidon): "
        + ", ".join(f"`{k}` ({len(v)})" for k, v in sorted(console.items())),
        "",
    ]

    # --- Vorschläge ---------------------------------------------------------------------------
    advice: Counter[str] = Counter()
    hidden: Counter[str] = Counter()
    for result in results:
        for entry in result.get("combos", []):
            # Seit 04.10.2026 trägt ein Vorschlag auch die Teile, denen er gilt.
            for path, value, *_rest in entry.get("advice", []):
                advice[f"{path} = {value}"] += 1
            for path, _value, *_rest in entry.get("advice_hidden", []):
                hidden[path] += 1
    lines += ["## Vorschläge", "", "| Vorschlag | Anzahl |", "|---|---|"]
    lines += [f"| `{key}` | {count} |" for key, count in advice.most_common(40)]
    lines += [
        "",
        "Nicht angeboten, weil der Slicer ihn nicht nimmt oder selbst deckelt: "
        + ", ".join(f"`{k}` ({v})" for k, v in hidden.most_common()),
        "",
    ]

    # --- Schmale Stege ------------------------------------------------------------------------
    lines += [
        "## Schmale Stege in der ersten Schicht",
        "",
        "| Modell | Anteil < 3 mm | Tempo Schicht 1 (Median je Slicer) |",
        "|---|---|---|",
    ]
    rows = []
    for result in results:
        narrow = (result.get("narrow") or {}).get("narrow_share", {}).get("r1.5")
        if narrow is None:
            continue
        speeds = []
        for entry in result.get("combos", []):
            for run in entry.get("variants", {}).get("standard", []):
                fast = [
                    v["median"]
                    for k, v in (run.get("first_layer_speeds") or {}).items()
                    if k not in ("rim", "support", "other")
                ]
                if fast:
                    speeds.append(f"{entry['slicer']}/{entry['printer']} {max(fast):.0f}")
        rows.append((narrow, Path(result.get("model", "?")).name, speeds))
    for narrow, model, speeds in sorted(rows, key=lambda row: -row[0])[:60]:
        lines.append(f"| {model} | {narrow:.0%} | {', '.join(speeds[:6])} |")
    lines.append("")

    # --- Stützbedarf gegen das Urteil des Slicers ------------------------------------------
    # ``stuetzen_auto`` schaltet nur die Stützen an; Art, Schwelle und
    # Brückenregel bleiben die des Herstellerprofils. Stützt der Slicer dann
    # nichts Nennenswertes, widerspricht er Solidons „Stützen nötig“ — der Weg
    # aus ``support_ways`` sagt, welche Regel es verlangte (Paket 3).
    lines += [
        "## Stützbedarf gegen das Urteil des Slicers",
        "",
        "| Modell | Slicer/Drucker | Stütze m | Solidons Weg |",
        "|---|---|---|---|",
    ]
    agreeing = disagreeing = 0
    for result in results:
        for entry in result.get("combos", []):
            for run in entry.get("variants", {}).get("stuetzen_auto", []):
                if not run.get("ok"):
                    continue
                if not any(f.startswith("Slicer stützt nicht") for f in run.get("flags", [])):
                    agreeing += 1
                    continue
                disagreeing += 1
                ways = [
                    f"{body}: Inseln {w['island_layers']}, Stück {w['patch']}, Summe {w['overhang']}, Brücke {w['bridge_max']}"
                    for body, w in (entry.get("support_ways") or {}).items()
                    if w.get("needed")
                ]
                lines.append(
                    f"| {Path(result.get('model', '?')).name} | {entry['slicer']}/{entry['printer']} "
                    f"| {run.get('support_m') or 0.0:.2f} | {'; '.join(ways)[:200]} |"
                )
    lines += [
        "",
        f"Der Slicer stützt, wo Solidon Stützen verlangt: {agreeing}; er stützt nicht: {disagreeing}.",
        "",
    ]
    # Übernommene Vorschläge, die Stützen einschalten und trotzdem keine
    # bringen: ein zweiter Vorschlag hebt den ersten auf (Wedge-Lock, 04.10.2026).
    cancelled = [
        f"{Path(result.get('model', '?')).name} · {entry['slicer']}/{entry['printer']}"
        for result in results
        for entry in result.get("combos", [])
        for run in entry.get("variants", {}).get("vorschlaege", [])
        if any(f.startswith("Stützvorschlag ohne Stütze") for f in run.get("flags", []))
    ]
    lines += [
        f"Übernommene Stützvorschläge ohne Stütze im G-Code: {len(cancelled)}"
        + (f" ({', '.join(cancelled[:20])})" if cancelled else ""),
        "",
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
