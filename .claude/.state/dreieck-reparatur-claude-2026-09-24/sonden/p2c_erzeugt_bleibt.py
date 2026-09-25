"""Sonde 2c: Ein erzeugtes Merkmal, das die Reparatur nicht berührt, behält Name, Herkunft und Erzeuger.

Würfel mit angesetztem Zapfen, der Zapfen per ``resize_feature`` geändert
(provenance ``generated``), daneben ein loses Kleinstteil. „Kleine Teile
entfernen“ ändert das Netz, lässt den Zapfen aber stehen. Danach nennt ein
weiterer Schritt den Zapfen.
"""

from __future__ import annotations

import os
import sys
import tempfile

_ISOLATED = tempfile.mkdtemp(prefix="solidon-sonde-")
for _variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
                  "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED
sys.path.insert(0, r"F:\3D Druck")

from pathlib import Path  # noqa: E402

import trimesh  # noqa: E402

from app.core.activation import store as activation_store  # noqa: E402

activation_store.DEMO_UNTIL = None
activation_store.TRIAL_FROM = activation_store.DEMO_FROM

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Fit, FeatureRef, Source  # noqa: E402

load_operations()
PROFILE = profiles.make_profile("centauri-carbon-2", "petg")
OUT = Path(__file__).with_suffix(".txt")


class Asked:
    def __init__(self) -> None:
        self.questions = []

    def __call__(self, question, choices):
        self.questions.append((question, list(choices)))
        return choices[0]


def show(out, title, project):
    asked = Asked()
    result = evaluate(project.document, PROFILE, sources=ProjectSources(project), ask=asked)
    out.write(f"\n# {title}: complete={result.complete} stopped_at={result.stopped_at}\n")
    for question, choices in asked.questions:
        out.write(f"  FRAGE {question!r} {choices}\n")
    for finding in result.scene.report.findings:
        if finding.severity != "info" or finding.code.startswith(("perceive", "repair")):
            out.write(f"  Befund {finding.severity} {finding.code} op={finding.op_id} "
                      f"{dict(finding.values) if finding.values else ''}\n")
    for name, feature in sorted(result.scene.objects["obj_1"].features.items()):
        if feature.kind in {"pin", "hole"}:
            out.write(f"  {name}: {feature.kind} d={float(feature.params['diameter']):.3f} "
                      f"prov={feature.provenance} by={feature.created_by} rec={feature.recognised} "
                      f"n={len(feature.face_indices)} src={dict(feature.measure_sources)}\n")
    out.flush()
    return result


def main() -> None:
    stock = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    pin = trimesh.creation.cylinder(radius=3.0, height=8.0, sections=48)
    pin.apply_translation((0.0, 0.0, 9.0))
    body = trimesh.boolean.union([stock, pin])
    crumb = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    crumb.apply_translation((30.0, 0.0, 0.0))
    payload = trimesh.util.concatenate([body, crumb]).export(file_type="stl")
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(id="src_1", kind="import",
                                               path="sources/probe.stl", sha256="")
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    with OUT.open("w", encoding="utf-8") as out:
        first = show(out, "geladen", project)
        pins = [n for n, f in first.scene.objects["obj_1"].features.items() if f.kind == "pin"]
        history.apply("Zapfen ändern", [OperationDraft(
            op="resize_feature", inputs=("obj_1",),
            params={"at_feature": pins[0], "diameter": 5.0}, seed=20260924)])
        second = show(out, "Zapfen geändert", project)
        project.document.fits.append(Fit(name="probe", a=FeatureRef("obj_1", pins[0]),
                                         b=FeatureRef("obj_1", pins[0]), kind="clearance",
                                         tolerance="auto:petg"))
        history.apply("Kleine Teile entfernen", [OperationDraft(
            op="repair", inputs=("obj_1",), params={"small_components": True})])
        show(out, "repariert (Kleinstteil weg)", project)
        history.apply("Zapfen noch einmal ändern", [OperationDraft(
            op="resize_feature", inputs=("obj_1",),
            params={"at_feature": pins[0], "diameter": 4.0}, seed=20260925)])
        show(out, "Zapfen danach geändert", project)


if __name__ == "__main__":
    main()
