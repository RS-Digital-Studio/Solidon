# Ein Kalenderdatum folgt der App-Sprache

`QLocale()` ohne Argument folgt der Prozesssprache. Solidon wechselt seine
Anzeigesprache aber im laufenden Prozess. Ein ausgeschriebener Monat kann
deshalb deutsch in einem spanischen Dialog stehen, obwohl der Satz aus dem
richtigen Katalog kommt.

Für sprachabhängige Ausgaben eine Locale aus `app.i18n.get_language()` bilden.
Die Abnahme braucht die tatsächlichen Langformen aller ausgelieferten Sprachen
und ein gerendertes Fenster; ein übersetzter Quelltext allein sieht den Fehler
nicht.
