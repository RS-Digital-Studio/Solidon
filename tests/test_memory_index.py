"""Der Erinnerungs-Index verträgt zwei Sitzungen, die gleichzeitig schreiben.

`.claude/memory/MEMORY.md` ist eine geteilte Datei, und an diesem Projekt
arbeiten mehrere Sitzungen zugleich. Lesen, anhängen, schreiben verliert dabei
still einen Eintrag — und eine fehlende Erinnerung meldet sich nicht.
`tools/memory_index.py` legt deshalb eine Sperre daneben, liest **unter** ihr
und zählt vor dem Schreiben nach.

Der tragende Fall ist der letzte: zwei echte Prozesse, kein nachgestelltes
Wettrennen im selben Interpreter.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools import memory_index

REPOSITORY = Path(__file__).resolve().parent.parent

BEISPIEL = """# Memory — Probe

Ein Vorspann.

## Diese Maschine

- [Erster](erster.md) — etwas.
- [Zweiter](zweiter.md) — etwas anderes.

## Roberts Vorgaben

- [Dritter](dritter.md) — noch etwas.
"""


def _index(tmp_path: Path, inhalt: str = BEISPIEL) -> Path:
    datei = tmp_path / "MEMORY.md"
    datei.write_text(inhalt, encoding="utf-8", newline="")
    return datei


def test_a_line_lands_at_the_end_of_its_section(tmp_path: Path) -> None:
    """Ans Ende des Abschnitts, nicht an seinen Anfang.

    Der Index wächst chronologisch; wer oben einfügt, schiebt bei jedem
    Eintrag den ganzen Abschnitt durch den Diff.
    """
    datei = _index(tmp_path)

    memory_index.insert(datei, "- [Neuer](neuer.md) — dazugekommen.", section="Diese Maschine")

    zeilen = datei.read_text(encoding="utf-8").split("\n")
    assert zeilen[zeilen.index("- [Zweiter](zweiter.md) — etwas anderes.") + 1] == (
        "- [Neuer](neuer.md) — dazugekommen."
    )
    assert "## Roberts Vorgaben" in zeilen


def test_the_rest_of_the_file_stays_byte_for_byte(tmp_path: Path) -> None:
    """Genau eine Zeile dazu — jede andere unverändert."""
    datei = _index(tmp_path)
    vorher = datei.read_text(encoding="utf-8").split("\n")

    memory_index.insert(datei, "- [Neuer](neuer.md) — dazu.", section="Roberts Vorgaben")

    nachher = datei.read_text(encoding="utf-8").split("\n")
    assert len(nachher) == len(vorher) + 1
    nachher.remove("- [Neuer](neuer.md) — dazu.")
    assert nachher == vorher


@pytest.mark.parametrize("missing_parent", [False, True])
def test_an_unreadable_index_is_reported_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], missing_parent: bool
) -> None:
    """Der CLI-Aufruf nennt den unlesbaren Index und einen nächsten Schritt."""
    folder = tmp_path / "fehlt" if missing_parent else tmp_path
    path = folder / "MEMORY.md"
    assert memory_index.main(["--index", str(path), "--line", "- [Probe](probe.md)"]) == 1
    error = capsys.readouterr().err
    assert str(path) in error and "Prüfen Sie" in error
    assert "Traceback" not in error
    assert not path.exists()


def test_a_failed_replace_keeps_the_index_and_reports_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ein Schreibfehler bewahrt die alte Datei und entfernt die temporäre Ausgabe."""
    path = _index(tmp_path)

    def refuse(source: Path, target: Path) -> None:
        raise PermissionError("Datei gesperrt")

    monkeypatch.setattr(Path, "replace", refuse)
    assert memory_index.main(["--index", str(path), "--line", "- [Probe](probe.md)"]) == 1
    assert str(path) in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == BEISPIEL
    assert not list(tmp_path.glob(".memory-index-*"))


def test_a_line_without_a_pointer_is_refused(tmp_path: Path) -> None:
    """Ohne ``[Titel](datei.md)`` findet ``test_directory_docs`` den Eintrag nicht.

    Eine Zeile, die der Wächter nicht als Zeiger liest, ist schlimmer als
    keine: Die Notiz gilt dann als nicht verzeichnet, und der Lauf wird rot an
    einer Stelle, die mit dem Einfügen nichts zu tun zu haben scheint.
    """
    datei = _index(tmp_path)

    with pytest.raises(memory_index.IndexWriteError):
        memory_index.insert(datei, "- Einfach nur Text.", section="Diese Maschine")

    assert datei.read_text(encoding="utf-8") == BEISPIEL


def test_a_line_with_a_break_inside_is_refused(tmp_path: Path) -> None:
    """Eine Zeile mit Umbruch wären zwei Zeilen, und die Nachzählung sähe es nicht.

    Sie zählt Listenelemente; zusammengefügt wird danach über den Umbruch. Ein
    Wagenrücklauf wäre schlimmer: Er erzeugte ein CRLF, und der nächste Lauf
    weigert sich, den Index überhaupt noch anzufassen — das Werkzeug machte
    sich an der Datei unbrauchbar, die es schützen soll. Aus dem Review vom
    10.09.2026.
    """
    datei = _index(tmp_path)

    for kaputt in (
        "- [a](a.md) — eins" + "\n" + "- [b](b.md) — zwei",
        "- [a](a.md) — eins" + "\r",
    ):
        with pytest.raises(memory_index.IndexWriteError):
            memory_index.insert(datei, kaputt, section="Diese Maschine")

    assert datei.read_text(encoding="utf-8") == BEISPIEL


def test_a_section_that_appears_twice_is_refused(tmp_path: Path) -> None:
    """Bei zwei gleichnamigen Abschnitten wird nicht geraten (Regel 21).

    ``lines.index`` nähme still den ersten, und ``check_only_one_line_appeared``
    fängt das nicht: Eine Zeile im falschen Abschnitt ist auch „genau eine
    dazu". Ein doppelter Titel ist bei drei Maschinen ein realistisches
    Merge-Artefakt.
    """
    doppelt = BEISPIEL + ("\n## Diese Maschine\n\n- [Vierter](vierter.md) — nochmal.\n")
    datei = _index(tmp_path, doppelt)

    with pytest.raises(memory_index.IndexWriteError):
        memory_index.insert(datei, "- [Neuer](neuer.md) — dazu.", section="Diese Maschine")

    assert datei.read_text(encoding="utf-8") == doppelt


def test_an_unknown_section_is_refused(tmp_path: Path) -> None:
    """Lieber gar nicht einfügen als an der falschen Stelle (Regel 21)."""
    datei = _index(tmp_path)

    with pytest.raises(memory_index.IndexWriteError):
        memory_index.insert(datei, "- [Neuer](neuer.md) — dazu.", section="Gibt es nicht")

    assert datei.read_text(encoding="utf-8") == BEISPIEL


def test_the_count_catches_a_placement_that_lost_a_line() -> None:
    """Die Kontrolle fängt einen Fehler **dieses** Werkzeugs, nicht der anderen Sitzung.

    Die Sperre schützt vor der zweiten Sitzung. Was sie nicht fängt, ist ein
    Muster, das zu viel trifft, oder ein Ausrutscher beim Zusammensetzen — und
    genau danach sieht diese Prüfung.
    """
    vorher = ["a", "b", "c"]

    with pytest.raises(memory_index.IndexWriteError):
        memory_index.check_only_one_line_appeared(vorher, ["a", "neu", "c"], "neu")
    with pytest.raises(memory_index.IndexWriteError):
        memory_index.check_only_one_line_appeared(vorher, ["a", "b", "c", "neu", "x"], "neu")

    memory_index.check_only_one_line_appeared(vorher, ["a", "b", "neu", "c"], "neu")


def test_two_processes_writing_at_once_both_keep_their_line(tmp_path: Path) -> None:
    """Der Fall, für den das Werkzeug gebaut ist — mit zwei echten Prozessen.

    Ein nachgestelltes Wettrennen im selben Interpreter prüft die Sperre
    nicht: Sie ist eine Datei-Sperre des Betriebssystems, und ob sie hält,
    entscheidet sich zwischen **Prozessen**. Beide fügen zwanzigmal ein.

    **Gegenprobe gemessen** (10.09.2026), damit diese Zusage nicht nur so
    aussieht: Dieselben zwei Prozesse gegen eine ungeschützte **Nachbildung**
    — lesen, kurz warten, schreiben — verloren in drei Läufen 20, 17 und 20
    von 40 Einträgen. Über ``tools/memory_index.py`` fehlte in denselben drei
    Läufen keiner. Belegt ist damit, dass Lesen-Warten-Schreiben verliert;
    dass **dieser** Test rot wird, wenn man die Sperre aus **diesem** Code
    nimmt, ist damit nicht belegt — die Mutation steht aus.
    """
    datei = _index(tmp_path)
    script = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from tools import memory_index;"
        "from pathlib import Path;"
        "[memory_index.insert(Path(sys.argv[2]),"
        " f'- [{sys.argv[3]}{i}]({sys.argv[3]}{i}.md) — Probe.',"
        " section='Diese Maschine') for i in range(20)]"
    )
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(REPOSITORY), str(datei), prefix],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for prefix in ("erst", "zweit")
    ]
    try:
        for process in processes:
            _, stderr = process.communicate(timeout=60)
            assert process.returncode == 0, stderr.decode("utf-8", errors="replace")
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate()

    text = datei.read_text(encoding="utf-8")
    fehlend = [
        f"{prefix}{i}"
        for prefix in ("erst", "zweit")
        for i in range(20)
        if f"({prefix}{i}.md)" not in text
    ]
    assert not fehlend, f"verlorene Einträge: {fehlend}"
    assert text.count("- [Erster](erster.md)") == 1, "der Altbestand blieb nicht unversehrt"
