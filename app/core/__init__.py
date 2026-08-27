"""Der kopflose Kern: alles, was rechnet, nichts, was zeichnet.

Harte Regel (Bauplan §8, AGENTS.md Regel 1): kein Qt unterhalb von ``app.ui``.
Dieses Paket muss auf einem Rechner ohne installiertes Qt importierbar
bleiben; ``tests/test_core_isolation.py`` erzwingt das.

Kommunikation nach außen läuft ausschließlich über den ``OpContext``:
``ctx.progress``, ``ctx.ask``, ``ctx.cancelled``. Keine globalen Objekte,
keine Dialoge.
"""
