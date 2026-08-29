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

import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any, Final

import pytest

import tools.check_env as check_env
import tools.gate_lock as gate_lock
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
    """Die Version steht in ``branding.py`` und in ``pyproject.toml``.

    Sie ist dieselbe Zahl mit zwei Lesern: der Über-Dialog, jede Projektdatei
    (``app_version``), das 3MF, der Fehlerbericht und der Update-Vergleich lesen
    ``APP_VERSION``; die Paketmetadaten und alles, was ``pip`` daraus macht,
    lesen ``pyproject.toml``. Laufen sie auseinander, nennt ein Paket eine
    andere Version als das Fenster darin — und niemand merkt es, denn keines von
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
        "Beide tragen dieselbe Version — eine von ihnen wurde vergessen."
    )


# --- der festgeschriebene Versionssatz -------------------------------------------
#
# `constraints.txt` hält fest, *in welcher* Version ein Paket installiert wird.
# Sie half nur nichts, solange niemand nachsah: Wer das `-c` beim Installieren
# vergisst, bekommt andere Versionen als die, gegen die die Suite grün ist.
# `tools/check_env.py` sieht nach, der Sitzungsstart-Hook ruft es auf. Was hier
# geprüft wird, ist das Werkzeug — nicht die Umgebung dieses Laufs: Der
# wöchentliche Frühwarnlauf der CI installiert **absichtlich** ohne
# `constraints.txt`, und ein Test, der ihn rot färbt, entwertet ihn.


def test_the_pinned_set_is_read_completely() -> None:
    """Jede Zeile `name==version` landet im Satz, normalisiert nach PEP 503."""
    satz = pinned()

    assert len(satz) > 50, f"nur {len(satz)} Einträge — liest `constraints.txt` noch?"
    assert "pyside6" in satz, "PySide6 fehlt im Satz, obwohl die Oberfläche darauf steht"
    # `svg.path` steht mit Punkt in der Datei und muss trotzdem gefunden werden
    assert satz["svg-path"][0] == "svg.path"
    for name, version in satz.values():
        assert not version.startswith(("<", ">", "=")), f"{name} ist keine feste Version: {version}"


def test_names_compare_the_way_the_index_compares_them() -> None:
    """`svg.path`, `svg_path` und `SVG-Path` sind dasselbe Paket (PEP 503)."""
    assert normal("svg.path") == normal("svg_path") == normal("SVG-Path") == "svg-path"


def test_a_deviating_version_is_found() -> None:
    """Der Fall vom 06.08.2026: der Klon zog eine andere Version, die Suite fiel um."""
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
# eine Version, die *bricht*; dass es überhaupt eine neuere *gäbe*, sagt er
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
    """``website/README.md`` erklärt ausführlich, wie die Seiten gebaut sind —
    eine interne Karte, die niemand im Netz lesen soll.

    Der Abgleich lud sie brav mit hoch, und sie lag öffentlich da. Was die
    Regel hält, ist diese Zeile: Was unter ``website/`` liegt und ``.md``
    heißt, geht nicht hinauf.
    """
    import tools.upload_website as upload

    assert not upload.wanted(upload.LOCAL_ROOT / "README.md")
    assert not upload.wanted(upload.LOCAL_ROOT / "dl" / "Solidon3D-Setup.exe")
    assert not upload.wanted(upload.LOCAL_ROOT / "activation.seed")
    assert not upload.wanted(upload.LOCAL_ROOT / "operator.token")
    assert not upload.wanted(upload.LOCAL_ROOT / "api" / "activation.sqlite")
    assert not upload.wanted(upload.LOCAL_ROOT / "Anfrage.solidon-request")
    assert upload.wanted(upload.LOCAL_ROOT / "index.html")
    assert upload.wanted(upload.LOCAL_ROOT / "bilder" / "schau-skull.webp")
    assert all(path.suffix != ".md" for path in upload.local_files())


def test_uploading_a_page_includes_its_outdated_stamped_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine neue Seite darf nicht auf alte gemeinsame Dateien zeigen.

    **Der Fall.** Am 29.08.2026 lag der neue Changelog auf dem Server, seine
    Auswahl änderte aber nur das Feld: ``site.js`` war dort noch die Fassung
    ohne Umschaltlogik. Der HTML-Verweis trug schon den neuen Inhaltsstempel,
    nur die Bytes hinter der Adresse waren nie mit hochgeladen worden.

    Wer eine Seite auswählt, nimmt deshalb alle von ihr gestempelten Dateien
    mit, die oben fehlen oder abweichen. Bereits gleiche Dateien bleiben aus
    dem Upload heraus.
    """
    import tools.upload_website as upload

    page = upload.LOCAL_ROOT / "changelog.html"
    script = upload.LOCAL_ROOT / "site.js"
    style = upload.LOCAL_ROOT / "style.css"
    checked: list[Path] = []

    def is_outdated(_root: str, path: Path, _remote_size: int | None) -> bool:
        checked.append(path)
        return path == script

    monkeypatch.setattr(upload, "differs", is_outdated)

    selected = upload.with_outdated_page_assets(
        [page],
        "solidon3d.de/httpdocs",
        {"site.js": 1, "style.css": 1, "icon.svg": 1},
    )

    assert selected == [page, script]
    assert script in checked and style in checked


def test_activation_deployment_separates_public_and_private_roots() -> None:
    """Startwert und Datenbank können nie als Website-Ziele abgeleitet werden."""
    from tools import deploy_activation_server as deployment

    webroot, data_root, backup_root = deployment._paths({"root": "solidon3d.de/httpdocs"})

    assert webroot == "solidon3d.de/httpdocs"
    assert data_root == "solidon3d.de/appdata"
    assert backup_root == "solidon3d.de/backups/activation"
    assert all(
        path.name not in {"activation.seed", "activation.sqlite", "operator.token"}
        for path in deployment.PUBLIC_FILES
    )
    assert Path("api/operator.php") in deployment.PUBLIC_FILES


def test_activation_deployment_accepts_only_a_full_operator_token(tmp_path: Path) -> None:
    """Ein kurzer Zugang darf nie bis zum Produktivserver gelangen."""
    from tools import deploy_activation_server as deployment

    token = tmp_path / "operator.token"
    token.write_text("ab" * 32 + "\n", encoding="ascii")
    assert deployment._operator_token_is_valid(token)

    token.write_text("ab" * 31 + "\n", encoding="ascii")
    assert not deployment._operator_token_is_valid(token)


def test_activation_backup_contains_committed_rows_from_the_wal(tmp_path: Path) -> None:
    """Eine noch nicht eingecheckte WAL ist Teil der Datenbank, nicht Beifang."""
    import sqlite3

    from tools import deploy_activation_server as deployment

    source = tmp_path / "activation.sqlite"
    database = sqlite3.connect(source)
    try:
        database.execute("PRAGMA journal_mode=WAL")
        database.execute("PRAGMA wal_autocheckpoint=0")
        for table in ("licences", "activations", "activation_attempts", "operator_events"):
            database.execute(f"CREATE TABLE {table} (value TEXT)")
        database.commit()
        database.execute("INSERT INTO licences VALUES ('nur in der WAL')")
        database.commit()
        wal = source.with_name(source.name + "-wal")
        assert wal.is_file()

        snapshot = deployment._database_snapshot(source.read_bytes(), wal.read_bytes())
    finally:
        database.close()

    restored = tmp_path / "restored.sqlite"
    restored.write_bytes(snapshot)
    checked = sqlite3.connect(restored)
    try:
        assert checked.execute("SELECT value FROM licences").fetchone() == ("nur in der WAL",)
    finally:
        checked.close()


def test_activation_deployment_accepts_the_existing_three_table_schema(
    tmp_path: Path,
) -> None:
    """Die neue Endpunktdatei migriert erst nach dem sicheren Altbestand-Backup."""
    import sqlite3

    from tools import deploy_activation_server as deployment

    source = tmp_path / "activation.sqlite"
    database = sqlite3.connect(source)
    try:
        for table in ("licences", "activations", "activation_attempts"):
            database.execute(f"CREATE TABLE {table} (value TEXT)")
        database.commit()
    finally:
        database.close()

    snapshot = deployment._database_snapshot(source.read_bytes())

    assert snapshot
    with pytest.raises(SystemExit):
        deployment._database_bytes(source.read_bytes(), require_operator_events=True)


def test_operator_token_changes_only_with_an_explicit_rotation() -> None:
    from tools import deploy_activation_server as deployment

    old = ("ab" * 32).encode()
    new = ("cd" * 32).encode()
    assert not deployment._operator_upload_needed(old, old, False)
    with pytest.raises(SystemExit):
        deployment._operator_upload_needed(old, new, False)
    assert deployment._operator_upload_needed(old, new, True)


def test_raising_the_version_moves_both_places_and_nothing_else() -> None:
    """``tools/bump_version.py`` bewegt die Version dort, wo sie steht.

    Der Test darüber hält die beiden Orte zusammen; dieser hält das Werkzeug
    daran, das sie bewegt. Beide Regeln stecken darin, und beide sind schon
    einmal von Hand verletzt worden: Eine erhöhte Stelle setzt die dahinter auf
    null, und in ``pyproject.toml`` wird **die erste** ``version =``-Zeile
    getroffen — weiter unten stehen die Versionen der Abhängigkeiten, und ein
    Ersetzen über die ganze Datei nähme sie mit.

    Geschrieben wird hier nichts: Geprüft wird die Rechnung und die Zusage,
    dass ``--zeigen`` nur redet.
    """
    from app.branding import APP_VERSION
    from tools import bump_version

    assert bump_version.raised("0.1.1", "patch") == "0.1.2"
    assert bump_version.raised("0.1.9", "patch") == "0.1.10", "keine Ziffernarithmetik"
    assert bump_version.raised("0.1.1", "minor") == "0.2.0", "die Stelle dahinter fällt auf null"
    assert bump_version.raised("0.9.7", "major") == "1.0.0", "beide dahinter fallen auf null"

    # Und die Zeile, an der es ansetzt, gibt es noch — sonst hätte das Werkzeug
    # beim nächsten Bau nichts zu erhöhen und sagte das erst dann.
    assert bump_version.current() == APP_VERSION

    project = bump_version.PROJECT.read_text(encoding="utf-8")
    assert bump_version.PROJECT_LINE.search(project) is not None


# --- Das Schloss über dem Tor (tools/gate_lock.py) ------------------------------------

#: Kann diese Plattform den Prozessbaum lesen, den ``gate_lock`` braucht?
#:
#: **Die Bedingung fragt nach der Fähigkeit und nicht nach dem Namen der
#: Plattform**, denn das ist der Grund: ``_descendants`` liest den Baum unter
#: Windows über ``CreateToolhelp32Snapshot`` und sonst aus ``/proc``. Ein
#: POSIX-System **ohne** ``/proc`` — macOS — hat weder das eine noch das andere,
#: und dort meldet ``standing_still`` folgerichtig ``None``: „ich kann das hier
#: nicht messen." Das ist richtiges Verhalten des Werkzeugs und kein Fehler.
#:
#: **Warum das erst am 23.08.2026 auffiel**, obwohl die vier Prüfungen vom
#: Vortag stammen: Die macOS-Matrix läuft nur bei Tags und Handstarts, die
#: täglichen Pushes fahren Ubuntu. Dort gibt es ``/proc``, also war der Zweig
#: zufällig der richtige. Vier Tests waren auf macOS nie gelaufen — **nicht
#: grün, sondern ungeprüft**, und das sieht von außen gleich aus.
#:
#: **Und warum hier übersprungen und nicht portiert wird:** ``gate_lock``
#: serialisiert die Rechenzeit mehrerer Sitzungen auf *einer Arbeitsmaschine*.
#: Auf einem Bauserver gibt es weder mehrere Sitzungen noch ein Schloss — ein
#: Test, der dort ein nie gerufenes Werkzeug prüft, misst nichts. Ein
#: ``ps -eo pid=,ppid=``-Zweig wäre trotzdem besser und steht im Register;
#: gebaut wird er, wenn jemand ihn auf einem Mac fahren kann. Ungeprüfter Code
#: für eine Plattform, die man nicht hat, ist genau die Sorte, die hier gerade
#: aufgefallen ist.
KENNT_DEN_PROZESSBAUM: Final = sys.platform == "win32" or Path("/proc").is_dir()

braucht_prozessbaum = pytest.mark.skipif(
    not KENNT_DEN_PROZESSBAUM,
    reason="gate_lock liest den Prozessbaum über /proc oder die Windows-API; "
    "diese Plattform hat beides nicht",
)


@braucht_prozessbaum
def test_the_process_tree_is_read_along_the_chain_not_the_first_level() -> None:
    """Ein Enkel gehört zum Baum, auch wenn sein Vater dazwischen fehlt.

    **Der Fall, der diese Prüfung veranlasst hat.** Am 22.08.2026 hat eine
    Sitzung einen laufenden Testlauf für tot erklärt: „Die bash hat kein Kind
    mehr, kein pytest, nichts." Der ``pytest`` lief sehr wohl — eine Ebene
    tiefer, unter einem Zwischenprozess. Wer nur die erste Ebene zählt, misst
    die Prozesskette nicht. Hätte man dem Schluss geglaubt, wäre ein Torlauf
    mit 3453 bestandenen Tests verworfen worden.
    """
    import os
    import subprocess
    import time

    # Ein Kind, das selbst ein Kind startet und wartet: Der Enkel hängt zwei
    # Ebenen unter uns.
    innen = "import time; time.sleep(6)"
    aussen = f"import subprocess, sys; subprocess.run([sys.executable, '-c', {innen!r}])"
    kind = subprocess.Popen([sys.executable, "-c", aussen])
    try:
        time.sleep(1.5)
        baum = gate_lock._descendants(os.getpid())
        assert kind.pid in baum, "das eigene Kind fehlt im Baum"
        assert len(baum) >= 3, (
            f"der Enkel fehlt — gefunden wurden nur {len(baum)} Prozesse, "
            "die Kette wird also nicht verfolgt"
        )
    finally:
        kind.kill()
        kind.wait(timeout=5)


@braucht_prozessbaum
def test_standing_still_tells_a_sleeper_from_a_worker() -> None:
    """Ob etwas rechnet, sagt die Rechenzeit über ein **Intervall**.

    Die Gesamtzeit eines wartenden Wrappers ist immer klein, egal was sein Kind
    tut — auch dieser Fehler ist am 22.08.2026 einmal gemacht worden. Geprüft
    wird deshalb in beide Richtungen: Ein Schläfer muss als stehend erkannt
    werden **und** ein Rechner nicht. Eine Prüfung, die nur die eine Hälfte
    kann, meldet entweder immer Stillstand oder nie.
    """
    import subprocess
    import time

    schlaefer = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    rechner = subprocess.Popen([sys.executable, "-c", "x = 0\nwhile True:\n    x += 1"])
    try:
        time.sleep(0.5)
        assert gate_lock.standing_still(schlaefer.pid, sample=1.0) is True, (
            "ein Schläfer rechnet nicht"
        )
        assert gate_lock.standing_still(rechner.pid, sample=1.0) is False, "ein Rechner rechnet"
    finally:
        for prozess in (schlaefer, rechner):
            prozess.kill()
            prozess.wait(timeout=5)


def test_an_unknown_process_says_nothing_instead_of_standing_still() -> None:
    """„Nicht messbar" ist nicht „steht".

    Eine Prozessnummer, die niemand trägt, darf keinen Stillstand melden —
    sonst hinge an jeder verwaisten Nummer eine Warnung, und die Auskunft wäre
    wertlos. ``None`` heißt keine Aussage, und nur das.
    """

    assert gate_lock._cpu_seconds(0) is None
    assert gate_lock.standing_still(2**30) is None


@braucht_prozessbaum
def test_a_test_process_is_found_by_its_command_not_its_ancestry() -> None:
    """Der Wächter findet einen Testlauf auch dann, wenn die Kette zu ihm reißt.

    **Der Fall.** Am 22.08.2026 meldete der Wächter an einem belegten Tor
    „rechnet nicht" — richtig, aber aus dem falschen Grund: Sein Baum bestand
    aus **einem** Prozess, dem Halter selbst. Der ``pytest`` lief unter einer
    ganz anderen Kette, weil Windows die Elternnummer nicht umsetzt, wenn der
    Elternprozess endet. Beim nächsten Mal wäre der Lauf gesund gewesen, die
    Warnung trotzdem gekommen, und jemand hätte ihn abgebrochen.

    Dieser Test ist sein eigener Zeuge: Er läuft unter ``pytest``, also muss
    der Wächter ihn sehen.

    **Gesehen heißt: er selbst oder ein Vorfahre.** Unter ``pytest-xdist``
    läuft dieser Test in einem Worker, und dessen Kommandozeile ist ein
    nacktes ``python -c`` — weder ``pytest`` noch ``execnet`` stehen darin.
    Die erste Fassung fragte nur ``os.getpid() in _test_processes()`` und fiel
    deshalb unter ``-n 2``, gefunden von 3d-druck-b8 beim Parallelisieren der
    Suite. Der **Wächter** war nie falsch: Er nimmt zu jedem am Kommando
    gefundenen Prozess dessen Unterbaum, und über den kommt der Worker herein.
    Falsch war der Test, der eine Hälfte des Verfahrens prüfte und sie für das
    Ganze hielt — genau deshalb stehen beide Wege im Werkzeug: Der Baum wird
    über die Kette gelesen, und wo die Kette reißt, über das Kommando.
    """
    import os

    watched: set[int] = set()
    for pid in gate_lock._test_processes():
        watched |= gate_lock._descendants(pid)

    assert os.getpid() in watched, (
        "der laufende pytest findet sich nicht selbst — weder über das Kommando noch über die Kette"
    )


@braucht_prozessbaum
def test_a_named_process_is_measured_with_its_children() -> None:
    """Wer über das Kommando gefunden wird, wird mit seinem Unterbaum gemessen.

    ``subprocess.Popen`` startet auf Windows einen Wrapper, der den echten
    Python-Prozess erst erzeugt: Der Wrapper verbraucht 0,016 Sekunden und
    steht danach still, während sein Kind rechnet. Wer nur die gefundene
    Nummer misst, hält **jeden** solchen Lauf für stehend — und das ist der
    Fehlalarm, der einen gesunden Lauf kostet.

    Geprüft wird in beide Richtungen: ein rechnender Prozess darf nicht als
    stehend gelten, ein schlafender muss es.
    """
    import subprocess
    import time

    rechner = subprocess.Popen([sys.executable, "-c", "x = 0\nwhile True:\n    x += 1"])
    schlaefer = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(25)"])
    try:
        time.sleep(1.0)
        # Als ``extra`` übergeben und mit einer Wurzel gemessen, die selbst
        # nichts tut — nur der Unterbaum des Genannten kann den Ausschlag geben.
        assert gate_lock.standing_still(4, sample=1.0, extra=frozenset({rechner.pid})) is False, (
            "ein rechnender Testprozess wird als stehend gemeldet"
        )
        assert gate_lock.standing_still(4, sample=1.0, extra=frozenset({schlaefer.pid})) is True, (
            "ein schlafender Testprozess wird als rechnend gemeldet"
        )
    finally:
        for prozess in (rechner, schlaefer):
            prozess.kill()
            prozess.wait(timeout=5)


def test_a_finished_process_is_not_alive_while_its_handle_is_still_open() -> None:
    """Ein Handle auf einen Prozess heißt nicht, dass er läuft.

    **Der Fall, der es gezeigt hat.** Am 22.08.2026 stand das Schloss
    neunzehn Minuten auf einem Halter, dessen Testlauf längst beendet war;
    vier Sitzungen kamen nicht ins Tor, und ``_stale()`` übernahm es nicht,
    weil ``_alive()`` „lebt" sagte. Windows gibt den Prozesseintrag erst frei,
    wenn das letzte Handle darauf geschlossen ist — und jedes
    ``subprocess.Popen`` hält seines offen. ``OpenProcess`` liefert deshalb
    auch für einen beendeten Prozess ein Handle.

    Geprüft wird in beide Richtungen: Der beendete darf nicht als lebend
    gelten, der laufende muss es. Eine Prüfung, die nur die eine Hälfte kann,
    gibt entweder jedes Schloss sofort frei oder nie.
    """
    import subprocess
    import time

    # ``wait()`` beendet den Prozess, das Popen-Objekt hält sein Handle weiter.
    beendet = subprocess.Popen([sys.executable, "-c", "raise SystemExit(1)"])
    beendet.wait(timeout=10)
    laeuft = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(15)"])
    try:
        time.sleep(0.3)
        assert gate_lock._alive(beendet.pid) is False, (
            "ein beendeter Prozess gilt als lebend — das Schloss bliebe auf ihm stehen"
        )
        assert gate_lock._alive(laeuft.pid) is True, "ein laufender Prozess gilt als tot"
    finally:
        laeuft.kill()
        laeuft.wait(timeout=5)


# --- Aufräumen auf dem Server (tools/upload_website.py) --------------------------------


class _AttrappeFTP:
    """Antwortet wie eine FTP-Sitzung, so weit ``stale_packages`` sie benutzt.

    **Attrappiert werden nur die beiden Datenquellen** — was `version.json` oben
    sagt und was unter `dl/` liegt. Geprüft wird die Entscheidung darüber, und
    die steckt im Werkzeug, nicht hier. Der Unterschied ist am 23.08.2026 teuer
    geworden: Zwei Tests einer anderen Sitzung prüften an jenem Tag eine
    Attrappe statt der Sache und waren grün, während die Sache falsch war.
    """

    def __init__(self, version_json: dict[str, Any], dateien: list[str]) -> None:
        self.version_json = version_json
        self.dateien = dateien
        self.geloescht: list[str] = []

    def retrbinary(self, befehl: str, schreiben: Any) -> None:
        assert befehl.startswith("RETR "), befehl
        schreiben(json.dumps(self.version_json).encode("utf-8"))

    def mlsd(self, path: str, facts: list[str] | None = None) -> list[tuple[str, dict[str, str]]]:
        if not path.endswith("/dl"):
            return []
        return [(name, {"type": "file", "size": "1"}) for name in self.dateien]

    def delete(self, pfad: str) -> None:
        self.geloescht.append(pfad)


def _version_json(version: str) -> dict[str, Any]:
    return {
        "version": version,
        "packages": {
            "windows": {
                "url": f"https://solidon3d.de/api/count.php?f=Solidon3D-Setup-{version}.exe",
                "file": f"Solidon3D-Setup-{version}.exe",
                "size": 1,
                "sha256": "0" * 64,
            }
        },
    }


def test_the_cleanup_waits_until_the_server_names_the_new_version() -> None:
    """Gelöscht wird erst, wenn ``version.json`` **oben** die neue Fassung nennt.

    **Der Fall.** Beim Veröffentlichen von 0.1.3 wurden die alten Pakete
    gelöscht, bevor die Seiten und ``version.json`` hochgeladen waren. Mehrere
    Minuten lang zeigte die Startseite in sechs Sprachen auf vier Dateien, die
    es nicht mehr gab, und die Update-Prüfung bot jedem Kunden eine Fassung an,
    deren Datei 404 gab.

    **Warum es keine lokale Prüfung fangen konnte:** Lokal war durchgehend alles
    stimmig — die neue ``version.json`` lag hier, die neuen Pakete lagen hier.
    Falsch war nur, was *oben* lag, und danach hatte niemand gefragt. Deshalb
    liest die Bedingung den Server und nicht die Platte.
    """
    from app.branding import APP_VERSION
    from tools.upload_website import stale_packages

    alt = "0.0.1"
    sitzung = _AttrappeFTP(_version_json(alt), [f"Solidon3D-Setup-{alt}.exe"])
    veraltet, grund = stale_packages(sitzung, "httpdocs")  # type: ignore[arg-type]

    assert veraltet == [], "es wurde etwas zum Löschen vorgeschlagen, obwohl der Server alt ist"
    assert alt in grund and APP_VERSION in grund, f"der Grund nennt die Fassungen nicht: {grund}"


def test_the_cleanup_spares_what_the_version_file_still_promises() -> None:
    """Verschont wird, was ``version.json`` nennt — und was die Fassung trägt.

    Beide Namensfelder zählen. ``updates.py`` liest ``url`` **und** ``file``, und
    wer nur eines auswertet, hält eine Datei für entbehrlich, die das andere
    noch verspricht. Dazu kommt alles mit der laufenden Fassung im Namen: Die
    Attrappe dieses Tests nennt nur Windows; das aktuelle Flatpak darf der
    Abgleich trotzdem nicht löschen.
    """
    from app.branding import APP_VERSION
    from tools.upload_website import stale_packages

    aktuell = f"Solidon3D-Setup-{APP_VERSION}.exe"
    flatpak = f"Solidon3D-{APP_VERSION}-x86_64.flatpak"
    sitzung = _AttrappeFTP(
        _version_json(APP_VERSION),
        [aktuell, flatpak, "Solidon3D-Setup-0.0.1.exe", "Solidon3D-0.0.1-x86_64.flatpak"],
    )
    veraltet, grund = stale_packages(sitzung, "httpdocs")  # type: ignore[arg-type]

    assert grund == "", f"unerwarteter Einwand: {grund}"
    assert aktuell not in veraltet, "das Paket der laufenden Fassung soll bleiben"
    assert flatpak not in veraltet, "das aktuelle Flatpak bleibt auch ohne Eintrag in der Attrappe"
    assert veraltet == ["Solidon3D-0.0.1-x86_64.flatpak", "Solidon3D-Setup-0.0.1.exe"], veraltet


def test_the_promise_is_read_from_both_name_fields() -> None:
    """``url`` **und** ``file`` — und der Test unterscheidet sie ausdrücklich.

    **Warum das einen eigenen Test braucht.** In der echten ``version.json``
    tragen beide Felder denselben Namen. Ein Test, der sie mit gleichen Werten
    füttert, bleibt deshalb grün, wenn die Auswertung nur eines von beiden
    ansieht — die Gegenprobe zu den Tests darüber ist genau daran gescheitert.
    Und dieselbe Lücke gab es am selben Tag schon einmal, in
    ``test_website.py``: derselbe Name, zweimal in einer Datei, einmal geprüft.

    ``updates.py`` liest beide (Zeile 22 und 32): das eine, um zu laden, das
    andere, um die geladene Datei zu benennen. Wer nur eines auswertet, hält
    eine Datei für entbehrlich, die das andere Feld noch verspricht — und
    löscht sie.
    """
    from tools.upload_website import promised_files

    versprochen = promised_files(
        {
            "packages": {
                "windows": {
                    "url": "https://solidon3d.de/api/count.php?f=geladen.exe",
                    "file": "benannt.exe",
                }
            }
        }
    )
    assert versprochen == {"geladen.exe", "benannt.exe"}, (
        f"gefunden: {sorted(versprochen)} — beide Felder zählen, nicht nur eines"
    )


# --- Läuft die Automatik überhaupt? (tools/check_env.py) -------------------------------


def test_the_hook_check_notices_when_git_never_looks_at_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drei Antworten von ``git config``, drei Urteile.

    **Der Anlass.** ``CLAUDE.md`` sagt zu, dass jeder Commit sofort hinausgeht —
    ``.githooks/post-commit`` erledigt das. Am 23.08.2026 zeigte sich, dass Git
    diesen Hook nie angesehen hat: ``core.hooksPath`` war auf keiner Ebene
    gesetzt, und ohne ihn sucht Git in ``.git/hooks/``, wo nichts liegt.

    **Warum es niemandem auffiel:** Das Ergebnis stimmte trotzdem, weil immer
    jemand von Hand gepusht hat. Eine Automatik, die in Wahrheit Handarbeit ist,
    ist gefährlicher als gar keine — man verlässt sich auf sie.

    Geprüft wird deshalb nicht der Hook, sondern **dass er gerufen wird**. Und
    der dritte Fall ist der, den man vergisst: ein Pfad, der *gesetzt* ist und
    woandershin zeigt. „Nicht leer" ist nicht dasselbe wie „richtig".
    """

    class Antwort:
        def __init__(self, text: str) -> None:
            self.stdout = text
            self.returncode = 0

    for gesetzt, erwartet, was in (
        ("", False, "gar nicht gesetzt"),
        (".githooks\n", True, "auf .githooks gesetzt"),
        ("irgendwo/anders\n", False, "auf ein anderes Verzeichnis gesetzt"),
    ):
        monkeypatch.setattr(check_env.subprocess, "run", lambda *a, _t=gesetzt, **k: Antwort(_t))
        assert check_env.hooks_are_wired() is erwartet, was


def test_the_environment_report_names_the_command_that_fixes_the_hooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Befund ohne Handlungsvorschlag ist eine Klage (§ AGENTS.md, Regel 17).

    Der Bericht von ``check_env`` läuft beim Sitzungsstart. Er soll nicht sagen,
    dass etwas fehlt, sondern womit man es einrichtet — sonst sucht der Nächste
    dieselbe Zeile noch einmal.
    """
    # **Die Umgebung wird mitgestellt, nicht vorausgesetzt.** ``check`` steigt
    # aus, sobald ``.venv`` fehlt — und in der CI gibt es keine, dort läuft
    # alles im System-Python. Der Test war damit auf einem Entwicklerrechner
    # grün und auf dem Bauserver rot, und zwar seit seinem ersten Tag: Er kam
    # dort nie bis zu der Zeile, die er prüfen will.
    monkeypatch.setattr(check_env, "venv_python", lambda: Path(sys.executable))
    monkeypatch.setattr(
        check_env, "interpreter_version", lambda _python: check_env.required_version()
    )
    monkeypatch.setattr(check_env, "installed", lambda _python: {})
    monkeypatch.setattr(check_env, "pinned", dict)
    monkeypatch.setattr(check_env, "age_in_days", lambda: None)
    monkeypatch.setattr(check_env, "hooks_are_wired", lambda: False)
    findings, suggestions = check_env.check()

    passende = [zeile for zeile in suggestions if "core.hooksPath" in zeile]
    assert passende, f"kein Vorschlag zu den Hooks: {suggestions}"
    assert "git config core.hooksPath .githooks" in passende[0], passende[0]
    assert any("githooks" in zeile for zeile in findings), findings


def test_the_cleanup_refuses_when_the_version_file_promises_nothing() -> None:
    """Eine leere Schonliste schont nichts — dann wird gar nicht gelöscht.

    **Der Fall, den dieser Test festhält.** ``stale_packages`` verschont, was
    ``version.json`` nennt. Nennt sie nichts, ist die Schonliste leer, und dann
    steht **jede** Datei unter ``dl/`` auf der Liste, die nicht zufällig die
    laufende Fassung im Namen trägt — beim Veröffentlichen von 0.1.3 wären das
    vierzehn Pakete gewesen.

    Die Bedingung darüber greift hier nicht: Sie prüft die **Versionsnummer**,
    und die kann stimmen, während ``packages`` fehlt, leer ist oder Einträge
    trägt, die keine Zuordnungen sind. Genau dann ist die Auskunft
    unvollständig, und ein Werkzeug, das auf einem Produktivserver löscht, darf
    daraus keine weitreichende Handlung ableiten.
    """
    from app.branding import APP_VERSION
    from tools.upload_website import stale_packages

    for leer in ({}, {"packages": {}}, {"packages": {"windows": "kein Eintrag, nur Text"}}):
        payload = {"version": APP_VERSION, **leer}
        sitzung = _AttrappeFTP(payload, ["Solidon3D-Setup-0.0.1.exe"])
        stale, reason = stale_packages(sitzung, "httpdocs")  # type: ignore[arg-type]

        assert stale == [], f"würde löschen, obwohl version.json nichts nennt: {leer}"
        assert "kein einziges Paket" in reason, reason


def test_the_hook_check_reads_what_git_really_answers(tmp_path: Path) -> None:
    """Die Attrappe darüber prüft drei Fälle — dieser prüft, dass sie stimmen.

    **Warum beides.** Der Test darüber ersetzt ``subprocess.run`` und kommt
    damit in einer Millisekunde durch alle drei Antworten. Er prüft aber die
    *Annahme* über ``git config``, nicht ``git config`` selbst — und die Annahme
    war an einer Stelle falsch: Bei einem nicht gesetzten Wert antwortet Git mit
    **Exit 1** und leerer Ausgabe, die Attrappe meldete Exit 0. Dass es trotzdem
    trägt, liegt daran, dass ``hooks_are_wired`` allein die Ausgabe auswertet —
    aber das war Glück und nicht Absicht.

    Deshalb hier ein echtes Repository in einem Temp-Ordner: zwei Zustände, zwei
    Aufrufe, und die Verankerung, dass die Attrappe die Wirklichkeit trifft.
    """
    import subprocess

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args], capture_output=True, text=True, timeout=20
        )

    git("init", "-q")
    (tmp_path / ".githooks").mkdir()

    ohne = git("config", "--get", "core.hooksPath")
    assert ohne.stdout.strip() == "", "ein nicht gesetzter Wert gibt Text zurück?"
    assert ohne.returncode != 0, "Git meldet einen nicht gesetzten Wert als Erfolg?"

    git("config", "core.hooksPath", ".githooks")
    mit = git("config", "--get", "core.hooksPath")
    assert mit.stdout.strip() == ".githooks", mit.stdout
    assert mit.returncode == 0, mit.returncode


def test_the_lock_notices_when_the_tree_moves_under_a_run(tmp_path: Path) -> None:
    """Ein Lauf, unter dem jemand schreibt, misst einen Zeitpunkt und nicht den Baum.

    **Der Anlass, viermal am 23.08.2026.** Das Schloss serialisiert Rechenzeit —
    es hindert niemanden daran, in denselben Baum zu schreiben, während gemessen
    wird. Ein Torlauf lief zehn Minuten gegen einen Import, den eine andere
    Sitzung im selben Moment reparierte: zweimal rot, reproduzierbar, Ursache im
    Code gelesen und trotzdem falsch. Ein anderer sah eine Datei halb umgebaut
    und meldete Kennzahlen, die es so nie gab.

    **Verhindert wird nichts** — das kann ein Schloss nicht, ohne allen anderen
    das Schreiben zu verbieten. Gemeldet wird, und das genügt: Wer hinterher
    liest „vier Dateien haben sich bewegt", weiß, dass die Zahl darüber eine
    Momentaufnahme ist.

    Geprüft wird beides, denn eine Warnung, die immer kommt, liest niemand mehr.
    """
    from tools.gate_lock import _head_commit, _moved_sources, _source_stamps

    # **Der Stand gehört zur Messung.** Wer zwei Ergebnisse vergleicht, muss
    # sehen, ob sie denselben Commit meinen — 3d-druck-b8 hat einen richtigen
    # Befund zurückgezogen, weil sie nach einer fremden Reparatur nachmaß und
    # den neuen Stand für den alten hielt. Eine Zahl ohne Stand ist eine Zahl
    # ohne Datum.
    stand = _head_commit()
    assert stand, "kein Commit-Stand — läuft das hier ohne Git?"
    assert len(stand) >= 7, f"unerwarteter Stand: {stand!r}"

    stamps = _source_stamps()
    assert len(stamps) > 200, f"nur {len(stamps)} Quelldateien — stimmen die Ordner noch?"
    assert not _moved_sources(stamps), "ohne Schreibvorgang darf sich nichts bewegt haben"

    ziel = Path(__file__)
    vorher = ziel.stat().st_mtime
    try:
        ziel.touch()
        bewegt = _moved_sources(stamps)
        assert str(ziel.relative_to(ziel.parent.parent)) in bewegt, (
            f"die berührte Datei fehlt in {sorted(bewegt)[:4]}"
        )
    finally:
        os.utime(ziel, (vorher, vorher))


def test_the_version_file_waits_for_its_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    """``version.json`` geht erst hoch, wenn ihre Pakete oben liegen.

    **Der Fall.** Am 27.08.2026 lud ``--fehlend`` beim Veröffentlichen von
    0.2.1 sechs Startseiten und ``version.json`` hoch — und kein einziges
    Paket. Das ist kein Versehen im Aufruf, sondern die Bauart des Werkzeugs:
    :func:`wanted` nimmt ``dl/`` bewusst aus, weil Pakete einmal hochgehen und
    nicht bei jedem Abgleich. Nur zeigt ``version.json`` genau dorthin.

    Minutenlang versprach die Seite Fassung 0.2.1, und alle drei Pakete gaben
    HTTP 404 — derselbe Zustand wie am 23.08.2026 bei 0.1.3, nur von der
    anderen Seite verursacht: dort wurde zu früh gelöscht, hier zu früh
    veröffentlicht.

    **Gemessen wird an der Grenze**, also an :func:`remote_index`, das den
    Serverstand liefert. Eine Attrappe des FTP-Objekts wäre nach dem Code
    geformt, den sie prüfen soll — genau der Fehler, der am selben Tag den
    Release-Lauf gekostet hat (``FakePackage`` mit ``path.stat()``).
    """
    import tools.upload_website as upload

    version = upload.LOCAL_ROOT / "version.json"
    versprochen = upload.promised_files(json.loads(version.read_text(encoding="utf-8")))
    if not versprochen:
        pytest.skip("version.json führt noch keine Pakete — vor dem Release richtig")

    dateien = [version, upload.LOCAL_ROOT / "index.html"]

    # Nichts oben: version.json bleibt liegen, die Seite geht trotzdem.
    monkeypatch.setattr(upload, "remote_index", lambda *_: {})
    rest = upload.hold_back_version(None, "httpdocs", list(dateien))
    assert version not in rest, "version.json ging hoch, obwohl kein Paket oben liegt"
    assert upload.LOCAL_ROOT / "index.html" in rest, "die Seiten sollen trotzdem hochgehen"

    # Alles oben, und zwar vollständig: sie geht mit. Die Größe muss zu der
    # lokalen Datei passen — seit ``hold_back_version`` nicht mehr nur nach dem
    # Namen fragt, ist eine erfundene Größe ein halbes Paket.
    monkeypatch.setattr(
        upload,
        "remote_index",
        lambda *_: {f"dl/{name}": _ganze_groesse(name) for name in versprochen},
    )
    rest = upload.hold_back_version(None, "httpdocs", list(dateien))
    assert version in rest, "version.json blieb liegen, obwohl alle Pakete oben sind"


def _ganze_groesse(name: str) -> int:
    """Die Größe, die eine vollständig hochgeladene Datei oben hätte."""
    import tools.upload_website as upload

    hier = upload.LOCAL_ROOT / "dl" / name
    return hier.stat().st_size if hier.is_file() else 1


def test_the_version_file_waits_for_a_package_that_only_looks_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein abgebrochener Upload hinterlässt den Namen — und ein halbes Paket.

    **Warum der Name nicht reicht.** Die Pakete wiegen 260 bis 412 MB und gehen
    mit rund 1,8 MB/s hinauf; dass mehrere am Stück die Verbindung reißen, ist
    im Projekt vermerkt („ein halbes Paket sieht ganz aus"). Bricht der Upload
    ab, steht der Eintrag oben und trägt einen Teil der Bytes. Wer nur fragt, ob
    der Name da ist, gibt ``version.json`` darüber frei — und das ist schlimmer
    als der 404, gegen den die Funktion gebaut wurde: Es sieht wie ein Erfolg
    aus, und die Update-Automatik lädt das Bruchstück jedem Kunden herunter.

    Verschärfend kommt hinzu, dass ein zweiter Lauf es nicht heilt:
    :func:`wanted` nimmt ``dl/`` vom ``--fehlend``-Abgleich aus, die halbe Datei
    wird also nicht noch einmal angefasst.

    Die Größe liegt vor — ``remote_index`` liefert sie als ``dict[str, int]``,
    und :func:`differs` wie :func:`verify_downloads` vergleichen sie längst. Nur
    an dieser einen Stelle wurde sie verworfen.
    """
    import tools.upload_website as upload

    version = upload.LOCAL_ROOT / "version.json"
    versprochen = upload.promised_files(json.loads(version.read_text(encoding="utf-8")))
    vorhanden = [name for name in versprochen if (upload.LOCAL_ROOT / "dl" / name).is_file()]
    if not vorhanden:
        pytest.skip("kein Paket unter website/dl/ — ohne Vergleichsmaß sagt der Fall nichts")

    dateien = [version, upload.LOCAL_ROOT / "index.html"]
    halbes = vorhanden[0]

    def oben(_session: object, _pfad: str) -> dict[str, int]:
        """Alle Namen liegen oben — eines davon aber nur zur Hälfte."""
        stand = {f"dl/{name}": _ganze_groesse(name) for name in versprochen}
        stand[f"dl/{halbes}"] = _ganze_groesse(halbes) // 2
        return stand

    monkeypatch.setattr(upload, "remote_index", oben)
    rest = upload.hold_back_version(None, "httpdocs", list(dateien))

    assert version not in rest, (
        f"version.json ging hoch, obwohl {halbes} oben nur halb liegt — "
        "der Name allein hat entschieden"
    )
    assert upload.LOCAL_ROOT / "index.html" in rest, "die Seiten sollen trotzdem hochgehen"

    # Gegenprobe: dieselbe Lage, nur vollständig — dann geht sie mit.
    monkeypatch.setattr(
        upload,
        "remote_index",
        lambda *_: {f"dl/{name}": _ganze_groesse(name) for name in versprochen},
    )
    rest = upload.hold_back_version(None, "httpdocs", list(dateien))
    assert version in rest, "version.json blieb liegen, obwohl alle Pakete vollständig oben sind"


def test_only_the_five_delivered_files_go_into_the_box() -> None:
    """Der Kasten nimmt fünf Dateien — die, die auch hochgeladen werden.

    **Der Fall.** Der Baulauf wirft acht aus: Linux drei (Archiv, AppImage,
    Flatpak), macOS zwei je Architektur. Ab der nächsten Version werden fünf
    hochgeladen: Windows, die beiden Mac-Pakete sowie AppImage und Flatpak für
    Linux. Das Archiv bleibt ein Bauartefakt.

    Am 27.08.2026 gingen beim Release von 0.2.1 alle acht in den Kasten. Die
    Startseiten verwiesen danach in sechs Sprachen auf vier Dateien, die nie
    hochgeladen werden; ein Klick darauf hätte 404 gegeben, und keine Prüfung
    hätte etwas gesagt — ``--alte-pakete`` sieht nur ``version.json``, und die
    führt ohnehin nur drei.

    Geprüft wird in beide Richtungen. Die zweite wiegt schwerer: Eine Datei zu
    viel ist ein toter Verweis, eine zu wenig lässt ein ganzes Zielsystem ohne
    Download — und das sieht niemand, der die Seite auf seinem Rechner ansieht.
    """
    from tools.make_download import DELIVERED, refuse_wrong_delivery

    ausgeliefert = [
        Path("Solidon3D-Setup-0.2.1.exe"),
        Path("Solidon3D-0.2.1-x86_64.AppImage"),
        Path("Solidon3D-0.2.1-x86_64.flatpak"),
        Path("Solidon3D-0.2.1-macos-arm64.pkg"),
        Path("Solidon3D-0.2.1-macos-x86_64.pkg"),
    ]
    assert len(ausgeliefert) == len(DELIVERED), "die Probe deckt nicht jeden Platz ab"
    refuse_wrong_delivery(ausgeliefert)  # muss durchgehen

    # Zu viel: die drei aus dem Baulauf, die nicht ausgeliefert werden.
    for zu_viel in (
        "Solidon3D-0.2.1-linux-x86_64.tar.gz",
        "Solidon3D-0.2.1-macos-arm64.zip",
        "Solidon3D-0.2.1-macos-x86_64.zip",
    ):
        with pytest.raises(SystemExit) as fehler:
            refuse_wrong_delivery([*ausgeliefert, Path(zu_viel)])
        assert zu_viel in str(fehler.value), f"{zu_viel} wird nicht benannt"

    # Zu wenig: jeder Platz einzeln ausgelassen.
    for ausgelassen in range(len(ausgeliefert)):
        rest = [p for i, p in enumerate(ausgeliefert) if i != ausgelassen]
        with pytest.raises(SystemExit) as fehler:
            refuse_wrong_delivery(rest)
        assert "fehlt" in str(fehler.value), f"Platz {ausgelassen} fehlt unbemerkt"


# --- Die Auszeichnung für Suchmaschinen (tools/make_seo.py) ---------------------------


def test_the_stripped_answer_keeps_no_gap_before_a_comma() -> None:
    """Ein Tag wird zu einem Leerzeichen — vor einem Satzzeichen darf keines bleiben.

    ``_plain`` ersetzt jedes Tag durch ein Leerzeichen, damit das Ende eines
    Absatzes nicht am Anfang des nächsten klebt. Steht hinter dem Tag ein
    Satzzeichen, wurde daraus eine Lücke davor: aus ``<b>…1.0</b>, die
    Verkaufsversion`` wurde ``…1.0 , die Verkaufsversion``. Am 28.08.2026 stand
    das an sechs Stellen in der ausgelieferten Auszeichnung, in fünf Sprachen.

    Die Gegenprobe gehört dazu: Vor ``:`` setzt die französische Fassung
    bewusst ein Leerzeichen. Ein Fix über alle Satzzeichen hätte sie gebrochen.
    """
    from tools.make_seo import _plain

    assert _plain("<b>Version 1.0</b>, die Fassung") == "Version 1.0, die Fassung"
    assert (
        _plain("<p>als Baustein speichern</p>. Beim Anlegen")
        == "als Baustein speichern. Beim Anlegen"
    )
    assert _plain("<p>eins</p><p>zwei</p>") == "eins zwei", "die Absatzgrenze ging verloren"
    assert _plain("un terminal&nbsp;: <code>flatpak</code>") == "un terminal : flatpak"


def test_a_foreign_file_does_not_take_a_delivery_slot() -> None:
    """Der Platz gehört dem Produkt, nicht der Endung.

    ``delivery_slot`` entschied allein am Suffix. Damit besetzte jede fremde
    ``.exe`` im Übergabeordner den Windows-Platz — und
    ``refuse_wrong_delivery`` fängt das nur, solange auch die echte Datei dabei
    ist: Dann meldet sie „zweimal". Liegt die fremde allein da, sah die
    Auslieferung vollständig aus.

    Die Gegenprobe gehört dazu: Die fünf echten Namen müssen ihre Plätze
    weiterhin bekommen, sonst hätte die Härtung die Auslieferung stillgelegt.
    """
    from tools.make_download import DELIVERED, delivery_slot

    assert delivery_slot("irgendwas-fremdes.exe") == "", "eine fremde .exe besetzt Windows"
    assert delivery_slot("setup.exe") == "", "ein Allerweltsname besetzt Windows"
    assert delivery_slot("fremd-x86_64.AppImage") == "", "ein fremdes AppImage besetzt Linux"
    assert delivery_slot("fremd-x86_64.flatpak") == "", "ein fremdes Flatpak besetzt Linux"

    echt = {
        "Solidon3D-Setup-9.9.9.exe": "Windows",
        "Solidon3D-9.9.9-x86_64.AppImage": "Linux AppImage",
        "Solidon3D-9.9.9-x86_64.flatpak": "Linux Flatpak",
        "Solidon3D-9.9.9-macos-arm64.pkg": "macOS (Apple Silicon)",
        "Solidon3D-9.9.9-macos-x86_64.pkg": "macOS (Intel)",
    }
    assert set(echt.values()) == {label for label, _s, _m in DELIVERED}, (
        "die fünf Plätze haben sich geändert — dieser Test kennt sie nicht mehr"
    )
    for name, platz in echt.items():
        assert delivery_slot(name) == platz, f"{name} bekam {delivery_slot(name)!r} statt {platz!r}"


def test_windowed_suite_selection_follows_the_fixture_graph(tmp_path: Path) -> None:
    """Vererbte Fenster-Fixtures zählen, bloße Wörter im Quelltext nicht."""
    from tools.list_windowed_tests import collect_windowed

    (tmp_path / "conftest.py").write_text(
        "import pytest\n"
        "@pytest.fixture\n"
        "def qt_app():\n"
        "    return object()\n"
        "@pytest.fixture\n"
        "def middle(qt_app):\n"
        "    return qt_app\n",
        encoding="utf-8",
    )
    windowed = tmp_path / "test_windowed.py"
    windowed.write_text(
        "def test_windowed(middle):\n    assert middle is not None\n",
        encoding="utf-8",
    )
    plain = tmp_path / "test_plain.py"
    plain.write_text(
        "def test_plain():\n"
        '    """MainWindow, Viewport und pyvista sind hier nur Wörter."""\n'
        "    assert True\n",
        encoding="utf-8",
    )

    found = collect_windowed((tmp_path,), confcutdir=tmp_path)

    assert found == (windowed.resolve(),)
