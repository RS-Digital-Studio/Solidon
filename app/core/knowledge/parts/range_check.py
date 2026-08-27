"""Der Bereichstest in der Anwendung (§24.3, §24.5 — Konzept E3).

§24.3 sagt: „Ein Baustein ohne diesen Test gilt als nicht vorhanden", und
§24.5 verlangt für eigene Bausteine denselben Test, mit Warnhinweis im
Katalog, wenn er nicht bestanden ist. Für die mitgelieferten Bausteine läuft
er in der Suite (``tests/test_parts.py``); ein Kunde hat keine Suite — sein
Rezept wird deshalb **beim Anlegen** geprüft, mit Fortschritt und Abbruch,
und das Ergebnis bleibt am Baustein.

Die Ecken sind dieselben wie im Test, und das ist der Punkt: eine Regel, ein
Ort. Kein kartesisches Produkt — die Geschichte, warum es siebzehn von
achtzehn Bausteinen ungeprüfte Ecken bescherte, steht an :func:`corners` —
sondern so viele Kombinationen wie die längste Werteliste, zyklisch gefüllt:
Jeder Wert jedes Parameters kommt mindestens einmal vor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from app.core.types import BaseParams, CancelToken, PartResult, Profile, ProgressFn
from app.core.units import EPS_DISPLAY
from app.i18n import _


def corners(params: type[BaseParams]) -> list[dict[str, Any]]:
    """Der Parameterbereich als die Werte, die ein Baustein überstehen muss.

    Der kleinste und der größte Wert jeder Zahl, jede Wahl jedes Enums, beide
    Zustände jedes Schalters — jeder davon mindestens einmal. **Kein
    kartesisches Produkt:** Mit einer Obergrenze gekürzt trug es vom vierten
    Parameter an nur noch die ersten Werte der frühen Parameter; gezählt am
    21.08.2026 hatten siebzehn von achtzehn Bausteinen Ecken, die nie
    gefahren wurden. Zyklisch über die längste Liste ist der Lauf kürzer
    **und** vollständig je Wert. Was er nicht prüft, ist das Zusammenspiel
    zweier Extreme — dafür wäre das Produkt nötig, und das ist bei zwölf
    Parametern kein Test mehr, sondern ein Nachmittag.
    """
    lists: dict[str, list[Any]] = {}
    for entry in params.spec():
        values: list[Any] = []
        if entry.kind == "enum":
            values = list(entry.choices)
        elif entry.kind == "bool":
            values = [True, False]
        elif entry.kind in ("float", "int"):
            values = [entry.minimum, entry.maximum, entry.default]
            values = [value for value in values if value is not None]
        if values:
            lists[entry.name] = values
    if not lists:
        return [{}]
    longest = max(len(values) for values in lists.values())
    return [
        {name: values[index % len(values)] for name, values in lists.items()}
        for index in range(longest)
    ]


@dataclass(frozen=True, slots=True)
class RangeFailure:
    """Eine Ecke, die nicht hielt — mit den Werten, bei denen es geschah."""

    values: dict[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class RangeReport:
    """Was der Bereichstest ergeben hat. Hängt am Baustein, nicht im Hash.

    Der Hash ist die Version des Rezepts (§24.4) — stünde der Bericht darin,
    machte das **Prüfen** aus dem Rezept ein anderes, und jedes Projekt
    meldete beim Öffnen eine Änderung, die keine ist.
    """

    checked: int = 0
    failures: tuple[RangeFailure, ...] = ()

    @property
    def passed(self) -> bool:
        return self.checked > 0 and not self.failures


@dataclass(slots=True)
class _Silent:
    @property
    def is_cancelled(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        return None


#: Wie viele Eckpunkte die Spaltmessung abtastet. Der engste Spalt liegt bei
#: einem gedruckten Gelenk auf einer Fläche und nicht auf einer Ecke, also
#: genügt eine Stichprobe — und der Bereichstest fährt viele Ecken.
#: Der Parameter, in dem ein Baustein sein Spiel führt — derselbe Name wie
#: in ``parts/ops.py`` (``PLAY_FIELD``). Hier als eigene Zeichenkette und
#: nicht als Import, weil ``ops`` den Bereichstest kennt und nicht
#: umgekehrt; der Test darunter hält die beiden zusammen.
PLAY_FIELD: Final = "play"

GAP_SAMPLE: Final = 200


def printable_gap(mesh: Any, profile: Profile) -> float | None:
    """Der engste Spalt zwischen den Teilen eines mehrteiligen Bausteins.

    ``None``, wenn es nur ein Teil gibt — dann gibt es keinen Spalt, und eine
    Zahl wäre eine Behauptung.

    Gerechnet gegen den nächsten **Ort auf dem Dreieck** und nicht gegen den
    nächsten Eckpunkt: Zwischen zwei Zylinderflächen liegen die nächsten
    Punkte fast nie auf Ecken, und der Unterschied ist bei einem Spalt von
    zwei Zehnteln kein Feinschliff. Über eine Stichprobe der Eckpunkte, weil
    der Bereichstest die Ecken des Parameterraums fährt und nicht eine Ecke —
    gemessen am Bolzenscharnier: 247 Punkte gegen 392 Dreiecke, 26 ms, und der
    gefundene Spalt traf den eingestellten auf drei Stellen.
    """
    import numpy as np

    from app.core.geom.mesh import distance_to_triangles

    pieces = mesh.raw.split(only_watertight=False)
    if len(pieces) < 2:
        return None
    first, rest = pieces[0], pieces[1:]
    triangles = np.concatenate([piece.triangles for piece in rest])
    points = first.vertices[:: max(1, len(first.vertices) // GAP_SAMPLE)]
    return min(distance_to_triangles(triangles, np.asarray(p, dtype=float)) for p in points)


def check(
    params: type[BaseParams],
    build: Any,
    profile: Profile,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
    joined_by_host: bool = False,
    bodies: int = 1,
) -> RangeReport:
    """Fährt die Ecken und sagt je Ecke, was nicht hielt.

    ``joined_by_host`` nimmt die Prüfung auf **eine** Komponente heraus — für
    Bausteine, deren Teile erst der Träger verbindet. Der Lochwand-Einhänger
    setzt ohne Rückplatte je Haken einen Zapfen; zwei Zapfen sind zwei Körper,
    und an dem Teil, an das sie kommen, sind sie einer. Ohne diesen Schalter
    trüge sein Katalogeintrag eine Warnung über einen Baustein, der im Einsatz
    tadellos ist (§24.5 verlangt, dass ein gebrochener Bericht dort steht).
    Die übrigen drei Prüfungen gelten unverändert: Ein Baustein darf auch
    mehrteilig weder undicht noch leer noch zu dünn sein.

    ``bodies`` ist der **andere** mehrteilige Fall (§24.3, Entscheidung Robert
    vom 25.08.2026): print-in-place — ein Scharnier, das schon beim Drucken
    beweglich ist. Hier hält kein Träger die Teile zusammen, sie sollen
    getrennt bleiben. Geprüft wird deshalb nicht *ob* der Baustein zerfällt,
    sondern **ob er in so viele Teile zerfällt, wie er erklärt hat**: Zwei
    statt zwei ist die Zusage, drei statt zwei ist ein Fehler wie jeder andere.
    Unerklärtes Zerfallen bleibt damit rot — die Prüfung wird nicht schwächer,
    sondern genauer.

    ``build`` ist, was aus Werten einen Körper macht — für ein Rezept die
    Auswertung, für eine ``.py`` ihre Funktion. Die vier Prüfungen sind die
    der Suite: wasserdicht, Volumen, eine Komponente, nichts dünner als ein
    Viertel der druckbaren Mindestwand. Ein Fehlschlag bricht nicht ab — der
    Kunde soll **alle** brechenden Ecken sehen, nicht je Lauf eine.

    Abbruch ist Abbruch (§15.6): Was bis dahin geprüft ist, kommt zurück,
    und ``checked`` sagt ehrlich, wie weit es kam — ein abgebrochener Lauf
    sieht nie wie ein bestandener aus, denn ``passed`` verlangt Fehlerfreiheit
    **über alle** Ecken, und die Zahl steht daneben.
    """
    from app.core.geom.mesh import as_mesh_data

    token = cancelled or _Silent()
    plan = corners(params)
    failures: list[RangeFailure] = []
    checked = 0
    for index, values in enumerate(plan):
        if token.is_cancelled:
            break
        if progress is not None:
            progress(
                index / len(plan),
                str(_("Bereichstest, Ecke {n} von {total}")).format(n=index + 1, total=len(plan)),
            )
        # **Das Spiel kommt aus dem Profil, wie im Einsatz.** Ein Baustein
        # deklariert ``play`` und lässt es auf null; ``insert_part`` setzt dort
        # ``profile.material.clearance`` ein (``ops.py``, Regel 7). Der
        # Bereichstest tat das nicht und fuhr damit einen Zustand, den es nie
        # gibt: beim Bolzenscharnier ein Gelenk mit einer Hundertstel Spalt,
        # das beim Drucken verschweißt. Geprüft wurde eine Geometrie, die
        # niemand bekommt.
        entered = dict(values)
        if PLAY_FIELD in entered and not entered[PLAY_FIELD]:
            entered[PLAY_FIELD] = profile.material.clearance
        try:
            result: PartResult = build(params(**entered))
        except Exception as problem:  # eine brechende Ecke ist das Ergebnis, kein Absturz
            failures.append(RangeFailure(values=entered, reason=str(problem)[:200]))
            checked += 1
            continue
        mesh = as_mesh_data(result.mesh)
        if not mesh.is_watertight:
            failures.append(RangeFailure(dict(values), str(_("nicht wasserdicht"))))
        elif mesh.volume <= 0.0:
            failures.append(RangeFailure(dict(values), str(_("kein Volumen"))))
        elif not joined_by_host and mesh.component_count != max(bodies, 1):
            # **Die erklärte Zahl, nicht die Eins.** Wer nichts deklariert,
            # bekommt ``bodies=1`` und damit genau die alte Prüfung; wer zwei
            # erklärt, muss zwei bauen — auch das ist eine Zusage, die brechen
            # kann, und ein Scharnier, das in drei Teile fällt, ist genauso
            # kaputt wie eine Rastnase, die in zwei fällt.
            failures.append(
                RangeFailure(
                    dict(values),
                    str(_("zerfällt in {found} Teile statt {declared}")).format(
                        found=mesh.component_count, declared=max(bodies, 1)
                    ),
                )
            )
        elif min(mesh.bounds.size) <= profile.minimum_wall_thickness / 4.0:
            failures.append(RangeFailure(entered, str(_("dünner als druckbar"))))
        elif (
            bodies > 1
            and (gap := printable_gap(mesh, profile)) is not None
            # **``EPS_DISPLAY`` und nicht ``EPS_GEOM``**: Das hier ist eine
            # Fertigungsfrage, kein Rechenvergleich. Der gemessene Spalt fällt
            # um Bruchteile kleiner aus als der eingestellte, weil ein
            # facettierter Zylinder seine Sehne zeigt und nicht den Bogen —
            # gemessen 0,2499 bei eingestellten 0,25, und mit dem
            # Rechenepsilon meldete die Prüfung ein Scharnier, das genau
            # richtig gebaut war. Ein Hundertstel Millimeter liegt unter jeder
            # Druckauflösung; was darunter liegt, ist kein Spalt und kein
            # Fehler.
            and (gap < profile.material.clearance - EPS_DISPLAY)
        ):
            # **Der Spalt ist bei einem print-in-place-Teil die ganze Sache.**
            # Zu eng verschweißt beim Drucken, und aus zwei Körpern wird einer
            # — der Bereichstest sähe davon nichts, weil er die Geometrie vor
            # dem Drucker prüft und nicht danach. Gemessen wird gegen das
            # kalibrierte Material und nie gegen eine Zahl im Code (Regel 7).
            failures.append(
                RangeFailure(
                    entered,
                    str(_("Spalt {gap} mm — der Drucker legt {least} mm")).format(
                        gap=round(gap, 2), least=round(profile.material.clearance, 2)
                    ),
                )
            )
        checked += 1
    if progress is not None:
        progress(1.0, str(_("Bereichstest abgeschlossen")))
    return RangeReport(checked=checked, failures=tuple(failures))
