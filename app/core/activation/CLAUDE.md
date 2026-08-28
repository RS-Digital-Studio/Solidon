# `app/core/activation/` — Freischaltung

Lizenzschlüssel, Gerätefreigabe, Demo-Frist — und wo die Grenze verläuft.

## Die Karte

| Datei | Rolle |
|---|---|
| `__init__.py` | Die Grenze selbst: was ohne vollständige Freischaltung geht und was nicht |
| `key.py` | Das Format des Lizenzschlüssels: lesen, prüfen, zerlegen |
| `ed25519.py` | Signieren und Prüfen nach RFC 8032, **in reinem Python** |
| `device.py` | Das Geräte-Schlüsselpaar im Schlüsselbund des Betriebssystems |
| `certificate.py` | Signierte Anforderung, Antwort und Abmeldung für Online- und Dateiweg |
| `store.py` | Wo Schlüssel und Zertifikat liegen und wie befristete Angebote gezählt werden (§38) |
| `integrity.py` | Das signierte Manifest über die eigene Auslieferung |

## Warum Ed25519 von Hand

Damit die Signaturen an keiner Krypto-Bibliothek hängen, die im gebauten Paket
fehlen oder eine Lizenzfrage aufwerfen könnte. Es ist wenig Code und er ist
gegen die RFC-Vektoren geprüft. Der private Geräteteil liegt trotzdem nicht in
einer Datei, sondern ausschließlich im System-Schlüsselbund.

## Öffentlich und privat

Die **öffentlichen** Schlüssel der Kaufcode- und Aktivierungsaussteller stehen
im Quelltext — sie müssen dort stehen, sonst kann die Anwendung nichts prüfen.
Die **privaten** Teile liegen weder im Repository noch beim Kunden. Es sind
getrennte Paare: `tools/make_licence_keys.py` erzeugt Kaufcodes,
`tools/setup_activation_server.py` richtet den Aktivierungsdienst ein.

Ein ab dem 01.11.2026 ausgestellter Verkaufscode allein schaltet nichts frei.
Erst ein vom Dienst signiertes und an den privaten Geräteteil gebundenes
Zertifikat öffnet die vier Grenzen. Bereits ausgegebene Bestandsschlüssel vor
diesem Stichtag bleiben ohne nachträgliche Gerätebindung gültig. Das Zertifikat
hat kein Ablaufdatum: Nach dem ausdrücklichen Aktivierungsklick bleibt die
Anwendung ohne Konto, Hintergrundprüfung und Netz verwendbar.

## Das Lizenzmanifest ist ein Artefakt je Arbeitsbaum

`tools/build_licence_module.py` baut das Prüfmodul aus den Grenzdateien. Es
ist **gitignoriert** — ändert sich eine der Grenzdateien, wird
`tests/test_packaging.py` rot, und die Antwort ist ein neuer Bau, kein
Löschen. Die CI überspringt diesen Test.

## Grenzen

- Nichts hier zeigt einen Dialog. Der Kern meldet, die Oberfläche fragt.
- Der Netzweg liegt in `app/core/licence_service.py` und wird nur nach einem
  ausdrücklichen Klick geladen; der Dateiweg benutzt dieselben Dokumente.
- Eine abgelaufene Frist ist kein Absturz, sondern ein Zustand mit Weg nach
  vorn (Regel 17).
