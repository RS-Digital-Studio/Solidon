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
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / ".claude" / "scripts" / "suite-getrennt.sh"

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
    environment["SUITE_WURZEL"] = str(SCRIPT.parent.parent.parent)
    environment["SUITE_KOPIE"] = str(tmp_path / "kopie.sh")
    environment["SUITE_NUR_FUNKTIONEN"] = "1"
    # Der Interpreter, der diesen Test fährt — sonst sucht das Skript die
    # venv unter dem Windows-Namen und findet auf Linux keine.
    environment["SUITE_PYTHON"] = sys.executable
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
    environment["SUITE_WURZEL"] = str(SCRIPT.parent.parent.parent)
    environment["SUITE_KOPIE"] = str(tmp_path / "kopie.sh")
    environment["SUITE_NUR_FUNKTIONEN"] = "1"
    # Der Interpreter, der diesen Test fährt — sonst sucht das Skript die
    # venv unter dem Windows-Namen und findet auf Linux keine.
    environment["SUITE_PYTHON"] = sys.executable
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


def test_native_crashes_stay_red_even_after_all_tests_passed(tmp_path: Path) -> None:
    """Erfolgreiche Zusicherungen ersetzen keinen sauber beendeten Prozess."""
    teardown = "." * 60 + "\n"
    torn = "." * 33 + "\n"
    assert ask('zaehlt_als_fehler 127 "$P" 60', teardown, tmp_path)
    assert ask('zaehlt_als_fehler 139 "$P" 60', torn, tmp_path)
    assert ask('zaehlt_als_fehler 139 "$P" ""', teardown, tmp_path)

    # Ein Shell-Aufruf prüft alle Statuswerte, auch den ursprünglichen
    # Windows-Code; die Entscheidung darf von der Ausgabe nicht abhängen.
    decision = (
        "for code in 1 3 5 127 134 139 3221226505; do "
        'zaehlt_als_fehler "$code" "$P" 60 || exit 1; done; '
        '! zaehlt_als_fehler 0 "$P" 60'
    )
    assert ask(decision, teardown + "60 passed in 0.01s\n", tmp_path)


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


def fake_suite(
    tmp_path: Path,
    *,
    queue_only: bool = False,
    release: bool = False,
    arguments: tuple[str, ...] = (),
    **options: str,
) -> subprocess.CompletedProcess[str]:
    """Die echte Torsteuerung mit einem schnellen Interpreter-Doppel ausführen.

    Das Doppel beantwortet Importprobe, Fixture-Sammlung und pytest-Aufrufe,
    ohne weitere Python-Interpreter, Qt oder reale Tests zu starten.
    """
    wrapper = tmp_path / "fakepython.sh"
    wrapper.write_text(
        """#!/usr/bin/env bash
printf '%s\n' "$*" >> "$SUITE_WURZEL/calls.txt"
printf 'BLAS=%s\n' "${OPENBLAS_NUM_THREADS:-ungesetzt}" >> "$SUITE_WURZEL/umgebung.txt"
case "$*" in
  *list_windowed_tests.py*)
    printf '%s\n' 'tests/test_fake.py'
    exit "${FAKE_LIST_EXIT:-0}" ;;
  *--collect-only*)
    for ((i=0; i<${FAKE_COUNT:-6}; i++)); do
      printf 'tests/test_fake.py::test_%s\n' "$i"
    done
    exit "${FAKE_COLLECT_EXIT:-0}" ;;
esac
[ "${1:-}" = "-c" ] && [ "${FAKE_IMPORT_TERM:-0}" -eq 1 ] && kill -TERM "$PPID"
[ "${1:-}" = "-c" ] && exit "${FAKE_IMPORT_EXIT:-0}"
count=0
for argument in "$@"; do
  case "$argument" in *::*) count=$((count + 1));; esac
done
if [ "$count" -eq 0 ]; then
  if [ "${FAKE_EMPTY_CORE:-0}" -eq 1 ]; then
    printf 'no tests ran in 0.01s\n'
    exit 5
  fi
  printf '1 passed in 0.01s\n'
  exit 0
fi
if [ "$count" -gt "${FAKE_LIMIT:-2}" ]; then
  for ((i=0; i<count/3; i++)); do printf '.'; done
  printf '\n'
  exit 139
fi
for ((i=0; i<count; i++)); do printf '.'; done
printf '\n%s passed in 0.01s\n' "$count"
""",
        encoding="utf-8",
        newline="\n",
    )
    wrapper.chmod(0o755)
    environment = dict(os.environ)
    environment.update(
        SUITE_WURZEL=tmp_path.as_posix(),
        SUITE_KOPIE=(tmp_path / "kopie.sh").as_posix(),
        SUITE_PORTION="60",
        SUITE_MIN_PORTION="2",
        SUITE_PYTHON=wrapper.as_posix(),
    )
    environment.update(options)
    script = SCRIPT
    if queue_only:
        # Hier ist ausschließlich die echte Warteschlange der Prüfling.
        # Sammlung und Diagnoseklassifikation haben eigene Gegenproben oben
        # und unten. Der Stub liefert ausschließlich native Abbrüche ohne F/E.
        _before, separator, queue = SCRIPT.read_text(encoding="utf-8").partition(
            "\nfor file in $windowed; do\n"
        )
        assert separator, "die echte Warteschlange fehlt"
        script = tmp_path / "queue.sh"
        script.write_text(
            f'SUITE_NUR_FUNKTIONEN=1\nsource "{SCRIPT.as_posix()}"\n'
            'windowed="tests/test_fake.py"\nPORTION=60\nMINDEST=2\n'
            'sammelgruppe="1 passed in 0.01s"\n'
            f'protokoll="{(tmp_path / "queue.log").as_posix()}"\n'
            "PY=fake_python\n"
            # Der Stub beendet nur seinen Kindprozess, nicht die Torsteuerung.
            f'fake_python() ( source "{wrapper.as_posix()}" "$@"; )\n'
            "namen_von() { for ((i=0; i<${FAKE_COUNT:-6}; i++)); do "
            'printf "tests/test_fake.py::test_%s\\n" "$i"; done; }\n'
            'nicht_gelaufen() { [ "$1" -ne 0 ]; }\n' + separator + queue,
            encoding="utf-8",
            newline="\n",
        )
    return subprocess.run(
        [BASH or "bash", str(script), *(["--release"] if release else []), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        cwd=tmp_path,
        timeout=60,
    )


@pytest.mark.parametrize(
    ("options", "arguments", "copy_fails", "expected_exit"),
    [
        ({}, (), False, 0),
        ({"FAKE_EMPTY_CORE": "1"}, (), False, 1),
        ({}, ("--unbekannt",), False, 2),
        ({"SUITE_PYTHON": "does-not-exist/python"}, (), False, 2),
        ({"FAKE_IMPORT_EXIT": "1"}, (), False, 4),
        ({"FAKE_IMPORT_TERM": "1"}, (), False, None),
        ({}, (), True, 1),
    ],
    ids=[
        "erfolg",
        "kerngruppe-leer",
        "aufruffehler",
        "interpreter-fehlt",
        "importfehler",
        "import-abgebrochen",
        "kopierfehler",
    ],
)
def test_the_real_self_copy_and_own_logs_are_removed_on_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    options: dict[str, str],
    arguments: tuple[str, ...],
    copy_fails: bool,
    expected_exit: int | None,
) -> None:
    """Auch der Neustart auf der eigenen Skriptkopie muss seine Dateien räumen."""
    script = tmp_path / ".claude" / "scripts" / "suite-getrennt.sh"
    script.parent.mkdir(parents=True)
    shutil.copyfile(SCRIPT, script)
    monkeypatch.setattr(sys.modules[__name__], "SCRIPT", script)
    temporary = tmp_path / "temporäre Dateien"
    temporary.mkdir()
    unrelated = temporary / "fremdes Protokoll.txt"
    unrelated.write_text("bewahren", encoding="utf-8")
    if copy_fails:
        bash_env = tmp_path / "bash-env.sh"
        bash_env.write_text("cp() { return 1; }\n", encoding="utf-8", newline="\n")
        options = {"BASH_ENV": bash_env.as_posix(), **options}

    result = fake_suite(
        tmp_path,
        arguments=arguments,
        SUITE_WURZEL="",
        TMPDIR=temporary.as_posix(),
        **options,
    )

    if expected_exit is None:
        # Git Bash und POSIX melden Signale mit unterschiedlichen Statuswerten.
        assert result.returncode != 0, result.stdout + result.stderr
    else:
        assert result.returncode == expected_exit, result.stdout + result.stderr
    assert list(temporary.iterdir()) == [unrelated]
    assert unrelated.read_text(encoding="utf-8") == "bewahren"
    assert script.is_file(), "das Original gehört nicht zur temporären Kopie"


def test_sourced_helpers_preserve_the_callers_protocol(tmp_path: Path) -> None:
    """Ein von außen ausgewertetes Protokoll gehört nicht dem Torlauf."""
    log = "1 passed in 0.01s\n"
    assert ask('zusammenfassung "$P"', log, tmp_path)
    assert (tmp_path / "protokoll.txt").read_text(encoding="utf-8") == log


def test_a_portion_that_swallows_tests_is_halved_until_it_runs(tmp_path: Path) -> None:
    """Die Diagnose erreicht jeden Test, frühere Prozessabbrüche bleiben rot."""
    result = fake_suite(tmp_path, queue_only=True)
    output = result.stdout + result.stderr
    # Sechs reißen, beide Dreier ebenfalls; Eins und Zwei laufen durch.
    assert output.count("geteilt in") == 3, output
    assert output.count("1 passed in 0.01s") == 3, output
    assert output.count("2 passed in 0.01s") == 2, output
    assert "Läufe mit Fehler: 3" in output, output
    assert result.returncode == 1, output


def test_a_portion_that_never_runs_stops_at_the_floor(tmp_path: Path) -> None:
    """Die vorhandene Mindestgröße beendet erfolglose Diagnoseversuche."""
    result = fake_suite(tmp_path, queue_only=True, FAKE_COUNT="4", FAKE_LIMIT="0")
    output = result.stdout + result.stderr
    assert output.count("geteilt in") == 1, output
    assert "Läufe mit Fehler: 3" in output, output
    assert result.returncode == 1, output


@pytest.mark.parametrize("release", [False, True])
def test_a_clean_stub_suite_has_a_successful_process_exit(tmp_path: Path, release: bool) -> None:
    """Alle erfolgreichen Teilprozesse ergeben auch einen erfolgreichen Torprozess."""
    result = fake_suite(tmp_path, release=release, FAKE_LIMIT="6")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Läufe mit Fehler: 0" in result.stdout
    calls = (tmp_path / "calls.txt").read_text(encoding="utf-8")
    # Je Test getrennt: keine Datei fällt aus dem regulären Tor, und die
    # Releaseprozesse fahren nur Fenster- und Rendererfälle ihrer Datei.
    assert "--ignore" not in calls
    # Erzeugnisvergleiche (``rendered``) nur beim Release — zwischen zwei
    # Paketbauten sind sie erwartbar rot (23.09.2026).
    if release:
        assert "-m not performance and not windowed and not rendering -n" in calls
    else:
        assert "-m not performance and not windowed and not rendering and not rendered -n" in calls
    assert ("list_windowed_tests.py" in calls) is release
    assert ("--collect-only -q -m (windowed or rendering) and not performance" in calls) is release
    assert ("tests/test_fake.py::test_0" in calls) is release


@pytest.mark.parametrize(("given", "expected"), [(None, "1"), ("6", "6")], ids=["frei", "gesetzt"])
def test_every_gate_process_gets_one_blas_thread_unless_the_caller_chose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: str | None, expected: str
) -> None:
    """OpenBLAS sagt je Rechenkern einen Puffer zu — jeder Torprozess bekommt einen Faden.

    Gemessen an 32 Kernen: 1,6 GB privater Speicher je Prozess nach numpy,
    scipy, trimesh und manifold3d, mit einem Faden 0,1 GB; acht Arbeiter und
    die Kindprozesse der Tests zahlen das einzeln. Ein Wert des Aufrufers
    bleibt. Geprüft über Importprobe, Sammlung und alle Läufe des Release-Tors.
    """
    if given is None:
        monkeypatch.delenv("OPENBLAS_NUM_THREADS", raising=False)
    else:
        monkeypatch.setenv("OPENBLAS_NUM_THREADS", given)

    result = fake_suite(tmp_path, release=True, FAKE_LIMIT="6")

    assert result.returncode == 0, result.stdout + result.stderr
    seen = (tmp_path / "umgebung.txt").read_text(encoding="utf-8").splitlines()
    assert len(seen) >= 4, seen
    assert set(seen) == {f"BLAS={expected}"}


def test_an_empty_core_collection_cannot_pass_the_regular_gate(tmp_path: Path) -> None:
    result = fake_suite(tmp_path, FAKE_EMPTY_CORE="1")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "NICHT-GELAUFEN" in result.stdout


def test_a_failed_windowed_collection_does_not_run_the_core_group(tmp_path: Path) -> None:
    """Auch eine teilweise ausgegebene Fensterliste darf den Fehler nicht verdecken."""
    result = fake_suite(tmp_path, release=True, FAKE_LIST_EXIT="3")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Exit 3" in result.stderr
    assert "in einem Zug" not in result.stdout


def test_a_failed_node_collection_is_not_run_as_a_partial_list(tmp_path: Path) -> None:
    """Ein Sammelfehler mit einigen gültigen Namen bleibt ein Befund."""
    result = fake_suite(tmp_path, release=True, FAKE_COLLECT_EXIT="2")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Sammlung,Exit:2" in result.stdout
    assert "--> Teil" not in result.stdout


@pytest.mark.parametrize("interpreter", ["", "does-not-exist/python"])
def test_an_explicit_invalid_interpreter_never_uses_a_fallback(
    tmp_path: Path, interpreter: str
) -> None:
    """Eine vorhandene alte Umgebung darf die ausdrücklich gewählte nicht ersetzen."""
    fallback = tmp_path / ".venv" / "bin" / "python"
    fallback.parent.mkdir(parents=True)
    marker = tmp_path / "fallback-used"
    fallback.write_text(
        f'#!/usr/bin/env bash\nprintf used > "{marker.as_posix()}"\nexit 0\n',
        encoding="utf-8",
        newline="\n",
    )
    fallback.chmod(0o755)
    result = fake_suite(tmp_path, SUITE_PYTHON=interpreter)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "SUITE_PYTHON ist nicht ausführbar" in result.stderr
    assert not marker.exists(), "der ungültige Wunsch wurde still ersetzt"


@pytest.mark.parametrize("failures", [0, 1, 256, 257])
def test_the_final_exit_does_not_wrap_after_256_failures(tmp_path: Path, failures: int) -> None:
    """Der tatsächliche Schlussblock muss einen booleschen Prozessstatus liefern."""
    _prefix, separator, ending = SCRIPT.read_text(encoding="utf-8").partition(
        '\necho "======================================"\n'
    )
    assert separator, "der echte Abschlussblock fehlt"
    probe = tmp_path / "abschluss.sh"
    probe.write_text(
        f'fails={failures}\nschlecht="probe"\nsammelgruppe="1 passed"\n' + ending,
        encoding="utf-8",
        newline="\n",
    )
    result = subprocess.run([BASH or "bash", str(probe)], capture_output=True, text=True, timeout=5)
    assert result.returncode == (0 if failures == 0 else 1)
