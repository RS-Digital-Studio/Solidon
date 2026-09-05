"""Jede Ausnahme trägt mindestens einen Handlungsvorschlag (Bauplan §33.1,
§2.7).

Ein Fehler, der mit „fehlgeschlagen" endet, ist unfertig. Die Prüfung läuft die
ganze Hierarchie ab — eine neue Ausnahmeklasse kann also nicht ohne einen
durchrutschen.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import re
from pathlib import Path

import pytest

from app.core import errors
from app.core.errors import (
    AmbiguityError,
    AppError,
    BooleanFailedError,
    GeometryError,
    InternalError,
    UnitUnknownError,
    UserError,
    ValidationError,
)


def _import_every_core_module() -> None:
    """Zieht jedes Modul unter ``app.core`` einmal herein.

    ``AppError.__subclasses__()`` kennt nur die Klassen, deren Modul schon
    importiert ist — und das war beim Sammeln dieser Datei nur ein Teil. Etliche
    Ausnahmen leben in Modulen, die erst der Betrieb lädt (``LicenceKeyError``,
    ``BackendUnavailable`` und die anderen Backend-Fehler): Sie liefen nie durch
    die Prüfung auf einen Handlungsvorschlag, und ob sie *dieser* Lauf zufällig
    doch sah, hing an der Importreihenfolge der übrigen Testdateien — ein
    stiller Erfolg, kein zugesicherter.
    """
    import app.core

    for module in pkgutil.walk_packages(app.core.__path__, "app.core."):
        importlib.import_module(module.name)


def all_error_classes() -> list[type[AppError]]:
    _import_every_core_module()
    found: list[type[AppError]] = []
    seen: set[type[AppError]] = set()
    stack = [AppError]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        found.append(current)
        stack.extend(current.__subclasses__())
    # Erhobene Menge (Ladevorgang): Bleibt ein Modul stumm liegen, schrumpft sie,
    # ohne dass ein Test rot wird — parametrisiert über eine kürzere Liste ist
    # jeder Einzelfall weiter grün. Die Bodenzusicherung fängt genau das. Sie
    # steht bewusst *unter* der wahren Zahl (rund zwei Dutzend), nicht auf ihr:
    # ein unvollständiger Import kollabiert auf die ~15 eager geladenen Klassen,
    # das fängt die 20 — ein legitimes Hinzufügen oder Entfernen einer Klasse
    # (etwa der OpenSCAD-Fehler mit ihrem Backend) bricht sie dagegen nicht. Eine
    # Zahl auf dem Ist-Stand wäre bei jeder Registeränderung rot.
    assert len(found) >= 20, (
        f"zu wenige Fehlerklassen gesammelt ({len(found)}) — Import unvollständig?"
    )
    return found


def core_sources() -> list[Path]:
    return sorted((Path(__file__).resolve().parent.parent / "app" / "core").rglob("*.py"))


@pytest.mark.parametrize("path", core_sources(), ids=lambda entry: entry.name)
def test_no_error_text_carries_a_placeholder_nobody_fills(path: Path) -> None:
    """Ein ``{platzhalter}`` in einem Fehlertext bleibt wörtlich stehen.

    Anderswo ist er richtig: die Oberfläche setzt ihre Texte mit ``.format``
    zusammen, und ``tr("{grams} g").format(...)`` ist der übliche Weg. Einen
    Fehler formatiert dagegen niemand nach — ``show_details`` zeigt
    ``str(error.detail)``, wie es ist, und hängt die ``values`` als eigene
    Zeilen darunter. Wer den Wert in den Satz schreibt, zeigt dem Nutzer
    geschweifte Klammern.

    **Es sei denn, der Übersetzer setzt ihn selbst ein.** ``_("… {n} …", n=4)``
    gibt einen fertigen Satz zurück; die Werte reisen im ``TranslatableText``
    mit und stehen da, sobald jemand ``str()`` darauf ruft. Der Kern geht
    diesen Weg an mehreren Stellen (``colour_ops``, ``paint``,
    ``prepare_ops``), und er ist der **einzige**, auf dem eine Zahl in einen
    übersetzten Satz kommt, ohne dass jede Sprache dieselbe Wortstellung
    braucht.

    Bis zum 04.09.2026 hat diese Prüfung nicht unterschieden und jeden
    Platzhalter gemeldet — auch einen gefüllten. Gemessen an
    ``boolean.py``: Der Kunde las „Von 4 Rechenstufen sind 2 gelaufen", der
    Test meldete „unersetzter Platzhalter". Geprüft wird deshalb, ob der
    Aufruf, in dem der Text steht, für **jeden** seiner Platzhalter ein
    gleichnamiges Schlüsselwort mitgibt; fehlt eines, bleibt es ein Verstoß.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    placeholder = re.compile(r"\{([a-z_]+)\}")
    offenders: list[str] = []

    def unfilled(value: ast.expr, filled: frozenset[str]) -> None:
        """Sammelt jeden Platzhalter, den niemand einsetzt.

        ``filled`` sind die Schlüsselwörter des umgebenden Aufrufs. Ein Text,
        der tiefer in einem eigenen Aufruf steckt, bekommt dessen eigene —
        deshalb steigt die Suche über die Aufrufe hinab statt über
        ``ast.walk`` in einem Zug.
        """
        if isinstance(value, ast.Call):
            own = frozenset(word.arg for word in value.keywords if word.arg)
            for part in value.args:
                unfilled(part, own)
            return
        for text in ast.walk(value):
            if not (isinstance(text, ast.Constant) and isinstance(text.value, str)):
                continue
            open_names = set(placeholder.findall(text.value)) - filled
            if open_names:
                offenders.append(f"{path.name}:{text.lineno} {sorted(open_names)}")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg in ("detail", "title"):
                unfilled(keyword.value, frozenset())

    assert not offenders, "Fehlertexte mit unersetztem Platzhalter:\n" + "\n".join(offenders)


@pytest.mark.parametrize("error_class", all_error_classes(), ids=lambda cls: cls.__name__)
def test_every_error_can_be_raised_bare(error_class: type[AppError]) -> None:
    error = error_class()
    assert str(error.title), "an error needs a title saying what did not work"
    assert error.suggestions, "an error without a suggestion is unfinished"


@pytest.mark.parametrize("error_class", all_error_classes(), ids=lambda cls: cls.__name__)
def test_every_error_serialises(error_class: type[AppError]) -> None:
    data = error_class().as_dict()
    assert data["type"] == error_class.__name__
    assert data["suggestions"]


def test_hierarchy_matches_the_plan() -> None:
    assert issubclass(UserError, AppError)
    assert issubclass(ValidationError, UserError)
    assert issubclass(AmbiguityError, UserError)
    assert issubclass(UnitUnknownError, UserError)
    assert issubclass(GeometryError, AppError)
    assert issubclass(errors.NotManifoldError, GeometryError)
    assert issubclass(BooleanFailedError, GeometryError)
    assert issubclass(errors.OutOfBuildVolume, GeometryError)
    assert issubclass(errors.ExternalToolError, AppError)
    assert issubclass(InternalError, AppError)


def test_a_programming_error_is_not_a_user_error() -> None:
    assert not issubclass(InternalError, UserError)
    assert not issubclass(ValidationError, InternalError)


def test_ambiguity_offers_the_candidates() -> None:
    error = AmbiguityError(candidates=("hole_3", "hole_4"))
    ids = [action.id for action in error.suggestions]
    assert "choose:hole_3" in ids
    assert "choose:hole_4" in ids


def test_unit_question_offers_the_units() -> None:
    error = UnitUnknownError()
    ids = [action.id for action in error.suggestions]
    assert ids[:3] == ["unit:mm", "unit:cm", "unit:in"]


def test_the_unit_buttons_are_named_and_not_abbreviated() -> None:
    """Auf dem Knopf steht der Name der Einheit, nicht ihr Kürzel.

    Neben einer Zahl ist „in" eindeutig; als Antwort auf eine Frage nicht —
    auf Deutsch ist „in" ein Verhältniswort, und der Kunde sollte raten, was
    der mittlere von drei Knöpfen bedeutet. Der Wert bleibt, wie er ist: die
    Kennung trägt ihn (``unit:in``), die Beschriftung nennt ihn.
    """
    error = UnitUnknownError()
    labels = [str(action.label) for action in error.suggestions[:3]]

    assert labels == ["Millimeter (mm)", "Zentimeter (cm)", "Zoll (in)"], (
        f"die Einheiten stehen als Kürzel auf den Knöpfen: {labels}"
    )


def test_boolean_failure_keeps_stages_and_seed() -> None:
    error = BooleanFailedError(attempted=("direct", "welded"), seed=20260727)
    assert error.attempted == ("direct", "welded")
    assert error.as_dict()["values"]["seed"] == 20260727


def test_the_boolean_failure_says_which_stages_really_ran() -> None:
    """„Auf allen Stufen" war beim Arbeiten im Fenster nie wahr (§17.2, §31).

    Dort läuft die kurze Kette — direkt und verschweißt —, die vollen vier
    Stufen laufen beim Export. Der Titel behauptete trotzdem, es sei alles
    versucht, und daneben stand als einziger Rat *Voxelstufe erzwingen*: also
    genau die Stufe, die noch offen war. Zwei Sätze, die sich widersprechen.

    Jetzt sagt der Titel, was gilt — und wo die Voxelstufe wirklich dran war,
    fällt der Rat weg, statt eine Wiederholung anzubieten.

    Beide Titel nennen seit dem 29.08.2026 die Handlung statt des Verfahrens:
    „boolesch" steht in keinem Menü und in keinem Glossareintrag, und „im
    Entwurf" verwies auf eine Qualitätsstufe, die in der Oberfläche keinen
    Namen trägt — im Skizzenmodus zeichnet der Kunde einen Entwurf.
    """
    vorschau = BooleanFailedError(attempted=("direct", "welded"))
    assert "Vorschau" in str(vorschau.title)
    assert errors.USE_VOXEL_STAGE in vorschau.suggestions, "hier ist die Stufe noch offen"

    voll = BooleanFailedError(attempted=("direct", "welded", "jittered", "voxel"))
    assert "keinem Weg" in str(voll.title)
    assert errors.USE_VOXEL_STAGE not in voll.suggestions, (
        "die Voxelstufe war dran — sie zu erzwingen wäre eine Wiederholung"
    )
    assert voll.suggestions, "without a suggestion the error ends in a dead end"


def test_cancelling_is_not_an_error() -> None:
    assert not issubclass(errors.OperationCancelled, AppError)


def test_the_title_follows_the_constraint_not_the_class() -> None:
    """„Ein Wert liegt außerhalb des zulässigen Bereichs." stand über allem.

    Auch über „Diese Datei ist keine STEP-Datei." und über einem fehlenden
    Parameternamen hinter dem @. Die Oberfläche zeichnet den Titel groß und das
    Detail klein: Wer hinsieht, liest zuerst einen Satz, der nicht stimmt, und
    sucht dann bei den Zahlen.

    Von rund 170 Stellen, die diese Ausnahme werfen, betreffen acht eine
    Zahlenspanne. Drei eigene Klassen sind aus genau diesem Missverhältnis
    entstanden; hier steht die Ursache statt des nächsten Einzelfalls.
    """
    from app.core.errors import UserError, ValidationError

    for constraint in ("minimum", "maximum", "range", "positive"):
        error = ValidationError(field="wall", constraint=constraint, detail="Zu dünn.")
        assert "Bereichs" in str(error.title), f"{constraint} ist eine Spanne"

    # ``positive`` steht hier seit dem 24.08.2026 und stand vorher in keiner der
    # beiden Listen -- eine Lücke, keine Entscheidung. Die nach unten offene
    # Spanne ist eine Spanne, und mit sechzehn Aufrufern über
    # ``require_positive`` ist sie die häufigste von allen. Gegenprobe über den
    # echten Weg, nicht über den Konstruktor: Sonst prüft der Test die Liste,
    # die er selbst aufzählt.
    with pytest.raises(ValidationError) as gemessen:
        errors.require_positive("wall", 0.0)
    assert "Bereichs" in str(gemessen.value.title), (
        "require_positive muss den Bereichstitel tragen, nicht den allgemeinen"
    )
    assert gemessen.value.constraint == "positive"

    for constraint in ("empty", "type", "unknown_object", "required", ""):
        error = ValidationError(field="source", constraint=constraint, detail="Keine STEP-Datei.")
        assert str(error.title) == str(UserError.default_title), (
            f"{constraint!r} ist keine Spanne — der Titel darf keine behaupten"
        )

    # Ein selbst gesetzter Titel bleibt unberührt: acht Stellen nennen ihren
    # eigenen, und der ist immer genauer als beide Vorgaben.
    own = ValidationError(title="Dieses Profil gibt es nicht.", detail="…")
    assert str(own.title) == "Dieses Profil gibt es nicht."


#: Beschränkungen, die bewusst **keine** Zahlenspanne sind.
#:
#: Das Gegenstück zu ``errors._RANGE_CONSTRAINTS``, und beide zusammen müssen
#: alles abdecken, was ``app/core`` wirklich setzt — dafür sorgt der Test
#: darunter. Getrennt geführt, weil die Frage nicht maschinell zu beantworten
#: ist: „zu wenige Punkte" und „zwischen drei und vierundsechzig Ecken" sehen im
#: Quelltext gleich aus, und nur beim zweiten steht eine Zahl in einem Feld, die
#: der Kunde ändern kann.
_NOT_A_RANGE = frozenset(
    {
        "absolute_path", "already_solid", "ambiguous_reference", "broken_scheme",
        "checksum", "choices",
        # „#RRGGBB" ist ein Format und keine Spanne: Eine Filamentfarbe kann
        # nicht „zu groß" sein, sie ist lesbar oder nicht.
        "changed", "colour",
        "consumes", "count_in_use", "cycle", "damaged", "damaged_sketch", "degenerate_normal",
        "empty", "exists", "expected_sha256",
        # Die Eingangsprüfung beim Einlesen (``loader.check_readable``):
        # leer, abgeschnitten, kein Netz, kein Archiv, null Dreiecke. Keine
        # davon ist eine Spanne — der Kunde kann an einer kaputten Datei
        # keine Zahl ändern, und „Ein Wert liegt außerhalb des zulässigen
        # Bereichs" stünde über jeder von ihnen falsch.
        "file_empty", "file_too_large", "file_truncated",
        "format", "grammar", "history_moved", "host",
        "invalid_archive", "inverted",
        "known_pattern",
        "json_depth", "known_structure", "library_state", "missing_file", "missing_gathered",
        "missing_link",
        "missing_payload",
        "needs_diameter", "no_area", "no_base_dir", "no_cavity", "no_direction", "no_face",
        "no_geometry", "no_migration", "no_normal", "no_outline", "no_profile",
        "no_repair_target", "no_section",
        "no_shapes", "no_size", "no_sources", "no_split", "no_triangles",
        "not_a_face", "not_a_hole", "not_a_mesh", "not_a_number", "not_an_archive",
        "not_a_project", "private_destination",
        "not_a_twin", "not_movable", "not_outline", "not_step", "not_upright", "one_body",
        # Eine vorgegebene Ausgabekennung, die es schon gibt (CORE-01): kein Feld.
        "output_taken",
        "point_count",
        "recipe_format", "remove_failed", "restore_failed",
        "repair_not_for_exact_body",
        "required",
        "scheme",
        # Der Dateiprüfer weist eine Datei aus mehreren Gründen ab — unbekannte
        # Operation, Titel zu lang. Eine Zahl ist nur einer davon,
        # und der Titel „Ein Wert liegt außerhalb des zulässigen Bereichs"
        # stünde über den anderen falsch.
        "shared_resource_limit", "shared_rules", "source",
        "sweep_needs_xy", "target_behind", "target_count", "target_parallel", "toml",
        # Zu groß für den Löser, zu viele Körper in der Baugruppe: Grenzen,
        # aber keine Zahl in einem Feld — die Datei ist so, wie sie ist (G-09, B-04).
        "too_large", "too_many_bodies",
        "too_many_triangles", "too_new", "type", "undo_with_changes", "unknown",
        "unknown_feature", "unknown_format", "unknown_object", "unknown_parameter",
        "unknown_placeholder", "unknown_region", "unknown_shape", "unknown_source",
        "unknown_target",
        "unknown_transaction", "unreadable", "unsupported_compression", "unsupported_format",
        "undo", "unsafe_url", "unwritable", "userinfo",
        "value_not_allowed", "web_page",
    }
)  # fmt: skip


def constraints_in_core() -> tuple[dict[str, str], list[str]]:
    """Jede ``constraint``-Angabe aus ``app/core`` — feste Werte und dynamische.

    Zurück kommt einmal ``{wert: erste Fundstelle}`` und einmal die Liste der
    Stellen, an denen kein fester Wert steht.
    """
    fest: dict[str, str] = {}
    beweglich: list[str] = []
    for path in core_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "constraint":
                    continue
                wert = keyword.value
                if isinstance(wert, ast.Constant) and isinstance(wert.value, str):
                    if wert.value:
                        fest.setdefault(wert.value, f"{path.name}:{node.lineno}")
                elif path.name != "errors.py":
                    # In ``errors.py`` reicht der Konstruktor sein eigenes
                    # Argument weiter — das ist die Definition, kein Aufruf.
                    beweglich.append(f"{path.name}:{node.lineno}")
    return fest, beweglich


def test_every_constraint_is_sorted_into_range_or_not() -> None:
    """Keine Beschränkung darf unbemerkt an beiden Listen vorbeilaufen.

    **Der Vorgänger konnte diese Lücke nicht finden.** Er zählte vier Spannen
    und fünf Gegenbeispiele auf, beide von Hand — und prüfte nie, was der Code
    tatsächlich setzt. ``corner_count`` („zwischen drei und vierundsechzig
    Ecken"), ``negative``, ``too_short`` und ``minimum_wall`` standen in keiner
    der beiden Listen und trugen deshalb den vagen Titel; für den Test gab es
    sie nicht. Ein Test, der nur seine eigene Aufzählung bestätigt, misst sich
    selbst.

    Hier kommt der **Ist-Zustand aus dem Quelltext** und der **Soll-Zustand aus
    den beiden kuratierten Listen**. Wer eine neue Beschränkung einführt, ordnet
    sie ein — oder der Lauf ist rot und sagt, welche fehlt.
    """
    fest, beweglich = constraints_in_core()

    assert not beweglich, (
        "Eine Beschränkung aus einer Variablen lässt sich nicht einordnen. "
        f"Stellen: {beweglich}. In ``solver.py`` stand dort einmal die Elementart "
        "(„circle“), und der Titel richtete sich danach."
    )

    unsortiert = {
        wert: ort
        for wert, ort in fest.items()
        if wert not in errors._RANGE_CONSTRAINTS and wert not in _NOT_A_RANGE
    }
    assert not unsortiert, (
        "Diese Beschränkungen kennt keine der beiden Listen — trägt sie in "
        "``errors._RANGE_CONSTRAINTS`` ein, wenn eine Zahl in einem Feld eine "
        f"Grenze verletzt, sonst in ``_NOT_A_RANGE``: {unsortiert}"
    )

    doppelt = errors._RANGE_CONSTRAINTS & _NOT_A_RANGE
    assert not doppelt, f"in beiden Listen, also ohne Antwort: {sorted(doppelt)}"

    verwaist = (errors._RANGE_CONSTRAINTS | _NOT_A_RANGE) - set(fest)
    assert not verwaist, (
        f"Diese Beschränkungen setzt der Kern nicht mehr: {sorted(verwaist)}. "
        "Eine Karteileiche in der Liste deckt beim nächsten Mal einen echten Fehler."
    )


def test_a_range_constraint_really_reads_like_one() -> None:
    """Stichprobe über den echten Weg, nicht über den Konstruktor.

    Die vier aus dem Befund vom 24.08.2026: Jede nennt in ihrem Detailtext eine
    Grenze, und über jeder stand „Die Eingabe war so nicht verwendbar."
    """
    from app.core.sketch.shapes import polygon

    with pytest.raises(ValidationError) as ecke:
        polygon(corners=2, diameter=10.0)
    assert ecke.value.constraint == "corner_count"
    assert "Bereichs" in str(ecke.value.title), (
        "„zwischen drei und vierundsechzig Ecken“ nennt beide Grenzen — "
        "der Titel darf nicht vager sein als das Detail"
    )


def test_no_action_label_ends_in_a_full_stop() -> None:
    """Auf einem Knopf steht keine Punktuation — er ist keine Aussage.

    Fünf Beschriftungen endeten mit einem Punkt (``Nur exportieren und selbst
    slicen.``, ``Ausgabe des Slicers ansehen.``, ``Maschinenprofil prüfen.``,
    ``Einen anderen Slicer auswählen.``, ``Dreiecke verringern.``), die
    dreißig übrigen nicht. Nebeneinander im selben Dialog sieht das aus wie
    zwei Sorten Vorschlag; und der Punkt reist in jeden der fünf Kataloge mit,
    wo ihn niemand mehr zurücknimmt.

    Gemessen wird über alle Handlungen des Moduls, nicht über eine Liste: Die
    nächste kommt dazu, ohne dass jemand hier nachträgt.
    """
    from app.core.errors import Action

    offenders = {
        name: str(entry.label)
        for name in dir(errors)
        if isinstance(entry := getattr(errors, name), Action) and str(entry.label).endswith(".")
    }

    assert not offenders, f"Knopfbeschriftungen mit Schlusspunkt: {offenders}"


def test_a_suggestion_has_to_fit_the_error() -> None:
    """„Reparieren und erneut versuchen" stand an Fehlern, wo es nichts zu
    reparieren gibt.

    ``GeometryError`` führt als Vorgabe „Reparieren und erneut versuchen" und
    „Stellen zeigen". Beide haben einen Handler, erscheinen also als Knopf — und
    an zwei Stellen taten beide nichts: Der Verrundungsradius steckt an einem
    exakten B-Rep-Körper, an dem es nichts zu reparieren gibt, und „Diese
    Operation arbeitet nur auf Netzen" wird durch Netzreparatur nicht wahr.
    Regel 17 war damit optisch erfüllt und in der Sache verletzt.

    Geprüft wird die Aussage und nicht die Stelle: Wo im Text vom Radius die
    Rede ist, gehört „Eingabe korrigieren" dazu und nicht die Reparatur.
    """
    import pathlib

    from app.core.brep import edit as brep_edit
    from app.core.errors import CANCEL, CORRECT_INPUT, REPAIR_AND_RETRY
    from app.core.geom import mesh as mesh_module

    for module, needle in ((brep_edit, "Radius"), (mesh_module, "nur auf Netzen")):
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        assert needle in source, f"{module.__name__}: der Fehlertext ist fort"

    # Der Radiusfehler, geworfen wie im Betrieb.
    problem = GeometryError(
        detail="Der Radius ist für diese Kanten zu groß.",
        suggestions=(CORRECT_INPUT, CANCEL),
        values={"size_mm": 4.0, "edges": 12},
    )
    ids = {action.id for action in problem.suggestions}
    assert "correct_input" in ids, "die Antwort auf einen zu großen Radius ist ein kleinerer"
    assert REPAIR_AND_RETRY.id not in ids, "an einem exakten Körper gibt es nichts zu reparieren"
    assert "show_locations" not in ids, "und dieser Fehler nennt keine Stellen"


def test_missing_software_offers_the_install_list_and_not_a_bug_report() -> None:
    """Eine fehlende Zusatzkomponente ist kein Fehler, den man melden könnte.

    ``BRepUnavailable`` nannte keine Vorschläge. ``AppError`` fällt dann auf
    „Abbrechen" zurück, und einem Dialog, dem sonst nichts bleibt, legt
    ``dialogs.offered_actions`` den Fehlerbericht bei — wer also eine
    Verrundung ohne OpenCASCADE versuchte, wurde gebeten, einen Fehler zu
    melden. Eine fehlende Zusatzkomponente schlägt stattdessen ``install`` vor.

    Geprüft an mehreren, damit es nicht an einer Klasse hängt: OpenCASCADE, ein
    Slicer, ComfyUI. Die Kennung am Fehler sagt „installieren", nicht „melden" —
    ein Vorschlag ohne Gegenstück ist keiner.
    """
    from app.core.brep.kernel import BRepUnavailable
    from app.core.errors import INSTALL_MISSING, ExternalToolError

    for problem in (
        BRepUnavailable(),
        ExternalToolError(tool="PrusaSlicer"),
        ExternalToolError(tool="ComfyUI"),
    ):
        ids = {action.id for action in problem.suggestions}
        assert INSTALL_MISSING.id in ids, (
            f"{type(problem).__name__}: der Weg zur Installation fehlt"
        )
        assert "report_error" not in ids, "fehlende Software ist kein Fehlerbericht"


def test_all_three_refusals_of_the_alignment_offer_a_way_out(monkeypatch) -> None:
    """Regel 17 für alle drei, nicht für eine.

    ``align.py`` sagt dreimal „An diesem Merkmal lässt sich nichts ausrichten."
    Eine der drei trug einen Vorschlag, die zwei anderen endeten mit dem Satz
    allein — gefunden am 03.09.2026, als alle achtzehn Fehlerklassen und alle
    zehn direkt geworfenen ``AppError`` auf ihre Auswege abgeklopft wurden.

    Für den Kunden ist der Fall dreimal derselbe: Er hat etwas angeklickt, mit
    dem sich nicht ausrichten lässt. Dass es einmal an der Merkmalsart liegt,
    einmal an fehlenden Maßen und einmal an einer Richtung der Länge null,
    ändert an seinem nächsten Schritt nichts — er klickt etwas anderes an.

    **Gefragt wird nach ``pick_feature`` und nicht danach, ob überhaupt etwas
    dasteht.** Die erste Fassung dieses Tests prüfte ``assert
    error.suggestions`` — und blieb grün, als die Vorschläge testweise wieder
    entfernt wurden. ``AppError.default_suggestions`` ist ``(CANCEL,)``, also
    ist die Liste **nie** leer: Der Test hätte „Regel 17 ist erfüllt" gemeldet
    für genau den Zustand, den Regel 17 verbietet. Derselbe Fehler eine Ebene
    höher, den 85 am selben Tag bei ``NeedsSolidError`` fand — formal ein
    Vorschlag, praktisch „geht nicht, brich ab".
    """

    def wege(fehler: AppError) -> list[str]:
        return [action.id for action in fehler.suggestions]

    from app.core.errors import AppError
    from app.core.geom import align
    from app.core.types import Feature

    herkunft = "detected"

    # Eine Bohrung ohne Achse und ohne Mitte: der Zweig „keine Lage gespeichert".
    ohne_lage = Feature(id="hole_1", kind="hole", provenance=herkunft, params={})
    with pytest.raises(AppError) as erste:
        align.frame_of(ohne_lage)
    assert "pick_feature" in wege(erste.value), wege(erste.value)

    # Eine Achse der Länge null.
    mit_nullachse = Feature(
        id="hole_2",
        kind="hole",
        provenance=herkunft,
        params={"axis": (0.0, 0.0, 0.0), "centre": (0.0, 0.0, 0.0)},
    )
    with pytest.raises(AppError) as zweite:
        align.frame_of(mit_nullachse)
    assert "pick_feature" in wege(zweite.value), wege(zweite.value)

    # Und der Zweig, der seinen Vorschlag schon hatte — die Gegenprobe.
    fremde_art = Feature(id="edge_1", kind="edge_loop", provenance=herkunft, params={})
    with pytest.raises(AppError) as dritte:
        align.frame_of(fremde_art)
    assert "pick_feature" in wege(dritte.value), wege(dritte.value)


def test_the_refusal_of_a_broken_file_offers_more_than_the_exit() -> None:
    """Eine Absage beim Einlesen trägt eine Handlung, die der Dialog auch zeigt.

    **Die naheliegende Prüfung wäre stumpf.** ``assert error.suggestions``
    bleibt immer grün, weil ``AppError.default_suggestions`` ``(CANCEL,)`` ist.
    Und ``correct_input``, das ``ValidationError`` von Haus aus mitbringt,
    zeigt der Fehlerdialog hier gar nicht: Es steht in ``dialogs.NEEDS_OP`` und
    braucht die Kennung eines Schrittes — beim Lesen einer Datei gibt es
    keinen, denn die Prüfung läuft, bevor die Operation entsteht.

    Gefragt wird deshalb nach dem, was **übrig bleibt**, wenn der Dialog
    gefiltert hat. Bliebe nur *Abbrechen*, endete der Fehler mit „geht nicht" —
    genau das verbietet Regel 17.
    """
    import struct

    from app.core.ingest.plan import import_plan
    from app.ui.dialogs import NEEDS_OP

    # Ein Kopf, der zwölf Dreiecke ansagt, und genau eines dahinter: der
    # abgebrochene Download. Ohne Escape-Folgen gebaut — ``bytes(80)`` ist
    # dasselbe wie achtzig Nullbytes und übersteht jedes Werkzeug dazwischen.
    abgeschnitten = bytes(80) + struct.pack("<I", 12) + bytes(50)

    for name, payload in (
        ("leer.stl", b""),
        ("halb.stl", abgeschnitten),
        ("seite.stl", b"<!DOCTYPE html><html><body>404 Not Found</body></html>"),
        ("ohne_dreiecke.stl", bytes(80) + struct.pack("<I", 0)),
        ("kein_archiv.3mf", b"Das ist kein ZIP-Archiv."),
    ):
        with pytest.raises(ValidationError) as gefangen:
            import_plan("src_1", name, payload)
        gezeigt = [
            action.id
            for action in gefangen.value.suggestions
            if action.id != "cancel" and action.id not in NEEDS_OP
        ]
        assert gezeigt, f"{name}: die Absage endet mit „geht nicht“"


def test_no_internal_error_speaks_to_the_customer() -> None:
    """Ein ``InternalError``, dessen Text übersetzt ist, ist keiner.

    Die Hierarchie trennt Bedienfehler von Programmfehlern (`kern.md`), und
    ``InternalError`` ist die Klasse für das Zweite: Was hier landet, war nicht
    vorgesehen, und die Antwort darauf ist ein Fehlerbericht. Ein Text, der
    durch ``_()`` geht, ist dagegen einer, den der Kunde lesen soll — und wer
    ihn schreibt, hat einen Bedienfall als Programmfehler abgelegt.

    Genau so ist es einmal passiert: ``resize_hole`` warf „Die geänderte
    Bohrung wurde gerechnet, aber danach nicht wiedererkannt. Erstellen Sie
    einen Fehlerbericht mit dem betroffenen Modell.", wenn jemand eine Bohrung
    so weit verkleinerte, dass die Erkennung sie nicht mehr fand. Die Geometrie
    war richtig gerechnet, der Kunde hatte den Fall selbst herbeigeführt, und
    die geworfene Ausnahme nahm das Ergebnis mit.

    **Die Regel ist keine Meinung, sondern der Bestand.** Gemessen am
    03.09.2026: 26 Wurfstellen, davon 25 mit englischem Detailtext und genau
    eine mit einem übersetzten — die oben. Der Wächter hält fest, was ohnehin
    gilt.

    Gefunden hat die Regel 3d-druck-a0 beim Durchsehen aller Wurfstellen,
    nachdem der Einzelfall behoben war.
    """
    quelle = Path(errors.__file__).resolve().parents[1]
    offenders: list[str] = []
    geprueft = 0
    for datei in sorted(quelle.rglob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Raise) or not isinstance(knoten.exc, ast.Call):
                continue
            gerufen = knoten.exc.func
            name = getattr(gerufen, "id", None) or getattr(gerufen, "attr", None)
            if name != "InternalError":
                continue
            geprueft += 1
            detail = next(
                (
                    schluessel.value
                    for schluessel in knoten.exc.keywords
                    if schluessel.arg == "detail"
                ),
                None,
            )
            if not isinstance(detail, ast.Call):
                continue
            uebersetzer = getattr(detail.func, "id", None) or getattr(detail.func, "attr", None)
            if uebersetzer in ("_", "tr"):
                offenders.append(f"{datei.relative_to(quelle)}:{knoten.lineno}")

    assert geprueft > 15, f"nur {geprueft} Wurfstellen gefunden — die Suche greift nicht mehr"
    assert not offenders, (
        "ein InternalError mit übersetztem Text ist ein Bedienfall in der falschen "
        f"Klasse: {offenders}"
    )
