# Ein Katalogschlüssel ist ein Wort, und Wörter sind vergeben

**Was passiert ist (26.08.2026):** Ein neues Wertelabel sollte „Platz"
heißen. Der Schlüssel stand schon in allen fünf Katalogen — als Quelltext
des Materialslots, übersetzt mit „Slot"/„Ranura"/„Emplacement". Der
Nachzug überschrieb die fünf Übersetzungen, und jede Slot-Beschriftung
hätte fortan „Room" gesagt. Aufgefallen am Diff (`-  "Platz": "Slot"`),
nicht am Test — `test_translations` prüft Vollständigkeit, nicht
Bedeutung.

**Die Regel:** Der Katalog ist flach — ein deutsches Wort, eine
Übersetzung. Zwei Bedeutungen unter einem Wort kann er nicht tragen. Wer
einen neuen Quelltext anlegt, prüft zuerst, ob der Schlüssel schon
vergeben ist (`git diff` der Kataloge nach dem Eintragen lesen — eine
Zeile mit `-` vor einem Schlüssel, den man nicht angefasst zu haben
glaubt, ist der Alarm), und weicht sonst auf einen eindeutigen Quelltext
aus („Platz daneben" statt „Platz").

**Die Gegenrichtung, gefunden am 26.08.2026:** Derselbe *englische*
Schlüssel trägt zwei Sachen. In `app/ui/labels.py` heißt `slot` zweimal
**Langloch** — ein Schlitz für Schrauben mit Spiel — und einmal **Platz**, den
Materialslot; `radius` gehört zu Bohrungen und Verrundungen, nicht zum Pinsel.
Wer einen Umbau am Schlüsselnamen entlangfährt, benennt die falschen mit um.

Daraus die Suchregel für jede Umbenennung im Katalog: **Weder Text- noch
Schlüsselsuche trägt allein.** Die Textsuche verpasst, was anders heißt
(`slots` heißt „Plätze", `strokes` heißt „Striche" — beide fielen bei einer
Suche nach „Slot" und „Pinsel" durch); die Schlüsselsuche findet, was zufällig
gleich heißt. Beide Listen nebeneinanderlegen und **jeden Treffer an seiner
Verwendung** entscheiden, nicht am Namen.

**Verwandt:** [[uebersetzung-neu-statt-flicken]] — auch dort gilt: Der
Bestand hat Vorrang, Neues bekommt eigene Worte.
