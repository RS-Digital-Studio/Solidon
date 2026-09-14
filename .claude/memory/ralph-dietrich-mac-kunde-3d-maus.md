---
name: ralph-dietrich-mac-kunde-3d-maus
description: "Ralph W. Dietrich — Zahntechniker auf dem Mac, Anlass der 3D-Maus; sein Mac-Bericht vom 05.09.2026 ist die offene Feldbestätigung für Treiberweg und Update-Erkennung; am 14.09.2026 meldete er Windows 11 mit Smart App Control (Solidon startet nicht, Signatur fehlt)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 95e497f0-4c76-4675-bd77-72812e9a19e3
  modified: 2026-09-05T10:05:05.656Z
---

Ralph W. Dietrich (in Konzept und ROADMAP „R. W. D.") ist der Dentalkunde vom
30.08.2026, dessen Anfrage die SpaceMouse auslöste. Er arbeitet auf dem Mac,
hatte am 05.09.2026 noch Version 0.2.2 und meldete zu Roberts Mail vom
04.09.2026, dass die 3D-Maus nichts tut; sein Screenshot zeigt inzwischen eine
0.3.x-Fassung mit dem Merkmal-Panel (Kiefermodell mit Zapfen).

**Why:** Auf dem Mac hält 3DxWare das Gerät exklusiv, rohes HID bleibt leer;
seit dem 05.09.2026 liest `DriverReader` über das 3Dconnexion-Framework — am
Gerät ungemessen. Ob der Mac den Update-Hinweis auf 0.3.x je zeigte, ist ebenso
offen; das Paket 0.3.4 trägt das Zertifikatsbündel nachweislich.

**How to apply:** Seine nächste Rückmeldung ist die Messung für beides. Zu
erfragen: bewegt die Maus die Kamera nach Update auf die nächste Fassung, und
was steht in `~/Library/Logs/Solidon3D/app.log` hinter „update check did not
answer". Sein Kiefer-Scan zeigte außerdem 281 erfundene Rundformen im Objektbaum; seit
82d34278 (05.09.2026) lässt die Erkennung Kugel, Ring, Kegel und Verrundung auf
Freiformen weg und meldet es als Befund — Zapfen und Standfläche bleiben.
Kontaktdaten stehen in Roberts Mail, nicht hier. Verwandt:
[[alexander-schneider-kunde-und-mac-tester]].

**Nachtrag 14.09.2026 — er hat auch Windows 11.** Ralph meldete um 08:43, dass
Windows 11 seit dem aktuellen Update Solidon3D nicht startet, solange *Smart
App Control* eingeschaltet ist; er hat es ausgeschaltet („Systemeinstellung →
Smart App Control → Aus"). Der Grund ist RM-001: Das Windows-Setup ist nicht
signiert, und Smart App Control lässt nur signierte Anwendungen zu. Das
Abschalten ist ein Preis, den die Website seither nennt (es lässt sich ohne
Neuinstallation von Windows nicht wieder einschalten); die Antwort ist die
Windows-Signierung, nicht der Workaround. Dazu sein Hinweis auf den Defender,
der VLC beim Start ausbremst — nicht gemessen, nur gehört.
