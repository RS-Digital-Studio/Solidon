---
name: schutz-verliert-ein-geschwister
description: "Wer eine Funktion um eine Variante erweitert, muss den ALTEN Namen durch conftest, Fixtures, Patches und Wächter grepen — eine Isolierung zeigt auf Namen, nicht auf Absichten."
metadata:
  type: feedback
---

Am 30.08.2026 an der Slicer-Auswahl: `discover.find_program` bekam mit
`find_programs` eine Mehrzahl-Variante. Die alte stand in einer autouse-Fixture
(`tests/conftest.py`, `_machine_stays_out_of_it`), die nach §38 verhindert, dass
die Suite die Maschine fragt, auf der sie läuft. **Die neue stand dort nicht.**

Damit sah jeder Test, der den Druckdialog baut, auf einem Entwicklerrechner mit
drei Slicern etwas anderes als der Bauserver mit keinem:

    vorher    _slicer_path = None            _needs_profiles = False
    nachher   _slicer_path = ElegooSlicer    _needs_profiles = True

Zwei Tests fielen. Betroffen war die ganze Datei.

**Das Lehrstück ist der dritte Test**, der dabei mitfiel und *vorher grün* war:
Er patchte `find_program` (Einzahl), während der geprüfte Weg über die Mehrzahl
lief. Der Patch ging ins Leere — grün war der Test nur, weil die **ungepatchte
echte Suche** auf dieser Maschine zufällig ohne Profilbestand endete, und das
sah aus wie das erwartete Leeren. Ein ins Leere gehender Patch ist schlimmer als
gar keiner: Er behauptet eine Isolierung, die es nicht gibt, und macht das
Ergebnis von der Maschine abhängig, ohne dass jemand es liest.

**Why:** Eine Isolierung — Fixture, Monkeypatch, Wächtermuster — zeigt auf einen
**Namen**, nicht auf eine Absicht. Sie kann nicht wissen, dass die Absicht
inzwischen einen zweiten Namen hat. Der Schutz bricht dabei still: Nichts wird
rot, weil ein Schutz fehlt; rot wird erst irgendwann etwas anderes, an einer
Stelle, die mit der Erweiterung nichts zu tun hat.

**How to apply:** Wer eine Funktion um eine Variante erweitert, grept den
**alten** Namen durch `tests/conftest.py`, alle Fixtures, alle `monkeypatch`-
Aufrufe und die Wächtermuster — und trägt die neue überall dort nach. Zwei
Minuten Suche. Die Gegenprobe ist beidseitig: Riegel heraus → rot, Riegel
hinein → grün, Rückstellung bestätigt.

Die Umkehrung von [[reparierter-fehler-hat-zwillinge]]: Dort hat der *Fehler*
ein Geschwister, hier hat der *Schutz* eines verloren. Verwandt mit
[[waechter-reichweite-nur-im-kommentar]] — dort deckt der Schutz weniger, als
sein Kommentar behauptet; hier deckt er weniger, als er einmal deckte.
Siehe auch [[waechter-zaehlt-das-falsche]].

**Und die Grenze dieser Notiz, am 30.08.2026 gemessen: Ein Wächter über ein
*Verhalten* trägt den Namen der Funktion nirgends.** Ich habe `_recolour`
ersatzlos entfernt und vorher durch `app/` und `tests/` gegrept — null Treffer
außerhalb der Datei. Rot wurde trotzdem etwas: `test_the_open_tool_keeps_its_
symbol_readable` sicherte zu, dass das Symbol des aktiven Werkzeugs eine
**andere Farbe** hat als die ruhenden, also genau das, was `_recolour` tat. Der
Name kam darin nicht vor, und der Test stand in `test_ui.py`, nicht in
`test_tool_strip.py`.

Die brauchbare Frage ist deshalb nicht „wer ruft das", sondern: **Wer würde rot,
wenn das Gegenteil gälte?** Praktisch heißt das, nach der *Wirkung* zu suchen
(hier: nach dem Namen des Knopfes, nach `icon()`, nach der Farbe) und nicht nur
nach dem Bezeichner.
