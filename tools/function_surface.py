"""Welche Fläche eine Zeile zeigt, was sie im Bild trägt und was ihre Handlung tat (D0-P2, RM-737).

Die Fläche einer Zeile folgt der Art ihres Ziels (:func:`surface_for`): der
offene Dialog, sonst bei einer Befundhandlung und beim Bericht der Prüfbericht,
bei einem Werkzeug seine Leiste über der Ansicht, sonst die Karte der Auswahl.
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

from collections.abc import Mapping, Sequence
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
    """Der offene Dialog — Operationsdialog oder modales Fenster —, sonst ``None``."""
    return _shown(window, "dialog")


def surface_for(window: Any, target: str) -> Any:
    """Die Fläche, die eine Zeile mit diesem Ziel zeigt (F-30).

    Ein offener Dialog geht vor — ihn hat die Zeile geöffnet. Ein Ziel
    ``dialog:<klasse>`` ist das Fenster dieser Klasse. Sonst nach der Zielart:
    Befund, Befundhandlung und ``report*`` der Prüfbericht, ``tool:<name>`` die
    Leiste des Werkzeugs (``handle:bar.<name>``), sonst die Karte der Auswahl
    und zuletzt das Fenster.
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
    return _shown(window, "selection") or window


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


def classes_of(widget: Any) -> set[str]:
    """Die Klassennamen eines Fensters samt Basisklassen."""
    return {cls.__name__ for cls in type(widget).__mro__}


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
    sie dort. Gefragt wird, was zu sehen ist.
    """
    kind, _separator, rest = name.partition(":")
    if kind != "feature.field":
        return name
    moved = f"measure.field:{rest.partition('.')[2]}"
    if _shown(window, name) is None and _shown(window, moved) is not None:
        return moved
    return name


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
    """
    spec = row.get("spec") or {}
    scene = str(spec.get("start_scene") or row.get("start_scene") or "")
    if not scene:
        return "Zeile ohne Startszene, die ihren Befund trägt"
    kind = str(row.get("target") or "").partition(":")[0]
    if kind in OPENED_ELSEWHERE and not spec.get("route"):
        return f"Zeile ohne Weg zu ihrem Fenster ({kind}:, keine route in der Spezifikation)"
    return ""
