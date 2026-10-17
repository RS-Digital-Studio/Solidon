"""Eine Zeilenspezifikation darf ihre Handbuch- und Websitestellen nennen (FD-150, RM-737).

Prüfpunkt 11 misst Versprechen über ``manual.help_for`` und nur an Operationen;
eine Zeile ohne Operation nennt ihre Stellen in der Spezifikation (``manual``,
``website``). Die Werte prüft ``tools/function_promises.py``; hier nur, dass die
Schlüssel keine ungültige Spezifikation machen.
"""

from __future__ import annotations

from tools import function_list, function_scenes


def test_manual_and_website_are_known_keys_of_a_row_spec() -> None:
    rows = function_list.rows()
    row = next(row for row in rows if row.id == "report")
    entry = function_list.SpecEntry(
        "D8",
        "d08.toml",
        {"manual": "pruefbericht#befunde", "website": ["funktionen.html#pruefbericht"]},
    )
    issues = function_list.validate_specs(rows, {row.id: entry}, function_scenes.load_scenes())
    assert not any("unbekannte Schlüssel" in issue for issue in issues), issues
    unknown = function_list.SpecEntry("D8", "d08.toml", {"handbuch": "x"})
    issues = function_list.validate_specs(rows, {row.id: unknown}, function_scenes.load_scenes())
    assert any("unbekannte Schlüssel" in issue for issue in issues), issues
