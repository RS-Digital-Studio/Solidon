"""Der Ergebnis-Cache über dem Operations-Hash (Bauplan §15, §38).

Zwei Ebenen. Im Speicher ein LRU-Ablage, begrenzt über die Dreieckszahl —
denn die ist es, die den Rechner wirklich füllt. Auf der Platte dieselben
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
import shutil
import threading
from collections import OrderedDict
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Protocol

from app.core.log import get_logger
from app.core.paths import ensure_dir, results_cache_dir
from app.core.scene.serialise import (
    finding_from_data,
    finding_to_data,
    solver_from_data,
    solver_to_data,
)
from app.core.types import (
    Feature,
    Finding,
    MaterialSlot,
    Mesh,
    SceneObject,
    SolverInfo,
    Transform,
)
from app.i18n import TranslatableText

_log = get_logger(__name__)

#: Grobe Obergrenze im Speicher. Eine Million Dreiecke ist das
#: Viewport-Ziel (§31).
DEFAULT_TRIANGLE_BUDGET: Final = 20_000_000

#: Obergrenze des Platten-Caches; die ältesten Einträge gehen zuerst.
DEFAULT_DISK_BUDGET_BYTES: Final = 2 * 1024 * 1024 * 1024


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

    @property
    def cost(self) -> int:
        """Dreiecke dieses Eintrags — das Maß, in dem das Budget zählt."""
        return sum(entry.mesh.triangle_count for entry in self.objects)


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
    ) -> None:
        self._entries: OrderedDict[str, CachedResult] = OrderedDict()
        self._cost = 0
        self._budget = triangle_budget
        self._disk = disk
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

        Ein ``RLock`` und kein ``Lock``: ``get`` ruft bei einem Treffer auf der
        Platte ``_store`` auf, hält das Schloss also schon."""

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

    def _store(self, key: str, result: CachedResult) -> None:
        """Nur mit gehaltenem Schloss aufrufen — siehe :attr:`_lock`."""
        if key in self._entries:
            self._cost -= self._entries.pop(key).cost
        self._entries[key] = result
        self._cost += result.cost
        while self._cost > self._budget and len(self._entries) > 1:
            _, dropped = self._entries.popitem(last=False)
            self._cost -= dropped.cost
            self.statistics.evictions += 1

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
            self._entries.clear()
            self._cost = 0

    @property
    def cost(self) -> int:
        with self._lock:
            return self._cost

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


# --- Plattenebene ----------------------------------------------------------------


def _feature_to_data(feature: Feature) -> dict[str, Any]:
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
    }


def _feature_from_data(data: dict[str, Any]) -> Feature:
    return Feature(
        id=data["id"],
        kind=data["kind"],
        provenance=data["provenance"],
        params=data["params"],
        face_indices=tuple(data["face_indices"]),
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
    """
    if isinstance(name, TranslatableText):
        return {"msgid": name.msgid, "context": name.context}
    return str(name)


def _name_from_data(data: str | dict[str, Any]) -> TranslatableText | str:
    """Gegenstück zu :func:`_name_to_data`.

    Eine schlichte Zeichenkette ist ein selbst vergebener Name — **und ein
    Eintrag aus einem älteren Cache**, der die Unterscheidung noch nicht
    kannte. Beide sind wörtlich gemeint und bleiben es.
    """
    if isinstance(data, dict):
        return TranslatableText(data["msgid"], data.get("context"))
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
    }


def _slot_from_data(data: dict[str, Any]) -> MaterialSlot:
    colour = data.get("colour")
    return MaterialSlot(
        index=data["index"],
        name=_name_from_data(data["name"]),
        colour=(colour[0], colour[1], colour[2]) if colour else None,
        material=data.get("material"),
        material_type=data.get("material_type"),
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
            objects = tuple(
                SceneObject(
                    id=entry["id"],
                    name=_name_from_data(entry["name"]),
                    mesh=self.codec.loads((folder / entry["mesh"]).read_bytes()),
                    kind=entry["kind"],
                    features={
                        key_: _feature_from_data(value) for key_, value in entry["features"].items()
                    },
                    material_slots=[_slot_from_data(slot) for slot in entry["material_slots"]],
                    material=entry.get("material"),
                    created_by=entry["created_by"],
                    visible=entry["visible"],
                    plate=entry.get("plate", 0),
                )
                for entry in data["objects"]
            )
            # Die drei Beifänge gehören zum Ergebnis wie die Körper selbst:
            # ohne `transform` liest `_with_features` die alten Merkmale im
            # falschen Bezugspunkt und benennt sie um (§21.2), ohne
            # `findings` verschwindet die Voxel-Warnung, die §17.2 nie
            # stillschweigend lassen will. Sie wurden geschrieben — nur
            # gelesen hat sie niemand.
            findings = tuple(finding_from_data(entry) for entry in data.get("findings", []))
            solver = solver_from_data(data.get("solver"))
            raw_transform = data.get("transform")
            transform: Transform | None = (
                tuple(tuple(float(value) for value in row) for row in raw_transform)  # type: ignore[assignment]
                if raw_transform
                else None
            )
        except (OSError, KeyError, ValueError) as problem:
            # Ein beschädigter Cache-Eintrag ist nie fatal: verwerfen und
            # neu rechnen.
            _log.warning("dropping unreadable cache entry %s: %s", key, problem)
            shutil.rmtree(folder, ignore_errors=True)
            return None
        folder.touch(exist_ok=True)
        return CachedResult(objects=objects, findings=findings, solver=solver, transform=transform)

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
        folder = ensure_dir(self._folder(key))
        entries: list[dict[str, Any]] = []
        try:
            for position, entry in enumerate(result.objects):
                name = f"{position}{self.codec.suffix}"
                (folder / name).write_bytes(self.codec.dumps(entry.mesh))
                entries.append(
                    {
                        "id": entry.id,
                        "name": _name_to_data(entry.name),
                        "mesh": name,
                        "kind": entry.kind,
                        "features": {
                            key_: _feature_to_data(value) for key_, value in entry.features.items()
                        },
                        "material_slots": [_slot_to_data(slot) for slot in entry.material_slots],
                        "material": entry.material,
                        "created_by": entry.created_by,
                        "visible": entry.visible,
                        "plate": entry.plate,
                    }
                )
            payload: dict[str, Any] = {"objects": entries}
            if result.findings:
                payload["findings"] = [finding_to_data(entry) for entry in result.findings]
            if result.solver is not None:
                payload["solver"] = solver_to_data(result.solver)
            if result.transform is not None:
                payload["transform"] = [list(row) for row in result.transform]
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
