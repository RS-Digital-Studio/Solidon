# `app/core/activation/` — Freischaltung

Testlauf, Lizenzschlüssel, Demo-Frist — und wo die Grenze verläuft.

## Die Karte

| Datei | Rolle |
|---|---|
| `__init__.py` | Die Grenze selbst: was ohne Schlüssel geht und was nicht |
| `key.py` | Das Format des Lizenzschlüssels: lesen, prüfen, zerlegen |
| `ed25519.py` | Signaturprüfung nach RFC 8032, **in reinem Python** |
| `store.py` | Wo der Schlüssel liegt und wie der Testlauf gezählt wird (§38) |
| `integrity.py` | Das signierte Manifest über die eigene Auslieferung |

## Warum Ed25519 von Hand

Damit die Prüfung an keiner Krypto-Bibliothek hängt, die im gebauten Paket
fehlen oder eine Lizenzfrage aufwerfen könnte. Es ist wenig Code, er ist
nachlesbar, und er tut nur das eine.

## Öffentlich und privat

Der **öffentliche** Schlüssel steht im Quelltext — er muss dort stehen, sonst
kann niemand prüfen. Der **private** liegt nicht im Repository und wird nie
committet; `tools/make_licence_keys.py` erzeugt die Paare.

## Das Lizenzmanifest ist ein Artefakt je Arbeitsbaum

`tools/build_licence_module.py` baut das Prüfmodul aus den Grenzdateien. Es
ist **gitignoriert** — ändert sich eine der Grenzdateien, wird
`tests/test_packaging.py` rot, und die Antwort ist ein neuer Bau, kein
Löschen. Die CI überspringt diesen Test.

## Grenzen

- Nichts hier zeigt einen Dialog. Der Kern meldet, die Oberfläche fragt.
- Eine abgelaufene Frist ist kein Absturz, sondern ein Zustand mit Weg nach
  vorn (Regel 17).
