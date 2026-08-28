---
name: messung-iterierte-die-schluessel
description: "Über ein Wörterbuch iteriert man die Schlüssel. getattr auf einem String gibt den Vorgabewert, und None gegen None liest sich wie Gleichheit — neun grüne Zeilen, alle wertlos."
metadata:
  type: feedback
---

Am 28.08.2026 sollte ich messen, ob das Druckerprofil des Erzeugers die
Geometrie der neun Beispielprojekte beeinflusst. Mein Skript:

```
for o in r.scene.objects:
    v = getattr(o, "volume", None)
```

`scene.objects` ist ein **Wörterbuch**. Die Schleife bekam die Schlüssel —
Zeichenketten wie `"obj_1"` —, `getattr` fand daran kein `volume` und gab
brav `None` zurück. Herausgekommen sind neun Zeilen `gleich=True`, und ich
habe sie als Entwarnung weitergegeben: „Das Erzeuger-Profil ist folgenlos."

Richtig gemessen (`.values()`) unterscheiden sich die Volumina um 2,74 mm³ —
und das deckt sich mit der Überschlagsrechnung für fünf Bohrungen bei
0,05 mm Toleranzunterschied. Die Aussage war also nicht ungenau, sondern
verkehrt.

**Widerlegt hat es kein Nachdenken, sondern ein Nebenprodukt.** Nach dem
Neuerzeugen standen fünf Vorschaubilder als geändert im Baum. Die Vorschau
bekommt nur die Netze (`render_preview(entry.mesh …)`) — kein Profil, kein
Bett. Wenn die Bilder sich ändern, müssen die Netze verschieden sein. Die
Gegenprobe (zwei Erzeugerläufe ohne Änderung → bitgleiche Dateien) schloss
aus, dass der Lauf einfach rauscht.

**Why:** `None == None` ist wahr, und ein Vergleich zweier leerer Messungen
sieht aus wie ein bestandener Test. Das ist dieselbe Klasse wie
[[messwerkzeug-misst-sich-selbst]]: Was ein Werkzeug meldet, ist zuerst eine
Eigenschaft des Werkzeugs. Hier kam dazu, dass Python jeden Schritt
klaglos mitmacht — kein Fehler, keine Warnung, nur ein stiller Vorgabewert.
Verwandt ist [[gemessene-frage-ist-nicht-die-gestellte]]: Gemessen wurde
„sind zwei Nichtmessungen gleich", gestellt war „ändert das Profil die
Geometrie".

**How to apply:**

- **Positivkontrolle vor dem Urteil.** Bevor ein Vergleich als Ergebnis
  gilt: einmal einen Fall messen, dessen Ausgang feststeht. Bei einer
  Gleichheitsprüfung heißt das, absichtlich einen Unterschied zu erzeugen
  und zu sehen, dass er auffällt.
- **Trefferzahl mitschreiben.** Nicht nur „gleich/verschieden", sondern die
  Werte selbst ausgeben. `volume=None` in der Ausgabe hätte den Fehler
  sofort verraten; `gleich=True` verbarg ihn.
- **Bei `for x in <dict>` innehalten.** Gemeint ist fast immer `.values()`
  oder `.items()`. Das Muster sieht richtig aus und ist es selten.
- **`getattr(obj, name, None)` verdeckt den Typfehler.** Wo der Vorgabewert
  nur eine fehlende Eigenschaft abfangen soll, fängt er auch das falsche
  Objekt ab. Ohne Vorgabewert wäre es ein `AttributeError` gewesen.
- **Ein widersprechendes Nebenprodukt ernst nehmen.** Die geänderten Bilder
  passten nicht zum Messergebnis. Wer das als Rauschen abtut, behält den
  falschen Befund — siehe [[der-index-schreck-war-ein-artefakt]].

Verwandt: [[sollwert-aus-dem-pruefling]] und [[was-die-suite-nicht-findet]] —
auch dort war der Finder nicht der Test, sondern etwas daneben.
