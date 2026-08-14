"""Die Werkzeugkette prüft sich selbst: läuft sie überhaupt auf dem, was sie soll?

Warum es diese Datei gibt: Das Tor besteht aus vier Läufen (`pytest`, `ruff
check`, `ruff format`, `mypy`), und in derselben Woche ist es zweimal blind
gewesen, ohne dass ein einziger davon rot wurde.

**Der erste Fall** (2026-08-06, siehe ROADMAP): ``python_version`` stand auf
3.11, während ``requires-python`` längst 3.13 verlangte. numpys Stubs benutzen
die ``type``-Anweisung aus PEP 695, mypy brach beim Einlesen ab und meldete
„1 error ... errors prevented further checking" — **keine einzige
Projektdatei** wurde geprüft, und die Meldung sah aus wie ein kleiner Fehler.

**Der zweite Fall** (derselbe Tag): Die Umgebung stand auf Python 3.11,
``requires-python`` auf 3.13. Solange kein 3.12-Feature im Code war, fiel es
nicht auf. Mit den ersten PEP-695-Typparametern brach der Import der Anwendung
— pytest und mypy starben, ``ruff`` blieb grün, weil es einen eigenen Parser
mit ``target-version`` mitbringt und den Interpreter nie ansieht.

Beide Male war der Fehler nicht im Code, sondern unter ihm. Die drei Tests hier
kosten Millisekunden und hätten beide gefangen.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any, Final

from tools.check_env import abweichungen, aufbaubefehl, festgeschrieben, normal

#: Die Wurzel des Arbeitsbaums — von hier aus liegt ``pyproject.toml`` daneben.
_ROOT: Final = Path(__file__).resolve().parent.parent


def _pyproject() -> dict[str, Any]:
    with (_ROOT / "pyproject.toml").open("rb") as handle:
        data: dict[str, Any] = tomllib.load(handle)
    return data


def _required_version() -> tuple[int, int]:
    """Die Untergrenze aus ``requires-python`` als Zahlenpaar.

    Absichtlich nur ``>=`` und nichts weiter: die Angabe ist seit jeher eine
    einzelne Untergrenze, und ein Auswerter für die ganze Grammatik der
    Spezifikation wäre mehr Code als die Sache, die er absichert.
    """
    raw = str(_pyproject()["project"]["requires-python"]).strip()
    assert raw.startswith(">="), f"requires-python ist keine einfache Untergrenze: {raw!r}"
    major, minor = raw.removeprefix(">=").strip().split(".")[:2]
    return int(major), int(minor)


def test_the_interpreter_meets_what_the_project_demands() -> None:
    """Die laufende Umgebung erfüllt ``requires-python``.

    Ohne diesen Test sagt ein Lauf auf der falschen Interpreterversion nichts
    darüber, ob der Code funktioniert — er sagt nur, ob er sich auf *dieser*
    Version übersetzen ließ. Eine zu alte Umgebung fällt hier auf, statt
    irgendwann als ``SyntaxError`` mitten im Import.
    """
    required = _required_version()
    running = sys.version_info[:2]

    assert running >= required, (
        f"Diese Umgebung fährt Python {running[0]}.{running[1]}, "
        f"das Projekt verlangt {required[0]}.{required[1]} oder neuer. "
        "Umgebung neu aufbauen (siehe CLAUDE.md), nicht den Code zurückdrehen."
    )


def test_mypy_checks_against_the_version_that_is_demanded() -> None:
    """``python_version`` ist die Zielversion der Prüfung, nicht der Interpreter.

    Steht sie zu niedrig, liest mypy die Stubs seiner Abhängigkeiten mit einer
    Grammatik, die deren Schreibweise nicht kennt, bricht ab und prüft nichts —
    bei einem Exit-Code, den ein flüchtiger Blick für einen einzelnen Befund
    hält. Genau daran hing das Tor, vermutlich monatelang.
    """
    required = _required_version()
    configured = str(_pyproject()["tool"]["mypy"]["python_version"])

    assert configured == f"{required[0]}.{required[1]}", (
        f"mypy prüft gegen {configured}, das Projekt verlangt {required[0]}.{required[1]}."
    )


def test_ruff_targets_the_version_that_is_demanded() -> None:
    """Dasselbe für ruff — sonst meldet es Schreibweisen als veraltet, die es
    hier noch nicht gibt, oder übersieht solche, die längst gehen."""
    required = _required_version()
    configured = str(_pyproject()["tool"]["ruff"]["target-version"])

    assert configured == f"py{required[0]}{required[1]}", (
        f"ruff zielt auf {configured}, das Projekt verlangt py{required[0]}{required[1]}."
    )


# --- der festgeschriebene Versionssatz -------------------------------------------
#
# `constraints.txt` hält fest, *in welcher* Fassung ein Paket installiert wird.
# Sie half nur nichts, solange niemand nachsah: Wer das `-c` beim Installieren
# vergisst, bekommt andere Fassungen als die, gegen die die Suite grün ist.
# `tools/check_env.py` sieht nach, der Sitzungsstart-Hook ruft es auf. Was hier
# geprüft wird, ist das Werkzeug — nicht die Umgebung dieses Laufs: Der
# wöchentliche Frühwarnlauf der CI installiert **absichtlich** ohne
# `constraints.txt`, und ein Test, der ihn rot färbt, entwertet ihn.


def test_the_pinned_set_is_read_completely() -> None:
    """Jede Zeile `name==fassung` landet im Satz, normalisiert nach PEP 503."""
    satz = festgeschrieben()

    assert len(satz) > 50, f"nur {len(satz)} Einträge — liest `constraints.txt` noch?"
    assert "pyside6" in satz, "PySide6 fehlt im Satz, obwohl die Oberfläche darauf steht"
    # `svg.path` steht mit Punkt in der Datei und muss trotzdem gefunden werden
    assert satz["svg-path"][0] == "svg.path"
    for name, fassung in satz.values():
        assert not fassung.startswith(("<", ">", "=")), f"{name} ist keine feste Fassung: {fassung}"


def test_names_compare_the_way_the_index_compares_them() -> None:
    """`svg.path`, `svg_path` und `SVG-Path` sind dasselbe Paket (PEP 503)."""
    assert normal("svg.path") == normal("svg_path") == normal("SVG-Path") == "svg-path"


def test_a_deviating_version_is_found() -> None:
    """Der Fall vom 06.08.2026: der Klon zog eine andere Fassung, die Suite fiel um."""
    satz = {"numpy": ("numpy", "2.4.0"), "trimesh": ("trimesh", "4.12.2")}

    assert abweichungen(satz, {"numpy": "2.5.0", "trimesh": "4.12.2"}) == [
        "numpy 2.5.0 statt 2.4.0"
    ]
    assert abweichungen(satz, {"numpy": "2.4.0", "trimesh": "4.12.2"}) == []


def test_a_package_that_is_absent_is_not_a_deviation() -> None:
    """Constraints, nicht Requirements: der Windows-Eintrag fehlt auf Linux zu Recht."""
    satz = {"pywin32-ctypes": ("pywin32-ctypes", "0.2.3")}

    assert abweichungen(satz, {}) == []


def test_the_rebuild_command_pins_the_versions() -> None:
    """Ohne das `-c` ist der Vorschlag genau der Fehler, den er beheben soll."""
    for mit_venv in (True, False):
        befehl = aufbaubefehl(mit_venv=mit_venv)
        assert "-c constraints.txt" in befehl, befehl
        assert "-e" in befehl, befehl
    assert "venv" in aufbaubefehl(mit_venv=False), "ohne Umgebung muss sie zuerst angelegt werden"
