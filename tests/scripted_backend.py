"""Ein Modell, das sagt, was man ihm aufgetragen hat (Bauplan §35, §40).

Die Agenten-Suite muss die Mechanik prüfen, nicht das Wetter: trägt der
Kontext die Auswahl, ist ein Vorschlag genau eine Transaktion, nimmt ein Undo
ihn wirklich zurück. Nichts davon braucht ein Sprachmodell, und es gegen eines
laufen zu lassen machte die Suite langsam, teuer und wackelig zugleich.

Also fährt die Suite dieses Backend. Es antwortet aus einem Skript und behält
alles, wonach es gefragt wurde — so kann ein Test behaupten, dass Steckbrief,
Prüfbericht und Regelsammlung das Modell wirklich erreicht haben.

**Hier und nicht in ``app/core/backends/``**, wo es bis zum 02.09.2026 lag:
Was nur die Suite braucht, reist nicht zum Kunden (``app/CLAUDE.md`` —
„Nichts hier ist ein Hilfsprogramm"). Keine Anwendungsdatei importierte es
je; sieben Testdateien tun es, und die finden es hier, wie ``agent_cases``
und ``php_probe``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.backends.llm import Message, Reply
from app.core.backends.mesh import (
    CancelledFn,
    GeneratedMesh,
    GenerationFailed,
    _silent,
)
from app.core.errors import OperationCancelled
from app.core.geom.mesh import read_mesh
from app.core.types import ProgressFn
from app.i18n import _

Answer = Reply | Callable[[Sequence[Message]], Reply]


@dataclass(slots=True)
class ScriptedBackend:
    """Gibt vorbereitete Antworten aus und schreibt das Gespräch mit."""

    answers: list[Answer] = field(default_factory=list)
    model: str = "scripted"
    seen: list[list[Message]] = field(default_factory=list)
    """Jede Anfrage der Reihe nach — hieraus liest die Suite den Kontext."""
    tools_seen: list[tuple[str, ...]] = field(default_factory=list)
    images_supported: bool = False
    """Einstellbar, damit ein Test beide Wege fährt: mit Bildern und ohne."""

    @property
    def id(self) -> str:
        return "scripted"

    @property
    def available(self) -> bool:
        return True

    @property
    def supports_images(self) -> bool:
        return self.images_supported

    def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]] = (),
        *,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
    ) -> Reply:
        self.seen.append(list(messages))
        self.tools_seen.append(tuple(str(entry.get("name", "")) for entry in tools))
        if not self.answers:
            return Reply(text="", model=self.model, stop_reason="end_turn")
        answer = self.answers.pop(0)
        reply = answer(messages) if callable(answer) else answer
        return Reply(
            text=reply.text,
            tool_calls=reply.tool_calls,
            model=reply.model or self.model,
            stop_reason=reply.stop_reason or ("tool_use" if reply.tool_calls else "end_turn"),
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            # Die Cache-Zahlen reisen mit, sonst misst ein Szenario mit
            # ihnen stillschweigend ungewichtet — das Budget rechnet damit.
            cache_read_tokens=reply.cache_read_tokens,
            cache_write_tokens=reply.cache_write_tokens,
        )

    @property
    def last_system_prompt(self) -> str:
        """Was dem Modell bei der letzten Anfrage über die Welt gesagt wurde."""
        if not self.seen:
            return ""
        return " ".join(entry.content for entry in self.seen[-1] if entry.role == "system")


# --- Der Generator der Suite (Weg 3) -------------------------------------------------
#
# Bis zum 22.09.2026 lag er in ``app/core/backends/mesh.py`` und reiste damit
# im Kundenpaket mit — derselbe Befund wie beim Sprachmodell darüber, nur
# zwanzig Tage später: Keine Anwendungsdatei importierte ihn.


@dataclass(slots=True)
class ScriptedMeshBackend:
    """Ein Generator, der eine vorbereitete Datei zurückgibt (§35).

    Weg 3 muss ohne Grafikkarte testbar sein, und ein Test, der nur saubere
    Geometrie zu sehen bekäme, bewiese nichts — vorbereitet werden hier also
    die kaputten Körper, die ein Generator wirklich liefert.
    """

    answers: dict[str, bytes] = field(default_factory=dict)
    fallback: bytes | None = None
    suffix: str = ".stl"
    calls: list[tuple[str, int]] = field(default_factory=list)

    @property
    def id(self) -> str:
        return "scripted"

    @property
    def available(self) -> bool:
        return bool(self.answers) or self.fallback is not None

    def text_to_mesh(
        self,
        prompt: str,
        *,
        seed: int = 0,
        progress: ProgressFn = _silent,
        cancelled: CancelledFn | None = None,
    ) -> GeneratedMesh:
        self.calls.append((prompt, seed))
        progress(0.5, str(_("Modell wird erzeugt")))
        # Auch der Doppel fragt: Ein Test soll den Abbruchweg fahren können,
        # ohne eine Grafikkarte und ohne eine Sekunde Wartezeit.
        if cancelled is not None and cancelled():
            raise OperationCancelled
        payload = self.answers.get(prompt, self.fallback)
        if payload is None:
            raise GenerationFailed(detail=f"nothing scripted for {prompt!r}")
        return self._as_result(payload, prompt, seed)

    def image_to_mesh(
        self,
        image: bytes,
        *,
        seed: int = 0,
        progress: ProgressFn = _silent,
        cancelled: CancelledFn | None = None,
    ) -> GeneratedMesh:
        self.calls.append((f"<image {len(image)}>", seed))
        if cancelled is not None and cancelled():
            raise OperationCancelled
        if self.fallback is None:
            raise GenerationFailed(detail="nothing scripted for an image")
        return self._as_result(self.fallback, "", seed)

    def _as_result(self, payload: bytes, prompt: str, seed: int) -> GeneratedMesh:
        return GeneratedMesh(
            mesh=read_mesh(payload, self.suffix),
            payload=payload,
            suffix=self.suffix,
            backend=self.id,
            prompt=prompt,
            seed=seed,
        )
