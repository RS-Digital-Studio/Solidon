"""Die drei Panels links und der Prüfbericht rechts (Bauplan §2.5).

Drei einklappbare Abschnitte, keine drei Fenster: Objektbaum, Parameter,
Verlauf. Sie lesen aus dem Dokument und der letzten Auswertung, und sie ändern
nie selbst Geometrie — jede Änderung geht durch eine Operation (AGENTS.md
Regel 2).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final, cast

from PySide6.QtCore import QByteArray, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core import drawing
from app.core.drawing import Theme as DrawingTheme
from app.core.errors import (
    ARRANGE_ON_BED,
    CHANGE_SELECTION,
    CHOOSE_PRINTER,
    CORRECT_INPUT,
    PLACE_ON_BED,
    REPAIR_AND_RETRY,
    SCALE_TO_FIT,
    SHOW_HISTORY,
    SHOW_LOCATIONS,
    SPLIT_MODEL,
    Action,
    AppError,
)
from app.core.log import get_logger
from app.core.registry import REGISTRY
from app.core.scene import EvaluationResult
from app.core.types import Document, Feature, Finding, ObjectId
from app.core.units import LengthUnit
from app.i18n import sort_key, tr
from app.ui.dialogs import handlers_of
from app.ui.icons import icon
from app.ui.labels import (
    NumberSpin,
    compact_length,
    feature_measure,
    feature_name,
    group_title,
    kind_requirement,
    length,
    localised,
    localised_value,
    spoiled_the_exact_body,
    value_line,
    volume,
)
from app.ui.overlay import LEFT_WIDTH
from app.ui.palette import SEVERITY_ENCODING, Role, text_colour
from app.ui.style import NORMAL, TIGHT, make_primary, set_level

_log = get_logger(__name__)

#: Zeichen je Schweregrad, aus der gemeinsamen Kodierung — Farbe steht nie
#: allein (§19.1).
SEVERITY_MARKER = {name: entry.symbol for name, entry in SEVERITY_ENCODING.items()}

#: Wie viele Operationen ein Kontextmenü flach zeigt, bevor es nach Kategorie
#: gruppiert. Dieselbe Zahl, die ``MAX_SUBMENU_ENTRIES`` in
#: ``tests/test_interface_limits.py`` der Menüleiste zieht, und aus demselben
#: Grund: darüber liest niemand mehr, er sucht.
MAX_MENU_ROWS = 12


def folded_groups(sizes: dict[str, int], limit: int = MAX_MENU_ROWS, fixed: int = 0) -> list[str]:
    """Welche Gruppen ein Untermenü bekommen, damit das Menü in die Grenze passt.

    Reine Rechnung über Namen und Anzahlen — **kein Qt**, und deshalb ohne ein
    einziges Fenster prüfbar. Das ist hier keine Stilfrage: Am 24.08.2026 wurde
    gemessen, dass jeder Test, der über die ``window``-Fixture ein
    ``MainWindow`` baut, die Abrissquote der **ganzen Testdatei** hebt (2 von 9
    auf 2 von 3). Eine Frage, die eine Funktion beantworten kann, bekommt kein
    Fenster.

    Gefaltet wird von der größten Gruppe abwärts und nur so weit, bis der Rest
    in die Grenze passt. Eine Gruppe mit einem einzigen Eintrag wird **nie**
    gefaltet: Ihr Untermenü spart keine Zeile und kostet einen Klick. Bleibt
    das Menü danach zu lang, bleibt es zu lang — ein Aufklappen, das nichts
    bündelt, macht es nicht kürzer, sondern nur tiefer.

    ``fixed`` sind Zeilen, die mitzählen, aber nie gefaltet werden können —
    im Bausteine-Untermenü die Einträge, die zu keinem Baustein der Bibliothek
    gehören und deshalb keine Gruppe haben.

    **Und die einzige Gruppe wird nie gefaltet**, gleich wie lang sie ist.
    Bliebe sonst ein Menü, das aus einem einzigen Untermenü besteht: ein Klick
    für alles, und die Zwischenebene hieße, wonach man ohnehin schon geklickt
    hat. Das ist dieselbe Ausnahme, die ``registry.surfaces.group_is_flat`` für
    die Menüleiste macht — dort wörtlich als „Bausteine → Bausteine → Deckel
    erzeugen" beschrieben. Sie stand hier zuerst nicht, obwohl der Text auf die
    Regel verwies: Eine zitierte Regel ist keine befolgte.
    """
    if len(sizes) < 2 and not fixed:
        return []
    rows = sum(sizes.values()) + fixed
    folded: list[str] = []
    for title in sorted(sizes, key=lambda name: (-sizes[name], name)):
        if rows <= limit or sizes[title] < 2:
            break
        folded.append(title)
        rows -= sizes[title] - 1
    return folded


#: In welcher Reihenfolge die Schweregrade stehen. Die Zeile über der Liste
#: zählt Fehler, Warnungen und Hinweise getrennt — sie verspricht damit eine
#: Rangfolge, und die Liste darunter hielt sie nicht: sie hängte an, wie es
#: kam, also stand bei zwei Warnungen und vier Hinweisen zuoberst ein Hinweis.
#: Wer einen Fehler suchte, musste ihn filtern statt lesen.
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _by_severity(findings: Iterable[Finding]) -> list[Finding]:
    """Schweres zuerst, sonst in der Reihenfolge, in der es entstanden ist.

    Stabil sortiert: innerhalb eines Grades bleibt die Kette der Operationen
    lesbar, und die erzählt, an welcher Stelle etwas schiefging.
    """
    return sorted(findings, key=lambda entry: SEVERITY_ORDER.get(entry.severity, 3))


#: Was gegen einen Befund hilft, je Befundkennung.
#:
#: **Ein Befund, der nur sagt, was nicht stimmt, ist die halbe Antwort.** §2.7
#: verlangt drei Teile — was nicht ging, warum, und was jetzt möglich ist —,
#: und der letzte fehlte hier ganz: Der Prüfbericht sagte „Das Objekt steht
#: über den Bauraum hinaus" und hörte auf. Dabei waren die Handlungen dazu
#: vollständig gebaut. Sie hingen an ``OutOfBuildVolume``, einer Ausnahme, die
#: **niemand wirft** — Bauraum ist ein Bericht und keine Sperre (§29), und
#: damit war der einzige Weg zu drei fertigen Vorschlägen zugemauert.
#:
#: Die Kennungen sind stabil (``Finding.code``), also ist diese Tabelle keine
#: Textsuche über Meldungen. Was hier fehlt, bekommt kein Menü — lieber keins
#: als eines, das nichts tut.
FINDING_ACTIONS: dict[str, tuple[Action, ...]] = {
    # Drei Antworten auf „passt nicht": kleiner machen, teilen — oder einen
    # anderen Drucker nehmen. Die dritte fehlte, solange ihr Handler fehlte,
    # und sie ist für den Kunden mit zwei Maschinen die naheliegendste.
    "arrange.out_of_build_volume": (SPLIT_MODEL, SCALE_TO_FIT, CHOOSE_PRINTER),
    # **Zu groß und nur verrutscht sind zwei Fälle.** Beide meldete der Kern
    # unter derselben Kennung, also bekam auch das Teil, das bloß zur Hälfte
    # unter der Platte steckt, *Modell teilen* und *Auf den Bauraum
    # verkleinern* angeboten — die beiden Handlungen, die hier nichts
    # ausrichten. Und es ist der häufigste Fall überhaupt: Ein
    # heruntergeladenes Modell ist um den Ursprung zentriert, und §17.1 setzt
    # es bewusst nicht von selbst auf (``place_on_bed`` steht auf „aus").
    # „Anbieten, nicht erzwingen" heißt dann aber, dass es hier auch angeboten
    # werden muss.
    "arrange.below_bed": (PLACE_ON_BED,),
    # **Beide Wege, und der zweite ist der, den Robert verlangt hat**
    # (24.08.2026): „bei an bett ausrichten sollten alle ans bett richtig
    # angeordnet werden wie fürs drucken." *Auf das Bett setzen* senkt diesen
    # einen Körper ab und lässt x und y, wie sie sind — das ist die genaue
    # Antwort auf ein Schweben. *Auf dem Bett anordnen* legt die ganze Szene
    # druckfertig, und das ist die Antwort, wenn mehr als einer in der Luft
    # hängt. Bei ``below_bed`` steht der zweite Knopf bewusst nicht: Ein Körper
    # unter der Platte ist der Normalfall eines frisch geladenen Modells, und
    # dort soll ein Klick genau das tun, was er sagt.
    "arrange.above_bed": (PLACE_ON_BED, ARRANGE_ON_BED),
    "arrange.off_the_plate": (ARRANGE_ON_BED,),
    # Derselbe Sachverhalt, nur eine Stufe später gemessen: nicht die Szene
    # ragt hinaus, sondern die **Druckdatei**, die der Slicer daraus gemacht
    # hat (``gcode.printed_extent``). CuraEngine prüft seinen Bauraum nicht.
    # Es hilft dasselbe wie oben — anordnen, und wenn es allein nicht passt,
    # verkleinern.
    "gcode.off_the_bed": (ARRANGE_ON_BED, SCALE_TO_FIT),
    "export.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    "ingest.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    # **Dritter Melder derselben Sache, und er stand ohne Menü da.** „Nicht
    # geschlossen" meldet der Kern an drei Stellen: beim Einlesen, beim
    # Exportieren und nach jedem Zug des Agenten (``agent.not_watertight``,
    # ``app/core/agent/checks.py``). Zwei trugen die beiden Handlungen, der
    # dritte nicht — wer über den Chat ein Objekt aufriss, bekam den Satz und
    # sonst nichts, obwohl beide Handler gebaut und verdrahtet sind.
    #
    # Er ist dabei der einzige der drei, der seine Objektkennung mitbringt:
    # ``_object_of`` muss hier nicht auf die Auswahl raten.
    "agent.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    # Die Rücknahme-Warnung des Agenten (Gesamtreview H-1): „nimmt auch alle
    # jüngeren mit" braucht den Blick in den Verlauf — dort stehen die
    # Transaktionen, um die es geht. Der Befund existierte im Kern, die
    # Oberfläche kannte ihn nicht.
    "agent.undo_sweeps": (SHOW_HISTORY,),
    # Vierter Melder derselben Sache: eine Netzoperation, die den Körper
    # aufgemacht hat (``mesh_ops._deviation_findings``). Gemessen beim
    # Vereinfachen einer Ente — geschlossen hinein, offen heraus, und im
    # Bericht stand nur, dass sich die Fläche kaum verschoben hat.
    "mesh.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    # **Drei Befunde über die Auswahl, und keiner hatte ein Menü.** Sie
    # tragen alle ihre Schrittkennung, und was hilft, ist dasselbe: andere
    # Objekte wählen. *Eingabe korrigieren* wäre hier nicht nur
    # unverdrahtet, sondern falsch — `field="in"` ist keine Zeile im
    # Formular, und der Dialog öffnete sich auf ein Feld, das es nicht gibt.
    "evaluate.missing_input": (CHANGE_SELECTION,),
    "evaluate.too_few_inputs": (CHANGE_SELECTION,),
    "evaluate.object_count": (CHANGE_SELECTION,),
}

#: Kennungen der Befunde, die aus einer Ausnahme einer Operation entstanden
#: sind (``evaluate._finding_from``): ``op.<operation>.<Ausnahmeklasse>``.
_FROM_AN_OPERATION: Final = "op."


def actions_for(finding: Finding) -> tuple[Action, ...]:
    """Was gegen diesen Befund hilft — aus der Tabelle oder aus seiner Herkunft.

    **Der häufigste Befund mit einer offensichtlichen Antwort hatte keine.**
    Eine Operation, deren Werte nicht gehen, wirft keinen Fehlerdialog: Der
    Kern macht daraus einen Befund und hält die Kette an (§15.3). Im Bericht
    stand dann „Der Wert liegt über dem zulässigen Höchstwert" — und der Weg
    zurück zu diesem Wert war, ihn im Verlauf selbst zu finden und
    doppelzuklicken. Das ist entdeckbar, aber es ist nicht der kurze Weg, den
    §2.7 verlangt: was jetzt möglich ist, als anklickbare Handlung.

    Diese Befunde tragen ihre Schrittkennung immer (`_finding_from` setzt sie),
    also gibt es genau einen Schritt zu öffnen, und ``edit_operation`` tut
    danach das Richtige: derselbe Dialog, dieselben Werte, und beim Übernehmen
    wird der Schritt **ersetzt** statt ein zweiter angelegt.

    Als Muster und nicht als Tabellenzeile, weil die Kennung den Namen der
    Operation und der Ausnahme enthält — das sind 86 mal n Zeilen, die alle
    dasselbe sagen würden.
    """
    known = FINDING_ACTIONS.get(finding.code)
    if known:
        return known
    if finding.code.startswith(_FROM_AN_OPERATION) and finding.op_id is not None:
        return (CORRECT_INPUT,)
    return ()


def as_error(finding: Finding) -> AppError:
    """Einen Befund so verpacken, dass die Fehlerhandlungen ihn annehmen.

    Die Handler des Fensters (``error_handlers``) arbeiten auf einem
    ``AppError``, weil sie aus dem Fehlerdialog kommen. Ein Befund ist keiner
    — er trägt aber genau die zwei Angaben, die sie lesen: den Körper und die
    Zahlen. Sie zweimal zu schreiben, einmal für Fehler und einmal für
    Befunde, hieße zwei Wahrheiten über dieselbe Handlung.
    """
    return AppError(
        title=finding.message,
        object_id=finding.object_id,
        op_id=finding.op_id,
        values=dict(finding.values),
    )


#: Farbe der zurückgenommenen Schritte im Verlauf — dieselbe wie für einen
#: verworfenen Chatbeitrag, und aus demselben Grund.
UNDONE_COLOUR = "#7a828c"


def _severity_label(severity: str) -> str:
    """Der Schweregrad als Wort — die Filterzeile zeigt beides (Regel 18)."""
    return {
        "error": tr("Fehler"),
        "warning": tr("Warnung"),
        "info": tr("Hinweis"),
    }.get(severity, severity)


def origin_label(source: str) -> str:
    """Hier geschätzt oder aus G-Code gemessen — nie verwechselt (§22.5)."""
    return tr("intern geschätzt") if source == "internal" else tr("aus G-Code")


#: Werte, die in der Zeile eines Befunds stehen — die, nach denen man beim
#: Lesen zuerst fragt: welcher Körper, und wie viel.
#:
#: Der Wert dahinter ist die Einheit, die dazugehört, oder ``""`` für Zahlen,
#: die für sich stehen. Sie steht **hier** und nicht im Kern: dort ist eine
#: Zahl ein Wert, und wie sie geschrieben wird, entscheidet die Anzeige —
#: dieselbe Trennung wie zwischen ``format_length`` und ``length``.
_LINE_VALUES: dict[str, str] = {
    "object": "",
    # „Ein Merkmal hat keinen Nachfolger mehr" — welches? Nach dem Einsetzen
    # eines Bausteins standen sechs wortgleiche Zeilen im Bericht, und nichts
    # daran war unterscheidbar; die Kennung stand längst im Befund, nur nie in
    # der Zeile. Derselbe Fund wie bei den zwei ausgehöhlten Klötzen darunter,
    # gefunden am 25.08.2026 bei der Verifikation im echten Fenster.
    "feature": "",
    "a": "",
    "b": "",
    "excess": "",
    "shared": "",
    # Aushöhlen sagte „Die Wandstärke stimmt im Rahmen des Rasters", ohne die
    # Wandstärke zu nennen — und wie viel Material dabei gespart wurde, also
    # die Frage, für die man die Operation überhaupt aufruft, stand nur im
    # Tooltip.
    "wall_mm": "mm",
    "removed_cm3": "cm³",
}


def _op_title(name: str) -> str:
    """Der Titel einer Operation, wie das Menü ihn zeigt.

    Der Verlauf schrieb den Registernamen: zwischen „Grundkörper" und
    „Versteifung" stand `insert_screw_hole`. Beides sind dieselben Schritte,
    nur kommt der eine Text aus der Transaktion und der andere aus dem Code.

    Eine Operation, die das Register nicht kennt, behält ihren Namen — eine
    Projektdatei aus einer neueren Version ist kein Grund, eine Zeile leer zu
    lassen.
    """
    try:
        return str(REGISTRY.get(name).title)
    except AppError:
        return name


def _identity(finding: Finding) -> tuple[Any, ...]:
    """Woran zwei Befunde derselbe sind.

    Der Code allein reicht nicht — zwei Körper stehen aus verschiedenen Gründen
    über den Bauraum hinaus, und das sind zwei Zeilen. Die Werte gehören dazu:
    ändert sich die Zahl, ist es eine neue Aussage über dieselbe Sache.
    """
    return (
        finding.code,
        finding.object_id,
        str(finding.message),
        tuple(sorted((key, str(value)) for key, value in finding.values.items())),
    )


def _line_for(finding: Finding, names: Mapping[str, str] | None = None) -> str:
    """Die Zeile eines Befunds: die Meldung und wovon sie handelt.

    „Zwei Objekte überschneiden sich" — welche zwei? „Ein Objekt steht über den
    Bauraum hinaus" — welches, und um wie viel? Die Antworten standen schon in
    ``values``, aber nur im Tooltip: man musste wissen, dass dort etwas ist, und
    mit der Maus hinfahren. Jetzt stehen sie in der Zeile.

    Nur die fünf Felder, nach denen man beim Lesen zuerst fragt. Alle wären
    wieder ein Tooltip, nur breiter — und der bleibt ohnehin daneben stehen.

    Dazu ``object_id``, wenn der Befund eines trägt und es nicht ohnehin unter
    den Werten steht. Das ist der Fall, den die Liste bis hierher nicht sah:
    ein Befund je Körper, zweimal derselbe Satz, und nichts daran
    unterscheidbar — zwei ausgehöhlte Klötze meldeten „Ausgehöhlt. Die
    Wandstärke stimmt im Rahmen des Rasters." als zwei Zeilen, die aussahen wie
    ein Fehler in der Anwendung.

    ``names`` löst die Kennung zum Namen auf. Ohne die Zuordnung bleibt die
    Kennung stehen: „obj_2" ist weniger als „Klotz B", aber mehr als nichts.
    """
    extra = [
        # Über ``localised_value``: Ein Befund trägt neben Zahlen auch Pfade,
        # Adressen und Endungen, und ``localised`` tauschte dort jeden Punkt
        # gegen ein Komma — „sources/1_cube_clean,stl".
        #
        # Die Merkmalskennung bekommt ihr Wort davor: Neben dem aufgelösten
        # Objektnamen läse sich ein nacktes „face_3" wie ein zweiter Name —
        # und der eigene Maßstab des Fensters sagt, dass eine Kennung allein
        # niemandem sagt, welche Fläche gemeint ist.
        (
            f"{tr('Merkmal')} {finding.values[key]}"
            if key == "feature"
            else f"{localised_value(finding.values[key])} {unit}".strip()
        )
        for key, unit in _LINE_VALUES.items()
        if key in finding.values
    ]
    if finding.object_id and "object" not in finding.values:
        identifier = str(finding.object_id)
        extra.insert(0, (names or {}).get(identifier, identifier))
    if not extra:
        return str(finding.message)
    return f"{finding.message} — {' · '.join(extra)}"


def _origin_text(created_by: int | None, document: Document | None) -> str:
    """Aus welcher Operation und Transaktion ein Körper stammt (§18.8).

    Die Transaktion ist die Einheit, die der Verlauf zeigt und die ein Undo
    nimmt (§15.5) — sie zu nennen verbindet den Körper im Baum mit der Zeile
    im Verlauf. Fehlt das Dokument, bleibt die Operationsnummer.
    """
    if created_by is None:
        return ""
    text = f"{tr('aus Operation')} {created_by}"
    if document is None:
        return text
    for transaction in document.transactions:
        if created_by in transaction.ops:
            return f"{text} · {transaction.title}"
    return text


def _empty_objects_text() -> str:
    """Was in der leeren Objektliste steht.

    Sie war ein stummer Kasten. Ein neues Projekt beginnt genau hier, und wer
    zum ersten Mal davorsitzt, sieht drei leere Flächen und keinen Anfang —
    die Parameterleiste daneben sagt seit jeher, wozu sie da ist.
    """
    return tr(
        "Noch keine Objekte. Über „Erzeugen“ entsteht ein Körper, "
        "„Modell einfügen“ liest eine Datei ein."
    )


def _empty_history_text() -> str:
    """Was im leeren Verlauf steht — und wozu er gut ist."""
    return tr(
        "Noch keine Schritte. Jede Änderung steht hier als eine Zeile "
        "und lässt sich mit Strg+Z zurücknehmen."
    )


class ObjectTree(QWidget):
    """Objekte der Szene mit ihren Merkmalen, Herkunft und Größe (§18.8,
    §18.5).
    """

    selectionChanged = Signal(object)
    featureSelected = Signal(object)
    """Ein im Baum gewähltes Merkmal — trägt seine ID, oder None."""
    operationRequested = Signal(object)
    """Eine aus dem Kontextmenü gewählte Operation — trägt ihre ``OperationSpec``."""
    visibilityRequested = Signal(object, bool)
    """Ein- oder ausblenden (§18.8) — trägt die Kennungen und den Wunsch."""
    isolateRequested = Signal(object)
    """Nur diese zeigen — trägt die Kennungen. Ein zweiter Aufruf hebt es auf."""
    stepRequested = Signal(int)
    """Den Schritt öffnen, der das gewählte Merkmal erzeugt hat (§21.2) —
    trägt seine Kennung."""
    sketchOnFaceRequested = Signal(str)
    """Auf dieser planaren Fläche zeichnen (§30.1) — trägt die Merkmalskennung.

    Der Empfänger baut daraus die Ebene ``feature:<id>``; der Baum kennt den
    Skizzenmodus nicht und soll ihn nicht kennen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tree = QTreeWidget(self)
        self.tree.setAccessibleName(tr("Objekte"))
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([tr("Objekt"), tr("Maße")])
        # Die Maßspalte nimmt, was sie braucht; der Rest gehört den Namen.
        # Vorher standen beide auf derselben festen Breite, und auf dreifache
        # Fensterbreite gezogen blieb die Maßspalte schmal, während links
        # jeder Merkmalsname abgeschnitten war.
        header = self.tree.header()
        # **Der Satz darüber galt nicht.** ``stretchLastSection`` steht auf Qts
        # Vorgabe ``True`` und überstimmt das ``ResizeToContents`` der letzten
        # Spalte: gemessen standen beide auf genau der Hälfte, 128 zu 128 bei
        # 258 Pixeln Baumbreite. Nach Abzug von Einzug und Vorschaubild blieb
        # für den Namen so wenig, dass „Gehäuseboden" und „Gehäuseboden (Kopie)
        # Prüfstück" — die zwei Körper des ersten Beispielprojekts — als
        # dieselbe abgeschnittene Zeichenkette dastanden.
        #
        # Den Deckel nur abzuschalten kippt es aber bloß um: dann nimmt die
        # Maßspalte, was ihr Inhalt braucht, und bei „60 x 40 x 12 mm" waren das
        # 186 von 258 Pixeln — 70 für den Namen, schlechter als vorher. Beide
        # Spalten wollen Platz, und die Frage ist nicht, wer ihn bekommt,
        # sondern in welchem Verhältnis. Die Maßspalte bekommt, was sie braucht,
        # und höchstens :data:`MEASURE_SHARE`; der Rest gehört dem Namen. Gesetzt
        # wird in ``_size_columns``, denn beides ändert sich: der Inhalt und die
        # Breite.
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        # §25: Vereinigen, Abziehen und Schnittmenge nehmen zwei Körper. Mit
        # Einfachauswahl war keine davon über das Menü ausführbar — die
        # Operation bekam einen Eingang, wo sie zwei erwartet, und lehnte ab.
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setRootIsDecorated(True)
        # Ohne das zeichnet Qt jedes Symbol auf Textgröße herunter, und das
        # gerenderte Vorschaubild wäre umsonst gerechnet.
        self.tree.setIconSize(QSize(_preview_pixels(self.tree), _preview_pixels(self.tree)))
        self._order: list[ObjectId] = []
        """Die Reihenfolge, in der angeklickt wurde. „A minus B" ist nicht „B
        minus A", und die Reihenfolge im Baum weiß davon nichts."""
        self._hidden: frozenset[ObjectId] = frozenset()
        self._unit: LengthUnit = "mm"
        self._room: int | None = None
        """Die Höhe, die diese Karte haben darf — von der Überlagerung
        zugeteilt (§2.5). ``None`` heißt: noch niemand hat es gesagt."""
        self._result: EvaluationResult | None = None
        self._document: Document | None = None
        self._theme: DrawingTheme = "dark"
        """Für welches Thema die Vorschaubilder gezeichnet werden."""
        self._previews: dict[str, QIcon] = {}
        """Gerenderte Vorschaubilder, nach dem Hash des Objekts.

        Nach dem Hash und nicht nach der Kennung: „obj_1" bleibt dasselbe
        Objekt, wenn sich seine Wandstärke ändert — sein Bild nicht. Der Hash
        steht ohnehin im Ergebnis, weil der Stapel ihn zum Zwischenspeichern
        braucht."""
        self._pending: list[tuple[QTreeWidgetItem, str, Any]] = []
        """Was noch gezeichnet werden muss. Erst nach dem Aufbau, sonst steht
        der Baum still, während das erste Bild entsteht — und bei einem
        gescannten Teil sind das achtzig Millisekunden je Zeile."""
        """Das Zuletzt-Gezeigte, damit sich der Baum ohne neue Auswertung
        neu zeichnen kann — beim Ausblenden ändert sich nur die Anzeige."""
        self.tree.itemSelectionChanged.connect(self._on_selection)
        # Wer einen Körper aufklappt, will seine Merkmale sehen und nicht in
        # einem Feld von zwei Zeilen danach scrollen.
        self.tree.itemExpanded.connect(self._fit)
        self.tree.itemCollapsed.connect(self._fit)
        self.tree.setAcceptDrops(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)

        # Der leere Zustand liegt über dem Baum, nicht darin: eine Zeile im
        # Baum wäre auswählbar, hätte eine Spalte „Maße" und sähe aus wie ein
        # Objekt namens „Noch keine Objekte".
        self._empty = QLabel(_empty_objects_text(), self)
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._empty.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        fit_wrapped(self._empty)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._empty)
        layout.addWidget(self.tree)

    def set_hidden(self, hidden: frozenset[ObjectId]) -> None:
        """Welche Körper gerade nicht gezeichnet werden — nur zum Anzeigen."""
        if hidden == self._hidden:
            return
        self._hidden = hidden
        self.show_scene(self._result, self._document)

    def set_unit(self, unit: LengthUnit) -> None:
        """§19.3: Millimeter oder Zoll in der Maße-Spalte."""
        if unit == self._unit:
            return
        self._unit = unit
        self.show_scene(self._result, self._document)

    def set_theme(self, theme: str) -> None:
        """Ein anderes Thema heißt andere Vorschaubilder.

        Der Vorrat wird geleert und nicht umgefärbt: Die Bilder sind SVG mit
        eingebackenen Farben, und ein helles Teil auf hellem Grund ist kein
        Bild mehr.
        """
        if theme == self._theme:
            return
        self._theme = "light" if theme == "light" else "dark"
        self._previews.clear()
        self.show_scene(self._result, self._document)

    def _want_preview(self, item: QTreeWidgetItem, object_id: ObjectId, entry: Any) -> None:
        """Merkt vor, dass diese Zeile ein Bild bekommen soll.

        Steht es schon im Vorrat, kommt es sofort — dann hat sich am Körper
        nichts geändert, und Rendern hieße dasselbe Bild zweimal zeichnen.
        """
        stamp = self._stamp(object_id, entry)
        ready = self._previews.get(stamp)
        if ready is not None:
            item.setIcon(0, ready)
            return
        self._pending.append((item, stamp, entry))

    def _stamp(self, object_id: ObjectId, entry: Any) -> str:
        """Woran ein Bild hängt: am Hash des Körpers, nicht an seiner Kennung.

        Fehlt der Hash — bei einer Szene, die nie durch den Stapel lief —,
        tut es die Dreieckszahl mit der Kennung. Sie ist gröber und würde eine
        Formänderung bei gleicher Zahl übersehen; das ist hier verkraftbar,
        weil es um ein Bild von zwanzig Pixeln geht.
        """
        hashes = self._result.object_hashes if self._result else {}
        known = hashes.get(object_id)
        return str(known) if known else f"{object_id}:{entry.mesh.triangle_count}"

    def _render_pending(self) -> None:
        """Zeichnet die vorgemerkten Bilder — eines je Aufruf.

        Eines und nicht alle: Bei einem gescannten Teil kostet ein Bild achtzig
        Millisekunden, und fünf davon am Stück sind eine halbe Sekunde, in der
        das Fenster steht. So kommt jedes Bild einzeln nach, und dazwischen
        bleibt die Anwendung bedienbar — dasselbe Verfahren wie im Katalog.
        """
        if not self._pending:
            return
        item, stamp, entry = self._pending.pop(0)
        try:
            image = drawing.thumbnail(
                entry.mesh.raw,
                _preview_pixels(self.tree),
                theme=self._theme,
            )
        except Exception as problem:  # pragma: no cover - hängt am Netz
            # Ein Vorschaubild ist Beiwerk. Scheitert es, bleibt die Zeile, wie
            # sie war — eine Ansicht, die wegen eines Bildes nicht aufgeht,
            # wäre der teuerste mögliche Umgang mit einer Nebensache.
            _log.info("no preview for %s: %s", stamp, problem)
        else:
            found = _svg_icon(image, _preview_pixels(self.tree))
            self._previews[stamp] = found
            # Die Zeile kann inzwischen weg sein — eine neue Auswertung räumt
            # den Baum, während hier noch gezeichnet wird.
            if self.tree.indexFromItem(item).isValid():
                item.setIcon(0, found)
        if self._pending:
            QTimer.singleShot(0, self, self._render_pending)

    def show_scene(self, result: EvaluationResult | None, document: Document | None = None) -> None:
        selected = self.selected_objects()
        selected_feature = self.selected_feature()
        self._result = result
        self._document = document
        self.tree.clear()
        # Was noch nicht gezeichnet war, gehört zu Zeilen, die es nicht mehr
        # gibt. Der Vorrat bleibt: dieselben Körper kommen meist wieder.
        self._pending.clear()
        if result is None:
            return
        for object_id, entry in result.scene.objects.items():
            size = entry.mesh.bounds.size
            # §19.3: die Einheit stand hier fest, obwohl sie eine Einstellung
            # ist. Umgerechnet wird nur für die Anzeige — im Netz bleibt jede
            # Zahl ein Millimeter.
            # Kompakt, weil die Spalte eng ist: mit fester Stellenzahl brauchte
            # sie dreihundert Pixel und bekam zweihundertsechzig, seit die Zonen
            # über der Ansicht liegen. Die Nullen standen dort, weil die
            # Formatierung sie vorsieht — nicht weil jemand sie gemessen hätte.
            # Krumme Maße behalten ihre Stellen.
            measures = " × ".join(compact_length(value, self._unit) for value in size)
            item = QTreeWidgetItem([str(entry.name), f"{measures} {self._unit}"])
            item.setData(0, Qt.ItemDataRole.UserRole, object_id)
            state = tr("geschlossen") if entry.mesh.is_watertight else tr("offen")
            # §30: welche Sorte Körper das ist, gehört in den Baum, denn sie
            # entscheidet, was sich noch mit ihm tun lässt — und der Weg von
            # B-Rep zu Mesh ist eine Einbahnstraße.
            kind = tr("exakt") if entry.kind == "brep" else tr("Netz")
            tip = f"{object_id} · {kind} · {entry.mesh.triangle_count} {tr('Dreiecke')} · {state}"
            if entry.material:
                tip += f" · {entry.material}"
            # §18.8: woher der Körper kommt. Ohne das ist ein Baum mit sieben
            # Teilen aus einer Teilung eine Liste ohne Vorgeschichte — und die
            # Frage „welcher Schritt hat das gemacht" nur durch Ausprobieren zu
            # beantworten.
            origin = _origin_text(entry.created_by, document)
            if origin:
                tip += f" · {origin}"
            item.setToolTip(0, tip)
            if entry.kind == "brep":
                item.setText(0, f"{entry.name}  ·  {kind}")
            if object_id in self._hidden:
                # Zeichen und Wort: eine ausgegraute Zeile allein wäre Farbe als
                # einzige Kodierung (Regel 18).
                item.setIcon(0, icon("hidden", self.tree))
                item.setText(0, f"{item.text(0)}  ·  {tr('ausgeblendet')}")
            else:
                # Ein Vorschaubild statt eines Aufzählungszeichens: „Dose" und
                # „Dose Deckel" sind zwei Zeilen Text, die man liest — zwei
                # Bilder erkennt man. Das ausgeblendete Objekt behält sein
                # eigenes Zeichen; es hat gerade nichts zu zeigen.
                self._want_preview(item, object_id, entry)
            if entry.material:
                # §12: ein Körper, der nicht im Material des Projekts ist, muss das
                # dort sagen, wo die Teile aufgezählt werden — sonst zeigt sich
                # der Unterschied nur an einer Passung, die auf einmal ein
                # anderes Spiel will.
                item.setText(1, f"{item.text(1)}  ·  {entry.material}")
            for feature_id, feature in entry.features.items():
                # Name links, Maß rechts. Vorher stand die ganze Beschriftung
                # links und rechts der Typ („hole", „face") — links war damit
                # abgeschnitten, was rechts gefehlt hat.
                child = QTreeWidgetItem(
                    [feature_name(feature_id, feature), feature_measure(feature)]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, object_id)
                child.setData(1, Qt.ItemDataRole.UserRole, feature_id)
                child.setToolTip(0, f"{feature_id} · {feature.provenance}")
                item.addChild(child)
            self.tree.addTopLevelItem(item)
            item.setExpanded(object_id in selected)
        self.tree.resizeColumnToContents(0)
        self._restore(selected, selected_feature)
        self._fit()
        # Erst steht der Baum, dann kommen die Bilder nach. Andersherum wartet
        # der Nutzer auf eine Liste, die längst fertig gerechnet ist.
        if self._pending:
            QTimer.singleShot(0, self, self._render_pending)

    def _rows(self) -> int:
        """Die sichtbaren Zeilen — ein zugeklappter Ast zählt als eine."""
        rows = 0
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is None:
                continue
            rows += 1 + (item.childCount() if item.isExpanded() else 0)
        return rows

    def wanted_height(self) -> int:
        """Die Höhe, bei der jede Zeile zu sehen wäre."""
        return view_chrome(self.tree) + self._rows() * row_height_of(self.tree)

    def least_height(self) -> int:
        """Und die, unter die diese Karte nicht geht (siehe ``fit_to_rows``)."""
        if self.tree.topLevelItemCount() == 0:
            return least_empty_height(self._empty)
        return least_height_of(self.tree)

    def set_room(self, pixels: int) -> None:
        """Wie hoch diese Karte werden darf (siehe ``fit_to_rows``)."""
        if pixels == self._room:
            return
        self._room = pixels
        self._fit()

    def _size_columns(self) -> None:
        """Die Maßspalte so breit wie ihr Inhalt, höchstens ein Teil des Ganzen.

        Aufgerufen, wenn sich der Inhalt ändert und wenn sich die Breite ändert
        — an beidem hängt das Ergebnis. Ohne Breite (vor dem ersten Legen) gibt
        es nichts zu teilen.
        """
        width = self.tree.viewport().width()
        if width <= 0:
            return
        needed = self.tree.sizeHintForColumn(1)
        self.tree.header().resizeSection(1, max(0, min(needed, int(width * MEASURE_SHARE))))

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Beim Breiterwerden neu teilen."""
        super().resizeEvent(event)
        self._size_columns()

    def _fit(self) -> None:
        """So hoch wie der Inhalt — aufgeklappte Merkmale zählen mit.

        Die zweite Zeile ist die entscheidende: ``fit_to_rows`` bemisst den
        Baum, nicht die Karte um ihn herum. Ohne sie meldete die Karte ihre
        nackte Mindesthöhe, und die Spalte drückte sie auf elf Pixel — ein
        leerer Rahmen über einem angeschnittenen Wort, während der Baum
        darunter seine hundert Pixel für sich behielt und nichts davon zu
        sehen war.
        """
        # Der leere Zustand tritt an die Stelle des Baums, nicht daneben: Ein
        # Satz über einem leeren Rahmen sähe aus, als fehlte darunter etwas.
        empty = self.tree.topLevelItemCount() == 0
        self._empty.setVisible(empty)
        self.tree.setVisible(not empty)
        fit_to_rows(self.tree, self._rows(), room=self._room)
        self._size_columns()
        self.setMinimumHeight(self.sizeHint().height())
        self.updateGeometry()

    def _restore(self, objects: Sequence[ObjectId], feature_id: str | None) -> None:
        """Behält die Auswahl über eine Neuauswertung hinweg — sie zu verlieren
        kostet den Nutzer die Stelle, an der er gearbeitet hat.

        Das Merkmal gilt nur, wenn genau ein Körper gewählt war; bei mehreren
        gibt es keines, auf das es sich beziehen könnte.
        """
        if not objects:
            # Ohne Auswahl bekommt die erste Zeile wenigstens die Marke des
            # aktuellen Eintrags — gewählt ist damit nichts, aber die Tastatur
            # hat einen Anfang. Ohne sie stand ``currentItem()`` auf nichts,
            # und wer per Tabulator in den Baum kam, bewegte mit den
            # Pfeiltasten gar nichts.
            first = self.tree.topLevelItem(0)
            if first is not None and self.tree.currentItem() is None:
                self.tree.setCurrentItem(first)
                first.setSelected(False)
            return
        wanted = set(objects)
        self._order = list(objects)
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is None or item.data(0, Qt.ItemDataRole.UserRole) not in wanted:
                continue
            if feature_id is not None and len(wanted) == 1:
                for child_index in range(item.childCount()):
                    child = item.child(child_index)
                    if child is not None and child.data(1, Qt.ItemDataRole.UserRole) == feature_id:
                        child.setSelected(True)
                        break
                else:
                    item.setSelected(True)
                continue
            item.setSelected(True)

    def selected(self) -> ObjectId | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        value: ObjectId | None = items[0].data(0, Qt.ItemDataRole.UserRole)
        return value

    def selected_objects(self) -> tuple[ObjectId, ...]:
        """Die gewählten Körper in der Reihenfolge, in der sie angeklickt
        wurden.

        Ein angeklicktes Merkmal zählt für seinen Körper: wer eine Bohrung
        markiert und dann etwas mit dem Teil tut, meint das Teil.
        """
        chosen = {
            object_id
            for item in self.tree.selectedItems()
            if (object_id := item.data(0, Qt.ItemDataRole.UserRole)) is not None
        }
        ordered = [object_id for object_id in self._order if object_id in chosen]
        ordered.extend(sorted(chosen.difference(ordered)))
        return tuple(ordered)

    def selected_feature(self) -> str | None:
        items = self.tree.selectedItems()
        if len(items) != 1:
            # Bei mehreren Zeilen ist „das gewählte Merkmal" keine Frage mit
            # einer Antwort — dann gilt keines als gewählt.
            return None
        value: str | None = items[0].data(1, Qt.ItemDataRole.UserRole)
        return value

    def step_selection(self, forward: bool = True) -> None:
        """Zum nächsten Körper weiterschalten (§19.2).

        Reihum: hinter dem letzten kommt wieder der erste. Ohne den Umlauf
        endet das Durchblättern am Rand, und wer einen Körper sucht, muss
        wissen, in welche Richtung er liegt.
        """
        count = self.tree.topLevelItemCount()
        if not count:
            return
        chosen = self.selected_objects()
        current = -1
        if chosen:
            for index in range(count):
                item = self.tree.topLevelItem(index)
                if item is not None and item.data(0, Qt.ItemDataRole.UserRole) == chosen[0]:
                    current = index
                    break
        target = self.tree.topLevelItem((current + (1 if forward else -1)) % count)
        if target is not None:
            self.tree.setCurrentItem(target)
            self.tree.scrollToItem(target)

    def select_object(self, object_id: ObjectId | None) -> None:
        """Wählt einen Körper von außen aus — der Fehlerdialog tut das, wenn er
        zeigt, worum es ging, und ein Klick in der Ansicht ebenso.

        ``None`` hebt die Auswahl auf: wer neben das Modell klickt, will sie
        loswerden.
        """
        self.tree.clearSelection()
        if object_id is not None:
            self._restore((object_id,), None)

    def select_feature(self, object_id: ObjectId, feature_id: str) -> None:
        """Folgt einem Klick im Viewport — die zwei Ansichten zeigen eine
        Auswahl (§18.5).
        """
        self.tree.clearSelection()
        self._restore((object_id,), feature_id)

    def _on_selection(self) -> None:
        self._remember_order()
        self.selectionChanged.emit(self.selected())
        self.featureSelected.emit(self.selected_feature())

    def _remember_order(self) -> None:
        """Führt mit, in welcher Reihenfolge angeklickt wurde.

        Qt gibt die Auswahl in Baumreihenfolge zurück, und die sagt nichts
        darüber, was zuerst gemeint war. Abgewähltes fällt heraus, Neues kommt
        hinten dazu.
        """
        current = {
            object_id
            for item in self.tree.selectedItems()
            if (object_id := item.data(0, Qt.ItemDataRole.UserRole)) is not None
        }
        self._order = [object_id for object_id in self._order if object_id in current]
        self._order.extend(sorted(current.difference(self._order)))

    def operations_for_object(self) -> tuple[Any, ...]:
        """Operationen, die auf einem gewählten Objekt arbeiten — der kürzeste
        Weg vom Sehen zum Tun (§2.6).

        Angeboten werden alle, auch die, die auf dieser Bauart nicht können:
        Ausgegraut mit Grund steht sie da und sagt, was ihr fehlt — verschwunden
        ließe sie den Nutzer suchen, wo nichts fehlt (dieselbe Entscheidung wie
        in der Menüleiste). Welche das sind, entscheidet
        :meth:`kinds_of_selection` beim Bauen des Menüs.
        """
        # Nach Titel sortiert, wie die Menüleiste: ``REGISTRY.all()`` liefert
        # nach dem internen englischen Namen, und im Kontextmenü stand damit
        # „An Merkmal ausrichten" vor „Textur aufbringen" vor „Auf dem Bett
        # anordnen". Sortiert wird mit ``sort_key`` wie dort, sonst rutscht
        # „Überhangfächer" hinter das letzte Z — „Ü" steht im Zeichensatz
        # hinter „z".
        return tuple(
            sorted(
                (spec for spec in REGISTRY.all() if spec.consumes == 1),
                key=lambda spec: sort_key(spec.title),
            )
        )

    def kinds_of_selection(self) -> list[str]:
        """Die Bauart jedes gewählten Körpers — Netz oder exakt.

        Hier und nicht im Fenster: Der Baum hält die Auswahl **und** die
        Auswertung, und beide Menüs — die Leiste oben und das Kontextmenü hier —
        brauchen dieselbe Antwort. Vorher stand die Rechnung im Fenster, und das
        Kontextmenü fragte niemanden.
        """
        if self._result is None:
            return []
        objects = self._result.scene.objects
        return [objects[entry].kind for entry in self.selected_objects() if entry in objects]

    def operations_for_feature(self, kind: str) -> tuple[Any, ...]:
        """Was eine Bohrung oder eine Fläche anbietet, direkt aus ``applies_to``
        (§10, §18.5).
        """
        return REGISTRY.for_feature(kind)

    def _feature_kind(self) -> str | None:
        """Die Art des gewählten Merkmals — ``hole``, ``face``, ``edge``.

        Gelesen wurde sie aus der zweiten Spalte des Baums, und dort steht das
        Maß: „Ø3,22 mm" für eine Bohrung, „4334 mm²" für eine Fläche. Als Art
        an ``for_feature`` gereicht, fand die Anfrage nie eine Operation, und
        das Kontextmenü an einem Merkmal bestand aus Ausblenden und Alles
        andere ausblenden — an genau dem Ort, den §18.5 „die wichtigste
        Einzelfunktion" nennt.
        """
        feature = self._chosen_feature()
        return feature.kind if feature is not None else None

    def _chosen_feature(self) -> Feature | None:
        """Das gewählte Merkmal selbst, oder nichts.

        Zwei Fragen hängen daran, und beide brauchen dasselbe Objekt: was es
        anbietet (``kind``) und aus welchem Schritt es stammt
        (``created_by``).
        """
        feature_id = self.selected_feature()
        object_id = self.selected()
        if feature_id is None or object_id is None or self._result is None:
            return None
        entry = self._result.scene.objects.get(object_id)
        return entry.features.get(feature_id) if entry is not None else None

    def isolation_holds(self, chosen: tuple[str, ...]) -> bool:
        """Ob genau diese Auswahl gerade isoliert ist — alles andere versteckt.

        Eine Antwort für Beschriftung **und** Wirkung: Vorher lasen beide
        dasselbe Feld mit verschiedener Frage, und der Rechtsklick auf einen
        ausgeblendeten Körper versprach „Alles andere ausblenden" und blendete
        alles ein (Gesamtreview I-6).
        """
        if not self._hidden:
            return False
        everything = {
            item.data(0, Qt.ItemDataRole.UserRole)
            for index in range(self.tree.topLevelItemCount())
            if (item := self.tree.topLevelItem(index)) is not None
        }
        return self._hidden == frozenset(everything - set(chosen))

    def context_menu(self) -> QMenu | None:
        """Das Menü zur aktuellen Auswahl, oder nichts.

        Gebaut wird es hier und nicht dort, wo es aufgeht: der Viewport zeigt
        dasselbe Menü, wenn jemand mit rechts auf einen Körper klickt. §18.5
        nennt das Kontextmenü am Merkmal den Ort für Weg 1 — zwei Menüs mit
        derselben Aufgabe wären zwei Gelegenheiten, auseinanderzulaufen.
        """
        chosen = self.selected_objects()
        if not chosen:
            return None

        menu = QMenu(self)
        # **Ohne diese Zeile schreibt das Menü seine Gründe ins Leere.** ``QMenu``
        # zeigt Tooltips von Haus aus nicht an; ``_add_operation`` setzt an jeder
        # gesperrten Operation den Satz, der sagt, was ihr fehlt, und Qt warf ihn
        # weg. Die Menüleiste setzt es an ihren drei Stellen seit je — hier stand
        # die ganze Kette da und war unsichtbar.
        menu.setToolTipsVisible(True)
        self._add_source_step(menu)
        # Vor der Sichtbarkeit und aus demselben Grund wie der Schritt darüber:
        # Er gilt der **Fläche**, die Sichtbarkeit dem Körper. Wer mit rechts
        # auf eine Deckfläche zeigt, meint die Deckfläche (§18.5).
        self._add_sketch_on_face(menu)
        self._add_visibility(menu, chosen)

        kind = self._feature_kind()
        entries = self.operations_for_feature(kind) if kind else ()
        if not entries:
            # **Wer genauer gezeigt hat, bekommt nicht weniger.** Zu einer
            # Merkmalsart ohne eigene Operationen bestand das Menü aus
            # Ausblenden — weniger als bei einem Klick auf den Körper daneben,
            # und der Körper *ist* mitgewählt. Beim Gewinde eines Bausteins
            # (``thread``) ist das heute der Fall. Dieselbe Überlegung, aus der
            # ``applies_to`` in der Befehlspalette eine Reihenfolge ist und
            # keine Auswahl: Was zum Merkmal passt, steht vorn — was nicht dazu
            # passt, verschwindet deswegen nicht.
            entries = self.operations_for_object()
        if entries:
            menu.addSeparator()
            self._add_operations(menu, entries, self.kinds_of_selection())
        return menu

    def _add_operations(
        self, menu: QMenu, entries: Sequence[Any], kinds: Sequence[str] = ()
    ) -> None:
        """Die Operationen ins Menü — flach, solange man sie überblickt.

        An einem Merkmal sind es eine Handvoll, und die stehen direkt da: der
        kurze Weg vom Sehen zum Tun (§2.6) verträgt kein Aufklappen. An einem
        ganzen Körper sind es siebenundfünfzig, und eine Liste dieser Länge ist
        kein Menü mehr, sondern ein Register ohne Suchfeld — dieselbe Grenze,
        die `tests/test_interface_limits.py` für die Menüleiste zieht.

        Gruppiert wird dann nach derselben Kategorie, nach der auch die
        Menüleiste gruppiert. Beides kommt aus dem Register, kann also nicht
        auseinanderlaufen.

        **Und gruppiert wird nur, soweit es die Länge verlangt.** Hier stand
        „über zwölf Zeilen: alles in Untermenüs", und das kostet an einem
        Merkmal mehr, als es einbringt. Gemessen am Flächenklick, 19
        Operationen in vier Gruppen:

            10  Bausteine
             5  Ändern
             2  Erzeugen
             2  Vorbereiten

        Vorher wurden daraus vier Untermenüs, und damit brauchte **jede**
        Operation zwei Klicks — auch die Bohrung, die mit einer zweiten Zeile
        allein in „Erzeugen" lag. Eine Gruppe aus zwei Einträgen zu falten
        spart eine Zeile und kostet für beide einen Klick; das ist ein
        schlechtes Geschäft.

        Untermenüs bekommen deshalb nur die **größten** Gruppen, und nur so
        viele, bis der Rest in die Zeilengrenze passt. Am Flächenklick ist das
        genau eine: „Bausteine" bündelt zehn Einträge zu einer Zeile, die
        übrigen neun stehen direkt da. Zehn Zeilen, neun davon mit einem
        Klick erreichbar statt keiner.

        Dieselbe Abwägung steht längst in ``registry.surfaces.group_is_flat``
        für die Menüleiste — eine Zwischenebene, die nichts bündelt, ist ein
        Klick für nichts. Wiederverwenden ließ sie sich nicht: Sie rechnet
        über die Gruppen der Leiste, hier geht es um die eines Merkmals.

        **Die Grenze gilt den Operationen, nicht dem ganzen Menü.** Über
        diesen Einträgen stehen noch Sichtbarkeit und der Skizzenschritt;
        am Flächenklick sind es damit zwölf Zeilen und zwei Trennstriche
        statt zehn. Das ist bewusst so: Wer die drei mitzählte, müsste eine
        zweite Gruppe falten, und die erste, die dran wäre, ist „Ändern" —
        darin liegt die Bohrung, also genau der Eintrag, dessen zweiter Klick
        diesen Umbau ausgelöst hat.
        """
        if len(entries) <= MAX_MENU_ROWS:
            for spec in entries:
                self._add_operation(menu, spec, kinds)
            return

        groups: dict[str, list[Any]] = {}
        for spec in entries:
            groups.setdefault(group_title(str(spec.category)), []).append(spec)

        # Die größten zuerst zusammenfalten: Jede gefaltete Kategorie spart
        # ihre Einträge minus die eine Zeile, die ihr Untermenü kostet. Eine
        # Kategorie mit einem Eintrag spart nichts und wird deshalb nie
        # gefaltet — auch dann nicht, wenn es danach immer noch zu lang ist.
        # Dann ist das Menü eben lang; ein Aufklappen, das nichts bündelt,
        # macht es nicht kürzer, sondern nur tiefer.
        folded = folded_groups({title: len(found) for title, found in groups.items()})

        direct = [spec for spec in entries if group_title(str(spec.category)) not in folded]
        for spec in direct:
            self._add_operation(menu, spec, kinds)
        if folded and direct:
            menu.addSeparator()
        # Mit dem Menü als Elternteil erzeugt, nicht über ``addMenu(titel)``:
        # sonst hält nichts auf der Python-Seite das Untermenü, und sein
        # C++-Objekt wird eingesammelt, während es noch im Menü hängt —
        # dieselbe Falle wie in der Menüleiste.
        for title in sorted(folded):
            submenu = QMenu(title, menu)
            # Ein Untermenü erbt die Eigenschaft nicht — und am ganzen Körper
            # stehen die Operationen des exakten Kerns gerade hier drin.
            submenu.setToolTipsVisible(True)
            self._fill_submenu(submenu, groups[title], kinds)
            menu.addMenu(submenu)

    def _fill_submenu(self, menu: QMenu, specs: Sequence[Any], kinds: Sequence[str]) -> None:
        """Ein gefaltetes Untermenü füllen — mit einer zweiten Ebene, wo es
        sonst zu lang wird.

        Betrifft die Bausteine, und erst seit sie vollständig an der Fläche
        stehen: Vorher waren es zehn, seit `at_face` sind es siebzehn, und
        siebzehn flach untereinander sind eine Liste zum Absuchen. Die
        Gliederung ist nicht erfunden — es ist dieselbe Gruppe, nach der auch
        der Katalog seine Kacheln und die Menüleiste ihre Einträge ordnet
        (``parts.GROUPS``), dort in ``_subgroup_for``.

        Was zu keinem Baustein gehört, bleibt oben stehen: ``create_lid`` ist
        eine Operation und kein Eintrag der Bibliothek.
        """
        if len(specs) <= MAX_MENU_ROWS:
            for spec in specs:
                self._add_operation(menu, spec, kinds)
            return

        from app.core.knowledge.parts import GROUPS
        from app.core.knowledge.parts.ops import part_of

        buckets: dict[str, list[Any]] = {}
        loose: list[Any] = []
        for spec in specs:
            part = part_of(str(spec.name))
            if part is None:
                loose.append(spec)
            else:
                buckets.setdefault(str(GROUPS[part.group]), []).append(spec)

        # Dieselbe Regel wie eine Ebene höher, und aus demselben Grund: „Kabel
        # und Schläuche" hat einen einzigen Baustein, und ein Untermenü dafür
        # wäre der Klick für nichts, den dieser Umbau gerade abschafft.
        sizes = {title: len(found) for title, found in buckets.items()}
        deep = folded_groups(sizes, fixed=len(loose))

        for spec in loose:
            self._add_operation(menu, spec, kinds)
        for title in sorted(buckets):
            if title not in deep:
                for spec in buckets[title]:
                    self._add_operation(menu, spec, kinds)
        if deep:
            menu.addSeparator()
        for title in sorted(deep):
            deeper = QMenu(title, menu)
            deeper.setToolTipsVisible(True)
            for spec in buckets[title]:
                self._add_operation(deeper, spec, kinds)
            menu.addMenu(deeper)

    def _add_operation(self, menu: QMenu, spec: Any, kinds: Sequence[str] = ()) -> None:
        action = menu.addAction(str(spec.title))
        action.setStatusTip(str(spec.doc))
        action.setToolTip(str(spec.doc))
        # **Was auf dieser Bauart nicht geht, sagt es vorher.** Hier stand jede
        # Operation mit einem Eingang anklickbar da, auch die sieben des exakten
        # Kerns: Wer am Netz-Körper *Verrunden* wählte, füllte einen Dialog aus
        # und bekam danach eine Absage — die Sackgasse, die Regel 19 ausschließt
        # und die die Menüleiste seit je vermeidet. Der Satz kommt aus
        # ``labels``, damit beide Menüs dasselbe sagen.
        reason = kind_requirement(spec, kinds, spoiled_the_exact_body(self._result))
        if reason:
            action.setEnabled(False)
            action.setStatusTip(reason)
            action.setToolTip(reason)
        action.triggered.connect(
            lambda _checked=False, entry=spec: self.operationRequested.emit(entry)
        )

    def _on_context_menu(self, position: QPoint) -> None:
        menu = self.context_menu()
        if menu is not None:
            menu.exec(self.tree.viewport().mapToGlobal(position))

    def _add_source_step(self, menu: QMenu) -> None:
        """„Diesen Schritt ändern" — der Weg vom Ergebnis zurück zum Schritt
        (§21.2).

        **Ein erzeugtes Merkmal bietet immer den Schritt an, der es erzeugt
        hat.** Die Frage lautete lange, welche Operation fachlich auf ein
        fertiges Gewinde gehört, und ``for_feature`` gab darauf nichts zurück
        — ``thread`` stand deshalb als benannte Ausnahme im Konsistenztest.
        Über ``applies_to`` wäre die Antwort eine neue Operation je
        Merkmalsart gewesen; über die Provenienz ist sie ein Eintrag, der für
        alle gilt und jede neue Merkmalsart von selbst mitnimmt.

        Er steht **vor** der Sichtbarkeit, weil er dem Merkmal gilt und die
        Sichtbarkeit dem Körper: Wer mit rechts auf eine Bohrung zeigt, meint
        die Bohrung (§18.5). Und er ist der einzige Weg vom *Ergebnis* zurück
        zum *Schritt* — ohne ihn sucht der Kunde unter vierzehn Zeilen des
        Verlaufs die eine, die das Ding erzeugt hat, das er gerade ansieht.

        Ein **erkanntes** Merkmal hat keinen Erzeuger und bekommt den Eintrag
        nicht: Er führte dort ins Leere, und das ist schlechter als keiner.
        """
        feature = self._chosen_feature()
        if feature is None or feature.created_by is None:
            return
        step = feature.created_by
        change = menu.addAction(tr("Diesen Schritt ändern"))
        change.setStatusTip(tr("Öffnet den Schritt, der dieses Merkmal erzeugt hat."))
        change.triggered.connect(lambda _checked=False: self.stepRequested.emit(step))
        menu.addSeparator()

    def _add_sketch_on_face(self, menu: QMenu) -> None:
        """„Auf dieser Fläche zeichnen" — der Weg auf ein vorhandenes Teil.

        Bauplan §30.1 nennt zwei Orte für eine Skizzenebene: eine Hauptebene
        **oder eine angeklickte planare Fläche**, und
        ``app/core/sketch/planes.py`` nennt die zweite „die interessantere,
        denn sie ist der Weg, auf einem vorhandenen Teil weiterzubauen, statt
        daneben". Die Rechnung dazu steht seit je; **erreichbar war sie nur
        über ein Klappfeld** mit Zeilen wie „Fläche an Gehäuse — 2 400 mm²,
        oben", also über das Wiedererkennen einer Fläche in einer Liste statt
        über das Zeigen auf sie.

        Dass es der richtige Weg ist, sagt die Anwendung schon selbst:
        ``sketch_pocket`` verspricht in ihrem ``doc`` „Ein Klick auf eine
        Fläche trägt den Ort vorab ein". Über den Operationsdialog wird das
        eingelöst (``OpDialog.take_feature``), über den Skizzenmodus nicht —
        dasselbe Versprechen, an einer Stelle gehalten und an der anderen
        nicht.

        Nur an einer **Fläche**: Auf einer Bohrung oder einer Kante gibt es
        keine Ebene zu zeichnen, und ein Eintrag, der dort ins Leere führte,
        wäre schlechter als keiner — dieselbe Überlegung wie bei
        :meth:`_add_source_step` und dem erkannten Merkmal ohne Erzeuger.
        """
        if self._feature_kind() != "face":
            return
        feature_id = self.selected_feature()
        if feature_id is None:
            return
        draw = menu.addAction(tr("Auf dieser Fläche zeichnen"))
        draw.setStatusTip(tr("Beginnt eine Skizze auf dieser Fläche statt auf einer Grundebene."))
        draw.triggered.connect(
            lambda _checked=False: self.sketchOnFaceRequested.emit(str(feature_id))
        )

    def _add_visibility(self, menu: QMenu, chosen: tuple[ObjectId, ...]) -> None:
        """Ein- und ausblenden und isolieren (§18.8).

        Keine Operationen: eine Ansichtsentscheidung gehört nicht in den
        Verlauf, sonst steht dort bald mehr Hin und Her als Arbeit. Zurück
        kommt sie über denselben Eintrag, nicht über ein Undo.
        """
        wants_hiding = any(object_id not in self._hidden for object_id in chosen)
        label = tr("Ausblenden") if wants_hiding else tr("Einblenden")
        hide = menu.addAction(label)
        hide.triggered.connect(
            lambda _checked=False: self.visibilityRequested.emit(chosen, not wants_hiding)
        )

        isolate = menu.addAction(
            tr("Alles andere ausblenden") if not self.isolation_holds(chosen) else tr("Alle zeigen")
        )
        isolate.triggered.connect(lambda _checked=False: self.isolateRequested.emit(chosen))


def _empty_parameters_text() -> str:
    """Der leere Zustand sagt, wozu die Leiste da ist — „Noch keine
    Parameter." allein ließ die Frage offen, wie denn einer entsteht."""
    return tr(
        "Noch keine Parameter. Ein Parameter ist ein benanntes Maß — "
        "Operationen und Skizzen rechnen mit ihm."
    )


class ParameterPanel(QWidget):
    """Benannte Projektmaße; an einer Zahl zu drehen baut das Modell
    neu (§13).
    """

    parameterEdited = Signal(str, float)
    addRequested = Signal()
    """Der Nutzer will ein Maß benennen — das Fenster öffnet den Dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        self._form = QFormLayout()
        self._form.setContentsMargins(0, 0, 0, 0)
        self._empty = QLabel(_empty_parameters_text(), self)
        self._empty.setWordWrap(True)
        fit_wrapped(self._empty)
        self._form.addRow(self._empty)
        self._editors: dict[str, QDoubleSpinBox] = {}
        # §2.3: das Anlegen war ein Agentenwerkzeug und sonst nichts — wer
        # ohne Sprachmodell arbeitet, brauchte einen Weg mit der Maus.
        self.add_button = QPushButton(tr("Parameter anlegen …"), self)
        self.add_button.clicked.connect(self.addRequested)
        outer.addLayout(self._form)
        outer.addWidget(self.add_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self._outer = outer
        self._fit()

    def _fit(self) -> None:
        """So hoch wie der Inhalt — wie die beiden Karten darüber und darunter.

        Der Streckfaktor am Ende ist weg: er beanspruchte Restplatz in einer
        Spalte, die keinen verteilt, und der umbrochene Satz des leeren
        Zustands wurde stattdessen gestaucht, bis er unter dem Knopf lag.

        Das Label wird hier **nicht** angefasst: ``show_document`` räumt die
        Zeilen des Formulars weg, und damit ist das C++-Objekt des alten
        Labels fort, während die Python-Referenz noch steht. Wer es hier
        vermäße, stürbe an genau dem — beim ersten Projekt mit Parametern.
        """
        self.setMinimumHeight(self._outer.sizeHint().height())
        self.updateGeometry()

    def show_document(self, document: Document) -> None:
        while self._form.rowCount():
            self._form.removeRow(0)
        self._editors.clear()

        if not document.parameters:
            self._empty = QLabel(_empty_parameters_text(), self)
            self._empty.setWordWrap(True)
            fit_wrapped(self._empty)
            self._form.addRow(self._empty)
            self._fit()
            return

        for name, parameter in document.parameters.items():
            if parameter.expression:
                # Abgeleitete Werte werden gezeigt, nicht bearbeitet — der Ausdruck
                # besitzt sie.
                label = QLabel(f"{localised(f'{parameter.value:.2f}')} {parameter.unit}", self)
                label.setToolTip(parameter.expression)
                self._form.addRow(f"{parameter.title or name}", label)
                continue
            editor = NumberSpin(self)
            editor.setDecimals(2)
            editor.setSuffix(f" {parameter.unit}")
            editor.setMinimum(parameter.minimum if parameter.minimum is not None else -100_000.0)
            editor.setMaximum(parameter.maximum if parameter.maximum is not None else 100_000.0)
            editor.setValue(parameter.value)
            editor.setKeyboardTracking(False)
            editor.valueChanged.connect(
                lambda value, key=name: self.parameterEdited.emit(key, value)
            )
            self._editors[name] = editor
            self._form.addRow(f"{parameter.title or name}", editor)
        self._fit()


class HistoryPanel(QWidget):
    """Transaktionen, neueste zuletzt. Die Einheit des Undo (§15.5).

    Eine Transaktion ist eine Zeile, denn das ist es, was ein Undo
    zurücknimmt. Ihre Operationen bekommen eine eigene Zeile, wo es mehr als
    eine gibt — ein Agentenvorschlag, eine Teilung in vier —, damit sich jeder
    Schritt des Stapels öffnen und korrigieren lässt, nicht nur die, die allein
    kamen (§15.4).
    """

    operationActivated = Signal(int)
    """Eine Operation wurde doppelt angeklickt — trägt ihre ID, zum Ändern (§15.4)."""
    bakeRequested = Signal(int)
    """Der Stand einer Formsitzung soll festgeschrieben werden (Entscheidung D).

    Als Signal und nicht als Aufruf: Die Nachfrage stellt das Fenster, denn sie
    ist die einzige im ganzen Programm — die Handlung ist nicht folgenlos
    rücknehmbar, und Regel 19 gilt nur für die, die es sind."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.list = QListWidget(self)
        self.list.setAccessibleName(tr("Verlauf"))
        self.list.itemDoubleClicked.connect(self._on_activated)
        self.list.setToolTip(tr("Doppelklick öffnet die Operation und ihre Parameter."))
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
        self._room: int | None = None
        """Wie beim Objektbaum: die zugeteilte Höhe, ``None`` bis sie kommt."""
        self._bakeable: frozenset[int] = frozenset()
        """Formsitzungen, deren Stand sich festschreiben lässt — also die, die
        noch aus ihren Zügen gerechnet werden."""
        # Wie beim Objektbaum: ein Satz statt eines stummen Kastens.
        self._empty = QLabel(_empty_history_text(), self)
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._empty.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        fit_wrapped(self._empty)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._empty)
        layout.addWidget(self.list)

    def wanted_height(self) -> int:
        """Die Höhe, bei der jeder Schritt zu sehen wäre."""
        return view_chrome(self.list) + self.list.count() * row_height_of(self.list)

    def least_height(self) -> int:
        """Und die, unter die diese Karte nicht geht (siehe ``fit_to_rows``).

        Der leere Verlauf ist der Fall, an dem es auffiel: ``wanted_height``
        meldete vier Pixel, der Boden gab hundertzwölf, und die Überlagerung
        verteilte nach den vier.
        """
        if self.list.count() == 0:
            return least_empty_height(self._empty)
        return least_height_of(self.list)

    def set_room(self, pixels: int) -> None:
        """Wie hoch diese Karte werden darf (siehe ``fit_to_rows``)."""
        if pixels == self._room:
            return
        self._room = pixels
        self._fit()

    def _fit(self) -> None:
        """So hoch wie der Inhalt, höchstens so hoch wie zugeteilt."""
        empty = self.list.count() == 0
        self._empty.setVisible(empty)
        self.list.setVisible(not empty)
        fit_to_rows(self.list, self.list.count(), room=self._room)
        # Dieselbe Stelle wie im Objektbaum: die Liste ist bemessen, die Karte
        # um sie herum meldete weiter ihre Mindesthöhe und wurde auf zehn Pixel
        # gedrückt.
        self.setMinimumHeight(self.sizeHint().height())
        self.updateGeometry()

    def show_document(
        self,
        document: Document,
        stopped_at: int | None = None,
        undone: Sequence[Any] = (),
    ) -> None:
        """Der Verlauf, und was ein Redo zurückholen würde.

        Zurückgenommene Transaktionen verschwanden hier spurlos: der Verlauf
        endete beim aktuellen Stand, und ob es noch etwas wiederherzustellen
        gab, verriet nur der Zustand des Menüeintrags. Sie stehen jetzt unten,
        durchgestrichen und ausgegraut — wie ein verworfener Chatbeitrag, und
        aus demselben Grund: es ist passiert, es gilt nur gerade nicht (§26.3).
        """
        self.list.clear()
        titles = {entry.id: _op_title(entry.op) for entry in document.ops}
        self._bakeable = frozenset(
            entry.id
            for entry in document.ops
            if entry.op == "sculpt_strokes" and not entry.params.get("baked")
        )
        for transaction in document.transactions:
            # Nur was abweicht, wird ausgeschrieben (§26.4). „(Nutzer)" stand
            # vorher an jeder Zeile — in einem Projekt ohne Agenten also
            # überall, und was überall steht, liest niemand mehr. Dieselbe
            # Überlegung wie beim Material im Steckbrief: genannt wird, was
            # nicht die Regel ist.
            by = f"  ({tr('Agent')})" if transaction.origin.by == "agent" else ""
            item = QListWidgetItem(f"{transaction.title}{by}")
            if stopped_at is not None and stopped_at in transaction.ops:
                # §15.3: die betroffenen Operationen werden im Verlauf markiert.
                item.setText(f"! {item.text()}")
            item.setToolTip(
                f"{transaction.id} · {tr('Ops')} "
                + ", ".join(str(entry) for entry in transaction.ops)
            )
            if len(transaction.ops) == 1:
                item.setData(Qt.ItemDataRole.UserRole, transaction.ops[0])
            self.list.addItem(item)

            if len(transaction.ops) > 1:
                for op_id in transaction.ops:
                    child = QListWidgetItem(f"    {op_id}  {titles.get(op_id, '')}")
                    child.setData(Qt.ItemDataRole.UserRole, op_id)
                    self.list.addItem(child)

        for transaction in reversed(list(undone)):
            item = QListWidgetItem(f"{transaction.title}  ({tr('zurückgenommen')})")
            font = QFont(item.font())
            font.setStrikeOut(True)
            item.setFont(font)
            item.setForeground(QColor(UNDONE_COLOUR))
            item.setToolTip(tr("Ein Wiederholen holt diesen Schritt zurück."))
            self.list.addItem(item)

        self._fit()
        self.list.scrollToBottom()

    def _on_activated(self, item: QListWidgetItem) -> None:
        op_id = item.data(Qt.ItemDataRole.UserRole)
        if op_id is not None:
            self.operationActivated.emit(int(op_id))

    def _on_context_menu(self, position: QPoint) -> None:
        """Was man mit einem Schritt tun kann, dort, wo er steht.

        Bisher gab es nur den Doppelklick, und den findet, wer ihn probiert.
        Angeboten wird, was der Stapel wirklich kann: einen Schritt öffnen und
        seine Zahlen ändern (§15.4). Einen Schritt aus der Mitte zu entfernen
        steht nicht dabei — spätere Operationen bauen auf seinen Ausgaben auf,
        und ein Menüeintrag, der manchmal geht, ist schlimmer als keiner.
        """
        item = self.list.itemAt(position)
        op_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if op_id is None:
            return

        menu = QMenu(self)
        action = menu.addAction(tr("Parameter ändern …"))
        action.triggered.connect(lambda _checked=False: self.operationActivated.emit(int(op_id)))
        if int(op_id) in self._bakeable:
            # Nur an einer Formsitzung, und nur an einer, die noch gerechnet
            # wird: Ein Eintrag, der an jedem Schritt steht und an fast keinem
            # etwas tut, ist einer, den man nicht mehr liest.
            frozen = menu.addAction(tr("Stand festschreiben …"))
            frozen.triggered.connect(lambda _checked=False: self.bakeRequested.emit(int(op_id)))
        menu.exec(self.list.viewport().mapToGlobal(position))


#: Ab wie vielen Befunden der Bericht seine Filterzeile zeigt.
#:
#: Zwei, denn bei einem einzigen Befund kann ein Filter nur ihn treffen oder die
#: Zeile „Kein Befund passt zu …" erzeugen — und bei null zeigte der Bericht ein
#: Suchfeld, eine Filterauswahl und einen leeren Kasten für nichts.
FILTER_FROM = 2


class ReportPanel(QWidget):
    """Befunde aus Einlesen, Operationen und Prüfungen (§17.3)."""

    findingActivated = Signal(object)

    contentGrew = Signal()
    """Die Liste hat Zeilen bekommen und will mehr Platz.

    Ein ``QListWidget`` meldet das von sich aus nicht — seine Wunschgröße
    hängt an der Größenrichtlinie, nicht am Inhalt. Und die Karte hängt in
    keinem Layout, das ein ``LayoutRequest`` weiterreichen könnte: sie bekommt
    ihre Geometrie von ``OverlayHost`` zugewiesen. Wer weiß, dass sich etwas
    geändert hat, sagt es — das ist der Weg, den ``OverlayHost.reflow``
    ausdrücklich vorsieht.
    """

    alertsChanged = Signal(int)
    """Wie viele Fehler und Warnungen jetzt im Bericht stehen.

    Der Reiter darüber trägt die Zahl; ohne sie ist eine Warnung unsichtbar,
    solange Chat oder Tour vorn stehen.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._names: Mapping[str, str] = {}
        """Kennung zu Namen — aus der gezeigten Szene und aus allen Namen, die
        die Auswertung je vergeben hat. Siehe :meth:`show_result`."""
        self._document: Document | None = None
        """Nur für die Herkunftszeile im Tooltip — welcher Schritt das gemeldet
        hat. Der Bericht braucht das Dokument für nichts anderes."""
        self._alerts = 0
        """Fehler und Warnungen im aktuellen Bericht — siehe :meth:`alerts`."""
        self.list = QListWidget(self)
        self.list.setAccessibleName(tr("Befunde"))
        # §2.7 schreibt die Sätze, die hier stehen — im schmalen rechten
        # Bereich endeten sie mitten im Wort hinter einer horizontalen
        # Bildlaufleiste. Umbruch statt Abschneiden: die Leiste bleibt aus,
        # und kein Befund wird auf „…" gekürzt.
        self.list.setWordWrap(True)
        self.list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # §18.4 sagt „Klick auf eine Warnung fährt die Kamera hin" —
        # ``itemActivated`` allein hieß aber Doppelklick oder Eingabetaste,
        # und wer einmal klickte, bekam nichts. Beide Wege führen zum Ort;
        # dass ein Doppelklick dann zweimal fährt, ist dasselbe Ziel.
        self.list.itemClicked.connect(self._on_activated)
        self.list.itemActivated.connect(self._on_activated)
        # Und was dagegen hilft, steht im Kontextmenü — siehe :meth:`_on_menu`.
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_menu)
        self.summary = QLabel(tr("Keine Befunde."), self)
        self.summary.setWordWrap(True)
        # Die Kennzahlen darunter: was der Bericht in Sätzen sagt, hier als
        # Zahlen zum Vergleichen und Weitergeben.
        self.facts = QLabel("", self)
        self.facts.setWordWrap(True)
        self.facts.setProperty("level", "caption")
        self.facts.setVisible(False)

        # Ein Bericht mit hundert Hinweisen und zwei Fehlern versteckt die zwei.
        # Gefiltert wird über den Text und über den Schweregrad; beides
        # zusammen, weil „Wandstärke" und „nur die Fehler" verschiedene Fragen
        # sind (§17.3).
        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("Befunde durchsuchen …"))
        self.search.setAccessibleName(tr("Befunde durchsuchen"))
        self.search.textChanged.connect(self._refilter)
        self.severity = QComboBox(self)
        self.severity.setAccessibleName(tr("Nach Schweregrad filtern"))
        self.severity.addItem(tr("Alle"), "")
        for name in ("error", "warning", "info"):
            self.severity.addItem(f"{SEVERITY_MARKER[name]} {_severity_label(name)}", name)
        self.severity.currentIndexChanged.connect(self._refilter)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.addWidget(self.search, stretch=1)
        filter_row.addWidget(self.severity)
        # Der leere Bericht ist der häufigste — und er zeigte ein Suchfeld, eine
        # Filterauswahl und einen leeren Kasten darunter. Drei Bedienelemente
        # für nichts, und der Satz „Keine Befunde." dazwischen. Was es nicht zu
        # filtern gibt, bekommt keinen Filter (siehe ``_show_controls``).

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        layout.addWidget(self.summary)
        # Wenn der Filter alles wegnimmt, steht sonst ein leerer Rahmen da und
        # sagt nicht, ob nichts passt oder ob der Bericht leer ist. Ein Label
        # und kein Listeneintrag: gefiltert wird über ``setHidden``, die Liste
        # bleibt gefüllt, und ein Eintrag darin wäre beim nächsten Filtern im
        # Weg.
        self._nothing = QLabel("", self)
        self._nothing.setWordWrap(True)
        self._nothing.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        self._nothing.setVisible(False)

        # **Was gegen den gewählten Befund hilft, steht darunter.** Gebaut waren
        # die Handlungen längst, nur hingen sie an einem Rechtsklick auf eine
        # Listenzeile — und §2.7 verspricht „anklickbare Handlungen", nicht
        # welche zum Suchen. Der Fehlerdialog hat dafür seit je Knöpfe; der
        # Bericht, in dem die häufigeren Fälle landen, hatte keine. Leer bleibt
        # die Zeile unsichtbar, wie die Filterzeile über der leeren Liste.
        self._offers = QWidget(self)
        self._offers.setVisible(False)
        self._offer_row = QHBoxLayout(self._offers)
        self._offer_row.setContentsMargins(0, TIGHT, 0, 0)
        self._offer_row.setSpacing(TIGHT)
        self._offer_row.addStretch(1)
        self.list.itemSelectionChanged.connect(self._show_offers)

        layout.addWidget(self.facts)
        layout.addLayout(filter_row)
        layout.addWidget(self._nothing)
        layout.addWidget(self.list)
        layout.addWidget(self._offers)

    def _show_offers(self) -> None:
        """Die Handlungen zum gewählten Befund als Knöpfe (§2.7).

        Dieselbe Quelle wie das Kontextmenü — :func:`actions_for` und die
        Handler des Fensters. Zwei Zugänge zu einer Wahrheit: der Rechtsklick
        ist der schnelle, diese Zeile der, den man findet.

        Neu gebaut statt versteckt: Welche Knöpfe hier stehen, hängt am
        gewählten Befund, und ein Vorrat aus wiederverwendeten Knöpfen müsste
        seine Beschriftung, seinen Handler und seine Sichtbarkeit einzeln
        nachziehen — drei Gelegenheiten für einen Knopf, der das Falsche tut.
        """
        row = self._offer_row
        while row.count() > 1:
            item = row.takeAt(row.count() - 1)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        items = self.list.selectedItems()
        finding: Finding | None = (
            items[0].data(Qt.ItemDataRole.UserRole) if len(items) == 1 else None
        )
        handlers = handlers_of(self)
        offered = (
            [action for action in actions_for(finding) if action.id in handlers]
            if finding is not None
            else []
        )
        for action in offered:
            button = QPushButton(str(action.label), self._offers)
            button.setToolTip(str(finding.message) if finding is not None else "")
            if action.primary:
                make_primary(button)
            button.clicked.connect(
                lambda _checked=False, chosen=action, entry=finding: handlers[chosen.id](
                    as_error(entry)
                )
            )
            row.addWidget(button)
        self._offers.setVisible(bool(offered))

    def _show_controls(self) -> None:
        """Filterzeile und Liste nur, wenn es etwas zu filtern gibt.

        Ein Bericht ohne Befunde ist der Normalfall — und er zeigte ein
        Suchfeld, eine Filterauswahl und einen leeren Listenkasten. Drei
        Elemente, von denen keines etwas tun kann, und der einzige Satz mit
        Inhalt („Keine Befunde.") stand darüber wie eine Überschrift.

        Die Schwelle ist **zwei**, nicht eins: Bei einem einzigen Befund kann
        ein Filter nur ihn selbst treffen oder die Zeile „Kein Befund passt zu
        …" erzeugen. Beides ist keine Auskunft, die jemand gesucht hat.
        """
        count = self.list.count()
        self.list.setVisible(bool(count))
        for widget in (self.search, self.severity):
            widget.setVisible(count >= FILTER_FROM)
        if count < FILTER_FROM and (self.search.text() or self.severity.currentIndex()):
            # Ein Filter, der verschwindet, nimmt seine Wirkung mit — sonst
            # bliebe eine Auswahl gesetzt, die niemand mehr sehen und
            # zurücknehmen kann.
            self.search.clear()
            self.severity.setCurrentIndex(0)

    def _refilter(self) -> None:
        """Blendet aus, was nicht passt — gelöscht wird nichts.

        Die Zählung über der Liste bleibt die des ganzen Berichts: eine
        Filterzeile, die auch die Zusammenfassung filtert, verschweigt, dass es
        noch etwas anderes gibt.
        """
        query = self.search.text().casefold()
        wanted = str(self.severity.currentData() or "")
        for row in range(self.list.count()):
            item = self.list.item(row)
            finding: Finding = item.data(Qt.ItemDataRole.UserRole)
            matches = (not query or query in str(finding.message).casefold()) and (
                not wanted or finding.severity == wanted
            )
            item.setHidden(not matches)

        visible = sum(1 for row in range(self.list.count()) if not self.list.item(row).isHidden())
        if visible or not self.list.count():
            self._nothing.setVisible(False)
            return
        term = self.search.text().strip()
        level = self.severity.currentText().strip()
        if term and wanted:
            sentence = tr("Kein Befund passt zu „{begriff}“ und „{stufe}“.")
        elif term:
            sentence = tr("Kein Befund passt zu „{begriff}“.")
        else:
            sentence = tr("Kein Befund dieser Stufe: „{stufe}“.")
        self._nothing.setText(str(sentence).format(begriff=term, stufe=level))
        self._nothing.setVisible(True)

    def show_result(
        self, result: EvaluationResult | None, document: Document | None = None
    ) -> None:
        # ``document`` nur für die Herkunft im Tooltip: welcher Schritt einen
        # Befund gemeldet hat. Die Liste sortiert nach Schwere, und damit
        # stehen Sätze aus verschiedenen Schritten untereinander — bei
        # ``weg3-generiert-aufbereiten`` liest sich das als Widerspruch:
        # „Das Modell ist nicht geschlossen." direkt neben „Eine offene Stelle
        # ist geschlossen und damit fort." Beides stimmt, das eine kommt vom
        # Einlesen, das andere von der Reparatur — und das stand nirgends.
        self._document = document
        # Die Namen der Körper, damit ein Befund sagen kann, welchen er meint.
        # Sie stehen im Ergebnis, das ohnehin hereinkommt — die Kennung „obj_2"
        # wäre die zweitbeste Antwort auf „welcher denn".
        #
        # Zwei Quellen, und die Reihenfolge ist die Aussage: Zuerst alle Namen,
        # die die Auswertung je vergeben hat, darüber die der Endszene. Ein
        # Körper, der noch da ist, heißt also so, wie er *jetzt* heißt; einer,
        # den ein späterer Schritt verbraucht hat, so wie er hieß, als der
        # Befund entstand. Vorher gab es nur die zweite Quelle, und dann stand
        # im Bericht „obj_1" — sichtbar im Handbuchbild, in allen sechs
        # Sprachen: Das Aushöhlen meldet etwas über die Dose, und nach
        # ``create_lid`` gibt es sie nicht mehr.
        self._names = (
            {
                **{str(key): name for key, name in result.object_names.items()},
                **{str(key): str(entry.name) for key, entry in result.scene.objects.items()},
            }
            if result
            else {}
        )
        self.list.clear()
        for finding in _by_severity(result.scene.report.findings if result else ()):
            self._append(finding)
        self._count_up()
        self._measure_up(result)
        self._refilter()
        self._show_controls()
        self._grew()

    def add_findings(self, findings: list[Finding]) -> None:
        """Hängt Befunde an, die nicht aus der Auswertung kamen — die
        G-Code-Gegenprobe etwa (§28.2). Sie behalten ihre eigene
        Herkunft (§22.5).

        Was schon dasteht, kommt nicht noch einmal. Mehrere Prüfungen sehen
        dieselbe Sache: „Kollisionen prüfen" und die Exportprüfung melden beide,
        dass ein Körper über den Bauraum hinaussteht, und nach beiden stand die
        Zeile zweimal da. Zweimal gemeldet ist nicht zweimal passiert — ein
        Zähler daneben wäre eine Zahl, die etwas anderes behauptet.
        """
        known = self._known()
        fresh = []
        for finding in findings:
            key = _identity(finding)
            if key in known:
                continue
            known.add(key)
            self._append(finding)
            fresh.append(key)
        self._resort()
        self._count_up()
        self._refilter()
        # Auch hier: ein Befund, der nachkommt, bringt die Filterzeile mit —
        # sonst hängt sie an dem Stand, den die Auswertung hinterließ.
        self._show_controls()
        self._grew()
        if fresh:
            # Nach dem Ordnen steht der neue Befund nicht mehr unten, sondern
            # dort, wo sein Gewicht ihn hinstellt — also wird er gesucht und
            # nicht die Liste ans Ende gefahren.
            self._show_first_of(fresh)

    def _grew(self) -> None:
        """Melden, dass die Liste jetzt mehr Platz will — siehe ``contentGrew``.

        Die Karte blieb sonst so hoch, wie sie beim Auswerten war, und Befunde,
        die danach nachkamen (G-Code-Gegenprobe §28.2, Kollisionsprüfung,
        Exportprüfung), verschwanden hinter einem Rollbalken, während neben der
        Karte hunderte Pixel frei blieben.

        Aufgefallen ist es am Handbuchbild: acht Befunde im Kopf gezählt, zwei
        zu sehen.
        """
        self.list.updateGeometry()
        self.updateGeometry()
        self.contentGrew.emit()

    def _resort(self) -> None:
        """Die ganze Liste nach Schwere ordnen.

        Nach jedem Anhängen und nicht nur beim Aufbau: ein Fehler, der über
        ``add_findings`` nachkommt, gehört nach oben und nicht ans Ende
        dessen, was schon dasteht.
        """
        findings = [
            self.list.item(row).data(Qt.ItemDataRole.UserRole) for row in range(self.list.count())
        ]
        self.list.clear()
        for finding in _by_severity(findings):
            self._append(finding)

    def _show_first_of(self, keys: list[tuple[Any, ...]]) -> None:
        """Zum obersten der genannten Befunde scrollen."""
        for row in range(self.list.count()):
            item = self.list.item(row)
            if _identity(item.data(Qt.ItemDataRole.UserRole)) in keys:
                self.list.scrollToItem(item)
                return

    def _known(self) -> set[tuple[Any, ...]]:
        """Woran die Liste einen Befund wiedererkennt."""
        return {
            _identity(self.list.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self.list.count())
        }

    def _append(self, finding: Finding) -> None:
        """Einen Befund als Eintrag anhängen."""
        item = QListWidgetItem(_line_for(finding, self._names))
        # Die Farbe folgt der Fläche, auf der sie landet. Die Rollenfarben sind
        # für den dunklen Untergrund gewählt; auf der weißen Liste des hellen
        # Themas brachte Bernstein 2,22 und das Hinweisblau 2,67 — jede Zeile
        # des Prüfberichts stand damit unter der Lesbarkeitsgrenze. Gefragt
        # wird die Liste selbst und nicht das eingestellte Thema: sie weiß, auf
        # was hier geschrieben wird.
        tone = QColor(
            text_colour(
                cast(Role, finding.severity),
                self.list.palette().base().color().name(),
            )
        )
        # Die Form trägt den Schweregrad, die Farbe verstärkt ihn nur: ein
        # Dreieck bleibt ein Dreieck, auch wo die Farbe nicht ankommt.
        item.setIcon(icon(f"severity-{finding.severity}", self.list, colour=tone))
        item.setData(Qt.ItemDataRole.UserRole, finding)
        item.setForeground(tone)
        # §22.5: woher eine Zahl kommt, ist Teil des Befunds und wird nie dem
        # Leser zum Annehmen überlassen — eine Schätzung ist keine Messung.
        details = [f"{tr('Herkunft')}: {origin_label(finding.source)}"]
        step = _origin_text(finding.op_id, self._document)
        if step:
            details.append(step)
        details.extend(value_line(key, value) for key, value in finding.values.items())
        item.setToolTip(" · ".join(details))
        self.list.addItem(item)

    def _count_up(self) -> None:
        """Die Zeile über der Liste aus der Liste selbst zählen.

        Nicht aus dem übergebenen Ergebnis: Befunde kommen aus zwei Richtungen
        — aus der Auswertung und über ``add_findings`` —, und wer nur die eine
        zählt, schreibt „Keine Befunde" über eine Liste voller Befunde. Genau
        das stand hier.
        """
        counts = dict.fromkeys(SEVERITY_MARKER, 0)
        for row in range(self.list.count()):
            finding: Finding = self.list.item(row).data(Qt.ItemDataRole.UserRole)
            counts[finding.severity] += 1
        alerts = counts["error"] + counts["warning"]
        if alerts != self._alerts:
            self._alerts = alerts
            self.alertsChanged.emit(alerts)
        if not any(counts.values()):
            self.summary.setText(tr("Keine Befunde."))
            return
        self.summary.setText(
            f"{counts['error']} × {tr('Fehler')} · "
            f"{counts['warning']} × {tr('Warnung')} · "
            f"{counts['info']} × {tr('Hinweis')}"
        )

    def alerts(self) -> int:
        """Wie viele Befunde nach Aufmerksamkeit verlangen — Fehler und
        Warnungen, keine Hinweise.

        Der Reiter über diesem Panel trägt die Zahl. Ohne sie ist eine Warnung
        unsichtbar, solange etwas anderes vorn steht: ein eingelesenes Netz mit
        offenen Stellen meldete sich im Bericht, und im Fenster sah man einen
        Reiter, der aussah wie vorher.

        Hinweise zählen nicht mit. „Doppelte Punkte wurden verschweißt" ist
        eine Auskunft und keine Aufforderung; eine Zahl, die bei jedem Projekt
        dasteht, wird zur Tapete.
        """
        return self._alerts

    def _measure_up(self, result: EvaluationResult | None) -> None:
        """Die Kennzahlen über den Befunden — wasserdicht, Volumen, Teile.

        Ein Bericht aus Sätzen sagt, *was* zu tun ist; er sagt nicht, woran man
        gerade ist. Diese drei Zahlen tun das, und sie kosten nichts: Sie
        stehen im ausgewerteten Netz und werden nicht gerechnet.

        Bewusst nur, was ohne Schichtanalyse dasteht. Schmalste Wand und
        schlimmster Überhang gehören der Sache nach hierher, aber sie kosten
        einen Schnitt durch jede Schicht — eine Zeile, die beim Öffnen jeder
        Datei sekundenlang rechnet, ist keine Auskunft, sondern eine Bremse.
        """
        meshes = [entry.mesh for entry in result.scene.objects.values()] if result else []
        if not meshes:
            self.facts.setText("")
            self.facts.setVisible(False)
            return

        content = sum(float(mesh.volume) for mesh in meshes)
        parts = sum(int(mesh.component_count) for mesh in meshes)
        tight = sum(1 for mesh in meshes if mesh.is_watertight)
        # Das Wort steht neben dem Zeichen, nicht statt seiner (Regel 18).
        closed = (
            tr("wasserdicht")
            if tight == len(meshes)
            else f"{tight}/{len(meshes)} {tr('geschlossen')}"
        )
        # Hier stand ein Malzeichen vor einem Plural, und das ist falsches
        # Deutsch: mit Singular hieße es zweimal dasselbe Teil, gemeint sind
        # zwei. Die Zeile darüber zählt Befunde und behält ihr Malzeichen —
        # dort steht der Singular dahinter.
        # **Über ``volume`` und nicht mit eigener Rechnung.** Hier stand
        # ``format_decimal(volume / 1000.0, 1)} cm³`` — zwei Fehler in einer
        # Zeile: Ein Teil von zwei Millimetern Kantenlänge stand als „0,0 cm³"
        # da, und in Zoll stand es auch dann in Kubikzentimetern, wenn jede
        # Länge daneben in Zoll gemessen war (§19.3). Beides beantwortet
        # ``labels.volume``: die Einheit aus der Anzeigeeinstellung, die Größe
        # aus dem Kern (:func:`units.format_volume`). Ohne Argument, weil diese
        # Karte keine eigene Einheit führt — die Anzeigeeinheit ist ein
        # Zustand, kein Feld.
        self.facts.setText(
            f"{closed} · {volume(content)} · {parts} {tr('Teil') if parts == 1 else tr('Teile')}"
        )
        self.facts.setVisible(True)

    def worst_severity(self, result: EvaluationResult | None) -> str | None:
        if result is None:
            return None
        return result.scene.report.worst_severity

    def _on_activated(self, item: QListWidgetItem) -> None:
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        self.findingActivated.emit(finding)

    def _on_menu(self, position: QPoint) -> None:
        """Was gegen diesen Befund hilft — als anklickbare Handlung (§2.7).

        Der Bericht sagte, was nicht stimmt, und hörte da auf. „Das Objekt
        steht über den Bauraum hinaus" ist ein Satz mit einer offensichtlichen
        Antwort — teilen oder verkleinern —, und beide Handlungen gab es
        längst: Sie hingen an ``OutOfBuildVolume``, einer Ausnahme, die
        **niemand wirft**. Drei Vorschläge, vollständig gebaut, nie angeboten.

        Angeboten wird nur, wofür das Fenster einen Handler hat, wie im
        Fehlerdialog auch (:func:`app.ui.dialogs.offered_actions`). Ein Befund
        ohne Handlung bekommt kein leeres Menü — das wäre ein Klick, der
        Auskunft verspricht und keine gibt.
        """
        item = self.list.itemAt(position)
        if item is None:
            return
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        offers = actions_for(finding)
        handlers = handlers_of(self)
        offered = [action for action in offers if action.id in handlers]
        if not offered:
            return

        menu = QMenu(self)
        chosen: dict[Any, Any] = {}
        for action in offered:
            chosen[menu.addAction(str(action.label))] = action
        # Die Stubs versprechen eine Aktion; wer das Menü wegklickt, bekommt
        # None. Dieselbe Notlüge wie bei ``currentItem`` in der Palette.
        picked = cast(QAction | None, menu.exec(self.list.viewport().mapToGlobal(position)))
        if picked is None:
            return
        # Die Handler des Fensters arbeiten auf einem ``AppError`` — sie
        # kommen aus dem Fehlerdialog. Ein Befund ist keiner, trägt aber
        # dieselben zwei Angaben, die sie brauchen: den Körper und die Zahlen.
        handlers[chosen[picked].id](as_error(finding))


class MeasurementLabel(QLabel):
    """Maße der Auswahl für die Statusleiste (§2.5)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._unit: LengthUnit = "mm"
        self.clear_selection()

    def set_unit(self, unit: LengthUnit) -> None:
        """§19.3: die Anzeigeeinheit. Der Kern bleibt bei Millimetern."""
        self._unit = unit

    def clear_selection(self) -> None:
        self.setText(tr("Keine Auswahl"))

    def show_object(self, name: str, size: tuple[float, float, float], content: float) -> None:
        self.setText(
            f"{name}   "
            f"{length(size[0], self._unit, with_unit=False)} × "
            f"{length(size[1], self._unit, with_unit=False)} × "
            f"{length(size[2], self._unit)}   "
            f"{volume(content, self._unit)}"
        )


#: Höchstanteil der Maßspalte im Objektbaum.
#:
#: Beide Spalten wollen Platz: der Name, weil zwei Körper eines Projekts sich
#: sonst nicht unterscheiden, und das Maß, weil eine halbe Zahl keine ist. Bei
#: 258 Pixeln Breite bekam der Name mit Qts Vorgabe 128 und mit reiner
#: Inhaltsbreite der Maßspalte 70 — beides zu wenig. Zwei Fünftel für das Maß
#: lassen dem Namen die Mehrheit und reichen für „60 x 40 x 12 mm" in der
#: Schrift, mit der wirklich gezeichnet wird.
MEASURE_SHARE = 0.4

#: Wie viele Zeilen eine Karte der linken Spalte mindestens hoch wird — drei,
#: damit der leere Zustand seinen Satz zeigen kann.
MIN_ROWS = 3

#: Der Deckel, solange niemand gesagt hat, wie viel Platz da ist.
#:
#: Er war einmal die ganze Antwort auf „ein Baum mit fünfzig Teilen darf nicht
#: die Spalte nehmen und den Verlauf hinausschieben". Die Sorge ist richtig,
#: eine Konstante ist die falsche Antwort darauf: im Vollbild stand der Baum
#: bei dreißig sichtbaren Zeilen auf zwölf und rollte, während unter der Karte
#: dreihundert Pixel leer blieben. Wie viel Platz da ist, weiß nur die
#: Überlagerung — sie teilt ihn über ``set_room`` zu, und dann gilt ihre Zahl
#: statt dieser.
MAX_ROWS = 12


def fit_wrapped(label: QLabel) -> None:
    """Gibt einem umbrochenen Text die Höhe, die er wirklich braucht.

    Ein ``QLabel`` mit Zeilenumbruch meldet seine Höhe über
    ``heightForWidth``, und diese Kette reißt in einem Layout ohne
    Streckfaktor: der Satz „Noch keine Parameter …" bekam siebzehn Pixel und
    war nach anderthalb Zeilen abgeschnitten. Die Breite steht fest — die
    linke Spalte ist so breit, wie das Überlagerungsschema sie macht.
    """
    inner = LEFT_WIDTH - 2 * NORMAL
    label.setMinimumHeight(label.heightForWidth(inner))


def view_chrome(view: QAbstractItemView) -> int:
    """Was eine Liste über ihren Zeilen braucht: Rahmen, Spaltenkopf, Luft.

    Die zwei Pixel Luft am Ende sind nicht Zierde: ohne sie endet die letzte
    Zeile genau auf der Kante des Sichtfelds, und eine Zeile, die auf den
    Rahmen stößt, sieht abgeschnitten aus, auch wenn sie vollständig da ist.

    **Gefragt wird die Wunschhöhe des Kopfes, nicht seine aktuelle.** Ein
    Spaltenkopf, den Qt noch nicht gelegt hat, meldet 30 Pixel statt 16 —
    gemessen an einem frisch gebauten Baum. Der Deckel wurde daraus berechnet,
    also war der Objektbaum vierzehn Pixel höher als die zwölf Zeilen, die er
    zeigen sollte. Aufgefallen ist das erst, als eine andere Änderung den Kopf
    früher legte: Vorher lasen die Rechnung und der Test, der sie prüft,
    denselben falschen Wert, und beide waren zufrieden. Die Wunschhöhe steht von
    Anfang an fest.
    """
    header = 0
    if isinstance(view, QTreeWidget) and not view.isHeaderHidden():
        head = view.header()
        header = head.sizeHint().height() if head is not None else 0
    return header + 2 * view.frameWidth() + 2


def row_height_of(view: QAbstractItemView) -> int:
    """Wie hoch eine Zeile dieser Liste ist — notfalls geschätzt."""
    height = view.sizeHintForRow(0) if view.model() is not None else 0
    if height <= 0:
        height = view.fontMetrics().height() + 2 * TIGHT
    return height


def fit_to_rows(view: QAbstractItemView, rows: int, *, room: int | None = None) -> None:
    """Setzt die Höhe einer Liste oder eines Baums auf ihren Inhalt.

    Die linke Spalte baut ihre Karten ohne Streckfaktor, „so hoch wie ihr
    Inhalt" — gemeint war das seit je, umgesetzt war es nicht: Qt gab jeder
    Ansicht ihre eigene Mindesthöhe von etwa zwei Zeilen und ließ es dabei.
    Der Objektbaum scrollte damit ab dem zweiten Körper, während unter der
    Spalte sechshundert Pixel leer blieben — und der zweite Körper ist genau
    das, was nach einer Teilung entsteht.

    ``room`` ist die Höhe, die diese Liste haben darf. Sie kommt von der
    Überlagerung, die als einzige weiß, wie hoch das Fenster ist und wie viele
    Karten sich darin teilen müssen. Ohne sie gilt ``MAX_ROWS`` — für einen
    Aufruf, der von außerhalb der Spalte kommt, und für den Augenblick vor dem
    ersten Zuteilen.
    """
    chrome = view_chrome(view)
    row_height = row_height_of(view)
    wanted = chrome + max(rows, 0) * row_height
    ceiling = room if room is not None else chrome + MAX_ROWS * row_height
    view.setFixedHeight(max(least_height_of(view), min(wanted, ceiling)))


def least_height_of(view: QAbstractItemView) -> int:
    """Unter diese Höhe geht eine Liste nicht, was auch zugeteilt wird.

    Dieselbe Zahl, die ``fit_to_rows`` als Boden durchsetzt — und deshalb muss
    die Überlagerung sie kennen: Sie verteilte den Platz anteilig am Bedarf und
    rechnete damit für eine leere Verlaufsliste mit vier Pixeln, während der
    Boden ihr hundertzwölf gab. Die Summe der Zuteilungen lag danach über dem
    Platz, den es gab, und die Karte darüber wurde vom Layout zusammengedrückt,
    bis Zeilen außerhalb lagen.
    """
    return view_chrome(view) + MIN_ROWS * row_height_of(view)


def least_empty_height(label: QLabel) -> int:
    """Der Boden einer Karte, die gerade ihren leeren Zustand zeigt.

    Der leere Zustand tritt an die *Stelle* der Liste, und seine Höhe kommt aus
    dem umbrochenen Satz (``fit_wrapped``), nicht aus ``fit_to_rows``. Der
    leere Verlauf nannte deshalb 64 Pixel als Boden und stand auf 112 — die 48
    Pixel Unterschied fehlten der Karte darüber, und ihre letzten Zeilen lagen
    außerhalb des Abschnitts.

    Beide Zahlen hängen an der festen Spaltenbreite und nicht an der
    Zuteilung — die Bedingung, unter der die Spalte stillsteht.
    """
    return max(label.minimumHeight(), label.sizeHint().height())


def collapsible(title: str, content: QWidget, *, open_now: bool = True) -> QWidget:
    """Ein Abschnitt, der sich zuklappen lässt — §2.5 verlangt genau das.

    Er hieß so und war keiner: eine fette Überschrift über dem Inhalt, ohne
    Umschalter. Wer den Verlauf groß haben wollte, konnte die anderen beiden
    nicht wegklappen, und drei Abschnitte in einer schmalen Spalte teilen sich
    die Höhe, ob sie sie brauchen oder nicht.

    Der Umschalter ist ein Knopf mit dem Titel darauf, kein Zeichen daneben:
    die ganze Zeile ist damit die Fläche, die man trifft, und der gedrückte
    Zustand sagt ohne Farbe, ob offen oder zu ist (Regel 18).
    """
    wrapper = QWidget()
    heading = QToolButton(wrapper)
    # Eine Kopfzeile ist kein Umschalter im Sinne der Werkzeugzeile: sie steht
    # dauerhaft auf „offen", und ein dauerhaft eingefärbter Balken wäre die
    # lauteste Fläche im Fenster für die Aussage „hier ist nichts geschehen".
    heading.setObjectName("sectionHeading")
    heading.setText(title)
    heading.setCheckable(True)
    # ``open_now=False`` für alles, was hinter „Weitere Einstellungen" gehört
    # (§2.4): die drei Abschnitte der linken Spalte stehen offen, ein
    # Startwert in einem Erzeugungsdialog nicht.
    heading.setChecked(open_now)
    heading.setAutoRaise(True)
    heading.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    heading.setArrowType(Qt.ArrowType.DownArrow if open_now else Qt.ArrowType.RightArrow)
    content.setVisible(open_now)
    set_level(heading, "section")
    heading.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def toggled(open_now: bool) -> None:
        content.setVisible(open_now)
        heading.setArrowType(Qt.ArrowType.DownArrow if open_now else Qt.ArrowType.RightArrow)

    heading.toggled.connect(toggled)

    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(heading)
    layout.addWidget(content)
    return wrapper


def describe_selection(result: EvaluationResult | None, object_id: ObjectId | None) -> Any:
    """Name, Größe und Volumen des gewählten Objekts, oder None."""
    if result is None or object_id is None:
        return None
    entry = result.scene.objects.get(object_id)
    if entry is None:
        return None
    return entry.name, entry.mesh.bounds.size, entry.mesh.volume


def _preview_pixels(widget: QWidget) -> int:
    """Wie groß ein Vorschaubild wird — an der Zeilenhöhe, nicht in Pixeln.

    Wer seine Schrift größer stellt, bekommt größere Zeilen; ein Bild in
    fester Größe säße dann in einer Zeile, die doppelt so hoch ist.

    Der Faktor kommt aus dem Bild und nicht aus einer Überlegung: Bei
    Zeilenhöhe mal 1,15 war ein Quader ein Punkt, an dem nichts zu erkennen
    war — und ein Bild, das man nicht erkennt, ist teurer als kein Bild.

    Größer geht trotzdem nicht: Die Karte ist 260 Pixel breit, ein volles
    Kantenmaß nimmt davon gut die Hälfte, und ab Zeilenhöhe mal 1,7 stand
    „Dose Deckel" als „Dose Dec…" da. Ein Name, den man lesen kann, ist mehr
    wert als eine Silhouette, die man erkennt — das Bild bleibt deshalb die
    Wiedererkennung nebenher und wird nie die Auskunft selbst. Eine
    Maßspalte mit Deckel half nicht: Sie war schon am Anschlag.
    """
    return max(int(widget.fontMetrics().height() * 1.2), 18)


def _svg_icon(svg: str, size: int) -> QIcon:
    """Ein SVG als Symbol, scharf auf HiDPI.

    Doppelt gerastert und dann auf die Anzeigegröße gesetzt: Ein Bild in
    genau der Punktgröße franst auf einem skalierten Bildschirm aus.
    """
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return QIcon()
    image = QImage(QSize(size, size) * 2, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.setDevicePixelRatio(2.0)
    return QIcon(QPixmap.fromImage(image))
