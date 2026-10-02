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

import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final

from app.core.errors import CANCEL, CHECK_UPDATES, ValidationError
from app.core.log import get_logger
from app.core.scene.gathered import carry_over
from app.i18n import _

_log = get_logger(__name__)

#: Aktuelle Version von ``project.json``.
FORMAT_VERSION: Final = 42


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


def _keep_reports_without_suggestions_valid(data: dict[str, Any]) -> dict[str, Any]:
    """15 → 16: Befunde können anklickbare Auswege mittragen (§2.7).

    Das neue Feld liegt in ``report.json`` und im Plattencache, nicht in
    ``project.json``. Eine ältere Datei hat es deshalb nicht und bleibt ohne
    Umrechnung gültig: Beim erneuten Auswerten entstehen die Handlungen aus
    der Ausnahme neu. Die Versionsgrenze schützt trotzdem vor der umgekehrten
    Richtung — eine ältere Anwendung würde die Auswege beim nächsten Speichern
    still verwerfen und den Prüfbericht wieder zur Sackgasse machen.
    """
    return data


def _allow_removed_operations(data: dict[str, Any]) -> dict[str, Any]:
    """16 → 17: Änderungsseiten können einen gelöschten Schritt tragen.

    Seit v12 enthält ``edited_ops`` vollständige Fassungen eines geänderten
    Schritts. Ab v17 darf dort auch ``null`` stehen: Auf dieser Seite der
    Transaktion ist der Schritt entfernt, auf der anderen steht seine Fassung
    für Undo und Redo. Alte Dateien enthalten kein solches ``null`` und
    brauchen deshalb keine inhaltliche Umrechnung; die Versionsgrenze schützt
    sie vor einer älteren Anwendung, die den Wert nicht lesen könnte.
    """
    return data


def _allow_a_named_pivot(data: dict[str, Any]) -> dict[str, Any]:
    """17 → 18: Drehen und Skalieren dürfen einen genannten Punkt tragen.

    ``about`` kannte ``centre``, ``origin`` und ``bed`` — alle drei liest die
    Operation aus dem *eigenen* Netz. Ab v18 gibt es ``point``, und dann gelten
    ``pivot_x``/``pivot_y``/``pivot_z``: So drehen mehrere gewählte Körper um
    **dieselbe** Stelle, statt jeder um sich selbst.

    Alte Dateien tragen keinen solchen Punkt und brauchen keine inhaltliche
    Umrechnung. **Die Versionsgrenze ist trotzdem nötig, und der Grund ist
    gemessen:** Eine v0.2.2-Anwendung nimmt ``about="point"`` an, statt es
    abzulehnen — ``anchor_point`` kennt den Wert nicht und fällt still auf
    ``bounds.centre`` durch. Sie rechnete also eine Gruppendrehung als lauter
    Einzeldrehungen und zeigte ein falsches Ergebnis ohne einen Hinweis
    darauf. Mit dem Sprung sagt sie stattdessen, dass die Datei zu neu ist.

    Dasselbe Muster wie bei 16 → 17: keine Umrechnung, nur ein Schutz.
    """
    return data


def _name_the_radius_a_radius(data: dict[str, Any]) -> dict[str, Any]:
    """18 → 19: Was an einem Kreis gemessen wurde, heißt jetzt ``radius``.

    **Der Kunde denkt in Durchmesser, der Kreis maß Radius.** Ein Kreis wird
    über Mittelpunkt und Randpunkt bemaßt; bis v18 war das eine ``distance``
    und hieß in der Oberfläche „Abstand". Wer für eine M3-Bohrung 3,2 tippte,
    bekam ein Loch mit 6,4 mm — und das Wort „Radius" kam in der ganzen
    Bedienung nicht vor, es gab also nicht einmal einen Anlass zu stutzen.

    Ab v19 gibt es ``radius`` und ``diameter`` als eigene Arten. Diese
    Migration ändert **keine gespeicherte Zahl**: Sie deutet um, was der
    Bestand ohnehin meinte, und die Geometrie bleibt Punkt für Punkt dieselbe.
    Ein Kreis, der mit 3,2 gespeichert wurde, steht danach als „R 3,2" da und
    nicht als „Ø 3,2" — die Bemaßung heißt, was sie ist.

    **Umgedeutet wird nur, was eindeutig ist** (Auflage aus der Freigabe): die
    beiden Punkte müssen Mittelpunkt und Rand **desselben** Kreises sein, und
    zwar in dieser Reihenfolge. Im Zweifel bleibt ``distance`` stehen. Ein stehen
    gebliebenes ist eine kosmetische Restzweisprachigkeit im Einzelfall; ein
    falsch umgedeutetes wäre eine falsche Beschriftung an einer
    Kundenbemaßung, und die fällt niemandem auf.
    """
    for operation in data.get("ops", []):
        params = operation.get("params")
        if not isinstance(params, dict):
            continue
        for key, value in params.items():
            if key != "sketch" or not isinstance(value, str) or not value:
                continue
            params[key] = _rename_circle_measures(value)
    return data


def _rename_circle_measures(text: str) -> str:
    """Der eigentliche Griff — auf dem Text der Skizze, nicht auf dem Modell.

    Eine Migration läuft **vor** dem Einlesen: Zu diesem Zeitpunkt ist die
    Skizze eine Zeichenkette im Parameter, und ein Modell daraus zu bauen hieße,
    den Leser des neuen Formats auf eine Datei des alten loszulassen.
    """
    try:
        sketch = json.loads(text)
    except TypeError, ValueError:
        return text
    if not isinstance(sketch, dict):
        return text
    elements = sketch.get("elements")
    constraints = sketch.get("constraints")
    if not isinstance(elements, list) or not isinstance(constraints, list):
        return text

    # Welcher flache Punktindex gehört zu welchem Element? Die Zählung ist
    # dieselbe wie in ``edit.flat_points``: Elemente in ihrer Reihenfolge,
    # jedes mit seinen Punkten.
    circles: dict[tuple[int, int], bool] = {}
    cursor = 0
    for element in elements:
        if not isinstance(element, dict):
            return text
        points = element.get("points")
        if not isinstance(points, list):
            return text
        count = len(points)
        if element.get("kind") == "circle" and count == 2:
            circles[(cursor, cursor + 1)] = True
        cursor += count

    changed = False
    for constraint in constraints:
        if not isinstance(constraint, dict) or constraint.get("kind") != "distance":
            continue
        targets = constraint.get("targets")
        if not isinstance(targets, list) or len(targets) != 2:
            continue
        if circles.get((targets[0], targets[1])):
            constraint["kind"] = "radius"
            changed = True
    return json.dumps(sketch, ensure_ascii=False) if changed else text


def _keep_explicit_choices(data: dict[str, Any]) -> dict[str, Any]:
    """Erhält alte Werte, ohne fehlende Material- oder Chatidentität zu erraten.

    Alte Chatantworten verraten nicht, ob sie ohne Vorschlag entstanden oder
    verworfen wurden. Alte Spulenwerte bleiben einem unbekannten Material
    zugeordnet und müssen vor der Übernahme auf ein bekanntes bestätigt werden.
    """
    for entry in data.get("chat", []):
        entry.setdefault("discarded", False)
    settings = data.get("print_settings") or {}
    for override in settings.get("slot_overrides", []):
        if override is not None:
            override.setdefault("material", None)
            override.setdefault("material_type", None)
    return _bind_old_lid_fits(data)


def _bind_old_lid_fits(data: dict[str, Any]) -> dict[str, Any]:
    """Bindet alte Deckelpassungen in jedem gespeicherten Undo-Zustand.

    Ein flacher Deckel hatte früher überhaupt keine Beziehung. Nur wenn
    sein nichtpositiver Wert belegt ist und nirgends eine bewusste
    Fit-Entfernung steht, wird die fehlende Beziehung ergänzt. Die echten
    History-Rückschritte lösen dabei auch alte Neuplanungen und Op-Fassungen
    auf; eine aktuelle Kennung gehört nicht ungeprüft in eine Undo-Seite.

    **Dieser Schritt ist anders als alle vor ihm.** Die siebzehn älteren
    Migrationen sind reine Wörterbuchumformungen; dieser ruft ``History``,
    ``document_from_data`` und ``fit_for_lid`` in ihrer **heutigen** Fassung.
    Das trägt, solange diese Funktionen v20-Daten noch lesen. Beim nächsten
    Formatwechsel wird er deshalb gegen eine eingecheckte v19-Datei mit
    Deckel nachgemessen, bevor v21 einen Schlüssel einführt, den
    ``document_from_data`` dann erwartet (Abnahme des Gesamt-Reviews,
    06.09.2026; Register in ROADMAP.md).
    """
    from app.core.errors import AppError
    from app.core.expressions import resolve, resolve_value
    from app.core.lid_flow import fit_for_lid
    from app.core.scene.history import History, _living_objects
    from app.core.scene.serialise import document_from_data, fit_to_data
    from app.core.types import Document, Fit, Operation

    versions = list(data.get("ops", []))
    for transaction in data.get("transactions", []):
        for state in (transaction.get("changes") or {}).values():
            versions.extend(
                version for version in (state.get("edited_ops") or {}).values() if version
            )
    if not any(version.get("op") == "create_lid" for version in versions):
        return data

    def lids(document: Document) -> dict[frozenset[str], Operation]:
        """Nur ein eindeutig belegtes Ausgabepaar bekommt eine Bindung."""
        found: dict[frozenset[str], Operation] = {}
        ambiguous: set[frozenset[str]] = set()
        for operation in document.ops:
            if operation.op != "create_lid" or len(operation.outputs) != 2:
                continue
            proposed = fit_for_lid(operation, ())
            key = frozenset((str(proposed.a), str(proposed.b)))
            if key in found:
                ambiguous.add(key)
            found[key] = operation
        return {key: operation for key, operation in found.items() if key not in ambiguous}

    original = document_from_data(data)
    existing = list(original.fits)
    for transaction in original.transactions:
        if transaction.changes is not None:
            for state in (transaction.changes.before, transaction.changes.after):
                existing.extend(state.fits or ())
    represented = {frozenset((str(fit.a), str(fit.b))) for fit in existing}
    missing: dict[frozenset[str], Operation] = {}
    history = History(original)
    while True:
        for key, operation in lids(original).items():
            if key in represented:
                continue
            value = operation.params.get("collar")
            if value is None:
                continue  # Die damalige Vorgabe war positiv, kein belegter flacher Deckel.
            try:
                value = resolve_value(value, resolve(original.parameters))
            except AppError, TypeError, ValueError, KeyError:
                continue
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and value <= 0.0
            ):
                missing[key] = operation
        if history.undo() is None:
            break

    additions: dict[frozenset[str], Fit] = {}
    for key, operation in sorted(missing.items(), key=lambda item: item[1].id):
        fit = fit_for_lid(operation, existing)
        additions[key] = fit
        existing.append(fit)

    def converted(document: Document) -> list[dict[str, Any]]:
        current_lids = lids(document)
        result = []
        for fit in document.fits:
            operation = current_lids.get(frozenset((str(fit.a), str(fit.b))))
            if operation is not None and fit.when_positive is None:
                fit = replace(fit, when_positive=(operation.id, "collar"))
            result.append(fit)
        living = _living_objects(document.ops)
        for key, fit in additions.items():
            operation = current_lids.get(key)
            if operation is not None and set(operation.outputs) <= living:
                result.append(replace(fit, when_positive=(operation.id, "collar")))
        return [fit_to_data(fit) for fit in result]

    original = document_from_data(data)
    history = History(original)
    after = converted(original)
    data["fits"] = after
    for transaction in reversed(data.get("transactions", [])):
        history.undo()
        before = converted(original)
        changes = transaction.get("changes") or {}
        if before != after or any(state.get("fits") is not None for state in changes.values()):
            changes.setdefault("before", {})["fits"] = before
            changes.setdefault("after", {})["fits"] = after
            transaction["changes"] = changes
        after = before
    return data


def _add_spool_bindings(data: dict[str, Any]) -> dict[str, Any]:
    """20 → 21: örtliche Spulen bleiben ohne ausdrückliche Wahl ungebunden."""
    settings = data.get("print_settings")
    if isinstance(settings, dict):
        settings.setdefault("spool_bindings", [])
        settings.setdefault("inventory_project_id", "")
    return data


def _add_slot_profile_bindings(data: dict[str, Any]) -> dict[str, Any]:
    """21 → 22: Alte Profilpositionen bleiben bis zur ausgewerteten Szene unverändert."""
    settings = data.get("print_settings")
    if isinstance(settings, dict):
        settings.setdefault("slot_profile_bindings", None)
    return data


def _remember_the_export(data: dict[str, Any]) -> dict[str, Any]:
    """22 → 23: Ein Projekt merkt sich Format und Namensschema (§29, RM-141).

    Beides leer heißt „noch nie exportiert": Dann gilt 3MF und die Vorgabe,
    die zur Zahl der Teile passt — genau das Verhalten, das eine Datei von
    vor diesem Schritt gewohnt ist.
    """
    data.setdefault("export", {"format": "", "scheme": ""})
    return data


def _add_protected_faces(data: dict[str, Any]) -> dict[str, Any]:
    """23 → 24: Gesperrte Sichtflächen stehen im Dokument (§22.3, RM-080).

    Eine ältere Datei hat keine Sperren, und ein leeres Wörterbuch sagt genau
    das: *Automatisch teilen* darf überall schneiden — so, wie es diese Datei
    immer getan hat. Bis zu diesem Schritt lebte die Markierung nur in der
    Ansicht und ging mit dem Schließen verloren.
    """
    data.setdefault("protected", {})
    return data


def _keep_raw_import_coordinates(data: dict[str, Any]) -> dict[str, Any]:
    """24 → 25: Bestehende Ladeschritte behalten ihre Rohachsen und Einheiten.

    Neue GLB-/GLTF-Importe folgen Meter und Y-oben. Das darf weder beim Öffnen
    noch nach Undo eine alte importierte oder erzeugte Quelle umdeuten.
    Deshalb werden auch sämtliche gespeicherten Änderungsseiten erfasst.
    """
    operations = list(data.get("ops", []))
    for transaction in data.get("transactions", []):
        for state in (transaction.get("changes") or {}).values():
            operations.extend((state.get("edited_ops") or {}).values())
    for operation in operations:
        if operation is not None and operation.get("op") == "load":
            operation.setdefault("params", {}).setdefault("coordinates", "legacy_raw")
    return data


def _allow_several_filament_colours(data: dict[str, Any]) -> dict[str, Any]:
    """25 → 26: Ein Filament darf mehrere Farben tragen (§20, 19.09.2026).

    Der Parameter ``colour`` von *Filament zuweisen* und *Filament auf eine
    Fläche* nimmt seither bis zu vier Farben, durch Leerzeichen getrennt —
    dieselbe Schreibweise, in der die Orca-Familie ein mehrfarbiges Filament
    führt. An einer älteren Datei ist nichts umzuschreiben: Eine Farbe ist
    weiterhin eine Farbe. Die Stufe steht trotzdem, und zwar für die andere
    Richtung: Ein älteres Programm, das eine Datei mit zwei Farben öffnete,
    hielte mitten in der Auswertung mit „Die Farbe wird als #RRGGBB
    angegeben" an — als wäre die Eingabe falsch. Mit der Versionsgrenze sagt
    es stattdessen, was gilt: Die Datei ist neuer, ein Update öffnet sie.
    """
    return data


def _qualify_match_answers(data: dict[str, Any]) -> dict[str, Any]:
    """26 → 27: Alte Antworten ohne erfundenen Körperbezug unter ``legacy`` erhalten.

    Auch jede gespeicherte Undo-Fassung trägt ihre eigenen unveränderten
    Abdrücke. Selbst ein früherer Merkmalsname ``legacy`` bleibt ein Name
    innerhalb dieser Hülle; der Serializer nimmt keine eigene Umstellung vor.
    """
    operations = list(data.get("ops", []))
    for transaction in data.get("transactions", []):
        changes = transaction.get("changes")
        if changes is None:
            continue
        if not isinstance(changes, dict):
            raise ValueError("schema:transactions.changes")
        for side in ("before", "after"):
            state = changes.get(side, {})
            if not isinstance(state, dict):
                raise ValueError(f"schema:transactions.changes.{side}")
            edited = state.get("edited_ops")
            if edited is None:
                continue
            if not isinstance(edited, dict):
                raise ValueError(f"schema:transactions.changes.{side}.edited_ops")
            operations.extend(edited.values())
    for operation in operations:
        if operation is None:
            continue
        if not isinstance(operation, dict):
            raise ValueError("schema:edited_operation")
        if operation.get("matches"):
            operation["matches"] = {"legacy": operation["matches"]}
    return data


def _allow_native_alias_groups(data: dict[str, Any]) -> dict[str, Any]:
    """27 → 28: Eine native Neuwahl reist als ``native-group:``-Antwort mit Scope.

    Wer am umgebauten exakten Körper gewählt hat, welche aktuelle Fläche einen
    alten Bezug fortführt, hat das in ``Operation.matches`` unter einer
    eigenen Domäne stehen — mit dem ``scope``, der Fassung des Erzeugers, für
    die die Wahl gilt (§21.3, P1.4c). An einer älteren Datei ist nichts
    umzuschreiben: Ihre Netzgruppen und ``legacy``-Abdrücke bleiben, wie sie
    sind, und keine davon wird als native Zustimmung umgedeutet oder mit einem
    Scope aus ungeprüfter Geometrie versehen. Die Stufe steht für die andere
    Richtung: Ein älteres Programm liest den Datensatz mit fünf Feldern als
    Schemafehler; mit der Versionsgrenze sagt es stattdessen, dass die Datei
    neuer ist und ein Update sie öffnet.
    """
    return data


def _allow_edge_answers(data: dict[str, Any]) -> dict[str, Any]:
    """28 → 29: Eine Kantenantwort reist als ``edge-answer:``-Datensatz am Eingang.

    Wer für *Verrunden*, *Fase* oder *Wulst* gewählt hat, welche von zwei
    Kanten mit demselben Schlüssel gemeint ist, hat das in
    ``Operation.matches`` unter einer dritten Domäne stehen — gebunden an den
    Eingangskörper, das Feld, das Schlüsselbündel und die Fassung des Eingangs
    (§21.3, P1.4c). An einer älteren Datei ist nichts umzuschreiben: Ihre
    Gruppen bleiben, wie sie sind, und aus keinem Schlüsselbündel wird eine
    Antwort erfunden. Die Stufe steht wieder für die andere Richtung: Ein
    älteres Programm läse den Datensatz als Schemafehler; mit der
    Versionsgrenze sagt es stattdessen, dass die Datei neuer ist.
    """
    return data


#: Welche Abläufe eine Passung aus dem Material gerechnet haben — Operation,
#: und die Merkmalsnamen der beiden Seiten.
_MATERIAL_FLOWS: Final[dict[str, tuple[frozenset[str], frozenset[str]]]] = {
    "create_lid": (frozenset({"lid_cavity"}), frozenset({"lid_collar"})),
    "screw_lid": (frozenset({"lid_neck_thread"}), frozenset({"lid_cap_thread"})),
}

#: Die Nahtpassungen des Teilens: Stift auf der einen Hälfte, Bohrung auf der anderen.
_SEAM_OPERATIONS: Final = frozenset({"split_pinned", "split_line"})


def _let_seam_and_lid_fits_follow_their_bodies(data: dict[str, Any]) -> dict[str, Any]:
    """29 → 30: Passungen aus *Teilen* und *Deckel* nennen kein Material mehr.

    Stifte, Kragen und Gewinde rechnen ihr Spiel aus dem Material, in dem ihre
    Körper gedruckt werden. Die Passung dazu schrieb bis Version 29 das
    Projektmaterial des Augenblicks fest (``auto:petg``), und nach einem
    Wechsel prüfte sie gegen ein Material, das niemand mehr druckt: geteilt in
    PETG, gerechnet in TPU, und der Prüfbericht meldete jeden Stift als
    verletzt (Durchsicht 0.5.0). Seitdem schreiben die Abläufe ``auto:``,
    und das folgt den Körpern (§14).

    **Umgeschrieben wird nur, was ein solcher Ablauf angelegt hat**, erkannt
    an der Operation, deren Ausgaben die Passung verbindet, und an den
    Merkmalsnamen, die er vergibt. Eine benannte Kennung an jeder anderen
    Passung bleibt stehen: Dort kann jemand ein Material mit Absicht gemeint
    haben (§12), und das zu überschreiben wäre geraten. In jedem gespeicherten
    Undo-Zustand gilt dasselbe, sonst holte ein Strg+Z die alte Kennung
    zurück.

    **Dieselbe Stufe führt ``carried_profiles`` ein** (``Document``): die
    eigenen Drucker und Materialien, die ein Projekt mitnimmt, damit es auf
    einem zweiten Rechner rechnet. Umzuschreiben ist dafür nichts — eine
    ältere Datei trägt keine, und das Speichern füllt das Feld. Die
    Versionsgrenze steht für die andere Richtung: Ein älteres Programm
    öffnete die Datei, fände den Drucker nicht und hielte an; so sagt es,
    dass die Datei neuer ist.
    """
    versions: list[dict[str, Any]] = [
        entry for entry in data.get("ops", []) if isinstance(entry, dict)
    ]
    for transaction in data.get("transactions", []):
        if not isinstance(transaction, dict):
            continue
        for state in (transaction.get("changes") or {}).values():
            if not isinstance(state, dict):
                continue
            versions.extend(
                version
                for version in (state.get("edited_ops") or {}).values()
                if isinstance(version, dict)
            )

    def side(reference: Any) -> tuple[str, str] | None:
        if not isinstance(reference, str) or ":" not in reference:
            return None
        object_id, feature_id = reference.split(":", 1)
        return object_id, feature_id

    def made_by_a_flow(fit: dict[str, Any]) -> bool:
        first, second = side(fit.get("a")), side(fit.get("b"))
        if first is None or second is None:
            return False
        for operation in versions:
            outputs = [str(entry) for entry in operation.get("out") or ()]
            name = operation.get("op")
            flow = _MATERIAL_FLOWS.get(str(name))
            if (
                flow is not None
                and outputs[:2] == [first[0], second[0]]
                and first[1] in flow[0]
                and second[1] in flow[1]
            ):
                return True
            if (
                name in _SEAM_OPERATIONS
                and {first[0], second[0]} <= set(outputs)
                and first[0] != second[0]
                and first[1].startswith("pin_")
                and second[1].startswith("bore_")
            ):
                return True
        return False

    def follow(fits: Any) -> None:
        if not isinstance(fits, list):
            return
        for fit in fits:
            if not isinstance(fit, dict):
                continue
            tolerance = fit.get("tolerance")
            if (
                isinstance(tolerance, str)
                and tolerance.startswith("auto:")
                and tolerance != "auto:"
                and made_by_a_flow(fit)
            ):
                fit["tolerance"] = "auto:"

    follow(data.get("fits"))
    for transaction in data.get("transactions", []):
        if not isinstance(transaction, dict):
            continue
        for state in (transaction.get("changes") or {}).values():
            if isinstance(state, dict):
                follow(state.get("fits"))
    return data


def _allow_curve_sketches(data: dict[str, Any]) -> dict[str, Any]:
    """30 → 31: Skizzen kennen Ellipse, Ellipsenbogen und drei Kurvenbedingungen.

    Ein Skizzentext darf seither die Elemente ``ellipse`` und
    ``elliptical_arc`` tragen und die Bedingungen ``on_curve``, ``smooth``
    und ``curvature``, deren Ziele auch Kurven nennen (RM-188 P6.6a/b). An
    einer älteren Datei ist nichts umzuschreiben: Ihre Linien, Kreise, Bögen
    und Splines bedeuten dasselbe wie vorher, und keine ihrer Bedingungen
    zeigt auf eine Kurve. Die Stufe steht für die andere Richtung: Ein
    älteres Programm hielte mitten in der Auswertung mit „Diese Elementart
    gibt es nicht" an — als wäre die Skizze beschädigt. Mit der
    Versionsgrenze sagt es stattdessen, dass die Datei neuer ist und ein
    Update sie öffnet.
    """
    return data


def _allow_suppressed_steps(data: dict[str, Any]) -> dict[str, Any]:
    """31 → 32: Ein Schritt kann ausgeschaltet sein, und der Verlauf baut sich um (P7).

    Ein ausgeschalteter Schritt trägt ``suppressed`` — ob er gewählt oder
    mitgenommen wurde, welche Merkmale seine Verweise trafen und welche
    Passungen mit ihm ruhen —, und eine Transaktion, die Schritte einfügt,
    verschiebt, aus- oder einschaltet, trägt ``revision``. Beides ist additiv:
    Eine ältere Datei hat keinen ausgeschalteten Schritt und keinen Umbau,
    umzuschreiben ist nichts, und nichts wird nachträglich als ausgeschaltet
    gedeutet. Die Stufe steht für die andere Richtung: Ein älteres Programm
    überläse ``suppressed`` und rechnete den ausgeschalteten Schritt mit — ein
    anderes Teil als das gespeicherte; mit der Versionsgrenze sagt es
    stattdessen, dass die Datei neuer ist.
    """
    return data


def _read_step_assemblies(data: dict[str, Any]) -> dict[str, Any]:
    """32 → 33: Eine STEP-Datei kommt als Baugruppe an (P7.4).

    Ein neuer Ladeschritt trägt in ``bodies`` die gewählten Körper der Datei
    und dazu die Haken fürs Bett und die Kopienummer wie ``load``. Ein
    älterer Schritt trägt nichts davon, und ohne ``bodies`` liest er die
    Datei wie bisher als einen Körper — derselbe Schritt ergibt dasselbe Teil
    (§15.1). Umzuschreiben ist also nichts.

    Die Stufe steht für die andere Richtung, wie 25 → 26: Ein älteres
    Programm, das einen Schritt mit ``bodies`` öffnete, hielte mitten in der
    Auswertung an einem unbekannten Parameter an — als wäre die Datei kaputt.
    Mit der Versionsgrenze sagt es, was gilt: Die Datei ist neuer, ein Update
    öffnet sie.
    """
    return data


def _allow_large_recognition_answers(data: dict[str, Any]) -> dict[str, Any]:
    """33 → 34: Vollerkennung großer Importe trägt eine ausdrückliche Antwort.

    Alte Projekte enthalten keine solche Wahl. Nichts wird freigegeben oder
    umgeschrieben; große Ladeschritte fragen erst bei ihrer nächsten Auswertung.
    Ältere Leser kennen die neue ``matches``-Domäne nicht und sollen das
    Projekt als neuer erkennen, statt eine gültige Antwort als Schaden zu melden.
    """
    return data


def _keep_repairs_as_they_were(data: dict[str, Any]) -> dict[str, Any]:
    """34 → 35: Gespeicherte Reparaturschritte lösen Überschneidungen nicht auf.

    Seit dem 24.09.2026 löst *Reparieren* Überschneidungen von sich aus auf
    (Entscheidung Robert). Ein Schritt speichert nur, was von der Vorgabe
    abweicht — auch der aus „Reparieren und erneut versuchen" trägt leere
    Parameter —, und ein alter Schritt ohne den Schlüssel hätte beim Öffnen
    still vereinigt, was er vorher nur gemeldet hat. Er bekommt deshalb den
    Wert, mit dem er damals rechnete; der Befund daran bietet das Auflösen an.
    Auch sämtliche gespeicherten Änderungsseiten werden erfasst — nur die zwei
    Seiten ``before`` und ``after``; was ``changes`` sonst trägt, ist kein
    Verlaufsstand.
    """
    operations = list(data.get("ops", []))
    for transaction in data.get("transactions", []):
        changes = transaction.get("changes")
        if not isinstance(changes, dict):
            continue
        for side in ("before", "after"):
            state = changes.get(side)
            if isinstance(state, dict) and isinstance(state.get("edited_ops"), dict):
                operations.extend(state["edited_ops"].values())
    for operation in operations:
        if isinstance(operation, dict) and operation.get("op") == "repair":
            params = operation.setdefault("params", {})
            if isinstance(params, dict):
                params.setdefault("self_intersections", False)
    return data


def _mark_own_print_settings(data: dict[str, Any]) -> dict[str, Any]:
    """35 → 36: Welche Druckeinstellungen eine eigene Wahl waren.

    Ab Format 36 weiß jeder Wert, woher er kommt (Konzept Herstellerprofil,
    27.09.2026): Nur die eigene Wahl und der übernommene Vorschlag gehen als
    Abweichung zum Slicer, alles andere kommt aus dem Profil des Herstellers.
    Eine ältere Datei trägt einen vollen Satz ohne Herkunft, und er belegt
    keine Entscheidung — die Übergabe, die Filamentzuweisung und das
    Rückgängigmachen schrieben den aufgelösten Satz ungefragt hinein.

    Als eigene Wahl gilt, was **weder** der heutigen Auflösung für Drucker,
    Material und Stufe des Projekts **noch** der Vorgabe der Dataclass
    gleicht (:func:`app.core.knowledge.print_settings.legacy_choices`) — und
    auch nicht der Auflösung, mit der die schreibende Version rechnete: bis
    0.5.0 die Tempi der Stufe ohne das Tempo des Druckers. Früher übernommene
    Vorschläge werden dabei eigene Wahl; sie galten schon bisher der ganzen
    Platte.

    **Wie** :func:`_bind_old_lid_fits` **ruft dieser Schritt die heutigen
    Funktionen** — die Auflösung von heute ist der Vergleich. Festgehalten
    ist er an ``tests/data/projects/print_settings_v33.p3d``, gespeichert von
    Solidon 0.5.0 selbst. Das Profil ist das der Sitzung, einschließlich eines
    Druckers, den nur das Projekt mitbringt
    (:func:`app.core.knowledge.profiles.project_profile`).
    """
    stored = data.get("print_settings")
    if not isinstance(stored, dict) or not _readable_print_settings(stored):
        # Ein beschädigter Satz bleibt, wie er ist: Die Schemaprüfung nach der
        # Migration meldet ihn mit Handlungsvorschlag. Hier gelesen, wäre er
        # ein ``AttributeError`` — ein Programmierfehler mit Fehlerbericht
        # (Review Stufe A+B, R1).
        return data
    from app.core.errors import AppError
    from app.core.knowledge import print_settings, profiles
    from app.core.scene.serialise import print_settings_from_data
    from app.core.types import PrintSettings

    found = data.get("scene")
    scene: dict[str, Any] = found if isinstance(found, dict) else {}
    printer = str(scene.get("printer", ""))
    material = profiles.material_for(printer, str(scene.get("material", "")))
    settings = print_settings_from_data(stored, material)
    carried = data.get("carried_profiles")
    references: tuple[PrintSettings, ...]
    try:
        profile = profiles.project_profile(
            printer, material, carried if isinstance(carried, dict) else None
        )
        references = (
            print_settings.resolve(profile, settings.quality),
            print_settings.resolve(profile, settings.quality, legacy=True),
        )
    except AppError, KeyError, ValueError:
        references = ()
    stored["chosen"] = sorted(print_settings.legacy_choices(settings, *references))
    stored["accepted"] = []
    return data


#: Die Gruppen eines Druckeinstellungssatzes — je eine Zuordnung.
_SETTING_GROUP_NAMES: Final = (
    "layers",
    "shell",
    "infill",
    "temperature",
    "cooling",
    "speed",
    "support",
    "adhesion",
    "retraction",
    "filament",
)


def _readable_print_settings(stored: dict[str, Any]) -> bool:
    """Hat der Satz die Form, die ``print_settings_from_data`` liest?

    Geprüft wird nur die Form, nicht der Inhalt: jede Gruppe eine Zuordnung,
    die Stufe ein Text, die Spulen- und Slotlisten Listen aus Zuordnungen.
    Einen falschen Wert darin meldet die Schemaprüfung selbst.
    """
    if not all(isinstance(stored.get(group, {}), dict) for group in _SETTING_GROUP_NAMES):
        return False
    if not isinstance(stored.get("quality", "standard"), str):
        return False
    for key in ("spool_bindings", "slot_overrides", "slot_profile_bindings"):
        value = stored.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            return False
    return isinstance(stored.get("slot_profiles", []), list)


#: Die Operationen, die Kanten nach ihrer Lage wählen (``edges`` als Gruppe).
_EDGE_GROUP_OPERATIONS: Final = frozenset({"fillet_edges", "chamfer_edges", "bead_edges"})


def _keep_edge_groups_as_they_were(data: dict[str, Any]) -> dict[str, Any]:
    """36 → 37: Gespeicherte Kantengruppen zählen jeden Ring weiter als waagerecht.

    Seit RM-279 nimmt eine Gruppe nach Lage einen geschlossenen Ring nur,
    wenn er waagerecht liegt (``edges.choose`` über ``edge_lie_of``); die
    Mündung einer Querbohrung gehört zu keiner. Bis Format 36 galt ``flat`` an
    jedem Ring — „alle waagerechten Kanten“, „oben“ und „unten“ konnten die
    Mündungen einer Querbohrung mitrunden. Ein alter Schritt bekommt deshalb
    ``rings_by_plane = False`` und trifft beim Öffnen dieselben Kanten wie
    beim Speichern. Wie 34 → 35 auch in den gespeicherten Fassungen ``before``
    und ``after`` jeder Änderung; ein Schritt, der den Schlüssel schon trägt,
    bleibt, wie er ist. Festgehalten an ``tests/data/projects/edge_groups_v36.p3d``,
    geschrieben vom Stand vor der Änderung.
    """
    operations = list(data.get("ops", []))
    for transaction in data.get("transactions", []):
        changes = transaction.get("changes")
        if not isinstance(changes, dict):
            continue
        for side in ("before", "after"):
            state = changes.get(side)
            if isinstance(state, dict) and isinstance(state.get("edited_ops"), dict):
                operations.extend(state["edited_ops"].values())
    for operation in operations:
        if isinstance(operation, dict) and operation.get("op") in _EDGE_GROUP_OPERATIONS:
            params = operation.setdefault("params", {})
            if isinstance(params, dict):
                params.setdefault("rings_by_plane", False)
    return data


def _place_further_models_freely(data: dict[str, Any]) -> dict[str, Any]:
    """37 → 38: Ein weiteres Modell kommt an eine freie Stelle (Robert, 28.09.2026).

    Neue Ladeschritte nach dem ersten tragen ``free_spot`` (``load`` und
    ``load_step``) und legen das Modell aufgesetzt an die erste freie Stelle,
    die sie einmal rechnen und in ``spot_x``, ``spot_y``, ``spot_plate``
    festhalten; ein erzeugtes Modell trägt beides an ``fit_to_size`` (Weg 3).
    Ein älterer Schritt trägt den Schalter nicht, und ohne ihn bleibt das
    Modell an seinen Dateikoordinaten wie gespeichert — umzuschreiben ist
    also nichts (festgehalten an ``tests/data/projects/further_model_v37.p3d``).

    Die Stufe steht für die andere Richtung wie 32 → 33: Ein älteres Programm
    hielte an dem unbekannten Parameter mitten in der Auswertung an, als wäre
    die Datei kaputt; mit der Versionsgrenze sagt es, dass ein Update sie
    öffnet.
    """
    return data


#: Die Schritte, deren Langloch ihren Winkel im Rahmen der Normalen des Schritts zählen.
_SLOTTED_DRILLS: Final = frozenset({"drill_hole", "drill_brep_hole"})


def _keep_slot_directions_as_they_were(data: dict[str, Any]) -> dict[str, Any]:
    """38 → 39: Ein gespeicherter Langlochwinkel meint weiter dieselbe Richtung.

    Seit dem 30.09.2026 zählt der Winkel eines Langlochs gegen
    ``prepare.slot_frame``: Eine Achse im Messrauschen neben einer Hauptachse
    gilt als die Hauptachse. Bis Format 38 zählte er gegen ``frame_of`` der
    Achse, und dort bestimmte das Rauschen die erste Rahmenachse — derselbe
    Winkel meinte heute eine andere Richtung, und ein gespeichertes Langloch
    stünde nach dem Update verdreht im Teil.

    **Bei der Auswertung umrechnen, nicht in der Datei.** Ein gespeicherter
    Winkel kann ein Ausdruck über Projektparameter sein. Sein Zahlenwert und
    die Achse, auf die er wirkt, können sich bei jeder Auswertung ändern. Die
    Migration markiert deshalb nur alte Langlöcher mit ``measured_frame``;
    die Operation rechnet den unveränderten Winkel anhand der dann aufgelösten
    Achse um. So bleiben Winkel- und Achsausdrücke auch nach Verlauf,
    Speichern und erneutem Öffnen gebunden.

    * *Bohrung setzen* mit Haken *Langloch* liest seine Normale aus den
      aufgelösten Parametern. Ohne Normale gilt eine Hauptachse; beide Rahmen
      stimmen dort überein.
    * *Zum Langloch ziehen* liest die Achse des erkannten Merkmals erst bei der
      Auswertung. Der Marker bleibt im Schritt, damit auch spätere Änderungen
      an vorherigen Schritten dieselbe alte Winkelbedeutung behalten.

    Wie 34 → 35 auch in den gespeicherten Fassungen ``before`` und ``after``
    jeder Änderung; ein Schritt, der den Schlüssel schon trägt, bleibt, wie er
    ist. Festgehalten an ``tests/data/projects/slot_angle_frame_v38.p3d``,
    geschrieben vom Stand vor der Änderung.
    """
    operations = list(data.get("ops", []))
    for transaction in data.get("transactions", []):
        changes = transaction.get("changes")
        if not isinstance(changes, dict):
            continue
        for side in ("before", "after"):
            state = changes.get(side)
            if isinstance(state, dict) and isinstance(state.get("edited_ops"), dict):
                operations.extend(state["edited_ops"].values())
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        kind = operation.get("op")
        if kind != "slot_hole" and kind not in _SLOTTED_DRILLS:
            continue
        params = operation.setdefault("params", {})
        if not isinstance(params, dict):
            continue
        if kind == "slot_hole":
            params.setdefault("measured_frame", True)
            continue
        if params.get("slotted") is not True:
            continue
        params.setdefault("measured_frame", True)
    return data


def _keep_sculpt_mirrors_as_they_were(data: dict[str, Any]) -> dict[str, Any]:
    """Format 39 → 40: Formsitzungen spiegeln bisher am Nullpunkt der Szene.

    Seit RM-363 gehen die Symmetrieebenen durch die Mitte des Körpers
    (``mirror_at_body``). Ein altes Projekt mit Symmetrie an einem Körper
    abseits der Mitte sähe nach dem Öffnen anders aus — deshalb bekommt jeder
    vorhandene Formschritt den alten Bezug ausdrücklich, auch in den
    gespeicherten Fassungen ``before`` und ``after`` jeder Änderung. Ein
    Schritt, der den Schlüssel schon trägt, bleibt, wie er ist. Festgehalten
    an ``tests/data/projects/sculpt_mirror_v39.p3d``, geschrieben vom Stand
    vor der Änderung.
    """
    operations = list(data.get("ops", []))
    for transaction in data.get("transactions", []):
        changes = transaction.get("changes")
        if not isinstance(changes, dict):
            continue
        for side in ("before", "after"):
            state = changes.get(side)
            if isinstance(state, dict) and isinstance(state.get("edited_ops"), dict):
                operations.extend(state["edited_ops"].values())
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") != "sculpt_strokes":
            continue
        params = operation.setdefault("params", {})
        if isinstance(params, dict):
            params.setdefault("mirror_at_body", False)
    return data


def _keep_sculpt_brushes_as_they_were(data: dict[str, Any]) -> dict[str, Any]:
    """Format 40 → 41: Formsitzungen behalten den Pinsel, mit dem sie gemalt wurden.

    Seit RM-376 bewegt ein Zug nur dem Pinsel zugewandte Punkte
    (``front_only``), seit RM-378 wirkt ein Zug auf der Symmetrieebene nur
    einmal (``mirror_once``). Ein altes Projekt sähe damit anders aus; jeder
    vorhandene Formschritt bekommt beide Schalter aus, auch in den
    gespeicherten Fassungen jeder Änderung. Festgehalten an
    ``tests/data/projects/sculpt_brush_v40.p3d``, geschrieben vom Stand davor.
    """
    operations = list(data.get("ops", []))
    for transaction in data.get("transactions", []):
        changes = transaction.get("changes")
        if not isinstance(changes, dict):
            continue
        for side in ("before", "after"):
            state = changes.get(side)
            if isinstance(state, dict) and isinstance(state.get("edited_ops"), dict):
                operations.extend(state["edited_ops"].values())
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") != "sculpt_strokes":
            continue
        params = operation.setdefault("params", {})
        if isinstance(params, dict):
            params.setdefault("front_only", False)
            params.setdefault("mirror_once", False)
    return data


def _name_the_cut_plane(data: dict[str, Any]) -> dict[str, Any]:
    """Format 41 → 42: Ein Schnitt *An Fläche* sagt, dass er an einer Fläche hängt.

    *Abschneiden* trägt seit RM-400 ein Feld ``plane``: an einer Achse, an einer
    Fläche, durch eine Kante oder durch drei Punkte. Bis Format 41 hieß ein
    gesetztes ``at_feature`` „parallel zu dieser Fläche“, und Achse und Neigung
    standen wirkungslos daneben (M4 der Nachprüfung). Jeder solche Schritt
    bekommt ``plane = "at_face"`` und trägt seine Position als ``offset`` weiter,
    auch in den gespeicherten Fassungen jeder Änderung; ein Schritt ohne
    Fläche schneidet an der Achse wie bisher, die Vorgabe von ``plane``.
    Festgehalten an ``tests/data/projects/cut_away_face_v41.p3d``, geschrieben
    vom Stand davor.
    """
    operations = list(data.get("ops", []))
    for transaction in data.get("transactions", []):
        changes = transaction.get("changes")
        if not isinstance(changes, dict):
            continue
        for side in ("before", "after"):
            state = changes.get(side)
            if isinstance(state, dict) and isinstance(state.get("edited_ops"), dict):
                operations.extend(state["edited_ops"].values())
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") != "cut_away":
            continue
        params = operation.get("params")
        if isinstance(params, dict) and params.get("at_feature"):
            params.setdefault("plane", "at_face")
            # Die Position zählte dort von der Fläche aus; das tut jetzt der Abstand.
            if "position" in params:
                params.setdefault("offset", params["position"])
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
    Step(from_version=15, to_version=16, apply=_keep_reports_without_suggestions_valid),
    Step(from_version=16, to_version=17, apply=_allow_removed_operations),
    Step(from_version=17, to_version=18, apply=_allow_a_named_pivot),
    Step(from_version=18, to_version=19, apply=_name_the_radius_a_radius),
    Step(from_version=19, to_version=20, apply=_keep_explicit_choices),
    Step(from_version=20, to_version=21, apply=_add_spool_bindings),
    Step(from_version=21, to_version=22, apply=_add_slot_profile_bindings),
    Step(from_version=22, to_version=23, apply=_remember_the_export),
    Step(from_version=23, to_version=24, apply=_add_protected_faces),
    Step(from_version=24, to_version=25, apply=_keep_raw_import_coordinates),
    Step(from_version=25, to_version=26, apply=_allow_several_filament_colours),
    Step(from_version=26, to_version=27, apply=_qualify_match_answers),
    Step(from_version=27, to_version=28, apply=_allow_native_alias_groups),
    Step(from_version=28, to_version=29, apply=_allow_edge_answers),
    Step(from_version=29, to_version=30, apply=_let_seam_and_lid_fits_follow_their_bodies),
    Step(from_version=30, to_version=31, apply=_allow_curve_sketches),
    Step(from_version=31, to_version=32, apply=_allow_suppressed_steps),
    Step(from_version=32, to_version=33, apply=_read_step_assemblies),
    Step(from_version=33, to_version=34, apply=_allow_large_recognition_answers),
    Step(from_version=34, to_version=35, apply=_keep_repairs_as_they_were),
    Step(from_version=35, to_version=36, apply=_mark_own_print_settings),
    Step(from_version=36, to_version=37, apply=_keep_edge_groups_as_they_were),
    Step(from_version=37, to_version=38, apply=_place_further_models_freely),
    Step(from_version=38, to_version=39, apply=_keep_slot_directions_as_they_were),
    Step(from_version=39, to_version=40, apply=_keep_sculpt_mirrors_as_they_were),
    Step(from_version=40, to_version=41, apply=_keep_sculpt_brushes_as_they_were),
    Step(from_version=41, to_version=42, apply=_name_the_cut_plane),
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
