---
name: rechnung-warnt-sie-erlaubt-nicht
description: "Eine Abhängigkeitsrechnung darf sagen, dass etwas fehlt, nie dass etwas weg darf — und eine Begründung wie „ist überall vorhanden\" ist keine Messung."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 979875fd-bfa8-4b06-9f26-64e50bc5303e
  modified: 2026-09-02T21:45:18.782Z
---

Am 02.09.2026 habe ich 64 Bibliotheken aus dem Linux-Paket geworfen, mit der
Begründung „Grundbestand jedes Linux mit Fenster". Zwanzig davon werden
gebraucht — `libQt6Core` hängt hart an `libglib-2.0`, `libQt6Network` an
`libzstd` und `libbrotlidec`, CPythons `_bz2` und `_lzma` an ihren
Bibliotheken. Ein solches Paket startet auf einem System ohne sie überhaupt
nicht. Der Bau läuft durch, die Suite kennt keine ELF-Kanten, `mypy` sieht
nichts: Der Fehler wäre erst beim Kunden aufgetaucht.

**Why:** Drei Fallen, jede für sich ausreichend.

1. **Die Begründung war nicht gemessen.** „Auf jedem Rechner vorhanden"
   klang plausibel und ist für zstd und brotli auf älteren Distributionen
   falsch. Maßstab ist die Ausschlussliste des AppImage-Projekts
   (`pkg2appimage/excludelist`) — die einzige erprobte Aussage darüber, was
   fehlen darf.
2. **Die erste Nachrechnung war selbst falsch.** Sie nahm alle Dateien als
   Wurzeln, auch die Systembibliotheken — dadurch hielten sich `libgtk-3` und
   `libgdk-3` gegenseitig am Leben, und die halbe GTK-Kette sah gebraucht aus.
   Wurzeln sind Anwendung, Module und Paketbibliotheken, nie das, worüber man
   gerade urteilt.
3. **Und die teuerste: Eine Rechnung taugt zur Warnung, nie zur Erlaubnis.**
   `libpython3.13.so.1.0` steht in derselben Rechnung als verwaist, weil
   PyInstaller sie über `dlopen` lädt und davon keine `DT_NEEDED`-Kante weiß.
   Wer die Liste ausrechnen ließe, würfe den Interpreter aus dem Paket.

**How to apply:** Was entfernt wird, wird **benannt** und begründet; die
Rechnung prüft nur die Gegenrichtung — bleibt eine Kante offen, ist es ein
Fehler. Beides als Test gegen einen eingecheckten Korpus
(`tests/data/linux/paket-0.2.1-abhaengigkeiten.json`, mit einem eigenen
ELF-Leser aus dem ausgelieferten Tarball gewonnen; auf Windows gibt es kein
`ldd`). Und die Gegenprobe fahren, statt sie zu behaupten: Mutation setzen,
rot sehen, zurückstellen — meine Behauptung „gegen den alten Stand ist er rot"
stand eine Stunde ungemessen im Commit.

Verwandt: [[messung-galt-fuer-den-stand-davor]], [[benannte-falle-schuetzt-nicht]],
[[pruefjob-nur-beim-tag-hat-nie-gemessen]] (auch dort: gebaut heißt nicht
gemessen), [[eigener-messfehler-widerlegt-den-befund-nicht]].
