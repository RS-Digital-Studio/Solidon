"""Nachträgliches Ändern am wirklich übernommenen Verlaufsschritt (Prüfpunkt 12)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tools import function_surface as surfaces
from tools.function_checks import STEP_WITHOUT_VALUES
from tools.function_machine import Step, StepMachine
from tools.function_protocol import unmeasured

if TYPE_CHECKING:
    from tools.function_bench import FunctionFlow


class RevisionPhase:
    """Prüfpunkt 12 als Phase von FunctionFlow, wie GesturePhases und SwitchPhase."""

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
        if not applied or not applied.get("ops"):
            unmeasured(self.data, "revise", "kein übernommener Schritt")
            return
        if len(applied["ops"]) <= len((states.get("before") or {}).get("ops") or ()):
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
                self.preview_steps(
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
