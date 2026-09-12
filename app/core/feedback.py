"""Der Bogen, der je Version nach fünfzehn Minuten fragt, wie es läuft (§37.2).

Solidon ist bis zum Verkaufsstart eine Demo, und eine Demo, die niemanden
fragt, erfährt nichts. Was fehlt, merkt der, der damit arbeitet — nicht der,
der es gebaut hat. Also fragt die Anwendung einmal je Version nach: nach
fünfzehn Minuten tatsächlicher Arbeit, über alle Sitzungen dieser Version.

**Die Grenze zur verbotenen Telemetrie bleibt, wo sie ist.** Dieses Modul
zählt eine Zahl in einer Datei im Nutzerprofil und beantwortet die Frage, ob
sich das Fragen lohnt. Es sendet nichts, es kennt keinen Server, und es gibt
den Weg hinaus nicht ein zweites Mal: Was der Kunde schreibt, geht durch
denselben Dialog und denselben Knopf wie jede andere Rückmeldung
(:mod:`app.core.support`). Ein Zeitgeber, der selbst sendete, wäre Telemetrie,
gleich wie freundlich er begründet ist — hier öffnet er nicht einmal ein
Fenster, er macht einen Streifen sichtbar, den der Kunde anklicken kann oder
nicht.

**Warum ein eigener Stand und nicht der Testlaufmarker.** ``trial.json`` hält
zwei Kalendertage und ist absichtlich löschbar (wer ihn wegwirft, hat wieder
vierzehn Tage). In der Demo zählt er ohnehin nichts, weil dort ein Stichtag
gilt. Ein Feedback-Zähler daran verschwände mit ihm oder wäre von vornherein
tot.

**Und warum er an der Demo hängt.** :attr:`Activation.in_demo` ist die eine
Zeile, an der die Unterscheidung zwischen Demo und Verkaufsversion hängt —
``DEMO_UNTIL`` steht auf einem Datum oder auf ``None``. Der Bogen fragt nach
dem, was bis zum Release fehlt; mit dem Stichtag verschwindet er im selben
Zug, ohne dass jemand ein zweites Datum nachziehen muss.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from app import branding
from app.core import activation
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_config_dir
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Nach fünfzehn Minuten aktiver Nutzung der jeweiligen Version wird gefragt.
DUE_SECONDS: Final = 15 * 60

#: Auch eine unbeantwortete Einladung wird je Version nur einmal angezeigt.
MAX_INVITATIONS: Final = 1

#: Wo der Stand liegt. Neben ``settings.json`` und ``trial.json``, lesbar und
#: löschbar wie die beiden — wer ihn wegwirft, wird noch einmal gefragt, und
#: das ist kein Schaden, den es zu verhindern gälte.
STATE_FILE: Final = "feedback.json"

#: Was im Streifen steht, wenn er fällig wird. Der Text gehört hierher und
#: nicht in die Oberfläche: Er ist die Frage, und die Frage ist der Inhalt
#: dieses Moduls — die Oberfläche zeigt sie nur an.
INVITATION_TITLE: Final = _("Wie läuft es mit Solidon?")
INVITATION_BODY: Final = _(
    "Ich entwickle Solidon allein. Hinweise zu Fehlern, Verbesserungen und zur "
    "Bedienung helfen mir dabei. Ich berücksichtige jede Rückmeldung bei der "
    "Weiterentwicklung der App."
)
INVITATION_ACCEPT: Final = _("Rückmeldung geben")
INVITATION_DECLINE: Final = _("Nein danke")

#: Was über dem Bogen steht, wenn er offen ist. Er tritt an die Stelle des
#: Satzes, mit dem sich der Rückmeldungsdialog sonst öffnet: Dort hat jemand
#: von sich aus etwas zu sagen, hier ist er gefragt worden.
OPENING: Final = _(
    "Ich entwickle Solidon allein. Ihre Hinweise zu Fehlern, Verbesserungen und "
    "zur Bedienung helfen mir, die App weiterzuentwickeln. Ich berücksichtige "
    "jede Rückmeldung.\n\nDanke, dass Sie sich die Zeit nehmen. Kein Feld ist Pflicht — auch ein "
    "einziger Satz hilft. Die Antwort geht an {address}; gesendet wird nur, "
    "was unten steht."
)

#: Die Frage nach dem Gesamteindruck und ihre fünf Antworten.
#:
#: Als Wort und als Zahl, nicht als Sternenreihe und erst recht nicht als
#: Farbverlauf: Regel 18 verlangt eine zweite Kodierung, und fünf Wörter sind
#: die einzige, die auch in einer Vorlesehilfe ankommt.
RATING_LABEL: Final = _("Wie gut kommen Sie mit dem Programm zurecht?")
RATINGS: Final[tuple[tuple[int, TranslatableText], ...]] = (
    (1, _("Gar nicht gut")),
    (2, _("Mit Mühe")),
    (3, _("Geht so")),
    (4, _("Ganz gut")),
    (5, _("Sehr gut")),
)


@dataclass(frozen=True, slots=True)
class Question:
    """Eine Frage des Bogens: ihr Schlüssel, ihr Text, ihr Beispiel.

    Der Schlüssel reist in den Nachrichtentext und bleibt englisch; gelesen
    wird ``label``. ``hint`` steht als blasser Text im leeren Feld — er
    beantwortet die Frage, die vor jedem leeren Feld steht: *wie ausführlich
    denn?*
    """

    key: str
    label: TranslatableText
    hint: TranslatableText


#: Die zwei Fragen. Es sind zwei und nicht sechs, weil ein Bogen, der eine
#: Seite füllt, unbeantwortet bleibt — und weil Roberts Auftrag genau diese
#: zwei nennt: was schon gut ist, und was bis zum Erscheinen besser werden
#: muss.
QUESTIONS: Final[tuple[Question, ...]] = (
    Question(
        "good",
        _("Was hat gut funktioniert?"),
        _("Was Sie behalten würden, wie es ist."),
    ),
    Question(
        "missing",
        _("Was hat gefehlt oder gestört?"),
        _("Was Sie gesucht und nicht gefunden haben, oder was länger gedauert hat als nötig."),
    ),
)


@dataclass(slots=True)
class Progress:
    """Was die Anwendung sich je Version über den Bogen merkt — und sonst nichts.

    Vier Werte, alle über den Kunden und keiner über sein Modell: wie lange
    gearbeitet wurde, wie oft gefragt wurde, ob geantwortet und ob abgelehnt
    wurde.
    """

    used_seconds: float = 0.0
    """Gezählte Arbeitszeit über alle Sitzungen dieser Version. Nicht die Zeit, die das
    Fenster offen stand — was zählt, entscheidet die Oberfläche, indem sie nur
    für Minuten mit Eingaben :func:`record` ruft."""

    invitations: int = 0
    """Wie oft der Streifen schon zu sehen war."""

    answered: bool = False
    """Ob eine Rückmeldung abgeschickt wurde."""

    declined: bool = False
    """Ob *Nein danke* geklickt wurde. Getrennt von :attr:`answered`, weil es
    zwei verschiedene Auskünfte sind und nur eine davon eine Rückmeldung ist."""

    @property
    def settled(self) -> bool:
        """Ob die Sache erledigt ist — so oder so.

        Die Oberfläche hält daran ihren Zeitgeber an: Weiterzählen, wenn
        niemand mehr gefragt wird, schriebe jede Minute eine Datei, die
        niemand mehr liest.
        """
        return self.answered or self.declined or self.invitations >= MAX_INVITATIONS


def state_path() -> Path:
    return user_config_dir() / STATE_FILE


def _read_versions() -> dict[str, Any]:
    """Liest die Versionsstände. Der frühere globale Stand gilt für keine Version.

    Fehlende oder beschädigte Dateien beginnen die Zählung neu. Alte Stände
    bleiben erhalten, damit ein Zurückwechseln keine zweite Einladung auslöst.
    """
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    versions = data.get("versions")
    return versions if isinstance(versions, dict) else {}


def read() -> Progress:
    """Der abgelegte Stand der laufenden Version, oder ein frischer."""
    data = _read_versions().get(branding.APP_VERSION)
    if not isinstance(data, dict):
        return Progress()
    fresh = Progress()
    return Progress(
        used_seconds=max(0.0, float(data.get("used_seconds", fresh.used_seconds) or 0.0)),
        invitations=max(0, int(data.get("invitations", fresh.invitations) or 0)),
        answered=bool(data.get("answered", fresh.answered)),
        declined=bool(data.get("declined", fresh.declined)),
    )


def write(progress: Progress) -> None:
    """Legt den Stand ab. Ein schreibgeschütztes Profil hält nichts an.

    Dann wird beim nächsten Start wieder bei null gezählt — der Bogen kommt
    später oder gar nicht, und das ist die freundliche Richtung des Fehlers.
    """
    try:
        versions = _read_versions()
        versions[branding.APP_VERSION] = asdict(progress)
        ensure_dir(user_config_dir())
        state_path().write_text(json.dumps({"versions": versions}), encoding="utf-8")
    except OSError as problem:
        _log.warning("feedback state could not be written: %s", problem)


def record(seconds: float) -> Progress:
    """Zählt gearbeitete Zeit dazu und gibt den neuen Stand zurück.

    Negative Zeit gibt es nicht: Eine rückwärts gestellte Uhr ist der Grund,
    warum hier Sekunden ankommen und keine Zeitpunkte — die Oberfläche misst
    mit einer Uhr, die nicht zurückläuft.
    """
    progress = read()
    if seconds > 0:
        progress.used_seconds += seconds
        write(progress)
    return progress


def due(progress: Progress | None = None) -> bool:
    """Ob der Streifen jetzt gezeigt werden soll.

    Drei Bedingungen, und alle drei müssen stimmen: die Zeit ist zusammen,
    die Sache ist nicht erledigt, und es läuft die Demo. Die letzte ist die
    wichtigste — nach dem Verkaufsstart ist „was fehlt bis zum Erscheinen"
    die falsche Frage, und sie verschwindet mit derselben Zeile, mit der der
    Stichtag verschwindet.
    """
    stand = read() if progress is None else progress
    if stand.settled or stand.used_seconds < DUE_SECONDS:
        return False
    return activation.state().in_demo


def enabled(progress: Progress | None = None) -> bool:
    """Ob überhaupt noch gezählt und gefragt wird.

    Zwei Gründe dagegen: Für diese Version ist die Sache erledigt
    (beantwortet, abgelehnt oder einmal gezeigt), oder es läuft keine Demo.
    Die Oberfläche hält daran ihre Uhr an — eine Minute zu zählen, die
    niemanden mehr interessiert, schreibt jede Minute eine Datei, die niemand
    mehr liest.
    """
    stand = read() if progress is None else progress
    return not stand.settled and activation.state().in_demo


def mark_invited() -> Progress:
    """Der Streifen ist zu sehen; damit ist diese Version eingeladen."""
    progress = read()
    progress.invitations += 1
    write(progress)
    return progress


def mark_declined() -> Progress:
    """*Nein danke* — und das gilt. Der Weg über *Hilfe → Rückmeldung senden*
    bleibt offen, aber in dieser Version wird nicht mehr gefragt."""
    progress = read()
    progress.declined = True
    write(progress)
    return progress


def mark_answered() -> Progress:
    """Die Rückmeldung ist heraus. Wer geantwortet hat, wird nicht noch einmal
    in derselben Version gefragt."""
    progress = read()
    progress.answered = True
    write(progress)
    return progress


def rating_name(value: int) -> str:
    """Die Wortmarke zu einer Stufe. Unbekannte Stufe gibt es nicht, aber
    falls doch, steht die Zahl da und nicht nichts."""
    for step, label in RATINGS:
        if step == value:
            return str(label)
    return str(value)


def compose(
    rating: int | None = None,
    answers: Mapping[str, str] | None = None,
    extra: str = "",
) -> str:
    """Baut aus den Antworten den Text, der gesendet wird.

    Er entsteht hier und nicht im Dialog, damit die Vorschau dort genau das
    zeigen kann, was ankommt — und damit ein Test ihn prüfen kann, ohne ein
    Fenster zu bauen.

    **Leere Antworten fallen heraus**, mitsamt ihrer Überschrift. Ein Bogen,
    der „Was hat gefehlt: (nichts angegeben)" schickt, macht aus einer
    ausgelassenen Frage eine beantwortete.
    """
    given = dict(answers or {})
    blocks: list[str] = []

    if rating is not None:
        blocks.append(f"{RATING_LABEL} {rating}/{len(RATINGS)} ({rating_name(rating)})")

    for question in QUESTIONS:
        text = given.get(question.key, "").strip()
        if text:
            blocks.append(f"{question.label}\n{text}")

    if extra.strip():
        blocks.append(extra.strip())

    return "\n\n".join(blocks)
