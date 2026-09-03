---
name: gehaertete-fassung-trifft-alten-zustand
description: "Ein Upload, der eine neue Zustandsprüfung mitbringt, kippt Dateien, die es vorher schon gab: count.php an 0644 (Zähler zwei Stunden still), der Aktivierungsdienst an 0644 seit fünf Tagen (alle vier Endpunkte 503). Nach jedem solchen Upload die Zustandsdateien listen und einen Endpunkt abfragen."
metadata:
  type: feedback
---

Zweimal innerhalb von 24 Stunden, am 02./03.09.2026, mit demselben Ablauf:

| | die neue Prüfung | die alte Datei | wie es aussah |
|---|---|---|---|
| `count.php` | `count_stream_is_named_private` verlangt 0600 | Monatsdatei kam per FTPS mit 0644 zurück | 302 und 204 wie immer, zwei Stunden keine Zeile geschrieben |
| Aktivierung | `activation_require_private_file` verwirft `fileperms & 0077` | `activation.seed` und `activation.sqlite` lagen seit dem 28.08. mit 0644 | alle vier Endpunkte 503 „noch nicht vollständig eingerichtet" |

**Why:** Wer eine gehärtete Fassung hochlädt, sucht den Fehler in dem Code, den
er gerade geändert hat. Die Ursache liegt aber in einer Datei, die er **nicht**
angefasst hat und die Wochen älter ist — sie war die ganze Zeit falsch, nur
hat vorher niemand hingesehen. Und die Meldung führt weg von der Ursache:
„noch nicht vollständig eingerichtet" liest sich wie „nie aufgesetzt" und
nicht wie „falsche Rechte", der Zähler sagte gar nichts. Beide Male hat die
Sitzung, die hochgeladen hatte, ihren eigenen Upload verdächtigt und lag damit
halb richtig: Sie hat es ausgelöst, verschuldet hat sie es nicht.

**FTPS ist der Wiederholungstäter.** Eine hochgeladene Datei bekommt 0644,
nicht die Rechte des Originals. Wer eine Zustandsdatei über FTPS ersetzt,
erzeugt genau diesen Fall.

**How to apply:** Nach jedem Upload einer Fassung, die eine neue
Zustandsprüfung mitbringt — und nach jedem FTPS-Ersatz einer Zustandsdatei —
zwei Messungen, die zusammen zwei Minuten kosten:

    LIST solidon3d.de/appdata          # Rechte lesen, 0600 erwartet
    LIST solidon3d.de/solidon-stats
    GET  /api/activation-health.php    # ein Endpunkt, der den Zustand anfasst

Heilung ist `SITE CHMOD 600` über FTPS; danach dieselbe Messung noch einmal,
denn der Beleg ist die Antwort des Dienstes und nicht der Befehl.

**Und die Prüfung nicht schweigen lassen.** Beide Fälle haben eine Meldung ins
Fehlerprotokoll bekommen ([[waechter-sieht-nur-das-getane]] ist die
allgemeinere Form). Eine Zustandsprüfung, die den Dienst abschaltet und nichts
sagt, ist von „niemand war da" nicht zu unterscheiden — siehe auch
[[reparierter-fehler-hat-zwillinge]]: Der Ordner hatte dieselbe Krankheit wie
die Datei, und er wurde beim ersten Mal übersehen.

Zugang und Wege stehen in [[solidon3d-webserver-zugang]].
