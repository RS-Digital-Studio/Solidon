"""Der Sprachfall: je Fläche eines Pakets die Aufnahmen in einer Sprache (D0-P, RM-737).

:class:`LanguageFlow` geht für jede Zeile eines Pakets bis zu ihrer Fläche
(``FunctionFlow`` mit der Phase ``surface``) und schreibt je Fläche ein
Protokoll unter ``surfaces/``. Vor jeder Fläche steht ein Anfangsvermerk in
``bench.json``; ein Vermerk ohne Ergebnis heißt, der vorige Lauf starb dort, und
die Fläche wird mit diesem Fehler übersprungen (Review M14).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.function_bench import FunctionFlow
from tools.function_protocol import empty_protocol, safe_name, unmeasured
from tools.function_setup import Variant, place_window


class LanguageFlow:
    """Ein Sprachfall: je Zeile eines Pakets die Fläche öffnen und ihre Texte messen (Prüfpunkt 9).

    Ein Prozess je Sprache und Paket — sechs Sprachen in einem Prozess brechen
    ab (``tools/CLAUDE.md``). Je Fläche ein Protokoll nach demselben Schema unter
    ``surfaces/<zeile>.json``, mit ``texts`` und ``fields``; was dort steht, wird
    beim nächsten Lauf übersprungen (wieder aufnehmbar je Fläche).
    """

    def __init__(
        self,
        application: Any,
        window: Any,
        folder: Path,
        bench: dict[str, Any],
        persist: Callable[[], None],
        rows: Sequence[Mapping[str, Any]],
        variant: Variant,
        scenes: Path,
        version: Mapping[str, str],
    ) -> None:
        self.application = application
        self.window = window
        self.folder = folder
        self.bench = bench
        self.persist = persist
        self.rows = rows
        self.variant = variant
        self.scenes = scenes
        self.version = version

    def run(self) -> None:
        from tools.file_acceptance import write_json

        surfaces = self.folder / "surfaces"
        done: list[str] = []
        placed = place_window(self.application, self.window, self.variant)
        crashed = str(self.bench.get("surface_started") or "")
        for row in self.rows:
            path = surfaces / f"{safe_name(str(row.get('id', '')))}.json"
            if path.exists():
                done.append(str(row.get("id")))
                continue
            size = [self.window.width(), self.window.height()]
            protocol = empty_protocol(row, self.variant.protocol(placed, size), self.version)
            if crashed and str(row.get("id")) == crashed:
                # Die Fläche, an der der vorige Lauf starb, kommt nicht wieder dran —
                # sonst begänne jeder neue Lauf mit ihr und stürbe wieder (Review M14).
                protocol["errors"].append("Die Fläche brach im vorigen Lauf den Prozess ab")
                unmeasured(protocol, "texts", "abgestürzt")
                write_json(path, protocol)
                done.append(crashed)
                self.bench["surface_started"] = None
                self.persist()
                continue
            # Vor jeder Fläche ein Anfangsvermerk; ohne Ergebnis danach war es ein Absturz.
            self.bench["surface_started"] = str(row.get("id"))
            self.persist()
            flow = FunctionFlow(
                self.application,
                self.window,
                self.folder,
                protocol,
                lambda: None,
                row,
                self.variant,
                self.scenes,
                bench=self.bench,
                out=self.folder.parent.parent,
            )
            if flow.reset():
                flow.phase_surface()
            write_json(path, protocol)
            done.append(str(row.get("id")))
            self.bench["surfaces_done"] = done
            self.bench["surface_started"] = None
            self.persist()
        self.bench["surfaces_done"] = done
        self.persist()
