"""Application root package.

Layering rule (Bauplan §8): ``app.core`` never imports from ``app.ui``.
``app.ui`` and ``app.cli`` are entry points on top of the core.
"""
