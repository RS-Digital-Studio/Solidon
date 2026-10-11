# Prüfbericht `konzept`-Agent zur Komponentenentscheidung (11.10., nach „kein Workaround“)

Urteil: noch nicht abgabefähig; Entscheidung für Komponenten richtig, Mixin-Ablehnung sauber.
Gemessen auf main `ee6b810fe` (MainWindow 895 Methoden, 335 Attribute). Skripte:
`F:\tmp-agenten\struktur-k\` (probe/hostparent.py, probe/selfproto.py).

## Schwer
1. Ersetzungsliste kennt kein nacktes `self`: 332× `self` als Wert in MainWindow (97
   `weak_slot(self, MainWindow._m)`, 64 Klassenbezüge `MainWindow.<m>`, ~40× Qt-Elternteil, 29
   `show_error(…, self)`, 13 `QTimer(self)`, 11 `isValid(self)`, 4 `weakref.ref(self)`, 14
   `getattr(self, "…")`, 4 `hasattr`). Protocol ist kein QWidget: `QDialog(self._host)` →
   `[arg-type]` (mypy strict); PlacementFlow umgeht mit `cast(QObject, dialog)`. Mechanisch: 256
   `connect(self.m)`, 87 Lambdas, 48 geschachtelte Funktionen, 1 Property; kein dynamisches getattr.
   Vorschlag: fünf Formen der Ersetzungsliste; Qt-Elternteil `self._host.window()` (Protokoll nennt
   `def window(self) -> QWidget`), Besitzer von weak_slot/QTimer/isValid die Komponente,
   `MainWindow.<m>` → `<Komponente>.<m>`, getattr/hasattr mit fester Zeichenkette vorher in eigenem
   Commit gewöhnliches Attribut; kein cast, kein Any (besteht mypy strict).
2. Zentrale Methoden berühren fast den ganzen Zustand: `_build_central` 162/335 Attribute,
   `__init__` 103, `_build_menus` und `_discard_gestures` je 40, `_update_actions` 32,
   `wait_for_workers` 22, `release`/`closeEvent` je 13; 66 Attribute berührt eine
   Lebenszyklus-Methode außer `__init__`. Zuweisungen in Komponenten-Konstruktor = keine
   Verschiebung; Widget-Reihenfolge bestimmt Tab-Kette. Vorschlag: zuerst diese Methoden in eigenen
   Commits in Abschnitte je Bereich zerlegen (belegt durch Fenstertests und Tab-Kette), dann nimmt der
   Schnitt einen Abschnitt ganz mit; Posten in 4.3.
3. Vorbild trägt Workaround: `PlacementFlow.__init__(dialog: PlacementHost, window: Any, …)`
   (placement_flow.py:1565), `getattr(self.window, "<name>", None)` in `_apply_placed_feature`
   (4651), `slot_drag_takes_the_accept` (1926), `announce` (4637), `overlay` (1597, 5438), dreimal
   `self.window._clear_preview()`. Zieht eine Methode um, liefert getattr still None. „Keine
   namensbasierten Verbindungen“ gilt nur für Qt: 18 Zeichenkettenzugriffe im Fenster auf sich,
   `shortcuts_window.py` 3× (`_op_actions`, `toolbar`), 5 in tools/. Bessere Vorbilder: `DrawFlow`,
   `LocalRecognitionFlow`, `SealFlow` (QObject-Kinder, `window: MainWindow` unter TYPE_CHECKING).
   Vorschlag: Muster PlacementHost (Protokoll) + DrawFlow (Kind, typisiert); Fensterseite von
   PlacementFlow = CS-16 (Fehler), vor Schritt 4 beheben.

## Mittel
4. Lebensdauer außerhalb des Beweises: `release` → `self.session.disconnect(self)`
   (main_window.py:29514; Kommentar nennt Ubuntu-Absturz); ≥ 36
   `self.session.<signal>.connect(self.<m>)`; `WorkerLeash(self)` (3173). Vorschlag: jede Komponente
   mit Empfängern/Arbeitern hat `release()`, MainWindow.release ruft es vor `session.disconnect`;
   Test: danach erreicht kein Sitzungssignal eine Komponente.
5. Tests/Werkzeuge: 2 246 Zugriffe auf MainWindow-only-Methoden in 70 Testdateien, 149
   `monkeypatch.setattr(window, "<m>")`, 152 `window.<member> = …` (legt still Attribut an); tools/:
   52 Zugriffe in 13 Werkzeugen, 5 `getattr(window, "…")`. Vorschlag W5: jeder verschobene Name als
   Zugriff, Zuweisungsziel und Zeichenkette in app/, tools/, tests/ umschreiben, Rest rot (866 von
   889 Methodennamen sonst in app/ eindeutig).
6. W1-Puffer 50 Zeilen = Streuzahl, misst nicht Regel 6; ~10 Commits/Tag. Vorschlag: gelistete Datei
   bekommt keine neue Funktion/Methode/Klasse (auch geschachtelt); je Datei eine Zahl (Definitionen),
   nur Verschiebeschritte ändern sie; Zeilen in bestehenden Rümpfen = Fix.
7. W2 „meldet“ nur → rot; Schritt 0 behebt vorher 25 `raising=False` und Kopfkopien gepatchter
   Namen (CS-11); Zusammenführen in eigenem Commit vor dem Schnitt.
8. Abnahme/Reihenfolge: „Datei ist weg“ gilt bei Komponentenschritten nicht; vor der Klasse 22
   Arbeiterklassen, 52 Funktionen rein verschiebbar. Schritt 4: Paket `app/ui/main_window/` —
   Arbeiter und Funktionen in Sachmodule, Klasse nach `window.py`, dann erste Komponente. 4.5:
   Komponente im eigenen Modul unter 2 000 Zeilen, Protokoll erhoben. Abschnitt 1 nicht „reine“.
9. Aufwand: Posten ergeben 22–39 Tage ohne Zusatzposten → „sechs bis acht Wochen, nach Probe in
   Schritt 4 neu geschätzt“, Rechnung offenlegen.
10. CS-14: `_BoundedBehavior` ruft acht Methoden fest als `NumberSpin.<m>(self, …)`; Protokoll als
    Selbsttyp → `[arg-type]` (probe/selfproto.py); an `BoundedLengthSpin` werden Überschreibungen von
    `LengthSpin` übersprungen, `showEvent` von Hand nachgebaut (labels.py:920). Art Fehler; Fix: eine
    Klassenlinie, Ablehnen in `NumberSpin` (kooperativ über super()), Test.

## Leicht
11. W4-Ausnahme `activation` unnötig (rekursiver Helfer liefert dieselbe Menge); Flachheit, falls
    nötig, als Zusicherung „keine Unterordner“.
12. Regel 9 vs. W1-Liste: „keine Ausnahmeliste, die einen Fehler verdeckt oder wachsen darf; eine
    Bestandsliste, die nur schrumpft, ist keine“.
13. 3.3-Zahlen: „Qt-Überschreibungen, ohne `__init__`: MainWindow 5, Viewport 9, PlacementFlow 1“;
    `@override` steht in main_window.py und viewport.py nirgends.
14. W6 an `_pin_ui_widgets`: Zuordnung Modul → Klasse nötig (in `app.ui.leash` fehlen beide planmäßig).
15. CS-15: Mechanismus benannt (`_windows_live_until_their_test_ends`: Abbau ohne geordnetes
    `release`; `_PinOnImport`: Produktcode hält Besitzer nicht zyklisch). Offen nur Produktseite: ob
    das Produkt einen Abbau ohne `release` ausschließt (Sprachwechsel, zweites Fenster,
    eigenständiger Viewport); „elternlose Dialoge, die eine `WorkerLeash` besitzen“.
