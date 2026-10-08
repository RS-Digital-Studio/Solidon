# Begründungen zu `.claude/rules/auslieferung.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

Warum es die Datei gibt: „Bis zum 14.09.2026 gab es diese Datei nicht; die
Regeln lagen in Karten, Erinnerungen und Commit-Meldungen verstreut
(RM-098)."

## Die Pflichtprüfungen geben das Paket frei

Warum über alle Seiten gelesen wird: GitHub gibt eine Liste höchstens zu 100
Einträgen je Seite heraus, und ein Taglauf hatte mit 0.5.3 schon 31 Artefakte;
jede Plattform, die der Vertrag der CI dazunimmt, bringt weitere. Wer nur die
erste Seite liest, fände das Signierarchiv auf der zweiten nie.

Warum der Job „Neueste Versionen“ nur meldet (RM-350): Am Tag v0.5.3 wurde er
rot (`cadquery-ocp-novtk 8.0.1.1.0` ohne festgeschriebenen Lizenztext), der
Taglauf endete auf „failure“, und `sign_release.verify_ci_run` verlangte
`success` — das Windows-Setup ließ sich für diesen Tag nicht signieren, obwohl
Kern, Fenster und Pakete grün waren. Seither `continue-on-error` am Job
(`81303aaab`) und `ADVISORY_JOBS` in der Signierung (`6e16a2cef`).

## Jedes Kundenpaket startet bei jedem Release einmal

Der Anlass, aus der Regel verschoben (RM-505): 0.5.1 bestand Suite, Bau,
Signatur und Notarisierung und beendete sich auf jedem Mac nach 20 bis 40
Sekunden — kein Schritt hatte das ausgelieferte Programm je gestartet.

Warum SIP zählt (RM-104, 06.10.2026): `csrutil status` meldet auf
`macos-26-intel` und `macos-latest` „disabled“ (Lauf 37488283777). Gemessen
ist dort auch, dass beide Schutzwege der Hardened Runtime nicht greifen: Ein
ctypes- und cffi-Rückruf ohne Berechtigung lief am 05.10. auf dem Intel-Runner
durch, und am 06.10. startete eine ad hoc mit Hardened Runtime signierte App
mit ad hoc signierten Bibliotheken (Lauf 37490502237) — auf einem Kunden-Mac
lehnt die Bibliotheksprüfung Bibliotheken ohne Team-ID ab. Dass SIP der Grund
ist, ist gefolgert, nicht gemessen. Auf den Intel-Macs eines Kunden (macOS 26,
zu Hause 26.5) hing derselbe Stand vor dem ersten Fenster. Fremde Berichte
vom selben Fehlerbild auf echten Intel-Macs mit macOS 26:
<https://github.com/andreagrandi/draftomen/issues/905> (26.7.1) und
<https://github.com/PeonPing/peon-ping/issues/589> (Apples eigenes
`osascript`, 26.6.2, Stapel `ffi_closure_alloc` → `dlmmap` →
`open_temp_exec_file_dir`).

Verlangt war bis 0.5.3 ein leeres Absturzprotokoll. faulthandler schreibt aber
auch Windows-Ausnahmen, die das System selbst abfängt (COM `0x8001010d`,
Fragebogen S-20261006-5be329); seitdem zählt nur, was `log.fatal_records` als
tödlich ausweist. Eine Ausnahme, die der Hauptfaden überlebt hat, hält den
Starttest damit nicht mehr an; eine aus einem Treiberfaden ohne Python-Zustand
nennt faulthandler keinem Faden zu, und sie zählt weiter als Absturz.

## Die Version wird vor dem Bau erhöht, und nur über das Werkzeug

Warum ein nie veröffentlichter Fehler nicht in den Changelog gehört: „— der
Kunde suchte ihn sonst bei sich."

## Kein Release ohne frischen Bausteinnachweis

> Seit dem 22.09.2026 dauert der Lauf mit vier Prozessen Minuten statt der
> halben Stunde, die ihn am 03.09.2026 aus der Suite nahm.

## Keine Abhängigkeit ohne Lizenz, keine Lizenz ohne Nachweis am Artefakt

Warum die Stückliste aus dem Kundenartefakt kommt: „Eine SBOM aus der
Entwicklungsumgebung ist eine Vorschau."

## Signieren ist ein eigener Vertrauensraum

Warum genau diese eine Berechtigung (RM-104): CPython legt seit
<https://github.com/python/cpython/issues/128485> beim Laden von `_ctypes`
eine Closure an und gibt sie wieder frei (`_ctypes_mod_exec` →
`Py_ffi_closure_alloc`, 3.14), und PyInstallers Bootstrap lädt ctypes vor den
Laufzeithaken und dem Einstiegsskript (`pyiboot01_bootstrap` →
`pyimod03_ctypes.install`, 6.22.3) — ein Hänger dort hinterlässt weder
Absturzdatei noch Protokoll. Umgehen lässt sich ctypes nicht: Bootstrap,
`app/core/process.py` und numpy laden es. libffis `dlmmap` holt anonymen Speicher
mit `PROT_EXEC` und ohne `MAP_JIT`; scheitert das mit EPERM, weicht es auf
Temp-Dateien aus, und dieser Weg kreist. `allow-jit` erlaubt nur `MAP_JIT` und
hülfe nicht; `disable-library-validation` braucht der Developer-ID-Bau nicht,
alle Bibliotheken tragen dieselbe Team-ID. ARM nimmt Apples Trampolintabelle.
Gefahren am 06.10.2026 mit dem wörtlich aus `build.yml` geschnittenen
Signierteil, ad hoc statt Developer ID, am veröffentlichten 0.5.3: Liste am
Hauptprogramm, keine an `Python.framework` und `_cffi_backend` (Lauf
37490502237); in der heutigen Fassung `--verify --deep --strict` grün, Start
auf Intel und ARM, und der geschnittene Rücklesetext bricht ohne Liste und bei
`<false/>` ab und lässt die Liste durch (Lauf 37530339300). Developer-ID-
Zeitstempel und Notarisierung mit der Liste sind im Handstart von
`build.yml` belegt (Lauf 37530876754, beide Architekturen grün), die Wirkung
belegt erst ein echter Intel-Mac mit macOS 26.

## Was der Kunde bekommt, ist geprüft — und zwar die verteilte Menge

Der Fall, an dem sich die verteilte Menge von der geprüften unterschied: „(die
AppImage stand in keiner `version.json`)".
