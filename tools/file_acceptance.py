"""Native Einzeldatei- und Funktionsabnahme: jeder Fall im echten Fenster, jeder Schritt mit Bild.

    .venv\\Scripts\\python.exe tools/file_acceptance.py inventory --manifest <json> --out <ordner>
    .venv\\Scripts\\python.exe tools/file_acceptance.py inventory --source <bestand> --out <ordner>
    .venv\\Scripts\\python.exe tools/file_acceptance.py inventory --functions --out <ordner>
        [--package D4] [--rows <kennung>,…] [--phases main,escape]
        [--variants basis,sprachen,…,vorhersage,schrift,schriftwechsel] (function_setup.PHASES)
    .venv\\Scripts\\python.exe tools/file_acceptance.py run --out <ordner> [--first 1] [--last 9]
        [--again] [--timeout <s>] [--screen <name oder nummer>] [--total <s>] [--binding <json>]
    .venv\\Scripts\\python.exe tools/file_acceptance.py seal --out <ordner>
    .venv\\Scripts\\python.exe tools/file_acceptance.py report --out <ordner>
        [--package D4] [--verdicts <toml>] [--checklist <md>] [--runs <ablage>]

``--manifest`` nimmt das Manifest des Dateiaudits
(``ui-audit/2026-09-15-files/manifest.json``: 187 Fälle in seiner Zählung),
``--source`` einen Ordner wie ``F:\\3D Dateien`` (RM-184). ``--functions`` legt
die Funktionsfälle des Funktionsdurchgangs an (RM-737, Konzept
``konzept-funktionsdurchgang-2026-10.md`` §5): je Zeile der erzeugten
Funktionsliste (``tools/function_list.py``) und Variante ein Fall, je Sprache
und Paket ein Sprachfall; dazu die Startszenen nach ``<ordner>/scenes/`` und die
Menüleiste des gebauten Fensters nach ``<ordner>/menubar.json``. Gefahren
werden sie vom Prüfstand (``tools/function_bench.py`` und seine Nachbarn) —
dieses Werkzeug bleibt der eine Einstieg (Konzept §12: kein drittes
Fensterwerkzeug).

**Jede geprüfte Handlung ist ein Eingabeereignis** (Bauplan D0 B5): Auswahl per
Klick auf die Baumzeile, Zahlen getippt mit dem Dezimalzeichen der Sprache,
*Übernehmen* geklickt, Rückgängig und Wiederholen über ihre Tasten — jeder Klick
an der Stelle, die ``guide_targets.next_click`` nennt, mit der Probe, ob dort
wirklich das Ziel liegt (``function_walk.Walk``). Nur die Startszene entsteht
über ``open_path``. Der Kindprozess setzt ``AA_DontUseNativeDialogs``: Den
Systemdialog prüft nur Stufe C.

Gebaut aus dem Serienlauf des Dateiaudits vom 15.09.2026 (``audit.py``: ein
frischer Prozess je Datei, das echte Fenster, ein eigenes Nutzerprofil je
Fall) und seinem Kundenweg an der Bohrung (``detail_ui.py``). Je Dateifall:

1. **Import** über ``MainWindow.open_path`` — der Weg von Menü, Zuletzt-Liste
   und Ziehen; der Systemdialog gehört dem Betriebssystem. Eine Rückfrage
   beantwortet der Hauptknopf ihres Dialogs.
2. **Erkennung**: Merkmale je Körper nach Art, dazu die funktionalen Gruppen.
3. **Maßänderung** an einem repräsentativen Merkmal (Bohrung vor Langloch vor
   Gewinde vor Kegel vor Zapfen vor Fläche): gewählt mit einem Klick auf seine
   Zeile im Objektbaum (``tree.row:``), geändert am ersten Längenfeld des
   Merkmalfensters, das ein Maß und keine Lage nennt — hineingeklickt, alles
   markiert, die neue Zahl getippt.
4. **Vorschau**, **Übernehmen** (``feature.apply``), **Rückgängig** und
   **Wiederholen** über die Tasten aus ``shortcut_schemes``. Ob die Vorschau
   steht oder abgesagt ist, liest der Lauf ab, wo der Kunde es sieht: Band mit
   Legende, gesperrtes *Übernehmen* mit seinem Grund.

Je Schritt ein Bild des Fensters und je Körper ein Netzabdruck (SHA-256 über
Ecken und Dreiecke, ein exakter Körper über seine Vernetzung im selben
Prozess). Geprüft wird, dass Rückgängig den Stand des Imports
wiederherstellt, Wiederholen den übernommenen, dass die Vorschau zeigt, was
übernommen wird, und dass die Änderung etwas geändert hat. An der Drillholder-
Datei geht das für **jede** Bohrung (``--bores`` oder ``BORE_CASES``).

**Ausgabe außerhalb des Repositorys** (``--out``): Bilder und Profile gehören
nicht in den Arbeitsbaum. Je Fall ein Ordner ``cases/<nummer>`` mit
``result.json``, ``process.json``, Protokollen und Bildern; dazu
``summary.json`` und ``summary.md``. Ein abgeschlossener Fall wird beim
nächsten Lauf übersprungen (``--again`` fährt ihn neu).

Kein Testlauf und nicht im Tor: Der Lauf braucht ein echtes Fenster und
dauert. Seine Logik — Bestand, Wahl des Merkmals, neue Zahl, Abgleich der
Abdrücke, Bericht — prüft ``tests/test_file_acceptance.py`` ohne Fenster, die
der Funktionsfälle ``tests/test_function_bench.py`` und ihre Nachbarn.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

#: Was als Fall zählt — dieselben Endungen wie im Dateiaudit vom 15.09.
MODEL_SUFFIXES: frozenset[str] = frozenset(
    {".stl", ".3mf", ".step", ".stp", ".glb", ".svg", ".p3d"}
)

#: Fälle, an denen jede Bohrung einzeln abgenommen wird — Teil des Dateinamens.
BORE_CASES: tuple[str, ...] = ("drill-holder",)

#: Welches Merkmal für die Maßänderung steht: das erste dieser Arten, das ein
#: Längenfeld trägt. ``group`` ist der Boden einer Kammer, einer Nut oder eines
#: Kanals (*Kammer ändern*, RM-184). Wulst, Kugel und Muster ändert *Merkmal
#: ändern* ebenso — am 1x1-tray trugen nur die Wülste ein Maß.
FEATURE_PRIORITY: tuple[str, ...] = (
    "hole",
    "slot",
    "thread",
    "group",
    "cone",
    "pin",
    "fillet",
    "torus",
    "sphere",
    "pattern",
    "face",
)

#: Wie viele Merkmale höchstens versucht werden, bis eines ein Längenfeld hat.
MOST_FEATURE_TRIES = 12

#: Wie viele Merkmale einer Art höchstens darunter sind: Am 1x1-tray trugen
#: vier Kegel und sieben Rundungen kein Längenfeld und verbrauchten die
#: Versuche, bevor ein Wulst drankam.
MOST_TRIES_PER_KIND = 3

#: Was ein Durchgang notiert, wenn das Merkmalfenster kein Längenfeld zeigt.
NO_LENGTH_FIELD = "kein Längenfeld am Merkmal"

#: Was ein Durchgang notiert, wenn die Vorschau jede versuchte Zahl absagt —
#: am 1x1-bin brach die breitere Kammer durch die Wand.
REFUSED = "jede Maßänderung abgesagt"

#: Die Stufe eines Falls, an dem kein versuchtes Merkmal eine Änderung trug —
#: keine Abweichung, denn geprüft wurde nichts. Warum, sagen ``tried`` und
#: ``refusals`` im Ergebnis.
UNCHANGEABLE = "kein Merkmal ließ sich ändern"

#: Feldtitel, die eine Lage nennen und kein Maß. Am Drillholder stand
#: „Merkmal verschieben — X“ vor „Bohrung ändern — Durchmesser“, und der Lauf
#: verschob jede Bohrung, statt ihr Maß zu ändern.
POSITION_TITLES: frozenset[str] = frozenset({"X", "Y", "Z"})

#: Wie lange ein Fall höchstens dauern darf (Sekunden), Import und Schritte zusammen.
CASE_TIMEOUT = 600.0

#: Dasselbe für einen Fall mit jeder Bohrung: Der Drillholder brauchte offscreen
#: unter Fremdlast 904 s für 23 von 29 Bohrungen.
BORE_CASE_TIMEOUT = 3600.0

#: Wie oft ein Zwischenstand geschrieben wird, bevor der Fall abbricht.
WRITE_ATTEMPTS = 20

#: Wie lange ein einzelner Schritt im Fenster warten darf (Sekunden).
STEP_TIMEOUT = 180.0

#: Dasselbe für einen Funktionsfall: Sein Grundsatz geht dieselbe Zeile in
#: zwölf Phasen ab, jede von der Startszene aus (``function_bench.FunctionFlow``).
FUNCTION_CASE_TIMEOUT = 1800.0

#: Und für einen Sprachfall, der die Flächen aller Zeilen eines Pakets abgeht —
#: wieder aufnehmbar je Fläche, also verliert ein Abbruch nur die eine.
LANGUAGE_CASE_TIMEOUT = 3600.0

#: Wie lange der Kindprozess braucht, um die Menüleiste am Fenster zu zählen (Sekunden).
MENUBAR_TIMEOUT = 600.0

#: Alle wie viel Sekunden ein Fall die Stapel seiner Fäden nach :data:`STACK_LOG` schreibt.
HANG_DUMP_S = 300.0

#: Wohin ein Fall die Stapel seiner Fäden schreibt: bei einem Absturz und alle
#: :data:`HANG_DUMP_S`, solange er steht (``faulthandler``).
STACK_LOG = "stapel.log"

#: Wohin ein Fall jede Meldung von Qt schreibt. Ein ``qFatal`` — ein ASSERT in Qt —
#: endet ohne Python-Stapel und ohne Zeile in ``stderr.log``, denn unter Windows
#: geht die Meldung eines Fensterprozesses an den Debugger (Probelauf, Befund A).
QT_LOG = "qt.log"

#: Was ein Fall bis zu seinem Ende offen halten muss: die Datei der Stapel, die
#: Datei der Qt-Meldungen und deren Empfänger.
_HELD: list[Any] = []

#: Die Arten eines Falls: eine Datei (RM-184), eine Zeile der Funktionsliste,
#: eine Sprache über die Flächen eines Pakets, der Start einer Zeile des
#: Startablaufs über ``app.ui.app.main`` (RM-737).
CASE_KINDS: tuple[str, ...] = ("file", "function", "language", "start")

#: Die Quelle der Zeilen, die vor dem Hauptfenster stehen (``function_list.startup_rows``):
#: Sie laufen als Startfall, nicht als Funktionsfall.
STARTUP_SOURCE = "startablauf"

#: Das Messprofil des Audits: kein Materialurteil, nur ein fester Rahmen —
#: auch der Filamentdrucker der Funktionsfälle (``function_setup.PRINTERS``).
PRINTER = "centauri-carbon-2"
MATERIAL = "petg"

STEPS: tuple[str, ...] = (
    "01-import",
    "02-selection",
    "03-preview",
    "04-applied",
    "05-undo",
    "06-redo",
)


@dataclass(frozen=True, slots=True)
class Case:
    """Ein Fall der Abnahme: eine Datei, ein Archivmitglied, eine Funktion oder eine Sprache.

    ``kind`` ist einer aus :data:`CASE_KINDS`; ``row`` die Kennung der Zeile
    (beim Sprachfall das Paket), ``variant`` die Bedingungen des Laufs
    (``function_setup.Variant``). Alte ``cases.json`` ohne diese Felder sind
    Dateifälle und bleiben lesbar.
    """

    number: int
    relative: str
    path: str
    suffix: str
    bores: bool = False
    kind: str = "file"
    row: str = ""
    variant: dict[str, Any] = field(default_factory=dict)


# --- Bestand -----------------------------------------------------------------


def outside_the_repository(out: Path) -> Path:
    """Der Ausgabeordner — nie im Arbeitsbaum: Bilder und Profile reisen nicht mit."""
    resolved = out.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise SystemExit(
            f"Der Ausgabeordner liegt im Repository: {resolved}. Wählen Sie einen Ordner außerhalb."
        )
    return resolved


def is_bore_case(relative: str) -> bool:
    """Ob an diesem Fall jede Bohrung einzeln abgenommen wird."""
    name = Path(relative.replace(" :: ", "/")).name.lower()
    return any(marker in name for marker in BORE_CASES)


def cases_from_source(source: Path, out: Path) -> list[Case]:
    """Der Bestand eines Ordners in der Zählweise des Audits.

    Modelle und Projekte direkt, Archivmitglieder ausgepackt (``archive-models``
    im Ausgabeordner), Sicherungen ``.vor-reparatur`` als Projektkopie — die
    Originale bleiben unberührt. Nummeriert wird in der Reihenfolge der Pfade,
    Archivmitglieder hinter allen Dateien.
    """
    direct: list[Case] = []
    members: list[tuple[str, bytes, str]] = []
    copies = out / "archive-models"
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(source))
        suffix = path.suffix.lower()
        if suffix in MODEL_SUFFIXES:
            direct.append(Case(0, relative, str(path), suffix, is_bore_case(relative)))
        elif suffix == ".vor-reparatur":
            copies.mkdir(parents=True, exist_ok=True)
            target = copies / f"backup-{len(direct) + 1}.p3d"
            shutil.copyfile(path, target)
            direct.append(Case(0, relative, str(target), ".p3d"))
        elif suffix == ".zip" and zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    inner = Path(info.filename).suffix.lower()
                    if not info.is_dir() and inner in MODEL_SUFFIXES:
                        members.append(
                            (f"{relative} :: {info.filename}", archive.read(info), inner)
                        )
    numbered = [
        Case(number, case.relative, case.path, case.suffix, case.bores)
        for number, case in enumerate(direct, 1)
    ]
    for offset, (relative, payload, suffix) in enumerate(members):
        copies.mkdir(parents=True, exist_ok=True)
        number = len(numbered) + 1
        target = copies / f"{number}-{offset}{suffix}"
        target.write_bytes(payload)
        numbered.append(Case(number, relative, str(target), suffix, is_bore_case(relative)))
    return numbered


def cases_from_manifest(manifest: Path) -> list[Case]:
    """Die Fälle eines Audit-Manifests — dieselben Nummern, dieselben Dateien.

    Gezählt wird wie im Audit: Modelle, Projekte, ausgepackte Archivmitglieder
    und Sicherungen mit eigener Prüfkopie (``audit_path``).
    """
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    found: list[Case] = []
    for entry in entries:
        if entry.get("suffix") not in MODEL_SUFFIXES and "audit_path" not in entry:
            continue
        path = str(entry.get("audit_path", entry["path"]))
        suffix = Path(path).suffix.lower()
        found.append(
            Case(
                int(entry["id"]),
                str(entry["relative"]),
                path,
                suffix,
                is_bore_case(str(entry["relative"])),
            )
        )
    return found


def write_json(path: Path, data: object, attempts: int = WRITE_ATTEMPTS) -> None:
    """Schreibt über eine Nebendatei und ersetzt dann — mit Wiederholung.

    Windows sperrt eine gerade gelesene Datei kurz (Virenprüfer, Indexdienst):
    Am Drillholder brach ein Fall nach 23 von 29 Bohrungen mit
    ``OSError: [Errno 22]`` beim Zwischenstand ab. Ersetzt wird erst, wenn die
    Nebendatei vollständig ist; ein Leser sieht nie eine halbe Datei.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=1, default=str).encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    for attempt in range(attempts):
        try:
            temporary.write_bytes(payload)
            temporary.replace(path)
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.2 * (attempt + 1))


def read_cases(out: Path) -> list[Case]:
    return [Case(**entry) for entry in json.loads((out / "cases.json").read_text(encoding="utf-8"))]


#: Die Nutzerordner, die ein Fall auf sein Profil legt. Nie ``HOME`` oder
#: ``USERPROFILE``: Grafiktreiber und ihre Zwischenspeicher hängen daran, und die
#: Adapterfrage der Ansicht hing dann (Erinnerung „sonden-bauen“).
PROFILE_VARIABLES: tuple[str, ...] = (
    "APPDATA",
    "LOCALAPPDATA",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
)


def isolate(profile: Path) -> None:
    """Nutzerordner auf ``profile``, Schlüsselbund auf die Attrappe — vor ``import app``."""
    profile.mkdir(parents=True, exist_ok=True)
    os.environ.update(dict.fromkeys(PROFILE_VARIABLES, str(profile)))
    from app.core.paths import isolate_secrets  # nach den Ordnern: app liest sie

    isolate_secrets(os.environ)


# --- Funktionsfälle (RM-737) -----------------------------------------------------


def function_cases(
    rows: Sequence[Mapping[str, Any]],
    *,
    packages: Sequence[str] = (),
    row_ids: Sequence[str] = (),
    variant_sets: Sequence[str] = ("basis",),
    languages: Sequence[str] | None = None,
    phases: Sequence[str] = (),
    first_number: int = 1,
) -> list[Case]:
    """Die Fälle zu Zeilen der Funktionsliste: je Zeile und Variante, je Sprache und Paket.

    ``rows`` sind die Zeilen aus ``tools/function_list.py`` (Plan D0, Abschnitt 2.3).
    ``packages`` und ``row_ids`` schränken ein; eine Kennung, die keine Zeile
    trifft, ist ein Fehler — ein Lauf, der still nichts prüft, sähe aus wie einer,
    der nichts fand. ``sprachen`` faltet nicht je Zeile aus: Ein Prozess je
    Sprache, Paket und Einrichtung der Startszenen geht die Flächen seiner Zeilen
    ab (``tools/CLAUDE.md``, sechs Sprachen in einem Prozess brechen ab;
    ``function_cases``, FD-101). ``phases`` beschränkt jeden
    Funktionsfall auf diese Phasen (``function_setup.PHASES``) — für die
    Nachprüfung einer Zeile nach einem Fix.

    Was die Spezifikation an Lizenz und Vorbedingungen nennt, gilt für jeden Fall
    der Zeile, ebenso die Vorbedingungen ihrer Startszene
    (``function_setup.scene_setup``); eine Vorbedingung mit zwei Zuständen bekommt im Satz ``basis``
    einen Lauf im anderen Zustand dazu, denn „fehlt“ ist der Fehlerweg
    (``function_setup.spec_variants``). Die Läufe von ``lizenz`` liest
    ``function_setup.variant_sets`` jetzt an der Fassung. Eine Zeile des
    Startablaufs (:data:`STARTUP_SOURCE`) wird im Satz ``basis`` ein Startfall
    im Zustand „Demo abgelaufen“ und in keinem anderen Satz gefahren — sie hat
    kein Fenster, an dem eine Phase liefe. ``phases`` gilt nur für Sätze, die
    sie haben; ein Satz ohne eine davon fällt weg.
    """
    from app.i18n.catalog import available_languages
    from tools.function_list import STARTUP_LICENCE
    from tools.function_scenes import row_scenes
    from tools.function_setup import PHASES, Variant, scene_setup, spec_variants
    from tools.function_setup import variant_sets as known_sets

    sets = known_sets()
    unknown_sets = sorted(set(variant_sets) - set(sets))
    if unknown_sets:
        raise ValueError(
            f"unbekannte Variantensätze: {', '.join(unknown_sets)} — bekannt: {', '.join(sets)}"
        )
    unknown_phases = sorted(
        set(phases) - {phase for name in variant_sets for phase in PHASES.get(name, ())}
    )
    if unknown_phases:
        raise ValueError(f"Phasen {unknown_phases} gibt es in {list(variant_sets)} nicht")
    known = {str(row["id"]) for row in rows}
    missing = sorted(set(row_ids) - known)
    if missing:
        raise ValueError(f"keine Zeile mit der Kennung: {', '.join(missing)}")
    chosen = [
        row
        for row in rows
        if (not packages or row.get("package") in packages)
        and (not row_ids or str(row["id"]) in row_ids)
    ]
    cases: list[Case] = []
    number = first_number
    for name in variant_sets:
        own = tuple(phase for phase in phases if phase in PHASES[name])
        if phases and not own:
            continue
        for row in chosen if name != "sprachen" else ():
            if row.get("source") == STARTUP_SOURCE:
                if name == "basis" and not phases:
                    variant = Variant.of({"set": "start", "licence": STARTUP_LICENCE})
                    cases.append(
                        Case(
                            number,
                            f"{row['id']} [{STARTUP_LICENCE}]",
                            "",
                            "",
                            kind="start",
                            row=str(row["id"]),
                            variant=variant.as_dict(),
                        )
                    )
                    number += 1
                continue
            scene = str((row.get("spec") or {}).get("start_scene") or row.get("start_scene") or "")
            base, others = spec_variants(row.get("spec"))
            # Was die Startszene verlangt (OpenCASCADE fehlt, Generator läuft), gilt
            # für jeden Fall der Zeile — ohne Gegenlauf, sonst fehlte ihr Befund;
            # ebenso die Szene des Fehlfalls, der im selben Fall läuft (C-L4).
            needed: dict[str, str] = {}
            for key in reversed(row_scenes(row)):
                needed.update(scene_setup(key).preconditions)
            if needed:
                base = {**base, "preconditions": {**base.get("preconditions", {}), **needed}}
            entries = [{**base, **entry, "phases": own} for entry in sets[name]]
            if name == "basis" and not phases:
                entries += [{**base, "set": "basis", **other} for other in others]
            for entry in entries:
                variant = Variant.of(entry)
                label = ", ".join(
                    f"{key}={value}"
                    for key, value in entry.items()
                    if key not in ("set", "phases") and value
                )
                cases.append(
                    Case(
                        number,
                        f"{row['id']} [{label or name}]",
                        f"scenes/{scene}.p3d" if scene else "",
                        "",
                        kind="function",
                        row=str(row["id"]),
                        variant=variant.as_dict(),
                    )
                )
                number += 1
    if "sprachen" in variant_sets:
        from tools.function_cases import language_cases

        spoken = tuple(languages) if languages is not None else available_languages()
        packages = {str(row.get("package")) for row in chosen}
        cases += language_cases(rows, packages, spoken, number, "vorhersage" in variant_sets)
    return cases


def read_rows(out: Path) -> dict[str, dict[str, Any]]:
    """Die Zeilen eines Funktionslaufs, wie das Inventar sie abgelegt hat (``rows.json``)."""
    path = out / "rows.json"
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["id"]): row for row in loaded}


def function_inventory(
    out: Path,
    *,
    packages: Sequence[str],
    row_ids: Sequence[str],
    variant_sets: Sequence[str],
    phases: Sequence[str] = (),
) -> list[Case]:
    """``inventory --functions``: Menüleiste, Zeilen, Fälle und Startszenen ablegen.

    Zuerst zählt ein Kindprozess am gebauten Fenster die Menüleiste
    (``menubar.json``, :func:`menubar`) — die Fensterbefehle entstehen erst mit
    dem Fenster (Konzept §3). Dann baut ``tools/function_list.py`` (D0-L) daraus
    und aus Register, Dialogklassen und Wortschatz die Zeilen; ``rows.json``
    trägt sie für Kindprozesse und Bericht (D0-U liest dieselbe Datei). Die
    Startszenen speichert ``function_scenes.save_scenes`` nach ``scenes/``: alle
    leichten, und die schweren dazu, sobald eine gewählte Zeile in einer
    schweren beginnt — L baut die Szenen nur als Ganzes. Jeder Fall öffnet
    davon seine eigene Kopie (``function_bench.FunctionFlow.scene_path``).
    """
    from dataclasses import asdict as as_dict

    from tools import function_list, function_scenes

    entries = function_list.read_menubar(menubar(out))
    rows = [as_dict(row) for row in function_list.rows(entries)]
    cases = function_cases(
        rows, packages=packages, row_ids=row_ids, variant_sets=variant_sets, phases=phases
    )
    from tools.function_cases import package_of

    chosen = {case.row for case in cases if case.kind in ("function", "start")}
    languages = {package_of(case.row) for case in cases if case.kind == "language"}
    kept = [row for row in rows if str(row["id"]) in chosen or row.get("package") in languages]
    write_json(out / "rows.json", kept)
    catalogue = function_scenes.load_scenes()
    # Auch die Startszene des Fehlfalls (``fault_case.start_scene``): Sie fehlte,
    # und der Fehlfall von *Auf das Bett setzen* lief nie (Probelauf F-34).
    wanted = {key for row in kept for key in function_scenes.row_scenes(row)}
    heavy = any(catalogue[key].heavy for key in wanted if key in catalogue)
    function_scenes.save_scenes(out / "scenes", heavy=heavy)
    return cases


def menubar(out: Path) -> Path:
    """Die Fensterbefehle des gebauten Fensters nach ``menubar.json`` — in einem Kindprozess.

    Offscreen genügt: Gezählt werden Einträge und ihre Kennungen, nicht ihr Bild.
    Ein eigener Prozess, weil das Inventar selbst kein Fenster baut und ein
    Fenster im selben Prozess die Fälle danach nicht stören soll.
    """
    from app.core.paths import isolate_secrets

    out.mkdir(parents=True, exist_ok=True)  # cwd des Kindes (RC-10)
    target = out / "menubar.json"
    try:
        finished = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "menubar", "--out", str(out)],
            cwd=out,
            env=isolate_secrets({**os.environ, "PYTHONUTF8": "1", "QT_QPA_PLATFORM": "offscreen"}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=MENUBAR_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as expired:
        # Eine Meldung statt eines Stapels (Review L6).
        raise RuntimeError(
            f"Die Menüleiste ließ sich nicht zählen: Der Kindprozess antwortete"
            f" nach {MENUBAR_TIMEOUT:.0f} s nicht."
        ) from expired
    if finished.returncode != 0 or not target.is_file():
        raise RuntimeError(f"Die Menüleiste ließ sich nicht zählen:\n{finished.stderr[-4000:]}")
    return target


def menubar_child(out: Path) -> int:
    """Kindprozess von :func:`menubar`: Fenster bauen, Menüleiste lesen, schreiben.

    Das Profil steht auf der Quellsprache: Die Kennungen der Fensterbefehle sind
    die deutschen Menüpfade (``function_list.MenuEntry``), gleich welche
    Sprache das System spricht.
    """
    isolate(out / "menubar-profile")
    sys.path.insert(0, str(ROOT))
    from tools import function_setup

    function_setup.write_profile(function_setup.Variant())
    from app.core.bootstrap import load_operations
    from app.ui.app import build_application
    from tools import function_list
    from tools.window_bench import record_shutdown, shutdown_window

    load_operations()
    application, window = build_application([])
    try:
        function_list.write_menubar(out / "menubar.json", function_list.menubar_of(window))
    finally:
        record_shutdown({}, lambda: None, shutdown_window(window, application))
    return 0


# --- Wahl und Abgleich ----------------------------------------------------------


def group_anchors(groups: Sequence[str]) -> set[str]:
    """Die Böden von Kammer, Nut und Kanal aus den Gruppenzeilen der Erkennung.

    Eine Zeile heißt ``art/variante:anker`` (:meth:`WindowFlow._recognition`);
    ein Anschluss mit Durchgang hat kein Innenmaß und zählt nicht.
    """
    found: set[str] = set()
    for line in groups:
        kind, _slash, rest = line.partition("/")
        variant, _colon, anchor = rest.partition(":")
        if kind in ("chamber", "channel") and variant != "passage" and anchor:
            found.add(anchor)
    return found


def ranked_features(
    objects: Mapping[str, Mapping[str, str]],
    anchors: Mapping[str, set[str]] | None = None,
) -> list[tuple[str, str]]:
    """Die Merkmale für die Maßänderung in der Folge, in der sie versucht werden.

    ``objects`` nennt je Körper seine Merkmale mit Art (``{"obj_1": {"hole_6":
    "hole"}}``), ``anchors`` je Körper die Böden seiner Kammern und Kanäle —
    sie stehen als ``group`` in :data:`FEATURE_PRIORITY`: Am 1x1-bin trägt
    keine Fläche ein Längenfeld, die Kammer schon. Zuerst die Art, bei
    gleicher Art der Körper, dann die Nummer — so trifft jeder Lauf dieselben
    Merkmale. Je Art höchstens :data:`MOST_TRIES_PER_KIND`, damit jede Art an
    die Reihe kommt.
    """
    ranked: list[tuple[int, str, int, str]] = []
    for object_id, features in objects.items():
        floors = (anchors or {}).get(object_id, set())
        for feature_id, own in features.items():
            kind = "group" if feature_id in floors else own
            if kind not in FEATURE_PRIORITY:
                continue
            number = feature_id.rpartition("_")[2]
            ranked.append(
                (
                    FEATURE_PRIORITY.index(kind),
                    object_id,
                    int(number) if number.isdigit() else 0,
                    feature_id,
                )
            )
    chosen: list[tuple[str, str]] = []
    per_kind: dict[int, int] = {}
    for rank, object_id, _number, feature_id in sorted(ranked):
        if per_kind.get(rank, 0) < MOST_TRIES_PER_KIND:
            per_kind[rank] = per_kind.get(rank, 0) + 1
            chosen.append((object_id, feature_id))
    return chosen


def choose_feature(objects: Mapping[str, Mapping[str, str]]) -> tuple[str, str] | None:
    """Das erste Merkmal aus :func:`ranked_features` — oder keines."""
    ranked = ranked_features(objects)
    return ranked[0] if ranked else None


def first_with_a_length_field(
    candidates: Sequence[tuple[str, str]],
    cycle: Callable[[tuple[str, str]], dict[str, Any]],
    tries: int = MOST_FEATURE_TRIES,
) -> tuple[list[str], dict[str, Any] | None]:
    """Der erste Durchgang an einem Merkmal mit Längenfeld, und wer davor versucht wurde.

    **Ein Merkmal ohne Längenfeld ist kein Fall der Maßänderung**: Am 1x1-bin
    stand vorn ein Kegel, dessen Merkmalfenster nur einen Winkel trägt. Ebenso
    wenig eines, an dem die Vorschau jede versuchte Zahl absagt (:data:`REFUSED`).
    Versucht wird das nächste, höchstens ``tries`` Merkmale; trägt keines,
    bleibt der letzte Durchgang mit seinem Vermerk stehen.
    """
    tried: list[str] = []
    record: dict[str, Any] | None = None
    for chosen in candidates[:tries]:
        record = cycle(chosen)
        tried.append(chosen[1])
        if record.get("note") not in (NO_LENGTH_FIELD, REFUSED):
            break
    return tried, record


def bore_ids(features: Mapping[str, str]) -> list[str]:
    """Alle Bohrungen eines Körpers, nach ihrer Nummer."""

    def number(feature_id: str) -> int:
        tail = feature_id.rpartition("_")[2]
        return int(tail) if tail.isdigit() else 0

    return sorted((name for name, kind in features.items() if kind == "hole"), key=number)


def changed_value(value: float) -> float:
    """Die neue Zahl einer Maßänderung: ein Zehntel mehr, mindestens ein halber Millimeter.

    Eine Null (ein Versatz) wird ein Millimeter. Gerundet auf zwei Stellen,
    wie das Feld sie zeigt — sonst stünde im Bericht eine Zahl, die niemand
    getippt haben kann.
    """
    if abs(value) < 1e-9:
        return 1.0
    step = max(abs(value) * 0.1, 0.5)
    return round(value + step, 2)


def size_field_first(names: Sequence[str]) -> int:
    """Welches Längenfeld die Maßänderung nimmt: das erste, das keine Lage nennt.

    Ein Feld heißt „<Handlung> — <Feld>“ (``accessibleName``, :data:`POSITION_TITLES`);
    trägt das Merkmalfenster nur Lagen, bleibt es beim ersten.
    """
    for index, name in enumerate(names):
        if name.rpartition(" — ")[2].strip() not in POSITION_TITLES:
            return index
    return 0


def values_to_try(value: float) -> tuple[float, ...]:
    """Die Zahlen einer Maßänderung, in der Folge, in der sie versucht werden.

    Zuerst mehr (:func:`changed_value`), dann ebenso viel weniger — eine
    größere Kammer bricht durch eine dünne Wand, eine kleinere nie. Weniger
    nur, solange die Zahl positiv bleibt.
    """
    larger = changed_value(value)
    if abs(value) < 1e-9:
        return (larger,)
    smaller = round(value - max(abs(value) * 0.1, 0.5), 2)
    return (larger, smaller) if smaller > 0.0 else (larger,)


def mesh_digest(vertices: Any, faces: Any) -> str:
    """Der Abdruck eines Netzes: SHA-256 über Ecken und Dreiecke, wie im Audit."""
    import numpy as np

    return hashlib.sha256(
        np.ascontiguousarray(vertices).tobytes() + np.ascontiguousarray(faces).tobytes()
    ).hexdigest()


def body_digest(mesh: Any) -> str:
    """Der Abdruck eines Körpers — ein exakter über seine Vernetzung.

    Die Vernetzung ist im selben Prozess für denselben Körper dieselbe; über
    Prozesse hinweg wird nicht verglichen. Ein Körper, der sich nicht vernetzen
    lässt, hat keinen Abdruck (leere Zeichenkette) — der Abgleich nennt ihn
    dann ungleich, statt ihn zu übergehen.
    """
    from app.core.errors import AppError
    from app.core.geom.mesh import as_mesh_data

    try:
        data = as_mesh_data(mesh)
    except AppError:
        return ""
    return mesh_digest(data.raw.vertices, data.raw.faces)


def compared(
    states: Mapping[str, Mapping[str, str]], preview: Mapping[str, str] | None
) -> dict[str, bool | None]:
    """Was die Abdrücke über die Schritte sagen — ``None`` heißt: nicht prüfbar.

    ``states`` nennt je Schritt (:data:`STEPS`) die Abdrücke je Körper.
    """

    def same(first: str, second: str) -> bool | None:
        if first not in states or second not in states:
            return None
        return dict(states[first]) == dict(states[second])

    changed = same("01-import", "04-applied")
    preview_matches: bool | None = None
    if preview is not None and "04-applied" in states:
        applied = states["04-applied"]
        shown = {key: value for key, value in preview.items() if key in applied}
        preview_matches = bool(shown) and all(applied[key] == value for key, value in shown.items())
    return {
        "changed": None if changed is None else not changed,
        "undo_restores_import": same("01-import", "05-undo"),
        "redo_restores_applied": same("04-applied", "06-redo"),
        "preview_shows_result": preview_matches,
    }


def passed(checks: Mapping[str, bool | None]) -> bool:
    """Bestanden: jede prüfbare Aussage stimmt, Rückgängig und Wiederholen sind geprüft."""
    if checks.get("undo_restores_import") is None or checks.get("redo_restores_applied") is None:
        return False
    return all(value is not False for value in checks.values())


def case_stage(record: Mapping[str, Any]) -> str:
    """Die Stufe eines Falls nach seinem letzten Durchgang.

    ``done`` oder ``abweichung`` nur, wenn eine Änderung übernommen und geprüft
    wurde; trägt der letzte Durchgang einen Vermerk (kein Längenfeld, jede Zahl
    abgesagt), hat sich kein Merkmal ändern lassen (:data:`UNCHANGEABLE`). Am
    1x1-tray hieß das „abweichung“, obwohl kein Schritt etwas geprüft hatte.
    """
    if record.get("note"):
        return UNCHANGEABLE
    return "done" if passed(record.get("checks", {})) else "abweichung"


# --- Bericht ----------------------------------------------------------------------


def function_summary(case: Case, folder: Path, process: Mapping[str, Any]) -> dict[str, Any]:
    """Ein Funktions- oder Sprachfall in der Übersicht: wie weit er kam, was ihn aufhielt.

    Geurteilt wird hier nicht — das tut ``function_report`` aus dem Protokoll und
    den Urteilen. Die Übersicht sagt, ob der Lauf durchkam, wie die
    Dateiabnahme es für ihre Fälle sagt.
    """
    state = _read(folder / "bench.json")
    protocols = [_read(folder / "function.json")] if case.kind in ("function", "start") else []
    protocols += [_read(path) for path in sorted((folder / "surfaces").glob("*.json"))]
    return {
        "number": case.number,
        "relative": case.relative,
        "kind": case.kind,
        "row": case.row,
        "variant": case.variant.get("set", ""),
        "stage": state.get("stage", "nicht gelaufen"),
        "exit_code": process.get("exit_code"),
        "timeout": process.get("timeout"),
        "seconds": process.get("wall_s"),
        "findings": sum(len(protocol.get("findings") or []) for protocol in protocols),
        "unmeasured": sum(len(protocol.get("unmeasured") or {}) for protocol in protocols),
        "errors": [error for protocol in protocols for error in protocol.get("errors") or []]
        + ([state["harness_exception"]] if "harness_exception" in state else [])
        + [f"nicht beendet: {name}" for name in state.get("stragglers", [])]
        + ([process["crash"]] if process.get("crash") else []),
    }


def summary(out: Path, cases: Sequence[Case]) -> dict[str, Any]:
    """Alle Fälle in einer Übersicht — geschrieben als ``summary.json`` und ``summary.md``."""
    rows: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    for case in cases:
        folder = out / "cases" / f"{case.number:03d}"
        process = _read(folder / "process.json")
        if case.kind != "file":
            functions.append(function_summary(case, folder, process))
            continue
        result = _read(folder / "result.json")
        row = {
            "number": case.number,
            "relative": case.relative,
            "stage": result.get("stage", "nicht gelaufen"),
            "exit_code": process.get("exit_code"),
            "timeout": process.get("timeout"),
            "seconds": process.get("wall_s"),
            "objects": len(result.get("objects", [])),
            "features": sum(len(entry.get("features", {})) for entry in result.get("objects", [])),
            "groups": sum(len(entry.get("groups", [])) for entry in result.get("objects", [])),
            "feature": result.get("selection", {}).get("feature"),
            "checks": result.get("checks", {}),
            "passed": bool(result.get("checks")) and passed(result.get("checks", {})),
            "bores": [
                {"feature": bore.get("feature"), "passed": passed(bore.get("checks", {}))}
                for bore in result.get("bores", [])
            ],
            "errors": result.get("errors", [])
            + ([result["harness_exception"]] if "harness_exception" in result else [])
            + [f"nicht beendet: {name}" for name in result.get("stragglers", [])]
            + ([process["crash"]] if process.get("crash") else []),
        }
        rows.append(row)
    data = {
        "cases": len(rows),
        "ran": sum(1 for row in rows if row["exit_code"] is not None),
        "passed": sum(1 for row in rows if row["passed"]),
        "bores": sum(len(row["bores"]) for row in rows),
        "bores_passed": sum(1 for row in rows for bore in row["bores"] if bore["passed"]),
        "rows": rows,
        "function_cases": len(functions),
        "function_ran": sum(1 for row in functions if row["exit_code"] is not None),
        "function_complete": sum(
            1 for row in functions if row["exit_code"] == 0 and row["stage"] == "done"
        ),
        "functions": functions,
    }
    write_json(out / "summary.json", data)
    from tools.acceptance_summary import markdown

    (out / "summary.md").write_text(markdown(data), encoding="utf-8")
    return data


def _read(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


# --- Lauf --------------------------------------------------------------------------


def resumes(case: Case, process: Mapping[str, Any]) -> bool:
    """Ob ein schon gelaufener Fall beim nächsten ``run`` weiterläuft, ohne ``--again``.

    Nur ein abgebrochener Sprachfall: Er nimmt seine Flächen einzeln wieder auf
    (``function_language.LanguageFlow``) und verliert durch einen Abbruch nur die
    eine, an der er stand. Jeder andere Fall läuft nur mit ``--again`` neu.
    """
    return case.kind == "language" and (
        process.get("exit_code") != 0 or bool(process.get("timeout"))
    )


def case_timeout(case: Case, timeout: float) -> float:
    """Wie lange der Prozess eines Falls laufen darf: ``--timeout``, mindestens seine Frist."""
    if case.bores:
        return max(timeout, BORE_CASE_TIMEOUT)
    if case.kind == "function":
        return max(timeout, FUNCTION_CASE_TIMEOUT)
    if case.kind == "language":
        return max(timeout, LANGUAGE_CASE_TIMEOUT)
    return timeout


def run(
    out: Path,
    first: int,
    last: int,
    again: bool,
    timeout: float,
    screen: str = "",
    guard: Any = None,
) -> int:
    """Je Fall ein frischer Prozess mit eigenem Profil — wie im Audit.

    ``screen`` legt das Fenster auf einen Schirm (Nummer oder Name); ohne Angabe
    nimmt der Fall den ersten, der nicht der Hauptschirm ist. Mit Funktionsfällen
    misst der Lauf zuerst einmal den Referenzfaktor (§31, Entscheidung
    Koordinator 12.10.); alle Fälle dieses Laufs lesen ihn aus ``reference.json``.
    ``guard`` (``acceptance_guard.RunGuard``) hält Gesamtfrist und Siegel: vor
    jedem Fall geprüft, die Frist des Falls höchstens die verbleibende Zeit.
    """
    sys.path.insert(0, str(ROOT))
    from app.core.paths import isolate_secrets
    from app.core.process import no_error_dialogs, process_group_options, terminate_process_tree
    from tools.function_cases import RESTART_EXIT, most_restarts, prediction_wait_s

    cases = read_cases(out)
    if any(case.kind in ("function", "language") for case in cases):
        from tools.function_capture import measure_reference

        print(f"Referenzfaktor {measure_reference(out):.3f}", flush=True)
    failures = 0
    ran: int | None = None  # der zuletzt gelaufene Fall — ihn trifft ein Siegelbruch (RC2-7)
    for case in cases:
        if not first <= case.number <= last:
            continue
        folder = out / "cases" / f"{case.number:03d}"
        status = folder / "process.json"
        if status.exists() and not again and not resumes(case, _read(status)):
            continue
        if guard is not None and (stop := guard.stop_reason()):
            print(f"HALT vor [{case.number:03d}]: {stop}", flush=True)
            if getattr(guard, "broken", False) and ran is not None:
                print(f"Fall {ran:03d} lief unter geändertem Stand; seine Belege gelten nicht.")
            failures, ran = failures + 1, None  # gesagt; nach der Schleife nicht noch einmal
            break
        folder.mkdir(parents=True, exist_ok=True)
        print(f"START [{case.number:03d}] {case.relative}", flush=True)
        began = time.perf_counter()
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "child",
            "--out",
            str(out),
            "--case",
            str(case.number),
        ]
        if screen:
            command += ["--screen", screen]
        # Ein Sprachfall, der vor einer Fläche einen frischen Prozess braucht, läuft
        # gleich weiter — höchstens einmal je Zeile (FD-132).
        restarts = (
            most_restarts(read_rows(out).values(), case.row) if case.kind == "language" else 0
        )
        waiting = prediction_wait_s(case, read_rows(out).values())  # Vorhersagetor (V4)
        mode = "w"
        while True:
            with (
                (folder / "stdout.log").open(mode, encoding="utf-8") as stdout,
                (folder / "stderr.log").open(mode, encoding="utf-8") as stderr,
                no_error_dialogs(),
            ):
                # Im Fallordner, nie im Baum: Ein Speicherdialog, der nur einen
                # Dateinamen vorschlägt, schreibt in den Arbeitsordner (RC-10).
                process = subprocess.Popen(
                    command,
                    stdout=stdout,
                    stderr=stderr,
                    cwd=folder,
                    env=isolate_secrets({**os.environ, "PYTHONUTF8": "1"}),
                    **process_group_options(no_window=True),
                )
                try:
                    wanted = case_timeout(case, timeout) + waiting
                    code = process.wait(timeout=guard.case_limit(wanted) if guard else wanted)
                    timed_out = False
                except subprocess.TimeoutExpired:
                    terminate_process_tree(process)
                    code = process.wait()
                    timed_out = True
                except BaseException:
                    terminate_process_tree(process)
                    raise
            if code != RESTART_EXIT or timed_out or restarts <= 0:
                break
            restarts, mode = restarts - 1, "a"
        write_json(
            status,
            {
                "exit_code": code,
                "timeout": timed_out,
                "wall_s": time.perf_counter() - began,
                "pid": process.pid,
                "crash": crash_note(folder) if code != 0 or timed_out else "",
            },
        )
        failures += int(code != 0 or timed_out)
        wall = time.perf_counter() - began
        print(f"END [{case.number:03d}] exit={code} timeout={timed_out} {wall:.1f}s", flush=True)
        ran = case.number
    if guard is not None and ran is not None and (broken := guard.seal_reason()):
        print(f"HALT nach [{ran:03d}]: Fall {ran:03d} lief unter geändertem Stand. {broken}")
        failures += 1
    summary(out, cases)
    return 1 if failures else 0


def child(out: Path, number: int, screen: str = "") -> int:
    """Ein Fall im echten Fenster — eine Datei hier, eine Funktion oder Sprache im Prüfstand."""
    case = next(entry for entry in read_cases(out) if entry.number == number)
    folder = out / "cases" / f"{number:03d}"
    folder.mkdir(parents=True, exist_ok=True)
    # Vor dem ersten Import von ``app``: Die Anwendung liest die Nutzerordner beim Import.
    isolate(folder / "profile")
    sys.path.insert(0, str(ROOT))
    crash_records(folder)
    # Dasselbe Dateiprotokoll wie ``app.main``, im Profil des Falls (FD-163):
    # Ohne es stand die Wartezeile des Abbaus (FD-154) in keinem Protokoll. Unter
    # macOS liegt es sonst in ``~/Library/Logs``, außerhalb des Profils.
    from app.core.log import configure
    from app.core.paths import user_log_dir

    mac = sys.platform == "darwin"
    configure(to_console=False, directory=folder / "profile" / "logs" if mac else user_log_dir())
    if case.kind == "start":
        return start_child(out, case, folder)
    if case.kind != "file":
        return function_child(out, case, folder, screen)
    data: dict[str, Any] = {
        "case": asdict(case),
        "stage": "start",
        "errors": [],
        "questions": [],
        "dialogs": [],
        "states": {},
        "steps": [],
    }

    def persist() -> None:
        write_json(folder / "result.json", data)

    persist()
    # Das Register füllt sonst ``main`` vor dem Fenster — wie im Audit hier.
    from app.core.bootstrap import load_operations
    from app.ui.app import build_application
    from tools import function_setup
    from tools.window_bench import record_shutdown, shutdown_window

    exit_code = 0
    application: Any = None
    window: Any = None
    try:
        # Der feste Rahmen der Abnahme (RM-184): Das neue Projekt, das *Neues
        # Projekt* anlegt, nimmt Drucker und Material aus dem Profil
        # (:data:`PRINTER`, :data:`MATERIAL`), und die Ersteinrichtung ist erledigt.
        function_setup.write_profile(function_setup.Variant())
        load_operations()
        no_native_dialogs()
        application, window = build_application([])
        flow = WindowFlow(application, window, window.session, folder, data, persist)
        flow.prepare()
        flow.run(case)
    except Exception:
        data["harness_exception"] = traceback.format_exc()
        persist()
        exit_code = 1
    finally:
        stragglers: tuple[str, ...] = ()
        if window is not None:
            window.session.forget_changes()
            stragglers = shutdown_window(window, application)
        record_shutdown(data, persist, stragglers)
    return exit_code


def crash_records(folder: Path) -> None:
    """Ein abbrechender Fall nennt, wo und warum — in Dateien im Fallordner.

    :data:`STACK_LOG` trägt die Stapel aller Fäden bei einem Absturz und alle
    :data:`HANG_DUMP_S`, wenn der Fall steht — ohne py-spy (Erinnerung
    „abrisse-haenger-und-lebensdauer“). :data:`QT_LOG` trägt jede Meldung von Qt,
    Zeile für Zeile auf die Platte; dort steht ein ``qFatal``, das ``faulthandler``
    nicht sieht. Beides lebt bis zum Ende des Prozesses.
    """
    import faulthandler

    from PySide6.QtCore import qInstallMessageHandler

    stacks = (folder / STACK_LOG).open("w", encoding="utf-8", buffering=1)
    faulthandler.enable(file=stacks, all_threads=True)
    faulthandler.dump_traceback_later(HANG_DUMP_S, repeat=True, file=stacks)
    messages = (folder / QT_LOG).open("w", encoding="utf-8", buffering=1)

    def note(kind: Any, context: Any, message: str) -> None:
        messages.write(f"{kind.name} {message}\n")
        messages.flush()

    _HELD.extend([stacks, messages, note])
    qInstallMessageHandler(note)


def crash_note(folder: Path) -> str:
    """Was ein abgebrochener Fall zuletzt sagte: das letzte ``qFatal``, sonst sein Absturzstapel.

    Ein ``QtCriticalMsg`` ist eine Warnung, an der kein Fall stirbt; er nennt den
    Grund nur, wenn es weder ``qFatal`` noch Stapel gibt (Durchsicht welle4 C-L11).
    """
    qt = folder / QT_LOG
    lines = qt.read_text(encoding="utf-8", errors="replace").splitlines() if qt.is_file() else []
    fatal = [line for line in lines if line.startswith("QtFatalMsg")]
    if fatal:
        return fatal[-1]
    stacks = folder / STACK_LOG
    text = stacks.read_text(encoding="utf-8", errors="replace") if stacks.is_file() else ""
    start = max(text.rfind("Fatal Python error"), text.rfind("Windows fatal exception"))
    if start >= 0:
        return text[start:].strip()[:2000]
    critical = [line for line in lines if line.startswith("QtCriticalMsg")]
    return critical[-1] if critical else ""


def no_native_dialogs() -> None:
    """Qt-Dialoge statt der des Systems (B7): Systemdialoge lassen sich nicht bedienen.

    Den echten Systemdialog prüft Stufe C von Hand; so bleibt der Rest des Wegs in
    Stufe A, und ein Fall hängt nicht an einem Fenster, das kein Ereignis erreicht.
    """
    from PySide6.QtCore import QCoreApplication, Qt

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)


def version_info() -> dict[str, str]:
    """Commit und Anwendungsversion für das Protokoll (``version``: ``commit``, ``app``)."""
    from app.branding import APP_VERSION

    finished = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return {"commit": finished.stdout.strip(), "app": APP_VERSION}


def function_child(out: Path, case: Case, folder: Path, screen: str) -> int:
    """Ein Funktions- oder Sprachfall: Profil, Lizenz, Vorbedingungen, Fenster, Prüfstand.

    Die Reihenfolge ist die Aussage: Das Profil liegt vor dem Bau des Fensters,
    denn die Anwendung liest Sprache, Thema, Einheit und Drucker beim Start;
    Skalierung und Bewegung stehen vor der ``QApplication``; Lizenz und
    Vorbedingungen über die Nahtstellen der Suite nach dem Laden des Registers
    und vor dem Fenster.

    Zwei Dateien: ``function.json`` ist das Messprotokoll nach dem Schema von
    D0-U, ``bench.json`` hält, was nur den Lauf betrifft (Phase, Ausnahme,
    Abbau, erledigte Flächen). Ein Sprachfall schreibt kein ``function.json``,
    sondern je Fläche ein Protokoll unter ``surfaces/``.
    """
    from tools import function_bench, function_language, function_protocol, function_setup
    from tools.function_cases import RESTART_EXIT, install_user_data, rows_of, setup_of_case
    from tools.function_scenes import row_scenes

    variant = function_setup.Variant.of({**case.variant, **({"screen": screen} if screen else {})})
    if variant.scale != 1.0:
        os.environ["QT_SCALE_FACTOR"] = f"{variant.scale:g}"
    if not variant.motion:
        os.environ["SOLIDON3D_MOTION"] = "aus"
    rows = read_rows(out)
    scenes = out / "scenes"
    # Ein neuer Lauf beginnt ohne die Kopien und Sicherungen des vorigen (Review N2).
    state: dict[str, Any] = {
        "case": asdict(case),
        "stage": "start",
        "cleared": function_setup.fresh_case(folder),
    }
    version = version_info()

    def keep() -> None:
        write_json(folder / "bench.json", state)

    keep()
    data: dict[str, Any] | None = None
    if case.kind == "function":
        row = rows.get(case.row) or {"id": case.row}
        data = function_protocol.empty_protocol(row, variant.protocol(None, (0, 0)), version)

    def persist() -> None:
        if data is not None:
            write_json(folder / "function.json", data)
        keep()

    persist()
    from app.core.bootstrap import load_operations, load_user_parts
    from app.ui.app import build_application
    from tools.function_capture import run_reference_factor
    from tools.window_bench import record_shutdown, shutdown_window

    exit_code = 0
    application: Any = None
    window: Any = None
    try:
        # Vorbereitung im ``try``: Scheitert Profil, Lizenz oder eine
        # Vorbedingung, steht der Grund in ``bench.json`` und in der Übersicht.
        second = function_setup.case_scene(folder, scenes, function_setup.SECOND_SCENE)
        function_setup.write_profile(variant, recent=[second] if second is not None else [])
        # Eigene Bausteine und Spulen der Startszene und der Szene des Fehlfalls
        # liegen im Nutzerordner, bevor die Anwendung ihn liest (C-L4); im
        # Sprachfall die seiner Einrichtung (FD-101).
        owners = (
            row_scenes(row)
            if data is not None
            else setup_of_case(rows.values(), case.row).user_data
        )
        state["user_data"] = [path for key in owners for path in install_user_data(key)]
        load_operations()
        # Wie ``app.main``: die eigenen Bausteine aus dem Nutzerordner, ihre
        # Ladebefunde in den Bericht. Ohne sie lag ein Baustein im Ordner und
        # stand nie im Register (FD-101, *Gespeicherte Bausteine behalten*).
        user_findings = load_user_parts()
        no_native_dialogs()
        function_setup.apply_licence(variant.licence)
        state["preconditions_applied"] = function_setup.apply_preconditions(variant.preconditions)
        state["reference_factor"] = run_reference_factor(out)
        application, window = build_application([])
        if user_findings:
            window.report.add_findings(list(user_findings))
        flow: Any
        if data is None:
            package_rows = rows_of(rows.values(), case.row)
            flow = function_language.LanguageFlow(
                application, window, folder, state, keep, package_rows, variant, scenes, version
            )
        else:
            flow = function_bench.FunctionFlow(
                application, window, folder, data, persist, row, variant, scenes, state, out
            )
            flow.prepare()
        if flow.run() is False:
            # Vor einer Fläche braucht der Sprachfall einen neuen Prozess (FD-132).
            state["stage"] = "neustart"
            exit_code = RESTART_EXIT
        else:
            state["stage"] = "done"
    except Exception:
        state["harness_exception"] = traceback.format_exc()
        persist()
        exit_code = 1
    finally:
        stragglers: tuple[str, ...] = ()
        if window is not None:
            window.session.forget_changes()
            stragglers = shutdown_window(window, application)
        record_shutdown(state, persist, stragglers)
    return exit_code


def start_child(out: Path, case: Case, folder: Path) -> int:
    """Ein Startfall: Profil, Zustand „Demo abgelaufen“, dann ``app.ui.app.main`` selbst.

    Kein ``build_application``: Das Starttor steht in ``main`` vor dem Fenster
    (``function_start.StartFlow``). ``function.json`` ist das Protokoll nach dem
    Schema von D0-U, ``bench.json`` der Lauf samt Ausgang von ``main``.
    """
    from tools import function_protocol, function_setup, function_start
    from tools.window_bench import record_shutdown, wait_for_workers

    variant = function_setup.Variant.of(case.variant)
    row = read_rows(out).get(case.row) or {"id": case.row}
    state: dict[str, Any] = {
        "case": asdict(case),
        "stage": "start",
        "cleared": function_setup.fresh_case(folder),
    }
    data = function_protocol.empty_protocol(row, variant.protocol(None, (0, 0)), version_info())

    def persist() -> None:
        write_json(folder / "function.json", data)
        write_json(folder / "bench.json", state)

    persist()
    exit_code = 0
    try:
        function_setup.write_profile(variant)
        function_setup.apply_licence(variant.licence)
        no_native_dialogs()
        state["main_exit_code"] = function_start.StartFlow(data, persist).run()
        state["stage"] = "done"
    except Exception:
        state["harness_exception"] = traceback.format_exc()
        exit_code = 1
    finally:
        # Kein Fenster mehr, aber vielleicht ein Arbeiter: dieselbe Wartestelle
        # und derselbe benannte Ausgang wie in den Fensterfällen (RF-11, RF-18).
        record_shutdown(state, persist, wait_for_workers())
    return exit_code


class WindowFlow:
    """Die Schritte eines Dateifalls am Fenster; jeder schreibt sein Bild und seine Abdrücke.

    Jede Handlung ist ein Eingabeereignis über ``function_walk.Walk`` — Klick
    mit Probe an der Stelle, die ``next_click`` nennt, Tippen, Taste (B5). Was
    hier direkt am Fenster gelesen wird — Abdrücke, Merkmale, Feldwerte —, ist
    Ablesen; ``tests/test_function_guard.py`` hält per AST, dass diese Klasse
    keine Bedienung umgeht.
    """

    def __init__(
        self,
        application: Any,
        window: Any,
        session: Any,
        folder: Path,
        data: dict[str, Any],
        persist: Callable[[], None],
    ) -> None:
        from tools.function_walk import QtPorts, Walk

        self.application = application
        self.window = window
        self.session = session
        self.folder = folder
        self.data = data
        self.persist = persist
        self.began = time.perf_counter()
        self.ports = QtPorts(window, self.began)
        self.walker = Walk(self.ports, data.setdefault("steps", []), self.began)
        self._answering = False

    # Warten und Aufnehmen ---------------------------------------------------------

    def pump(self, seconds: float = 0.3) -> None:
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            self.application.processEvents()
            time.sleep(0.01)

    def wait_for(self, done: Callable[[], bool], label: str, timeout: float = STEP_TIMEOUT) -> None:
        began = time.perf_counter()
        while time.perf_counter() - began < timeout:
            self.application.processEvents()
            if done():
                self.pump()
                self.data.setdefault("events", []).append(
                    {"step": label, "seconds": time.perf_counter() - began}
                )
                self.persist()
                return
            if self.data["errors"]:
                raise RuntimeError(f"{label}: {self.data['errors'][-1]}")
            time.sleep(0.01)
        raise TimeoutError(label)

    def drive(self, label: str, steps: Sequence[Any], timeout: float = STEP_TIMEOUT) -> None:
        """Fährt Schritte über den Automaten; ein Fund oder Fehler bricht den Fall ab.

        Ein Fenster aus ``pump`` schließt er wie eins seiner Schritte (FD-173)."""
        self.walker.phase = label
        from tools.function_machine import StepMachine, drive, nested_since_now, qt_schedule

        machine = StepMachine(
            qt_schedule,
            time.perf_counter,
            unstick=self._escape,
            on_stuck=lambda: self._stuck(label),
            nested=nested_since_now(),
        )
        drive(machine, steps, lambda: self.pump(0.005), time.perf_counter, timeout)
        if machine.finding is not None:
            raise RuntimeError(f"{label}: {machine.finding}")
        if machine.error is not None:
            if "Zeitgrenze" in machine.error:
                raise TimeoutError(f"{label}: {machine.error}")
            raise RuntimeError(f"{label}: {machine.error}")

    def new_result(self, previous: Any, label: str) -> None:
        self.wait_for(
            lambda: (
                self.session.last_result is not None
                and self.session.last_result is not previous
                and not self.session.busy
            ),
            label,
        )

    def _escape(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        widget = QApplication.activePopupWidget() or QApplication.activeModalWidget()
        if widget is not None:
            QTest.keyClick(widget, Qt.Key.Key_Escape)

    def _stuck(self, label: str) -> None:
        """Escape schloss das Fenster nicht: welches es war, steht im Ergebnis (Review L12)."""
        from PySide6.QtWidgets import QApplication

        widget = QApplication.activePopupWidget() or QApplication.activeModalWidget()
        if widget is not None:
            self.data["errors"].append(
                f"{label}: {type(widget).__name__} „{widget.windowTitle()}“ ließ sich"
                " nicht mit Escape schließen"
            )
            self.persist()

    def _sweep(self) -> None:
        """Ein modales Fenster: die Rückfrage mit ihrem Hauptknopf beantworten, sonst Escape.

        **Ein Zeitgeber**, wie im Audit: Ein ``exec()`` aus einem Ereignis heraus
        läuft in einer eigenen Schleife, und die Warteschleife hier käme erst
        nach seinem Ende wieder dran. Mit Riegel: Der Klick läuft selbst durch
        Ereignisse, und ein zweiter Durchgang bediente dasselbe Fenster zweimal.
        """
        from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton

        modal = QApplication.activeModalWidget()
        if modal is None or self._answering:
            return
        self._answering = True
        try:
            record: dict[str, Any] = {
                "class": type(modal).__name__,
                "title": modal.windowTitle(),
                "text": [label.text() for label in modal.findChildren(QLabel)],
                "buttons": [button.text() for button in modal.findChildren(QPushButton)],
            }
            self.data["dialogs"].append(record)
            if type(modal).__name__ == "AskDialog":
                lists = modal.findChildren(QListWidget)
                choices = (
                    [lists[0].item(row).text() for row in range(lists[0].count())] if lists else []
                )
                current = lists[0].currentItem() if lists else None
                answer = current.text() if current is not None else ""
                self.data["questions"].append(
                    {"question": " ".join(record["text"]), "choices": choices, "answer": answer}
                )
                try:
                    self.walker.click_once("dialog.accept")
                except Exception as problem:
                    self.data["errors"].append(f"Rückfrage nicht beantwortet: {problem}")
                    self._escape()
                return
            self._escape()
        finally:
            self._answering = False

    def shot(self, label: str) -> dict[str, str]:
        """Bild des Fensters und Abdruck je Körper für diesen Schritt."""
        self.pump()
        picture = self.window.screen().grabWindow(int(self.window.winId()))
        picture.save(str(self.folder / f"{label}.png"))
        result = self.session.last_result
        digests = {
            object_id: body_digest(entry.mesh) for object_id, entry in result.scene.objects.items()
        }
        self.data["states"][label] = digests
        self.persist()
        return digests

    # Die Schritte -----------------------------------------------------------------

    def prepare(self) -> None:
        """Wache anlegen, Fenster zeigen, *Neues Projekt* klicken."""
        from PySide6.QtCore import QTimer

        from tools.function_machine import Step

        self.session.failed.connect(
            lambda error: self.data["errors"].append(str(error)), self.window
        )
        self.session.importFailed.connect(
            lambda error: self.data["errors"].append(str(error)), self.window
        )
        self.sweeper = QTimer(self.window)
        self.sweeper.timeout.connect(self._sweep)
        self.sweeper.start(250)
        self.window.showMaximized()
        self.pump()
        previous = self.session.last_result
        self.drive(
            "Neues Projekt",
            [
                self.walker.step("start.new"),
                Step(
                    "neues Projekt steht",
                    lambda machine: None,
                    ready=lambda: (
                        self.session.last_result is not None
                        and self.session.last_result is not previous
                        and not self.session.busy
                    ),
                    timeout_s=STEP_TIMEOUT,
                ),
            ],
        )
        self.session.forget_changes()

    def run(self, case: Case) -> None:
        previous = self.session.last_result
        self.data["stage"] = "import"
        self.persist()
        began = time.perf_counter()
        self.window.open_path(Path(case.path))
        self.new_result(previous, "Import")
        self.data["import_s"] = time.perf_counter() - began
        self.shot("01-import")
        self.data["stage"] = "recognition"
        self.data["objects"] = self._recognition()
        self.persist()
        objects = {entry["id"]: entry["features"] for entry in self.data["objects"]}
        anchors = {entry["id"]: group_anchors(entry["groups"]) for entry in self.data["objects"]}
        if case.bores:
            self.data["bores"] = []
            for object_id, features in sorted(objects.items()):
                for feature_id in bore_ids(features):
                    prefix = f"bore-{feature_id}-"
                    try:
                        record = self._cycle(object_id, feature_id, prefix, restore=True)
                    except (TimeoutError, RuntimeError) as problem:
                        # Die Bohrung, an der der Fall hängen blieb, steht im
                        # Bericht — nicht nur die, die vorher bestanden.
                        self.data["bores"].append(
                            {"object": object_id, "feature": feature_id, "error": str(problem)}
                        )
                        self.persist()
                        raise
                    self.data["bores"].append(record)
                    self.persist()
        # Die Absagen aller versuchten Merkmale, nicht nur die des letzten.
        refusals: list[dict[str, Any]] = []

        def attempt(chosen: tuple[str, str]) -> dict[str, Any]:
            record = self._cycle(*chosen, "", restore=False)
            refusals.extend({"feature": chosen[1], **entry} for entry in record.get("refusals", []))
            return record

        tried, cycle = first_with_a_length_field(ranked_features(objects, anchors), attempt)
        if cycle is None:
            self.data["stage"] = "kein Merkmal"
            self.persist()
            return
        self.data["tried"] = tried
        self.data["selection"] = cycle["selection"]
        self.data["refusals"] = refusals
        self.data["checks"] = cycle["checks"]
        self.data["stage"] = case_stage(cycle)
        self.persist()

    def _recognition(self) -> list[dict[str, Any]]:
        from app.core.geom.mesh import as_mesh_data
        from app.core.perceive.groups import functional_groups

        found = []
        for object_id, entry in self.session.last_result.scene.objects.items():
            groups = (
                functional_groups(entry.features, as_mesh_data(entry.mesh))
                if entry.features
                else ()
            )
            found.append(
                {
                    "id": object_id,
                    "name": str(entry.name),
                    "triangles": entry.mesh.triangle_count,
                    "watertight": entry.mesh.is_watertight,
                    "features": {
                        feature_id: feature.kind for feature_id, feature in entry.features.items()
                    },
                    "groups": [f"{group.kind}/{group.variant}:{group.anchor}" for group in groups],
                }
            )
        return found

    def _fields(self) -> list[Any]:
        """Die sichtbaren, freien Längenfelder des Merkmalfensters, in ihrer Folge."""
        from app.ui.labels import LengthSpin

        return [
            spin
            for spin in self.window.feature_panel.findChildren(LengthSpin)
            if spin.isVisible() and spin.isEnabled()
        ]

    def _cycle(
        self, object_id: str, feature_id: str, prefix: str, *, restore: bool
    ) -> dict[str, Any]:
        """Auswahl, Maßänderung, Vorschau, Übernehmen, Rückgängig, Wiederholen an einem Merkmal."""
        from app.core.guides import TARGET_PROPERTY

        record: dict[str, Any] = {"object": object_id, "feature": feature_id}
        states: dict[str, dict[str, str]] = {}
        states["01-import"] = self.shot(f"{prefix}01-import")
        self.drive(f"{prefix}Auswahl", [self.walker.step(f"tree.row:{object_id}.{feature_id}")])
        self.pump(0.5)
        states["02-selection"] = self.shot(f"{prefix}02-selection")
        fields = self._fields()
        record["selection"] = {
            "object": object_id,
            "feature": feature_id,
            "fields": [
                {
                    "name": spin.accessibleName(),
                    "value": spin.value_mm(),
                    "target": str(spin.property(TARGET_PROPERTY) or ""),
                }
                for spin in fields
            ],
        }
        if not fields:
            record["checks"] = {
                "changed": None,
                "undo_restores_import": None,
                "redo_restores_applied": None,
                "preview_shows_result": None,
            }
            record["note"] = NO_LENGTH_FIELD
            return record
        chosen = record["selection"]["fields"][
            size_field_first([spin.accessibleName() for spin in fields])
        ]
        if not chosen["target"]:
            raise RuntimeError(
                f"{prefix}Feld „{chosen['name']}“ trägt kein Wortschatzkennzeichen"
                " — ohne Ziel kein Klick (Plan D0, Abschnitt 2.1, feature.field:)"
            )
        before = float(chosen["value"])
        preview: dict[str, str] | None = None
        taken: float | None = None
        refusals: list[dict[str, Any]] = []
        for after in values_to_try(before):
            outcome, detail = self._previewed(chosen["target"], after, f"{prefix}Vorschau {after}")
            if outcome == "shown":
                taken, preview = after, detail
                break
            refusals.append({"value": after, "reason": detail})
        record["selection"]["changed"] = {
            "name": chosen["name"],
            "target": chosen["target"],
            "before": before,
            "after": taken,
        }
        if refusals:
            record["refusals"] = refusals
        if taken is None:
            # Keine Zahl trägt: zurück zum gemessenen Wert, getippt wie jede
            # andere, und das nächste Merkmal ist dran
            # (:func:`first_with_a_length_field`).
            self.drive(f"{prefix}zurück", self._typing(chosen["target"], before))
            self.pump(0.5)
            record["checks"] = {
                "changed": None,
                "undo_restores_import": None,
                "redo_restores_applied": None,
                "preview_shows_result": None,
            }
            record["note"] = REFUSED
            return record
        states["03-preview"] = self.shot(f"{prefix}03-preview")
        previous = self.session.last_result
        self.drive(f"{prefix}Übernehmen", [self.walker.step("feature.apply")])
        self.new_result(previous, f"{prefix}Übernehmen")
        states["04-applied"] = self.shot(f"{prefix}04-applied")
        previous = self.session.last_result
        self.drive(f"{prefix}Rückgängig", [self._key(self._undo_keys(), "Rückgängig")])
        self.new_result(previous, f"{prefix}Rückgängig")
        states["05-undo"] = self.shot(f"{prefix}05-undo")
        previous = self.session.last_result
        self.drive(f"{prefix}Wiederholen", [self._key(self._redo_keys(), "Wiederholen")])
        self.new_result(previous, f"{prefix}Wiederholen")
        states["06-redo"] = self.shot(f"{prefix}06-redo")
        record["states"] = states
        record["preview"] = preview
        record["checks"] = compared(states, preview)
        if restore:
            previous = self.session.last_result
            self.drive(f"{prefix}zurück zum Import", [self._key(self._undo_keys(), "Rückgängig")])
            self.new_result(previous, f"{prefix}zurück zum Import")
        return record

    def _undo_keys(self) -> Any:
        from PySide6.QtGui import QKeySequence

        return QKeySequence(QKeySequence.StandardKey.Undo)

    def _redo_keys(self) -> Any:
        """Die Wiederholen-Taste, die im Menü steht (``shortcut_schemes.redo_keys``)."""
        from PySide6.QtGui import QKeySequence

        from app.ui.shortcut_schemes import redo_keys

        return redo_keys(sys.platform, QKeySequence(QKeySequence.StandardKey.Redo))[0]

    def _key(self, sequence: Any, label: str) -> Any:
        from tools.function_machine import SETTLE_MS, Step

        def act(machine: Any) -> None:
            self.walker.record({"target": label, "key": sequence.toString()})
            self.ports.keys(sequence)

        return Step(f"Taste {label}", act, settle_ms=SETTLE_MS)

    def _typing(self, target: str, value: float) -> list[Any]:
        """Ins Feld klicken, alles markieren, die Zahl in der Anzeigeeinheit tippen.

        Markiert und getippt wird nur, wenn der Fokus im Feld liegt
        (``function_walk.focus_check``, Review M13).
        """
        from PySide6.QtGui import QKeySequence

        from app.ui import guide_targets
        from app.ui.labels import display_unit
        from tools.function_machine import SETTLE_MS, Step
        from tools.function_walk import focus_check, typed_number

        text = typed_number(value, display_unit())

        def field() -> Any:
            try:
                return guide_targets.widget_for(self.window, target)
            except LookupError:
                return None

        def mark(machine: Any) -> None:
            focus_check(field(), target)
            keys = QKeySequence(QKeySequence.StandardKey.SelectAll)
            self.walker.record({"target": "alles markieren", "key": keys.toString()})
            self.ports.keys(keys)

        def type_it(machine: Any) -> None:
            focus_check(field(), target)
            self.walker.record({"target": target, "typed": text})
            self.ports.type_text(text)

        return [
            self.walker.step(target),
            Step("alles markieren", mark, settle_ms=SETTLE_MS),
            Step(f"tippen {text}", type_it, settle_ms=SETTLE_MS),
        ]

    def _previewed(self, target: str, value: float, label: str) -> tuple[str, Any]:
        """Eine Zahl ins Feld tippen und warten, bis die Vorschau sie zeigt oder absagt.

        Abgelesen, wo der Kunde es sieht: ``("shown", Abdrücke)``, wenn das Band
        die Legende einer **neuen** Differenz trägt; ``("refused", Satz)``, wenn
        *Übernehmen* gesperrt ist und seinen Grund nennt (Kurzhilfe und
        zugängliche Beschreibung, dieselbe Stelle, an der auch die Grenzablehnung
        eines Feldes steht); ``("none", …)`` ohne beides bis :data:`STEP_TIMEOUT`.
        Die Absage der vorigen Zahl gilt nicht für diese: Mit dem Tippen fällt sie,
        bevor das Warten beginnt.
        """
        from app.ui import guide_targets

        viewport = self.window.viewport
        shown = viewport.difference
        heard: dict[str, str] = {}

        def settled() -> bool:
            try:
                button = guide_targets.widget_for(self.window, "feature.apply")
                banner = guide_targets.widget_for(self.window, "preview.banner")
            except LookupError:
                return False
            reason = button.accessibleDescription() or button.toolTip()
            if not button.isEnabled() and reason:
                heard["refused"] = reason
                return True
            difference = viewport.difference
            legend = getattr(banner, "legend", None)
            return (
                difference is not None
                and difference is not shown
                and banner.isVisible()
                and legend is not None
                and legend.isVisible()
            )

        self.drive(f"{label} tippen", self._typing(target, value))
        try:
            self.wait_for(settled, label, STEP_TIMEOUT)
        except TimeoutError:
            return "none", "keine Vorschau"
        if "refused" in heard:
            return "refused", heard["refused"]
        difference = viewport.difference
        return "shown", {
            key: body_digest(entry.result.mesh)
            for key, entry in difference.entries.items()
            if entry.result is not None
        }


# --- Einstieg -------------------------------------------------------------------------


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--out", required=True, type=Path)
    origin = inventory.add_mutually_exclusive_group(required=True)
    origin.add_argument("--manifest", type=Path)
    origin.add_argument("--source", type=Path)
    origin.add_argument("--functions", action="store_true")
    inventory.add_argument("--package", action="append", default=[])
    inventory.add_argument("--rows", default="")
    inventory.add_argument("--variants", default="basis")
    inventory.add_argument("--phases", default="")
    running = commands.add_parser("run")
    running.add_argument("--out", required=True, type=Path)
    running.add_argument("--first", type=int, default=1)
    running.add_argument("--last", type=int, default=10**6)
    running.add_argument("--again", action="store_true")
    running.add_argument("--timeout", type=float, default=CASE_TIMEOUT)
    running.add_argument("--screen", default="")
    running.add_argument("--total", type=float, default=None)
    running.add_argument("--binding", type=Path, default=None)
    one = commands.add_parser("child")
    one.add_argument("--out", required=True, type=Path)
    one.add_argument("--case", required=True, type=int)
    one.add_argument("--screen", default="")
    bar = commands.add_parser("menubar")
    bar.add_argument("--out", required=True, type=Path)
    sealing = commands.add_parser("seal")
    sealing.add_argument("--out", required=True, type=Path)
    reporting = commands.add_parser("report")
    reporting.add_argument("--out", required=True, type=Path)
    reporting.add_argument("--package", action="append", default=[])
    reporting.add_argument("--verdicts", type=Path, default=None)
    reporting.add_argument("--checklist", type=Path, default=None)
    reporting.add_argument("--runs", type=Path, default=None)
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    # Dieser Baum vorn: Als Skript steht sonst ``tools/`` an erster Stelle, und
    # ``import app`` träfe die Installation der ``.venv`` — womöglich ein
    # anderer Arbeitsbaum (Erinnerung „sonden-bauen“).
    sys.path.insert(0, str(ROOT))
    out = outside_the_repository(arguments.out)
    if arguments.command == "inventory":
        # **Ein leerer Bestand ist keine Abnahme**: Mit ``--source`` auf
        # ``audit.py`` statt auf einen Ordner zählte der Bestand null Fälle und
        # endete mit 0 — ein Lauf darüber hätte nichts geprüft und nichts gesagt.
        if arguments.source is not None and not arguments.source.is_dir():
            print(
                f"{arguments.source} ist kein Ordner: --source nimmt einen Bestand wie"
                " F:\\3D Dateien, --manifest das Manifest des Dateiaudits.",
                file=sys.stderr,
                flush=True,
            )
            return 2
        if arguments.functions:
            try:
                cases = function_inventory(
                    out,
                    packages=arguments.package,
                    row_ids=[entry for entry in arguments.rows.split(",") if entry],
                    variant_sets=[entry for entry in arguments.variants.split(",") if entry],
                    phases=[entry for entry in arguments.phases.split(",") if entry],
                )
            except ValueError as problem:
                print(str(problem), file=sys.stderr, flush=True)
                return 2
        else:
            cases = (
                cases_from_manifest(arguments.manifest)
                if arguments.manifest
                else cases_from_source(arguments.source, out)
            )
        if not cases:
            print("Kein Fall gefunden — der Bestand ist leer.", file=sys.stderr, flush=True)
            return 1
        write_json(out / "cases.json", [asdict(case) for case in cases])
        kinds = {kind: sum(case.kind == kind for case in cases) for kind in CASE_KINDS}
        counted = ", ".join(f"{kind} {count}" for kind, count in kinds.items() if count)
        print(
            f"{len(cases)} Fälle ({counted}),"
            f" davon {sum(case.bores for case in cases)} mit jeder Bohrung",
            flush=True,
        )
        return 0
    if arguments.command == "run":
        from tools.acceptance_guard import RunGuard

        try:
            guard = RunGuard(arguments.total, arguments.binding)
        except (ValueError, RuntimeError) as problem:
            print(problem, file=sys.stderr, flush=True)
            return 2
        return run(
            out,
            arguments.first,
            arguments.last,
            arguments.again,
            arguments.timeout,
            arguments.screen,
            guard,
        )
    if arguments.command == "child":
        return child(out, arguments.case, arguments.screen)
    if arguments.command == "menubar":
        return menubar_child(out)
    if arguments.command == "seal":
        # Das Siegel des Laufs für ``[[run]].seal`` der Urteile (RC2-1).
        from tools.function_verdict_rules import seal_run

        try:
            print(seal_run(out), flush=True)
        except OSError as problem:
            print(problem, file=sys.stderr, flush=True)
            return 2
        return 0
    cases = read_cases(out)
    data = summary(out, cases)
    print(f"{data['passed']} von {data['cases']} Dateifällen bestanden", flush=True)
    if not any(case.kind != "file" for case in cases):
        return 0
    from tools import function_report

    return function_report.write_all(
        out,
        packages=arguments.package,
        verdicts=arguments.verdicts,
        checklist=arguments.checklist,
        runs=arguments.runs,
    )


if __name__ == "__main__":
    sys.exit(main())
