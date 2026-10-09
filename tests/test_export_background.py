"""Was neben einem Export läuft und was ihm vorausgeht (RM-670, §2.8, §29).

Ein 3MF-Export las bei jedem Aufruf den ganzen Profilbestand des Slicers, und
die Druckbefunde, die das feine Ergebnis vor dem Schreiben auslöste, rechneten
gleichzeitig. Geprüft werden die Methoden des Hauptfensters an einem
Namensraum, ohne Fenster und ohne Faden: dass die Befunde dem Export folgen,
statt neben ihm zu rechnen, und dass der Slicerbestand nach dem Start gelesen
wird, sobald keine Auswertung läuft.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from app.core.export import slicer_profiles
from app.ui import main_window
from app.ui.main_window import MainWindow, _ProgressState


class _Flow:
    """Die Berichtsanalyse, wie das Fenster sie sieht: starten und abbrechen."""

    def __init__(self) -> None:
        self.started: list[object] = []
        self.cancelled = 0

    def start(self, result: object, *_args: object, **_kwargs: object) -> None:
        self.started.append(result)

    def cancel(self) -> None:
        self.cancelled += 1


def _window(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Ein Namensraum mit den echten Methoden, um die es geht."""
    monkeypatch.setattr(main_window, "fit_checks", SimpleNamespace(fit_kinds_for=lambda *_args: ()))
    monkeypatch.setattr(main_window, "missing_profile_basis", lambda _document: ())
    result = SimpleNamespace(scene=SimpleNamespace(objects={}))
    window = SimpleNamespace(
        _exporting=False,
        _export_waiting=None,
        _export_worker=None,
        _close_requested=False,
        _print_findings=_Flow(),
        _print_findings_after_export=None,
        _progress_states={
            "export": _ProgressState(
                active=True,
                text="",
                minimum=0,
                maximum=0,
                value=0,
                accessible_name="",
                accessible_description="",
                cancel_description="",
                cancellable=False,
                cancel_enabled=False,
                immediate=False,
            )
        },
        session=SimpleNamespace(
            last_result=result,
            picture=None,
            busy=False,
            project=SimpleNamespace(document=None),
            fine_current=True,
        ),
        settings_used="einstellungen",
        announced=[],
    )
    window.result = result
    window.effective_print_settings = lambda: window.settings_used
    window._print_profile = lambda _settings: "profil"
    window._update_review_status = lambda: None
    window._set_progress_state = lambda *_args, **_kwargs: None
    window._progress_idle = lambda: None
    window._update_actions = lambda: None
    window._hold_until_done = lambda _worker: None
    window.announce = window.announced.append
    window._is_current_result = lambda found: found is window.session.last_result
    window._start_print_findings = lambda found, settings: MainWindow._start_print_findings(
        window, found, settings
    )
    window._print_findings_after_export_ended = lambda: (
        MainWindow._print_findings_after_export_ended(window)
    )
    return window


def test_print_findings_wait_for_the_export_and_follow_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Das feine Ergebnis, auf das ein Export wartet, löste die Schichtanalyse aus
    — und die rechnete neben dem Schreiben (W4-2: 17 bis 51 Prozent der Zeit).
    Sie wartet jetzt, bis die Datei steht, und kommt dann für genau diesen Stand."""
    window = _window(monkeypatch)
    window._export_waiting = (Path("teil.3mf"), "3mf", window.session.project)
    worker = object()

    def starts_writing(*_waiting: object) -> None:
        window._exporting = True
        window._export_worker = worker

    window._write_when_current = starts_writing

    MainWindow._start_print_findings(window, window.result, "einstellungen")
    assert window._print_findings.started == [], "nicht neben dem wartenden Export"
    assert window._print_findings.cancelled == 1, "der Lauf des alten Stands endet"

    MainWindow._export_when_current(window)
    assert window._print_findings.started == [], "nicht, solange geschrieben wird"

    MainWindow._export_worker_done(window, worker)
    assert window._print_findings.started == [window.result], "nach dem Schreiben"
    assert window._print_findings_after_export is None

    MainWindow._start_print_findings(window, window.result, "einstellungen")
    assert window._print_findings.started == [window.result, window.result], "ohne Export sofort"


def test_findings_of_a_replaced_result_do_not_follow_the_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kam während des Schreibens ein neuer Stand, rechnet dessen eigene Auswertung."""
    window = _window(monkeypatch)
    worker = object()
    window._exporting = True
    window._export_worker = worker
    MainWindow._start_print_findings(window, window.result, "einstellungen")

    window.session.last_result = SimpleNamespace(scene=SimpleNamespace(objects={}))
    MainWindow._export_worker_done(window, worker)

    assert window._print_findings.started == []


def test_a_cancelled_waiting_export_lets_the_findings_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wer den wartenden Export abbricht, bekommt die Befunde trotzdem."""
    window = _window(monkeypatch)
    window._export_waiting = (Path("teil.3mf"), "3mf", window.session.project)
    MainWindow._start_print_findings(window, window.result, "einstellungen")

    MainWindow._cancel_export(window)

    assert window._print_findings.started == [window.result]


class _Thread:
    """Ein Faden, der nicht läuft: Gezählt wird, was gestartet würde."""

    started: ClassVar[list[dict[str, object]]] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    def start(self) -> None:
        _Thread.started.append(self.kwargs)


def test_the_slicer_store_is_read_after_the_start_once_nothing_is_evaluated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der erste 3MF-Export trug das Lesen des Bestands selbst, eine bis drei
    Sekunden. Ein Faden liest ihn nach dem Start — aber nicht neben einer
    Auswertung, etwa der eines beim Start geöffneten Modells (RM-672), und als
    Daemon, damit ein hängender Dateizugriff das Beenden nicht aufhält."""
    _Thread.started = []
    monkeypatch.setattr(main_window, "threading", SimpleNamespace(Thread=_Thread))
    window = _window(monkeypatch)
    window._slicer_warm_wanted = False
    window._warm_slicer = lambda: MainWindow._warm_slicer(window)
    window.session.busy = True

    MainWindow._warm_slicer(window)
    assert _Thread.started == [] and window._slicer_warm_wanted, "gemerkt, nicht gestartet"

    window.session.busy = False
    quiet = _Quiet(window)
    MainWindow._on_busy(quiet, False)

    assert _Thread.started == [
        {"target": main_window._warm_the_slicer, "name": "slicer-warmup", "daemon": True}
    ]
    assert not window._slicer_warm_wanted


class _Quiet:
    """Das Fenster nach einer Auswertung: Was ``_on_busy`` sonst anstößt, schweigt."""

    def __init__(self, window: Any) -> None:
        self.__dict__["_window"] = window

    def __getattr__(self, name: str) -> Any:
        window = self.__dict__["_window"]
        if name in ("_slicer_warm_wanted", "_warm_slicer", "_halted"):
            return getattr(window, name, False)
        if name == "_progress_states":
            return {"evaluation": SimpleNamespace(value=0)}
        if name == "feature_panel":
            return SimpleNamespace(limit_fit=lambda *_args: None)
        if name == "_run_timing":
            return SimpleNamespace(begin=lambda: None, end=lambda: None)
        return lambda *_args, **_kwargs: None


def test_the_warmup_fills_the_store_the_export_asks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Der Faden fragt, was der Export fragt: die Maschinen des gefundenen
    Slicers und welche Drucker er kennt."""
    program = tmp_path / "orca-slicer.exe"
    asked: list[tuple[str, ...]] = []
    monkeypatch.setattr(main_window.tools, "slicer_program", lambda: program)
    monkeypatch.setattr(
        slicer_profiles,
        "find_profiles",
        lambda executable, flavour, kinds: (
            asked.append(("find", str(executable), flavour, *kinds)) or []
        ),
    )
    monkeypatch.setattr(
        slicer_profiles,
        "known_printers",
        lambda flavour, executable: asked.append(("known", flavour, str(executable))) or (),
    )

    main_window._warm_the_slicer()

    assert asked == [
        ("find", str(program), "orca", "machine"),
        ("known", "orca", str(program)),
    ]


def test_the_warmup_without_a_slicer_does_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_window.tools, "slicer_program", lambda: None)
    monkeypatch.setattr(
        slicer_profiles, "find_profiles", lambda *_args: pytest.fail("ohne Slicer nichts lesen")
    )

    main_window._warm_the_slicer()


def test_a_failing_warmup_is_no_crash_report(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Ein Fehler im Daemon-Faden ginge sonst als Absturzbericht hinaus
    (``log._unhandled_thread``); der Export liest dann eben selbst."""
    import logging

    def unreadable() -> Path:
        raise OSError("Netzlaufwerk getrennt")

    monkeypatch.setattr(main_window.tools, "slicer_program", unreadable)

    with caplog.at_level(logging.INFO, logger="app.ui.main_window"):
        main_window._warm_the_slicer()

    assert any("slicer warmup failed" in record.getMessage() for record in caplog.records)


def test_the_start_of_the_window_schedules_the_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Angestoßen wird das Lesen beim Start des Fensters, hinter dem Vorabimport."""
    scheduled: list[tuple[int, object]] = []
    monkeypatch.setattr(
        main_window,
        "QTimer",
        SimpleNamespace(singleShot=lambda delay, _context, slot: scheduled.append((delay, slot))),
    )
    monkeypatch.setattr(main_window, "first_run", SimpleNamespace(should_run=lambda _s: False))
    window = SimpleNamespace(
        settings=SimpleNamespace(check_for_updates=False),
        _usage=SimpleNamespace(start=lambda: None),
        _offer_unsaved_recovery=lambda: None,
        _apply_remote=lambda: None,
        _announce_the_sale=lambda: None,
        _warm_slicer=object(),
    )

    MainWindow.start(window)

    assert scheduled == [(main_window.SLICER_WARMUP_DELAY_MS, window._warm_slicer)]
