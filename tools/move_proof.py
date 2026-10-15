"""Der Beweis des Verschiebewerkzeugs: alter und neuer Baum, verglichen gegen den Zuschnitt.

Plan Schritt 0, 2.7 Punkt 5, und Konzept Codestruktur 4.1: Jede Definition ist nach dem Schritt
``ast``-gleich mit ihrer Fassung davor, nachdem genau die erklärten Änderungen angewandt sind;
jede umgeschriebene Datei ebenso; Lesermengen (W2) und Registerabzug (W3) sind gleich. Der Beweis
bekommt zwei **Bäume** und den Zuschnitt, nicht die Umschreibtabelle des Planers — er prüft das
Ergebnis, nicht den Weg, und lässt sich deshalb an einem von Hand geschriebenen Sollbaum und
dessen Mutanten prüfen (``tests/test_move_proof.py``).

Geprüft wird in dieser Reihenfolge, jede Abweichung ist ein Eintrag in ``Proof.errors``:

1. **Dateien:** Was neu ist, entfällt oder sich ändert, folgt aus dem Zuschnitt; jede andere Datei
   ist byte-gleich. Eine geänderte Datei ohne erklärte Abweichung ist rot.
2. **Je Definition und Datei** der Strukturvergleich aus ``tools/move_compare.py``; je Modus die
   erklärten Abweichungen (Modulmodus hier, ``copies`` in ``tools/move_proof_copies.py``,
   Komponente in ``tools/move_proof_component.py``).
3. **Baumweit über R:** jede Patch-Stelle mit ihren abgebildeten Zielen (auch in unveränderten
   Dateien), keine neue unauflösbare Stelle (W5), keine Abfrage ``hasattr``/``getattr`` mit
   Vorgabe, die nachher still ins Leere fragt (R zählt sie nur), die Lesermenge jedes gepatchten
   und jedes verschobenen Namens — vorher (abgebildet) gleich nachher — und kein neuer Fund von
   W2 (Regeln a bis e, je Regel, Datei und abgebildetem Ziel; die Kopfkopien der Originale
   prüft dazu der Modus ``copies``).
4. **Registerabzug:** ``tools/registry_dump.py --out`` im alten und im neuen Baum, Byte für Byte.

Das Protokoll (``Proof.text()``) nennt je Definition, Datei, Patch-Stelle und Lesermenge, was
verglichen wurde; ``Proof.counts`` sind die Grundmengen, die nie leer sein dürfen.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from tools.code_index import Index, PatchSite
from tools.move_compare import module_of_expression
from tools.move_cut import Cut
from tools.move_forms import Calls, folded_names
from tools.move_proof_component import ComponentProof
from tools.move_proof_copies import CopiesProof
from tools.move_proof_module import ModuleProof
from tools.move_source import SourceError
from tools.move_trees import Mapping, Proof, Trees

__all__ = ["Mapping", "Proof", "Trees", "prove"]


def prove(
    cut: Cut,
    old_root: Path,
    new_root: Path,
    *,
    old_index: Index | None = None,
    new_index: Index | None = None,
    registry: bool = True,
    cache: bool = False,
) -> Proof:
    """Beweist den Schnitt ``cut`` zwischen den Bäumen ``old_root`` und ``new_root``."""
    proof = Proof(cut)
    old_index = old_index or Index.build(old_root, cache=cache)
    new_index = new_index or Index.build(new_root, cache=cache)
    trees = Trees(old_root, new_root, old_index, new_index)
    for path in trees.changed + trees.added:
        if not path.endswith(".py"):
            proof.error(
                f"{path}: keine Python-Datei, und doch geändert — der Schnitt ändert nur Code"
            )
    try:
        if cut.mode == "module":
            mapping: Mapping = ModuleProof(proof, trees, cut).run()
        elif cut.mode == "copies":
            mapping = CopiesProof(proof, trees, cut).run()
        else:
            mapping = ComponentProof(proof, trees, cut).run()
    except SourceError as error:
        proof.error(str(error))
        return proof
    check_patch_sites(proof, trees, mapping)
    check_unresolved(proof, trees, mapping)
    check_queries(proof, trees, mapping)
    check_readers(proof, trees, mapping)
    check_findings(proof, trees, mapping)
    if registry:
        check_registry(proof, trees)
    return proof


# --------------------------------------------------------------- baumweite Prüfungen über R


def check_patch_sites(proof: Proof, trees: Trees, mapping: Mapping) -> None:
    """Jede Patch-Stelle zielt nachher auf das abgebildete Ziel von vorher — auch in Dateien,
    die sich nicht geändert haben (ein vergessener Pfad als Text)."""
    old_by_file: dict[str, list[PatchSite]] = {}
    new_by_file: dict[str, list[PatchSite]] = {}
    for site in trees.old_index.patch_sites():
        old_by_file.setdefault(site.path, []).append(site)
    for site in trees.new_index.patch_sites():
        new_by_file.setdefault(site.path, []).append(site)
    for path in sorted(set(old_by_file) | set(new_by_file)):
        before = old_by_file.get(path, [])
        after = new_by_file.get(path, [])
        if len(before) != len(after):
            proof.error(f"{path}: {len(after)} Patch-Stellen statt {len(before)}")
            continue
        for old_site, new_site in zip(before, after, strict=True):
            proof.counts["patch_sites"] += 1
            mismatch = mapping.site_mismatch(old_site, new_site)
            if mismatch is not None:
                proof.error(f"{path}:{new_site.line}: Patch-Stelle {new_site.text!r} {mismatch}")
            elif old_site.text != new_site.text:
                proof.note(f"Patch {path}:{old_site.line}: {old_site.text} → {new_site.text}")


def check_unresolved(proof: Proof, trees: Trees, mapping: Mapping) -> None:
    """Kein Bezug wird unauflösbar (W5): jede unauflösbare Stelle nachher gab es vorher schon."""
    before = Counter(
        (u.path, u.kind, *mapping.ref(u.module, u.name)) for u in trees.old_index.unresolved()
    )
    after = Counter((u.path, u.kind, u.module, u.name) for u in trees.new_index.unresolved())
    for path, kind, module, name in sorted((after - before).elements()):
        proof.error(f"{path}: {kind}-Bezug {module}.{name} löst sich nachher nicht auf (W5)")


def check_queries(proof: Proof, trees: Trees, mapping: Mapping) -> None:
    """Kein Aufruf mit festem Attributnamen auf ein Modul fragt nachher ins Leere, der vorher
    (abgebildet) etwas fand: ``hasattr(M, "N")``, ``getattr(M, "N", vorgabe)``,
    ``setattr``/``delattr`` und jeder dieser Aufrufe über einen Alias (``has = hasattr``,
    ``builtins.hasattr``; Review 2, RM-M20). Eine Leere meldet der Auflöser nur für
    ``getattr(M, "N")`` ohne Vorgabe über den eingebauten Namen (W5); die übrigen sind nach dem
    Schnitt weder Bezug noch unauflösbar — einen Bezug nennt er nur, solange es den Namen gibt
    (CS-27). Der Beweis sucht sie deshalb selbst, über ``tools/move_forms.py`` und
    ``resolve``/``exists`` aus R, in jeder Datei beider Bäume."""
    every = _queries(trees, "new")
    proof.counts["queries"] = sum(len(sites) for sites in every.values())
    before = {
        key: sites
        for key, sites in _queries(trees, "old").items()
        if not trees.old_index.exists(*key)
    }
    after = {key: sites for key, sites in every.items() if not trees.new_index.exists(*key)}
    expected = Counter(
        mapping.ref(module, name) for (module, name), sites in before.items() for _ in sites
    )
    for key, sites in sorted(after.items()):
        if len(sites) <= expected[key]:
            continue
        for site in sites:
            proof.error(
                f"{site}: fragt {key[0]} nach {key[1]}, das es nachher nicht gibt (hasattr, "
                "getattr mit Vorgabe oder über einen Alias, setattr, delattr: die Antwort wäre "
                "still eine andere) — die Stelle auf das Modul umschreiben, das den Namen danach "
                "trägt"
            )


def _queries(trees: Trees, side: str) -> dict[tuple[str, str], list[str]]:
    """Je ``(M, N)`` die Stellen eines Baums mit Attributnamen auf ein Modul, deren Leere der
    Auflöser nicht als W5 meldet, deren erstes Argument laut R genau ein Modul ist; der Name
    auch gefaltet."""
    index = trees.old_index if side == "old" else trees.new_index
    files = trees.old_files if side == "old" else trees.new_files
    calls = Calls(index, files)
    found: dict[tuple[str, str], list[str]] = {}
    for path, data in files.items():
        if not path.endswith(".py") or not calls.may_call(data):
            continue
        source = trees.old(path) if side == "old" else trees.new(path)
        for named in calls.every(path, source.tree):
            reference = named.plain and named.kind == "getattr" and len(named.call.args) == 2
            if reference or named.call.keywords or len(named.call.args) > 3:
                continue
            module = module_of_expression(index, path, named.target)
            if module is None:
                continue
            for name in sorted(folded_names(index, path, named.name) or ()):
                found.setdefault((module, name), []).append(f"{path}:{named.call.lineno}")
    return found


def check_readers(proof: Proof, trees: Trees, mapping: Mapping) -> None:
    """Die Lesermenge jedes gepatchten Namens (W2, ``reach_dump``) und jedes verschobenen Namens:
    vorher (abgebildet) gleich nachher, je Name einzeln."""
    old_reach = trees.old_index.reach_dump()
    new_reach = trees.new_index.reach_dump()
    keys = set(old_reach) | set(mapping.keys())
    proof.counts["reach_keys"] = len(old_reach)
    for key in sorted(keys):
        expected = mapping.expected_readers(trees, key)
        if expected is None:
            expected = {
                ":".join(mapping.reader(*reader.split(":", 1)))
                for reader in _readers(trees.old_index, key)
            }
        new_key = mapping.reach_key(*key)
        actual = set(_readers(trees.new_index, new_key))
        if new_key in new_reach:
            actual = set(new_reach[new_key])
        if expected != actual:
            proof.error(
                f"Lesermenge {key[0]}.{key[1]} → {new_key[0]}.{new_key[1]}: fehlt "
                f"{sorted(expected - actual)}, neu {sorted(actual - expected)}"
            )
        else:
            proof.note(
                f"Leser {key[0]}.{key[1]} → {new_key[0]}.{new_key[1]}: {len(actual)} gleich"
                + (f" ({', '.join(sorted(actual))})" if actual else "")
            )
    for key in sorted(set(new_reach) - {mapping.reach_key(*k) for k in old_reach}):
        proof.error(f"{key[0]}.{key[1]}: nachher gepatcht, vorher nicht")


def check_findings(proof: Proof, trees: Trees, mapping: Mapping) -> None:
    """Kein neuer Fund von W2 (``patch_findings``, Regeln a bis e): Ein Patch-Ziel, das es
    nachher nicht gibt (a), ein ``raising=False`` (b), eine Kopfkopie eines gepatchten Namens (c),
    eine leere Lesermenge (d), ein unauflösbares Ziel (e). Verglichen wird je Regel, Datei und
    abgebildetem Ziel; bei c je gebundenem Namen, denn der Halter kann wandern. Weniger Funde sind
    erlaubt (der Modus ``copies`` beseitigt c-Funde)."""

    def keys(index: Index, mapped: bool) -> Counter[tuple[str, ...]]:
        found: Counter[tuple[str, ...]] = Counter()
        for rule, items in index.patch_findings().items():
            for item in items:
                if rule == "c":
                    found[("c", item.name)] += 1
                    continue
                target = (item.module, item.name)
                module, name = mapping.reach_key(*target) if mapped else target
                found[(rule, item.path, module, name)] += 1
        return found

    before = keys(trees.old_index, mapped=True)
    after = keys(trees.new_index, mapped=False)
    proof.counts["findings"] = sum(before.values())
    new = after - before
    for rule, items in trees.new_index.patch_findings().items():
        for item in items:
            key = ("c", item.name) if rule == "c" else (rule, item.path, item.module, item.name)
            if new[key] <= 0:
                continue
            new[key] -= 1
            proof.error(
                f"W2-Fund {rule} neu: {item.path}:{item.line} {item.module}.{item.name} "
                f"({item.detail}) — der Schnitt darf keinen Fund von W2 schaffen"
            )
    proof.note(
        f"W2-Funde vorher {sum(before.values())}, nachher {sum(after.values())} "
        f"({', '.join(f'{r}: {sum(v for k, v in after.items() if k[0] == r)}' for r in 'abcde')})"
    )


def _readers(index: Index, key: tuple[str, str]) -> list[str]:
    return sorted({f"{r.module}:{r.qualname}" for r in index.readers(*key)})


def check_registry(proof: Proof, trees: Trees) -> None:
    """``tools/registry_dump.py --out`` in beiden Bäumen, Byte für Byte (W3)."""
    script = Path("tools") / "registry_dump.py"
    if not (trees.old_root / script).is_file():
        proof.error(
            "tools/registry_dump.py fehlt im alten Baum — der Registerabzug (W3) gehört zum Beweis"
        )
        return
    before = _dump(trees.old_root, script, proof)
    after = _dump(trees.new_root, script, proof)
    if before is None or after is None:
        return
    proof.counts["registry_bytes"] = len(before)
    digest = hashlib.sha256(before).hexdigest()
    if before != after:
        old_lines = before.decode("utf-8", "replace").splitlines()
        new_lines = after.decode("utf-8", "replace").splitlines()
        first = next(
            (n for n, (a, b) in enumerate(zip(old_lines, new_lines, strict=False)) if a != b),
            min(len(old_lines), len(new_lines)),
        )
        proof.error(
            f"Registerabzug weicht ab ab Zeile {first + 1}: vorher "
            f"{old_lines[first] if first < len(old_lines) else '—'!r}, nachher "
            f"{new_lines[first] if first < len(new_lines) else '—'!r}"
        )
        return
    proof.note(f"Registerabzug byte-gleich: {len(before)} Byte, SHA-256 {digest}")


def _dump(root: Path, script: Path, proof: Proof) -> bytes | None:
    with tempfile.TemporaryDirectory(prefix="move-names-dump-") as folder:
        out = Path(folder) / "dump.txt"
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONUTF8"] = "1"
        environment.pop("PYTHONPATH", None)
        done = subprocess.run(
            [sys.executable, str(root / script), "--out", str(out)],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
        if done.returncode != 0 or not out.is_file():
            proof.error(
                f"Registerabzug in {root} endete mit {done.returncode}: "
                f"{(done.stderr or done.stdout).strip()[-400:]}"
            )
            return None
        return out.read_bytes()
