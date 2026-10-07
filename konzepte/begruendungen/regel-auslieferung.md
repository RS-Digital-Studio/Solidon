# Begründungen zu `.claude/rules/auslieferung.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

Warum es die Datei gibt: „Bis zum 14.09.2026 gab es diese Datei nicht; die
Regeln lagen in Karten, Erinnerungen und Commit-Meldungen verstreut
(RM-098)."

## Die Pflichtprüfungen geben das Paket frei

Zur Grenze von 100 Artefakten je Release-Lauf: „Am 25.09.2026 waren es rund
45".

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

## Was der Kunde bekommt, ist geprüft — und zwar die verteilte Menge

Der Fall, an dem sich die verteilte Menge von der geprüften unterschied: „(die
AppImage stand in keiner `version.json`)".
