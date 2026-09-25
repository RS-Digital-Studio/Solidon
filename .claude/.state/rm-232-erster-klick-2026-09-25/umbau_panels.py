"""Einmalig: RM-232 — die Kernauskünfte des Merkmalfensters als reine Funktion,
dazu Nachschlagen, Merken und ein Wartezustand für die Antwort aus dem Arbeiter."""

from __future__ import annotations

from pathlib import Path

path = Path("app/ui/panels.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str) -> None:
    global text
    assert text.count(old) == 1, (text.count(old), old[:100])
    text = text.replace(old, new)


swap(
    '''def _nothing() -> None:
    """Ein toter schwacher Verweis — der Anfangsstand des Merkers."""
    return None
''',
    '''def _nothing() -> None:
    """Ein toter schwacher Verweis — der Anfangsstand des Merkers."""
    return None


def feature_answers(
    feature_id: str,
    feature: Feature,
    features: Mapping[str, Feature] | None,
    mesh: MeshData | None,
) -> _FeatureAnswers:
    """Was der Kern über dieses Merkmal sagt: Hohlraumkette, Handlungen, Gleichartige.

    Rein und ohne Qt, deshalb auch im Nebenthread aufrufbar (RM-232): An der
    dichten Platte mit 204 000 Dreiecken kosteten die drei Auskünfte beim
    ersten Klick einer Bohrung 130 ms im Hauptfaden, jede weitere Bohrung
    beim ersten Mal noch rund 60. Wer sie im Arbeiter rechnet, gibt ihr dort
    die Arbeiterkopie des Netzes (``placement_flow.for_a_worker``): Die
    trägen trimesh-Merker sind nicht threadsicher.
    """
    from app.core.perceive import relations
    from app.core.perceive.actions import actions_for

    cavity: tuple[Feature, ...] = ()
    touches_other = False
    reason: relations.FeatureGroupReason | None = None
    if features is not None:
        if mesh is not None:
            state = relations.cavity_chain_state_at(feature, features, mesh)
            touches_other, reason = state.touches_other, state.reason
            cavity = state.chain or ()
        else:
            cavity = relations.bore_and_widening_at(feature, features) or ()
    actions = actions_for(
        feature,
        features,
        mesh=mesh,
        cavity=cavity,
        touches_other=touches_other,
        reason=reason,
    )
    groups: dict[str, FeatureActionGroup] = {}
    if features is not None and mesh is not None:
        groups = {
            group.action: group
            for group in relations.alike_for_actions(
                (str(action.op) for action in actions if action.op),
                feature_id,
                features,
                mesh,
            )
        }
    return _FeatureAnswers(cavity, tuple(actions), groups)
''',
)

swap(
    '''        Merkmalsliste; ein anderer Körper oder eine neue Auswertung beginnt
        von vorn, und der Körper wird nur schwach gehalten.
        """
        from app.core.perceive import relations
        from app.core.perceive.actions import actions_for

        known: dict[str, tuple[Feature, _FeatureAnswers]] | None = None
        if features is not None and mesh is not None:
            body, listed, known = self._answers
            if body() is not mesh.raw or listed is not features:
                known = {}
                self._answers = (weakref.ref(mesh.raw), features, known)
            cached = known.get(feature_id)
            if cached is not None and cached[0] is feature:
                return cached[1]
        cavity: tuple[Feature, ...] = ()
        touches_other = False
        reason: relations.FeatureGroupReason | None = None
        if features is not None:
            if mesh is not None:
                state = relations.cavity_chain_state_at(feature, features, mesh)
                touches_other, reason = state.touches_other, state.reason
                cavity = state.chain or ()
            else:
                cavity = relations.bore_and_widening_at(feature, features) or ()
        actions = actions_for(
            feature,
            features,
            mesh=mesh,
            cavity=cavity,
            touches_other=touches_other,
            reason=reason,
        )
        groups: dict[str, FeatureActionGroup] = {}
        if features is not None and mesh is not None:
            groups = {
                group.action: group
                for group in relations.alike_for_actions(
                    (str(action.op) for action in actions if action.op),
                    feature_id,
                    features,
                    mesh,
                )
            }
        answers = _FeatureAnswers(cavity, tuple(actions), groups)
        if known is not None:
            known[feature_id] = (feature, answers)
        return answers
''',
    '''        Merkmalsliste; ein anderer Körper oder eine neue Auswertung beginnt
        von vorn, und der Körper wird nur schwach gehalten. Gerechnet wird in
        :func:`feature_answers`; an einem großen Körper tut das der Arbeiter
        des Fensters, und seine Antwort liegt hier schon, wenn der Aufbau
        kommt (:meth:`remember_answers`, RM-232).
        """
        known = self.known_answers(feature_id, feature, features, mesh)
        if known is not None:
            return known
        answers = feature_answers(feature_id, feature, features, mesh)
        if features is not None and mesh is not None:
            self.remember_answers(feature_id, feature, features, mesh, answers)
        return answers

    def known_answers(
        self,
        feature_id: str,
        feature: Feature,
        features: Mapping[str, Feature] | None,
        mesh: MeshData | None,
    ) -> _FeatureAnswers | None:
        """Die gemerkte Antwort des Kerns zu diesem Merkmal — ``None``, wenn es keine gibt."""
        if features is None or mesh is None:
            return None
        body, listed, known = self._answers
        if body() is not mesh.raw or listed is not features:
            return None
        cached = known.get(feature_id)
        return cached[1] if cached is not None and cached[0] is feature else None

    def remember_answers(
        self,
        feature_id: str,
        feature: Feature,
        features: Mapping[str, Feature],
        mesh: MeshData,
        answers: _FeatureAnswers,
    ) -> None:
        """Eine Antwort des Kerns für diesen Körper und diese Merkmalsliste merken."""
        body, listed, known = self._answers
        if body() is not mesh.raw or listed is not features:
            known = {}
            self._answers = (weakref.ref(mesh.raw), features, known)
        known[feature_id] = (feature, answers)

    def show_pending(self, feature_id: str, feature: Feature) -> None:
        """Name und Maß des Merkmals, solange seine Handlungen noch ermittelt werden.

        Der Kern antwortet an einem großen Körper im Arbeiter (RM-232); bis
        dahin steht, was schon feststeht, und ein Satz, dass der Rest kommt.
        Eine Zeile zum Klicken gibt es in diesem Zustand nicht — was sie
        anböte, weiß noch niemand.
        """
        self.clear()
        _set_shown(self._empty, False)
        heading = QLabel(f"{cavity_name(feature_id, feature, ())}  ·  {feature_measure(feature)}")
        heading.setWordWrap(True)
        fit_wrapped(heading)
        set_level(heading, "section")
        self._rows.insertWidget(self._rows.count() - 1, heading)
        self._built.append(heading)
        self.show_note(tr("Die Handlungen werden ermittelt …"))
''',
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
