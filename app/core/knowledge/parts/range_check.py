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
from typing import Any

from app.core.types import BaseParams, CancelToken, PartResult, Profile, ProgressFn
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


def check(
    params: type[BaseParams],
    build: Any,
    profile: Profile,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> RangeReport:
    """Fährt die Ecken und sagt je Ecke, was nicht hielt.

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
        try:
            result: PartResult = build(params(**values))
        except Exception as problem:  # eine brechende Ecke ist das Ergebnis, kein Absturz
            failures.append(RangeFailure(values=dict(values), reason=str(problem)[:200]))
            checked += 1
            continue
        mesh = as_mesh_data(result.mesh)
        if not mesh.is_watertight:
            failures.append(RangeFailure(dict(values), str(_("nicht wasserdicht"))))
        elif mesh.volume <= 0.0:
            failures.append(RangeFailure(dict(values), str(_("kein Volumen"))))
        elif mesh.component_count != 1:
            failures.append(RangeFailure(dict(values), str(_("zerfällt in Teile"))))
        elif min(mesh.bounds.size) <= profile.minimum_wall_thickness / 4.0:
            failures.append(RangeFailure(dict(values), str(_("dünner als druckbar"))))
        checked += 1
    if progress is not None:
        progress(1.0, str(_("Bereichstest abgeschlossen")))
    return RangeReport(checked=checked, failures=tuple(failures))
