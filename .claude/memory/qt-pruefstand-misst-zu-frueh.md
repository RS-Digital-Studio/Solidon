---
name: qt-pruefstand-misst-zu-frueh
description: processEvents führt DeferredDelete nicht aus und rechnet ein Layout nicht fertig — zwei Fehlbefunde an einem Nachmittag, beide durch Gegenproben widerlegt
metadata:
  type: feedback
---

**`app.processEvents()` ist nicht die Ereignisschleife.** Zwei Dinge, die die
laufende Anwendung tut, tut es nicht — und beide erzeugen Befunde, die
plausibel aussehen und falsch sind. Am 30.08.2026 bei V8 (Leistenbreiten in
sechs Sprachen) an einem Nachmittag beide getroffen.

## 1. `DeferredDelete` wird nicht zugestellt

Ein Widget, das mit `deleteLater()` abgeräumt wird, lebt unter `processEvents`
weiter. Wer Kinder zählt, zählt die alten mit.

Gemessen an der Schichtenleiste, die ihre Legende bei jedem Öffnen neu baut
(`takeAt` + `deleteLater` in `analysis_bar.update_legend`):

| Bedienfolge | mit `processEvents` allein | mit `sendPostedEvents(None, DeferredDelete)` |
|---|---|---|
| 6× Werkzeug öffnen | **6** Trennstrich-Labels | **1** |

Das sah nach einem schweren Kundenfehler aus — „wer die Leiste mehrfach
öffnet, sammelt Trennstriche an" — und wäre beinahe in fremdes Gebiet
gemeldet worden. Die Anwendung ist sauber; der Prüfstand war es nicht.

**Die Zeile, die fehlt:**
`app.sendPostedEvents(None, QEvent.Type.DeferredDelete)`

## 2. Ein Layout steht nach `resize()` nicht sofort

Fünfzehn Runden `processEvents` reichten nicht. Dieselbe Leiste meldete:

| Fensterbreite | nach 15 Runden | sauber gemessen |
|---|---|---|
| 1920 | 757 | **855** |
| 1440 | 854 | **855** |
| 800 | 668 | 768 |

**Das Warnsignal war die Nicht-Monotonie**: Bei 1920 weniger Platz als bei
1440 kann ein korrektes Layout nicht vergeben. Wo eine Zahl mit einer Größe
steigen *muss* und es nicht tut, ist die Messung falsch, nicht die Sache.
Das ist die Kehrseite von „Ein Messwert, der zu glatt ist, ist selbst der
Befund" (`.claude/rules/ansicht.md`): Dort verrät die verdächtige Gleichheit,
hier die verdächtige Unordnung.

**Sechzig Runden nach `resize`, fünfundzwanzig nach `set_language` und nach
`tools.activate`** — und dazu die Probe `fenster.width() == angefordert`,
bevor irgendeine Zahl gilt.

## 3. `set_language()` allein ist nicht der Kundenweg

Der dritte Fehlbefund desselben Nachmittags: Nach `install_language` +
`set_language` trugen die Rollenknöpfe in **allen sechs Sprachen** den
deutschen Text. Eine frisch gebaute Leiste hatte daneben die richtige
Übersetzung — das sah nach einem klaren Fehler aus, und zwar nach einem
schweren.

Die Anwendung macht es anders: `app.rebuild_for_language` **baut das Fenster
neu**. `tr()` übersetzt sofort, ein einmal gesetzter Text bleibt also stehen;
ein `retranslate()` müsste 367 Aufrufe allein in `main_window.py` nachziehen
und bei jedem neuen mitwachsen. Wer nur `set_language` ruft, stellt einen
Zustand her, den kein Kunde je sieht.

**Und der Beleg stand im Code.** Der Docstring von `rebuild_for_language`
nennt genau diese Messung — „nach einem Sprachwechsel waren 170 von 170
sichtbaren Texten unverändert", datiert auf den 25.08.2026. Ein Blick dorthin
hätte den Umweg gespart; siehe [[beleg-stand-im-eigenen-kontext]].

**Je Sprache ein frisches Fenster** ist der Prüfstand, der misst, was ein
Kunde sieht. Siehe [[sprachwechsel-zwei-schritte]] für die andere Hälfte:
`install_language` lädt, `set_language` aktiviert — beide zusammen sind
trotzdem nicht der Neubau.

## Was statt „mehr Runden" hilft

Die ersten drei Anläufe haben die Rundenzahl erhöht — 15, dann 60. Beim
vierten Fenster meldete dieselbe Leiste wieder Unsinn: Höhe 12 bei einem
höchsten Kind von 4. **Eine feste Zahl ist immer für ein bestimmtes Fenster
richtig und für das nächste falsch**, weil sie eine Dauer schätzt, wo eine
Bedingung gemeint ist.

Gewartet wird auf einen **Zustand**: bis Breite, Höhe und die Positionen der
Kinder sich dreimal hintereinander nicht mehr ändern.

```
def warte_bis_still(w, runden=400):
    vorher, gleich = None, 0
    for _ in range(runden):
        app.processEvents()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        jetzt = (w.width(), w.height(), tuple(sorted(
            (k.y(), k.height()) for k in w.findChildren(QWidget)
            if k.parentWidget() is w and k.isVisible())))
        gleich = gleich + 1 if (jetzt == vorher and jetzt[1] > 1) else 0
        if gleich >= 3:
            return True
        vorher = jetzt
    return False
```

Das schließt Falle 1 und 2 zugleich: `sendPostedEvents` steckt darin, und die
Bedingung ersetzt jede geschätzte Dauer. Wo sie nach 400 Runden nicht greift,
wird **nicht gemessen** statt geraten — eine Zeile „kam nicht zur Ruhe" ist
eine ehrlichere Ausgabe als eine Zahl, die niemand nachprüft.

## Die Regel darüber

Ein Prüfstand, der Qt fernsteuert, zeigt per Voreinstellung **einen Zustand,
den die Anwendung so nie hat** — halb abgeräumt, halb gelegt, halb übersetzt.
Bevor eine Zahl zum Befund wird, gehört die Frage dazu: *Kann dieser Wert
überhaupt so aussehen, wenn alles richtig ist?* Dreimal lautete die Antwort
nein, und dreimal lag es am Prüfstand.

**Die Kosten sind unsymmetrisch, und darum lohnt die Gegenprobe immer.** Ein
verworfener Fehlbefund kostet eine Messung; ein gemeldeter kostet eine fremde
Sitzung ihre Zeit und den Melder seine Glaubwürdigkeit. Zwei der drei hier
hätten in fremdes Gebiet gezeigt.

Siehe auch [[messwerkzeug-misst-sich-selbst]], [[sondenbau]] und
[[oberflaeche-von-hand-fahren]] — dieselbe Familie, andere Ebene: Dort ging es
um die *Lage*, in der gemessen wird, hier um den *Zeitpunkt*.

**Vierte Gestalt, 30.08.2026 (15, an B10): `resize(sizeHint())` misst einen
Zustand, den kein Kunde sieht.** Der `sizeHint` der Druckeinstellungen wird
von der **ungekürzten** Reiterleiste bestimmt (1264 Punkte), obwohl die
Reiter seit D11 gekürzt werden können — im Betrieb entscheidet das Layout,
und der Dialog öffnet mit 695. Ein Prüfstand, der sich auf den sizeHint
setzt, misst also eine Breite, die es nur im Prüfstand gibt. Die Frage vor
jeder Fenstermessung: Ist die Größe die, mit der die Anwendung wirklich
öffnet — oder die, die ein Hint gern hätte?
