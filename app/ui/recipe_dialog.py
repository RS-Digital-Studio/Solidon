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
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError
from app.core.knowledge.parts import GROUPS, PARTS
from app.core.knowledge.parts import recipe as recipes
from app.core.log import get_logger
from app.core.types import Document, Feature, Profile
from app.i18n import tr
from app.ui.labels import NumberSpin, feature_label
from app.ui.leash import Worker, WorkerLeash
from app.ui.style import TIGHT, make_primary

_log = get_logger(__name__)

#: Die Gruppe, unter der ein selbst angelegter Baustein im Katalog steht.
#:
#: Eine eigene und nicht die des Vorbilds: Der Kunde soll sein Teil
#: wiederfinden, ohne es zwischen siebzehn mitgelieferten zu suchen. Ändern
#: kann er sie im Dialog — die vorhandenen Gruppen stehen zur Auswahl.
#: Wo ein eigener Baustein landet, solange der Kunde nichts anderes wählt —
#: dieselbe Vorgabe, die ``recipe.from_data`` für ein Rezept ohne Gruppe nimmt.
DEFAULT_GROUP = "structure"

#: Wie hoch eine Rollfläche höchstens von sich aus werden darf, in
#: Bildpunkten. Rund zwei Parameterzeilen — genug, damit sichtbar ist, dass
#: es je Parameter einen Block gibt, und wenig genug, dass zwölf davon den
#: Dialog nicht ueber den Schirm schieben.
MOST_ROOM = 520

# Die zwei Plätze, die ein freigegebener Wert im späteren Dialog haben kann
# (§2.5, gestufte Tiefe). Schlüssel des Rezeptformats und keine Beschriftungen —
# als Konstanten, weil ein Literal in einem ``addItem`` von der Prüfung auf
# feste Oberflächentexte nicht von einem Text zu unterscheiden ist.
PLACE_FRONT = "front"
PLACE_ADVANCED = "advanced"


class _RangeWorker(Worker):
    """Der Bereichstest, abseits des Oberflächen-Threads (§2.8, §38).

    Er wertet das Rezept an den Ecken jedes Zahlenbereichs aus — bei drei
    freigegebenen Maßen sind das sechs Auswertungen, und jede rechnet den
    ganzen Ausschnitt. Im Hauptthread wäre der Dialog dabei eingefroren.
    """

    done = Signal(object)

    def __init__(self, recipe: Any, profile: Profile) -> None:
        super().__init__()
        self._recipe = recipe
        self._profile = profile

    def work(self) -> None:
        self.done.emit(recipes.range_check(self._recipe, self._profile))


class _ParamRow:
    """Eine Zeile der Parameterliste: freigeben, und wie er im Dialog aussieht."""

    def __init__(self, parameter: Any, parent: QWidget) -> None:
        self.name = parameter.name
        # **Der Haken trägt den Namen des Projektparameters.** Ohne ihn stehen
        # bei drei Parametern dreimal dieselben sieben Zeilen untereinander —
        # „Beschriftung: Breite", „Beschriftung: Höhe" —, und welcher Parameter
        # gerade eingerichtet wird, steht nirgends. Sichtbar wurde das erst am
        # gerenderten Dialog; die Felder waren einzeln alle richtig.
        self.take = QCheckBox(str(parameter.name), parent)
        self.take.setChecked(True)
        self.take.setAccessibleName(tr("Diesen Wert freigeben"))

        self.title = QLineEdit(str(parameter.title or parameter.name), parent)
        self.title.setAccessibleName(tr("Beschriftung"))
        self.unit = QLineEdit(str(parameter.unit or ""), parent)
        self.unit.setAccessibleName(tr("Einheit"))
        self.unit.setFixedWidth(64)

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
        self.minimum.setValue(
            float(parameter.minimum) if parameter.minimum is not None else min(value / 2, value)
        )
        self.maximum.setValue(
            float(parameter.maximum) if parameter.maximum is not None else max(value * 2, value)
        )
        self.default.setValue(value)
        self.minimum.setAccessibleName(tr("Kleinster Wert"))
        self.maximum.setAccessibleName(tr("Größter Wert"))
        self.default.setAccessibleName(tr("Vorgabe"))

        self.placement = QComboBox(parent)
        self.placement.addItem(tr("Vorn im Dialog"), PLACE_FRONT)
        self.placement.addItem(tr("Unter „Weitere Einstellungen“"), PLACE_ADVANCED)
        self.placement.setAccessibleName(tr("Wo der Wert steht"))

        self.doc = QLineEdit(parent)
        self.doc.setPlaceholderText(tr("Ein Satz: was passiert, wenn man ihn ändert"))
        self.doc.setAccessibleName(tr("Beschreibung"))

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
            unit=self.unit.text().strip(),
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
        # sehen, welche Stelle er freigibt. Dieselbe Quelle wie Viewport und
        # Statusleiste (§18.5); zwei Formulierungen für ein Merkmal wären zwei
        # Gelegenheiten, auseinanderzulaufen.
        self.take = QCheckBox(feature_label(feature.id, feature), parent)
        self.take.setChecked(True)
        self.take.setAccessibleName(tr("Dieses Merkmal nach außen geben"))
        self.name = QLineEdit(self.feature_id, parent)
        self.name.setAccessibleName(tr("Öffentlicher Name"))


class RecipeDialog(QDialog):
    """Fragt, was aus dem Ausschnitt ein Baustein macht — und legt ihn an.

    Der Aufrufer bringt mit, was das Dokument hergibt: den Ausschnitt
    (``op_ids``), die eingebetteten Quellen und die Merkmale des ausgewerteten
    Körpers. Alles Übrige beantwortet der Kunde hier.
    """

    saved = Signal(str)
    """Der Name des angelegten Bausteins — das Fenster frischt den Katalog auf."""

    def __init__(
        self,
        document: Document,
        payloads: dict[str, bytes],
        op_ids: tuple[int, ...],
        features: tuple[Feature, ...],
        profile: Profile,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Auswahl als Baustein speichern"))
        self._document = document
        self._payloads = payloads
        self._op_ids = op_ids
        self._profile = profile
        self._leash = WorkerLeash(self)
        self._worker: _RangeWorker | None = None
        self._recipe: Any = None
        self._abandoned = False
        """Ob der Dialog verworfen wurde, während der Bereichstest lief."""

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

        head = QFormLayout()
        head.addRow(tr("Name:"), self.title)
        head.addRow(tr("Gruppe:"), self.group)
        head.addRow(tr("Beschreibung:"), self.doc)

        self._params = [_ParamRow(entry, self) for entry in document.parameters.values()]
        self._features = [_FeatureRow(entry, self) for entry in features]

        layout = QVBoxLayout(self)
        layout.setSpacing(TIGHT)
        layout.addLayout(head)
        layout.addWidget(self._parameter_box())
        layout.addWidget(self._feature_box())

        # Was der Bereichstest ergeben hat — leer, bis er gelaufen ist. Er
        # läuft beim Speichern und nicht vorher: Der Kunde soll die Grenzen
        # erst festlegen, sonst prüft er einen Bereich, den er gleich ändert.
        self.report = QLabel("", self)
        self.report.setWordWrap(True)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        layout.addWidget(self.report)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        # ``button()`` gibt für eine Standardschaltfläche, die man selbst
        # angefordert hat, immer eine zurück — eine Prüfung auf ``None`` wäre
        # ein Zweig, den mypy als unerreichbar meldet.
        self._save = buttons.button(QDialogButtonBox.StandardButton.Save)
        self._save.setText(tr("Baustein anlegen"))
        make_primary(self._save)
        buttons.accepted.connect(self._store)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_enabled()

    # --- Aufbau ---------------------------------------------------------------

    def _parameter_box(self) -> QWidget:
        box = QGroupBox(tr("Welche Maße soll man einstellen können?"), self)
        form = QFormLayout(box)
        if not self._params:
            # §2.7: Ein leerer Kasten sagt nicht, was fehlt. Dieser hier schon,
            # denn ohne Projektparameter ist der Baustein starr — er ließe sich
            # anlegen und danach an keiner Stelle anpassen.
            form.addRow(
                QLabel(
                    tr(
                        "Dieser Ausschnitt hat keine Projektparameter. Der Baustein "
                        "wäre damit unveränderlich. Legen Sie zuerst Parameter an "
                        "und binden Sie die Maße daran, die einstellbar sein sollen."
                    ),
                    box,
                )
            )
            return _scrolled(box, self)
        for row in self._params:
            line = QWidget(box)
            strip = QFormLayout(line)
            strip.setContentsMargins(0, 0, 0, 0)
            strip.addRow(tr("Beschriftung:"), row.title)
            strip.addRow(tr("Einheit:"), row.unit)
            strip.addRow(tr("Kleinster Wert:"), row.minimum)
            strip.addRow(tr("Größter Wert:"), row.maximum)
            strip.addRow(tr("Vorgabe:"), row.default)
            strip.addRow(tr("Steht:"), row.placement)
            strip.addRow(tr("Beschreibung:"), row.doc)
            form.addRow(row.take, line)
            row.take.toggled.connect(line.setEnabled)
            row.take.toggled.connect(self._update_enabled)
        return _scrolled(box, self)

    def _feature_box(self) -> QWidget:
        box = QGroupBox(tr("Welche Stellen soll man später anklicken können?"), self)
        form = QFormLayout(box)
        if not self._features:
            form.addRow(
                QLabel(
                    tr(
                        "An diesem Körper wurde kein Merkmal erkannt. Ohne benannte "
                        "Stelle lässt sich später nichts daran ausrichten — der "
                        "Baustein bleibt trotzdem benutzbar."
                    ),
                    box,
                )
            )
            return _scrolled(box, self)
        # Eine Kopfzeile über den zwei Spalten. Ohne sie steht neben „Bohrung 1
        # · Ø5,20 mm" ein Feld mit „hole_1" darin, und niemand weiß, ob er das
        # ändern darf oder soll — der Kastentitel erklärt den Haken, nicht das
        # Feld daneben.
        head_place = QLabel(tr("Stelle"), box)
        head_name = QLabel(tr("Name im Rezept"), box)
        for label in (head_place, head_name):
            font = label.font()
            font.setBold(True)
            label.setFont(font)
        form.addRow(head_place, head_name)

        for row in self._features:
            form.addRow(row.take, row.name)
            row.take.toggled.connect(row.name.setEnabled)
            row.take.toggled.connect(self._update_enabled)
        return _scrolled(box, self)

    # --- Zustand --------------------------------------------------------------

    def _update_enabled(self) -> None:
        """Der Knopf kann nur, was er verspricht.

        Drei Bedingungen, und jede hat ihren Grund im Kern: ein Name (sonst
        heißt der Baustein wie nichts), mindestens ein benanntes Merkmal
        (``capture`` weist leere Mengen ab, §18d) und mindestens ein
        freigegebener Parameter (sonst ist das Teil unveränderlich).
        """
        named = any(row.take.isChecked() for row in self._features)
        adjustable = any(row.take.isChecked() for row in self._params)
        self._save.setEnabled(bool(self.title.text().strip()) and named and adjustable)
        self._save.setToolTip(
            ""
            if self._save.isEnabled()
            else tr(
                "Zum Anlegen fehlt: ein Name, mindestens eine anklickbare Stelle "
                "und mindestens ein einstellbares Maß."
            )
        )

    # --- Anlegen --------------------------------------------------------------

    def _store(self) -> None:
        """Rezept schneiden, Bereich prüfen, ablegen — in dieser Reihenfolge."""
        title = self.title.text().strip()
        try:
            self._recipe = recipes.capture(
                self._document,
                self._payloads,
                name=_identifier(title),
                title=title,
                group=str(self.group.currentData()),
                op_ids=self._op_ids,
                exposed=tuple(row.exposed() for row in self._params if row.take.isChecked()),
                features={
                    row.name.text().strip() or row.feature_id: row.feature_id
                    for row in self._features
                    if row.take.isChecked()
                },
                doc=self.doc.text().strip(),
                profile=self._profile,
            )
        except AppError as error:
            # Der Kern prüft beim Schneiden und sagt mit Vorschlag, was fehlt
            # (Regel 17). Hier wird nichts umformuliert — der Satz von dort ist
            # genauer als jeder, den dieser Dialog erfinden könnte.
            self.report.setText(f"{error.title}\n{error.detail or ''}".strip())
            return

        # **Erst nachsehen, ob der Name frei ist — vor dem Schreiben und vor
        # dem Warten.** ``recipes.save`` legt die Datei unter dem Namen an und
        # überschreibt dabei, was dort liegt; ``register`` merkt die Kollision
        # erst danach. Wer einen Namen zweimal vergibt, verlöre still sein
        # erstes Rezept und bekäme einen internen Fehler dazu.
        #
        # Gefragt wird vor dem Bereichstest: Der dauert, und eine Absage nach
        # dreißig Sekunden Wartebalken ist eine Absage zu spät.
        if taken_name(self._recipe.name):
            self.report.setText(
                str(
                    tr(
                        "Einen Baustein dieses Namens gibt es schon. Wählen Sie einen "
                        "anderen Namen — der vorhandene bleibt, wie er ist."
                    )
                )
            )
            return

        self.progress.setVisible(True)
        self.report.setText(tr("Der Baustein wird über seine Grenzen geprüft …"))
        if self._save is not None:
            self._save.setEnabled(False)
        worker = _RangeWorker(self._recipe, self._profile)
        worker.done.connect(self._checked)
        worker.crashed.connect(self._failed)
        worker.finished.connect(lambda done=worker: self._worker_done(done))
        self._worker = worker
        self._leash.start(worker)

    def reject(self) -> None:
        """Abbrechen heißt abbrechen — auch mitten im Bereichstest.

        Der Test läuft in einem Arbeiter, und der lässt sich nicht anhalten;
        was er meldet, muss deshalb hier verfallen. Ohne diese Notiz legte
        ``_checked`` den Baustein an, nachdem der Dialog längst zu war — ein
        Ergebnis auf eine Frage, die zurückgezogen wurde.
        """
        self._abandoned = True
        super().reject()

    def _checked(self, checked: Any) -> None:
        """Der Bereichstest ist durch — ablegen und registrieren."""
        if self._abandoned:
            return
        self.progress.setVisible(False)
        self._recipe = checked
        try:
            recipes.save(checked)
            recipes.register(checked)
        except AppError as error:
            self._failed(error)
            return
        report = getattr(checked, "range_report", None)
        passed = getattr(report, "passed", None)
        if passed is False:
            # §24.5 verlangt den Hinweis, nicht die Verweigerung: Der Baustein
            # ist angelegt und im Katalog, er trägt nur die Warnung mit.
            self.report.setText(
                tr(
                    "Angelegt — aber an den Grenzen kam kein brauchbarer Körper "
                    "heraus. Der Katalog zeigt das an; engere Grenzen beheben es."
                )
            )
        self.saved.emit(str(checked.name))
        self.accept()

    def _failed(self, error: object) -> None:
        self.progress.setVisible(False)
        self._update_enabled()
        title = getattr(error, "title", None)
        detail = getattr(error, "detail", "") or ""
        self.report.setText(f"{title or tr('Der Baustein ließ sich nicht anlegen.')}\n{detail}")
        _log.warning("recipe could not be stored: %s", error)

    def _worker_done(self, worker: object) -> None:
        if self._worker is worker:
            self._worker = None

    def release(self) -> None:
        """Wartet auf den Bereichstest — ein Fenster geht nicht vor seinem Arbeiter."""
        self._leash.wait_all()


def _scrolled(inner: QWidget, parent: QWidget) -> QScrollArea:
    """Ein Kasten, der rollt statt zu wachsen.

    Zwölf Parameter sind selten und möglich; ohne das wächst der Dialog über
    den Bildschirm hinaus, und der Knopf steht unten außerhalb.
    """
    area = QScrollArea(parent)
    area.setWidget(inner)
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    # **Und sie sagt, wie viel sie zeigen möchte.** Eine QScrollArea meldet von
    # sich aus eine Wunschhöhe, die mit ihrem Inhalt nichts zu tun hat: Der
    # Dialog ging damit so klein auf, dass schon der zweite Parameter
    # angeschnitten war, und wer drei anlegt, sieht beim Öffnen nur den
    # ersten. Gedeckelt bleibt es trotzdem — zwölf Parameter sollen den
    # Dialog nicht über den Bildschirm hinaus wachsen lassen.
    area.setMinimumHeight(min(inner.sizeHint().height(), MOST_ROOM))
    return area


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
