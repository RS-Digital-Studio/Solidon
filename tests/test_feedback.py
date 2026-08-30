"""Der Bogen nach dreißig Minuten (§37.2) — zählen, fragen, aufhören.

Die drei Fragen dieser Datei: Wird die Zeit richtig gezählt? Wird zur richtigen
Zeit gefragt — und, wichtiger, wann wird **nicht** mehr gefragt? Und bleibt der
Kern dabei stumm, also ohne eigenen Weg hinaus?
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.core import activation, feedback
from app.i18n import TranslatableText


@pytest.fixture(autouse=True)
def own_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Jeder Test bekommt sein eigenes Profil.

    Die Suite biegt die Nutzerverzeichnisse schon in einen Temp-Ordner um
    (§38), aber alle Tests teilen ihn — und dieses Modul schreibt eine Datei,
    deren Inhalt der nächste Test sonst vorfindet.
    """
    monkeypatch.setattr(feedback, "user_config_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def demo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die laufende Demo — der Zustand, in dem überhaupt gefragt wird.

    ``conftest`` nimmt der Suite den Stichtag weg, damit sie nicht am Tag
    danach rot wird. Wer die Demo braucht, setzt sie ausdrücklich.
    """
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(days_left=68, deadline=date(2026, 10, 30)),
    )


@pytest.fixture
def sold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Verkaufsversion: kein Stichtag, also keine Demo."""
    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=14))


def test_time_adds_up_across_sessions(own_config: Path) -> None:
    """Die Zeit steht in einer Datei, nicht im Prozess."""
    feedback.record(600)
    feedback.record(600)

    assert (own_config / feedback.STATE_FILE).is_file(), "der Stand liegt im Profil"
    assert feedback.read().used_seconds == pytest.approx(1200)


def test_time_never_runs_backwards() -> None:
    """Eine negative Spanne ist keine Zeit — sie kommt von einer Uhr."""
    feedback.record(600)
    feedback.record(-300)

    assert feedback.read().used_seconds == pytest.approx(600)


def test_nobody_is_asked_before_the_half_hour(demo: None) -> None:
    """Eine Minute vor der Zeit wird nicht gefragt, eine Sekunde danach schon."""
    feedback.record(feedback.DUE_SECONDS - 60)
    assert not feedback.due(), "vor der halben Stunde bleibt es still"

    feedback.record(61)
    assert feedback.due(), "danach wird gefragt"


def test_the_sold_version_does_not_ask(sold: None) -> None:
    """„Was fehlt bis zum Erscheinen" ist nach dem Erscheinen die falsche Frage.

    Sie verschwindet mit derselben Zeile wie der Stichtag —
    ``DEMO_UNTIL = None``, und niemand muss ein zweites Datum nachziehen.
    """
    feedback.record(feedback.DUE_SECONDS * 10)

    assert not feedback.due(), "ohne Demo wird nicht gefragt"


def test_a_refusal_holds(demo: None) -> None:
    """*Nein danke* ist eine Antwort und gilt dauerhaft."""
    feedback.record(feedback.DUE_SECONDS)
    feedback.mark_declined()

    assert not feedback.due()
    assert feedback.read().settled


def test_an_answer_ends_it(demo: None) -> None:
    """Wer geantwortet hat, wird nicht noch einmal gefragt."""
    feedback.record(feedback.DUE_SECONDS)
    feedback.mark_answered()

    assert not feedback.due()


def test_three_invitations_are_enough(demo: None) -> None:
    """Wer nichts entscheidet, wird dreimal gefragt und dann nicht mehr.

    Der Streifen kommt wieder, weil „stehen gelassen" keine Antwort ist —
    aber nicht endlos, weil der vierte ungelesen weggeklickt würde.
    """
    feedback.record(feedback.DUE_SECONDS)

    for round_number in range(feedback.MAX_INVITATIONS):
        assert feedback.due(), f"Einladung {round_number + 1} steht noch aus"
        feedback.mark_invited()

    assert not feedback.due(), "nach der dritten ist Schluss"
    assert feedback.read().settled


def test_a_broken_file_costs_nothing_but_the_count(own_config: Path) -> None:
    """Eine beschädigte Datei hält nichts an — sie enthält eine Minutenzahl."""
    (own_config / feedback.STATE_FILE).write_text("{kaputt", encoding="utf-8")

    assert feedback.read() == feedback.Progress()

    (own_config / feedback.STATE_FILE).write_text(json.dumps([1, 2]), encoding="utf-8")

    assert feedback.read() == feedback.Progress()


def test_a_read_only_profile_does_not_stop_anything(
    monkeypatch: pytest.MonkeyPatch, own_config: Path
) -> None:
    """Ohne Schreibrecht wird ab null gezählt, statt zu scheitern."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise OSError("read-only")

    monkeypatch.setattr(Path, "write_text", refuse)

    assert feedback.record(feedback.DUE_SECONDS).used_seconds == pytest.approx(feedback.DUE_SECONDS)
    assert feedback.read() == feedback.Progress()


def test_the_message_carries_only_what_was_answered() -> None:
    """Eine ausgelassene Frage wird keine beantwortete."""
    text = feedback.compose(
        rating=None,
        answers={"good": "Die Parameterleiste.", "missing": "   "},
    )

    assert "Die Parameterleiste." in text
    assert str(feedback.QUESTIONS[0].label) in text
    assert str(feedback.QUESTIONS[1].label) not in text, "die leere Frage fällt heraus"


def test_the_rating_arrives_as_a_word_not_only_a_number() -> None:
    """Regel 18: die Stufe trägt eine zweite Kodierung, und die liest sich."""
    text = feedback.compose(rating=5, answers={})

    assert "5/5" in text
    assert str(dict(feedback.RATINGS)[5]) in text


def test_an_empty_survey_stays_empty() -> None:
    """Kein Feld ist Pflicht — und ein Bogen ohne Inhalt erfindet keinen.

    ``support.check`` lehnt eine leere Sendung mit einem Vorschlag ab; ein
    ``compose``, das Überschriften ohne Antworten zurückgäbe, umginge das.
    """
    assert feedback.compose() == ""


def test_every_text_of_the_survey_can_be_translated() -> None:
    """Regel 20 — für die Texte, die der Kunde im Bogen liest."""
    texts: list[object] = [
        feedback.INVITATION_TITLE,
        feedback.INVITATION_BODY,
        feedback.INVITATION_ACCEPT,
        feedback.INVITATION_DECLINE,
        feedback.OPENING,
        feedback.RATING_LABEL,
    ]
    texts.extend(label for _step, label in feedback.RATINGS)
    for question in feedback.QUESTIONS:
        texts.extend((question.label, question.hint))

    for text in texts:
        assert isinstance(text, TranslatableText), f"fest eingebaut: {text!r}"


def test_the_survey_has_its_own_kind() -> None:
    """Der Bogen sortiert sich im Posteingang selbst — und wählt sich nicht."""
    from app.core import support

    assert support.KIND_SURVEY in support.KIND_NAMES
    assert support.KIND_SURVEY not in {support.KIND_IDEA, support.KIND_BUG}


def test_the_counter_has_no_way_out() -> None:
    """§37.2: Ein Zeitgeber, der selbst sendete, wäre Telemetrie.

    Dieses Modul zählt und fragt. Es kennt keinen Server, keinen Versand und
    keine Sendung — was der Kunde schreibt, geht durch denselben Knopf wie
    jede andere Rückmeldung.
    """
    import inspect

    source = inspect.getsource(feedback)

    for forbidden in ("urlopen", "support.send", "Ticket("):
        assert forbidden not in source, f"der Bogen sendet nicht selbst: {forbidden}"


def test_the_form_hands_over_what_was_filled_in(qt_app: object) -> None:
    """Das Widget sammelt ein, der Kern setzt zusammen — und nichts dazwischen.

    Der Bogen baut seinen Text über :func:`app.core.feedback.compose`, damit
    die Vorschau des Dialogs zeigen kann, was ankommt.
    """
    from app.ui.survey import SurveyForm

    form = SurveyForm()

    assert form.rating() is None, "ohne Klick gibt es keine Stufe"

    form.ratings.button(4).setChecked(True)
    form.fields["good"].setPlainText("Der Verlauf zeigt jeden Schritt.")
    text = form.text(extra="Und die Beispiele waren hilfreich.")

    assert "4/5" in text
    assert "Der Verlauf zeigt jeden Schritt." in text
    assert "Und die Beispiele waren hilfreich." in text
    assert str(feedback.QUESTIONS[1].label) not in text, "das leere Feld fällt heraus"


def test_the_form_says_when_something_changed(qt_app: object) -> None:
    """Ohne dieses Signal zeigt die Vorschau etwas anderes als die Sendung."""
    from app.ui.survey import SurveyForm

    form = SurveyForm()
    seen: list[int] = []
    form.changed.connect(lambda: seen.append(1))

    form.ratings.button(2).setChecked(True)
    form.fields["missing"].setPlainText("Ein Kürzel für die Ansicht.")

    assert seen, "die Vorschau erfährt von der Änderung"


def _work_happened(application: object) -> None:
    """Eine Taste, wie sie ein Nutzer drückt — und nicht ein gesetztes Feld.

    Der Filter hängt an der Anwendung, also muss das Ereignis über sie laufen:
    Wer stattdessen den Merker im Objekt setzt, prüft die Buchführung und nicht
    die Erkennung.
    """
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QWidget

    target = QWidget()
    press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "a")
    application.notify(target, press)  # type: ignore[attr-defined]


def test_the_clock_counts_work_and_not_an_open_window(qt_app: object, demo: None) -> None:
    """Ein Fenster, das über Nacht offen steht, hat nicht die Nacht gearbeitet."""
    from app.ui.survey import TICK_SECONDS, UsageClock

    clock = UsageClock()
    clock.start()

    clock.tick()
    assert feedback.read().used_seconds == pytest.approx(0), "eine leere Minute zählt nicht"

    _work_happened(qt_app)
    clock.tick()
    assert feedback.read().used_seconds == pytest.approx(TICK_SECONDS)

    clock.tick()
    assert feedback.read().used_seconds == pytest.approx(TICK_SECONDS), (
        "der Merker gilt für eine Minute, nicht für den Rest der Sitzung"
    )
    clock.stop()


def test_the_clock_keeps_asking_until_someone_can_listen(qt_app: object, demo: None) -> None:
    """Sie meldet sich — und gibt nicht auf, wenn der Moment schlecht ist.

    Das Fenster kann gerade rechnen; dann fragt niemand. Hielte die Uhr sich
    daraufhin an, wäre der Bogen für die ganze Sitzung verloren. Angehalten
    wird sie von dem, der die Karte wirklich zeigt.
    """
    from app.ui.survey import TICK_SECONDS, UsageClock

    feedback.record(feedback.DUE_SECONDS - TICK_SECONDS)
    clock = UsageClock()
    clock.start()
    seen: list[int] = []
    clock.due.connect(lambda: seen.append(1))

    _work_happened(qt_app)
    clock.tick()
    assert seen == [1], "die Zeit ist zusammen, also wird gefragt"
    assert clock.running(), "und noch einmal, falls gerade niemand zuhören konnte"

    _work_happened(qt_app)
    clock.tick()
    assert seen == [1, 1]

    clock.stop()


def test_the_clock_stops_when_the_matter_is_settled(qt_app: object, demo: None) -> None:
    """Ist die Sache erledigt, zählt sie nicht weiter.

    Eine Uhr, die läuft, obwohl niemand mehr gefragt wird, schreibt jede
    Minute eine Datei, die niemand mehr liest.
    """
    from app.ui.survey import TICK_SECONDS, UsageClock

    feedback.record(feedback.DUE_SECONDS - TICK_SECONDS)
    clock = UsageClock()
    clock.start()
    feedback.mark_declined()

    _work_happened(qt_app)
    clock.tick()

    assert not clock.running()


def test_the_clock_does_not_start_when_there_is_nothing_to_ask(qt_app: object, demo: None) -> None:
    """Wer *Nein danke* geklickt hat, hat auch keine Uhr mehr."""
    from app.ui.survey import UsageClock

    feedback.mark_declined()
    clock = UsageClock()
    clock.start()

    assert not clock.running()


def test_a_moving_mouse_is_not_work(qt_app: object, demo: None) -> None:
    """Ein Zeiger, der über das Fenster streicht, ist keine Nutzung.

    Ohne diese Grenze zählte jedes Fenster, über das jemand hinwegfährt,
    seine Minute — und ein Fenster, in dem der Zeiger ruht, keine.
    """
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QWidget

    from app.ui.survey import UsageClock

    clock = UsageClock()
    clock.start()

    somewhere = QPointF(4.0, 4.0)
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        somewhere,
        somewhere,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qt_app.notify(QWidget(), move)  # type: ignore[attr-defined]
    clock.tick()

    assert feedback.read().used_seconds == pytest.approx(0)
    clock.stop()


# --- Die Karte im Fenster -----------------------------------------------------


def test_the_card_edge_is_quiet_and_the_button_keeps_the_accent() -> None:
    """Die Karte trägt die Linienfarbe, ihr Knopf den Akzent.

    **B6 der Design-Durchsicht:** Ohne dass der Kunde etwas getan hat, trugen
    vier Elemente gleichzeitig die Akzentkante — darunter diese Karte. Eine
    Karte ist eine Fläche und keine Aufforderung; was gefragt ist, sagt der
    Knopf, und der behält den Akzent.

    Die Trennlinie stammt aus
    ``konzepte/konzept-akzentfarben-haushalt-2026-08.md`` und heißt
    **flüchtig gegen dauerhaft**: Die Kartenkante steht da, bevor irgendetwas
    geschieht, und gehört damit zu den leisen Formen.

    Geprüft am Stylesheet und nicht am Bild: Welche Farbe gesetzt wird, ist
    die Absicht; wie sie aussieht, hängt am Thema.
    """
    pytest.importorskip("PySide6")

    from PySide6.QtWidgets import QApplication

    from app.ui.survey import SurveyNotice
    from app.ui.theme import THEMES

    if QApplication.instance() is None:
        QApplication([])

    karte = SurveyNotice()
    karte.set_theme("dark")
    stil = karte.styleSheet()
    farben = THEMES["dark"]

    kante = [teil for teil in stil.split("}") if "#surveyNotice {" in teil]
    assert kante, f"die Regel der Karte fehlt im Stylesheet: {stil[:120]!r}"
    assert farben["line"] in kante[0], f"die Kartenkante muss die Linienfarbe tragen: {kante[0]!r}"
    assert farben["highlight"] not in kante[0], (
        "die Kartenkante darf den Akzent nicht tragen — sie leuchtete sonst, "
        "ohne dass der Kunde etwas getan hat"
    )

    knopf = [teil for teil in stil.split("}") if "#surveyGive" in teil]
    assert knopf and farben["highlight"] in knopf[0], (
        "der Knopf behält den Akzent — er ist die Handlung, um die es geht"
    )
