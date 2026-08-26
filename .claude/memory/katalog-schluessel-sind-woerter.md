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

**Verwandt:** [[uebersetzung-neu-statt-flicken]] — auch dort gilt: Der
Bestand hat Vorrang, Neues bekommt eigene Worte.
