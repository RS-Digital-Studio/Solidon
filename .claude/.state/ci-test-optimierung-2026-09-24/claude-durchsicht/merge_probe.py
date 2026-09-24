import sys, dataclasses
sys.path.insert(0, r"F:\3D Druck")
import pytest
import tests.test_parts as t
spec = t.PARTS.all()[0]
calls = []
real = spec.fn
def fake(params):
    result = real(params)
    calls.append(1)
    if len(calls) == 1:
        return dataclasses.replace(result, features={})
    return dataclasses.replace(result, mesh=result.mesh.replacing(result.mesh.raw.copy().apply_scale(1.01)))
try:
    t.test_a_part_names_the_features_it_promised(dataclasses.replace(spec, fn=fake))
    print("GRÜN (schlecht)")
except AssertionError as error:
    text = str(error)
    print("rot, beide gemeldet:", "no features" in text and "volume" in text)
