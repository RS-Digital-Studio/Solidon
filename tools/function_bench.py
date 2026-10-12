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

Was gemessen wird, steht im Messprotokoll ``cases/<nr>/function.json``
(Plan D0, Abschnitt 2.7), das ``tools/function_report.py`` liest. Welches Feld welchen
Prüfpunkt trägt, sagt :data:`POINT_FIELDS`.
"""

from __future__ import annotations

import ast
import hashlib
import json
import time
import traceback
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final, Protocol

from tools.file_acceptance import MATERIAL, PRINTER

# --- Wege und Funde ---------------------------------------------------------------

#: Warum ein Klick fällt (``guide_targets.next_click``): das Ziel selbst …
TARGET_REASON: Final = "ziel"

#: … oder ein Wegklick davor, der etwas aufdeckt. Jeder zählt (E1, Prüfpunkt 2).
WAY_REASONS: Final[frozenset[str]] = frozenset(
    {"reiter", "klappe", "menue", "untermenue", "aufklappen", "rollen"}
)

#: Der Fund, wenn an der Stelle des Klicks etwas anderes liegt als das Ziel.
COVERED: Final = "verdeckt"

#: Der Fund, wenn ``next_click`` keinen Weg mehr nennt (Prüfpunkt 1, schwer).
NOT_FOUND: Final = "nicht auffindbar"

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

#: Ruhe nach dem Tippen einer Suchprobe, bevor die Treffer gelesen werden: Die
#: Suche filtert bei jedem Zeichen, und die Liste baut sich danach in einer
#: Ereignisrunde; eine Sekunde trägt beides auch unter Fremdlast.
SEARCH_SETTLE_MS: Final = 1000

#: Wie lange eine ganze Phase eines Funktionsfalls dauern darf (Sekunden).
PHASE_TIMEOUT_S: Final = 900.0

#: Die Aufrufe, die eine Bedienung umgehen (Konzept §12 „Die Abkürzungen der
#: Bildwerkzeuge“, Bauplan D0 B5). Ein Name mit ``*`` meint den Anfang.
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

#: Die Lizenzzustände eines Falls (Prüfpunkt 18): laufende und abgelaufene Demo,
#: laufender und abgelaufener Testlauf, gekauft.
LICENCE_STATES: Final[tuple[str, ...]] = (
    "demo",
    "demo_abgelaufen",
    "test",
    "abgelaufen",
    "gekauft",
)

#: Äußere Vorbedingungen und ihre Zustände (Plan D0, Abschnitt 2.4); die erste ist die Vorgabe.
PRECONDITIONS: Final[dict[str, tuple[str, ...]]] = {
    "ki": ("vorhanden", "fehlt"),
    "comfyui": ("vorhanden", "fehlt"),
    "slicer": ("vorhanden", "fehlt"),
    "printer": ("filament", "resin"),
}

#: Drucker und Material je Druckart — der feste Rahmen des Dateiaudits für
#: Filament (``file_acceptance.PRINTER``), das allgemeine Harzprofil für Resin
#: (``knowledge/data/printers.toml``).
PRINTERS: Final[dict[str, tuple[str, str]]] = {
    "filament": (PRINTER, MATERIAL),
    "resin": ("generic-resin-130", "resin"),
}

#: Wie lange eine laufende Demo oder ein laufender Testlauf im Prüfstand noch dauert.
RUNNING_DAYS: Final = 14

#: Die Fenstergrößen aus Z6: Startgröße und Laptop mit Taskleiste.
WINDOW_SIZES: Final[tuple[str, ...]] = ("1280x820", "1366x728")

#: Die Skalierungen aus Z6.
SCALES: Final[tuple[float, ...]] = (1.0, 1.5, 2.0)


#: Die Phasen je Variantensatz, in ihrer Folge (``FunctionFlow.phase_<name>``).
#: Jede beginnt an der Startszene; ``sprachen`` hat eine eigene Klasse
#: (:class:`LanguageFlow`) und deshalb keine Phase hier.
PHASES: Final[dict[str, tuple[str, ...]]] = {
    "basis": (
        "search",
        "escape",
        "main",
        "edit_later",
        "fault",
        "matrix",
        "cancel",
        "halt",
        "switch",
        "hover",
        "drag",
        "promise",
    ),
    "lizenz": ("licence",),
    "zoll": ("surface",),
    "skalierung": ("surface",),
    "dunkel": ("surface",),
    "sprachen": (),
}


@dataclass(frozen=True, slots=True)
class Variant:
    """Unter welchen Bedingungen ein Fall läuft (Protokollfeld ``variant``).

    ``set`` sagt, welche Phasen laufen: ``basis`` den ganzen Weg, ``lizenz`` nur
    Angebot und Sperre, ``zoll``, ``skalierung`` und ``dunkel`` den Weg bis zur
    offenen Fläche mit ihren Aufnahmen (:data:`VARIANT_SETS`, :data:`PHASES`).
    ``phases`` beschränkt auf einzelne davon — die Nachprüfung einer Zeile nach
    einem Fix fährt nur, was der Fix berührt (Konzept §7).
    """

    set: str = "basis"
    language: str = "de"
    theme: str = "light"
    unit: str = "mm"
    licence: str = "gekauft"
    preconditions: Mapping[str, str] = field(default_factory=dict)
    screen: str = ""
    scale: float = 1.0
    window_size: str = ""
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

    def check(self) -> None:
        """Nur Zustände, die der Prüfstand herstellen kann."""
        if self.set not in PHASES:
            raise ValueError(f"Variantensatz {self.set!r} ist keiner aus {tuple(PHASES)}")
        strange = sorted(set(self.phases) - set(PHASES[self.set]))
        if strange:
            raise ValueError(f"Phasen {strange} gibt es im Satz {self.set!r} nicht")
        if self.licence not in LICENCE_STATES:
            raise ValueError(f"Lizenzzustand {self.licence!r} ist keiner aus {LICENCE_STATES}")
        for name, state in self.preconditions.items():
            allowed = PRECONDITIONS.get(name)
            if allowed is None or state not in allowed:
                raise ValueError(f"Vorbedingung {name}={state!r} gibt es nicht")
        if self.unit not in ("mm", "in"):
            raise ValueError(f"Anzeigeeinheit {self.unit!r} gibt es nicht")
        if self.theme not in ("light", "dark"):
            raise ValueError(f"Thema {self.theme!r} gibt es nicht")
        if self.window_size and parse_size(self.window_size) is None:
            raise ValueError(f"Fenstergröße {self.window_size!r} ist nicht BREITExHÖHE")
        if not self.scale > 0:
            raise ValueError(f"Skalierung {self.scale} ist nicht positiv")

    @property
    def printing(self) -> str:
        return self.preconditions.get("printer", PRECONDITIONS["printer"][0])


#: Die Variantensätze der Kommandozeile (``--variants``), je Zeile ausgefaltet.
#: ``sprachen`` ist kein Satz je Zeile: Je Sprache und Paket geht ein Prozess die
#: Flächen aller Zeilen ab (:class:`LanguageFlow`).
VARIANT_SETS: Final[dict[str, tuple[dict[str, Any], ...]]] = {
    "basis": ({"set": "basis"},),
    "zoll": ({"set": "zoll", "unit": "in"},),
    "lizenz": tuple(
        {"set": "lizenz", "licence": state}
        for state in ("demo_abgelaufen", "abgelaufen", "gekauft")
    ),
    "skalierung": (
        *({"set": "skalierung", "window_size": size} for size in WINDOW_SIZES),
        *({"set": "skalierung", "scale": scale} for scale in SCALES if scale != 1.0),
    ),
    "dunkel": ({"set": "dunkel", "theme": "dark"},),
    "sprachen": (),
}


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
    """Der Freischaltzustand eines Lizenzzustands, ohne private Schlüssel.

    Gekauft heißt Kaufcode samt Gerätezertifikat, gebaut wie in
    ``tests/helpers.set_test_license`` — die Oberfläche graut nur aus, die Hürde
    liegt im Datenpfad (``activation``), und genau das Ausgrauen ist geprüft
    (Plan D0, Abschnitt 5.1).
    """
    from app.core import activation
    from app.core.activation import key

    if state == "gekauft":
        licence = key.Licence(
            major=key.current_major(),
            purchased_on=today - timedelta(days=30),
            order="PRUEFSTAND-1",
            holder="pruefstand@beispiel.de",
        )
        certificate = activation.ActivationCertificate(
            licence_digest="pruefstand",
            device_public=b"\x01" * 32,
            device_name="Prüfstand",
            activation_id="pruefstand",
            issued_on=today - timedelta(days=29),
        )
        return activation.Activation(licence=licence, certificate=certificate)
    if state == "demo":
        return activation.Activation(
            days_left=RUNNING_DAYS, deadline=today + timedelta(days=RUNNING_DAYS)
        )
    if state == "demo_abgelaufen":
        return activation.Activation(days_left=0, deadline=today - timedelta(days=1))
    if state == "test":
        return activation.Activation(days_left=RUNNING_DAYS)
    if state == "abgelaufen":
        return activation.Activation(days_left=0)
    raise ValueError(f"Lizenzzustand {state!r} ist keiner aus {LICENCE_STATES}")


def apply_licence(state: str, today: date | None = None) -> Any:
    """Setzt den Lizenzzustand über die Nahtstelle der Suite (``activation._cached``).

    Nur im Kindprozess eines Falls. Testlauf und Demo brauchen dazu die Frist
    der Auslieferung: ein Testlauf ist nur einer, wenn die Fassung einen anbietet
    (``store.TRIAL_FROM``), eine Demo nur mit Stichtag (``store.DEMO_UNTIL``) —
    dieselben zwei Zeilen wie ``tests/conftest._the_calendar_stays_out_of_it``.
    """
    from app.core import activation
    from app.core.activation import store

    day = today or date.today()
    cached = licence_activation(state, day)
    if state in ("test", "abgelaufen", "gekauft"):
        store.DEMO_UNTIL = None
        store.TRIAL_FROM = store.DEMO_FROM
    else:
        store.DEMO_UNTIL = cached.deadline
    activation._cached = cached
    return cached


def apply_preconditions(preconditions: Mapping[str, str]) -> dict[str, str]:
    """Setzt „fehlt“ über die Nahtstellen der Suite; „vorhanden“ ist die Maschine selbst.

    Gibt zurück, was wirklich gilt: ``vorhanden`` verlangt, aber auf dieser
    Maschine nicht da, steht als ``fehlt (Maschine)`` im Protokoll — ein Fall
    misst dann nicht, was er verspricht, und sagt es.
    """
    from app.core import discover
    from app.core.backends import llm, mesh

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
                mesh.reachable = lambda url, seconds=0.0: False  # type: ignore[assignment]
            applied[name] = "fehlt"
            continue
        applied[name] = state if _present(name) else "fehlt (Maschine)"
    return applied


def _present(name: str) -> bool:
    """Ob eine Vorbedingung auf dieser Maschine wirklich erfüllt ist."""
    from app.core import tools
    from app.core.backends import llm, mesh

    if name == "slicer":
        return bool(tools.slicer_programs())
    if name == "ki":
        return any(backend.available() for backend in llm.backends())
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
    selection: Mapping[str, Any] | None = None,
    camera: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Der Abdruck einer Szene (Konzept §4 „Szenenabdruck“, Plan D0, Abschnitt 2.7).

    Ops mit ihren Parametern, Projektparameter und Passungen über die
    Schreibweise der Projektdatei (``scene.serialise``), je Körper sein Netz
    (``file_acceptance.body_digest``). Auswahl und Kamera stehen getrennt: Nach
    einem Rückgängig ist eine andere Auswahl ein Vermerk, kein Fehler (Prüfpunkt 5).
    """
    from app.core.scene.serialise import fit_to_data, operation_to_data, parameter_to_data
    from tools.file_acceptance import body_digest

    ops = [operation_to_data(entry) for entry in document.ops]
    parameters = {
        str(name): parameter_to_data(parameter) for name, parameter in document.parameters.items()
    }
    fits = [fit_to_data(fit) for fit in document.fits]
    bodies = (
        {str(key): body_digest(entry.mesh) for key, entry in scene.objects.items()}
        if scene is not None
        else {}
    )
    return {
        "history_length": len(document.ops),
        "ops": _digest(ops),
        "op_names": [entry.op for entry in document.ops],
        "parameters": _digest(parameters),
        "fits": _digest(fits),
        "bodies": bodies,
        "selection": dict(selection or {}),
        "camera": [
            [round(float(value), 4) for value in part] if isinstance(part, (list, tuple)) else part
            for part in (camera or ())
        ],
    }


#: Die Teile eines Abdrucks, die zum Dokument gehören; Auswahl und Kamera nicht.
DOCUMENT_PARTS: Final[tuple[str, ...]] = ("history_length", "ops", "parameters", "fits", "bodies")


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

#: Welche Felder des Protokolls welchen Prüfpunkt tragen (Plan D0, Abschnitt 2.7, 3.1).
#: Jeder der 19 Prüfpunkte hat mindestens eines; was Stufe B dazu urteilt, steht
#: in :data:`STAGE_B`. ``tests/test_function_bench.py`` hält beides gegen das
#: Gerüst (:func:`empty_protocol`).
POINT_FIELDS: Final[dict[int, tuple[str, ...]]] = {
    1: ("place", "search"),
    2: ("steps",),
    3: ("preview",),
    4: ("result", "cli"),
    5: ("states",),
    6: ("timing",),
    7: ("fault", "messages"),
    8: ("texts", "fields", "manual_opened"),
    9: ("texts", "units"),
    10: ("tab_chain", "names", "focus_return"),
    11: ("promise",),
    12: ("edit_later",),
    13: ("matrix",),
    14: ("cancel",),
    15: ("halt", "insertion"),
    16: ("switch",),
    17: ("place",),
    18: ("licence_runs",),
    19: (
        "layout",
        "fonts",
        "state_images",
        "contrast",
        "icons",
        "animations",
        "scrollbars",
        "frames",
        "modals",
        "raw_windows",
        "hover_labels",
        "empty_states",
    ),
}

#: Was Stufe B an einem Prüfpunkt am Bild urteilt (Konzept §5 „Stufe B“). Stufe A
#: misst trotzdem; der Vermerk sagt, dass das Urteil dort nicht endet.
STAGE_B: Final[dict[int, str]] = {
    1: "Herkunft der Suchproben",
    2: "Weg und Entscheidungen mit Vorwissen",
    7: "Wortlaut der Meldungen (V5)",
    8: "Gesamturteil Verständlichkeit (V4 bis V6)",
    9: "keine Bedeutung allein über Farbe (Regel 18)",
    11: "Inhalt von Handbuchstelle und Website",
    13: "Matrix gegen grenzen.md",
    19: "G9, Z3, Z4, I1 bis I6 und der Vergleich",
}


def empty_protocol(
    row: Mapping[str, Any], case_kind: str, variant: Variant, version: Mapping[str, str]
) -> dict[str, Any]:
    """Das Gerüst eines Messprotokolls: jedes Feld da, ungemessen heißt ``None``.

    ``unmeasured`` nennt je Feld, warum es leer blieb — fehlende ``steps``
    ergeben bei U „nicht gemessen“, nie „gut“ (Plan D0, Abschnitt 3.1, Prüfpunkt 2).
    """
    data: dict[str, Any] = {
        "row": str(row.get("id", "")),
        "kind": case_kind,
        "row_kind": row.get("kind"),
        "package": row.get("package"),
        "spec": dict(row.get("spec") or {}),
        "target": row.get("target"),
        "variant": variant.as_dict(),
        "version": dict(version),
        "scene": None,
        "steps": [],
        "states": {},
        "stage_b": {str(point): text for point, text in STAGE_B.items()},
        "unmeasured": {},
        "images": [],
        "errors": [],
    }
    for names in POINT_FIELDS.values():
        for name in names:
            data.setdefault(name, None)
    data["steps"] = []
    data["states"] = {}
    data["modals"] = []
    data["raw_windows"] = []
    data["messages"] = []
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
        if machine.finished and machine.depth == 0:
            break
        if machine.deadline is not None and clock() > machine.deadline + timeout_s:
            # Der Automat hat seine Frist und eine zweite dazu verpasst — dann
            # tickt er nicht mehr, und diese Schleife ist die letzte Wache.
            machine.stop(error=f"Phase nach {2 * timeout_s:.0f} s nicht fertig")
            return


# --- Der Weg zum Ziel --------------------------------------------------------------------------


class ClickLike(Protocol):
    """Was ``guide_targets.next_click`` zurückgibt (Plan D0, Abschnitt 2.2)."""

    rect: Any
    button: Any
    why: str
    target: Any


class Ports(Protocol):
    """Die Verbindung zur Oberfläche; am Fenster :class:`QtPorts`, im Test nachgestellt."""

    def next_click(self, name: str) -> ClickLike: ...
    def widget_under(self, point: Any) -> Any: ...
    def covers(self, target: Any, hit: Any) -> bool: ...
    def centre(self, rect: Any) -> Any: ...
    def press(self, widget: Any, point: Any, button: str) -> None: ...
    def keys(self, sequence: Any) -> None: ...
    def type_text(self, text: str) -> None: ...
    def describe(self, widget: Any) -> dict[str, Any]: ...
    def zone_of(self, widget: Any) -> str: ...
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
        #: Die Phase, zu der die nächsten Einträge gehören — der Hauptweg heißt
        #: ``weg`` und ``übernehmen``; nur sie zählt U für E1 bis E4.
        self.phase = ""

    def record(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Ein Eintrag in ``steps``, mit Phase und Zeit seit dem Start des Falls."""
        entry = {**entry, "phase": self.phase, "t": self._t()}
        self.steps.append(entry)
        return entry

    def step(self, name: str, button: str = "left") -> Step:
        """Ein Schritt, der bis zum Ziel wächst: jeder Wegklick reiht den nächsten ein."""
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
            machine.insert([Step(f"weg zu {name}", act, settle_ms=SETTLE_MS)])

        return Step(f"weg zu {name}", act, settle_ms=SETTLE_MS)

    def click_once(self, name: str, button: str = "left") -> str:
        """Ein Klick auf dem Weg zu ``name``; gibt seinen Grund zurück."""
        try:
            click = self.ports.next_click(name)
        except LookupError as error:
            self.record({"target": name, "finding": NOT_FOUND, "detail": str(error)})
            raise BenchFinding(NOT_FOUND, name, str(error)) from error
        point = self.ports.centre(click.rect)
        hit = self.ports.widget_under(point)
        record = self.record(
            {
                "target": name,
                "why": click.why,
                "button": button_name(click.button) if click.why != TARGET_REASON else button,
                "rect": self.ports.rect_data(click.rect),
                "point": self.ports.point_data(point),
                "widget_at": self.ports.describe(hit) if hit is not None else None,
                "hit": hit is not None and self.ports.covers(click.target, hit),
                "zone": self.ports.zone_of(hit if hit is not None else click.target),
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
        return str(click.why)

    def _t(self) -> float:
        return round(self.ports.now() - self.began, 4)


def way_clicks(steps: Sequence[Mapping[str, Any]]) -> int:
    """Wie viele Wegklicks ein Weg gekostet hat (``why`` nicht ``ziel``)."""
    return sum(1 for step in steps if step.get("why") in WAY_REASONS)


def place_of(steps: Sequence[Mapping[str, Any]], target: str) -> dict[str, Any] | None:
    """Wo das Ziel einer Zeile steht, aus ihrem ersten Weg (Prüfpunkt 1, 17).

    ``ort`` ist die Art des Fundorts — Karte, Menü, Werkzeugleiste, Kontext —, aus
    der Zone des Zielklicks und der Gründe davor. ``None``, wenn der Weg nicht
    ankam.
    """
    walked: list[Mapping[str, Any]] = []
    for step in steps:
        if step.get("target") != target:
            continue
        walked.append(step)
        if step.get("why") == TARGET_REASON or step.get("finding"):
            break
    if not walked or walked[-1].get("why") != TARGET_REASON or not walked[-1].get("hit"):
        return None
    reasons = [str(step.get("why")) for step in walked]
    zone = str(walked[-1].get("zone") or "")
    if any(step.get("button") == "right" for step in walked):
        where = "kontext"
    elif "menue" in reasons or zone == "menue":
        where = "menue"
    elif zone == "kopf":
        where = "werkzeugleiste"
    else:
        where = "karte" if zone.startswith("karte") else zone
    return {
        "ort": where,
        "zone": zone,
        "why": reasons,
        "way_clicks": way_clicks(walked),
        "widget": walked[-1].get("widget_at"),
    }


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

    def covers(self, target: Any, hit: Any) -> bool:
        if target is None or hit is None:
            return False
        if target is hit:
            return True
        is_ancestor = getattr(target, "isAncestorOf", None)
        return bool(is_ancestor is not None and is_ancestor(hit))

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

    def describe(self, widget: Any) -> dict[str, Any]:
        from app.core.guides import TARGET_PROPERTY

        if widget is None:
            return {}
        mark = widget.property(TARGET_PROPERTY)
        return {
            "class": type(widget).__name__,
            "object_name": widget.objectName(),
            "mark": str(mark) if mark else "",
        }

    def zone_of(self, widget: Any) -> str:
        from app.ui import guide_targets

        if widget is None:
            return ""
        return str(guide_targets.zone_of(self.window, widget))  # type: ignore[attr-defined]

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

#: Die Szene, in die der Projektwechsel geht (Prüfpunkt 16).
SECOND_SCENE: Final = "zweites_projekt"

#: Die Szenen, deren Rechnung lang genug für *Abbrechen* ist (Prüfpunkt 14).
SLOW_SCENES: Final[tuple[str, ...]] = ("langsam_2s", "langsam_10s")

#: Wie lange nach einem Abbruch oder Projektwechsel auf späte Ereignisse gewartet wird.
LATE_WINDOW_S: Final = 3.0

#: Wie lange nach einem Klick auf eine Handlung auf ihre Wirkung gewartet wird.
EFFECT_WINDOW_S: Final = 2.0

#: Das Ziel für den ersten Eintrag unter *Datei → Zuletzt geöffnet* (Prüfpunkt 16).
#: Der Name kommt aus dem Wortschatz (``menubar_name``); der Fall bricht mit
#: „nicht auffindbar“ ab, wenn es ihn nicht gibt, statt den Wechsel zu umgehen.
RECENT_TARGET: Final = "menu:menubar.datei.zuletzt_geoeffnet.1"


def default_apply_target(row: Mapping[str, Any]) -> str | None:
    """Womit eine Zeile übernommen wird, wenn ihre Spezifikation nichts sagt.

    Handlungen des Merkmalfensters und Kantenzeilen mit *Übernehmen* dort,
    Operationen mit dem Hauptknopf ihres Dialogs; ein Fensterbefehl wirkt mit
    seinem Klick selbst.
    """
    target = str(row.get("target") or "")
    if target.startswith(("feature:", "edge:")):
        return "feature.apply"
    if target.startswith(("operation:", "dialog:")):
        return "dialog.accept"
    return None


def route_of(row: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Der Weg einer Zeile: ihre Schritte aus der Spezifikation, sonst ihr Ziel.

    ``route`` nennt, was ``next_click`` allein nicht findet — einen Rechtsklick
    auf eine Baumzeile, dann den Eintrag im Kontextmenü (Plan D0, Abschnitt 2.4).
    """
    spec = row.get("spec") or {}
    route = [
        (str(entry["target"]), str(entry.get("button", "left"))) for entry in spec.get("route", ())
    ]
    target = str(row.get("target") or "")
    if target and (not route or route[-1][0] != target) and not spec.get("route_ends_elsewhere"):
        route.append((target, "left"))
    return route


def body_figures(scene: Any) -> dict[str, Any]:
    """Kennzahlen je Körper: Volumen, Außenmaß, Dreiecke, dicht (Prüfpunkt 4)."""
    from app.core.errors import AppError
    from app.core.geom.mesh import as_mesh_data

    figures: dict[str, Any] = {}
    for key, entry in scene.objects.items():
        try:
            raw = as_mesh_data(entry.mesh).raw
        except AppError as problem:
            figures[str(key)] = {"error": str(problem)}
            continue
        low, high = raw.bounds
        figures[str(key)] = {
            "volume": round(float(raw.volume), 4),
            "extents": [round(float(value), 4) for value in high - low],
            "triangles": len(raw.faces),
            "watertight": bool(raw.is_watertight),
            "features": {str(name): feature.kind for name, feature in entry.features.items()},
        }
    return figures


def cli_arguments(operation: Mapping[str, Any]) -> list[str] | None:
    """Die Werte eines Schritts als Kommandozeile von ``app.cli.main run``.

    Nur Zahlen, Texte und Wahrheitswerte haben dort ein Feld; ein Schritt mit
    anderen Werten (Listen, Bezüge) ist über die Kommandozeile nicht derselbe —
    dann ``None``, und Prüfpunkt 4 vermerkt den Vergleich als nicht prüfbar.
    """
    arguments = [str(operation["op"])]
    inputs = [str(name) for name in operation.get("inputs", ())]
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


class FunctionFlow:
    """Ein Funktionsfall am echten Fenster: Phasen nach der Variante, jede mit Abdruck.

    Jede Phase beginnt an der Startszene (:meth:`reset`) und endet ohne offenes
    Fenster; scheitert eine, steht ihr Grund in ``errors`` oder ``findings``,
    und die nächste läuft trotzdem. Gemessen wird ins Protokoll ``data``,
    geschrieben nach jeder Phase (``persist``) — ein Absturz lässt stehen, was
    schon gemessen war.
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
    ) -> None:
        from tools.function_capture import FrameCounter, Heartbeat, ModalWatch

        self.application = application
        self.window = window
        self.session = window.session
        self.folder = folder
        self.data = data
        self.persist = persist
        self.row = dict(row)
        self.spec: dict[str, Any] = dict(row.get("spec") or {})
        self.variant = variant
        self.scenes = scenes
        self.began = time.perf_counter()
        self.ports = QtPorts(window, self.began)
        self.walker = Walk(self.ports, data["steps"], self.began)
        self.heartbeat = Heartbeat()
        self.frames = FrameCounter()
        self.watch = ModalWatch(self.began)
        self._timers: list[Any] = []
        self.scene_key = str(self.spec.get("start_scene") or row.get("start_scene") or EMPTY_SCENE)

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
            self.data.setdefault("findings", []).append(
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
            self.data.setdefault("closed_by_escape", []).append(
                {"phase": label, "times": machine.unsticks}
            )
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
            self.walker.record({"target": name, "key": str(sequence)})
            self.ports.keys(sequence)

        return Step(f"taste {name}", act, settle_ms=SETTLE_MS)

    def _t(self) -> float:
        return round(time.perf_counter() - self.began, 4)

    def undo_keys(self) -> Any:
        from PySide6.QtGui import QKeySequence

        return QKeySequence(QKeySequence.StandardKey.Undo)

    def redo_keys(self) -> Any:
        """Die Wiederholen-Taste aus ``shortcut_schemes.redo_keys`` — die, die im Menü steht."""
        import sys

        from PySide6.QtGui import QKeySequence

        from app.ui.shortcut_schemes import redo_keys

        return redo_keys(sys.platform, QKeySequence(QKeySequence.StandardKey.Redo))[0]

    def snapshot(self, label: str) -> dict[str, Any]:
        """Der Abdruck jetzt, unter ``states[label]``."""
        result = self.session.last_result
        tree = self.window.object_tree
        printed = scene_print(
            self.session.project.document,
            result.scene if result is not None else None,
            selection={
                "objects": [str(name) for name in tree.selected_objects()],
                "features": [[str(a), str(b)] for a, b in tree.selected_features()],
            },
            camera=self.window.viewport.camera_pose(),
        )
        self.data["states"][label] = printed
        self.persist()
        return printed

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
        self.data["variant"]["placed"] = place_window(self.application, self.window, self.variant)
        for _ in range(20):
            self.pump()
        self.data["frames_wrapped"] = self.frames.wrap(
            getattr(self.window.viewport, "renderer", None)
        )
        self.persist()

    def finish(self) -> None:
        """Was die Wachen gesehen haben, ins Protokoll."""
        self.data["modals"] = list(self.watch.modals)
        self.data["raw_windows"] = list(self.watch.raw_windows)
        self.data["manual_opened"] = self.watch.opened("ManualWindow")
        for timer in self._timers:
            timer.stop()
        self.persist()

    # --- Startszene ---------------------------------------------------------------------

    def reset(self) -> bool:
        """Zurück an die Startszene; die Vorbereitung ist nicht die geprüfte Handlung.

        Beim ersten Mal steht der Startbildschirm da, und die leere Szene beginnt
        mit einem Klick auf *Neues Projekt*. Danach öffnet ``open_path`` die
        Szenendatei (Konzept §5: „Nur die Startszene entsteht über
        ``open_path``“). Was die Phase davor geändert hat, wird verworfen, ohne die
        Speicherfrage zu stellen — sie gehört nicht zu dieser Zeile.
        """
        previous = self.session.last_result
        path = self.scenes / f"{self.scene_key}.p3d"
        on_start = self.window.stack.currentWidget() is self.window.start_screen
        began = time.perf_counter()
        if self.scene_key == EMPTY_SCENE and on_start:
            steps = [self.walker.step("start.new")]
        elif path.is_file():
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
        """Je Feld: hinklicken, alles markieren, tippen; ohne Mitschreiben mit Tab bestätigen."""
        from PySide6.QtGui import QKeySequence

        steps: list[Step] = []
        for target, value in inputs.items():
            steps.append(self.walker.step(target))
            if isinstance(value, bool):
                # Ein Haken wird geklickt, wenn er anders steht; der Weg oben
                # hat ihn schon einmal geklickt, also stimmt er, wenn er jetzt
                # dem Wert entspricht — sonst ein zweiter Klick.
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
            text = (
                typed_number(float(value), self.variant.unit)
                if isinstance(value, (int, float))
                else str(value)
            )
            steps.append(
                self.key_step(QKeySequence(QKeySequence.StandardKey.SelectAll), "alles markieren")
            )
            steps.append(
                Step(
                    f"tippen {target}",
                    lambda machine, target=target, text=text: self._type(target, text),
                    settle_ms=SETTLE_MS,
                )
            )
        return steps

    def _tick_box(self, machine: StepMachine, target: str, value: bool) -> None:
        box = self.widget(target)
        if box is not None and bool(box.isChecked()) != value:
            machine.insert([self.walker.step(target)])

    def _type(self, target: str, text: str) -> None:
        """Tippt ans Fokusfeld; ein Feld, das erst beim Verlassen übernimmt, bekommt Tab."""
        from PySide6.QtWidgets import QAbstractSpinBox, QApplication

        self.walker.record({"target": target, "typed": text})
        self.ports.type_text(text)
        focus = QApplication.focusWidget()
        spin = (
            focus
            if isinstance(focus, QAbstractSpinBox)
            else getattr(focus, "parentWidget", lambda: None)()
        )
        if isinstance(spin, QAbstractSpinBox) and not spin.keyboardTracking():
            self.walker.record({"target": target, "key": "Tab"})
            self.ports.keys("Tab")

    def preview_steps(self) -> list[Step]:
        """Warten, bis die Vorschau steht oder abgesagt ist — abgelesen, nicht erfragt.

        Steht: das Band zeigt die Legende einer neuen Differenz. Abgesagt: der
        Übernehmen-Knopf ist gesperrt und nennt seinen Grund (Tooltip und
        zugängliche Beschreibung). Beides sieht der Kunde.
        """
        shown = {"difference": self.window.viewport.difference}
        apply_name = self.spec.get("apply") or default_apply_target(self.row)

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
            button = self.widget(apply_name) if apply_name else None
            if button is not None and not button.isEnabled():
                return bool(button.accessibleDescription() or button.toolTip())
            return not apply_name and self.idle()

        return [Step("vorschau merken", remember), self.wait_step("vorschau steht", settled)]

    def preview_record(self) -> dict[str, Any]:
        """Band, Differenz und Sperrgrund, wie sie gerade stehen (Prüfpunkt 3, I2)."""
        from app.ui.session import COARSE_PREVIEW_ABOVE
        from tools.file_acceptance import body_digest
        from tools.function_capture import visible_texts

        banner = self.widget("preview.banner")
        difference = self.window.viewport.difference
        apply_name = self.spec.get("apply") or default_apply_target(self.row)
        button = self.widget(apply_name) if apply_name else None
        triangles = (self.data.get("scene") or {}).get("triangles") or 0
        entries = getattr(difference, "entries", {}) if difference is not None else {}
        return {
            "banner_text": visible_texts(banner)
            if banner is not None and banner.isVisible()
            else [],
            "bodies": {
                str(key): body_digest(entry.result.mesh)
                for key, entry in entries.items()
                if entry.result is not None
            },
            "figures": {str(key): fig for key, fig in body_figures(_SceneOf(entries)).items()}
            if entries
            else {},
            "coarse": triangles > COARSE_PREVIEW_ABOVE,
            "refused": bool(button is not None and not button.isEnabled()),
            "reason": (button.accessibleDescription() or button.toolTip())
            if button is not None
            else "",
        }

    # --- Die Phasen ------------------------------------------------------------------------

    def run(self) -> None:
        """Die Phasen der Variante (:data:`PHASES`); jede beginnt an der Startszene."""
        if not self.reset():
            self.finish()
            return
        for name in self.variant.phases or PHASES[self.variant.set]:
            phase: Callable[[], None] = getattr(self, f"phase_{name}")
            self.data["stage"] = name
            try:
                phase()
            except Exception:
                self.data["errors"].append(f"{name}: {traceback.format_exc()}")
            self.persist()
        self.finish()

    def phase_search(self) -> None:
        """Prüfpunkt 1 und I6: jede Suchprobe getippt, der Rang aus ``search_hits``."""
        from PySide6.QtGui import QKeySequence

        from app.ui import guide_targets

        probes = list(self.spec.get("search_probes") or ())
        questions = [{"word": text, "origin": "frage"} for text in self.spec.get("questions") or ()]
        if not probes and not questions:
            unmeasured(self.data, "search", "Spezifikation ohne Suchproben")
            return
        target = str(self.row.get("target") or "")
        found: dict[str, Any] = {}
        for probe in [*probes, *questions]:
            word = str(probe["word"])
            hits: list[str] = []

            def read(machine: StepMachine, hits: list[str] = hits) -> None:
                hits[:] = list(guide_targets.search_hits(self.window))  # type: ignore[attr-defined]

            field_name = str(self.spec.get("search_target") or "search")
            ok = self.run_steps(
                f"suche {word}",
                [
                    self.walker.step(field_name),
                    self.key_step(
                        QKeySequence(QKeySequence.StandardKey.SelectAll), "alles markieren"
                    ),
                    Step(
                        f"tippen {word}",
                        lambda machine, word=word, field_name=field_name: self._type(
                            field_name, word
                        ),
                        settle_ms=SEARCH_SETTLE_MS,
                    ),
                    Step("treffer lesen", read),
                    self.key_step("Escape", "suche leeren"),
                ],
            )
            found[word] = {
                "origin": probe.get("origin"),
                "rank": search_rank(hits, target) if ok else None,
                "hits": hits[:10],
            }
        self.data["search"] = found
        self.reset()

    def phase_escape(self) -> None:
        """Prüfpunkt 5: Weg, Eingaben, Vorschau, dann Escape — der Stand ist der vorher."""
        inputs = self.spec.get("inputs") or {}
        self.snapshot("before")
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
        self.snapshot("escape")
        self.reset()

    def phase_main(self) -> None:
        """Hauptweg: Ort, Weg, Eingaben, Vorschau, Fläche, Übernehmen, Rückgängig, Wiederholen."""
        from PySide6.QtWidgets import QApplication

        from tools import function_capture as capture

        inputs = self.spec.get("inputs") or {}
        target = str(self.row.get("target") or "")
        first_step = len(self.data["steps"])
        focus = QApplication.focusWidget()
        focus_before = capture.focus_record(focus, self.window) if focus is not None else None
        self.snapshot("before")
        surface: dict[str, Any] = {}

        def capture_surface(machine: StepMachine) -> None:
            root = self.surface()
            surface.update(capture.sheet_snapshot(root))
            surface["texts"] = capture.text_entries(root)
            surface["fields"] = capture.field_entries(root)
            surface["messages"] = capture.message_entries(self.window)
            surface["empty_states"] = capture.empty_states(self.window)
            apply_button = self.widget(
                self.spec.get("apply") or default_apply_target(self.row) or ""
            )
            surface["state_images"] = (
                [
                    {
                        "mark": capture.mark_of(apply_button),
                        "states": capture.state_images(apply_button),
                    }
                ]
                if apply_button is not None and apply_button.isVisible()
                else []
            )
            surface["tab_chain"] = capture.tab_chain(root, lambda: self.ports.keys("Tab"))

        ok = self.run_steps(
            "weg",
            [
                *self.path_steps(),
                *self.input_steps(inputs),
                *(self.preview_steps() if inputs else [self.wait_step("ruhe", self.idle)]),
                Step("fläche aufnehmen", capture_surface),
            ],
        )
        self.data["place"] = place_of(self.data["steps"][first_step:], target)
        for name in (
            "texts",
            "fields",
            "layout",
            "fonts",
            "contrast",
            "icons",
            "animations",
            "scrollbars",
        ):
            self.data[name] = surface.get(name)
        self.data["state_images"] = surface.get("state_images")
        self.data["tab_chain"] = surface.get("tab_chain")
        self.data["names"] = [entry.get("name", "") for entry in surface.get("fields") or ()]
        self.data["messages"] = surface.get("messages") or []
        self.data["empty_states"] = surface.get("empty_states")
        self.data["primaries"] = surface.get("primaries")
        if inputs:
            self.data["preview"] = self.preview_record()
            self.snapshot("preview")
        if not ok:
            unmeasured(self.data, "result", "der Weg kam nicht an")
            return
        self.apply_and_measure()
        after = QApplication.focusWidget()
        self.data["focus_return"] = {
            "before": focus_before,
            "after": capture.focus_record(after, self.window) if after is not None else None,
        }
        self.undo_and_redo()

    def apply_and_measure(self) -> None:
        """Übernehmen mit Herzschlag und Zeiten (Prüfpunkt 6), dann Ergebnis und Kommandozeile."""
        from tools import function_capture as capture

        apply_name = self.spec.get("apply") or default_apply_target(self.row)
        previous = self.session.last_result
        timing: dict[str, Any] = {
            "total_s": None,
            "first_feedback_s": None,
            "progress_shown_s": None,
            "cancel_shown_s": None,
            "main_gap_ms": None,
            "budget_s": self.spec.get("budget_s"),
            "budget_ref": self.spec.get("budget_ref"),
            "reference_factor": None,
        }
        status_before = self.window.statusBar().currentMessage()
        moment = {"t0": 0.0}

        def start(machine: StepMachine) -> None:
            moment["t0"] = time.perf_counter()
            self.heartbeat.open(moment["t0"])

        def watched() -> bool:
            from PySide6.QtWidgets import QApplication, QProgressBar

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
        if apply_name:
            steps.append(self.walker.step(apply_name))
        steps.append(self.wait_step("ergebnis", watched))
        ok = self.run_steps("übernehmen", steps)
        timing["main_gap_ms"] = self.heartbeat.close(time.perf_counter())
        if ok:
            timing["total_s"] = round(time.perf_counter() - moment["t0"], 3)
            factor = capture.reference_factor()
            timing["reference_factor"] = round(factor, 3)
        self.data["timing"] = timing
        self.data["after_apply_modal"] = capture.modal_now()
        self.snapshot("applied")
        result = self.session.last_result
        if result is not None:
            self.data["result"] = {"bodies": body_figures(result.scene)}
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
        Werten des übernommenen an, und beide Ergebnisse gehen durch den einen
        Vergleich der Suite (``tests/print_equal``). Der Prozess erbt die
        umgebogenen Nutzerordner dieses Falls.
        """
        import shutil
        import subprocess
        import sys

        from app.core.scene.serialise import operation_to_data

        document = self.session.project.document
        if not document.ops or self.data.get("states", {}).get("applied", {}).get(
            "history_length", 0
        ) <= (self.data.get("states", {}).get("before", {}).get("history_length", 0)):
            return {"compared": False, "reason": "kein neuer Schritt"}
        scene = self.scenes / f"{self.scene_key}.p3d"
        if not scene.is_file():
            return {"compared": False, "reason": "Startszene ohne Datei"}
        arguments = cli_arguments(operation_to_data(document.ops[-1]))
        if arguments is None:
            return {"compared": False, "reason": "Werte ohne Kommandozeilenfeld"}
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
            return {"compared": False, "reason": finished.stderr[-2000:], "arguments": arguments}
        from copy import deepcopy

        from app.core.scene import project as projects
        from app.core.scene.evaluate import evaluate
        from tests import print_equal

        # Beide Dokumente in derselben Güte gerechnet: Das Fenster zeigt den
        # Entwurf, die Datei bekommt die feine Rechnung (``wartezeit.md``).
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
            "compared": True,
            "quality": "fine",
            "arguments": arguments,
            "print_equal": verdict.print_equal,
            "largest_mm": verdict.largest,
            "where": verdict.where,
            "discrete": verdict.discrete[:10],
        }

    def phase_edit_later(self) -> None:
        """Prüfpunkt 12: Doppelklick auf den Schritt im Verlauf öffnet ihn mit seinen Werten."""
        from app.core.scene.serialise import operation_to_data
        from tools import function_capture as capture

        applied = self.data["states"].get("redo") or self.data["states"].get("applied")
        if not applied or applied.get("history_length", 0) == 0:
            unmeasured(self.data, "edit_later", "kein übernommener Schritt")
            return
        number = int(applied["history_length"])
        document = self.session.project.document
        params = (
            dict(operation_to_data(document.ops[-1]).get("params") or {}) if document.ops else {}
        )
        record: dict[str, Any] = {"row": f"history.row:{number}", "params": params}

        def read(machine: StepMachine) -> None:
            record["fields"] = capture.field_entries(self.surface())

        self.run_steps(
            "nachträglich ändern",
            [
                self.walker.step(f"history.row:{number}", "double"),
                Step("fläche lesen", read, settle_ms=SETTLE_MS * 2),
            ],
        )
        numeric = [
            entry["mark"]
            for entry in record.get("fields") or ()
            if str(entry.get("mark", "")).startswith("field:")
            and isinstance(params.get(str(entry["mark"]).partition(":")[2]), (int, float))
            and not isinstance(params.get(str(entry["mark"]).partition(":")[2]), bool)
        ]
        length_before = len(document.ops)
        if numeric:
            from tools.file_acceptance import changed_value

            name = str(numeric[0])
            value = changed_value(float(params[name.partition(":")[2]]))
            previous = self.session.last_result
            self.run_steps(
                "neuer wert",
                [
                    *self.input_steps({name: value}),
                    self.walker.step("dialog.accept"),
                    self.wait_step(
                        "geändert", lambda: self.idle() and self.session.last_result is not previous
                    ),
                ],
            )
            record["typed"] = {name: value}
        record["length_before"] = length_before
        record["length_after"] = len(self.session.project.document.ops)
        self.data["edit_later"] = record
        self.reset()

    def phase_fault(self) -> None:
        """Prüfpunkt 7: der erzwungene Fehlfall, die Meldung und ihre erste Handlung."""
        from tools import function_capture as capture

        fault = self.spec.get("fault_case")
        if not fault:
            unmeasured(self.data, "fault", "Spezifikation ohne Fehlfall")
            return
        record: dict[str, Any] = {"case": dict(fault), "messages": [], "action": None}

        def read(machine: StepMachine) -> None:
            record["messages"] = capture.message_entries(self.window)
            record["preview"] = self.preview_record()

        self.run_steps(
            "fehlfall",
            [
                *[
                    self.walker.step(str(entry["target"]), str(entry.get("button", "left")))
                    for entry in fault.get("route", ())
                ],
                *self.path_steps(),
                *self.input_steps(fault.get("inputs") or {}),
                *(self.preview_steps() if fault.get("inputs") else []),
                Step("meldung lesen", read, settle_ms=SETTLE_MS),
            ],
        )
        actions = [
            action
            for message in record["messages"]
            for action in message.get("actions", ())
            if action.get("enabled") and action.get("target")
        ]
        if actions:
            action = actions[0]
            before = self.snapshot("fault_before_action")
            self.run_steps(
                "handlung der meldung",
                [
                    self.walker.step(str(action["target"])),
                    self.wait_step("ruhe", self.idle, EFFECT_WINDOW_S * 30),
                ],
            )
            after = self.snapshot("fault_after_action")
            record["action"] = {
                **action,
                "clicked": True,
                "effect": {
                    "document_changed": compare_prints(before, after)["same"] is False,
                    "modal": capture.modal_now(),
                    "messages_after": capture.message_entries(self.window),
                },
            }
        self.data["fault"] = record
        self.data["messages"] = [*(self.data.get("messages") or []), *record["messages"]]
        self.reset()

    def phase_matrix(self) -> None:
        """Prüfpunkt 13: sechs Auswahlstufen — angeboten, grau mit Grund oder nicht da."""
        result = self.session.last_result
        objects = list(result.scene.objects.items()) if result is not None else []
        features = [
            (str(key), str(name), feature.kind)
            for key, entry in objects
            for name, feature in entry.features.items()
        ]
        bodies = [str(key) for key, _entry in objects]
        edges = [entry for entry in features if entry[2] == "edge"]
        stages: dict[str, list[tuple[str, str]] | None] = {
            "ohne": [],
            "ein_koerper": [(f"tree.row:{bodies[0]}", "left")] if bodies else None,
            "mehrere_koerper": (
                [(f"tree.row:{bodies[0]}", "left"), (f"tree.row:{bodies[1]}", "ctrl+left")]
                if len(bodies) > 1
                else None
            ),
            "ein_merkmal": [(f"tree.row:{features[0][0]}.{features[0][1]}", "left")]
            if features
            else None,
            "mehrere_merkmale": (
                [
                    (f"tree.row:{features[0][0]}.{features[0][1]}", "left"),
                    (f"tree.row:{features[1][0]}.{features[1][1]}", "ctrl+left"),
                ]
                if len(features) > 1
                else None
            ),
            "kante": [(f"view:{edges[0][0]}.{edges[0][1]}", "left")] if edges else None,
        }
        target = str(self.row.get("target") or "")
        matrix: dict[str, Any] = {}
        for stage, clicks in stages.items():
            if clicks is None:
                matrix[stage] = {
                    "state": "nicht herstellbar",
                    "reason": "die Startszene hat dafür zu wenig",
                }
                continue
            self.reset()
            selection = [self.key_step("Escape", "auswahl leeren")] if not clicks else []
            selection += [self.walker.step(name, button) for name, button in clicks]
            if not self.run_steps(f"matrix {stage} auswahl", selection):
                matrix[stage] = {
                    "state": "nicht herstellbar",
                    "reason": "Auswahl ließ sich nicht klicken",
                }
                continue
            matrix[stage] = self.offer_state(target)
        self.data["matrix"] = matrix
        self.reset()

    def offer_state(self, target: str) -> dict[str, Any]:
        """Wie ein Ziel gerade dasteht: angeboten (und wirksam?), grau mit Grund, fehlt."""
        from app.ui import guide_targets
        from tools import function_capture as capture

        try:
            guide_targets.next_click(self.window, target)  # type: ignore[attr-defined]
        except LookupError as error:
            return {"state": "fehlt", "reason": str(error)}
        widget = self.widget(target)
        if widget is not None and not widget.isEnabled():
            return {
                "state": "grau",
                "reason": widget.accessibleDescription() or widget.toolTip(),
            }
        before = self.snapshot("matrix_before")
        result_before = self.session.last_result
        difference = self.window.viewport.difference
        opened: dict[str, Any] = {}

        def look(machine: StepMachine) -> None:
            opened["modal"] = capture.modal_now()
            opened["surface"] = type(self.surface()).__name__
            opened["preview"] = self.window.viewport.difference is not difference
            opened["result"] = self.session.last_result is not result_before

        self.run_steps(
            f"matrix klick {target}",
            [*self.path_steps(), Step("wirkung", look, settle_ms=int(EFFECT_WINDOW_S * 1000))],
        )
        after = self.snapshot("matrix_after")
        effective = bool(
            opened.get("modal")
            or opened.get("preview")
            or opened.get("result")
            or opened.get("surface") not in (None, type(self.window).__name__)
            or compare_prints(before, after)["same"] is False
        )
        return {"state": "angeboten", "effective": effective, "effect": opened}

    def phase_cancel(self) -> None:
        """Prüfpunkt 14: *Abbrechen* während der Rechnung, danach der Stand von vorher."""
        if self.scene_key not in SLOW_SCENES and not self.spec.get("cancel"):
            unmeasured(self.data, "cancel", "Startszene rechnet nicht lang genug")
            return
        inputs = self.spec.get("inputs") or {}
        apply_name = self.spec.get("apply") or default_apply_target(self.row)
        before = self.snapshot("before_cancel")
        previous = self.session.last_result
        moment = {"t0": 0.0, "shown": None}

        def start(machine: StepMachine) -> None:
            moment["t0"] = time.perf_counter()

        def cancel_visible() -> bool:
            cancel = self.widget("progress.cancel")
            if cancel is not None and cancel.isVisible():
                moment["shown"] = round(time.perf_counter() - moment["t0"], 3)
                return True
            return False

        steps = [*self.path_steps(), *self.input_steps(inputs), Step("uhr", start)]
        if apply_name:
            steps.append(self.walker.step(apply_name))
        steps += [
            self.wait_step("abbrechen sichtbar", cancel_visible, timeout_s=30.0),
            self.walker.step("progress.cancel"),
            self.wait_step("ruhe", lambda: not self.session.busy, timeout_s=60.0),
        ]
        clicked = self.run_steps("abbruch", steps)
        settle_until = time.perf_counter() + LATE_WINDOW_S
        while time.perf_counter() < settle_until:
            self.pump()
        after = self.snapshot("cancelled")
        self.data["cancel"] = {
            "cancel_shown_s": moment["shown"],
            "clicked": clicked,
            "late_result": self.session.last_result is not previous
            and compare_prints(before, after)["same"] is False,
            "compared": compare_prints(before, after),
        }
        self.reset()

    def phase_halt(self) -> None:
        """Prüfpunkt 15: Haltgrund mit Schrittnummer; Einfügen an einer Marke."""
        import re

        from tools import function_capture as capture

        if self.scene_key == "halt":
            texts = capture.message_entries(self.window) + [
                {"carrier": "baum", "text": text}
                for text in capture.visible_texts(self.window.object_tree)
            ]
            self.data["halt"] = {
                "texts": texts,
                "with_number": any(re.search(r"\d", str(entry.get("text", ""))) for entry in texts),
            }
        else:
            unmeasured(self.data, "halt", "Startszene ohne angehaltene Kette")
        if not self.spec.get("insertion"):
            unmeasured(self.data, "insertion", "Spezifikation ohne Einfügen")
            return
        length = len(self.session.project.document.ops)
        if length < 1:
            unmeasured(self.data, "insertion", "kein Schritt, vor dem eingefügt werden könnte")
            return
        previous = self.session.last_result
        record: dict[str, Any] = {}

        def read(machine: StepMachine) -> None:
            record["messages"] = capture.message_entries(self.window)
            record["result"] = self.session.last_result is not previous

        self.run_steps(
            "einfügen",
            [
                self.walker.step(f"history.row:{length}", "right"),
                self.walker.step("menu:history.insert"),
                *self.path_steps(),
                *self.input_steps(self.spec.get("inputs") or {}),
                *(self.preview_steps() if self.spec.get("inputs") else []),
                *(
                    [
                        self.walker.step(
                            str(self.spec.get("apply") or default_apply_target(self.row))
                        )
                    ]
                    if (self.spec.get("apply") or default_apply_target(self.row))
                    else []
                ),
                Step("antwort lesen", read, settle_ms=int(EFFECT_WINDOW_S * 1000)),
            ],
        )
        self.data["insertion"] = record
        self.reset()

    def phase_switch(self) -> None:
        """Prüfpunkt 16: Projektwechsel über *Zuletzt geöffnet* während der Vorschau."""
        from tools import function_capture as capture

        inputs = self.spec.get("inputs") or {}
        if not inputs:
            unmeasured(self.data, "switch", "keine Eingaben, keine Vorschau beim Wechsel")
            return
        second = self.scenes / f"{SECOND_SCENE}.p3d"
        if not second.is_file():
            unmeasured(self.data, "switch", f"Szene {SECOND_SCENE} fehlt")
            return
        project = self.session.project
        modals_before = len(self.watch.modals)
        self.run_steps(
            "wechsel",
            [
                *self.path_steps(),
                *self.input_steps(inputs),
                self.walker.step(RECENT_TARGET),
                self.wait_step(
                    "anderes projekt", lambda: self.session.project is not project and self.idle()
                ),
            ],
        )
        until = time.perf_counter() + LATE_WINDOW_S
        while time.perf_counter() < until:
            self.pump()
        self.data["switch"] = {
            "switched": self.session.project is not project,
            "late_modals": self.watch.modals[modals_before:],
            "late_messages": capture.message_entries(self.window),
        }
        self.snapshot("after_switch")
        self.reset()

    def phase_hover(self) -> None:
        """I1: Name und Maß beim Überfahren je erkannter Art (``view:``), ohne Klick."""
        from tools import function_capture as capture

        result = self.session.last_result
        if result is None:
            return
        seen: dict[str, Any] = {}
        for key, entry in result.scene.objects.items():
            for name, feature in entry.features.items():
                if feature.kind in seen:
                    continue
                target = f"view:{key}.{name}"
                texts: list[str] = []

                def hover(machine: StepMachine, target: str = target) -> None:
                    click = self.ports.next_click(target)
                    point = self.ports.centre(click.rect)
                    hit = self.ports.widget_under(point)
                    if hit is not None:
                        from PySide6.QtTest import QTest

                        QTest.mouseMove(hit, hit.mapFromGlobal(point))

                def read(machine: StepMachine, texts: list[str] = texts) -> None:
                    texts[:] = capture.visible_texts(self.window.viewport)

                self.run_steps(
                    f"überfahren {target}",
                    [Step("hin", hover), Step("lesen", read, settle_ms=SETTLE_MS * 4)],
                )
                seen[feature.kind] = {"target": target, "texts": texts}
        self.data["hover_labels"] = seen

    def phase_drag(self) -> None:
        """Z1: ein Zug am Griff, je Bewegung die Zeit bis zum nächsten Bild."""
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest

        drag = self.spec.get("drag")
        if not drag:
            unmeasured(self.data, "frames", "Spezifikation ohne Zug")
            return
        if not self.data.get("frames_wrapped"):
            unmeasured(self.data, "frames", "kein Renderer, kein Bildzähler")
            return
        target = str(drag["target"])
        moves: list[float] = []

        def pull(machine: StepMachine) -> None:
            click = self.ports.next_click(target)
            point = self.ports.centre(click.rect)
            hit = self.ports.widget_under(point)
            if hit is None or not self.ports.covers(click.target, hit):
                raise BenchFinding(COVERED, target, "der Griff liegt unter etwas anderem")
            local = hit.mapFromGlobal(point)
            QTest.mousePress(hit, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local)
            for step in range(1, int(drag.get("moves", 20)) + 1):
                offset = QPoint(int(drag.get("dx", 4)) * step, int(drag.get("dy", 0)) * step)
                moves.append(time.perf_counter())
                QTest.mouseMove(hit, local + offset)
                self.application.processEvents()
            QTest.mouseRelease(
                hit, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local
            )

        self.run_steps("zug", [*self.path_steps()[:-1], Step("ziehen", pull, settle_ms=SETTLE_MS)])
        from tools.function_capture import reference_factor

        self.data["frames"] = {
            "latencies_ms": self.frames.latencies(moves),
            "reference_factor": round(reference_factor(), 3),
        }
        self.reset()

    def phase_promise(self) -> None:
        """Prüfpunkt 11: Handbuchstelle und Website je Sprache, ohne Fenster."""
        self.data["promise"] = promise_of(self.row)

    def phase_licence(self) -> None:
        """Prüfpunkt 18: Wie das Ziel im Lizenzzustand dasteht, und ob Schreiben gesperrt bleibt."""
        target = str(self.row.get("target") or "")
        before = self.snapshot("before")
        state = self.offer_state(target)
        after = self.snapshot("licence_after")
        state["document_changed"] = compare_prints(before, after)["same"] is False
        self.data["licence_runs"] = {self.variant.licence: state}

    def phase_surface(self) -> None:
        """Zoll, Skalierung, dunkles Thema: Weg bis zur offenen Fläche, dann ihre Aufnahmen."""
        from tools import function_capture as capture

        surface: dict[str, Any] = {}

        def take(machine: StepMachine) -> None:
            root = self.surface()
            surface.update(capture.sheet_snapshot(root))
            surface["texts"] = capture.text_entries(root)
            surface["window"] = [self.window.width(), self.window.height()]

        self.run_steps(
            "fläche", [*self.path_steps(), Step("aufnehmen", take, settle_ms=SETTLE_MS * 2)]
        )
        for name in ("texts", "layout", "fonts", "contrast", "icons", "scrollbars", "primaries"):
            self.data[name] = surface.get(name)
        self.data["accents"] = surface.get("accents")
        self.data["window_size"] = surface.get("window")
        if self.variant.unit == "in":
            self.data["units"] = {
                "unit": "in",
                "mm_texts": [
                    entry["text"]
                    for entry in surface.get("texts") or ()
                    if " mm" in f" {entry['text']}"
                ],
            }


class _SceneOf:
    """Die Einträge einer Vorschaudifferenz als Szene für :func:`body_figures`."""

    def __init__(self, entries: Mapping[Any, Any]) -> None:
        self.objects = {
            key: _Body(entry.result.mesh, getattr(entry.result, "features", {}))
            for key, entry in entries.items()
            if entry.result is not None
        }


@dataclass(slots=True)
class _Body:
    mesh: Any
    features: Mapping[str, Any]


def promise_of(row: Mapping[str, Any]) -> dict[str, Any]:
    """Wo Handbuch und Website eine Operation zusagen (Prüfpunkt 11, Stufe A).

    Die Handbuchstelle aus ``manual.help_for``; je Sprache, ob die
    Funktionsseite der Website ihren Kundentitel nennt (Pfade aus
    ``site_nav.entries_for``, Titel aus dem Katalog). Den Inhalt urteilt Stufe B.
    """
    from app.core import manual
    from app.core.registry.registry import REGISTRY
    from app.i18n import source_text
    from app.i18n.catalog import available_languages
    from tools.file_acceptance import ROOT
    from tools.site_nav import entries_for, site_text

    target = str(row.get("target") or "")
    kind, _separator, name = target.partition(":")
    if kind != "operation" or not REGISTRY.has(name):
        return {"help": None, "website": {}, "reason": "keine Operation"}
    page, anchor = manual.help_for(name)
    title = source_text(REGISTRY.get(name).title)
    website: dict[str, bool] = {}
    for language in available_languages():
        address = entries_for(language)[0][0].lstrip("/")
        path = ROOT / "website" / address
        shown = site_text(title, language)
        website[language] = path.is_file() and shown in path.read_text(encoding="utf-8")
    return {"help": {"page": page, "anchor": anchor}, "title": title, "website": website}


class LanguageFlow:
    """Ein Sprachfall: je Zeile eines Pakets die Fläche öffnen und ihre Texte messen (Prüfpunkt 9).

    Ein Prozess je Sprache und Paket — sechs Sprachen in einem Prozess brechen
    ab (``tools/CLAUDE.md``). Wieder aufnehmbar je Fläche: Was unter
    ``surfaces/<zeile>.json`` steht, wird übersprungen.
    """

    def __init__(
        self,
        application: Any,
        window: Any,
        folder: Path,
        data: dict[str, Any],
        persist: Callable[[], None],
        rows: Sequence[Mapping[str, Any]],
        variant: Variant,
        scenes: Path,
    ) -> None:
        self.application = application
        self.window = window
        self.folder = folder
        self.data = data
        self.persist = persist
        self.rows = rows
        self.variant = variant
        self.scenes = scenes

    def run(self) -> None:
        from tools import function_capture as capture
        from tools.file_acceptance import write_json

        surfaces = self.folder / "surfaces"
        done: list[str] = []
        for row in self.rows:
            safe = safe_name(str(row.get("id", "")))
            path = surfaces / f"{safe}.json"
            if path.exists():
                done.append(str(row.get("id")))
                continue
            record: dict[str, Any] = {
                "row": row.get("id"),
                "language": self.variant.language,
                "steps": [],
            }
            flow = FunctionFlow(
                self.application,
                self.window,
                self.folder,
                {**empty_protocol(row, "language", self.variant, {}), "steps": record["steps"]},
                lambda: None,
                row,
                self.variant,
                self.scenes,
            )
            if flow.reset():
                texts: list[dict[str, Any]] = []
                fields_seen: list[dict[str, Any]] = []

                def take(
                    machine: StepMachine,
                    flow: FunctionFlow = flow,
                    texts: list[dict[str, Any]] = texts,
                    fields_seen: list[dict[str, Any]] = fields_seen,
                ) -> None:
                    root = flow.surface()
                    texts.extend(capture.text_entries(root))
                    fields_seen.extend(capture.field_entries(root))

                flow.run_steps(
                    "fläche", [*flow.path_steps(), Step("texte", take, settle_ms=SETTLE_MS * 2)]
                )
                record["texts"] = texts
                record["fields"] = fields_seen
                record["cut"] = [dict(entry) for entry in capture.overflowing(texts)]
                record["errors"] = flow.data["errors"]
                record["findings"] = flow.data.get("findings", [])
            write_json(path, record)
            done.append(str(row.get("id")))
            self.data["surfaces_done"] = done
            self.persist()
        self.data["surfaces_done"] = done
        self.data["texts"] = {"surfaces": len(done), "folder": "surfaces"}
        self.persist()


def safe_name(text: str) -> str:
    """Ein Dateiname aus einer Kennung: ``Datei/Speichern unter …`` → ``Datei_Speichern_unter``."""
    cleaned = "".join(
        character if character.isalnum() or character in "._-" else "_" for character in text
    )
    return cleaned.strip("_")[:120] or "zeile"
