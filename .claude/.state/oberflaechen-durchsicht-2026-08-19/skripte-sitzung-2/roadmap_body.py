"""Die zwei erledigten Punkte des Abschnitts abhaken, mit Messwert."""

from __future__ import annotations

from pathlib import Path

path = Path("ROADMAP.md")
text = path.read_text(encoding="utf-8")

KEYS_OLD = """- [ ] **Nackte Tasten gehören dem Fokus — außer Entf, und das ist zu wenig
      durchdacht.**"""
KEYS_NEW = """- [x] **Nackte Tasten gehören dem Fokus — vier von ihnen** (`23cc1ea`).
      Entschieden ist es je Taste, so wie der Punkt es verlangte, und die Grenze
      verläuft zwischen *Bewegen im Inhalt* und *Befehl an das Fenster*: Pos1,
      Ende, Bild auf und Bild ab gehören dem Bedienelement mit dem Fokus, die
      Ziffern der Darstellungsarten bleiben Fensterbefehle. Der Filter nimmt
      dafür das `ShortcutOverride` an, das Qt vor jedem Kürzel an die Fokuskette
      schickt — Listen und Bäume nehmen es für Pos1 nicht an, deshalb gewann
      „Alles einpassen".

      Zwei Messwerte aus dem Bau: Der Filter hängt an der **Anwendung** (vom
      Fenster aus ist das Ereignis nicht zu sehen) und dort **einmal** — je
      Fenster installiert wuchs die Kette mit jedem gebauten Fenster, und
      `tests/test_ui.py` blieb bei 97 % stehen, zweimal, nach je zehn Minuten
      abgebrochen. Mit einem Filter: 223 Tests in 3:16.

      Der ursprüngliche Text des Punktes, zur Erinnerung, was daran nicht
      trivial war:"""

assert text.count(KEYS_OLD) == 1
text = text.replace(KEYS_OLD, KEYS_NEW)

SPLIT_OLD = """- [ ] **Der Trennen-Bereich hat laut Fund 130 Punkte Totraum.** Offscreen
      gemessen kommt das Gegenteil heraus — die Leiste wünscht 146 Pixel und
      bekommt 24 —, weil Qt dort ohne Schriftfamilien andere Metriken rechnet.
      Dieser Fund braucht die echte Plattform, so wie die Abbildungen sie
      brauchen; aus dem Offscreen-Lauf ist er nicht zu entscheiden."""
SPLIT_NEW = """- [x] **Der Trennen-Bereich hatte 109 Punkte Totraum, und der Satz darin war
      null Punkte breit** (`b66987b`). Auf der echten Plattform gemessen, wie
      der Punkt es verlangte: 1440 Bildpunkte Fensterbreite, Karte 685 breit.
      Die Zustandszeile („Auf das Teil klicken — dort fängt die Trennlinie an.")
      bekam in der Zeile mit den sechs Bedienelementen **null** Bildpunkte — die
      anderen brauchten 670 —, weil ihre waagerechte Politik `Ignored` war. Die
      hatte ihren Grund (sie schützte den Hauptknopf vor „etzt trenne"), ihr
      Preis war größer: Ein umbrechender Text verlangt für die Breite null eine
      Höhe von 160 Punkten, und daraus wurde der gemeldete Totraum.

      Beides erledigt eine zweite Zeile. Nachher gemessen: Karte **132** statt
      241, Leiste 59 statt 168, keine unsichtbare Beschriftung mehr — und die
      anderen sieben Werkzeugkarten unverändert bei 81 bis 112."""

assert text.count(SPLIT_OLD) == 1
text = text.replace(SPLIT_OLD, SPLIT_NEW)

path.write_text(text, encoding="utf-8")
print("zwei Punkte abgehakt")
