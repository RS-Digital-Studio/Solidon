# Der Größenfall

Er liegt nicht als Datei bei: 26214410 Bytes neben zwanzig
Dateien, die zusammen keine 20 KB wiegen, und dieser Ordner wird eingecheckt.

Zum Nachbauen, auf beiden Seiten dieselbe Datei:

    python -c "open('zu-gross.bin','wb').write(b'{\"name\": \"x\", \"title\": \"' \
        + b'z' * 26214410 + b'\"}')"

Erwartet wird **eine** Meldung über die Größe, und zwar **bevor** irgendetwas
geparst wird. Das ist die eigentliche Zusage: Eine Datei, die zu groß ist,
wird nicht erst gelesen — wer sie parst und danach die Größe prüft, hat den
Fall nicht abgedeckt, sondern nur seine Meldung.
