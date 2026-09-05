---
name: php-lokal-fuer-die-gegenstelle
description: "PHP liegt per winget auf der Maschine (8.4 seit 20.08.2026, seit 05.09.2026 nur noch 8.5) — damit ist website/api/support.php prüfbar, aber mbstring braucht ein explizites extension_dir."
metadata: 
  node_type: memory
  type: project
  originSessionId: c72aa14e-a229-497c-b236-92f8dce4cd57
  modified: 2026-09-05T17:03:15.695Z
---

`website/api/support.php` ist der einzige Code des Projekts, der nicht in
Python läuft und nicht auf dieser Maschine. Er ging bis dahin ungeprüft per
FTPS auf den Server — ein Tippfehler wäre erst dem ersten Nutzer aufgefallen,
der etwas schickt.

Seit dem 20.08.2026 ist PHP da, seit dem 05.09.2026 als 8.5 (winget führt dort
8.5.8, php.net schon 8.5.10 — winget hinkt eine Handvoll Patches hinterher):

```
winget install --id PHP.PHP.8.5
```

**Nicht 8.3 nehmen** — winget kennt dort 8.3.32, und php.net hat die Datei
bereits abgeräumt (404 beim Download). Die neueren Reihen liegen im
`archives/`-Zweig und laden. Die ausführbare Datei landet unter
`%LOCALAPPDATA%\Microsoft\WinGet\Packages\PHP.PHP.8.5_*\php.exe`, und winget
trägt **das Paketverzeichnis** in den Benutzer-PATH ein — eine **schon
laufende Shell sieht es nicht**, `shutil.which("php")` gibt dort weiter
`None`. Zwei Reihen nebeneinander stehen im PATH in der Reihenfolge ihrer
Installation, die ältere gewinnt; `winget uninstall` der alten lässt ihren
PATH-Eintrag stehen (05.09.2026 von Hand entfernt).

**mbstring ist die eigentliche Falle.** Die Installation bringt keine
`php.ini` mit, also sucht PHP seine Erweiterungen unter dem einkompilierten
`C:\php\ext` — das es nicht gibt. `mb_substr` fehlt dann, und
`header_safe()`/`encode_subject()` sterben mit „undefined function". Der Weg
hinaus ist ein abgeleiteter Pfad, kein fester:

```
php -d extension_dir=<neben php.exe>\ext -d extension=mbstring …
```

Genau das macht `tests/test_support.py` seit `f309d1b`; ohne PHP überspringen
sich die beiden Tests, die CI merkt also nichts davon.

**Der ganze Weg lässt sich lokal durchspielen**, ohne die Produktion
anzufassen: `php -S 127.0.0.1:8123 -t website/api` als Gegenstelle,
`-d SMTP=127.0.0.1 -d smtp_port=2525` auf einen selbstgebauten
Socket-Fänger, und dann `app.core.support.send(ticket, url=…)` mit dem
echten Client. Was der Fänger schreibt, ist die fertige MIME-Mail — darin
sieht man die gefalteten Betreff-Wörter, die bereinigten Anhangsnamen und den
`Reply-To`. Der Fänger ist rund 60 Zeilen; er muss `EHLO`, `MAIL`, `RCPT`,
`DATA` und den Schlusspunkt beantworten, mehr nicht.

**Why:** Ohne PHP bleibt der Endpunkt eine Vermutung, und ein Nachbau in
Python prüft den Nachbau, nicht die Datei.

**How to apply:** Bei jeder Änderung an `support.php` erst `php -l`, dann
`pytest tests/test_support.py`. Vor dem Hochladen bleibt
`tools/check_support.py` die Probe gegen den echten Server — siehe
[[solidon3d-webserver-zugang]].
