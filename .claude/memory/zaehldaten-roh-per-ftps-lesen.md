---
name: zaehldaten-roh-per-ftps-lesen
description: "Besucher-, Download- und Updatezahlen ohne das Passwort der Statistikseite: die Monatsdateien solidon3d.de/solidon-stats/*.jsonl lesend per FTPS holen und selbst auszählen."
metadata:
  node_type: memory
  type: reference
  originSessionId: 16858858-2f4c-42a6-ae4f-a846b5780d7d
  modified: 2026-09-25T11:08:24.794Z
---

Die Statistikseite (`api/stats.php`) sieht nur Robert; ihr Passwort kenne ich
nicht. Die Rohzeilen liegen daneben und sind über den Webserver-Zugang lesbar
(gemessen am 25.09.2026):

- Ort: `/solidon3d.de/solidon-stats/<JJJJ-MM>.jsonl` (UTC-Monat), außerhalb
  von `httpdocs`.
- Holen: `tools/upload_website.connect()` mit `.webserver.json`, `cwd`, `nlst`,
  `retrbinary` in **einer** Sitzung, Ziel Scratchpad. Nur lesen, nichts
  schreiben.
- Felder: `t` Zeit, `k` Art (`p` Seite, `d` Download, `u` Updateabfrage beim
  Programmstart), `v` Pfad/Paket/Version, `r` Referrer-Host, `u` Tageskennung
  des Besuchers (je Tag neu gesalzen, über Tage nicht verknüpfbar; bei `k=u`
  leer).
- Folge: Eindeutige Personen über mehrere Tage lassen sich nicht zählen, nur
  eindeutige je Tag. Updateabfragen sind Programmstarts, keine Nutzer.
- Der Zähler lässt DNT/GPC aus und begrenzt je Client und Minute — die Zahlen
  sind Untergrenzen.

Zusammenhang: [[statistikseite-lokal-vorschauen]] (die Seite selbst prüfen),
[[solidon3d-webserver-zugang]] (Anmeldung, eine Sitzung), Zahlenstand in
[[verkaufsphase-preise-und-demo-zahlen]].
