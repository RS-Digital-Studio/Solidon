"""Welche Operation eine Datei einliest — für Fenster und Kommandozeile.

Die Entscheidung ist klein und stand zweimal im Code: STEP nimmt den exakten
Kern, eine flache Zeichnung wird extrudiert, alles andere ist ein Netz, und bei
einer 3MF-Baugruppe steht die Körperzahl in der Datei. Das Fenster traf sie
vollständig (``Session.import_payload``); die Kommandozeile legte immer ``load``
auf den Stapel.

Was dabei herauskam, ist die schlechteste Sorte Fehler — einer, der eine
Unwahrheit sagt: ``solidon3d import projekt.p3d teil.step`` antwortete „Dieses
Dateiformat kann nicht gelesen werden.", für ein Format, das dieselbe Anwendung
im Fenster einliest. Dasselbe für SVG und DXF.

Deshalb steht sie jetzt hier: eine Stelle, zwei Aufrufer, kein Weg
auseinanderzulaufen. Der Titel gehört dazu — er steht im Verlauf, und „STEP
laden" gegen „Modell laden" ist Teil derselben Entscheidung.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.core.brep import step as brep_step
from app.core.export import threemf
from app.core.ingest.loader import check_limits, check_unpacked
from app.core.ingest.outline import is_outline
from app.core.scene.history import OperationDraft
from app.i18n import TranslatableText, _

#: Der Titel der Transaktion je Weg. Im Verlauf steht er, nicht der Op-Name.
_TITLES: Final[dict[str, TranslatableText]] = {
    "load_step": _("STEP laden"),
    "load_outline": _("Zeichnung extrudieren"),
    "load": _("Modell laden"),
}


@dataclass(frozen=True, slots=True)
class ImportPlan:
    """Was aus einer Datei wird: eine Transaktion mit genau einem Entwurf."""

    title: TranslatableText
    draft: OperationDraft
    asks_unit: bool
    """Ob die Einheitenfrage überhaupt gestellt werden muss.

    Nur ein Netz hat sie, und auch das nicht immer. STEP trägt seine Einheit
    selbst, und eine flache Zeichnung hat keine dritte Dimension, bis jemand
    sagt, wie dick sie sein soll (§25, §30, §11.1) — dort wäre die Frage eine
    Zumutung ohne Zweck. Eine 3MF sagt ihre Einheit ebenfalls selbst, sofern
    sie das ``unit``-Attribut führt.
    """


def import_plan(source_id: str, name: str, payload: bytes, unit: str = "auto") -> ImportPlan:
    """Der Einleseweg für eine Datei, entschieden an ihrer Endung.

    ``payload`` wird nur für die 3MF-Baugruppe gebraucht: Wie viele Körper eine
    Datei hält, entscheidet sich **vor** der Operation, weil der Stapel die
    Objekt-IDs vergibt, bevor irgendetwas läuft (§11). Gezählt wird ohne eine
    einzige Koordinate zu lesen.
    """
    suffix = Path(name).suffix
    # Die Größengrenze steht vor jeder Operation, für **jedes** Format — nicht
    # nur für 3MF. Eine zu große STL ging sonst als Quelle ins Dokument, die
    # Operation landete im Stapel und scheiterte erst bei der Auswertung, und
    # die übergroße Quelle wanderte beim nächsten Speichern in die Projektdatei.
    # (Die entpackte Größe bleibt 3MF-eigen — nur ein Archiv hat eine.)
    check_limits(len(payload), 0)
    if brep_step.is_step(suffix):
        return ImportPlan(
            title=_TITLES["load_step"],
            draft=OperationDraft(op="load_step", params={"source": source_id}),
            asks_unit=False,
        )
    if is_outline(suffix):
        return ImportPlan(
            title=_TITLES["load_outline"],
            draft=OperationDraft(op="load_outline", params={"source": source_id}),
            asks_unit=False,
        )
    parts = 1
    asks = True
    if suffix.lower() == ".3mf":
        # **Die entpackte Grenze steht vor dem Parsen.** Zählen heißt bei einer
        # 3MF, das ganze XML zu lesen, und das geschieht hier — im Hauptthread,
        # bevor irgendeine Operation läuft. Eine Datei von 1,9 MB wird dabei zu
        # 660 MB im Speicher. ``check_unpacked`` gibt es für genau diesen Fall
        # (§32); es lief nur an der falschen Stelle, nämlich erst in der
        # Operation. Die Zahlen dafür stehen im zentralen Verzeichnis des
        # Archivs — geprüft wird, ohne ein Byte des Inhalts zu lesen.
        check_unpacked(payload)
        # Körper und Dreiecke in einem streamenden Lauf. Die entpackte Grenze
        # allein hält den Speicher nicht auf: read_objects hebt beim Vollparse
        # rund das Zwölffache der entpackten XML in ET.Element-Objekte, und die
        # Dreiecksgrenze griff bisher erst *nach* diesem Parsen. Sie greift
        # jetzt hier, vor jeder Operation — gezählt wurde ohne eine Koordinate.
        parts, triangles = threemf.scan_assembly(payload)
        check_limits(len(payload), triangles)
        # Eine 3MF trägt ihre Einheit im ``unit``-Attribut. Wo sie dasteht,
        # stellt die Operation die Frage nicht — und dann darf der Aufrufer
        # sie auch nicht vorweg stellen: Die Kommandozeile tat es, und ihre
        # Antwort hätte die Angabe der Datei überschrieben.
        asks = threemf.declared_unit(payload) is None
    return ImportPlan(
        title=_TITLES["load"],
        draft=OperationDraft(
            op="load",
            params={"source": source_id, "unit": unit},
            produces=max(parts, 1),
        ),
        asks_unit=asks,
    )
