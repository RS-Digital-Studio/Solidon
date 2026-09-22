# P1.4b – lesende Gegenprüfung der reinen Antwortschicht

Geprüft wurden `app/core/perceive/match_decisions.py`, seine direkten Tests und das reine Datenschema in `match_records.py`. `evaluate.py` wurde ausdrücklich nicht geprüft; die folgenden Befunde belegen die öffentlichen Helferverträge, keinen ungeprüften Produktionsaufruf. Produktdateien wurden nicht geändert.

## Drei reproduzierte Lücken

Die gezielte Sonde `p14b-answer-review-probe.py` wurde einmal ausgeführt. Das unveränderte Rotprotokoll steht in `p14b-answer-review-probe.txt`; direkter Prozess-Exit **1**. Jeder der drei Gegenfälle wurde vor dem abschließenden Assert einzeln ausgegeben.

1. **Unvollständige Anspruchsgruppe kann publiziert werden.** `mapping_with_decisions` prüft, ob Entscheidungs- und übergebene Anspruchsschlüssel gleich sind, aber nicht, ob die Ansprüche eine vollständige Gruppe aus `result.ambiguous` bilden. Bei `ambiguous={a:(x,), b:(x,)}`, übergebenem `claims={a:(x,)}` und `decisions={a:x}` entsteht `{a:x}`. Ein konkurrierendes altes Merkmal bleibt unberücksichtigt. Die Grenze sollte die vollständige gemeinsame Zielmenge samt Anspruchskanten gegen das Ergebnis validieren. `group_fingerprint` verwendet denselben Helfer derzeit mit einem leeren MatchResult ausschließlich zur lokalen Wahlprüfung; dafür empfiehlt sich ein enger interner Wahlprüfer, damit die eigentliche Publikationsgrenze vollständig prüfen kann.

2. **Ein reservierter, nicht gewählter Kandidat bleibt im wiedererkannten Gruppenmuster.** Für `claims={a:(x,y), b:(x,y)}`, die gespeicherte Wahl `{a:y, b:None}` und `reserved_targets={x}` gibt `resolve_group` die Wahl erneut frei. Der reservierte Zieltest betrachtet nur die ausgewählten Entscheidungen. Der vereinbarte vollständige Gruppenvertrag verlangt, dass die Gruppe keinen freigegebenen Außennachfolger weiter beansprucht; daher muss die gesamte aktuelle Kandidatenmenge mit den reservierten Zielen abgeglichen werden. Der Matcher soll solche widersprüchlichen Gruppen bereits vermeiden; der direkte Antworthelfer bestätigt sie derzeit dennoch.

3. **Nichtendliche aktuelle Geometrie wird als alter Treffer bestätigt.** Ein gültiger gespeicherter Loch-Fingerprint wird gegen denselben aktuellen Kandidaten mit `centre=(NaN,0,0)` erneut als gültige Wahl aufgelöst. Die Ursache liegt im gemeinsamen `matching.resolve`: Die berechneten Kosten sind NaN, `best > MATCH_THRESHOLD` und der Rivalenvergleich ergeben beide falsch, sodass die Kandidaten-ID zurückgegeben wird. Neue gespeicherte Datensätze sind auf Endlichkeit geprüft; diese Prüfung schützt nicht die aktuelle Geometrie. Die gemeinsame Wiedererkennung muss nichtendliche aktuelle Vergleichswerte zurückweisen, statt einen erfolgreichen Treffer zu melden. Keine zweite Geometrie-/Kostenformel im Antwortmodul ergänzen.

## Gelesene intakte Verträge und Grenze des Nachweises

Gruppenbildung schließt gemeinsame Nachfolger transitiv. Neue Fingerprints tragen Rohmaß und Achsenrichtung; Identitätsänderungen werden geometrisch und mit beidseitig eindeutiger Zuordnung aller Kandidaten geprüft. Anzahl und Anspruchskanten werden verglichen. Explizite Nichtfortführung ist Teil des vollständigen Datensatzes. Lokale Entscheidungen werden vor Kopie/Publikation auf Kandidatenzugehörigkeit und gemeinsame Injektivität geprüft. Die vorhandenen Tests prüfen unter anderem geometrische Zwillinge, geänderte Beteiligte, doppelte gewählte Ziele, Nichtfortführung und Abbruch ohne Mutation.

Die ergänzte Callback-Weitergabe durch die Schema-Prüfschleifen wird parallel umgesetzt und ist deshalb hier kein neuer Befund. Keine Fenster-, Leistungs- oder Gesamtsuite wurde ausgeführt. Der einzige neue Lauf ist die gezielte reine Kernsonde oben.
