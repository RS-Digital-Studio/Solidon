"""Die Halteleine für Arbeiter-Threads (`app/ui/leash.py`).

Ein ``QThread`` hat hier keinen Qt-Elternteil; ihn hält allein die
Python-Referenz. Fällt sie weg, während der Thread noch läuft, zerstört der
Speicherbereiniger das C++-Objekt unter ihm — eine Zugriffsverletzung ohne
Zeile, irgendwann später und selten reproduzierbar. Genau deshalb hat die
Leine eigene Tests: Was sie falsch macht, fällt nicht dort auf, wo es
passiert.
"""

from __future__ import annotations

import gc
import weakref

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QThread
from PySide6.QtWidgets import QApplication

from app.ui.leash import Worker, WorkerLeash


class _Schlaefer(QThread):
    """Ein Arbeiter, der lange genug lebt, um beim Halten noch zu laufen."""

    def run(self) -> None:
        self.msleep(120)


def test_a_worker_that_is_none_goes_through_quietly(qt_app: QApplication) -> None:
    """``None`` ist kein Arbeiter, und die Leine soll daran nicht ersticken.

    Ein Slot, der sein Feld leert und den alten Inhalt an die Leine reicht,
    bekommt ``None``, wenn vor ihm schon jemand aufgeräumt hat — beim
    Aufräumen einer Sitzung passiert genau das. Ohne die Prüfung landete
    ``None`` in der Liste, und der Zeitgeber danach fragte es nach
    ``isRunning``: ein ``AttributeError`` im Teardown, weit weg von seiner
    Ursache. ``retire`` fing den Fall seit jeher ab, ``hold_until_done``
    nicht.
    """
    leine = WorkerLeash(QObject())

    leine.hold_until_done(None)
    leine.retire(None)

    assert leine.pending() == (), "None gehört nicht in die Halteliste"


def test_a_finished_worker_is_held_until_it_really_stopped(qt_app: QApplication) -> None:
    """``finished`` heißt „``run`` ist zurück", nicht „das Objekt darf weg"."""
    leine = WorkerLeash(QObject())
    arbeiter = _Schlaefer()
    arbeiter.start()

    leine.hold_until_done(arbeiter)
    assert arbeiter in leine.pending(), "der laufende Arbeiter wird nicht gehalten"

    leine.wait_all()
    assert not arbeiter.isRunning()


def test_two_workers_are_held_side_by_side(qt_app: QApplication) -> None:
    """Eine Liste, kein Feld — das ist der ganze Unterschied.

    Die Sitzung hielt je Arbeiterart genau einen, und der nächste löste ihn
    ab. Bei einer Kette geht das schief: ``_on_thread_done`` startet bei
    ``_rerun_pending`` sofort den nächsten Lauf, und wird der schnell fertig,
    überschreibt er das Feld, während Qt den Vorgänger noch abräumt.
    """
    leine = WorkerLeash(QObject())
    erster, zweiter = _Schlaefer(), _Schlaefer()
    erster.start()
    zweiter.start()

    leine.hold_until_done(erster)
    leine.hold_until_done(zweiter)

    assert set(leine.pending()) == {erster, zweiter}, "der zweite hat den ersten verdrängt"
    leine.wait_all()


# --- gehalten ab dem Start, nicht ab dem Ende -----------------------------------


def test_a_worker_is_held_from_the_moment_it_starts(qt_app: QApplication) -> None:
    """Der Absturz, den die Erstinbetriebnahme sichtbar gemacht hat.

    Gehalten wurde bisher erst, wenn ein Arbeiter fertig war; solange er lief,
    hing er allein am Feld seines Dialogs. Ein Dialog, der vorher freigegeben
    wird, nahm damit die letzte Referenz auf einen **laufenden** Thread mit —
    und der Speicherbereiniger zerstörte das C++-Objekt darunter.
    """
    import app.ui.leash as leash_module

    leine = WorkerLeash(QObject())
    arbeiter = _Schlaefer()

    leine.start(arbeiter)
    try:
        assert arbeiter in leash_module.alive(), "gehalten, während er läuft"
    finally:
        arbeiter.wait(2000)


def test_a_started_worker_is_let_go_after_it_stopped(qt_app: QApplication) -> None:
    """Und wieder losgelassen — sonst wäre die Menge ein Leck."""
    import app.ui.leash as leash_module

    leine = WorkerLeash(QObject())
    arbeiter = _Schlaefer()

    leine.start(arbeiter)
    arbeiter.wait(2000)
    for _ in range(100):
        qt_app.processEvents()
        if arbeiter not in leash_module.alive():
            break
        arbeiter.msleep(10)

    assert arbeiter not in leash_module.alive()


def test_no_worker_is_started_past_the_leash(qt_app: QApplication) -> None:
    """Was an der Leine vorbei startet, sieht ``wait_for_all`` nicht — und
    damit verspricht jede Zusicherung darüber mehr, als sie halten kann.

    Sieben Arbeiter starteten mit blankem ``worker.start()``: der Download,
    der Export, die Analysekarte, die Schichtanalyse, die Ollama-Größe, die
    Update-Abfrage und der Erzeuger im Generierungsdialog. Alle sieben hingen
    solange allein am Feld ihres Besitzers — genau die Lage, gegen die
    ``WorkerLeash.start`` geschrieben wurde —, und keiner von ihnen stand in
    ``_alive``.

    Aufgefallen ist es nicht an einem Absturz, sondern an einer Frage von
    3d-druck-33 zu ihrer Aufräum-Fixture: Sie wollte über den Rückgabewert von
    ``wait_for_all`` melden, wer einen Test überlebt hat. Eine Meldung, die
    nur die Hälfte sieht, ist schlechter als keine — sie liest sich wie eine
    Zusage.

    Geprüft wird am Quelltext und nicht am Verhalten, weil das Verhalten es
    nicht zeigt: Ein Arbeiter an der Leine vorbei läuft völlig normal, bis das
    Fenster unter ihm weggeräumt wird.
    """
    import re
    from pathlib import Path

    # Vom Testverzeichnis aus, nicht vom Arbeitsverzeichnis: ein Wächter, der
    # nur beim Aufruf aus dem Projektstamm etwas findet, ist keiner.
    verstoesse = []
    for pfad in sorted((Path(__file__).parent.parent / "app" / "ui").glob("*.py")):
        if pfad.name == "leash.py":
            continue  # dort steht der eine richtige Aufruf
        for nummer, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), 1):
            if re.fullmatch(r"\s*\w*worker\.start\(\)\s*", zeile, re.IGNORECASE):
                verstoesse.append(f"{pfad.as_posix()}:{nummer}")

    assert not verstoesse, (
        "diese Arbeiter starten an der Leine vorbei und sind damit für "
        f"wait_for_all unsichtbar: {verstoesse}"
    )


def test_waiting_for_all_catches_a_worker_without_a_window(qt_app: QApplication) -> None:
    """Der Fall, den ein Rundgang über die Fenster nicht findet.

    ``MainWindow.wait_for_workers`` erreicht die Arbeiter seines Fensters; die
    Aufräum-Fixture der Suite ruft es über ``application.topLevelWidgets()``.
    Ein Arbeiter an einem **Dialog** steht in keinem dieser Fenster — und genau
    so einer stand am 23.08.2026 in einem ``py-spy``-Abzug, während der
    Hauptthread in ``processEvents()`` auf den Import-Lock wartete, den der
    Arbeiter hielt.

    Hier hat der Besitzer nicht einmal mehr eine Referenz: Die Leine ist weg,
    und trotzdem muss der Thread erreichbar sein. Das kann nur ``_alive``,
    weil es modulweit ist.
    """
    import app.ui.leash as leash_module

    leine = WorkerLeash(QObject())
    arbeiter = _Schlaefer()
    leine.start(arbeiter)
    del leine

    assert arbeiter in leash_module.alive(), "gehalten, obwohl seine Leine weg ist"

    steht_noch = leash_module.wait_for_all(2000)

    assert not arbeiter.isRunning(), "nach dem Warten läuft er nicht mehr"
    assert arbeiter not in steht_noch, steht_noch


def test_waiting_for_all_reports_who_did_not_stop(qt_app: QApplication) -> None:
    """Und wer die Frist reißt, wird genannt statt verschwiegen.

    Eine Aufräumhilfe, die stumm weitergeht, verschiebt das Problem an die
    Stelle, an der niemand mehr weiß, woher es kommt — dieselbe Begründung,
    aus der ``crashed`` verbunden wird und nicht ins Leere läuft.
    """
    import app.ui.leash as leash_module

    leine = WorkerLeash(QObject())
    arbeiter = _Schlaefer()
    leine.start(arbeiter)

    steht_noch = leash_module.wait_for_all(1)

    if arbeiter.isRunning():
        assert arbeiter in steht_noch, "wer nach der Frist läuft, steht im Ergebnis"
    arbeiter.wait(2000)


def test_a_worker_survives_the_death_of_its_leash(qt_app: QApplication) -> None:
    """Der eigentliche Fall: Der Halter geht, der Thread läuft weiter.

    Die Menge ist modulweit und nicht an der Leine, und der Zeitgeber hängt an
    einem Objekt, das die Widgets überlebt. Ohne beides bliebe hier ein
    laufender Thread ohne Referenz zurück.
    """
    import gc

    import app.ui.leash as leash_module

    arbeiter = _Schlaefer()
    besitzer = QObject()
    WorkerLeash(besitzer).start(arbeiter)

    del besitzer
    gc.collect()

    assert arbeiter in leash_module.alive(), "die modulweite Menge hält ihn"
    arbeiter.wait(2000)
    for _ in range(100):
        qt_app.processEvents()
        if arbeiter not in leash_module.alive():
            break
        arbeiter.msleep(10)
    assert arbeiter not in leash_module.alive(), "und lässt ihn danach los"


def test_a_finished_worker_does_not_keep_its_owner_alive(qt_app: QApplication) -> None:
    """Das Fertigsignal darf keinen Ring zurück zum Fenster schließen."""
    besitzer = QObject()
    beobachter = weakref.ref(besitzer)
    leine = WorkerLeash(besitzer)
    arbeiter = _Schlaefer()

    leine.start(arbeiter)
    arbeiter.wait(2000)
    del besitzer, leine
    for _ in range(5):
        qt_app.processEvents()
    gc.collect()

    assert beobachter() is None, "der Rückruf des Arbeiters hält sein Fenster fest"


# --- ein Arbeiter, der auch mit dem Unerwarteten zurückkommt ---------------------


class _Zerbricht(Worker):
    """Ein Arbeiter, der wirft — wie es jeder kann, den niemand daran hindert."""

    def work(self) -> None:
        raise PermissionError(13, "Zugriff verweigert", "custom_nodes")


def test_an_unexpected_error_comes_back_as_a_signal(qt_app: QApplication) -> None:
    """**Der Fund, aus dem diese Basisklasse entstanden ist.**

    Ein ``run``, das eine Ausnahme durchlässt, sendet sein Ergebnissignal nie —
    und wer darauf wartet, wartet für immer. Nachgestellt am
    Einrichtungsdialog für ComfyUI: Liegt die Installation unter ``Program
    Files``, wirft das Kopieren der Knoten einen ``PermissionError``, und im
    Fenster stand „Wird eingerichtet …" mit laufendem Balken, bis jemand das
    Programm beendet.
    """
    seen: list[str] = []
    arbeiter = _Zerbricht()
    arbeiter.crashed.connect(seen.append)

    arbeiter.start()
    arbeiter.wait(2000)
    qt_app.processEvents()

    assert len(seen) == 1, "genau eine Meldung"
    assert "PermissionError" in seen[0], "die Art steht darin"
    assert "custom_nodes" in seen[0], "und was gemeint war"


def test_the_worker_ends_even_when_it_throws(qt_app: QApplication) -> None:
    """Und der Thread endet regulär — die Leine bekommt ihr ``finished``."""
    import app.ui.leash as leash_module

    arbeiter = _Zerbricht()
    WorkerLeash(QObject()).start(arbeiter)
    arbeiter.wait(2000)
    for _ in range(100):
        qt_app.processEvents()
        if arbeiter not in leash_module.alive():
            break
        arbeiter.msleep(10)

    assert not arbeiter.isRunning()
    assert arbeiter not in leash_module.alive(), "auch ein zerbrochener wird losgelassen"


def test_a_worker_without_work_says_so(qt_app: QApplication) -> None:
    """Wer erbt und ``work`` vergisst, erfährt es als Meldung statt als Stille."""
    seen: list[str] = []
    arbeiter = Worker()
    arbeiter.crashed.connect(seen.append)

    arbeiter.start()
    arbeiter.wait(2000)
    qt_app.processEvents()

    assert seen and "NotImplementedError" in seen[0]


def test_every_worker_in_the_surface_uses_the_base_class() -> None:
    """Von dreiundzwanzig Arbeitern fing genau einer eine unerwartete Ausnahme.

    Die anderen zweiundzwanzig konnten ihr Fenster in einen Wartezustand ohne
    Ausgang bringen: die Ladeanzeige der Auswertung, der gesperrte
    Export-Menüeintrag, „Der Profilbestand wird durchgesehen …". Geprüft wird
    die Regel und nicht die Zahl — wer einen neuen anlegt, erbt.
    """
    import ast
    from pathlib import Path

    strays: list[str] = []
    for path in sorted((Path(__file__).resolve().parent.parent / "app" / "ui").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {getattr(base, "id", getattr(base, "attr", "")) for base in node.bases}
            if "QThread" in bases and path.name != "leash.py":
                strays.append(f"{path.name}:{node.name}")

    assert not strays, "erbt von QThread statt von leash.Worker: " + ", ".join(strays)


def test_every_worker_has_somebody_listening_for_its_crash() -> None:
    """Ein Signal, das niemand hört, ist keine Antwort.

    Die Basisklasse allein verschiebt den Fund nur: Sie fängt die Ausnahme und
    protokolliert sie, aber der Wartezustand löst sich erst, wenn jemand
    ``crashed`` verbindet.

    **Je Startstelle, nicht je Datei.** Die Dateiprüfung war in der Datei mit
    sechs Arbeitern blind: Zwei verbundene reichten ihr, und vier Startstellen
    standen taub da — die Legende blieb für immer auf „wird berechnet", die
    Schichtanalyse-Zeile stand, und „Nach einer neuen Version sehen" wurde ein
    toter Knopf (Gesamtreview 25.08.2026, I-2/E-8). Geprüft wird jetzt: In
    jeder Funktion, die einen ``…Worker(...)`` baut, wird auch
    ``crashed.connect`` gerufen.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "app" / "ui"

    def worker_classes(tree: ast.AST) -> set[str]:
        return {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            and any(getattr(base, "id", "") == "Worker" for base in node.bases)
        }

    trees = {
        path: ast.parse(path.read_text(encoding="utf-8")) for path in sorted(root.glob("*.py"))
    }
    known = set().union(*(worker_classes(tree) for tree in trees.values()))
    assert known, "keine Worker-Klassen gefunden — dann prüft der Lauf nichts"

    deaf: list[str] = []
    sites = 0
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            builds = [
                call
                for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and (
                    getattr(call.func, "id", "") in known or getattr(call.func, "attr", "") in known
                )
            ]
            if not builds:
                continue
            sites += 1
            listens = any(
                isinstance(call, ast.Call)
                and getattr(call.func, "attr", "") == "connect"
                and getattr(getattr(call.func, "value", None), "attr", "") == "crashed"
                for call in ast.walk(node)
            )
            if not listens:
                deaf.append(f"{path.name}:{node.name}")

    assert sites >= 10, f"nur {sites} Startstellen gefunden — dann prüft der Lauf zu wenig"
    assert not deaf, "baut Arbeiter, hört aber nicht auf crashed: " + ", ".join(deaf)


def test_the_sweep_over_the_surface_finds_files_to_read() -> None:
    """Drei Prüfungen hier lesen ``app/ui/*.py`` und sichern zu, dass sie
    nichts Verbotenes finden.

    Eine Zusicherung auf „nichts gefunden" ist auch dann grün, wenn nichts
    gelesen wurde: Zieht der Ordner um oder wird eine Datei zum Paket, liefert
    der Glob eine leere Liste, und die Schleife läuft nie. Die Prüfung meldet
    dann „kein Verstoß" und meint „nicht nachgesehen".
    """
    from pathlib import Path

    files = sorted((Path(__file__).resolve().parent.parent / "app" / "ui").glob("*.py"))

    # Weit unter dem Stand (52) — das soll einen Zusammenbruch fangen, nicht
    # jede neue oder gelöschte Datei melden.
    assert len(files) >= 20, f"nur {len(files)} Dateien unter app/ui — falscher Pfad?"


def test_the_leash_turns_away_what_is_not_a_worker(qt_app: QApplication) -> None:
    """Was kein ``isRunning`` hat, kommt nicht in die Menge der Gehaltenen.

    Der Zeitgeber, der später nachsieht, ob ein Arbeiter ausgelaufen ist,
    fragt jeden Eintrag nach ``isRunning``. Ein Fremdkörper darin ist deshalb
    kein Schönheitsfehler, sondern eine Ausnahme in einem Qt-Rückruf — weit
    weg von ihrer Ursache, ohne einen Test rot zu machen, und sie beendet die
    Aufräumkette für **alle** übrigen Arbeiter dieses Durchgangs.

    Der Docstring von ``hold_until_done`` beschrieb genau diesen Fall und
    deckte nur einen seiner Werte ab: ``None``. Am 30.08.2026 stand
    ``'object' object has no attribute 'isRunning'`` zweimal je Lauf im
    Protokoll — ``_on_split_done`` reicht auch einen fremden Arbeiter hierher
    (richtig so, ein veralteter Thread läuft ja noch), und
    ``test_a_stale_split_worker_cannot_deliver`` schickt dafür eine Attrappe
    durch die ganze Kette.

    **Latent war er jahrelang:** Ohne den Suite-Pin fiel die letzte Referenz,
    bevor der Zeitgeber feuerte, und der Rückruf lief nie. Seit der Pin auch
    Viewports hält, lebt alles lange genug. Ein Fehler, den nur eine
    Aufräumung verdeckt, ist keiner weniger.

    Geprüft werden beide Eingänge — sie sind die einzigen Stellen, an denen
    etwas in ``leash._alive`` gelangt, und deshalb dürfen sich die Leser
    danach auf einen Arbeiter verlassen.
    """
    from app.ui import leash

    fremd = object()
    vorher = set(leash._alive)
    leine = leash.WorkerLeash(QObject())
    leine.hold_until_done(fremd)
    leine.retire(fremd)

    assert set(leash._alive) == vorher, "ein Fremdkörper ist in die Menge gelangt"
    assert fremd not in leash._alive
