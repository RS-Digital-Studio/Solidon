"""Nachträgliches Ändern am wirklich übernommenen Verlaufsschritt (Prüfpunkt 12)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Final

from tools import function_surface as surfaces
from tools.function_checks import REVISE_WAYS, STEP_WITHOUT_VALUES
from tools.function_machine import Step, StepMachine
from tools.function_protocol import unmeasured

if TYPE_CHECKING:
    from tools.function_bench import FunctionFlow

#: Die zwei Wege, einen Projektparameter nachträglich zu ändern (FD-127), mit
#: denselben Namen wie die Wege eines Schritts (``function_checks.REVISE_WAYS``).
REVISE_PARAMETER_WAYS: Final = REVISE_WAYS
#: Die Beschriftung der ersten Zeile der Parameterleiste; ihr Rechtsklick öffnet
#: das Menü der Leiste mit *Ändern …* (``menu:parameters.edit``). Der neue
#: Parameter einer Startszene ohne Parameter steht dort.
PARAMETER_ROW: Final = "parameters.first.label"
#: Der letzte Eintrag der Verlaufsliste, auch ohne Schritt (``history.row``
#: nennt nur Einträge mit Schrittnummer).
HISTORY_ENTRY: Final = "history.last"
#: Die Klicks je Weg (FD-127).
PARAMETER_ROUTES: Final[dict[str, tuple[tuple[str, str], ...]]] = {
    REVISE_PARAMETER_WAYS[0]: ((PARAMETER_ROW, "right"), ("menu:parameters.edit", "left")),
    REVISE_PARAMETER_WAYS[1]: ((HISTORY_ENTRY, "double"),),
}


class RevisionPhase:
    """Prüfpunkt 12 als Phase von FunctionFlow, wie GesturePhases und SwitchPhase."""

    def shown_steps(self: FunctionFlow, triggering: list[Step]) -> list[Step]:
        """Weg und Eingaben, dann die Vorschau — ohne Eingaben nur Ruhe wie der Hauptweg.

        Ohne Eingaben gibt es keinen Entwurf und kein Band; ``preview_steps``
        wartete dann zweimal 180 s auf „vorschau steht“ (``countersink_hole``
        im Schlusslauf).
        """
        if self.spec.get("inputs"):
            return self.preview_steps(triggering)
        return [*triggering, self.wait_step("ruhe", self.idle)]

    def phase_revise(self: FunctionFlow) -> None:
        """Prüfpunkt 12: Schritt über Kontextmenü und Doppelklick ändern, Verlauf gleich lang.

        Je Weg öffnet der Klick den übernommenen Schritt; Felder und Parameter
        stehen nebeneinander, dann eine neue Zahl ins erste Zahlenfeld des
        Schritts, Übernehmen, und die Verlaufslänge danach. Gemessen wird nur,
        wenn die Zeile einen Schritt anlegt, und „geöffnet“ heißt: sein Dialog
        steht offen — nicht die Karte der Auswahl, die immer da ist (F-23). Ein
        Schritt ohne Wert hat keinen Dialog (:data:`STEP_WITHOUT_VALUES`).
        """
        from app.core.scene.serialise import operation_to_data
        from tools import function_capture as capture
        from tools.file_acceptance import changed_value

        states = self.data["states"]
        applied = states.get("redo") or states.get("applied")
        before = states.get("before") or {}
        grown = applied is not None and len(applied.get("ops") or ()) > len(before.get("ops") or ())
        if (
            applied is not None
            and not grown
            and applied.get("project_params") != before.get("project_params")
        ):
            # Ein Projektparameter ist ein Eintrag im Verlauf ohne Operation; er
            # wird über seinen eigenen Weg geändert (FD-127).
            self.revise_parameter()
            return
        if not applied or not applied.get("ops"):
            unmeasured(self.data, "revise", "kein übernommener Schritt")
            return
        if not grown:
            unmeasured(self.data, "revise", "die Zeile legt keinen Schritt im Verlauf an")
            return
        number = len(applied["ops"])
        entries: list[dict[str, Any]] = []
        for way, route in (
            ("menue", [(f"history.row:{number}", "right"), ("menu:history.edit", "left")]),
            ("doppelklick", [(f"history.row:{number}", "double")]),
        ):
            if not self.reset():
                # Kein Weg ohne Startszene (Durchsicht welle4 C-L15): Er änderte
                # sonst, was die vorige Phase liegen ließ.
                self.data["errors"].append(f"nachträglich {way}: Startszene nicht herstellbar")
                continue
            previous = self.session.last_result
            accepted = self.run_steps(
                f"übernehmen für {way}",
                self.shown_steps(
                    [*self.path_steps(), *self.input_steps(self.spec.get("inputs") or {})]
                )
                + ([self.apply_step()] if self.apply_target else [])
                + [
                    self.wait_step(
                        "übernommen",
                        lambda previous=previous: (
                            self.idle()
                            and self.session.last_result is not previous
                            and len(self.session.project.document.ops) == number
                        ),
                    )
                ],
            )
            if not accepted:
                self.data["errors"].append(
                    f"nachträglich {way}: neuer Schritt nicht vollständig übernommen"
                )
                continue
            document = self.session.project.document
            if not document.ops:
                entries.append(
                    {
                        "way": way,
                        "opened": False,
                        "fields": {},
                        "params": {},
                        "history_before": 0,
                        "history_after": 0,
                    }
                )
                continue
            params = dict(operation_to_data(document.ops[-1]).get("params") or {})
            if not params:
                self.data["revise"] = []
                unmeasured(self.data, "revise", STEP_WITHOUT_VALUES)
                return
            record: dict[str, Any] = {
                "way": way,
                "opened": False,
                "fields": {},
                "params": params,
                "history_before": len(document.ops),
                "history_after": None,
                "typed_values": {},
                "params_after": None,
            }

            def read(machine: StepMachine, record: dict[str, Any] = record) -> None:
                dialog = surfaces.open_dialog(self.window)
                record["opened"] = dialog is not None
                record["fields"] = capture.field_values(dialog) if dialog is not None else {}
                params = record["params"]
                numeric = [
                    name
                    for name in record["fields"]
                    if isinstance(params.get(name), (int, float))
                    and not isinstance(params.get(name), bool)
                ]
                if not record["opened"] or not numeric:
                    return
                name = numeric[0]
                value = changed_value(float(params[name]))
                previous = self.session.last_result
                accept = "dialog.accept" if self.widget("dialog") is not None else "feature.apply"

                def typed(machine: StepMachine) -> None:
                    record["typed_values"] = {name: value}

                def read_accepted(machine: StepMachine) -> None:
                    record["params_after"] = dict(
                        operation_to_data(self.session.project.document.ops[-1]).get("params") or {}
                    )
                    self.picture(f"nachtraeglich-{record['way']}")

                # Innerhalb desselben Automaten bleibt auch ein modaler Dialog
                # offen. Ein beendeter Leselauf würde ihn mit Escape schließen.
                machine.insert(
                    [
                        *self.preview_steps(self.input_steps({f"field:{name}": value})),
                        Step("getippt", typed),
                        self.walker.step(accept),
                        self.wait_step(
                            "geändert",
                            lambda: self.idle() and self.session.last_result is not previous,
                        ),
                        Step("übernommene werte lesen", read_accepted),
                    ]
                )

            def dialog_or_window() -> Any:
                return surfaces.open_dialog(self.window) or self.window

            self.run_steps(
                f"nachträglich {way}",
                [
                    *(self.walker.step(name, button) for name, button in route),
                    # Erst geöffnet und still, dann lesen (Review M1).
                    self.until_step(
                        "geöffnet", lambda: surfaces.open_dialog(self.window) is not None
                    ),
                    self.still_step("fläche steht still", dialog_or_window),
                    Step("felder lesen", read),
                ],
            )
            record["history_after"] = len(self.session.project.document.ops)
            entries.append(record)
        self.data["revise"] = entries

    def revise_parameter(self: FunctionFlow) -> None:
        """Prüfpunkt 12 an einer Zeile, die einen Projektparameter anlegt (FD-127).

        Ein Parameter ist ein Eintrag im Verlauf („Parameter Breite“) ohne
        Operation; ``phase_revise`` sah keinen Schritt und maß nichts. Seine
        zwei Wege: *Ändern …* über seine Zeile in der Parameterleiste
        (:data:`PARAMETER_ROW` rechts, dann ``menu:parameters.edit``) und der
        Doppelklick auf seinen Eintrag im Verlauf (:data:`HISTORY_ENTRY`). Beide
        öffnen den Dialog des Parameters mit seinen Werten; eine neue Zahl
        ändert ihn. Die Verlaufslänge ist hier die Zahl der Projektparameter —
        eine Änderung legt keinen zweiten an. Öffnet ein Weg nichts, misst
        Prüfpunkt 12 das als Fund. Ein Weg, dessen Ziel der Wortschatz nicht
        kennt, oder ein neuer Parameter, der nicht in der ersten Zeile steht,
        ist nicht gemessen — die Lücke liegt am Prüfstand, nicht am Produkt.
        """
        from app.core import guides
        from tools import function_capture as capture
        from tools.file_acceptance import changed_value

        entries: list[dict[str, Any]] = []
        gaps: list[str] = []
        for way in REVISE_PARAMETER_WAYS:
            route = PARAMETER_ROUTES[way]
            unknown = [target for target, _button in route if not guides.is_target(target)]
            if unknown:
                gaps.append(f"{way}: Ziel {', '.join(unknown)} fehlt im Wortschatz")
                continue
            if not self.reset():
                self.data["errors"].append(f"nachträglich {way}: Startszene nicht herstellbar")
                continue
            known = set(self.session.project.document.parameters)

            def created(known: set[str] = known) -> bool:
                return self.idle() and bool(set(self.session.project.document.parameters) - known)

            accepted = self.run_steps(
                f"anlegen für {way}",
                self.shown_steps(
                    [*self.path_steps(), *self.input_steps(self.spec.get("inputs") or {})]
                )
                + ([self.apply_step()] if self.apply_target else [])
                + [self.wait_step("angelegt", created)],
            )
            document = self.session.project.document
            new = [name for name in document.parameters if name not in known]
            if not accepted or not new:
                self.data["errors"].append(f"nachträglich {way}: kein Parameter angelegt")
                continue
            name = new[0]
            if way == REVISE_PARAMETER_WAYS[0] and list(document.parameters).index(name):
                gaps.append(f"{way}: der neue Parameter steht nicht in der ersten Zeile")
                continue
            record: dict[str, Any] = {
                "way": way,
                "opened": False,
                "fields": {},
                "params": parameter_values(document.parameters[name]),
                "history_before": len(document.parameters),
                "history_after": None,
                "typed_values": {},
                "params_after": None,
            }

            def read(
                machine: StepMachine, record: dict[str, Any] = record, name: str = name
            ) -> None:
                dialog = surfaces.open_dialog(self.window)
                record["opened"] = dialog is not None
                record["fields"] = capture.field_values(dialog) if dialog is not None else {}
                if not record["opened"] or "value" not in record["fields"]:
                    return
                value = changed_value(float(record["params"]["value"]))

                def typed(machine: StepMachine) -> None:
                    record["typed_values"] = {"value": value}

                def changed() -> bool:
                    now = self.session.project.document.parameters.get(name)
                    old = float(record["params"]["value"])
                    return bool(
                        self.idle() and now is not None and not math.isclose(now.value, old)
                    )

                def read_accepted(machine: StepMachine) -> None:
                    parameters = self.session.project.document.parameters
                    record["params_after"] = (
                        parameter_values(parameters[name]) if name in parameters else {}
                    )
                    self.picture(f"nachtraeglich-{record['way']}")

                machine.insert(
                    [
                        *self.input_steps({"field:value": value}),
                        Step("getippt", typed),
                        self.walker.step("dialog.accept"),
                        self.wait_step("geändert", changed),
                        Step("übernommene werte lesen", read_accepted),
                    ]
                )

            def dialog_or_window() -> Any:
                return surfaces.open_dialog(self.window) or self.window

            self.run_steps(
                f"nachträglich {way}",
                [
                    *(self.walker.step(target, button) for target, button in route),
                    self.until_step(
                        "geöffnet", lambda: surfaces.open_dialog(self.window) is not None
                    ),
                    self.still_step("fläche steht still", dialog_or_window),
                    Step("felder lesen", read),
                ],
            )
            record["history_after"] = len(self.session.project.document.parameters)
            entries.append(record)
        if gaps:
            unmeasured(self.data, "revise", "; ".join(gaps))
        self.data["revise"] = entries


def parameter_values(parameter: Any) -> dict[str, Any]:
    """Was der Dialog eines Parameters zeigt, aus dem Dokument: Name, Wert, Einheit, Ausdruck.

    Die Grenzen stehen dort als Text eines freien Felds und sind nicht ohne
    Umrechnung mit der Zahl vergleichbar; verglichen wird, was beide gleich tragen.
    """
    return {
        "name": parameter.name,
        "value": float(parameter.value),
        "unit": parameter.unit,
        "expression": parameter.expression or "",
    }
