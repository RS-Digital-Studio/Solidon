---
name: signal-passt-an-den-falschen-slot
description: "Qt verbindet jedes Signal, dessen Stelligkeit zum Slot passt — ein str-Signal an einem str-Slot mit anderer Bedeutung läuft fehlerfrei falsch, und kein Test mit Attrappen sieht es."
metadata:
  node_type: memory
  type: feedback
---

**`dialog.saved.connect(catalog.show_parts)`** — eine Zeile, kein Fehler, kein
Warnhinweis. `saved` ist `Signal(str)` und trägt den **Namen** des
gespeicherten Rezepts; `show_parts(text: str = "")` nimmt einen **Suchtext**.
Beides ist ein `str`, Qt verbindet es, und der Katalog zeigte nach dem
Speichern nur noch den neuen Baustein — bei leerem Suchfeld, sodass der Kunde
nicht einmal sehen konnte, *warum*. Gefunden am 25.08.2026 nur deshalb, weil
die Verifikation im echten Fenster das Bildschirmfoto der Station ansah
(Commit abb074b).

**Why:** Der Typ prüft die Form, nicht die Bedeutung. Ein Signal-Argument,
das zufällig zur Signatur des Slots passt, ist die stillste Art der
Fehlverdrahtung: nichts wirft, nichts loggt, und ein Test, der den Empfänger
mockt, bestätigt nur, *dass* verbunden wurde. Die Wirkung sieht erst, wer die
Oberfläche danach wirklich ansieht.

**How to apply:** Beim `connect` nicht fragen „passt die Signatur?", sondern
„was *bedeutet* das Argument beim Empfänger?". Im Zweifel einen Slot ohne
Parameter anbieten (wie `PartCatalog.refresh()`), der nichts missverstehen
kann. Und bei der Prüfung: nach jeder Station der Bedienung das Ergebnis
**ansehen** — die Kette der Funde vom 25.08.2026 (fehlender letzter Schritt,
gekaperte Suche, fehlendes Vorschaubild, fehlende Kennzeichnung) stand in
keinem roten Test, aber in jedem Bildschirmfoto. Verwandt:
[[oberflaeche-von-hand-fahren]], [[eine-kette-endet-am-letzten-glied]],
[[text-gesetzt-heisst-nicht-gezeigt]].
