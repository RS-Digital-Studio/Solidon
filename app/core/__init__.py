"""Headless core: everything that computes, nothing that renders.

Hard rule (Bauplan §8, AGENTS.md rule 1): no Qt below ``app.ui``. This package
must stay importable on a machine without Qt installed; ``tests/test_core_isolation.py``
enforces it.

Communication with the outside world happens through ``OpContext`` only:
``ctx.progress``, ``ctx.ask``, ``ctx.cancelled``. No global objects, no dialogs.
"""
