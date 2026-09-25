"""Einmalig: Review R3/R4/R20 — Außen je Verschachtelungsbaum, Teil im Teil nur im
Material, ein Körper ohne Schalenapparat."""

from __future__ import annotations

from pathlib import Path

path = Path("app/core/geom/repair.py")
text = path.read_text(encoding="utf-8")
start = text.index("class _Shells:")
end = text.index("def part_inside_finding(")
new = '''class _Shells:
    """Die Schalen eines Netzes: Dreiecke, Volumen, Hüllquader — einmal gelesen.

    Eine umhüllende Schale wird beim ersten Strahl gegen sie ausgeschnitten und
    behält danach Dreiecke und Hüllquader (Befund B19 der Durchsicht
    24.09.2026): Vorher kopierte jede Innenschale die ganze Außenschale neu,
    und 300 Hohlräume in 331 280 Dreiecken kosteten 7,2 s. Ob eine Schale in
    einer anderen liegt, fragt derselbe Strahl wie die Hohlraumerkennung
    (``perceive.features._point_inside_shell``). Die Hüllquader entstehen je
    Dreieck und werden je Schale zusammengefasst, ohne Kopie der Ecken
    (Review R20).
    """

    def __init__(self, body: trimesh.Trimesh) -> None:
        self.components = face_components(body)
        count = len(self.components)
        labels = np.empty(len(body.faces), dtype=np.int64)
        for index, members in enumerate(self.components):
            labels[members] = index
        self.triangles = np.asarray(body.triangles, dtype=np.float64)
        self.volumes = _shell_volumes(body, labels, count)
        self.low = np.full((count, 3), np.inf)
        self.high = np.full((count, 3), -np.inf)
        if count > 1:
            np.minimum.at(self.low, labels, self.triangles.min(axis=1))
            np.maximum.at(self.high, labels, self.triangles.max(axis=1))
        self._outer: dict[int, tuple[np.ndarray, tuple[np.ndarray, np.ndarray]]] = {}

    def containers(self, inner: int) -> list[tuple[int, bool | None]]:
        """Die Schalen, in denen ``inner`` liegt, mit der Antwort des Strahls.

        ``True`` ist belegt, ``None`` sagt der Strahl nicht; wer sicher außen
        liegt, fehlt. Vorab sieben die Hüllquader.
        """
        candidates = np.flatnonzero(
            np.all(self.low <= self.low[inner], axis=1)
            & np.all(self.high >= self.high[inner], axis=1)
        )
        found: list[tuple[int, bool | None]] = []
        for other in candidates.tolist():
            if other == inner:
                continue
            answer = self.inside(inner, other)
            if answer is not False:
                found.append((other, answer))
        return found

    def inside(self, inner: int, outer: int) -> bool | None:
        """Liegt ``inner`` in ``outer``? ``None``, wenn der Strahl es nicht entscheidet."""
        from app.core.perceive.features import _point_inside_shell, _triangle_bounds

        if outer not in self._outer:
            shell = self.triangles[self.components[outer]]
            self._outer[outer] = (shell, _triangle_bounds(shell))
        shell, bounds = self._outer[outer]
        point = self.triangles[self.components[inner][0], 0]
        return _point_inside_shell(point, shell, bounds)


def turn_shells_outward(body: trimesh.Trimesh) -> bool:
    """Richtet an einem geschlossenen Netz jeden freien Körper samt Inhalt nach außen.

    **Das Vorzeichen des ganzen Körpers reicht nicht** (Durchsicht
    24.09.2026). Bis dahin wurde nur umgestülpt, wenn das Gesamtvolumen
    negativ war: Zwei getrennte Würfel, einer davon innen-außen verkehrt,
    haben zusammen das Volumen null, und die Reparatur sagte „nichts zu
    reparieren" über einem Teil, das jeder Slicer je nach Füllregel als Loch
    liest.

    **Und eine Umkehr gilt dem Baum, nicht allem** (Review R3): Eine Schale,
    die in keiner anderen liegt, ist Material und muss positiv sein. Ist sie
    negativ, dreht sie sich um — und mit ihr alles, was belegt in ihr liegt,
    denn ein ganzer Hohlkörper verkehrt herum hat außen minus und innen plus.
    Ein richtiger Hohlkörper daneben bleibt, wie er ist; vorher kippte die
    Gesamtumkehr seinen Hohlraum mit, und ein korrektes Modell kam
    mehrdeutig heraus. Was dazwischen liegt — eine positive Schale im
    Material einer positiven —, kann ein verkehrter Hohlraum oder ein
    doppeltes Teil sein; das wird nicht geraten (Regel 21), sondern gemeldet
    (:func:`parts_inside_parts`).

    Sagt der Strahl nicht, ob eine Schale frei steht, gilt sie als umschlossen
    und bleibt unberührt. Liefert, ob etwas umgedreht wurde. Das Netz wird
    dabei verändert.
    """
    if not len(body.faces):
        return False
    shells = _Shells(body)
    count = len(shells.components)
    if count == 1:
        # Ein Körper braucht keinen Strahl (Review R20): sein Vorzeichen sagt alles.
        if shells.volumes[0] < 0.0:
            body.invert()
            return True
        return False
    inside_of = [shells.containers(index) for index in range(count)]
    turn = np.zeros(count, dtype=bool)
    for root in range(count):
        if inside_of[root] or shells.volumes[root] >= 0.0:
            continue
        turn[root] = True
        for member in range(count):
            if any(other == root and answer for other, answer in inside_of[member]):
                turn[member] = True
    if not turn.any():
        return False
    faces = np.asarray(body.faces, dtype=np.int64).copy()
    for index in np.flatnonzero(turn).tolist():
        members = shells.components[index]
        faces[members] = faces[members][:, ::-1]
    body.faces = faces
    return True


def parts_inside_parts(body: trimesh.Trimesh) -> list[tuple[float, float, float]]:
    """Die Mitten der Schalen, die nach außen zeigen und im Material einer anderen liegen.

    Der Rest von Befund B9 der Durchsicht 24.09.2026: Ein Würfel mit falsch
    herum gewickelter Innenschale hatte 9 000 statt 7 000 mm³, und nichts sagte
    es. Ob die innere Schale ein Hohlraum ist, der verkehrt steht, oder ein
    doppeltes Teil, weiß nur der Kunde (Regel 21); Slicer drucken die Stelle je
    nach Füllregel hohl oder voll.

    **Im Material, nicht nur innen** (Review R4): Eine Kugel, die frei in einem
    Hohlraum liegt — eine Rassel, ein Teil im Käfig —, liegt in zwei Schalen,
    der positiven außen und der negativen des Hohlraums, und dort ist Luft; jede
    Füllregel druckt sie voll. Gezählt wird deshalb die Summe der Vorzeichen
    aller belegt umschließenden Schalen: ab eins liegt die Schale im Material.
    Gefragt nach :func:`turn_shells_outward`, am geschlossenen Netz.
    """
    if not len(body.faces):
        return []
    shells = _Shells(body)
    positive = np.flatnonzero(shells.volumes > 0.0)
    if len(positive) < 2:
        return []
    places = []
    for index in positive.tolist():
        depth = sum(
            1 if shells.volumes[other] > 0.0 else -1
            for other, answer in shells.containers(index)
            if answer
        )
        if depth >= 1:
            middle = (shells.low[index] + shells.high[index]) / 2.0
            places.append((float(middle[0]), float(middle[1]), float(middle[2])))
    return places


'''
text = text[:start] + new + text[end:]
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
