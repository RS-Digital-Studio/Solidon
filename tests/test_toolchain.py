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

import pytest

import tools.check_env as check_env
from tools.check_env import (
    mismatches,
    normal,
    pinned,
    setup_command,
    upper_bounds,
    version_tuple,
)

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


def test_the_version_is_the_same_in_both_places_that_carry_it() -> None:
    """Die Fassung steht in ``branding.py`` und in ``pyproject.toml``.

    Sie ist dieselbe Zahl mit zwei Lesern: der Über-Dialog, jede Projektdatei
    (``app_version``), das 3MF, der Fehlerbericht und der Update-Vergleich lesen
    ``APP_VERSION``; die Paketmetadaten und alles, was ``pip`` daraus macht,
    lesen ``pyproject.toml``. Laufen sie auseinander, nennt ein Paket eine
    andere Fassung als das Fenster darin — und niemand merkt es, denn keines von
    beiden ist kaputt.

    Der Anlass steht in der ROADMAP unter der Demo: die Zahl wurde am 14.08.2026
    von 0.7.0 auf 0.1.0 gesetzt, und bis dahin hielt die beiden Orte nichts
    zusammen außer Aufmerksamkeit. Die Zählregel — letzte Stelle plus eins je
    ausgeliefertem Bau — dreht also immer an zwei Stellen.
    """
    from app.branding import APP_VERSION

    packaged = str(_pyproject()["project"]["version"])

    assert packaged == APP_VERSION, (
        f"pyproject.toml nennt {packaged}, app/branding.py nennt {APP_VERSION}. "
        "Beide tragen dieselbe Fassung — eine von ihnen wurde vergessen."
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
    satz = pinned()

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

    assert mismatches(satz, {"numpy": "2.5.0", "trimesh": "4.12.2"}) == ["numpy 2.5.0 statt 2.4.0"]
    assert mismatches(satz, {"numpy": "2.4.0", "trimesh": "4.12.2"}) == []


def test_a_package_that_is_absent_is_not_a_deviation() -> None:
    """Constraints, nicht Requirements: der Windows-Eintrag fehlt auf Linux zu Recht."""
    satz = {"pywin32-ctypes": ("pywin32-ctypes", "0.2.3")}

    assert mismatches(satz, {}) == []


def test_the_rebuild_command_pins_the_versions() -> None:
    """Ohne das `-c` ist der Vorschlag genau der Fehler, den er beheben soll."""
    for with_venv in (True, False):
        befehl = setup_command(with_venv=with_venv)
        assert "-c constraints.txt" in befehl, befehl
        assert "-e" in befehl, befehl
    assert "venv" in setup_command(with_venv=False), "ohne Umgebung muss sie zuerst angelegt werden"


# --- aktuell bleiben, ohne die Grenzen zu reißen ---------------------------------
#
# Festgenagelt ist nicht dasselbe wie gepflegt. Der wöchentliche CI-Lauf meldet
# eine Fassung, die *bricht*; dass es überhaupt eine neuere *gäbe*, sagt er
# niemandem. `--outdated` beantwortet das — und muss dabei die Grenzen kennen,
# die absichtlich gesetzt sind.


def test_a_deliberate_upper_bound_is_read_from_the_project(tmp_path, monkeypatch) -> None:
    """Eine Obergrenze ist eine Entscheidung, und `--outdated` muss sie kennen.

    Sonst schlägt es jede Woche einen Sprung vor, der absichtlich nicht kommt
    — und wird nach zwei Wochen ignoriert. Geprüft wird an einer erfundenen
    Datei: Das Projekt selbst hat seit dem trimesh-5-Sprung am 14.08.2026
    **keine** Obergrenze mehr, und ein Test, der eine braucht, hinge davon ab,
    dass wieder eine entsteht.
    """
    datei = tmp_path / "pyproject.toml"
    datei.write_text(
        '[project]\ndependencies = [\n  "numpy>=1.26",\n  "trimesh>=4.4,<5",\n]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(check_env, "PYPROJECT", datei)

    grenzen = upper_bounds()

    assert grenzen.get("trimesh") == "5"
    assert "numpy" not in grenzen, "eine offene Untergrenze ist keine Grenze"


def test_the_project_currently_pins_nothing_from_above() -> None:
    """Der Ist-Stand, damit sein Ende auffällt.

    Fällt dieser Test, hat jemand eine Obergrenze gesetzt — dann gehört der
    Grund in `pyproject.toml` daneben, so wie es bei `trimesh<5` stand.
    """
    assert upper_bounds() == {}, (
        f"neue Obergrenze(n): {sorted(upper_bounds())} — steht der Grund daneben?"
    )


def test_versions_compare_as_numbers_not_as_text() -> None:
    """Sonst gilt „10.0" als kleiner als „9.0", und die Grenze greift verkehrt."""
    assert version_tuple("5.0.0") > version_tuple("4.12.2")
    assert version_tuple("10.0") > version_tuple("9.0")
    assert version_tuple("2.9.0.post0") == (2, 9, 0)
    assert version_tuple("") == ()


def test_freezing_keeps_the_head_that_explains_the_file(tmp_path, monkeypatch) -> None:
    """`pip freeze > constraints.txt` wäre der naheliegende Weg — und löscht die
    neunzehn Zeilen Erklärung, die die Datei überhaupt verständlich machen."""
    ziel = tmp_path / "constraints.txt"
    ziel.write_text(
        "# Der Versionssatz, gegen den die Suite grün ist.\n"
        "#\n"
        "# Warum es die Datei gibt: hier steht der Grund.\n"
        "\n"
        "numpy==2.4.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_env, "CONSTRAINTS", ziel)

    class Antwort:
        returncode = 0
        stdout = "Zebra==1.0\nnumpy==2.5.0\n"
        stderr = ""

    monkeypatch.setattr(check_env.subprocess, "run", lambda *a, **k: Antwort())

    assert check_env.freeze(Path("python")) == 0

    geschrieben = ziel.read_text(encoding="utf-8")
    assert "# Warum es die Datei gibt: hier steht der Grund." in geschrieben
    assert "numpy==2.5.0" in geschrieben
    assert "numpy==2.4.0" not in geschrieben
    # sortiert wie im Bestand, damit ein Diff die Änderung zeigt und nicht die Ordnung
    assert geschrieben.strip().splitlines()[-2:] == ["numpy==2.5.0", "Zebra==1.0"]


# --- Der Zugang zum Webserver -------------------------------------------------------


def test_the_web_access_never_lands_in_the_repository() -> None:
    """Ein Passwort im Repository ist ein veröffentlichtes Passwort.

    Auch in einem privaten: Ein Klon davon liegt auf jeder Maschine, auf der
    jemand einmal gearbeitet hat, und die Versionsgeschichte vergisst nichts.
    Der Zugang steht deshalb in ``.webserver.json``, und die Datei ist
    ausgeschlossen.
    """
    import tools.upload_website as upload

    root = Path(__file__).resolve().parent.parent
    ignored = (root / ".gitignore").read_text(encoding="utf-8")

    assert "/.webserver.json" in ignored
    assert upload.ACCESS_FILE.name == ".webserver.json"
    assert upload.ACCESS_FILE.parent == root


def test_the_upload_tool_carries_no_password_of_its_own() -> None:
    """Die Vorlage nennt Host und Benutzer, das Passwort trägt sie nicht."""
    import tools.upload_website as upload

    assert upload.TEMPLATE["password"] == "hier eintragen"
    assert "@" not in upload.TEMPLATE["host"], "kein Zugang in der Adresse"


def test_only_files_below_the_website_go_up(tmp_path: Path) -> None:
    """Der Zielpfad wird aus dem lokalen abgeleitet — was daneben liegt, hat
    dort keinen abzuleiten, und ein geratener wäre schlimmer als eine Absage.
    """
    import tools.upload_website as upload

    inside = upload.LOCAL_ROOT / "api" / "support.php"
    assert upload.remote_name(inside) == "api/support.php"

    with pytest.raises(ValueError):
        upload.remote_name(tmp_path / "fremd.html")


def test_developer_notes_stay_off_the_public_server() -> None:
    """``website/README.md`` erklärt, wie die Seiten gebaut sind — 232 Zeilen,
    die niemand im Netz lesen soll.

    Der Abgleich lud sie brav mit hoch, und sie lag öffentlich da. Was die
    Regel hält, ist diese Zeile: Was unter ``website/`` liegt und ``.md``
    heißt, geht nicht hinauf.
    """
    import tools.upload_website as upload

    assert not upload.wanted(upload.LOCAL_ROOT / "README.md")
    assert not upload.wanted(upload.LOCAL_ROOT / "dl" / "Solidon3D-Setup.exe")
    assert upload.wanted(upload.LOCAL_ROOT / "index.html")
    assert upload.wanted(upload.LOCAL_ROOT / "bilder" / "schau-skull.webp")
    assert all(path.suffix != ".md" for path in upload.local_files())
