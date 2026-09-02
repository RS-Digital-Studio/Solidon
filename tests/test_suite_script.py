"""Der Prüfstand für ``suite-getrennt.sh`` — das Werkzeug, das das Tor fährt.

**Ein Prüfwerkzeug ist auch nur Code, und es war schon viermal der Fehler**
(`.claude/rules/tests.md`). Dieses hier entscheidet, ob ein Lauf als grün, als
rot oder als „nie gelaufen" gilt, und aus dieser Entscheidung liest jede
Sitzung ab, ob sie fertig ist. Ein Fehler darin ist teurer als ein roter Test:
Er sieht aus wie ein grüner Stand.

Geprüft wird zweierlei. Die vier Auswertungsfunktionen bekommen **gefälschte
Protokolle** — je Zweig eines, auch für die, die im echten Lauf selten
entstehen. Und die Halbierungsschleife bekommt ein **gefälschtes pytest**, das
über einer bestimmten Portionsgröße reißt: Nur so lässt sich zeigen, dass das
Skript von selbst kleiner wird, statt eine Konstante zu brauchen.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parent.parent
    / ".claude"
    / ".state"
    / "oberflaechen-durchsicht-2026-08-19"
    / "suite-getrennt.sh"
)

BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="ohne bash gibt es nichts zu prüfen")


def test_the_script_lies_where_the_house_rules_point() -> None:
    """Ein Skip über das fehlende Skript hätte einen Umzug still grün gemacht.

    ``CLAUDE.md`` und `/pruefen` nennen den Pfad wörtlich; wer das Skript
    verschiebt oder umbenennt, bekommt hier einen roten Test statt einer
    Datei voller Skips — und die übrigen Prüfungen darunter melden dann nicht
    „übersprungen", sondern scheitern an einer Ursache, die dieser Test nennt.
    """
    assert SCRIPT.exists(), (
        f"{SCRIPT} fehlt — den Pfad in CLAUDE.md, tests/CLAUDE.md und "
        ".claude/skills/pruefen/SKILL.md nachziehen, oder das Skript zurücklegen"
    )


def ask(question: str, log: str, tmp_path: Path) -> bool:
    """Ruft eine Entscheidungsfunktion des Skripts gegen ein gefälschtes Protokoll.

    ``question`` ist ein vollständiger Aufruf mit ``$P`` als Platzhalter für
    den Protokollpfad; zurück kommt, ob die Funktion wahr gesagt hat.
    """
    protocol = tmp_path / "protokoll.txt"
    protocol.write_text(log, encoding="utf-8")
    environment = dict(os.environ)
    # Beide Variablen setzen: Ohne ``SUITE_WURZEL`` kopiert sich das Skript und
    # startet neu, ohne ``SUITE_KOPIE`` scheitert sein ``trap`` am Ende.
    environment["SUITE_WURZEL"] = str(SCRIPT.parent.parent.parent.parent)
    environment["SUITE_KOPIE"] = str(tmp_path / "kopie.sh")
    environment["SUITE_NUR_FUNKTIONEN"] = "1"
    call = question.replace("$P", str(protocol).replace("\\", "/"))
    result = subprocess.run(
        [BASH or "bash", "-c", f'source "{str(SCRIPT).replace(chr(92), "/")}"; {call}'],
        capture_output=True,
        text=True,
        env=environment,
    )
    return result.returncode == 0


def explain(question: str, log: str, tmp_path: Path) -> str:
    """Dieselbe Frage mit ``set -x`` — die Spur, welche Zeile des Skripts entschied.

    **Eine Sonde, keine Zusicherung.** ``test_native_crash_text_is_not_mistaken_
    for_failed_test_markers`` war am 02.09.2026 lokal grün (Windows, Git Bash)
    und in der Linux-CI rot, mit denselben Werkzeugen (GNU sed 4.9, GNU grep,
    LF im Skript) — und ``ask`` sagt nur wahr oder falsch. Wer den Fehler
    sehen will, braucht die Ausgabe von ``fortschritt`` und den Weg durch
    ``nicht_gelaufen`` auf genau der Maschine, auf der es rot ist.
    """
    protocol = tmp_path / "protokoll.txt"
    protocol.write_text(log, encoding="utf-8")
    environment = dict(os.environ)
    environment["SUITE_WURZEL"] = str(SCRIPT.parent.parent.parent.parent)
    environment["SUITE_KOPIE"] = str(tmp_path / "kopie.sh")
    environment["SUITE_NUR_FUNKTIONEN"] = "1"
    call = question.replace("$P", str(protocol).replace("\\", "/"))
    script = str(SCRIPT).replace(chr(92), "/")
    result = subprocess.run(
        [
            BASH or "bash",
            "-c",
            f'source "{script}"; '
            f'echo "--- fortschritt:"; fortschritt "{protocol!s}" | od -c | head -5; '
            f'echo "--- Protokoll:"; od -c "{protocol!s}" | head -8; '
            'echo "--- Werkzeuge:"; sed --version | head -1; grep --version | head -1; '
            "bash --version | head -1; "
            f"echo '--- Spur:'; set -x; {call}",
        ],
        capture_output=True,
        text=True,
        env=environment,
    )
    return f"rc={result.returncode}\n{result.stdout}\n{result.stderr}"


def test_a_run_that_swallowed_tests_is_told_apart_from_a_red_one(tmp_path: Path) -> None:
    """Nur ein Riss lässt sich durch Teilen heilen — ein roter Test nicht.

    Die Unterscheidung ist der ganze Zweck von ``nicht_gelaufen``. Ohne sie
    teilte das Skript eine Portion mit einem echten Fehlschlag bis zur
    Mindestgröße hinunter und gewänne dabei nichts als Laufzeit.
    """
    full = "." * 20 + "\n20 passed in 3.00s\n"
    torn = "." * 12 + "\n"
    red = "." * 8 + "F" + "." * 11 + "\n1 failed, 19 passed in 3.00s\n"
    teardown = "." * 20 + "\n"

    assert not ask('nicht_gelaufen 0 "$P" 20', full, tmp_path), "ein sauberer Lauf riss nicht"
    assert ask('nicht_gelaufen 139 "$P" 20', torn, tmp_path), (
        "zwölf von zwanzig Zeichen: der Lauf hat acht Tests verschluckt"
    )
    assert not ask('nicht_gelaufen 1 "$P" 20', red, tmp_path), (
        "ein roter Test ist kein Riss — Teilen macht ihn nicht grün"
    )
    assert not ask('nicht_gelaufen 127 "$P" 20', teardown, tmp_path), (
        "alle zwanzig Zeichen da: der Riss kam beim Abbau, jeder Test lief"
    )
    assert not ask('nicht_gelaufen 139 "$P" ""', torn, tmp_path), (
        "ohne bekannte Soll-Größe darf niemand behaupten, es fehle etwas"
    )

    # **Der Fall, den allein die Schlusszeile entscheidet.** Die Fälle darüber
    # tragen ihr Urteil doppelt — ein rotes Zeichen *und* eine Fehlerzeile —,
    # und eine Gegenprobe zeigte, dass die Zeilenprüfung dadurch ungeprüft
    # blieb: Nimmt man sie heraus, wird nichts rot. Ein Abbruch beim Sammeln
    # schreibt genau das: wenige Punkte, kein einziges ``E``, und „1 error".
    # Teilen hilft dort nicht, also ist es kein Riss.
    collect_error = "." * 12 + "\n1 error in 3.00s\n"
    assert not ask('nicht_gelaufen 139 "$P" 20', collect_error, tmp_path), (
        "eine Fehlerzeile ist kein Riss, auch ohne rotes Zeichen im Fortschritt"
    )


def test_a_teardown_crash_stays_green_and_a_swallowed_run_does_not(tmp_path: Path) -> None:
    """Die zweite Entscheidung: Was zählt am Ende als Fehllauf?

    Beide Fälle enden mit einem Absturz und ohne Schlusszeile. Sie
    unterscheidet nichts als die **Anzahl** der Fortschrittszeichen — und
    genau darin lag der Unterschied zwischen „alles gelaufen, Riss beim
    Aufräumen" und „ein Drittel gelaufen, Rest unbekannt".
    """
    teardown = "." * 60 + "\n"
    torn = "." * 33 + "\n"

    assert not ask('zaehlt_als_fehler 127 "$P" 60', teardown, tmp_path), (
        "sechzig von sechzig gelaufen — das ist kein Fehllauf"
    )
    assert ask('zaehlt_als_fehler 139 "$P" 60', torn, tmp_path), (
        "dreiunddreißig von sechzig: siebenundzwanzig Tests sind nie gelaufen"
    )
    assert ask('zaehlt_als_fehler 139 "$P" ""', teardown, tmp_path), (
        "ohne Soll-Größe bleibt es bei der strengen Bewertung"
    )


def test_native_crash_text_is_not_mistaken_for_failed_test_markers(tmp_path: Path) -> None:
    """Die Wörter des Absturzberichts sind keine pytest-Fortschrittszeichen."""
    torn = (
        "." * 10
        + "Fatal Python error: Aborted\n"
        + "Extension modules: numpy._core, PySide6.QtCore\n"
    )

    assert ask('nicht_gelaufen 3 "$P" 26', torn, tmp_path), (
        "zehn von sechsundzwanzig Tests liefen — die Portion muss geteilt werden\n"
        + explain('nicht_gelaufen 3 "$P" 26', torn, tmp_path)
    )
    assert ask('zaehlt_als_fehler 3 "$P" 26', torn, tmp_path), (
        "vor der erfolgreichen Teilung bleibt der verschluckte Lauf rot"
    )


def test_a_portion_that_swallows_tests_is_halved_until_it_runs(tmp_path: Path) -> None:
    """Die Portionsgröße pflegt sich selbst — das ist der ganze Punkt von G18.

    Gemessen am 31.08.2026: ``test_ui.py`` kommt mit sechzig durch,
    ``test_print_settings_ui.py`` riss schon bei vierzig, und zwar an keinem
    einzelnen Test — dreiundzwanzig rissen, vierundzwanzig nicht,
    vierunddreißig liefen, vierzig rissen wieder. Eine gepflegte Zahl je Datei
    wäre am Tag ihres Eintrags schon falsch.

    Geprüft wird mit einem **gefälschten pytest**, das über einer Grenze reißt
    und darunter durchläuft. Nur so lässt sich zeigen, dass das Skript kleiner
    wird, statt eine Konstante zu brauchen: Ein echter Lauf wäre langsam, von
    der Maschine abhängig und würde genau die Eigenschaft nicht beweisen.
    """
    fake = tmp_path / "fakepytest.py"
    fake.write_text(
        # Zählt die Testnamen im Aufruf. Über der Grenze schreibt es so viele
        # Punkte, wie es *geschafft* hätte, und stirbt; darunter läuft es durch
        # und schreibt die Schlusszeile.
        "import sys\n"
        "names = [a for a in sys.argv if '::' in a]\n"
        "limit = int(__import__('os').environ.get('FAKE_LIMIT', '8'))\n"
        "if not names:\n"
        "    print('1 passed in 0.01s')\n"
        "    sys.exit(0)\n"
        "if len(names) > limit:\n"
        "    print('.' * (len(names) // 3))\n"
        "    sys.exit(139)\n"
        "print('.' * len(names))\n"
        "print(f'{len(names)} passed in 0.01s')\n",
        encoding="utf-8",
    )
    listing = tmp_path / "list_windowed_tests.py"
    listing.write_text("print('tests/test_fake.py')\n", encoding="utf-8")

    # Ein Stub für ``--collect-only``: zwanzig Namen, die das Skript in
    # Portionen schneidet.
    collect = tmp_path / "collect.py"
    collect.write_text(
        "import sys\n"
        # Der Wrapper bekommt **jeden** Aufruf des Skripts, auch den nach der
        # Dateiliste. Ohne diesen Zweig las das Skript die Schlusszeile des
        # Stubs als Dateinamen und fuhr „1", „passed" und „in" als Testdateien.
        "if any('list_windowed_tests' in a for a in sys.argv):\n"
        "    print('tests/test_fake.py')\n"
        "    sys.exit(0)\n"
        "if '--collect-only' in sys.argv:\n"
        "    for i in range(20):\n"
        "        print(f'tests/test_fake.py::test_{i}')\n"
        "    sys.exit(0)\n"
        f"exec(open(r'{fake}').read())\n",
        encoding="utf-8",
    )

    # ``SUITE_PYTHON`` erwartet ein Programm, das wie ``python.exe`` gerufen
    # wird (``"$PY" -m pytest …``). Ein Wrapper schiebt die Argumente an den
    # Stub weiter; ``-m pytest`` interessiert ihn nicht, er sucht Testnamen.
    wrapper = tmp_path / "fakepy.sh"
    interpreter = Path(__import__("sys").executable).as_posix()
    wrapper.write_text(
        f'#!/usr/bin/env bash\nexec "{interpreter}" "{collect.as_posix()}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    wrapper.chmod(0o755)

    environment = dict(os.environ)
    environment["SUITE_WURZEL"] = str(tmp_path)
    environment["SUITE_KOPIE"] = str(tmp_path / "kopie.sh")
    environment["SUITE_PORTION"] = "10"
    environment["SUITE_MIN_PORTION"] = "2"
    environment["FAKE_LIMIT"] = "4"
    environment["SUITE_PYTHON"] = str(wrapper)

    (tmp_path / "tools").mkdir(exist_ok=True)
    shutil.copy(listing, tmp_path / "tools" / "list_windowed_tests.py")
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_fake.py").write_text("", encoding="utf-8")

    result = subprocess.run(
        [BASH or "bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        # **Kodierung ausdrücklich**, sonst liest Python die Ausgabe in der
        # Systemkodierung: Aus „Läufe" wurde „L�ufe", und der Vergleich
        # scheiterte an einem Wort, das im Protokoll richtig dastand.
        encoding="utf-8",
        errors="replace",
        env=environment,
        cwd=tmp_path,
    )
    output = result.stdout + result.stderr

    assert "geteilt in" in output, (
        "das Skript hat nicht geteilt, obwohl der Lauf Tests verschluckte:\n" + output[-2000:]
    )
    # Zwanzig Tests, Portionen zu zehn, und das gefälschte pytest reißt über
    # vier: Zehn reißen, fünf reißen, zwei und drei laufen. Also mehrere
    # Teilungen je Portion — und am Ende kein Fehllauf, ohne dass jemand eine
    # Zahl gepflegt hätte.
    assert output.count("geteilt in") >= 2, f"nur einmal geteilt:\n{output[-2000:]}"
    assert "Läufe mit Fehler: 0" in output, (
        "nach dem Verkleinern lief alles durch, das Skript meldet trotzdem einen Fehler:\n"
        + output[-2000:]
    )


def test_a_portion_that_never_runs_stops_at_the_floor(tmp_path: Path) -> None:
    """Wer immer reißt, wird gemeldet — nicht endlos geteilt.

    Die Mindestgröße ist kein Feinschliff, sondern der Schutz gegen eine
    Schleife, die nie endet: Ohne sie teilte das Skript weiter, bis eine
    „Portion" keinen einzigen Test mehr enthält, und legte sich selbst
    schlafen. Eine Gegenprobe hat gezeigt, dass genau dieser Zweig ungeprüft
    war — der Fall darüber wird grün, bevor er den Boden erreicht.

    Geprüft wird mit einem pytest, das **jede** Portion reißen lässt. Das
    Skript muss dann aufhören und einen Fehllauf melden, statt weiterzuteilen.
    """
    fake = tmp_path / "fakepytest.py"
    fake.write_text(
        "import sys\n"
        "names = [a for a in sys.argv if '::' in a]\n"
        "if any('list_windowed_tests' in a for a in sys.argv):\n"
        "    print('tests/test_fake.py')\n"
        "    sys.exit(0)\n"
        "if '--collect-only' in sys.argv:\n"
        "    for i in range(8):\n"
        "        print(f'tests/test_fake.py::test_{i}')\n"
        "    sys.exit(0)\n"
        "if not names:\n"
        "    print('1 passed in 0.01s')\n"
        "    sys.exit(0)\n"
        # Reißt immer, und zwar nach der Hälfte — ein Riss, den kein Teilen
        # heilt, weil er nicht an der Menge liegt.
        "print('.' * (len(names) // 2))\n"
        "sys.exit(139)\n",
        encoding="utf-8",
    )
    wrapper = tmp_path / "fakepy.sh"
    interpreter = Path(__import__("sys").executable).as_posix()
    wrapper.write_text(
        f'#!/usr/bin/env bash\nexec "{interpreter}" "{fake.as_posix()}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    wrapper.chmod(0o755)

    environment = dict(os.environ)
    environment["SUITE_WURZEL"] = str(tmp_path)
    environment["SUITE_KOPIE"] = str(tmp_path / "kopie.sh")
    environment["SUITE_PORTION"] = "4"
    environment["SUITE_MIN_PORTION"] = "2"
    environment["SUITE_PYTHON"] = str(wrapper)

    (tmp_path / "tools").mkdir(exist_ok=True)
    (tmp_path / "tools" / "list_windowed_tests.py").write_text("", encoding="utf-8")
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_fake.py").write_text("", encoding="utf-8")

    result = subprocess.run(
        [BASH or "bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        cwd=tmp_path,
        timeout=120,
    )
    output = result.stdout + result.stderr

    assert "Läufe mit Fehler: 0" not in output, (
        "ein Lauf, der nie durchkam, wurde als grün gemeldet:\n" + output[-1500:]
    )
    # Und nicht endlos: Bei acht Tests, Portionen zu vier und einem Boden von
    # zwei sind höchstens zwei Teilungen je Portion möglich.
    assert output.count("geteilt in") <= 4, (
        f"das Skript teilte {output.count('geteilt in')} Mal — der Boden greift nicht"
    )
