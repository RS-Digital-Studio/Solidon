---
name: php-lokal-fuer-die-gegenstelle
description: "PHP 8.4 liegt seit 20.08.2026 per winget auf der Maschine — damit ist website/api/support.php prüfbar, aber mbstring braucht ein explizites extension_dir."
metadata: 
  node_type: memory
  type: project
  originSessionId: c72aa14e-a229-497c-b236-92f8dce4cd57
  modified: 2026-08-20T13:51:26.358Z
---

`website/api/support.php` ist der einzige Code des Projekts, der nicht in
Python läuft und nicht auf dieser Maschine. Er ging bis dahin ungeprüft per
FTPS auf den Server — ein Tippfehler wäre erst dem ersten Nutzer aufgefallen,
der etwas schickt.

Seit dem 20.08.2026 ist PHP da:

```
winget install --id PHP.PHP.8.4
```

**Nicht 8.3 nehmen** — winget kennt dort 8.3.32, und php.net hat die Datei
bereits abgeräumt (404 beim Download). 8.4 liegt im `archives/`-Zweig und
lädt. Die ausführbare Datei landet unter
`%LOCALAPPDATA%\Microsoft\WinGet\Packages\PHP.PHP.8.4_*\php.exe` und kommt
über einen Alias in den PATH — eine **schon laufende Shell sieht ihn nicht**,
`shutil.which("php")` gibt dort weiter `None`.

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
