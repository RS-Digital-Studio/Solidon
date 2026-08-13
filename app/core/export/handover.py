"""Übergabe an den Slicer (Bauplan §29, §28.1).

Solidon baut keinen G-Code-Slicer (§22) — es bedient einen. Der Unterschied
zum Wechseln in ein anderes Programm ist, dass die Einstellungen hier bleiben:
Solidon schreibt sie als Profil, ruft den Slicer im Konsolenmodus, und liest
die entstandene Datei mit :mod:`app.core.slice.gcode` wieder ein. Wer das
benutzt, sieht den Slicer nicht mehr.

Was Solidon **nicht** mitbringt, ist das Maschinenwissen: Bettform,
Anfahrwege, Start- und Endcode, die Eigenheiten einer Kinematik. Das steht in
den Profilen, die der Slicer mitbringt, und genau dort bleibt es. Solidon
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

from app.core import activation
from app.core.errors import OPEN_SETTINGS, Action, ExternalToolError
from app.core.export import slicer_keys, slicer_profiles
from app.core.export.slicer_keys import SlicerFlavour
from app.core.knowledge.print_settings import read_path, with_path
from app.core.log import get_logger
from app.core.slice import gcode
from app.core.types import Finding, PrintSettings, Profile, SettingAdvice
from app.i18n import _

_log = get_logger(__name__)

#: Slicen dauert länger als alles andere, was Solidon außer Haus gibt. Fünf
#: Minuten sind großzügig für ein Teil und immer noch eine Grenze.
TIMEOUT_SECONDS: Final = 300.0

#: Wonach im Ausgabeordner gesucht wird — die Slicer benennen selbst.
GCODE_SUFFIXES: Final = (".gcode", ".gco", ".g")

#: Was in einem Profil „dazu sage ich nichts" heißt. Ein Filamentprofil, das
#: den Rückzug auf ``nil`` stellt, widerspricht Solidon nicht — es überlässt
#: den Wert dem Drucker.
_NO_STATEMENT: Final = frozenset({"nil", "", "none"})


@dataclass(frozen=True, slots=True)
class SlicerSetup:
    """Welcher Slicer, und worauf seine Profile aufsetzen.

    ``machine_profile`` und ``base_process`` tragen bevorzugt **Namen** aus
    dem Bestand des Slicers — so reisen sie in eine Projektdatei, ohne gegen
    Regel 12 zu verstoßen, und zeigen auf einem zweiten Rechner nicht ins
    Leere. Ein Pfad wird ebenso angenommen; :func:`profile_file` löst beides
    zur Datei auf, denn der Slicer nimmt nur die.
    """

    executable: Path
    flavour: SlicerFlavour
    machine_profile: str = ""
    base_process: str = ""
    base_filament: str = ""
    """Das Filamentprofil des Slicers, auf das Solidon seine Werte legt.

    Ohne das kennt der Slicer nur „PETG"; mit ihm weiß er, *welches* — und
    fährt die Werte des Herstellers für alles, was Solidon nicht setzt.
    """

    @property
    def name(self) -> str:
        return self.executable.stem


def profile_file(chosen: str, setup: SlicerSetup, kind: slicer_profiles.ProfileKind) -> Path | None:
    """Die Datei zu einem Profil, gleich ob ein Name oder ein Pfad ankam.

    Beides muss gehen, und das ist kein Entgegenkommen, sondern die Folge aus
    zwei Anforderungen, die auseinanderziehen: in die Projektdatei gehört der
    **Name** — ein Pfad dort verstößt gegen Regel 12 und zeigt auf einem
    zweiten Rechner ins Leere. Der Slicer dagegen nimmt nur die **Datei**; wer
    ihm den Namen reicht, bekommt „can not find setting file" und einen
    Abbruch, bevor das Modell angesehen wird.

    Ohne diese Auflösung dazwischen war das Ergebnis stiller: ``base_process``
    trug einen Namen, ``Path(name).is_file()`` sagte nein, und das
    geschriebene Prozessprofil hatte zweiundvierzig Schlüssel statt
    zweiundsechzig — ohne ``inherits``, ohne ``compatible_printers``. Genau
    die beiden, an denen die Orca-Familie die Verträglichkeit prüft.
    """
    if not chosen:
        return None
    direkt = Path(chosen)
    if direkt.is_file():
        return direkt
    # ``kind`` und nicht ``type_of``: das eine ist der Ordner, aus dem das
    # Profil stammt, das andere sein ``type``-Feld — und das steht in den
    # mitgelieferten Profilen der Orca-Familie durchweg leer.
    #
    # Gesucht wird ausdrücklich nach dieser Art. Ohne die Angabe gilt
    # ``DEFAULT_KINDS``, und darin fehlen die Filamentprofile mit Absicht —
    # sie vervielfachen den Bestand. Wer hier nach einem Filament fragte, bekam
    # deshalb nie eines: die Schleife lief über Maschinen und Prozesse und
    # endete in „no filament profile named ...". Nach einer Art zu fragen ist
    # obendrein schneller als nach zweien.
    for entry in slicer_profiles.find_profiles(setup.executable, setup.flavour, kinds=(kind,)):
        if entry.name == chosen and entry.kind == kind:
            found = Path(entry.path)
            if found.is_file():
                return found
    _log.warning("no %s profile named %r in this slicer", kind, chosen)
    return None


def detect(executable: Path | str) -> SlicerSetup:
    """Was für ein Slicer das ist. Erkennt an seinem Namen (§29)."""
    path = Path(executable)
    flavour = slicer_keys.flavour_of(path.name)
    if flavour is None:
        raise ExternalToolError(
            tool=path.name,
            detail=_("Solidon kennt die Kommandozeile dieses Programms nicht."),
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
        value = entry.write(read_path(settings, entry.path))
        # Ein leerer Text heißt „dazu sagt Solidon nichts" (siehe
        # ``_number_or_silent``). Er darf weder in die Datei noch in die
        # Gegenprobe: geschrieben überschriebe er den Wert des Herstellers,
        # verglichen meldete er eine Abweichung von nichts.
        if value != "":
            written[entry.key] = value
    return _cura_dependants(_only_chosen_adhesion(written, settings, flavour), flavour)


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


def object_keys(
    settings: PrintSettings, advice: Sequence[SettingAdvice], flavour: SlicerFlavour
) -> dict[str, str]:
    """Die Abweichungen eines Teils in der Sprache des Slicers (§29).

    Übernommen wird die ganze Gruppe, nicht nur der geänderte Wert. Wer die
    Haftungsart auf Brim stellt, braucht auch dessen Breite — und die Maße der
    Arten, die *nicht* gewählt sind, müssen auf null, sonst läuft unter dem
    Teil zusätzlich ein Raft mit (siehe :func:`_only_chosen_adhesion`).
    """
    if not advice:
        return {}
    groups = {entry.path.partition(".")[0] for entry in advice}
    keys = {
        entry.key for entry in slicer_keys.TABLES[flavour] if entry.path.partition(".")[0] in groups
    }
    changed = as_mapping(_applied(settings, advice), flavour)
    return {key: value for key, value in changed.items() if key in keys}


def _applied(settings: PrintSettings, advice: Sequence[SettingAdvice]) -> PrintSettings:
    """Die Einstellungen mit den Abweichungen dieses Teils darin.

    Nicht über :func:`app.core.slice.advise.apply` — der Kern soll von hier
    nach dort nicht abhängen, und es sind zwei Zeilen.
    """
    changed = settings
    for entry in advice:
        changed = with_path(changed, entry.path, entry.value)
    return changed


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


def _cura_dependants(written: dict[str, str], flavour: SlicerFlavour) -> dict[str, str]:
    """Was bei ``CuraEngine`` von einem anderen Wert abhängt (§29).

    Zwei Fälle, beide an einem echten Lauf gegen PrusaSlicer gemessen — derselbe
    Würfel, dieselben Einstellungen:

    **Die erste Bahnbreite ist dort ein Anteil, kein Maß.**
    ``initial_layer_line_width_factor`` will Prozent von ``line_width``.
    Solidon schrieb den Millimeterwert hinein: 0,449 wurde zu 0,449 Prozent,
    und die erste Schicht bekam ein Zweihundertstel der Breite, die sie haben
    sollte.

    Der Schalter, ohne den die Beschleunigungswerte nicht gelten, steht
    daneben in :func:`_machine_keys` — hier fiele er durch, weil
    :func:`by_section` nur behält, was in der Zuordnungstabelle steht.
    """
    if flavour != "cura":
        return written
    width = _as_float(written.get("line_width"))
    first = _as_float(written.get("initial_layer_line_width_factor"))
    if width and first:
        written["initial_layer_line_width_factor"] = f"{first / width * 100.0:g}"
    return written


def _as_float(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _machine_keys(profile: Profile, flavour: SlicerFlavour) -> dict[str, str]:
    """Was der Slicer über die Maschine wissen muss, wenn kein Profil greift.

    Für ``prusa`` ist eine ``.ini`` eigenständig lauffähig, sobald Düse und
    Bettform darin stehen. Orca lädt ein Maschinenprofil aus seinem Bestand,
    und dem hier hineinzureden hieße, seine Anfahrwege und seinen Startcode
    zu überschreiben.

    ``cura`` stand lange bei Orca, und das war falsch: ``CuraEngine`` ist
    nicht die Kommandozeile eines Slicers, sondern die Rechenmaschine hinter
    dem Fenster. Sie löst keine Vererbung auf — was das Fenster sonst aus
    Definition, Qualität, Material und Variante zusammenrechnet, muss ihr
    einzeln mitgegeben werden. Ohne Bettmaße rechnete sie einen G-Code, in
    dessen Kopf ``MINX:2.14748e+06`` stand: der Grenzwert eines Ganzzahltyps,
    also gar keine Angabe.
    """
    if flavour == "cura":
        width, depth, height = profile.printer.build_volume
        return {
            "machine_width": f"{width:g}",
            "machine_depth": f"{depth:g}",
            "machine_height": f"{height:g}",
            "machine_nozzle_size": f"{profile.printer.nozzle_diameter:g}",
            # Solidon rechnet um den Ursprung, hier wie bei Prusa.
            "machine_center_is_zero": "true",
            # Zwei Einstellungen aus `fdmprinter.def.json` tragen keinen
            # Vorgabewert — das Fenster füllt sie aus dem Qualitätsprofil.
            # Ohne sie bricht der Lauf mit „Trying to retrieve setting with
            # no value given" ab, bevor er die erste Schicht ansieht.
            "roofing_layer_count": "0",
            "flooring_layer_count": "0",
            # Und einer, ohne den zwei geschriebene Werte nicht gelten:
            # ``CuraEngine`` rechnet ohne ihn mit ``machine_acceleration``
            # weiter und übergeht `acceleration_print` und
            # `acceleration_wall_0`, die daneben stehen.
            "acceleration_enabled": "true",
        }
    if flavour != "prusa":
        return {}
    printer = profile.printer
    width, depth, height = printer.build_volume
    # Um den Ursprung, nicht ab der Ecke: Solidon rechnet zentriert — die
    # Anordnung beginnt bei ``-width/2`` (siehe ``arrange_on_bed``), und ein
    # exportierter Körper steht bei x -30..30. Ein Bett von 0 bis 256 liegt
    # daneben, und PrusaSlicer sagte dazu „All objects are outside of the
    # print volume" und schrieb nichts. Die Bettform beschreibt hier dieselbe
    # Welt wie die Koordinaten, die mit ihr kommen.
    half_width, half_depth = width / 2.0, depth / 2.0
    corners = (
        f"{-half_width:g}x{-half_depth:g},{half_width:g}x{-half_depth:g},"
        f"{half_width:g}x{half_depth:g},{-half_width:g}x{half_depth:g}"
    )
    return {
        "nozzle_diameter": f"{printer.nozzle_diameter:g}",
        "bed_shape": corners,
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
        target = directory / "solidon.ini"
        lines = [f"# {settings.title} — von Solidon geschrieben, nicht von Hand"]
        lines += [f"{key} = {value}" for key, value in sorted(values.items())]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return SlicerConfig(process=target)

    if setup.flavour == "orca":
        target = directory / "solidon_process.json"
        target.write_text(
            json.dumps(
                _orca_process(split.get("process", {}), settings, setup),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        filament = directory / "solidon_filament.json"
        filament.write_text(
            json.dumps(
                _orca_filament(split.get("filament", {}), settings, profile, setup),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return SlicerConfig(process=target, filament=filament)

    target = directory / "solidon_cura.txt"
    target.write_text(
        "\n".join(f"{key}={value}" for key, value in sorted(values.items())) + "\n",
        encoding="utf-8",
    )
    return SlicerConfig(process=target)


def project_settings(
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
    extruders: int = 1,
) -> dict[str, object]:
    """Die Einstellungen einer Platte, wie eine Orca-Projektdatei sie führt.

    Dieselben Werte wie in :func:`write_config`, nur in *einer* Abbildung statt
    in zwei Dateien: eine 3MF trennt Prozess und Filament nicht, sie hat einen
    Satz Schlüssel. Damit trägt die exportierte Datei ihre Temperaturen,
    Geschwindigkeiten und Kühlung selbst — sonst öffnet der Slicer sie mit dem
    Profil, das gerade eingestellt ist, und was Solidon über dieses Teil weiß,
    ist beim Öffnen weg.

    Aufgesetzt wird auf den Bestand des Slicers, nicht auf Erfundenes: das
    benannte System-Prozessprofil und -Filamentprofil werden gelesen, Solidons
    Werte kommen darüber. Was Solidon nicht anfasst, bleibt so, wie der
    Hersteller es abgestimmt hat (§29).

    Die Filamentschlüssel werden zu **Listen**, einer je Extruder — so führt
    das Format sie, und ein blanker String kommt in der Oberfläche als leeres
    Feld an.
    """
    if setup.flavour != "orca":
        # Nur diese Familie liest Einstellungen aus der 3MF. Cura bekommt sie
        # über die Kommandozeile, PrusaSlicer über seine INI.
        return {}

    split = by_section(settings, setup.flavour)
    filament_values = split.get("filament", {})

    # Eine Projektdatei trägt kein ``inherits`` — sie muss die Werte
    # ausgeschrieben enthalten. Die Erbkette wird deshalb **aufgelöst**, für
    # Maschine wie Prozess, nicht nur die oberste Datei gelesen.
    #
    # Das ist der Unterschied zu ``write_config``: dort bekommt der Slicer eine
    # Profildatei und löst selbst auf. Hier bekommt er ein Projekt, und was
    # darin fehlt, füllt er aus dem Profil, das gerade eingestellt ist. Genau
    # das ist passiert: von 546 Schlüsseln standen 122 in der Datei, der Rest
    # kam aus der Auswahl des Nutzers — die 3MF sagte drei Wände, gedruckt
    # wurden zwei, und der Unterschied waren 127 Gramm.
    document: dict[str, object] = {}
    grundlagen: tuple[tuple[slicer_profiles.ProfileKind, str], ...] = (
        ("machine", setup.machine_profile),
        ("process", setup.base_process),
    )
    for kind, chosen in grundlagen:
        found = profile_file(chosen, setup, kind)
        if found is not None:
            document.update(slicer_profiles.resolve_values(found))

    document.update(_orca_process(split.get("process", {}), settings, setup))
    filament = _orca_filament(filament_values, settings, profile, setup)
    document.update(filament)
    document.update(_machine_keys(profile, setup.flavour))

    for key in ("type", "instantiation", "inherits"):
        document.pop(key, None)

    # Welche Schlüssel je Extruder geführt werden, sagt die Übersetzungstabelle
    # selbst — sie trägt die Sektion je Eintrag. Eine zweite Liste hier wäre
    # beim nächsten neuen Schlüssel schon falsch.
    per_extruder = set(filament.keys())
    resolved: dict[str, object] = {
        key: ([value] * extruders if key in per_extruder and not isinstance(value, list) else value)
        for key, value in document.items()
    }

    # Erst nach der Umwandlung: das hier sind Angaben *über* die Datei, keine
    # Werte je Extruder. Als Liste geschrieben liest der Slicer sie nicht.
    resolved["from"] = "project"
    resolved["name"] = "project_settings"

    # Woran der Slicer erkennt, wofür diese Werte gelten. Ohne sie lädt er
    # seine eigene Auswahl darunter, und was hier nicht ausdrücklich steht,
    # kommt aus einem Profil, das niemand gewählt hat.
    if setup.machine_profile:
        resolved["printer_settings_id"] = setup.machine_profile
    if setup.base_process:
        resolved["print_settings_id"] = setup.base_process
    if setup.base_filament:
        resolved["filament_settings_id"] = [setup.base_filament] * extruders
    resolved.setdefault("printer_model", profile.printer.title)
    resolved.setdefault("nozzle_diameter", [str(profile.printer.nozzle_diameter)])
    return resolved


def _orca_process(
    values: dict[str, str],
    settings: PrintSettings,
    setup: SlicerSetup,
) -> dict[str, object]:
    """Das Prozessprofil für die Orca-Familie.

    Diese Slicer nehmen kein Prozessprofil an, das nicht zum Drucker passt —
    sie brechen mit „process not compatible with printer" ab, bevor sie das
    Modell überhaupt ansehen. Die Kompatibilität steht in Feldern, die
    Solidon nicht kennt und nicht erfinden sollte (``compatible_printers``,
    ``inherits``, die Düsenbindung).

    Also wird nichts erfunden: das benannte Systemprofil wird gelesen und die
    Solidon-Werte kommen darüber. Was Solidon nicht anfasst, bleibt genau so
    stehen, wie der Hersteller es abgestimmt hat — das ist die Aufteilung aus
    §29 in einer Datei.
    """
    document: dict[str, object] = {}
    base = profile_file(setup.base_process, setup, "process")
    if base is not None:
        loaded = json.loads(base.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            document.update(loaded)
    if not document:
        document = {
            "type": "process",
            "name": f"Solidon {settings.title}",
            "from": "User",
            "instantiation": "true",
        }
    document.update(values)
    # Objektmarken, unabhängig von den Einstellungen: Solidon schickt eine
    # Baugruppe mit benannten Teilen, und ohne die Marken im G-Code kann der
    # Drucker keines davon einzeln ausschließen. Löst sich einer von zwölf
    # Behältern nach sechs Stunden, ist sonst die ganze Platte verloren — der
    # Satz, um den es hier geht, lief ohne sie.
    document["gcode_label_objects"] = "1"
    # Ein eigener Name, obwohl das Systemprofil die Grundlage war. Sonst steht
    # im G-Code „0.20mm Standard @Elegoo CC2 0.4 nozzle", und wer die Datei
    # hinterher liest, hält Solidons Werte für die des Herstellers. Genau
    # diese Verwechslung hat einen Satz Gewürzbehälter gekostet: die
    # Projektdatei trug den Namen eines Systemprofils, der Slicer lud sein
    # eigenes darunter, und zehn von elf Werten waren still weg.
    document["name"] = f"Solidon {settings.title}"
    return document


def _orca_filament(
    values: dict[str, str],
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup,
) -> dict[str, object]:
    """Das Filamentprofil für die Orca-Familie.

    Zwei Dinge unterscheiden es vom Prozessprofil. Erstens stehen die Werte
    dort als Liste, ein Eintrag je Filamentplatz — ein blanker String wird
    nicht angenommen. Zweitens braucht es ``filament_type``, sonst weiß der
    Slicer nicht, welche Grundannahmen gelten.

    Wie beim Prozess (§29) legt Solidon seine Werte auf das Profil des
    Herstellers, statt eines zu erfinden. Der Unterschied zum Prozess: hier
    wird die Erbkette vorher **aufgelöst**. Ein Filamentprofil bei Elegoo
    setzt selbst drei Werte und erbt fünfzig; kopierte man nur die oberste
    Datei, stünde in der Übergabe ein Bruchstück.
    """
    # Der Name nennt die Spule, nicht die Qualitätsstufe. „Solidon Standard —
    # PETG" stand über Werten von Elegoo PETG PRO: 5 mm³/s statt 11, 240 Grad
    # statt 250 — richtig gerechnet, falsch beschriftet. Wer die Druckdatei
    # später liest oder sie jemandem gibt, sieht nur „PETG" und legt die
    # falsche Rolle ein. Das „Solidon" davor bleibt, denn die Werte sind
    # Solidons und nicht die des Herstellers.
    marke = Path(setup.base_filament).stem if setup.base_filament else ""
    document: dict[str, object] = {
        "type": "filament",
        "name": f"Solidon {marke or settings.title}",
        "from": "User",
        "instantiation": "true",
        "filament_type": [slicer_keys.filament_type(profile.material.id)],
    }
    # Über ``profile_file``, nicht über ``Path(...).is_file()``: hierher kommt
    # bevorzugt ein **Name** aus dem Bestand des Slicers, denn ein Pfad
    # verstieße in der Projektdatei gegen Regel 12. Direkt als Pfad gelesen
    # sagte ``is_file()`` schlicht nein, und das Herstellerprofil wurde still
    # übersprungen — dieselbe Falle, die beim Prozessprofil schon einmal
    # zweiundvierzig Schlüssel statt zweiundsechzig ergab.
    #
    # Hier kostete es mehr als Schlüssel: ohne das Profil des Herstellers
    # fehlten die Temperaturen aller Druckplatten außer der einen, die Solidon
    # selbst setzt. Der Slicer wählte „Cool Plate", fand dort die 35 Grad
    # seiner eigenen Vorgabe, und ein PETG-Druck ging mit kaltem Bett hinaus.
    base = profile_file(setup.base_filament, setup, "filament")
    if base is not None:
        inherited = slicer_profiles.resolve_values(base)
        document.update({key: _as_slots(value) for key, value in inherited.items()})
    document.update({key: [value] for key, value in values.items()})
    return _with_every_plate(document, values)


#: Die Druckplatten, die die Orca-Familie auseinanderhält. Welche aufliegt,
#: weiß Solidon nicht — deshalb bekommt jede denselben Wert.
PLATE_KINDS: Final = ("cool", "eng", "hot", "textured", "supertack")


def _with_every_plate(document: dict[str, object], values: Mapping[str, str]) -> dict[str, object]:
    """Die Betttemperatur auf jede Druckplatte, nicht nur auf eine.

    ``curr_bed_type`` gehört der Maschine, die Temperatur dem Material — und
    Solidon kennt nur das zweite. Schreibt es allein ``hot_plate_temp`` und
    der Nutzer hat eine andere Platte eingestellt, liest der Slicer die
    Temperatur einer Platte, über die nie jemand entschieden hat.

    Erfunden wird dabei nichts: geschrieben wird derselbe Wert, den Solidon
    ohnehin für das Bett gesetzt hat. Danach ist das Ergebnis unabhängig
    davon, welche Platte gewählt ist — dieselbe Vorsicht wie bei den
    Haftungsarten, wo ein ungenutztes Maß sonst als eigener Schalter wirkt.
    """
    for suffix in ("", "_initial_layer"):
        value = values.get(f"hot_plate_temp{suffix}")
        if value is None:
            continue
        for plate in PLATE_KINDS:
            document[f"{plate}_plate_temp{suffix}"] = [value]
    return document


def _as_slots(value: object) -> object:
    """Filamentwerte stehen als Liste. Was aus einem Profil einzeln kommt,
    wird dazu gemacht — sonst mischt die Datei zwei Schreibweisen."""
    return value if isinstance(value, list) else [value]


def profile_differences(settings: PrintSettings, setup: SlicerSetup) -> list[Finding]:
    """Wo Solidons Werte von denen des Filamentprofils abweichen (§29, §22.5).

    Beide Seiten haben recht, und das ist der Punkt. Solidons Tabelle sagt,
    was PETG im Allgemeinen verträgt; das Profil des Herstellers sagt, was
    *diese Spule* auf *diesem Drucker* verträgt. Beim transluzenten Elegoo-PETG
    sind das 255 °C bei 70 °C Bett gegen 240 bei 80 — und ein Volumenstrom von
    10 mm³/s statt 12.

    Gemeldet, nicht stillschweigend übernommen: die Einstellung ist die
    Entscheidung des Nutzers. Wer den Hinweis liest, kann ihr widersprechen —
    und genau das soll er können (§2.7).
    """
    if setup.flavour != "orca" or not setup.base_filament:
        return []
    base = Path(setup.base_filament)
    if not base.is_file():
        return []

    inherited = slicer_profiles.resolve_values(base)
    written = by_section(settings, setup.flavour).get("filament", {})
    apart: list[str] = []
    for key, ours in written.items():
        theirs = inherited.get(key)
        if theirs is None:
            continue
        value = theirs[0] if isinstance(theirs, list) and theirs else theirs
        # ``nil`` ist keine Gegenaussage, sondern eine Nicht-Aussage: der Wert
        # bleibt dann beim Drucker. Das als Abweichung zu melden hieße, fünf
        # Zeilen Rauschen neben die drei zu stellen, auf die es ankommt.
        if str(value).strip().casefold() in _NO_STATEMENT:
            continue
        if not _same(str(value), ours):
            apart.append(f"{key}: {ours} statt {value}")

    if not apart:
        return []
    _log.info("filament profile differs in %d value(s)", len(apart))
    return [
        Finding(
            code="slicer.filament_differs",
            severity="info",
            message=_(
                "Das Filamentprofil des Herstellers nennt andere Werte als die "
                "Einstellungen. Übergeben werden die Einstellungen."
            ),
            values={
                "profile": base.stem,
                "count": len(apart),
                "settings": "; ".join(sorted(apart)),
            },
            source="internal",
        )
    ]


def _command(
    setup: SlicerSetup,
    models: Sequence[Path],
    config: SlicerConfig,
    output: Path,
    keep_arrangement: bool = False,
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
            str(output / "solidon.gcode"),
            *files,
        ]

    if setup.flavour == "orca":
        # Beide Profile, immer in dieser Reihenfolge: erst die Maschine, dann
        # der Prozess. Umgekehrt prüft der Slicer die Verträglichkeit gegen
        # einen Drucker, den er noch nicht kennt, und bricht ab.
        # Auch hier die Datei, nicht der Name: der Slicer sucht keinen Bestand
        # ab, er öffnet einen Pfad. Steht dort ein Name, endet der Lauf mit
        # „can not find setting file", noch bevor das Modell an die Reihe kommt.
        machine = profile_file(setup.machine_profile, setup, "machine")
        settings_arg = f"{machine};{config.process}" if machine else str(config.process)
        arguments = [binary, "--load-settings", settings_arg]
        # Das Filament kommt über einen eigenen Schalter. Es mit in
        # ``--load-settings`` zu geben hilft nicht: der Slicer sortiert die
        # Dateien nach ihrem ``type``, und ein Filamentprofil, das dort
        # ankommt, wird verworfen statt geladen.
        if config.filament is not None:
            arguments += ["--load-filaments", str(config.filament)]
        if keep_arrangement:
            # Ohne diesen Schalter ordnet die Orca-Familie **immer** neu an,
            # egal in welchen Koordinaten die Teile ankommen — gemessen an zwei
            # Läufen derselben Szene, die denselben G-Code ergaben. Damit war
            # alles folgenlos, was Solidon über die Platte weiß: `arrange_bed`,
            # der Haftungsrand, die Plattenzuordnung. Gesetzt wird er nur, wenn
            # die Anordnung wirklich eine ist (siehe
            # :func:`app.core.export.writer.arrangement_holds`) — sonst
            # druckten zwei Teile übereinander.
            arguments += ["--arrange", "0"]
        return [*arguments, "--slice", "0", "--outputdir", str(output), *files]

    arguments = [binary, "slice", "-v"]
    basis = setup.machine_profile or _cura_base(setup.executable)
    if basis:
        arguments += ["-j", basis]
    values: list[str] = []
    for line in config.process.read_text(encoding="utf-8").splitlines():
        if line.strip():
            values += ["-s", line.strip()]
    arguments += values
    # **Und dieselben Werte noch einmal auf dem Extruder.** ``CuraEngine`` hält
    # zwei Ebenen: was global gilt, und was der Extruder-Zug sagt — und das
    # meiste, was einen Druck ausmacht, liest es vom Zug. Was nur global steht,
    # wird nicht etwa übernommen, sondern von der Vorgabe der Definition
    # überschrieben. Gemessen an einem 20-mm-Würfel gegen PrusaSlicer: 748 mm
    # Filament statt 1410, weil Wandzahl, Bahnbreite und Füllung nie ankamen.
    # Das Fenster sortiert die Werte nach ``settable_per_extruder``; sie beide
    # Male zu setzen kommt am selben Ort heraus und braucht die Definition
    # nicht zu lesen.
    arguments += ["-e0"]
    extruder = _cura_extruder_base(setup.executable)
    if extruder:
        arguments += ["-j", extruder]
    arguments += values
    for entry in files:
        arguments += ["-l", entry]
    arguments += ["-o", str(output / "solidon.gcode")]
    return arguments


def _cura_base(executable: Path) -> str:
    """Die Grunddefinition neben ``CuraEngine``, sofern sie dort liegt.

    ``CuraEngine`` braucht mindestens eine Definition, sonst kennt es keinen
    einzigen Einstellungsnamen. ``fdmprinter.def.json`` ist die Wurzel, von
    der alle Druckerdefinitionen erben — die Maschine selbst beschreibt
    Solidon daneben über :func:`_machine_keys`, statt eine der
    zwölfhundert Herstellerdefinitionen zu wählen und deren Vererbungskette
    nachzubauen. Die kennt nur das Fenster.

    Nichts, wenn sie nicht daliegt: dann scheitert der Lauf und sagt das,
    statt einen Pfad zu erfinden.
    """
    return _cura_definition(executable, "fdmprinter.def.json")


def _cura_extruder_base(executable: Path) -> str:
    """Die Grunddefinition des Extruder-Zugs, neben der des Druckers.

    Sie gibt dem Zug die Werte, die keine Einstellung von Solidon setzt —
    Düsenversatz, Startposition, Kühlung im Ruhezustand. Ohne sie bleibt der
    Zug leer, und eine Abfrage darauf endet mit „Trying to retrieve setting
    with no value given".
    """
    return _cura_definition(executable, "fdmextruder.def.json")


def _cura_definition(executable: Path, filename: str) -> str:
    for folder in (
        executable.parent / "share" / "cura" / "resources" / "definitions",
        executable.parent / "resources" / "definitions",
    ):
        found = folder / filename
        if found.is_file():
            return str(found)
    return ""


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
    keep_arrangement: bool = False,
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
    # §2 C: die Druckdatei ist ein herausgegebenes Ergebnis — wie der Export.
    activation.require(activation.SLICER)
    # Absolut, bevor irgendetwas damit geschieht: der Lauf unten setzt sein
    # eigenes Arbeitsverzeichnis, ein relativer Pfad zeigt dort ins Leere. Die
    # Prüfung gleich darunter sähe die Datei trotzdem — sie sucht im
    # Verzeichnis des aufrufenden Prozesses —, und der Fehler käme erst vom
    # Slicer selbst, als „No such file" mit einem Pfad, den es aus seiner
    # Sicht wirklich nicht gibt.
    models = [entry.resolve() for entry in ([model] if isinstance(model, Path) else model)]
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
    with tempfile.TemporaryDirectory(prefix="solidon-slice-") as directory:
        workspace = Path(directory)
        config = write_config(settings, profile, setup, workspace)
        # Aus demselben Grund wie die Modellpfade: der Slicer schreibt sonst
        # neben sein Arbeitsverzeichnis statt dorthin, wo die Datei erwartet
        # wird — und ``_find_gcode`` sucht an der leeren Stelle.
        target = (output_dir if output_dir is not None else workspace).resolve()
        target.mkdir(parents=True, exist_ok=True)

        completed = subprocess.run(
            _command(setup, models, config, target, keep_arrangement),
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
        if not gcode.extrudes(payload):
            # Eine große Datei ohne eine einzige Förderbewegung. Der Slicer ist
            # durchgelaufen und hat den Rückgabewert 0 gemeldet, aber das
            # Modell nicht verarbeitet — meist, weil ihm eine Einstellung
            # fehlte, die er stillschweigend als „nichts drucken" auslegt. Das
            # als Erfolg durchzulassen wäre schlimmer als der Abbruch: der
            # Nutzer schickte eine leere Datei an den Drucker.
            raise ExternalToolError(
                tool=setup.name,
                exit_code=completed.returncode,
                detail=_(
                    "Die Druckdatei enthält keine einzige Materialbahn — "
                    "der Slicer hat das Modell nicht verarbeitet."
                ),
                values={"output": _tail(completed.stdout, completed.stderr)},
                suggestions=(
                    Action(id="check_profile", label=_("Maschinenprofil prüfen.")),
                    Action(id="show_output", label=_("Ausgabe des Slicers ansehen.")),
                    Action(id="export_only", label=_("Nur exportieren und selbst slicen.")),
                ),
            )
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

    findings = [*profile_differences(settings, setup), *ignored, *gcode.findings_for(metrics)]
    findings.append(
        Finding(
            code="slicer.handover",
            severity="info",
            message=_(
                "Diese Datei kommt aus dem externen Slicer, gerechnet mit den Werten aus Solidon."
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
    """Kam an, was Solidon geschrieben hat? (§28.2)

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
                "Der Slicer hat Einstellungen anders übernommen, als Solidon sie geschrieben hat."
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
        # Leer zählt nicht als geschrieben. CuraEngine legt die Datei an,
        # bevor es rechnet, und lässt sie liegen, wenn ihm die Maschine nicht
        # reicht — der Lauf meldete dann Erfolg über null Bytes, und die
        # Kennzahlen daraus waren sämtlich ``None``.
        if entry.is_file()
        and entry.suffix.casefold() in GCODE_SUFFIXES
        and entry.stat().st_size > 0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: entry.stat().st_mtime)
