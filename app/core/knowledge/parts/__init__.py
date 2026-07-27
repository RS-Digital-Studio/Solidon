"""The part library (Bauplan §24).

Licensed under MIT, unlike the rest of the application (see the LICENSE file in
this directory). The reason is in §36: the geometry these parts produce ends up
in the users' own models, so nothing here may raise a licence question for them.

Parts are built against ``manifold3d``, not OpenSCAD, so ``insert_part`` depends
on no external installation and stays testable.
"""
