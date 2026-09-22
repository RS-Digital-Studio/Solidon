"""Gegenprobe: andere ausdrückliche Zuordnung muss den Folgecache entwerten."""
from __future__ import annotations
import os
import sys
from pathlib import Path
from dataclasses import replace

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
isolated = Path(__file__).with_suffix('.userdata')
isolated.mkdir(exist_ok=True)
for name in ('APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME'):
    os.environ[name] = str(isolated)

import trimesh
from app.core.geom.mesh import MeshData
from app.core.knowledge.profiles import make_profile
from app.core.perceive.features import detect
from app.core.registry import Registry, op_params, param, register_op
from app.core.scene import History, OperationDraft, ResultCache, evaluate
from app.core.scene.project import new_project
from app.core.types import BaseParams, Feature, OpResult, SceneObject
from app.i18n import _

@op_params
class Empty(BaseParams):
    pass

@op_params
class Referenced(BaseParams):
    at_feature: str = param(title=_("Merkmal"), kind='feature')

meshes = []
for positions in (((0.0, -3.0), (0.0, 3.0)), ((-3.0, 0.0), (3.0, 0.0))):
    raw = trimesh.creation.box(extents=(80.0, 40.0, 8.0))
    raw.apply_translation((0, 0, 4))
    for x, y in positions:
        cutter = trimesh.creation.cylinder(radius=1.0, height=20.0, sections=32)
        cutter.apply_translation((x, y, 4))
        raw = trimesh.boolean.difference([raw, cutter])
    meshes.append(MeshData.of(raw))

calls = {'make': 0, 'change': 0, 'use': 0}
registry = Registry()

@register_op(name='cache_probe_make', title=_("Platte"), category='primitive', params=Empty,
             consumes=0, produces=1, registry=registry)
def make(ctx):
    calls['make'] += 1
    old = {f'before_{index}': Feature(f'before_{index}', 'hole', 'generated',
           {'centre': (0.0, y, 8.0), 'axis': (0.0, 0.0, 1.0), 'diameter': 2.0}, created_by=1)
           for index, y in enumerate((-3.0, 3.0), 1)}
    return OpResult(outputs=[SceneObject(id='', name='Platte', mesh=meshes[0], features=old)])

@register_op(name='cache_probe_change', title=_("Bohrungen"), category='prepare', params=Empty,
             consumes=1, produces=1, registry=registry)
def change(ctx):
    calls['change'] += 1
    return OpResult(outputs=[replace(ctx.inputs[0], mesh=meshes[1], features={})])

@register_op(name='cache_probe_use', title=_("Markierung"), category='scene', params=Referenced,
             consumes=1, produces=2, registry=registry)
def use(ctx):
    calls['use'] += 1
    source = ctx.inputs[0]
    x, y, z = source.features[ctx.params.at_feature].params['centre']
    marker = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    marker.apply_translation((x, y, z + 6))
    return OpResult(outputs=[source, SceneObject(id='', name='Markierung', mesh=MeshData.of(marker))])

project = new_project('centauri-carbon-2', 'petg')
history = History(project.document, registry=registry)
history.apply('Platte', [OperationDraft(op='cache_probe_make')])
history.apply('Bohrungen', [OperationDraft(op='cache_probe_change', inputs=('obj_1',))])
history.apply('Markierung', [OperationDraft(op='cache_probe_use', inputs=('obj_1',), params={'at_feature': 'before_1'})])
profile = make_profile('centauri-carbon-2', 'petg')
found = detect(meshes[1])
holes = sorted((float(feature.params['centre'][0]), name) for name, feature in found.items() if feature.kind == 'hole')
assert len(holes) == 2, holes
left, right = holes[0][1], holes[1][1]
cache = ResultCache()

class TracedCache(ResultCache):
    def __init__(self):
        super().__init__()
        self.access = []
    def get(self, key):
        result = super().get(key)
        self.access.append((key, result is not None))
        return result
cache = TracedCache()

def run(choice, selected_cache):
    asked = []
    def ask(question, choices):
        asked.append((question, choices))
        if len(asked) == 1:
            assert choice in choices, (choice, choices)
            return choice
        return next(candidate for candidate in choices if candidate in (left, right))
    result = evaluate(project.document, profile, registry=registry, cache=selected_cache, ask=ask)
    assert result.complete, [(f.code, str(f.message)) for f in result.scene.report.findings]
    assert asked, 'Die ausdrückliche Wahl muss tatsächlich erfolgt sein.'
    marker = next(body for body in result.scene.objects.values() if str(body.name) == 'Markierung')
    return result, float(marker.mesh.bounds.centre[0])

first, first_x = run(left, cache)
first_access = list(cache.access)
first_calls = dict(calls)
cache.access.clear()
second, second_x = run(right, cache)
second_access = list(cache.access)
second_calls = dict(calls)
reference, reference_x = run(right, ResultCache())
print('holes:', holes)
print('first marker x / right with warm cache / right with fresh cache:', first_x, second_x, reference_x)
print('calls after left:', first_calls, 'after warm right:', second_calls)
print('cache accesses left:', first_access)
print('cache accesses right:', second_access)
print('left output hashes:', first.object_hashes)
print('right output hashes:', second.object_hashes)
print('reserved IDs:', next(body for body in first.scene.objects.values() if str(body.name) == 'Platte').reserved_feature_ids, next(body for body in second.scene.objects.values() if str(body.name) == 'Platte').reserved_feature_ids)
print('saved decisions left:', first.matches)
print('saved decisions right:', second.matches)
assert first_x < -2.9 and reference_x > 2.9
assert second_x > 2.9, 'Andere bestätigte Gruppenantwort benutzt das linke Folgeergebnis aus dem Cache.'

