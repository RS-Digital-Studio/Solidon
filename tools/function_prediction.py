"""Das Vorhersagetor: vor dem Handlungsklick eine Vorhersage binden (V4, FD-168, RM-737).

V4 fragt, ob der Kunde aus Titel, erstem Satz und Vorschau vorhersagen kann, was
der Klick auf die Handlung tut. Ein *gut* trägt nur eine Vorhersage, die **vor**
dem Klick stand (FD-148, ``prediction_bound``); geschrieben nach dem Lauf, ist
sie ein Teilbeleg. Bis hierher hielt kein Fallprozess an: Die Fälle 29, 36 und 37
schrieben ihre Vorhersage nach dem Lauf, und jedes V4 blieb offen.

Ein Fall mit ``Variant.predict`` (Variantensatz ``vorhersage`` oder ein
Sprachfall daneben) hält vor jedem Handlungsklick an: im Hauptweg vor dem
Übernehmen, im Sprachfall vor dem Klick einer Soforthandlung. Je Klick ein
Ordner (:meth:`PredictionGate.folder`) mit diesen Dateien:

1. ``ready.json`` — der Fall wartet: Bilder vor dem Klick mit SHA256, die
   sichtbaren Texte, ``nonce``, ``commit``, ``row``, ``target`` und
   ``before_sha256`` (SHA256 der Bildliste).
2. ``prediction.json`` — schreibt der Prüfer, nachdem er nur diese Bilder
   gesehen hat: ``nonce``, ``commit``, ``row``, ``before_sha256`` unverändert
   aus ``ready.json``, dazu ``title``, ``first_sentence``, ``preview``,
   ``prediction`` (UTF-8).
3. ``prediction-before-click.json`` — die Bytes der freigegebenen Vorhersage,
   unverändert und nur neu angelegt; ``release.json`` mit ihrem SHA256, der
   Zeit und dem Schritt- und Bildindex. Erst dann fällt der Klick.
4. ``after.json`` — die Bilder nach dem Klick mit SHA256.

Ohne gültige Vorhersage binnen :data:`PREDICTION_WAIT_S` fällt der Klick
trotzdem, damit der übrige Fall gemessen wird; das Protokoll sagt warum
(``prediction.reason``), und V4 bleibt *offen*. Eine Vorhersage, die nicht zum
Bild gehört oder ein Feld leer lässt, wird abgewiesen (``prediction.rejected``),
und das Tor wartet weiter auf eine gültige.

Das Protokoll trägt die Bindung als ``prediction.bound``: Pfad relativ zum
Lauf und SHA256, so wie das Urteil sie als ``prediction_bound`` nennt
(``function_verdict_rules.release_problems`` hält beide gleich).
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

from tools.function_machine import STEP_TIMEOUT_S, Step

#: Wie lange ein Fall vor einem Klick höchstens auf die Vorhersage wartet (Sekunden).
PREDICTION_WAIT_S: Final = 600.0
#: Wie oft das Tor nach ``prediction.json`` sieht (Sekunden).
POLL_S: Final = 0.2

READY: Final = "ready.json"
PREDICTION: Final = "prediction.json"
SEALED: Final = "prediction-before-click.json"
RELEASE: Final = "release.json"
AFTER: Final = "after.json"

#: Was eine Vorhersage unverändert aus ``ready.json`` übernimmt — die Bindung ans Bild.
BINDING_KEYS: Final = ("nonce", "commit", "row", "before_sha256")
#: Was der Prüfer schreibt: Titel, erster Satz und Vorschau, wie er sie liest, und
#: was der Klick seiner Erwartung nach tut (Skill ux-review, V4).
PREDICTION_KEYS: Final = ("title", "first_sentence", "preview", "prediction")

#: Gründe ohne Bindung — das Protokoll nennt sie in ``prediction.reason``.
NO_PICTURE: Final = "kein Bild vor dem Klick; ohne Bild gibt es nichts vorherzusagen"
NO_PREDICTION: Final = "keine gültige Vorhersage binnen {seconds:.0f} s; der Klick fiel ohne"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def bound_of(path: str, sha256: str) -> str:
    """Die Bindung, wie Protokoll und Urteil sie nennen: Pfad relativ zum Lauf, SHA256."""
    return f"{path} {sha256}"


def prediction_problems(prediction: object, before: Mapping[str, Any]) -> list[str]:
    """Warum eine Vorhersage nicht freigegeben wird — leer, wenn sie zum Bild gehört."""
    if not isinstance(prediction, Mapping):
        return ["keine JSON-Tabelle"]
    problems = [
        f"{key} gehört nicht zu diesem Bild"
        for key in BINDING_KEYS
        if prediction.get(key) != before.get(key)
    ]
    problems += [
        f"{key} ist leer" for key in PREDICTION_KEYS if not str(prediction.get(key) or "").strip()
    ]
    return problems


class PredictionGate:
    """Ein Tor vor einem Klick: Bild und Texte vorlegen, Vorhersage binden, freigeben.

    ``picture(label)`` nimmt das Fenster und seine offenen Dialoge auf und hängt
    die Pfade relativ zu ``out`` an ``data["images"]`` (``FunctionFlow.picture``);
    ``texts()`` liest die sichtbaren Texte. ``clock`` ist im Test die Uhr des
    nachgestellten Zeitgebers.
    """

    def __init__(
        self,
        folder: Path,
        out: Path,
        data: dict[str, Any],
        *,
        row: str,
        target: str,
        picture: Callable[[str], None],
        texts: Callable[[], list[str]],
        label: Callable[[str], str] = lambda name: name,
        clock: Callable[[], float] = time.monotonic,
        wait_s: float = PREDICTION_WAIT_S,
    ) -> None:
        self.folder = folder
        self.out = out
        self.data = data
        self.row = row
        self.target = target
        self.picture = picture
        self.texts = texts
        self.label = label
        self.clock = clock
        self.wait_s = wait_s
        self.before: dict[str, Any] | None = None
        self.started = 0.0
        self.next_poll = 0.0
        self.seen: set[str] = set()
        self.record: dict[str, Any] = {
            "ready": None,
            "target": target,
            "bound": None,
            "path": None,
            "sha256": None,
            "step_index": None,
            "image_index": None,
            "reason": None,
            "rejected": [],
            "after": [],
        }

    # --- Schritte --------------------------------------------------------------------

    def before_steps(self) -> list[Step]:
        """Vor dem Klick: anfragen, dann warten, bis gebunden ist oder die Frist ablief."""
        return [
            Step("vorhersage anfragen", self.ask),
            Step(
                "vorhersage binden",
                lambda machine: None,
                ready=self.bound,
                timeout_s=self.wait_s + STEP_TIMEOUT_S,
            ),
        ]

    def after_steps(self) -> list[Step]:
        """Nach dem Klick und seiner Wirkung: das Bild danach, mit SHA256."""
        return [Step("vorhersage: bild danach", self.after)]

    # --- Ablauf ----------------------------------------------------------------------

    def _pictures(self, name: str) -> dict[str, str]:
        start = len(self.data["images"])
        self.picture(self.label(name))
        return {
            path: digest((self.out / path).read_bytes()) for path in self.data["images"][start:]
        }

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.out).as_posix()

    def ask(self, machine: Any) -> None:
        """Bild und Texte vorlegen und ``ready.json`` schreiben; der Fall wartet danach."""
        self.data["prediction"] = self.record
        if self.folder.exists() and any(self.folder.iterdir()):
            # Ein früherer Lauf dieses Falls: sein Tor bleibt als Beleg daneben stehen.
            self.folder.rename(self.folder.with_name(f"{self.folder.name}-{uuid.uuid4().hex[:8]}"))
        self.folder.mkdir(parents=True)
        images = self._pictures("v4-vorher")
        self.started = self.clock()
        if not images:
            self.record["reason"] = NO_PICTURE
            return
        before = {
            "nonce": str(uuid.uuid4()),
            "commit": str((self.data.get("version") or {}).get("commit") or ""),
            "row": self.row,
            "target": self.target,
            "created_utc": _utc(),
            "images": images,
            "texts": self.texts(),
            "before_sha256": digest(json.dumps(images, sort_keys=True).encode("utf-8")),
        }
        self.before = before
        ready = self.folder / READY
        _write(ready, before)
        self.record["ready"] = self._relative(ready)
        print(f"V4 wartet: {ready}", flush=True)

    def bound(self) -> bool:
        """Ob der Klick fallen darf: gebunden, ohne Bild oder nach Ablauf der Frist."""
        if self.before is None or self.record["bound"] is not None:
            return True
        now = self.clock()
        if now - self.started > self.wait_s:
            self.record["reason"] = NO_PREDICTION.format(seconds=self.wait_s)
            return True
        if now < self.next_poll:
            return False
        self.next_poll = now + POLL_S
        path = self.folder / PREDICTION
        if not path.is_file():
            return False
        raw = path.read_bytes()
        sha256 = digest(raw)
        if sha256 in self.seen:
            return False
        self.seen.add(sha256)
        try:
            prediction = json.loads(raw.decode("utf-8-sig"))
        except ValueError as error:
            problems = [f"nicht lesbar: {error}"]
        else:
            problems = prediction_problems(prediction, self.before)
        if problems:
            self.record["rejected"].append({"sha256": sha256, "problems": problems})
            return False
        self.release(raw, sha256)
        return True

    def release(self, raw: bytes, sha256: str) -> None:
        """Die Vorhersage versiegeln und freigeben — danach fällt der Klick."""
        sealed = self.folder / SEALED
        with sealed.open("xb") as handle:
            handle.write(raw)
        steps, images = len(self.data["steps"]), len(self.data["images"])
        _write(
            self.folder / RELEASE,
            {
                "prediction_sha256": sha256,
                "released_utc": _utc(),
                "target": self.target,
                "before_sha256": (self.before or {}).get("before_sha256"),
                "step_index": steps,
                "image_index": images,
            },
        )
        path = self._relative(sealed)
        self.record.update(
            bound=bound_of(path, sha256),
            path=path,
            sha256=sha256,
            step_index=steps,
            image_index=images,
        )

    def after(self, machine: Any) -> None:
        if self.before is None:
            return
        images = self._pictures("v4-nachher")
        _write(self.folder / AFTER, {"images": images})
        self.record["after"] = sorted(images)


def gate_for(
    flow: Any, target: str, *, folder: Path, label: Callable[[str], str] | None = None
) -> PredictionGate:
    """Das Tor eines Falls mit ``Variant.predict`` vor dem Klick auf ``target``.

    ``flow`` ist ein ``FunctionFlow``: Fenster, Protokoll, Bild. Im Sprachfall
    trägt ``label`` Sprache und Zeile in die Bildnamen.
    """
    from tools import function_capture as capture
    from tools import function_surface as surfaces

    def texts() -> list[str]:
        shown = [flow.window, *surfaces.windows_to_picture(flow.window)]
        return [text for root in shown for text in capture.visible_texts(root)]

    return PredictionGate(
        folder,
        flow.out,
        flow.data,
        row=str(flow.row.get("id") or ""),
        target=target,
        picture=flow.picture,
        texts=texts,
        label=label or (lambda name: name),
    )


def extra_s(variant: Any) -> float:
    """Wie viel länger eine Phase mit Tor dauern darf als ohne (``PHASE_TIMEOUT_S``)."""
    return PREDICTION_WAIT_S + STEP_TIMEOUT_S if variant.predict else 0.0
