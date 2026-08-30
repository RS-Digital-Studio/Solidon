---
name: zufallsziehung-ist-keine-zuordnung
description: "Bei sporadischen Abstürzen ordnet erst eine Verteilung zu — drei Läufe rot und eine grüne Gegenprobe sind zwei Ziehungen aus derselben 7/8-Verteilung."
metadata:
  type: feedback
---

Am 30.08.2026 an `test_print_settings_ui.py`: Nach zwei neu hinzugefügten Tests
riss die Datei mit Exit 139 ab — **dreimal in Folge, immer bei exakt 64
Punkten**. Die Gegenprobe ohne die zwei Tests: **Exit 0.**

Damit stand die Zuordnung scheinbar fest: vier Messungen, alle in dieselbe
Richtung, sogar mit einer stabilen Zahl. Acht Wiederholungen je Variante
zeigten etwas anderes:

    MIT den neuen Tests    8 von 8 Läufen gerissen
    OHNE die neuen Tests   7 von 8 Läufen gerissen

**Der Abriss passiert praktisch immer.** Die drei roten Läufe und die eine
grüne Gegenprobe waren zwei Ziehungen aus derselben Verteilung — die grüne war
das eine Achtel. Ein ganzer Tag Suche nach einem eigenen Fehler hätte daran
gehangen.

Auch die stabile Zahl täuschte: „immer bei 64 Punkten" liest sich wie
Determinismus, ist aber nur die Stelle, an der die Datei ihr Fenster abbaut —
sie ist bei jedem Riss dieselbe, ob er nun kommt oder nicht.

**Why:** Bei einem sporadischen Ereignis ist ein einzelner Lauf eine Ziehung,
keine Messung. Eine Gegenprobe, die einmal grün ist, beweist nur, dass grün
vorkommt. Das ist dieselbe Logik wie bei einer Leistungsmarke, die um die
Schwelle streut — nur dass ein Absturz binär aussieht und deshalb sicherer
wirkt, als er ist.

**How to apply:** Bevor ein Absturz jemandem zugeordnet wird — auch sich
selbst —, beide Varianten **mehrfach** fahren und die *Quote* vergleichen,
nicht das Ergebnis. Fünf bis acht Läufe je Variante genügen; sie kosten
Minuten. Ein Unterschied von 8/8 gegen 7/8 ist keiner, 8/8 gegen 0/8 ist
einer.

Verwandt mit [[bekannte-familie-erklaert-nicht-den-ausloeser]] (dort erklärt
die Familie den Mechanismus, nie den Auslöser) und
[[leistungstests-fremdlast]]. Die Schwester in der Zeitmessung steht in
`.claude/rules/tests.md` unter „Die Regel fängt Fremdlast — sie fängt keinen
Wert, der um die Schwelle streut".

**Und die Umkehrung, die am 30.08.2026 fast teurer war: Ein einzelner *grüner*
Lauf ist so wenig eine Basisrate wie ein einzelner roter.** `test_widget_lifetime.py`
gab in meinem Baum zweimal 127; der allererste Lauf in einem frischen Worktree
auf reinem HEAD war **grün**. Zwei Läufe lang sah es damit aus, als hätte meine
Änderung den Absturz verursacht — die Zuordnung stand schon, und ich hätte sie
gemeldet. Vier Läufe auf reinem HEAD: einer grün, drei mit 127.

Wer eine Änderung entlasten will, misst die Basisrate mit derselben Sorgfalt wie
den Verdacht. Ein grüner Vergleichslauf beweist nichts, er ist nur eine Ziehung
aus einer Verteilung, die man noch nicht kennt.
