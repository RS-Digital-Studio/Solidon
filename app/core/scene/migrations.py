"""Formatversionen und die Migrationskette (Bauplan §16.2).

Gleiche Version: laden. Älter: die Kette läuft. Neuer: freundlich ablehnen,
statt die Hälfte zu laden — eine Datei aus einem neueren Release kann
Operationen enthalten, die dieses nicht kennt.

Migrationsschritte werden nie zusammengefasst (AGENTS.md, Checkliste
„Dateiformat ändern"): jeder behält seine eigene Funktion, seinen eigenen
Test und seine eigene eingecheckte Beispieldatei — so funktioniert die Kette
von der allerersten Version an weiter.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from app.core.errors import CANCEL, CHECK_UPDATES, ValidationError
from app.core.log import get_logger
from app.core.scene.gathered import carry_over
from app.i18n import _

_log = get_logger(__name__)

#: Aktuelle Version von ``project.json``.
FORMAT_VERSION: Final = 15


@dataclass(frozen=True, slots=True)
class Step:
    """Ein Schritt der Kette, von einer Version zur nächsten."""

    from_version: int
    to_version: int
    apply: Callable[[dict[str, Any]], dict[str, Any]]


def _add_chat(data: dict[str, Any]) -> dict[str, Any]:
    """1 → 2: das Gespräch zog ins Projekt (§26.3).

    Eine Datei aus der Zeit vor dem Agenten hat schlicht kein Gespräch, und
    eine leere Liste sagt genau das. Sonst ändert sich nichts — darum ist
    dieser Schritt eine eigene Funktion und bleibt für immer eine.
    """
    data.setdefault("chat", [])
    return data


def _mark_generated_sources(data: dict[str, Any]) -> dict[str, Any]:
    """2 → 3: eine Quelle trägt, wie sie erzeugt wurde (§27, Säule B).

    Quellen aus der Zeit vor Säule B waren alle importiert oder aus Bausteinen
    gebaut, die zwei neuen Felder sind für jede von ihnen leer. Was der
    Schritt wirklich tut: das beim Hereinkommen festhalten — statt eine Datei
    zu hinterlassen, die aussieht, als hätte sie irgendwo ihren Prompt
    verloren.
    """
    for source in data.get("sources", {}).values():
        if source.get("type") == "generated":
            source.setdefault("origin", {}).setdefault("prompt", "")
    return data


def _add_print_settings(data: dict[str, Any]) -> dict[str, Any]:
    """3 → 4: womit gedruckt wird, steht im Projekt (§29).

    Eine ältere Datei hat keine eigenen Druckeinstellungen, und ``None`` sagt
    genau das: es gilt weiter, was sich aus Qualitätsstufe, Material und
    Drucker ergibt. Erst wer sie einmal ändert, hat welche — vorher wäre ein
    voller Satz Zahlen in der Datei eine Behauptung über eine Entscheidung,
    die niemand getroffen hat.
    """
    data.setdefault("print_settings", None)
    return data


def _add_transaction_changes(data: dict[str, Any]) -> dict[str, Any]:
    """4 → 5: eine Transaktion trägt auch, was keine Operation war (§15.5).

    Bis hierher konnte eine Transaktion nur Operationen enthalten; Parameter,
    Passungen, Drucker und Material standen außerhalb des Undo. Eine ältere
    Datei hat für ihre Transaktionen also nichts einzutragen — ``None`` sagt
    genau das, und ein Undo darauf verhält sich wie bisher.

    Was der Schritt *nicht* tut: die Änderungen nachträglich erfinden. Welche
    Zahl vor einer alten Transaktion galt, steht nirgends; sie zu raten hieße,
    ein Undo anzubieten, das etwas Falsches zurücklegt.
    """
    for transaction in data.get("transactions", ()):
        transaction.setdefault("changes", None)
    return data


def _keep_transaction_titles_literal(data: dict[str, Any]) -> dict[str, Any]:
    """5 → 6: ein Transaktionstitel darf eine Message-ID sein (§4.1).

    Ab Version 6 vermerkt ``title_translatable``, dass ein Titel aus dem Code
    stammt und erst bei der Anzeige in die aktive Sprache aufgelöst wird.
    Eine ältere Datei trägt den aufgelösten Text, und dabei bleibt es: ob er
    aus dem Code kam oder vom Nutzer getippt wurde, steht nirgends, und ein
    Abgleich mit dem Katalog wäre geraten — ein selbst vergebener Titel, der
    zufällig einem Katalogeintrag gleicht, würde plötzlich übersetzt. Alte
    Titel bleiben also wörtlich; strukturell ändert dieser Schritt nichts.

    Die Versionserhöhung selbst ist der Schutz: eine ältere Version des
    Programms kennt die Markierung nicht und würde sie beim Speichern
    stillschweigend verwerfen — sie lehnt eine Version-6-Datei stattdessen
    freundlich ab.
    """
    return data


def _keep_bores_centred(data: dict[str, Any]) -> dict[str, Any]:
    """6 → 7: die Position einer Bohrung ist ihre Mündung (§25).

    Bis Version 6 lag die *Mitte* der Bohrung auf der Position. Wer eine Fläche
    anklickte, bekam ihre Höhe eingetragen — und damit eine Bohrung, die zur
    Hälfte über dem Teil in der Luft stand und nur halb so tief ging wie
    verlangt. Ab Version 7 fängt sie an der Position an und geht von dort ins
    Material.

    Für eine alte Datei ändert das die Maße, also wird sie nicht umgedeutet:
    ihre Bohrungen bekommen ``anchor="centre"`` und rechnen weiter, wie sie
    gerechnet haben. Umzurechnen wäre nichts — die Richtung ins Material
    steckt in der Geometrie, und die liegt hier nicht vor.

    Durchgehende Bohrungen (``depth`` null) trifft es ohnehin nicht: durch ist
    durch, egal von wo aus gemessen.
    """
    for operation in data.get("ops", ()):
        if operation.get("op") == "drill_hole":
            operation.setdefault("params", {})["anchor"] = "centre"
    return data


def _add_feature_matches(data: dict[str, Any]) -> dict[str, Any]:
    """8 → 9: Operationen bekommen ein Feld für Zuordnungsantworten (§15.7).

    Bis Version 8 galt die Antwort auf „Welches Merkmal entspricht ``pin_1``?"
    für einen Lauf und war danach vergessen — gemessen 99 modale Fenster für 7
    verschiedene Entscheidungen in einem einzigen Durchgang. Ab Version 9 steht
    sie als geometrischer Abdruck in ``matches``.

    **Umzurechnen gibt es nichts, und das ist Absicht.** Eine alte Datei hat
    keine gespeicherten Antworten, und keine zu haben ist der gültige Zustand:
    Beim ersten Auswerten wird gefragt wie bisher, danach nie wieder. Ein
    fehlendes Feld heißt „noch nicht gefragt" und nie „keine Antwort nötig" —
    deshalb wird hier nichts gesetzt, statt ein leeres Feld einzutragen, das
    sonst wie eine Aussage aussähe.
    """
    return data


def _add_translatable_params(data: dict[str, Any]) -> dict[str, Any]:
    """9 → 10: Operationen vermerken, welche Parameter Message-IDs tragen (§4.1).

    Bis Version 9 war ein Objektname in der Datei immer wörtlich gemeint. Ab
    Version 10 kann eine Operation vermerken, dass einer ihrer Parameter eine
    **Message-ID** ist — dann zeigt die Anwendung ihn in der eingestellten
    Sprache, und die mitgelieferten Beispiele heißen für einen englischen Kunden
    „Housing" statt „Gehäuse".

    **Umzurechnen gibt es nichts, und das ist die eigentliche Aussage.** Eine
    alte Datei hat keinen Vermerk, und keinen zu haben heißt „wörtlich" — genau
    das, was für jede bestehende Datei richtig ist. Wer 2026 ein Objekt
    „Halterung" genannt hat, meinte das Wort und keine Message-ID; es
    nachträglich zu einer zu erklären, hieße seinen Namen zu übersetzen. Das ist
    dieselbe Entscheidung wie bei ``title_translatable`` in Schritt 5 → 6.
    """
    return data


def _fold_split_plane_into_split_pinned(data: dict[str, Any]) -> dict[str, Any]:
    """10 → 11: *An Ebene teilen* geht in *Teilen* auf (§25).

    Die beiden Operationen rechneten dasselbe. ``split_plane`` war
    ``split_pinned`` mit ``pins = 0`` — gemessen und nicht vermutet: gleiche
    Hälften, gleiche Namen, gleiche Merkmale, gleiche Befunde. Zwei Einträge
    dafür sind aus Kundensicht ein Ratespiel, und im Menü waren sie schon
    zusammengelegt; erreichbar blieb der Zwilling aber weiter über die
    Befehlspalette, und dort standen wieder zwei Zeilen, die dasselbe tun.

    **Die Null ist der ganze Schritt, und sie muss ausdrücklich dastehen.**
    Das Feld *Passstifte* hat als Vorgabe zwei Stifte, nicht null — wer den
    Parameter wegließe, bekäme aus einem alten Projekt plötzlich ein
    verstiftetes Teil. Alles andere (Achse, Position) heißt in beiden
    Operationen gleich und wandert unverändert mit.
    """
    for operation in data.get("ops", []):
        if operation.get("op") != "split_plane":
            continue
        operation["op"] = "split_pinned"
        operation.setdefault("params", {})["pins"] = 0
    return data


def _add_edited_operations(data: dict[str, Any]) -> dict[str, Any]:
    """11 → 12: Eine Transaktion kann die Fassungen eines geänderten Schritts
    tragen (``edited_ops`` in den Änderungsseiten, §15.4, §15.5).

    Bis Version 11 schrieben die drei Änderungswege — Parameter, Eingänge,
    Rechenkern — am Verlauf vorbei ins Dokument: Der alte Stand war nach dem
    Speichern unwiederbringlich, und ein Undo traf einen anderen Schritt.

    **Umzurechnen gibt es nichts, und das ist die eigentliche Aussage:** Eine
    alte Datei hat solche Fassungen nicht, und keine zu haben heißt, dass es
    dort nichts zurückzulegen gibt — die Änderungen von damals sind längst
    die einzige Fassung ihrer Schritte. Dieselbe Entscheidung wie bei den
    Vermerken in Schritt 9 → 10.
    """
    return data


def _scad_steps_stay_but_stop_computing(data: dict[str, Any]) -> dict[str, Any]:
    """12 → 13: ``create_from_scad`` gibt es nicht mehr (OpenSCAD-Ausbau).

    Bis Version 12 durfte eine Projektdatei einen Schritt tragen, der beim
    Auswerten OpenSCAD startete und sein Programm im Parameter ``source``
    führte. Am 26.08.2026 ist die Operation entfallen — was sie leistete, kann
    der eigene Kern seit den Skizzen (§30.1).

    **Umgeschrieben wird nichts, und das ist die Entscheidung.** Der Schritt
    bleibt stehen, mitsamt seinem Quelltext. Zwei Gründe:

    Erstens ist der Quelltext **Arbeit des Kunden**. Eine Migration, die ihn
    wegwirft, nimmt ihm etwas, das er nirgends wiederbekommt; eine, die ihn
    stehen lässt, kostet ihn einen Blick in den Schrittdialog und ein
    Kopieren. Was Solidon nicht mehr rechnen kann, darf es trotzdem
    aufbewahren.

    Zweitens ist ein Schritt, der **anhält**, sichtbar — ein gelöschter ist
    weg. Die Auswertung hält an dieser Stelle mit einem Befund an und sagt,
    welcher Schritt es ist; ein Modell, dem klaglos ein Körper fehlt, schickt
    jemanden auf die Suche nach einem Fehler, den es nicht gibt (Regel 21).

    Die Version steigt trotzdem, und darin liegt die eigentliche Aussage: Eine
    Datei ab v13 **kann** keinen ausführbaren Quelltext mehr tragen, weil es
    keine Operation mehr gibt, die einen entgegennimmt. Das ist §32 in seiner
    stärksten Form, und es steht nur dann in der Datei, wenn die Nummer es
    sagt. Dieselbe Bauart wie Schritt 11 → 12, der auch nichts umrechnet.
    """
    return data


def _point_strokes_stay_but_stop_computing(data: dict[str, Any]) -> dict[str, Any]:
    """13 → 14: ``paint_slot`` malt nicht mehr um einen Punkt (Filament-Umbau).

    Bis Version 13 trug ein Bemal-Schritt einen Klickpunkt und einen Radius;
    seit dem 26.08.2026 färbt er eine **erkannte Fläche** vollständig
    (``at_feature``). Ein alter Schritt lässt sich nicht umrechnen: Der Punkt
    weiß nicht, welches Merkmal gemeint war, und die Erkennung von heute kann
    an seiner Stelle eine andere Fläche finden als die von damals.

    **Umgeschrieben wird deshalb nichts**, dieselbe Entscheidung wie bei
    Schritt 12 → 13. Der Schritt bleibt mit seinen Werten stehen; die
    Auswertung hält an ihm an und sagt, welcher es ist. Geraten wäre
    schlimmer als angehalten: Eine Farbe, die nach dem Update auf einer
    anderen Fläche sitzt, sieht der Kunde erst im Slicer — und dann glaubt er
    seiner Datei nicht mehr.

    Die Version steigt trotzdem, und darin liegt die Aussage: Eine Datei ab
    v14 **kann** keinen Bemal-Schritt ohne Fläche tragen, weil die Operation
    keinen ohne annimmt.
    """
    return data


def _protect_filament_metadata(data: dict[str, Any]) -> dict[str, Any]:
    """14 → 15: Farbschritte können Typ und Slicer-Profil einer Spule tragen.

    Die beiden neuen Parameter ``material_type`` und ``slicer_profile`` sind
    optional. Eine alte Operation ohne sie bedeutet deshalb bereits eindeutig
    „kein eigener Typ, kein eigenes Herstellerprofil"; Werte nachzutragen
    würde nur die Datei aufblähen und keine Information hinzufügen.

    Die Versionsgrenze ist trotzdem notwendig: Eine Anwendung bis Format 14
    kennt die Parameter nicht und würde eine neue Datei zunächst annehmen,
    dann mitten in der Auswertung an einem vermeintlich unbekannten Feld
    stoppen. Mit Version 15 lehnt sie die Datei stattdessen sofort und mit dem
    vorhandenen Update-Vorschlag ab. Wie bei 11 → 12 ist also die Grenze selbst
    der ganze Migrationsschritt.
    """
    return data


#: Alle bekannten Schritte, älteste zuerst.
MIGRATIONS: Final[tuple[Step, ...]] = (
    Step(from_version=1, to_version=2, apply=_add_chat),
    Step(from_version=2, to_version=3, apply=_mark_generated_sources),
    Step(from_version=3, to_version=4, apply=_add_print_settings),
    Step(from_version=4, to_version=5, apply=_add_transaction_changes),
    Step(from_version=5, to_version=6, apply=_keep_transaction_titles_literal),
    Step(from_version=6, to_version=7, apply=_keep_bores_centred),
    Step(from_version=7, to_version=8, apply=carry_over),
    Step(from_version=8, to_version=9, apply=_add_feature_matches),
    Step(from_version=9, to_version=10, apply=_add_translatable_params),
    Step(from_version=10, to_version=11, apply=_fold_split_plane_into_split_pinned),
    Step(from_version=11, to_version=12, apply=_add_edited_operations),
    Step(from_version=12, to_version=13, apply=_scad_steps_stay_but_stop_computing),
    Step(from_version=13, to_version=14, apply=_point_strokes_stay_but_stop_computing),
    Step(from_version=14, to_version=15, apply=_protect_filament_metadata),
)


def migrate(
    data: dict[str, Any],
    target: int = FORMAT_VERSION,
    steps: Sequence[Step] = MIGRATIONS,
) -> dict[str, Any]:
    """Hebt ein Dokument auf ``target`` — oder sagt, warum das nicht geht."""
    version = int(data.get("format_version", 0))
    if version == target:
        return data
    if version > target:
        raise ValidationError(
            # Der Titel der Oberklasse hieße „Die Eingabe war so nicht
            # verwendbar" — hier ist keine Eingabe im Spiel, sondern eine Datei
            # aus der Zukunft. Die Oberfläche zeichnet den Titel groß.
            title=_("Diese Projektdatei ist neuer als das Programm."),
            field="format_version",
            detail=_(
                "Diese Datei stammt aus einer neueren Version des Programms. Ein Update öffnet sie."
            ),
            constraint="too_new",
            values={"file_version": version, "supported": target},
            # **Der Satz nannte den Weg, und niemand ging ihn.** „Ein Update
            # öffnet sie" stand da, während die Anwendung eine Update-Prüfung im
            # Hilfe-Menü führt — angeboten wurde stattdessen *Eingabe
            # korrigieren*, und an einer Datei aus der Zukunft gibt es keine
            # Eingabe zu korrigieren (§2.7).
            suggestions=(CHECK_UPDATES, CANCEL),
        )

    by_source = {step.from_version: step for step in steps}
    current = data
    while version < target:
        step = by_source.get(version)
        if step is None:
            raise ValidationError(
                field="format_version",
                detail=_("Für diese Dateiversion fehlt der Umstellungsschritt."),
                constraint="no_migration",
                values={"file_version": version, "supported": target},
            )
        _log.info("migrating project from %d to %d", step.from_version, step.to_version)
        current = step.apply(dict(current))
        current["format_version"] = step.to_version
        version = step.to_version
    return current
