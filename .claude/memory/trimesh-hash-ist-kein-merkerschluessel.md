---
name: trimesh-hash-ist-kein-merkerschluessel
description: "hash(trimesh) rechnet bei jedem Aufruf über die Daten — 0,44 ms an 200 000 Dreiecken, und ein Merker fragt tausendfach; Schlüssel ist id() mit weakref, und je Frage ein eigener Merker mit eigener Größe, sonst verdrängt eine häufige Frage die Antwort auf eine seltene zwischen ihren zwei Lesern"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-21T19:30:00.000Z
---

Gemessen am 21.09.2026 an der Merkmalserkennung (`_remembered` in
`app/core/perceive/features.py`): Der Merker je Netz und Fleck nahm
`hash(body)` als Schlüssel. trimesh hält den Hash nicht — es rechnet ihn bei
jedem Aufruf über Ecken und Dreiecke neu, 0,44 ms an der Lochplatte mit
204 000 Dreiecken. Bei einigen tausend Fragen je Erkennung war der
Schlüssel teurer als manche Antwort. Jetzt `id(body)` plus ein `weakref`, das
beim Lesen mit dem Körper verglichen wird; der Leser hält den Körper ohnehin,
und ein neuer Körper unter alter Adresse fällt am Weakref durch.

Die zweite Falle im selben Merker: ein LRU von 64 über alle Fragen hinweg.
`_a_sliver` fragte 218-mal zwischen den zwei Lesern von `_facets_standing_apart`
— und verdrängte deren Antwort, also rechnete die zweite Lesung neu. Je Frage
ein eigenes OrderedDict mit passender Grenze (die Stützpunktlesung hält acht,
weil ihre Felder so groß sind wie der Fleck, alles andere viertausend).

**Why:** Ein Merker ist nur so billig wie sein Schlüssel, und ein gemeinsamer
Merker für Fragen verschiedener Häufigkeit misst die falsche Frage: Die
Trefferquote sah gut aus, weil die häufige Frage traf — die teure Frage traf nie.

**How to apply:** Vor dem Merken den Schlüssel messen (`hash` an einem
Objekt, das keinen hält, ist eine Rechnung). Trefferquote je Frage zählen,
nicht insgesamt. Siehe [[lineares-sieb-vor-der-verfeinerung-ist-unsicher]]
für das, was am selben Tag nicht half.
