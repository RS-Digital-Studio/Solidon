"""Prüfpunkt 13: die Auswahlmatrix eines Funktionsfalls (D0-P, RM-737).

Aus ``function_bench`` gelöst, damit der Fall unter der Größengrenze der
Codestruktur bleibt (Regel 6, 2 000 Zeilen). :class:`MatrixPhase` stellt sechs
Auswahlstufen her und fragt je Stufe, wie das Ziel der Zeile dasteht:
angeboten (und wirksam?), grau mit Grund, fehlt oder nicht herstellbar.

**Derselbe Weg wie der Hauptweg** (FD-100): Nach der Auswahl der Stufe folgen
die übrigen Klicks der Zeile — der Befund, an dem eine Befundhandlung steht,
ein Rechtsklick vor einem Kontextmenü (:func:`way_of`) —, und eine Handlung,
die nach der Auswahl in der Maßgruppe im Bild steht, steht dort, ohne Klick
(F-20). Vorher klickte die Matrix nur die Auswahl: *Auf das Bett setzen* hieß
an allen Stufen „fehlt“, weil der Befund nie gewählt war, und *Bohrung ändern*
am Merkmal „steht nicht da“, weil sie im Bild stand. Der Gegenfall bleibt: Wo
die Handlung an einer Stufe nicht gilt, fehlt sie. ``FunctionFlow`` erbt die
Phase.

**Ein Fenster als Ziel wird gelesen, solange es steht** (RC-4,
:meth:`MatrixPhase.window_step`): Der Automat räumt ein modales Fenster am Ende
des Laufs mit Escape ab, danach gefragt hieß jede Fensterzeile „fehlt“. Auch
der Lizenzlauf (Prüfpunkt 18) liest so.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final

from tools import function_surface as surfaces
from tools.function_checks import MATRIX_UNREACHABLE, SELECTION_STAGES
from tools.function_machine import Step, StepMachine
from tools.function_protocol import compare_prints
from tools.function_setup import route_of, selected_feature, walk_target

if TYPE_CHECKING:
    from tools.function_bench import FunctionFlow

#: Die Klicks, mit denen ein Weg auswählt: Baumzeile, Stelle und Kante im Bild.
#: Die Matrix ersetzt sie durch die Auswahl ihrer Stufe.
SELECTION_PREFIXES: Final[tuple[str, ...]] = ("tree.row:", "view:", "view.edge:")


def is_window(target: str) -> bool:
    """Ob das Ziel ein Fenster ist, das ein anderer Klick öffnet (Rückfrage, Meldung)."""
    return target.partition(":")[0] in surfaces.OPENED_ELSEWHERE


def way_of(row: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Der Weg der Zeile ohne ihre Auswahl und ohne ihr Ziel — was nach jeder Stufe folgt."""
    target = walk_target(row)
    return [
        (name, button)
        for name, button in route_of(row)
        if name != target and not name.startswith(SELECTION_PREFIXES)
    ]


class MatrixPhase:
    """Prüfpunkt 13 als Phase von ``FunctionFlow``, wie ``SwitchPhase`` und ``RevisionPhase``."""

    def matrix_features(self: FunctionFlow) -> list[tuple[str, str, str]]:
        """Die Merkmale der Startszene, das Merkmal der Zeile und seine Art zuerst.

        Die Stufe „ein Merkmal“ wählt so das Merkmal, an dem die Zeile steht
        (``Row.route``), „mehrere Merkmale“ dazu eines derselben Art — vorher
        das erste der Szene, gleich welcher Art.
        """
        result = self.session.last_result
        objects = list(result.scene.objects.items()) if result is not None else []
        features = [
            (str(key), str(name), str(feature.kind))
            for key, entry in objects
            for name, feature in entry.features.items()
        ]
        selected = selected_feature(self.row)
        own = [entry for entry in features if (entry[0], entry[1]) == selected]
        kind = own[0][2] if own else None
        rest = [entry for entry in features if entry not in own]
        return own + sorted(rest, key=lambda entry: entry[2] != kind)

    def phase_matrix(self: FunctionFlow) -> None:
        """Prüfpunkt 13: sechs Auswahlstufen — angeboten, grau, fehlt, nicht herstellbar."""
        result = self.session.last_result
        objects = list(result.scene.objects) if result is not None else []
        features = self.matrix_features()
        bodies = [str(key) for key in objects]
        # Eine Kante ist kein Merkmal, sondern eine Stelle im Bild: erst der
        # Körper, dann der Klick auf seine Kante (gestufte Tiefe, §18.5). Ohne
        # sichtbare Kante hat die Szene dafür zu wenig — kein Klick ins Leere,
        # der „nicht auffindbar“ gegen die Anwendung schriebe (Durchsicht
        # welle4 C-M4: vorher suchte die Matrix Merkmale der Art ``edge``).
        edge = f"view.edge:{bodies[0]}" if bodies else ""
        try:
            if edge:
                self.ports.next_click(edge)
        except LookupError:
            edge = ""
        clicks: dict[str, list[tuple[str, str]] | None] = {
            "ohne": [],
            "ein_koerper": [(f"tree.row:{bodies[0]}", "left")] if bodies else None,
            "mehrere_koerper": (
                [(f"tree.row:{bodies[0]}", "left"), (f"tree.row:{bodies[1]}", "ctrl+left")]
                if len(bodies) > 1
                else None
            ),
            "ein_merkmal": (
                [(f"tree.row:{features[0][0]}.{features[0][1]}", "left")] if features else None
            ),
            "mehrere_merkmale": (
                [
                    (f"tree.row:{features[0][0]}.{features[0][1]}", "left"),
                    (f"tree.row:{features[1][0]}.{features[1][1]}", "ctrl+left"),
                ]
                if len(features) > 1
                else None
            ),
            "eine_kante": [(f"tree.row:{bodies[0]}", "left"), (edge, "left")] if edge else None,
        }
        assert tuple(clicks) == tuple(SELECTION_STAGES)
        target = walk_target(self.row)
        way = way_of(self.row)
        matrix: dict[str, Any] = {}
        for stage, route in clicks.items():
            if route is None:
                matrix[stage] = {
                    "state": MATRIX_UNREACHABLE,
                    "reason": "die Startszene hat dafür zu wenig",
                    "effective": None,
                }
                continue
            if not self.reset():
                # Ohne Startszene stünde die Stufe an dem, was die vorige liegen
                # ließ — eine andere Lage (Durchsicht welle4 C-L15).
                matrix[stage] = {
                    "state": MATRIX_UNREACHABLE,
                    "reason": "die Startszene ließ sich nicht herstellen",
                    "effective": None,
                }
                continue
            selection = [self.key_step("Escape", "auswahl leeren")] if not route else []
            # Nach der Auswahl der Weg der Zeile: der Befund, der Rechtsklick (FD-100).
            selection += [self.walker.step(name, button) for name, button in [*route, *way]]
            # Gelesen wird, wenn das Ziel steht, im Bild steht oder so lange ohne
            # Weg blieb wie auf dem Hauptweg (``Walk.stable``): Die Kantenzeilen
            # baut das Merkmalfenster nach dem Klick, und sofort gefragt hieß die
            # Zeile an der gewählten Kante „fehlt“ (Prüfstandlauf zu C-M4, Fall 002).
            settled = self.walker.stable(target)
            selection.append(
                Step(
                    f"{target} steht",
                    lambda machine: None,
                    ready=lambda settled=settled: self.in_view_now(target) or settled(),
                )
            )
            read: dict[str, Any] = {}
            if is_window(target):
                selection.append(self.window_step(target, read))
            if not self.run_steps(f"matrix {stage} auswahl", selection):
                matrix[stage] = {
                    "state": MATRIX_UNREACHABLE,
                    "reason": "die Auswahl oder der Weg der Zeile danach ließ sich nicht gehen",
                    "effective": None,
                }
                continue
            matrix[stage] = (
                read if is_window(target) else self.offer_state(target, f"matrix {stage}")
            )
        self.data["matrix"] = matrix

    def licence_state(
        self: FunctionFlow, target: str, inputs: list[str], read: Mapping[str, Any]
    ) -> tuple[str, str]:
        """Wie das Ziel im Lizenzlauf dasteht (Prüfpunkt 18): Zustand und Grund.

        Ein Fenster als Ziel hat sein Lauf schon gelesen, solange es stand
        (``read``, :meth:`window_step`). Mit Bild steht eine Handlung am Merkmal in
        der Maßgruppe; ihr Feld ist dann, was offen oder grau dasteht, der Kopf im
        Merkmalfenster ist verborgen (F-20: vorher „fehlt“ in jedem Lizenzzustand,
        auch „licensed“). Der Grund kommt nur aus dem grauen Ziel; fehlt es, ist das
        kein Grund, sondern ein eigener Zustand (Durchsicht welle4 C-S1).
        """
        if read:
            return str(read["state"]), str(read["reason"]) if read["state"] == "grau" else ""
        probe = (
            surfaces.field_name(self.window, inputs[0])
            if target.startswith("feature:") and surfaces.in_view(self.window, inputs)
            else target
        )
        grey = surfaces.grey_reason(self.window, probe)
        try:
            self.ports.next_click(probe)
        except LookupError:
            return "fehlt", ""
        return ("grau", grey) if grey is not None else ("angeboten", "")

    def window_step(self: FunctionFlow, target: str, into: dict[str, Any]) -> Step:
        """Ein Fenster als Ziel lesen, solange es steht — ohne Klick in seine Mitte (RC-4).

        Erreicht ist es, sobald es dasteht (FD-101, ``path_steps``): angeboten und
        wirksam, denn der Weg hat es geöffnet. Steht es nicht, nennt der Öffner der
        Zeile seinen Grund, wenn er grau ist; sonst fehlt es.
        """
        openers = [name for name, _button in route_of(self.row) if name != target]

        def read(machine: StepMachine) -> None:
            try:
                self.ports.next_click(target)
            except LookupError as error:
                grey = surfaces.grey_reason(self.window, openers[-1]) if openers else None
                state = "grau" if grey is not None else "fehlt"
                into.update(state=state, reason=grey or str(error), effective=None)
            else:
                into.update(state="angeboten", reason="", effective=True)

        return Step(f"{target} lesen", read, ready=self.walker.stable(target))

    def in_view_now(self: FunctionFlow, target: str) -> bool:
        """Ob die Handlung der Zeile gerade in der Maßgruppe im Bild steht (F-20, FD-100)."""
        inputs = list(self.spec.get("inputs") or {})
        return target.startswith("feature:") and (
            surfaces.feature_in_view(self.window, target) or surfaces.in_view(self.window, inputs)
        )

    def offer_state(self: FunctionFlow, target: str, label: str) -> dict[str, Any]:
        """Wie ein Ziel gerade dasteht: angeboten (und wirksam?), grau mit Grund, fehlt.

        Steht die Handlung in der Maßgruppe im Bild, ist sie dort angeboten,
        ohne Klick — ihre Felder stehen zum Tippen offen (Ort ``ansicht``); grau
        heißt dann: das Feld ihrer ersten Eingabe ist gesperrt, mit seinem Grund.
        """
        from tools import function_capture as capture
        from tools.function_bench import surface_signature

        if self.in_view_now(target):
            inputs = list(self.spec.get("inputs") or {})
            probe = surfaces.field_name(self.window, inputs[0]) if inputs else ""
            grey = surfaces.grey_reason(self.window, probe) if probe else None
            if grey is not None:
                return {"state": "grau", "reason": grey, "effective": None, "place": "ansicht"}
            return {"state": "angeboten", "reason": "", "effective": True, "place": "ansicht"}
        try:
            self.ports.next_click(target)
        except LookupError as error:
            return {"state": "fehlt", "reason": str(error), "effective": None}
        grey = surfaces.grey_reason(self.window, target)
        if grey is not None:
            return {"state": "grau", "reason": grey, "effective": None}
        before = self.scene_now()
        result_before = self.session.last_result
        difference = self.window.viewport.difference
        shown = surface_signature(self.surface())
        opened: dict[str, bool] = {}

        def effects() -> dict[str, bool]:
            return {
                "modal": capture.modal_now() is not None,
                "dialog": surfaces.open_dialog(self.window) is not None,
                # Was der Kunde an seiner Fläche sieht: Felder klappen auf (F-23).
                "surface": surface_signature(self.surface()) != shown,
                "preview": self.window.viewport.difference is not difference,
                "result": self.session.last_result is not result_before,
            }

        def look(machine: StepMachine) -> None:
            opened.update(effects())
            self.mark_own(machine)

        # Erst warten, bis eine Wirkung da ist oder die Frist um ist, dann lesen
        # (Review M1): Vorschau und Ergebnis kommen später als ein Klick.
        self.run_steps(
            f"{label} klick",
            [
                self.walker.step(target),
                self.until_step(
                    "wirkung", lambda: any(effects().values()) and not self.session.busy
                ),
                Step("wirkung lesen", look),
            ],
        )
        after = self.scene_now()
        effective = any(opened.values()) or compare_prints(before, after)["same"] is False
        return {"state": "angeboten", "reason": "", "effective": effective}
