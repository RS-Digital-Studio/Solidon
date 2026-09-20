"""S2: Je Baustein das deklarierte Schema, die Normteilbezüge und die Bauhelfer.

Liest ``PartSpec.params.__param_spec__`` für Eingaben, Grenzen, Einheiten und
Wahlmöglichkeiten; sucht im Quelltext der Bausteinfunktion nach Aufrufen von
``shapes.*``, ``build.*``, ``standards.*`` und ``geom.*``. Das ist die
Grundlage der Zuordnung „welcher exakte Bauweg für welche Konstruktion".
"""

from __future__ import annotations

import inspect
import re
import sys
from collections import Counter

import _iso  # noqa: F401

from app.core import bootstrap

bootstrap.load_operations()

from app.core.knowledge.parts.registry import PARTS  # noqa: E402

CALL = re.compile(
    r"\b(shapes|build|standards|lathe|boolean|transform|contours|edit|profiles)\.(\w+)\("
)
STD = re.compile(
    r"\b(STANDARD_\w+|HEATSET\w*|SCREWS?\w*|NUTS?\w*|MAGNETS?\w*|BEARINGS?\w*|standards\.\w+)"
)


def out(line: str) -> None:
    print(line)
    sys.stdout.flush()


def source_of(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        return inspect.getsource(fn)
    except OSError, TypeError:
        return ""


helpers_total: Counter[str] = Counter()
for spec in sorted(PARTS.all(), key=lambda s: (s.group, s.name)):
    out("=" * 100)
    out(f"{spec.name}  [{spec.group}]  v{spec.version}  Datei: {inspect.getsourcefile(spec.fn)}")
    out(f"  Titel: {spec.title}")
    out(f"  doc: {str(spec.doc)[:200]}")
    if spec.caveat:
        out(f"  caveat: {str(spec.caveat)[:200]}")
    out(f"  features: {spec.features}")
    requirements = [(r.name, r.when, r.equals, r.unless) for r in spec.feature_requirements]
    out(f"  feature_requirements: {requirements}")
    out(f"  wall: parameter={spec.wall.parameter} reason={spec.wall.reason} when={spec.wall.when}")
    out(
        f"  grip_from_profile={spec.grip_from_profile} feasible={'ja' if spec.feasible else 'nein'}"
    )
    out("  Parameter:")
    for p in spec.params.__param_spec__:  # type: ignore[attr-defined]
        rng = ""
        if p.minimum is not None or p.maximum is not None:
            rng = f" [{p.minimum}..{p.maximum}]"
        ch = f" choices={p.choices}" if p.choices else ""
        dep = f" depends_on={p.depends_on}" if p.depends_on else ""
        sub = f" subtractive_on={p.subtractive_on}" if p.subtractive_on else ""
        req = " PFLICHT" if p.required else ""
        unit = f" {p.unit}" if p.unit else ""
        out(
            f"    {p.name:20} {p.kind:8} default={p.default!r}{unit}{rng}{ch}{dep}{sub}{req} "
            f"({p.placement}) — {p.title}"
        )
    sources = [source_of(spec.fn)]
    for extra in (spec.host_cut, spec.host_add, spec.feasible):
        if extra is not None:
            sources.append(source_of(extra))
    text = "\n".join(sources)
    calls = Counter(f"{m.group(1)}.{m.group(2)}" for m in CALL.finditer(text))
    helpers_total.update(calls)
    out(f"  Bauhelfer: {dict(sorted(calls.items()))}")
    std = sorted({m.group(1) for m in STD.finditer(text)})
    out(f"  Normteile/Tabellen im Quelltext: {std}")
    # Weitere private Helfer derselben Datei, die der Baustein ruft
    private = sorted(set(re.findall(r"\b(_[a-z]\w+)\(", text)))
    out(f"  private Helfer: {private}")

out("")
out("Bauhelfer über alle Bausteine:")
for name, count in helpers_total.most_common():
    out(f"  {name:32} {count}")
