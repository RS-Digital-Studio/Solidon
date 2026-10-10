"""Welche Funktionen der Erkennung fragen dasselbe mehrfach? Aufrufe gegen verschiedene Eingänge.

python wiederholt.py <baum> <fall> <funktion> [<funktion> ...]

Erkennung nach dem Schritt (wie tempo.py); je Funktion Aufrufe, verschiedene
Eingänge (Fleck als Bytes, übrige Argumente als repr) und CPU in der Funktion.
"""

from __future__ import annotations

import functools
import hashlib
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\sl-e\konzepte\nachweise-oertliche-erkennung-2026-10\messbank")
import _baum

TREE = _baum.setup(sys.argv[1])
_baum.activation_free()
CASE = sys.argv[2]
NAMES = sys.argv[3:]

import numpy as np  # noqa: E402

from app.core.perceive import features as F  # noqa: E402

calls: Counter[str] = Counter()
inputs: dict[str, set[bytes]] = defaultdict(set)
spent: Counter[str] = Counter()
active = [False]
depth = defaultdict(int)


def fingerprint(value) -> bytes:
    if (
        isinstance(value, (list, tuple))
        and value
        and all(isinstance(v, (int, np.integer)) for v in value[:5])
    ):
        return np.asarray(value, dtype=np.int64).tobytes()
    if isinstance(value, np.ndarray):
        return value.tobytes()
    if hasattr(value, "faces") and hasattr(value, "vertices"):
        return b"body%d" % id(value)
    return repr(value).encode()


def wrap(name: str) -> None:
    shipped = getattr(F, name)

    @functools.wraps(shipped)
    def watched(*args, **kwargs):
        if not active[0] or depth[name]:
            return shipped(*args, **kwargs)
        calls[name] += 1
        digest = hashlib.blake2b(digest_size=12)
        for value in args:
            digest.update(fingerprint(value))
        for key in sorted(kwargs):
            if key != "check_cancelled":
                digest.update(key.encode() + fingerprint(kwargs[key]))
        inputs[name].add(digest.digest())
        depth[name] += 1
        started = time.process_time()
        try:
            return shipped(*args, **kwargs)
        finally:
            spent[name] += time.process_time() - started
            depth[name] -= 1

    setattr(F, name, watched)


for name in NAMES:
    wrap(name)

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.cache import ResultCache  # noqa: E402
from app.core.scene.history import OperationDraft  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

load_operations()
SPOTS = {"staender": (-87.9, -6.8), "eiffel": (-34.2, 2.1)}
FILES = {
    "staender": _baum.KUNDE / "parametric-laptop-riser.stl",
    "eiffel": _baum.KUNDE
    / "埃菲尔铁塔（高18cm+、22cm、28cm）、一体无支撑"  # noqa: RUF001
    / "埃菲尔铁塔18cm_repariert.stl",
}
path = FILES[CASE]
payload = path.read_bytes()
project = new_project("centauri-carbon-2", "petg")
project.document.sources["src_1"] = Source(
    id="src_1", kind="import", path=f"sources/model{path.suffix.lower()}", sha256=""
)
project.sources["src_1"] = payload
plan = import_plan("src_1", path.name, payload, "mm", first_model=True)
history = History(project.document)
history.apply("Laden", [plan.draft])
profile = profiles.make_profile("centauri-carbon-2", "petg")
sources = ProjectSources(project)
cache = ResultCache()


def run():
    return evaluate(project.document, profile, sources=sources, ask=lambda q, c: c[0], cache=cache)


ids = list(run().scene.objects)
x, y = SPOTS[CASE]
history.apply(
    "Zylinder",
    [
        OperationDraft(
            op="create_cylinder",
            params={"diameter": 6.0, "height": 400.0, "z": -100.0, "x": x, "y": y},
        )
    ],
)
tool = [key for key in run().scene.objects if key not in ids][-1]
history.apply("Abziehen", [OperationDraft(op="subtract_objects", inputs=(ids[0], tool))])
active[0] = True
run()
for name in sorted(NAMES, key=lambda n: -spent[n]):
    print(
        f"{name:40s} Aufrufe {calls[name]:7d}  verschieden {len(inputs[name]):7d}  CPU {spent[name]:6.2f} s",
        flush=True,
    )
import os  # noqa: E402

os._exit(0)
