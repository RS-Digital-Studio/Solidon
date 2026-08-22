# Drehanleitung — Video 1: Der Gartentor-Adapter

Für das erste Video auf beiden Kanälen. Was hier gefilmt wird, kann ich nicht
erzeugen: eine Hand, ein Tor, ein gedrucktes Teil, das einrastet. Den
Bildschirmteil und den Schnitt mache ich.

**Aufwand: rund zwanzig Minuten.** Telefon genügt.

---

## Warum dieses Teil

Weil es eine Geschichte hat, die jeder versteht, der einen Drucker besitzt:
Das Tor hat sich gesetzt, fünf Zentimeter Spalt, die Falle greift nicht mehr,
seit einem Jahr hält eine Kette das Tor zu. Kein Software-Merkmal, sondern ein
Ärgernis mit einem sichtbaren Anfang und einem hörbaren Ende.

Der entscheidende Moment ist dabei nicht der fertige Adapter, sondern das
Prüfstück: `Torschloss_Adapter_KappenTest.stl` wird zuerst gedruckt, um die
Steckpassung übers Blech zu prüfen. Sitzt es zu stramm, ändert sich **eine
Zahl** — `CLR`, das Steckspiel, von 0,4 auf 0,5 — und das ganze Teil stimmt
wieder. Genau das ist der Unterschied zwischen parametrisch konstruieren und
neu konstruieren, und hier ist er kein Argument, sondern ein Handgriff.

---

## Die Einstellungen

Alles **hochkant** filmen. Aus Hochformat lässt sich Querformat schneiden,
umgekehrt nicht. Je Einstellung ruhig fünf Sekunden laufen lassen, auch wenn
am Ende zwei übrig bleiben — Anfang und Ende schneide ich weg.

| # | Was | Dauer | Worauf es ankommt |
|---|---|---|---|
| 1 | Das Tor, geschlossen, mit Kette und Vorhängeschloss | 5 s | Die Notlösung muss sofort lesbar sein. Etwas Abstand, ganzes Tor im Bild. |
| 2 | Nah auf den Spalt zwischen Schlosskasten und Blech | 5 s | Der Spalt ist das Problem. Wenn ein Maßband danebenpasst: umso besser. |
| 3 | Die Falle, die ins Leere greift | 5 s | Klinke drücken, Falle fährt aus, trifft nichts. |
| 4 | Prüfstück wird aufs Blech geschoben | 5 s | Die Hand von der Seite, nicht von oben — sonst verdeckt sie alles. |
| 5 | Der fertige Adapter wird aufgesteckt | 6 s | Eine durchgehende Bewegung, nicht stückeln. |
| 6 | Tor schließt, Falle rastet ein | 6 s | **Die wichtigste Einstellung.** Mit Ton — das Klicken ist der Beweis. |
| 7 | Tor zu, Kette hängt daneben ungenutzt | 4 s | Der Schlusspunkt: das Problem ist weg, die Behelfslösung überflüssig. |

**Optional, wenn schnell zu haben:** Der Drucker während des Drucks (5 s) und
das Teil frisch von der Platte (4 s). Beides funktioniert gut, ist aber nicht
nötig.

---

## Technisches

- **Ton mitlaufen lassen**, besonders bei Einstellung 6. Das Einrasten ist der
  überzeugendste Moment des ganzen Videos, und synthetisch nachbauen lässt es
  sich nicht.
- **Tageslicht**, kein Gegenlicht. Sonne im Rücken der Kamera.
- **Nicht zoomen und nicht schwenken** während der Aufnahme. Näher herangehen
  ist besser als heranzoomen.
- **Stabil halten**, gern gegen etwas abstützen. Verwackeltes Material lässt
  sich nicht retten.
- Querformat brauche ich **nicht** zusätzlich — ich schneide es aus dem
  Hochformat.

---

## Was danach passiert

Aus diesen Einstellungen und dem Bildschirmteil (Konstruktion in Solidon, der
Moment mit dem geänderten Spiel) baue ich:

* eine hochkante Version für TikTok, 25 bis 35 Sekunden
* eine quere Version für YouTube aus demselben Material
* beide auf Deutsch und Englisch, mit Untertiteln

Der Aufbau steht: Problem (Einstellung 1–3) — Lösung (Bildschirm + 4) — Beweis
(5–7) — Schluss. Das Problem in den ersten fünf Sekunden, weil dort entschieden
wird, ob jemand weiterschaut.

---

## Bevor du losgehst

Zwei Dinge, die ich nicht weiß:

1. **Ist der Adapter gedruckt und montiert?** In der Spezifikation standen im
   Juli noch offene Maße (`PIECE_W`, `POCKET_W`, `POCKET_DEPTH`). Ist er noch
   nicht am Tor, wird das Video erst danach gedreht — gestellt funktioniert es
   nicht, man sieht es.
2. **Hängt die Kette noch dran?** Wenn das Tor längst repariert ist, fehlt der
   Anfang der Geschichte. Dann nehmen wir ein anderes Teil; der
   Pool-Filterball-Einsatz und der Glasdeckel hätten dieselbe Struktur.
