"""Der Weg zum Ziel: jeder Klick ein Eingabeereignis mit Probe (D0-P, RM-737).

``guide_targets.next_click`` nennt den nächsten Klick auf dem Weg des Kunden —
Reiter, Klappe, Menü, Untermenü, Aufklappen, Rollen, zuletzt das Ziel —, und
``guide_targets.widget_under`` sagt, was an dieser Stelle wirklich liegt
(:class:`QtPorts`). Ist es nicht der Empfänger dieses Klicks, ist das der Fund
„verdeckt“; bleibt kein Weg, „nicht auffindbar“ (:class:`Walk`). Der Empfänger
folgt der Art, die ``next_click`` je Zielart nennt (:meth:`QtPorts.receiver`):
eine Zeile ihre Liste, eine Menüzeile das Menü mit genau dieser Zeile, eine
Operation ihr Suchtreffer, Knopf oder Menüeintrag, ein Baustein seine Kachel,
eine Leiste über der Ansicht ihr Widget, ein Griff die Ansicht.

Zahlen werden getippt, mit dem Dezimalzeichen der Sprache (:func:`typed_number`),
und nur, wenn der Fokus im Feld des Ziels liegt (:func:`focus_check`).

Falle: **Die Zeiten sind 0,1 s, 1 s und 2 s.** Ein Klick fällt erst, wenn sein
Ort :data:`STABLE_S` lang stillsteht; „verdeckt“ zählt erst, wenn es
:data:`COVERED_S` lang deckt; „nicht auffindbar“ erst nach :data:`MISSING_S`
ohne Weg. Die Karten setzen ihre Höhen Runden nach dem Inhalt, und ein Dialog
nach einer Rechnung kommt nach dem Klick, der sie startete — wer kürzer wartet,
meldet einen Zwischenstand, den der Kunde nie sieht.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final, Protocol

from tools.function_checks import (
    COVERED,
    MAIN_PHASES,
    NO_RESPONSE,
    NOT_FOUND,
    PLACES,
    WHY,
)
from tools.function_machine import SETTLE_MS, BenchFinding, Step, StepMachine

#: Warum ein Klick fällt (``guide_targets.next_click``): das Ziel selbst …
TARGET_REASON: Final = "ziel"

#: … oder ein Wegklick davor, der etwas aufdeckt (``function_checks.WHY``).
WAY_REASONS: Final[frozenset[str]] = frozenset(WHY) - {TARGET_REASON}

#: Die Phase des Wegs und die des Übernehmens — zusammen der Hauptweg, den U für
#: E1 bis E4 zählt (``function_checks.MAIN_PHASES``).
PATH_PHASE, APPLY_PHASE = MAIN_PHASES

#: Wie viele Wegklicks ein Ziel höchstens braucht, bevor der Weg als Kreis gilt.
#: Der längste Weg im Bestand ist Menütitel, Untermenü, Eintrag; dazu Reiter,
#: Klappe und Rollen in der Karte — sieben. Einer Luft.
MOST_WAY_CLICKS: Final = 8

#: Wie lange der nächste Klick unverändert stehen muss, bevor er fällt (Sekunden):
#: Die Karten setzen ihre Höhen über Nullzeitgeber, mehrere Ereignisrunden nach
#: einem Aufklappen. Die Probezeile ``resize_hole`` traf nach 120 ms noch die
#: Klappe „Parameter“, nach dreißig Ereignisrunden ihre Zeile.
STABLE_S: Final = 0.1

#: Wie lange etwas über dem stillstehenden Klickort liegen muss, bevor es als
#: „verdeckt“ zählt (Sekunden): Wächst der Baum nach einem Aufklappen, setzt er
#: seine Höhe sofort, die Karte ihre erst Runden später — dazwischen liegt die
#: neue Zeile außerhalb ihres Abschnitts, über der Karte oder unter der nächsten
#: Klappe. Ein Kunde sieht diesen Zwischenstand nicht; was nach einer Sekunde
#: noch deckt, sieht er.
COVERED_S: Final = 1.0

#: Wie lange ein Ziel ohne Weg sein darf, bevor es „nicht auffindbar“ ist
#: (Sekunden): so lange wie die Frist, in der eine Handlung wirkt — ein Dialog
#: nach einer Rechnung kommt nach dem Klick, der sie startete (Review M14).
#: Gezählt wird erst, wenn das Fenster nicht mehr sagt, dass etwas kommt
#: (``Ports.pending``): Das Merkmalfenster ermittelt seine Zeilen im Arbeiter,
#: und nach zwei Sekunden hieß *Bohrung ändern* „nicht auffindbar“, obwohl es
#: danach dastand (Probelauf F-20).
MISSING_S: Final = 2.0

#: Wie lange das Fenster sagen darf, dass etwas kommt, bevor das Ausbleiben der
#: Fund „keine Rückmeldung“ ist (Sekunden, Prüfpunkt 6).
PENDING_S: Final = 60.0


def typed_number(value_mm: float, unit: str = "mm") -> str:
    """Was der Kunde in ein Längenfeld tippt: Anzeigeeinheit, Dezimalzeichen der Sprache.

    Die Einheit rechnet ``units.from_mm``, die Stellen ``units.decimals_for`` und
    das Dezimalzeichen ``i18n.decimal_separator`` — dieselben Quellen wie Feld
    und Text der Anwendung. Nullen hinten fallen weg, wie man tippt: ``5`` statt
    ``5,00``.
    """
    from app.core.units import decimals_for, from_mm
    from app.i18n import decimal_separator

    shown = from_mm(value_mm, unit)  # type: ignore[arg-type]
    digits = decimals_for(unit)  # type: ignore[arg-type]
    text = f"{shown:.{digits}f}".rstrip("0").rstrip(".")
    if text in ("", "-0"):
        text = "0"
    return text.replace(".", decimal_separator())


class ClickLike(Protocol):
    """Was ``guide_targets.next_click`` zurückgibt (``guide_targets.Click``).

    ``target`` ist der Wortschatzname, ``direction`` die Richtung beim Rollen
    (1 nach unten, -1 nach oben).
    """

    rect: Any
    button: Any
    why: str
    target: Any
    direction: int
    wheel_angle: int


class Ports(Protocol):
    """Die Verbindung zur Oberfläche; am Fenster :class:`QtPorts`, im Test nachgestellt."""

    def next_click(self, name: str) -> ClickLike: ...
    def widget_under(self, point: Any) -> Any: ...
    def covers(self, click: ClickLike, hit: Any) -> bool: ...
    def centre(self, rect: Any) -> Any: ...
    def press(self, widget: Any, point: Any, button: str, *, wheel_angle: int = 120) -> None: ...
    def move(self, point: Any) -> None: ...
    def keys(self, sequence: Any) -> None: ...
    def type_text(self, text: str) -> None: ...
    def describe(self, widget: Any, point: Any = None) -> dict[str, Any]: ...
    def zone_of(self, widget: Any) -> str | None: ...
    def rect_data(self, rect: Any) -> list[int]: ...
    def point_data(self, point: Any) -> list[int]: ...
    def now(self) -> float: ...
    def pending(self) -> bool: ...
    def aim(self, click: ClickLike, point: Any) -> Any: ...


def button_name(button: Any) -> str:
    """Die Taste eines Klicks als Wort: ``left``, ``right``, ``double``, ``wheel_up`` …"""
    if isinstance(button, str):
        return button or "left"
    text = str(getattr(button, "name", button)).lower()
    if "right" in text:
        return "right"
    if "middle" in text:
        return "middle"
    return "left"


def with_modifier(button: str, modifier: str) -> str:
    """Taste und Zusatztaste als ein Wort, wie :meth:`QtPorts.press` es liest: ``ctrl+left``."""
    return f"{modifier}+{button}" if modifier else button


class Walk:
    """Der Weg des Kunden zu einem Ziel: Wegklicks, dann das Ziel — jeder mit Probe.

    Jeder Klick holt ``next_click`` neu, denn erst der vorige deckt den nächsten
    auf. An der Mitte des genannten Rechtecks fragt ``widget_under``, was dort
    liegt; nur wenn es das Ziel des Klicks oder eines seiner Kinder ist, geht der
    Klick dorthin. Jeder Klick steht mit Grund, Ort, Treffer und Zone in
    ``steps`` (Protokollfeld, Prüfpunkt 2, E1, E4).
    """

    def __init__(self, ports: Ports, steps: list[dict[str, Any]], began: float) -> None:
        self.ports = ports
        self.steps = steps
        self.began = began
        #: Die Phase der nächsten Einträge. Der Hauptweg heißt ``weg`` und
        #: ``übernehmen`` (``function_checks.MAIN_PHASES``); nur er zählt für E1 bis E4.
        self.phase = ""
        #: Wird gerufen, bevor ein Klick auf ein Ziel (nicht einen Wegklick) fällt,
        #: mit dessen Namen — so merkt sich der Fall den Fokus vor dem Öffnen.
        self.before_target: Callable[[str], None] | None = None

    def record(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Ein Eintrag in ``steps``, mit Phase und Zeit seit dem Start des Falls."""
        entry = {**entry, "phase": self.phase, "t": self._t()}
        self.steps.append(entry)
        return entry

    def step(
        self,
        name: str,
        button: str = "left",
        *,
        stop_before_target: bool | Callable[[], bool] = False,
    ) -> Step:
        """Ein Schritt, der bis zum Ziel wächst: jeder Wegklick reiht den nächsten ein.

        Geklickt wird erst, wenn der nächste Klick :data:`STABLE_S` lang derselbe
        ist und an seiner Stelle das Ziel liegt (:meth:`stable`): Nach einem
        Aufklappen setzt die Karte ihre Höhen erst in den folgenden
        Ereignisrunden (``fenster.md``, „Wie die Karten ihre Höhe teilen“);
        vorher lag an der genannten Stelle noch die Karte oder die nächste
        Klappe, und die Probe meldete „verdeckt“, wo nur gewartet werden musste.
        Was :data:`COVERED_S` lang deckt, bleibt der Fund.
        """
        counter = {"way": 0}
        way: list[tuple[Any, ...]] = []
        waited: dict[str, str] = {}

        def act(machine: StepMachine) -> None:
            if waited.get("silent"):
                self.record({"target": name, "finding": NO_RESPONSE, "detail": waited["silent"]})
                raise BenchFinding(NO_RESPONSE, name, waited["silent"])
            why = self.click_once(name, button, stop_before_target=stop_before_target)
            if why == TARGET_REASON:
                return
            counter["way"] += 1
            last = self.steps[-1] if self.steps else {}
            way.append((last.get("why"), tuple(last.get("rect") or ())))
            if counter["way"] > MOST_WAY_CLICKS:
                detail = f"nach {MOST_WAY_CLICKS} Wegklicks noch nicht am Ziel"
                same = len(way) - next(
                    (index + 1 for index in range(len(way) - 1, -1, -1) if way[index] != way[-1]),
                    0,
                )
                if way[-1][0] == "rollen" and same > 1:
                    # Zuletzt jedes Mal dasselbe Rollen, und der Weg nennt danach
                    # wieder dasselbe: Die Liste bringt das Ziel nicht ins Bild.
                    detail += (
                        f" — die letzten {same} Klicks rollten an derselben Stelle,"
                        " das Ziel kam nicht ins Bild"
                    )
                raise BenchFinding(NOT_FOUND, name, detail)
            machine.insert(
                [Step(f"weg zu {name}", act, ready=self.stable(name, waited), settle_ms=SETTLE_MS)]
            )

        return Step(f"weg zu {name}", act, ready=self.stable(name, waited), settle_ms=SETTLE_MS)

    def stable(
        self,
        name: str,
        waited: dict[str, str] | None = None,
        *,
        button: Callable[[], Any] | None = None,
    ) -> Callable[[], bool]:
        """Ob der nächste Klick zu ``name`` fallen kann.

        Er muss seit :data:`STABLE_S` derselbe sein, und an seiner Mitte liegt
        das Ziel — oder seit :data:`COVERED_S` etwas anderes; dann meldet der
        Klick „verdeckt“. Ohne Weg wartet er :data:`MISSING_S` — ein Dialog nach
        einer Rechnung, der Startbildschirm nach *Neu* erscheinen später als der
        Klick davor (Review M14) —, dann meldet der Klick „nicht auffindbar“.
        Solange das Fenster sagt, dass etwas kommt (``Ports.pending``), zählt die
        Frist nicht; sagt es das länger als :data:`PENDING_S`, steht in
        ``waited`` der Grund, und der Klick meldet „keine Rückmeldung“.

        Erst den Zeiger öffentlich anfahren, dann in einem späteren Takt neu
        prüfen: Ein Tooltip kann erst durch diese Bewegung verschwinden. Für
        Knöpfe ohne Wortschatznamen löst ``button`` das aktuelle Widget auf.
        Kein Ereignispumpen hier oder im anschließenden ``click_button``:
        Der Automat darf seinen Folgeschritt erst nach dem wirklichen Klick
        betreten. Seine vorhandene Schrittfrist bleibt unverändert.
        """
        seen: dict[str, Any] = {
            "key": None,
            "since": 0.0,
            "covered": None,
            "missing": None,
            "pending": None,
        }

        def ready() -> bool:
            now = self.ports.now()
            target_button = None
            identity: str | int
            try:
                if button is None:
                    click = self.ports.next_click(name)
                    rect = click.rect
                    point = self.ports.aim(click, self.ports.centre(rect))
                    identity = str(click.why)
                else:
                    from PySide6.QtCore import QPoint, QRect
                    from shiboken6 import isValid

                    target_button = button()
                    if (
                        target_button is None
                        or not isValid(target_button)
                        or not target_button.isVisible()
                        or not target_button.isEnabled()
                    ):
                        seen["key"] = seen["covered"] = None
                        return False
                    rect = QRect(target_button.mapToGlobal(QPoint()), target_button.size())
                    point = rect.center()
                    identity = id(target_button)
            except LookupError:
                if self.ports.pending():
                    seen["missing"] = None
                    if seen["pending"] is None:
                        seen["pending"] = now
                    if now - seen["pending"] < PENDING_S:
                        return False
                    if waited is not None:
                        waited["silent"] = (
                            f"nach {PENDING_S:.0f} s sagt das Fenster noch, dass es ermittelt"
                        )
                    return True
                seen["pending"] = None
                if seen["missing"] is None:
                    seen["missing"] = now
                return bool(now - seen["missing"] >= MISSING_S)
            seen["missing"] = seen["pending"] = None
            key = (identity, tuple(self.ports.rect_data(rect)), tuple(self.ports.point_data(point)))
            if key != seen["key"]:
                seen["key"], seen["since"], seen["covered"] = key, now, None
                self.ports.move(point)
                return False
            if now - seen["since"] < STABLE_S:
                return False
            hit = self.ports.widget_under(point)
            matches = hit is not None and (
                (hit is target_button or target_button.isAncestorOf(hit))
                if target_button is not None
                else self.ports.covers(click, hit)
            )
            if matches:
                seen["covered"] = None
                return True
            if seen["covered"] is None:
                seen["covered"] = now
            return bool(now - seen["covered"] >= COVERED_S)

        return ready

    def click_once(
        self,
        name: str,
        button: str = "left",
        *,
        stop_before_target: bool | Callable[[], bool] = False,
    ) -> str:
        """Ein Klick auf dem Weg zu ``name``; gibt seinen Grund zurück."""
        try:
            click = self.ports.next_click(name)
        except LookupError as error:
            self.record({"target": name, "finding": NOT_FOUND, "detail": str(error)})
            raise BenchFinding(NOT_FOUND, name, str(error)) from error
        point = self.ports.aim(click, self.ports.centre(click.rect))
        hit = self.ports.widget_under(point)
        why = str(click.why)
        if why == "rollen":
            pressed = "wheel_up" if int(getattr(click, "direction", 1) or 1) < 0 else "wheel_down"
        elif why == TARGET_REASON:
            pressed = button
        else:
            pressed = button_name(click.button)
        record = self.record(
            {
                "target": name,
                "why": why,
                "button": pressed,
                "rect": self.ports.rect_data(click.rect),
                "point": self.ports.point_data(point),
                "widget_at": self.ports.describe(hit, point) if hit is not None else None,
                "hit": hit is not None and self.ports.covers(click, hit),
                "zone": self.ports.zone_of(hit) if hit is not None else None,
                "decision": False,
            }
        )
        if not record["hit"]:
            record["finding"] = COVERED
            raise BenchFinding(
                COVERED,
                name,
                f"an {record['point']} liegt {record['widget_at']}, nicht das Ziel des Klicks",
            )
        if why == TARGET_REASON and (
            stop_before_target() if callable(stop_before_target) else stop_before_target
        ):
            # Die Fläche einer Soforthandlung muss vor ihrer Wirkung stehen.
            # Wegklicks und Trefferprüfung bleiben vollständig; nur der letzte
            # Klick entfällt, und das Protokoll behauptet keinen solchen.
            record["button"] = None
            record["detail"] = "Ziel vor der Handlung erreicht"
            return why
        if why == TARGET_REASON and self.before_target is not None:
            self.before_target(name)
        angle = int(getattr(click, "wheel_angle", 120)) if why == "rollen" else 120
        if why == "rollen":
            record["wheel_angle"] = angle
        if angle != 120:
            self.ports.press(hit, point, record["button"], wheel_angle=angle)
        else:
            self.ports.press(hit, point, record["button"])
        return why

    def _t(self) -> float:
        return round(self.ports.now() - self.began, 4)


def click_button(ports: Any, walker: Walk, button: Any, label: str) -> bool:
    """Ein Knopf ohne Wortschatznamen — Rückfrage, Starttor —, angeklickt mit Probe.

    W führt für diese Knöpfe keinen Namen (Bericht: Lücke für W). Geklickt wird
    trotzdem nur, wenn ``widget_under`` an der Mitte den Knopf trifft; der
    Klick steht wie jeder andere in ``steps``, mit ``label`` als Ziel. ``False``
    heißt: verdeckt, nicht geklickt — der Eintrag trägt den Fund.
    """
    from PySide6.QtCore import QPoint, QRect
    from shiboken6 import isValid

    if button is None or not isValid(button) or not button.isVisible() or not button.isEnabled():
        raise RuntimeError(
            f"{label}: Knopf nach der Zielprüfung nicht bedienbar; Ziel neu ermitteln"
        )

    rect = QRect(button.mapToGlobal(QPoint(0, 0)), button.size())
    point = rect.center()
    hit = ports.widget_under(point)
    record = walker.record(
        {
            "target": label,
            "why": TARGET_REASON,
            "button": "left",
            "rect": ports.rect_data(rect),
            "point": ports.point_data(point),
            "widget_at": ports.describe(hit, point) if hit is not None else None,
            "hit": hit is not None and (hit is button or button.isAncestorOf(hit)),
            "zone": None,
            "decision": False,
        }
    )
    if not record["hit"]:
        record["finding"] = COVERED
        record["detail"] = f"an {record['point']} liegt {record['widget_at']}, nicht {label}"
        return False
    ports.press(hit, point, "left")
    return True


def way_clicks(steps: Sequence[Mapping[str, Any]]) -> int:
    """Wie viele Wegklicks ein Weg gekostet hat (``why`` nicht ``ziel``)."""
    return sum(1 for step in steps if step.get("why") in WAY_REASONS)


def place_of(steps: Sequence[Mapping[str, Any]], target: str) -> dict[str, Any]:
    """Wo das Ziel einer Zeile steht, aus ihrem Hauptweg (Prüfpunkt 1, 17; Schema ``place``).

    ``where`` ist einer aus ``function_checks.PLACES``: ``kontext`` bei einem
    Rechtsklick auf dem Weg, ``menue`` bei einem Menü, ``werkzeugleiste`` am
    Kopf des Fensters, sonst ``karte``. ``path`` sind die sichtbaren Texte der
    Klicks bis zum Ziel. Kam der Weg nicht an, steht der Grund in ``error``.
    Gelesen wird der ganze Hauptweg: Wirkt der Klick auf das Ziel selbst, fällt
    er in der Phase Übernehmen (``FunctionFlow.phase_main``).
    """
    walked = [step for step in steps if step.get("phase") in (PATH_PHASE, APPLY_PHASE)]
    upto: list[Mapping[str, Any]] = []
    for step in walked:
        upto.append(step)
        if step.get("target") == target and (
            step.get("why") == TARGET_REASON or step.get("finding")
        ):
            break
    final = upto[-1] if upto else None
    if final is None or final.get("target") != target:
        return {"where": None, "path": [], "error": "der Hauptweg erreichte das Ziel nicht"}
    if final.get("finding") or not final.get("hit"):
        return {
            "where": None,
            "path": [],
            "error": str(final.get("detail") or final.get("finding")),
        }
    clicks = [step for step in upto if step.get("why")]
    reasons = {str(step.get("why")) for step in clicks}
    zones = [str(step.get("zone") or "") for step in clicks if step.get("target") == target]
    if any(str(step.get("button", "")).endswith("right") for step in clicks):
        where = "kontext"
    elif reasons & {"menue", "untermenue"} or "menue" in zones:
        where = "menue"
    elif zones and zones[0] == "kopf":
        where = "werkzeugleiste"
    else:
        where = "karte"
    assert where in PLACES
    path = [
        str((step.get("widget_at") or {}).get("text") or step.get("target"))
        for step in clicks
        if step.get("target") == target
    ]
    return {"where": where, "path": path, "error": None}


class QtPorts:
    """Die Ports am echten Fenster: ``guide_targets`` und ``QTest``-Ereignisse.

    Ereignisse gehen an das Widget, das an der Stelle liegt — wie die Maus des
    Kunden. Tasten gehen an das Widget mit dem Fokus, wie die Tastatur.
    """

    def __init__(self, window: Any, began: float) -> None:
        self.window = window
        self.began = began

    def next_click(self, name: str) -> ClickLike:
        from app.ui import guide_targets

        return guide_targets.next_click(self.window, name)  # type: ignore[attr-defined,no-any-return]

    def widget_under(self, point: Any) -> Any:
        from app.ui import guide_targets

        return guide_targets.widget_under(point)  # type: ignore[attr-defined]

    def covers(self, click: ClickLike, hit: Any) -> bool:
        """Ob der Treffer der Probe das ist, was der Klick meint — das Ziel oder ein Kind davon.

        ``Click`` nennt eine Fläche, kein Widget. Ein Behälter zählt nur, wenn er
        der Behälter **dieses** Ziels ist (Review S2, :meth:`receiver`): beim
        Rollen die Liste der Zeile oder die Rollfläche mit genau diesem Rechteck
        oder diesem sichtbaren Teil (so nennt W sie), beim Reiter die
        Reiterleiste, bei Menütitel, Untermenü und Menüzeile das Menü oder die
        Leiste mit genau dieser Zeile, bei einer Zeile ihre Liste, ihr Baum oder
        der Katalog, bei ``view:``, einem Griff und ``viewport`` die Ansicht,
        bei einer Operation oder einem Befehl der Ort, an dem
        ``guide_targets.next_click`` sie nennt (:meth:`shows_command`), sonst
        das Widget hinter dem Namen (``widget_for``, auch eine Leiste über der
        Ansicht) oder das mit genau diesem Rechteck. Liegt an der Stelle etwas
        anderes — eine Liste, eine Karte, die Ansicht, ein Dialog —, ist das
        der Fund „verdeckt“.
        """
        from PySide6.QtCore import QPoint, QRect

        kind, receiver = self.receiver(click)
        rect = click.rect
        if receiver is not None:
            return bool(hit is receiver or receiver.isAncestorOf(hit))
        if kind == "befehl":
            return self.shows_command(click, hit)
        probe = hit
        while probe is not None:
            area = QRect(probe.mapToGlobal(QPoint(0, 0)), probe.size())
            if kind == "rechteck" and area == rect:
                return True
            if kind == "rollfläche" and _scrolls(probe) and rect in (area, _shown(probe)):
                return True
            if kind == "menüzeile" and _carries_line(probe, rect):
                return True
            if (
                kind not in ("rechteck", "rollfläche", "menüzeile")
                and isinstance(probe, kind)
                and area.contains(rect.center())
            ):
                return True
            if probe.isWindow():
                return False
            probe = probe.parentWidget()
        return False

    def receiver(self, click: ClickLike) -> tuple[Any, Any]:
        """Wer diesen Klick empfangen soll: ``(Art, Widget)``.

        Ein Widget, wenn es eines gibt; sonst eine Art: ``"rechteck"`` — das
        Widget mit genau dem Rechteck des Klicks (Klappe) —, ``"rollfläche"`` —
        eine Rollfläche mit genau diesem Rechteck oder sichtbaren Teil —,
        ``"menüzeile"`` — ein Menü oder die Menüleiste mit einer Zeile genau an
        diesem Rechteck —, ``"befehl"`` (:meth:`shows_command`) oder die Klasse
        der Reiterleiste. Die Art folgt dem, was ``next_click`` je Zielart
        nennt (Review N1): Ein Ziel ohne eigenes Widget ist kein Rechteck.
        """
        from PySide6.QtWidgets import QTabBar

        from app.ui import guide_targets

        name = str(getattr(click, "target", "") or "")
        why = str(click.why)
        kind = name.partition(":")[0]
        if why == "rollen":
            # Gerollt wird die Liste der Zeile; sonst die Rollfläche, deren
            # sichtbaren Teil der Klick nennt (W nennt dort das Sichtbare).
            view = self.row_view(kind, name)
            return ("rollfläche", None) if view is None else (None, view)
        if why == "klappe":
            return "rechteck", None
        if why == "reiter":
            return QTabBar, None
        if why in ("menue", "untermenue") or kind in ("menu", "history"):
            return "menüzeile", None
        view = self.row_view(kind, name)
        if view is not None:
            return None, view
        if why != TARGET_REASON:
            return "rechteck", None
        if kind in ("command", "operation"):
            return "befehl", None
        try:
            return None, guide_targets.widget_for(self.window, name)
        except LookupError:
            return "rechteck", None

    def shows_command(self, click: ClickLike, hit: Any) -> bool:
        """Ob der Treffer eine Operation oder einen Befehl dort zeigt, wo ``next_click`` sie nennt.

        In dieser Folge sucht W sie (``guide_targets._command_click``): ihre Zeile
        in der Trefferliste der Suche, ihr Knopf in der Karte, das Werkzeug eines
        ``command:tool.*``, ein Knopf der Werkzeugleiste mit genau dem Rechteck,
        sonst ihre Zeile in einem offenen Menü oder der Menüleiste. Liegt die
        Trefferliste an der Stelle, zählt nur die Zeile **dieses** Namens.
        """
        from PySide6.QtCore import QPoint, QRect, Qt

        from app.ui import guide_targets

        name = str(getattr(click, "target", "") or "")
        kind, _separator, entry = name.partition(":")
        rect = click.rect
        operations = self.window.selection_operations
        hits = operations.hits
        if hits.isVisible() and (hit is hits or hits.isAncestorOf(hit)):
            row = hits.itemAt(hits.viewport().mapFromGlobal(rect.center()))
            return row is not None and row.data(Qt.ItemDataRole.UserRole) == entry
        places = [operations.button_for(entry)]
        if kind == "command" and entry.startswith("tool."):
            with contextlib.suppress(LookupError):
                places.append(
                    guide_targets.widget_for(self.window, f"tool:{entry.removeprefix('tool.')}")
                )
        for place in places:
            if (
                place is not None
                and place.isVisible()
                and (hit is place or place.isAncestorOf(hit))
            ):
                return True
        probe = hit
        while probe is not None:
            if QRect(probe.mapToGlobal(QPoint(0, 0)), probe.size()) == rect:
                return True
            if _carries_line(probe, rect):
                return True
            if probe.isWindow():
                return False
            probe = probe.parentWidget()
        return False

    def row_view(self, kind: str, name: str) -> Any:
        """Das Widget, das ein Ziel ohne eigenes Widget trägt, oder ``None``.

        Die Liste oder der Baum einer Zeile, die Liste des offenen Katalogs für
        ``part:``, die Ansicht für ``view:``, ``view.edge:``, ``viewport`` und einen Griff im
        Bild; eine Leiste über der Ansicht (``handle:bar.*``) ist ihr eigenes
        Widget und liegt in der Werkzeugzeile, nicht in der Ansicht (Review N1).
        """
        from PySide6.QtWidgets import QApplication

        from app.ui import guide_targets
        from app.ui.catalog import PartCatalog

        window = self.window
        if window is None:
            return None
        if kind in ("view", "view.edge") or name == "viewport":
            return window.viewport
        if kind == "handle":
            try:
                return guide_targets.widget_for(window, name)
            except LookupError:
                return window.viewport
        if kind == "part":
            catalog = QApplication.activeModalWidget()
            return catalog.list if isinstance(catalog, PartCatalog) else None
        if kind == "tree.row":
            return window.object_tree.tree
        if kind == "history.row" or name == "history.last":
            return window.history_panel.list
        if kind == "start.recent":
            return window.start_screen.recent_list
        if kind == "finding":
            return window.report.list
        return None

    def centre(self, rect: Any) -> Any:
        return rect.center()

    def press(self, widget: Any, point: Any, button: str, *, wheel_angle: int = 120) -> None:
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        if wheel_angle <= 0:
            raise ValueError("Der Radwinkel muss positiv sein (Achtelgrad).")
        local = widget.mapFromGlobal(point)
        modifiers = Qt.KeyboardModifier.NoModifier
        held, plus, rest = button.rpartition("+")
        if plus:
            button = rest
            for name in held.split("+"):
                modifiers |= {
                    "ctrl": Qt.KeyboardModifier.ControlModifier,
                    "shift": Qt.KeyboardModifier.ShiftModifier,
                    "alt": Qt.KeyboardModifier.AltModifier,
                }[name]
        top = widget.window()
        if top is not QApplication.activeWindow() and top.windowType() != Qt.WindowType.Popup:
            # Ein Klick des Kunden holt sein Fenster nach vorn; ``QTest`` schickt
            # nur das Ereignis. Ohne das blieb der Fokus nach dem Klick in ein
            # Feld des nichtmodalen Operationsdialogs im Hauptfenster, und
            # getippt wurde nicht (Probelauf F-34).
            top.activateWindow()
            # Am echten Schirm kommt die Aktivierung Runden später, und mit ihr
            # setzt das Fenster seinen alten Fokus — erst danach fällt der Klick.
            for _round in range(50):
                QApplication.processEvents()
                if QApplication.activeWindow() is top:
                    break
                time.sleep(0.01)
            QApplication.processEvents()
        QTest.mouseMove(widget, local)
        if button in ("wheel_up", "wheel_down"):
            if not hasattr(QTest, "wheelEvent"):
                raise RuntimeError(
                    "Der Prüfstand braucht QTest.wheelEvent ab Qt 6.8. "
                    "Die gepinnte Umgebung über tools/check_env.py prüfen und "
                    "mit --install gegen constraints.txt herstellen."
                )
            step = wheel_angle if button == "wheel_up" else -wheel_angle
            # Der Qt-Eingabepfad reicht ignorierte Radereignisse an die Eltern
            # weiter. Direktes sendEvent bleibt dagegen beim getroffenen Kind.
            handle = top.windowHandle()
            QTest.wheelEvent(
                handle, handle.mapFromGlobal(point), QPoint(0, step), stateKey=modifiers
            )
            return
        if button == "double":
            # Ein Doppelklick des Kunden ist erst ein Klick, dann der zweite
            # Druck: ``mouseDClick`` allein schickt nur das Doppelklickereignis,
            # und eine Liste meldet ``itemDoubleClicked`` nur an der Zeile, die
            # vorher gedrückt war — kein Doppelklick des Prüfstands öffnete je
            # einen Verlaufsschritt (Probelauf F-34, Prüfpunkt 12).
            QTest.mouseClick(widget, Qt.MouseButton.LeftButton, modifiers, local)
            QTest.mouseDClick(widget, Qt.MouseButton.LeftButton, modifiers, local)
            # Danach lässt der Kunde die Taste los; ``mouseDClick`` tut das nicht.
            # Ohne Loslassen hielt Qt die linke Taste bis zum nächsten Klick für
            # gedrückt: Jede Bewegung bis dahin war ein Zug ohne Enter und Leave,
            # und ein Tooltip blieb über dem nächsten Ziel stehen (FD-83). Wie bei Qt
            # empfängt das Loslassen das gedrückte Widget oder, wenn der
            # Doppelklick es abgebaut hat, das unter dem Zeiger.
            from shiboken6 import isValid

            release = widget if isValid(widget) else self.widget_under(point)
            if release is not None:
                QTest.mouseRelease(
                    release, Qt.MouseButton.LeftButton, modifiers, release.mapFromGlobal(point)
                )
            return
        mouse = {
            "left": Qt.MouseButton.LeftButton,
            "right": Qt.MouseButton.RightButton,
            "middle": Qt.MouseButton.MiddleButton,
        }[button]
        QTest.mouseClick(widget, mouse, modifiers, local)
        if button == "right":
            # Ein Rechtsklick des Kunden bringt nach dem Loslassen auch das
            # Kontextmenüereignis; QTest schickt nur die Maus (Probelauf,
            # Befund B: ``menu:history.edit`` fand nie ein offenes Menü).
            # Öffnet der Empfänger sein Menü mit ``exec()``, kehrt das erst
            # nach dessen Ende zurück — der Automat läuft darin weiter.
            from PySide6.QtGui import QContextMenuEvent

            context = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local, point, modifiers)
            QApplication.sendEvent(widget, context)

    def move(self, point: Any) -> None:
        """Die Maus an eine Stelle, ohne zu klicken — Überfahren für I1."""
        from PySide6.QtTest import QTest

        hit = self.widget_under(point)
        if hit is not None:
            QTest.mouseMove(hit, hit.mapFromGlobal(point))

    def keys(self, sequence: Any) -> None:
        """Eine Tastenfolge an das Fokuswidget, sonst an das Fenster."""
        from PySide6.QtGui import QKeySequence
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        keys = sequence if isinstance(sequence, QKeySequence) else QKeySequence(sequence)
        for index in range(keys.count()):
            combination = keys[index]
            target = QApplication.focusWidget() or QApplication.activeModalWidget() or self.window
            QTest.keyClick(target, combination.key(), combination.keyboardModifiers())

    def type_text(self, text: str) -> None:
        """Tippt ``text`` Zeichen für Zeichen in das Widget mit dem Fokus, wie eine Tastatur.

        ``QTest.keyClicks`` kennt nur ASCII: An ö, ß oder € bricht Qt mit einem
        ASSERT in ``qasciikey.cpp`` den ganzen Prozess ab, ohne eine Zeile in
        ``stderr.log`` (Probelauf, Befund A: die Suchprobe „Bohrung vergrößern“).
        Jedes Zeichen geht deshalb als Tastendruck mit seinem Text hinaus — mit
        der Taste, die Qt für ein Zeichen aus Latin-1 kennt (der Code des
        Großbuchstabens, ß selbst), sonst ``Key_unknown``; eingefügt wird der Text.
        """
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        for character in text:
            target = QApplication.focusWidget() or self.window
            upper = character.upper()
            code = ord(upper) if len(upper) == 1 and ord(upper) < 256 else ord(character)
            try:
                key = Qt.Key(code) if code < 256 else Qt.Key.Key_unknown
            except ValueError:
                key = Qt.Key.Key_unknown
            QTest.sendKeyEvent(
                QTest.KeyAction.Click, target, key, character, Qt.KeyboardModifier.NoModifier
            )

    def describe(self, widget: Any, point: Any = None) -> dict[str, Any]:
        """Klasse, Name, Kennzeichen und der sichtbare Text an der Stelle des Klicks.

        Am Text hängt ``place.path``: Ein Menü nennt die Zeile unter dem Zeiger,
        eine Reiterleiste den Reiter, eine Liste den Eintrag, ein Knopf sich selbst.
        """
        from PySide6.QtWidgets import QAbstractItemView, QMenu, QMenuBar, QTabBar

        from app.core.guides import TARGET_PROPERTY

        if widget is None:
            return {}
        text = ""
        local = widget.mapFromGlobal(point) if point is not None else None
        if isinstance(widget, (QMenu, QMenuBar)) and local is not None:
            action = widget.actionAt(local)
            text = action.text() if action is not None else ""
        elif isinstance(widget, QTabBar) and local is not None:
            index = widget.tabAt(local)
            text = widget.tabText(index) if index >= 0 else ""
        elif isinstance(widget.parentWidget(), QAbstractItemView) and local is not None:
            view = widget.parentWidget()
            index = view.indexAt(local)
            text = str(index.data() or "") if index.isValid() else ""
        elif callable(getattr(widget, "text", None)):
            text = str(widget.text() or "")
        mark = widget.property(TARGET_PROPERTY)
        return {
            "class": type(widget).__name__,
            "object_name": widget.objectName(),
            "mark": str(mark) if mark else "",
            "text": text.replace("&", ""),
        }

    def zone_of(self, widget: Any) -> str | None:
        from app.ui import guide_targets

        if widget is None:
            return None
        zone = guide_targets.zone_of(self.window, widget)  # type: ignore[attr-defined]
        return str(zone) if zone else None

    def rect_data(self, rect: Any) -> list[int]:
        return [rect.x(), rect.y(), rect.width(), rect.height()]

    def point_data(self, point: Any) -> list[int]:
        return [point.x(), point.y()]

    def now(self) -> float:
        return time.perf_counter()

    def aim(self, click: ClickLike, point: Any) -> Any:
        """Wohin der Kunde bei einem Feld klickt: in sein Eingabefeld, nicht in den Behälter.

        Ein Zahlenfeld des Operationsdialogs (``ValueField``) ist breiter als
        sein Kästchen; die Mitte des Behälters lag am echten Schirm im leeren Teil
        daneben, und der Fokus blieb im Rollbereich des Dialogs (Probelauf F-34).
        """
        from PySide6.QtCore import QPoint, QRect
        from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QLineEdit

        from app.ui import guide_targets

        name = str(getattr(click, "target", "") or "")
        if str(getattr(click, "why", TARGET_REASON)) != TARGET_REASON:
            return point
        if name.partition(":")[0] not in ("field", "feature.field", "measure.field"):
            return point
        try:
            holder = guide_targets.widget_for(self.window, name)
        except LookupError:
            return point
        kinds = (QAbstractSpinBox, QComboBox, QLineEdit)
        if isinstance(holder, kinds):
            return point
        boxes = [box for kind in kinds for box in holder.findChildren(kind) if box.isVisible()]
        hit = self.widget_under(point)
        if not boxes or any(hit is box or box.isAncestorOf(hit) for box in boxes):
            return point
        return QRect(boxes[0].mapToGlobal(QPoint(0, 0)), boxes[0].size()).center()

    def pending(self) -> bool:
        """Ob das Fenster sagt, dass gleich etwas kommt (``function_surface.pending``)."""
        from tools.function_surface import pending

        return self.window is not None and pending(self.window)


def _scrolls(widget: Any) -> bool:
    """Ob ein Widget eine Rollfläche ist oder deren Sichtfläche."""
    from PySide6.QtWidgets import QAbstractScrollArea

    parent = widget.parentWidget()
    return isinstance(widget, QAbstractScrollArea) or isinstance(parent, QAbstractScrollArea)


def _carries_line(widget: Any, rect: Any) -> bool:
    """Ob ``widget`` ein Menü oder die Menüleiste ist und eine Zeile genau an ``rect`` trägt."""
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QMenu, QMenuBar

    if not isinstance(widget, (QMenu, QMenuBar)):
        return False
    for action in widget.actions():
        place = widget.actionGeometry(action)
        if not place.isEmpty() and QRect(widget.mapToGlobal(place.topLeft()), place.size()) == rect:
            return True
    return False


def _shown(widget: Any) -> Any:
    """Der sichtbare Teil eines Widgets, global — so nennt W die Fläche zum Rollen.

    Dieselbe Rechnung wie W (``guide_targets.unclipped``): was die Eltern nicht
    abschneiden. ``visibleRegion`` zog den Inhalt der Rollfläche ab, und der füllt
    ihre Sichtfläche — der Teil war leer oder ein Randstreifen.
    """
    from app.ui import guide_targets

    return guide_targets.unclipped(widget)


def focus_check(field: Any, target: str) -> None:
    """Ob der Fokus im Feld des Ziels liegt — sonst wird nicht getippt (Review M13).

    Im Feld heißt: das Feld selbst, ein Kind davon (die Textzeile eines
    Zahlenfelds) oder sein Fokusvertreter. Sonst ein Fehler mit dem Namen des
    Widgets, das den Fokus hat.
    """
    from PySide6.QtWidgets import QApplication

    from tools.function_capture import name_of

    focus = QApplication.focusWidget()
    if field is None:
        raise RuntimeError(f"{target}: kein Feld hinter dem Namen — nicht getippt")
    inside = focus is not None and (
        focus is field or field.isAncestorOf(focus) or field.focusProxy() is focus
    )
    if not inside:
        holder = f"{type(focus).__name__} „{name_of(focus)}“" if focus is not None else "nichts"
        raise RuntimeError(f"{target}: der Fokus liegt auf {holder}, nicht im Feld — nicht getippt")
