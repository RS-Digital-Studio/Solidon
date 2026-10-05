"""„Auswahl als Baustein speichern" — der Dialog aus Konzept §16, Schritt 3 bis 5.

Ein eigener Baustein ist ein **Rezept**: ein Ausschnitt aus dem Stapel plus die
Beschreibung seiner Parameter, gespeichert als Daten. Das Format und die
Auswertung liegen im Kern (:mod:`app.core.knowledge.parts.recipe`); hier steht
nur, was der Kunde beantworten muss, damit daraus ein Baustein wird.

**Der Dialog fragt so wenig wie möglich.** Ein Projektparameter trägt schon
Titel, Einheit und Grenzen — der Kunde hat sie beim Anlegen angegeben (§13).
Was er noch nicht weiß, ist die Bedienung des künftigen Bausteindialogs: ob ein
Wert vorn steht oder unter „Weitere Einstellungen", und welcher Satz ihn
erklärt. Danach wird gefragt; alles andere steht vorbelegt da und lässt sich
ändern.

**Und er fragt nach den Merkmalen** (§18d). Ein Rezept muss sagen, welche
Merkmale es nach außen gibt und wie sie heißen, sonst ist die Provenienzkette
an der Naht zwischen Rezept und benutzendem Projekt unterbrochen: Wer später
eine Schraube in „das Loch oben" setzen will, braucht dafür einen Namen, den
das Rezept vergeben hat.

Der Bereichstest (Schritt 5) läuft in einem Arbeiter — er rechnet die Ecken
jedes Zahlenbereichs durch, und das dauert bei einem Rezept aus zwanzig
Schritten spürbar lange (§2.8).
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from itertools import pairwise
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError, FileWriteError, InternalError
from app.core.knowledge.parts import GROUPS, PARTS
from app.core.knowledge.parts import recipe as recipes
from app.core.log import get_logger
from app.core.types import Document, Feature, Profile, measure_status
from app.i18n import tr
from app.ui.dialogs import problem_text
from app.ui.labels import (
    PARAMETER_UNITS,
    NumberSpin,
    area,
    feature_measure_tip,
    feature_name,
    length,
    localised,
    measure_text,
    wheel_needs_focus,
)
from app.ui.leash import Worker, WorkerLeash, weak_slot
from app.ui.panels import align_forms, collapsible, least_number_width
from app.ui.style import (
    NORMAL,
    SPACE,
    TIGHT,
    WIDE,
    ContentFitIntent,
    ContentHeight,
    DialogScrollArea,
    make_primary,
    set_level,
)

_log = get_logger(__name__)

#: Die Gruppe, unter der ein selbst angelegter Baustein im Katalog steht.
#:
#: Eine eigene und nicht die des Vorbilds: Der Kunde soll sein Teil
#: wiederfinden, ohne es zwischen siebzehn mitgelieferten zu suchen. Ändern
#: kann er sie im Dialog — die vorhandenen Gruppen stehen zur Auswahl.
#: Wo ein eigener Baustein landet, solange der Kunde nichts anderes wählt —
#: dieselbe Vorgabe, die ``recipe.from_data`` für ein Rezept ohne Gruppe nimmt.
DEFAULT_GROUP = "structure"

# Die zwei Plätze, die ein freigegebener Wert im späteren Dialog haben kann
# (§2.5, gestufte Tiefe). Schlüssel des Rezeptformats und keine Beschriftungen —
# als Konstanten, weil ein Literal in einem ``addItem`` von der Prüfung auf
# feste Oberflächentexte nicht von einem Text zu unterscheiden ist.
PLACE_FRONT = "front"
PLACE_ADVANCED = "advanced"


class _CheckWorker(Worker):
    """Schneiden und prüfen, beides abseits des Oberflächen-Threads (§2.8, §38).

    Der Bereichstest wertet das Rezept an den Ecken jedes Zahlenbereichs aus —
    bei drei freigegebenen Maßen sechs Auswertungen, jede über den ganzen
    Ausschnitt. Dass das hierher gehört, war von Anfang an klar.

    **Das Schneiden gehört ebenfalls hierher**, und das war es nicht.
    ``capture`` liest nicht nur Werte ab, es rechnet den Ausschnitt einmal
    durch (die Probe aus Konzept §18a) — gemessen am 25.08.2026: 85 ms für
    einunddreißig Boolesche an Grundkörpern, aber 3900 ms für Kugel → glätten
    → aushöhlen. Das lief im Hauptthread, und zwar bevor der
    Fortschrittsbalken sichtbar wurde: Der Kunde sah vier Sekunden lang ein
    totes Fenster und danach einen Balken. §2.8 setzt die Schwelle bei zwei
    Sekunden.

    Abbrechen wirkt erst nach dem Schnitt — ``capture`` nimmt kein Token, und
    mitten in einer Auswertung lässt sich nichts anhalten. Der Unterschied ist
    trotzdem der ganze: Das Fenster bleibt bedienbar.
    """

    done = Signal(object)
    failed = Signal(object)
    """Ein Fehler des Kerns, mit seinem Satz — nicht ``crashed``.

    ``Worker.crashed`` gibt eine Zeichenkette, und ein ``AppError`` trägt einen
    Titel, einen Grund und Handlungsvorschläge (Regel 17). Durch ``crashed``
    käme davon nichts an: ``_failed`` fände weder ``title`` noch ``detail`` und
    zeigte seinen Notsatz.
    """
    step = Signal(float, str)
    """Wie weit er ist (0 bis 1) und woran — eine Ecke je Meldung."""

    def __init__(self, cut: Callable[[], Any], profile: Profile) -> None:
        super().__init__()
        self._cut = cut
        self._profile = profile
        self._stopped = False

    @property
    def is_cancelled(self) -> bool:
        """Das Token, nach dem ``check`` vor jeder Ecke fragt."""
        return self._stopped

    def stop(self) -> None:
        """Aufhören, sobald die laufende Ecke durch ist.

        Mitten in einer Auswertung lässt sich nichts anhalten — ``check`` fragt
        zwischen den Ecken. Bei sechs Ecken ist das der Bruchteil, den es
        dauert, statt der ganzen Rechnung.
        """
        self._stopped = True

    def work(self) -> None:
        # Der Schnitt hat keinen eigenen Fortschritt — er ist ein Stück, nicht
        # eine Reihe. Was er hat, ist ein Satz, und der steht da, bevor er
        # anfängt: Vier Sekunden ohne Auskunft sind vier Sekunden Zweifel.
        self.step.emit(0.0, str(tr("Der Ausschnitt wird geschnitten und einmal gerechnet …")))
        try:
            recipe = self._cut()
            if self.is_cancelled:
                return
            checked = recipes.range_check(
                recipe,
                self._profile,
                progress=lambda share, note: self.step.emit(float(share), str(note)),
                cancelled=self,
            )
        except AppError as error:
            # Schnitt und Bereichsplanung tragen beide einen konkreten
            # Handlungsvorschlag; er gehört unverändert in den Dialog.
            self.failed.emit(error)
            return
        self.done.emit(checked)


#: Die Einheiten, die ein freigegebenes Maß tragen kann — und was sie bewirken.
#: Umgerechnet wird ausschließlich ``mm`` (§19.3); alles andere ist eine
#: Beschriftung. Mehr Auswahl wäre keine: „cm" gäbe es im Kern nicht, es sähe
#: nur so aus.
#:
#: Öffentlicher Name für bestehende Nutzer und Tests dieses Dialogs. Die
#: Wahrheit selbst liegt bei den übrigen gemeinsamen Oberflächenbeschriftungen:
#: Parameterdialog, linke Leiste und Rezept dürfen nicht auseinanderlaufen.
UNITS = PARAMETER_UNITS


class _ParamRow:
    """Eine Zeile der Parameterliste: freigeben, und wie er im Dialog aussieht."""

    def __init__(self, parameter: Any, parent: QWidget) -> None:
        self.name = parameter.name
        # **Der Haken trägt die Beschriftung des Maßes, nicht seinen
        # Schlüssel** (RM-517): Dort stand ``breite`` und ``hoehe`` — der
        # Schlüssel, mit dem der Verlauf rechnet, während die Parameterleiste
        # „Breite" zeigt (``parameter.title or name``). Ändert der Kunde die
        # Beschriftung unter „Weitere Einstellungen", zieht der Haken mit.
        shown = str(parameter.title or parameter.name)
        self.take = QCheckBox(shown, parent)
        self.derived = str(parameter.expression or "")
        """Der Ausdruck des Projektparameters, oder leer.

        **Eine abgeleitete Zeile geht ohne Haken auf.** Der Kern schneidet die
        Formel weg, sobald der Wert von außen kommt (``recipe._with_values``,
        und dort ist das richtig) — vorgehakt hieß also: Ein Projekt mit
        ``breite = 40`` und ``hoehe = =@breite/2`` wurde zu einem Baustein mit
        zwei unabhängigen Feldern, und „Breite" auf 60 ließ „Höhe" auf 20
        stehen statt auf 30. Ohne ein Wort. Die Parameterleiste hält sich an
        die Gegenregel — abgeleitete Werte werden gezeigt, nicht bearbeitet,
        der Ausdruck besitzt sie —, und dieser Dialog gab sie zum Bearbeiten
        frei, ohne zu fragen.

        Verboten ist es nicht: Die Bindung zu lösen ist ein zulässiger Wunsch.
        Es ist nur eine Entscheidung, und die trifft der Kunde.
        """
        self.take.setChecked(not self.derived)
        # **Jedes Feld sagt, zu welchem Wert es gehört.** Bei zwei Parametern
        # las der Bildschirmleser zweimal „Diesen Wert freigeben",
        # „Beschriftung", „Einheit" — der sichtbare Name am Haken war
        # überschrieben. Der Name bleibt Name, der Satz wird Beschreibung.
        self.take.setAccessibleName(shown)
        self.take.setAccessibleDescription(tr("Diesen Wert freigeben"))

        self.hint: QLabel | None = None
        if self.derived:
            note = str(
                tr(
                    "Wird aus {expression} gerechnet. Freigegeben verliert dieser "
                    "Wert seine Formel: Der Baustein bekommt dafür ein eigenes Feld, "
                    "das sich nicht mehr von selbst mitzieht."
                ).format(expression=self.derived)
            )
            self.hint = QLabel(note, parent)
            self.hint.setWordWrap(True)
            # Regel 18: nicht nur die fehlende Marke im Kästchen — der Satz
            # steht sichtbar da, hängt am Haken und wird vorgelesen.
            self.take.setToolTip(note)
            self.take.setStatusTip(note)
            self.take.setAccessibleDescription(note)

        self.title = QLineEdit(shown, parent)
        # **Die Einheit entscheidet über die Umrechnung, nicht über die
        # Beschriftung.** ``op_dialog.shown_unit`` zeigt ein Feld genau dann in
        # der eingestellten Anzeigeeinheit, wenn seine Einheit ``mm`` ist
        # (§19.3); der Kern bekommt in jedem Fall Millimeter (§11.1). Als
        # Freitextfeld war das eine Falle: Wer „cm" eintippte, schaltete die
        # Umrechnung ab, das Feld sagte danach [cm], und gebaut wurden mm.
        #
        # Eine unbekannte Einheit des Projektparameters wird **nicht still
        # umgedeutet**, sondern als eigener Eintrag aufgenommen und vorgewählt
        # (Regel 21): So sieht der Kunde, was der Fall ist, statt es zu erfahren,
        # wenn das Teil falsch herauskommt.
        self.unit = QComboBox(parent)
        for code, label in UNITS:
            self.unit.addItem(str(label), code)
        chosen = str(parameter.unit or "")
        if self.unit.findData(chosen) < 0:
            self.unit.addItem(
                str(tr("{unit} — wird nicht umgerechnet").format(unit=chosen or "?")), chosen
            )
        self.unit.setCurrentIndex(self.unit.findData(chosen))

        # Die Grenzen stehen am Projektparameter, wenn der Kunde sie gesetzt
        # hat. Wo nicht, ist die Vorgabe ihr eigener Anhaltspunkt: die Hälfte
        # und das Doppelte sind keine Wahrheit, aber ein Bereich, den man
        # ansieht und ändert — besser als zwei leere Felder, die den
        # Bereichstest wertlos machen.
        value = float(parameter.value)
        self.minimum = NumberSpin(parent)
        self.maximum = NumberSpin(parent)
        self.default = NumberSpin(parent)
        for spin in (self.minimum, self.maximum, self.default):
            spin.setRange(-1_000_000.0, 1_000_000.0)
            # Zwei Stellen wie überall sonst: „20,000" liest sich als
            # zwanzigtausend, und für ein Maß in Millimetern ist die dritte
            # Stelle ohnehin unter der Druckgenauigkeit.
            spin.setDecimals(2)
        # **Auch um die Null herum ein Bereich.** Die Hälfte und das Doppelte
        # sind bei 0 beide 0, und bei einem negativen Wert stehen sie verkehrt
        # herum — beides ergibt ``min == max``, und der Bereichstest prüft dann
        # eine einzige Ecke und meldet sie als bestanden. Ein Millimeter Luft
        # nach beiden Seiten ist keine Wahrheit über das Teil, aber ein
        # Bereich, den man ansieht und ändert.
        span = abs(value) or 1.0
        self.minimum.setValue(
            float(parameter.minimum) if parameter.minimum is not None else value - span / 2
        )
        self.maximum.setValue(
            float(parameter.maximum) if parameter.maximum is not None else value + span
        )
        self.default.setValue(value)

        self.placement = QComboBox(parent)
        self.placement.addItem(tr("Vorn im Dialog"), PLACE_FRONT)
        self.placement.addItem(tr("Unter „Weitere Einstellungen“"), PLACE_ADVANCED)

        self.doc = QLineEdit(parent)
        self.doc.setPlaceholderText(tr("Ein Satz: was passiert, wenn man ihn ändert"))

        # Die Überschrift seines Blocks unter „Weitere Einstellungen“ — dort
        # stehen Beschriftung, Einheit, Platz und Satz jedes Maßes beisammen.
        self.heading = QLabel(shown, parent)
        set_level(self.heading, "section")
        self._name_fields(shown)
        self.title.textChanged.connect(self._renamed)

    def _renamed(self, text: str) -> None:
        """Haken, Überschrift und Feldnamen folgen der Beschriftung."""
        shown = text.strip() or str(self.name)
        self.take.setText(shown)
        self.take.setAccessibleName(shown)
        self.heading.setText(shown)
        self._name_fields(shown)

    def _name_fields(self, shown: str) -> None:
        """**Jedes Feld sagt, zu welchem Maß es gehört** — mit seiner Beschriftung.

        Bei zwei Maßen las der Bildschirmleser zweimal „Vorgabe", „Einheit";
        und der Schlüssel (``breite``) ist auch für ihn kein Name.
        """
        for field, label in (
            (self.title, tr("Beschriftung", context="Feld")),
            (self.unit, tr("Einheit")),
            (self.default, tr("Vorgabe")),
            (self.minimum, tr("Kleinster Wert")),
            (self.maximum, tr("Größter Wert")),
            (self.placement, tr("Platz im Dialog")),
            (self.doc, tr("Beschreibung")),
        ):
            field.setAccessibleName(tr("{field} · {value}", field=label, value=shown))

    def restore(self, entry: Any) -> None:
        """Übernimmt die Angaben, die dieses Maß im bearbeiteten Baustein trug (E6).

        Beschriftung, Einheit, Grenzen, Vorgabe, Platz und Satz — also genau
        das, was der Kunde beim ersten Mal eingetippt hat. Ohne das wäre
        „bearbeiten" für jedes freigegebene Maß sieben Felder neu, und der
        Baustein käme mit anderen Grenzen zurück als er hatte.

        **Und der Haken sitzt**, auch bei einem abgeleiteten Wert: Dass die
        Formel weichen soll, hat der Kunde damals entschieden; ihn dieselbe
        Frage noch einmal beantworten zu lassen, hieße, seine Antwort nicht zu
        kennen.
        """
        self.take.setChecked(True)
        self.title.setText(str(entry.title))
        unit = str(entry.unit or "")
        if self.unit.findData(unit) < 0:
            self.unit.addItem(
                str(tr("{unit} — wird nicht umgerechnet").format(unit=unit or "?")), unit
            )
        self.unit.setCurrentIndex(self.unit.findData(unit))
        if entry.minimum is not None:
            self.minimum.setValue(float(entry.minimum))
        if entry.maximum is not None:
            self.maximum.setValue(float(entry.maximum))
        self.default.setValue(float(entry.default))
        self.placement.setCurrentIndex(max(0, self.placement.findData(str(entry.placement))))
        self.doc.setText(str(entry.doc or ""))

    def ordered(self) -> bool:
        """Ob kleinster, Vorgabe und größter Wert einen Bereich aufspannen.

        Der Bereichstest fährt die Ecken zwischen Minimum und Maximum ab; steht
        das Minimum darüber, prüft er einen Bereich, den es nicht gibt, und
        meldet ihn als bestanden.

        **Gleich ist nicht genug.** ``min == max`` liest sich wie eine gültige
        Ordnung und ist dieselbe Falschaussage: eine Ecke, geprüft und als
        Bereich verbucht. Dazu wäre ein freigegebenes Maß, das sich nicht
        ändern lässt, ein Feld, das der Kunde vergeblich anfasst — wer einen
        festen Wert will, gibt ihn nicht frei.
        """
        return self.minimum.value() < self.maximum.value() and (
            self.minimum.value() <= self.default.value() <= self.maximum.value()
        )

    def widgets(self) -> tuple[QWidget, ...]:
        return (
            self.take,
            self.title,
            self.unit,
            self.minimum,
            self.maximum,
            self.default,
            self.placement,
            self.doc,
        )

    def exposed(self) -> Any:
        return recipes.ExposedParam(
            name=self.name,
            title=self.title.text().strip() or self.name,
            default=self.default.value(),
            unit=str(self.unit.currentData()),
            minimum=self.minimum.value(),
            maximum=self.maximum.value(),
            placement=str(self.placement.currentData()),
            doc=self.doc.text().strip(),
        )


class _FeatureRow:
    """Eine Zeile der Merkmalsliste: nach außen sichtbar, und unter welchem Namen."""

    def __init__(self, feature: Feature, parent: QWidget) -> None:
        self.feature_id = str(feature.id)
        # „Bohrung 3 · ⌀4,2" und nicht „hole_1": Die Kennung ist der Schlüssel
        # des Rezepts, nicht die Sprache des Kunden — vor dem Speichern soll er
        # sehen, welche Stelle er freigibt. Name wie im Viewport (§18.5), die
        # Zahl ohne Herkunftswort: „Maßherkunft nicht bestimmt" beantwortete
        # hier eine Frage, die beim Speichern niemand stellt (RM-517).
        shown = place_label(feature)
        self.take = QCheckBox(shown, parent)
        self.take.setChecked(True)
        # Wie am Parameter: der Name der Stelle bleibt Name, der Satz wird
        # Beschreibung, und das Namensfeld sagt, zu welcher Stelle es gehört.
        self.take.setAccessibleName(shown)
        self.take.setAccessibleDescription(tr("Dieses Merkmal nach außen geben"))
        tip = feature_measure_tip(feature)
        if tip:
            self.take.setToolTip(tip)
        # Der Name, unter dem ein Projekt die Stelle später anspricht. Er
        # steht unter „Weitere Einstellungen“: Die Vorgabe (die Kennung) taugt,
        # und als Beschriftung vorn war sie ein Rohschlüssel.
        self.label = QLabel(shown, parent)
        self.name = QLineEdit(self.feature_id, parent)
        self.name.setAccessibleName(
            tr("{field} · {value}", field=tr("Name der Stelle"), value=shown)
        )
        self.label.setBuddy(self.name)

    def restore(self, public_name: str | None) -> None:
        """Übernimmt, was der bearbeitete Baustein an dieser Stelle versprach (E6).

        ``None`` heißt: Der Ursprung gab dieses Merkmal **nicht** nach außen —
        dann bleibt der Haken weg. Ein Entwurf, der stillschweigend mehr
        Merkmale verspricht als der Baustein, den er ersetzt, wäre ein anderer
        Baustein unter demselben Namen.
        """
        self.take.setChecked(public_name is not None)
        if public_name is not None:
            self.name.setText(public_name)


def place_label(feature: Feature) -> str:
    """„Bohrung 1 · Ø4,20 mm“ — der Name einer Stelle und ihr Maß, ohne Herkunftswort.

    Der Name kommt aus derselben Quelle wie im Viewport (``feature_name``).
    Die Zahl steht nur, wo sie bestimmt ist; das Wort zu ihrer Herkunft
    („gemessen“, „Maßherkunft nicht bestimmt“) steht in der Kurzhilfe
    (``feature_measure_tip``) — beim Freigeben einer Stelle ist es keine
    Auskunft, sondern ein Rätsel.
    """
    name = feature_name(feature.id, feature)
    shown: Callable[[float], str]
    if feature.kind == "hole":
        key, prefix, shown = "diameter", "Ø", length
    elif feature.kind in ("face", "curved_face"):
        key, prefix, shown = "area", "", area
    else:
        return name
    if not measure_status(feature, key).available:
        return name
    value = measure_text(feature, key, prefix=prefix, format_value=shown, with_source=False)
    return tr("{name} · {value}", name=name, value=value)


#: Wie viele Schrittnummern der Umfangssatz aufzählt, bevor er abkürzt. Bei
#: einem Ausschnitt aus vier Schritten sind die Nummern die Auskunft; bei
#: einem aus dreißig sind sie eine Zeile, die niemand liest.
SCOPE_NUMBERS_SHOWN = 8


def scope_text(op_ids: tuple[int, ...], total: int) -> str:
    """Der Satz über dem Dialog: welche Schritte in den Baustein wandern.

    Reine Rechnung über zwei Zahlen und deshalb ohne Fenster prüfbar.

    Drei Fälle, und der erste ist der häufige: Wer sein Teil gerade gebaut
    hat, wählt nichts aus und bekommt den ganzen Stapel. Das ist richtig so,
    steht aber trotzdem da — eine Vorgabe, die stillschweigend greift, ist
    eine Vermutung des Kunden (§2.4).
    """
    if not op_ids:
        return str(tr("Kein Schritt gewählt — der Baustein bliebe leer."))
    # Dieselben zwei Schlüssel, mit denen der Chat seine Züge zählt
    # (``chat.py``): „alle 1 Schritte" wäre die Art Satz, die eine Anwendung
    # billig aussehen lässt, und übersetzt sind beide längst.
    count = len(op_ids)
    steps = tr("1 Schritt") if count == 1 else tr("{n} Schritte").format(n=count)
    if count >= total:
        return str(tr("Der Baustein bekommt den ganzen Verlauf: {steps}.").format(steps=steps))
    numbers = ", ".join(str(op_id) for op_id in op_ids[:SCOPE_NUMBERS_SHOWN])
    if count > SCOPE_NUMBERS_SHOWN:
        numbers = f"{numbers} …"
    return str(
        tr("Der Baustein bekommt {steps} von {total}: {numbers}").format(
            steps=steps, total=total, numbers=numbers
        )
    )


class RecipeDialog(QDialog):
    """Fragt, was aus dem Ausschnitt ein Baustein macht — und legt ihn an.

    Der Aufrufer bringt mit, was das Dokument hergibt: den Ausschnitt
    (``op_ids``), die eingebetteten Quellen und die Merkmale des ausgewerteten
    Körpers. Alles Übrige beantwortet der Kunde hier.
    """

    saved = Signal(str, bool)
    """Der Name des angelegten Bausteins und ob sein Bereichstest bestand.

    Das zweite Feld, weil der Dialog seinen eigenen Warnsatz nicht zeigen
    kann: Er setzte ihn und rief im selben Atemzug ``accept()``. §24.5
    verlangt den Hinweis, nicht die Verweigerung — also muss er dorthin, wo
    nach dem Schließen noch jemand hinsieht.
    """

    def __init__(
        self,
        document: Document,
        payloads: dict[str, bytes],
        op_ids: tuple[int, ...],
        features: tuple[Feature, ...],
        profile: Profile,
        parent: QWidget | None = None,
        origin: Any = None,
    ) -> None:
        super().__init__(parent)
        self._height = ContentHeight()
        self.setWindowTitle(
            tr("Baustein bearbeiten")
            if origin is not None
            else tr("Auswahl als Baustein speichern")
        )
        self._document = document
        self._payloads = payloads
        self._op_ids = op_ids
        self._profile = profile
        self._origin = origin
        """Der Baustein, aus dem dieses Dokument als Entwurf kam, oder ``None``.

        Ein ``Recipe`` — als ``Any`` angenommen, damit dieser Dialog nichts aus
        dem Kern importieren muss, was er nur weiterreicht. Er belegt daraus
        seine Felder vor und gibt die Importquittung an ``capture`` zurück,
        damit ein fremder Baustein fremd bleibt (§32)."""
        self._leash = WorkerLeash(self)
        self._worker: _CheckWorker | None = None
        self._abandoned = False
        """Ob der Dialog verworfen wurde, während der Bereichstest lief."""
        self._checking = False
        """Ob gerade geschnitten und geprüft wird — die Frage, die ``isVisible``
        nicht beantwortet: Ein Kind eines ungezeigten Fensters meldet ``False``,
        obwohl es gesetzt ist."""

        self.title = QLineEdit(self)
        self.title.setPlaceholderText(tr("Zum Beispiel: Halter für die Werkbank"))
        self.title.setAccessibleName(tr("Name des Bausteins"))
        self.title.textChanged.connect(self._update_enabled)

        # **Die sechs Gruppen des Katalogs, keine siebte.** Der Schlüssel ist
        # englisch und steht im Rezept, der Titel ist übersetzt und steht im
        # Fenster — wie überall im Katalog. Ein selbst getippter Name wäre
        # weder das eine noch das andere: ``Registry.register`` weist jede
        # Gruppe ab, die nicht in ``GROUPS`` steht, und der Kunde bekäme beim
        # Speichern einen internen Fehler statt eines Bausteins.
        #
        # Eine eigene Gruppe für selbst gebaute Teile kommt, wenn es vier
        # davon gibt (Konzept §6.3) — bis dahin wäre sie eine Zeile im Katalog,
        # hinter der meistens nichts steht.
        self.group = QComboBox(self)
        for key, title in GROUPS.items():
            self.group.addItem(str(title), key)
        self.group.setCurrentIndex(max(0, self.group.findData(DEFAULT_GROUP)))
        self.group.setAccessibleName(tr("Gruppe im Katalog"))

        self.doc = QLineEdit(self)
        self.doc.setPlaceholderText(tr("Ein Satz: wofür ist das Teil"))
        self.doc.setAccessibleName(tr("Beschreibung"))

        # **Die Lizenz steht im Klartext, nicht als Kennung.** „CC-BY-SA-4.0"
        # sagt einem Kunden ohne CAD-Vergangenheit nichts; was er wissen muss,
        # ist, was ein anderer mit seinem Teil tun darf. Die Kennung reist in
        # der Datei, der Satz steht im Dialog.
        #
        # Die Vorgabe ist **keine** Lizenz: Wer nichts wählt, hat nichts
        # angegeben, und das ist ein zulässiger Zustand (siehe
        # ``Recipe.license``) — kein stillschweigend gesetzter Wert, der
        # später wie eine Zusage aussieht.
        self.licence = QComboBox(self)
        self.licence.addItem(tr("Nicht angegeben"), "")
        for key, label in recipes.LICENCE_LABELS.items():
            self.licence.addItem(str(label), key)
        self.licence.setAccessibleName(tr("Lizenz für die Weitergabe"))

        self.author = QLineEdit(self)
        self.author.setPlaceholderText(tr("Ihr Name oder Kürzel"))
        self.author.setAccessibleName(tr("Autor"))

        # Ohne Doppelpunkt, wie jedes andere Formular der Anwendung: Die
        # Spalte selbst sagt, dass links der Name der Zeile steht. **Name und
        # Gruppe in einer Zeile** — beides beantwortet „wie finde ich ihn im
        # Katalog wieder“; Beschreibung, Lizenz und Autor stehen hinten
        # (RM-517: 21 Felder für zwei Maße, 978 Punkte hoch).
        naming = QWidget(self)
        naming_row = QHBoxLayout(naming)
        naming_row.setContentsMargins(0, 0, 0, 0)
        naming_row.setSpacing(NORMAL)
        naming_row.addWidget(self.title, 1)
        group_label = QLabel(tr("Gruppe"), naming)
        group_label.setBuddy(self.group)
        naming_row.addWidget(group_label)
        naming_row.addWidget(self.group)
        head = QFormLayout()
        _one_line(head)
        head.addRow(tr("Name"), naming)

        self._params = [_ParamRow(entry, self) for entry in document.parameters.values()]
        self._features = [_FeatureRow(entry, self) for entry in features]

        # **Was mitgeht, steht oben.** Der Titel nennt eine „Auswahl", und bis
        # der Verlauf eine Mehrfachauswahl bekam, gab es keine — es war immer
        # der ganze Stapel. Jetzt gibt es beides, und welches von beidem gilt,
        # sah der Kunde nirgends: Eine Vorgabe, die stillschweigend greift, ist
        # eine Vermutung (§2.4). Der Satz nennt deshalb auch den Normalfall.
        self.scope = QLabel(scope_text(op_ids, len(document.ops)), self)
        self.scope.setWordWrap(True)
        self.scope.setAccessibleName(tr("Umfang des Bausteins"))

        # **Ein Satz, und nur bei fremder Herkunft** (§32, E6): Wer einen
        # eingelesenen Baustein bearbeitet und ersetzt, behält ihn als fremden
        # — die Quittung belegt die Reise und nicht den Inhalt. Das ist die
        # richtige Antwort und zugleich die überraschende; sie gehört dorthin,
        # wo entschieden wird. Bei einem eigenen Baustein stünde hier eine
        # Zeile, die nichts sagt.
        self.provenance = QLabel("", self)
        self.provenance.setWordWrap(True)
        self.provenance.setVisible(False)
        if origin is not None and getattr(origin, "imported_origin", None) is not None:
            self.provenance.setText(
                tr(
                    "Dieser Baustein kam als Datei zu Ihnen. Er bleibt auch nach dem "
                    "Bearbeiten als eingelesen gekennzeichnet."
                )
            )
            self.provenance.setVisible(True)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(NORMAL)
        layout.addWidget(self.scope)
        layout.addWidget(self.provenance)
        layout.addLayout(head)
        layout.addWidget(self._parameter_box())
        layout.addWidget(self._feature_box())
        # Was einmal stimmt und selten geändert wird, steht hinten — mit
        # Inhaltsangabe, damit man weiß, dass es dort ist (``fenster.md``).
        self._more = self._more_box()
        self.more_section = collapsible(
            tr("Weitere Einstellungen"),
            self._more,
            open_now=False,
            contents=tr("Beschreibung, Lizenz, Autor; je Maß Einheit und Platz; Namen der Stellen"),
        )
        layout.addWidget(self.more_section)

        # Was der Bereichstest ergeben hat — leer, bis er gelaufen ist. Er
        # läuft beim Speichern und nicht vorher: Der Kunde soll die Grenzen
        # erst festlegen, sonst prüft er einen Bereich, den er gleich ändert.
        self.range_plan = QLabel("", self)
        self.range_plan.setWordWrap(True)
        self.range_plan.setVisible(False)
        layout.addWidget(self.range_plan)
        self.report = QLabel("", self)
        self.report.setWordWrap(True)
        self.report.setVisible(False)
        # **Die Zahl steht neben dem Balken, nicht darauf** (`tests/test_style.py`):
        # Mittig gesetzt wandert der Rand der Füllung darunter durch, und ab
        # sechzig Prozent liegt sie ganz auf Bernstein — 1,69 Kontrast. Eine
        # Farbe, die auf beiden Gründen trägt, gibt es nicht.
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        self.percent = QLabel("", self)
        self.percent.setVisible(False)
        self.stop_check = QPushButton(tr("Abbrechen"), self)
        self.stop_check.setVisible(False)
        self.stop_check.clicked.connect(self._stop_check)
        waiting = QHBoxLayout()
        waiting.setContentsMargins(0, 0, 0, 0)
        waiting.addWidget(self.progress, 1)
        waiting.addWidget(self.percent)
        waiting.addWidget(self.stop_check)
        layout.addLayout(waiting)
        layout.addWidget(self.report)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        button_layout = buttons.layout()
        assert button_layout is not None
        button_layout.setSpacing(SPACE)
        # ``button()`` gibt für eine Standardschaltfläche, die man selbst
        # angefordert hat, immer eine zurück — eine Prüfung auf ``None`` wäre
        # ein Zweig, den mypy als unerreichbar meldet.
        self._save = buttons.button(QDialogButtonBox.StandardButton.Save)
        self._save.setText(tr("Baustein anlegen"))
        make_primary(self._save)
        buttons.accepted.connect(self._store)
        buttons.rejected.connect(self.reject)
        layout.addStretch(1)
        self._scroll = DialogScrollArea(self)
        self._scroll.setWidget(content)
        self._scroll.contentSizeChanged.connect(self._fit_soon)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        outer.setSpacing(NORMAL)
        outer.addWidget(self._scroll, 1)
        outer.addWidget(buttons)
        for editor in (*content.findChildren(NumberSpin), *content.findChildren(QComboBox)):
            wheel_needs_focus(editor)
        # **Eine Beschriftungskante vorn, eine hinten** (RM-518): Die Namen der
        # Stellen sind lang („Schrägfläche · 2880 mm²“) und zögen sonst die
        # Spalte vorn auf ihre Breite.
        align_forms(self, apart=(self._more,))

        # **Erst jetzt**, denn die Vorbelegung schreibt in Felder, die es
        # vorher nicht gibt — und sie muss vor ``_update_enabled`` stehen, weil
        # der Knopf aus dem Titel liest, ob er anlegt oder ersetzt.
        self._restore_origin()
        self._update_enabled()

    # --- Aufbau ---------------------------------------------------------------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 — Qt-Name
        super().showEvent(event)
        # Noch einmal, sobald das Thema die Schrift gesetzt hat: Haken und
        # Wort messen erst danach ihre wirkliche Breite.
        align_forms(self, apart=(self._more,))
        self._fit_soon("initial")

    def _fit_soon(self, intent: ContentFitIntent = "passive") -> None:
        QTimer.singleShot(0, self, weak_slot(self, RecipeDialog._fit_content, intent))

    def _fit_content(self, intent: ContentFitIntent) -> None:
        """Passt an den Auslöser an; manuelle Breite und Höhe bleiben maßgeblich."""
        self._height.fit(self, self._scroll, intent=intent)

    def _restore_origin(self) -> None:
        """Legt die Angaben des bearbeiteten Bausteins zurück in den Dialog (E6).

        Ohne das hieße „bearbeiten": Titel, Gruppe, Beschreibung, Lizenz, Autor
        und je freigegebenem Maß sieben Felder noch einmal eintippen — und wer
        eines anders tippt, bekommt beim Ersetzen einen anderen Baustein als
        den, den er bearbeiten wollte. Die Herkunft **ist** die Vorbelegung.

        Was der Ursprung nicht kennt, bleibt, wie es der Dialog aufgebaut hat:
        Ein Maß, das der Kunde seit dem letzten Mal hinzugefügt hat, steht mit
        den Vorschlägen aus dem Projektparameter da, und ein Merkmal, das das
        Rezept nie nach außen gab, bleibt ohne Haken.
        """
        origin = self._origin
        if origin is None:
            return
        self.title.setText(str(origin.title))
        self.group.setCurrentIndex(max(0, self.group.findData(str(origin.group))))
        self.doc.setText(str(origin.doc or ""))
        self.licence.setCurrentIndex(max(0, self.licence.findData(str(origin.license or ""))))
        self.author.setText(str(origin.author or ""))
        exposed = {str(entry.name): entry for entry in origin.exposed}
        for row in self._params:
            entry = exposed.get(row.name)
            if entry is not None:
                row.restore(entry)
        # Umgedreht: Das Rezept führt öffentlicher Name → Merkmals-ID, gesucht
        # wird über die ID, die der Auswerter gerade geliefert hat.
        public = {str(value): str(key) for key, value in dict(origin.features).items()}
        for feature_row in self._features:
            feature_row.restore(public.get(feature_row.feature_id))

    def _parameter_box(self) -> QWidget:
        """Je Maß eine Zeile: „[✓] Breite · Vorgabe [120] von [60] bis [240]“.

        Vorher waren es sieben Zeilen je Maß in einem gerahmten Kasten
        (RM-517). Was ein Maß sonst noch trägt — Beschriftung, Einheit, Platz
        im Dialog, Satz —, steht unter „Weitere Einstellungen“; die Vorgaben
        dafür kommen aus dem Projektparameter und stimmen fast immer.
        """
        box = QWidget(self)
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(TIGHT)
        column.addWidget(_section(tr("Welche Maße soll man einstellen können?"), box))
        if not self._params:
            # §2.7: Ein leerer Abschnitt sagt nicht, was fehlt. Dieser hier
            # schon, denn ohne Projektparameter ist der Baustein starr — er
            # ließe sich anlegen und danach an keiner Stelle anpassen.
            empty = QLabel(
                tr(
                    "Dieser Ausschnitt hat keine Projektparameter. Der Baustein "
                    "wäre damit unveränderlich. Legen Sie zuerst Parameter an "
                    "und binden Sie die Maße daran, die einstellbar sein sollen."
                ),
                box,
            )
            empty.setWordWrap(True)
            column.addWidget(empty)
            return box
        form = QFormLayout()
        _one_line(form)
        column.addLayout(form)
        for row in self._params:
            line = QWidget(box)
            fields = QHBoxLayout(line)
            fields.setContentsMargins(0, 0, 0, 0)
            fields.setSpacing(NORMAL)
            # **Die Vorgabe vor ihren Grenzen**: Sie werden aus ihr abgeleitet
            # (``_ParamRow``, halbe Spanne darunter, eine darüber), und der
            # Parameterdialog ordnet ebenso — Wert, dann Grenzen.
            for word, spin in (
                (tr("Vorgabe"), row.default),
                (tr("von", context="Bereich"), row.minimum),
                (tr("bis", context="Bereich"), row.maximum),
            ):
                label = QLabel(word, line)
                label.setBuddy(spin)
                # So breit wie die Zahl, nicht wie der Wertebereich: drei
                # Felder über die ganze Zeile trennten „von“ und „bis“ von
                # ihren Zahlen.
                spin.setFixedWidth(least_number_width(spin) + 2 * NORMAL)
                fields.addWidget(label)
                fields.addWidget(spin)
            fields.addStretch(1)
            for before, after in pairwise((row.take, row.default, row.minimum, row.maximum)):
                QWidget.setTabOrder(before, after)
            if row.hint is not None:
                # **Über der Zeile und außerhalb von ``line``.** Der Satz
                # erklärt, warum der Haken fehlt — säße er im Block, den der
                # Haken abschaltet, wäre er ausgegraut, solange er gebraucht
                # wird, und lesbar erst, wenn er erledigt ist.
                row.hint.setParent(box)
                form.addRow(row.hint)
            # Senkrecht dehnbar, sonst gibt das Formular dem Haken nur seine
            # eigene Höhe, und er steht über der Mitte der Zahlenfelder.
            row.take.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            form.addRow(row.take, line)
            row.take.toggled.connect(line.setEnabled)
            row.take.toggled.connect(self._update_enabled)
            # Die Zeile folgt dem Haken von Anfang an: Eine abgeleitete Zeile
            # geht ohne Haken auf, und bedienbare Felder daneben versprächen
            # eine Wirkung, die sie nicht haben.
            line.setEnabled(row.take.isChecked())
            # **Der Knopf muss mitbekommen, was er prüft**: Grenzen und
            # Vorgabe entscheiden mit, ob er kann.
            for field in (row.minimum, row.default, row.maximum):
                field.valueChanged.connect(self._update_enabled)
        return box

    def _feature_box(self) -> QWidget:
        """Je Stelle ein Haken mit ihrem Namen — der Name im Rezept steht hinten."""
        box = QWidget(self)
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(TIGHT)
        column.addWidget(_section(tr("Welche Stellen soll man später anklicken können?"), box))
        if not self._features:
            empty = QLabel(
                tr(
                    "An diesem Körper wurde kein Merkmal erkannt. Ohne benannte "
                    "Stelle lässt sich später nichts daran ausrichten — der "
                    "Baustein bleibt trotzdem benutzbar."
                ),
                box,
            )
            empty.setWordWrap(True)
            column.addWidget(empty)
            return box
        for row in self._features:
            column.addWidget(row.take)
            row.take.toggled.connect(row.name.setEnabled)
            row.take.toggled.connect(row.label.setEnabled)
            row.take.toggled.connect(self._update_enabled)
            row.name.textChanged.connect(self._update_enabled)
        return box

    def _more_box(self) -> QWidget:
        """Was hinter „Weitere Einstellungen“ steht: Angaben zum Baustein, je
        Maß Beschriftung, Einheit, Platz und Satz, und die Namen der Stellen.
        """
        box = QWidget(self)
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(NORMAL)
        about = QFormLayout()
        _one_line(about)
        about.addRow(tr("Beschreibung"), self.doc)
        about.addRow(tr("Lizenz"), self.licence)
        about.addRow(tr("Autor"), self.author)
        column.addLayout(about)
        for row in self._params:
            column.addWidget(row.heading)
            form = QFormLayout()
            _one_line(form)
            form.addRow(tr("Beschriftung", context="Feld"), row.title)
            form.addRow(tr("Einheit"), row.unit)
            form.addRow(tr("Platz im Dialog"), row.placement)
            form.addRow(tr("Beschreibung"), row.doc)
            column.addLayout(form)
            for field in (row.heading, row.title, row.unit, row.placement, row.doc):
                row.take.toggled.connect(field.setEnabled)
                field.setEnabled(row.take.isChecked())
            for before, after in pairwise((row.title, row.unit, row.placement, row.doc)):
                QWidget.setTabOrder(before, after)
        if self._features:
            column.addWidget(_section(tr("Namen der Stellen"), box))
            names = QFormLayout()
            _one_line(names)
            for feature in self._features:
                names.addRow(feature.label, feature.name)
            column.addLayout(names)
        return box

    # --- Zustand --------------------------------------------------------------

    def _update_enabled(self) -> None:
        """Der Knopf kann nur, was er verspricht.

        Jede Bedingung hat ihren Grund im Kern: ein Name (sonst heißt der
        Baustein wie nichts), mindestens ein benanntes Merkmal (``capture``
        weist leere Mengen ab, §18d), mindestens ein freigegebener Parameter
        (sonst ist das Teil unveränderlich), Grenzen in ihrer Ordnung, je
        Stelle ein eigener Name — und ein Name, den es noch nicht gibt.

        **Der vergebene Name gehört hierher und nicht ans Ende.** Er wurde
        beim Klick auf *Anlegen* geprüft, also nachdem der Kunde Name, Gruppe,
        Beschreibung, zu jedem Parameter sechs Felder und zu jedem Merkmal eine
        Zeile ausgefüllt hatte. Die Auskunft war richtig und kam zwölf Felder
        zu spät.
        """
        title = self.title.text().strip()
        named = any(row.take.isChecked() for row in self._features)
        adjustable = any(row.take.isChecked() for row in self._params)
        ordered = all(row.ordered() for row in self._params if row.take.isChecked())
        unique = self._unique_feature_names()
        from app.core.knowledge.parts.range_check import require_range_size

        exposed = tuple(row.exposed() for row in self._params if row.take.isChecked())
        count = recipes.range_size(exposed)
        range_error = ""
        try:
            require_range_size(count)
        except AppError as error:
            range_error = str(error.detail)
        # **Nur, wenn es den Kunden etwas angeht** (RM-517): „Bereichstest:
        # 4 Kombinationen.“ stand vor jedem Speichern da — eine Zahl über
        # unsere Prüfung, keine über sein Teil. Was bleibt, ist der Fall, in
        # dem zu viele Maße freigegeben sind; der Satz dazu kommt aus dem Kern
        # und nennt den Weg.
        self.range_plan.setText(range_error)
        self.range_plan.setVisible(bool(range_error))
        # **Ein vergebener Name ist kein Fehler, sondern der zweite Fall.**
        # „Ändern heißt neu speichern" steht im Handbuch (Kapitel *Eigene
        # Bausteine*), und wer die Breite seines Halters nachträglich ändert,
        # soll keinen zweiten Namen erfinden müssen. Der Knopf sagt, was er
        # tut, und daneben steht, was mit dem vorhandenen Stand geschieht.
        taken = bool(title) and taken_name(_identifier(title))
        self._save.setEnabled(
            bool(title)
            and named
            and adjustable
            and ordered
            and unique
            and not range_error
            and not self._checking
        )
        self._save.setText(tr("Baustein ersetzen") if taken else tr("Baustein anlegen"))
        hint = (
            range_error or self._why_locked(named, adjustable, ordered, unique)
            if not self._save.isEnabled()
            else str(
                tr(
                    "Ersetzt den vorhandenen Baustein dieses Namens — Datei, "
                    "Katalogeintrag und Rechnung. Projekte, die ihn benutzen, "
                    "rechnen beim nächsten Öffnen mit dem neuen Stand."
                )
            )
            if taken
            else ""
        )
        # **An alle drei Kanäle, nicht nur an den Tooltip** (Regel 18). Der Satz
        # stand hier immer schon — ``_why_locked`` formuliert ihn —, er erreichte
        # aber nur die Maus. Wer den Knopf mit der Tastatur anfährt, liest die
        # Statuszeile; ein Bildschirmleser die zugängliche Beschreibung. Das
        # Handbuch verspricht den Satz an dieser Stelle ausdrücklich; eingelöst
        # war er für zwei von drei Wegen.
        self._save.setToolTip(hint)
        self._save.setStatusTip(hint)
        self._save.setAccessibleDescription(hint)

    # --- Anlegen --------------------------------------------------------------

    def _unique_feature_names(self) -> bool:
        """Ob jede freigegebene Stelle einen eigenen Namen trägt.

        Die Namen werden zu Schlüsseln eines Wörterbuchs, und zwei gleiche
        überschreiben sich dort **still**: Der Kunde gibt zwei Bohrungen
        denselben Namen und bekommt einen Baustein mit einer.
        """
        chosen = [
            row.name.text().strip() or row.feature_id
            for row in self._features
            if row.take.isChecked()
        ]
        return len(chosen) == len(set(chosen))

    def _why_locked(self, named: bool, adjustable: bool, ordered: bool, unique: bool) -> str:
        """Warum der Knopf nicht kann — der erste Grund, der zutrifft.

        Einer und nicht alle: Vier Sätze auf einmal liest niemand, und wer den
        ersten behebt, bekommt den nächsten. Die Reihenfolge folgt dem Weg
        durch den Dialog, von oben nach unten.

        Ein **vergebener Name steht nicht darunter**: Er ist kein Hindernis,
        sondern der zweite Fall, und was er bedeutet, sagt der Knopf selbst.
        """
        if self._checking:
            return str(tr("Der Baustein wird gerade geprüft — einen Augenblick."))
        if not self.title.text().strip():
            return str(tr("Der Baustein braucht einen Namen."))
        if not adjustable:
            if self._params and all(row.derived for row in self._params):
                # **Der häufige Fall seit der Umstellung.** Trägt jeder
                # Parameter des Ausschnitts einen Ausdruck, ist keine Zeile
                # vorgehakt — und „sonst ist das Teil starr" ließe den Kunden
                # nach einem Haken suchen, den er längst sieht.
                return str(
                    tr(
                        "Jeder Wert hier wird aus einem anderen gerechnet. Haken Sie "
                        "den an, der einstellbar sein soll — er verliert dabei seine "
                        "Formel."
                    )
                )
            return str(tr("Geben Sie mindestens ein Maß frei — sonst ist das Teil starr."))
        if not ordered:
            return str(
                tr(
                    "Ein Bereich braucht zwei verschiedene Enden, und die Vorgabe "
                    "muss dazwischen liegen. Prüfen Sie kleinsten und größten Wert."
                )
            )
        if not named:
            return str(tr("Geben Sie mindestens eine Stelle frei, an der man das Teil anfasst."))
        if not unique:
            return str(tr("Zwei Stellen tragen denselben Namen — jede braucht einen eigenen."))
        return ""

    def _store(self) -> None:
        """Rezept schneiden, Bereich prüfen, ablegen — in dieser Reihenfolge."""
        # **Nur einer läuft — und die Frage steht vor allem anderen.** Nach
        # einem Fehlschlag gibt ``_update_enabled`` den Knopf wieder frei, und
        # ein zweiter Klick startete einen zweiten Arbeiter: ``self._worker``
        # wurde überschrieben, der erste lief ohne Halter weiter und meldete in
        # einen Dialog, der ihn nicht mehr kennt. Gefragt wird ganz oben, denn
        # weiter unten hätte der zweite Klick den Balken des ersten schon auf
        # null zurückgesetzt und seinen Satz überschrieben.
        if self._worker is not None and self._worker.isRunning():
            # Der Riegel, nicht die Auskunft: Der Knopf ist währenddessen
            # gesperrt und trägt den Grund (``_why_locked``). Hierher kommt nur,
            # wer den Weg an ihm vorbei nimmt — ein Kürzel, ein zweites
            # Fenster, ein Signal, das den Knopf zwischendurch freigegeben hat.
            return

        # Was der Schnitt braucht, wird **hier** abgelesen: Widgets gehören dem
        # Hauptthread, und ein Arbeiter, der sie anfasst, ist ein Absturz, der
        # nur meistens ausbleibt (§38). Das Ablesen kostet nichts — es ist der
        # Schnitt danach, der rechnet.
        title = self.title.text().strip()
        name = _identifier(title)
        group = str(self.group.currentData())
        exposed = tuple(row.exposed() for row in self._params if row.take.isChecked())
        features = {
            row.name.text().strip() or row.feature_id: row.feature_id
            for row in self._features
            if row.take.isChecked()
        }
        doc = self.doc.text().strip()
        licence = str(self.licence.currentData() or "")
        author = self.author.text().strip()
        # Nur, solange derselbe Baustein gemeint ist: Wer den Namen ändert,
        # legt einen **zweiten** an, und der ist seiner. Die Quittung gehört
        # dem Eintrag, aus dem der Entwurf kam, nicht dem Entwurf.
        imported_origin = (
            getattr(self._origin, "imported_origin", None)
            if self._origin is not None and name == str(self._origin.name)
            else None
        )

        # **Erst nachsehen, ob der Name frei ist — vor dem Schneiden, vor dem
        # Schreiben und vor dem Warten.** ``recipes.save`` legt die Datei unter
        # dem Namen an und überschreibt dabei, was dort liegt; ``register``
        # merkt die Kollision erst danach. Wer einen Namen zweimal vergibt,
        # verlöre still sein erstes Rezept und bekäme einen internen Fehler
        # dazu. Gefragt wird ganz vorn, denn der Name steht fest, bevor
        # irgendetwas gerechnet ist — und eine Absage nach vier Sekunden
        # Wartebalken ist eine Absage zu spät.
        def cut() -> Any:
            """Der Schnitt mit den abgelesenen Werten — läuft im Arbeiter."""
            return recipes.capture(
                self._document,
                self._payloads,
                name=name,
                title=title,
                group=group,
                op_ids=self._op_ids,
                exposed=exposed,
                features=features,
                doc=doc,
                licence=licence,
                author=author,
                # **Die Reise reist mit** (E6, §32): Ein eingelesener Baustein
                # bleibt eingelesen, auch wenn der Kunde ein Maß geändert hat.
                # Ohne diese Zeile machte ``_catalog_source`` beim nächsten
                # Start still einen eigenen daraus.
                imported_origin=imported_origin,
                profile=self._profile,
            )

        self._show_waiting(True)
        self._say(tr("Der Baustein wird über seine Grenzen geprüft …"))
        # **Über ``_update_enabled``, nicht mit der Hand.** ``setEnabled(False)``
        # sperrte den Knopf ohne Grund daneben — und ein Tastendruck ließ ihn
        # danach wieder aufgehen, weil ``_update_enabled`` von der laufenden
        # Prüfung nichts wusste. Jetzt weiß es davon, und der Weg ist einer.
        self._update_enabled()
        self._fit_soon()
        QTimer.singleShot(0, self, self._reveal_report)
        worker = _CheckWorker(cut, self._profile)
        worker.step.connect(self._step)
        worker.failed.connect(self._failed)
        worker.done.connect(self._checked)
        # **``crashed`` gibt eine Zeichenkette, kein ``AppError``** — und eine
        # Zeichenkette hat ein ``title``: die Methode ``str.title()``. Ohne die
        # Verpackung las ``_failed`` sie als Titel, und im Fenster stand
        # ``<built-in method title of str object at 0x…>``. Dieselbe Verpackung
        # benutzen alle anderen Arbeiter des Projekts.
        worker.crashed.connect(lambda detail: self._failed(InternalError(detail=detail)))
        worker.finished.connect(lambda done=worker: self._worker_done(done))
        self._worker = worker
        self._leash.start(worker)

    def _say(self, text: str) -> None:
        """Ein Satz unter den Feldern — sichtbar nur, solange er etwas sagt."""
        self.report.setText(text)
        self.report.setVisible(bool(text))

    def _reveal_report(self) -> None:
        """Macht den Prüfstatus im Rollbereich sichtbar, ohne das Fenster zu ändern."""
        self._scroll.ensureWidgetVisible(self.report, 0, NORMAL)

    def reject(self) -> None:
        """Abbrechen heißt abbrechen — auch mitten im Bereichstest.

        Der Test läuft in einem Arbeiter, und der lässt sich nicht anhalten;
        was er meldet, muss deshalb hier verfallen. Ohne diese Notiz legte
        ``_checked`` den Baustein an, nachdem der Dialog längst zu war — ein
        Ergebnis auf eine Frage, die zurückgezogen wurde.
        """
        self._abandoned = True
        if self._worker is not None:
            self._worker.stop()
        super().reject()

    def _show_waiting(self, running: bool) -> None:
        """Balken, Zahl und Abbrechen gehören zusammen — sichtbar oder nicht."""
        # **Der Zustand steht hier, nicht in ``isVisible()``.** Ein Kind eines
        # ungezeigten Fensters meldet ``False``, obwohl es gesetzt ist — im
        # Betrieb fällt das nie auf, im Test sofort. Und die Frage lautet
        # ohnehin „läuft eine Prüfung?", nicht „sieht man den Balken?".
        self._checking = running
        for widget in (self.progress, self.percent, self.stop_check):
            widget.setVisible(running)
        if running:
            self.progress.setValue(0)
            self.percent.setText("")

    def _step(self, share: float, note: str) -> None:
        """Eine Ecke ist durch — Balken, Zahl und Satz nachziehen."""
        self.progress.setValue(max(0, min(100, round(share * 100))))
        self.percent.setText(f"{localised(f'{share * 100:.0f}')} %")
        if note:
            self._say(note)

    def _stop_check(self) -> None:
        """Der Bereichstest wird abgebrochen, der Dialog bleibt offen.

        Anders als *Abbrechen* unten: Das verwirft den ganzen Vorgang. Wer hier
        drückt, will die Prüfung nicht abwarten — und darf danach Grenzen
        ändern und es noch einmal versuchen.
        """
        if self._worker is not None:
            self._worker.stop()
        self._show_waiting(False)
        self._say(tr("Der Bereichstest wurde abgebrochen."))
        self._update_enabled()

    def _checked(self, checked: Any) -> None:
        """Der Bereichstest ist durch — ablegen und registrieren."""
        if self._abandoned or not self._checking:
            # Nicht mehr gefragt: Der Dialog ist zu, oder jemand hat die
            # Prüfung abgebrochen und das Ergebnis kommt hinterher.
            return
        self._show_waiting(False)
        try:
            # **Ein Aufruf für beide Fälle.** ``replace`` legt an, wenn der Name
            # frei ist, und tauscht sonst Datei, Katalogeintrag und Operation
            # zusammen — mit Rückstellung, wenn ein Schritt scheitert. Der
            # frühere Weg war ``save`` und dann ``register``, und dazwischen lag
            # die Lücke: ``save`` hatte die alte Datei längst überschrieben,
            # wenn ``register`` den Namen ablehnte.
            recipes.replace(checked)
        except AppError as error:
            self._failed(error)
            return
        except OSError as problem:
            # **Der Datenträger ist kein AppError.** Volle Platte, Schreibschutz,
            # ein Ordner, den jemand weggezogen hat: ``save`` reicht den
            # ``OSError`` durch, und ungefangen verlässt er den Slot — die
            # Oberfläche steht dann mit laufendem Balken da und sagt nichts
            # (Regel 17).
            self._failed(
                FileWriteError(
                    target=str(getattr(checked, "name", "")),
                    detail=str(problem),
                )
            )
            return
        report = getattr(checked, "range_report", None)
        # **Der Warnsatz gehört nach draußen.** Er stand hier, und einen Atemzug
        # später schloss ``accept()`` den Dialog — gesetzt, nie gelesen. §24.5
        # verlangt den Hinweis, nicht die Verweigerung: Der Baustein ist
        # angelegt und im Katalog, er trägt nur die Warnung mit. Wer sie lesen
        # soll, muss sie dort finden, wo er nach dem Schließen hinsieht.
        self.saved.emit(str(checked.name), getattr(report, "passed", None) is not False)
        self.accept()

    def _failed(self, error: object) -> None:
        """Titel, Grund **und was hilft** — die Vorschläge des Kerns fielen weg.

        ``problem_text`` setzt jede Angabe in eine eigene Zeile und hängt die
        Vorschläge an, die hier kein Knopf einlöst (Regel 17).
        """
        self._show_waiting(False)
        self._update_enabled()
        self._say(
            problem_text(error)
            if isinstance(error, AppError)
            else str(tr("Der Baustein ließ sich nicht anlegen."))
        )
        _log.warning("recipe could not be stored: %s", error)

    def _worker_done(self, worker: object) -> None:
        if self._worker is worker:
            self._worker = None

    def release(self) -> None:
        """Wartet auf den Bereichstest — ein Fenster geht nicht vor seinem Arbeiter."""
        self._leash.wait_all()


def _one_line(form: QFormLayout) -> None:
    """Beschriftung und Feld in einer Zeile, nie darüber (``fenster.md``).

    Senkrecht mittig: Ein Haken ist niedriger als die Zahlenfelder daneben und
    stand sonst über ihrer Mitte.
    """
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    # Fest, denn der Stilabstand hängt an der Art der Beschriftung: Hinter
    # einem Haken war er kleiner als hinter einem Wort, und die Felder unter
    # „Name“ begannen zehn Punkte weiter rechts als die unter „Breite“.
    form.setHorizontalSpacing(NORMAL)


def _section(text: str, parent: QWidget) -> QLabel:
    """Eine flache Abschnittsüberschrift statt eines gerahmten Kastens (RM-518)."""
    label = QLabel(text, parent)
    label.setWordWrap(True)
    set_level(label, "section")
    return label


def taken_name(name: str) -> bool:
    """Ob dieser Bausteinname schon vergeben ist — im Register oder auf Platte.

    Beides, und nicht nur eines: Registriert ist, was beim Start geladen wurde;
    auf der Platte kann eine Datei liegen, die dabei fehlgeschlagen ist. Wer
    nur das Register fragt, überschreibt sie.
    """
    if PARTS.has(name):
        return True
    return (recipes.recipes_dir() / f"{name}.json").exists()


def _identifier(title: str) -> str:
    """Aus dem Titel einen Bezeichner, wie ihn das Register verlangt.

    Kleinbuchstaben, Unterstriche, keine Umlaute — und wenn davon nichts
    übrig bleibt, ein Ersatzname statt einer leeren Zeichenkette.
    """
    table = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    folded = "".join(table.get(char, char) for char in title.casefold())
    # **Alles andere Fremde wird zerlegt, nicht durchgelassen.** ``é`` und ``ñ``
    # sind ``isalnum()`` und überlebten den Filter darunter — das Register
    # nimmt sie nicht (``^[a-z][a-z0-9_]*$``), und der Kunde bekam für
    # „Café-Halter" einen internen Fehler statt eines Bausteins. NFKD trennt
    # den Akzent vom Buchstaben, und die kombinierenden Zeichen fallen weg.
    folded = unicodedata.normalize("NFKD", folded)
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    cleaned = "".join(char if char.isascii() and char.isalnum() else "_" for char in folded)
    stripped = "_".join(part for part in cleaned.split("_") if part)
    if not stripped:
        return "eigener_baustein"
    # **Und er fängt mit einem Buchstaben an.** „3er Halter" ergab „3er_halter",
    # und auch das lehnt das Muster ab. Ein Wort davor ist ehrlicher als eine
    # abgeschnittene Ziffer: Der Kunde hat sie hingeschrieben, weil sie zählt.
    if not stripped[0].isalpha():
        stripped = f"teil_{stripped}"
    return stripped
