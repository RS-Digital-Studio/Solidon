"""Formsprache: Stylesheet, Typografie-Skala, Abstandsraster (Bauplan §19.3).

`theme.py` setzt Farben — Hintergrund, Text, Auswahl. Das war lange alles, und
darum sah die Anwendung aus wie jede andere Qt-Anwendung: Fusion-Knöpfe,
Fusion-Felder, Fusion-Reiter, keine eigenen Radien, keine Abstufung zwischen
Haupt- und Nebenknopf, keine Zustände über den Vorgaben.

Drei Dinge stehen hier, und sie hängen zusammen:

**Das Stylesheet** definiert Knöpfe, Felder, Listen, Reiter, Kopfzeilen und
Trenner einmal, mit ihren Zuständen (normal, überfahren, Fokus, gedrückt,
gesperrt). Es lebt in Python und nicht in einer `.qss`-Datei neben dem Paket:
Farben kommen aus dem Thema und die Schriftgrößen aus der Systemeinstellung, es
wäre also ohnehin eine Vorlage — und eine Datei, die beim Paketieren
vergessen wird, nimmt der Anwendung stillschweigend ihr ganzes Aussehen.

**Die Typografie-Skala** hat vier Stufen. Vorher war alles gleich laut: im
Objektbaum war der Name so groß wie das Maß, im Prüfbericht ein Fehler so groß
wie ein Hinweis. Nebentext — Maße, Einheiten, Herkunft — soll lesbar sein, nicht
mitreden.

**Das Abstandsraster** ist eine Zahl und ihre Vielfachen. Vorher standen Dinge
mal 2, mal 3, mal 5, mal 6 Pixel auseinander, jede Stelle für sich entschieden;
das ist der Eindruck, dass alles ein bisschen daneben sitzt, ohne dass man
einen einzelnen Fehler benennen kann.
"""

from __future__ import annotations

from typing import Final, Literal, cast

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFocusEvent, QFont, QKeyEvent, QResizeEvent, QScreen, QShowEvent, QWindow
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QLabel,
    QLayout,
    QLayoutItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
    QWidgetAction,
)

from app.core.log import get_logger
from app.ui import app_events
from app.ui.theme import THEMES, Theme

_log = get_logger(__name__)

#: Die Grundzahl des Rasters. Jeder Abstand in der Oberfläche ist ein
#: Vielfaches davon — ``tests/test_style.py`` prüft das.
SPACE = 4

TIGHT = SPACE
"""Zwischen Dingen, die zusammengehören: Symbol und Beschriftung."""
NORMAL = SPACE * 2
"""Der Regelabstand zwischen Bedienelementen einer Zeile."""
ROOMY = SPACE * 3
"""Die Innenkante eines Panels oder Dialogs."""
WIDE = SPACE * 4
"""Zwischen Abschnitten, die nichts miteinander zu tun haben."""

#: Mindestmaß einer ausdrücklich großen Trefferfläche. Der gewöhnliche
#: Desktopknopf bleibt kompakt; nur ein über :func:`make_large_target`
#: markierter Einstieg nimmt dieses Maß ein.
TARGET_SIZE = 44

#: Die vier Stufen, in absteigender Lautstärke.
LEVELS = ("title", "section", "body", "caption")

#: Faktor und Gewicht je Stufe, bezogen auf die Grundschriftgröße des Systems.
#: Relativ und nicht absolut, weil §19.3 skalierbare Schrift verlangt: wer seine
#: Systemschrift größer stellt, bekommt hier alles größer, nicht nur den Rest.
SCALE: dict[str, tuple[float, int]] = {
    "title": (1.75, 600),
    "section": (1.15, 600),
    "body": (1.0, 400),
    "caption": (0.85, 400),
}


def type_scale(base: int) -> dict[str, tuple[int, int]]:
    """Punktgrößen und Gewichte der vier Stufen zu einer Grundgröße."""
    return {
        level: (max(round(base * factor), 1), weight) for level, (factor, weight) in SCALE.items()
    }


def set_level(widget: QWidget, level: str) -> None:
    """Setzt die Typografie-Stufe eines Widgets.

    Über eine Qt-Eigenschaft und nicht über ein eigenes Stylesheet je Widget:
    so steht die Gestaltung an einer Stelle, und ein Themenwechsel muss nicht
    hundert Einzelfälle einsammeln.

    **Nur die vier aus** :data:`LEVELS`. Die Stufen sind **Lautstärke** —
    Größe, Gewicht, Nebentextfarbe —, und wer hier eine Bedeutung einsetzt,
    schreibt sie in eine Eigenschaft, die kein Selektor liest: Einunddreißig
    Aufrufe trugen ``warning``, ``info``, ``ok`` oder ``note``, und gerendert
    waren sie **pixelgleich** mit gar keiner Stufe. Eine Zeile, die sagt, dass
    sie warnt, sah aus wie gewöhnlicher Text. Für Bedeutungen steht
    :func:`set_role` daneben.
    """
    if level not in LEVELS:
        raise ValueError(
            f"{level!r} ist keine Typografie-Stufe, sondern vermutlich eine Bedeutung — "
            f"erlaubt sind {LEVELS}, für Bedeutungen gibt es set_role()"
        )
    widget.setProperty("level", level)
    _repolish(widget)


def set_role(widget: QLabel, role: str, text: str) -> None:
    """Eine Zeile, die eine Bedeutung trägt: Farbe **und** Zeichen (Regel 18).

    Text und Rolle in einem Aufruf, und das ist der Punkt: Der Bestand setzte
    beides getrennt (``setText`` und eine Zeile darunter die Stufe), und in
    genau dieser Lücke ist die Kodierung verlorengegangen. Wer den Satz
    schreibt, sagt hier zugleich, was er bedeutet — vergessen lässt sich das
    nicht mehr.

    Der Bildschirmleser bekommt die Bedeutung als **Wort**, nicht als Zeichen:
    „Warnung" liest sich vor, „!" nicht.
    """
    import html

    from app.i18n import tr
    from app.ui.palette import ROLE_MARKS, SEVERITY_ENCODING, text_colour

    if role not in ROLE_MARKS:
        raise ValueError(f"{role!r} ist keine Bedeutung — erlaubt sind {sorted(ROLE_MARKS)}")

    widget.setProperty("role", role)
    if not text:
        widget.setText("")
        widget.setAccessibleDescription("")
        _repolish(widget)
        return

    # **Die Farbe trägt das Zeichen, den Satz trägt der Fließtext** — dieselbe
    # Entscheidung wie im Prüfbericht, und aus demselben gemessenen Grund. Die
    # Rollenfarben sind als Schrift zu schwach: „Warnung" bringt im hellen
    # Thema 3,76 gegen die Fensterfläche, „Hinweis" ebenfalls 3,76 und im
    # dunklen 4,28 — WCAG 1.4.3 verlangt 4,5 für gewöhnlichen Text. Ein voll
    # eingefärbter Satz wäre also ausgerechnet dort am schlechtesten lesbar, wo
    # er am dringendsten ist. Als Zeichen gilt die Grenze für Grafik (1.4.11,
    # 3,0), und die halten beide Rollen in beiden Themen.
    ground = widget.palette().window().color().name()
    # Die Einengung ist für mypy und für den Leser dieselbe Aussage: Genau
    # diese zwei Rollen sind auch Schweregrade und haben deshalb eine Farbe.
    tint = text_colour(role, ground) if role in ("warning", "info") else ""  # type: ignore[arg-type]
    mark = html.escape(ROLE_MARKS[role])
    painted = f'<span style="color: {tint}">{mark}</span>' if tint else mark
    # ``html.escape`` auf dem Satz, nicht auf dem Zeichen allein: Der Text kommt
    # aus Katalogen und aus Fehlermeldungen, und ein ``<`` darin machte aus der
    # Zeile stillen Unsinn. Was hier gebaut wird, ist die einzige Stelle, an der
    # die Anwendung eine Beschriftung als Auszeichnungstext setzt.
    widget.setTextFormat(Qt.TextFormat.RichText)
    widget.setText(f"{painted}&nbsp;&nbsp;{html.escape(text)}")
    encoding = SEVERITY_ENCODING.get(role)
    spoken = tr(encoding.label_key) if encoding is not None else tr("Erledigt")
    widget.setAccessibleDescription(tr("{name}: {value}", name=spoken, value=text))
    _repolish(widget)


class WrappedNote(QLabel):
    """Ein umbrochener Satz, der die Höhe einfordert, die er wirklich braucht.

    Ein ``QLabel`` mit Zeilenumbruch meldet der Layoutrechnung als Mindesthöhe
    **eine** Zeile; was er wirklich braucht, sagt erst ``heightForWidth``, und
    das fragt ein Dialog für seine eigene Mindestgröße nicht. Wächst der Satz
    nach dem Öffnen — eine Prüfung ist fertig, eine Absage kommt an —, bleibt
    das Fenster auf seiner Aufmachgröße stehen, und der Fehlbetrag wird aus den
    Nachbarn gepresst. Gemessen am Erzeugen-Dialog (Befund Robert, 19.09.2026):
    Nach der Antwort „kein ComfyUI" stand der lange Satz da, und das
    Beschreibungsfeld darüber hatte noch 11 von 26 Punkten Höhe.

    Derselbe Fall wie beim Erststart (``first_run._grow_to_content``), nur an
    der Quelle: Der Satz pinnt seine Mindesthöhe selbst, sobald er einen neuen
    Text oder eine neue Breite hat, und sagt es über :attr:`grown` weiter,
    damit das Fenster nachwächst. Über einen Zeitgeber, nicht sofort — direkt
    nach ``setText`` meldet ``heightForWidth`` noch den alten Stand.
    """

    grown = Signal()
    """Die Mindesthöhe hat sich geändert, nach oben oder unten; wer den Satz
    zeigt, folgt ihr."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWordWrap(True)

    def setText(self, text: str) -> None:  # noqa: N802 — Qt gibt den Namen
        super().setText(text)
        QTimer.singleShot(0, self, self.claim_height)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 — Qt gibt den Namen
        super().resizeEvent(event)
        # Schmaler heißt mehr Zeilen, breiter weniger: Die gepinnte Höhe
        # gehört zur Breite, an der sie gemessen wurde.
        self.claim_height()

    def claim_height(self) -> None:
        """Die Mindesthöhe auf das setzen, was der Satz in dieser Breite braucht.

        **Gemessen ohne die gepinnte Höhe.** ``QLabel.heightForWidth`` meldet
        nie weniger als die eigene Mindesthöhe; auf einen Satz in zehn Zeilen
        gemessen blieb jeder kürzere danach zehn Zeilen hoch, und das Fenster
        darum konnte nichts zurückgeben.
        """
        if self.width() <= 0:
            return
        pinned = self.minimumHeight()
        self.setMinimumHeight(0)
        wanted = max(self.heightForWidth(self.width()), 0) if self.text() else 0
        self.setMinimumHeight(wanted)
        if wanted != pinned:
            self.grown.emit()


class DialogScrollArea(QScrollArea):
    """Dialoginhalt in natürlicher Größe, bei Platzmangel scrollbar.

    Die Aktionsknöpfe bleiben außerhalb. Anders als der gewöhnliche Rollbereich
    deckelt dieser den Größenwunsch nicht auf wenige Textzeilen; kurze Formulare
    öffnen sich vollständig. Die Mindestgröße lässt lange Formulare dennoch
    kleiner werden, ohne deren Felder zusammenzudrücken.
    """

    contentSizeChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._content_hint: QSize | None = None
        self._content_height: object | None = None
        self._screen_window: QWindow | None = None
        self._screen: QScreen | None = None
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt gibt den Namen
        content = self.widget()
        if content is None:
            return super().sizeHint()
        wanted = content.sizeHint().expandedTo(content.minimumSizeHint())
        layout = content.layout()
        if layout is not None and layout.hasHeightForWidth():
            width = self.viewport().width() if self.isVisible() else wanted.width()
            wanted.setHeight(
                max(content.minimumSizeHint().height(), layout.totalHeightForWidth(width))
            )
        frame = self.frameWidth() * 2
        return wanted + QSize(frame, frame)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt gibt den Namen
        return QSize(TARGET_SIZE * 2, TARGET_SIZE * 2)

    def setWidget(self, widget: QWidget) -> None:  # noqa: N802 — Qt gibt den Namen
        super().setWidget(widget)
        widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        from app.ui.leash import stop_watching_the_dying

        if stop_watching_the_dying(self, watched, event):
            return False
        if watched is self.widget() and event.type() == QEvent.Type.LayoutRequest:
            self.updateGeometry()
            wanted = self.sizeHint()
            if wanted != self._content_hint:
                self._content_hint = wanted
                self.contentSizeChanged.emit()
        return super().eventFilter(watched, event)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 — Qt gibt den Namen
        super().showEvent(event)
        QTimer.singleShot(0, self, self._fit_window)

    def _fit_window(self) -> None:
        window = self.window()
        if isinstance(window, QDialog):
            handle = window.windowHandle()
            if handle is not None:
                self._watch_screen(handle)
            height = self._content_height
            if isinstance(height, ContentHeight):
                height.fit_to_screen(window)
            else:
                fit_dialog_to_screen(window)

    def _watch_screen(self, window: QWindow) -> None:
        """Bildschirmwechsel, nutzbare Fläche und DPI an den Dialog binden."""
        if window is not self._screen_window:
            if self._screen_window is not None:
                self._screen_window.screenChanged.disconnect(self._screen_changed)
            self._screen_window = window
            window.screenChanged.connect(self._screen_changed)
        self._watch_screen_metrics(window.screen())

    def _watch_screen_metrics(self, screen: QScreen | None) -> None:
        if screen is self._screen:
            return
        if self._screen is not None:
            self._screen.availableGeometryChanged.disconnect(self._screen_changed)
            self._screen.logicalDotsPerInchChanged.disconnect(self._screen_changed)
        self._screen = screen
        if screen is not None:
            screen.availableGeometryChanged.connect(self._screen_changed)
            screen.logicalDotsPerInchChanged.connect(self._screen_changed)

    def _screen_changed(self, *_args: object) -> None:
        """Die Fensterbegrenzung nach dem Qt-Umlauf neu berechnen."""
        if self._screen_window is not None:
            self._watch_screen_metrics(self._screen_window.screen())
        QTimer.singleShot(0, self, self._fit_window)


def fit_dialog_to_screen(dialog: QWidget) -> None:
    """Ein Dialogfenster beim Öffnen oder Bildschirmwechsel erreichbar halten.

    Erst nach dem Anzeigen aufrufen, wenn Qt den Fensterrahmen kennt. Bei
    gewöhnlichen Größenänderungen bleibt der Anker stehen; überlange Inhalte
    gehören in einen Rollbereich.
    """
    screen = dialog.screen()
    if screen is None or dialog.isMaximized() or dialog.isFullScreen():
        return
    room = screen.availableGeometry().adjusted(NORMAL, NORMAL, -NORMAL, -NORMAL)
    frame = dialog.frameGeometry()
    border = frame.size() - dialog.size()
    dialog.resize(
        min(dialog.width(), max(1, room.width() - border.width())),
        min(dialog.height(), max(1, room.height() - border.height())),
    )
    frame = dialog.frameGeometry()
    x = max(room.left(), min(frame.left(), room.right() - frame.width() + 1))
    y = max(room.top(), min(frame.top(), room.bottom() - frame.height() + 1))
    if x != frame.left() or y != frame.top():
        dialog.move(x, y)


ContentFitIntent = Literal["initial", "explicit", "passive"]


def _natural_item_width(item: QLayoutItem | None) -> int:
    """Liest die natürliche Breite auch dann, wenn Qt das Element verbirgt."""
    if item is None:
        return 0
    hints = [item.sizeHint(), item.minimumSize()]
    widget = item.widget()
    if widget is not None:
        hints.extend((widget.sizeHint(), widget.minimumSizeHint(), widget.minimumSize()))
    layout = item.layout()
    if layout is not None:
        hints.extend((layout.sizeHint(), layout.minimumSize()))
    return max((hint.width() for hint in hints if hint.isValid()), default=0)


def form_natural_width(form: QFormLayout) -> int:
    """Breite eines Formulars samt verborgenen und spaltenübergreifenden Zeilen."""
    margins = form.contentsMargins()
    label_width = 0
    field_width = 0
    spanning_width = 0
    for index in range(form.count()):
        item = form.itemAt(index)
        if item is None:
            continue
        _, role = cast(tuple[int, QFormLayout.ItemRole], form.getItemPosition(index))
        width = _natural_item_width(item)
        if role == QFormLayout.ItemRole.LabelRole:
            label_width = max(label_width, width)
        elif role == QFormLayout.ItemRole.FieldRole:
            field_width = max(field_width, width)
        elif role == QFormLayout.ItemRole.SpanningRole:
            spanning_width = max(spanning_width, width)
    spacing = form.horizontalSpacing()
    if spacing < 0:
        spacing = max(0, form.spacing())
    paired_width = label_width + field_width
    if label_width and field_width:
        paired_width += spacing
    return margins.left() + max(paired_width, spanning_width) + margins.right()


def _side_margins(owner: QLayout | QWidget) -> int:
    margins = owner.contentsMargins()
    return margins.left() + margins.right()


def _layout_holding(layout: QLayout, widget: QWidget) -> QLayout | None:
    """Das Layout, in dem ``widget`` unmittelbar steht — auch verschachtelt."""
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue
        if item.widget() is widget:
            return layout
        inner = item.layout()
        if inner is not None and (found := _layout_holding(inner, widget)) is not None:
            return found
    return None


def expanded_width(scroll: QScrollArea, *parts: QFormLayout | QWidget) -> int:
    """Wie breit das Fenster um ``scroll`` sein muss, damit nach dem Aufklappen nichts quer rollt.

    Die eine Rechnung für zugeklappte Zeilen (RM-342 D-N5): Ein verborgener
    Teil trägt zur Größe seiner Eltern nichts bei, und ein Dialog, der nur das
    Sichtbare misst, rollt nach dem Aufklappen quer. Gerechnet wird ohne Ein-
    und Ausblenden von innen nach außen: ein Formular mit allen Zeilen, auch
    den bedingt verborgenen (:func:`form_natural_width`), ein anderes Widget
    mit seiner eigenen Größe — Reiter melden ihre breiteste Seite —, dann
    jeder Rand der umschließenden Layouts und Widgets (eine Gruppe trägt ihren
    Rahmen dort), am Rollbereich dessen Rahmen und der senkrechte Rollbalken,
    den das Aufklappen bringt, bis zum Fenster. Der sichtbare Inhalt zählt mit
    seiner Mindestbreite und demselben Rollbalken mit; wie breit er bequem
    wäre, sagt die ``sizeHint`` des Fensters, die der Aufrufer danebenlegt.
    """
    widest = 0
    content = scroll.widget()
    content_layout = content.layout() if content is not None else None
    if content is not None and content_layout is not None:
        widest = _outward(content.minimumSizeHint().width(), content_layout, scroll)
    for part in parts:
        if isinstance(part, QFormLayout):
            widest = max(widest, _outward(form_natural_width(part), part, scroll))
        else:
            own = max(part.sizeHint().width(), part.minimumSizeHint().width())
            widest = max(widest, _past(own, part, scroll))
    return widest


def _outward(width: int, layout: QLayout, scroll: QScrollArea) -> int:
    """``width`` innerhalb von ``layout`` samt aller Ränder bis zum Fenster.

    Die Ränder von ``layout`` selbst stecken schon in ``width``.
    """
    while True:
        parent = layout.parent()
        if not isinstance(parent, QLayout):
            break
        width += _side_margins(parent)
        layout = parent
    owner = layout.parentWidget()
    if owner is None or owner.isWindow():
        return width
    if owner is scroll.widget():
        chrome = 2 * scroll.frameWidth() + scroll.verticalScrollBar().sizeHint().width()
        return _past(width + chrome, scroll, scroll)
    return _past(width + _side_margins(owner), owner, scroll)


def _past(width: int, widget: QWidget, scroll: QScrollArea) -> int:
    """``width`` eines Widgets samt dessen eigener Ränder, weiter bis zum Fenster."""
    host = widget.parentWidget()
    host_layout = host.layout() if host is not None else None
    holder = _layout_holding(host_layout, widget) if host_layout is not None else None
    if holder is None:
        return width
    return _outward(width + _side_margins(holder), holder, scroll)


def _content_size_for_intent(
    current: QSize,
    natural: QSize,
    intent: ContentFitIntent,
    *,
    grow_width: bool = False,
    natural_width: int = 0,
    height_floor: int = 0,
    available_height: int | None = None,
) -> QSize | None:
    """Reine Größenentscheidung; äußere Qt-Messungen bleiben beim Aufrufer.

    ``passive`` wächst nur in der Höhe und gibt nie Höhe zurück: Nachgereichter
    Inhalt — das Ergebnis einer Hintergrundprüfung samt Knopf — braucht Platz,
    ein kürzerer Inhalt danach ließe den Rahmen bei jedem Statuswechsel springen.
    """
    if intent == "passive":
        height = natural.height()
        if available_height is not None:
            height = min(height, available_height)
        if height <= current.height():
            return None
        return QSize(current.width(), height)
    if intent == "explicit":
        height = natural.height()
        if available_height is not None:
            height = min(height, available_height)
        return QSize(current.width(), max(1, height))
    width = current.width()
    if grow_width:
        width = max(width, natural.width())
    width = max(width, natural_width)
    return QSize(width, max(natural.height(), height_floor))


def _hidden_height(scroll: QScrollArea) -> int:
    """Wie viel vom Inhalt unter dem Rand des Rollbereichs liegt, in Punkten.

    Gemessen an der Breite, die der Inhalt wirklich hat, nicht am Ausschnitt:
    Ist er breiter und rollt quer, bräche er in der schmaleren Breite in mehr
    Zeilen um, als er hat.
    """
    content = scroll.widget()
    if content is None:
        return 0
    layout = content.layout()
    if layout is not None:
        layout.activate()
    needed = content.sizeHint().expandedTo(content.minimumSizeHint()).height()
    if layout is not None and layout.hasHeightForWidth():
        width = max(content.width(), scroll.viewport().width())
        needed = max(content.minimumSizeHint().height(), layout.totalHeightForWidth(width))
    return max(0, needed - scroll.viewport().height())


class ContentHeight:
    """Größenvertrag für Dialoge mit Rollbereich.

    Eine anfängliche Messung passt den aktuellen Dialoginhalt ein. Explizites
    Auf- und Zuklappen darf Höhe zurückgeben oder hinzufügen und hält den
    Fensteranker; passive Inhaltsänderungen dürfen den Rahmen nach der
    Anfangsmessung bis zum Bildschirmrand vergrößern, nie verkleinern, und
    halten den Anker, sobald einmal ausdrücklich geklappt wurde.
    Sobald der Kunde Breite oder Höhe ändert, bleiben beide Maße für die
    Dialoglebenszeit maßgeblich. Mehrinhalt rollt dann im Scrollbereich.
    """

    __slots__ = ("_anchored", "_initialized", "fitted", "user")

    def __init__(self) -> None:
        self.fitted: QSize | None = None
        self.user: QSize | None = None
        self._initialized = False
        self._anchored = False

    @property
    def initial_fit_done(self) -> bool:
        """Ob die natürliche Anfangsgröße des Dialogs bereits gemessen wurde."""
        return self._initialized

    def _observe_user_size(self, dialog: QWidget) -> None:
        if dialog.isVisible() and self.fitted is not None and dialog.size() != self.fitted:
            self.user = QSize(dialog.size())

    def _remember_size(self, dialog: QWidget) -> None:
        self.fitted = QSize(dialog.size())
        if self.user is not None:
            self.user = QSize(dialog.size())

    def floor(self, dialog: QWidget) -> int:
        """Merkt eine seit der letzten eigenen Messung gewählte Nutzergröße."""
        self._observe_user_size(dialog)
        return self.user.height() if self.user is not None else 0

    def fit_to_screen(self, dialog: QWidget) -> None:
        """Stellt nach einem Bildschirmwechsel nur die Erreichbarkeit her."""
        self._observe_user_size(dialog)
        fit_dialog_to_screen(dialog)
        self._remember_size(dialog)

    def prepare_width_for_measurement(self, dialog: QWidget, width: int) -> None:
        """Legt die automatische Breite vor der Inhaltshöhenmessung fest.

        Ein Dialog muss für umbrochene Inhalte manchmal zuerst auf seine
        natürliche Breite kommen. Diese eigene Zwischenanpassung darf nicht als
        manuelle Nutzergröße gelten, auch wenn ein früher Bildschirmfit bereits
        eine Ausgangsgröße gespeichert hat.
        """
        self._observe_user_size(dialog)
        if self.user is not None:
            return
        dialog.resize(max(dialog.width(), width), dialog.height())
        self._remember_size(dialog)

    @staticmethod
    def _available_height_on_screen(dialog: QWidget) -> int | None:
        """Die Höhe, die ``fit_dialog_to_screen`` dem Dialog höchstens lässt."""
        # Ein ungezeigtes Fenster hat noch keinen Bildschirm, auch wenn Qt
        # es anders verspricht.
        screen: QScreen | None = dialog.screen()
        if screen is None:
            return None
        room = screen.availableGeometry().adjusted(NORMAL, NORMAL, -NORMAL, -NORMAL)
        border_height = dialog.frameGeometry().height() - dialog.height()
        return max(1, room.height() - border_height)

    @staticmethod
    def _available_height_at_anchor(dialog: QWidget) -> int:
        screen = dialog.screen()
        room = screen.availableGeometry().adjusted(NORMAL, NORMAL, -NORMAL, -NORMAL)
        frame = dialog.frameGeometry()
        top = max(frame.top(), room.top())
        frame_height = max(1, room.bottom() - top + 1)
        border_height = frame.height() - dialog.height()
        return max(1, frame_height - border_height)

    def settle(
        self,
        dialog: QWidget,
        width: int,
        height: int,
        *,
        intent: ContentFitIntent,
    ) -> None:
        """Setzt eine automatische Größe oder bewahrt eine manuelle vollständig."""
        self._observe_user_size(dialog)
        if self.user is not None:
            self._remember_size(dialog)
            return
        keeps_anchor = self._keeps_anchor(intent)
        anchor = dialog.frameGeometry().topLeft() if keeps_anchor else None
        if keeps_anchor:
            available = self._available_height_at_anchor(dialog)
            if available is not None:
                height = min(height, available)
        dialog.resize(width, height)
        layout = dialog.layout()
        if layout is not None:
            layout.activate()
        if keeps_anchor:
            if anchor is not None and dialog.frameGeometry().topLeft() != anchor:
                dialog.move(anchor)
        else:
            fit_dialog_to_screen(dialog)
        self._remember_size(dialog)
        if intent == "initial":
            self._initialized = True
        elif intent == "explicit":
            self._anchored = True

    def _widen_before_measuring(
        self, dialog: QWidget, *, grow_width: bool, natural_width: int
    ) -> None:
        """Stellt die Anfangsbreite ein, bevor die Höhe gemessen wird.

        Umbrochener Text braucht schmal mehr Zeilen als breit. Gemessen in der
        Ausgangsbreite und erst danach verbreitert, öffnete der Druckdialog
        unter Linux (DejaVu Sans) 104 Punkte höher als sein Inhalt, und das
        erste Zuklappen nahm sie wieder weg. Die Breite ist dieselbe, die
        ``_content_size_for_intent`` und ``fit_dialog_to_screen`` danach
        ergeben; diese eigene Zwischengröße gilt nicht als Zug des Kunden.
        """
        width = dialog.width()
        if grow_width:
            width = max(width, dialog.sizeHint().width())
        width = max(width, natural_width)
        screen = dialog.screen()
        if screen is not None:
            room = screen.availableGeometry().adjusted(NORMAL, NORMAL, -NORMAL, -NORMAL)
            border = dialog.frameGeometry().width() - dialog.width()
            width = min(width, max(1, room.width() - border))
        if width == dialog.width():
            return
        dialog.resize(width, dialog.height())
        self._remember_size(dialog)

    def _keeps_anchor(self, intent: ContentFitIntent) -> bool:
        """Ob der Dialog oben stehen bleibt, statt hinaufzurücken.

        Ausdrückliches Klappen hält die Überschrift unter dem Zeiger; danach
        rückt auch nachgereichter Inhalt den Dialog nicht mehr hinauf.
        """
        return intent == "explicit" or (intent == "passive" and self._anchored)

    def fit(
        self,
        dialog: QWidget,
        scroll: QScrollArea,
        *,
        intent: ContentFitIntent,
        grow_width: bool = False,
        natural_width: int = 0,
        natural_size: QSize | None = None,
    ) -> None:
        """Misst Inhalt nach dem Anlass, der ihn geändert hat.

        ``initial`` passt die Anfangsgröße an; ``explicit`` hält Breite und
        Anker; ``passive`` — nachgereichter Inhalt, Status, Suche — hält die
        Breite und wächst höchstens auf die Bildschirmhöhe; fehlt unter dem
        Dialog Platz, rückt er nur so weit hinauf wie nötig, nach einem
        ausdrücklichen Klappen nicht mehr (RM-487). Vor der Anfangsmessung
        und nach einem Zug des Kunden ändert ``passive`` nur das Layout im
        Scrollbereich.
        """
        if isinstance(scroll, DialogScrollArea):
            scroll._content_height = self
        layout = dialog.layout()
        if layout is None or not dialog.isVisible():
            return
        if intent == "initial" and self._initialized:
            intent = "passive"
        # Erst die liegengebliebenen Layout-Anfragen: Ein Zuklappen meldet sich
        # bei den Eltern über ``LayoutRequest`` in der Warteschlange, und der
        # Nullzeitgeber der Klappe kam davor an — gemessen wurde der
        # aufgeklappte Inhalt, und die Einstellungen gaben ihre Höhe nicht zurück.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
        floor = self.floor(dialog)
        if intent == "passive" and (self.user is not None or not self._initialized):
            return
        if intent == "initial" and natural_size is None and self.user is None:
            self._widen_before_measuring(dialog, grow_width=grow_width, natural_width=natural_width)
        scroll.updateGeometry()
        layout.invalidate()
        layout.activate()
        if intent == "passive":
            # Gewachsen wird um das, was im Rollbereich verdeckt läge — nicht
            # auf einen Größenwunsch, der auch ohne verdeckten Inhalt größer sein
            # kann (ein Umbruch, gemessen an einer anderen Breite).
            wanted = QSize(dialog.width(), dialog.height() + _hidden_height(scroll))
        else:
            wanted = natural_size if natural_size is not None else dialog.sizeHint()
        target = _content_size_for_intent(
            dialog.size(),
            wanted,
            intent,
            grow_width=grow_width,
            natural_width=natural_width,
            height_floor=floor,
            available_height=(
                self._available_height_at_anchor(dialog)
                if self._keeps_anchor(intent)
                else self._available_height_on_screen(dialog)
                if intent == "passive"
                else None
            ),
        )
        if target is None:
            return
        self.settle(dialog, target.width(), target.height(), intent=intent)


def select_data(box: QComboBox, identifier: str) -> None:
    """Wählt den Eintrag eines Kombifelds mit dieser Kennung — und nichts, wenn
    es ihn nicht gibt; die bisherige Wahl bleibt dann stehen."""
    index = box.findData(identifier)
    if index >= 0:
        box.setCurrentIndex(index)


def fit_height_after_show(dialog: QDialog) -> None:
    """Die Aufmachhöhe einen Ereignisumlauf nach dem ersten Anzeigen nachmessen.

    Vor dem Anzeigen kennt Qt weder Stylesheet noch endgültige Breite, und ein
    umbrochener Satz meldet dann mehr Zeilen, als er in der echten Breite
    braucht: Der Unterstützen-Dialog öffnete 618 Punkte hoch für 541 Punkte
    Inhalt, der Dateiweg der Freischaltung 276 für 244 — die Differenz stand
    als leere Fläche über den Knöpfen. Nachgemessen wird einmal, danach gehört
    die Höhe dem Kunden. Aufzurufen aus ``showEvent``.
    """
    if dialog.property("heightFitted"):
        return
    dialog.setProperty("heightFitted", True)

    def fit() -> None:
        layout = dialog.layout()
        if layout is not None:
            layout.activate()
        dialog.resize(
            dialog.width(), max(dialog.minimumSizeHint().height(), dialog.sizeHint().height())
        )
        fit_dialog_to_screen(dialog)

    QTimer.singleShot(0, dialog, fit)


def make_primary(button: QPushButton) -> QPushButton:
    """Macht einen Knopf zum Hauptknopf — und breit genug für seine eigene
    Beschriftung.

    ``setDefault(True)`` allein genügt nicht, und das ist der Fehler, den man
    erst im Bild sieht: Das Stylesheet setzt für ``QPushButton:default`` ein
    ``font-weight: 600``, gezeichnet wird also halbfett. Qt rechnet die
    bevorzugte Breite aber aus der **normalen** Schrift des Widgets — bei
    „Jetzt trennen" sind das 77 gegen 89 Bildpunkte. Wo ein Layout dem Knopf
    genau seine bevorzugte Breite gibt, und in einer engen Leiste tut es das,
    stand auf dem Hauptknopf „etzt trenne".

    Die Schrift hier am Widget zu setzen behebt beides an einer Stelle: Die
    Zeichnung bleibt, wie sie war, und die Breitenrechnung kennt sie jetzt.
    Fett bleibt dabei die zweite Kodierung neben der Akzentfarbe (Regel 18) —
    sie zu streichen wäre die andere Möglichkeit gewesen und die schlechtere.
    """
    button.setDefault(True)
    font = button.font()
    font.setWeight(QFont.Weight.DemiBold)
    button.setFont(font)
    _keep_the_primary()
    return button


#: Die Fokusgründe, mit denen die Tastatur einen Knopf erreicht: Tab und
#: Umschalt+Tab. Ein Kürzel (``ShortcutFocusReason``) fokussiert einen Knopf
#: nicht, es löst ihn gleich aus.
_KEYBOARD_REASONS: Final = frozenset(
    {Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason}
)

#: Die Fokusgründe, mit denen ein Fenster den Fokus abgibt und zurückbekommt,
#: ohne dass im Fenster jemand gewählt hätte: Fensterwechsel und Menü.
_WINDOW_REASONS: Final = frozenset(
    {Qt.FocusReason.ActiveWindowFocusReason, Qt.FocusReason.PopupFocusReason}
)


def enter_belongs_to_focus(reason: Qt.FocusReason, *, forced: bool) -> bool:
    """Ob Enter dem Knopf gehört, der mit diesem Grund den Fokus bekam.

    Wer mit Tab auf *Abbrechen* geht und Enter drückt, meint *Abbrechen*
    (Bauplan §19.2). Maus, Fensterwechsel und ``setFocus`` aus dem Code
    zeigen dagegen auf keine Absicht für die Eingabetaste; dort bleibt sie
    beim Hauptknopf.

    ``forced`` heißt: Der Fokus ist nicht gegangen, er wurde vertrieben. Qt
    reicht ihn von einem Widget, das gesperrt oder verborgen wird, mit
    ``TabFocusReason`` an das nächste weiter — so landete er während der
    Erzeugung auf *Abbrechen*, ohne dass jemand Tab gedrückt hätte, und
    Enter hätte nach dem Lauf das Ergebnis verworfen.
    """
    return reason in _KEYBOARD_REASONS and not forced


def _dialog_of(widget: QWidget) -> QDialog | None:
    """Der Dialog, in dem ein Knopf sitzt — dieselbe Suche wie Qts ``dialogParent``."""
    current: QWidget | None = widget
    while current is not None and not current.isWindow():
        current = current.parentWidget()
        if isinstance(current, QDialog):
            return current
    return None


class _FocusTakesNoAccent(QObject):
    """Kein Knopf wird Hauptknopf, weil er den Fokus bekommt — Enter gehört
    trotzdem dem Knopf, den die Tastatur gewählt hat.

    ``QPushButton`` mit ``autoDefault`` — in einem ``QDialog`` die Vorgabe —
    macht sich in ``focusInEvent`` selbst zum Default: Akzentfarbe ohne
    halbfette Schrift, und Enter löst ihn aus. In der Aufnahme des
    Workshopfilms stand „Bild wählen …“ nach dem Dateidialog orange neben
    „Erzeugen“; während der Erzeugung ging der Fokus vom gesperrten
    „Erzeugen“ auf „Abbrechen“, und nach dem Lauf stand „Übernehmen“ grau,
    „Abbrechen“ orange — Enter hätte das Ergebnis verworfen. Alle zwölf
    Dialoge mit Hauptknopf taten es (``tests/test_style.py``). Der Zuhörer
    sieht das Fokusereignis vor dem Knopf und nimmt ihm ``autoDefault``,
    solange er nicht der Hauptknopf ist.

    **Ohne ``autoDefault`` reicht ein Knopf Enter an den Dialog weiter, und
    der klickt den Hauptknopf** (RM-334): Tab auf *Abbrechen* und Enter
    verwarf in „Abgeschnittene Schritte verwerfen?“ die Schritte, in
    „Ungesicherte Änderungen“ überschrieb es die Projektdatei. Deshalb merkt
    sich der Zuhörer den Knopf, den die Tastatur erreicht hat
    (:func:`enter_belongs_to_focus`), und klickt ihn selbst, wenn Enter
    kommt. Der Akzent bleibt dabei beim Hauptknopf — er sagt, was empfohlen
    ist; der Fokusrahmen sagt, was Enter und Leertaste auslösen.

    Hier und nicht je Dialog, weil es jeden Knopf betrifft, auch die, die
    ein Dialog erst später baut, und die, denen ein Dialog ``autoDefault``
    ausdrücklich nimmt (:func:`no_primary` und die Nebenknöpfe in Katalog,
    Dichtweg, Unterstützen).
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        #: Der Knopf, auf den die Tastatur zuletzt gegangen ist, solange er den
        #: Fokus hält.
        self._typed_to: QPushButton | None = None
        #: Ob das Widget, das gerade den Fokus abgab, gesperrt oder verborgen
        #: war — gilt für das nächste ``FocusIn`` und dann nicht mehr.
        self._forced = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt gibt den Namen
        kind = event.type()
        # **Ein Fensterwechsel ist keine neue Wahl** (RM-415): Wer mit Tab auf
        # *Abbrechen* ging, kurz in ein anderes Fenster wechselte und
        # zurückkam, meinte mit Enter weiter *Abbrechen*. Qt meldet Gehen und
        # Wiederkommen als ``ActiveWindowFocusReason`` (ein Menü als
        # ``PopupFocusReason``); dabei bleibt die Wahl der Tastatur stehen.
        away = isinstance(event, QFocusEvent) and event.reason() in _WINDOW_REASONS
        if kind == QEvent.Type.FocusOut:
            if isinstance(watched, QWidget):
                self._forced = not (watched.isEnabled() and watched.isVisible())
            if watched is self._typed_to and not away:
                self._typed_to = None
            return False
        if kind == QEvent.Type.FocusIn:
            forced, self._forced = self._forced, False
            if isinstance(watched, QPushButton) and not watched.isDefault():
                if watched.autoDefault():
                    watched.setAutoDefault(False)
                if away and watched is self._typed_to:
                    return False
                typed = isinstance(event, QFocusEvent) and enter_belongs_to_focus(
                    event.reason(), forced=forced
                )
                self._typed_to = watched if typed and _dialog_of(watched) is not None else None
            return False
        if (
            kind == QEvent.Type.KeyPress
            and watched is self._typed_to
            and isinstance(event, QKeyEvent)
            and isinstance(watched, QPushButton)
        ):
            return self._enter(watched, event)
        return False

    @staticmethod
    def _enter(button: QPushButton, event: QKeyEvent) -> bool:
        """Enter auf dem per Tastatur gewählten Knopf: ihn klicken, nicht den Hauptknopf.

        Dieselbe Bedingung wie ``QDialog.keyPressEvent``, damit nur die Taste
        umgeleitet wird, die der Dialog sonst an seinen Default gäbe; ein
        Knopf mit ``autoDefault`` oder als Default behandelt Enter selbst.
        """
        key = event.key()
        modifiers = event.modifiers()
        plain = modifiers == Qt.KeyboardModifier.NoModifier or (
            key == Qt.Key.Key_Enter and modifiers == Qt.KeyboardModifier.KeypadModifier
        )
        if (
            key not in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            or not plain
            or button.autoDefault()
            or button.isDefault()
            or not (button.isEnabled() and button.hasFocus())
        ):
            return False
        button.click()
        return True


def _keep_the_primary() -> None:
    """Den Zuhörer einmal je Anwendung anmelden — am einen Filter der Anwendung."""
    application = QCoreApplication.instance()
    if application is None or application.findChildren(_FocusTakesNoAccent):
        return
    app_events.listen(
        _FocusTakesNoAccent(application),
        (QEvent.Type.FocusIn, QEvent.Type.FocusOut, QEvent.Type.KeyPress),
    )


def make_danger(button: QPushButton) -> QPushButton:
    """Macht einen Knopf zum Verwerfen kenntlich — das Fehlerrot als Fläche.

    *Abbrechen* unter *Übernehmen* (Robert, 11.09.2026: „das abbrechen mit
    rotem hintergrund"): Beide stehen übereinander, beide gleich breit, und
    der eine wirft weg, was der andere ausführt. Die Farbe kommt aus der
    Rolle ``error`` der Palette, je Thema in der Fassung, die auf der
    Fensterfläche lesbar ist — das Wort auf dem Knopf ist die zweite
    Kodierung (Regel 18), die Schrift darauf rechnet :func:`readable_on`.
    Über eine Eigenschaft und nicht über ein Stylesheet je Widget, aus
    demselben Grund wie :func:`set_level`.
    """
    button.setProperty("danger", True)
    _repolish(button)
    return button


def make_large_target(button: QPushButton) -> QPushButton:
    """Markiert einen Knopf als große, fehlertolerante Trefferfläche.

    Ein bloßes ``setMinimumHeight(TARGET_SIZE)`` überlebt das globale
    Stylesheet nicht: Qt setzt dessen ``min-height`` beim Polieren erneut und
    machte aus 44 Punkten wieder 26. Der opt-in-Selektor im Stylesheet hält
    den Vertrag in derselben Schicht, die ihn sonst überschreiben würde.
    """
    button.setProperty("targetSize", "large")
    _repolish(button)
    return button


def no_primary(dialog: QWidget) -> None:
    """Nimmt einem Fenster den Hauptknopf, den es nie bestellt hat.

    ``QDialog`` vergibt beim **ersten** ``show()`` von selbst einen Default —
    Qt nimmt dafür den ersten Knopf mit ``autoDefault``, gleich wo er sitzt.
    Damit trägt er die Akzentfarbe aus ``QPushButton:default``, ohne die
    halbfette Schrift, die :func:`make_primary` daneben setzt: Bedeutung
    allein über Farbe, also gegen Regel 18.

    Gefunden wird das nur am **angezeigten** Fenster. Vor dem ``show()``
    meldet ``isDefault()`` überall ``False``, und ein Wächter, der den
    Quelltext nach ``setDefault(True)`` durchsucht, sieht nichts: Es ruft ja
    niemand.

    Gedacht ist die Funktion für ein Fenster, das gar keine Handlung anbietet
    und nur einen Ausgang hat — dort wäre der Akzent auf „Schließen" eine
    Empfehlung, den Dialog zu verlassen. Wer eine Handlung hat, nimmt
    :func:`make_primary`; ein Fenster ohne akzentuierten Knopf lässt sonst
    suchen.
    """
    for button in dialog.findChildren(QPushButton):
        button.setAutoDefault(False)
        button.setDefault(False)
    # Ohne ``autoDefault`` gäbe ein per Tab erreichter Knopf Enter an einen
    # Dialog ohne Default weiter, und nichts geschähe; der Zuhörer gibt sie ihm.
    _keep_the_primary()


#: Der Objektname, an dem das Stylesheet eine Menü-Überschrift erkennt.
MENU_HEADING = "menuHeading"


def menu_heading(menu: QMenu, title: str) -> QWidgetAction:
    """Setzt eine **sichtbare** Kategorie-Überschrift in ein Menü.

    ``QMenu.addSection`` tut das nicht: Auf Windows ist ein Abschnitt
    derselbe Trennstrich wie ``addSeparator``, und der Text wird verworfen.
    Gemessen an einem Menü mit zwei Einträgen, Kontrastpunkte gegen den
    Menügrund — Überschrift **1201**, nackter Trennstrich **1201**, und
    dieselbe Höhe: Der Titel bekam nicht einmal Platz. Dasselbe in einem
    Prozess, der nie ein Stylesheet gesetzt hat (437 gegen 437), und
    dasselbe mit sechs verschiedenen ``QMenu::separator``-Regeln. Das
    Stylesheet war unschuldig; die Kategorienamen, die der Menüaufbau mit
    fünfzehn Zeilen Begründung setzt, erschienen nie.

    Ein Label in einer ``QWidgetAction`` erscheint (1333 Punkte). Und es
    **zählt trotzdem nicht als Zeile**: ``setSeparator(True)`` hält
    ``isSeparator()`` wahr — die Zwölf-Zeilen-Grenze aus §35 rechnet danach,
    und eine Überschrift ist keine Zeile, die man anklickt. Beides zusammen
    ist gemessen: zwei gezählte Zeilen statt drei, bei unverändert 439
    hellen Punkten im Bild.
    """
    from PySide6.QtWidgets import QLabel

    label = QLabel(title, menu)
    label.setObjectName(MENU_HEADING)
    set_level(label, "caption")
    font = label.font()
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)

    action = QWidgetAction(menu)
    action.setDefaultWidget(label)
    # Der Text steht **auch** an der Aktion, nicht nur im Label: Der
    # Barrierefreiheitsbaum liest ihn dort, und der Wächter, der jede
    # Kategorie bei ihrem Namen verlangt, fragt danach. Genau dieser Wächter
    # war grün, während der Name nie erschien — gesetzt heißt nicht gezeigt.
    action.setText(title)
    # Kein Klickziel: Die Überschrift benennt, sie tut nichts.
    action.setEnabled(False)
    action.setSeparator(True)
    menu.addAction(action)
    return action


#: Der Objektname, an dem das Stylesheet eine Trennlinie erkennt.
DIVIDER = "divider"


def divider(parent: QWidget) -> QWidget:
    """Eine senkrechte Linie zwischen zwei Auskünften, die einander nicht
    erklären.

    Statuszeile und Kopfzeile reihen Labels nebeneinander, und der Abstand
    dazwischen ist derselbe wie der zwischen den Wörtern einer Zeile:
    „… bis zum 30.10.2026  51 g · 3 h 30 min" liest sich als **ein** Satz,
    obwohl links der Lizenzstand steht und rechts der Materialverbrauch. In
    der Kopfzeile dasselbe mit „… 220 mm   PLA".

    Innerhalb einer Auskunft trennt weiter der Mittelpunkt („51 g · 3 h"):
    Was zusammengehört, bleibt in einer Zeile; was verschiedene Fragen
    beantwortet, bekommt diese Linie.
    """
    from PySide6.QtWidgets import QFrame

    line = QFrame(parent)
    line.setObjectName(DIVIDER)
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFixedWidth(1)
    return line


def rule(parent: QWidget) -> QWidget:
    """Eine waagerechte Linie zwischen zwei Blöcken, die einander nicht erklären.

    Das Gegenstück zu :func:`divider`, nur für Untereinander: Im Merkmalsfenster
    stehen mehrere Handlungen mit je eigenen Feldern, und ein Abstand allein
    trennt sie nicht — an einer Bohrung folgen auf drei Zahlenfelder wieder
    drei, und wer nicht auf die Überschriften sieht, liest sie als eine Reihe
    (Robert, 10.09.2026: „die unterschiedlichen einstellungen noch abgrenzen
    durch einen strich").
    """
    from PySide6.QtWidgets import QFrame

    line = QFrame(parent)
    line.setObjectName(DIVIDER)
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


def _repolish(widget: QWidget) -> None:
    """Qt liest dynamische Eigenschaften nur beim Aufbau — hier noch einmal."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


#: Wie weit die Fläche des aktiven Werkzeugs zum Fenster hin gemischt wird.
#:
#: Der Wert entscheidet nicht über Lesbarkeit — dafür steht die Kante ein —,
#: sondern über die Lautstärke. Gemessen im dunklen Thema gegen die
#: Fensterfarbe: 0,25 gibt 1,59, 0,35 gibt 1,90, 0,50 gibt 2,52. Die
#: Zebrafläche, mit der die Fläche nicht zu verwechseln sein darf, liegt bei
#: 1,13, und die Linienfarbe des Fensters bei 2,30. 0,35 hält den Abstand nach
#: unten (2,15 gegen das Zebra) und bleibt unter der Linienfarbe — das aktive
#: Werkzeug ist damit leiser als jeder Rahmen im Fenster.
_ACTIVE_MIX: Final = 0.35


def _mixed(front: str, back: str, share: float) -> str:
    """Mischt zwei Hexfarben, ``share`` ist der Anteil der vorderen."""
    first = [int(front[i : i + 2], 16) for i in (1, 3, 5)]
    second = [int(back[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(
        f"{round(a * share + b * (1 - share)):02x}" for a, b in zip(first, second, strict=True)
    )


def active_fill(theme: Theme) -> str:
    """Die Fläche, die ein aktives Werkzeug trägt.

    **Der Akzent gehört dem Flüchtigen und genau einem Dauerhaften.** Vier
    Flächen im Fenster leuchteten dauerhaft in Bernstein — der Hauptknopf, das
    aktive Werkzeug, die Kartenkante, das ablaufende Datum —, und vier
    Dauerleuchten machen aus einem Signal eine Tapete. Das aktive Werkzeug
    sagt „du bist hier" und nicht „tu das"; es bekommt deshalb eine gedämpfte
    Fläche, während die volle Farbe dem Hauptknopf bleibt.

    Was die Aussage danach trägt, ist die **Kante**, und das ist der Teil, der
    im hellen Thema mehr gewinnt als die Fläche verliert: Der Rahmen nahm
    bisher ``highlight`` und kam damit auf 1,70 gegen das Fenster, die Fläche
    auf dieselben 1,70 — der aktive Knopf riss dort die 3,0 aus WCAG 1.4.11
    an keiner einzigen Stelle. Mit ``accent_line`` sind es 3,01, und im
    dunklen Thema bleiben es dieselben 5,54 wie vorher.
    """
    colours = THEMES[theme]
    return _mixed(colours["highlight"], colours["window"], _ACTIVE_MIX)


#: Die zwei Pfeile am Zahlenfeld, als Zeichnung ohne Datei im Paket.
#:
#: Ein Dreieck, zweimal — nach oben und nach unten. ``{colour}`` füllt die
#: Textfarbe des Themas ein.
#: Die Zeichenfläche ist genau so groß wie der Platz im Stylesheet — ein
#: Dreieck aus einer 8-zu-5-Fläche in ein 8-zu-4-Feld gequetscht sitzt unscharf.
_ARROW_SVG: Final = {
    "up": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4">'
    '<path d="M0 4 L4 0 L8 4 Z" fill="{colour}"/></svg>',
    "down": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 4">'
    '<path d="M0 0 L4 4 L8 0 Z" fill="{colour}"/></svg>',
}


def arrow_files(theme: Theme) -> dict[str, str] | None:
    """Legt die Pfeile des Zahlenfelds als Dateien ab und nennt ihre Pfade.

    **Warum überhaupt Dateien.** Qt hört auf, die Unterelemente eines
    ``QSpinBox`` selbst zu zeichnen, sobald ein Stylesheet an ihm eine
    Rahmeneigenschaft setzt — und das tut die Regel, die allen Eingabefeldern
    ihren Radius gibt. Übrig blieben zwei leere Kästchen. Ein Dreieck aus
    Rahmenkanten, wie man es in HTML baut, hilft nicht: Qt füllt die Fläche
    und zeichnet einen hellen Block. Bleibt ein Bild, und ein Bild braucht in
    einem Stylesheet einen Pfad.

    **Warum nicht im Paket.** Eine mitgelieferte Datei hätte eine feste Farbe,
    also bräuchte jedes Thema seine eigene — und eine Datei, die beim
    Paketieren vergessen wird, nimmt den Pfeilen ihr Aussehen genauso still,
    wie es hier verloren ging. Geschrieben wird deshalb in den Cache (§38), der
    jederzeit gelöscht werden darf; beim nächsten Start steht er wieder da.

    Gibt ``None`` zurück, wenn sich nichts schreiben lässt. Dann bleiben die
    Knöpfe leer — das ist der Zustand von vorher und kein Grund, eine
    Anwendung nicht zu starten.
    """
    from app.core.paths import ensure_dir, user_cache_dir

    try:
        folder = ensure_dir(user_cache_dir() / "style")
        paths = {}
        for direction, template in _ARROW_SVG.items():
            target = folder / f"spin-{direction}-{theme}.svg"
            target.write_text(template.format(colour=THEMES[theme]["text"]), encoding="utf-8")
            paths[direction] = target.as_posix()
        return paths
    except OSError as problem:
        _log.info("Die Pfeile des Zahlenfelds ließen sich nicht ablegen: %s", problem)
        return None


#: Der Haken in Listen und Bäumen, als Zeichnung ohne Datei im Paket.
#:
#: Dieselbe Form wie das Ankreuzfeld eines Dialogs — ein Kästchen von
#: ``ROOMY`` Punkten in der Feldfläche, das Häkchen in der Textfarbe —, damit
#: ein Haken in einer Liste nicht anders aussieht als einer daneben.
_CHECK_BOX: Final = (
    '<rect x="0.5" y="0.5" width="11" height="11" rx="2" fill="{base}" stroke="{edge}"/>'
)
_CHECK_SVG: Final = {
    "unchecked": _CHECK_BOX,
    "checked": _CHECK_BOX + '<path d="M2.8 6.3 L5 8.5 L9.3 3.6" fill="none" stroke="{mark}" '
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "indeterminate": _CHECK_BOX
    + '<path d="M3 6 H9" stroke="{mark}" stroke-width="1.6" stroke-linecap="round"/>',
}


def check_files(theme: Theme) -> dict[str, str] | None:
    """Legt die Haken der Listen als Dateien ab und nennt ihre Pfade.

    **Warum überhaupt Bilder.** In einer markierten Zeile setzt die Regel
    ``::item:selected`` die Schriftfarbe auf ``highlight_text``, und Fusion
    zeichnet das Häkchen des Listenhakens in genau dieser Farbe — im dunklen
    Thema dunkel auf das dunkle Kästchen. Ein gesetzter Haken in der
    gewählten Zeile sah damit aus wie ein leeres schwarzes Kästchen, während
    darunter „4 von 4 Körpern“ stand; in den übrigen Zeilen war das Häkchen
    ein um ein Fünftel abgedunkeltes Grau und wirkte gesperrt. Mit eigenem
    Bild ist der Haken in jeder Zeile derselbe.

    Ablage und Rückfall wie bei :func:`arrow_files`: im Cache, und ohne
    Schreibrecht ``None`` — dann zeichnet Qt wieder selbst.
    """
    from app.core.paths import ensure_dir, user_cache_dir

    colours = THEMES[theme]
    try:
        folder = ensure_dir(user_cache_dir() / "style")
        paths = {}
        for state, drawing in _CHECK_SVG.items():
            for locked in (False, True):
                edge = colours["disabled"] if locked else colours["line"]
                mark = colours["disabled"] if locked else colours["text"]
                name = f"{state}-disabled" if locked else state
                target = folder / f"check-{name}-{theme}.svg"
                body = drawing.format(base=colours["base"], edge=edge, mark=mark)
                target.write_text(
                    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">{body}</svg>',
                    encoding="utf-8",
                )
                paths[name] = target.as_posix()
        return paths
    except OSError as problem:
        _log.info("Die Haken der Listen ließen sich nicht ablegen: %s", problem)
        return None


def _check_rules(checks: dict[str, str] | None) -> str:
    """Die Stylesheet-Zeilen, die den Listenhaken ihre Bilder geben."""
    if not checks:
        return ""
    views = ("QTreeView", "QListView", "QTableView")

    def selector(state: str) -> str:
        return ", ".join(f"{view}::indicator{state}" for view in views)

    return f"""
{selector("")} {{ width: {ROOMY}px; height: {ROOMY}px; }}
{selector(":unchecked")} {{ image: url("{checks["unchecked"]}"); }}
{selector(":checked")} {{ image: url("{checks["checked"]}"); }}
{selector(":indeterminate")} {{ image: url("{checks["indeterminate"]}"); }}
{selector(":unchecked:disabled")} {{ image: url("{checks["unchecked-disabled"]}"); }}
{selector(":checked:disabled")} {{ image: url("{checks["checked-disabled"]}"); }}
{selector(":indeterminate:disabled")} {{ image: url("{checks["indeterminate-disabled"]}"); }}
"""


def _arrow_rules(arrows: dict[str, str] | None, line: str = "", hover: str = "") -> str:
    """Die Stylesheet-Zeilen, die die Pfeile ins Zahlenfeld und in die
    Combobox setzen.

    ``line`` und ``hover`` gehören zum Pfeilfeld der Combobox: Es steht
    **hier** und nicht bei den übrigen Feldregeln, weil Qt den Pfeil darin
    nicht mehr selbst zeichnet, sobald es eine eigene Regel hat — ohne
    Pfeildateien wäre das gestaltete Feld also leer, und dann ist Qts
    native Zeichnung das kleinere Übel."""
    if not arrows:
        return ""
    return f"""
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url("{arrows["up"]}");
    width: {NORMAL}px;
    height: {SPACE}px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url("{arrows["down"]}");
    width: {NORMAL}px;
    height: {SPACE}px;
}}
/* **Das Pfeilfeld schnitt die gerundete Ecke von innen an.** Ohne eigene
   Regel zeichnet Qt es als Rechteck bis an den Rahmen — an einem Feld mit
   Radius liegt dann eine gerade Kante in der Rundung, und das sieht aus wie
   ein Zeichenfehler. Es bekommt deshalb dieselben Radien wie das Feld und
   dieselbe Trennkante wie das Zahlenfeld nebenan. */
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: {WIDE}px;
    background: transparent;
    border-left: 1px solid {line};
    border-top-right-radius: {SPACE}px;
    border-bottom-right-radius: {SPACE}px;
}}
QComboBox::drop-down:hover {{ background: {hover}; }}
/* Die Combobox braucht ihn aus demselben Grund: Sobald ``::drop-down`` eine
   eigene Regel hat, hört Qt auf, den Pfeil selbst zu zeichnen. Gemessen —
   vierzehn Farben im Pfeilfeld vorher, zwei danach, also Fläche und
   Trennlinie und sonst nichts. Es ist derselbe Pfeil wie am Zahlenfeld;
   zwei Zeichnungen für dieselbe Geste wären zwei, die auseinanderlaufen. */
QComboBox::down-arrow {{
    image: url("{arrows["down"]}");
    width: {NORMAL}px;
    height: {SPACE}px;
}}
"""


def stylesheet(
    theme: Theme,
    base_point_size: int,
    arrows: dict[str, str] | None = None,
    checks: dict[str, str] | None = None,
) -> str:
    """Das Stylesheet der Anwendung, gefüllt aus Thema und Schriftgröße.

    ``arrows`` sind die Pfeile des Zahlenfelds, siehe :func:`arrow_files`. Ohne
    sie bleiben die Auf- und Ab-Knöpfe leer — für einen Test, der nur die
    Farben liest, ist das gleichgültig. ``checks`` sind die Haken der Listen
    (:func:`check_files`); ohne sie zeichnet Qt sie selbst.
    """
    colours = THEMES[theme]
    sizes = type_scale(base_point_size)
    window = colours["window"]
    base = colours["base"]
    text = colours["text"]
    # Zwei Farben, nicht eine. ``muted`` ist Nebentext — Maße, Einheiten,
    # Spaltenköpfe, Gruppentitel, der stille Reiter: leise, aber zu lesen.
    # ``disabled`` heißt gesperrt und soll genau das zeigen. Beides lag auf
    # demselben Wert, und damit war beides falsch: Ein Fünftel aller
    # Beschriftungen trug die Sperrfarbe und kam auf 2,59 Kontrast im hellen
    # Thema, während ein gesperrter Knopf sich von einem stillen Spaltenkopf
    # nicht unterschied.
    muted = colours["muted"]
    disabled = colours["disabled"]
    line = colours["line"]
    highlight = colours["highlight"]
    on_highlight = colours["highlight_text"]
    highlight_pressed = colours["highlight_pressed"]
    from app.ui.palette import ROLES, readable_on

    danger = ROLES["error"]
    on_danger = readable_on(danger)
    accent_line = colours["accent_line"]
    hover = colours["alternate"]
    tooltip = colours["tooltip"]

    # Der Fokusring nimmt dieselbe Farbe wie die Akzentkante, und aus demselben
    # Grund: Er muss auf seinem Untergrund zu sehen sein. ``highlight`` ist
    # dafür nur im dunklen Thema geeignet — der Bernstein bringt gegen das
    # helle Fenster 1,70 und gegen ein weißes Feld 2,06, und WCAG 1.4.11
    # verlangt für die Umrandung eines Bedienelements 3,0. Ein Ring, den man
    # nicht sieht, ist für den, der ohne Maus arbeitet, gar keiner.
    # ``accent_line`` ist im dunklen Thema derselbe Bernstein und im hellen der
    # abgedunkelte Ton daneben: 3,66 auf Weiß, 3,01 auf dem Fenster.
    focus = accent_line

    # Der Rahmen eines Eingabefelds ist immer zwei Punkte breit — im
    # Ruhezustand wie im Fokus. Er war einen breit und wuchs beim Fokus auf
    # zwei, und das brach das Aufklappmenü jeder Combobox: Qt leitet die Höhe
    # des Popups aus dem Innenrechteck der Combobox ab, verlor durch den
    # zweiten Rahmenpunkt zwei Punkte, kippte damit in den Rollbetrieb und
    # verlor an dessen zwei Pfeilen weitere zehn. Zwölf Punkte sind ein halber
    # Eintrag: Wer „Bezugspunkt" anklickte, sah „Mündung" und darunter „Mitte"
    # waagerecht durchgeschnitten. Gemessen bei zwei, drei, vier und fünf
    # Einträgen, in beiden Themen, und es traf jede Combobox, die den Fokus
    # hatte — also jede, die man anklickt.
    #
    # Der Fokus sagt es deshalb über **Farbe und Strichart**: Der Ring bleibt
    # zwei Punkte breit und wird gestrichelt. Ein erster Anlauf ließ nur die
    # Farbe wechseln, mit dem Argument, ein Punkt Rahmenbreite sei ohnehin
    # keine wahrnehmbare Kodierung gewesen — das stimmt und trägt trotzdem
    # nicht: Regel 18 verlangt die zweite Kodierung, nicht den Nachweis, dass
    # die alte auch keine war. Kontrast unverändert 8,02 im dunklen Thema.
    #
    # **Und der Ruhezustand behält die volle Linienfarbe.** Ein erster Anlauf
    # dämpfte sie zur Feldfläche hin, damit der doppelt so breite Rahmen so
    # leise wirkt wie der einfache vorher — das sah im Bild gut aus und war
    # gemessen falsch: 1,90 statt 3,33 im dunklen Thema, also unter den 3,0,
    # die WCAG 1.4.11 für die Umrandung eines Bedienelements verlangt. Und die
    # Fläche trägt die Grenze nicht mit: Feld gegen Fenster sind 1,45. Wer den
    # Rahmen dämpft, nimmt dem Feld seine einzige Kante.
    field_line = line

    # Die Fläche des aktiven Werkzeugs und dieselbe Fläche unter dem Zeiger.
    # Der überfahrene Ton ist nicht die Zebrafarbe, sondern derselbe Akzent
    # eine Stufe lauter: Ein aktiver Knopf, der beim Überfahren ins Graue
    # wechselt, sieht aus, als hätte er sich abgeschaltet.
    active = active_fill(theme)
    active_hover = _mixed(highlight, window, _ACTIVE_MIX + 0.15)

    # Eine Fläche, die über dem Fenster steht statt in ihm: die Hauptaktionen
    # der Auswahl (RM-510). Sie trugen die Füllung eines Eingabefelds (``base``)
    # und sahen aus wie ein Feld, in das man tippt.
    raised = _mixed(colours["text"], window, 0.07)

    return f"""
/* --- Typografie: vier Stufen, Größe und Gewicht und Farbe --------------- */
*[level="title"] {{ font-size: {sizes["title"][0]}pt; font-weight: {sizes["title"][1]}; }}
*[level="section"] {{ font-size: {sizes["section"][0]}pt; font-weight: {sizes["section"][1]}; }}
*[level="body"] {{ font-size: {sizes["body"][0]}pt; font-weight: {sizes["body"][1]}; }}
*[level="caption"] {{
    font-size: {sizes["caption"][0]}pt;
    font-weight: {sizes["caption"][1]};
    color: {muted};
}}


/* --- Knöpfe: Haupt- und Nebenknopf sind zu unterscheiden ---------------- */
QPushButton {{
    background: {window};
    border: 1px solid {line};
    border-radius: {SPACE}px;
    padding: {TIGHT}px {ROOMY}px;
    min-height: {WIDE}px;
}}
/* Die Höhe im Selektor meint nur die Inhaltsbox. Je Seite kommen vier Punkte
   Padding und ein Punkt Rahmen hinzu; im Fokus ersetzen drei Punkte Padding
   plus zwei Punkte Rahmen dieselbe Summe. So ergeben sich exakt mindestens
   TARGET_SIZE Punkte, ohne große Systemschrift auf dieses Maß zu deckeln. */
QPushButton[targetSize="large"] {{
    min-height: {TARGET_SIZE - 2 * TIGHT - 2}px;
}}
QPushButton:hover {{ background: {hover}; }}
/* Das Info-Zeichen neben einer Überschrift: ein Kreis mit „i" darin, dessen
   Tooltip den Absatz trägt, der vorher unter der Zeile stand. Die Erklärung
   verschwindet damit nicht, sie belegt nur keine drei Zeilen mehr, solange
   niemand sie liest (Robert, 10.09.2026: „die beschreibungen die über den
   buttons zum übernehmen dastehen auch in einen tooltipp"). Der Buchstabe ist
   die zweite Kodierung neben der Form — Regel 18 gilt auch für ein Zeichen,
   das nur eine Erklärung ankündigt. */
QToolButton#infoDot {{
    border: 1px solid {line};
    border-radius: 9px;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    padding: 0px;
    color: {muted};
    background: transparent;
    font-weight: 600;
}}
QToolButton#infoDot:hover {{ color: {text}; border-color: {text}; background: {hover}; }}
QToolButton#infoDot:focus {{ color: {text}; border: 2px dashed {highlight}; }}
QPushButton:pressed {{ background: {line}; }}
QPushButton:default {{
    background: {highlight};
    color: {on_highlight};
    border-color: {highlight};
    font-weight: 600;
}}
QPushButton:default:hover {{ background: {highlight}; border-color: {text}; }}
QPushButton:disabled {{ color: {disabled}; border-color: {line}; background: {window}; }}
/* Der Hauptknopf gibt beim Drücken nach. Ohne eigene Regel gewann hier
   ``:default`` — es steht später und wiegt gleich schwer —, und der lauteste
   Knopf der Anwendung war der einzige, der auf einen Klick nichts tat.

   **Und die Regel allein genügte nicht.** Sie nahm ``accent_line``, und die
   *ist* im dunklen Thema der Bernstein selbst: gedrückt sah aus wie
   losgelassen, im voreingestellten Thema, auf jedem Hauptknopf. Im hellen
   fiel es nie auf, weil dort der abgedunkelte Ton steht. Jetzt steht der
   Druckzustand als eigene Farbe in der Themen-Tabelle — 1,78 Unterschied zum
   Ruhezustand, dunkle Schrift darauf 4,47. */
QPushButton:default:pressed {{
    background: {highlight_pressed};
    border-color: {highlight_pressed};
}}
/* Ein Knopf, der verwirft (``make_danger``): das Fehlerrot der Palette als
   Fläche, damit *Abbrechen* neben dem bernsteinfarbenen *Übernehmen* nicht
   wie dessen Zwilling aussieht. Der Rahmen wechselt beim Überfahren wie am
   Hauptknopf; gedrückt wird die Fläche dunkler über den Rahmen der Fläche. */
QPushButton[danger="true"] {{
    background: {danger};
    color: {on_danger};
    border-color: {danger};
}}
QPushButton[danger="true"]:hover {{ background: {danger}; border-color: {text}; }}
QPushButton[danger="true"]:pressed {{ background: {danger}; border-color: {on_danger}; }}
/* Zwei Bildpunkte Rahmen statt einem, und der Innenabstand gibt den einen
   wieder her: sonst wandert die Beschriftung beim Durchtabben um einen Punkt,
   und ein Dialog zittert unter der Tabulatortaste. */
QPushButton:focus {{
    border: 2px solid {focus};
    padding: {TIGHT - 1}px {ROOMY - 1}px;
}}

/* **Rahmenlos sah nicht nach Knopf aus.** Der Ruhezustand trug eine
   durchsichtige Kante, sichtbar wurde sie erst beim Überfahren — und in der
   Bewegen-Karte stehen drei Modusknöpfe nebeneinander, von denen nur der
   gewählte eine Fläche hat: Die anderen beiden las man als Beschriftungen.
   Die Ruhekante nimmt dieselbe Linienfarbe wie jeder andere Knopf und jedes
   Feld — ein erster Anlauf griff zur leiseren Zebrafarbe, und die ist gegen
   die Dialogfläche **1,13** im dunklen und **1,01** im hellen Thema: eine
   Kante, die es gibt und die niemand sieht. Mit der Linienfarbe sind es 2,30
   und 2,00, so viel wie der Rahmen eines Eingabefelds; was diese Farbe
   leistet, ist eine Frage an das Thema, dass der Knopf sie nicht
   unterschreitet, eine an das Stylesheet. Wer keine Kante will, setzt sie wie
   die Kopfzeile unten ausdrücklich auf ``none``. */
QToolButton {{
    border: 1px solid {line};
    border-radius: {SPACE}px;
    padding: {TIGHT}px {NORMAL}px;
}}
QToolButton:hover {{ background: {hover}; border-color: {line}; }}
/* **Das aktive Werkzeug sagt „du bist hier", nicht „tu das"** — die Begründung
   und die Messwerte stehen bei ``active_fill``. Die Schrift wird hier nicht
   gesetzt: Sie bleibt die des Themas, und damit wechselt beim Einschalten
   eines Werkzeugs allein die Fläche. Das ist auch die Bedingung dafür, dass
   ein **Symbol** neben der Beschriftung stehen bleiben darf — auf voller
   Akzentfläche brauchte es eine eigene dunkle Fassung, sonst standen Zeichen
   und Wort derselben Aussage in entgegengesetzten Farben.
   Und der überfahrene aktive Knopf antwortet: Ohne eigene Regel gewinnt
   ``:checked`` gegen ``:hover``, und dann ist der eine Knopf im Fenster, den
   man am ehesten wieder anklickt, der einzige ohne Rückmeldung. */
QToolButton:checked {{ background: {active}; border-color: {accent_line}; }}
QToolButton:checked:hover {{ background: {active_hover}; border-color: {accent_line}; }}
QToolButton:focus {{
    border: 2px solid {focus};
    padding: {TIGHT - 1}px {NORMAL - 1}px;
}}

/* **Gesperrt war nicht zu erkennen.** Für das Ankreuzfeld gab es gar keine
   Regel; Qt zeichnet das Kästchen dann nativ und in beiden Zuständen
   gleich, während die Beschriftung daneben über die Palette verblasste —
   ein Haken, der gesetzt aussieht und sich nicht setzen lässt. Beides fällt
   jetzt zusammen auf die Sperrfarbe, und der Rahmen des Kästchens mit. */
QCheckBox:disabled, QRadioButton:disabled {{ color: {disabled}; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: {ROOMY}px;
    height: {ROOMY}px;
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    border: 1px solid {disabled};
    background: transparent;
}}

/* Panel-Kopfzeilen sind dauerhaft „gedrückt"; eingefärbt wären sie die
   lauteste Fläche im Fenster für die stillste Aussage. */
QToolButton#sectionHeading {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {line};
    border-radius: 0;
    padding: {NORMAL}px {NORMAL}px {TIGHT}px {NORMAL}px;
    text-align: left;
}}
QToolButton#sectionHeading:hover {{ background: {hover}; }}
QToolButton#sectionHeading:checked {{ background: transparent; color: {text}; }}
QToolButton#sectionHeading:checked:hover {{ background: {hover}; }}

/* Eine Beispielkachel ist semantisch und funktional ein großer Knopf mit zwei
   Zeilen darin. Ihre eigene Innenkante kommt aus dem Layout; die gewöhnliche
   Knopfpolsterung würde sie ein zweites Mal auftragen. */
QPushButton#exampleTile {{
    background: {base};
    border: 1px solid {line};
    border-radius: {NORMAL}px;
    min-height: 0;
    padding: 0;
}}
/* Überfahren wechselt die **Fläche**, Fokus den **Rahmen**. Beides über den
   Rahmen zu sagen war im dunklen Thema — dem voreingestellten — keine Aussage:
   dort ist ``highlight`` derselbe Bernstein wie ``focus``, und die zwei
   Zustände unterschieden sich um einen Bildpunkt Rahmenbreite. Wer mit dem
   Tabulator durch die neun Kacheln geht, sah nicht, welche die Eingabetaste
   auslösen würde. */
QPushButton#exampleTile:hover {{ background: {hover}; }}
QPushButton#exampleTile:focus {{ border: 2px solid {focus}; padding: 0; }}
QPushButton#exampleTile:pressed {{ background: {line}; }}

/* Die technische Modellzeile liegt in der dunklen rechten Seitenfläche auch
   im hellen Thema. Eine eigene, palettengesteuerte Infofläche hält Schrift
   und Untergrund deshalb in beiden Themen als geprüftes Paar zusammen. */
QLabel#chatModelHint {{
    color: {text};
    background: {base};
    border: 1px solid {line};
    border-radius: {SPACE}px;
    padding: {TIGHT // 2}px {TIGHT}px;
}}

/* Die Auswahlhandlungen bilden den unteren Teil derselben rechten Karte.
   Eine sichtbare Kante trennt sie von Bericht und Chat; die Beschriftungen
   bleiben in schmalen Fenstern linksbündig und nutzen die ganze Breite. */
QWidget#selectionOperations {{
    border-top: 1px solid {line};
}}
QWidget#selectionOperations QToolButton {{
    text-align: left;
}}
QWidget#selectionOperations QToolButton#quickOperation {{
    background: {raised};
    border: 1px solid {line};
    border-radius: {SPACE}px;
    padding: {TIGHT}px {NORMAL}px;
}}
QWidget#selectionOperations QToolButton#quickOperation:hover {{
    background: {hover};
    border-color: {accent_line};
}}
QWidget#selectionOperations QToolButton#quickOperation:focus {{
    border: 2px dashed {focus};
}}
/* Die Liste darunter besteht aus flachen Zeilen (RM-510): ohne Fläche und
   Rahmen, bis der Zeiger darüber steht — so stehen die Hauptaktionen vorn und
   die Liste dahinter, und der Fokus bleibt gestrichelt sichtbar. */
QWidget#selectionOperations QToolButton#operationRow {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {SPACE}px;
    padding: {TIGHT // 2}px {TIGHT}px;
}}
QWidget#selectionOperations QToolButton#operationRow:hover {{
    background: {hover};
    border-color: {line};
}}
QWidget#selectionOperations QToolButton#operationRow:focus {{
    border: 2px dashed {focus};
}}
/* Das Suchfeld der Werkzeugleiste ist ein Knopf, der aussieht wie ein Feld
   (RM-506): Fläche und Rahmen eines Eingabefelds, Text in der Nebenfarbe,
   linksbündig — wer es sieht, weiß, dass man hier sucht. */
QPushButton#functionSearch {{
    background: {base};
    border: 1px solid {line};
    border-radius: {SPACE}px;
    color: {muted};
    min-height: 0px;
    padding: {TIGHT // 2}px {NORMAL}px;
    text-align: left;
}}
QPushButton#functionSearch:hover {{ border-color: {accent_line}; }}
QPushButton#functionSearch:focus {{ border: 2px dashed {focus}; }}
/* Der Pfeil vor einer Handlung im Merkmalfenster klappt sie auf (RM-510).
   Offen sagt er mit seiner Richtung, nicht mit einer Akzentfläche — die
   gehört dem aktiven Werkzeug. */
QToolButton#actionHeading {{
    background: transparent;
    border: 1px solid transparent;
    padding: 0px;
}}
QToolButton#actionHeading:hover, QToolButton#actionHeading:checked:hover {{
    background: {hover};
    border-color: {line};
}}
QToolButton#actionHeading:checked {{ background: transparent; border-color: transparent; }}
QToolButton#actionHeading:focus {{ border: 2px dashed {focus}; }}

/* Die Tour ist eine Folge kleiner Karten statt einer grauen Textwand. Der
   aktuelle Auftrag trägt eine Akzentkante und einen Hintergrund; Pfeil,
   Haken oder Strich bleiben die zweite Kodierung des Zustands (Regel 18). */
QFrame#tourStepRow {{
    border: 1px solid transparent;
    border-radius: {NORMAL}px;
    padding: {TIGHT}px;
}}
QFrame#tourStepRow[tourState="current"] {{
    background: {hover};
    border-left: 3px solid {accent_line};
}}
QFrame#tourStepRow[tourState="skipped"] {{
    border-left: 3px dashed {line};
}}

/* Der Unterstützen-Dialog zeigt als ruhige Karte, wofür das Geld ist: je
   Zeile ein Symbol, ein halbfettes Stichwort und ein Satz. Die zwei Wege
   nach draußen stehen darunter, gleichwertig und ohne Akzent. */
QFrame#donationPurposes {{
    background: {base};
    border: 1px solid {line};
    border-radius: {NORMAL}px;
}}
QFrame#donationPurposes QLabel {{ background: transparent; }}
QFrame#donationPurposes QLabel#donationPoint {{ font-weight: 600; }}

/* --- Eingaben: der Fokus muss man sehen -------------------------------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {base};
    border: 2px solid {field_line};
    border-radius: {SPACE}px;
    padding: {TIGHT - 1}px {NORMAL - 1}px;
    selection-background-color: {highlight};
    selection-color: {on_highlight};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover,
QComboBox:hover, QPlainTextEdit:hover, QTextEdit:hover {{
    border-color: {muted};
}}
/* Nie die Breite — der Grund steht oben bei ``field_line``. Wohl aber die
   **Strichart**: Farbe allein wäre eine Bedeutung über Farbe, und Regel 18
   verlangt eine zweite Kodierung. Gestrichelt und nicht gepunktet, weil der
   feinere Strich im Bild unruhig wirkt und weniger Fläche trägt; dieselbe
   Wahl hat der Reiter schon getroffen (``QTabBar::tab:selected:focus``).
   Die Rahmenbreite bleibt bei zwei Punkten, also bleibt auch das
   Aufklappmenü der Combobox heil — gemessen, 48 von 48 Punkten. */
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 2px dashed {focus};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {disabled};
    background: {window};
}}

/* --- Die Pfeile am Zahlenfeld ------------------------------------------
   Sobald ein Stylesheet an einem ``QSpinBox`` eine Rahmeneigenschaft setzt,
   hört Qt auf, dessen Unterelemente nativ zu zeichnen. Übrig blieben zwei
   leere Kästchen mit einem Strich dazwischen — auf jedem Zahlenfeld jedes
   Dialogs, in beiden Themen. Wer das sieht, hält es für einen Grafikfehler
   und klickt nicht hin.

   ``arrow_files`` erzeugt dafür SVG-Dateien in den Farben des Themas.
   Ihr Docstring begründet den Bildweg und die Ablage im Cache. */
/* **Vier Punkte breiter, und der Trennstrich rückt nach innen.** Die
   Zielfläche war rund zehn auf elf Punkte — für eine Maus wenig, für einen
   Stift oder eine zittrige Hand zu wenig, und die Knöpfe liegen übereinander,
   teilen sich die Feldhöhe also. ``subcontrol-origin: border`` legte sie
   außerdem auf den Feldrahmen, sodass ihr eigener Trennstrich unter ihm lag:
   Man sah zwei Pfeile ohne erkennbare Flächen. Mit ``padding`` als Ursprung
   sitzt die Kante sichtbar neben der Zahl. */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: padding;
    width: {WIDE}px;
    background: transparent;
    border-left: 1px solid {line};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-position: top right;
    border-top-right-radius: {SPACE}px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: {SPACE}px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {hover};
}}
{_arrow_rules(arrows, line, hover)}
QComboBox QAbstractItemView {{
    background: {base};
    border: 1px solid {line};
    selection-background-color: {highlight};
    selection-color: {on_highlight};
}}

/* --- Listen und Bäume: überfahren und gewählt sind zwei Zustände -------- */
QTreeView, QListView, QTableView, QTreeWidget, QListWidget {{
    background: {base};
    border: 1px solid {line};
    border-radius: {SPACE}px;
    alternate-background-color: {hover};
}}
QTreeView::item, QListView::item, QTableView::item {{ padding: {TIGHT}px; }}
QTreeView::item:hover, QListView::item:hover, QTableView::item:hover {{ background: {hover}; }}
QTreeView::item:selected, QListView::item:selected, QTableView::item:selected {{
    background: {highlight};
    color: {on_highlight};
}}
/* Der Bericht wählt den ersten lösbaren Befund selbst vor. Diese dauerhafte
   Vorauswahl ist Orientierung, kein zweiter Handlungsaufruf neben dem
   akzentuierten Lösungsknopf: ruhige Fläche plus Akzentkante kodieren sie
   weiterhin doppelt, ohne im Ruhezustand eine zweite Signalfläche zu bilden. */
QListWidget#reportFindings::item:selected {{
    background: {active};
    color: {text};
    border-left: 3px solid {accent_line};
}}
QHeaderView::section {{
    background: {window};
    color: {muted};
    border: none;
    border-bottom: 1px solid {line};
    padding: {TIGHT}px {NORMAL}px;
    font-weight: 600;
}}

/* Ein Kachelraster wählt über Rahmen **und** Hintergrund. Voll eingefärbt
   verschwände das Vorschaubild in der Auswahlfarbe. */
QListWidget#tileGrid::item:selected {{
    background: {hover};
    color: {text};
    border: 2px solid {highlight};
    border-radius: {SPACE}px;
}}
QListWidget#tileGrid::item:hover {{ background: {hover}; border-radius: {SPACE}px; }}
{_check_rules(checks)}

/* --- Reiter ------------------------------------------------------------ */
QTabWidget::pane {{ border: 1px solid {line}; border-radius: {SPACE}px; top: -1px; }}
QTabBar::tab {{
    background: transparent;
    color: {muted};
    border: 1px solid transparent;
    border-top-left-radius: {SPACE}px;
    border-top-right-radius: {SPACE}px;
    padding: {TIGHT}px {ROOMY}px;
}}
QTabBar::tab:hover {{ color: {text}; background: {hover}; }}
/* Der aktive Reiter trägt eine Akzentkante — und zwar zusätzlich zu Fläche,
   Farbe und Fettschrift, die er schon hatte (Regel 18 bleibt unberührt).
   Vorher unterschied ihn vom stillen allein der Flächenwechsel, und der lag
   bei 1,10 Kontrast: Ob Prüfbericht oder Chat gilt, war eine Frage des
   zweiten Blicks. Das obere Padding gibt die drei Pixel wieder her, sonst
   rutscht die Beschriftung nach unten. */
QTabBar::tab:selected {{
    color: {text};
    background: {base};
    border-color: {line};
    border-top: 3px solid {accent_line};
    border-bottom-color: {base};
    padding-top: {max(TIGHT - 2, 0)}px;
    font-weight: 600;
}}
/* Die Reiterleiste zeigte den Tastaturfokus mit null Bildpunkten Unterschied —
   in beiden Themen. Wer mit dem Tabulator hierher kommt, sah nicht, dass er
   hier ist, und die Pfeiltasten wechselten scheinbar grundlos den Reiter.

   ``:selected:focus`` und nicht ``:focus`` allein: Der Zustand gilt der Leiste,
   also träfe ``QTabBar::tab:focus`` alle Reiter zugleich — in einer QTabBar ist
   der aktuelle der fokussierte. Gestrichelt, weil der aktive Reiter schon
   Akzentkante, Fläche und Fettschrift trägt; eine zweite durchgezogene Linie
   wäre nicht zu unterscheiden. */
QTabBar::tab:selected:focus {{ border: 2px dashed {focus}; }}

/* --- Rahmen, Trenner, Gruppen ------------------------------------------ */
QGroupBox {{
    border: 1px solid {line};
    border-radius: {SPACE}px;
    margin-top: {ROOMY}px;
    padding-top: {NORMAL}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: {ROOMY}px;
    padding: 0 {TIGHT}px;
    color: {muted};
    font-weight: 600;
}}
/* Die Fuge zwischen zwei Bereichen ist auch ihr Griff. Sie war einen
   Bildpunkt breit — optisch eine feine Linie und praktisch nicht zu treffen;
   wer die Detailspalte des Katalogs verbreitern wollte, zielte auf einen
   Pixel. Jetzt ist sie so breit, dass ein Zeiger sie findet, und färbt sich
   beim Überfahren, damit sie sagt, dass sie sich ziehen lässt. */
/* **Die Fuge war unsichtbar, bis man sie traf.** Der Griff trug die
   Fensterfarbe, also Kontrast 1,00 — dass die Spalten sich verschieben
   lassen, erfuhr nur, wer zufällig mit der Maus darüberfuhr. Für einen
   Kunden ohne CAD-Gewohnheiten ist das keine Entdeckung, sondern eine, die
   ausbleibt.

   Sichtbar wird sie über eine schmale Mittellinie in der Trennfarbe des
   Themas (2,30 im dunklen, 2,00 im hellen gegen das Fenster) — nicht über
   die volle Fläche: Acht Punkte Linienfarbe zwischen zwei Panels wären ein
   Balken, keine Fuge. Beim Überfahren nimmt der ganze Griff den Akzent, wie
   bisher. */
QSplitter::handle {{ background: {window}; }}
QSplitter::handle:horizontal {{
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 {window}, stop: 0.42 {window}, stop: 0.42 {line},
        stop: 0.58 {line}, stop: 0.58 {window}, stop: 1 {window});
}}
QSplitter::handle:vertical {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {window}, stop: 0.42 {window}, stop: 0.42 {line},
        stop: 0.58 {line}, stop: 0.58 {window}, stop: 1 {window});
}}
QSplitter::handle:hover {{ background: {accent_line}; }}
QSplitter::handle:horizontal {{ width: {NORMAL}px; }}
QSplitter::handle:vertical {{ height: {NORMAL}px; }}

/* --- Regler ------------------------------------------------------------- */
/* **Das letzte Bedienelement ohne eigene Form.** Gemessen an der Leiste, an
   der ihn ein Kunde wirklich zieht: Der Schnittregler trug in **beiden**
   Themen dieselben einundzwanzig Farben — #454545, #1e1e1e, #626262 —, und
   keine davon steht in ``theme.py``. Es waren Qts Vorgaben, also ein
   kantiges Rechteck im dunklen und ein weißer Kreis im hellen Thema, mitten
   in einer Leiste, deren übrige Teile dem Thema folgen. Drei Regler hängen
   daran: Schnittebene, Schichthöhe, Explosionsweite.

   Der Griff ist rund und **breiter als hoch gedacht**: Er wird gezogen, und
   ein Ziel von zehn Punkten trifft niemand zuverlässig. Der zurückgelegte
   Teil der Rille trägt den Akzent — er sagt, wo der Wert steht, und das ist
   dieselbe Aussage wie beim Fortschritt.

   Gesperrt heißt hier wirklich gesperrt: Griff und gefüllte Rille fallen auf
   die Sperrfarbe, sonst sieht ein Regler bedienbar aus, den nichts bewegt. */
QSlider::groove:horizontal {{
    height: {SPACE + 2}px;
    background: {line};
    border-radius: {(SPACE + 2) // 2}px;
}}
QSlider::sub-page:horizontal {{
    background: {accent_line};
    border-radius: {SPACE // 2}px;
}}
/* **Der Griff ist so groß, dass man ihn trifft.** Er maß zwölf Punkte, und
   das ist unter dem, was eine Maus bei einer Zuggeste sicher fasst; wer
   danebentraf, verschob den Regler seitenweise statt zu ziehen (Robert,
   03.09.2026). Achtzehn Punkte sind die Größe, die Qt für einen Zuggriff
   ohnehin annimmt, und die Rinne darunter wächst um zwei mit, damit das
   Verhältnis stimmt. Danebentreffen kostet seit `TrackSlider` ohnehin
   nichts mehr — der Klick springt zur Stelle. */
QSlider::handle:horizontal {{
    background: {muted};
    border: 1px solid {line};
    width: {ROOMY + 6}px;
    height: {ROOMY + 6}px;
    margin: -{NORMAL}px 0;
    border-radius: {(ROOMY + 6) // 2}px;
}}
QSlider::handle:horizontal:hover {{ background: {text}; }}
QSlider::handle:horizontal:pressed {{ background: {accent_line}; }}
QSlider::handle:horizontal:disabled {{ background: {disabled}; border-color: {disabled}; }}
QSlider::sub-page:horizontal:disabled {{ background: {disabled}; }}

/* --- Bildlaufleisten: schmal und still --------------------------------- */
QScrollBar:vertical {{ background: transparent; width: {ROOMY}px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: {ROOMY}px; margin: 0; }}
/* **Beide Mindestmaße, nicht eines.** ``min-height`` wirkt nur am senkrechten
   Griff; der waagerechte schrumpfte damit auf zwei Punkte, sobald links etwas
   Breites lag — bei einer Zeile von 4000 Punkten in einem Fenster von 300 war
   er weder zu sehen noch zu greifen. Gemessen 12 Punkte im dunklen und 4 im
   hellen Thema, gegen die 44, die er jetzt hat. */
QScrollBar::handle {{
    background: {line};
    border-radius: {SPACE}px;
    min-height: {WIDE}px;
    min-width: {WIDE}px;
}}
QScrollBar::handle:hover {{ background: {muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* --- Menüs und Statuszeile --------------------------------------------- */
QMenuBar {{ background: {window}; border-bottom: 1px solid {line}; }}
QMenuBar::item {{ padding: {TIGHT}px {ROOMY}px; background: transparent; }}
QMenuBar::item:selected {{ background: {hover}; }}
QMenu {{ background: {base}; border: 1px solid {line}; padding: {TIGHT}px; }}
QMenu::item {{ padding: {TIGHT}px {WIDE}px; border-radius: {SPACE}px; }}
QMenu::item:selected {{ background: {highlight}; color: {on_highlight}; }}
QMenu::separator {{ height: 1px; background: {line}; margin: {TIGHT}px {NORMAL}px; }}
/* Die Kategorie-Überschrift (siehe :func:`menu_heading`). Sie ist ein Label
   in einer Aktion, also greift die Trennstrich-Regel darüber nicht — was
   gerade der Punkt ist: Qt zeichnete den Text von ``addSection`` gar nicht.
   Leise wie Nebentext und halbfett, damit sie benennt statt mitzureden. */
QLabel#{MENU_HEADING} {{
    color: {muted};
    background: transparent;
    padding: {TIGHT}px {NORMAL}px 0 {NORMAL}px;
}}
QStatusBar {{ border-top: 1px solid {line}; }}
QStatusBar::item {{ border: none; }}
/* Die Trennlinie zwischen zwei Auskünften (siehe :func:`divider`) — Qts
   eigene Item-Rahmen sind oben ausgeschaltet, und ein 3D-Rahmen wäre
   ohnehin die falsche Form. */
QFrame#{DIVIDER} {{ color: {line}; background: {line}; border: none; }}
/* Die Konturfarbe bleibt fachlich fest, ihr Rand folgt dem Thema. */
QFrame#layerLegendStroke {{ border-color: {line}; }}

/* Der Hinweis unter dem Zeiger war das letzte Element ohne eigene Form: Qt
   zeichnete ihn kantig und randlos, während daneben jedes Feld seinen Radius
   trug. Er erklärt die Werkzeugzeile und jeden gesperrten Knopf — also ist er
   kein Nebenschauplatz. */
QToolTip {{
    background: {tooltip};
    color: {text};
    border: 1px solid {line};
    border-radius: {SPACE}px;
    padding: {TIGHT}px {NORMAL}px;
}}

/* --- Fortschritt -------------------------------------------------------- */
QProgressBar {{
    border: 1px solid {line};
    border-radius: {SPACE}px;
    background: {base};
    text-align: center;
}}
QProgressBar::chunk {{ background: {highlight}; border-radius: {SPACE}px; }}
/* Gesperrt heißt leiser — und hier muss es dastehen, nicht in der Palette.
   Ein Stylesheet gewinnt gegen sie: die Disabled-Gruppe trägt den gedämpften
   Akzent, gezeichnet wurde trotzdem der volle. Gemessen an einem Balken,
   zweimal gerendert: 2018 Akzentpunkte bedienbar, 2018 gesperrt. Beim Regler
   nebenan hat die Palette gereicht, weil ihn kein Stylesheet anfasst — dort
   sind es jetzt 404 gegen 0. */
QProgressBar:disabled {{ color: {disabled}; }}
QProgressBar::chunk:disabled {{ background: {disabled}; }}

"""


def apply_style(application: QApplication, theme: Theme) -> None:
    """Legt das Stylesheet über die Anwendung. Wirkt sofort und überall."""
    font = application.font()
    application.setStyleSheet(
        stylesheet(theme, max(font.pointSize(), 1), arrow_files(theme), check_files(theme))
    )
