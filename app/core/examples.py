"""Die Beispielprojekte (Bauplan §37.2, §2.2).

„Dokumentation, Abnahmetest und Startbildschirm-Inhalt zugleich." Sie sind
also kein Ordner mit Dateien, die jemand irgendwann exportiert hat — sie
entstehen aus denselben Operationen wie alles andere, gebaut von
:mod:`tools.make_examples`, und die Suite öffnet und rechnet jedes davon.

Die ersten vier beantworten „wie fange ich an" — eines je Weg aus §2.2 —, die
übrigen „was kann das eigentlich". Ihre Zahl steht in :data:`EXAMPLES` und
sonst nirgends: eine zweite Stelle wäre nach dem nächsten Beispiel falsch.

Eines je Weg aus §2.2:

* **Weg 1** — fremdes Modell anpassen: einlesen, reparieren, aufs Bett,
  bohren.
* **Weg 2** — neu bauen: Parameter, ein Körper, Bausteine aus der Bibliothek.
* **Weg 3** — erzeugen: ein Mesh von außen läuft durch die Reparaturkette und
  wird geteilt. Der Generator selbst ist P9; das Beispiel bringt ein fertiges
  Mesh mit und sagt das, statt so zu tun, als hätte es eines erzeugt.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.branding import PROJECT_SUFFIX
from app.i18n import TranslatableText, _

#: Wo die Beispiele in der Installation liegen.
EXAMPLES_DIRNAME: Final = "examples"

#: Kantenlänge eines Vorschaubildes. Größer als eine Bausteinvorschau: eine
#: Kachel auf dem Startbildschirm ist keine Zeile in einer Liste.
PREVIEW_SIZE: Final = 220

#: Auf so viele Dreiecke wird vor dem Zeichnen heruntergerechnet. Ein
#: ausgehöhltes Teil mit Gitterfüllung bringt zweihunderttausend mit, und das
#: Bild davon wäre elf Megabyte für eine Kachel von zweihundert Pixeln.
#:
#: Gemessen: bei 1500 Dreiecken liegt ein Bild bei gut hundertfünfzig
#: Kilobyte, bei 4000 beim Anderthalbfachen und bei 800 fällt die Form
#: sichtbar auseinander — ein Kalibrierteil besteht aus Zapfen und Bohrungen,
#: und beide brauchen ihre Rundung.
PREVIEW_TRIANGLES: Final = 1500


@dataclass(frozen=True, slots=True)
class Example:
    """Ein Beispielprojekt, wie der Startbildschirm es zeigt."""

    id: str
    title: TranslatableText | str
    way: str
    doc: TranslatableText | str

    @property
    def filename(self) -> str:
        return f"{self.id}{PROJECT_SUFFIX}"

    @property
    def preview_name(self) -> str:
        """Wie das Vorschaubild heißt — dieselbe Antwort für den, der es
        schreibt, und den, der es zeigt."""
        return f"{self.id}.svg"


EXAMPLES: Final[tuple[Example, ...]] = (
    Example(
        id="weg1-halterung-anpassen",
        title=_("Vorhandenes Modell anpassen"),
        way="1",
        doc=_(
            "Eine heruntergeladene Halterung öffnen, automatisch prüfen, aufs Druckbett "
            "stellen und eine Bohrung ergänzen. Der häufigste Einstieg."
        ),
    ),
    Example(
        id="weg2-halter-konstruieren",
        title=_("Eigenes Teil bauen"),
        way="2",
        doc=_(
            "Einen Halter aus Grundformen und fertigen Bausteinen zusammensetzen. "
            "Breite, Tiefe und Stärke lassen sich direkt ändern."
        ),
    ),
    Example(
        id="weg3-generiert-aufbereiten",
        title=_("Modell aus Text oder Bild vorbereiten"),
        way="3",
        doc=_(
            "Ein automatisch erzeugtes Modell prüfen, reparieren, auf das Druckbett "
            "stellen und weiterbearbeiten. Ein fertiges Beispiel ist bereits enthalten."
        ),
    ),
    Example(
        id="weg4-figur-formen",
        title=_("Figur frei formen"),
        way="4",
        doc=_(
            "Einfache Körper weich verbinden und anschließend wie Ton von Hand formen. "
            "Für Figuren und freie Formen ohne genaue Maße."
        ),
    ),
    # Die fünf darunter sind keine weiteren Wege — sie zeigen, was auf den vier
    # Wegen an Werkzeug bereitliegt. Die vier oben beantworten „wie fange ich
    # an", diese „was kann das eigentlich".
    Example(
        id="gehaeuse-mit-bausteinen",
        title=_("Bausteine — Muttern, Buchsen, Kabel"),
        way="",
        doc=_(
            "Ein Gehäuseboden mit Mutternfalle, Heat-Set-Buchse, Schraubenloch und "
            "Kabeldurchführung. Vier Klicks statt vier halber Stunden."
        ),
    ),
    Example(
        id="schild-zweifarbig",
        title=_("Beschriftung — zweifarbig"),
        way="",
        doc=_(
            "Ein Schild mit Schrift in einem eigenen Filament: der 3MF-Export "
            "macht daraus den Farbwechsel — und die Lettern bleiben ein eigener Körper."
        ),
    ),
    Example(
        id="skizze-mit-massen",
        title=_("Skizzieren — ein Umriss, der sich bemaßen lässt"),
        way="",
        doc=_(
            "Eine runde Platte aus einer Skizze: Der Durchmesser ist eine Bedingung, "
            "kein Punkt — ändert man den Projektparameter, folgt der Umriss. Dazu "
            "eine Tasche, ebenfalls skizziert."
        ),
    ),
    Example(
        id="drucker-kalibrieren",
        title=_("Kalibrieren — einmal drucken, dann stimmt es"),
        way="",
        doc=_(
            "Toleranzleiter, Wandstärkenleiter und Überhangfächer auf einer Platte. "
            "Die gemessenen Werte gehören danach ins Materialprofil."
        ),
    ),
    Example(
        id="aushoehlen-und-teilen",
        title=_("Druckvorbereitung — aushöhlen, teilen, anordnen"),
        way="",
        doc=_(
            "Material sparen, das Teil an einer Ebene mit Passstiften trennen und "
            "beide Hälften auf das Bett legen."
        ),
    ),
    # Das letzte ist keine achte Sorte, sondern die Summe: es legt hintereinander,
    # was die anderen einzeln zeigen. Es steht auch auf dem Startbildschirm und
    # im Handbuch — ein Beispiel, das nach einer Platte mit Löchern aussieht,
    # zeigt ein Programm, das Löcher bohren kann.
    Example(
        id="dose-mit-deckel",
        title=_("Alles zusammen — Dose mit Deckel"),
        way="",
        doc=_(
            "Benannte Maße, ausgehöhlt und oben offen, Kabeldurchführung und "
            "Einpressbuchse in der Wand, ein Deckel aus der Öffnung geschnitten "
            "statt nachgezeichnet, beschriftet und neben die Dose gelegt."
        ),
    ),
)


def directory() -> Path:
    """Wo die mitgelieferten Beispiele liegen. Neben dem Paket, nicht in den
    Nutzerdaten."""
    return Path(__file__).resolve().parent.parent / EXAMPLES_DIRNAME


def paths() -> tuple[Path, ...]:
    """Die Beispiele, die wirklich da sind — ein fehlendes ist kein Fehler."""
    folder = directory()
    return tuple(
        folder / example.filename for example in EXAMPLES if (folder / example.filename).is_file()
    )


def preview_of(example: Example) -> str:
    """Das Vorschaubild eines Beispiels, oder ein leerer Text.

    Ein fehlendes Bild ist kein Fehler: die Beispiele entstehen aus
    `tools/make_examples.py`, und wer das Repository frisch auscheckt, hat
    sie, bevor er es laufen lässt. Die Kachel zeigt dann eben nur Titel und
    Satz — so, wie sie es vorher immer tat.
    """
    path = directory() / example.preview_name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def render_preview(meshes: Iterable[object], theme: str = "light") -> str:
    """Zeichnet die Körper eines Beispiels als ein Vorschaubild.

    Alle zusammen und nicht einzeln: eine Kachel zeigt, was das Beispiel
    enthält, und bei „Aushöhlen und teilen" sind das zwei Hälften, die
    nebeneinanderliegen. Getrennt gerendert wäre jede für sich richtig und die
    Aussage falsch.

    Heruntergerechnet, bevor gezeichnet wird — siehe ``PREVIEW_TRIANGLES``.
    Das Ergebnis fließt nirgends zurück; es ist ein Bild, keine Geometrie.
    """
    from app.core import drawing
    from app.core.geom.mesh import MeshData, concatenated
    from app.core.geom.mesh_ops import decimate

    raw = [mesh.raw for mesh in meshes]  # type: ignore[attr-defined]
    if not raw:
        return ""
    body = concatenated(raw) if len(raw) > 1 else raw[0]
    reduced = decimate(MeshData.of(body), PREVIEW_TRIANGLES)
    tone = drawing.palette(theme).solid  # type: ignore[arg-type]
    return drawing.project(
        reduced.raw,
        PREVIEW_SIZE,
        tone,
        theme=theme,  # type: ignore[arg-type]
        edges=True,
    )


def by_path(path: Path) -> Example | None:
    for example in EXAMPLES:
        if path.name == example.filename:
            return example
    return None
