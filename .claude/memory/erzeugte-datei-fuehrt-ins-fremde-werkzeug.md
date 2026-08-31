---
name: erzeugte-datei-fuehrt-ins-fremde-werkzeug
description: "Ein Befund im eigenen Gebiet endet im Werkzeug, das ihn erzeugt — und das gehört oft jemand anderem."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 60dfe3ed-7cce-4c68-a256-9db7aac288cb
  modified: 2026-08-31T07:26:58.409Z
---

Wer in seinem Gebiet eine **erzeugte** Datei prüft und dort etwas findet, darf
sie nicht ändern — die Änderung gehört ins Werkzeug. Damit wechselt der Befund
das Gebiet, ohne dass jemand eine Grenze überschritten zu haben glaubt: Die
Frage kam aus dem eigenen Bereich, die Antwort liegt in einem fremden.

Am 31.08.2026 geprüft, ob die neue Schriftskala auf allen Seiten trägt. Eine
Seite hatte eigene Größen — `handbuch.html`, und die ist erzeugt. Der Weg
führte in `tools/make_manual.py`, und dort lag die uncommittete Arbeit einer
anderen Sitzung an einer Navigationsleiste. Geschrieben, **dann** in
`git status` gesehen.

**Why:** Bei einer handgepflegten Datei stellt sich die Frage nach dem Halter
von selbst — man öffnet eine fremde Datei und merkt es. Bei einer erzeugten
merkt man es nicht: Man ist in seinem eigenen Gebiet unterwegs, misst seine
eigene Sache, und der Sprung ins fremde Werkzeug fühlt sich wie ein
Zwischenschritt an. Die Karte in `website/CLAUDE.md` führt die erzeugten
Dateien samt Werkzeug in einer Tabelle — sie beantwortet „darf ich das
ändern?", nicht „wem gehört das gerade?".

**How to apply:** Vor jedem Schreiben in einer Werkzeugdatei `git status` auf
sie ansehen — die Prüfung muss den Schreibbefehl noch ändern können, steht
also in einem **eigenen** Aufruf davor, nicht in derselben Kette (siehe
[[parallele-sitzung-im-arbeitsbaum]]). Liegt dort fremde Arbeit: melden, die
Wahl lassen (zusammen committen, nacheinander, oder zurücknehmen), und bis zur
Antwort nichts anfassen. Und beim Melden dazusagen, ob das fremde Vorhaben den
Erzeugerlauf ohnehin auslöst — dann reist die eigene Änderung im selben Zug
mit hinaus. Verwandt: [[freies-gebiet-einfach-machen]] gilt für Dateien, die
bei niemandem eingetragen sind; ein Werkzeug ist selten eingetragen und
trotzdem oft belegt.
