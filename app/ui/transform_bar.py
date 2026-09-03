"""Die Grundsteuerung: drei Rollen, die Zahlen daneben (Bauplan §18.11).

Verschieben, Drehen, Skalieren sind das, was ein Kunde zuerst tut — in jedem
Slicer stehen sie als drei Knöpfe nebeneinander, und daneben die Felder der
gewählten Rolle. Diese Leiste tut dasselbe.

**Der Griff im Bild bleibt vollständig.** Die Rolle entscheidet nur, welche
Zahlen danebenstehen; gezogen wird weiter an allen Achsen. Ein Haken „Gizmo"
stand hier einmal und ist ersatzlos entfallen: Wer das Werkzeug öffnet, will
bewegen — das Werkzeug **ist** der Griff.

**Gerechnet wird nichts.** Jeder Feldwert wird zu einer registrierten
Operation (§2, Regel 2); die Leiste meldet nur, welche und mit welchen Werten.
Ein Zug ist damit ein Schritt im Verlauf und einzeln zurücknehmbar.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QWidget,
    QWidgetAction,
)

from app.i18n import tr
from app.ui.icons import icon
from app.ui.labels import LengthSpin, NumberSpin, choice_label
from app.ui.style import NORMAL, TIGHT, make_primary

#: **Kein Einrasten als Vorgabe** (Entscheidung Robert, 03.09.2026).
#:
#: Hier stand ein Millimeter und fünfzehn Grad, und beides wirkte, ohne dass
#: es irgendwo sichtbar gewesen wäre: Der Fang lebt in einem Popup hinter
#: einem Symbolknopf. Beim Verschieben fiel das nicht auf — ein Millimeter ist
#: feiner als eine Mausbewegung. Beim Drehen verschwand jeder Zug unter
#: siebeneinhalb Grad **spurlos**: Der Körper drehte sich unter der Maus mit,
#: die Zahl am Zeiger zählte mit, und das Loslassen rundete auf null. Der
#: Befund lautete deshalb „das Drehen geht gar nicht".
#:
#: Eine 3D-Szene hat kein Raster, an dem etwas einrasten könnte — wer runde
#: Werte will, tippt sie (die Zahl am Zeiger nimmt Eingaben) oder stellt den
#: Fang im Popup ein. Null heißt dort seit je „kein Einrasten"; jetzt ist es
#: auch die Vorgabe.
DEFAULT_GRID_STEP = 0.0
DEFAULT_ANGLE_STEP = 0.0

#: Die drei Rollen in der Reihenfolge, in der man sie braucht.
#:
#: Kein Wörterbuch, sondern eine Folge: Die Reihenfolge ist die Aussage —
#: erst hinstellen, dann ausrichten, dann anpassen. Jede Rolle nennt ihr
#: Symbol, ihren Namen und die Operation, die sie auslöst.
ROLES: tuple[tuple[str, str, str], ...] = (
    ("move", "translate_object", "move"),
    ("rotate", "rotate_object", "rotate"),
    ("scale", "scale_object", "scale"),
)


class TransformBar(QWidget):
    """Drei Rollen mit ihren Feldern, dazu Raster- und Winkelfang."""

    #: Eine Operation mit ihren Werten — das Fenster macht daraus einen Schritt.
    applyRequested = Signal(str, dict)
    snappingChanged = Signal(float, float)
    #: Welche Rolle gerade gewählt ist; die Ansicht hebt die passenden Griffe hervor.
    roleChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        #: Wie breit die Leiste mit Wort sein will — gemerkt im breiten
        #: Zustand, siehe :meth:`_fit_roles`.
        self._roomy_width = 0

        self.roles = QButtonGroup(self)
        self.roles.setExclusive(True)
        self.role_buttons: dict[str, QToolButton] = {}
        role_row = QHBoxLayout()
        role_row.setContentsMargins(0, 0, 0, 0)
        role_row.setSpacing(TIGHT)
        for index, (key, _op, symbol) in enumerate(ROLES):
            button = QToolButton(self)
            button.setCheckable(True)
            button.setText(_role_name(key))
            button.setIcon(icon(symbol, button))
            # **Symbol und Wort nebeneinander.** Die drei Zeichen sind geeinigt
            # — jeder Slicer führt sie —, aber „verstanden, bevor man liest"
            # heißt nicht „ohne Wort": Wer sie zum ersten Mal sieht, bekommt
            # beides und lernt das Bild nebenbei (Regel 18, §2.6).
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setToolTip(_role_hint(key))
            button.setStatusTip(_role_hint(key))
            self.roles.addButton(button, index)
            self.role_buttons[key] = button
            role_row.addWidget(button)
        self.role_buttons["move"].setChecked(True)
        self.roles.idClicked.connect(self._role_chosen)

        self.fields = QStackedWidget(self)

        self.fields.addWidget(self._move_fields())
        self.fields.addWidget(self._rotate_fields())
        self.fields.addWidget(self._scale_fields())

        self.apply = QPushButton(self)
        self.apply.setText(tr("Anwenden"))
        make_primary(self.apply)
        self.apply.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.apply.clicked.connect(self._apply)
        # **Ein Knopf und kein Zug beim Tippen.** Drei Felder nacheinander zu
        # verlassen ergäbe drei Schritte im Verlauf für eine Bewegung; der
        # Knopf macht daraus einen. Die Eingabetaste löst ihn mit aus — wer
        # eine Zahl tippt, will sie anwenden, nicht erst zielen.
        #
        # **Die Eingabetaste, und nur sie** — ``editingFinished`` feuert auch
        # beim Fokusverlust, und der Knopf daneben nimmt den Fokus beim Klick.
        # Tippen und klicken wandte den Wert damit zweimal an: aus 5 mm wurden
        # 10 mm, aus 90° 180°, und zurück brauchte es zwei Strg+Z.
        for spin in (self.dx, self.dy, self.dz, self.angle_value, self.factor, self.largest):
            spin.lineEdit().returnPressed.connect(self._maybe_apply_on_return)

        self.snap = self._snap_button()

        layout = QHBoxLayout(self)
        # **Die Leiste darf schmaler werden, als ihre Kinder wollen.** Sonst
        # summiert das Layout deren Mindestbreiten zu einer Untergrenze, die
        # ein enges Fenster nicht einhalten kann — Qt quetscht dann trotzdem,
        # nur ohne dass die Umschaltung in :meth:`_fit_roles` je zum Zug käme.
        # Mit gelöster Kopplung fällt zuerst das Wort und das Symbol bleibt.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.addLayout(role_row)
        layout.addWidget(self.fields)
        layout.addWidget(self.apply)
        layout.addStretch(1)
        # **Der Fang steht hinter einem Knopf, nicht in der Zeile.** Er gilt
        # allen drei Rollen, wird einmal eingestellt und dann nie wieder
        # angefasst — und kostete als vier Widgets mehr Breite als die drei
        # Rollen zusammen (gemessen: 397 von 1253 Punkten auf Französisch,
        # davon 202 für die zwei Etiketten). Was in der Zeile steht, ist das,
        # was man **tut**; was man **einstellt**, liegt einen Klick daneben.
        layout.addWidget(self.snap)

    def _snap_button(self) -> QToolButton:
        """Der Fang: ein Knopf, dahinter seine zwei Felder mit vollem Namen.

        **Ein Popup und kein Dialog.** Die Werte bleiben stehen, es gibt keinen
        Modus und nichts zu bestätigen — wer das Menü wieder schließt, hat
        eingestellt, was er eingestellt hat (Regel 19).

        **Und ein wortloser Knopf trägt seinen Namen an drei Stellen**
        (``oberflaeche.md``): im Barrierefreiheitsbaum, im Tooltip und in der
        Statuszeile. Das Zeichen ist ein Punkt im Raster — das Einrasten
        selbst, nicht ein Zahnrad: Ein Zahnrad hieße „Einstellungen" und stünde
        damit für alles.
        """
        button = QToolButton(self)
        button.setIcon(icon("snap", button))
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setAccessibleName(tr("Fang"))
        button.setToolTip(tr("Fang — auf welchen Schritt ein Zug einrastet."))
        button.setStatusTip(button.toolTip())
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Der Rasterfang ist eine Länge, also folgt er der Anzeigeeinheit
        # (§19.3). Der Winkelfang daneben nicht — ein Winkel in Zoll wäre keine
        # Umschaltung, sondern ein Fehler mit Einstellung.
        menu = QMenu(button)
        holder = QWidget(menu)
        rows = QFormLayout(holder)
        self.grid = LengthSpin(holder)
        self.grid.set_range_mm(0.0, 100.0)
        self.grid.set_value_mm(DEFAULT_GRID_STEP)
        self.grid.valueChanged.connect(self._emit_snapping)
        self.angle = NumberSpin(holder)
        self.angle.setDecimals(1)
        self.angle.setRange(0.0, 90.0)
        self.angle.setValue(DEFAULT_ANGLE_STEP)
        self.angle.setSuffix(tr(" °"))
        self.angle.valueChanged.connect(self._emit_snapping)
        # **Hier ist Platz für den vollen Namen**, anders als in der Zeile: Im
        # Popup steht, was das Feld tut, und nicht bloß, wie es heißt.
        rows.addRow(tr("Rasterfang"), self.grid)
        rows.addRow(tr("Winkelfang"), self.angle)
        holder.setStatusTip(tr("Null heißt: kein Einrasten."))

        action = QWidgetAction(menu)
        action.setDefaultWidget(holder)
        menu.addAction(action)
        button.setMenu(menu)
        return button

    # --- Enge --------------------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt-Name
        """Immer der Platz für die Wörter — auch wenn gerade Symbole stehen.

        **Sonst schließt sich ein Kreis.** Die Leiste schaltet bei Enge auf
        Symbole, ist dadurch schmaler, meldet eine kleinere Wunschbreite, der
        Container gibt daraufhin genau diese — und die Bedingung für die
        Rückkehr tritt nie wieder ein. Gemessen: Bei einem 1600 Punkte breiten
        Fenster stand die Leiste auf 677 und zeigte in allen sechs Sprachen
        dieselbe Breite, weil kein Wort mehr da war, das sich unterscheiden
        könnte.

        Wer den Platz für die Wörter **verlangt**, bekommt ihn, wo er da ist,
        und weicht nur, wo er wirklich fehlt. Dieselbe Lehre wie bei der
        Höhenverteilung der Karten: nicht mit dem rechnen, was man gerade
        selbst gesetzt hat.
        """
        hint = super().sizeHint()
        if self._roomy_width:
            hint.setWidth(max(hint.width(), self._roomy_width))
        return hint

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Name
        """Wird es eng, weicht das Wort und das Symbol bleibt."""
        super().resizeEvent(event)
        self._fit_roles()

    def _fit_roles(self) -> None:
        """Symbol und Wort, solange Platz ist — sonst nur das Symbol.

        **Ein Layout kürzt im Zweifel jeden Posten anteilig**, und ein Knopf mit
        Beschriftung verliert dabei zuerst die Beschriftung: „Verschieben"
        bekam 149 Punkte für 184 gewünschte und stand als „Versch…" da. Ein
        halbes Wort ist schlechter als kein Wort — das Symbol allein ist
        geeignet, weil es in jedem Slicer dasselbe bedeutet, und der Name steht
        weiter im Tooltip, in der Statuszeile und im Barrierefreiheitsbaum.

        **Gemessen wird gegen einen gemerkten Wert, nicht gegen den aktuellen.**
        Wer die Wunschbreite im Symbolzustand liest, bekommt die kleine Zahl und
        schaltet sofort zurück — die Leiste flackerte bei jedem Pixel. Der
        Platzbedarf mit Wort wird deshalb im **breiten** Zustand gemerkt und im
        engen nur noch verglichen; dieselbe Regel wie bei der Höhenverteilung
        der Karten („nie mit den Werten rechnen, die gerade gesetzt wurden").

        Der Wert wird beim Sprachwechsel von selbst neu gemerkt: Eine andere
        Sprache macht die Knöpfe breiter, die Leiste wird größer angefragt, und
        der nächste breite Durchlauf schreibt ihn fort.
        """
        wordy = Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        icon_only = Qt.ToolButtonStyle.ToolButtonIconOnly
        showing_words = next(iter(self.role_buttons.values())).toolButtonStyle() == wordy

        if showing_words:
            self._roomy_width = self.sizeHint().width()
            if self.width() < self._roomy_width:
                self._set_role_style(icon_only)
        elif self._roomy_width and self.width() >= self._roomy_width:
            self._set_role_style(wordy)

    def _set_role_style(self, style: Qt.ToolButtonStyle) -> None:
        for button in self.role_buttons.values():
            button.setToolButtonStyle(style)

    def roles_show_words(self) -> bool:
        """Ob die Rollen gerade ihr Wort tragen — für Tests und Bilder."""
        return next(iter(self.role_buttons.values())).toolButtonStyle() == (
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )

    # --- die drei Feldsätze -----------------------------------------------------

    def _move_fields(self) -> QWidget:
        """X, Y, Z in Millimetern — der Weg, nicht die Zielstelle."""
        holder = QWidget(self)
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(TIGHT)
        self.dx = LengthSpin(holder)
        self.dy = LengthSpin(holder)
        self.dz = LengthSpin(holder)
        for name, spin in (("X", self.dx), ("Y", self.dy), ("Z", self.dz)):
            spin.set_range_mm(-500.0, 500.0)
            spin.set_value_mm(0.0)
            row.addWidget(QLabel(name, holder))
            row.addWidget(spin)
        return holder

    def _rotate_fields(self) -> QWidget:
        """Achse und Winkel — mehr braucht eine Drehung um eine Hauptachse nicht."""
        holder = QWidget(self)
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(TIGHT)
        self.axis = QComboBox(holder)
        # **Ein Bildschirmleser liest keine Beschriftung daneben.** Das Etikett
        # links steht im Layout, nicht im Barrierefreiheitsbaum; ohne eigenen
        # Namen meldet die Box sich als „QComboBox(-)". Derselbe Text wie am
        # Etikett — zwei Formulierungen für dasselbe Feld wären zwei Antworten
        # auf die Frage, was es ist (Regel 18).
        self.axis.setAccessibleName(tr("Achse"))
        for key in ("x", "y", "z"):
            self.axis.addItem(choice_label(key), key)
        self.axis.setCurrentIndex(2)
        self.angle_value = NumberSpin(holder)
        self.angle_value.setDecimals(1)
        self.angle_value.setRange(-360.0, 360.0)
        self.angle_value.setValue(90.0)
        # Die Einheit steht am Wert, nicht in der Beschriftung (§19.3) — und
        # sie geht durch tr(): Im Französischen gehört vor das Prozentzeichen
        # ein Leerzeichen, im Englischen nicht.
        self.angle_value.setSuffix(tr(" °"))
        # **Vorgewählt, weil das Teil sonst in der Luft steht.** Eine Drehung um
        # X oder Y kippt den Körper, und seine Unterseite liegt danach irgendwo
        # — mal über der Platte, mal darunter. Wer dreht, will fast immer
        # drucken, und ein Teil, das nicht aufliegt, druckt nicht.
        #
        # Der Haken bleibt trotzdem einer: Wer eine Baugruppe in ihrer Lage
        # zueinander dreht, braucht genau das nicht, und für den ist ein
        # ungefragtes Aufsetzen ein Fehler, den er erst im Slicer bemerkt.
        self.to_bed = QCheckBox(tr("aufs Bett"), holder)
        self.to_bed.setChecked(True)
        self.to_bed.setToolTip(
            tr(
                "Setzt das Teil nach dem Drehen mit seiner Unterseite auf die "
                "Platte. Beides zusammen ist ein Schritt im Verlauf und geht mit "
                "einem Strg+Z zurück."
            )
        )
        self.to_bed.setAccessibleDescription(self.to_bed.toolTip())

        row.addWidget(QLabel(tr("Achse"), holder))
        row.addWidget(self.axis)
        row.addWidget(QLabel(tr("Winkel"), holder))
        row.addWidget(self.angle_value)
        row.addWidget(self.to_bed)
        return holder

    def _scale_fields(self) -> QWidget:
        """Prozent oder Millimeter — dieselbe Absicht, zwei Wege.

        Der Umschalter ist der Grund, aus dem hier zwei Felder liegen: „auf
        120 %" und „auf 80 mm größte Kante" sind für den Kunden dieselbe
        Handlung, für den Kern zwei Operationen (``scale_object`` und
        ``fit_to_size``). Wer ein Teil auf ein Maß bringen will, soll das Maß
        eintippen können, statt den Faktor auszurechnen.
        """
        holder = QWidget(self)
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(TIGHT)
        self.factor = NumberSpin(holder)
        self.factor.setDecimals(1)
        self.factor.setRange(1.0, 1000.0)
        self.factor.setValue(100.0)
        self.factor.setSuffix(tr(" %"))
        self.largest = LengthSpin(holder)
        self.largest.set_range_mm(0.1, 1000.0)
        self.largest.set_value_mm(50.0)
        self.largest.setVisible(False)

        self.by_size = QToolButton(holder)
        self.by_size.setCheckable(True)
        self.by_size.setText(tr("auf Maß"))
        self.by_size.setToolTip(
            tr("Statt eines Faktors die größte Kante eintragen — der Faktor ergibt sich.")
        )
        self.by_size.setStatusTip(self.by_size.toolTip())
        self.by_size.toggled.connect(self._scale_mode_changed)

        row.addWidget(self.factor)
        row.addWidget(self.largest)
        row.addWidget(self.by_size)
        return holder

    # --- Bedienung ---------------------------------------------------------------

    def _scale_mode_changed(self, by_size: bool) -> None:
        self.factor.setVisible(not by_size)
        self.largest.setVisible(by_size)

    def _role_chosen(self, index: int) -> None:
        self.fields.setCurrentIndex(index)
        self.roleChanged.emit(ROLES[index][0])

    def role(self) -> str:
        """Welche Rolle gerade gewählt ist."""
        return ROLES[max(self.roles.checkedId(), 0)][0]

    def drops_to_bed(self) -> bool:
        """Ob nach der Drehung aufgesetzt werden soll.

        Nur beim Drehen: Verschieben ist eine Ansage über den Ort — wer
        ``dz = 10`` tippt, will das Teil oben haben, und ein Aufsetzen danach
        nähme ihm genau das. Skalieren wäre ein Fall für sich; solange es
        nicht beauftragt ist, bleibt es beim Drehen.
        """
        return self.role() == "rotate" and self.to_bed.isChecked()

    def draft(self) -> tuple[str, dict[str, Any]]:
        """Die Operation zur gewählten Rolle, mit den Werten der Felder.

        **Millimeter, gleich was angezeigt wird.** ``LengthSpin.value_mm``
        rechnet die Anzeigeeinheit zurück; der Kern rechnet in Millimetern
        (Regel 6), und ein Zoll-Wert, der ungerechnet in einen Draft liefe,
        wäre ein Teil um den Faktor 25,4 daneben.
        """
        role = self.role()
        if role == "move":
            return "translate_object", {
                "dx": self.dx.value_mm(),
                "dy": self.dy.value_mm(),
                "dz": self.dz.value_mm(),
            }
        if role == "rotate":
            return "rotate_object", {
                "axis": self.axis.currentData(),
                "angle": float(self.angle_value.value()),
            }
        if self.by_size.isChecked():
            return "fit_to_size", {"largest": self.largest.value_mm()}
        return "scale_object", {"factor": float(self.factor.value()) / 100.0}

    def _apply(self) -> None:
        op, params = self.draft()
        self.applyRequested.emit(op, params)

    def _maybe_apply_on_return(self) -> None:
        """Die Eingabetaste im Feld wirkt wie der Knopf daneben."""
        self._apply()

    def steps(self) -> tuple[float, float]:
        """Rasterschritt in Millimetern und Winkelschritt in Grad. Null heißt kein
        Einrasten.
        """
        return self.grid.value_mm(), float(self.angle.value())

    def _emit_snapping(self) -> None:
        grid, angle = self.steps()
        self.snappingChanged.emit(grid, angle)


def _role_name(key: str) -> str:
    """Der Name einer Rolle — dieselben Wörter wie im Operationsregister."""
    return {
        "move": tr("Verschieben"),
        "rotate": tr("Drehen"),
        "scale": tr("Skalieren"),
    }[key]


def _role_hint(key: str) -> str:
    """Was die Rolle tut, in einem Satz — Tooltip und Statuszeile lesen ihn."""
    return {
        "move": tr("Das Teil versetzen — am Griff im Bild oder über X, Y, Z."),
        "rotate": tr("Um eine Hauptachse drehen — Achse wählen, Winkel eintragen."),
        "scale": tr("Größer oder kleiner — als Faktor oder auf ein Maß."),
    }[key]
