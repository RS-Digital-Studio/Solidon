"""Der Ergebnis-Cache über dem Operations-Hash (Bauplan §15, §38).

Zwei Ebenen. Im Speicher eine LRU-Ablage, begrenzt über die Bytes, die ihre
Netze samt deren Cache halten, und über die Dreieckszahl (RM-567,
:data:`MEMORY_SHARE`). Auf der Platte dieselben
Ergebnisse unter demselben Hash, damit das Wiederöffnen eines Projekts nicht
den ganzen Stapel neu rechnet (§31: unter einer Sekunde aus dem
Platten-Cache).

Geschrieben wird der Cache nur nach einem vollständigen Lauf (§15.6) — ein
abgebrochener darf keinen halben Stapel hinterlassen.

Ein Netz zu serialisieren braucht den Geometriekern, den der Kern nicht
importiert. Die Plattenebene nimmt darum einen :class:`MeshCodec` von außen;
ohne ihn bleibt sie abgeschaltet, und es gibt nur die Speicherebene.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import struct
import threading
import zipfile
import zlib
from collections import OrderedDict
from collections.abc import Callable, Collection, Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final, Protocol, cast

from app.core.errors import AppError
from app.core.log import get_logger
from app.core.paths import ensure_dir, results_cache_dir
from app.core.scene.serialise import (
    finding_from_data,
    finding_to_data,
    solver_from_data,
    solver_to_data,
    translatable_values_from_data,
    translatable_values_to_data,
)
from app.core.types import (
    Feature,
    FeatureContinuation,
    FeatureRef,
    Finding,
    MaterialSlot,
    Mesh,
    SceneObject,
    SolverInfo,
    SurfacePatch,
    Transform,
)
from app.i18n import TranslatableText

_log = get_logger(__name__)

#: Grobe Obergrenze im Speicher. Eine Million Dreiecke ist das
#: Viewport-Ziel (§31).
DEFAULT_TRIANGLE_BUDGET: Final = 20_000_000

#: **Die Grenze, die wirklich hält, zählt Bytes** (RM-567). Die Dreiecke
#: darüber sagen nicht, was ein Eintrag hält: ein Netz mit allem, was
#: ``trimesh``, die Erkennung und der Prüfbericht an ihm merken, 157 bis 644
#: Byte je Dreieck und eine Schichtanalyse von 108 MB dazu (Laptop-Riser,
#: 08.10.2026). Zwanzig Millionen Dreiecke waren damit drei bis dreizehn
#: Gigabyte; im Fenster hielt jedes Verschieben am Spiderman (886 000
#: Dreiecke) 230 MB mehr fest, ohne dass je etwas verdrängt wurde. Die
#: Speicherebene hält deshalb höchstens ein Achtel des eingebauten
#: Arbeitsspeichers — auf 8 GB ein Gigabyte, auf 16 GB zwei —, mindestens
#: :data:`MEMORY_FLOOR`, höchstens :data:`MEMORY_CEILING`. Was sie verdrängt,
#: liegt weiter auf der Platte und kommt von dort zurück.
MEMORY_SHARE: Final = 8
MEMORY_FLOOR: Final = 512 * 1024 * 1024
MEMORY_CEILING: Final = 4 * 1024 * 1024 * 1024
#: Wovon die Grenze ausgeht, wenn der Rechner seinen Speicher nicht nennt.
ASSUMED_MEMORY: Final = 8 * 1024 * 1024 * 1024
#: Was ein Körper je Dreieck hält, der seinen Speicher nicht selbst nennt —
#: ein exakter Körper oder ein Prüfnetz der Tests: Ecken und Dreiecke, ohne
#: Cache.
FALLBACK_BYTES_PER_TRIANGLE: Final = 36


def default_memory_budget() -> int:
    """Wie viel die Speicherebene auf diesem Rechner höchstens hält, in Bytes."""
    from app.core.memory import physical_memory

    installed = physical_memory() or ASSUMED_MEMORY
    return max(MEMORY_FLOOR, min(MEMORY_CEILING, installed // MEMORY_SHARE))


def held_by(
    result: CachedResult,
    kept: Collection[int] = (),
    seen: set[int] | None = None,
    freeable: list[int] | None = None,
    counted: dict[int, tuple[Any, int, dict[int, tuple[object, int]]]] | None = None,
) -> int:
    """Wie viele Bytes ein Eintrag gerade hält — Netze samt Cache, Merkmale.

    Gemessen wird nicht einmal für immer: Ein Netz im Cache ist dasselbe
    Objekt wie in der Szene, und was später an ihm gerechnet wird —
    Nachbarschaften, die Schichtanalyse des Prüfberichts —, hängt sich an ihn
    und wiegt mit. Netze, deren Nummer (``id``) in ``kept`` steht, hält die
    Szene ohnehin; sie zählen hier nicht. Felder, deren Nummer in ``seen``
    steht, sind schon gezählt — ein bewegtes Netz teilt seine
    Nachbarschaften mit seinem Quellnetz (``transform._carry_cache``).
    ``freeable`` sammelt in seinem ersten Element, was schlanke Netze davon
    freigäben (``MeshData.lean``).

    ``counted`` merkt die Bytes je Merkmalssatz: Ein Eintrag ändert seine
    Merkmale nie, und sie jedes Mal neu zu zählen kostete am Eiffelturm
    (4 878 Merkmale, neun Einträge) 1,4 s je ``trim``. Gemerkt wird je Satz
    sein Rest und seine großen Behälter (``memory.held_parts``): Was zwei
    Sätze teilen — die Dreiecksnummern eines bewegten Merkmals —, zählt
    einmal; je Satz für sich gezählt, hielt die Grenze am Laptop-Riser nach
    vier Verschieben 150 statt 122 MB (Nachprüfung L, M-3).
    """
    from app.core.memory import held_bytes, held_parts

    seen = set() if seen is None else seen
    total = 0
    for entry in result.objects:
        if id(entry.mesh) in kept:
            continue
        total += _mesh_bytes(entry.mesh, seen, freeable)
        if counted is None:
            total += held_bytes(entry.features, seen)
            continue
        features = entry.features
        known = counted.get(id(features))
        if known is None or known[0] is not features:
            known = (features, *held_parts(features))
            counted[id(features)] = known
        if id(features) in seen:
            continue
        total += known[1]
        # Der Satz selbst kann einer seiner Teile sein; erst danach als
        # gezählt vermerkt.
        for identity, (_holder, size) in known[2].items():
            if identity not in seen:
                seen.add(identity)
                total += size
        seen.add(id(features))
    return total


def _mesh_bytes(mesh: Mesh, seen: set[int], freeable: list[int] | None = None) -> int:
    """Ein Netz samt dem, was die Erkennung für seinen Körper gemerkt hat.

    Die Merker der Erkennung hängen am Körper und gehen mit ihm
    (``perceive.features.held_answers``); wer das Netz hält, hält sie mit.
    """
    from app.core.memory import held_bytes

    measure = getattr(mesh, "held_bytes", None)
    if not callable(measure):
        return mesh.triangle_count * FALLBACK_BYTES_PER_TRIANGLE
    total = int(measure(seen, freeable))
    raw = getattr(mesh, "raw", None)
    if raw is not None:
        from app.core.perceive.features import held_answers

        # Je Merker einzeln: Die Liste ist gemischt, und ihre Folge kommt
        # aus einer Menge (Review L, M1). Sie hängen am alten Körper und
        # gehen mit ihm, wenn ein schlankes Netz ihn ersetzt.
        answers = sum(held_bytes(answer, seen) for answer in held_answers(raw))
        total += answers
        if freeable is not None:
            freeable[0] += answers
    return total


def _held_signature(result: CachedResult) -> tuple[tuple[int, int, int], ...]:
    """Woran zu sehen ist, ob ein Eintrag seit der letzten Messung gewachsen ist.

    Je Körper sein Netz und die Zahl der Einträge in dessen Cache. Gewachsen
    ist er nur, wenn dort etwas dazukam; neu zu messen kostet am Riser 5 ms
    und mit Schichtanalyse 40 ms — je Ablegen über alle Einträge zu viel.
    """
    signature = []
    for entry in result.objects:
        raw = getattr(entry.mesh, "raw", None)
        cache = getattr(getattr(raw, "_cache", None), "cache", None)
        signature.append(
            (id(entry.mesh), len(cache) if isinstance(cache, dict) else 0, len(entry.features))
        )
    return tuple(signature)


def _memo_bytes(seen: set[int] | None = None) -> int:
    """Was die Merker der Auswertung halten; sie zählen in derselben Grenze (Review L, G3).

    Der Merker der Zuordnung (``perceive.matching.matched_bytes``) und der
    gemerkten Zuordnungsschritte samt Teilhashes
    (``scene.evaluate.remembered_bytes``, RM-593). Sie gehören keinem Eintrag
    und werden hier nicht verdrängt — ihre eigenen Grenzen zählen Kennungen
    und Merkmale.

    Mit ``seen`` — den schon gezählten Feldern der Einträge — zählen die
    Schritte nur, was sie darüber hinaus halten: Ihre bewegten Merkmale teilen
    die Dreiecksnummern mit den Einträgen (Nachprüfung L, M-3). Ohne ``seen``
    ihr Gewicht über den eigenen Eintrag hinaus, eine Obergrenze.
    """
    from app.core.perceive.matching import matched_bytes
    from app.core.scene.evaluate import remembered_bytes, remembered_parts

    if seen is None:
        return matched_bytes() + remembered_bytes()
    steps = 0
    for rest, parts in remembered_parts():
        steps += rest
        for identity, (_holder, size) in parts.items():
            if identity not in seen:
                seen.add(identity)
                steps += size
    return matched_bytes() + steps


def _release_steps(excess: int) -> int:
    """Gibt gemerkte Zuordnungsschritte frei, wenn das allein die Grenze hält; nennt die Bytes.

    Vor dem Verdrängen eines Eintrags (``ResultCache.trim``): Ein vergessener
    Schritt kostet die nächste Auswertung seine Zuordnung, ein verdrängter
    Eintrag sein ganzes Ergebnis. Reicht der ganze Merker nicht, bleibt er —
    sonst gäbe jede Auswertung ihn frei und merkte ihn wieder, und am
    Eiffelturm unter zu knapper Grenze ordnete jede Auswertung jeden Schritt
    neu zu (Paket L). Der Merker der Zuordnung bleibt immer; seine Grenze
    zählt Kennungen.
    """
    from app.core.scene.evaluate import release_remembered_steps, remembered_bytes

    if remembered_bytes() < excess:
        return 0
    return release_remembered_steps(excess)


def _leaner(result: CachedResult, kept: Collection[int]) -> CachedResult:
    """Der Eintrag mit schlanken Netzen (``MeshData.lean``) außer denen der Szene."""
    objects = []
    changed = False
    for body in result.objects:
        lean = getattr(body.mesh, "lean", None)
        if id(body.mesh) in kept or not callable(lean):
            objects.append(body)
            continue
        mesh = lean()
        changed |= mesh is not body.mesh
        objects.append(body if mesh is body.mesh else replace(body, mesh=mesh))
    return replace(result, objects=tuple(objects)) if changed else result


#: Obergrenze des Platten-Caches; die ältesten Einträge gehen zuerst.
DEFAULT_DISK_BUDGET_BYTES: Final = 2 * 1024 * 1024 * 1024

#: Wie viele Halte der vollen Kette die Speicherebene behält (``refuse``). Ein
#: Satz je Schritt, kein Netz — die Grenze hält nur eine lange Sitzung klein.
_REFUSALS_KEPT: Final = 256

#: Der Stand der Geometrie- und Merkmalsauskunft, den ein Eintrag tragen muss.
#: Derselbe Stand geht in den Operationshash ein und entwertet die
#: Speicherebene; alte Einträge sind Fehltreffer. Was ihn bisher hob, in der
#: Reihenfolge der Änderungen — die letzten beiden mit Nummer:
#:
#: - exakte Blindböden, Gewinde und eindeutige Innen-/Außenrollen für Passungen;
#: - zusammengefasste Langlochwände und radial bearbeitbare Zylinderwände;
#: - lokale Flächenrollen, kleine Funktionsflächen und aufgelöste kurze Gewinde;
#: - lokale Merkmale, transformierte Suchumfänge und gerichtete B-Rep-Gewinde;
#: - maßgeänderte Sackböden mit ihrer vollständigen Fläche;
#: - die weiteren Farben eines Materialslots (``extra_colours``, 19.09.2026);
#: - native Flächenhistorie und ungerundete Integrale statt alter
#:   Tessellierungs- und Maßauskünfte, auch in vernetzten Folgeergebnissen;
#: - bestätigte Ebenen und Zylinder aus NURBS-Trägern — leere frühere
#:   Auskünfte tragen keine Folgeoperation weiter;
#: - Innenräume mit vollständigen Luftgrenzen ohne Materialinseln;
#: - dieselbe eindeutige Erzeugerzuordnung für native wie für Netzmerkmale;
#: - vollständige Mess- und Attributdaten für Konturmaße, native Ringmerkmale
#:   und native Filamentflächen;
#: - Rundflächenmaße, rationale Kugelträger und die ausdrückliche Herkunft
#:   jedes Maßes;
#: - Teilträger und ihre Originaldreiecke;
#: - Antworten konkurrierender bisheriger Merkmale als ganze Gruppe;
#: - Folgehashes mit der tatsächlichen Bindung samt aktuellen Flächenträgern;
#: - belegte Übergänge alter Merkmale (``continuations``): ein Eintrag ohne das
#:   Feld kennt keinen Beleg und wird neu gerechnet;
#: - 22 (20.09.2026, P2.5): ein gemessenes Gewinde trägt Händigkeit, Gangzahl,
#:   Vorschub, Kamm- und Grundradius und seine Wendelabweichung;
#: - 23 (21.09.2026): `object_hash` hasht Dreiecksnummern als Bytes und
#:   Fließkommawerte über `float()` — dieselbe Auskunft, ein anderer Schlüssel.
#: - 24 (22.09.2026, RM-071): der Profilschlüssel trägt das Druckverfahren,
#:   Pixelgröße und Mindestwand des Druckers — ein auf Resin umgestelltes
#:   Projekt rechnet seine Befunde neu statt sie aus dem FDM-Cache zu holen.
#: - 25 (22.09.2026, Durchsicht 0.5.0): der Profilschlüssel trägt die
#:   Düsenzahl, und der Operationsschlüssel das Profil jedes Eingangs mit
#:   eigenem Material — eine geänderte Düsenzahl ordnet neu an, ein
#:   kalibriertes Körpermaterial bohrt neu.
#: - 26: vollständige Topologieauskunft nach Aufsetzen und Zentrieren beim
#:   Import; zuvor abgewiesene Folgeoperationen werden neu gerechnet.
#: - 27: Kreisfits mit plattformgleicher QR-Rechnung statt LAPACK; alte
#:   Mittelpunktwerte und Folgegeometrie werden neu gerechnet. Eigenständige
#:   Senkungen verwenden ihren echten Boden statt eines neu gefächerten Deckels.
#: - 28 (24.09.2026): eine gerundete Seite nimmt jede koplanare Facette ganz,
#:   die an ihre Rundungsnaht grenzt — gespeicherte Merkmale sind zu klein.
#: - 29 (26.09.2026): das Ergebnis von *Kanten verfeinern* trägt seinen
#:   Herkunftsvermerk auf der Platte (``refined_from``). Ein älterer Eintrag hat
#:   ihn nicht, und am feineren Netz liefe die Erkennung nach dem Öffnen neu —
#:   mit anderen Merkmalen als in der Sitzung. Dazu lesen sich gespeicherte
#:   Merkmale neu: Die Ebenenregel zählt eine geteilte Facette höchstens je
#:   Umrissecke, eine Naht teilt einen Mantel in Bohrung und Kegel, ein
#:   exakter Baustein liest sein Ergebnis aus der Topologie, und ein Lochfeld
#:   am Netz gibt nur noch seine benannten Bohrungen aus.
#: - 30 (27.09.2026, R1-Rest): Ein Netz nach *Kanten verfeinern* trägt je
#:   Dreieck seinen Ursprung (``geom.mesh.refined_units``) durch die folgenden
#:   Schritte und auf die Platte (``MeshData.to_bytes``), und die Erkennung
#:   zählt danach je Ursprung. Ein älterer Eintrag hat ihn nicht; an einem
#:   geteilten und danach gebohrten Netz läse die Erkennung nach dem Öffnen
#:   anders als in der Sitzung. Und am exakten Körper gehört die Fase einer
#:   schrägen Mündung zum Langloch, auch wo OpenCASCADE sie als BSpline führt.
#: - 31 (27.09.2026, RM-261): Das Ergebnis einer Booleschen trägt jedes
#:   Dreieck, das der Schnitt nicht berührt hat, in der Darstellung seines
#:   Eingangs — Eckenfolge und Reihenfolge der Ecken
#:   (``geom.attributes.in_source_layout``). Ein älterer Eintrag trägt die des
#:   Kerns, und die Erkennung läse nach dem Öffnen in den letzten Stellen
#:   anders als in der Sitzung.
#: - 32 (28.09.2026): Ein Schritt, der keinen Prozesswert liest
#:   (``OperationSpec.reads_process``), trägt Schichthöhe, Bahnbreite und
#:   Überhanggrenze nicht mehr im Schlüssel — Laden, Kopieren und Verschieben
#:   bleiben, wenn der Druckdialog sie ändert.
#: - 33 (28.09.2026, freie Stelle): Ein Eintrag trägt die Antworten seines
#:   Schritts (``answered``) — die erkannte Einheit, die freie Stelle. Ein
#:   älterer Eintrag hat sie nicht, und ein Treffer ließe den Schritt
#:   unbeantwortet: Das weitere Modell suchte seine Stelle bei jeder Änderung
#:   davor neu.
#: - 34 (RM-308): sich kreuzende Schnittsegmente tragen ihre Fläche und
#:   Innenlöcher; alte Ausrichtungen und daraus erzeugte Körper rechnen neu.
#: - 35 (RM-253/RM-319): Die Schnitt- und Kontaktklassifikation hat sich
#:   geändert. Ältere Reparaturergebnisse müssen neu berechnet werden.
#: - 36 (RM-381/RM-382/RM-383): Die Boolesche Vorvereinigung prüft auch
#:   Szenenkörper als Werkzeug, rechnet an nicht vereinbaren Teilen mit Befund
#:   statt anzuhalten, und der Ort von ``boolean.parts_united`` kommt aus der
#:   Suche über Hüllquaderbäume. Gespeicherte Ergebnisse trügen alte Befunde.
#: - 37 (RM-485): Gerichtete Schichtschnitte halten eingeschlossene Luft frei.
#:   Ausrichtungen und Auto-Split-Ergebnisse aus der alten Materialfläche
#:   müssen neu berechnet werden.
#: - 38 (RM-486): Clipper-Säulen ersetzen GEOS-Differenzen. Gespeicherte
#:   Ausrichtungen rechnen mit den neuen Stützkennzahlen erneut.
#: - 39 (RM-388/RM-450): Merkmalsnamen folgen belegten Übergängen unabhängig
#:   von späteren Verbrauchern; geteilte Flächen behalten nur räumlich belegte
#:   Nachfolger. Frühere Bindungen werden mit denselben Schritten neu bestimmt.
#: - 40: Importierte Musterfelder werden nach Lage und Richtung getrennt;
#:   örtlich erkannte Muster ersetzen ihre alten Zellmerkmale auch im Folgeschritt.
#: - 41 (RM-226): Die Mitte zylindrischer Rundungen liegt auch am exakten
#:   Körper auf der begrenzten Achse; alte Flächenschwerpunkte dürfen keine
#:   Nachbauten, Folgeschritte oder Merkmalsbindungen mehr steuern.
#: - 42 (RM-226): Kugelige Eckrundungen tragen ebenfalls den Trägermittelpunkt
#:   statt des Flächenschwerpunkts; Nachbau und Folgeoperationen lesen ihn.
#: - 43 (RM-226): Ein Zylinder, der quer zu seiner Achse nicht in seinen
#:   Körper passt, ist auch am exakten Kern keine Verrundung, sondern eine
#:   gekrümmte Fläche wie am Netz; gespeicherte exakte Merkmale nennen ihn noch
#:   ``fillet``. Auf ``main`` stand die 43 zugleich für RM-504 (unten).
#: - 44 (RM-226): Das Netz trennt tangential verbundene Rundungen an ihren
#:   Zylindern, nennt Kugelecken zwischen verrundeten Kanten Verrundung und die
#:   Ebenen dazwischen Fläche; gespeicherte Netzmerkmale führen dort noch eine
#:   einzige gekrümmte Fläche.
#: - 45: Zusammenführung beider Linien. RM-504 (auf ``main`` die 43): Der
#:   exakte Körper liest Muster an seiner Tessellierung; ein gespeicherter
#:   STEP-Import trüge sonst weiter Einzelflächen. Ausdrücklich
#:   zusammengefasste Zellen binden sich wie Texturen an ihre Oberfläche. Ein
#:   Eintrag aus nur einer der beiden Linien kennt die andere Änderung nicht.
#: - 46 (RM-226): Ein Langloch ist am exakten Kern so tief wie seine ganze
#:   Wand, über beide Bögen; ein Zylinder mit schrägem oder freiem Rand misst
#:   seine Achsgrenzen an der Form statt an den Parametergrenzen.
#: - 47 (RM-226): Die tangentiale Trennung gibt ein Ziel nach
#:   ``TANGENTIAL_FIRST_SEEDS`` vergeblichen Keimen auf, nach dem ersten
#:   Stück nach ``TANGENTIAL_FUTILE_SEEDS`` in Folge.
#: - 48 (RM-411): Zusammenführung mit der Langlochlinie (auf ``main`` die 44).
#:   Ein exaktes Langloch verlangt den geschlossenen Mantel wie am Netz; zwei
#:   Bögen, deren Mantel über eine weitere Wand läuft, sind keines. Gespeicherte
#:   Merkmale nannten dort ein Langloch, und ein exakter Stopfen, der den Körper
#:   verlöre, ist jetzt eine Absage statt eines Ergebnisses.
#: - 49 (RM-254/RM-210): Zusammenführung mit der Erkennungslinie (dort die 43).
#:   Im wandernden Umriss bestätigt nur ein Kreis, den sein Stück festlegt, und
#:   ein Bogen zwischen zwei seiner Ecken gehört zu ihm; Kegelläufe beginnen an
#:   der Quadrik der Stützpunkte. Gespeicherte Erkennungen trügen alte
#:   Verrundungen und Kegel.
#: - 50 (RM-226, Nachtrag 04.10.2026): Bögen desselben Rings sind am exakten
#:   Kern ein Ring wie am Netz, auch über einen Durchbruch
#:   (``brep.features._joined_tori``); Zwillinge behalten nach jedem exakten
#:   Neubau und in der Auswertung des exakten Körpers ihre Namen nach der Lage
#:   ihrer Oberfläche (``matching.settled_twins``). Gespeicherte exakte
#:   Erkennungen und Ergebnisse trügen zwei Ringe und neue Namen für Zwillinge.
#: - 51 (RM-226, Nachtrag 04.10.2026): Die Tessellierung eines exakten Körpers
#:   trägt keine Dreiecke ohne Fläche mehr. Ein gespeicherter Netzzwilling trüge
#:   sie noch und läse nach der ersten Booleschen andere Merkmale als vorher.
#: - 52 (RM-187): Bausteine, Muster, Skizzenbögen, Teilen und die Schritte aus
#:   ``prepare_ops`` rechnen ohne BLAS, LAPACK und die Winkelfunktionen der
#:   Plattform. Gespeicherte Ergebnisse und Mustererkennungen trügen noch die
#:   letzte Stelle der Maschine, auf der sie entstanden.
#: - 53 (RM-548, Review G): Zusammengelegte Mäntel sind am exakten Kern ganz,
#:   sobald einer selbst die volle Umdrehung trägt
#:   (``brep.features._cylinder_group_extent``). Gespeicherte exakte Erkennungen
#:   nannten die Bohrung durch berührende Platten angeschnitten.
#: - 54 (Welle 2): Die Pakete G, B und L auf einem gemeinsamen Stand; trennt ihn
#:   von den Ergebnissen der einzelnen Zweige.
#: - 55 (RM-592): Eine Boolesche ohne Wirkung gibt ihren Eingang in dessen
#:   Dreiecksfolge zurück (``attributes.in_source_layout``). Ein gespeichertes
#:   Ergebnis trüge die Folge des Kerns und träfe den Merkmalscache nicht.
CACHE_FORMAT_VERSION: Final = 55


@dataclass(frozen=True, slots=True)
class CachedResult:
    """Was eine Operation erzeugt hat, bereit zum erneuten Herausgeben."""

    objects: tuple[SceneObject, ...]
    findings: tuple[Finding, ...] = ()
    solver: SolverInfo | None = None
    transform: Transform | None = None
    """Beim Ergebnis aufgehoben: eine Operation aus dem Cache muss dieselbe
    Bewegung melden wie beim ersten Mal, sonst überlebten die Bezeichner nur
    einen kalten Lauf."""
    continuations: tuple[tuple[FeatureContinuation, ...], ...] = ()
    """Aus demselben Grund aufgehoben: die belegten Übergänge alter Merkmale
    je Ausgabe (``OpResult.feature_continuations``). Ein Cachetreffer, der
    sie verlöre, ließe eine bewusst geänderte Bohrung beim zweiten Lauf als
    unbelegt anhalten."""
    answered: dict[str, Any] = field(default_factory=dict)
    """Was die Operation für ihre Parameter festgestellt hat (``OpResult.answered``,
    §15.7). Ein Treffer gibt es weiter wie ein frischer Lauf: Die Sitzung
    schreibt die Antwort nur, wenn sie das Ergebnis annimmt — kam der Schritt
    danach aus dem Cache, ohne sie, blieb er unbeantwortet und rechnete bei
    jeder Änderung davor anders."""
    reads_quality: bool = True
    """Ob die Operation nach der Güte gefragt hat (RM-494). Ein Treffer meldet
    es weiter wie ein frischer Lauf; ohne Angabe gilt sie als gefragt."""

    @property
    def cost(self) -> int:
        """Dreiecke und zusätzliche Merkmalsindizes teilen dieselbe Speichergrenze."""
        return sum(
            entry.mesh.triangle_count
            + (cavity.triangle_count if (cavity := getattr(entry.mesh, "cavity", None)) else 0)
            + sum(
                len(feature.face_indices)
                + sum(len(patch.face_indices) for patch in feature.surface_patches)
                for feature in entry.features.values()
            )
            for entry in self.objects
        )


class MeshCodec(Protocol):
    """Macht aus einem Netz Bytes und zurück. Liefert die Geometrieschicht."""

    @property
    def suffix(self) -> str: ...

    def stores(self, mesh: Mesh) -> bool:
        """Ob dieser Körper überhaupt auf die Platte gehört.

        **Gefragt wird, statt es am Fehler zu merken.** ``dumps`` wirft bei
        einem Körper der falschen Sorte, und dieser Wurf sah bis zum
        27.08.2026 genauso aus wie ein Programmfehler im Payload — beide
        landeten als ``TypeError`` in derselben Warnung. Der eine ist
        Normalbetrieb (§30), der andere hat zweimal Tage gekostet. Wer vorher
        fragt, muss sie hinterher nicht auseinanderhalten.
        """
        ...

    def dumps(self, mesh: Mesh) -> bytes: ...

    def loads(self, data: bytes) -> Mesh: ...


@dataclass(slots=True)
class CacheStatistics:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    disk_hits: int = 0


class ResultCache:
    """Die Speicherebene, wahlweise mit Plattenebene dahinter."""

    def __init__(
        self,
        triangle_budget: int = DEFAULT_TRIANGLE_BUDGET,
        disk: DiskCache | None = None,
        memory_budget: int | None = None,
    ) -> None:
        self._entries: OrderedDict[str, CachedResult] = OrderedDict()
        self._cost = 0
        self._budget = triangle_budget
        self._memory_budget = default_memory_budget() if memory_budget is None else memory_budget
        self._held: dict[str, tuple[tuple[Any, ...], int]] = {}
        #: Bytes je Merkmalssatz eines Eintrags (``held_by``, ``counted``).
        self._features_held: dict[int, tuple[Any, int, dict[int, tuple[object, int]]]] = {}
        """Je Schlüssel die zuletzt gemessenen Bytes und woran die Messung hing
        (:func:`_held_signature`)."""
        self._disk = disk
        self._refusals: OrderedDict[str, AppError] = OrderedDict()
        """Das Urteil der vollen Kette über Schritte, an denen sie gescheitert ist (RM-534).

        Ein Ergebnis gibt es dort nicht, also auch keinen Eintrag oben. Ohne
        dieses Gedächtnis rechnete jede Änderung hinter einem solchen Schritt
        ihn noch einmal mit allen Stufen — am Kundenteil 17 s, um denselben
        Satz zu sagen. Gemerkt wird die Ausnahme, nicht der Befund: Den baut
        die Auswertung am Treffer mit der Kennung, die der Schritt dann trägt.
        Nur im Speicher — die Platte trägt nur, was ein vollständiger
        Durchlauf hinterlassen hat (§15.6)."""
        self.statistics = CacheStatistics()
        self._lock = threading.RLock()
        """Ein Schloss, weil mehr als ein Faden hier hineinschreibt.

        Die Auswertung läuft in einem Arbeiter (§15.6), der Agent in einem
        zweiten, die Vorschau in einem dritten — und alle drei legen am Ende
        eines vollständigen Laufs ihr Ergebnis ab. ``_store`` ist dabei kein
        einzelner Schritt, sondern vier: den alten Eintrag herausnehmen, die
        Kosten abziehen, den neuen einhängen, verdrängen bis das Budget passt.
        Zwei Fäden mittendrin, und ``_cost`` stimmt nicht mehr mit dem überein,
        was wirklich in der Liste liegt: Der Cache verdrängt dann entweder zu
        früh (jeder Schritt wird neu gerechnet) oder gar nicht mehr (er wächst,
        bis der Speicher knapp wird).

        **Ein ``RLock``, und der Grund dafür stimmt seit dem Umbau nicht mehr.**
        Hier stand, ``get`` rufe bei einem Plattentreffer ``_store`` bei bereits
        gehaltenem Schloss. Das war einmal so; heute gibt ``get`` das Schloss
        vor dem Dateizugriff ausdrücklich ab (der Satz dazu steht dort) und
        nimmt es für ``_store`` neu. Beide Aufrufer — ``get`` und ``put`` —
        treten also einfach ein, und ein ``Lock`` täte es.

        Er bleibt trotzdem, und der Grund ist der schwächere von zweien: Ein
        ``Lock`` würde eine versehentlich wiedereintretende Änderung als
        Verklemmung zeigen statt sie durchzulassen. Das ist ein Argument für
        den Tausch, aber es ist eine Verhaltensänderung unter Nebenläufigkeit
        und gehört nicht in eine Berichtigung. Wer hier arbeitet, soll den Satz
        lesen und nicht die alte Begründung glauben."""

    def get(self, key: str) -> CachedResult | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
                self.statistics.hits += 1
                return entry
        # Die Platte außerhalb des Schlosses: Sie liest eine Datei, und das
        # dauert — solange dürfen die anderen Fäden nicht warten.
        if self._disk is not None:
            from_disk = self._disk.get(key)
            if from_disk is not None:
                with self._lock:
                    self.statistics.disk_hits += 1
                    self._store(key, from_disk)
                return from_disk
        with self._lock:
            self.statistics.misses += 1
        return None

    def put(self, key: str, result: CachedResult, *, to_disk: bool = False) -> None:
        """Legt ein Ergebnis ab — im Speicher immer, auf der Platte auf Verlangen.

        **Die Vorgabe ist ``False``, und das ist die wichtigste Entscheidung an
        dieser Signatur.** Wer ablegt, muss sagen, dass dieses Ergebnis dauerhaft
        gelten darf. Die Asymmetrie entscheidet: Wer bei ``True`` als Vorgabe das
        ``to_disk=False`` vergisst, bekommt **falsche** Ergebnisse, still und über
        Sitzungen hinweg. Wer hier das ``to_disk=True`` vergisst, bekommt eine
        **langsamere** Anwendung, und das sieht man an einer Zahl. Dieselbe Regel
        wie beim mitgeführten Ordnerstand: Der Fehler darf in die harmlose
        Richtung gehen und in keine andere.

        Der Fall, für den es das Wort gibt: **Ein Ergebnis, das keine reine
        Funktion des Dokuments ist.** Der Cache trägt seinen Schlüssel aus Op, Parametern,
        Eingängen, Profil, Qualität und Startwert; was aus einer Antwort auf
        ``ctx.ask`` entstanden ist, hängt an etwas, das dort nicht steht. Im
        Speicher ist das richtig und gewollt — dieselbe Sitzung fragt nicht
        zweimal. Auf der Platte wäre es falsch: Der Nutzer öffnet ein Projekt
        wieder und bekommt stillschweigend eine Annahme, wo eine Frage stand,
        und ob überhaupt gefragt wird, entschiede das Dateisystem — eine
        Cache-Datei darf jederzeit gelöscht werden (§38), die Antwort wäre
        also manchmal da und manchmal nicht. Regel 21 sagt „nie stillschweigend
        raten".

        Wer das setzt, ist der Auswerter: Er sieht, ob eine Operation gefragt
        hat. Sobald §15.7 umgesetzt ist — die Antwort steht in den Parametern
        der fragenden Operation —, ist keine Operation mehr davon betroffen und
        das Schlüsselwort tut nichts mehr. Es bleibt trotzdem stehen: für die
        nächste Operation, die fragt, ohne festzuhalten.
        """
        with self._lock:
            self._store(key, result)
        if self._disk is not None and to_disk:
            self._disk.put(key, result)

    def refuse(self, key: str, error: AppError) -> None:
        """Merkt, dass der Schritt unter ``key`` auch mit der vollen Kette anhält."""
        with self._lock:
            self._refusals.pop(key, None)
            self._refusals[key] = error
            while len(self._refusals) > _REFUSALS_KEPT:
                self._refusals.popitem(last=False)

    def refusal(self, key: str) -> AppError | None:
        """Der gemerkte Halt der vollen Kette unter ``key``, sonst ``None``."""
        with self._lock:
            return self._refusals.get(key)

    def _store(self, key: str, result: CachedResult) -> None:
        """Nur mit gehaltenem Schloss aufrufen — siehe :attr:`_lock`."""
        gone: list[CachedResult] = []
        if key in self._entries:
            gone.append(self._entries.pop(key))
            self._cost -= gone[-1].cost
            self._held.pop(key, None)
        self._entries[key] = result
        self._cost += result.cost
        while self._cost > self._budget and len(self._entries) > 1:
            dropped_key, dropped = self._entries.popitem(last=False)
            gone.append(dropped)
            self._held.pop(dropped_key, None)
            self._cost -= dropped.cost
            self.statistics.evictions += 1
        self._release_steps_of(gone)

    def _release_steps_of(self, gone: Iterable[CachedResult]) -> int:
        """Nur mit gehaltenem Schloss aufrufen — vergisst die Schritte verlassener Merkmale.

        Ein gemerkter Zuordnungsschritt zählt die Merkmale seines Eintrags
        nicht mit (``evaluate._remember_step``); verlässt der Eintrag die
        Speicherebene, geht der Schritt mit, außer ein anderer Eintrag hält
        dieselben Merkmale (Nachprüfung L, G-6). Gibt die Bytes zurück.
        """
        sources = {id(body.features) for entry in gone for body in entry.objects}
        if not sources:
            return 0
        sources -= self._features_present()
        if not sources:
            return 0
        from app.core.scene.evaluate import release_steps_of

        return release_steps_of(sources)

    def _features_present(self) -> set[int]:
        """Nur mit gehaltenem Schloss — die Kennungen der Merkmalssätze aller Einträge."""
        return {id(body.features) for entry in self._entries.values() for body in entry.objects}

    def with_held_features(
        self,
        then: Callable[[frozenset[int], Callable[[object], dict[int, tuple[object, int]]]], None],
    ) -> None:
        """Ruft ``then`` mit den Kennungen der Merkmalssätze aller Einträge, unter dem Schloss.

        Für den Merker der Zuordnungsschritte (``evaluate._keep_steps``): Er
        nimmt nur Schritte, deren Merkmale hier liegen, und kein anderer Faden
        verdrängt sie dazwischen. Das Zweite gibt die großen Behälter eines
        dieser Sätze (``memory.held_parts``) aus demselben Merker, den
        :meth:`trim` danach liest — gezählt wird jeder Satz einmal, hier oder
        dort, wie vor dem Merker der Schritte.
        """
        with self._lock:
            then(frozenset(self._features_present()), self._feature_parts)

    def _feature_parts(self, features: object) -> dict[int, tuple[object, int]]:
        """Nur mit gehaltenem Schloss — die großen Behälter eines Merkmalssatzes, gemerkt."""
        from app.core.memory import held_parts

        known = self._features_held.get(id(features))
        if known is None or known[0] is not features:
            known = (features, *held_parts(features))
            self._features_held[id(features)] = known
        return known[2]

    def trim(self, keep: Iterable[Mesh] = ()) -> None:
        """Hält die Bytegrenze der Speicherebene (RM-567).

        Gerufen von der Auswertung am Ende jedes vollständigen Laufs, mit den
        Netzen ihrer fertigen Szene in ``keep``: Die hält die Szene ohnehin,
        sie zählen nicht und bleiben, wie sie sind. Am Ende und nicht beim
        Ablegen, weil ein Netz wächst, nachdem es abgelegt wurde —
        Zurücknehmen legt nichts ab und wertet doch einen älteren Stand aus,
        dessen Netz seine Nachbarschaften neu rechnet, am Spiderman 256 MB je
        Schritt zurück (08.10.2026).

        Was dabei losgelassen wird, meldet sie der Speicherbereinigung
        (``memory.note_released``, RM-594): Ein ``trimesh``-Netz hängt in
        Ringen an sich selbst und wird erst frei, wenn sie läuft.
        """
        from app.core.memory import note_released

        with self._lock:
            released = self._trim(list(keep))
        note_released(released)

    def _trim(self, kept: Sequence[Mesh]) -> int:
        """Nur mit gehaltenem Schloss aufrufen — siehe :attr:`_lock`.

        Gibt zurück, wie viele Bytes schlanke Netze und verdrängte Einträge
        losgelassen haben.
        """
        # Die Bytes zuletzt, in zwei Stufen. **Erst schrumpfen, dann
        # verdrängen**: Eine Auswertung geht den Verlauf von vorn durch und
        # fragt jeden Schritt hier ab. Wer die ältesten Einträge verdrängt,
        # holt sie bei der nächsten Auswertung von der Platte und verdrängt
        # dabei die nächsten — am Spiderman mit acht Schritten las jede
        # Auswertung acht Netze von der Platte, 15 statt 2 s (08.10.2026). Was
        # ein älterer Eintrag wirklich braucht, sind Ecken, Dreiecke und
        # Merkmale; Kantentabellen und Nachbarschaften rechnet ein neues
        # Netz aus denselben Feldern, wenn jemand fragt (``MeshData.lean``).
        # Die Schichtanalyse des Prüfberichts behält es (Nachprüfung L, M-2).
        # Der jüngste Eintrag bleibt immer ganz, auch über der Grenze — ohne
        # ihn rechnete der nächste Schritt alles noch einmal.
        ids = {id(mesh) for mesh in kept}
        held = sum(self._unkept(key, entry, ids) for key, entry in self._entries.items())
        if held + _memo_bytes() <= self._memory_budget:
            return 0
        # Die Schätzung je Eintrag zählt geteilte Felder mehrfach; über der
        # Grenze wird **einmal** genau gezählt, jedes Feld einmal, beim
        # jüngsten zuerst, und danach abgezogen, was frei wird (Review L,
        # M2): Verdrängen ändert die Zurechnung der jüngeren Einträge nicht,
        # und was ein schlankes Netz losließe, steht beim Zählen fest. Nach
        # jedem Schritt neu zu zählen kostete am Riser unter 150 MB Grenze
        # 3 s je Auswertung, mit dem Verlauf quadratisch wachsend.
        sizes, freeable, held = self._exact(kept, ids)
        released = 0
        older = list(self._entries)[:-1]
        for key in older:
            if held <= self._memory_budget:
                return released
            if freeable[key] <= 0:
                continue
            entry = self._entries[key]
            leaner = _leaner(entry, ids)
            if leaner is entry:
                continue
            self._entries[key] = leaner
            self._held.pop(key, None)
            held -= freeable[key]
            released += freeable[key]
            sizes[key] -= freeable[key]
        if held > self._memory_budget:
            freed = _release_steps(held - self._memory_budget)
            held -= freed
            released += freed
        gone: list[CachedResult] = []
        for key in older:
            if held <= self._memory_budget:
                break
            entry = self._entries[key]
            if any(id(body.mesh) in ids for body in entry.objects):
                continue
            del self._entries[key]
            gone.append(entry)
            self._held.pop(key, None)
            held -= sizes[key]
            released += sizes[key]
            self._cost -= entry.cost
            self.statistics.evictions += 1
        return released + self._release_steps_of(gone)

    def _exact(
        self, kept: Sequence[Mesh], ids: set[int]
    ) -> tuple[dict[str, int], dict[str, int], int]:
        """Je Eintrag seine Bytes und was schlanke Netze davon freigäben, dazu die Summe.

        Jedes Feld einmal: erst die Szene, dann vom jüngsten Eintrag an, dann
        die gemerkten Zuordnungsschritte (Nachprüfung L, M-3), zuletzt der
        Merker der Zuordnung.
        """
        present = {id(body.features) for entry in self._entries.values() for body in entry.objects}
        for gone in set(self._features_held) - present:
            del self._features_held[gone]
        seen: set[int] = set()
        for mesh in kept:
            _mesh_bytes(mesh, seen)
        sizes: dict[str, int] = {}
        freeable: dict[str, int] = {}
        for key in reversed(list(self._entries)):
            loose = [0]
            sizes[key] = held_by(self._entries[key], ids, seen, loose, self._features_held)
            freeable[key] = loose[0]
        return sizes, freeable, sum(sizes.values()) + _memo_bytes(seen)

    def _unkept(self, key: str, entry: CachedResult, kept: set[int]) -> int:
        """Die Bytes eines Eintrags ohne die Netze der Szene; gemerkt, solange er nicht wächst.

        Auch der Eintrag, dessen Netz die Szene zeigt: Neu gezählt kostete er
        am Eiffelturm bei jeder Auswertung eine halbe Sekunde, ohne dass sich
        an ihm etwas geändert hatte. Welche seiner Netze die Szene hält, steht
        deshalb mit im Merker.
        """
        shown = tuple(id(body.mesh) in kept for body in entry.objects)
        signature = (*_held_signature(entry), shown)
        known = self._held.get(key)
        if known is None or known[0] != signature:
            known = (
                signature,
                held_by(entry, kept if any(shown) else (), counted=self._features_held),
            )
            self._held[key] = known
        return known[1]

    def _held_bytes(self) -> int:
        """Die Bytes aller Einträge; neu gemessen wird nur, was gewachsen ist."""
        total = 0
        for key, entry in self._entries.items():
            signature = (*_held_signature(entry), (False,) * len(entry.objects))
            known = self._held.get(key)
            if known is None or known[0] != signature:
                known = (signature, held_by(entry, counted=self._features_held))
                self._held[key] = known
            total += known[1]
        return total

    def clear(self) -> None:
        """Leert die **Speicher**ebene. Die Platte bleibt, und das ist der Sinn.

        Der Name hat gelogen, solange es nur eine Ebene gab: Es gab nichts
        anderes zu leeren. Der einzige Aufrufer ist ``Session._reset_for``, also
        der Projektwechsel, und dort ist genau das richtig — was auf der Platte
        liegt, ist die Arbeit, für die es die Ebene gibt (§31: „Projekt öffnen
        aus Plattencache, unter 1 s"). Sie beim Wechsel mitzuleeren machte das
        Wiederöffnen für immer unmöglich.

        Dass es beim Wechsel überhaupt nichts zu leeren gibt, hängt am
        Schlüssel: Er kennt den Inhalt der Quelle
        (``SourceAccess.identity``), also gehört jeder Eintrag genau dem
        Projekt, aus dem er kam. Vor dem 22.08.2026 war das nicht so, und dieses
        ``clear`` war die einzige Stelle, die verhinderte, dass ein Projekt die
        Geometrie eines anderen bekam.

        Wer die Platte wirklich leeren will, ruft ``DiskCache.clear``. Dass die
        Platte ein ``clear`` hier übersteht, hält
        ``test_the_memory_level_fills_itself_from_disk`` fest.
        """
        with self._lock:
            gone = list(self._entries.values())
            self._entries.clear()
            self._release_steps_of(gone)
            self._held.clear()
            self._features_held.clear()
            self._refusals.clear()
            self._cost = 0

    @property
    def cost(self) -> int:
        with self._lock:
            return self._cost

    @property
    def held_bytes(self) -> int:
        """Wie viele Bytes die Speicherebene gerade hält (RM-567)."""
        with self._lock:
            return self._held_bytes()

    @property
    def memory_budget(self) -> int:
        """Wie viele Bytes sie höchstens hält; den jüngsten Eintrag behält sie immer."""
        return self._memory_budget

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


# --- Plattenebene ----------------------------------------------------------------


def feature_to_data(feature: Feature) -> dict[str, Any]:
    """Die gemeinsame vollständige Merkmalsauskunft für Plattencache und Folgehash."""
    return {
        "id": feature.id,
        "kind": feature.kind,
        "provenance": feature.provenance,
        "params": dict(feature.params),
        "face_indices": list(feature.face_indices),
        "created_by": feature.created_by,
        # Ohne dies fiel ein Merkmal aus dem warmen Cache auf die Vorgabe
        # ``True`` zurück: Ein Baustein benennt seine Bohrungen beim Bauen,
        # ``detect`` findet sie an ihrer Stelle nicht, und ``recognised=False``
        # hält sie trotzdem fest (types.py). Als ``True`` wandert das Merkmal in
        # die Erkennungsprüfung, findet keinen Partner und verwaist — der Fehler,
        # gegen den das Feld eingebaut wurde, nur eine Cache-Ebene weiter.
        "recognised": feature.recognised,
        "measure_sources": dict(feature.measure_sources),
        "surface_patches": [
            {
                "kind": patch.kind,
                "params": dict(patch.params),
                "face_indices": list(patch.face_indices),
                "source": patch.source,
            }
            for patch in feature.surface_patches
        ],
    }


def _frame_from_data(value: Any) -> Transform | None:
    """Ein gespeicherter Bezugsrahmen ist endlich und affin, sonst ein Cachefehler."""
    if value is None:
        return None
    if not isinstance(value, list | tuple) or len(value) != 4:
        raise ValueError("invalid cached frame")
    rows: list[tuple[float, ...]] = []
    for row in value:
        if not isinstance(row, list | tuple) or len(row) != 4:
            raise ValueError("invalid cached frame row")
        if any(isinstance(cell, bool) or not isinstance(cell, int | float) for cell in row):
            raise ValueError("invalid cached frame value")
        cells = tuple(float(cell) for cell in row)
        if not all(math.isfinite(cell) for cell in cells):
            raise ValueError("nonfinite cached frame")
        rows.append(cells)
    if not all(
        math.isclose(cell, expected, rel_tol=0.0, abs_tol=0.0)
        for cell, expected in zip(rows[3], (0.0, 0.0, 0.0, 1.0), strict=True)
    ):
        raise ValueError("nonaffine cached frame")
    return cast(Transform, tuple(rows))


def _surface_patches_from_data(
    data: object, indices: tuple[int, ...], face_count: int | None
) -> tuple[SurfacePatch, ...]:
    """Wegwerfbare Cache-Daten gegen denselben Trägervertrag wie die Erkennung lesen."""
    from app.core.perceive.surfaces import valid_patch

    if not isinstance(data, list):
        raise ValueError("invalid cached surface patches")
    if not data:
        return ()
    if any(not isinstance(index, int) or isinstance(index, bool) for index in indices):
        raise ValueError("invalid cached feature indices")
    allowed = frozenset(indices)
    patches = []
    for item in data:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("kind"), str)
            or not isinstance(item.get("source"), str)
            or not isinstance(item.get("params"), dict)
            or not isinstance(item.get("face_indices"), list)
        ):
            raise ValueError("invalid cached surface patch")
        patch = SurfacePatch(
            kind=item["kind"],
            source=item["source"],
            params={
                key: tuple(value) if isinstance(value, list) else value
                for key, value in item["params"].items()
            },
            face_indices=tuple(item["face_indices"]),
        )
        if not valid_patch(patch, face_count=face_count, allowed_indices=allowed):
            raise ValueError("invalid cached surface geometry")
        patches.append(patch)
    return tuple(patches)


def _continuations_from_data(
    data: object, outputs: int
) -> tuple[tuple[FeatureContinuation, ...], ...]:
    """Die belegten Übergänge je Ausgabe lesen — oder den Eintrag verwerfen.

    Ein fehlendes Feld ist innerhalb dieses Formatstands eine leere Folge:
    Die Operation hat keinen Beleg ausgestellt. Ein Feld mit falscher Gestalt
    ist dagegen ein beschädigter Eintrag; die Zuordnung darf ihn nicht halb
    lesen und den Rest für „kein Beleg" halten.
    """
    if not isinstance(data, list):
        raise ValueError("invalid cached continuations")
    if not data:
        return ()
    if len(data) != outputs:
        raise ValueError("cached continuations do not match the outputs")
    result: list[tuple[FeatureContinuation, ...]] = []
    for per_output in data:
        if not isinstance(per_output, list):
            raise ValueError("invalid cached continuations")
        entries = []
        for item in per_output:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("source"), str)
                or not isinstance(item.get("target"), str)
                or not item["target"]
            ):
                raise ValueError("invalid cached continuation")
            entries.append(FeatureContinuation(FeatureRef.parse(item["source"]), item["target"]))
        result.append(tuple(entries))
    return tuple(result)


#: Was ein beschädigter Eintrag beim Lesen wirft — und damit verworfen wird.
#:
#: **Nicht nur das JSON kann kaputt sein, sondern auch das Netz daneben.** Bis
#: zur Durchsicht vor 0.5.0 standen hier ``OSError``, ``KeyError`` und
#: ``ValueError`` — die Fehler einer kaputten ``objects.json``. Ein halb
#: geschriebenes oder verstümmeltes ``.npz`` wirft aber aus ``np.load``
#: ``zipfile.BadZipFile``, ``EOFError`` oder ``zlib.error``, und das lief durch
#: ``evaluate`` bis in die Oberfläche: Das Projekt ließ sich nicht mehr öffnen,
#: bis jemand den Cacheordner von Hand löschte (gemessen: eine halbierte Datei
#: genügt). ``TypeError`` und ``AttributeError`` gehören dazu, weil ein
#: verstümmeltes JSON auch die falsche **Gestalt** tragen kann — eine Liste,
#: wo ein Wörterbuch stehen muss —, und ``IndexError`` und ``struct.error``,
#: weil ein abgeschnittenes Feld beim Lesen einer Zahl endet. Der Grund steht
#: mit seiner Art im Protokoll; ein Fehler in unserem Code fällt dort weiter auf.
_DAMAGED_ENTRY: Final = (
    OSError,
    KeyError,
    ValueError,
    TypeError,
    AttributeError,
    IndexError,
    EOFError,
    zipfile.BadZipFile,
    zlib.error,
    struct.error,
)


def _warm_figures(mesh: Mesh) -> None:
    """Volumen, Fläche, Dichtheit, Teilezahl und Hüllquader einmal hier anfassen — im Arbeiter.

    Ein Netz von der Platte kommt mit kalten Kennzahlen, und wer sie zuerst
    liest, ist der Hauptthread: der Objektbaum (`describe_selection`), die
    Faktenzeile und die Prüfliste. An `dense_1m.stl` waren das beim zweiten
    Öffnen 1,5 Sekunden im Fenster — Trägheitstensor, Zusammenhang und
    Dichtheit —, während der erste Lauf sie längst im Arbeiter gerechnet
    hatte (Review, 21.09.2026). trimesh merkt sich die Zahlen am Netz; hier
    gerechnet, liest das Fenster sie nur noch ab. Der exakte Körper misst
    seinen Hüllquader an der Form, an ``build_tray_v3.step`` 0,47 s, und
    merkt ihn sich seit dem 22.09.2026 ebenso.
    """
    with suppress(Exception):
        for figure in ("volume", "area", "is_watertight", "component_count", "bounds"):
            getattr(mesh, figure)


#: Die Endung der Herkunftsdatei eines verfeinerten Netzes neben seinem Netz.
_ORIGIN_SUFFIX: Final = ".origin.npy"


def _refinement_to_disk(folder: Path, position: int, mesh: Mesh) -> dict[str, str] | None:
    """Legt den Herkunftsvermerk von *Kanten verfeinern* neben das Netz — falls es einen trägt.

    Der Vermerk (``perceive.features.refinement_note``) lebt im Speicher des
    Netzes. Ohne ihn auf der Platte lief die Erkennung nach dem Wiederöffnen am
    feineren Netz neu und las dort etwas anderes als in der Sitzung: am
    Screen-Cover nach 1 mm 45 Verrundungen statt einer gerundeten Seite, und
    72 Namen zeigten auf andere Merkmale (Durchsicht 0.5.1, erkennung-02).
    Dasselbe Dokument hatte damit je nach Cache zwei Merkmalsstände (§15.1).
    """
    import io

    import numpy as np

    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import refinement_note

    if not isinstance(mesh, MeshData):
        return None
    noted = refinement_note(mesh)
    if noted is None:
        return None
    key, origin = noted
    name = f"{position}{_ORIGIN_SUFFIX}"
    buffer = io.BytesIO()
    np.save(buffer, np.asarray(origin, dtype=np.int64), allow_pickle=False)
    (folder / name).write_bytes(buffer.getvalue())
    return {"source": key.hex(), "origin": name}


def _refinement_from_disk(folder: Path, record: Any, mesh: Mesh) -> None:
    """Legt einen gelesenen Herkunftsvermerk wieder an das Netz.

    Geprüft wird hier nur die Form — ein beschädigter Eintrag wirft einen der
    Fehler aus :data:`_DAMAGED_ENTRY` und wird neu gerechnet. Ob der Vermerk
    stimmt, prüft ``perceive.features.refined_twin`` am Eingang und an der
    Geometrie, bevor er etwas überträgt.
    """
    import io

    import numpy as np

    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import restore_refinement_note

    if not isinstance(mesh, MeshData):
        raise TypeError("refined_from")
    source = bytes.fromhex(str(record["source"]))
    name = str(record["origin"])
    if len(source) != 16 or Path(name).name != name or not name.endswith(_ORIGIN_SUFFIX):
        raise ValueError("refined_from")
    origin = np.load(io.BytesIO((folder / name).read_bytes()), allow_pickle=False)
    if origin.dtype.kind not in "iu" or origin.shape != (mesh.triangle_count,):
        raise ValueError("refined_from")
    restore_refinement_note(mesh, source, origin)


def _movement_to_disk(mesh: Mesh) -> list[dict[str, Any]] | None:
    """Der Bewegungsvermerk eines starr bewegten Netzes für die Platte — falls es einen trägt.

    Derselbe Grund wie bei :func:`_refinement_to_disk`: Der Vermerk
    (``perceive.features.movement_note``) lebt im Speicher des Netzes, und ohne
    ihn lief die Erkennung nach dem Wiederöffnen an jedem ausgerichteten oder
    angeordneten Körper neu, den der Plattencache lieferte.
    """
    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import movement_note

    if not isinstance(mesh, MeshData):
        return None
    note = movement_note(mesh)
    if not note:
        return None
    return [
        {"source": key.hex(), "matrix": [[float(value) for value in row] for row in cells]}
        for key, cells in note
    ]


def _movement_from_disk(record: Any, mesh: Mesh) -> None:
    """Legt einen gelesenen Bewegungsvermerk wieder an das Netz.

    Geprüft wird hier nur die Form; ob er stimmt, prüft
    ``perceive.features.moved_from`` am Eingang und an der Geometrie.
    """
    import math

    import numpy as np

    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import MOVEMENT_NOTE_DEPTH, restore_movement_note

    if not isinstance(mesh, MeshData) or not isinstance(record, list):
        raise TypeError("moved_from")
    if not record or len(record) > MOVEMENT_NOTE_DEPTH:
        raise ValueError("moved_from")
    note = []
    for entry in record:
        key = bytes.fromhex(str(entry["source"]))
        cells = np.asarray(entry["matrix"], dtype=np.float64)
        if len(key) != 16 or cells.shape != (4, 4) or not all(map(math.isfinite, cells.flat)):
            raise ValueError("moved_from")
        note.append((key, cells))
    restore_movement_note(mesh, tuple(note))


def _feature_from_data(data: dict[str, Any], *, face_count: int | None = None) -> Feature:
    indices = tuple(data["face_indices"])
    return Feature(
        id=data["id"],
        kind=data["kind"],
        provenance=data["provenance"],
        params=data["params"],
        face_indices=indices,
        # **Mit ``get`` und nicht über den Index.** Der Cache ist hashbasiert
        # und wegwerfbar — nur weggeworfen wird er nicht, wenn ein Feld
        # dazukommt: Der Hash steht über dem Operationsstapel, nicht über der
        # Gestalt dieser Datei. Ein Eintrag von gestern kennt ``created_by``
        # nicht, und ein ``KeyError`` beim Lesen des Caches wäre ein Fehler
        # ohne Handlungsvorschlag an einer Stelle, an der es nichts zu
        # entscheiden gibt.
        created_by=data.get("created_by"),
        # ``get`` mit der Vorgabe wie oben: Ein Eintrag von vor diesem Feld
        # kennt ``recognised`` nicht, und der Cache ist wegwerfbar, nicht
        # versioniert.
        recognised=data.get("recognised", True),
        measure_sources=data.get("measure_sources", {}),
        surface_patches=_surface_patches_from_data(
            data.get("surface_patches", []), indices, face_count
        ),
    )


def _name_to_data(name: TranslatableText | str) -> str | dict[str, Any]:
    """Der **stabile** Teil eines Namens, nicht seine Übersetzung.

    Benutzt für den Objektnamen und für den Namen eines Materialslots
    (:func:`_slot_to_data`) — zwei Felder, ein Verfahren. Der zweite kam drei
    Tage nach dem ersten dazu, mit derselben Protokollzeile und derselben
    Folge; die beiden Aufrufe stehen deshalb nebeneinander und nicht in zwei
    Fassungen.

    Seit Objektnamen aus dem Register kommen, ist ``SceneObject.name`` ein
    :class:`TranslatableText` und kein ``str`` — und ``json.dumps`` kann den
    nicht ablegen. Der Eintrag fiel darum still durch den ``except``-Zweig
    weiter unten, der für nicht ablegbare B-Rep-Körper gedacht ist: Ein
    einziger übersetzter Name ließ den Cache-Eintrag der **ganzen** Auswertung
    fallen, also rechnete jedes konstruierte Projekt bei jeder Auswertung neu.
    Gefunden am 23.08.2026 beim Handlauf von Weg 2, an einer Zeile im
    Protokoll: ``Object of type TranslatableText is not JSON serializable``.

    **Abgelegt wird die Message-ID, nie ``str(...)``.** Die Übersetzung wechselt
    mit der Sprache; ein Cache, der sie speicherte, gäbe einen deutschen Namen
    zurück, sobald jemand die Oberfläche umstellt — ein Fehler, den nur ein
    warmer Cache zeigt. Dasselbe tut :func:`~app.core.scene.serialise.
    transaction_to_data` für den Titel einer Transaktion, dort über drei
    Felder; hier genügt eines, weil der Name allein steht.

    Was ein Nutzer selbst benannt hat, ist ein ``str`` und bleibt einer.

    **Die Werte gehören dazu.** „Slot 2" ist die Message-ID ``Slot {number}``
    und die Zahl zwei — ohne sie käme aus dem Cache ein Name mit sichtbarem
    Platzhalter zurück. Sie sind der sprachneutrale Teil und altern nicht.

    **Und sie gehen über den Helfer aus** :mod:`~app.core.scene.serialise`.
    Ein rohes ``dict(name.values)`` trug einen übersetzbaren Wert unverändert
    weiter, und genau daran ist der ``except``-Zweig weiter unten einmal
    stillschweigend zugeschnappt — derselbe Ablauf wie oben beschrieben, nur
    eine Ebene tiefer. Dass heute kein Name einen solchen Wert führt, ist
    keine Eigenschaft dieser Funktion, sondern der Aufrufer von heute.
    """
    if isinstance(name, TranslatableText):
        data: dict[str, Any] = {"msgid": name.msgid, "context": name.context}
        values = translatable_values_to_data(name)
        if values is not None:
            data["values"] = values
        return data
    return str(name)


def _name_from_data(data: str | dict[str, Any]) -> TranslatableText | str:
    """Gegenstück zu :func:`_name_to_data`.

    Eine schlichte Zeichenkette ist ein selbst vergebener Name — **und ein
    Eintrag aus einem älteren Cache**, der die Unterscheidung noch nicht
    kannte. Beide sind wörtlich gemeint und bleiben es.
    """
    if isinstance(data, dict):
        return TranslatableText(
            data["msgid"],
            data.get("context"),
            translatable_values_from_data(data.get("values")),
        )
    return data


def _slot_to_data(slot: MaterialSlot) -> dict[str, Any]:
    """Ein Materialslot als Daten — der Name über :func:`_name_to_data`.

    **Der Zwilling des Objektnamens, gefunden am 26.08.2026** an derselben
    Protokollzeile, die ihn drei Tage vorher schon einmal genannt hatte:
    ``could not write cache entry …: Object of type TranslatableText is not
    JSON serializable``, diesmal beim Erzeugen der Website-Bilder aus
    ``schild-zweifarbig.p3d``. Der Weg dorthin: Die Beispielprojekte vermerken
    an einer Operation, welche Parameter Message-IDs tragen
    (``Operation.translatable``, §4.1), die Auswertung macht daraus ein
    :class:`TranslatableText` (``scene/evaluate.py``), und ``assign_slot``
    reicht ``params.name`` unverändert in den Slot weiter. Ein einziger
    übersetzbarer Slotname ließ damit den Cache-Eintrag der **ganzen**
    Auswertung fallen — das Projekt rechnete bei jedem Öffnen neu.

    Abgelegt wird deshalb dasselbe wie beim Objektnamen: die Message-ID, nie
    ``str(...)``. Ein Slotname wandert in den Objektbaum, in den Farbdialog und
    in die 3MF-Baugruppe; läge die Übersetzung in der Cache-Datei, hieße der
    Slot nach einem Sprachwechsel weiter „Weiß".
    """
    return {
        "index": slot.index,
        "name": _name_to_data(slot.name),
        "colour": list(slot.colour) if slot.colour else None,
        "material": slot.material,
        "material_type": slot.material_type,
        "extra_colours": [list(one) for one in slot.extra_colours],
    }


def _slot_from_data(data: dict[str, Any]) -> MaterialSlot:
    colour = data.get("colour")
    return MaterialSlot(
        index=data["index"],
        name=_name_from_data(data["name"]),
        colour=(colour[0], colour[1], colour[2]) if colour else None,
        material=data.get("material"),
        material_type=data.get("material_type"),
        extra_colours=tuple(
            (one[0], one[1], one[2]) for one in data.get("extra_colours", ()) if one
        ),
    )


def drop_other_versions(directory: Path) -> None:
    """Räumt die Ergebnis-Ordner früherer Fassungen weg.

    Der Ordner trägt die Fassung im Pfad (:func:`results_cache_dir`), weil ein
    Eintrag sonst ein Update überlebt und ein Netz liefert, das alter Code
    gerechnet hat. Der Preis dafür ist ein toter Ordner je Fassung, und der ist
    nicht klein: Er darf bis an das Budget wachsen, also bis zwei Gigabyte.
    Das eigene Budget räumt ihn nie weg — es zählt nur den eigenen Ordner.

    Deshalb hier, einmal beim Anlegen. Gelöscht wird ausschließlich neben dem
    eigenen Ordner, und dort stehen nur Fassungen: ``sandbox``, ``updates`` und
    ``style`` liegen eine Ebene höher und werden nicht gesehen — genau dafür
    hat die Ablage zwei Ebenen.

    Weggeräumt wird dabei auch der Ordner desselben Programms mit einem anderen
    Stand der eigenen Bausteine — für den Aufräumer ist das derselbe Fall, und
    das ist richtig: Der alte Stand ist so tot wie eine alte Fassung.

    Läuft daneben noch eine ältere Fassung, verliert die ihren Cache und rechnet
    neu. Das ist zumutbar: Ein Ergebnis-Cache ist per Zusage jederzeit löschbar
    (§38), und zwei Fassungen gleichzeitig laufen zu lassen ist der Ausnahmefall.
    Gefährlich ist es nicht — wer gerade daraus liest, findet einen Eintrag nicht
    mehr, verwirft ihn und rechnet neu.
    """
    parent = directory.parent
    if not parent.is_dir():
        return
    for other in parent.iterdir():
        if other == directory or not other.is_dir():
            continue
        shutil.rmtree(other, ignore_errors=True)
        _log.info("dropped result cache of an older version: %s", other.name)


def _folder_bytes(folder: Path) -> int:
    """Was ein einzelner Eintrag belegt.

    Rekursiv, obwohl ein Eintrag heute flach ist: Dieselbe Zahl entsteht in
    :meth:`DiskCache.size_bytes` über den ganzen Ordner, und zwei Definitionen
    für dieselbe Zahl driften. Der mitgeführte Stand ruht darauf, dass Summe
    und Einzelteil dasselbe meinen.

    Was unter der Hand verschwindet, zählt als nichts — siehe
    :meth:`DiskCache.trim`.
    """
    if not folder.is_dir():
        return 0
    total = 0
    for path in folder.rglob("*"):
        with suppress(OSError):
            if path.is_file():
                total += path.stat().st_size
    return total


def _finding_to_cache(finding: Finding) -> dict[str, Any]:
    """Ein Befund für den Plattencache — samt Rand und Paar, die die Projektdatei nicht trägt.

    ``Finding.outline`` (der Rand einer geschlossenen Öffnung für *Stelle
    zeigen*) steht nicht in :func:`finding_to_data`: Die Projektdatei behält
    ihr Format, der Bericht wird ohnehin neu ausgewertet. Der Cache aber gibt
    das Ergebnis eines Schritts zurück, als wäre er gerechnet worden — ohne
    den Rand hätte ein warmer Cache *Stelle zeigen* still zurückgestuft.
    Ebenso ``Finding.object_ids``: Ohne sie spräche nach einem warmen Cache ein
    entfernter Körper wieder aus dem Bericht.
    """
    data = finding_to_data(finding)
    if finding.outline:
        data["outline"] = [[list(first), list(second)] for first, second in finding.outline]
    if finding.object_ids:
        data["object_ids"] = list(finding.object_ids)
    return data


def _cached_finding(data: dict[str, Any]) -> Finding:
    """Die Umkehrung von :func:`_finding_to_cache`; ein Eintrag ohne Rand oder Paar bleibt ohne."""
    finding = finding_from_data(data)
    outline = data.get("outline")
    if outline:
        finding = replace(
            finding,
            outline=tuple(
                (
                    (float(first[0]), float(first[1]), float(first[2])),
                    (float(second[0]), float(second[1]), float(second[2])),
                )
                for first, second in outline
            ),
        )
    bodies = data.get("object_ids")
    if bodies:
        finding = replace(finding, object_ids=tuple(str(name) for name in bodies))
    return finding


@dataclass(slots=True)
class DiskCache:
    """Ergebnisse auf der Platte, benannt nach dem Operations-Hash (§38)."""

    codec: MeshCodec
    directory: Path = field(default_factory=results_cache_dir)
    budget_bytes: int = DEFAULT_DISK_BUDGET_BYTES
    _known_bytes: int | None = field(default=None, init=False, repr=False, compare=False)
    """Was der Ordner nach eigener Rechnung belegt, oder ``None`` vor dem
    ersten Zählen. Siehe :meth:`_account_for`."""

    def _folder(self, key: str) -> Path:
        return self.directory / key[:2] / key

    def get(self, key: str) -> CachedResult | None:
        folder = self._folder(key)
        index = folder / "objects.json"
        if not index.is_file():
            return None
        try:
            data = json.loads(index.read_text(encoding="utf-8"))
            if data.get("format_version") != CACHE_FORMAT_VERSION:
                return None
            objects_list = []
            for entry in data["objects"]:
                mesh = self.codec.loads((folder / entry["mesh"]).read_bytes())
                if "refined_from" in entry:
                    _refinement_from_disk(folder, entry["refined_from"], mesh)
                if "moved_from" in entry:
                    _movement_from_disk(entry["moved_from"], mesh)
                _warm_figures(mesh)
                objects_list.append(
                    SceneObject(
                        id=entry["id"],
                        name=_name_from_data(entry["name"]),
                        mesh=mesh,
                        kind=entry["kind"],
                        # **Nicht gegen die Dreieckszahl des gespeicherten Netzes
                        # prüfen.** Hier liegt die rohe Ausgabe der Operation, und
                        # die trägt rechtmäßig Merkmale ihres Eingangs mit
                        # Nummern des Eingangsnetzes — der Bausteinwirt nach der
                        # Vereinigung, das Reparieren; erst `_with_features`
                        # bindet sie an das neue Netz, beim Treffer wie beim
                        # frischen Lauf. Mit der Prüfung verwarf der Cache jeden
                        # solchen Eintrag: „Dose mit Deckel" rechnete die
                        # Kabeldurchführung bei jedem Öffnen neu (Review,
                        # 21.09.2026). Trägervertrag und Zugehörigkeit der
                        # Nummern zum Merkmal bleiben geprüft.
                        features={
                            key_: _feature_from_data(value)
                            for key_, value in entry["features"].items()
                        },
                        material_slots=[_slot_from_data(slot) for slot in entry["material_slots"]],
                        material=entry.get("material"),
                        created_by=entry["created_by"],
                        visible=entry["visible"],
                        plate=entry.get("plate", 0),
                        reserved_feature_ids=tuple(sorted(entry.get("reserved_feature_ids", ()))),
                        frame=_frame_from_data(entry["frame"]),
                    )
                )
            objects = tuple(objects_list)
            # Die drei Beifänge gehören zum Ergebnis wie die Körper selbst:
            # ohne `transform` liest `_with_features` die alten Merkmale im
            # falschen Bezugspunkt und benennt sie um (§21.2), ohne
            # `findings` verschwindet die Voxel-Warnung, die §17.2 nie
            # stillschweigend lassen will. Sie wurden geschrieben — nur
            # gelesen hat sie niemand.
            findings = tuple(_cached_finding(entry) for entry in data.get("findings", []))
            solver = solver_from_data(data.get("solver"))
            raw_transform = data.get("transform")
            transform: Transform | None = (
                tuple(tuple(float(value) for value in row) for row in raw_transform)  # type: ignore[assignment]
                if raw_transform
                else None
            )
            continuations = _continuations_from_data(data.get("continuations", []), len(objects))
            answered = data.get("answered", {})
            if not isinstance(answered, dict) or not all(isinstance(k, str) for k in answered):
                raise ValueError("invalid cached answers")
            reads_quality = data.get("reads_quality", True) is not False
        except _DAMAGED_ENTRY as problem:
            # Ein beschädigter Cache-Eintrag ist nie fatal: verwerfen und
            # neu rechnen.
            _log.warning(
                "dropping unreadable cache entry %s: %s: %s", key, type(problem).__name__, problem
            )
            shutil.rmtree(folder, ignore_errors=True)
            return None
        # Ein paralleler Aufräumer darf den gerade gelesenen Ordner nach dem
        # letzten ``read_bytes`` entfernen. Das Ergebnis ist bereits sicher
        # im Speicher; nur seine LRU-Markierung fällt in diesem Rennen aus.
        # ``Path.touch`` wäre hier falsch: Nach dem Löschen legt es am alten
        # Ordnerpfad eine reguläre Datei an und blockiert den nächsten Schreibzug.
        with suppress(OSError):
            os.utime(folder, None)
        return CachedResult(
            objects=objects,
            findings=findings,
            solver=solver,
            transform=transform,
            continuations=continuations,
            answered=answered,
            reads_quality=reads_quality,
        )

    def put(self, key: str, result: CachedResult) -> None:
        # **Der gewollte Fall kommt gar nicht erst in den Fehlerpfad** (§30):
        # Ein B-Rep-Ergebnis wird neu gerechnet statt gecacht, denn den Cache
        # gibt es für teure Boolesche Arbeit auf großen Netzen, und eine
        # Verrundung auf einem exakten Körper sind Millisekunden. Das ist
        # Normalbetrieb und keine Warnung wert — bis hierher war es beides
        # zugleich, siehe der Kommentar am ``except`` weiter unten.
        keeps = [entry for entry in result.objects if not self.codec.stores(entry.mesh)]
        if keeps:
            _log.info(
                "not caching %s: %d object(s) are not mesh backed — recomputed instead (§30)",
                key,
                len(keeps),
            )
            return
        entries: list[dict[str, Any]] = []
        folder: Path | None = None
        try:
            # Im selben Fehlerpfad wie das Schreiben: Eine volle Platte oder
            # entzogene Rechte beim Anlegen des Unterordners warfen die rohe
            # OSError durch ``evaluate`` — und mit ihr das fertig gerechnete
            # Ergebnis (Gesamtreview 05.09.2026, CORE-10).
            folder = ensure_dir(self._folder(key))
            for position, entry in enumerate(result.objects):
                name = f"{position}{self.codec.suffix}"
                (folder / name).write_bytes(self.codec.dumps(entry.mesh))
                record: dict[str, Any] = {
                    "id": entry.id,
                    "name": _name_to_data(entry.name),
                    "mesh": name,
                    "kind": entry.kind,
                    "features": {
                        key_: feature_to_data(value) for key_, value in entry.features.items()
                    },
                    "material_slots": [_slot_to_data(slot) for slot in entry.material_slots],
                    "material": entry.material,
                    "created_by": entry.created_by,
                    "visible": entry.visible,
                    "plate": entry.plate,
                    "reserved_feature_ids": list(entry.reserved_feature_ids),
                    "frame": entry.frame,
                }
                refined = _refinement_to_disk(folder, position, entry.mesh)
                if refined is not None:
                    record["refined_from"] = refined
                moved = _movement_to_disk(entry.mesh)
                if moved is not None:
                    record["moved_from"] = moved
                entries.append(record)
            payload: dict[str, Any] = {"format_version": CACHE_FORMAT_VERSION, "objects": entries}
            if result.findings:
                payload["findings"] = [_finding_to_cache(entry) for entry in result.findings]
            if result.solver is not None:
                payload["solver"] = solver_to_data(result.solver)
            if result.transform is not None:
                payload["transform"] = [list(row) for row in result.transform]
            if any(result.continuations):
                payload["continuations"] = [
                    [{"source": str(entry.source), "target": entry.target} for entry in per_output]
                    for per_output in result.continuations
                ]
            if result.answered:
                payload["answered"] = dict(result.answered)
            if not result.reads_quality:
                payload["reads_quality"] = False
            (folder / "objects.json").write_text(json.dumps(payload), encoding="utf-8")
        except (OSError, TypeError) as problem:
            # ``TypeError`` hatte hier **zwei** Ursachen, und die zweite hat
            # zweimal Tage gekostet, weil sie wie die erste aussah:
            #
            # 1. Ein Körper, den der Codec nicht ablegen kann — ein
            #    B-Rep-Ergebnis (§30). Das war gewollt und trotzdem eine
            #    Warnung. **Seit dem 27.08.2026 fragt ``put`` vorher**
            #    (``codec.stores``) und kommt hier nicht mehr an.
            # 2. Ein Wert im Payload, den ``json.dumps`` nicht kennt — bisher
            #    zweimal ein :class:`TranslatableText`, erst im Objektnamen
            #    (23.08.2026), dann im Namen eines Materialslots (26.08.2026).
            #    Das ist **nicht** gewollt: Der Eintrag fällt still weg, und das
            #    Projekt rechnet bei jedem Öffnen den ganzen Stapel neu.
            #
            # Was hier ankommt, meint deshalb nur noch den zweiten Fall — die
            # Warnung ist wieder eine. ``_name_to_data`` deckt die zwei
            # bekannten Stellen ab; eine dritte wäre ein weiteres Feld dieses
            # Payloads.
            _log.warning("could not write cache entry %s: %s", key, problem)
            if folder is not None:
                shutil.rmtree(folder, ignore_errors=True)
            return
        self._account_for(folder)

    def _account_for(self, folder: Path) -> None:
        """Rechnet den frisch geschriebenen Eintrag auf und räumt, wenn nötig.

        Hier stand ``self.trim()``, und das war die teuerste Zeile des Caches:
        ``trim`` fragt zuerst, wie groß der Ordner ist, und diese Frage geht
        über jede Datei darin. Gemessen an einem Cache mit 2000 Einträgen
        kostet der Gang **254 ms** — bei 500 noch 62, bei 100 noch 20. Er lief
        nach *jedem* geschriebenen Op-Ergebnis; eine Auswertung mit einem
        Dutzend neuer Schritte hätte also drei Sekunden mit dem Zählen von
        Dateien verbracht, um einen Cache zu füllen, der Zeit sparen soll.

        Jetzt wird mitgezählt: Was geschrieben wurde, kommt auf einen Stand
        oben drauf, und über den Ordner geht es erst, wenn dieser Stand das
        Budget reißt. Einmal je Prozess muss es sein — beim ersten Schreiben
        ist der Stand unbekannt, weil frühere Läufe im Ordner liegen.

        Der Stand darf zu hoch liegen und nie zu niedrig: Ein Eintrag, der
        unter demselben Schlüssel ein zweites Mal geschrieben wird, zählt
        zweimal, und ein beschädigter, den ``get`` wegwirft, zählt weiter mit.
        Beides führt zu einem ``trim``, das einmal zu früh kommt — und das
        zählt neu und stellt den Stand richtig. Der umgekehrte Fehler wäre
        ein Cache, der über sein Budget wächst, ohne es zu merken.
        """
        if self._known_bytes is None:
            self.trim()
            return
        self._known_bytes += _folder_bytes(folder)
        if self._known_bytes > self.budget_bytes:
            self.trim()

    def size_bytes(self) -> int:
        """Was der Cache belegt — ein Gang über jede Datei darin."""
        if not self.directory.is_dir():
            return 0
        total = 0
        for path in self.directory.rglob("*"):
            with suppress(OSError):
                if path.is_file():
                    total += path.stat().st_size
        return total

    def trim(self) -> None:
        """Wirft die am längsten unbenutzten Einträge, bis das Budget stimmt.

        Ein Gang über den Ordner, nicht einer je gelöschtem Eintrag: Die Größe
        jedes Eintrags steht schon fest, wenn die Reihenfolge feststeht, und
        abziehen ist billiger als noch einmal zählen. Vorher lief ``size_bytes``
        in der Löschschleife — bei einem Cache, der weit über das Budget
        gewachsen ist, war das der Gang über alle Dateien mal der Zahl der
        gelöschten Ordner.

        **Ein Eintrag, der zwischen Auflisten und Ansehen verschwindet, wird
        übersprungen und wirft nicht.** Diesen Ordner teilen mehrere Prozesse:
        zwei Fenster, die Oberfläche neben der Kommandozeile, und beim Wechsel
        der Fassung ein Aufräumer. Ein `stat` auf etwas, das ein anderer gerade
        gelöscht hat, wäre sonst ein Fehler, der aus ``put`` heraus die ganze
        Auswertung mitnimmt — nachdem sie alles gerechnet hat, und nur weil das
        Aufräumen nicht klappte. Ein Cache darf keinen Lauf kosten, den er
        beschleunigen soll.
        """
        entries: list[tuple[float, Path, int]] = []
        for folder in self.directory.glob("*/*"):
            with suppress(OSError):
                if folder.is_dir():
                    entries.append((folder.stat().st_mtime, folder, _folder_bytes(folder)))
        total = sum(size for _, _, size in entries)
        self._known_bytes = total
        if total <= self.budget_bytes:
            return
        for _, folder, size in sorted(entries, key=lambda entry: entry[0]):
            shutil.rmtree(folder, ignore_errors=True)
            total -= size
            self._known_bytes = total
            if total <= self.budget_bytes:
                return

    def clear(self) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)
        self._known_bytes = 0


def disk_backed_cache() -> ResultCache:
    """Der Cache, den die Anwendung benutzt: Speicher über Platte (§38).

    Hier stand nichts, und das war der Fehler. `DiskCache` war gebaut,
    `MeshCodec` war gebaut, `ResultCache` nahm die Ebene als Argument, und
    `tests/test_cache.py` bewies jedes Stück für sich — aber die zwei Stellen,
    an denen die Anwendung wirklich einen Cache baute, übergaben sie nicht:
    ``app/ui/session.py`` schrieb ``ResultCache()``, und die Kommandozeile
    übergab überhaupt keinen. Jedes Öffnen eines Projekts rechnete den ganzen
    Operationsstapel neu; bei einem Körper mit 1,3 Millionen Dreiecken sind das
    gemessen 5063 ms gegen 209 ms mit Platte. §38 verspricht die Ebene, §31
    setzt ihr ein Ziel — verbunden war sie nicht.

    Deshalb steht der Bauer jetzt hier und nicht bei den Aufrufern: Eine
    Anwendung mit zwei Einstiegen braucht **eine** Antwort auf die Frage, wie
    ihr Cache aussieht, sonst driften die zwei.

    Der Codec kommt aus einem Import in dieser Funktion und nicht aus dem
    Modulkopf. Das ist die Zeile, die der Kopf dieser Datei beschreibt: Ein Netz
    zu serialisieren braucht die Geometrieschicht, und wer nur den Cache
    importiert, soll sie nicht mitziehen — `DiskCache` bleibt mit einem falschen
    Netz prüfbar. Genau diese Trennung hat den Anschluss vergessbar gemacht;
    eine Vorgabe hätte sie aufgehoben, ein Bauer nimmt ihr die Falle.

    **Ohne Platte statt mit Fehler.** Lässt sich der Ordner nicht anlegen — ein
    volles Laufwerk, ein Profil ohne Schreibrecht —, kommt der Cache ohne sie
    zurück. Eine Beschleunigung ist keine Voraussetzung, und ein Fehler beim
    Start wegen eines Ordners, den der Nutzer nie sehen wollte, wäre schlimmer
    als ein Projekt, das langsamer öffnet.
    """
    from app.core.geom.mesh import MeshCodec

    try:
        disk = DiskCache(codec=MeshCodec())
        ensure_dir(disk.directory)
        drop_other_versions(disk.directory)
    except OSError as problem:
        _log.warning("no disk cache, working from memory only: %s", problem)
        return ResultCache()
    return ResultCache(disk=disk)
