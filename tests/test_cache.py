"""Ergebniscache über den Op-Hash (Bauplan §15, §38)."""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import time
from pathlib import Path

import pytest

from app.core.scene.cache import CachedResult, DiskCache, ResultCache
from app.core.scene.hashing import digest, object_hash, operation_hash, profile_key
from app.core.types import Mesh, Operation, Profile, SceneObject
from app.i18n import TranslatableText
from tests.conftest import FakeMesh, make_object


class FakeCodec:
    """Steht für die Geometrieschicht, die den echten später liefert."""

    suffix = ".json"

    def stores(self, mesh: Mesh) -> bool:
        return True

    def dumps(self, mesh: Mesh) -> bytes:
        source = mesh  # type: ignore[assignment]
        return json.dumps(
            {
                "triangles": source.triangle_count,
                "vertices": source.vertex_count,
                "size": list(source.bounds.size),
            }
        ).encode("utf-8")

    def loads(self, data: bytes) -> Mesh:
        values = json.loads(data)
        return FakeMesh(  # type: ignore[return-value]
            triangles=values["triangles"],
            vertices=values["vertices"],
            size=tuple(values["size"]),
        )


def result(triangles: int = 100, object_id: str = "obj_1") -> CachedResult:
    return CachedResult(objects=(make_object(object_id, triangles=triangles),))


def test_a_recognised_flag_survives_the_cache() -> None:
    """Szene 3: ohne ``recognised`` im Cache verwaisen benannte Baustein-Bohrungen.

    Ein Baustein benennt seine Bohrungen beim Bauen und setzt ``recognised=False``,
    weil ``detect`` sie an ihrer Stelle nicht findet. Fiel das Feld beim
    Cache-Treffer auf die Vorgabe ``True`` zurück, wanderte das Merkmal in die
    Erkennungsprüfung, fand keinen Partner und verwaiste — der Fehler, gegen den
    das Feld eingebaut wurde, nur eine Cache-Ebene weiter.
    """
    from app.core.scene.cache import _feature_from_data, _feature_to_data
    from app.core.types import Feature

    named = Feature(
        id="heatset_m4_bore_1",
        kind="hole",
        provenance="generated",
        params={"diameter": 4.0},
        face_indices=(),
        recognised=False,
        created_by=3,
    )

    revived = _feature_from_data(_feature_to_data(named))
    assert revived.recognised is False, "recognised überlebt den Cache"

    # Rückwärtsverträglich wie ``created_by``: ein Eintrag ohne das Feld gilt als
    # erkannt.
    old_entry = {
        "id": "x",
        "kind": "hole",
        "provenance": "detected",
        "params": {},
        "face_indices": [],
    }
    assert _feature_from_data(old_entry).recognised is True


def test_a_hit_returns_what_was_stored() -> None:
    cache = ResultCache()
    cache.put("key", result())
    assert cache.get("key") is not None
    assert cache.get("missing") is None
    assert cache.statistics.hits == 1
    assert cache.statistics.misses == 1


def test_the_budget_is_counted_in_triangles() -> None:
    cache = ResultCache(triangle_budget=250)
    cache.put("a", result(100, "obj_1"))
    cache.put("b", result(100, "obj_2"))
    assert cache.cost == 200
    assert len(cache) == 2

    cache.put("c", result(100, "obj_3"))
    assert len(cache) == 2, "the least recently used entry gives way"
    assert cache.get("a") is None
    assert cache.statistics.evictions == 1


def test_reading_an_entry_keeps_it_alive() -> None:
    cache = ResultCache(triangle_budget=250)
    cache.put("a", result(100, "obj_1"))
    cache.put("b", result(100, "obj_2"))
    cache.get("a")
    cache.put("c", result(100, "obj_3"))
    assert cache.get("a") is not None
    assert cache.get("b") is None


def test_the_hash_covers_everything_a_result_depends_on(profile: Profile) -> None:
    operation = Operation(id=1, op="resize_object", inputs=("obj_1",), outputs=("obj_1",))
    base = operation_hash(operation, {"size": 5.0}, ["h1"], profile, "fine")

    assert base == operation_hash(operation, {"size": 5.0}, ["h1"], profile, "fine")
    assert base != operation_hash(operation, {"size": 5.1}, ["h1"], profile, "fine")
    assert base != operation_hash(operation, {"size": 5.0}, ["h2"], profile, "fine")
    assert base != operation_hash(operation, {"size": 5.0}, ["h1"], profile, "draft")
    assert base != operation_hash(
        Operation(id=1, op="resize_object", seed=1), {"size": 5.0}, ["h1"], profile, "fine"
    )


def test_the_profile_enters_the_hash(profile: Profile) -> None:
    from app.core.knowledge import profiles as profile_table

    other = profile_table.make_profile("centauri-carbon-2", "asa")
    assert profile_key(profile) != profile_key(other)


def test_hashes_are_stable_and_short() -> None:
    assert digest("a", 1) == digest("a", 1)
    assert len(digest("a")) == 32
    assert object_hash("key", 0) != object_hash("key", 1)


def test_the_disk_level_survives_a_new_process(tmp_path: Path) -> None:
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", CachedResult(objects=(make_object("obj_1", triangles=42),)))

    fresh = DiskCache(codec=FakeCodec(), directory=tmp_path)
    restored = fresh.get("key")
    assert restored is not None
    assert restored.objects[0].id == "obj_1"
    assert restored.objects[0].mesh.triangle_count == 42


def test_the_memory_level_fills_itself_from_disk(tmp_path: Path) -> None:
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    cache = ResultCache(disk=disk)
    cache.put("key", result(), to_disk=True)
    cache.clear()

    assert cache.get("key") is not None
    assert cache.statistics.disk_hits == 1
    assert len(cache) == 1, "what came from disk stays in memory"


def test_a_damaged_entry_is_dropped_instead_of_raising(tmp_path: Path) -> None:
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", result())
    folder = next(path for path in tmp_path.rglob("objects.json"))
    folder.write_text("{not json", encoding="utf-8")

    assert disk.get("key") is None
    assert disk.get("key") is None, "the damaged entry was removed, not read again"


def test_the_disk_budget_is_kept(tmp_path: Path) -> None:
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path, budget_bytes=1)
    disk.put("a" * 32, result(100, "obj_1"))
    disk.put("b" * 32, result(100, "obj_2"))
    assert disk.size_bytes() <= 400, "trimming drops the oldest entries"


def test_objects_keep_their_features_through_the_disk_level(tmp_path: Path) -> None:
    from app.core.types import Feature

    entry = SceneObject(
        id="obj_1",
        name="Halterung",
        mesh=FakeMesh(),  # type: ignore[arg-type]
        features={
            "hole_3": Feature(
                id="hole_3",
                kind="hole",
                provenance="detected",
                params={"diameter": 5.2},
                face_indices=(1, 2, 3),
            )
        },
    )
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", CachedResult(objects=(entry,)))

    restored = disk.get("key")
    assert restored is not None
    feature = restored.objects[0].features["hole_3"]
    assert feature.kind == "hole"
    assert feature.params["diameter"] == 5.2
    assert feature.face_indices == (1, 2, 3)


def test_the_disk_cache_keeps_findings_solver_and_transform(tmp_path: Path) -> None:
    """Die drei Beifänge gehören zum Ergebnis wie die Körper selbst.

    `put` schrieb nur die Objekte, `get` baute ein kahles `CachedResult`:
    nach einem Platten-Treffer las `_with_features` die alten Merkmale ohne
    die gemeldete Bewegung im falschen Bezugspunkt (§21.2), und die
    Voxel-Warnung, die §17.2 nie stillschweigend lassen will, war weg.
    """
    from app.core.types import Finding, SolverInfo

    cache = DiskCache(codec=FakeCodec(), directory=tmp_path)
    moved = (
        (1.0, 0.0, 0.0, 12.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    cache.put(
        "key",
        CachedResult(
            objects=(make_object("obj_1"),),
            findings=(Finding(code="boolean.voxel", severity="warning", message="Voxelstufe."),),
            solver=SolverInfo(strategy="voxel"),
            transform=moved,
        ),
    )

    again = cache.get("key")

    assert again is not None
    assert [entry.code for entry in again.findings] == ["boolean.voxel"]
    assert again.solver is not None and again.solver.strategy == "voxel"
    assert again.transform == moved


def test_the_cache_survives_several_threads_writing_at_once() -> None:
    """Drei Fäden legen hier ab: Auswertung, Agent und Vorschau.

    ``_store`` ist kein einzelner Schritt, sondern vier — alten Eintrag
    herausnehmen, Kosten abziehen, neuen einhängen, verdrängen bis das Budget
    passt. Wechselt der Interpreter mittendrin den Faden, stimmt ``_cost``
    nicht mehr mit dem überein, was wirklich in der Liste liegt: Der Cache
    verdrängt dann zu früh (jeder Schritt wird neu gerechnet) oder gar nicht
    mehr (er wächst, bis der Speicher knapp wird).

    **Das Umschaltintervall ist der Kern dieses Tests, nicht Beiwerk.** Der
    erste Anlauf lief ohne es — und war damit wertlos: Mit dem üblichen
    Intervall von fünf Millisekunden trifft der Fadenwechsel praktisch nie in
    die vier Schritte hinein, und die Gegenprobe *ohne* Schloss lief null von
    fünf Mal auseinander. Ein Test, der auch ohne die geprüfte Sache grün ist,
    prüft nichts. Mit einer Mikrosekunde fällt dieselbe Gegenprobe zehnmal von
    zehn.
    """
    import sys
    import threading

    cache = ResultCache(triangle_budget=3_000)
    problems: list[BaseException] = []

    def work(start: int) -> None:
        try:
            for index in range(start, start + 200):
                cache.put(f"key-{index}", result(triangles=100))
                cache.get(f"key-{index - 1}")
        except BaseException as problem:  # pragma: no cover - nur im Fehlerfall
            problems.append(problem)

    before = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=work, args=(n * 10_000,)) for n in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sys.setswitchinterval(before)

    assert not problems, f"Ausnahme in einem Faden: {problems}"
    counted = sum(entry.cost for entry in cache._entries.values())
    assert cache.cost == counted, (
        f"Der Cache nennt {cache.cost}, in der Liste liegen {counted} — die Buchführung "
        "ist unter Nebenläufigkeit auseinandergelaufen."
    )
    assert cache.cost <= cache._budget or len(cache) == 1


# --- Die Plattenebene, angeschlossen ---------------------------------------------
#
# Sie war gebaut, getestet und in der Anwendung nicht verbunden: `DiskCache`
# stand, `MeshCodec` stand, `ResultCache` nahm sie als Argument — und
# `app/ui/session.py`, die einzige Stelle, an der die Anwendung einen Cache
# baut, übergab sie nicht. Jedes Öffnen eines Projekts rechnete den ganzen
# Stapel neu, obwohl §38 die Ebene verspricht und §31 ihr ein Ziel setzt.
#
# Die Tests hier prüfen die drei Dinge, die beim Anschließen entschieden werden
# mussten: dass der Weg trägt, dass der Cache nicht in fremden Ordnern räumt,
# und dass ein Eintrag ein Update nicht überlebt.


def test_the_factory_gives_a_cache_with_a_disk_level() -> None:
    """Der Bauer, den die Anwendung benutzt — mit Platte."""
    from app.core.scene import disk_backed_cache

    cache = disk_backed_cache()
    assert cache._disk is not None, "a cache without a disk level recomputes on every open"


def test_nothing_in_the_application_builds_a_cache_without_the_disk_level() -> None:
    """Der Test, der gefehlt hat — und er liest den Text, mit Absicht.

    Jeder Test hier drüber prüfte die Plattenebene für sich, und sie war in
    Ordnung. Niemand prüfte, ob die Anwendung sie benutzt: `app/ui/session.py`
    schrieb ``ResultCache()``, die Kommandozeile übergab gar keinen Cache, und
    kein Testfeld aus §35 deckt das ab — der Fehler saß nicht in einem Modul,
    sondern zwischen zwei.

    Deshalb strukturell und nicht funktional: Ein Test, der eine Sitzung baut
    und ihren Cache ansieht, prüft die eine Stelle, die er kennt. Dieser hier
    findet auch die dritte, die morgen dazukommt.
    """
    root = Path(__file__).parent.parent / "app"
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "cache.py":
            continue  # dort wohnt die Klasse und der Bauer mit seinem Rückfall
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "ResultCache(" in line and "disk=" not in line:
                offenders.append(f"{path.relative_to(root)}:{number}")
    assert not offenders, (
        "these build a result cache without a disk level, use disk_backed_cache(): "
        + ", ".join(offenders)
    )


def test_the_cache_folder_carries_the_application_version() -> None:
    """Ein Eintrag darf ein Update nicht überleben.

    Der Schlüssel ist der Operations-Hash, und der kennt Parameter, Profil und
    Qualität — nicht die *Umsetzung*. Eine behobene Boolesche Rückfallstufe
    hätte sonst ein altes Netz aus dem Cache bekommen.
    """
    from app.branding import APP_VERSION
    from app.core.paths import results_cache_dir, user_cache_dir

    folder = results_cache_dir()
    assert folder.name.startswith(APP_VERSION)
    assert folder.parent.parent == user_cache_dir(), "below the cache root, not beside it"


def test_the_cache_does_not_tidy_up_in_its_neighbours_folders(tmp_path: Path) -> None:
    """`trim` und `clear` dürfen nur den eigenen Ordner anfassen.

    Vorher stand `DiskCache.directory` per Vorgabe auf der Cache-**Wurzel**, und
    dort wohnen die heruntergeladenen Update-Pakete und
    der Stil-Cache. Ein `trim` hätte fremde Ordner gelöscht, um sein Budget zu
    halten, und `clear` hätte die Wurzel mitgenommen — samt einem Update-Paket,
    das gerade geprüft werden sollte.
    """
    from app.core.paths import ensure_dir

    root = tmp_path / "cache"
    stranger = ensure_dir(root / "updates" / "0.1.3")
    (stranger / "solidon-setup.exe").write_bytes(b"x" * 4096)
    own = ensure_dir(root / "results" / "0.1.2")

    disk = DiskCache(codec=FakeCodec(), directory=own, budget_bytes=1)
    disk.put("a" * 32, result(100, "obj_1"))
    disk.put("b" * 32, result(100, "obj_2"))
    disk.clear()

    assert (stranger / "solidon-setup.exe").is_file(), "the update package survived"


def test_an_older_version_folder_is_dropped(tmp_path: Path) -> None:
    """Der Preis der Versionsschranke, eingesammelt.

    Ohne diesen Schritt bliebe je Fassung ein toter Ordner liegen, der bis an
    das Budget gewachsen sein darf — das eigene Budget räumt ihn nie weg, es
    zählt nur den eigenen Ordner.
    """
    from app.core.paths import ensure_dir
    from app.core.scene import drop_other_versions

    results = tmp_path / "results"
    old = ensure_dir(results / "0.1.1")
    (old / "leftover").write_bytes(b"x")
    current = ensure_dir(results / "0.1.2")

    drop_other_versions(current)

    assert not old.exists(), "the folder of the previous version is gone"
    assert current.is_dir(), "the current one stays"
    assert results.is_dir(), "and nothing above it is touched"


def test_a_generated_feature_keeps_its_name_and_origin_through_the_disk(tmp_path: Path) -> None:
    """Ein erzeugtes Merkmal, einmal über die Platte — §21.2.

    Der Test darüber schickt ein **erkanntes** Merkmal und prüft die Maße; die
    Provenienz prüft er nicht. Sie ist aber der Teil, an dem §21.2 hängt: Ein
    erzeugtes Merkmal trägt den Namen der Operation, die es gemacht hat, und
    genau dieser Name ist es, worauf ein späterer Schritt sich beruft. Käme er
    als „detected" zurück, wäre die Kette still zerrissen.
    """
    from app.core.types import Feature

    entry = SceneObject(
        id="obj_1",
        name="Halterung",
        mesh=FakeMesh(),  # type: ignore[arg-type]
        features={
            "op3.pin_1": Feature(
                id="op3.pin_1",
                kind="pin",
                provenance="generated",
                params={"diameter": 3.0},
                face_indices=(4, 5),
            )
        },
    )
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", CachedResult(objects=(entry,)))

    restored = disk.get("key")
    assert restored is not None
    feature = restored.objects[0].features["op3.pin_1"]
    assert feature.id == "op3.pin_1"
    assert feature.provenance == "generated", "a generated feature must not come back as detected"
    assert feature.kind == "pin"


def test_the_budget_is_checked_without_walking_the_folder_every_time(tmp_path: Path) -> None:
    """Was geschrieben wurde, wird mitgezählt statt nachgezählt.

    `put` rief am Ende `trim`, und `trim` fragte zuerst über jede Datei im
    Ordner, wie groß er ist — gemessen 254 ms bei 2000 Einträgen, je
    geschriebenem Op-Ergebnis. Jetzt geht der Gang einmal je Prozess und danach
    erst wieder, wenn das Budget reißt.
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path, budget_bytes=10_000_000)
    assert disk._known_bytes is None, "nothing counted before the first write"

    disk.put("a" * 32, result(100, "obj_1"))
    after_first = disk._known_bytes
    assert after_first is not None, "the first write counts the folder once"

    disk.put("b" * 32, result(100, "obj_2"))
    assert disk._known_bytes is not None
    assert disk._known_bytes > after_first, "the second write was added, not recounted"
    assert disk._known_bytes == disk.size_bytes(), "and the running total is right"


def test_an_own_part_that_changed_gets_a_folder_of_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein eigener Baustein ist eine Operation, die kein Update begleitet.

    Ändert der Nutzer ein Maß in seinem eigenen Baustein (§24.5), bleiben
    Op-Name und Parameter gleich, und der Operations-Hash sieht nichts. Im
    Speicher war das gleichgültig; auf der Platte hieße es, dass die eigene
    Änderung beim nächsten Öffnen verschwiegen wird — und gemeldet wird sie
    nicht, denn ``changed_since_library`` liest gepflegte Änderungsverläufe,
    und die pflegt beim Ausprobieren niemand.
    """
    from app.branding import APP_VERSION
    from app.core import paths

    parts = tmp_path / "parts"
    parts.mkdir()
    monkeypatch.setattr(paths, "user_parts_dir", lambda: parts)

    without = paths.results_cache_dir()

    own = parts / "magnet_pocket.py"
    own.write_text("# ein eigener Baustein", encoding="utf-8")
    with_part = paths.results_cache_dir()

    own.write_text("# dasselbe Maß, ein anderer Wert", encoding="utf-8")
    os.utime(own, (1_000_000, 1_000_000))
    after_change = paths.results_cache_dir()

    assert without != with_part, "an own part has to show in the folder"
    assert with_part != after_change, "and changing it has to change the folder again"
    assert after_change.name.startswith(APP_VERSION), "the version still leads"


def test_two_readers_and_writers_share_one_folder(tmp_path: Path) -> None:
    """Den Ordner teilen mehrere Prozesse, und zwar seit dem Anschluss.

    Vorher gab es genau einen möglichen Schreiber, weil es keinen gab. Jetzt
    schreiben die Oberfläche und die Kommandozeile in denselben Ordner, zwei
    Fenster erst recht — und wenn einer davon aufräumt, darf der andere nicht
    darüber fallen. Was er verliert, ist ein Eintrag; was er tut, ist neu
    rechnen.
    """
    surface = DiskCache(codec=FakeCodec(), directory=tmp_path)
    terminal = DiskCache(codec=FakeCodec(), directory=tmp_path)

    surface.put("a" * 32, result(100, "obj_1"))
    terminal.put("b" * 32, result(100, "obj_2"))

    assert surface.get("b" * 32) is not None, "each one reads what the other wrote"
    assert terminal.get("a" * 32) is not None

    # Ein dritter mit einem Budget, das nichts zulässt: er räumt alles weg.
    DiskCache(codec=FakeCodec(), directory=tmp_path, budget_bytes=1).trim()

    assert surface.get("a" * 32) is None, "gone is gone, and that is not an error"
    terminal.put("c" * 32, result(100, "obj_3"))
    assert terminal.get("c" * 32) is not None, "and writing goes on afterwards"


def test_a_changed_core_file_gets_a_folder_of_its_own() -> None:
    """Die Fassung im Pfad hält für den Kunden, nicht für den Arbeitsbaum.

    Zwischen zwei Starts wird hier eine Boolesche Rückfallstufe geändert und
    ``APP_VERSION`` bleibt „0.1.2". Ohne diese Schranke läge danach das Netz
    des alten Codes im Cache, und die Berichtigung wäre stillschweigend
    ausgehebelt — auf der einzigen Maschine, auf der Solidon heute läuft.
    """
    from app.core import paths

    before = paths.results_cache_dir()

    touched = Path(paths.__file__)
    state = touched.stat()
    # Absolut in die Zukunft und nicht relativ zu dieser Datei: Gefragt ist das
    # **Maximum** über den Kern, und eine andere Datei kann längst jünger sein
    # — wer gerade `cache.py` geschrieben hat, machte diesen Test sonst rot,
    # ohne dass etwas kaputt war.
    os.utime(touched, ns=(state.st_atime_ns, time.time_ns() + 10_000_000_000))
    try:
        after = paths.results_cache_dir()
    finally:
        os.utime(touched, ns=(state.st_atime_ns, state.st_mtime_ns))

    assert before != after, "a touched core file has to show in the folder"
    assert paths.results_cache_dir() == before, "and putting the time back puts it back"


def test_a_built_package_needs_no_source_stamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein gebautes Paket hat keine Quelldateien, die sich ändern könnten.

    Dort ist die Fassung die ganze Wahrheit, und ein Gang über einen Ordner,
    den es nicht gibt, wäre nur Arbeit ohne Aussage.
    """
    import sys

    from app.branding import APP_VERSION
    from app.core import paths

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert paths.results_cache_dir().name == APP_VERSION


def test_nobody_writes_into_the_shared_cache_root() -> None:
    """Die Wurzel des Cache-Ordners gehört niemandem allein.

    Dort wohnen die Update-Pakete, der Stil-Cache und die
    Ergebnisse — und jeder von ihnen räumt in seinem eigenen Unterordner auf.
    Der Ergebnis-Cache tat es einmal in der Wurzel, mit ``rmtree``; das ist
    behoben, aber die Regel dahinter stand nur in einem Docstring. Hier steht
    sie als Test: Wer ``user_cache_dir()`` benutzt, hängt einen Unterordner an.
    """
    root = Path(__file__).parent.parent / "app"
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "paths.py":
            continue  # dort wird die Wurzel definiert
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            bare = line.lstrip()
            if "user_cache_dir" not in line or bare.startswith(("#", "from ", "import ")):
                continue
            # Auf den Namen muss ``() /`` folgen. Ohne Klammern ist es die
            # Funktion selbst — genau so stand der Fehler in `DiskCache`:
            # ``field(default_factory=user_cache_dir)``. Ein Wächter, der nur
            # den Aufruf sucht, hätte ihn nicht gesehen.
            if not line.split("user_cache_dir", 1)[1].lstrip().startswith("() /"):
                offenders.append(f"{path.relative_to(root)}:{number}")
    assert not offenders, (
        "these take the shared cache root itself instead of a folder below it: "
        + ", ".join(offenders)
    )


def test_the_disk_level_holds_only_what_was_offered_to_it(tmp_path: Path) -> None:
    """Ablegen auf der Platte ist ein Verlangen, kein Nebeneffekt.

    Die Vorgabe steht auf ``False``, weil die Fehlerrichtungen verschieden
    schwer sind: Ein vergessenes ``to_disk=False`` gäbe über Sitzungen hinweg
    falsche Ergebnisse, ein vergessenes ``to_disk=True`` nur eine langsamere
    Anwendung. Dieser Test hält die Richtung fest.
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    cache = ResultCache(disk=disk)

    cache.put("a" * 32, result(100, "obj_1"))
    assert disk.get("a" * 32) is None, "nothing lands on the disk unasked"
    assert cache.get("a" * 32) is not None, "but the memory level has it"

    cache.put("b" * 32, result(100, "obj_2"), to_disk=True)
    assert disk.get("b" * 32) is not None, "and what was offered is there"


def test_a_second_evaluation_comes_off_the_disk(tmp_path: Path, profile: Profile) -> None:
    """Zweimal auswerten, dazwischen den Speicher wegwerfen — §31, unter 1 s.

    Das ist der Weg, den die Anwendung beim Öffnen eines Projekts geht: ein
    frisches Fenster, ein leerer Speichercache, dieselbe Platte. Vorher wurde
    dabei der ganze Operationsstapel neu gerechnet.
    """
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    meshes = Path(__file__).parent / "data" / "meshes"
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/cube_clean.stl", sha256=""
    )
    project.sources["src_1"] = (meshes / "cube_clean.stl").read_bytes()
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )

    disk = DiskCache(codec=MeshCodec(), directory=tmp_path)
    sources = ProjectSources(project)
    evaluate(project.document, profile, sources=sources, cache=ResultCache(disk=disk))

    second = ResultCache(disk=disk)
    result = evaluate(project.document, profile, sources=sources, cache=second)

    assert second.statistics.disk_hits == 1, "the reopened project came off the disk"
    assert second.statistics.misses == 0, "nothing was recomputed"
    assert len(result.scene.objects) == 1


def test_a_question_comes_back_when_the_project_is_reopened(
    tmp_path: Path, profile: Profile
) -> None:
    """Was aus einer Antwort entstand, gehört nicht auf die Platte (§15.7).

    `bracket_inch.stl` ist zwischen Zoll und Zentimeter mehrdeutig, die
    Eingangsstufe fragt also (§11.1). Die Antwort steht heute nirgends im
    Dokument — nicht in den Parametern der fragenden Operation —, also ist das
    Ergebnis **keine reine Funktion des Dokuments**, und genau das darf der
    Cache nicht über eine Sitzung hinaus behalten.

    Gemessen am 22.08.2026, bevor es diesen Test gab: erste Auswertung fragte
    einmal, zweite über die Platte fragte **nicht**. Der Nutzer hätte ein
    Projekt geöffnet und stillschweigend eine Annahme bekommen, wo eine Frage
    stand — und ob überhaupt gefragt wird, hätte das Dateisystem entschieden,
    denn eine Cache-Datei darf jederzeit gelöscht werden (§38). Regel 21 sagt
    „nie stillschweigend raten".

    **Dieser Test und ``test_a_second_evaluation_comes_off_the_disk`` halten
    sich gegenseitig ehrlich.** Der andere verlangt einen Treffer auf der
    Platte, dieser verlangt sein Ausbleiben — beide können nicht grün sein,
    wenn die Ebene gar nicht benutzt wird. Damit ist die Gegenfrage beantwortet,
    die man jedem Test stellen sollte: Was müsste kaputt sein, damit er rot
    wird? Bei einem Paar, das sich ausschließt, gibt es darauf keine bequeme
    Antwort. Wer einen von beiden ändert, muss den anderen ansehen.

    Der Test bleibt stehen, wenn §15.7 umgesetzt ist. Dann steht die Antwort in
    den Parametern, der Schlüssel kennt sie, und **deshalb** wird wieder
    gefragt, sobald sie fehlt — dieselbe Aussage, ein anderer Weg dorthin.
    """
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    meshes = Path(__file__).parent / "data" / "meshes"
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/bracket_inch.stl", sha256=""
    )
    project.sources["src_1"] = (meshes / "bracket_inch.stl").read_bytes()
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "auto"})]
    )

    asked: list[str] = []

    def ask(question: str, choices: list[str]) -> str:
        asked.append(question)
        return choices[0]

    disk = DiskCache(codec=MeshCodec(), directory=tmp_path)
    sources = ProjectSources(project)
    evaluate(project.document, profile, sources=sources, cache=ResultCache(disk=disk), ask=ask)
    assert len(asked) == 1, "the ambiguity reaches whoever can answer it"

    # Ein neues Fenster: leerer Speicher, dieselbe Platte.
    evaluate(project.document, profile, sources=sources, cache=ResultCache(disk=disk), ask=ask)
    assert len(asked) == 2, "and it reaches them again, because the answer is nowhere"


def test_every_caller_says_whether_the_result_may_go_to_disk() -> None:
    """Die Entscheidung muss dastehen, nicht aus einer Vorgabe folgen.

    Die Vorgabe von ``to_disk`` ist ``False``, damit ein Vergessen nur langsam
    macht und nicht falsch. Das schützt gegen das Vergessen — nicht gegen ein
    falsches ``True``, und dagegen kann kein Test schützen: „hängt von etwas ab,
    das nicht im Dokument steht" ist an einer Aufrufstelle nicht ablesbar.

    Was dieser Test leistet, ist weniger und trotzdem etwas: Er verlangt, dass
    jede Stelle die Entscheidung **hinschreibt**. Damit steht sie in jedem Diff,
    den jemand liest, statt in einer Vorgabe, an die niemand denkt. Aus einer
    Bitte wird eine Aussage, über die man streiten kann.

    Der eigentliche Ort für die andere Hälfte ist nicht der Cache: Eine
    Operation, die die Uhr liest oder eine Datei außerhalb des Projekts,
    verstößt gegen §11 und Regel 9, ganz unabhängig von jeder Cache-Ebene.
    """
    root = Path(__file__).parent.parent / "app"
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "cache.py":
            continue  # dort wohnt die Klasse, und `DiskCache.put` kennt kein Wort
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ".put(" not in line or "to_disk=" in line:
                continue
            if "sink.put(" in line or "feed.put(" in line:
                # ``queue.Queue`` eines Pump-Fadens (comfy_setup._pump und
                # install._stream) — kein Cache, kennt kein ``to_disk``.
                # Kuratierte Ausnahme wie GERMAN_STEMS: Wer eine weitere
                # Warteschlange baut, trägt ihren Namen hier ein, und das
                # breite Netz bleibt gespannt.
                continue
            offenders.append(f"{path.relative_to(root)}:{number}")
    assert not offenders, (
        "these put a result into the cache without saying whether it may be kept: "
        + ", ".join(offenders)
    )


def test_a_translatable_object_name_does_not_drop_the_whole_entry(tmp_path: Path) -> None:
    """Ein übersetzbarer Name ließ den Cache-Eintrag der ganzen Auswertung fallen.

    Seit Objektnamen aus dem Register kommen, ist ``SceneObject.name`` ein
    ``TranslatableText``. ``json.dumps`` kann den nicht ablegen, und der
    ``TypeError`` landete im ``except``-Zweig, der für nicht ablegbare
    B-Rep-Körper gedacht ist: Der Ordner wurde weggeräumt, das Protokoll bekam
    eine Zeile, und für den Kunden rechnete jedes konstruierte Projekt bei
    jeder Auswertung neu — ohne dass etwas falsch war, nur langsam.

    Dieser Test prüft **beides**: dass der Eintrag entsteht, und dass der Name
    seine Message-ID behält statt seiner Übersetzung.
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    named = SceneObject(
        id="obj_1",
        name=TranslatableText("Quader"),
        mesh=FakeMesh(triangles=42),  # type: ignore[arg-type]
    )
    disk.put("key", CachedResult(objects=(named,)))

    restored = DiskCache(codec=FakeCodec(), directory=tmp_path).get("key")
    assert restored is not None, "der Eintrag fiel weg, statt geschrieben zu werden"
    assert restored.objects[0].name == TranslatableText("Quader")


def test_a_cached_name_is_stored_as_its_message_id(tmp_path: Path) -> None:
    """Nie die Übersetzung — die wechselt mit der Sprache, der Cache nicht.

    Läge der übersetzte Text in der Datei, bekäme der Kunde nach einem
    Sprachwechsel den alten Namen zurück: ein Fehler, den nur ein **warmer**
    Cache zeigt und den darum niemand beim Entwickeln sieht.
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put(
        "key",
        CachedResult(
            objects=(
                SceneObject(
                    id="obj_1",
                    name=TranslatableText("Quader"),
                    mesh=FakeMesh(triangles=1),  # type: ignore[arg-type]
                ),
            )
        ),
    )

    written = json.loads(next(tmp_path.rglob("objects.json")).read_text(encoding="utf-8"))

    assert written["objects"][0]["name"] == {"msgid": "Quader", "context": None}


def test_a_translatable_slot_name_does_not_drop_the_whole_entry(tmp_path: Path) -> None:
    """Der Zwilling drei Tage später, an derselben Protokollzeile.

    Der Test darüber hält den **Objektnamen** fest. Am 26.08.2026 kam dieselbe
    Zeile aus einem Lauf von ``tools/make_web_images.py de`` — ``could not
    write cache entry …: Object of type TranslatableText is not JSON
    serializable`` —, diesmal aus ``app/examples/schild-zweifarbig.p3d`` und
    aus einem anderen Feld: dem Namen eines **Materialslots**. Der Weg dorthin
    ist derselbe wie beim Objektnamen: Das Beispiel vermerkt an ``assign_slot``,
    dass ``name`` eine Message-ID trägt (``Operation.translatable``, §4.1), die
    Auswertung macht daraus ein ``TranslatableText``, und die Operation reicht
    ihn unverändert in den Slot weiter.

    **Geprüft wird der Ordner, nicht der Rückgabewert.** ``DiskCache.put`` gibt
    nichts zurück und fängt den ``TypeError`` selbst ab: Es räumt den Ordner
    weg, schreibt eine Zeile ins Protokoll und kehrt zurück, als wäre nichts
    gewesen. Ein Test, der nur ``put`` aufruft, sähe den Fehler deshalb nie —
    genau daran lag es, dass er dreimal durchkam.

    Beide Namen stehen absichtlich in **einem** Objekt: Der Payload wird in
    einem Zug geschrieben, ein einziges nicht ablegbares Feld nimmt alle
    anderen mit.
    """
    from app.core.types import MaterialSlot

    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    named = SceneObject(
        id="obj_2",
        name=TranslatableText("Lettern"),
        mesh=FakeMesh(triangles=42),  # type: ignore[arg-type]
        material_slots=[
            MaterialSlot(index=1, name=TranslatableText("Weiß"), colour=(1.0, 1.0, 1.0))
        ],
    )

    disk.put("key", CachedResult(objects=(named,)))

    written = list(tmp_path.rglob("objects.json"))
    assert written, "der Eintrag wurde weggeräumt, statt geschrieben zu werden"

    restored = DiskCache(codec=FakeCodec(), directory=tmp_path).get("key")
    assert restored is not None
    slot = restored.objects[0].material_slots[0]
    assert slot.name == TranslatableText("Weiß"), "der Slotname überlebt den Rundlauf"
    assert isinstance(slot.name, TranslatableText), "und zwar als Message-ID, nicht als Text"
    assert slot.colour == (1.0, 1.0, 1.0), "und die Farbe daneben ebenso"

    # In der Datei steht die ID, nicht ihre Übersetzung — sonst hieße der Slot
    # nach einem Sprachwechsel weiter „Weiß". Dasselbe prüft
    # ``test_a_cached_name_is_stored_as_its_message_id`` für den Objektnamen.
    data = json.loads(written[0].read_text(encoding="utf-8"))
    assert data["objects"][0]["material_slots"][0]["name"] == {"msgid": "Weiß", "context": None}


def test_every_field_of_a_cache_entry_survives_a_translatable_text(tmp_path: Path) -> None:
    """Der Wächter gegen den **nächsten** Zwilling, nicht gegen die zwei bekannten.

    Zweimal ist derselbe Fehler an einem anderen Feld desselben Payloads
    aufgetaucht, und beide Male hat ihn kein Test gefunden, sondern eine Zeile
    im Protokoll eines Laufs, der etwas ganz anderes wollte. Dieser Test füllt
    deshalb **jedes** Feld, das einen Text tragen kann, mit einem
    ``TranslatableText`` und verlangt, dass der Eintrag trotzdem entsteht:
    Objektname, Slotname, Befundtext und die Notiz des Lösers.

    Was dabei nicht in Frage kommt, steht ausdrücklich daneben — ``id``,
    ``kind``, ``provenance``, ``created_by``, ``visible``, ``plate``,
    ``index``, ``colour``, ``material``, ``face_indices`` und ``transform``
    sind Kennungen, Zahlen und Wahrheitswerte, und ``Feature.params`` trägt
    Maße. Wer dort einen Text unterbringt, hat ein anderes Problem als den
    Cache.

    Geprüft wird wieder am Ordner: ``put`` verschluckt den ``TypeError``.
    """
    from app.core.types import Feature, Finding, MaterialSlot, SolverInfo

    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    entry = SceneObject(
        id="obj_1",
        name=TranslatableText("Quader"),
        mesh=FakeMesh(triangles=7),  # type: ignore[arg-type]
        features={
            "hole_1": Feature(
                id="hole_1",
                kind="hole",
                provenance="generated",
                params={"diameter": 4.2},
                face_indices=(1, 2),
                created_by=3,
            )
        },
        material_slots=[MaterialSlot(index=0, name=TranslatableText("Körper"))],
    )

    disk.put(
        "key",
        CachedResult(
            objects=(entry,),
            findings=(
                Finding(
                    code="boolean.voxel",
                    severity="warning",
                    message=TranslatableText("Voxelstufe."),
                ),
            ),
            solver=SolverInfo(strategy="voxel", note=TranslatableText("Zurück vernetzt.")),
        ),
    )

    assert list(tmp_path.rglob("objects.json")), (
        "ein einziges nicht ablegbares Feld nimmt den ganzen Eintrag mit — "
        "und das Projekt rechnet danach bei jedem Öffnen neu"
    )

    restored = DiskCache(codec=FakeCodec(), directory=tmp_path).get("key")
    assert restored is not None
    assert restored.objects[0].name == TranslatableText("Quader")
    assert restored.objects[0].material_slots[0].name == TranslatableText("Körper")
    assert restored.findings[0].message == TranslatableText("Voxelstufe.")
    assert restored.solver is not None and restored.solver.strategy == "voxel"


def test_a_self_chosen_name_stays_a_plain_string(tmp_path: Path) -> None:
    """Was ein Nutzer selbst benannt hat, wird nicht übersetzt — und ein
    Eintrag aus einem älteren Cache, der die Unterscheidung noch nicht kannte,
    ist ebenfalls eine schlichte Zeichenkette und bleibt lesbar."""
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", CachedResult(objects=(make_object("obj_1", name="Meine Halterung"),)))

    restored = DiskCache(codec=FakeCodec(), directory=tmp_path).get("key")

    assert restored is not None
    assert restored.objects[0].name == "Meine Halterung"
    assert not isinstance(restored.objects[0].name, TranslatableText)


# --- Fremde Träger im Schlüssel (Gesamtreview-b, Szene 1 Rest) -------------------


def _face_carrier(object_id: str, face: str) -> SceneObject:
    from app.core.types import Feature

    return SceneObject(
        id=object_id,
        name=object_id,
        mesh=FakeMesh(),  # type: ignore[arg-type]
        features={
            face: Feature(id=face, kind="face", provenance="detected", params={}, face_indices=(1,))
        },
    )


def test_the_key_reads_the_carrier_of_a_named_feature() -> None:
    """``align_to_feature`` liest ein Ziel auf einem fremden Körper.

    ``operation_hash`` deckt die eigenen Eingänge — das benannte Merkmal
    steht aber auf einem fremden Körper, und dessen Hash stand nicht im
    Schlüssel: Platte um 40 mm verschoben, der ausgerichtete Körper blieb
    mit Cache an der alten Lage, und der Eintrag überlebte das Schließen
    (Gesamtreview-b, Bericht 01). Der Kontext trägt jetzt die Hashes
    **aller** Träger des Merkmals — alle, weil zwei Körper denselben
    Merkmalsnamen tragen können und der Schlüssel jede Lesart decken muss.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.registry import REGISTRY
    from app.core.scene.evaluate import _with_nested_context

    params_class = REGISTRY.get("align_to_feature").params
    objects = {"obj_9": _face_carrier("obj_9", "face_a")}

    before = _with_nested_context(
        params_class, {"feature": "face_a"}, {}, None, objects, {"obj_9": "h1"}
    )
    after = _with_nested_context(
        params_class, {"feature": "face_a"}, {}, None, objects, {"obj_9": "h2"}
    )
    assert "#feature" in before, "der Träger gehört in den Kontext"
    assert before["#feature"] != after["#feature"], "sein Hash muss den Schlüssel ändern"

    empty = _with_nested_context(params_class, {"feature": ""}, {}, None, objects, {"obj_9": "h1"})
    assert "#feature" not in empty, "ohne benanntes Merkmal bleibt der Schlüssel, wie er war"


def test_the_key_reads_the_up_to_target_and_the_sketch_plane() -> None:
    """Dieselbe Blindstelle zweimal: ``up_to`` und die Skizzenebene.

    ``sketch_extrude`` mit ``up_to`` liest die Höhe eines fremden Körpers
    (Quader 10 → 30 mm: die Extrusion blieb mit Cache bei z = 10), und jede
    ``sketch_*``-Op liest die Lage ihrer ``feature:<id>``-Ebene. Beide
    Träger gehören in den Kontext, jeder unter seinem eigenen Namen.
    """
    import dataclasses

    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.registry import REGISTRY
    from app.core.scene.evaluate import _with_nested_context
    from app.core.sketch.serialize import sketch_to_text
    from app.core.sketch.shapes import rectangle

    params_class = REGISTRY.get("sketch_extrude").params
    drawn = sketch_to_text(dataclasses.replace(rectangle(10.0, 10.0), plane="feature:face_p"))
    resolved = {"up_to": "face_t", "sketch": drawn}
    objects = {
        "obj_a": _face_carrier("obj_a", "face_t"),
        "obj_b": _face_carrier("obj_b", "face_p"),
    }

    base = _with_nested_context(
        params_class, resolved, {}, None, objects, {"obj_a": "t1", "obj_b": "p1"}
    )
    taller = _with_nested_context(
        params_class, resolved, {}, None, objects, {"obj_a": "t2", "obj_b": "p1"}
    )
    moved = _with_nested_context(
        params_class, resolved, {}, None, objects, {"obj_a": "t1", "obj_b": "p2"}
    )

    assert base["#up_to"] != taller["#up_to"], "wächst der Körper unter up_to, kippt der Schlüssel"
    assert base["#sketch.plane"] != moved["#sketch.plane"], (
        "wandert die Trägerfläche der Skizze, kippt der Schlüssel"
    )
    assert base["#up_to"] == moved["#up_to"], "und die zwei Träger bleiben getrennte Einträge"


class _RefusingCodec(FakeCodec):
    """Ein Codec, der diesen einen Körper nicht ablegen mag — wie der echte
    einen exakten Körper (§30)."""

    def stores(self, mesh: Mesh) -> bool:
        return False


def test_a_body_the_codec_will_not_store_is_no_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Der gewollte Fall darf nicht aussehen wie der ungewollte.

    ``put`` fing bis zum 27.08.2026 einen ``TypeError`` und schrieb
    ``could not write cache entry`` — für **zwei** Ursachen, die Gegenteiliges
    meinen: ein B-Rep-Ergebnis, das absichtlich neu gerechnet wird (§30), und
    ein Wert im Payload, den ``json.dumps`` nicht kennt. Der zweite ist ein
    Fehler und hat zweimal Tage gekostet, weil die Zeile im Protokoll dieselbe
    war. Im Kundenprotokoll vom 27.08.2026 (S-20260826-72a4dd) steht sie
    ebenfalls, hinter einem STEP-Import — dort war sie harmlos, und das sah man
    ihr nicht an.

    Seitdem fragt ``put`` vorher (``codec.stores``). Der gewollte Fall erreicht
    den Fehlerpfad nicht mehr, und die Warnung ist wieder eine.
    """
    disk = DiskCache(codec=_RefusingCodec(), directory=tmp_path)

    with caplog.at_level(logging.DEBUG, logger="app.core.scene.cache"):
        disk.put("key", CachedResult(objects=(make_object("obj_1", triangles=42),)))

    assert disk.get("key") is None, "abgelehnt heißt: nichts liegt da"
    warnungen = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert not warnungen, (
        "ein Körper, den der Codec bewusst nicht ablegt, ist Normalbetrieb — "
        f"keine Warnung: {[record.getMessage() for record in warnungen]}"
    )
    assert caplog.records, "und trotzdem nachlesbar, warum nichts gecacht wurde"


def test_a_payload_the_json_writer_cannot_take_stays_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Die Gegenprobe: Der **ungewollte** Fall bleibt eine Warnung.

    Sonst hätte die Trennung oben den Fehler mitgenommen, den sie sichtbar
    machen soll — ein Eintrag, der still wegfällt, während das Projekt bei
    jedem Öffnen den ganzen Stapel neu rechnet.
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    entry = make_object("obj_1", triangles=42)
    # Ein Wert, den ``json.dumps`` nicht kennt — dieselbe Sorte wie die zwei
    # ``TranslatableText`` von 23. und 26.08.2026, nur ohne deren Reparatur.
    broken = dataclasses.replace(entry, material=object())  # type: ignore[arg-type]

    with caplog.at_level(logging.DEBUG, logger="app.core.scene.cache"):
        disk.put("key", CachedResult(objects=(broken,)))

    assert disk.get("key") is None
    assert [record for record in caplog.records if record.levelno >= logging.WARNING], (
        "ein Payload, den der JSON-Schreiber nicht nimmt, ist ein Fehler und "
        "muss als Warnung stehen bleiben"
    )
