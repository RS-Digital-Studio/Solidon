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
3. **Baumweit über R:** jede Patch-Stelle mit ihren abgebildeten Zielen, keine neue unauflösbare
   Stelle (W5), die Lesermenge jedes gepatchten und jedes verschobenen Namens, die Kopfkopien
   und die Funde von W2 — vorher (abgebildet) gleich nachher.
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
from tools.move_cut import Cut
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
    check_readers(proof, trees, mapping)
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
