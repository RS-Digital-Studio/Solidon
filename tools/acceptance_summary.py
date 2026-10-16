"""Der Bericht eines Laufs von ``file_acceptance.py`` als Tabelle (``summary.md``).

Aus ``file_acceptance`` gelöst, damit der Prüfstand unter der Größengrenze der
Codestruktur bleibt (Regel 6, 2 000 Zeilen): Die Tabelle ist eine Sache für sich,
``file_acceptance.summary`` sammelt die Werte und ruft :func:`markdown`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def markdown(data: Mapping[str, Any]) -> str:
    """Der Bericht als Tabelle, ein Fall je Zeile."""
    lines = [
        "# Native Einzeldateiabnahme",
        "",
        f"Fälle: {data['cases']} · gelaufen: {data['ran']} · bestanden: {data['passed']}"
        f" · Bohrungen: {data['bores_passed']} von {data['bores']}",
        "",
        "| Nr. | Datei | Stufe | Exit | Sekunden | Körper | Merkmale | Gruppen | Merkmal"
        " | Geändert | Undo | Redo | Vorschau | Bestanden |",
        "|---:|---|---|---:|---:|---:|---:|---:|---|---|---|---|---|---|",
    ]

    def mark(value: object) -> str:
        return "ja" if value is True else "nein" if value is False else "-"

    for row in data["rows"]:
        checks = row.get("checks", {})
        seconds = row.get("seconds")
        cells = [
            row["number"],
            str(row["relative"]).replace("|", "/"),
            row["stage"],
            "-" if row["exit_code"] is None else row["exit_code"],
            "-" if seconds is None else f"{float(seconds):.1f}",
            row["objects"],
            row["features"],
            row["groups"],
            row["feature"] or "-",
            mark(checks.get("changed")),
            mark(checks.get("undo_restores_import")),
            mark(checks.get("redo_restores_applied")),
            mark(checks.get("preview_shows_result")),
            mark(row["passed"]),
        ]
        lines.append("| " + " | ".join(str(cell) for cell in cells) + " |")
    bores = [(row, bore) for row in data["rows"] for bore in row["bores"]]
    if bores:
        lines += ["", "## Jede Bohrung", "", "| Nr. | Bohrung | Bestanden |", "|---:|---|---|"]
        lines += [
            f"| {row['number']} | {bore['feature']} | {mark(bore['passed'])} |"
            for row, bore in bores
        ]
    functions = data.get("functions") or []
    if functions:
        lines += [
            "",
            "## Funktions- und Sprachfälle",
            "",
            f"Fälle: {data['function_cases']} · gelaufen: {data['function_ran']}"
            f" · durchgekommen: {data['function_complete']}",
            "",
            "| Nr. | Zeile | Art | Variante | Stufe | Exit | Sekunden | Funde | Ungemessen |",
            "|---:|---|---|---|---|---:|---:|---:|---:|",
        ]
        for row in functions:
            seconds = row.get("seconds")
            cells = [
                row["number"],
                str(row["relative"]).replace("|", "/"),
                row["kind"],
                row["variant"] or "-",
                row["stage"],
                "-" if row["exit_code"] is None else row["exit_code"],
                "-" if seconds is None else f"{float(seconds):.1f}",
                row["findings"],
                row["unmeasured"],
            ]
            lines.append("| " + " | ".join(str(cell) for cell in cells) + " |")
    failures = [row for row in [*data["rows"], *functions] if row["errors"]]
    if failures:
        lines += ["", "## Fehler", ""]
        for row in failures:
            first = str(row["errors"][0]).strip().splitlines()
            lines.append(f"- {row['number']} {row['relative']}: {first[-1] if first else ''}")
    return "\n".join(lines) + "\n"
