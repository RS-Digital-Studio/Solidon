"""Funktionsfälle des Prüfstands: der Kunde bedient eine Funktion, gemessen wird (D0, RM-737).

Kein eigener Einstieg. ``tools/file_acceptance.py`` legt die Fälle an
(``inventory --functions``), startet je Fall einen Prozess mit eigenem Profil
(``run``) und reicht ihn hierher weiter (``child`` → :class:`FunctionFlow`). Ein
drittes Fensterwerkzeug neben ``file_acceptance`` und ``make_guides`` gibt es
nicht (Konzept Funktionsdurchgang §12); ``tests/test_function_bench.py`` hält,
dass dieses Modul weder ``__main__`` noch ``argparse`` trägt.

Drei Grundsätze (Konzept §5, Plan D0, Abschnitt 0):

* **Jede Handlung ist ein Eingabeereignis an der Stelle, die der Kunde trifft.**
  ``guide_targets.next_click`` nennt den nächsten Klick auf seinem Weg — Reiter,
  Klappe, Menü, Untermenü, Aufklappen, Rollen, zuletzt das Ziel —, und
  ``guide_targets.widget_under`` sagt, was an dieser Stelle wirklich liegt. Ist
  es weder das Ziel noch eines seiner Kinder, ist das der Fund „verdeckt“; bleibt
  kein Weg, „nicht auffindbar“ (:class:`Walk`). Zahlen werden getippt, mit dem
  Dezimalzeichen der Sprache (:func:`typed_number`). Was so nicht erreichbar ist,
  wird ein Ziel im Wortschatz — nie ein Zugriff auf private Attribute, nie ein
  Kernaufruf. ``tests/test_function_bench.py`` sucht per AST nach ``click``,
  ``set_value*``, ``emit``, ``session.apply``, ``trigger``, ``select_*`` und
  ``action_undo``/``action_redo`` (:data:`FORBIDDEN_CALLS`).
* **Ereignisgetrieben** (B6): Ein Klick, der einen Dialog über ``exec()`` öffnet,
  kehrt erst nach dessen Ende zurück, und ein linear geschriebener Ablauf bliebe
  dort stehen. :class:`StepMachine` plant deshalb den nächsten Schritt über einen
  Zeitgeber **vor** der Handlung; er läuft in der verschachtelten Schleife des
  Dialogs weiter (Muster ``make_web_images.while_open``).
* **Abgelesen wird, was der Kunde sieht** — Vorschauband, Knopfzustand mit
  Grund, Statuszeile —, dazu der Szenenabdruck aus Dokument und Körpern
  (:func:`scene_print`), der sagt, ob Rückgängig wirklich zurückkehrt.

Vorbereitet wird außerhalb der geprüften Handlung: ein Nutzerprofil mit
Sprache, Thema, Einheit und Drucker (:func:`profile_settings`), der Lizenzzustand
und die äußeren Vorbedingungen über dieselben Nahtstellen wie die Suite
(:func:`apply_licence`, :func:`apply_preconditions`) — nur im Kindprozess, ohne
private Schlüssel. Systemdateidialoge prüft nur Stufe C; der Kindprozess setzt
``AA_DontUseNativeDialogs`` (B7).

**Das Messprotokoll gehört D0-U** (``tools/function_checks.PROTOCOL_SCHEMA``):
Feldnamen, Wertebereiche, Lizenzzustände, Auswahlstufen und die Phasen des
Hauptwegs kommen von dort, und ``validate_protocol`` prüft, was der Prüfstand
schreibt (:func:`empty_protocol`, Test in ``tests/test_function_bench.py``).
Zeilen und Startszenen kommen aus ``tools/function_list.py`` (D0-L).
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
import time
import traceback
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final, Protocol

from app.ui.main_window import START_SIZE
from tools.file_acceptance import MATERIAL, PRINTER
from tools.function_capture import run_reference_factor
from tools.function_checks import (
    COVERED,
    LAPTOP_SIZE,
    LICENCE_STATES,
    MAIN_PHASES,
    MATRIX_UNREACHABLE,
    NOT_FOUND,
    PLACES,
    PROTOCOL_SCHEMA,
    SCALES,
    SELECTION_STAGES,
    STARTUP_LICENCE,
    WHY,
    licence_runs,
)
from tools.function_list import PRECONDITIONS as SPEC_PRECONDITIONS

# --- Wege und Funde ---------------------------------------------------------------

#: Warum ein Klick fällt (``guide_targets.next_click``): das Ziel selbst …
TARGET_REASON: Final = "ziel"

#: … oder ein Wegklick davor, der etwas aufdeckt (``function_checks.WHY``).
WAY_REASONS: Final[frozenset[str]] = frozenset(WHY) - {TARGET_REASON}

#: Die Phase des Wegs und die des Übernehmens — zusammen der Hauptweg, den U für
#: E1 bis E4 zählt (``function_checks.MAIN_PHASES``).
PATH_PHASE, APPLY_PHASE = MAIN_PHASES

#: Wie viele Wegklicks ein Ziel höchstens braucht, bevor der Weg als Kreis gilt.
#: Der längste Weg im Bestand ist Menütitel, Untermenü, Eintrag; dazu Reiter,
#: Klappe und Rollen in der Karte — sieben. Einer Luft.
MOST_WAY_CLICKS: Final = 8

#: Takt des Schrittautomaten in Millisekunden.
TICK_MS: Final = 15

#: Ruhe nach einem Klick, bevor der nächste gerechnet wird: Ein Reiter, ein Menü
#: oder eine Klappe steht nach einer Ereignisrunde; die Karte setzt ihre Höhe
#: über einen Nullzeitgeber (``fenster.md``, „Wie die Karten ihre Höhe teilen“).
SETTLE_MS: Final = 120

#: Wie lange ein Schritt auf seine Voraussetzung wartet (Sekunden).
STEP_TIMEOUT_S: Final = 180.0

#: Wie lange der nächste Klick unverändert stehen muss, bevor er fällt (Sekunden):
#: Die Karten setzen ihre Höhen über Nullzeitgeber, mehrere Ereignisrunden nach
#: einem Aufklappen. Die Probezeile ``resize_hole`` traf nach 120 ms noch die
#: Klappe „Parameter“, nach dreißig Ereignisrunden ihre Zeile.
STABLE_S: Final = 0.1

#: Wie lange etwas über dem stillstehenden Klickort liegen muss, bevor es als
#: „verdeckt“ zählt (Sekunden): Wächst der Baum nach einem Aufklappen, setzt er
#: seine Höhe sofort, die Karte ihre erst Runden später — dazwischen liegt die
#: neue Zeile außerhalb ihres Abschnitts, über der Karte oder unter der nächsten
#: Klappe. Ein Kunde sieht diesen Zwischenstand nicht; was nach einer Sekunde
#: noch deckt, sieht er.
COVERED_S: Final = 1.0

#: Ruhe nach dem Tippen einer Suchprobe, bevor die Treffer gelesen werden: Die
#: Suche filtert bei jedem Zeichen, und die Liste baut sich danach in einer
#: Ereignisrunde; eine Sekunde trägt beides auch unter Fremdlast.
SEARCH_SETTLE_MS: Final = 1000

#: Wie lange eine ganze Phase eines Funktionsfalls dauern darf (Sekunden).
PHASE_TIMEOUT_S: Final = 900.0

#: Die Aufrufe, die eine Bedienung umgehen (Konzept §12 „Die Abkürzungen der
#: Bildwerkzeuge“, Plan D0 B5). Ein Name mit ``*`` meint den Anfang.
#: ``setValue``, ``setCurrentIndex``, ``setChecked`` und ``animateClick`` sind
#: dieselben Abkürzungen in Qts Schreibweise.
FORBIDDEN_CALLS: Final[tuple[str, ...]] = (
    "click",
    "animateClick",
    "set_value*",
    "setValue",
    "setCurrentIndex",
    "setChecked",
    "emit",
    "trigger",
    "select_*",
    "action_undo",
    "action_redo",
)


def forbidden_calls(source: str, *, within_class: str | None = None) -> list[tuple[int, str]]:
    """Wo ein Quelltext eine Bedienung umgeht: Zeile und Aufruf.

    ``session.apply`` zählt als Kernaufruf an der Oberfläche vorbei, ein
    ``apply`` an etwas anderem nicht. ``within_class`` prüft nur den Rumpf dieser
    Klasse (``WindowFlow`` in ``file_acceptance``). Der Wächter in
    ``tests/test_function_bench.py`` fährt diese Funktion über die drei Orte und
    einmal über einen Quelltext mit bekannten Verstößen.
    """
    tree = ast.parse(source)
    roots: list[ast.AST] = [tree]
    if within_class is not None:
        roots = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == within_class
        ]
        if not roots:
            raise LookupError(f"Klasse {within_class} steht nicht im Quelltext")
    found: list[tuple[int, str]] = []
    for root in roots:
        for node in ast.walk(root):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            name = node.func.attr
            receiver = ast.unparse(node.func.value)
            if name == "apply" and "session" in receiver.lower():
                found.append((node.lineno, f"{receiver}.apply"))
                continue
            for pattern in FORBIDDEN_CALLS:
                stem = pattern.rstrip("*")
                if name == pattern or (pattern.endswith("*") and name.startswith(stem)):
                    found.append((node.lineno, f"{receiver}.{name}"))
                    break
    return sorted(found)


# --- Vorbereitetes Profil und Vorbedingungen ----------------------------------------


def spec_licence(word: str) -> str:
    """Ein Lizenzwort der Zeilenspezifikation als Zustand des Protokolls.

    Die Wörter gehören D0-L (``function_list.PRECONDITIONS``), die Zustände D0-U
    (``function_checks.LICENCE_STATES``); hier steht nur die Übersetzung.
    „gekauft“ ist ``licensed``, „abgelaufen“ der gesperrte Lauf, den die
    ausgelieferte Fassung erreicht — der erste aus ``licence_runs()``:
    ``expired`` mit ``store.TRIAL_FROM``, sonst ``sale_without_trial``. „demo“
    hat seit der Entscheidung vom 12.10. keinen Lauf mehr: Eine abgelaufene Demo
    startet nicht (der Startfall), eine laufende ist kein eigener Zustand.
    """
    if word in licence_runs():
        # L stellt seine Wörter auf die Namen aus ``app.core.activation`` um.
        return word
    if word == "gekauft":
        return "licensed"
    if word == "abgelaufen":
        return licence_runs()[0]
    raise ValueError(
        f"Lizenzwort {word!r} hat keinen Lauf in der ausgelieferten Fassung"
        f" — erreichbar sind {licence_runs()} (Spezifikation mit D0-L klären)"
    )


#: Äußere Vorbedingungen, die der Prüfstand herstellt — die Liste der
#: Spezifikation ohne die Lizenz, die eine eigene Angabe der Variante ist.
PRECONDITIONS: Final[dict[str, tuple[str, ...]]] = {
    name: states for name, states in SPEC_PRECONDITIONS.items() if name != "licence"
}

#: Drucker und Material je Druckart — der feste Rahmen des Dateiaudits für
#: Filament (``file_acceptance.PRINTER``), das allgemeine Harzprofil für Resin
#: (``knowledge/data/printers.toml``).
PRINTERS: Final[dict[str, tuple[str, str]]] = {
    "filament": (PRINTER, MATERIAL),
    "resin": ("generic-resin-130", "resin"),
}

#: Die Fenstergrößen aus Z6 (``main_window.START_SIZE``, ``function_checks.LAPTOP_SIZE``).
WINDOW_SIZES: Final[tuple[str, ...]] = tuple(
    f"{width}x{height}" for width, height in (START_SIZE, LAPTOP_SIZE)
)

#: Die Phasen je Variantensatz, in ihrer Folge (``FunctionFlow.phase_<name>``).
#: Jede beginnt an der Startszene; ``sprachen`` hat eine eigene Klasse
#: (:class:`LanguageFlow`), ``start`` den echten Startweg (:class:`StartFlow`) —
#: beide deshalb ohne Phase hier.
PHASES: Final[dict[str, tuple[str, ...]]] = {
    "basis": (
        "search",
        "escape",
        "main",
        "revise",
        "fault",
        "matrix",
        "abort",
        "halt",
        "switch",
        "hover",
        "drag",
    ),
    "lizenz": ("licence",),
    "zoll": ("surface",),
    "skalierung": ("surface",),
    "dunkel": ("surface",),
    "bewegung": ("surface",),
    "sprachen": (),
    "start": (),
}


@dataclass(frozen=True, slots=True)
class Variant:
    """Unter welchen Bedingungen ein Fall läuft (Protokollfeld ``variant``).

    ``set`` sagt, welche Phasen laufen: ``basis`` den ganzen Weg, ``lizenz`` nur
    Angebot und Sperre, ``zoll``, ``skalierung``, ``dunkel`` und ``bewegung`` den
    Weg bis zur offenen Fläche mit ihren Aufnahmen, ``start`` den Startweg über
    ``app.ui.app.main`` (:func:`variant_sets`,
    :data:`PHASES`). ``phases`` beschränkt auf einzelne davon — die Nachprüfung
    einer Zeile nach einem Fix fährt nur, was der Fix berührt (Konzept §7).
    ``motion`` falsch heißt: Lauf mit ``SOLIDON3D_MOTION=aus`` (G8).
    """

    set: str = "basis"
    language: str = "de"
    theme: str = "light"
    unit: str = "mm"
    licence: str = "licensed"
    preconditions: Mapping[str, str] = field(default_factory=dict)
    screen: str = ""
    scale: float = 1.0
    window_size: str = ""
    motion: bool = True
    phases: tuple[str, ...] = ()

    @classmethod
    def of(cls, data: Mapping[str, Any] | None) -> Variant:
        """Aus dem Wörterbuch eines Falls; unbekannte Schlüssel sind ein Fehler."""
        data = dict(data or {})
        known = {item.name for item in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"unbekannte Angaben in der Variante: {', '.join(unknown)}")
        if "phases" in data:
            data["phases"] = tuple(data["phases"])
        variant = cls(**data)
        variant.check()
        return variant

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["preconditions"] = dict(self.preconditions)
        data["phases"] = list(self.phases)
        return data

    def protocol(
        self, placed: Mapping[str, Any] | None, window_size: Sequence[int]
    ) -> dict[str, Any]:
        """Die Variante, wie das Protokoll sie trägt: dazu Plattform, Schirm und echte Größe."""
        data = self.as_dict()
        data["platform"] = sys.platform
        data["placed"] = dict(placed or {})
        data["window_size"] = list(window_size)
        return data

    def check(self) -> None:
        """Nur Zustände, die der Prüfstand herstellen kann."""
        from app.core.units import DISPLAY_UNITS

        if self.set not in PHASES:
            raise ValueError(f"Variantensatz {self.set!r} ist keiner aus {tuple(PHASES)}")
        strange = sorted(set(self.phases) - set(PHASES[self.set]))
        if strange:
            raise ValueError(f"Phasen {strange} gibt es im Satz {self.set!r} nicht")
        if self.set == "start":
            if self.licence != STARTUP_LICENCE:
                raise ValueError(f"Der Startfall läuft im Zustand {STARTUP_LICENCE!r}")
        elif self.licence not in LICENCE_STATES:
            raise ValueError(
                f"Lizenzzustand {self.licence!r} ist keiner aus {LICENCE_STATES}"
                f" — {STARTUP_LICENCE!r} ist der Startfall, kein Lauf je Funktion"
            )
        for name, state in self.preconditions.items():
            allowed = PRECONDITIONS.get(name)
            if allowed is None or state not in allowed:
                raise ValueError(f"Vorbedingung {name}={state!r} gibt es nicht")
        if self.unit not in DISPLAY_UNITS:
            raise ValueError(f"Anzeigeeinheit {self.unit!r} ist keine aus {DISPLAY_UNITS}")
        if self.theme not in ("light", "dark"):
            raise ValueError(f"Thema {self.theme!r} gibt es nicht")
        if self.window_size and parse_size(self.window_size) is None:
            raise ValueError(f"Fenstergröße {self.window_size!r} ist nicht BREITExHÖHE")
        if not self.scale > 0:
            raise ValueError(f"Skalierung {self.scale} ist nicht positiv")

    @property
    def printing(self) -> str:
        return self.preconditions.get("printer", PRECONDITIONS["printer"][0])


#: Die Variantensätze der Kommandozeile (``--variants``), je Zeile ausgefaltet —
#: ohne ``lizenz``, dessen Läufe an der Fassung hängen (:func:`variant_sets`).
#: ``sprachen`` ist kein Satz je Zeile: Je Sprache und Paket geht ein Prozess die
#: Flächen aller Zeilen ab (:class:`LanguageFlow`).
FIXED_VARIANT_SETS: Final[dict[str, tuple[dict[str, Any], ...]]] = {
    "basis": ({"set": "basis"},),
    "zoll": ({"set": "zoll", "unit": "in"},),
    "skalierung": (
        *({"set": "skalierung", "window_size": size} for size in WINDOW_SIZES),
        *({"set": "skalierung", "scale": scale} for scale in SCALES if scale != 1.0),
    ),
    "dunkel": ({"set": "dunkel", "theme": "dark"},),
    "bewegung": ({"set": "bewegung", "motion": False},),
    "sprachen": (),
}


def variant_sets() -> dict[str, tuple[dict[str, Any], ...]]:
    """Alle Variantensätze, ``lizenz`` mit den Läufen dieser Fassung (Prüfpunkt 18).

    Welche Zustände erreichbar sind, hängt an ``store.TRIAL_FROM`` der
    Auslieferung (``function_checks.licence_runs``) und wird deshalb zur
    Inventarzeit gelesen, nicht beim Import. ``over`` ist kein Lauf: Eine
    abgelaufene Demo startet nicht, das misst der Startfall der D12-Zeile.
    """
    return {
        **FIXED_VARIANT_SETS,
        "lizenz": tuple({"set": "lizenz", "licence": state} for state in licence_runs()),
    }


def spec_variants(spec: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Was die Spezifikation einer Zeile an der Variante festlegt, und die Gegenläufe.

    Gibt die Grundangaben (Lizenz, Vorbedingungen, Druckart) und je benannter
    Vorbedingung mit zwei Zuständen einen Lauf im anderen Zustand zurück:
    „fehlt“ ist der Fehlerweg, und beide Zustände werden geprüft (Konzept §3).
    """
    preconditions = dict((spec or {}).get("preconditions") or {})
    base: dict[str, Any] = {}
    licence = preconditions.pop("licence", None)
    if licence is not None:
        base["licence"] = spec_licence(str(licence))
    if preconditions:
        base["preconditions"] = {str(key): str(value) for key, value in preconditions.items()}
    others: list[dict[str, Any]] = []
    for name, state in sorted(preconditions.items()):
        states = PRECONDITIONS.get(str(name), ())
        if name == "printer" or len(states) != 2:
            continue
        other = states[1] if state == states[0] else states[0]
        others.append(
            {
                "preconditions": {**base.get("preconditions", {}), str(name): other},
                "phases": ["main"],
            }
        )
    return base, others


def parse_size(text: str) -> tuple[int, int] | None:
    """``"1280x820"`` → ``(1280, 820)``; alles andere ``None``."""
    width, separator, height = text.lower().partition("x")
    if not separator or not width.isdigit() or not height.isdigit():
        return None
    return int(width), int(height)


def profile_settings(variant: Variant) -> Any:
    """Die Einstellungen des vorbereiteten Profils (``UiSettings``).

    Sprache, Thema, Einheit und Drucker kommen aus der Variante. Die
    Ersteinrichtung gilt als erledigt und die Updateprüfung ist aus: Beides ist
    eine eigene Zeile (D12) und gehört nicht in jeden Fall. Die Hinweise zu KI und
    Druck bleiben unbestätigt — sie sind Teil des Kundenwegs (Z2).
    """
    from app.ui.settings import UiSettings

    printer, material = PRINTERS[variant.printing]
    return UiSettings(
        language=variant.language,
        theme=variant.theme,
        display_unit=variant.unit,
        printer=printer,
        material=material,
        first_run_done=True,
        check_for_updates=False,
        update_default_lifted=True,
    )


def write_profile(variant: Variant, recent: Sequence[Path] = ()) -> Path:
    """Schreibt das Profil nach ``user_config_dir`` — nur nach umgebogenem ``APPDATA``.

    ``recent`` füllt *Zuletzt geöffnet*: Der Projektwechsel (Prüfpunkt 16) geht
    über das Menü, wie beim Kunden. Der Aufrufer hat die Nutzerordner vorher auf
    den Profilordner des Falls gelegt (``file_acceptance.isolate``); die Suite tut
    dasselbe in ``tests/conftest.py``.
    """
    from app.ui.settings import save_settings, settings_path

    settings = profile_settings(variant)
    settings.recent = [str(path) for path in recent]
    written = save_settings(settings)
    if written is None:
        raise OSError(f"Das Profil ließ sich nicht schreiben: {settings_path()}")
    return written


def licence_activation(state: str, today: date) -> Any:
    """Der Freischaltzustand zu einem Lauf (``function_checks.LICENCE_STATES``) oder ``over``.

    Die Namen sind Eigenschaften von ``activation.Activation``; gebaut wird je
    ein Zustand, an dem genau diese Eigenschaft gilt — ohne private Schlüssel,
    so wie D0-U ihn in seiner Gegenprobe baut. Kaufcode und Zertifikat tragen den
    Tag der Gerätebindung (``DEVICE_ACTIVATION_FROM``): Erst ab ihm wartet ein
    Kaufcode auf die Freigabe (``needs_activation``), mit Zertifikat ist er
    gekauft. ``sale_without_trial`` und ``expired`` sind derselbe Zustand ohne
    Kaufcode — welcher gilt, entscheidet ``store.TRIAL_FROM`` (:func:`apply_licence`).
    ``over`` ist der Startfall: eine Demo, deren Stichtag gestern war.
    """
    from app.core import activation
    from app.core.activation import key

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=activation.DEVICE_ACTIVATION_FROM,
        order="PRUEFSTAND-1",
        holder="pruefstand@beispiel.de",
    )
    if state == "licensed":
        certificate = activation.ActivationCertificate(
            licence_digest="pruefstand",
            device_public=b"\x01" * 32,
            device_name="Prüfstand",
            activation_id="pruefstand",
            issued_on=activation.DEVICE_ACTIVATION_FROM,
        )
        return activation.Activation(licence=licence, certificate=certificate)
    if state == "needs_activation":
        return activation.Activation(licence=licence)
    if state in ("sale_without_trial", "expired"):
        return activation.Activation(days_left=0)
    if state == STARTUP_LICENCE:
        return activation.Activation(days_left=0, deadline=today - timedelta(days=1))
    raise ValueError(f"Lizenzzustand {state!r} ist keiner aus {(*LICENCE_STATES, STARTUP_LICENCE)}")


def apply_licence(state: str, today: date | None = None) -> Any:
    """Setzt den Lizenzzustand über die Nahtstelle der Suite (``activation._cached``).

    Nur im Kindprozess eines Falls. Die vier Läufe sind Zustände der
    Verkaufsfassung, also ohne Demo-Stichtag (``store.DEMO_UNTIL``). Den Testlauf
    lässt der Prüfstand, wie die Fassung ihn ausliefert (``store.TRIAL_FROM``),
    außer für ``sale_without_trial`` — dort gibt es keinen. ``expired`` gibt es
    nur mit ausgeliefertem ``TRIAL_FROM`` (Entscheidung Koordinator, 12.10.);
    verlangt eine Zeile ihn ohne, ist das ein Fehler und kein stiller Ersatz.
    ``over`` trägt seinen Stichtag. Danach gilt genau die Eigenschaft des
    Zustands und keine der anderen, sonst bricht der Fall hier ab.
    """
    from app.core import activation
    from app.core.activation import store

    day = today or date.today()
    cached = licence_activation(state, day)
    if state == STARTUP_LICENCE:
        store.DEMO_UNTIL = cached.deadline
    else:
        store.DEMO_UNTIL = None
        if state == "sale_without_trial":
            store.TRIAL_FROM = None
        elif state == "expired" and store.TRIAL_FROM is None:
            raise ValueError(
                "„expired“ gibt es nur, wenn die Fassung einen Testlauf anbietet"
                f" (store.TRIAL_FROM) — erreichbar sind {licence_runs()}"
            )
    others = [name for name in (*LICENCE_STATES, STARTUP_LICENCE) if name != state]
    if not getattr(cached, state) or any(getattr(cached, name) for name in others):
        raise RuntimeError(f"Der Zustand {state!r} ließ sich nicht eindeutig herstellen")
    activation._cached = cached
    return cached


def apply_preconditions(preconditions: Mapping[str, str]) -> dict[str, str]:
    """Setzt „fehlt“ über die Nahtstellen der Suite; „vorhanden“ ist die Maschine selbst.

    Gibt zurück, was wirklich gilt: ``vorhanden`` verlangt, aber auf dieser
    Maschine nicht da, steht als ``fehlt (Maschine)`` im Protokoll — ein Fall
    misst dann nicht, was er verspricht, und sagt es.
    """
    from app.core import discover
    from app.core.backends import llm

    applied: dict[str, str] = {}
    for name, state in preconditions.items():
        if name == "printer":
            applied[name] = state
            continue
        if state == "fehlt":
            if name == "slicer":

                def only_what_was_set(tool_id: str, names: object) -> object:
                    return discover._remembered_program(tool_id)

                def only_what_was_set_plural(tool_id: str, names: object) -> object:
                    single = only_what_was_set(tool_id, names)
                    return () if single is None else (single,)

                discover.find_program = only_what_was_set  # type: ignore[assignment]
                discover.find_programs = only_what_was_set_plural  # type: ignore[assignment]
                discover.forget_cache()
            elif name == "ki":
                llm.backends = tuple  # type: ignore[assignment]
            elif name == "comfyui":
                _comfyui_unreachable()
            applied[name] = "fehlt"
            continue
        applied[name] = state if _present(name) else "fehlt (Maschine)"
    return applied


def _comfyui_addresses() -> frozenset[str]:
    """Wo ComfyUI gesucht wird: die Vorgabe und die gemerkte Adresse, normalisiert."""
    from app.core import discover
    from app.core.backends import mesh

    return frozenset(
        mesh.comfy_base(address)
        for address in (mesh.DEFAULT_COMFY_URL, discover.service_url("comfyui", ""))
        if address
    )


def _comfyui_unreachable() -> None:
    """„ComfyUI fehlt“ an beiden Wegen, die danach fragen (Review L1).

    Die Erzeugung fragt ``mesh.reachable``, der Werkzeugdialog
    ``tools.Tool.running`` über ``discover.reachable`` — die Suite kennt dafür
    keine Nahtstelle. ``discover.reachable`` bleibt für jede andere Adresse,
    wie sie war; nur ComfyUIs Adressen antworten nicht.
    """
    from app.core import discover
    from app.core.backends import mesh

    addresses = _comfyui_addresses()
    asked = discover.reachable

    def only_other_services(url: str, *args: Any, **kwargs: Any) -> bool:
        if mesh.comfy_base(url) in addresses:
            return False
        return bool(asked(url, *args, **kwargs))

    mesh.reachable = lambda url, seconds=0.0: False  # type: ignore[assignment]
    discover.reachable = only_other_services  # type: ignore[assignment]


def _present(name: str) -> bool:
    """Ob eine Vorbedingung auf dieser Maschine wirklich erfüllt ist.

    ``available`` ist an jedem Sprachmodell eine Eigenschaft, kein Aufruf (Review M2).
    """
    from app.core import tools
    from app.core.backends import llm, mesh

    if name == "slicer":
        return bool(tools.slicer_programs())
    if name == "ki":
        return any(bool(backend.available) for backend in llm.backends())
    if name == "comfyui":
        return mesh.reachable(mesh.DEFAULT_COMFY_URL)
    return True


# --- Zahlen -------------------------------------------------------------------------


def typed_number(value_mm: float, unit: str = "mm") -> str:
    """Was der Kunde in ein Längenfeld tippt: Anzeigeeinheit, Dezimalzeichen der Sprache.

    Die Einheit rechnet ``units.from_mm``, die Stellen ``units.decimals_for`` und
    das Dezimalzeichen ``i18n.decimal_separator`` — dieselben Quellen wie Feld
    und Text der Anwendung. Nullen hinten fallen weg, wie man tippt: ``5`` statt
    ``5,00``.
    """
    from app.core.units import decimals_for, from_mm
    from app.i18n import decimal_separator

    shown = from_mm(value_mm, unit)  # type: ignore[arg-type]
    digits = decimals_for(unit)  # type: ignore[arg-type]
    text = f"{shown:.{digits}f}".rstrip("0").rstrip(".")
    if text in ("", "-0"):
        text = "0"
    return text.replace(".", decimal_separator())


# --- Szenenabdruck ----------------------------------------------------------------------


def _digest(data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scene_print(
    document: Any,
    scene: Any | None,
    *,
    selection: Sequence[str] = (),
    camera: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Der Abdruck einer Szene (Konzept §4 „Szenenabdruck“, Plan D0, Abschnitt 2.7).

    ``ops`` nennt die Operationen in ihrer Folge — U liest daran, ob der Verlauf
    gewachsen ist —, ``params`` je Schritt den Abdruck seiner Werte,
    ``project_params`` und ``fits`` die Projektparameter und Passungen über die
    Schreibweise der Projektdatei (``scene.serialise``), ``bodies`` je Körper
    sein Netz (``file_acceptance.body_digest``). Auswahl und Kamera stehen
    getrennt: Nach einem Rückgängig ist eine andere Auswahl ein Vermerk, kein
    Fehler (Prüfpunkt 5).
    """
    from app.core.scene.serialise import fit_to_data, operation_to_data, parameter_to_data
    from tools.file_acceptance import body_digest

    operations = [operation_to_data(entry) for entry in document.ops]
    parameters = {
        str(name): parameter_to_data(parameter) for name, parameter in document.parameters.items()
    }
    bodies = (
        {str(key): body_digest(entry.mesh) for key, entry in scene.objects.items()}
        if scene is not None
        else {}
    )
    position, focal, up, scale = (list(camera) + [None] * 4)[:4] if camera else (None,) * 4
    return {
        "ops": [entry.op for entry in document.ops],
        "params": [_digest(entry.get("params")) for entry in operations],
        "project_params": _digest(parameters),
        "fits": _digest([fit_to_data(fit) for fit in document.fits]),
        "bodies": bodies,
        "selection": list(selection),
        "camera": {
            "position": _rounded(position),
            "focal": _rounded(focal),
            "up": _rounded(up),
            "scale": None if scale is None else round(float(scale), 4),
        },
    }


def _rounded(vector: Any) -> list[float] | None:
    return None if vector is None else [round(float(value), 4) for value in vector]


#: Die Teile eines Abdrucks, die zum Dokument gehören; Auswahl und Kamera nicht.
DOCUMENT_PARTS: Final[tuple[str, ...]] = ("ops", "params", "project_params", "fits", "bodies")


def compare_prints(
    first: Mapping[str, Any] | None, second: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Was zwei Abdrücke sagen — ``None`` heißt: nicht vergleichbar, weil einer fehlt."""
    if first is None or second is None:
        return {"same": None, "differs": [], "selection_same": None, "camera_same": None}
    differs = [part for part in DOCUMENT_PARTS if first.get(part) != second.get(part)]
    return {
        "same": not differs,
        "differs": differs,
        "selection_same": first.get("selection") == second.get("selection"),
        "camera_same": first.get("camera") == second.get("camera"),
    }


# --- Messprotokoll -----------------------------------------------------------------------


def protocol_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Die Zeile, wie das Protokoll sie trägt: nur die Schlüssel des Schemas.

    Das sind die Felder von L's ``Row`` (``function_checks.ROW_KEYS``), samt dem
    Auswahlweg ``route``; geklickt steht er zusätzlich in ``steps``.
    """
    keys = PROTOCOL_SCHEMA["row"].keys or frozenset()
    data = {key: row[key] for key in sorted(keys) if key in row}
    if "spec" in data:
        data["spec"] = dict(data["spec"] or {})
    if "covers" in data:
        data["covers"] = list(data["covers"] or ())
    return data


def protocol_spec(spec: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Die Spezifikation im Protokoll: nur die Schlüssel des Schemas, ohne Lesevermerke.

    ``function_list`` hängt an jede gelesene Spezifikation, aus welcher Datei und
    welchem Paket sie stammt (``file``, ``package``); das Protokoll trägt das Paket
    oben und die Datei nicht.
    """
    if not spec:
        return None
    keys = PROTOCOL_SCHEMA["spec"].keys or frozenset(spec)
    return {key: spec[key] for key in spec if key in keys}


def empty_protocol(
    row: Mapping[str, Any], variant: Mapping[str, Any], version: Mapping[str, str]
) -> dict[str, Any]:
    """Das Gerüst eines Messprotokolls nach ``function_checks.PROTOCOL_SCHEMA``.

    Jedes Feld des Schemas steht da; ungemessen heißt ``None``, und
    ``unmeasured`` nennt den Grund — fehlende ``steps`` ergeben bei U „nicht
    gemessen“, nie „gut“. ``variant`` ist schon die Form des Protokolls
    (:meth:`Variant.protocol`).
    """
    data: dict[str, Any] = dict.fromkeys(PROTOCOL_SCHEMA)
    data.update(
        {
            "row": protocol_row(row),
            "kind": str(row.get("kind") or ""),
            "package": str(row.get("package") or ""),
            "spec": protocol_spec(row.get("spec")),
            "variant": dict(variant),
            "version": {
                "commit": str(version.get("commit", "")),
                "app": str(version.get("app", "")),
            },
            "steps": [],
            "states": {},
            "findings": [],
            "closed_by_escape": [],
            "unmeasured": {},
            "images": [],
            "errors": [],
        }
    )
    return data


def unmeasured(data: dict[str, Any], name: str, reason: str) -> None:
    """Vermerkt, warum ein Feld leer bleibt — der erste Grund gilt."""
    data["unmeasured"].setdefault(name, reason)


# --- Der Schrittautomat (B6) -----------------------------------------------------------------


class BenchFinding(Exception):  # noqa: N818 - ein Fund, kein Fehler des Prüfstands
    """Ein Fund unterwegs: Der Weg endet hier, und das Protokoll sagt warum."""

    def __init__(self, kind: str, target: str, detail: str) -> None:
        super().__init__(f"{kind}: {target} — {detail}")
        self.kind = kind
        self.target = target
        self.detail = detail


@dataclass(slots=True)
class Step:
    """Ein Schritt des Automaten: warten, bis ``ready`` gilt, dann ``act``.

    ``act`` darf blockieren — ein Klick, der einen Dialog über ``exec()`` öffnet,
    kehrt erst nach dessen Ende zurück. Der Automat hat den nächsten Schritt dann
    schon geplant (:meth:`StepMachine._tick`). ``settle_ms`` ist die Ruhe danach.
    """

    name: str
    act: Callable[[StepMachine], object]
    ready: Callable[[], bool] | None = None
    settle_ms: int = TICK_MS
    timeout_s: float = STEP_TIMEOUT_S


class StepMachine:
    """Ereignisgetriebener Ablauf über einen Zeitgeber, auch durch modale Schleifen (B6).

    ``schedule(ms, rückruf)`` ist am Fenster ``QTimer.singleShot``, im Test ein
    nachgestellter Zeitgeber. Je Takt prüft der Automat die Voraussetzung des
    nächsten Schritts; ist sie erfüllt, plant er den folgenden Takt **und dann**
    erst die Handlung. So läuft der nächste Schritt in der Schleife eines
    Dialogs, den diese Handlung geöffnet hat. Fertig ist der Automat, wenn kein
    Schritt mehr wartet und keine Handlung mehr läuft (:attr:`done`).
    """

    def __init__(
        self,
        schedule: Callable[[int, Callable[[], None]], None],
        clock: Callable[[], float],
        *,
        tick_ms: int = TICK_MS,
        unstick: Callable[[], None] | None = None,
    ) -> None:
        self._schedule = schedule
        self._clock = clock
        self._tick_ms = tick_ms
        self._unstick = unstick
        self.queue: list[Step] = []
        self.index = 0
        self.depth = 0
        self.stopped = False
        self.error: str | None = None
        self.finding: BenchFinding | None = None
        self.log: list[dict[str, Any]] = []
        self.unsticks = 0
        self.deadline: float | None = None
        self._waiting_since: float | None = None

    def start(self, steps: Iterable[Step], timeout_s: float | None = None) -> None:
        self.queue = list(steps)
        self.index = 0
        self._waiting_since = None
        self.deadline = None if timeout_s is None else self._clock() + timeout_s
        self._schedule(0, self._tick)

    def insert(self, steps: Iterable[Step]) -> None:
        """Schritte vor den nächsten wartenden — für einen Weg, der unterwegs wächst."""
        self.queue[self.index : self.index] = list(steps)

    @property
    def finished(self) -> bool:
        return self.stopped or self.index >= len(self.queue)

    @property
    def done(self) -> bool:
        """Kein Schritt wartet mehr, und keine Handlung steht noch auf dem Stapel."""
        return self.finished and self.depth == 0

    def stop(self, *, error: str | None = None, finding: BenchFinding | None = None) -> None:
        if not self.stopped:
            self.stopped = True
            self.error = error
            self.finding = finding

    def _tick(self) -> None:
        now = self._clock()
        if not self.finished and self.deadline is not None and now > self.deadline:
            self.log.append({"step": "phase", "event": "timeout", "t": now})
            self.stop(error="Zeitgrenze der Phase überschritten")
        if self.finished:
            # Steht noch eine Handlung in einer modalen Schleife, kehrt sie erst
            # zurück, wenn ihr Fenster schließt — am Fenster mit Escape.
            if self.depth > 0 and self._unstick is not None:
                self.unsticks += 1
                self.log.append({"step": "unstick", "event": "act", "t": now})
                self._unstick()
                self._schedule(max(SETTLE_MS, self._tick_ms), self._tick)
            return
        step = self.queue[self.index]
        if self._waiting_since is None:
            self._waiting_since = now
        if step.ready is not None:
            try:
                ready = step.ready()
            except Exception:
                self.log.append({"step": step.name, "event": "ready-error", "t": now})
                self.stop(error=f"{step.name}: {traceback.format_exc()}")
                return
            if not ready:
                if now - self._waiting_since > step.timeout_s:
                    self.log.append({"step": step.name, "event": "timeout", "t": now})
                    self.stop(
                        error=f"{step.name}: Zeitgrenze von {step.timeout_s:.0f} s überschritten"
                    )
                    return
                self._schedule(self._tick_ms, self._tick)
                return
        self.index += 1
        self._waiting_since = None
        self.log.append({"step": step.name, "event": "act", "t": now})
        # Erst planen, dann handeln: Blockiert die Handlung in einer modalen
        # Schleife, läuft der nächste Takt darin.
        self._schedule(max(step.settle_ms, self._tick_ms), self._tick)
        self.depth += 1
        try:
            step.act(self)
        except BenchFinding as finding:
            self.log.append({"step": step.name, "event": "finding", "t": self._clock()})
            self.stop(finding=finding)
        except Exception:
            self.log.append({"step": step.name, "event": "error", "t": self._clock()})
            self.stop(error=f"{step.name}: {traceback.format_exc()}")
        finally:
            self.depth -= 1
            self.log.append({"step": step.name, "event": "returned", "t": self._clock()})


def drive(
    machine: StepMachine,
    steps: Iterable[Step],
    pump: Callable[[], None],
    clock: Callable[[], float],
    timeout_s: float = PHASE_TIMEOUT_S,
) -> None:
    """Fährt den Automaten, bis er fertig ist; ``pump`` lässt die Ereignisse laufen.

    Am Fenster ist ``pump`` ``processEvents`` mit kurzem Schlaf — nie
    ``QTest.qWait``, das den GIL hält (``tests.md``, „Beim Schreiben“). Die
    Zeitgrenze prüft der Automat selbst in jedem Takt, auch in einer modalen
    Schleife, in der diese Schleife hier gerade nicht läuft; danach räumt er
    über ``unstick`` ab, bis keine Handlung mehr auf dem Stapel steht.
    """
    machine.start(steps, timeout_s)
    while not machine.done:
        pump()
        if machine.deadline is not None and clock() > machine.deadline + timeout_s:
            # Der Automat hat seine Frist und eine zweite dazu verpasst — dann
            # tickt er nicht mehr, und diese Schleife ist die letzte Wache.
            machine.stop(error=f"Phase nach {2 * timeout_s:.0f} s nicht fertig")
            return


# --- Der Weg zum Ziel --------------------------------------------------------------------------


class ClickLike(Protocol):
    """Was ``guide_targets.next_click`` zurückgibt (``guide_targets.Click``).

    ``target`` ist der Wortschatzname, ``direction`` die Richtung beim Rollen
    (1 nach unten, -1 nach oben).
    """

    rect: Any
    button: Any
    why: str
    target: Any
    direction: int


class Ports(Protocol):
    """Die Verbindung zur Oberfläche; am Fenster :class:`QtPorts`, im Test nachgestellt."""

    def next_click(self, name: str) -> ClickLike: ...
    def widget_under(self, point: Any) -> Any: ...
    def covers(self, click: ClickLike, hit: Any) -> bool: ...
    def centre(self, rect: Any) -> Any: ...
    def press(self, widget: Any, point: Any, button: str) -> None: ...
    def keys(self, sequence: Any) -> None: ...
    def type_text(self, text: str) -> None: ...
    def describe(self, widget: Any, point: Any = None) -> dict[str, Any]: ...
    def zone_of(self, widget: Any) -> str | None: ...
    def rect_data(self, rect: Any) -> list[int]: ...
    def point_data(self, point: Any) -> list[int]: ...
    def now(self) -> float: ...


def button_name(button: Any) -> str:
    """Die Taste eines Klicks als Wort: ``left``, ``right``, ``double``, ``wheel_up`` …"""
    if isinstance(button, str):
        return button or "left"
    text = str(getattr(button, "name", button)).lower()
    if "right" in text:
        return "right"
    if "middle" in text:
        return "middle"
    return "left"


def with_modifier(button: str, modifier: str) -> str:
    """Taste und Zusatztaste als ein Wort, wie :meth:`QtPorts.press` es liest: ``ctrl+left``."""
    return f"{modifier}+{button}" if modifier else button


class Walk:
    """Der Weg des Kunden zu einem Ziel: Wegklicks, dann das Ziel — jeder mit Probe.

    Jeder Klick holt ``next_click`` neu, denn erst der vorige deckt den nächsten
    auf. An der Mitte des genannten Rechtecks fragt ``widget_under``, was dort
    liegt; nur wenn es das Ziel des Klicks oder eines seiner Kinder ist, geht der
    Klick dorthin. Jeder Klick steht mit Grund, Ort, Treffer und Zone in
    ``steps`` (Protokollfeld, Prüfpunkt 2, E1, E4).
    """

    def __init__(self, ports: Ports, steps: list[dict[str, Any]], began: float) -> None:
        self.ports = ports
        self.steps = steps
        self.began = began
        #: Die Phase der nächsten Einträge. Der Hauptweg heißt ``weg`` und
        #: ``übernehmen`` (``function_checks.MAIN_PHASES``); nur er zählt für E1 bis E4.
        self.phase = ""

    def record(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Ein Eintrag in ``steps``, mit Phase und Zeit seit dem Start des Falls."""
        entry = {**entry, "phase": self.phase, "t": self._t()}
        self.steps.append(entry)
        return entry

    def step(self, name: str, button: str = "left") -> Step:
        """Ein Schritt, der bis zum Ziel wächst: jeder Wegklick reiht den nächsten ein.

        Geklickt wird erst, wenn der nächste Klick :data:`STABLE_S` lang derselbe
        ist und an seiner Stelle das Ziel liegt (:meth:`stable`): Nach einem
        Aufklappen setzt die Karte ihre Höhen erst in den folgenden
        Ereignisrunden (``fenster.md``, „Wie die Karten ihre Höhe teilen“);
        vorher lag an der genannten Stelle noch die Karte oder die nächste
        Klappe, und die Probe meldete „verdeckt“, wo nur gewartet werden musste.
        Was :data:`COVERED_S` lang deckt, bleibt der Fund.
        """
        counter = {"way": 0}

        def act(machine: StepMachine) -> None:
            why = self.click_once(name, button)
            if why == TARGET_REASON:
                return
            counter["way"] += 1
            if counter["way"] > MOST_WAY_CLICKS:
                raise BenchFinding(
                    NOT_FOUND, name, f"nach {MOST_WAY_CLICKS} Wegklicks noch nicht am Ziel"
                )
            machine.insert(
                [Step(f"weg zu {name}", act, ready=self.stable(name), settle_ms=SETTLE_MS)]
            )

        return Step(f"weg zu {name}", act, ready=self.stable(name), settle_ms=SETTLE_MS)

    def stable(self, name: str) -> Callable[[], bool]:
        """Ob der nächste Klick zu ``name`` fallen kann.

        Er muss seit :data:`STABLE_S` derselbe sein, und an seiner Mitte liegt
        das Ziel — oder seit :data:`COVERED_S` etwas anderes; dann meldet der
        Klick „verdeckt“. Ohne Weg ist er sofort bereit — der Klick meldet dann
        „nicht auffindbar“.
        """
        seen: dict[str, Any] = {"key": None, "since": 0.0, "covered": None}

        def ready() -> bool:
            try:
                click = self.ports.next_click(name)
            except LookupError:
                return True
            key = (str(click.why), tuple(self.ports.rect_data(click.rect)))
            now = self.ports.now()
            if key != seen["key"]:
                seen["key"], seen["since"], seen["covered"] = key, now, None
                return False
            if now - seen["since"] < STABLE_S:
                return False
            hit = self.ports.widget_under(self.ports.centre(click.rect))
            if hit is not None and self.ports.covers(click, hit):
                seen["covered"] = None
                return True
            if seen["covered"] is None:
                seen["covered"] = now
            return bool(now - seen["covered"] >= COVERED_S)

        return ready

    def click_once(self, name: str, button: str = "left") -> str:
        """Ein Klick auf dem Weg zu ``name``; gibt seinen Grund zurück."""
        try:
            click = self.ports.next_click(name)
        except LookupError as error:
            self.record({"target": name, "finding": NOT_FOUND, "detail": str(error)})
            raise BenchFinding(NOT_FOUND, name, str(error)) from error
        point = self.ports.centre(click.rect)
        hit = self.ports.widget_under(point)
        why = str(click.why)
        if why == "rollen":
            pressed = "wheel_up" if int(getattr(click, "direction", 1) or 1) < 0 else "wheel_down"
        elif why == TARGET_REASON:
            pressed = button
        else:
            pressed = button_name(click.button)
        record = self.record(
            {
                "target": name,
                "why": why,
                "button": pressed,
                "rect": self.ports.rect_data(click.rect),
                "point": self.ports.point_data(point),
                "widget_at": self.ports.describe(hit, point) if hit is not None else None,
                "hit": hit is not None and self.ports.covers(click, hit),
                "zone": self.ports.zone_of(hit) if hit is not None else None,
                "decision": False,
            }
        )
        if not record["hit"]:
            record["finding"] = COVERED
            raise BenchFinding(
                COVERED,
                name,
                f"an {record['point']} liegt {record['widget_at']}, nicht das Ziel des Klicks",
            )
        self.ports.press(hit, point, record["button"])
        return why

    def _t(self) -> float:
        return round(self.ports.now() - self.began, 4)


def click_button(ports: Any, walker: Walk, button: Any, label: str) -> bool:
    """Ein Knopf ohne Wortschatznamen — Rückfrage, Starttor —, angeklickt mit Probe.

    W führt für diese Knöpfe keinen Namen (Bericht: Lücke für W). Geklickt wird
    trotzdem nur, wenn ``widget_under`` an der Mitte den Knopf trifft; der
    Klick steht wie jeder andere in ``steps``, mit ``label`` als Ziel. ``False``
    heißt: verdeckt, nicht geklickt — der Eintrag trägt den Fund.
    """
    from PySide6.QtCore import QPoint, QRect

    rect = QRect(button.mapToGlobal(QPoint(0, 0)), button.size())
    point = rect.center()
    hit = ports.widget_under(point)
    record = walker.record(
        {
            "target": label,
            "why": TARGET_REASON,
            "button": "left",
            "rect": ports.rect_data(rect),
            "point": ports.point_data(point),
            "widget_at": ports.describe(hit, point) if hit is not None else None,
            "hit": hit is not None and (hit is button or button.isAncestorOf(hit)),
            "zone": None,
            "decision": False,
        }
    )
    if not record["hit"]:
        record["finding"] = COVERED
        record["detail"] = f"an {record['point']} liegt {record['widget_at']}, nicht {label}"
        return False
    ports.press(hit, point, "left")
    return True


def way_clicks(steps: Sequence[Mapping[str, Any]]) -> int:
    """Wie viele Wegklicks ein Weg gekostet hat (``why`` nicht ``ziel``)."""
    return sum(1 for step in steps if step.get("why") in WAY_REASONS)


def place_of(steps: Sequence[Mapping[str, Any]], target: str) -> dict[str, Any]:
    """Wo das Ziel einer Zeile steht, aus ihrem Hauptweg (Prüfpunkt 1, 17; Schema ``place``).

    ``where`` ist einer aus ``function_checks.PLACES``: ``kontext`` bei einem
    Rechtsklick auf dem Weg, ``menue`` bei einem Menü, ``werkzeugleiste`` am
    Kopf des Fensters, sonst ``karte``. ``path`` sind die sichtbaren Texte der
    Klicks bis zum Ziel. Kam der Weg nicht an, steht der Grund in ``error``.
    """
    walked = [step for step in steps if step.get("phase") == PATH_PHASE]
    upto: list[Mapping[str, Any]] = []
    for step in walked:
        upto.append(step)
        if step.get("target") == target and (
            step.get("why") == TARGET_REASON or step.get("finding")
        ):
            break
    final = upto[-1] if upto else None
    if final is None or final.get("target") != target:
        return {"where": None, "path": [], "error": "der Hauptweg erreichte das Ziel nicht"}
    if final.get("finding") or not final.get("hit"):
        return {
            "where": None,
            "path": [],
            "error": str(final.get("detail") or final.get("finding")),
        }
    clicks = [step for step in upto if step.get("why")]
    reasons = {str(step.get("why")) for step in clicks}
    zones = [str(step.get("zone") or "") for step in clicks if step.get("target") == target]
    if any(str(step.get("button", "")).endswith("right") for step in clicks):
        where = "kontext"
    elif reasons & {"menue", "untermenue"} or "menue" in zones:
        where = "menue"
    elif zones and zones[0] == "kopf":
        where = "werkzeugleiste"
    else:
        where = "karte"
    assert where in PLACES
    path = [
        str((step.get("widget_at") or {}).get("text") or step.get("target"))
        for step in clicks
        if step.get("target") == target
    ]
    return {"where": where, "path": path, "error": None}


def search_rank(hits: Sequence[str], target: str) -> int | None:
    """Der Rang des Ziels unter den sichtbaren Treffern, ab 1; ``None``, wenn es fehlt."""
    for rank, hit in enumerate(hits, 1):
        if hit == target:
            return rank
    return None


# --- Am Fenster ------------------------------------------------------------------------------


class QtPorts:
    """Die Ports am echten Fenster: ``guide_targets`` und ``QTest``-Ereignisse.

    Ereignisse gehen an das Widget, das an der Stelle liegt — wie die Maus des
    Kunden. Tasten gehen an das Widget mit dem Fokus, wie die Tastatur.
    """

    def __init__(self, window: Any, began: float) -> None:
        self.window = window
        self.began = began

    def next_click(self, name: str) -> ClickLike:
        from app.ui import guide_targets

        return guide_targets.next_click(self.window, name)  # type: ignore[attr-defined,no-any-return]

    def widget_under(self, point: Any) -> Any:
        from app.ui import guide_targets

        return guide_targets.widget_under(point)  # type: ignore[attr-defined]

    def covers(self, click: ClickLike, hit: Any) -> bool:
        """Ob der Treffer der Probe das ist, was der Klick meint — das Ziel oder ein Kind davon.

        ``Click`` nennt eine Fläche, kein Widget. Gemeint ist das Widget, dessen
        Rechteck genau diese Fläche ist (Knopf, Klappe, Feld, Reiter als Knopf),
        oder der Behälter, in dem die Fläche als Zeile liegt: Liste und Baum,
        Menü und Menüleiste, Reiterleiste, die Ansicht, beim Rollen die
        Rollfläche. Ein Treffer gilt, wenn er selbst oder ein Vorfahr innerhalb
        seines Fensters das ist; eine Einladung, eine Karte oder ein Dialog
        darüber ist es nicht — der Fund „verdeckt“.
        """
        from PySide6.QtCore import QPoint, QRect
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QAbstractScrollArea,
            QMenu,
            QMenuBar,
            QTabBar,
        )

        holders: tuple[type, ...] = (QAbstractItemView, QMenu, QMenuBar, QTabBar)
        if str(click.why) == "rollen":
            holders = (*holders, QAbstractScrollArea)
        rect = click.rect
        probe = hit
        while probe is not None:
            area = QRect(probe.mapToGlobal(QPoint(0, 0)), probe.size())
            if area == rect:
                return True
            holder = isinstance(probe, holders) or probe is self.window.viewport
            if holder and area.contains(rect.center()):
                return True
            if probe.isWindow():
                return False
            probe = probe.parentWidget()
        return False

    def centre(self, rect: Any) -> Any:
        return rect.center()

    def press(self, widget: Any, point: Any, button: str) -> None:
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QWheelEvent
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        local = widget.mapFromGlobal(point)
        modifiers = Qt.KeyboardModifier.NoModifier
        held, plus, rest = button.rpartition("+")
        if plus:
            button = rest
            for name in held.split("+"):
                modifiers |= {
                    "ctrl": Qt.KeyboardModifier.ControlModifier,
                    "shift": Qt.KeyboardModifier.ShiftModifier,
                    "alt": Qt.KeyboardModifier.AltModifier,
                }[name]
        QTest.mouseMove(widget, local)
        if button in ("wheel_up", "wheel_down"):
            step = 120 if button == "wheel_up" else -120
            event = QWheelEvent(
                QPointF(local),
                QPointF(point),
                QPoint(0, 0),
                QPoint(0, step),
                Qt.MouseButton.NoButton,
                modifiers,
                Qt.ScrollPhase.NoScrollPhase,
                False,
            )
            QApplication.sendEvent(widget, event)
            return
        if button == "double":
            QTest.mouseDClick(widget, Qt.MouseButton.LeftButton, modifiers, local)
            return
        mouse = {
            "left": Qt.MouseButton.LeftButton,
            "right": Qt.MouseButton.RightButton,
            "middle": Qt.MouseButton.MiddleButton,
        }[button]
        QTest.mouseClick(widget, mouse, modifiers, local)

    def move(self, point: Any) -> None:
        """Die Maus an eine Stelle, ohne zu klicken — Überfahren für I1."""
        from PySide6.QtTest import QTest

        hit = self.widget_under(point)
        if hit is not None:
            QTest.mouseMove(hit, hit.mapFromGlobal(point))

    def keys(self, sequence: Any) -> None:
        """Eine Tastenfolge an das Fokuswidget, sonst an das Fenster."""
        from PySide6.QtGui import QKeySequence
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        keys = sequence if isinstance(sequence, QKeySequence) else QKeySequence(sequence)
        for index in range(keys.count()):
            combination = keys[index]
            target = QApplication.focusWidget() or QApplication.activeModalWidget() or self.window
            QTest.keyClick(target, combination.key(), combination.keyboardModifiers())

    def type_text(self, text: str) -> None:
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        target = QApplication.focusWidget() or self.window
        QTest.keyClicks(target, text)

    def describe(self, widget: Any, point: Any = None) -> dict[str, Any]:
        """Klasse, Name, Kennzeichen und der sichtbare Text an der Stelle des Klicks.

        Am Text hängt ``place.path``: Ein Menü nennt die Zeile unter dem Zeiger,
        eine Reiterleiste den Reiter, eine Liste den Eintrag, ein Knopf sich selbst.
        """
        from PySide6.QtWidgets import QAbstractItemView, QMenu, QMenuBar, QTabBar

        from app.core.guides import TARGET_PROPERTY

        if widget is None:
            return {}
        text = ""
        local = widget.mapFromGlobal(point) if point is not None else None
        if isinstance(widget, (QMenu, QMenuBar)) and local is not None:
            action = widget.actionAt(local)
            text = action.text() if action is not None else ""
        elif isinstance(widget, QTabBar) and local is not None:
            index = widget.tabAt(local)
            text = widget.tabText(index) if index >= 0 else ""
        elif isinstance(widget.parentWidget(), QAbstractItemView) and local is not None:
            view = widget.parentWidget()
            index = view.indexAt(local)
            text = str(index.data() or "") if index.isValid() else ""
        elif callable(getattr(widget, "text", None)):
            text = str(widget.text() or "")
        mark = widget.property(TARGET_PROPERTY)
        return {
            "class": type(widget).__name__,
            "object_name": widget.objectName(),
            "mark": str(mark) if mark else "",
            "text": text.replace("&", ""),
        }

    def zone_of(self, widget: Any) -> str | None:
        from app.ui import guide_targets

        if widget is None:
            return None
        zone = guide_targets.zone_of(self.window, widget)  # type: ignore[attr-defined]
        return str(zone) if zone else None

    def rect_data(self, rect: Any) -> list[int]:
        return [rect.x(), rect.y(), rect.width(), rect.height()]

    def point_data(self, point: Any) -> list[int]:
        return [point.x(), point.y()]

    def now(self) -> float:
        return time.perf_counter()


def qt_schedule(milliseconds: int, callback: Callable[[], None]) -> None:
    """Der Zeitgeber des Automaten am Fenster; er feuert auch in ``exec()``-Schleifen."""
    from PySide6.QtCore import QTimer

    QTimer.singleShot(milliseconds, callback)


def place_window(application: Any, window: Any, variant: Variant) -> dict[str, Any]:
    """Legt das Fenster auf den gewählten Schirm, **bevor** es erscheint.

    ``--screen`` nennt einen Schirm über seine Nummer oder seinen Namen; ohne
    Angabe der erste, der nicht der Hauptschirm ist — dort arbeitet Robert nicht
    (Erinnerung „qt-sonde-am-echten-fenster“). Ohne Fenstergröße maximiert, wie
    die Aufnahmewerkzeuge; mit Größe (Z6) genau diese, oben links auf dem Schirm.
    Später verschieben wechselte Größe und DPI mitten im Lauf.
    """
    screens = list(application.screens())
    primary = application.primaryScreen()
    chosen = None
    wanted = variant.screen.strip()
    if wanted.isdigit() and int(wanted) < len(screens):
        chosen = screens[int(wanted)]
    elif wanted:
        chosen = next(
            (
                screen
                for screen in screens
                if wanted.lower()
                in f"{screen.name()} {screen.model()} {screen.manufacturer()}".lower()
            ),
            None,
        )
    if chosen is None:
        chosen = next((screen for screen in screens if screen != primary), primary)
    area = chosen.availableGeometry()
    size = parse_size(variant.window_size) if variant.window_size else None
    if size is None:
        window.setGeometry(area)
        window.showMaximized()
    else:
        window.resize(*size)
        window.move(area.topLeft())
        window.show()
    return {
        "screen": chosen.name(),
        "model": chosen.model(),
        "ratio": float(chosen.devicePixelRatio()),
        "geometry": [area.x(), area.y(), area.width(), area.height()],
        "requested": wanted,
    }


# --- Der Funktionsfall am Fenster ------------------------------------------------------------

#: Die Szene, die jede Zeile ohne eigene Szene bekommt (Plan D0, Abschnitt 2.5).
EMPTY_SCENE: Final = "leer"

#: Die Szene ohne Projekt: Der Fall bleibt auf dem Startbildschirm (``start.*``).
START_SCREEN: Final = "startbildschirm"

#: Die Szene, in die der Projektwechsel geht (Prüfpunkt 16).
SECOND_SCENE: Final = "zweites_projekt"

#: Die Szenen, deren Rechnung lang genug für *Abbrechen* ist (Prüfpunkt 14).
SLOW_SCENES: Final[tuple[str, ...]] = ("langsam_2s", "langsam_10s")

#: Wie lange nach einem Abbruch oder Projektwechsel auf späte Ereignisse gewartet wird.
LATE_WINDOW_S: Final = 3.0

#: Wie lange nach einem Klick auf eine Handlung auf ihre Wirkung gewartet wird.
EFFECT_WINDOW_S: Final = 2.0

#: Z1: Bewegungen eines Zugs und ihr Takt — 60 je Sekunde wie eine Hand an der
#: Maus (Review L11), nicht so schnell, wie die Schleife sie senden kann.
DRAG_MOVES: Final = 20
DRAG_TICK_S: Final = 1 / 60

#: Die Meldungen der Ansicht während eines Zugs am Griff: Geist, Zahl am Zeiger,
#: verschobener Körper. Kommt keine, hat der Zug den Griff nicht gefasst.
DRAG_SIGNALS: Final[tuple[str, ...]] = (
    "transformDragged",
    "placementDragged",
    "previewDragged",
    "gizmoStatus",
    "featureMoved",
    "featureMoveProposed",
    "faceDragged",
    "scaleDragged",
    "slotDragged",
)

#: Die Einträge unter „Zuletzt geöffnet“ auf dem Startbildschirm (Prüfpunkt 16):
#: ``start.recent:<n>``, n ab 1 in der Folge der Liste. Ein Menü dafür gibt es
#: nicht; zum Startbildschirm führt *Datei → Neu* (``MainWindow.new_action``).
RECENT_KIND: Final = "start.recent"

#: Ein Szenenschlüssel, wie er im Dateinamen steht.
_STEP_NUMBER: Final = re.compile(r"\b(\d+)\b")


def case_scene(folder: Path, scenes: Path, key: str) -> Path | None:
    """Die eigene Kopie einer Startszene im Fallordner, beim ersten Mal angelegt.

    Geöffnet wird nie die gemeinsame Datei unter ``<out>/scenes``: Die Anwendung
    legt ihre Sicherung neben das Projekt (``<szene>.p3d.autosave``), und stirbt
    ein Fall danach, hinge jeder folgende Fall derselben Szene an der
    Wiederherstellungsfrage (Review M6, Erinnerung „sonden-bauen“). ``None``,
    wenn es die Szene nicht gibt.
    """
    import shutil

    source = scenes / f"{key}.p3d"
    if not source.is_file():
        return None
    copy = folder / "scenes" / source.name
    if not copy.is_file():
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, copy)
    return copy


def walk_target(row: Mapping[str, Any]) -> str:
    """Wohin der Hauptweg einer Zeile führt.

    Meist ihr Ziel. Eine Operation, deren Eingaben in einer Handlung des
    Merkmalfensters stehen (``feature.field:<op>.…``), findet der Kunde an der
    Auswahl als diese Handlung (``feature:<op>``) — ihr Eintrag liegt sonst nur
    im Kontextmenü, und ``next_click`` verlangte den Rechtsklick. Die Suche
    misst weiter das Ziel der Zeile (``operation:<op>``), denn so heißt der
    Treffer.
    """
    target = str(row.get("target") or "")
    kind, _separator, name = target.partition(":")
    if kind == "operation":
        inputs = (row.get("spec") or {}).get("inputs") or {}
        if any(str(key).startswith(f"feature.field:{name}.") for key in inputs):
            return f"feature:{name}"
    return target


def default_apply_target(row: Mapping[str, Any]) -> str | None:
    """Womit eine Zeile übernommen wird.

    Handlungen des Merkmalfensters und Kantenzeilen mit *Übernehmen* dort,
    Operationen mit dem Hauptknopf ihres Dialogs; ein Fensterbefehl und eine
    Bedienfläche wirken mit ihrem Klick selbst.
    """
    target = walk_target(row)
    if target.startswith(("feature:", "edge:")):
        return "feature.apply"
    if target.startswith(("operation:", "dialog:")):
        return "dialog.accept"
    return None


def route_of(row: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Der Hauptweg einer Zeile: Auswahl (L), Schritte der Spezifikation, dann das Ziel.

    ``row.route`` stellt die Auswahl der Anforderung her (``function_list``:
    Baumzeile, mit Strg weitere), ``spec.route`` nennt, was ``next_click``
    allein nicht findet (Rechtsklick, Kontextmenü). Jeder Schritt ist
    ``{target, button, modifier}``.
    """
    steps = [*(row.get("route") or ()), *((row.get("spec") or {}).get("route") or ())]
    route = [
        (
            str(entry["target"]),
            with_modifier(str(entry.get("button") or "left"), str(entry.get("modifier") or "")),
        )
        for entry in steps
    ]
    target = walk_target(row)
    if target and (not route or route[-1][0] != target):
        route.append((target, "left"))
    return route


def selected_feature(row: Mapping[str, Any]) -> tuple[str, str] | None:
    """Das Merkmal, das der Auswahlweg wählt (``tree.row:obj_1.hole_1``), oder keins."""
    for entry in reversed(list(row.get("route") or ())):
        target = str(entry.get("target") or "")
        if target.startswith("tree.row:"):
            body, _dot, feature = target.removeprefix("tree.row:").partition(".")
            return (body, feature) if feature else None
    return None


def result_metrics(scene: Any, document: Any, selected: tuple[str, str] | None) -> dict[str, Any]:
    """Kennzahlen des Ergebnisses, benannt wie die Erwartungen der Spezifikation.

    ``volume`` und ``extent`` über alle Körper, ``bounds.<achse>_<min|max>``,
    ``<art>.<wert>`` am gewählten Merkmal (``hole.diameter``; ohne Auswahl das
    erste seiner Art) und ``parameter.<name>`` aus den Projektparametern — die
    Namen, die ``tests/data/function_rows`` verwendet (Bericht D0-L).
    """
    from app.core.errors import AppError
    from app.core.geom.mesh import as_mesh_data

    metrics: dict[str, Any] = {}
    volume = 0.0
    lows: list[Any] = []
    highs: list[Any] = []
    for entry in scene.objects.values():
        try:
            raw = as_mesh_data(entry.mesh).raw
        except AppError:
            continue
        volume += float(raw.volume)
        low, high = raw.bounds
        lows.append(low)
        highs.append(high)
    if lows:
        low = [min(float(point[axis]) for point in lows) for axis in range(3)]
        high = [max(float(point[axis]) for point in highs) for axis in range(3)]
        metrics["volume"] = round(volume, 4)
        metrics["extent"] = [round(b - a, 4) for a, b in zip(low, high, strict=True)]
        for axis, name in enumerate("xyz"):
            metrics[f"bounds.{name}_min"] = round(low[axis], 4)
            metrics[f"bounds.{name}_max"] = round(high[axis], 4)
    seen: set[str] = set()
    ordered = []
    if selected is not None and selected[0] in scene.objects:
        chosen = scene.objects[selected[0]].features.get(selected[1])
        if chosen is not None:
            ordered.append(chosen)
    ordered += [feature for entry in scene.objects.values() for feature in entry.features.values()]
    for feature in ordered:
        if feature.kind in seen:
            continue
        seen.add(feature.kind)
        for key, value in feature.params.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                metrics[f"{feature.kind}.{key}"] = round(float(value), 4)
    for name, parameter in document.parameters.items():
        value = getattr(parameter, "value", None)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[f"parameter.{name}"] = round(float(value), 4)
    return metrics


def cli_arguments(operation: Mapping[str, Any]) -> list[str] | None:
    """Die Werte eines Schritts (``serialise.operation_to_data``) für ``app.cli.main run``.

    Nur Zahlen, Texte und Wahrheitswerte haben dort ein Feld; ein Schritt mit
    anderen Werten (Listen, Bezüge) ist über die Kommandozeile nicht derselbe —
    dann ``None``, und Prüfpunkt 4 vermerkt den Vergleich als nicht gemessen.
    """
    arguments = [str(operation["op"])]
    inputs = [str(name) for name in operation.get("in", ())]
    if inputs:
        arguments += ["--on", *inputs]
    for name, value in (operation.get("params") or {}).items():
        flag = "--" + str(name).replace("_", "-")
        if isinstance(value, bool):
            arguments.append(flag if value else "--no-" + str(name).replace("_", "-"))
        elif isinstance(value, (int, float, str)):
            arguments += [flag, str(value)]
        else:
            return None
    return arguments


def bodies_digest(bodies: Mapping[str, str]) -> str:
    """Ein Abdruck über die Abdrücke aller Körper — ``result.digest``, ``cli.digest``."""
    return _digest(dict(sorted(bodies.items())))


def step_number(text: str) -> int | None:
    """Die erste Zahl in einem Haltgrund — die Schrittnummer (Prüfpunkt 15)."""
    found = _STEP_NUMBER.search(text)
    return int(found.group(1)) if found else None


class FunctionFlow:
    """Ein Funktionsfall am echten Fenster: Phasen nach der Variante, jede mit Abdruck.

    Jede Phase beginnt an der Startszene (:meth:`reset`) und endet ohne offenes
    Fenster; scheitert eine, steht ihr Grund in ``errors`` oder ``findings``,
    und die nächste läuft trotzdem. Gemessen wird ins Protokoll ``data``,
    geschrieben nach jeder Phase (``persist``) — ein Absturz lässt stehen, was
    schon gemessen war. ``bench`` hält, was nur den Lauf betrifft (Phase,
    Ausnahme), getrennt vom Protokoll.
    """

    def __init__(
        self,
        application: Any,
        window: Any,
        folder: Path,
        data: dict[str, Any],
        persist: Callable[[], None],
        row: Mapping[str, Any],
        variant: Variant,
        scenes: Path,
        bench: dict[str, Any] | None = None,
        out: Path | None = None,
    ) -> None:
        from tools.function_capture import FrameCounter, Heartbeat, ModalWatch

        self.application = application
        self.window = window
        self.session = window.session
        self.folder = folder
        self.out = out or folder.parent.parent
        self.data = data
        self.persist = persist
        self.bench = bench if bench is not None else {}
        self.row = dict(row)
        self.spec: dict[str, Any] = dict(row.get("spec") or {})
        self.variant = variant
        self.scenes = scenes
        self.began = time.perf_counter()
        self.ports = QtPorts(window, self.began)
        self.walker = Walk(self.ports, data["steps"], self.began)
        self.heartbeat = Heartbeat()
        self.frames = FrameCounter()
        self.frames_wrapped = False
        self.watch = ModalWatch(self.began)
        self._timers: list[Any] = []
        self.scene_key = str(self.spec.get("start_scene") or row.get("start_scene") or EMPTY_SCENE)
        self.apply_target = default_apply_target(self.row)
        self.selected = selected_feature(self.row)
        #: Ein Referenzfaktor je Lauf (Bauplan §31, Entscheidung Koordinator 12.10.):
        #: aus dem Lauf (``reference.json``), sonst hier gemessen.
        self.reference_factor = float(
            self.bench.get("reference_factor") or run_reference_factor(self.out)
        )

    # --- Grundgerüst -----------------------------------------------------------------

    def pump(self) -> None:
        self.application.processEvents()
        time.sleep(0.005)

    def run_steps(
        self, label: str, steps: Sequence[Step], timeout_s: float = PHASE_TIMEOUT_S
    ) -> bool:
        """Fährt Schritte; ein Fund oder Fehler steht danach im Protokoll.

        ``label`` ist die Phase jedes Eintrags in ``steps``, den diese Schritte
        schreiben (``Walk.phase``).
        """
        self.walker.phase = label
        machine = StepMachine(qt_schedule, time.perf_counter, unstick=self.escape_modal)
        drive(machine, steps, self.pump, time.perf_counter, timeout_s)
        ok = True
        if machine.finding is not None:
            self.data["findings"].append(
                {
                    "phase": label,
                    "kind": machine.finding.kind,
                    "target": machine.finding.target,
                    "detail": machine.finding.detail,
                }
            )
            ok = False
        if machine.error is not None:
            self.data["errors"].append(f"{label}: {machine.error}")
            ok = False
        if machine.unsticks:
            self.data["closed_by_escape"].append({"phase": label, "times": machine.unsticks})
        self.persist()
        return ok

    def escape_modal(self) -> None:
        """Escape an das modale Fenster oder das offene Menü — wie der Kunde, der abbricht."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        widget = QApplication.activePopupWidget() or QApplication.activeModalWidget()
        if widget is not None:
            QTest.keyClick(widget, Qt.Key.Key_Escape)

    def idle(self) -> bool:
        return self.session.last_result is not None and not self.session.busy

    def wait_step(
        self, name: str, ready: Callable[[], bool], timeout_s: float = STEP_TIMEOUT_S
    ) -> Step:
        return Step(name, lambda machine: None, ready=ready, timeout_s=timeout_s)

    def do_step(self, name: str, action: Callable[[], object], settle_ms: int = TICK_MS) -> Step:
        return Step(name, lambda machine: action(), settle_ms=settle_ms)

    def key_step(self, sequence: Any, name: str) -> Step:
        def act(machine: StepMachine) -> None:
            text = sequence.toString() if hasattr(sequence, "toString") else str(sequence)
            self.walker.record({"target": name, "key": text, "button": None})
            self.ports.keys(sequence)

        return Step(f"taste {name}", act, settle_ms=SETTLE_MS)

    def undo_keys(self) -> Any:
        from PySide6.QtGui import QKeySequence

        return QKeySequence(QKeySequence.StandardKey.Undo)

    def redo_keys(self) -> Any:
        """Die Wiederholen-Taste aus ``shortcut_schemes.redo_keys`` — die, die im Menü steht."""
        from PySide6.QtGui import QKeySequence

        from app.ui.shortcut_schemes import redo_keys

        return redo_keys(sys.platform, QKeySequence(QKeySequence.StandardKey.Redo))[0]

    def scene_now(self) -> dict[str, Any]:
        """Der Abdruck jetzt (:func:`scene_print`)."""
        result = self.session.last_result
        tree = self.window.object_tree
        selection = [str(name) for name in tree.selected_objects()]
        selection += [f"{body}.{feature}" for body, feature in tree.selected_features()]
        return scene_print(
            self.session.project.document,
            result.scene if result is not None else None,
            selection=selection,
            # Ohne Renderer (offscreen) hat die Ansicht keine Kamera.
            camera=(
                self.window.viewport.camera_pose()
                if getattr(self.window.viewport, "renderer", None) is not None
                else None
            ),
        )

    def snapshot(self, label: str) -> dict[str, Any]:
        """Der Abdruck jetzt, unter ``states[label]`` (``function_checks.STATE_KEYS``)."""
        printed = self.scene_now()
        self.data["states"][label] = printed
        self.persist()
        return printed

    def picture(self, label: str) -> None:
        """Bild des Fensters und eines offenen Dialogs für Stufe B, relativ zu ``--out``."""
        from PySide6.QtWidgets import QApplication

        for suffix, widget in (("", self.window), ("-dialog", QApplication.activeModalWidget())):
            if widget is None:
                continue
            picture = widget.screen().grabWindow(int(widget.winId()))
            path = self.folder / f"{label}{suffix}.png"
            if picture.save(str(path)):
                self.data["images"].append(path.relative_to(self.out).as_posix())

    def widget(self, name: str) -> Any | None:
        """Das Widget hinter einem Wortschatznamen, oder ``None`` — nur zum Ablesen."""
        from app.ui import guide_targets

        try:
            return guide_targets.widget_for(self.window, name)
        except LookupError:
            return None

    def surface(self) -> Any:
        """Die offene Fläche: der Dialog, sonst die Karte der Auswahl, sonst das Fenster."""
        for name in ("dialog", "selection"):
            widget = self.widget(name)
            if widget is not None and widget.isVisible():
                return widget
        return self.window

    def window_size(self) -> list[int]:
        return [self.window.width(), self.window.height()]

    # --- Vorbereitung ------------------------------------------------------------------

    def prepare(self) -> None:
        """Wachen anlegen, Fenster auf den Schirm, Bildzähler um den Renderer."""
        from tools.function_capture import start_heartbeat

        self.session.failed.connect(
            lambda error: self.data["errors"].append(str(error)), self.window
        )
        self.session.importFailed.connect(
            lambda error: self.data["errors"].append(str(error)), self.window
        )
        self._timers.append(start_heartbeat(self.window, self.heartbeat))
        self._timers.append(self.watch.start(self.window))
        placed = place_window(self.application, self.window, self.variant)
        for _ in range(20):
            self.pump()
        self.data["variant"] = self.variant.protocol(placed, self.window_size())
        self.frames_wrapped = self.frames.wrap(getattr(self.window.viewport, "renderer", None))
        # Der Faktor gilt für Zeiten (Prüfpunkt 6) und Bilder (Z1); die Ziehzeiten
        # trägt erst der Zug nach (:meth:`phase_drag`).
        self.data["frames"] = {"reference_factor": self.reference_factor}
        self.persist()

    def finish(self) -> None:
        """Was die Wachen gesehen haben, ins Protokoll."""
        self.watch.poll()
        self.data["modals"] = self.watch.modal_entries()
        self.data["raw_windows"] = self.watch.raw_entries()
        self.data["windows"] = list(self.watch.windows)
        for timer in self._timers:
            timer.stop()
        self.persist()

    # --- Startszene ---------------------------------------------------------------------

    def scene_path(self, key: str) -> Path | None:
        """Die Kopie einer Szene im Fallordner (Review M6, :func:`case_scene`)."""
        return case_scene(self.folder, self.scenes, key)

    def new_project_line(self) -> str:
        """Der Wortschatzname von *Datei → Neu* in der Menüleiste, oder leer."""
        from app.ui import guide_targets

        return next(
            (
                str(name)
                for name, _menus, action in guide_targets.menubar_entries(self.window)
                if action is self.window.new_action
            ),
            "",
        )

    def reset(self) -> bool:
        """Zurück an die Startszene; die Vorbereitung ist nicht die geprüfte Handlung.

        Die Szene ``startbildschirm`` heißt: kein Projekt, der Fall beginnt dort;
        hat eine Phase ein Projekt geöffnet, führt *Datei → Neu* zurück (wie
        :meth:`phase_switch`). Die leere Szene beginnt beim ersten Mal mit einem
        Klick auf *Neues Projekt*. Sonst öffnet ``open_path`` die Kopie der
        Szenendatei im Fallordner (Konzept §5: „Nur die Startszene entsteht über
        ``open_path``“; :func:`case_scene`). Was die Phase davor geändert hat,
        wird verworfen, ohne die Speicherfrage zu stellen — sie gehört nicht zu
        dieser Zeile.
        """
        on_start = self.window.stack.currentWidget() is self.window.start_screen
        if self.scene_key == START_SCREEN:
            if self.data.get("scene") is None:
                self.data["scene"] = {
                    "key": START_SCREEN,
                    "triangles": 0,
                    "build_s": None,
                    "eval_s": 0.0,
                }
            if on_start:
                return True
            line = self.new_project_line()
            if not line:
                self.data["errors"].append("Datei → Neu trägt keinen Namen im Wortschatz")
                return False
            self.session.forget_changes()
            return self.run_steps(
                "startbildschirm",
                [
                    self.walker.step(f"menu:{line}"),
                    self.wait_step(
                        "startbildschirm steht",
                        lambda: self.window.stack.currentWidget() is self.window.start_screen,
                    ),
                ],
            )
        previous = self.session.last_result
        path = self.scene_path(self.scene_key)
        began = time.perf_counter()
        if self.scene_key == EMPTY_SCENE and on_start:
            steps = [self.walker.step("start.new")]
        elif path is not None:
            self.session.forget_changes()
            steps = [self.do_step("szene öffnen", lambda: self.window.open_path(path))]
        else:
            self.data["errors"].append(f"Startszene {self.scene_key} fehlt unter {self.scenes}")
            return False
        steps.append(
            self.wait_step(
                "szene steht",
                lambda: self.idle() and self.session.last_result is not previous,
            )
        )
        ok = self.run_steps(f"startszene {self.scene_key}", steps)
        self.session.forget_changes()
        if ok and self.data.get("scene") is None:
            result = self.session.last_result
            triangles = sum(entry.mesh.triangle_count for entry in result.scene.objects.values())
            self.data["scene"] = {
                "key": self.scene_key,
                "triangles": triangles,
                "build_s": None,
                "eval_s": round(time.perf_counter() - began, 3),
            }
        return ok

    # --- Wege, Eingaben, Vorschau --------------------------------------------------------------

    def path_steps(self) -> list[Step]:
        return [self.walker.step(target, button) for target, button in route_of(self.row)]

    def input_steps(self, inputs: Mapping[str, Any]) -> list[Step]:
        """Je Feld: hinklicken, alles markieren, tippen; ohne Mitschreiben mit Tab bestätigen.

        Ein Haken wird geklickt; ein Text, der keine Zahl ist, ist eine Wahl
        (``decision``, E3) — getippt wie jede Eingabe.
        """
        from PySide6.QtGui import QKeySequence

        steps: list[Step] = []
        for target, value in inputs.items():
            steps.append(self.walker.step(target))
            if isinstance(value, bool):
                steps.append(
                    Step(
                        f"haken {target}",
                        lambda machine, target=target, value=value: self._tick_box(
                            machine, target, value
                        ),
                        settle_ms=SETTLE_MS,
                    )
                )
                continue
            number = isinstance(value, (int, float))
            text = typed_number(float(value), self.variant.unit) if number else str(value)
            steps.append(
                self.key_step(QKeySequence(QKeySequence.StandardKey.SelectAll), "alles markieren")
            )
            steps.append(
                Step(
                    f"tippen {target}",
                    lambda machine, target=target, text=text, number=number: self._type(
                        target, text, decision=not number
                    ),
                    settle_ms=SETTLE_MS,
                )
            )
        return steps

    def _tick_box(self, machine: StepMachine, target: str, value: bool) -> None:
        """Der Weg hat den Haken einmal geklickt; steht er falsch, kommt ein zweiter Klick."""
        box = self.widget(target)
        if box is not None and bool(box.isChecked()) != value:
            machine.insert([self.walker.step(target)])

    def _type(self, target: str, text: str, *, decision: bool = False) -> None:
        """Tippt ans Fokusfeld; ein Feld, das erst beim Verlassen übernimmt, bekommt Tab."""
        from PySide6.QtWidgets import QAbstractSpinBox, QApplication

        self.walker.record({"target": target, "typed": text, "button": None, "decision": decision})
        self.ports.type_text(text)
        focus = QApplication.focusWidget()
        spin = (
            focus
            if isinstance(focus, QAbstractSpinBox)
            else getattr(focus, "parentWidget", lambda: None)()
        )
        if isinstance(spin, QAbstractSpinBox) and not spin.keyboardTracking():
            self.walker.record({"target": target, "key": "Tab", "button": None})
            self.ports.keys("Tab")

    def preview_steps(self) -> list[Step]:
        """Warten, bis die Vorschau steht oder abgesagt ist — abgelesen, nicht erfragt.

        Steht: das Band zeigt die Legende einer neuen Differenz. Abgesagt: der
        Übernehmen-Knopf ist gesperrt und nennt seinen Grund (Tooltip und
        zugängliche Beschreibung). Beides sieht der Kunde.
        """
        shown = {"difference": self.window.viewport.difference}

        def remember(machine: StepMachine) -> None:
            shown["difference"] = self.window.viewport.difference

        def settled() -> bool:
            banner = self.widget("preview.banner")
            difference = self.window.viewport.difference
            fresh = difference is not None and difference is not shown["difference"]
            legend = getattr(banner, "legend", None)
            if (
                fresh
                and banner is not None
                and banner.isVisible()
                and legend is not None
                and legend.isVisible()
            ):
                return True
            button = self.widget(self.apply_target) if self.apply_target else None
            if button is not None and not button.isEnabled():
                return bool(button.accessibleDescription() or button.toolTip())
            return not self.apply_target and self.idle()

        return [Step("vorschau merken", remember), self.wait_step("vorschau steht", settled)]

    def preview_record(self) -> dict[str, Any]:
        """Band, Differenz und Kennzahlen der Vorschau (Prüfpunkt 3, I2; Schema ``preview``)."""
        from app.ui.session import COARSE_PREVIEW_ABOVE
        from tools.file_acceptance import body_digest
        from tools.function_capture import visible_texts

        banner = self.widget("preview.banner")
        difference = self.window.viewport.difference
        triangles = (self.data.get("scene") or {}).get("triangles") or 0
        entries = getattr(difference, "entries", {}) if difference is not None else {}
        shown = {key: entry for key, entry in entries.items() if entry.result is not None}
        metrics = result_metrics(_SceneOf(shown), self.session.project.document, None)
        return {
            "bodies": {str(key): body_digest(entry.result.mesh) for key, entry in shown.items()},
            "coarse": triangles > COARSE_PREVIEW_ABOVE,
            "banner_text": "\n".join(visible_texts(banner))
            if banner is not None and banner.isVisible()
            else "",
            "volume": metrics.get("volume"),
            "extent": metrics.get("extent"),
        }

    def capture_surface(self, root: Any) -> None:
        """G1 bis G8, Texte, Felder und Tab-Kette der offenen Fläche ins Protokoll."""
        from tools import function_capture as capture

        theme = self.variant.theme
        for name, entries in capture.sheet_snapshot(root, theme, self.window_size()).items():
            self.data[name] = [*(self.data.get(name) or []), *entries]
        self.data["texts"] = [*(self.data.get("texts") or []), *capture.text_entries(root)]
        self.data["fields"] = [*(self.data.get("fields") or []), *capture.field_entries(root)]
        self.data["empty_states"] = [
            *(self.data.get("empty_states") or []),
            *capture.empty_states(self.window),
        ]

    # --- Die Phasen ------------------------------------------------------------------------

    def run(self) -> None:
        """Die Phasen der Variante (:data:`PHASES`), jede an der Startszene (Review M5).

        Vor jeder Phase geht der Fall zurück an die Startszene — auch nach einer,
        die mit einer Ausnahme endete. Gelingt das nicht, läuft die Phase nicht:
        Sie stünde sonst an dem, was die vorige liegen ließ, und ihre Messung
        gälte einer anderen Lage. Der Grund steht in ``errors``.
        """
        for name in self.variant.phases or PHASES[self.variant.set]:
            phase: Callable[[], None] = getattr(self, f"phase_{name}")
            self.bench["stage"] = name
            try:
                if not self.reset():
                    self.data["errors"].append(f"{name}: Startszene nicht herstellbar")
                    continue
                phase()
            except Exception:
                self.data["errors"].append(f"{name}: {traceback.format_exc()}")
            finally:
                self.persist()
        self.finish()

    def phase_search(self) -> None:
        """Prüfpunkt 1 und I6: jede Suchprobe getippt, der Rang aus ``search_hits``."""
        from PySide6.QtGui import QKeySequence

        from app.ui import guide_targets

        probes = [{**probe, "question": False} for probe in self.spec.get("search_probes") or ()]
        probes += [
            {"word": text, "origin": "fragebogen", "question": True}
            for text in self.spec.get("questions") or ()
        ]
        if not probes:
            unmeasured(self.data, "search", "Spezifikation ohne Suchproben")
            return
        target = str(self.row.get("target") or "")
        found: dict[str, Any] = {}
        for probe in probes:
            word = str(probe["word"])
            hits: list[str] = []

            def read(machine: StepMachine, hits: list[str] = hits) -> None:
                hits[:] = list(guide_targets.search_hits(self.window))  # type: ignore[attr-defined]

            ok = self.run_steps(
                f"suche {word}",
                [
                    self.walker.step("search"),
                    self.key_step(
                        QKeySequence(QKeySequence.StandardKey.SelectAll), "alles markieren"
                    ),
                    Step(
                        f"tippen {word}",
                        lambda machine, word=word: self._type("search", word),
                        settle_ms=SEARCH_SETTLE_MS,
                    ),
                    Step("treffer lesen", read),
                    self.key_step("Escape", "suche leeren"),
                ],
            )
            found[word] = {
                "rank": search_rank(hits, target) if ok else None,
                "hits": hits[:10],
                "origin": probe.get("origin"),
                "question": bool(probe["question"]),
            }
        self.data["search"] = found

    def phase_escape(self) -> None:
        """Prüfpunkt 5: Weg, Eingaben, Vorschau, dann Escape — der Stand ist der vorher."""
        inputs = self.spec.get("inputs") or {}
        before = self.scene_now()
        if not inputs:
            unmeasured(self.data, "states.escape", "keine Eingaben, kein Entwurf zum Verwerfen")
            return
        self.run_steps(
            "escape",
            [
                *self.path_steps(),
                *self.input_steps(inputs),
                *self.preview_steps(),
                self.key_step("Escape", "entwurf verwerfen"),
                self.wait_step("ruhe", self.idle),
            ],
        )
        self.data["states"].setdefault("before", before)
        self.snapshot("escape")

    def phase_main(self) -> None:
        """Hauptweg: Ort, Weg, Eingaben, Vorschau, Fläche, Übernehmen, Rückgängig, Wiederholen."""
        from PySide6.QtWidgets import QApplication

        from tools import function_capture as capture

        inputs = self.spec.get("inputs") or {}
        target = walk_target(self.row)
        focus_before = QApplication.focusWidget()
        self.snapshot("before")
        self.picture("01-vorher")
        surface: dict[str, Any] = {}

        def take_surface(machine: StepMachine) -> None:
            root = self.surface()
            self.watch.own.add(type(root).__name__)
            self.capture_surface(root)
            self.data["messages"] = capture.message_entries(self.window)
            apply_button = self.widget(self.apply_target) if self.apply_target else None
            if apply_button is not None and apply_button.isVisible():
                self.data["state_images"] = [
                    {
                        "surface": type(root).__name__,
                        "widget": capture.name_of(apply_button),
                        "states": capture.state_images(apply_button),
                    }
                ]
            chain = capture.tab_chain(root, lambda: self.ports.keys("Tab"))
            self.data["tab_chain"] = chain
            self.data["names"] = [entry["name"] for entry in chain]
            surface["root"] = type(root).__name__
            self.picture("02-flaeche")

        self.run_steps(
            PATH_PHASE,
            [
                *self.path_steps(),
                *self.input_steps(inputs),
                *(self.preview_steps() if inputs else [self.wait_step("ruhe", self.idle)]),
                Step("fläche aufnehmen", take_surface),
            ],
        )
        self.data["place"] = place_of(self.data["steps"], target)
        self.data["spot"] = self.spot()
        if inputs:
            self.data["preview"] = self.preview_record()
            self.snapshot("preview")
        if self.data["place"]["error"] is not None:
            unmeasured(self.data, "result", "der Hauptweg kam nicht an")
            return
        self.apply_and_measure()
        after = QApplication.focusWidget()
        self.data["focus_return"] = (
            None
            if focus_before is None or after is None
            else capture.name_of(after) == capture.name_of(focus_before)
        )
        self.undo_and_redo()

    def spot(self) -> dict[str, Any] | None:
        """E4: liegt über der bearbeiteten Stelle ein Fenster? Über ``view:`` und die Probe."""
        if self.selected is None:
            return None
        name = f"view:{self.selected[0]}.{self.selected[1]}"
        try:
            click = self.ports.next_click(name)
        except LookupError:
            return None
        point = self.ports.centre(click.rect)
        hit = self.ports.widget_under(point)
        covered = hit is not None and not self.ports.covers(click, hit)
        return {
            "point": self.ports.point_data(point),
            "covered_by": type(hit.window()).__name__ if covered and hit is not None else None,
        }

    def apply_and_measure(self) -> None:
        """Übernehmen mit Herzschlag und Zeiten (Prüfpunkt 6), dann Ergebnis und Kommandozeile."""
        from PySide6.QtWidgets import QApplication, QProgressBar

        previous = self.session.last_result
        timing: dict[str, Any] = {
            "total_s": None,
            "first_feedback_s": None,
            "progress_shown_s": None,
            "cancel_shown_s": None,
            "main_gap_ms": None,
            "budget_s": self.spec.get("budget_s"),
        }
        status_before = self.window.statusBar().currentMessage()
        moment = {"t0": 0.0}

        def start(machine: StepMachine) -> None:
            moment["t0"] = time.perf_counter()
            self.heartbeat.open(moment["t0"])

        def watched() -> bool:
            elapsed = round(time.perf_counter() - moment["t0"], 3)
            if timing["first_feedback_s"] is None and (
                QApplication.overrideCursor() is not None
                or self.session.busy
                or self.window.statusBar().currentMessage() != status_before
                or self.session.last_result is not previous
            ):
                timing["first_feedback_s"] = elapsed
            if timing["progress_shown_s"] is None and any(
                bar.isVisible() for bar in self.window.statusBar().findChildren(QProgressBar)
            ):
                timing["progress_shown_s"] = elapsed
            cancel = self.widget("progress.cancel")
            if timing["cancel_shown_s"] is None and cancel is not None and cancel.isVisible():
                timing["cancel_shown_s"] = elapsed
            return self.idle() and self.session.last_result is not previous

        steps = [Step("uhr", start)]
        if self.apply_target:
            steps.append(self.walker.step(self.apply_target))
        steps.append(self.wait_step("ergebnis", watched))
        ok = self.run_steps(APPLY_PHASE, steps)
        timing["main_gap_ms"] = self.heartbeat.close(time.perf_counter())
        if ok:
            timing["total_s"] = round(time.perf_counter() - moment["t0"], 3)
        self.data["timing"] = timing
        # Z2: Ein Fenster, das nach dem Übernehmen offen steht, hat die Wache
        # schon in modals notiert; hier steht es zum Lauf dazu.
        self.watch.note_after(APPLY_PHASE)
        self.watch.poll()
        applied = self.snapshot("applied")
        self.picture("03-uebernommen")
        result = self.session.last_result
        if result is not None:
            self.data["result"] = {
                "metrics": result_metrics(
                    result.scene, self.session.project.document, self.selected
                ),
                "digest": bodies_digest(applied["bodies"]),
            }
        self.data["cli"] = self.compare_with_cli()

    def undo_and_redo(self) -> None:
        """Rückgängig und Wiederholen über ihre Tasten (Prüfpunkt 5)."""
        for label, keys in (("undo", self.undo_keys()), ("redo", self.redo_keys())):
            previous = self.session.last_result
            self.run_steps(
                label,
                [
                    self.key_step(keys, label),
                    self.wait_step(
                        f"{label} steht",
                        lambda previous=previous: (
                            self.idle() and self.session.last_result is not previous
                        ),
                        timeout_s=60.0,
                    ),
                ],
            )
            self.snapshot(label)

    def compare_with_cli(self) -> dict[str, Any] | None:
        """Prüfpunkt 4: Dieselben Werte über die Kommandozeile ergeben ein druckgleiches Netz.

        Die Startszene wird kopiert, ``app.cli.main run`` legt den Schritt mit den
        Werten des übernommenen an, und beide Dokumente gehen in derselben Güte
        (fein) durch den einen Vergleich der Suite (``tests/print_equal``). Der
        Prozess erbt die umgebogenen Nutzerordner dieses Falls.
        """
        import shutil
        import subprocess
        from copy import deepcopy

        from app.core.scene.serialise import operation_to_data

        states = self.data["states"]
        document = self.session.project.document
        grown = len(states.get("applied", {}).get("ops", ())) > len(
            states.get("before", {}).get("ops", ())
        )
        if not document.ops or not grown:
            unmeasured(self.data, "cli", "kein neuer Schritt im Verlauf")
            return None
        scene = self.scenes / f"{self.scene_key}.p3d"
        if not scene.is_file():
            unmeasured(self.data, "cli", "Startszene ohne Datei")
            return None
        arguments = cli_arguments(operation_to_data(document.ops[-1]))
        if arguments is None:
            unmeasured(self.data, "cli", "Werte ohne Feld auf der Kommandozeile")
            return None
        copy = self.folder / "cli.p3d"
        shutil.copyfile(scene, copy)
        finished = subprocess.run(
            [sys.executable, "-m", "app.cli.main", "run", *arguments, str(copy)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            check=False,
        )
        if finished.returncode != 0:
            self.data["errors"].append(f"Kommandozeile: {finished.stderr[-2000:]}")
            unmeasured(self.data, "cli", "die Kommandozeile lehnte ab")
            return None
        from app.core.scene import project as projects
        from app.core.scene.evaluate import evaluate
        from tests import print_equal
        from tools.file_acceptance import body_digest

        loaded = projects.load(copy)
        profile = self.session.profile
        window_result = evaluate(
            deepcopy(document), profile, sources=projects.ProjectSources(self.session.project)
        )
        cli_result = evaluate(loaded.document, profile, sources=projects.ProjectSources(loaded))
        verdict = print_equal.compare(
            print_equal.shot(window_result, exports=()),
            print_equal.shot(cli_result, exports=()),
        )
        return {
            "digest": bodies_digest(
                {
                    str(key): body_digest(entry.mesh)
                    for key, entry in cli_result.scene.objects.items()
                }
            ),
            "max_deviation_mm": verdict.largest,
            "print_equal": verdict.print_equal,
        }

    def phase_revise(self) -> None:
        """Prüfpunkt 12: Schritt über Kontextmenü und Doppelklick ändern, Verlauf gleich lang.

        Je Weg öffnet der Klick den übernommenen Schritt; Felder und Parameter
        stehen nebeneinander, dann eine neue Zahl ins erste Zahlenfeld des
        Schritts, Übernehmen, und die Verlaufslänge danach.
        """
        from app.core.scene.serialise import operation_to_data
        from tools import function_capture as capture
        from tools.file_acceptance import changed_value

        applied = self.data["states"].get("redo") or self.data["states"].get("applied")
        if not applied or not applied.get("ops"):
            unmeasured(self.data, "revise", "kein übernommener Schritt")
            return
        number = len(applied["ops"])
        entries: list[dict[str, Any]] = []
        for way, route in (
            ("menue", [(f"history.row:{number}", "right"), ("menu:history.edit", "left")]),
            ("doppelklick", [(f"history.row:{number}", "double")]),
        ):
            self.reset()
            self.run_steps(
                f"übernehmen für {way}",
                [*self.path_steps(), *self.input_steps(self.spec.get("inputs") or {})]
                + ([self.walker.step(self.apply_target)] if self.apply_target else [])
                + [self.wait_step("übernommen", self.idle)],
            )
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
            record: dict[str, Any] = {
                "way": way,
                "opened": False,
                "fields": {},
                "params": params,
                "history_before": len(document.ops),
                "history_after": None,
            }

            def read(machine: StepMachine, record: dict[str, Any] = record) -> None:
                root = self.surface()
                record["opened"] = root is not self.window
                record["fields"] = capture.field_values(root)

            self.run_steps(
                f"nachträglich {way}",
                [
                    *(self.walker.step(name, button) for name, button in route),
                    Step("felder lesen", read, settle_ms=SETTLE_MS * 2),
                ],
            )
            numeric = [
                name
                for name, value in record["fields"].items()
                if isinstance(params.get(name), (int, float))
                and not isinstance(params.get(name), bool)
            ]
            if record["opened"] and numeric:
                name = numeric[0]
                previous = self.session.last_result
                accept = "dialog.accept" if self.widget("dialog") is not None else "feature.apply"
                self.run_steps(
                    f"neuer wert {way}",
                    [
                        *self.input_steps({f"field:{name}": changed_value(float(params[name]))}),
                        self.walker.step(accept),
                        self.wait_step(
                            "geändert",
                            lambda previous=previous: (
                                self.idle() and self.session.last_result is not previous
                            ),
                        ),
                    ],
                )
            record["history_after"] = len(self.session.project.document.ops)
            entries.append(record)
        self.data["revise"] = entries

    def phase_fault(self) -> None:
        """Prüfpunkt 7: erzwungener Fehlfall, Meldung, erste Handlung und ihre Wirkung."""
        from tools import function_capture as capture

        fault = self.spec.get("fault_case")
        if not fault:
            unmeasured(self.data, "messages", "Spezifikation ohne Fehlfall")
            return
        messages: list[dict[str, Any]] = []

        def read(machine: StepMachine) -> None:
            messages.extend(capture.message_entries(self.window))

        inputs = fault.get("inputs") or {}
        self.run_steps(
            "fehlfall",
            [
                *self.path_steps(),
                *self.input_steps(inputs),
                *(self.preview_steps() if inputs else []),
                Step("meldung lesen", read, settle_ms=SETTLE_MS),
            ],
        )
        self.picture("04-fehlfall")
        offered = [
            action
            for message in messages
            for action in message.get("actions", ())
            if action.get("target")
        ]
        if offered:
            action = offered[0]
            before = self.scene_now()
            modal_before = len(self.watch.modals)
            self.run_steps(
                "handlung der meldung",
                [
                    self.walker.step(str(action["target"])),
                    self.wait_step("ruhe", self.idle, EFFECT_WINDOW_S * 30),
                ],
            )
            self.watch.poll()
            after = self.scene_now()
            action["clicked"] = True
            action["effect"] = (
                compare_prints(before, after)["same"] is False
                or len(self.watch.modals) > modal_before
                or self.surface() is not self.window
            )
        self.data["messages"] = [*(self.data.get("messages") or []), *messages]

    def phase_matrix(self) -> None:
        """Prüfpunkt 13: sechs Auswahlstufen — angeboten, grau, fehlt, nicht herstellbar."""
        result = self.session.last_result
        objects = list(result.scene.objects.items()) if result is not None else []
        features = [
            (str(key), str(name), feature.kind)
            for key, entry in objects
            for name, feature in entry.features.items()
        ]
        bodies = [str(key) for key, _entry in objects]
        edges = [entry for entry in features if entry[2] == "edge"]
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
            "eine_kante": [(f"view:{edges[0][0]}.{edges[0][1]}", "left")] if edges else None,
        }
        assert tuple(clicks) == tuple(SELECTION_STAGES)
        target = walk_target(self.row)
        matrix: dict[str, Any] = {}
        for stage, route in clicks.items():
            if route is None:
                matrix[stage] = {
                    "state": MATRIX_UNREACHABLE,
                    "reason": "die Startszene hat dafür zu wenig",
                    "effective": None,
                }
                continue
            self.reset()
            selection = [self.key_step("Escape", "auswahl leeren")] if not route else []
            selection += [self.walker.step(name, button) for name, button in route]
            if not self.run_steps(f"matrix {stage} auswahl", selection):
                matrix[stage] = {
                    "state": MATRIX_UNREACHABLE,
                    "reason": "die Auswahl ließ sich nicht klicken",
                    "effective": None,
                }
                continue
            matrix[stage] = self.offer_state(target, f"matrix {stage}")
        self.data["matrix"] = matrix

    def offer_state(self, target: str, label: str) -> dict[str, Any]:
        """Wie ein Ziel gerade dasteht: angeboten (und wirksam?), grau mit Grund, fehlt."""
        from tools import function_capture as capture

        try:
            self.ports.next_click(target)
        except LookupError as error:
            return {"state": "fehlt", "reason": str(error), "effective": None}
        widget = self.widget(target)
        if widget is not None and not widget.isEnabled():
            return {
                "state": "grau",
                "reason": widget.accessibleDescription() or widget.toolTip(),
                "effective": None,
            }
        before = self.scene_now()
        result_before = self.session.last_result
        difference = self.window.viewport.difference
        opened: dict[str, bool] = {}

        def look(machine: StepMachine) -> None:
            opened["modal"] = capture.modal_now() is not None
            opened["surface"] = self.surface() is not self.window
            opened["preview"] = self.window.viewport.difference is not difference
            opened["result"] = self.session.last_result is not result_before

        self.run_steps(
            f"{label} klick",
            [
                self.walker.step(target),
                Step("wirkung", look, settle_ms=int(EFFECT_WINDOW_S * 1000)),
            ],
        )
        after = self.scene_now()
        effective = any(opened.values()) or compare_prints(before, after)["same"] is False
        return {"state": "angeboten", "reason": "", "effective": effective}

    def phase_abort(self) -> None:
        """Prüfpunkt 14: *Abbrechen* während der Rechnung, danach der Stand von vorher."""
        if self.scene_key not in SLOW_SCENES:
            unmeasured(self.data, "abort", "Startszene rechnet nicht lang genug")
            return
        inputs = self.spec.get("inputs") or {}
        before = self.scene_now()
        moment: dict[str, Any] = {"t0": 0.0, "shown": None}

        def start(machine: StepMachine) -> None:
            moment["t0"] = time.perf_counter()

        def cancel_visible() -> bool:
            cancel = self.widget("progress.cancel")
            if cancel is not None and cancel.isVisible():
                moment["shown"] = round(time.perf_counter() - moment["t0"], 3)
                return True
            return False

        steps = [*self.path_steps(), *self.input_steps(inputs), Step("uhr", start)]
        if self.apply_target:
            steps.append(self.walker.step(self.apply_target))
        steps += [
            self.wait_step("abbrechen sichtbar", cancel_visible, timeout_s=30.0),
            self.walker.step("progress.cancel"),
            self.wait_step("ruhe", lambda: not self.session.busy, timeout_s=60.0),
        ]
        clicked = self.run_steps("abbruch", steps)
        settle_until = time.perf_counter() + LATE_WINDOW_S
        while time.perf_counter() < settle_until:
            self.pump()
        self.data["states"].setdefault("before", before)
        self.snapshot("aborted")
        # Wie lange die Rechnung dauert, die hier abgebrochen wurde: aus dem Lauf
        # ohne Abbruch an derselben Szene — dem Hauptweg (Review M4) —, roh auf
        # diesem Rechner; nicht die Ladezeit der Startszene.
        timing = self.data.get("timing") or {}
        if timing.get("total_s") is None:
            unmeasured(self.data, "abort.eval_s", "der Hauptweg ohne Abbruch lief nicht durch")
        self.data["abort"] = {
            "eval_s": timing.get("total_s"),
            "cancel_shown_s": moment["shown"],
            "clicked": clicked,
        }

    def phase_halt(self) -> None:
        """Prüfpunkt 15: Haltgrund mit Schrittnummer; Einfügen vor dem letzten Schritt."""
        from tools import function_capture as capture

        if self.scene_key == "halt":
            texts = [entry["text"] for entry in capture.message_entries(self.window)]
            texts += capture.visible_texts(self.window.object_tree)
            reason = next(
                (text for text in texts if step_number(text) is not None), texts[0] if texts else ""
            )
            self.data["halt"] = {"text": reason, "step": step_number(reason)}
        else:
            unmeasured(self.data, "halt", "Startszene ohne angehaltene Kette")
        length = len(self.session.project.document.ops)
        if length < 1:
            unmeasured(self.data, "insertion", "kein Schritt, vor dem eingefügt werden könnte")
            return
        previous = self.session.last_result
        record: dict[str, Any] = {"outcome": None, "text": "", "actions": []}

        def read(machine: StepMachine) -> None:
            messages = capture.message_entries(self.window)
            record["text"] = " ".join(message["text"] for message in messages)
            record["actions"] = [
                {"label": action["label"], "target": action["target"]}
                for message in messages
                for action in message["actions"]
            ]
            record["outcome"] = "ergebnis" if self.session.last_result is not previous else "absage"

        self.run_steps(
            "einfügen",
            [
                self.walker.step(f"history.row:{length}", "right"),
                self.walker.step("menu:history.insert"),
                *self.path_steps(),
                *self.input_steps(self.spec.get("inputs") or {}),
                *([self.walker.step(self.apply_target)] if self.apply_target else []),
                Step("antwort lesen", read, settle_ms=int(EFFECT_WINDOW_S * 1000)),
            ],
        )
        self.data["insertion"] = record if record["outcome"] is not None else None
        if record["outcome"] is None:
            unmeasured(self.data, "insertion", "der Weg zur Einfügemarke kam nicht an")

    def recent_number(self, stem: str) -> int | None:
        """Die Stelle eines Projekts unter „Zuletzt geöffnet“ (ab 1), abgelesen an der Liste."""
        listing = self.window.start_screen.recent_list
        for row in range(listing.count()):
            item = listing.item(row)
            if item is not None and stem in f"{item.text()} {item.toolTip()}":
                return row + 1
        return None

    def phase_switch(self) -> None:
        """Prüfpunkt 16: Projektwechsel während Vorschau, Entwurf und Rechnung (Konzept §4).

        Der Weg des Kunden: *Datei → Neu* führt zum Startbildschirm, dort steht
        „Zuletzt geöffnet“ (``start.recent:<n>``); die Stelle des zweiten Projekts
        wird an der Liste abgelesen, wenn sie dasteht. Eine Speicherfrage
        beantwortet der Prüfstand mit *Verwerfen* (:meth:`answer_discard`). Je
        Lage (``function_checks.SWITCH_PHASES``):

        * ``vorschau`` — Eingaben getippt, die Vorschau steht;
        * ``entwurf`` — Eingaben getippt, gewechselt wird sofort, ohne auf die
          Vorschau zu warten;
        * ``rechnung`` — *Übernehmen* geklickt, gewechselt wird, während die
          Sitzung rechnet. War die Rechnung beim ersten Wechselklick schon vorbei,
          ist diese Lage nicht gemessen.

        Spät heißt: Nach dem Wechsel, wenn das neue Projekt steht, kommt binnen
        :data:`LATE_WINDOW_S` noch ein Fenster, eine neue Meldung oder eine
        Änderung am Abdruck des neuen Projekts.
        """
        from tools.function_checks import SWITCH_PHASES

        inputs = self.spec.get("inputs") or {}
        if self.scene_path(SECOND_SCENE) is None:
            unmeasured(self.data, "switch", f"Szene {SECOND_SCENE} fehlt")
            return
        new_line = self.new_project_line()
        if not new_line:
            unmeasured(self.data, "switch", "Datei → Neu trägt keinen Namen im Wortschatz")
            return
        measured: list[str] = []
        late: list[dict[str, Any]] = []
        notes: list[str] = []
        for number, situation in enumerate(SWITCH_PHASES):
            if number and not self.reset():
                notes.append(f"{situation}: Startszene nicht herstellbar")
                continue
            if situation in ("vorschau", "entwurf") and not inputs:
                notes.append(f"{situation}: keine Eingaben, kein {situation}")
                continue
            outcome = self.switch_once(situation, inputs, new_line)
            if outcome is None:
                notes.append(f"{situation}: der Wechsel kam nicht an oder fiel nicht in die Lage")
                continue
            measured.append(situation)
            late += outcome
            if situation == SWITCH_PHASES[0]:
                self.snapshot("after_switch")
        if notes:
            unmeasured(self.data, "switch", "; ".join(notes))
        if measured:
            self.data["switch"] = {"phases": measured, "late_events": late}

    def switch_once(
        self, situation: str, inputs: Mapping[str, Any], new_line: str
    ) -> list[dict[str, Any]] | None:
        """Ein Wechsel in einer Lage; die späten Ereignisse, oder ``None`` ohne Messung."""
        from tools import function_capture as capture

        project = self.session.project
        computing: dict[str, bool | None] = {"busy": None}

        def to_the_recent(machine: StepMachine) -> None:
            number = self.recent_number(SECOND_SCENE)
            if number is None:
                raise BenchFinding(
                    NOT_FOUND,
                    f"{RECENT_KIND}:?",
                    f"{SECOND_SCENE} steht nicht unter „Zuletzt geöffnet“",
                )
            machine.insert([self.walker.step(f"{RECENT_KIND}:{number}")])

        def note_busy(machine: StepMachine) -> None:
            computing["busy"] = bool(self.session.busy)

        steps = [*self.path_steps(), *self.input_steps(inputs)]
        if situation == "vorschau":
            steps += self.preview_steps()
        elif situation == "rechnung":
            if inputs:
                steps += self.preview_steps()
            if self.apply_target:
                steps.append(self.walker.step(self.apply_target))
            steps.append(Step("rechnet sie?", note_busy))
        steps += [
            self.walker.step(f"menu:{new_line}"),
            Step(
                "rückfrage",
                self.answer_discard,
                ready=lambda: capture.modal_now() is not None or self.on_start_screen(),
            ),
            self.wait_step("startbildschirm", self.on_start_screen),
            Step("liste lesen", to_the_recent, settle_ms=SETTLE_MS),
            self.wait_step(
                "anderes projekt", lambda: self.session.project is not project and self.idle()
            ),
        ]
        if not self.run_steps(f"wechsel {situation}", steps):
            return None
        if situation == "rechnung" and not computing["busy"]:
            return None
        self.watch.poll()
        modals_before = len(self.watch.modals)
        print_before = self.scene_now()
        texts_before = {entry["text"] for entry in capture.message_entries(self.window)}
        until = time.perf_counter() + LATE_WINDOW_S
        while time.perf_counter() < until:
            self.pump()
        self.watch.poll()
        events = [
            {"kind": "fenster", "text": entry["title"], "phase": situation}
            for entry in self.watch.modals[modals_before:]
        ]
        events += [
            {"kind": "meldung", "text": entry["text"], "phase": situation}
            for entry in capture.message_entries(self.window)
            if entry["text"] and entry["text"] not in texts_before
        ]
        changed = compare_prints(print_before, self.scene_now())
        if changed["same"] is False:
            events.append(
                {
                    "kind": "abdruck",
                    "text": f"das neue Projekt änderte sich danach: {changed['differs']}",
                    "phase": situation,
                }
            )
        return events

    def on_start_screen(self) -> bool:
        return bool(self.window.stack.currentWidget() is self.window.start_screen)

    def answer_discard(self, machine: StepMachine) -> None:
        """Steht die Speicherfrage, klickt der Prüfstand *Verwerfen* — wie der Kunde, der wechselt.

        Die Frage (``confirm_unsaved``, ``confirm_discard``) trägt keinen
        Wortschatznamen (Lücke für W); geklickt wird der Knopf mit der Rolle
        „verwerfen“, mit Probe (:func:`click_button`).
        """
        from PySide6.QtWidgets import QApplication, QMessageBox

        box = QApplication.activeModalWidget()
        if not isinstance(box, QMessageBox):
            return
        discard = next(
            (
                button
                for button in box.buttons()
                if box.buttonRole(button) == QMessageBox.ButtonRole.DestructiveRole
            ),
            None,
        )
        if discard is None:
            raise RuntimeError(f"Rückfrage „{box.windowTitle()}“ ohne Knopf zum Verwerfen")
        if not click_button(self.ports, self.walker, discard, "Verwerfen"):
            raise BenchFinding(COVERED, "Verwerfen", "der Knopf liegt unter etwas anderem")

    def phase_hover(self) -> None:
        """I1: Name und Maß beim Überfahren je erkannter Art (``view:``), ohne Klick."""
        from tools import function_capture as capture

        result = self.session.last_result
        if result is None or not any(entry.features for entry in result.scene.objects.values()):
            unmeasured(self.data, "hover_labels", "die Startszene trägt kein Merkmal")
            return
        labels: list[dict[str, Any]] = []
        seen: set[str] = set()
        for key, entry in result.scene.objects.items():
            for name, feature in entry.features.items():
                if feature.kind in seen:
                    continue
                seen.add(feature.kind)
                target = f"view:{key}.{name}"
                texts: list[str] = []

                def hover(machine: StepMachine, target: str = target) -> None:
                    click = self.ports.next_click(target)
                    self.ports.move(self.ports.centre(click.rect))

                def read(machine: StepMachine, texts: list[str] = texts) -> None:
                    texts[:] = capture.visible_texts(self.window.viewport)

                self.run_steps(
                    f"überfahren {target}",
                    [Step("hin", hover), Step("lesen", read, settle_ms=SETTLE_MS * 4)],
                )
                labels.append({"kind": feature.kind, "label": " ".join(texts)})
        self.data["hover_labels"] = labels

    def phase_drag(self) -> None:
        """Z1: ein Zug am Griff der Zeile, je Bewegung die rohe Zeit bis zum nächsten Bild."""
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest

        target = walk_target(self.row)
        if not target.startswith("handle:") and "Z1" not in (self.spec.get("criteria") or ()):
            unmeasured(self.data, "frames.raw_drag_ms", "kein Griff an dieser Zeile")
            return
        if not self.frames_wrapped:
            unmeasured(self.data, "frames.raw_drag_ms", "kein Renderer, kein Bildzähler")
            return
        moves: list[float] = []
        gripped = {"signals": 0}

        def noticed(*_values: object) -> None:
            gripped["signals"] += 1

        # Gefasst ist der Griff, wenn die Ansicht während des Zugs einen ihrer
        # Zugwerte meldet — Geist, Zahl am Zeiger, verschobener Körper (Review L11).
        listened = [
            getattr(self.window.viewport, name)
            for name in DRAG_SIGNALS
            if hasattr(self.window.viewport, name)
        ]
        for signal in listened:
            signal.connect(noticed)

        def pull(machine: StepMachine) -> None:
            click = self.ports.next_click(target)
            point = self.ports.centre(click.rect)
            hit = self.ports.widget_under(point)
            if hit is None or not self.ports.covers(click, hit):
                raise BenchFinding(COVERED, target, "der Griff liegt unter etwas anderem")
            local = hit.mapFromGlobal(point)
            QTest.mousePress(hit, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local)
            for number in range(1, DRAG_MOVES + 1):
                moves.append(time.perf_counter())
                QTest.mouseMove(hit, local + QPoint(4 * number, 0))
                # Im Takt einer Hand an der Maus, nicht so schnell die Schleife kann.
                until = time.perf_counter() + DRAG_TICK_S
                while time.perf_counter() < until:
                    self.application.processEvents()
            QTest.mouseRelease(
                hit, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local
            )

        try:
            self.run_steps(
                "zug", [*self.path_steps()[:-1], Step("ziehen", pull, settle_ms=SETTLE_MS)]
            )
        finally:
            for signal in listened:
                signal.disconnect(noticed)
        if not gripped["signals"]:
            unmeasured(self.data, "frames.raw_drag_ms", "der Zug fasste keinen Griff")
            return
        # Roh, wie gemessen; umgerechnet wird einmal, bei D0-U (Review M3).
        self.data["frames"] = {
            "raw_drag_ms": [
                None if value is None else round(value, 1) for value in self.frames.latencies(moves)
            ],
            "reference_factor": self.reference_factor,
        }

    def phase_licence(self) -> None:
        """Prüfpunkt 18: Wie das Ziel im Lizenzzustand dasteht, und ob Schreiben gesperrt ist."""
        target = walk_target(self.row)
        before = self.scene_now()
        selection = [
            self.walker.step(name, button) for name, button in route_of(self.row) if name != target
        ]
        self.run_steps(PATH_PHASE, selection)
        state = self.offer_state(target, "lizenz")
        writes = self.row.get("kind") == "operation" or (
            compare_prints(before, self.scene_now())["same"] is False
        )
        self.data["licence_runs"] = {
            self.variant.licence: {
                "writes": writes,
                "enabled": state["state"] == "angeboten",
                "reason": state.get("reason", ""),
            }
        }

    def phase_surface(self) -> None:
        """Zoll, Skalierung, Thema, Bewegung: Weg bis zur offenen Fläche, dann ihre Aufnahmen."""

        def take(machine: StepMachine) -> None:
            self.capture_surface(self.surface())
            self.picture(f"flaeche-{self.variant.set}")

        self.run_steps(
            PATH_PHASE, [*self.path_steps(), Step("aufnehmen", take, settle_ms=SETTLE_MS * 2)]
        )


class _SceneOf:
    """Die Einträge einer Vorschaudifferenz als Szene für :func:`result_metrics`."""

    def __init__(self, entries: Mapping[Any, Any]) -> None:
        self.objects = {
            key: _Body(entry.result.mesh, getattr(entry.result, "features", {}) or {})
            for key, entry in entries.items()
            if entry.result is not None
        }


@dataclass(slots=True)
class _Body:
    mesh: Any
    features: Mapping[str, Any]


#: Wie lange der Startfall auf das Starttor wartet: Meldung oder Hauptfenster (Sekunden).
START_WAIT_S: Final = 120.0


class StartFlow:
    """Der Startfall (D12, Zustand ``over``): der echte Startweg über ``app.ui.app.main``.

    Eine abgelaufene Demo startet nicht (Demo-Konzept §2 B2): ``main`` zeigt den
    Abschied und endet mit einem eigenen Ausgang. Der Prüfstand umgeht das
    Starttor nicht — er setzt nur den Zustand über die Nahtstelle der Suite
    (:func:`apply_licence`) und ruft ``main``. Weil ``main`` die
    ``QApplication`` selbst baut, wartet ein Nebenfaden, bis es sie gibt, und
    reicht dann einen Auftrag über die Warteschlange in den Hauptfaden
    (``QMetaObject.invokeMethod``). Von dort sieht ein Zeitgeber nach: Steht die
    Meldung, wird ihr Text gelesen und sie mit einem Klick auf *Schließen*
    samt Probe geschlossen — nie *Website öffnen*. Entsteht stattdessen ein
    Hauptfenster, hat das Tor nicht gehalten; das steht im Protokoll, und der
    Lauf endet.

    Ins Protokoll: ``messages`` (Text und Knöpfe), ``modals``/``raw_windows``/
    ``windows`` aus der Wache, der Klick in ``steps`` (Phase ``start``) und in
    ``result.metrics`` der Ausgang von ``main`` (``exit_code``), ob ein
    Hauptfenster entstand (``main_window``) und ob die Meldung erschien
    (``message_shown``). Geurteilt wird bei D0-U.
    """

    def __init__(self, data: dict[str, Any], persist: Callable[[], None]) -> None:
        from tools.function_capture import ModalWatch

        self.data = data
        self.persist = persist
        self.began = time.perf_counter()
        self.ports = QtPorts(None, self.began)
        self.walker = Walk(self.ports, data["steps"], self.began)
        self.walker.phase = "start"
        self.watch = ModalWatch(self.began)
        self.seen: dict[str, Any] = {"message": False, "main_window": False, "closed": False}
        self.deadline = time.monotonic() + START_WAIT_S

    def run(self, argv: Sequence[str] = ("solidon",)) -> int:
        """Ruft ``main`` und gibt seinen Ausgang zurück; das Protokoll steht danach."""
        import threading

        from PySide6.QtCore import QMetaObject, QObject, Qt, QTimer, Slot
        from PySide6.QtWidgets import QApplication

        from app.ui import app as start

        flow = self

        class Watch(QObject):
            """Lebt im Hauptfaden, bevor es eine ``QApplication`` gibt."""

            timer: Any = None

            @Slot()
            def begin(self) -> None:
                self.timer = QTimer(self)
                self.timer.timeout.connect(flow.look)
                self.timer.start(50)

        watch = Watch()
        stop = threading.Event()

        def hand_over() -> None:
            while not stop.is_set() and time.monotonic() < flow.deadline:
                if QApplication.instance() is not None:
                    QMetaObject.invokeMethod(watch, "begin", Qt.ConnectionType.QueuedConnection)
                    return
                time.sleep(0.01)

        helper = threading.Thread(target=hand_over, name="startfall", daemon=True)
        helper.start()
        try:
            code = int(start.main(list(argv)))
        finally:
            stop.set()
            helper.join(timeout=5)
            if watch.timer is not None:
                watch.timer.stop()
        self.watch.poll()
        self.data["modals"] = self.watch.modal_entries()
        self.data["raw_windows"] = self.watch.raw_entries()
        self.data["windows"] = list(self.watch.windows)
        self.data["result"] = {
            "metrics": {
                "exit_code": code,
                "main_window": bool(self.seen["main_window"]),
                "message_shown": bool(self.seen["message"]),
            }
        }
        if not self.seen["message"]:
            unmeasured(self.data, "messages", "das Starttor zeigte keine Meldung")
        self.persist()
        return code

    def look(self) -> None:
        """Ein Takt im Hauptfaden: Hauptfenster? Meldung? Dann lesen und schließen."""
        from PySide6.QtWidgets import QAbstractButton, QApplication, QMessageBox

        from app.ui.main_window import MainWindow
        from tools.function_capture import name_of, visible_texts

        self.watch.poll()
        if any(isinstance(top, MainWindow) for top in QApplication.topLevelWidgets()):
            if not self.seen["main_window"]:
                self.data["errors"].append("Die Anwendung startete trotz abgelaufener Demo")
                self.persist()
            self.seen["main_window"] = True
            QApplication.exit(2)
            return
        if time.monotonic() > self.deadline:
            self.data["errors"].append(f"Nach {START_WAIT_S:.0f} s weder Meldung noch Fenster")
            self.persist()
            QApplication.exit(3)
            return
        box = QApplication.activeModalWidget()
        if box is None or self.seen["closed"]:
            return
        self.seen["message"] = True
        buttons = [
            button
            for button in box.findChildren(QAbstractButton)
            if button.isVisible() and name_of(button)
        ]
        closing = (
            box.button(QMessageBox.StandardButton.Close) if isinstance(box, QMessageBox) else None
        )
        text = box.text() if isinstance(box, QMessageBox) else " ".join(visible_texts(box))
        entry = {
            "text": str(text),
            "actions": [
                {"label": name_of(button), "target": "", "clicked": False, "effect": None}
                for button in buttons
            ],
        }
        self.data["messages"] = [entry]
        self.seen["closed"] = True
        self.persist()
        if closing is None:
            self.data["errors"].append("Die Meldung hat keinen Knopf Schließen")
            self.ports.keys("Escape")
            return
        label = name_of(closing)
        for action in entry["actions"]:
            action["clicked"] = action["label"] == label
        self.persist()
        if not click_button(self.ports, self.walker, closing, label):
            for action in entry["actions"]:
                action["clicked"] = False
            self.data["findings"].append(
                {
                    "phase": "start",
                    "kind": COVERED,
                    "target": label,
                    "detail": str(self.data["steps"][-1].get("detail", "")),
                }
            )
            self.persist()
            self.ports.keys("Escape")


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
        for row in self.rows:
            path = surfaces / f"{safe_name(str(row.get('id', '')))}.json"
            if path.exists():
                done.append(str(row.get("id")))
                continue
            size = [self.window.width(), self.window.height()]
            protocol = empty_protocol(row, self.variant.protocol(placed, size), self.version)
            flow = FunctionFlow(
                self.application,
                self.window,
                self.folder,
                protocol,
                lambda: None,
                row,
                self.variant,
                self.scenes,
                out=self.folder.parent.parent,
            )
            if flow.reset():
                flow.phase_surface()
            write_json(path, protocol)
            done.append(str(row.get("id")))
            self.bench["surfaces_done"] = done
            self.persist()
        self.bench["surfaces_done"] = done
        self.persist()


def safe_name(text: str) -> str:
    """Ein Dateiname aus einer Kennung: ``Datei/Speichern unter …`` → ``Datei_Speichern_unter``."""
    cleaned = "".join(
        character if character.isalnum() or character in "._-" else "_" for character in text
    )
    return cleaned.strip("_")[:120] or "zeile"
