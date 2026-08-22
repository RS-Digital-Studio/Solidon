---
name: website-upload-grosse-dateien
description: "FTPS zum netcup-Paket läuft mit ~1,8 MB/s und bricht bei mehreren großen Dateien am Stück ab — je Paket ein Aufruf."
metadata:
  type: project
---

`tools/upload_website.py` überträgt mit rund 1,8 MB/s; ein 280-MB-Paket
braucht gut zweieinhalb Minuten. Werden **mehrere große Dateien in einem
Aufruf** übergeben, hat der Server am 22.08.2026 mitten in der zweiten die
Verbindung zurückgesetzt (`ConnectionResetError 10054`) — zurück blieb eine
Datei mit 209 von 279 MB, und zwar unter richtigem Namen und richtiger Größe
für jeden, der nur die Dateiliste ansieht.

**Why:** Ein abgebrochener FTP-Upload hinterlässt kein Fragment mit Kennzeichen,
sondern eine Datei, die vollständig aussieht. Wer danach nicht die Größe gegen
die lokale prüft, veröffentlicht ein kaputtes Paket.

**How to apply:** Je Paket ein eigener Aufruf. Danach den Serverstand gegen die
lokalen Größen prüfen (`session.mlsd(f"/{root}/dl", facts=["type","size"])`),
und zum Schluss die verlinkten Dateien per HTTP-HEAD über
`https://solidon3d.de/dl/<name>` — beides fängt genau diesen Fall. Zugang und
Falle mit dem SSH-Schalter: [[solidon3d-webserver-zugang]].
