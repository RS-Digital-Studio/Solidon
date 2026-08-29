"""Die Trennleiste: eine Linie zeichnen, und das Teil geht dort auseinander
(Bauplan §25, §18.2).

Der kürzeste Weg zu einem geteilten Teil, den es gibt: zweimal ins Bild
klicken, einmal auf *Jetzt trennen*. Was dazwischen passiert, steht in dieser Leiste
— nicht als Feld, das man ausfüllt, sondern als Satz, der sagt, was der nächste
Klick tut. Wer beim zweiten Klick war, sieht die Linie im Bild und darf sie
verwerfen; wer beim ersten war, liest, dass ein zweiter fehlt.

**Die Verbindung ist vorgewählt, nicht versteckt.** Zwei geklebte Hälften ohne
Stifte muss jemand von Hand in Deckung halten, während der Kleber greift — das
ist die Arbeit, die dieses Werkzeug abnehmen soll. Wer sie nicht will, nimmt
den Haken heraus; das ist ein Handgriff weniger als ihn zu suchen.

**Die Linie legt beim zweiten Punkt die Ebene fest.** Das Fenster zeigt sie
als durchscheinende, umrandete Fläche mit einem Rand außerhalb des Körpers;
eine spätere Kamerafahrt ändert sie nicht. Nach der Auswertung öffnet die
Explosionsansicht die beiden Hälften automatisch, damit Stifte und Löcher nicht
zwischen deckungsgleichen Schnittflächen verschwinden.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.geom.pins import PIN_COUNT
from app.core.geom.prepare_ops import CONNECTOR_SHAPES
from app.i18n import tr
from app.ui.labels import choice_label
from app.ui.style import NORMAL, TIGHT, make_primary
from app.ui.tool_strip import BarComboBox

#: Wie viele Punkte eine Trennlinie hat. Zwei — mehr wäre ein Polygonzug, und
#: der beschriebe eine Fläche, die kein Schnitt ist.
POINTS_NEEDED = 2


def state_text(points: int) -> str:
    """Was jetzt zu tun ist, in einem Satz.

    Drei Zustände, drei Sätze. Ein Werkzeug, das in jedem Zustand denselben
    Hinweis zeigt, sagt zweimal nichts — beim ersten Klick weiß der Nutzer
    schon, dass er klicken soll, und beim zweiten will er wissen, dass es
    weitergeht.
    """
    if points == 0:
        return tr("Auf das Teil klicken — dort fängt die Trennlinie an.")
    if points < POINTS_NEEDED:
        return tr("Zweiten Punkt anklicken. Zwischen beiden wird getrennt.")
    # Anführungszeichen, keine Sternchen: Die Leiste zeigt reinen Text, und ein
    # *Wort* zwischen Sternchen stand dort auch so im Bild — angesehen und
    # nachgebessert, nicht angenommen.
    return tr("Die Linie steht. „Jetzt trennen“ schneidet das Teil dort durch.")


class SplitBar(QWidget):
    """Trennlinie zeichnen, Verbindung wählen, trennen (§25)."""

    applyRequested = Signal()
    """Der Hauptknopf. Das Fenster macht daraus die Operation — die Leiste
    rechnet nichts und schneidet nichts."""
    clearRequested = Signal()
    """Die gezeichnete Linie verwerfen und von vorn anfangen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.state = QLabel(state_text(0), self)
        self.state.setWordWrap(True)
        # **Hier stand ``Ignored`` als waagerechte Politik**, und sie hatte
        # ihren Grund: In einer Zeile mit den Knöpfen nahm der umbrechende Text
        # seine bevorzugte Breite und drückte den Hauptknopf zusammen, bis auf
        # ihm „etzt trenne" stand. Der Preis war größer als der Gewinn — ein
        # Satz, der nachgibt, bis nichts bleibt, gibt bis null nach: Gemessen
        # bekam er bei 685 Bildpunkten Kartenbreite **null**, und als
        # umbrechender Text verlangte er für null Breite **160** Bildpunkte
        # Höhe. Beide Probleme kommen aus derselben Zeile, und die gibt es
        # nicht mehr (siehe unten). Ohne Konkurrenz braucht er keine Politik,
        # die ihn kleinredet.

        # Vorgewählt: siehe Modulkopf. Der Text sagt, was die Stifte tun, nicht
        # wie sie heißen — „Passstifte" ist das Wort für jemanden, der schon
        # weiß, worum es geht.
        self.connect_halves = QCheckBox(tr("Zum Zusammenstecken vorbereiten"), self)
        self.connect_halves.setChecked(True)
        self.connect_halves.setToolTip(
            tr(
                "Setzt Stifte in die eine Hälfte und die passenden Löcher in die "
                "andere. Die Teile finden dann beim Kleben von selbst zusammen; das "
                "Spiel kommt aus dem Materialprofil."
            )
        )
        self.connect_halves.toggled.connect(self._follow_connection)

        self.count = QSpinBox(self)
        self.count.setRange(1, 6)
        self.count.setValue(PIN_COUNT)
        self.count.setToolTip(
            tr("Zwei Stifte halten die Hälften gegen Verdrehen. Einer wäre ein Scharnier.")
        )
        self.count_label = QLabel(tr("Stifte"), self)

        # Die Form gehört neben die Zahl und nicht hinten in einen Dialog: Wer
        # einen Schwalbenschwanz will, will ihn *bevor* er trennt, und ein Wert,
        # den man erst nachträglich im Verlauf findet, ist ein zweiter
        # Arbeitsgang. Die Namen kommen aus derselben Quelle wie im Dialog
        # (``labels.choice_label``), sonst heißt dieselbe Form an zwei
        # Stellen anders.
        self.shape = BarComboBox(self)
        self.shape.setAccessibleName(tr("Form der Verbinder"))
        for value in CONNECTOR_SHAPES:
            self.shape.addItem(choice_label(value), userData=value)
        self.shape.setToolTip(
            tr(
                "Runde Stifte drucken am saubersten. Sechskant und Schwalbenschwanz "
                "sichern gegen Verdrehen, der Schwalbenschwanz zusätzlich gegen "
                "Auseinanderziehen."
            )
        )

        # Nicht „Trennen": so heißt der Umschalter, der diese Leiste öffnet.
        # Der Umschalter nennt das Werkzeug, der Knopf seine Handlung — sonst
        # stehen zwei gleich beschriftete Bedienelemente übereinander, und der
        # obere tut etwas anderes als der untere.
        self.apply = QPushButton(tr("Jetzt trennen"), self)
        make_primary(self.apply)
        self.apply.setEnabled(False)
        self.apply.clicked.connect(self.applyRequested)

        self.clear = QPushButton(tr("Linie löschen"), self)
        self.clear.setEnabled(False)
        self.clear.clicked.connect(self.clearRequested)

        # **Der Satz steht auf seiner eigenen Zeile**, und zwar seit er
        # gemessen wurde: In einer Zeile mit den sechs Bedienelementen bekam er
        # bei 685 Bildpunkten Kartenbreite **null** davon — die anderen
        # brauchten 670, und `Ignored` (siehe oben) heißt, dass er nachgibt, bis
        # nichts bleibt. Zu sehen war er damit nie, und weil er umbricht,
        # verlangte er für die Breite null eine Höhe von **160** Bildpunkten:
        # Die Karte des Trennwerkzeugs war 241 Punkte hoch, die der anderen
        # sieben Werkzeuge 81 bis 112, und dazwischen lag ein leeres Band.
        #
        # Beides erledigt eine zweite Zeile: Der Satz bekommt die ganze Breite
        # und braucht eine Zeilenhöhe, die Knöpfe behalten ihre.
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(self.connect_halves)
        controls.addWidget(self.count_label)
        controls.addWidget(self.count)
        controls.addWidget(self.shape)
        controls.addStretch(1)
        controls.addWidget(self.apply)
        controls.addWidget(self.clear)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.setSpacing(TIGHT)
        layout.addWidget(self.state)
        layout.addLayout(controls)

    def _follow_connection(self, wanted: bool) -> None:
        """Die Stiftzahl gehört zum Haken und verschwindet mit ihm.

        Ausgegraut stehen zu lassen wäre die zweite Möglichkeit; sie ist hier
        die schlechtere, weil die Leiste schmal ist und ein gesperrtes Feld
        genauso viel Platz braucht wie ein bedienbares.
        """
        self.count.setVisible(wanted)
        self.count_label.setVisible(wanted)
        self.shape.setVisible(wanted)

    def show_points(self, points: int) -> None:
        """Wie viele Punkte gesetzt sind — der einzige Zustand dieser Leiste."""
        self.state.setText(state_text(points))
        self.apply.setEnabled(points >= POINTS_NEEDED)
        self.clear.setEnabled(points > 0)

    def values(self) -> dict[str, int | str]:
        """Die Parameter, die nicht aus der Linie kommen."""
        if not self.connect_halves.isChecked():
            return {"pins": 0, "shape": "round"}
        return {"pins": int(self.count.value()), "shape": str(self.shape.currentData())}

    def reset(self) -> None:
        """Was das Schließen des Werkzeugs zurücknimmt."""
        self.show_points(0)
