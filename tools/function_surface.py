"""Welche Fläche eine Zeile zeigt, was sie im Bild trägt und was ihre Handlung tat (D0-P2, RM-737).

Die Fläche einer Zeile folgt der Art ihres Ziels (:func:`surface_for`): der
offene Dialog, sonst bei einer Befundhandlung und beim Bericht der Prüfbericht,
bei einem Werkzeug seine Leiste über der Ansicht, sonst die Seite oder der
Abschnitt der Karte, in der das Ziel steht (FD-130).
Vorher war es für jede Zeile ohne Dialog die Karte der Auswahl oder das ganze
Hauptfenster (Probelauf F-30). Ein Bild nimmt jedes sichtbare Fenster der Zeile
auf, auch den nichtmodalen Operationsdialog (:func:`windows_to_picture`, F-31).

Dazu, was sonst nur der Kunde sähe: ob das Fenster noch ermittelt, was gleich
dasteht (:func:`pending`, F-20), welche Treffer der Suche dieselbe Funktion
meinen (:func:`search_names`, F-27), welche Namen der Szene gehören
(:func:`scene_names`, F-10), ob eine Absage die Lizenzgrenze war
(:func:`licence_refusal`, F-35) und welche Zeile keinen Weg zu ihrer Fläche
hat (:func:`without_way`, F-32). Gelesen wird nur, was die Oberfläche zeigt
oder öffentlich führt — kein privater Name, keine Abkürzung (``function_guard``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

#: Zielarten, deren Fläche der Prüfbericht ist: der Befund, seine Handlung und
#: der Bericht selbst mit seinen Teilen.
REPORT_KINDS: Final[frozenset[str]] = frozenset({"finding", "finding.action"})

#: Zielarten, deren Fläche nur über einen benannten Weg aufgeht — ein Dialog
#: einer Klasse, ein rohes Meldungsfenster. Ohne ``route`` in der Spezifikation
#: kennt der Prüfstand den Klick nicht, der sie öffnet (F-32).
OPENED_ELSEWHERE: Final[frozenset[str]] = frozenset({"dialog", "meldung", "message"})

#: Der Satz, den das Merkmalfenster zeigt, solange es seine Handlungen im
#: Arbeiter ermittelt (``FeaturePanel.show_pending``) — als Message-ID.
PENDING_NOTE: Final = "Die Handlungen werden ermittelt …"


def _shown(window: Any, name: str) -> Any | None:
    """Das sichtbare Widget hinter einem Wortschatznamen, sonst ``None``."""
    from app.ui import guide_targets

    try:
        widget = guide_targets.widget_for(window, name)
    except LookupError:
        return None
    return widget if widget is not None and widget.isVisible() else None


def open_dialog(window: Any) -> Any | None:
    """Offene Bedienfläche, auch ein nichtmodaler Generator ohne Operationswortschatz."""
    from PySide6.QtWidgets import QApplication

    dialog = _shown(window, "dialog")
    if dialog is not None:
        return dialog
    opened = windows_to_picture(window)
    active = QApplication.activeWindow()
    if active in opened:
        return active
    if len(opened) > 1:
        raise RuntimeError("Mehrere offene Bedienflächen ohne eindeutiges aktives Fenster")
    return opened[0] if opened else None


def immediate_feature(window: Any, target: str) -> bool:
    """Ob die sichtbare Merkmalshandlung sofort wirkt statt ihre Felder aufzuklappen."""
    heading = _shown(window, target)
    return heading is not None and not heading.isCheckable()


#: Ziele ohne Art, deren Klick schon die Handlung ist: die erste Handlung des
#: Prüfberichts zum gewählten Befund (``guide_targets._report_action``).
AT_ONCE_TARGETS: Final[frozenset[str]] = frozenset({"report.action"})


def acts_at_once(window: Any, target: str) -> bool:
    """Ob der Klick auf das Ziel schon die Handlung ausführt, statt eine Fläche zu öffnen.

    Dann steht ihre Fläche **vor** dem Klick (FD-37, FD-115): Befundhandlungen
    und die erste Handlung des Berichts wirken mit dem Klick, eine Operation
    ohne Werte ebenso — ``MainWindow.run_operation`` fragt dann nichts —, eine
    Merkmalshandlung, deren Kopf nicht aufklappt (:func:`immediate_feature`).
    Entschieden an der Art der Handlung; vorher am Präfix des Ziels, und
    *Objekt entfernen* wurde nach seiner Wirkung gemessen.
    """
    from app.core.registry import REGISTRY

    kind, _separator, rest = target.partition(":")
    if kind == "feature":
        return immediate_feature(window, target)
    if kind == "operation":
        return REGISTRY.has(rest) and not REGISTRY.get(rest).params.spec()
    return kind == "finding.action" or target in AT_ONCE_TARGETS


def feature_in_view(window: Any, target: str) -> bool:
    """Die Zielhandlung steht sichtbar im Bild, auch ohne Eingaben in der Sprachspezifikation."""
    return (
        target.startswith("feature:")
        and op_in_view(window) == target.partition(":")[2]
        and _shown(window, "measure.apply") is not None
    )


def surface_for(window: Any, target: str) -> Any:
    """Die Fläche, die eine Zeile mit diesem Ziel zeigt (F-30).

    Ein offener Dialog geht vor — ihn hat die Zeile geöffnet. Ein Ziel
    ``dialog:<klasse>`` ist das Fenster dieser Klasse. Sonst nach der Zielart:
    Befund, Befundhandlung und ``report*`` der Prüfbericht, ``tool:<name>`` die
    Leiste des Werkzeugs (``handle:bar.<name>``), eine Merkmalshandlung ihre
    Zeile oder Maßgruppe; jedes andere Ziel die Fläche um den Ort, an dem es
    steht (:func:`place_of`, :func:`surface_around`). Die Karte der Auswahl ist
    es nur, wenn das Ziel dort steht: Vorher fiel jedes andere Ziel auf sie
    zurück, und die Parameterleiste wurde an der Auswahlkarte gemessen (FD-130).
    """
    kind, _separator, rest = target.partition(":")
    if kind == "dialog":
        own = _shown(window, target)
        if own is not None:
            return own
    dialog = open_dialog(window)
    if dialog is not None:
        return dialog
    if kind in REPORT_KINDS or target == "report" or target.startswith("report."):
        report = _shown(window, "report")
        if report is not None:
            return report
    if kind == "tool":
        bar = _shown(window, f"handle:bar.{rest}") or _shown(window, "tools")
        if bar is not None:
            return bar
    if kind == "feature":
        # Nur die Maßgruppe dieser Handlung gehört zur Zeile. Daneben kann
        # eine andere Handlung im Bild bleiben, während ihre Zeile aufgeht.
        if op_in_view(window) == rest:
            accept = _shown(window, "measure.apply")
            if accept is not None:
                return accept.parentWidget()
        heading = _shown(window, target)
        if heading is not None:
            return heading.parentWidget()
    if kind in SELECTION_KINDS:
        # Steht ihr Kopf gerade nicht da, bleibt ihr Ort das Merkmalfenster.
        return _shown(window, "selection") or window
    place = place_of(window, target)
    return window if place is None else surface_around(window, place)


#: Zielarten, die im Merkmalfenster der Auswahlkarte stehen.
SELECTION_KINDS: Final[frozenset[str]] = frozenset({"feature", "edge", "feature.field"})

#: Wo ein Ziel ohne eigenes Widget steht: Art → Ziel, dessen Widget der Ort ist.
#: Eine Zeile steht in ihrer Liste, ein Eintrag im Kontextmenü des Verlaufs am
#: Verlauf, eine Stelle im Bild in der Ansicht (FD-130).
TARGET_PLACES: Final[dict[str, str]] = {
    "tree.row": "tree",
    "history.row": "history",
    "history": "history",
    "history.last": "history",
    "finding": "report",
    "view": "viewport",
    "view.edge": "viewport",
    "handle": "viewport",
}


def place_of(window: Any, target: str) -> Any | None:
    """Das Widget, an dem das Ziel steht: sein eigenes, seine Liste, die Leiste seiner Zeile.

    Eine Operation oder ein Befehl steht als Knopf in der Auswahlkarte
    (``SelectionOperationsPanel.button_for``) oder, ohne sichtbaren Knopf, als
    Zeile der Menüleiste — wie ``guide_targets.next_click`` sie sucht. ``None``,
    wenn das Ziel gerade nirgends steht.
    """
    kind, _separator, rest = target.partition(":")
    if kind in ("command", "operation"):
        button = window.selection_operations.button_for(rest)
        return button if button is not None and button.isVisible() else window.menuBar()
    if kind == "menu":
        return window.menuBar()
    own = _shown(window, target)
    home = TARGET_PLACES.get(kind) or TARGET_PLACES.get(target)
    return own if own is not None or home is None else _shown(window, home)


def surface_around(window: Any, widget: Any) -> Any:
    """Die Fläche um ein Widget: die Seite oder der Abschnitt seiner Karte, sonst seine Leiste.

    Eine Karte (``overlay.CARD``) trägt Reiter — dann ist es die Seite, auf der
    das Widget steht (Auswahl, Prüfbericht, Chat) — oder Abschnitte (Objekte,
    Parameter, Verlauf), dann dieser Abschnitt samt Kopf. Außerhalb einer
    Karte die Werkzeug-, Menü- oder Statusleiste um das Widget, auf dem
    Startbildschirm dieser, sonst das Widget selbst.
    """
    from PySide6.QtWidgets import QMenuBar, QStatusBar, QTabWidget, QToolBar

    from app.ui.overlay import CARD

    chain: list[Any] = []
    node = widget
    while node is not None and node is not window:
        if node.objectName() == CARD:
            if not chain:
                return node
            top = chain[-1]
            if isinstance(top, QTabWidget):
                # Die Seite, wie die Reiter sie führen (``DetachableTabs`` hüllt sie ein).
                pages = (top.widget(index) for index in range(top.count()))
                return next(
                    (
                        page
                        for page in pages
                        if page is not None and (page is widget or page.isAncestorOf(widget))
                    ),
                    top,
                )
            return top
        if isinstance(node, (QToolBar, QMenuBar, QStatusBar)):
            return node
        chain.append(node)
        node = node.parentWidget()
    start = getattr(window, "start_screen", None)
    if start is not None and (widget is start or start.isAncestorOf(widget)):
        return start
    return widget


def surface_parts(window: Any, target: str, root: Any) -> tuple[Any, ...]:
    """Eigene Merkmalzeile samt sichtbarem Footer; keine fremde Maßgruppe.

    Der Footer steht außerhalb der rollenden Zeile. Nur deren aufgeklappter
    Kopf ordnet ihn dieser Handlung zu; die Maßgruppe enthält alles selbst.
    """
    if target.startswith("feature:"):
        heading = _shown(window, target)
        if (
            heading is not None
            and heading.parentWidget() is root
            and heading.isCheckable()
            and heading.isChecked()
        ):
            accept = _shown(window, "feature.apply")
            if accept is not None:
                footer = accept.parentWidget()
                if footer is not root and not root.isAncestorOf(footer):
                    return root, footer
    return (root,)


#: Woher Zeilen stammen, deren Fläche selbst eine Meldung ist (``function_list``).
MESSAGE_SOURCES: Final[frozenset[str]] = frozenset({"meldungsfenster", "startablauf"})


def own_surface(row: Mapping[str, Any], widget: Any) -> bool:
    """Ob ein offenes Fenster die Bedienfläche der Zeile ist (F-26).

    Eine Meldung — roh oder im Hausstil (``MessageDialog``) — und eine Rückfrage
    sind es nie, außer die Zeile ist diese Meldung (``message:<sache>``, Zeilen
    der Meldungsfenster und des Startablaufs) oder dieser Dialog
    (``dialog:<klasse>``). Sonst hieße die Fehlermeldung nach dem Klick „eigene
    Fläche“, und Z2, Z5 und E6 sähen sie nicht.
    """
    from tools.function_capture import message_window

    if not message_window(widget):
        return True
    target = str(row.get("target") or "")
    kind, _separator, rest = target.partition(":")
    return (
        kind == "message"
        or (kind == "dialog" and rest in classes_of(widget))
        or row.get("source") in MESSAGE_SOURCES
    )


def report_findings(session: Any) -> dict[str, str]:
    """Die Befunde des letzten Ergebnisses, je Kennung mit ihrem Satz (Prüfpunkt 7, ``befund``).

    Kennung heißt hier Code und Körper: Derselbe Befund an einem zweiten Körper
    ist ein neuer.
    """
    result = getattr(session, "last_result", None)
    report = getattr(getattr(result, "scene", None), "report", None)
    return {
        f"{finding.code}@{getattr(finding, 'object_id', '') or ''}": str(finding.message)
        for finding in getattr(report, "findings", ()) or ()
    }


def shown_findings(window: Any) -> set[str]:
    """Die Befundkennungen, die der Prüfbericht gerade als Zeilen zeigt."""
    from PySide6.QtCore import Qt

    listing = window.report.list
    return {
        str(getattr(finding, "code", ""))
        for row in range(listing.count())
        if (item := listing.item(row)) is not None
        and (finding := item.data(Qt.ItemDataRole.UserRole)) is not None
    }


def require_findings(window: Any, promised: Iterable[str]) -> None:
    """Hält an, wenn der Prüfbericht einen zugesagten Befund der Vorbereitung nicht zeigt.

    Nach Einfügemarke, Export oder *Automatisch teilen* gibt die Szene ihre
    Befunde zu (``promises.findings``); fehlt einer, ist die Vorbereitung nicht
    hergestellt — kein Fund an der Anwendung (Durchsicht welle4 C-L3).
    """
    missing = sorted(set(promised) - shown_findings(window))
    if missing:
        raise RuntimeError(
            f"Vorbereitung nicht hergestellt: der Prüfbericht zeigt {', '.join(missing)} nicht"
        )


def require_full_export_scope(window: Any) -> None:
    """Der Auslöser exportiert die ganze Szene, keine geerbte Teilauswahl (FD53)."""
    selected = set(window.object_tree.selected_objects())
    result = window.session.last_result
    if result is None or (selected and selected != set(result.scene.objects)):
        raise RuntimeError("Vorbereitung nicht hergestellt: Export umfasst nicht die ganze Szene")


def classes_of(widget: Any) -> set[str]:
    """Die Klassennamen eines Fensters samt Basisklassen."""
    return {cls.__name__ for cls in type(widget).__mro__}


#: Fenster, die der Kunde als Fenster seines Systems sieht. Der Fallprozess zeigt
#: Qts eigenen Dialog (``file_acceptance.no_native_dialogs``): Gemessen würde ein
#: Fenster, das der Kunde nie sieht (FD-122). Den echten prüft Stufe C am System.
SYSTEM_SURFACES: Final[tuple[str, ...]] = ("QFileDialog",)


def system_surface(widget: Any) -> str:
    """Welche Systemfläche ``widget`` vertritt — leer, wenn es ein Fenster der Anwendung ist."""
    names = classes_of(widget)
    return next((name for name in SYSTEM_SURFACES if name in names), "")


def grey_reason(window: Any, target: str) -> str | None:
    """Der Grund, mit dem das Ziel grau steht; ``None``, wenn es offen ist.

    Ein Widget nennt ihn in Kurzhilfe oder Beschreibung, die Kurzhilfe zuerst:
    Sie sieht der Kunde, wenn er auf den grauen Knopf zeigt. Die Beschreibung
    kann noch vom offenen Knopf stammen — die gesperrte Befundhandlung behält
    ihre Nebenfolge dort (F-34). Eine Menüzeile hat kein Widget — gefragt wird
    ihre Aktion; deren ``toolTip`` ist ohne eigenen Satz ihr Text, und der ist
    kein Grund.
    """
    from app.ui import guide_targets

    try:
        widget = guide_targets.widget_for(window, target)
    except LookupError:
        widget = None
    if widget is not None:
        if widget.isEnabled():
            return None
        return str(widget.toolTip() or widget.accessibleDescription())
    kind, _separator, rest = target.partition(":")
    if kind != "menu":
        return None
    action = next(
        (found for name, _menus, found in guide_targets.menubar_entries(window) if name == rest),
        None,
    )
    if action is None or action.isEnabled():
        return None
    tip = str(action.toolTip())
    text = action.text().replace("&", "")
    plain = {text, text.rstrip(".…").strip()}
    return tip if tip and tip not in plain else str(action.statusTip())


def fault_messages(window: Any, targets: Sequence[str]) -> list[dict[str, Any]]:
    """Was der Fehlfall meldet: die Meldungen der Oberfläche, als Sperrgrund aber nur der
    Grund, mit dem die Ziele der Zeile grau stehen (Prüfpunkt 7, V5).

    ``function_capture.message_entries`` nennt jeden grauen Knopf mit Kurzhilfe;
    „erwartet Sperrgrund“ war damit erfüllt, sobald irgendein fremder Knopf grau
    stand (Durchsicht welle4 C-L1). Gefragt wird :func:`grey_reason` an
    ``targets`` — dem Ziel der Zeile und dem, womit sie übernommen wird.
    """
    from app.ui import guide_targets
    from tools import function_capture as capture

    found = [
        entry for entry in capture.message_entries(window) if entry.get("kind") != "sperrgrund"
    ]
    for target in dict.fromkeys(targets):
        reason = grey_reason(window, target)
        if not reason:
            continue
        # Das graue Element selbst, damit die Felder seiner Fläche als Ausweg
        # zählen (FD-31); eine Menüzeile hat keins.
        try:
            widget = guide_targets.widget_for(window, target)
        except LookupError:
            widget = None
        found.append(
            {
                "text": reason,
                "actions": [],
                "kind": "sperrgrund",
                "way_out": capture.way_out(window, reason, widget),
            }
        )
    return found


def windows_to_picture(window: Any) -> list[Any]:
    """Die sichtbaren Fenster neben dem Hauptfenster: Dialoge, auch nichtmodale (F-31).

    Vorher kam nur ``activeModalWidget`` ins Bild, und der nichtmodale
    Operationsdialog fehlte in jedem. Menüs und Kurzhilfen sind keine Fenster
    der Zeile.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    kinds = (Qt.WindowType.Dialog, Qt.WindowType.Window, Qt.WindowType.Tool, Qt.WindowType.Sheet)
    return [
        widget
        for widget in QApplication.topLevelWidgets()
        if widget is not window
        and widget.isVisible()
        and widget.isWindow()
        and widget.windowType() in kinds
    ]


def picture_label(variant: Any, row_id: str, label: str) -> str:
    """Der Name eines Flächenbilds: im Sprachfall je Sprache und Zeile (F-31).

    Ein Sprachfall geht die Flächen aller Zeilen eines Pakets ab; mit einem
    Namen je Satz überschrieb jede Fläche das Bild der vorigen.
    """
    from tools.function_protocol import safe_name

    if variant.set == "sprachen":
        return f"{label}-{variant.language}-{safe_name(row_id)}"
    return f"{label}-{variant.set}"


def pending(window: Any) -> bool:
    """Ob das Fenster sichtbar sagt, dass gleich etwas kommt (F-20).

    Das Merkmalfenster zeigt :data:`PENDING_NOTE`, solange es seine Zeilen im
    Arbeiter rechnet (RM-232); die Sitzung rechnet, und ein Dialog nach der
    Rechnung kommt danach. Solange gilt ein fehlendes Ziel nicht als „nicht
    auffindbar“.
    """
    from PySide6.QtWidgets import QLabel

    from app.i18n import tr

    if bool(getattr(window.session, "busy", False)):
        return True
    note = tr(PENDING_NOTE)
    return any(
        label.isVisible() and label.text() == note
        for label in window.feature_panel.findChildren(QLabel)
    )


def search_names(window: Any, row: Mapping[str, Any]) -> frozenset[str]:
    """Die Treffernamen der Suche, die dieselbe Funktion meinen wie die Zeile (F-27).

    Das Ziel selbst; eine Operation unter ihrem Treffernamen, auch wenn ihre
    Zeile im Merkmalfenster oder am Filamentwähler steht; zu einer
    Befundhandlung die Operation gleichen Namens; zu einer Menüzeile der Befehl,
    dessen Aktion dieselbe ist (``command:<schlüssel>``, am Fenster
    nachgeschlagen); dazu, was die Zeile in ``covers`` trägt.
    """
    from app.core.registry import REGISTRY
    from app.ui import guide_targets

    target = str(row.get("target") or "")
    names = {target, *(f"operation:{name}" for name in row.get("covers") or ())}
    if row.get("kind") == "operation" and REGISTRY.has(str(row.get("id") or "")):
        names.add(f"operation:{row.get('id')}")
    kind, _separator, rest = target.partition(":")
    if kind == "finding.action" and REGISTRY.has(rest):
        names.add(f"operation:{rest}")
    if kind == "menu":
        action = next(
            (
                found
                for name, _menus, found in guide_targets.menubar_entries(window)
                if name == rest
            ),
            None,
        )
        if action is not None:
            for hit in guide_targets.search_hits(window):
                hit_kind, _dot, _key = hit.partition(":")
                if hit_kind != "command":
                    continue
                try:
                    if guide_targets.action_for(window, hit) is action:
                        names.add(hit)
                except LookupError:
                    continue
    return frozenset(name for name in names if name)


def search_rank(hits: Sequence[str], names: frozenset[str]) -> int | None:
    """Der Rang des ersten Treffers, der die Funktion meint, ab 1; ``None`` ohne."""
    return next((rank for rank, hit in enumerate(hits, 1) if hit in names), None)


def scene_names(session: Any) -> list[str]:
    """Was die Szene selbst benennt: die Körper nach ihren Dateien und das Projekt (F-10)."""
    names: list[str] = []
    result = session.last_result
    if result is not None:
        names += [str(entry.name) for entry in result.scene.objects.values() if entry.name]
    path = getattr(session, "path", None)
    if path is not None:
        names.append(Path(path).stem)
    return sorted(set(names))


def computing(window: Any) -> bool:
    """Ob der Kunde sieht, dass gerechnet wird: Sitzung, Wartezeiger, Balken, *Abbrechen*, Band.

    Eine Vorschau rechnet im eigenen Arbeiter, ohne dass die Sitzung „beschäftigt“
    heißt; zu sehen ist sie am Vorschauband ohne Legende — die steht erst mit der
    fertigen Differenz (§2.8, FunctionFlow.preview_steps).
    """
    from PySide6.QtWidgets import QApplication, QProgressBar

    if bool(getattr(window.session, "busy", False)) or QApplication.overrideCursor() is not None:
        return True
    if any(bar.isVisible() for bar in window.statusBar().findChildren(QProgressBar)):
        return True
    if _shown(window, "progress.cancel") is not None:
        return True
    banner = _shown(window, "preview.banner")
    legend = getattr(banner, "legend", None)
    return banner is not None and not (legend is not None and legend.isVisible())


def field_name(window: Any, name: str) -> str:
    """Der Name, unter dem ein Feld einer Merkmalshandlung gerade dasteht (F-20).

    Mit Bild rückt das Fenster die Handlung einer gewählten Bohrung in die
    Maßgruppe über der Ansicht: Ihre Felder heißen dort ``measure.field:<feld>``,
    und die Zeile im Merkmalfenster ist verborgen. Ohne Bild (offscreen) bleibt
    sie dort. Gefragt wird, was zu sehen ist — und **welche** Handlung dort
    steht (:func:`op_in_view`): An einer gesetzten Bohrung trägt die Maßgruppe
    *Bohrung im ursprünglichen Schritt ändern* (``drill_hole``), nicht *Bohrung
    ändern*; deren Felder heißen gleich (N5).
    """
    kind, _separator, rest = name.partition(":")
    if kind != "feature.field":
        return name
    op, _dot, field = rest.partition(".")
    moved = f"measure.field:{field}"
    if (
        _shown(window, name) is None
        and _shown(window, moved) is not None
        and op_in_view(window) == op
    ):
        return moved
    return name


def op_in_view(window: Any) -> str | None:
    """Die Handlung, deren Maße die Gruppe im Bild trägt (``FeaturePanel.measure_op``).

    Nicht die scharfe der Merkmalskarte: Die beiden fielen an einer erkannten
    Bohrung auseinander (FD-34, *Merkmal verschieben* scharf, *Bohrung ändern*
    im Bild), und der Prüfstand fand die Zeile dort nicht (FD-29).
    """
    panel = getattr(window, "feature_panel", None)
    measured = getattr(panel, "measure_op", None)
    return str(measured) if measured else None


def in_view(window: Any, inputs: Sequence[str]) -> bool:
    """Ob die Handlung mit diesen Eingaben in der Maßgruppe im Bild steht (F-20)."""
    return any(field_name(window, name) != name for name in inputs)


def licence_refusal(error: object) -> bool:
    """Ob eine Absage die Lizenzgrenze ist (``activation.require``, F-35).

    Dann hat die Handlung zu schreiben versucht — offen statt grau, auch wenn
    der Abdruck sich nicht änderte.
    """
    from app.core import activation

    refusals = tuple(
        cls
        for cls in (
            getattr(activation, "LicenceRequired", None),
            getattr(activation, "DeviceActivationRequired", None),
            getattr(activation, "DeviceDeactivationPending", None),
            getattr(activation, "InstallationDamaged", None),
        )
        if isinstance(cls, type)
    )
    return isinstance(error, refusals)


def without_way(row: Mapping[str, Any]) -> str:
    """Warum der Sprachfall die Fläche einer Zeile nicht erreicht — leer, wenn er sie erreicht.

    Ohne Startszene steht der Befund nicht da, dessen Handlung die Zeile ist; ein
    Dialog einer Klasse und ein Meldungsfenster gehen nur über einen benannten
    Weg auf (``spec.route``). Solche Zeilen sind nicht gelaufen, kein Fund (F-32).
    Ebenso ein Weg über einen Befund oder eine Befundhandlung, die die Startszene
    nicht zusagt (``promises``): Er hieße „nicht auffindbar“ gegen die Anwendung,
    wo die Szene fehlt (FD-101).
    """
    from tools.function_scenes import load_scenes

    spec = row.get("spec") or {}
    scene = str(spec.get("start_scene") or row.get("start_scene") or "")
    if not scene:
        return "Zeile ohne Startszene, die ihren Befund trägt"
    kind = str(row.get("target") or "").partition(":")[0]
    if kind in OPENED_ELSEWHERE and not spec.get("route"):
        return f"Zeile ohne Weg zu ihrem Fenster ({kind}:, keine route in der Spezifikation)"
    promises = getattr(load_scenes().get(scene), "promises", None)
    if promises is None:
        return f"Startszene {scene} steht nicht im Szenenkatalog"
    steps = [*(row.get("route") or ()), *(spec.get("route") or ()), {"target": row.get("target")}]
    for step in steps:
        name = str(step.get("target") or "")
        if name.startswith("finding:") and name[8:] not in promises.get("findings", ()):
            return f"Startszene {scene} sagt den Befund {name[8:]} nicht zu"
        if name.startswith("finding.action:") and name[15:] not in promises.get("actions", {}):
            return f"Startszene {scene} sagt die Handlung {name[15:]} nicht zu"
    return ""
