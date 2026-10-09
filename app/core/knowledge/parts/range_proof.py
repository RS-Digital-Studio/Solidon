"""Der Nachweis, dass jeder mitgelieferte Baustein über seinen Bereich geprüft ist (§24.3).

§24.3 sagt: „Ein Baustein ohne diesen Nachweis gilt als nicht abgenommen", und
die Website verspricht „jeder Baustein über seinen ganzen Maßbereich geprüft".
Bis zum 22.09.2026 stand dahinter nichts: Der Lauf über alle Bausteine war am
03.09.2026 aus der Suite gefallen, acht Bausteine waren nie gefahren worden,
und der Katalog unterdrückte die Warnung für mitgelieferte Bausteine mit der
Begründung, sie liefen „in der Suite" — sie liefen nirgends.

Seitdem gibt es den Nachweis als Datei: ``tools/check_part_ranges.py`` fährt
den Bereichstest (``range_check.check_part``) und schreibt je Baustein, womit
er gefahren wurde und was herauskam, nach ``data/part_ranges.toml``. Der
Katalog zeigt „über den ganzen Bereich geprüft" nur, wo dieser Eintrag zum
heutigen Stand des Bausteins passt; ein Test hält Datei und Bibliothek
zusammen, ohne neu zu rechnen.

**Was „derselbe Stand" heißt, sagt der Abdruck** (:func:`fingerprint`). Er
umfasst, was die Form eines Bausteins beschreibt und was die Prüfung an ihr
misst: die Datei, in der er steht, und die Bausteindateien, die sie
einbindet; die gemeinsamen Formen (``shapes``, ``build``, ``section``); die
Formmodule aus ``geom``, die eine dieser Dateien unmittelbar liest (Drehkörper,
Bewegungen, Konturen, Dichtweg); die Normteiltabelle; die Prüfung selbst
(``range_check``, ``geom.intersections``); sein Parameterschema samt Grenzen
und seine Deklaration; und das Materialprofil, mit dem gefahren wurde. Ändert
sich eines davon, passt der Nachweis nicht mehr, bis der Lauf wiederholt ist.

**Nicht darin steht der Netzkern darunter** — die Boolesche Rückfallkette
(``geom.boolean``) und die Netzhülle (``geom.mesh``). Jeder Baustein hängt an
beiden, und ein Abdruck, der sie enthielte, veraltete mit jeder Änderung am
Kern für alle fünfunddreißig zugleich. Den Kern prüfen seine eigenen Tests; den
Bausteinnachweis fährt der Release-Schritt ohnehin frisch
(``.claude/rules/auslieferung.md``).

Gefahren wird mit dem **Bezugsprofil** (:func:`reference_profile`, die Vorgabe
aus Drucker- und Materialtabelle), und daran misst auch der Katalog: Das
Material des gerade offenen Projekts ändert nicht, ob ein Baustein geprüft
ist. Zeilenenden zählen nicht: Der Abdruck liest jede Datei mit ``\\n``, damit
ein Klon unter Windows und einer unter Linux denselben Stand sehen.

**Im gebauten Paket gibt es die Quelldateien nicht** — sie liegen im Archiv
des Pakets. Dort vergleicht :func:`status` die Bausteinversion und die Zahl
der Ecken; den Abdruck hat das Release-Tor vor dem Bau geprüft, und nach dem
Bau ändert sich keine Datei mehr.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import inspect
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from app.core.knowledge.parts.registry import PartSpec
from app.core.types import Profile

#: Die Datei, die der Lauf schreibt und der Katalog liest.
PROOF_FILE: Final = Path(__file__).resolve().parent.parent / "data" / "part_ranges.toml"

_APP: Final = Path(__file__).resolve().parents[3]
_PARTS: Final = Path(__file__).resolve().parent

#: Die gemeinsamen Formen und die Prüfung — für jeden Baustein im Abdruck.
_SHARED: Final = (
    _PARTS / "shapes.py",
    _PARTS / "build.py",
    _PARTS / "section.py",
    _PARTS / "range_check.py",
    _APP / "core" / "geom" / "intersections.py",
    _APP / "core" / "knowledge" / "standards.py",
    _APP / "core" / "knowledge" / "data" / "standards.toml",
)

#: Module, die gelesen, aber nicht in den Abdruck genommen werden: der
#: Netzkern (siehe oben), die exakten Zwillinge — der Bereichstest rechnet am
#: Netz — und die Registerbuchhaltung, die keine Form trägt.
_NOT_SHAPE: Final = frozenset(
    {
        "app.core.geom.boolean",
        "app.core.geom.mesh",
        "app.core.knowledge.parts.exact",
        "app.core.knowledge.parts.registry",
        "app.core.knowledge.parts.ops",
        "app.core.knowledge.parts.range_proof",
    }
)

Status = Literal["proven", "stale", "failed", "missing"]


@dataclass(frozen=True, slots=True)
class ProofEntry:
    """Ein Eintrag des Nachweises: womit gefahren wurde und was herauskam."""

    name: str
    version: str
    fingerprint: str
    corners: int
    checked: int
    excluded: int
    failures: int
    passed: bool
    date: str


def _stamp(path: Path) -> tuple[int, int] | None:
    """Wann und wie groß — der Schlüssel der Merker; ``None`` ohne Datei."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


@functools.lru_cache(maxsize=128)
def _file_digest(path: Path, stamp: tuple[int, int]) -> str:
    """Der Inhalt einer Datei ohne Wagenrückläufe als Prüfsumme — je Stand einmal."""
    del stamp  # nur Schlüssel des Merkers
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@functools.lru_cache(maxsize=128)
def _imported_shapes(path: Path, stamp: tuple[int, int]) -> frozenset[Path]:
    """Die Form- und Bausteinmodule, die eine Datei unmittelbar einbindet."""
    del stamp  # nur Schlüssel des Merkers
    found: set[Path] = set()
    tree = ast.parse(path.read_bytes().decode("utf-8"))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
            names.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        for name in names:
            if name in _NOT_SHAPE or not name.startswith(
                ("app.core.geom.", "app.core.knowledge.parts.")
            ):
                continue
            candidate = _APP.parent / (name.replace(".", "/") + ".py")
            if candidate.is_file():
                found.add(candidate)
    return frozenset(found)


def _sources(spec: PartSpec) -> list[Path] | None:
    """Die Dateien, deren Inhalt den Stand dieses Bausteins ausmacht.

    ``None``, wenn sie nicht als Dateien vorliegen — im gebauten Paket.
    """
    source = inspect.getsourcefile(spec.fn)
    if source is None:
        return None
    own = Path(source).resolve()
    files = {own, *_SHARED}
    for base in (own, _PARTS / "shapes.py", _PARTS / "build.py", _PARTS / "section.py"):
        stamp = _stamp(base)
        if stamp is None:
            return None
        files |= _imported_shapes(base, stamp)
    return sorted(files, key=lambda item: item.as_posix())


def _declaration(spec: PartSpec) -> dict[str, object]:
    """Was der Baustein über sich erklärt und der Bereichstest liest."""
    return {
        "name": spec.name,
        "version": spec.version,
        "bodies": spec.bodies,
        "joined_by_host": spec.joined_by_host,
        "wall": [spec.wall.parameter, spec.wall.reason, spec.wall.when, repr(spec.wall.equals)],
        "features": [
            [entry.name, entry.when, repr(entry.equals), entry.unless, repr(entry.unless_equals)]
            for entry in spec.feature_requirements
        ],
        "feasible": spec.feasible is not None,
        "mirrored_by": spec.mirrored_by,
        "params": [
            [
                entry.name,
                entry.kind,
                repr(entry.minimum),
                repr(entry.maximum),
                repr(entry.default),
                list(entry.choices or ()),
            ]
            for entry in spec.params.spec()
        ],
    }


def _profile(profile: Profile) -> dict[str, object]:
    """Die Zahlen des Profils, die der Bereichstest benutzt."""
    return {
        "clearance": repr(profile.material.clearance),
        "press": repr(profile.material.press),
        "minimum_wall": repr(profile.minimum_wall_thickness),
    }


def reference_profile() -> Profile:
    """Das Profil, mit dem der Nachweis gefahren wird: die Vorgabe der Tabellen."""
    from app.core.knowledge.profiles import make_profile

    return make_profile()


def fingerprint(spec: PartSpec, profile: Profile) -> str | None:
    """Der Abdruck eines Bausteins — ändert er sich, passt der Nachweis nicht mehr.

    ``None``, wo die Quelldateien nicht lesbar sind (gebautes Paket).
    """
    sources = _sources(spec)
    if sources is None:
        return None
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            {"part": _declaration(spec), "profile": _profile(profile)},
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    )
    for path in sources:
        stamp = _stamp(path)
        if stamp is None:
            return None
        digest.update(path.relative_to(_APP.parent).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(_file_digest(path, stamp).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def load(path: Path = PROOF_FILE) -> dict[str, ProofEntry]:
    """Der eingecheckte Nachweis, je Baustein ein Eintrag; ohne Datei leer."""
    stamp = _stamp(path)
    return dict(_loaded(path, stamp)) if stamp is not None else {}


@functools.lru_cache(maxsize=4)
def _loaded(path: Path, stamp: tuple[int, int]) -> tuple[tuple[str, ProofEntry], ...]:
    del stamp  # nur Schlüssel des Merkers
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    entries: list[tuple[str, ProofEntry]] = []
    for item in data.get("parts", []):
        entry = ProofEntry(
            name=str(item["name"]),
            version=str(item["version"]),
            fingerprint=str(item["fingerprint"]),
            corners=int(item["corners"]),
            checked=int(item["checked"]),
            excluded=int(item["excluded"]),
            failures=int(item["failures"]),
            passed=bool(item["passed"]),
            date=str(item["date"]),
        )
        entries.append((entry.name, entry))
    return tuple(entries)


def status(
    spec: PartSpec,
    profile: Profile | None = None,
    proofs: dict[str, ProofEntry] | None = None,
) -> Status:
    """Ob der Nachweis zum heutigen Stand dieses Bausteins passt.

    ``proven`` verlangt dreierlei: denselben Stand, alle Ecken gefahren und
    keine gebrochene. ``failed`` ist ein Lauf zum heutigen Stand, der eine Ecke
    nicht hielt; ``stale`` ein Lauf zu einem früheren Stand; ``missing`` gar
    keiner. Ohne Profil gilt das Bezugsprofil, mit dem das Werkzeug fährt.
    """
    from app.core.knowledge.parts.range_check import part_corner_count

    entry = (proofs if proofs is not None else load()).get(spec.name)
    if entry is None:
        return "missing"
    current = fingerprint(spec, profile if profile is not None else reference_profile())
    if current is not None and entry.fingerprint != current:
        return "stale"
    corners = part_corner_count(spec)
    if current is None and (entry.version != spec.version or entry.corners != corners):
        return "stale"
    if not entry.passed or entry.failures or entry.checked != corners:
        return "failed"
    return "proven"


def render(entries: dict[str, ProofEntry], profile: Profile) -> str:
    """Die Nachweisdatei als TOML, nach Namen sortiert — derselbe Stand, derselbe Text."""
    lines = [
        "# Bereichsnachweis der mitgelieferten Bausteine (Bauplan §24.3).",
        "#",
        "# Erzeugt von tools/check_part_ranges.py — nicht von Hand bearbeiten. Der",
        "# Abdruck (fingerprint) sagt, gegen welchen Stand gefahren wurde; passt er",
        "# nicht mehr, zeigt der Katalog die Warnung, und",
        "# tests/test_parts.py::test_every_shipped_part_carries_a_current_range_proof",
        "# wird rot, bis das Werkzeug erneut lief.",
        "#",
        f"# Materialprofil: Spiel {profile.material.clearance} mm, Übermaß "
        f"{profile.material.press} mm, Mindestwand {profile.minimum_wall_thickness} mm.",
    ]
    for name in sorted(entries):
        entry = entries[name]
        lines.extend(
            [
                "",
                "[[parts]]",
                f'name = "{entry.name}"',
                f'version = "{entry.version}"',
                f'fingerprint = "{entry.fingerprint}"',
                f"corners = {entry.corners}",
                f"checked = {entry.checked}",
                f"excluded = {entry.excluded}",
                f"failures = {entry.failures}",
                f"passed = {'true' if entry.passed else 'false'}",
                f'date = "{entry.date}"',
            ]
        )
    return "\n".join(lines) + "\n"
