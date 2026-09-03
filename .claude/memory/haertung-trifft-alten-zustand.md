---
name: haertung-trifft-alten-zustand
description: Eine gehärtete Fassung deckt beim ersten Upload auf, was seit Tagen falsch steht — die Zustandsdateien sind älter als die Prüfung, die sie prüft
metadata:
  type: project
---

Zweimal in derselben Nacht (03.09.2026), Wort für Wort dieselbe Geschichte:

* Der neue `count.php` verlangt `0600` für seine Zähldatei. Die per FTPS
  zurückgespielte Datei kam mit `0644` — **zwei Stunden lang zählte der Server
  nichts**, jede Anfrage mit 302 beantwortet, keine Zeile geschrieben.
* Die neuen Aktivierungsendpunkte verlangen dasselbe für
  `appdata/activation.seed` und `activation.sqlite`. Beide lagen seit dem
  28.08. mit `0644` dort — **alle vier Endpunkte antworteten mit 503**, „noch
  nicht vollständig eingerichtet", sobald die gehärtete Fassung oben war.

**Why:** Die Prüfung (`fileperms & 0077`) kam mit dem Release ins Repository;
die Dateien sind älter. Der Upload hat den Fehler nicht verursacht, sondern
sichtbar gemacht — und zwar zum schlechtestmöglichen Zeitpunkt, im Moment der
Veröffentlichung. FTPS überträgt keine Rechte: Was hochgeladen oder
zurückgespielt wird, bekommt die Vorgabe des Servers.

**How to apply:** Nach jedem Upload, der eine gehärtete Fassung mitbringt, die
Endpunkte **abfragen** statt anzunehmen, dass sie laufen — `activation-health.php`
antwortet `{"ok": true, "protocol": 1}`, `count.php` schreibt eine Zeile.
Antwortet etwas mit 503 „nicht vollständig eingerichtet", sind es die Rechte
der Zustandsdateien: `SITE CHMOD 600` auf die Datei, `700` auf ihr
Verzeichnis. Und wer eine solche Prüfung neu einbaut, prüft **vorher** den
Bestand auf dem Server, statt sie den ersten Kunden finden zu lassen.
Verwandt: [[solidon3d-webserver-zugang]].
