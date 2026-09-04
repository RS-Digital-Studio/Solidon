"""Die Halteleine für Arbeiter-Threads.

Ein ``QThread`` bekommt hier keinen Qt-Elternteil; ihn hält allein die
Python-Referenz. Fällt sie weg, während der Thread noch läuft, zerstört der
Speicherbereiniger das C++-Objekt unter ihm — eine Zugriffsverletzung ohne
Zeile, irgendwann später und selten reproduzierbar.

Das Hauptfenster hatte dieses Muster (``_retire``/``_hold_until_done``), die
Dialoge nicht: fünf Stellen schrieben ``self._worker = None`` direkt im
``finished``-Slot — zu früh, denn ``finished`` heißt „``run`` ist zurück",
nicht „das Objekt darf weg" —, und ein Lambda, das blind ``None`` schreibt,
trifft obendrein den Nachfolger, wenn der Vorgänger später fertig wird. Die
Gebietsregel beschreibt beides; hier steht es einmal statt sechsmal.

**Warum der Aufräumbefehl überall ``release`` heißt.** Er hieß einmal fünf
verschiedene Dinge — ``release``, ``wait_for_workers``, ``wait_for_survey``,
``wait_for_look``, ``wait_for_setup`` —, und wer eine Testfixture darauf
baute, sammelte sie nacheinander ein: erst zwei, dann drei, dann vier. Der
fünfte fehlte, und der Prozess starb beim Abbau an einem Thread, der sein
Fenster überlebt hatte. Ein Name, den die Fixture blind rufen kann, ist die
einzige Form, die mitwächst; es sind inzwischen vierzehn Klassen.

**Der fachliche Name daneben bleibt.** ``wait_for_setup`` und seine
Geschwister geben zurück, **ob** ein Lauf fertig wurde, und werden beim
Schließen gefragt. Aufräumen fragt nicht, es wartet — die beiden tun
Verschiedenes und behalten deshalb getrennte Namen.

**Die Frist der fachlichen Methode bleibt ihre eigene.** In den Dialogen stand
zuerst ``wait_for_...(timeout_ms)``, und damit bekam eine Erhebung, für die 30
Sekunden vorgesehen sind, die 2 Sekunden aus :data:`WAIT_TIMEOUT_MS`, die für
das Einsammeln der Leine gedacht sind. Gemessen an ``test_chat_ui``: zwei von
vier Läufen starben danach beim Abbau, gegen null von vier davor. Der
Parameter von ``release`` gilt der Leine, nicht der Sache.

**Auch eine Klasse ohne eigenen Arbeiter braucht ihn.** Wer nur eine
``WorkerLeash`` hält und keinen Weg anbietet, ihr Schluss zu sagen, fällt
nicht auf, solange jeder Test schließt: Der Weg über ``reject``/``closeEvent``
wartet, der Weg über das bloße Wegräumen nicht. Beim Erstlauf-Dialog las ein
Test die Sprachliste und schloss nie — dann stirbt der Prozess beim Abbau, und
die Ursache steht drei Dateien weiter.
"""

from __future__ import annotations

import gc
import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Final

from PySide6.QtCore import QEvent, QObject, QThread, QTimer, Signal
from shiboken6 import isValid

from app.core.log import get_logger

_log = get_logger(__name__)

#: Wie lange bis zum nächsten Blick, wenn ein fertiger Arbeiter beim ersten
#: noch lief. Der eine Versuch von früher ließ ihn dauerhaft in der Liste,
#: und ``wait_all`` lief ihn bei jedem Aufruf mit ab.
RELEASE_RETRY_MS: Final = 50

#: Wie lange am Fensterende auf einen Arbeiter gewartet wird. Er hat ein
#: Abbruch-Token und sollte längst zurück sein; die Grenze ist für den Fall,
#: dass er es nicht ist — ein Fenster, das beim Schließen unbegrenzt wartet,
#: ist eingefroren und sagt es nicht.
WAIT_TIMEOUT_MS: Final = 2000

#: Jeder gehaltene Arbeiter, über alle Leinen hinweg.
#:
#: **Modulweit und nicht nur an der Leine**, und der Grund ist ein Absturz, den
#: die Erstinbetriebnahme sichtbar gemacht hat: Ihr Dialog startet beim Aufbau
#: eine Erhebung. Wird er freigegeben — ein Test lässt ihn fallen, ein Fenster
#: räumt ihn weg —, während der Arbeiter noch läuft oder gerade fertig wurde,
#: dann geht mit dem Dialog die Leine, mit der Leine ihre Liste und damit die
#: letzte Referenz auf den ``QThread``. Der Speicherbereiniger zerstört das
#: C++-Objekt unter einem laufenden Thread, und der Abriss kommt später und
#: ohne Zeile — genau die Sorte, gegen die es dieses Modul gibt.
#:
#: Ein Arbeiter kostet hier nichts als seinen Zeiger, und er verschwindet,
#: sobald ``isRunning`` nein sagt.
_alive: set[Any] = set()

#: Der Zeitgeber braucht einen Empfänger, der die Widgets überlebt. Ein
#: Lambda ohne Empfänger läuft ins Leere, sobald das Fenster weg ist — und
#: genau dann muss noch jemand nachsehen, ob der Thread ausgelaufen ist.
_keeper: QObject | None = None


def _keeper_object() -> QObject:
    """Das langlebige Gegenstück zu den Widgets. Beim ersten Bedarf angelegt."""
    global _keeper
    if _keeper is None:
        _keeper = QObject()
    return _keeper


def alive() -> tuple[Any, ...]:
    """Was insgesamt noch gehalten wird. Für Tests und die Fehlersuche."""
    return tuple(_alive)


def _release_global(worker: Any) -> None:
    """Einen abgewarteten Arbeiter erst nach seinen eingereihten Signalen lösen.

    ``wait`` beendet den Thread, stellt aber sein ``finished``-Signal noch
    nicht zu. Die modulweite Referenz davor zu streichen kann das C++-Objekt
    unter dem eingereihten Signal freigeben. Der langlebige Empfänger hält den
    Arbeiter bis zur nächsten Runde der Ereignisschleife sicher fest.
    """
    if worker is None or not isValid(worker):
        _alive.discard(worker)
        return
    if worker.isRunning():
        QTimer.singleShot(RELEASE_RETRY_MS, _keeper_object(), lambda: _release_global(worker))
        return
    _alive.discard(worker)


def wait_for_all(timeout_ms: int = 2000) -> tuple[Any, ...]:
    """Auf jeden gehaltenen Arbeiter warten — auch auf die ohne Fenster.

    **Wer über die Fenster geht, findet nicht alle.** ``MainWindow`` hat
    ``wait_for_workers``, und die Aufräum-Fixture der Suite ruft es über
    ``application.topLevelWidgets()``. Ein Arbeiter, der an einem **Dialog**
    hängt — die Erhebung der Erstinbetriebnahme, die Werkzeugprobe des Chats —,
    steht in keinem dieser Fenster: Der Dialog ist längst weggeräumt, sein
    Thread läuft, und die Fixture geht weiter zu ``processEvents()``.

    Dort treffen sich dann zwei, die nicht zusammenkommen dürfen. Gefunden am
    23.08.2026 in einem Stapelabzug von ``py-spy``:

        Arbeiter:    install.py:341  __import__(requirement.module)
                     first_run.py:98 work
        Hauptthread: conftest.py:192 application.processEvents()

    ``__import__`` nimmt den Import-Lock; was ``processEvents`` an Python-Code
    auslöst und seinerseits importiert, wartet darauf. Das ist kein Absturz,
    sondern ein **Warten** — die Läufe stehen bei 0,00 CPU, sie stürzen nicht.
    Und es erklärt, warum ein ``gc.collect()`` an derselben Stelle nichts
    ausrichtete: Einsammeln hilft nicht gegen Warten.

    Die Antwort ist ``_alive``, und zwar genau deshalb, weil es **modulweit**
    ist: Es kennt jeden Arbeiter, den irgendeine Leine gestartet hat, gleich
    ob sein Besitzer noch existiert. Zurück kommt, wer nach der Frist immer
    noch läuft — für einen Test, der das melden statt verschweigen soll.
    """
    stubborn: list[Any] = []
    for worker in tuple(_alive):
        if worker is None or not isValid(worker):
            # Ein Arbeiter, dessen C++-Objekt schon weg ist: ``isRunning``
            # darauf ist die Zugriffsverletzung ohne Zeile. Die Python-Hülle
            # überlebt die C++-Seite, wenn ein Qt-Elternteil sie mitnimmt.
            _alive.discard(worker)
            continue
        if worker.isRunning():
            worker.wait(timeout_ms)
        if worker.isRunning():
            # Wer die Frist reißt, bleibt gehalten: Ihn loszulassen hieße, das
            # C++-Objekt unter einem laufenden Thread freizugeben.
            stubborn.append(worker)
            continue
        # Das ``finished``-Signal liegt jetzt möglicherweise noch in Qts
        # Ereignisschlange. Die globale Halterung fällt deshalb ebenfalls erst
        # dort; so kann der Rückruf seine Leine geordnet aufräumen.
        QTimer.singleShot(0, _keeper_object(), lambda done=worker: _release_global(done))
    return tuple(stubborn)


class Worker(QThread):
    """Ein Arbeiter, der auch mit dem Unerwarteten zurückkommt.

    **Ein ``run``, das eine Ausnahme durchlässt, sendet sein Ergebnissignal
    nie** — und wer darauf wartet, wartet für immer. Nachgestellt am
    Einrichtungsdialog für ComfyUI: Liegt die Installation unter ``Program
    Files``, wirft das Kopieren der Knoten einen ``PermissionError``. Die
    Ausnahme landet auf stderr, wo sie kein Kunde sieht; im Fenster steht
    „Wird eingerichtet …", der Balken läuft, der Knopf sagt „Abbrechen" — und
    dabei bleibt es, bis jemand das Programm beendet.

    Von dreiundzwanzig Arbeitern in der Oberfläche fing genau **einer** eine
    unerwartete Ausnahme, und das war der Versand der Rückmeldung. Die anderen
    zweiundzwanzig konnten ihr Fenster in einen Wartezustand ohne Ausgang
    bringen.

    Erwartete Fehler gehören weiter in ``work``: Sie sind ein Ergebnis und
    werden als eines zurückgegeben (``InstallResult.reason``,
    ``pull_model`` → Satz, ``SetupFailed`` → eigenes Signal). Was hier ankommt,
    ist das, womit niemand gerechnet hat, und dafür gibt es genau eine
    Antwort: sagen, dass es passiert ist, den Wartezustand auflösen, und die
    Zeile ins Protokoll (§33.2).

    Wer erbt, schreibt :meth:`work` statt ``run`` und verbindet ``crashed`` —
    ``tests/test_leash.py`` hält beides fest.
    """

    crashed = Signal(str)
    """Was schiefging, als Text — Ausnahmeart und Meldung, für „Details"."""

    def run(self) -> None:
        try:
            self.work()
        except Exception as problem:  # genau der Sinn dieser Klasse
            _log.exception("worker %s did not come back", type(self).__name__)
            self.crashed.emit(f"{type(problem).__name__}: {problem}")

    def work(self) -> None:
        """Was der Arbeiter tut. Unterklassen setzen das."""
        raise NotImplementedError


class WorkerLeash:
    """Hält fertige und ersetzte Arbeiter, bis Qt wirklich mit ihnen durch ist.

    ``context`` ist das Widget, dem die Zeitgeber gehören: ein Lambda ohne
    Empfänger läuft weiter, wenn das Fenster längst weg ist, und greift dann
    in ein zerstörtes C++-Objekt.
    """

    def __init__(self, context: QObject) -> None:
        self._context = context
        self._held: list[Any] = []

    def start(self, worker: Any) -> None:
        """Einen Arbeiter starten — und ihn ab diesem Moment halten.

        **Der Unterschied zu :meth:`hold_until_done` ist der Zeitpunkt, und er
        ist der ganze Punkt.** Gehalten wurde bisher erst, wenn ein Arbeiter
        fertig war; solange er lief, hing er allein am Feld seines Dialogs. Ein
        Dialog, der vorher freigegeben wird — ein Fenster räumt ihn weg, ein
        Test lässt ihn fallen —, nimmt damit die letzte Referenz auf einen
        **laufenden** Thread mit. Sichtbar wurde das, als die
        Erstinbetriebnahme ihre Erhebung in einen Arbeiter bekam: Die
        Testdatei brach reproduzierbar an der Stelle ab, an der ein Dialog aus
        einem vorigen Test einging.

        Wer einen Arbeiter über diese Methode startet, muss ihn nicht mehr
        selbst am Leben halten; sein Feld ist danach nur noch die Antwort auf
        „läuft gerade einer".
        """
        if worker is None:
            return
        _alive.add(worker)
        worker.finished.connect(self._finished_callback(worker))
        worker.start()

    def _finished_callback(self, worker: Any) -> Callable[[], None]:
        """Das Fertigsignal halten, ohne Arbeiter oder Besitzer einzuschließen.

        Das Signal gehört dem Arbeiter. Ein Rückruf mit ``self`` und
        ``worker`` als Abschluss schließt deshalb genau den Ring, den die
        Leine verhindern soll: Arbeiter → Rückruf → Leine → Fenster. Beide
        Verweise bleiben hier schwach; die modulweite Menge hält den Arbeiter
        so lange sicher fest, wie es nötig ist.
        """
        leash_ref = weakref.ref(self)
        worker_ref = weakref.ref(worker)

        def finished() -> None:
            found_worker = worker_ref()
            if found_worker is None:
                return
            found_leash = leash_ref()
            if found_leash is None:
                QTimer.singleShot(
                    0,
                    _keeper_object(),
                    lambda done=found_worker: _release_global(done),
                )
                return
            found_leash.hold_until_done(found_worker)

        return finished

    def hold_until_done(self, worker: Any) -> None:
        """Den fertigen Arbeiter halten, bis ``isRunning`` nein sagt.

        Wer sein Feld leeren will, tut das im eigenen Slot davor und **nur
        für seinen eigenen Arbeiter** — siehe Gebietsregel.

        ``None`` geht durch, wie bei :meth:`retire`: Ein Slot, der sein Feld
        leert und den alten Inhalt hierherreicht, bekommt None, wenn schon
        jemand vor ihm aufgeräumt hat. Ohne diese Zeile landete None in der
        Liste, und der Zeitgeber danach fragte es nach ``isRunning`` — ein
        AttributeError im Teardown, weit weg von seiner Ursache.

        **Und alles andere, was kein ``isRunning`` hat, ebenso.** Die
        ``None``-Zeile darüber beschrieb den Fall richtig und deckte nur einen
        seiner Werte ab: Ein blankes ``object()`` legt sich genauso in die
        Liste, und der Zeitgeber stirbt daran genauso — nur eben mit
        ``'object' object has no attribute 'isRunning'`` statt mit ``None``.
        Gefunden am 30.08.2026 über eine Sonde am Eingang: ``_on_split_done``
        reicht auch einen **fremden** Arbeiter hierher (richtig so, ein
        veralteter Thread läuft ja noch), und `test_a_stale_split_worker_cannot_deliver`
        schickt dafür eine Attrappe durch die ganze Kette.

        Der Fehler war dabei jahrelang latent: Ohne den Suite-Pin fiel die
        letzte Referenz, bevor der Zeitgeber feuerte — der Rückruf lief nie.
        Seit der Pin auch Viewports hält, lebt alles lange genug, und die
        Ausnahme stand zweimal je Lauf im Protokoll. **Ein Fehler, den nur
        eine Aufräumung verdeckt, ist keiner weniger.**
        """
        if not hasattr(worker, "isRunning"):
            return
        if worker not in self._held:
            self._held.append(worker)
        _alive.add(worker)
        # Der Empfänger überlebt das Widget (siehe :data:`_keeper`): Stirbt der
        # Dialog zuerst, muss trotzdem noch jemand nachsehen, ob der Thread
        # ausgelaufen ist — sonst bleibt er für immer gehalten.
        QTimer.singleShot(0, _keeper_object(), lambda: self._release(worker))

    def retire(self, worker: Any) -> None:
        """Hält einen ersetzten Arbeiter fest, bis er ausgelaufen ist.

        Sein Ergebnis will niemand mehr — aber sein Thread läuft noch, und
        ohne Referenz zerstört der Speicherbereiniger das QThread-Objekt
        unter ihm.

        Dieselbe Eingangsprüfung wie in :meth:`hold_until_done`, und aus
        demselben Grund: Hier stand ``worker is None``, und ein Wert ohne
        ``isRunning`` wäre eine Zeile später an genau dieser Abfrage
        gestorben. **Die beiden Eingänge sind die einzigen Stellen, an denen
        etwas in ``_alive`` gelangt** — wer danach daraus liest
        (``wait_for_all``, ``_release``), darf sich deshalb auf einen
        Arbeiter verlassen.
        """
        if not hasattr(worker, "isRunning") or not worker.isRunning():
            return
        if worker in self._held:
            # Zweimal zurückgestellt heißt nicht zweimal gehalten: sonst stünde
            # er doppelt in der Liste, ``_release`` nähme nur das erste
            # Vorkommen heraus, und an ``finished`` hinge eine zweite Leitung,
            # die dasselbe noch einmal tut.
            return
        self._held.append(worker)
        _alive.add(worker)
        # Nicht beim Signal selbst loslassen — dieselbe Begründung wie in
        # ``hold_until_done``, und derselbe Weg hinaus, damit es nur einen
        # gibt.
        worker.finished.connect(self._finished_callback(worker))

    def _release(self, worker: Any) -> None:
        """Einen ausgelaufenen Arbeiter loslassen — und keinen, der noch läuft."""
        if worker not in _alive:
            return
        if worker.isRunning():
            QTimer.singleShot(RELEASE_RETRY_MS, _keeper_object(), lambda: self._release(worker))
            return
        _alive.discard(worker)
        if worker in self._held:
            self._held.remove(worker)

    def pending(self) -> tuple[Any, ...]:
        """Was gerade gehalten wird — für das Warten am Fensterende."""
        return tuple(self._held)

    def wait_all(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Auf alle gehaltenen Arbeiter warten — am Ende eines Fensters.

        Ein Thread, der sein Fenster überlebt, nimmt den Prozess mit. Genau
        dieser Fall stand hier stumm: ``wait`` gibt ``False`` zurück, wenn die
        Frist reißt, und der Rückgabewert wurde nicht angesehen. Der Abriss kam
        dann später und ohne Zeile — dieselbe Sorte Absturz, gegen die es
        dieses Modul überhaupt gibt.

        Erzwungen wird nichts: ``terminate`` bricht einen Thread mitten im
        Rechnen ab und hinterlässt genau die halb freigegebenen Objekte, die
        den Absturz ausmachen. Was hier steht, ist die Zeile im Protokoll, die
        den nächsten Abriss erklärt.
        """
        for worker in self.pending():
            if worker.isRunning() and not worker.wait(timeout_ms):
                _log.warning(
                    "worker %s did not finish within %d ms — the process may crash on exit",
                    type(worker).__name__,
                    timeout_ms,
                )


def weak_slot[Owner: QObject](
    owner: Owner, call: Callable[..., None], *bound: Any, forward: bool = False
) -> Callable[..., None]:
    """Ein Signalempfänger, der seinen Besitzer **nicht** am Leben hält.

    **Für den einen Fall, den die zwei einfacheren nicht abdecken.** Qt hält
    eine gebundene Methode von sich aus schwach, ein Lambda dagegen stark — wer
    ``connect(self.tue)`` schreibt, hat nichts zu bedenken, und wer feste Werte
    braucht, schreibt eine Methode dafür. Übrig bleibt der Wert aus einer
    **Schleife**: Zehn Knöpfe, die je ein anderes Werkzeug wählen, brauchen den
    Namen am Rückruf, und ein Lambda mit Vorgabeargument schließt genau den
    Ring, gegen den dieses Modul da ist.

    Gemessen: ``partial(self.tue, 1)`` hilft **nicht**, obwohl es wie die
    saubere Fassung eines Lambdas aussieht — es hält die gebundene Methode und
    damit den Besitzer. Von zehn losgelassenen Objekten überlebten alle zehn.

    ``call`` ist die **ungebundene** Funktion (``Editor._tool_chosen``), damit
    hier keine gebundene Methode entsteht; sie bekommt den Besitzer als erstes
    Argument und danach die gebundenen Werte.

    **Was das Signal schickt, wird verworfen** — ``clicked`` sendet ein
    ``checked``, das die wenigsten Empfänger wollen, und ein durchgereichtes
    Argument zu viel ist ein ``TypeError`` erst zur Laufzeit und erst beim
    Klicken. Wer es braucht, sagt ``forward=True``; dann kommt es hinter den
    gebundenen Werten an.
    """
    ref = weakref.ref(owner)

    def slot(*sent: Any) -> None:
        found = ref()
        if found is not None:
            call(found, *bound, *(sent if forward else ()))

    return slot


def stop_watching_the_dying(watcher: QObject, watched: QObject, event: QEvent) -> bool:
    """Bestellt den Filter ab, wenn das überwachte Objekt stirbt.

    Gibt zurück, ob das Ereignis damit erledigt ist — eine Aufrufstelle
    schreibt::

        if stop_watching_the_dying(self, watched, event):
            return False

    **Ein Filter hängt am überwachten Objekt und bleibt dort, bis eine Seite
    ihn entfernt.** Solange kein Fenster starb, fiel das nicht auf; seit sie
    sterben können (`acb0dd5`, ``weak_slot`` weiter oben), läuft der Filter in
    den Abbau hinein und fragt halb abgeräumte Widgets nach ihrer Geometrie::

        libshiboken: Internal C++ object (OverlayHost/ObjectTree) already deleted.

    Qt schickt ``Destroy``, **bevor** die C++-Seite weg ist: der letzte Takt,
    in dem das Abbestellen noch möglich ist.

    **Die Richtung ist der ganze Punkt.** Stirbt das *Filterobjekt*, räumt Qt
    selbst auf — das ist gemessen und hält, und es ist der Grund, warum die
    reine Zählung ``installEventFilter`` gegen ``removeEventFilter`` lange
    keine Aussage war. Gefährlich ist die andere Richtung: Stirbt das
    *überwachte* Objekt, läuft der Filter des Überlebenden weiter.

    Gemessen an ``tests/test_first_run.py`` für den ersten Fall
    (``overlay.py``), je sechs Läufe: **vier von sechs** mit einem
    Teardown-Fehler ohne diese Zeilen, **null von sechs** mit ihnen.

    **Was nicht half, und das gehört dazu:** Zwei Wachen am Eingang der
    Rechnung — ``isValid`` auf Wirt, Ansicht und Zonen — senkten die Quote
    nicht (drei bis vier von sechs blieben rot). Eine Prüfung am Eingang
    gewinnt keinen Wettlauf, der **während** des Aufrufs entschieden wird. Das
    Abbestellen dagegen sorgt dafür, dass der Aufruf gar nicht erst kommt.

    ``QCoreApplication`` als überwachtes Objekt braucht das nicht — sie
    überlebt jeden Filter. Die vier Stellen, die dort installieren, rufen diese
    Funktion deshalb nicht.

    **Wie weit das trägt, ist gemessen, und die Zahl ist ernüchternd.** Ein
    Zähler in dieser Funktion, über vier Fensterdateien am 30.08.2026:

    | Datei | Aufrufe | davon ``Destroy`` | wer |
    |---|---|---|---|
    | ``test_first_run`` | 507 807 | **6** | nur ``OverlayHost`` |
    | ``test_overlay`` | 25 786 | **0** | — |
    | ``test_ui`` | 3 489 045 | **113** | nur ``OverlayHost`` |

    Von den sieben Aufrufstellen schlägt in vier Millionen Ereignissen **eine**
    an — und das ist die, für die der Griff ursprünglich gebaut wurde. Der
    Grund steht in der Lebensdauer: Wo ein Elternteil sein eigenes Kind
    beobachtet (``chat.py``, ``catalog.py``, ``op_dialog.py``,
    ``sketch_editor.py``), sterben beide zusammen, und Qt räumt selbst auf.

    **Die sechs anderen bleiben trotzdem, und zwar als Vorsorge und nicht als
    Behebung** — so steht es auch im Register. Sie kosten einen Typvergleich je
    Ereignis, sie decken den Fall „ein Kind geht einzeln" (Layoutwechsel,
    ``deleteLater``), und der Wächter in ``tests/test_widget_lifetime.py`` sorgt
    dafür, dass die nächste Filterstelle den Griff mitbekommt. Wer sie streichen
    will, hat die Zahl auf seiner Seite; wer sie behält, den Fall, den die Suite
    nicht fährt. Was nicht geht, ist sie für eine Behebung zu halten.
    """
    if event.type() != QEvent.Type.Destroy:
        return False
    watched.removeEventFilter(watcher)
    return True


@contextmanager
def undisturbed() -> Iterator[None]:
    """Ereignisse zustellen, ohne dass der Speicherbereiniger dazwischenfährt.

    **Warum das nötig wurde.** Bis zum 22.08.2026 gab diese Anwendung kein
    einziges Fenster je frei — jedes hing an einem Rückruf, der es festhielt.
    Seit die Ringe aufgelöst sind, räumt der Speicherbereiniger sie ab, und er
    tut es dort, wo er gerade gerufen wird: mitten in ``processEvents``,
    während Qt Ereignisse an genau diese Widgets zustellt. Was dabei zerstört
    wird, wird zweimal zerstört — der Prozess stirbt mit
    ``0xC0000374`` (Heap Corruption), ohne eine Zeile eigenen Codes im Stapel.

    Gemessen an ``tests/test_pose_session.py``, je acht Läufe auf leerer
    Maschine:

    ======================================  ==========
    Stand                                   rote Läufe
    ======================================  ==========
    vor dem Auflösen der Ringe                    1/8
    nach dem Auflösen, ohne diesen Schutz         6/8
    nach dem Auflösen, mit diesem Schutz          1/8
    ======================================  ==========

    Die letzte Zeile ist der Punkt: Der Schutz stellt genau den Zustand her,
    den es vor dem Umbau gab — ohne den Umbau zurückzunehmen. Das eine
    verbleibende Rot ist das bekannte Grundrauschen und in beiden Ständen da.

    **Kein Ersatz für sauberes Aufräumen**, sondern ein Fenster, in dem nicht
    aufgeräumt wird. Wer Qt-Objekte hält, gibt sie weiterhin selbst frei; hier
    wird nur verhindert, dass es *währenddessen* passiert.
    """
    enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if enabled:
            gc.enable()
