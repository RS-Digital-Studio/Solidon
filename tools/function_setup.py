"""Was ein Funktionsfall vorbereitet, bevor die geprüfte Handlung beginnt (D0-P, RM-737).

Die Variante eines Falls (:class:`Variant`: Satz, Sprache, Thema, Einheit,
Lizenz, Vorbedingungen, Schirm, Fenstergröße, Skalierung, Bewegung, Phasen) und
was aus ihr folgt: das Nutzerprofil (:func:`write_profile`), der Lizenzzustand
und die äußeren Vorbedingungen über dieselben Nahtstellen wie die Suite
(:func:`apply_licence`, :func:`apply_preconditions`) — nur im Kindprozess, ohne
private Schlüssel —, der Platz des Fensters (:func:`place_window`), die eigene
Kopie jeder Startszene im Fallordner (:func:`case_scene`, :func:`fresh_case`)
der Weg einer Zeile (:func:`walk_target`, :func:`route_of`) und was die
Startszene darüber hinaus verlangt (:func:`scene_setup`): ihre Vorbedingungen,
eigene Bausteine im Nutzerordner (:func:`install_own_parts`) und die Klicks vor
der Zeile — Einfügemarke, Export, *Automatisch teilen* (:func:`preparation_route`).

Vorbereitung ist nicht die geprüfte Handlung (Konzept §5): Sie darf schreiben,
was der Kunde nie sieht. Zustandsnamen und Spezifikation kommen von D0-L
(``tools/function_list.py``); übersetzt wird nichts.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final

from app.ui.main_window import START_SIZE
from tools.file_acceptance import MATERIAL, PRINTER
from tools.function_checks import (
    LAPTOP_SIZE,
    SCALES,
)
from tools.function_list import (
    LICENCE_STATES,
    STARTUP_LICENCE,
    licence_states,
)
from tools.function_list import PRECONDITIONS as SPEC_PRECONDITIONS
from tools.function_walk import with_modifier


def spec_licence(word: str) -> str:
    """Der Lizenzzustand aus der Zeilenspezifikation, wenn die Fassung ihn erreicht.

    Spezifikation und Zustandsnamen gehören D0-L (``function_list.PRECONDITIONS``,
    ``LICENCE_STATES``, ``licence_states()``) — der Prüfstand übersetzt nichts.
    Ein Zustand, den die ausgelieferte Fassung nicht erreicht (``expired`` ohne
    ``store.TRIAL_FROM``), ist ein Fehler, kein anderer Lauf (Regel 21); ``over``
    ist der Startfall, kein Lauf je Funktion.
    """
    if word in licence_states():
        return word
    raise ValueError(
        f"Lizenzzustand {word!r} hat keinen Lauf in der ausgelieferten Fassung"
        f" — erreichbar sind {licence_states()}, {STARTUP_LICENCE!r} ist der Startfall"
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
    Auslieferung (``function_list.licence_states``) und wird deshalb zur
    Inventarzeit gelesen, nicht beim Import. ``over`` ist kein Lauf: Eine
    abgelaufene Demo startet nicht, das misst der Startfall der D12-Zeile.
    """
    return {
        **FIXED_VARIANT_SETS,
        "lizenz": tuple({"set": "lizenz", "licence": state} for state in licence_states()),
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


@dataclass(frozen=True, slots=True)
class SceneSetup:
    """Was eine Startszene über ihre Datei hinaus verlangt (``function_scenes.Scene``)."""

    key: str = ""
    preconditions: Mapping[str, str] = field(default_factory=dict)
    """Gilt für jeden Fall, der in dieser Szene beginnt — ohne Gegenlauf: Ohne sie
    steht der Befund nicht da, um den es geht."""
    own_parts: tuple[Path, ...] = ()
    insert_before: int = 0
    cause: Mapping[str, str] = field(default_factory=dict)


def scene_setup(key: str) -> SceneSetup:
    """Die Angaben der Startszene ``key`` aus dem Szenenkatalog; leer ohne Szene."""
    from tools.function_scenes import DATA, load_scenes

    scene = load_scenes().get(key)
    if scene is None:
        return SceneSetup(key)
    return SceneSetup(
        key=key,
        preconditions=dict(scene.preconditions),
        own_parts=tuple(DATA / relative for relative in scene.own_parts),
        insert_before=scene.insert_before,
        cause=dict(scene.cause),
    )


def install_own_parts(setup: SceneSetup) -> list[Path]:
    """Legt die eigenen Bausteine der Szene in den Nutzerordner des Falls.

    Vor dem Start der Anwendung, die sie dort lädt — wie ein Rezept, das der
    Kunde früher gespeichert hat. Der Dateiname ist der Name des Rezepts.
    """
    import json

    from app.core.knowledge.parts import recipe

    if not setup.own_parts:
        return []
    folder = recipe.recipes_dir()
    folder.mkdir(parents=True, exist_ok=True)
    placed: list[Path] = []
    for source in setup.own_parts:
        name = str(json.loads(source.read_text(encoding="utf-8"))["name"])
        target = folder / f"{name}.json"
        target.write_bytes(source.read_bytes())
        placed.append(target)
    return placed


def preparation_route(setup: SceneSetup, folder: Path) -> list[dict[str, str]]:
    """Die Klicks, Eingaben und Tasten, die nach dem Öffnen den Zustand der Szene herstellen.

    Einträge mit ``target`` (und ``button``) sind Klicks wie im Weg einer Zeile,
    ``type`` tippt ins Feld mit dem Fokus, ``key`` drückt eine Taste. Die
    Einfügemarke setzt das Kontextmenü des Verlaufs, *Automatisch teilen* der Befehl
    am gewählten Körper, der Export der Befehl samt Dateidialog: ein Pfad im
    Fallordner mit der Endung des Formats.
    """
    from app.core.export.writer import FORMAT_SUFFIX

    route: list[dict[str, str]] = []
    if setup.insert_before:
        route += [
            {"target": f"history.row:{setup.insert_before}", "button": "right"},
            {"target": "history:insert"},
        ]
    kind = setup.cause.get("kind")
    if kind == "auto_split":
        route += [
            {"target": f"tree.row:{setup.cause['object']}"},
            {"target": "command:edit.auto_split"},
        ]
    elif kind == "export":
        suffix = FORMAT_SUFFIX[setup.cause["format"]]  # type: ignore[index]
        route += [
            {"target": "command:file.export"},
            {"key": "Ctrl+A"},
            {"type": str(folder / f"szene{suffix}")},
            {"key": "Return"},
        ]
    return route


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
    """Der Freischaltzustand zu einem Lauf (``function_list.LICENCE_STATES``) oder ``over``.

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
                f" (store.TRIAL_FROM) — erreichbar sind {licence_states()}"
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
            elif name == "opencascade":
                from app.core.brep import kernel

                # Dieselbe Nahtstelle wie die Suite (``tests/test_threads.py``):
                # Exakte Schritte sagen ab und bieten *Zusätzliche Programme* an.
                kernel.available = lambda: False
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
    if name == "opencascade":
        from app.core.brep import kernel

        return kernel.available()
    return True


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
    if chosen is None and wanted:
        # Nie still ein anderer Schirm (Review L14, Regel 21): Der Lauf mäße dann
        # Größe und Skalierung eines Schirms, den niemand verlangt hat.
        named = ", ".join(f"{number}: {screen.name()}" for number, screen in enumerate(screens))
        raise ValueError(f"--screen {wanted!r} trifft keinen Schirm — vorhanden: {named}")
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


#: Die Szene, die jede Zeile ohne eigene Szene bekommt (Plan D0, Abschnitt 2.5).
EMPTY_SCENE: Final = "leer"

#: Die Szene ohne Projekt: Der Fall bleibt auf dem Startbildschirm (``start.*``).
START_SCREEN: Final = "startbildschirm"

#: Die Szene, in die der Projektwechsel geht (Prüfpunkt 16).
SECOND_SCENE: Final = "zweites_projekt"

#: Die Szenen, deren Rechnung lang genug für *Abbrechen* ist (Prüfpunkt 14).
SLOW_SCENES: Final[tuple[str, ...]] = ("langsam_2s", "langsam_10s")


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


def fresh_case(folder: Path) -> list[str]:
    """Räumt weg, was ein früherer Lauf dieses Falls liegen ließ, und nennt es.

    Ein Fall, der nach einer Sicherung starb, ließ seine Szenenkopien samt
    ``<kopie>.p3d.autosave`` und im Profil die Sicherung eines namenlosen
    Projekts zurück; mit ``--again`` stand der neue Lauf dann an der
    Wiederherstellungsfrage (Review N2). Weg sind danach die Kopien — die
    nächste ist frisch (:func:`case_scene`) — und jede Sicherung im Profil;
    Einstellungen und Protokolle bleiben.
    """
    import shutil

    from app.core.scene.project import AUTOSAVE_SUFFIX

    cleared: list[str] = []
    copies = folder / "scenes"
    if copies.is_dir():
        cleared.extend(path.relative_to(folder).as_posix() for path in sorted(copies.rglob("*")))
        shutil.rmtree(copies)
    profile = folder / "profile"
    for leftover in sorted(profile.rglob(f"*{AUTOSAVE_SUFFIX}")) if profile.is_dir() else ():
        leftover.unlink()
        cleared.append(leftover.relative_to(folder).as_posix())
    return cleared


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
