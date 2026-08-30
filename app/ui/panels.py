"""Die drei Panels links und der Prüfbericht rechts (Bauplan §2.5).

Drei einklappbare Abschnitte, keine drei Fenster: Objektbaum, Parameter,
Verlauf. Sie lesen aus dem Dokument und der letzten Auswertung, und sie ändern
nie selbst Geometrie — jede Änderung geht durch eine Operation (AGENTS.md
Regel 2).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final, cast

from PySide6.QtCore import QByteArray, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QImage, QKeySequence, QPainter, QPixmap
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
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
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
    CANCEL,
    CHANGE_SELECTION,
    CHOOSE_PRINTER,
    CORRECT_INPUT,
    PLACE_ON_BED,
    REMOVE_SMALL_PARTS,
    REPAIR_AND_RETRY,
    SCALE_TO_FIT,
    SHOW_HISTORY,
    SHOW_LOCATIONS,
    SHOW_STEP_VALUES,
    SPLIT_MODEL,
    Action,
    AppError,
)
from app.core.log import get_logger
from app.core.registry import MENU_TWINS, REGISTRY
from app.core.registry.surfaces import MAX_MENU_ROWS as _MAX_MENU_ROWS
from app.core.registry.surfaces import folded_groups
from app.core.scene import EvaluationResult
from app.core.types import Document, Feature, Finding, ObjectId
from app.core.units import LengthUnit
from app.i18n import sort_key, tr
from app.ui.dialogs import handlers_of
from app.ui.icons import icon
from app.ui.labels import (
    NumberSpin,
    compact_length,
    feature_label,
    feature_measure,
    feature_name,
    fill_parameter_units,
    group_title,
    kind_requirement,
    length,
    localised,
    spoiled_the_exact_body,
    value_line,
    value_text,
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
# **Aus dem Kern, nicht als eigene Zahl.** Dieselbe Grenze aus §35 steht in
# ``registry/surfaces.py``, und dort gehört sie hin: Sie beschreibt, was ein
# Menü tragen kann, und der Kern baut die Menüstruktur. Zwei Zahlen für eine
# Grenze sind zwei Stellen, an denen jemand die eine erhöht.
MAX_MENU_ROWS = _MAX_MENU_ROWS

#: Datenrolle einer Verlaufszeile: **alle** Operationen, die sie umfasst, als
#: Tupel. Neben ``UserRole``, das die *eine* Operation zum Öffnen trägt und
#: bei einer Transaktion aus mehreren Schritten leer bleibt — ein Doppelklick
#: hätte dort keine, die er zeigen könnte. Die Mehrfachauswahl fragt diese
#: Rolle, weil sie die andere Frage stellt: was gehört zu dieser Zeile.
OPS_ROLE = int(Qt.ItemDataRole.UserRole) + 1


#: Kategorien, deren Gruppe am Merkmal sichtbar bleibt.
#:
#: Nicht der Gruppentitel, sondern die **Kategorie** des Registereintrags: Der
#: Titel ist übersetzt, und eine Liste deutscher Wörter träfe im englischen
#: Fenster nichts. Hier steht ``colour``, weil das Färben die Geste ist, für
#: die man auf eine Fläche zeigt (Entscheidung Robert, 27.08.2026) — wer eine
#: weitere aufnimmt, nimmt damit in Kauf, dass etwas anderes wandert.
#:
#: ``holes`` steht daneben, weil es schon einmal geschützt war: Der Umbau vom
#: 24.08.2026 hat die Faltung eigens umgestellt, damit die Bohrung nicht im
#: Untermenü landet — sie ist die häufigste Geste an einer fremden Fläche
#: überhaupt. Diese Zusage stand nur im Rang von ``MENU_GROUPS`` und wäre mit
#: dem Schutz des Färbens verloren gegangen: Dann hätte die Rechnung sich
#: „Ändern" genommen, und die Bohrung wäre gewandert. Was einmal ausdrücklich
#: entschieden wurde, gehört ausdrücklich hierher und nicht in eine Ordnung,
#: die jemand für einen anderen Zweck sortiert.
KEEP_VISIBLE: Final = ("colour", "holes")


def groups_to_keep(entries: Sequence[Any]) -> set[str]:
    """Die Gruppentitel, die sichtbar bleiben sollen (:data:`KEEP_VISIBLE`)."""
    return {
        str(group_title(str(spec.category)))
        for spec in entries
        if str(spec.category) in KEEP_VISIBLE
    }


#: In welcher Reihenfolge die Schweregrade stehen. Die Zeile über der Liste
#: zählt Fehler, Warnungen und Hinweise getrennt — sie verspricht damit eine
#: Rangfolge, und die Liste darunter hielt sie nicht: sie hängte an, wie es
#: kam, also stand bei zwei Warnungen und vier Hinweisen zuoberst ein Hinweis.
#: Wer einen Fehler suchte, musste ihn filtern statt lesen.
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


#: Ab wie vielen wortgleichen Befunden die Liste sie zu einer Zeile bündelt.
#:
#: Nach einem Weg-3-Erzeugungslauf standen 123 Befunde im Bericht, 118 davon
#: wortgleich („Ein Merkmal hat keinen Nachfolger mehr") — die fünf Zeilen,
#: die etwas sagten, gingen darin unter, allen voran das richtige
#: ``arrange.below_bed``. Jede Einzelzeile stimmt; die **Menge** begräbt.
#: Gebündelt wird deshalb in der Anzeige, nicht im Kern: Agent, CLI und
#: Tests lesen weiterhin jeden Befund einzeln. Bis drei bleibt es bei
#: Einzelzeilen — dort trägt „welches Objekt" mehr als eine Zahl.
BUNDLE_FROM = 4

#: Trägt an einer Sammelzeile, wie viele Befunde sie bündelt. Eine eigene
#: Rolle und nicht ``values["count"]``: Den Schlüssel führen auch Befunde des
#: Kerns („12 kleine Objekte übergangen"), und eine Zählung, die ihn läse,
#: zählte deren Zahl statt ihrer Zeile.
_BUNDLE_ROLE = int(Qt.ItemDataRole.UserRole) + 3


def _bundled(findings: list[Finding]) -> list[tuple[Finding, list[Finding]]]:
    """Wortgleiche Befunde ab :data:`BUNDLE_FROM` zu einer Zeile je Wortlaut.

    Gruppiert wird über Kennung, Grad und Wortlaut — nicht über die Werte,
    denn genau die (das jeweilige Merkmal) machen die 118 Zeilen verschieden.
    Die Reihenfolge der Erstvorkommen bleibt erhalten; kleine Gruppen kommen
    als Einzelzeilen zurück (leere Mitgliederliste).
    """
    groups: dict[tuple[str, str, str], list[Finding]] = {}
    order: list[tuple[str, str, str]] = []
    for finding in findings:
        key = (finding.code, finding.severity, str(finding.message))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(finding)
    result: list[tuple[Finding, list[Finding]]] = []
    for wording in order:
        members = groups[wording]
        if len(members) >= BUNDLE_FROM:
            result.append((members[0], members))
        else:
            result.extend((one, []) for one in members)
    return result


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
    # Ein Schritt, den diese Fassung nicht kennt (§16.2). Zwei Handlungen, und
    # die erste ist die, um die es geht: *Werte ansehen* holt heraus, was in
    # dem Schritt steht — bei einer Datei aus 0.1.3 der OpenSCAD-Quelltext,
    # den jemand geschrieben hat. Ohne sie wäre der Befund eine Sackgasse: ein
    # Satz, der „Ihre Werte bleiben erhalten" verspricht, und kein Weg dorthin.
    #
    # **Löschen liegt im Verlauf selbst.** Auch ein unbekannter Schritt lässt
    # sich dort als rücknehmbare Transaktion entfernen; dieser Befund führt
    # deshalb dorthin. *Werte ansehen* bleibt vorn, weil Löschen die Arbeit
    # aufräumt, ihren Inhalt aber nicht vorab zugänglich macht (§15.4).
    "evaluate.unknown_operation": (SHOW_STEP_VALUES, SHOW_HISTORY),
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
    # Die Druckdatei ist niedriger als das Modell: CuraEngine schneidet unter
    # ``z = 0`` wortlos ab (gemessen 30.08.2026, 50 statt 100 Schichten). Die
    # Ursache ist dieselbe wie bei ``arrange.below_bed`` — das Teil steckt
    # unter der Platte —, nur festgestellt an der fertigen Datei; die Handlung
    # ist darum dieselbe: aufsetzen und neu slicen.
    "gcode.shorter_than_model": (PLACE_ON_BED,),
    # Körper, die genau aufeinander liegen, sind im Bild einer. Das entsteht
    # auf mehreren Wegen — zweimal *Quader anlegen*, Duplizieren, ein Muster
    # ohne Abstand —, und keiner davon ist ein Fehler: Die Stückzahl gehört in
    # den Stapel, das Verteilen ans Anordnen (§25). *Auf dem Bett anordnen*
    # ist deshalb keine Reparatur, sondern der zweite Halbschritt, den die
    # Operationen bewusst nicht selbst tun — und ohne diesen Knopf muss man
    # ihn kennen, um ihn zu finden.
    "arrange.bodies_in_one_place": (ARRANGE_ON_BED,),
    # **Derselbe Sachverhalt eine Stufe weiter, und er stand ohne Knopf da.**
    # ``bodies_in_one_place`` meldet Körper, die genau aufeinander liegen;
    # ``collision`` meldet die, die sich teilweise durchdringen. Zwischen
    # beiden liegt kein Unterschied, den der Kunde träfe — er sieht zwei
    # Teile, die am selben Ort stehen, und will sie nebeneinander haben.
    #
    # Gefunden hat es die Nachbarsitzung beim Zählen der Befunde ohne
    # Handlung. Der Familientest daneben sah es nicht: Er gruppiert nach dem
    # Namen **hinter** dem Punkt, und ``collision`` ist damit eine Familie
    # mit einem Mitglied — immer gleich versorgt, immer grün.
    "arrange.collision": (ARRANGE_ON_BED,),
    # Dieselbe Handlung wie bei den Nachbarn: Was aneinander liegt, wird
    # nebeneinander gelegt. Der Befund kommt aus dem Teilen selbst, weil
    # nur die Operation weiß, dass die zwei Körper zusammengehören.
    "prepare.halves_in_place": (ARRANGE_ON_BED,),
    # Derselbe Sachverhalt, nur eine Stufe später gemessen: nicht die Szene
    # ragt hinaus, sondern die **Druckdatei**, die der Slicer daraus gemacht
    # hat (``gcode.printed_extent``). CuraEngine prüft seinen Bauraum nicht.
    # Es hilft dasselbe wie oben — anordnen, und wenn es allein nicht passt,
    # verkleinern.
    "gcode.off_the_bed": (ARRANGE_ON_BED, SCALE_TO_FIT),
    "export.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    "ingest.not_watertight": (REPAIR_AND_RETRY, SHOW_LOCATIONS),
    # **Der Satz sagte, dass nichts geschah — und bot nichts an.** „Es gibt
    # sehr kleine Einzelteile. Gelöscht wurde nichts.“ stand ohne Handlung
    # da, während ``repair`` sie mit ``small_components=True`` entfernt.
    # Gemessen am Korpus: zwei von zwanzig Modellen, beide Male eine
    # Warnung ohne Weg.
    "ingest.small_components": (REMOVE_SMALL_PARTS,),
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
    if finding.suggestions:
        # Im Fehlerdialog schließt „Abbrechen" das Fenster. Im Prüfbericht
        # ist kein Vorgang offen, den dieser Knopf abbrechen könnte; die Zeile
        # selbst bleibt einfach stehen. Dort ist CANCEL deshalb keine
        # Handlung, sondern ein irreführender Knopf ohne Handler.
        return tuple(action for action in finding.suggestions if action.id != CANCEL.id)
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
        suggestions=finding.suggestions,
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
#: **Eine Auswahl, keine Einheitentabelle.** Bis zum 27.08.2026 stand hier je
#: Schlüssel die Einheit, und damit entschied diese Tabelle ein zweites Mal,
#: was ``labels._VALUE_UNITS`` für den Tooltip schon entschieden hatte — mit
#: abweichendem Ergebnis und ohne die Umschaltung auf Zoll. Sie sagt jetzt nur
#: noch, **welche** Werte in die Zeile kommen und in welcher Reihenfolge;
#: **wie** sie geschrieben werden, sagt ``value_text``.
_LINE_VALUES: tuple[str, ...] = (
    "object",
    # „Ein Merkmal hat keinen Nachfolger mehr" — welches? Nach dem Einsetzen
    # eines Bausteins standen sechs wortgleiche Zeilen im Bericht, und nichts
    # daran war unterscheidbar; die Kennung stand längst im Befund, nur nie in
    # der Zeile. Derselbe Fund wie bei den zwei ausgehöhlten Klötzen darunter,
    # gefunden am 25.08.2026 bei der Verifikation im echten Fenster.
    "feature",
    "a",
    "b",
    "excess",
    "shared",
    # Aushöhlen sagte „Die Wandstärke stimmt im Rahmen des Rasters", ohne die
    # Wandstärke zu nennen — und wie viel Material dabei gespart wurde, also
    # die Frage, für die man die Operation überhaupt aufruft, stand nur im
    # Tooltip.
    "wall_mm",
    "removed_cm3",
)


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
            # **Dieselbe Quelle wie der Tooltip daneben**, und zwar seit der
            # Messung vom 27.08.2026: Die Zeile trug ihre Einheit selbst und
            # schrieb „1,2 mm · 3,456 cm³", während der Tooltip an demselben
            # Eintrag „Wandstärke: 1,20 mm · Entfernt: 3,5 cm³" sagte — zwei
            # Zahlen für denselben Wert, sichtbar in einem Blick. Und in Zoll
            # blieb die Zeile bei Millimetern stehen, weil eine feste Einheit
            # nicht umschalten kann. ``value_text`` beantwortet beides und
            # lässt Pfade, Kennungen und Versionsnummern unangetastet.
            else value_text(key, finding.values[key])
        )
        for key in _LINE_VALUES
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


def _feature_tip(feature_id: str, feature: Feature, document: Document | None) -> str:
    """Was dieses Merkmal ist, woher es kommt, und wie es heißt.

    Hier standen die Kennung und die Provenienz — die zwei technischsten
    Angaben, die es über ein Merkmal gibt: ``hole_1 · part:m3_screw``. Die
    Frage, die jemand stellt, der auf eine Zeile im Baum zeigt, ist eine
    andere, und Robert hat sie am 26.08.2026 wörtlich gestellt: *was ist das
    eigentlich*. Sie wird jetzt zuerst beantwortet.

    Die Reihenfolge ist die, in der man liest: **was** es ist samt seinem Maß,
    **woher** es kommt (der Schritt, den „Diesen Schritt ändern" öffnet), und
    zuletzt die **Kennung** — gebraucht wird sie nur, wenn man sie in ein
    Parameterfeld schreibt, und dafür genügt sie am Ende.

    **Es ist zugleich die zweite Kodierung, die Regel 18 verlangt.** Die
    Merkmalskarte *färbt*, was als Bohrung und was als Tasche gilt; ohne ein
    Wort daneben wäre die Farbe die einzige Aussage darüber.
    """
    lines = [feature_label(feature_id, feature)]
    # Erkannt oder erzeugt — das ist der Grund, aus dem es überhaupt da ist.
    # ``created_by`` trennt beides sauber: Was die Erkennung im Netz gefunden
    # hat, trägt keinen Schritt (§21.2).
    origin = _origin_text(feature.created_by, document)
    lines.append(origin or str(tr("Von der Erkennung gefunden")))
    lines.append(feature_id)
    return "\n".join(lines)


#: Wo am Gruppenknoten die Nummer seines Schrittes steht.
#:
#: Eine eigene Rolle und nicht ``UserRole``: Dort steht die Kennung des
#: Körpers, und die trägt der Knoten wie jede Zeile darunter — wer ihn
#: anklickt, hat das Teil gewählt. Die Schrittnummer ist eine zweite Auskunft
#: über dieselbe Zeile.
_STEP_ROLE = Qt.ItemDataRole.UserRole + 2


def _part_step(created_by: int | None, document: Document | None) -> tuple[str, int] | None:
    """Titel und Nummer des Schrittes, wenn er einen **Baustein** eingesetzt hat.

    Sonst ``None``. Gruppiert wird nur nach Bausteinen, und das hat einen
    Grund: Ein Baustein ist eine Sache mit einem Namen, die der Kunde als
    Ganzes eingesetzt hat — „Lochwand-Einhänger", nicht „drei Flächen und zwei
    Verrundungen". Eine Bohrung dagegen *ist* ein Merkmal; ein Knoten mit genau
    einem Kind darunter wäre eine Ebene, die nichts ordnet.
    """
    if created_by is None or document is None:
        return None
    for entry in document.ops:
        if entry.id != created_by:
            continue
        try:
            spec = REGISTRY.get(entry.op)
        except AppError:
            return None
        return (str(spec.title), created_by) if spec.category == "parts" else None
    return None


def _feature_item(item: QTreeWidgetItem, feature_id: str) -> QTreeWidgetItem | None:
    """Die Zeile dieses Merkmals — über alle Ebenen unter ``item``.

    Seit die Merkmale eines Bausteins unter seinem Knoten stehen, ist der Baum
    unter einem Körper zwei Ebenen tief. Wer nur die erste absucht, findet ein
    gruppiertes Merkmal nicht mehr.
    """
    for index in range(item.childCount()):
        child = item.child(index)
        if child is None:
            # Der Index liegt durch ``childCount`` im Bereich; der Qt-Stub
            # lässt dennoch ``None`` zu. Ein defensiver Wächter hält beides.
            continue
        if child.data(1, Qt.ItemDataRole.UserRole) == feature_id:
            return child
        deeper = _feature_item(child, feature_id)
        if deeper is not None:
            return deeper
    return None


def _visible_rows(item: QTreeWidgetItem | None) -> int:
    """Wie viele Zeilen dieser Ast zeigt: er selbst plus, was offen darunter steht.

    Der Nachbar von ``_feature_item`` und aus demselben Grund rekursiv — der
    Baum ist unter einem Körper zwei Ebenen tief, seit die Merkmale eines
    Bausteins unter seinem Knoten stehen.
    """
    if item is None:
        return 0
    rows = 1
    if item.isExpanded():
        rows += sum(_visible_rows(item.child(index)) for index in range(item.childCount()))
    return rows


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
    catalogRequested = Signal()
    """Den Bausteinkatalog öffnen — der kurze Weg vom gewählten Teil (§2.6).

    Ohne Kennung: Was gewählt ist, weiß das Fenster ohnehin, und der Katalog
    fragt es dort ab. Der Baum sagt nur, dass jemand ihn sehen will."""

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
        """Das Zuletzt-Gezeigte, damit sich der Baum ohne neue Auswertung
        neu zeichnen kann — beim Ausblenden ändert sich nur die Anzeige."""
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
            # §30: Nicht den Namen des Rechenkerns zeigen, sondern die Folge,
            # die für die nächste Handlung zählt. „Exakt" und „B-Rep" setzen
            # CAD-Wissen voraus und lassen das Dreiecksmodell wie die
            # schlechtere Wahl aussehen.
            kind = (
                tr("Flächen und Kanten einzeln bearbeitbar")
                if entry.kind == "brep"
                else tr("Einzelne Flächen und Kanten nicht bearbeitbar")
            )
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
                # Die ausführliche Folge steht im Tooltip; im schmalen Baum
                # muss die zweite Kodierung vollständig lesbar bleiben.
                item.setText(0, f"{entry.name}  ·  {tr('weiter bearbeitbar')}")
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
            # **Was aus einem Baustein kam, steht unter ihm.** Vierzehn
            # Merkmale flach untereinander sagen nicht, welche zusammengehören:
            # Der Kunde sieht sechs Verrundungen und findet den Einhänger
            # nicht, aus dem sie stammen (Befund Robert, 25.08.2026).
            groups: dict[int, QTreeWidgetItem] = {}
            for feature_id, feature in entry.features.items():
                # Name links, Maß rechts. Vorher stand die ganze Beschriftung
                # links und rechts der Typ („hole", „face") — links war damit
                # abgeschnitten, was rechts gefehlt hat.
                child = QTreeWidgetItem(
                    [feature_name(feature_id, feature), feature_measure(feature)]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, object_id)
                child.setData(1, Qt.ItemDataRole.UserRole, feature_id)
                tip = _feature_tip(feature_id, feature, document)
                # An beiden Spalten, wie der Regelsatz es für Zeilen verlangt:
                # Wer eine Zeile nicht versteht, zeigt auf das unverständliche
                # Wort und nicht auf die Zahl daneben.
                child.setToolTip(0, tip)
                child.setToolTip(1, tip)
                child.setStatusTip(0, tip.replace("\n", " · "))
                child.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, tip)

                part = _part_step(feature.created_by, document)
                if part is None:
                    item.addChild(child)
                    continue
                title, step = part
                group = groups.get(step)
                if group is None:
                    group = QTreeWidgetItem([title, ""])
                    # Der Knoten trägt seinen Körper wie jede Zeile darunter —
                    # wer ihn anklickt, hat das Teil gewählt und nicht nichts.
                    # Das Merkmal bleibt leer: Er ist keines, sondern ihr Dach.
                    group.setData(0, Qt.ItemDataRole.UserRole, object_id)
                    group.setData(1, Qt.ItemDataRole.UserRole, None)
                    # Und er weiß, aus welchem Schritt er kommt — daran hängt
                    # „Diesen Schritt ändern" (§21.2).
                    group.setData(0, _STEP_ROLE, step)
                    group.setToolTip(0, _origin_text(step, document))
                    groups[step] = group
                    item.addChild(group)
                group.addChild(child)
            for group in groups.values():
                group.setExpanded(True)
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
        """Die sichtbaren Zeilen — ein zugeklappter Ast zählt als eine.

        **Über alle Ebenen, nicht nur die erste.** Gezählt wurden lange die
        direkten Kinder, und das stimmte, solange der Baum zwei Ebenen hatte.
        Seit die Merkmale eines eingesetzten Bausteins unter seinem Knoten
        stehen, sind es drei — und dieser Knoten steht **immer** offen: Ein
        Körper mit sechs Verrundungen unter einem Einhänger meldete zwei
        Zeilen und zeigte acht. Die Karte bekam damit Höhe für zwei und einen
        Rollbalken, den es an dieser Stelle nicht geben soll.

        Dieselbe Ebenenblindheit hatte ``_restore`` schon einmal: Ein Klick im
        Viewport fand das Merkmal nicht, weil es eine Ebene tiefer lag. Wer
        eine Ebene einzieht, sucht die Stellen, die über Ebenen laufen.
        """
        return sum(
            _visible_rows(self.tree.topLevelItem(index))
            for index in range(self.tree.topLevelItemCount())
        )

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
                # **Über alle Ebenen, nicht nur die erste.** Die Merkmale eines
                # eingesetzten Bausteins stehen unter seinem Knoten; eine Suche
                # in den direkten Kindern findet dort den Knoten und nicht das
                # Merkmal. Ein Klick im Viewport auf eine Verrundung des
                # Einhängers markierte damit nichts, und aus dem Prüfbericht
                # führte der Sprung ins Leere.
                found = _feature_item(item, feature_id)
                if found is not None:
                    found.setSelected(True)
                    parent = found.parent()
                    while parent is not None:
                        parent.setExpanded(True)
                        parent = parent.parent()
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

        **Und die Karte wächst mit.** ``_restore`` klappt den Weg zum Merkmal
        auf, hier also bis zu zwei Knoten; ohne ``_fit`` bleibt die Karte auf
        der Höhe von vorher stehen, und die aufgeklappten Zeilen liegen unter
        ihrem Rand. In ``show_scene`` kommt ``_fit`` ohnehin danach — auf
        diesem Weg kam es nie.
        """
        self.tree.clearSelection()
        self._restore((object_id,), feature_id)
        self._fit()

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
                (
                    spec
                    for spec in REGISTRY.all()
                    if spec.consumes == 1 and spec.name not in MENU_TWINS
                ),
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

        **Ohne die zusammengelegten Zwillinge.** An jeder Fläche stand
        *Bohrung setzen* zweimal — ``drill_hole`` und ``drill_brep_hole``
        tragen denselben Titel, und der Kunde konnte nicht wissen, welche
        Zeile er nimmt; je nach Treffer bekam er einen anderen Rechenkern.
        Die Menüleiste legt das Paar seit je zusammen (``MENU_TWINS``): Der
        sichtbare Partner trägt den Eintrag, der andere ist über einen
        Umschalter in dessen Dialog erreichbar. Hier fehlte die Rechnung —
        dieselbe Frage an zwei Stellen, und eine kannte die Antwort nicht.

        **Weggelassen wird nur, wenn der Partner tatsächlich dabei ist.**
        Ein Zwilling, dessen Partner für diese Merkmalsart gar nicht gilt,
        wäre sonst spurlos weg statt zusammengelegt.

        """
        offered = REGISTRY.for_feature(kind)
        names = {spec.name for spec in offered}
        return tuple(spec for spec in offered if MENU_TWINS.get(spec.name) not in names)

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

        **Die Grenze gilt dem ganzen Menü, nicht nur den Operationen.** Über
        diesen Einträgen stehen noch Sichtbarkeit und der Skizzenschritt, und
        am Flächenklick ergab das dreizehn Zeilen gegen eine Grenze von zwölf.
        Sie zählen deshalb mit — gezählt am **gebauten** Menü und nicht als
        Zahl im Code: Beide Schritte darüber sind an Bedingungen geknüpft, und
        eine Konstante wäre in dem Augenblick falsch, in dem einer von ihnen
        ausbleibt. Trennstriche zählen nicht, sie sind keine Zeile, auf die man
        zeigt.

        Wer die drei mitzählt, muss eine zweite Gruppe falten — und die darf
        nicht „Ändern" sein, mit der Bohrung darin. Welche es wird, entscheidet
        ``folded_groups`` an der Reihenfolge der Menüleiste; hier steht nur die
        Zahl, gegen die es rechnet.
        """
        fixed = sum(1 for action in menu.actions() if not action.isSeparator())
        if len(entries) + fixed <= MAX_MENU_ROWS:
            for spec in entries:
                self._add_operation(menu, spec, kinds)
            return

        groups: dict[str, list[Any]] = {}
        for spec in entries:
            groups.setdefault(group_title(str(spec.category)), []).append(spec)

        # Jede gefaltete Kategorie spart ihre Einträge minus die eine Zeile,
        # die ihr Untermenü kostet. Eine Kategorie mit einem Eintrag spart
        # nichts und wird deshalb nie gefaltet — auch dann nicht, wenn es
        # danach immer noch zu lang ist. Dann ist das Menü eben lang; ein
        # Aufklappen, das nichts bündelt, macht es nicht kürzer, sondern nur
        # tiefer.
        folded = folded_groups(
            {title: len(found) for title, found in groups.items()},
            fixed=fixed,
            keep=groups_to_keep(entries),
        )

        direct = [spec for spec in entries if group_title(str(spec.category)) not in folded]
        for spec in direct:
            self._add_operation(menu, spec, kinds)
        if folded and direct:
            menu.addSeparator()
        # Mit dem Menü als Elternteil erzeugt, nicht über ``addMenu(titel)``:
        # sonst hält nichts auf der Python-Seite das Untermenü, und sein
        # C++-Objekt wird eingesammelt, während es noch im Menü hängt —
        # dieselbe Falle wie in der Menüleiste.
        parts_title = str(group_title("parts"))
        for title in sorted(folded):
            if title == parts_title:
                # **Wo die Bausteine gefaltet würden, tritt der Katalog an ihre
                # Stelle** — auf der obersten Ebene, nicht in einem Untermenü.
                # Er kostet dieselbe eine Zeile und zeigt Bilder statt
                # Textnamen (§2.6); siebzehn Zeilen wie
                # „Heat-Set-Einpressbuchse" sind genau die Darstellung, gegen
                # die der Katalog gebaut wurde. Und er bleibt damit **einen**
                # Klick vom gewählten Teil entfernt, wie Robert es zur
                # Bedingung gemacht hat — ein Untermenü machte daraus zwei,
                # und `test_a_chosen_part_reaches_the_catalogue_in_one_click`
                # hat das gefangen.
                #
                # **Was er nicht zeigt, steht in der Menüleiste.** Der
                # Katalog zeigt ``PARTS.all()``; *Deckel erzeugen* und
                # *Drehdeckel erzeugen* haben keine Kachel und sind hier
                # deshalb nicht erreichbar — sie stehen im Menü *Bausteine*.
                # Sie hier danebenzustellen kostete zwei Zeilen und riss die
                # Grenze (gemessen: 14 an einer Fläche); sie mitzufalten hieß,
                # *Bohrung setzen* eine Ebene tiefer zu legen. Welche der
                # beiden Fassungen die richtige ist, entscheidet Robert.
                self._add_catalog(menu)
                continue
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
        # Das Signal kommt in Koordinaten des gesamten Baums, ``itemAt`` und
        # der Ansichtsbereich erwarten dagegen Koordinaten ihres Viewports.
        # Ohne die Umrechnung trifft ein Rechtsklick unter der Kopfzeile die
        # Zeile darüber oder gar keine — gerade ein Bohrungsmenü verlor so
        # sein Zielmerkmal.
        viewport_position = self.tree.viewport().mapFrom(self.tree, position)
        item = self.tree.itemAt(viewport_position)
        if item is not None:
            # Der Rechtsklick meint die Zeile darunter. Ohne diese Auswahl
            # öffnete sich zwar das passende Kontextmenü, der Dialog erbte
            # aber ein vorher gewähltes Merkmal oder keines — ein Gewinde
            # stand dann nicht in der gerade angeklickten Bohrung.
            self.tree.clearSelection()
            item.setSelected(True)
            self.tree.setCurrentItem(item)
        menu = self.context_menu()
        if menu is not None:
            menu.exec(self.tree.viewport().mapToGlobal(viewport_position))

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

        **Und der Gruppenknoten eines Bausteins bietet ihn auch an.** Er ist
        kein Merkmal, sondern deren Dach — aber er ist die Zeile, die den
        Baustein beim Namen nennt, und wer den Einhänger ändern will, zeigt
        auf „Lochwand-Einhänger" und nicht auf eine seiner Flächen.
        """
        step = self._chosen_step()
        if step is None:
            feature = self._chosen_feature()
            if feature is None or feature.created_by is None:
                return
            step = feature.created_by
        change = menu.addAction(tr("Diesen Schritt ändern"))
        change.setStatusTip(tr("Öffnet den Schritt, der dieses Merkmal erzeugt hat."))
        change.triggered.connect(lambda _checked=False: self.stepRequested.emit(step))
        menu.addSeparator()

    def _chosen_step(self) -> int | None:
        """Die Schrittnummer der gewählten Zeile — nur Gruppenknoten haben eine."""
        items = self.tree.selectedItems()
        if len(items) != 1:
            return None
        value: int | None = items[0].data(0, _STEP_ROLE)
        return value

    def _add_catalog(self, menu: QMenu) -> None:
        """„Baustein einsetzen …" — der kurze Weg vom gewählten Teil zum Katalog.

        Die Bausteine haben seit dem 29.08.2026 keinen Menüort mehr: Ein
        räumliches Teil als Textzeile zu führen ist die schlechtere
        Darstellung (§2.6), und im Menü standen neunundzwanzig davon in sechs
        Untermenüs. Der Katalog mit Bildern war schon immer der bessere Ort —
        er lag nur in *Datei*, also dort, wo niemand hinsieht, der gerade auf
        eine Fläche zeigt.

        **Roberts Bedingung zu dieser Änderung**, und sie ist der Grund für
        diesen Eintrag: „solange man einfach zum Katalog kommt, wenn man das
        Teil gewählt hat". Von hier aus stimmt beides — die Auswahl steht, und
        der Katalog weiß dadurch, dass er den Hinweis auf die fehlende Stelle
        **nicht** zeigen muss.

        **Er steht an der Stelle, an der die Bausteine gefaltet würden — nicht
        fest oben im Menü** (:meth:`_add_operations`). Das ist eine
        Berichtigung, keine Feinheit: Zuerst stand er unbedingt oben, also auch
        dort, wo die Bausteine ohnehin flach danebenstanden. Am Merkmalsmenü
        einer Bohrung gemessen:

            Operationen für „hole"                  10
            Zeilen darüber (mit diesem Eintrag)      3
            13 > 12  ->  „Bausteine" wird gefaltet

        Ohne ihn sind es zwölf, also genau die Grenze, und alles steht flach.
        Die eine Zeile hat damit fünf Operationen eine Ebene tiefer geschoben —
        *Kugellager einsetzen*, *Heat-Set-Einpressbuchse*, *Mutternfalle*,
        *Schraube*, *Druckbares Gewinde* —, und das sind an einer Bohrung
        genau die fünf, die überhaupt in Frage kommen. §18.5 nennt diesen Ort
        „die wichtigste Einzelfunktion"; :meth:`_add_operations` rechnet
        darüber vor, dass ein gesparter Zeilenplatz gegen einen zusätzlichen
        Klick ein schlechtes Geschäft ist. Beides stand da, und die Zeile kam
        trotzdem hinzu: **ein Diff zeigt seine eine Zeile, nicht die Grenze,
        die sie reißt.**

        Am neuen Ort kostet er keine eigene Zeile: Er tritt an die Stelle des
        Untermenüs, das die Bausteine sonst bekämen. Wo sie flach passen — an
        einer Bohrung —, stehen sie flach und der Eintrag entfällt; der Katalog
        bleibt dann über *Datei → Bausteinkatalog …*, über das Menü *Bausteine*
        und über Strg+K erreichbar, also über drei Wege, die immer offen sind.

        **Ein Zwischenstand legte ihn stattdessen in ein Untermenü**, und
        dieser Docstring hat ihn eine Weile als Sollzustand beschrieben. Das
        machte aus Roberts einem Klick zwei;
        ``test_a_chosen_part_reaches_the_catalogue_in_one_click`` hat es
        gefangen. Was dabei offen bleibt, steht in
        :meth:`_add_operations` — die zwei Baustein-Operationen **ohne** Kachel
        sind auf diesem Weg nicht erreichbar und stehen in der Menüleiste.
        """
        insert = menu.addAction(tr("Baustein einsetzen …"))
        insert.setStatusTip(
            tr("Öffnet den Katalog mit Bildern — Mutternfalle, Rastnase, Scharnier und andere.")
        )
        insert.triggered.connect(lambda _checked=False: self.catalogRequested.emit())

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


class _CompactParameterUnitBox(QComboBox):
    """Zeigt die gewählte Einheit kurz und die Auswahlliste ausführlich.

    Die linke Karte ist 260 Pixel breit. Ein geschlossener Eintrag wie
    „mm — Länge“ beanspruchte dort fast so viel Platz wie die Zahl selbst;
    aufgeklappt ist die Erklärung dagegen genau richtig. Deshalb zeichnet nur
    die geschlossene Auswahl den gespeicherten Code. Die Einträge im Menü
    bleiben unverändert und erklären weiterhin ihre Bedeutung.
    """

    def _compact_text(self) -> str:
        # Keine Einheit ist absichtlich leer. Im geöffneten Menü steht weiter
        # der übersetzte Satz „ohne Einheit“; ein erfundenes Symbol in der
        # geschlossenen Anzeige wäre dagegen ein weiterer Oberflächentext.
        return str(self.currentData() or "")

    def paintEvent(self, _event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = self._compact_text()
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt gibt den Namen
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        codes = [str(self.itemData(index) or "") for index in range(self.count())]
        width = max((self.fontMetrics().horizontalAdvance(code) for code in codes), default=0)
        content = QSize(width + 2 * TIGHT, super().sizeHint().height())
        return self.style().sizeFromContents(
            QStyle.ContentsType.CT_ComboBox,
            option,
            content,
            self,
        )

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt gibt den Namen
        return self.sizeHint()


class ParameterPanel(QWidget):
    """Benannte Projektmaße; an einer Zahl zu drehen baut das Modell
    neu (§13).
    """

    parameterEdited = Signal(str, float)
    parameterUnitEdited = Signal(str, str)
    """Eine feste Einheit wurde in der Zeile gewählt."""
    heightChanged = Signal()
    """Die frei gesetzte Seitenkarte soll ihre Geometrie neu verteilen."""
    addRequested = Signal()
    """Der Nutzer will ein Maß benennen — das Fenster öffnet den Dialog."""
    limitsRequested = Signal(str)
    """Grenzen, Einheit oder Ausdruck eines vorhandenen Maßes ändern.

    Trägt den **Namen** des Parameters. Grenzen waren anlegbar und nie
    änderbar: Die Leiste liest ``minimum``/``maximum`` als Spinbox-Grenzen,
    und wer eine Obergrenze zu eng gesetzt hatte, fand ein Feld, das ohne ein
    Wort klemmt — *Parameter anlegen …* wies den Namen ab, und ein dritter Weg
    fehlte (§2.1: keine Sackgassen).
    """

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
        self._unit_editors: dict[str, QComboBox] = {}
        self._detail_buttons: dict[str, QToolButton] = {}
        """Der sichtbare Weg zu Grenzen, Einheit und Ausdruck jeder Zeile."""
        self._rows: dict[QWidget, str] = {}
        """Welches Widget zu welchem Parameter gehört — für das Kontextmenü.

        Beide Hälften der Zeile stehen darin: Wer mit rechts auf die
        Beschriftung zeigt, meint dieselbe Zeile wie der, der auf das Feld
        zeigt.
        """
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
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

        Nach ``removeRow`` und dem Neuaufbau trägt das äußere Layout noch
        seinen zwischengespeicherten Höhenwert vom alten Inhalt. Auf Windows
        kam dessen ``LayoutRequest`` zu spät für die frei gesetzte
        Überlagerung: Aus drei normalen Zeilen wurden dadurch elf Pixel hohe
        Schlitze. Deshalb wird erst im nächsten Ereignisschritt gemessen; dann
        hat Qt die neuen Kindgrößen in beide Layoutstufen aufgenommen.
        """
        self._form.invalidate()
        self._outer.invalidate()
        self.updateGeometry()
        QTimer.singleShot(0, self, self._apply_fitted_height)

    def _apply_fitted_height(self) -> None:
        """Die inzwischen berechnete Inhaltshöhe an Karte und Wirt melden."""
        self._form.activate()
        self._outer.activate()
        height = self._outer.sizeHint().height()
        if height == self.minimumHeight():
            return
        self.setMinimumHeight(height)
        self.updateGeometry()
        self.heightChanged.emit()

    def parameter_at(self, position: QPoint) -> str | None:
        """Welcher Parameter an dieser Stelle steht — oder ``None``.

        ``childAt`` gibt das **tiefste** Kind zurück, und eine ``NumberSpin``
        hat ein eigenes Eingabefeld darin: Ohne den Gang nach oben trifft ein
        Rechtsklick mitten in die Zahl niemanden.
        """
        widget: QWidget | None = self.childAt(position)
        while widget is not None and widget is not self:
            name = self._rows.get(widget)
            if name is not None:
                return name
            widget = widget.parentWidget()
        return None

    def context_menu(self, position: QPoint) -> QMenu | None:
        """Das Menü zur Zeile an dieser Stelle — oder ``None``, wo keine steht.

        Vom Öffnen getrennt, wie beim Objektbaum daneben: ``exec`` blockiert,
        und wer einen Eintrag prüfen will, braucht das Menü und nicht das
        Fenster darüber.

        Kein Menü auf leerer Fläche: Ein Kontextmenü mit einem einzigen
        ausgegrauten Eintrag sagt nur, dass man danebengeklickt hat, und das
        weiß man schon.
        """
        name = self.parameter_at(position)
        if name is None:
            return None
        menu = QMenu(self)
        # Ein Menü zeigt Hinweise nur, wenn man es ihm sagt — sonst kommt der
        # Satz an und Qt zeigt ihn nie.
        menu.setToolTipsVisible(True)
        entry = menu.addAction(tr("Ändern …"))
        note = tr("Untergrenze, Obergrenze, Einheit und Ausdruck dieses Maßes — rücknehmbar.")
        entry.setToolTip(note)
        entry.setStatusTip(note)
        entry.triggered.connect(lambda _checked=False, key=name: self.limitsRequested.emit(key))
        return menu

    def _on_context_menu(self, position: QPoint) -> None:
        menu = self.context_menu(position)
        if menu is not None:
            menu.exec(self.mapToGlobal(position))

    def _remember_row(self, name: str, field: QWidget) -> None:
        """Beide Hälften der Zeile dem Parameter zuordnen.

        Die Beschriftung baut ``addRow`` selbst aus der Zeichenkette;
        ``labelForField`` gibt sie heraus — dieselbe Stelle, an der auch der
        Operationsdialog seine Beschriftung wiederfindet.
        """
        self._rows[field] = name
        label = self._form.labelForField(field)
        if label is not None:
            self._rows[label] = name

    def _queue_parameter_edit(self, name: str, value: float) -> None:
        """Meldet eine fertige Eingabe erst nach dem Signal der Spinbox.

        ``show_document`` baut die Zeilen nach einer Änderung neu auf. Geschah
        das noch innerhalb von ``QDoubleSpinBox.valueChanged``, löschte Qt auf
        Windows das gerade sendende Eingabefeld; der Prozess verschwand ohne
        Fehlermeldung. Der nächste Ereignisschritt lässt das Signal vollständig
        zurückkehren, bevor die Leiste neu gebaut wird.
        """
        QTimer.singleShot(0, self, lambda: self.parameterEdited.emit(name, value))

    def _queue_parameter_unit_edit(self, name: str, unit: str) -> None:
        """Meldet auch die Einheit erst nach dem Signal ihrer Auswahlliste."""
        QTimer.singleShot(0, self, lambda: self.parameterUnitEdited.emit(name, unit))

    def _unit_activated(self, index: int) -> None:
        """Übernimmt die feste Auswahl, ohne den sendenden Kasten zu löschen."""
        editor = self.sender()
        if not isinstance(editor, QComboBox):
            return
        name = str(editor.property("parameterName") or "")
        if name:
            self._queue_parameter_unit_edit(name, str(editor.itemData(index) or ""))

    def _unit_editor(self, name: str, selected: str) -> QComboBox:
        """Die kompakte, nicht editierbare Einheitenauswahl einer Zeile."""
        editor = _CompactParameterUnitBox(self)
        fill_parameter_units(editor, selected)
        editor.setProperty("parameterName", name)
        editor.setAccessibleName(tr("Einheit"))
        editor.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        editor.activated.connect(self._unit_activated)
        self._unit_editors[name] = editor
        return editor

    def _details_clicked(self) -> None:
        """Öffnet die erweiterten Angaben der angeklickten Parameterzeile."""
        button = self.sender()
        if not isinstance(button, QToolButton):
            return
        name = str(button.property("parameterName") or "")
        if name:
            self.limitsRequested.emit(name)

    def _add_parameter_row(self, name: str, title: str, value: QWidget, unit: QComboBox) -> None:
        """Zahl, Einheit und sichtbaren Änderungsweg als eine Zeile."""
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
        layout.addWidget(value, 1)
        layout.addWidget(unit)
        details = QToolButton(row)
        # Das ausführliche Wort würde neben Zahl und Einheit die 260-Pixel-
        # Karte sprengen. Die Ellipse ist der sichtbare „mehr“-Knopf; Tooltip
        # und zugänglicher Name sagen ohne Symbolwissen, was dahinterliegt.
        # Auch das sichtbare Symbol kommt aus dem Katalog (Regel 20). Jede
        # Übersetzung von „Ändern …“ endet mit derselben typografischen
        # Ellipse; nur sie wird in der schmalen Zeile gezeichnet.
        details.setText(tr("Ändern …")[-1])
        details.setAutoRaise(True)
        note = tr("Untergrenze, Obergrenze, Einheit und Ausdruck dieses Maßes — rücknehmbar.")
        details.setToolTip(note)
        details.setStatusTip(note)
        details.setAccessibleName(tr("Parameter ändern"))
        details.setProperty("parameterName", name)
        details.clicked.connect(self._details_clicked)
        layout.addWidget(details)
        self._detail_buttons[name] = details
        self._form.addRow(title, row)
        self._remember_row(name, row)

    def show_document(self, document: Document) -> None:
        while self._form.rowCount():
            self._form.removeRow(0)
        self._editors.clear()
        self._unit_editors.clear()
        self._detail_buttons.clear()
        # **Vor dem Neuaufbau leeren, nicht danach.** ``removeRow`` löscht die
        # Widgets der alten Zeilen; ein Eintrag, der auf ein totes C++-Objekt
        # zeigt, beantwortet den nächsten Rechtsklick mit einem Absturz.
        self._rows.clear()

        if not document.parameters:
            self._empty = QLabel(_empty_parameters_text(), self)
            self._empty.setWordWrap(True)
            fit_wrapped(self._empty)
            self._form.addRow(self._empty)
            self._fit()
            return

        for name, parameter in document.parameters.items():
            unit = self._unit_editor(name, str(parameter.unit or ""))
            if parameter.expression:
                # Abgeleitete Werte werden gezeigt, nicht bearbeitet — der Ausdruck
                # besitzt sie.
                label = QLabel(localised(f"{parameter.value:.2f}"), self)
                label.setToolTip(parameter.expression)
                # Wie die Spinbox darf auch die reine Anzeige in der festen
                # linken Karte den Restplatz nutzen. Ohne ``Ignored`` machte
                # allein „42,00“ die Karte breiter als ihre vorgesehenen
                # 260 Pixel, obwohl die echte Schrift dort bequem hineinpasst.
                label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
                self._add_parameter_row(name, f"{parameter.title or name}", label, unit)
                # Auch die abgeleitete Zeile: Ihr Ausdruck ist genau das, was
                # man an ihr ändern will, und bearbeiten lässt sie sich sonst
                # nirgends.
                continue
            editor = NumberSpin(self)
            editor.setDecimals(2)
            editor.setMinimum(parameter.minimum if parameter.minimum is not None else -100_000.0)
            editor.setMaximum(parameter.maximum if parameter.maximum is not None else 100_000.0)
            editor.setValue(parameter.value)
            editor.setKeyboardTracking(False)
            # Der Wertebereich bestimmt sonst die Mindestbreite der Spinbox:
            # ±100 000 verlangt 156 Pixel, obwohl die aktuelle Zahl kurz ist.
            # In der festen linken Karte darf das Feld schrumpfen und nutzt den
            # Platz, der nach Einheit und Mehr-Knopf übrig bleibt.
            editor.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            editor.valueChanged.connect(
                lambda value, key=name: self._queue_parameter_edit(key, value)
            )
            self._editors[name] = editor
            self._add_parameter_row(name, f"{parameter.title or name}", editor, unit)
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
    noteRequested = Signal(str)
    """Was der Verlauf dem Nutzer zu sagen hat — das Fenster zeigt es an.

    Bisher nur für den Doppelklick, der nichts öffnen kann. Als Signal und
    nicht als eigene Zeile im Panel: Die Statuszeile ist der Ort für eine
    Auskunft, die eine Handlung begleitet, und der Verlauf hat keine."""
    removalRequested = Signal(object)
    """Die gewählten Operationen sollen nach einer Nachfrage gelöscht werden."""
    bakeRequested = Signal(int)
    """Der Stand einer Formsitzung soll festgeschrieben werden (Entscheidung D).

    Als Signal und nicht als Aufruf: Die Nachfrage stellt das Fenster, denn sie
    ist die einzige im ganzen Programm — die Handlung ist nicht folgenlos
    rücknehmbar, und Regel 19 gilt nur für die, die es sind."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.list = QListWidget(self)
        self.list.setAccessibleName(tr("Verlauf"))
        # **Mehrere Schritte wählbar** (§24.5): Ein Rezept nimmt beliebige
        # ``op_ids``, und solange der Verlauf nur einen Index kannte, wanderte
        # der ganze Stapel in jeden Baustein — wer einen Halter aus einem
        # gewachsenen Projekt herauslöst, bekam ein Teil, das Dinge baut, die
        # niemand bestellt hat. Dieselbe Auswahlart wie im Objektbaum daneben,
        # damit Strg- und Umschalt-Klick überall dasselbe tun.
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemDoubleClicked.connect(self._on_activated)
        self.list.setToolTip(
            tr(
                "Doppelklick öffnet die Operation und ihre Parameter. "
                "Mit Strg oder Umschalt mehrere Schritte wählen."
            )
        )
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
        self.remove_action = QAction(tr("Schritt löschen …"), self.list)
        self.remove_action.setShortcut(QKeySequence("Del"))
        self.remove_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.remove_action.triggered.connect(self._request_selected_removal)
        self.list.addAction(self.remove_action)
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
        deleted: set[int] = set()
        for transaction in document.transactions:
            changes = transaction.changes
            if changes is None or changes.after.edited_ops is None:
                continue
            before = changes.before.edited_ops or {}
            for op_id, version in changes.after.edited_ops.items():
                if version is not None:
                    continue
                deleted.add(op_id)
                previous = before.get(op_id)
                if previous is not None:
                    titles.setdefault(op_id, _op_title(previous.op))
        deleted_ids = frozenset(deleted)
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
            active_ops = tuple(op_id for op_id in transaction.ops if op_id not in deleted_ids)
            if transaction.ops and not active_ops:
                item.setText(f"{item.text()}  ({tr('gelöscht')})")
                font = QFont(item.font())
                font.setStrikeOut(True)
                item.setFont(font)
                item.setForeground(QColor(UNDONE_COLOUR))
            if len(transaction.ops) == 1 and active_ops:
                item.setData(Qt.ItemDataRole.UserRole, transaction.ops[0])
            # **Die Zeile trägt auch, was sie umfasst.** ``UserRole`` bleibt
            # die *eine* Operation zum Öffnen — eine Transaktion aus vier
            # Schritten hat keine, und das ist richtig, denn welchen sollte ein
            # Doppelklick zeigen. Für die Mehrfachauswahl zählt dagegen die
            # ganze Transaktion: Wer „Teilung in vier" wählt, meint alle vier.
            item.setData(OPS_ROLE, active_ops)
            self.list.addItem(item)

            if len(transaction.ops) > 1:
                for op_id in transaction.ops:
                    child = QListWidgetItem(f"    {op_id}  {titles.get(op_id, '')}")
                    if op_id not in deleted_ids:
                        child.setData(Qt.ItemDataRole.UserRole, op_id)
                        child.setData(OPS_ROLE, (op_id,))
                    else:
                        child.setText(f"{child.text()}  ({tr('gelöscht')})")
                        font = QFont(child.font())
                        font.setStrikeOut(True)
                        child.setFont(font)
                        child.setForeground(QColor(UNDONE_COLOUR))
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

    def selected_operations(self) -> tuple[int, ...]:
        """Die gewählten Schritte, aufsteigend und ohne Doppelte.

        Der Ausschnitt für ein Rezept (§24.5). Eine gewählte Transaktion zählt
        mit **allen** ihren Operationen: Wer „Teilung in vier" anklickt, meint
        die vier und nicht eine davon.

        **Aufsteigend, weil ein Stapel eine Reihenfolge hat.** Angeklickt wird
        in beliebiger Folge, gerechnet wird von unten nach oben; ein Rezept aus
        „Schritt 7, dann Schritt 3" gibt es nicht.

        Leer heißt leer und nicht „alles". Was bei leerer Auswahl geschieht,
        entscheidet der Aufrufer — das Fenster nimmt dann den ganzen Stapel,
        und es schreibt das auch hin.
        """
        chosen: set[int] = set()
        for item in self.list.selectedItems():
            ops = item.data(OPS_ROLE)
            if ops:
                chosen.update(int(op_id) for op_id in ops)
        return tuple(sorted(chosen))

    def _on_activated(self, item: QListWidgetItem) -> None:
        """Doppelklick: die Operation öffnen — oder sagen, warum nicht.

        Eine Transaktion aus mehreren Operationen trägt keine ``UserRole``;
        welche der vier sollte der Doppelklick zeigen? Ihre Schritte stehen
        eingerückt darunter und tragen je eine.

        **Stumm bleiben darf er deswegen nicht.** Sechs der neun Beispieltouren
        lehren genau diese Geste als *den* Weg zum Ändern („Öffnen Sie die
        Mutternfalle mit einem Doppelklick im Verlauf"), und der Tooltip der
        Liste verspricht sie ohne Einschränkung. Eine Handlung, die nichts tut,
        sagt, was stattdessen geht (Regel 17, §2.1).
        """
        op_id = item.data(Qt.ItemDataRole.UserRole)
        if op_id is not None:
            self.operationActivated.emit(int(op_id))
            return
        if item.data(OPS_ROLE):
            self.noteRequested.emit(
                tr(
                    "Dieser Schritt fasst mehrere Operationen zusammen. "
                    "Öffnen lässt sich jede einzeln — die eingerückten Zeilen darunter."
                )
            )

    def _request_selected_removal(self) -> None:
        """Die sichtbare Auswahl zum bestätigten Löschen weiterreichen."""
        chosen = self.selected_operations()
        if chosen:
            self.removalRequested.emit(chosen)

    def _operations_for_context(self, item: QListWidgetItem | None) -> tuple[int, ...]:
        """Die sichtbare Mehrfachauswahl oder allein die rechts angeklickte Zeile."""
        clicked = tuple(item.data(OPS_ROLE) or ()) if item is not None else ()
        if item is not None and item.isSelected():
            return self.selected_operations()
        if item is not None and clicked:
            self.list.clearSelection()
            item.setSelected(True)
            self.list.setCurrentItem(item)
        return tuple(int(op_id) for op_id in clicked)

    def _on_context_menu(self, position: QPoint) -> None:
        """Was man mit einem Schritt tun kann, dort, wo er steht.

        Bisher gab es nur den Doppelklick, und den findet, wer ihn probiert.
        Angeboten wird, was der Stapel wirklich kann: einen Schritt öffnen,
        seine Zahlen ändern oder ihn samt abhängigen Schritten löschen
        (§15.4). Das Löschen bleibt eine Transaktion und damit rücknehmbar.
        """
        item = self.list.itemAt(position)
        op_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        op_ids = self._operations_for_context(item)
        if not op_ids:
            return

        menu = QMenu(self)
        single_op = int(op_id) if op_id is not None and len(op_ids) == 1 else None
        if single_op is not None:
            action = menu.addAction(tr("Parameter ändern …"))
            action.triggered.connect(
                lambda _checked=False, chosen=single_op: self.operationActivated.emit(chosen)
            )
        remove = menu.addAction(tr("Schritt löschen …"))
        remove.triggered.connect(
            lambda _checked=False, chosen=op_ids: self.removalRequested.emit(chosen)
        )
        if single_op is not None and single_op in self._bakeable:
            # Nur an einer Formsitzung, und nur an einer, die noch gerechnet
            # wird: Ein Eintrag, der an jedem Schritt steht und an fast keinem
            # etwas tut, ist einer, den man nicht mehr liest.
            frozen = menu.addAction(tr("Stand festschreiben …"))
            frozen.triggered.connect(
                lambda _checked=False, chosen=single_op: self.bakeRequested.emit(chosen)
            )
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
        for finding, members in _bundled(
            _by_severity(result.scene.report.findings if result else ())
        ):
            self._append(finding, members=members)
        self._count_up()
        self._measure_up(result)
        self._refilter()
        self._show_controls()
        self._grew()
        # Nach dem Filtern, denn eine ausgeblendete Zeile ist keine Antwort.
        self._preselect()

    def add_findings(self, findings: list[Finding], *, replacing_source: str | None = None) -> None:
        """Hängt Befunde an, die nicht aus der Auswertung kamen — die
        G-Code-Gegenprobe etwa (§28.2). Sie behalten ihre eigene
        Herkunft (§22.5).

        Was schon dasteht, kommt nicht noch einmal. Mehrere Prüfungen sehen
        dieselbe Sache: „Kollisionen prüfen" und die Exportprüfung melden beide,
        dass ein Körper über den Bauraum hinaussteht, und nach beiden stand die
        Zeile zweimal da. Zweimal gemeldet ist nicht zweimal passiert — ein
        Zähler daneben wäre eine Zahl, die etwas anderes behauptet.

        ``replacing_source`` räumt zuerst ab, was diese Herkunft schon gemeldet
        hat. Die G-Code-Befunde beschreiben die **jeweils letzte** Druckdatei —
        Regel 14 gibt mit der Herkunft das Kriterium frei Haus. Ohne das stand
        nach drei Läufen dreimal die Druckzeit da, jede mit anderer Zahl und
        darum nie „dasselbe" für die Erkennung darüber (Roberts Foto,
        30.08.2026): Eine veraltete Aussage über eine ersetzte Datei ist keine
        Historie, sondern Irreführung.
        """
        if replacing_source is not None:
            for row in range(self.list.count() - 1, -1, -1):
                entry = self.list.item(row).data(Qt.ItemDataRole.UserRole)
                if entry is not None and entry.source == replacing_source:
                    self.list.takeItem(row)
        # Je Identität die Zeile, nicht nur die Menge: Derselbe Sachverhalt
        # kann mit zwei Gewichten eintreffen — die Auswertung meldet „unter dem
        # Druckbett" als Hinweis (ein Klick behebt es), die Exportprüfung beim
        # Schreiben als Warnung (der Klick ist nicht passiert). Die schwerere
        # Fassung ersetzt die leichtere; andersherum bliebe die Warnung stehen,
        # obwohl längst nur noch der Hinweis gilt — deshalb ersetzt auch die
        # leichtere die schwerere, sobald derselbe Sachverhalt leichter
        # wiederkommt. Was gleich schwer ist, bleibt wie bisher stehen.
        rows = {
            _identity(self.list.item(row).data(Qt.ItemDataRole.UserRole)): row
            for row in range(self.list.count())
        }
        fresh = []
        for finding in findings:
            key = _identity(finding)
            found_at = rows.get(key)
            if found_at is not None:
                standing = self.list.item(found_at).data(Qt.ItemDataRole.UserRole)
                if standing.severity == finding.severity:
                    continue
                self.list.takeItem(found_at)
                rows = {
                    _identity(self.list.item(index).data(Qt.ItemDataRole.UserRole)): index
                    for index in range(self.list.count())
                }
            self._append(finding)
            rows[key] = self.list.count() - 1
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

    def _preselect(self) -> None:
        """Den obersten Befund vorwählen, der eine Handlung anbietet.

        Die Knopfzeile unter der Liste zeigt die Handlungen des **gewählten**
        Befunds — und gewählt war nach dem Öffnen keiner. Der Kunde sah damit
        eine Liste und darunter nichts; dass ein Klick auf eine Listenzeile
        Knöpfe freischaltet, muss man wissen, und §2.7 verspricht anklickbare
        Handlungen und nicht auffindbare.

        Gemessen am häufigsten Fall überhaupt, dem ersten Öffnen eines
        Modells: ``block_with_rounded_edge.stl`` liegt von Z -10 bis +10, der
        Bericht meldet ``arrange.below_bed``, und *Auf das Bett setzen* löst es
        mit einem Klick. Vor der Vorauswahl standen dort null Knöpfe, nach
        einem Klick auf die Zeile einer — der Weg zur Lösung war einen Klick
        länger als nötig, und dieser Klick stand nirgends geschrieben.

        Drei Bedingungen, und jede hat ihren Grund:

        * **Nur ohne bestehende Wahl.** Eine Auswahl des Kunden zu
          überschreiben wäre schlimmer als keine Vorauswahl (§2.4).
        * **Nur sichtbare Zeilen.** ``_refilter`` blendet aus, was nicht zum
          Filter passt; eine versteckte Zeile vorzuwählen zeigt Knöpfe zu einem
          Befund, den niemand sieht.
        * **Nur mit angebotener Handlung.** Der oberste Befund ist der
          schwerste, aber nicht immer der, der etwas anzubieten hat —
          ``ingest.welded`` steht regelmäßig darüber und hat keine. Ihn
          vorzuwählen ließe die Zeile wieder leer.
        """
        if self.list.selectedItems():
            return
        handlers = handlers_of(self)
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.isHidden():
                continue
            finding = item.data(Qt.ItemDataRole.UserRole)
            if any(action.id in handlers for action in actions_for(finding)):
                self.list.setCurrentRow(row)
                return

    def _show_first_of(self, keys: list[tuple[Any, ...]]) -> None:
        """Zum obersten der genannten Befunde scrollen."""
        for row in range(self.list.count()):
            item = self.list.item(row)
            if _identity(item.data(Qt.ItemDataRole.UserRole)) in keys:
                self.list.scrollToItem(item)
                return

    def _append(self, finding: Finding, members: list[Finding] | None = None) -> None:
        """Einen Befund als Eintrag anhängen — oder ein Bündel als eine Zeile.

        ``members`` trägt bei einer Sammelzeile alle gebündelten Befunde
        (:func:`_bundled`). Die Zahl steht im Text der Zeile selbst und nicht
        nur im Tooltip (Regel 18: die Menge ist die Aussage, und sie braucht
        die sichtbare Kodierung); für die Zählung der Kopfzeile steht sie in
        :data:`_BUNDLE_ROLE`, damit ein Kernbefund mit eigenem ``count``-Wert
        weiter als eine Zeile zählt.
        """
        if members:
            names = ", ".join(
                str(one.values.get("feature", one.object_id or "?")) for one in members[:15]
            )
            if len(members) > 15:
                names += f" … (+{len(members) - 15})"
            # Die Zeile trägt Zahl und Satz — die Liste der Betroffenen wäre
            # dort die nächste Flut und gehört in den Tooltip. ``feature``
            # steht in ``_LINE_VALUES``, deshalb bekommt die Zeile den Satz
            # direkt und nicht ``_line_for`` über die Bündel-Werte.
            item = QListWidgetItem(f"{len(members)} × {finding.message}")
            item.setData(_BUNDLE_ROLE, len(members))
            finding = dataclasses.replace(
                finding,
                object_id=None,
                values={"count": len(members), "feature": names},
            )
        else:
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
            item = self.list.item(row)
            finding: Finding = item.data(Qt.ItemDataRole.UserRole)
            # Eine Sammelzeile (siehe ``_bundled``) zählt als das, was sie
            # bündelt — die Kopfzeile sagt sonst „6 Hinweise" über 123.
            counts[finding.severity] += item.data(_BUNDLE_ROLE) or 1
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


def open_section(content: QWidget) -> None:
    """Klappt den Abschnitt auf, in dem dieser Inhalt steckt — falls er zu ist.

    Der Gegenpart zu :func:`collapsible`, und er fehlte: Wer einen Bereich
    hervorhebt, muss ihn erst sichtbar machen. „Sehen Sie links in den
    Verlauf" ließ einen Rahmen um einen zugeklappten Abschnitt aufleuchten —
    also um eine Kopfzeile, unter der nichts steht.

    Gesucht wird unter den **direkten** Kindern des Wrappers: Der Inhalt hat
    eigene Knöpfe, und einer davon wäre sonst der erste Treffer. Steckt das
    Widget in keinem Abschnitt — der Prüfbericht sitzt in einem Reiter —,
    geschieht nichts.
    """
    wrapper = content.parentWidget()
    if wrapper is None:
        return
    for child in wrapper.children():
        if isinstance(child, QToolButton) and child.objectName() == "sectionHeading":
            if not child.isChecked():
                child.setChecked(True)
            return


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
