# Gebietsbericht: Infrastruktur und Vertrieb (Freischaltung, Update, Support, Fehler)

Testlauf des Gebiets grün (438 Tests) — keiner der Funde wird von einem Test gesehen. Skripte unter `review-infra\`.

## Hoch

### 1 [hoch] Ein einziger Start mit vorgestellter Uhr beendet Demo und Testlauf dauerhaft — VERIFIZIERT
`activation/store.py:196-205` (Testlauf), `:166-171` (Demo) — `effective = max(now, last_seen)` wird festgeschrieben, der Horizontwächter greift erst bei 365 Tagen Abstand. Alles darunter gilt als verstrichene Zeit, auch wenn die Uhr danach wieder stimmt. Gemessen: Start 25.08. → 67 Tage, Start mit Uhr 31.12. → 0, Uhr wieder richtig → 0 (Demo endgültig vorbei). Schlimmster Fall: leere BIOS-Batterie beim **ersten** Start — der Wächter klemmt nur `last_seen`, nie `first_run`. Ausweg (`trial.json` löschen) wird nirgends gesagt. Die vorhandenen Tests (`test_activation.py:311,324`) zementieren die Lücke. **Fix (Produktentscheidung Robert):** gezählte Nutzung statt Kalenderspanne (wie `feedback.py:209` mit monotoner Uhr) — „Zwei Schwellen, eine Frage", zwei Kalenderdaten können „Zeit vergangen?" und „Uhr falsch?" nicht trennen. Sofort und unabhängig: `first_run` denselben Plausibilitätswächter wie `last_seen`, und dem `LicenceRequired` einen Weg „Systemdatum prüfen" samt Markerpfad beilegen.

### 2 [hoch] Jede Absage der Gegenstelle kommt als „nicht erreichbar" an — der dafür gebaute Zweig ist tot — VERIFIZIERT
`support.py:376`, `:260-279` — `_post` ruft `urlopen` ohne `HTTPError`-Behandlung; jeder Status außer 200 wird zur Ausnahme → `SendFailed("Die Gegenstelle war nicht erreichbar.")`. `support.php:65-71` antwortet jeden Fehler mit eigenem Status (400/405/413/429/502); der Zweig `if not answer.get("ok")` ist gegen die echte Gegenstelle unerreichbar. Gemessen (lokales PHP): 502/429 → „nicht erreichbar", primärer Vorschlag *Noch einmal senden* — genau die Handlung, die die Sperre (12/Stunde/IP, trifft NAT schnell) verlängert. Zwilling der Lektion in `updates.py:434-445`. **Fix:** in `_post` `HTTPError` fangen, `read()`+`close()`, JSON-Körper wie normale Antwort zurückgeben; bei 429 `RETRY_SEND` nicht nach vorn.

## Mittel

### 3 [mittel] Frischer Rechner plus zurückgestellte Uhr: 2495 Tage Demo — VERIFIZIERT
`activation/store.py:152-175` — der Fix vom 25.08. (`c4692409`) deckt nur den Fall, dass schon ein Marker liegt. Ohne Marker schreibt `days_left` den falschen Tag als `first_run` fest. Gemessen: frischer Rechner Uhr 2020 → 2495 Tage; Marker gelöscht → 2495. Die Demo ist das ausgelieferte Produkt, ihr Stichtag hält nicht. **Fix:** `effective = max(now, last_seen, RELEASE_FLOOR)`, `RELEASE_FLOOR` beim Bau gesetzt (wie `MANIFEST_PUBLIC_KEY`).

### 4 [mittel] Datenschutzerklärung sagt „kein Kennzeichen"; die Startprüfung sendet `Solidon/0.1.5` — VERIFIZIERT
`updates.py:261` gegen `website/datenschutz.html:96-97` — der Text verspricht „kein Kennzeichen, keine Angaben über Ihren Rechner"; der Code seit `c4692409` sendet `User-Agent: Solidon/{APP_VERSION}` bei jedem Start, und die Anfrage wird mit dem Tageskennzeichen (IP+Salt) geloggt. „Texte altern mit ihrer Grenze" — die Datei wurde im Commit nicht angefasst. Rechtstext falsch vor dem Verkauf. **Fix:** `datenschutz.html` (handgepflegt) neu schreiben — Programmname+Version nennen, oder nur `Solidon` ohne Version senden.

### 5 [mittel] Beschädigte Installation: der zahlende Kunde liest „Testzeitraum abgelaufen" und soll kaufen — VERIFIZIERT
`activation/__init__.py:150-166` — `_determine()` gibt bei `not integrity.intact()` ein nacktes `Activation()` zurück, der gültige Schlüssel wird nicht gelesen. Ursachen ohne Angriff: Virenschutz-Quarantäne, abgebrochenes Update, Dateisystemfehler. In der Demo bleibt `deadline=None`, `over` falsch → Fenster startet, alles Schreibende zu, kein Abschiedsdialog. **Fix:** bei `not intact()` eigenen Fehler „Installation beschädigt" mit Wegen *Neu installieren*/`OPEN_DOWNLOAD_PAGE`/`REPORT_ERROR`.

### 6 [mittel] `remember()` umgeht die Manifestprüfung für die ganze Sitzung — VERIFIZIERT
`activation/__init__.py:196-200` — setzt `_cached = Activation(licence=licence)` direkt, ohne `integrity.intact()`. Nach dem erneuten Eintragen desselben Schlüssels läuft alles, `state()` gibt einen nie geprüften Zustand zurück. H4 einen Dialog weit von wirkungslos. **Fix:** in `remember()` denselben Wächter; bei `not intact()` Schlüssel ablegen, aber nicht freischalten.

### 7 [mittel] Ein Fehlerbericht, der sich nicht schreiben lässt, wirft einen nackten `OSError` aus dem Kern
`report.py:115-134` — `write()` ruft `ensure_dir`/`write_text`/`write_bytes` ohne Behandlung; Aufrufer `support_dialog.py:756-763` am Knopf ohne `try`. Das ist der Ausweg hinter gescheitertem Versand. `cli/main.py:718-727` macht es richtig, `errors.FileWriteError` existiert dafür. Zwilling: `discover.py:149-152` (`_store` schreibt `tools.json` ungeschützt). **Fix:** beide in `FileWriteError` mit `(RETRY, SAVE_ELSEWHERE, CANCEL)` umwandeln.

### 8 [mittel] Rückadressen, die der Client annimmt und PHP verwirft, verschwinden aus Reply-To — VERIFIZIERT
`support.py:94` (`^[^@\s]+@[^@\s.]+\.[^@\s]+$`) gegen `support.php:126,163` (`FILTER_VALIDATE_EMAIL`) — zwei Schwellen. Gemessen: `mueller@…` mit Umlaut, `a..b@…`, `.a@…` u. a. CLIENT-JA/PHP-NEIN. Der Kunde sieht „Rückantwort an: müller@…", der Server nimmt an, die Mail trägt kein `Reply-To` und „Rückadresse: keine" — Antwort geht an `noreply@`. **Fix:** in `support.php:163` bei ungültigem `$reply_to` den rohen `header_safe($contact)` in den Körper; `_ADDRESS` an dem ausrichten, was PHP annimmt.

## Gering
- **9** Nach 15 min Warten „Die Paketverwaltung ließ sich nicht starten" (`install.py:492-501`, `TimeoutExpired` in der Sammelklausel). Eigenen Grund + `by_hand()`.
- **10** Zwilling der Update-Fehlermeldung, der Kopie fehlen die Wege (`main_window.py:7514-7521` vs `updates.py:516-521`, erbt `INSTALL_MISSING` als ersten Weg). Dieselben zwei Wege setzen.
- **11** Der Regel-17-Wächter sieht 5 von 25 Fehlerklassen nicht (`test_errors.py:29-36`, `__subclasses__()` beim Import; `SendFailed`, `Backend*`, `GenerationFailed` fehlen). Vor dem Sammeln alle `app/core`-Module importieren.
- **12** `support.php` ist ein offenes Postfach, die Mail sagt nicht, woher sie kommt (`From: noreply@` besteht SPF/DKIM, beliebige Anhänge). Kopfzeile „aus dem öffentlichen Formular" + IP-Hash + User-Agent.

## Geprüft und in Ordnung
Ed25519 gegen RFC-8032-Vektoren (kleine Ordnung/`s>=L` verworfen); Schlüsselformat prüft Signatur vor Inhalt, jede Länge vor Verwendung; `integrity.py` deckt alles, was das Manifest deckt, Spec legt die vier Grenzdateien als Quelltext ab; `updates.py` verlangt Signatur/HTTPS/Rechnername/Prüfsumme vor Rückgabe, Start am Klick; `report.py` kennt kein `urlopen`; Support-Anhänge einzeln benannt, Modell nicht vorangehakt; `tour.py`/`examples.py` gegen das heutige Register; keine Platzhalter in Kernfehlertexten; keine Geheimnisse im Protokoll, Rotation 2 MB×5.

**Kann das so rein: nein** — Funde 1 und 2 treffen den ausgelieferten Stand unmittelbar (Uhr zerstört Demo/Testlauf; jede Server-Absage wird zur falschen Auskunft mit schädlichstem Vorschlag vorn).
