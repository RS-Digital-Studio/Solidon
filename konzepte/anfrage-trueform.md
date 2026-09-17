# Anfrage an Polydera (trueform) — Entwurf, zurückgezogen

> **Zurückgezogen am 17.09.2026, am selben Tag, an dem er entstand. Nicht
> senden.** Der Entwurf steht vollständig unten, weil er zeigt, wie knapp eine
> gut begründete Anfrage an einer ungeprüften Prämisse vorbeigehen kann.
>
> **Die tragende Begründung war falsch.** Frage 3 lautete: „Could you confirm
> that trueform guarantees identical output across x86 and arm64?" — und sie
> unterstellte, dass manifold3d das nicht tut. Gemessen ist das Gegenteil:
> Sind die Eingangskörper bitgleich, liefert manifold3d auf Windows, Ubuntu und
> macOS **dieselben Bits**. Der Unterschied, der uns Tage gekostet hat, entstand
> davor, in unserer eigenen Punkterzeugung: ``np.cos`` und ``np.sin`` wählen
> ihre Implementierung nach den Fähigkeiten der CPU.
>
> Die Behebung steht in ``units.circle_point`` und ``geom.lathe``; der Nachweis
> in ``tests/test_platform_identity.py`` und im Register unter
> [RM-187](../ROADMAP.md#rm-187).
>
> **Was daraus zu lernen ist**, und es ist teurer als der Entwurf: Ich hatte
> eine Ursache zugeordnet („FMA entsteht auf ARM von selbst"), sie erklärte den
> Befund, und ich habe drei Reparaturen und eine Kaufanfrage darauf gestellt,
> ohne den ersten Schritt der Kette je zu messen. Die Erklärung passte auch
> nicht ganz — Windows und Ubuntu sind beide x86 und lieferten trotzdem
> verschiedene Netze —, und dieser Widerspruch stand zwei Tage sichtbar da.
>
> Wenn trueform je wieder infrage kommt, dann wegen **Tempo** (18 ms gegen
> 120,3 ms im Anbieter-Benchmark) und aus keinem anderen Grund. Dafür müsste
> erst gemessen sein, dass die Booleschen Operationen bei uns überhaupt
> spürbar bremsen.

**Stand:** 17.09.2026 · **Nicht gesendet und nicht zu senden.** Empfänger laut
Website wäre `info@polydera.com`

Geschrieben auf Englisch, weil die Firma englischsprachig auftritt. Was
darunter steht, ist die deutsche Fassung der Begründung — für die Ablage, nicht
zum Mitsenden.

---

## Der Text

> **Subject:** Commercial licence enquiry — trueform in a paid desktop CAD
> application (Python, Windows/macOS/Linux)
>
> Hello,
>
> I am Robert Schneider of RS Digital. We develop **Solidon3D**, a commercial
> desktop application for preparing and constructing 3D-printable models
> (Python 3.14 with PySide6, shipped as signed installers for Windows, macOS
> and Linux; sold as a one-time purchase, no subscription, no cloud).
> The product page is https://solidon3d.de/.
>
> Our mesh booleans currently run on manifold3d. We are evaluating a move to
> trueform for two reasons, and I would like to ask what a commercial licence
> would cost before we invest in the integration.
>
> **1. Identical results on every platform.** This is the one that pushed us
> to look. Our test suite runs on Windows, Ubuntu and macOS. The same boolean
> operation — reducing the diameter of a counterbored hole — produces a mesh
> with 1178 triangles on x86 (Windows and Ubuntu) and 1176 on the arm64 macOS
> runner. All measured dimensions are identical to four decimals; only the
> triangulation differs. That difference is enough to change the boundary
> topology of one face, and a feature that our software recognises and lets
> the user edit on Windows cannot be edited the same way on a Mac. We are
> currently working around this in our own feature recognition, but we would
> much rather stand on a kernel where the question does not arise.
>
> From your documentation I understand trueform computes arrangements over a
> bounded integer kernel (int32 coordinates, int64 intermediates, int128
> predicates). If I read that correctly, the result is a function of the
> quantised input alone and therefore bit-identical on any architecture —
> which is exactly the property we need. **Could you confirm that trueform
> guarantees identical output across x86 and arm64?** It is the single most
> important question for us.
>
> **2. Speed.** Your published benchmark puts trueform at a 18 ms median
> against 120.3 ms for Manifold on 1000 Thingi10K pairs at 200K–1.5M polygons.
> Our users work interactively — every boolean sits between a click and a
> preview — so a factor of roughly seven is not a nicety for us.
>
> **What I would like to know:**
>
> 1. **Price and licence model** for a commercial, closed-source desktop
>    application distributed as a one-time purchase. We are a small company;
>    a rough order of magnitude is enough at this stage.
> 2. **Redistribution.** We ship a self-contained application built with
>    PyInstaller. The trueform binary would travel inside our installer. Is
>    that covered?
> 3. **Cross-platform determinism**, as above — ideally as a statement we can
>    rely on, not an implementation detail that may change.
> 4. **The bounded integer kernel in practice.** What coordinate range does
>    the int32 default cover, and how does one scale input for parts that are
>    a few hundred millimetres across with features of a few hundredths? Does
>    switching to the int64 base precision cost performance?
> 5. **Maturity and support.** trueform is at 0.x. What is your stability
>    policy for the Python API, and what support is included with a commercial
>    licence?
> 6. **Evaluation.** Is there a licence that lets us run trueform against our
>    own corpus — roughly 200 real customer models — before deciding?
>
> Thank you for your time. If it is easier to talk this through, I am happy to
> arrange a call.
>
> Kind regards,
> Robert Schneider
> RS Digital · robert.schneider97@gmail.com

---

## Warum diese sechs Fragen — die Begründung dahinter

**Frage 3 ist die wichtigste, und sie ist noch offen.** trueforms Website und
das Repository sagen zur Plattformgleichheit **nichts**. Der Integer-Kern legt
sie nahe — Ganzzahlarithmetik rundet nirgends —, aber „legt nahe" ist keine
Zusage, und genau daran ist manifold3d für uns gescheitert: Dort steht
„guaranteed manifold output" und kein Wort zur Numerik. Wenn Polydera das
nicht zusichern will, kaufen wir dasselbe Problem noch einmal.

**Frage 4 ist die technische Kehrseite des Kerns.** Ein quantisiertes Gitter
ist exakt, aber begrenzt. Bei int32 über ein Bauteil von 300 mm liegt die
Auflösung rechnerisch bei rund 1,4·10⁻⁷ mm — weit unter allem, was ein
Drucker auflöst, und unter unserer Schweißtoleranz. Das muss man aber wissen
und nicht annehmen, denn wer eine Bohrung mit 0,02 mm Materialzugabe schneidet,
lebt von den Nachkommastellen.

**Frage 1 und 2 entscheiden, ob es überhaupt infrage kommt.** trueform steht
unter der PolyForm Noncommercial License; für ein verkauftes Produkt braucht
es eine Vereinbarung. Und ein Paket, das der Kunde installiert, enthält die
Bibliothek — das ist Weiterverbreitung und gehört ausdrücklich geklärt.

**Frage 5, weil 0.9.8 eine Zahl ist, die etwas bedeutet.** Wir binden uns an
einen Kern, den wir nicht selbst warten. Bei manifold3d federt das die
Apache-Lizenz ab: Fällt das Projekt aus, dürfen wir forken. Bei einer
gekauften Lizenz federt nichts, also muss der Vertrag es tun.

**Frage 6, weil der Benchmark vom Anbieter stammt.** Die Methodik ist
offengelegt (1000 Thingi10K-Paare, M4 Max, PyPI-Wheels), und daran ist nichts
auszusetzen — aber gemessen hat sie der, der verkauft. Unsere 200 Kundenmodelle
aus dem Downloads-Korpus sind der Maßstab, der für uns zählt: Bajonettringe,
Uhrenteile, Organizer, Scans.

## Was wir über manifold3d wissen, und was davon in die Mail gehört

In die Mail gehört **nur der gemessene Befund** — 1178 gegen 1176 Dreiecke,
gleiche Maße, andere Randtopologie. Das ist unser Fall, nachvollziehbar und
ohne Wertung.

Nicht in die Mail gehört, was manifold3d sonst vorgeworfen wird. Der
Vollständigkeit halber, weil es die Entscheidung mitträgt:

* Die Bibliothek rechnet in IEEE-754 mit symbolischer Störung, nicht exakt.
  Die eigene Dokumentation nennt den Grund — exakte Arithmetik sei „slow,
  complex, and often still suffers failures in edge cases".
* Koplanare Flächen bleiben ein offener Punkt: In der Diskussion zu „kissing
  faces" steht, dass Flächen, die aus demselben Schnitt entstehen, eigentlich
  perfekt koplanar sein müssten, „but floating point is problematic".
* `SetTolerance`/`GetTolerance` sind aus der API gefallen, weil sie sich mit
  `epsilon` überschnitten — die Toleranzfrage ist dort in Bewegung.

**Und was für manifold3d spricht**, damit die Abwägung ehrlich bleibt: Es ist
Apache-2.0, es liefert Wheels für alle drei Plattformen, es hat in demselben
Benchmark 1000 von 1000 Paaren gültig gelöst (MeshLib 999), und es kostet
nichts. Ein Wechsel muss besser sein als das, nicht nur schneller.

## Die dritte Möglichkeit: Geogram

Steht in `konzepte/geogram-als-zweiter-kern.md`.
