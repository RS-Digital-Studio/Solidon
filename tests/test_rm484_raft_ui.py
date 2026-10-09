"""Fensterfreie Anschlussproben am tatsächlichen Zahlenfeld- und Änderungsweg."""

from types import SimpleNamespace

import pytest

from app.core.export import manufacturer
from app.core.knowledge import print_settings, profiles
from app.ui import print_settings_dialog as dialog


class Signal:
    def connect(self, callback):
        self.callback = callback


class Spin:
    """Zahlenfeldvertrag ohne QWidget, Fenster oder Ereignisschleife."""

    def __init__(self, parent=None):
        self.number = 0.0
        self.low = 0.0
        self.high = 2.0
        self.valueChanged = Signal()
        self.special = ""
        self.named_limits = None
        self.keyboard_tracking = True

    def setRange(self, low, high):  # noqa: N802 - Qt-Vertrag des Prüfstands
        self.low, self.high = low, high

    def setMinimum(self, low):  # noqa: N802 - Qt-Vertrag des Prüfstands
        self.low = low

    def minimum(self):
        return self.low

    def setSpecialValueText(self, text):  # noqa: N802 - Qt-Vertrag des Prüfstands
        self.special = text

    def name_limits(self, low, high):
        self.named_limits = low, high

    def setKeyboardTracking(self, value):  # noqa: N802 - Qt-Vertrag des Prüfstands
        self.keyboard_tracking = value

    def setValue(self, value):  # noqa: N802 - Qt-Vertrag des Prüfstands
        self.number = value

    def value(self):
        return self.number

    def sizeHint(self):  # noqa: N802 - Qt-Vertrag des Prüfstands
        return SimpleNamespace(width=lambda: 20)

    def toolTip(self):  # noqa: N802 - Qt-Vertrag des Prüfstands
        return ""

    def accessibleDescription(self):  # noqa: N802 - Qt-Vertrag des Prüfstands
        return ""

    def __getattr__(self, name):
        if name.startswith("set"):
            return lambda *args: None
        raise AttributeError(name)


@pytest.fixture
def raft_field(monkeypatch):
    for name in ("BoundedSpin", "QDoubleSpinBox", "QAbstractSpinBox"):
        monkeypatch.setattr(dialog, name, Spin)
    monkeypatch.setattr(dialog, "wheel_needs_focus", lambda editor: None)
    fields = [field for field in dialog.FIELDS if field.path == "adhesion.raft_gap"]
    assert len(fields) == 1, "Das Raftfeld muss genau einmal in der Haftungsgruppe stehen."
    return fields[0]


@pytest.mark.parametrize("value", (None, 0.0, 0.16))
def test_native_editor_roundtrip_keeps_unknown_separate_from_zero(raft_field, value):
    editor = dialog._make_setting_editor(raft_field, None, lambda: None)
    dialog._set_setting_editor(editor, raft_field, value)
    assert dialog._setting_editor_value(editor, raft_field) == value
    assert editor.special == "Vorgabe des Slicers"
    assert editor.named_limits == (0.0, 2.0)
    assert not editor.keyboard_tracking


def host_for(raft_field, editor, base, own):
    host = SimpleNamespace(
        _loading=False,
        _fields={raft_field.path: raft_field},
        _editors={raft_field.path: editor},
        _search_requirement_target="",
        _search_requirement_control="",
        settings=own,
        _base=lambda: base,
        _foundation=manufacturer.Foundation(base),
        _update_inactive_setting_rows=lambda: None,
        _mark_origins=lambda: None,
        _mark_fields_this_slicer_ignores=lambda: None,
        _refresh_advice=lambda: None,
    )

    def load(paths=None):
        dialog._set_setting_editor(editor, raft_field, host.settings.adhesion.raft_gap)

    host._load_into_editors = load
    return host


def base_with_gap(gap):
    base = print_settings.resolve(profiles.make_profile())
    assert hasattr(base.adhesion, "raft_gap")
    base = print_settings.with_path(base, "adhesion.kind", "raft")
    return print_settings.with_path(base, "adhesion.raft_gap", gap)


def test_keyboard_value_changes_only_the_raft_field(raft_field):
    base = base_with_gap(0.15)
    editor = dialog._make_setting_editor(raft_field, None, lambda: None)
    host = host_for(raft_field, editor, base, base)
    editor.setValue(0.16)
    dialog.PrintSettingsDialog._editor_changed(host, raft_field.path)
    assert host.settings.chosen == frozenset({"adhesion.raft_gap"})
    assert host.settings.adhesion.raft_gap == pytest.approx(0.16)
    assert host.settings.support == base.support


@pytest.mark.parametrize("base_gap", (None, 0.15))
def test_selecting_default_releases_origin_and_reloads_actual_base(raft_field, base_gap):
    base = base_with_gap(base_gap)
    own = print_settings.with_choice(base, "adhesion.raft_gap", 0.16)
    editor = dialog._make_setting_editor(raft_field, None, lambda: None)
    host = host_for(raft_field, editor, base, own)
    editor.setValue(editor.minimum())
    dialog.PrintSettingsDialog._editor_changed(host, raft_field.path)
    assert host.settings.adhesion.raft_gap == base_gap
    assert "adhesion.raft_gap" not in host.settings.explicit
    assert dialog._setting_editor_value(editor, raft_field) == base_gap
    changed_base = print_settings.with_path(base, "adhesion.raft_gap", 0.3)
    assert print_settings.on_base(host.settings, changed_base).adhesion.raft_gap == pytest.approx(
        0.3
    )


def test_foundation_button_releases_only_raft_choice(raft_field):
    base = base_with_gap(0.15)
    own = print_settings.with_choice(base, "adhesion.raft_gap", 0.16)
    own = print_settings.with_choice(own, "support.z_gap", 0.25)
    editor = dialog._make_setting_editor(raft_field, None, lambda: None)
    host = host_for(raft_field, editor, base, own)
    dialog.PrintSettingsDialog._reset_field(host, raft_field.path)
    assert host.settings.adhesion.raft_gap == pytest.approx(0.15)
    assert host.settings.chosen == frozenset({"support.z_gap"})
    assert host.settings.support.z_gap == pytest.approx(0.25)


def test_default_is_named_in_report_and_reset_tooltip():
    assert dialog.shown_value("adhesion.raft_gap", None) == "Vorgabe des Slicers"


@pytest.mark.parametrize("flavour", ("prusa", "orca", "cura"))
@pytest.mark.parametrize("layers", (0, 2))
def test_actual_row_refresh_matches_effective_raft_without_supports(monkeypatch, flavour, layers):
    class Choice:
        def __init__(self, value):
            self.value = value

        def currentData(self):  # noqa: N802 - Qt-Vertrag des Prüfstands
            return self.value

    monkeypatch.setattr(dialog, "QComboBox", Choice)
    settings = base_with_gap(0.16)
    settings = print_settings.with_path(settings, "adhesion.raft_layers", layers)
    settings = print_settings.with_path(settings, "support.style", "none")
    fields = {field.path: field for field in dialog.FIELDS}
    shown = {}
    rows = (*print_settings.SUPPORT_DETAILS, *print_settings.ADHESION_DETAILS)
    host = SimpleNamespace(
        settings=settings,
        session=SimpleNamespace(profile=profiles.make_profile()),
        _fields=fields,
        _editors={
            **{path: object() for path in rows},
            "adhesion.kind": Choice("raft"),
            "support.style": Choice("none"),
        },
        _current_flavour=lambda: flavour,
        _foundation_for_current_setup=lambda: None,
        _slicer_path="",
        _labels={path: path for path in rows},
        _refusals={},
        _tab_forms={
            group: SimpleNamespace(setRowVisible=lambda row, visible: shown.update({row: visible}))
            # Jedes Formular, in dem eine Detailzeile steht: Die volle Kühlung an
            # der Stütze steht unter „Kühlung“ (RM-583).
            for group in {fields[path].group for path in rows}
        },
        _queue_refit=lambda reason: None,
    )
    host._inactive_paths = lambda: dialog.PrintSettingsDialog._inactive_paths(host)
    dialog.PrintSettingsDialog._update_inactive_setting_rows(host)
    assert shown["adhesion.raft_gap"] is (layers > 0 or flavour == "cura")
    assert shown["adhesion.raft_layers"]
    assert not shown["support.z_gap"]
