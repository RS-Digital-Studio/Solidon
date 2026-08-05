"""Übergabe an den Slicer (Bauplan §29, §28.1).

Formwerk baut keinen G-Code-Slicer (§22) — es bedient einen. Der Unterschied
zum Wechseln in ein anderes Programm ist, dass die Einstellungen hier bleiben:
Formwerk schreibt sie als Profil, ruft den Slicer im Konsolenmodus, und liest
die entstandene Datei mit :mod:`app.core.slice.gcode` wieder ein. Wer das
benutzt, sieht den Slicer nicht mehr.

Was Formwerk **nicht** mitbringt, ist das Maschinenwissen: Bettform,
Anfahrwege, Start- und Endcode, die Eigenheiten einer Kinematik. Das steht in
den Profilen, die der Slicer mitbringt, und genau dort bleibt es. Formwerk
setzt sein Profil darauf — es überschreibt, es ersetzt nicht.

Ein Lauf ist abgesichert wie der OpenSCAD-Lauf (§32): feste Argumentliste,
kein Shell, eigener Arbeitsordner, Zeitlimit. Der Unterschied ist, dass hier
kein fremder Quelltext läuft, sondern ein Programm auf eine Datei zeigt.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from app.core.errors import OPEN_SETTINGS, Action, ExternalToolError
from app.core.export import slicer_keys
from app.core.export.slicer_keys import SlicerFlavour
from app.core.knowledge.print_settings import read_path
from app.core.log import get_logger
from app.core.slice import gcode
from app.core.types import Finding, PrintSettings, Profile
from app.i18n import _

_log = get_logger(__name__)

#: Slicen dauert länger als alles andere, was Formwerk außer Haus gibt. Fünf
#: Minuten sind großzügig für ein Teil und immer noch eine Grenze.
TIMEOUT_SECONDS: Final = 300.0

#: Wonach im Ausgabeordner gesucht wird — die Slicer benennen selbst.
GCODE_SUFFIXES: Final = (".gcode", ".gco", ".g")


@dataclass(frozen=True, slots=True)
class SlicerSetup:
    """Welcher Slicer, und worauf seine Profile aufsetzen.

    ``machine_profile`` und ``base_process`` sind Namen aus dem Bestand des
    Slicers, keine Pfade — sie reisen so auch in eine Projektdatei, ohne gegen
    Regel 12 zu verstoßen.
    """

    executable: Path
    flavour: SlicerFlavour
    machine_profile: str = ""
    base_process: str = ""

    @property
    def name(self) -> str:
        return self.executable.stem


def detect(executable: Path | str) -> SlicerSetup:
    """Was für ein Slicer das ist. Erkennt an seinem Namen (§29)."""
    path = Path(executable)
    flavour = slicer_keys.flavour_of(path.name)
    if flavour is None:
        raise ExternalToolError(
            tool=path.name,
            detail=_("Formwerk kennt die Kommandozeile dieses Programms nicht."),
            suggestions=(
                Action(id="choose_slicer", label=_("Einen anderen Slicer auswählen.")),
                Action(id="export_only", label=_("Nur exportieren und selbst slicen.")),
            ),
        )
    return SlicerSetup(executable=path, flavour=flavour)


def as_mapping(settings: PrintSettings, flavour: SlicerFlavour) -> dict[str, str]:
    """Die Einstellungen in der Sprache dieses Slicers (§29).

    Ohne Datei und ohne Aufruf — die Oberfläche zeigt damit an, was übergeben
    würde, und die Tests prüfen die Zuordnung, ohne dass ein Slicer installiert
    sein muss. Alle Profile zusammen, weil die Gegenprobe die Druckdatei als
    Ganzes liest und dort nicht mehr steht, aus welchem Profil ein Wert kam.
    """
    written: dict[str, str] = {}
    for entry in slicer_keys.TABLES[flavour]:
        written[entry.key] = entry.write(read_path(settings, entry.path))
    return _only_chosen_adhesion(written, settings, flavour)


def by_section(
    settings: PrintSettings, flavour: SlicerFlavour
) -> dict[slicer_keys.ProfileSection, dict[str, str]]:
    """Dieselben Werte, getrennt nach dem Profil, in das sie gehören (§29).

    Der Unterschied ist nicht kosmetisch: die Orca-Familie nimmt einen Wert
    nur an, wenn er im richtigen Profil steht. Eine Düsentemperatur im
    Prozessprofil wird stillschweigend übergangen — kein Fehler, keine
    Warnung, gedruckt wird mit dem, was zuletzt im Slicer eingestellt war.
    """
    complete = as_mapping(settings, flavour)
    split: dict[slicer_keys.ProfileSection, dict[str, str]] = {}
    for entry in slicer_keys.TABLES[flavour]:
        if entry.key in complete:
            split.setdefault(entry.section, {})[entry.key] = complete[entry.key]
    return split


def _only_chosen_adhesion(
    written: dict[str, str], settings: PrintSettings, flavour: SlicerFlavour
) -> dict[str, str]:
    """Nullt die Maße der Haftungsarten, die nicht gewählt sind.

    ``skirt_loops``, ``brim_width`` und ``raft_layers`` sind Maße *ihrer
    jeweiligen Art*, keine unabhängigen Schalter — aber die Slicer lesen sie
    als solche. Wer alle drei schreibt, bekommt alle drei: ein Raft unter
    einem Teil, für das „Skirt" eingestellt war.

    Das ist kein Schönheitsfehler. Ein ungewollter Raft kostet Material, Zeit
    und die Unterseite des Teils, und er fällt erst auf der Platte auf —
    hier gefunden, weil zwei kleine Teile plötzlich nicht mehr nebeneinander
    passten.
    """
    kind = settings.adhesion.kind
    for wanted, keys in slicer_keys.ADHESION_KEYS[flavour].items():
        if wanted == kind:
            continue
        for key in keys:
            if key in written:
                written[key] = "0"
    return written


def _machine_keys(profile: Profile, flavour: SlicerFlavour) -> dict[str, str]:
    """Was der Slicer über die Maschine wissen muss, wenn kein Profil greift.

    Nur für ``prusa``: dort ist eine ``.ini`` eigenständig lauffähig, sobald
    Düse und Bettform darin stehen. Orca und Cura laden ohnehin ein
    Maschinenprofil, und dem hier hineinzureden hieße, ihre Anfahrwege und
    ihren Startcode zu überschreiben.
    """
    if flavour != "prusa":
        return {}
    printer = profile.printer
    width, depth, height = printer.build_volume
    return {
        "nozzle_diameter": f"{printer.nozzle_diameter:g}",
        "bed_shape": f"0x0,{width:g}x0,{width:g}x{depth:g},0x{depth:g}",
        "max_print_height": f"{height:g}",
    }


@dataclass(frozen=True, slots=True)
class SlicerConfig:
    """Die Profildateien für einen Lauf.

    ``process`` trägt bei ``prusa`` und ``cura`` alles; bei der Orca-Familie
    steht daneben ``filament``, weil sie Werte nur aus dem Profil annimmt, in
    das sie gehören.
    """

    process: Path
    filament: Path | None = None


def write_config(
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    directory: Path,
) -> SlicerConfig:
    """Schreibt die Profile, die der Slicer gleich lädt."""
    split = by_section(settings, setup.flavour)
    values = {key: value for section in split.values() for key, value in section.items()}
    values |= _machine_keys(profile, setup.flavour)

    if setup.flavour == "prusa":
        target = directory / "formwerk.ini"
        lines = [f"# {settings.title} — von Formwerk geschrieben, nicht von Hand"]
        lines += [f"{key} = {value}" for key, value in sorted(values.items())]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return SlicerConfig(process=target)

    if setup.flavour == "orca":
        target = directory / "formwerk_process.json"
        target.write_text(
            json.dumps(
                _orca_process(split.get("process", {}), settings, setup),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        filament = directory / "formwerk_filament.json"
        filament.write_text(
            json.dumps(
                _orca_filament(split.get("filament", {}), settings, profile),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return SlicerConfig(process=target, filament=filament)

    target = directory / "formwerk_cura.txt"
    target.write_text(
        "\n".join(f"{key}={value}" for key, value in sorted(values.items())) + "\n",
        encoding="utf-8",
    )
    return SlicerConfig(process=target)


def _orca_process(
    values: dict[str, str],
    settings: PrintSettings,
    setup: SlicerSetup,
) -> dict[str, object]:
    """Das Prozessprofil für die Orca-Familie.

    Diese Slicer nehmen kein Prozessprofil an, das nicht zum Drucker passt —
    sie brechen mit „process not compatible with printer" ab, bevor sie das
    Modell überhaupt ansehen. Die Kompatibilität steht in Feldern, die
    Formwerk nicht kennt und nicht erfinden sollte (``compatible_printers``,
    ``inherits``, die Düsenbindung).

    Also wird nichts erfunden: das benannte Systemprofil wird gelesen und die
    Formwerk-Werte kommen darüber. Was Formwerk nicht anfasst, bleibt genau so
    stehen, wie der Hersteller es abgestimmt hat — das ist die Aufteilung aus
    §29 in einer Datei.
    """
    document: dict[str, object] = {}
    if setup.base_process:
        base = Path(setup.base_process)
        if base.is_file():
            loaded = json.loads(base.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                document.update(loaded)
    if not document:
        document = {
            "type": "process",
            "name": f"Formwerk {settings.title}",
            "from": "User",
            "instantiation": "true",
        }
    document.update(values)
    return document


def _orca_filament(
    values: dict[str, str],
    settings: PrintSettings,
    profile: Profile,
) -> dict[str, object]:
    """Das Filamentprofil für die Orca-Familie.

    Zwei Dinge unterscheiden es vom Prozessprofil. Erstens stehen die Werte
    dort als Liste, ein Eintrag je Filamentplatz — ein blanker String wird
    nicht angenommen. Zweitens braucht es ``filament_type``, sonst weiß der
    Slicer nicht, welche Grundannahmen gelten.

    Ein Systemprofil als Unterlage gibt es hier noch nicht; das kommt mit der
    nächsten Stufe, wenn Formwerk die Filamentprofile des Slicers liest. Bis
    dahin erbt die Datei von der Familie des Materials, und was Formwerk nicht
    setzt, kommt von dort.
    """
    document: dict[str, object] = {
        "type": "filament",
        "name": f"Formwerk {settings.title}",
        "from": "User",
        "instantiation": "true",
        "filament_type": [slicer_keys.filament_type(profile.material.id)],
    }
    document.update({key: [value] for key, value in values.items()})
    return document


def _command(
    setup: SlicerSetup,
    models: Sequence[Path],
    config: SlicerConfig,
    output: Path,
) -> list[str]:
    """Die Kommandozeile dieses Slicers. Eine Liste, nie eine Zeichenkette —
    ein Dateiname mit Leerzeichen ist sonst zwei Argumente.

    Mehrere Modelle gehen zusammen hinein: die Slicer ordnen sie selbst auf der
    Platte an, und das ist ihre Aufgabe. Eines nach dem anderen zu slicen
    ergäbe ebenso viele Druckdateien, von denen jede so tut, als sei sie der
    ganze Auftrag.
    """
    binary = str(setup.executable)
    files = [str(entry) for entry in models]

    if setup.flavour == "prusa":
        return [
            binary,
            "--export-gcode",
            "--load",
            str(config.process),
            "--output",
            str(output / "formwerk.gcode"),
            *files,
        ]

    if setup.flavour == "orca":
        # Beide Profile, immer in dieser Reihenfolge: erst die Maschine, dann
        # der Prozess. Umgekehrt prüft der Slicer die Verträglichkeit gegen
        # einen Drucker, den er noch nicht kennt, und bricht ab.
        settings_arg = (
            f"{setup.machine_profile};{config.process}"
            if setup.machine_profile
            else str(config.process)
        )
        arguments = [binary, "--load-settings", settings_arg]
        # Das Filament kommt über einen eigenen Schalter. Es mit in
        # ``--load-settings`` zu geben hilft nicht: der Slicer sortiert die
        # Dateien nach ihrem ``type``, und ein Filamentprofil, das dort
        # ankommt, wird verworfen statt geladen.
        if config.filament is not None:
            arguments += ["--load-filaments", str(config.filament)]
        return [*arguments, "--slice", "0", "--outputdir", str(output), *files]

    arguments = [binary, "slice", "-v"]
    if setup.machine_profile:
        arguments += ["-j", setup.machine_profile]
    for line in config.process.read_text(encoding="utf-8").splitlines():
        if line.strip():
            arguments += ["-s", line.strip()]
    for entry in files:
        arguments += ["-l", entry]
    arguments += ["-o", str(output / "formwerk.gcode")]
    return arguments


@dataclass(slots=True)
class SliceOutcome:
    """Was der Lauf gebracht hat."""

    gcode_path: Path
    metrics: gcode.GcodeMetrics
    findings: list[Finding] = field(default_factory=list)
    seconds: float = 0.0


def slice_model(
    model: Path | Sequence[Path],
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    *,
    output_dir: Path | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> SliceOutcome:
    """Slicen lassen und die Datei zurücklesen (§29, §28.1).

    Der Rückweg ist der Punkt: was herauskommt, ist nicht bloß eine Datei auf
    der Platte, sondern gemessene Kennzahlen, die im Prüfbericht neben den
    geschätzten stehen — mit ihrer Herkunft, nie mit ihnen vermischt
    (Regel 14).

    Mehrere Modelle gehen als eine Platte hinein und ergeben eine Druckdatei.
    Ein einzelner Pfad ist dabei der Sonderfall mit einem Eintrag, nicht ein
    anderer Weg.
    """
    models = [model] if isinstance(model, Path) else list(model)
    if not models:
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Es wurde nichts zum Slicen übergeben."),
        )
    missing = [entry for entry in models if not entry.is_file()]
    if missing:
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Die zu slicende Datei ist nicht da."),
            values={"path": ", ".join(entry.name for entry in missing)},
        )
    if not setup.executable.is_file():
        raise ExternalToolError(
            tool=setup.name,
            detail=_("Der eingestellte Slicer liegt nicht mehr an seinem Pfad."),
            suggestions=(OPEN_SETTINGS, Action(id="export_only", label=_("Nur exportieren."))),
        )

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="formwerk-slice-") as directory:
        workspace = Path(directory)
        config = write_config(settings, profile, setup, workspace)
        target = output_dir if output_dir is not None else workspace
        target.mkdir(parents=True, exist_ok=True)

        completed = subprocess.run(
            _command(setup, models, config, target),
            cwd=workspace,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        produced = _find_gcode(target)
        if produced is None:
            raise ExternalToolError(
                tool=setup.name,
                exit_code=completed.returncode,
                detail=_("Der Slicer hat keine Druckdatei geschrieben."),
                # Beide Ströme: die Orca-Familie protokolliert auf stdout und
                # lässt stderr leer. Nur stderr zu zeigen hieße, einen Fehler
                # ohne Text zu melden — und das ist schlimmer als keiner.
                values={"output": _tail(completed.stdout, completed.stderr)},
                suggestions=(
                    Action(id="show_output", label=_("Ausgabe des Slicers ansehen.")),
                    Action(id="check_profile", label=_("Maschinenprofil prüfen.")),
                    Action(id="export_only", label=_("Nur exportieren und selbst slicen.")),
                ),
            )

        payload = produced.read_text(encoding="utf-8", errors="replace")
        metrics = gcode.parse(payload)
        # Die Gegenprobe: hat der Slicer übernommen, was ihm geschrieben wurde?
        # Das ist die einzige Auskunft, die von ihm selbst kommt statt aus einer
        # Dokumentation, die für die installierte Fassung gelten mag oder nicht.
        ignored = verify(payload, as_mapping(settings, setup.flavour))
        if output_dir is None:
            # Der Ordner verschwindet gleich; die Datei muss den Aufrufer noch
            # erreichen können, also wandert sie neben das Modell.
            kept = models[0].with_suffix(".gcode")
            kept.write_bytes(produced.read_bytes())
            produced = kept

    findings = [*ignored, *gcode.findings_for(metrics)]
    findings.append(
        Finding(
            code="slicer.handover",
            severity="info",
            message=_(
                "Diese Datei kommt aus dem externen Slicer, gerechnet mit den Werten aus Formwerk."
            ),
            values={"slicer": metrics.slicer or setup.name, "settings": settings.title},
            source="gcode",
        )
    )
    return SliceOutcome(
        gcode_path=produced,
        metrics=metrics,
        findings=findings,
        seconds=time.perf_counter() - started,
    )


#: Wie ein Slicer seine Konfiguration in die Datei schreibt. Alle drei
#: Familien tun es, in leicht verschiedener Schreibweise.
_SETTING_LINE = re.compile(r"^;\s*(?P<key>[a-z_0-9]+)\s*=\s*(?P<value>.*?)\s*$", re.IGNORECASE)

#: Schlüssel, deren Wert der Slicer bewusst umrechnet oder ergänzt — eine
#: Abweichung dort ist keine. ``filament_colour`` etwa wird zu einer Liste,
#: weil ein Drucker mehrere Filamente führen kann.
#:
#: Die Filamentwerte standen hier lange mit derselben Begründung. Sie war
#: falsch: der Slicer rechnete sie nicht um, er bekam sie nie — sie lagen im
#: Prozessprofil, und dort liest er sie nicht. Seit sie im Filamentprofil
#: stehen, gehören sie in die Gegenprobe wie alles andere.
_RECOMPUTED: Final = frozenset(
    {
        "filament_colour",
        "nozzle_diameter",
        "bed_shape",
        "first_layer_speed",
        "brim_type",
        "wall_sequence",
        "support_type",
    }
)


def verify(text: str, written: Mapping[str, str]) -> list[Finding]:
    """Kam an, was Formwerk geschrieben hat? (§28.2)

    Die Slicer schreiben ihre wirksame Konfiguration als Kommentare in die
    Druckdatei. Das ist die einzige Auskunft darüber, ob eine Zuordnung
    stimmt — und sie kommt von dem Programm selbst, nicht aus einer
    Dokumentation, die für die installierte Fassung womöglich nicht gilt.

    Damit prüft sich jeder Slicer selbst, auch einer, den beim Bauen der
    Tabelle niemand vorliegen hatte. Gemeldet wird nur, was **nachweislich**
    abweicht: ein Schlüssel, den die Datei gar nicht nennt, sagt nichts —
    kein Slicer schreibt alles.
    """
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = _SETTING_LINE.match(line.strip())
        if match is not None:
            found.setdefault(match.group("key").casefold(), match.group("value"))

    ignored: list[str] = []
    for key, wanted in written.items():
        if key in _RECOMPUTED:
            continue
        actual = found.get(key.casefold())
        if actual is None or _same(actual, wanted):
            continue
        ignored.append(f"{key}: {wanted} → {actual}")

    if not ignored:
        return []
    _log.warning("slicer ignored %d setting(s): %s", len(ignored), "; ".join(ignored[:5]))
    return [
        Finding(
            code="slicer.setting_ignored",
            severity="warning",
            message=_(
                "Der Slicer hat Einstellungen anders übernommen, als Formwerk sie geschrieben hat."
            ),
            values={"count": len(ignored), "settings": "; ".join(sorted(ignored)[:10])},
            source="gcode",
        )
    ]


def _same(actual: str, wanted: str) -> str | bool:
    """Ob zwei Werte dasselbe meinen.

    Verglichen wird nachsichtig: ``0.2`` und ``0.20``, ``15%`` und ``15``,
    und eine Liste aus einem Element gegen dieses Element. Sonst meldete die
    Gegenprobe Unterschiede, die keine sind, und würde nach dem dritten Mal
    weggesehen.
    """
    left, right = actual.strip().strip("%"), wanted.strip().strip("%")
    if left == right:
        return True
    left = left.strip("[]").split(",")[0].strip().strip("\"'")
    if left == right:
        return True
    try:
        return abs(float(left) - float(right)) < 1e-6
    except ValueError:
        return False


def _tail(*streams: bytes, limit: int = 800) -> str:
    """Das Ende dessen, was der Slicer gesagt hat.

    Der Anfang ist bei allen dieser Programme eine Seite Versionsangaben; was
    erklärt, warum nichts herauskam, steht unten.
    """
    text = "\n".join(stream.decode("utf-8", errors="replace").strip() for stream in streams)
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[-limit:]


def _find_gcode(directory: Path) -> Path | None:
    """Die jüngste Druckdatei im Ordner.

    Die Slicer benennen selbst, und Orca hängt Plattennummern an. Gesucht wird
    deshalb nach Endung, nicht nach Namen — und die jüngste gewinnt, damit ein
    zweiter Lauf im selben Ordner nicht die Zahlen des ersten meldet.
    """
    candidates = [
        entry
        for entry in directory.iterdir()
        if entry.is_file() and entry.suffix.casefold() in GCODE_SUFFIXES
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: entry.stat().st_mtime)
