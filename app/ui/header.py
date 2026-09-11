"""Die Kopfzeile: was offen ist, und worauf es gedruckt wird.

Über dem Fenster stand bisher eine Werkzeugleiste mit vier Knöpfen und
tausend Pixeln Leerraum daneben. Die Knöpfe bleiben — neu ist, was rechts
davon steht: der Zustand, in dem sich das Projekt befindet.

**Warum das dort steht und nicht in einem Dialog.** Drucker und Material
entscheiden jede Toleranz im Stapel (§12): eine Passung ist ein Verweis ins
Materialprofil, kein Zahlenwert. Wer nicht weiß, gegen welches Material
gerechnet wird, weiß nicht, was seine Bohrung bedeutet — und musste dafür
bisher ``Strg+P`` drücken und ein Formular lesen.

Die Zeile behauptet nichts, was sie nicht weiß. Ohne offenes Projekt steht
dort nichts, und die Maße erscheinen erst, wenn es etwas zu messen gibt.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSignalBlocker, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QToolButton,
    QWidget,
)

from app.branding import PROJECT_SUFFIX
from app.core.knowledge import profiles
from app.core.scene import EvaluationResult
from app.core.types import Profile, SceneObject
from app.core.units import LengthUnit
from app.i18n import tr
from app.ui.icons import icon
from app.ui.labels import length
from app.ui.style import TARGET_SIZE, TIGHT, divider, set_level
from app.ui.tool_strip import BarComboBox


def project_name(title: str) -> str:
    """Der Titel ohne seine Dateiendung.

    ``session.title`` liefert den Dateinamen, mit einem Stern für
    Ungesichertes. Der Stern bleibt — er ist eine Aussage; ``.p3d`` fällt weg,
    denn es steht in jedem Projekt und unterscheidet keines vom anderen.
    """
    marker = "*" if title.endswith("*") else ""
    stem = title.removesuffix("*")
    return f"{stem.removesuffix(PROJECT_SUFFIX)}{marker}"


def bounds_text(result: EvaluationResult | None, unit: LengthUnit) -> str:
    """Das Außenmaß über alle Körper, oder nichts.

    Über alle und nicht je Körper: die Zeile beantwortet „passt das auf die
    Platte", und dafür zählt der Hüllquader über das Ganze. Was ein einzelner
    Körper misst, steht im Objektbaum.
    """
    if result is None or not result.scene.objects:
        return ""
    boxes = [entry.mesh.bounds for entry in result.scene.objects.values()]
    size = [
        max(box.maximum[axis] for box in boxes) - min(box.minimum[axis] for box in boxes)
        for axis in range(3)
    ]
    # Die Einheit einmal am Ende, wie im Objektbaum: dreimal „mm" in einer
    # Zeile sagt dreimal dasselbe und liest sich dreimal so lang.
    measures = " × ".join(length(value, unit, with_unit=False) for value in size)
    return f"{measures} {unit}"


def filament_names(profile: Profile, bodies: list[SceneObject]) -> tuple[str, ...]:
    """Die tatsächlich verwendeten Filamente samt unterscheidendem Namen.

    Der Projektwert ist nur die Vorgabe für Körper ohne eigenen Slot. Ein
    farbiger Schriftzug oder ein Körper aus anderem Material kommt zusätzlich
    dazu; gleiche Namen werden in ihrer ersten Reihenfolge behalten. Welche
    Slots zählen, bestimmt das Netz: eine leere Zuordnung bedeutet überall
    Slot 0, unbenutzte Slotdefinitionen sind keine verwendeten Filamente.
    """
    names: list[str] = []
    for body in bodies:
        slots = {slot.index: slot for slot in body.material_slots}
        used_indices = set(body.mesh.slot_indices)
        if not used_indices:
            used_indices.add(0)
        for index in sorted(used_indices):
            slot = slots.get(index)
            if slot is None:
                names.append(str(profiles.for_object(profile, body).material.title))
                continue
            name = str(slot.name).strip()
            material_id = profiles.material_id_for_type(slot.material_type or "")
            if material_id:
                material = str(profiles.material(material_id).title)
            elif slot.material_type:
                material = slot.material_type
            elif slot.material:
                material = slot.material
            else:
                # Ein importierter Slot kann nur einen Namen oder eine Farbe
                # tragen. Ohne eigene Materialangabe gilt dafür dieselbe
                # Projekt- oder Körpervorgabe wie für den Basisslot; eine
                # unbekannte ausdrücklich genannte Art bleibt oben erhalten.
                material = str(profiles.for_object(profile, body).material.title)
            colour = ""
            if slot.colour is not None:
                red, green, blue = (
                    max(0, min(255, round(channel * 255))) for channel in slot.colour
                )
                colour = f"#{red:02X}{green:02X}{blue:02X}"
            if name:
                # „Gehäuse“ allein sagt nicht, welche Spule einzulegen ist.
                # Die Materialart bleibt daneben, solange der Name sie nicht
                # ohnehin schon trägt.
                shown = (
                    name
                    if not material or material.casefold() in name.casefold()
                    else f"{name} ({material})"
                )
            else:
                shown = material or (
                    tr("Farbe {colour}").replace("{colour}", colour) if colour else ""
                )
            if shown and colour and colour.casefold() not in shown.casefold():
                shown = f"{shown} · {colour}"
            if shown:
                names.append(shown)
    return tuple(dict.fromkeys(name for name in names if name))


#: Wie der Wähler „kein Filter" nennt. Derselbe Wert wie in
#: ``explode_bar``, wo der Wähler herkommt — der Viewport kennt ihn.
ALL_PLATES = -1

#: Ein eigenes Profil darf aus einem einzigen, beliebig langen Wort bestehen.
#: Sein unterscheidendes Ende bleibt zugänglich, darf aber nicht erneut die
#: ganze Werkzeugleiste auf sein Vollmaß zwingen.
MAXIMUM_TAIL_CHARACTERS = 10

#: Leseraum der Projektangaben, sobald ein Projekt offen ist. Auf dem echten
#: Windows-Pfad reichen 660 Pixel für Name, Außenmaß, Druckerknopf und eine
#: klare Filamentanzahl; wird es enger, kürzt die Hauptwerkzeugleiste ihre
#: Wörter und lässt der Projektauskunft den Raum.
READABLE_HEADER_WIDTH = 660


class _EphemeralLabel(QLabel):
    """Ein Label, das seinen Text kürzt, statt seine Zeile zu sprengen.

    **Der Grund steht in der Messung** (Befund D6). Die Kopfzeile lebt als
    Widget in der Werkzeugleiste, und Qt gibt einem Widget dort entweder seine
    ``sizeHint``-Breite oder gar keinen Platz: Wer nicht hineinpasst, wandert
    ins Erweiterungsmenü hinter dem Pfeil. Ein ``QLabel`` meldet als
    Mindestbreite die volle Textbreite — gemessen an einem geöffneten Projekt
    waren das 273 px für den Namen, 275 für die Maße und 330 für den Drucker,
    zusammen 968 px für die ganze Zeile. Die Leiste wünschte damit 2283 px.

    Was daraus folgte, sah kein Test: **Auf einem 1920er Bildschirm war die
    Kopfzeile weg**, sobald jemand ein Projekt öffnete — Projektname, Maße,
    Druckplatte, Drucker und Material zusammen, verschwunden hinter einem
    unbeschrifteten Pfeil. Mit leerem Projekt passierte das nicht (dort will
    sie 103 px), und genau deshalb fällt es beim Ausprobieren nicht auf.

    Ein gekürzter Name ist eine schlechtere Auskunft als der ganze. **Keine
    Auskunft ist die schlechteste**: Der volle Text bleibt im Tooltip, und wer
    das Fenster breit zieht, bekommt ihn zurück.
    """

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        *,
        tail_words: int = 0,
        protected_end: str = "",
    ) -> None:
        super().__init__("", parent)
        self._full = ""
        self._display = ""
        self._tail_words = tail_words
        self._protected_end = protected_end
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        # Konstruktor und späteres Setzen laufen bewusst durch denselben Weg:
        # Volltext, Hilfe und sichtbare Kürzung dürfen nie auseinanderlaufen.
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 — Qt-Name
        """Merkt sich den ganzen Text und zeigt, was hineinpasst."""
        self._full = text
        self._display = text
        self._set_accessible_text(text)

    def setSummary(self, summary: str, full: str) -> None:  # noqa: N802 — Qt-Name
        """Eine kurze Auskunft zeigen und den vollen Inhalt zugänglich halten."""
        self._full = full
        self._display = summary
        self._set_accessible_text(full)
        # Die Zahl ist der Zweck einer echten Kurzfassung. Sie darf nicht
        # noch einmal zu „… Filamente“ gekürzt werden; für die Namen gibt es
        # den Tooltip. Ein einzelner, beliebig langer Profilname bleibt wie
        # bisher kürzbar und darf die Kopfzeile nicht verdrängen.
        if summary != full:
            self.setMinimumWidth(self.fontMetrics().horizontalAdvance(summary))
        self._fit()

    def _set_accessible_text(self, full: str) -> None:
        """Tooltip, Mindestmaß und sichtbare Fassung gemeinsam nachführen."""
        self.setToolTip(full)
        self.setAccessibleName(full)
        raw_tail, visible_tail = self._bounded_tail()
        if raw_tail:
            metrics = self.fontMetrics()
            full_width = metrics.horizontalAdvance(self._display)
            body = self._display[: -len(raw_tail)]
            tail_width = metrics.horizontalAdvance(f"{'…' if body else ''}{visible_tail}")
            # Ein echtes Minimum, kein ``minimumSizeHint`` unter ``Ignored``:
            # Stern, Einheit oder ein begrenztes Modellende passen damit
            # nachweisbar hinein, ohne die Leiste selbst wieder zu verdrängen.
            self.setMinimumWidth(min(full_width, tail_width))
        else:
            self.setMinimumWidth(0)
        self.updateGeometry()
        self._fit()

    def full_text(self) -> str:
        """Was dastünde, wenn der Platz reichte — für Tests und Vorleser."""
        return self._full

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        super().resizeEvent(event)
        self._fit()

    def _tail(self) -> str:
        """Das rohe Ende, dessen Bedeutung eine Kürzung nicht verschlucken darf."""
        if self._protected_end and self._display.endswith(self._protected_end):
            return self._protected_end
        if not self._tail_words:
            return ""
        words = self._display.split()
        return " ".join(words[-self._tail_words :])

    def _bounded_tail(self, room: int | None = None) -> tuple[str, str]:
        """Begrenzt ein unteilbares Ende, nicht den zugänglichen Volltext."""
        raw_tail = self._tail()
        if not raw_tail:
            return "", ""
        metrics = self.fontMetrics()
        limit = max(
            metrics.horizontalAdvance("…"),
            metrics.averageCharWidth() * MAXIMUM_TAIL_CHARACTERS,
        )
        if room is not None:
            limit = min(limit, max(0, room))
        visible_tail = metrics.elidedText(raw_tail, Qt.TextElideMode.ElideMiddle, limit)
        return raw_tail, visible_tail

    def _fit(self) -> None:
        """Kürzt sichtbar und hält das semantische Ende vollständig fest."""
        room = max(self.width(), self.minimumWidth())
        metrics = self.fontMetrics()
        if metrics.horizontalAdvance(self._display) <= room:
            super().setText(self._display)
            return
        raw_tail, visible_tail = self._bounded_tail(room)
        if not raw_tail:
            super().setText(metrics.elidedText(self._display, Qt.TextElideMode.ElideMiddle, room))
            return
        body = self._display[: -len(raw_tail)]
        if not body:
            super().setText(metrics.elidedText(self._display, Qt.TextElideMode.ElideMiddle, room))
            return
        body_room = max(0, room - metrics.horizontalAdvance(visible_tail))
        visible = metrics.elidedText(body, Qt.TextElideMode.ElideMiddle, body_room) + visible_tail
        # Kerning an der neuen Naht kann den getrennt berechneten Text um
        # einzelne Pixel verbreitern. Die sichtbare Zusage gewinnt auch dort.
        while body_room and metrics.horizontalAdvance(visible) > room:
            body_room -= 1
            visible = (
                metrics.elidedText(body, Qt.TextElideMode.ElideMiddle, body_room) + visible_tail
            )
        super().setText(visible)


class _PrinterControl(QWidget):
    """Druckername und direkter Wechselweg als eine responsive Einheit."""

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        return QSize(TARGET_SIZE, super().minimumSizeHint().height())


class HeaderBar(QWidget):
    """Projekt links, Zustand rechts — eine Zeile, die immer steht.

    **Der Plattenwähler wohnte im Explodieren.** Er stand in der Leiste, die
    Teile auseinanderzieht, und erschien nur, wenn dort auch der Schieber etwas
    zu tun hatte: Wer eine einzelne Platte ansehen wollte, suchte ihn unter
    einem Werkzeug für etwas anderes. Hier gehört er hin — die Zeile sagt, was
    offen ist und worauf gedruckt wird, und auf welche Platte man sieht, ist
    dieselbe Art Auskunft.
    """

    plateChanged = Signal(int)
    printerRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("headerBar")

        # **Die drei langen kürzen mit Bedeutung** (Befund D6). Name, Maße und
        # Drucker tragen zusammen 878 der 968 Pixel, die diese Zeile wünschte;
        # ihre Enden bleiben deshalb fest: Ungespeichert-Stern, Einheit und
        # Druckermodell. Plattenwahl und Material teilen den übrigen Raum
        # responsiv, wobei der Zweck „Platte“ nie abgeschnitten werden darf.
        self.title = _EphemeralLabel("", self, protected_end="*")
        set_level(self.title, "section")
        self.bounds = _EphemeralLabel("", self, tail_words=1)
        set_level(self.bounds, "caption")

        self.plates = BarComboBox(self)
        self.plates.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.plates.setAccessibleName(tr("Druckplatte"))
        self.plates.setToolTip(tr("Zeigt nur die Objekte einer Platte."))
        self.plates.currentIndexChanged.connect(self._on_plate)

        self.printer = _EphemeralLabel("", self, tail_words=2)
        set_level(self.printer, "caption")
        self.printer_button = QToolButton(self)
        self.printer_button.setText(tr("Drucker …"))
        self.printer_button.setIcon(icon("print_settings", self.printer_button))
        # **Mit Beschriftung, nicht nur als Symbol.** Der Text stand hier schon,
        # gezeigt wurde er nie — `ToolButtonIconOnly` warf ihn weg, und damit
        # war der einzige Weg zu den Druckeinstellungen ein Symbol ohne Wort.
        # Gefunden hat es der Nutzer nur, weil er zufällig mit der Maus
        # darüberfuhr und den Tooltip sah (Robert, 07.09.2026). Ein Knopf, den
        # man nur durch Schweben findet, ist keiner.
        self.printer_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.printer_button.setAutoRaise(True)
        printer_hint = tr("Öffnet die Druckeinstellungen; der Drucker steht dort ganz oben.")
        self.printer_button.setToolTip(printer_hint)
        self.printer_button.setStatusTip(printer_hint)
        self.printer_button.setAccessibleDescription(printer_hint)
        self.printer_button.clicked.connect(self.printerRequested)
        self.printer_control = _PrinterControl(self)
        printer_layout = QHBoxLayout(self.printer_control)
        printer_layout.setContentsMargins(0, 0, 0, 0)
        printer_layout.setSpacing(TIGHT)
        printer_layout.addWidget(self.printer, 1)
        printer_layout.addWidget(self.printer_button)
        self.printer_control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        # **Das Filament steht hier nicht mehr.** Es hing an der Projektvorgabe
        # und nicht an dem, was die Körper tragen — bei einem Projekt, dessen
        # einziger Körper „Ohne Filament" führte, sagte die Kopfzeile „PETG“.
        # Und selbst richtig gerechnet ist eine einzelne Angabe hier falsch,
        # sobald mehrere Körper verschiedene Filamente tragen: „2 Filamente"
        # beantwortet keine Frage (Robert, 07.09.2026). Wo welches Filament
        # sitzt, sagt der Filamentbereich links; er zählt die Körper dazu.
        self._divider = divider(self)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(TIGHT, 0, TIGHT, 0)
        self._layout.setHorizontalSpacing(TIGHT)
        self._layout.setVerticalSpacing(TIGHT)
        self._compact = False
        self._arranging = False
        self._arrange(False)
        # Dieselbe Trennung wie in der Statuszeile: Plattenwahl links,
        # Drucker und Material rechts — „… 220 mm   PLA" stand sonst als ein
        # Satz da, obwohl das eine eine Auswahl ist und das andere ein
        # Bericht.

        self.show_plates(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Bittet die Werkzeugleiste um das zweizeilige Kompaktmaß.

        ``QToolBar`` gibt einem eingebetteten Widget sonst sein Wunschmaß oder
        verschiebt es vollständig in den Überlauf. Das Kompaktmaß legt den
        Plattenzustand unter die übrigen Angaben; durch ``Expanding`` wächst
        der Header bei mehr Platz weiter und bleibt dann einzeilig.
        """
        preferred = super().sizeHint()
        has_project = any(label.full_text() for label in (self.title, self.bounds, self.printer))
        width = max(self._compact_width(), READABLE_HEADER_WIDTH) if has_project else 0
        return QSize(width, preferred.height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Das kleinste responsive Maß statt der Summe einer einzigen Zeile."""
        minimum = super().minimumSizeHint()
        return QSize(self._compact_width(), minimum.height())

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        self._arrange(self._wide_width() > event.size().width())
        super().resizeEvent(event)

    def _compact_width(self) -> int:
        """Breite der zweizeiligen Anordnung: Angaben oben, Filter unten."""
        top = (self.title, self.bounds, self.printer_control)
        top_width = sum(widget.minimumWidth() for widget in top) + TIGHT * (len(top) - 1)
        plate_width = self.plates.minimumWidth() if not self.plates.isHidden() else 0
        return max(top_width, plate_width) + TIGHT * 2

    def _wide_width(self) -> int:
        """Mindestbreite, ab der alle Angaben in eine Zeile passen."""
        widgets: list[QWidget] = [self.title, self.bounds]
        if not self.plates.isHidden():
            widgets.extend((self.plates, self._divider))
        widgets.append(self.printer_control)
        printer_action_width = self.printer.minimumWidth() + TARGET_SIZE
        return (
            sum(widget.minimumWidth() for widget in widgets)
            + printer_action_width
            + TIGHT * max(0, len(widgets) - 1)
            + TIGHT * 2
        )

    def _arrange(self, compact: bool) -> None:
        """Ordnet denselben Inhalt ohne Duplikat ein- oder zweizeilig an.

        **Nicht von innen heraus noch einmal.** ``activate()`` am Ende löst
        ein ``resizeEvent`` aus, und das fragt mit der **alten** Breite, ob
        es kompakt sein soll — mitten im Umbau, und mit der Antwort von
        vorhin: Ein Umbau auf zweizeilig stellte sich so noch im selben
        Aufruf wieder einzeilig zurück (gemessen an der freistehenden
        Kopfzeile in ``test_the_plate_filter_shows_its_complete_state_in_
        every_language``, sobald die Plattenspalte ihr Mindestmaß bekam).
        Solange hier umgebaut wird, gilt die Entscheidung des Aufrufers.
        """
        if self._arranging or (compact == self._compact and self._layout.count()):
            return
        self._arranging = True
        try:
            self._rearrange(compact)
        finally:
            self._arranging = False

    def _rearrange(self, compact: bool) -> None:
        widgets = (
            self.title,
            self.bounds,
            self.plates,
            self._divider,
            self.printer_control,
        )
        for widget in widgets:
            self._layout.removeWidget(widget)
        for column in range(8):
            self._layout.setColumnStretch(column, 0)
        # **Vor die Verzweigung, weil sie in beiden Zweigen dasselbe war.**
        # Beide Hälften begannen mit genau diesen zwei Zeilen; wer das liest,
        # sucht den Unterschied und findet keinen. Der Knopf trägt in jeder
        # Breite seine Beschriftung, und sein Name für den Bildschirmleser
        # hängt nicht an der Breite.
        #
        # **Beschriftet, nicht nur bebildert.** Hier stand `ToolButtonIconOnly`,
        # und weil `_arrange` bei jeder Breitenänderung läuft, hätte ein
        # gesetzter Stil im Aufbau allein nichts genützt — diese Zeile hat ihn
        # jedes Mal wieder weggenommen. Der einzige Weg zu den
        # Druckeinstellungen war damit ein Symbol ohne Wort.
        self.printer_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.printer_button.setAccessibleName(tr("Drucker wechseln"))
        if compact:
            self._layout.addWidget(self.title, 0, 0)
            self._layout.addWidget(self.bounds, 0, 1)
            self._layout.addWidget(self.printer_control, 0, 2)
            self._layout.addWidget(self.plates, 1, 0, 1, 3)
            for column, stretch in enumerate((2, 3, 3)):
                self._layout.setColumnStretch(column, stretch)
            self._divider.hide()
        else:
            self._layout.addWidget(self.title, 0, 0)
            self._layout.addWidget(self.bounds, 0, 1)
            self._layout.addWidget(self.plates, 0, 3)
            self._layout.addWidget(self._divider, 0, 4)
            self._layout.addWidget(self.printer_control, 0, 5)
            for column, stretch in (
                (0, 2),
                (1, 3),
                (5, 3),
            ):
                self._layout.setColumnStretch(column, stretch)
            self._divider.show()
        self._compact = compact
        self._stretch_the_plate_column()
        self._layout.invalidate()
        self._layout.activate()
        self.updateGeometry()

    def _stretch_the_plate_column(self) -> None:
        """Die Spalte des Plattenwählers dehnt sich genau dann, wenn er dasteht.

        **RM-158, und die Ursache lag im Zeitpunkt.** Der Wähler trägt die
        Größenrichtlinie ``Ignored``, und ein ``QGridLayout`` rechnet für
        eine Spalte **ohne** Dehnung dann mit null Breite — auch wenn das
        Widget darin ein Mindestmaß hat (nachgestellt an vier Beschriftungen
        in einem Gitter: die Spalte wird 0 breit, der Wähler 97, und der
        Nachbar beginnt sechs Bildpunkte hinter seinem Anfang). Die Dehnung
        stand hier bis zum 11.09.2026 nur, wenn der Wähler beim Anordnen
        gerade **nicht** versteckt war — und die Anwendung ordnet zuerst
        kompakt (das Fenster ist beim Bau 1280 breit), dann breit mit
        verstecktem Wähler, und zeigt ihn erst, wenn das Projekt seine
        Platten hat. In Roberts Fenster lag „Alle Platten" damit über
        „Elegoo Centauri Carbon 2", beide an derselben x-Stelle. Eine Sonde,
        die den Wähler beim Bau nicht versteckt vorfand, sah nichts davon.

        Deshalb an einer Stelle, gerufen vom Anordnen **und** vom Zeigen: Die
        Dehnung folgt der Sichtbarkeit, nicht dem Aufbau. Kompakt liegt der
        Wähler in der zweiten Zeile über alle Spalten, dort bleibt die Spalte
        ohne eigene Dehnung.
        """
        if not self._layout.count():
            return
        wanted = 0 if self._compact or self.plates.isHidden() else 1
        # Nur bei einer Änderung: ``setColumnStretch`` entwertet das Layout
        # auch für denselben Wert, und ein freistehendes Fenster nimmt beim
        # nächsten Durchlauf sein Wunschmaß statt der gesetzten Breite.
        if self._layout.columnStretch(3) != wanted:
            self._layout.setColumnStretch(3, wanted)

    def _reflow(self) -> None:
        """Zieht nach, wenn ein neuer Text sein semantisches Minimum ändert."""
        self._arrange(self._wide_width() > self.width())

    @property
    def plate(self) -> int:
        """Die Platte, die gezeigt wird, oder :data:`ALL_PLATES`."""
        value = self.plates.currentData()
        return ALL_PLATES if value is None else int(value)

    def show_plates(self, plates: int) -> None:
        """Baut den Wähler neu und behält die Platte, die betrachtet wurde.

        Sichtbar ab zwei Platten: Ein Element, das immer dasteht und meistens
        nichts tut, bringt Leuten bei, es zu ignorieren.
        """
        previous = self.plate
        # Fünfundzwanzig Zeilen zwischen Stummschalten und Aufheben, darunter
        # ein ``tr()`` mit Platzhalter und ein ``max()`` — genug Wege, auf
        # denen eine Ausnahme den Wähler für immer stumm zurückließe. Der
        # Blocker gibt ihn auf jedem Weg wieder frei.
        with QSignalBlocker(self.plates):
            self.plates.clear()
            self.plates.addItem(tr("Alle Platten"), ALL_PLATES)
            for index in range(plates):
                self.plates.addItem(tr("Platte {number}", number=index + 1), index)
            # Zweck **und Zustand** bleiben vollständig sichtbar. Nur „Platte“ zu
            # zeigen verbarg nach der Wahl, ob alle oder eine einzelne Platte gilt.
            # Der aktive Qt-Stil liefert Innenabstand, Rahmen und Pfeil. Qts
            # ``sizeHint`` speichert dagegen den ersten, noch leeren Inhalt im
            # Cache; nach dem Befüllen war er kleiner als der aktuelle Text.
            metrics = self.plates.fontMetrics()
            texts = [self.plates.itemText(index) for index in range(self.plates.count())]
            widest = max(texts, key=metrics.horizontalAdvance)
            option = QStyleOptionComboBox()
            option.initFrom(self.plates)
            option.currentText = widest
            needed = self.plates.style().sizeFromContents(
                QStyle.ContentsType.CT_ComboBox,
                option,
                QSize(metrics.horizontalAdvance(widest), metrics.height()),
                self.plates,
            )
            self.plates.setMinimumWidth(needed.width())
            if previous != ALL_PLATES and previous < plates:
                self.plates.setCurrentIndex(previous + 1)

        many = plates > 1
        self.plates.setVisible(many)
        self._stretch_the_plate_column()
        self._reflow()
        # **Gemeldet wird jede Änderung, nicht nur der Sonderfall „nur noch
        # eine Platte".** Fällt die Zahl auf genau die betrachtete Nummer,
        # greift die Wiederherstellung darüber nicht (``previous < plates`` ist
        # dann falsch), und ``clear()`` hat den Wähler längst auf „Alle
        # Platten" gestellt. Vorher blieb das stumm, solange mehr als eine
        # Platte übrig war: Der Wähler sagte „Alle Platten", die Ansicht
        # filterte weiter auf die verschwundene Nummer, und das Bild blieb
        # leer. Einen Rückweg gab es nicht — ein Klick auf denselben Eintrag
        # ändert den Index nicht und sendet deshalb auch nichts.
        if previous != ALL_PLATES and self.plate != previous:
            self.plateChanged.emit(self.plate)

    def _on_plate(self, index: int) -> None:
        del index
        self.plateChanged.emit(self.plate)

    def show_project(self, name: str, result: EvaluationResult | None, unit: LengthUnit) -> None:
        """Name und Außenmaß des offenen Projekts.

        Die Dateiendung fällt weg: dass ein Solidon-Projekt ``.p3d`` heißt,
        weiß der Dateidialog, und in einer Überschrift ist es Rauschen. Der
        Stern für Ungesichertes bleibt — er ist eine Aussage.
        """
        self.title.setText(project_name(name))
        self.bounds.setText(bounds_text(result, unit))
        self._reflow()

    def show_profile(self, profile: Profile, result: EvaluationResult | None = None) -> None:
        """Den Drucker des Projekts zeigen.

        *result* bleibt in der Signatur, obwohl die Kopfzeile es nicht mehr
        liest: Es sind zwei Aufrufer, und beide haben es zur Hand — den
        Parameter zu streichen hieße, sie beide anzufassen, damit hier eine
        Zeile weniger steht.
        """
        del result
        self.printer.setText(str(profile.printer.title))
        self._reflow()

    def state(self) -> tuple[str, str, str]:
        """Die vollständige Auskunft — unabhängig von der sichtbaren Kürzung."""
        return (
            self.title.full_text(),
            self.bounds.full_text(),
            self.printer.full_text(),
        )


def header_stylesheet(theme: str) -> str:
    """Eine Kante nach unten, sonst nichts.

    Die Kopfzeile ist kein Kasten: sie trägt keine Entscheidung, sie beantwortet
    eine Frage. Ein Rahmen darum machte aus einer Auskunft ein Bedienelement.
    """
    from app.ui.theme import THEMES

    colours = THEMES[theme]  # type: ignore[index]
    return f"""
QWidget#headerBar {{
    background: {colours["window"]};
    border-bottom: 1px solid {colours["line"]};
}}
"""
