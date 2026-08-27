# `locales/` — die Sprachkataloge

Ein JSON je Sprache. **Deutsch hat keine Datei** — es ist die Quelle.

## Der Schlüssel ist der deutsche Satz

Kein Symbol, keine ID: der Quelltext selbst. Das hat eine Folge, die schon
einmal zugeschnappt ist — **ein neu formuliertes Label kapert still den
Eintrag eines anderen**, wenn beide denselben deutschen Satz ergeben. Der
Alarm ist das Minus im Diff dieser Dateien; der Test sieht es nicht.

## Nicht von Hand anlegen

`.venv/Scripts/python.exe -m app.i18n.extract` zieht jeden Katalog auf den
Stand der Quellen und meldet, wie viele Texte offen sind. Neue Schlüssel
kommen leer hinein und werden dann übersetzt.

## Eine neue Sprache ist eine Datei hier und sonst nichts

Alles liest `available_languages()`, also dieses Verzeichnis.
`tests/test_translations.py` prüft **jede** gefundene Datei — eine
unvollständige wird nicht eingecheckt.
