"""Nur die unabhängige Fernkoordinaten-Sonde und ihre Formschranke protokollieren."""
import runpy
import sys

def trace(frame, event, arg):
    if frame.f_code.co_name == '_torus_matches':
        if event == 'return':
            print({key: frame.f_locals.get(key) for key in ('bound', 'major', 'minor', 'denominator', 'remaining')})
        return trace
    return None

sys.settrace(trace)
namespace = runpy.run_path('tests/test_brep_surfaces.py')
namespace['test_ring_measures_follow_a_remote_oblique_native_axis'](True)
