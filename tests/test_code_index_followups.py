"""Gegenbeispiele der letzten Durchsicht des Auflösers (N-01 bis N-08)."""

from __future__ import annotations

import ast

import pytest

from tests.code_index_helpers import build_index as _build

CASES: dict[str, dict[str, str]] = {
    "checking_comprehension": {
        "tools/use.py": "\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from app import mod\n"
        "    aliases = [module.MISSING for module in "
        "(mod,)]\n"
    },
    "dict_comprehension_overflow": {
        "tests/test_case.py": "\n"
        "from app import mod\n"
        "def test_patch(monkeypatch):\n"
        "    table = {left + right: mod for left in "
        "('0_', '1_', '2_', '3_', '4_', '5_', '6_', "
        "'7_', '8_', '9_', '10_', '11_', '12_', "
        "'13_', '14_', '15_', '16_', '17_', '18_', "
        "'19_', '20_', '21_', '22_', '23_', '24_', "
        "'25_', '26_', '27_', '28_', '29_', '30_', "
        "'31_', '32_', '33_', '34_', '35_', '36_', "
        "'37_', '38_', '39_', '40_', '41_', '42_', "
        "'43_', '44_', '45_', '46_', '47_', '48_', "
        "'49_', '50_', '51_', '52_', '53_', '54_', "
        "'55_', '56_', '57_', '58_', '59_', '60_', "
        "'61_', '62_', '63_', '64_', '65_', '66_', "
        "'67_', '68_', '69_',) for right in ('0_', "
        "'1_', '2_', '3_', '4_', '5_', '6_', '7_', "
        "'8_', '9_', '10_', '11_', '12_', '13_', "
        "'14_', '15_', '16_', '17_', '18_', '19_', "
        "'20_', '21_', '22_', '23_', '24_', '25_', "
        "'26_', '27_', '28_', '29_', '30_', '31_', "
        "'32_', '33_', '34_', '35_', '36_', '37_', "
        "'38_', '39_', '40_', '41_', '42_', '43_', "
        "'44_', '45_', '46_', '47_', '48_', '49_', "
        "'50_', '51_', '52_', '53_', '54_', '55_', "
        "'56_', '57_', '58_', '59_', '60_', '61_', "
        "'62_', '63_', '64_', '65_', '66_', '67_', "
        "'68_', '69_',)}\n"
        "    for name, module in table.items():\n"
        "        monkeypatch.setattr(module, name, "
        "None)\n"
    },
    "dict_comprehension_whole_row_overflow": {
        "app/m0.py": "target = 1\n",
        "app/m1.py": "target = 1\n",
        "app/m10.py": "target = 1\n",
        "app/m11.py": "target = 1\n",
        "app/m12.py": "target = 1\n",
        "app/m13.py": "target = 1\n",
        "app/m14.py": "target = 1\n",
        "app/m15.py": "target = 1\n",
        "app/m16.py": "target = 1\n",
        "app/m17.py": "target = 1\n",
        "app/m18.py": "target = 1\n",
        "app/m19.py": "target = 1\n",
        "app/m2.py": "target = 1\n",
        "app/m20.py": "target = 1\n",
        "app/m21.py": "target = 1\n",
        "app/m22.py": "target = 1\n",
        "app/m23.py": "target = 1\n",
        "app/m24.py": "target = 1\n",
        "app/m25.py": "target = 1\n",
        "app/m26.py": "target = 1\n",
        "app/m27.py": "target = 1\n",
        "app/m28.py": "target = 1\n",
        "app/m29.py": "target = 1\n",
        "app/m3.py": "target = 1\n",
        "app/m30.py": "target = 1\n",
        "app/m31.py": "target = 1\n",
        "app/m32.py": "target = 1\n",
        "app/m33.py": "target = 1\n",
        "app/m34.py": "target = 1\n",
        "app/m35.py": "target = 1\n",
        "app/m36.py": "target = 1\n",
        "app/m37.py": "target = 1\n",
        "app/m38.py": "target = 1\n",
        "app/m39.py": "target = 1\n",
        "app/m4.py": "target = 1\n",
        "app/m40.py": "target = 1\n",
        "app/m41.py": "target = 1\n",
        "app/m42.py": "target = 1\n",
        "app/m43.py": "target = 1\n",
        "app/m44.py": "target = 1\n",
        "app/m45.py": "target = 1\n",
        "app/m46.py": "target = 1\n",
        "app/m47.py": "target = 1\n",
        "app/m48.py": "target = 1\n",
        "app/m49.py": "target = 1\n",
        "app/m5.py": "target = 1\n",
        "app/m50.py": "target = 1\n",
        "app/m51.py": "target = 1\n",
        "app/m52.py": "target = 1\n",
        "app/m53.py": "target = 1\n",
        "app/m54.py": "target = 1\n",
        "app/m55.py": "target = 1\n",
        "app/m56.py": "target = 1\n",
        "app/m57.py": "target = 1\n",
        "app/m58.py": "target = 1\n",
        "app/m59.py": "target = 1\n",
        "app/m6.py": "target = 1\n",
        "app/m60.py": "target = 1\n",
        "app/m61.py": "target = 1\n",
        "app/m62.py": "target = 1\n",
        "app/m63.py": "target = 1\n",
        "app/m64.py": "target = 1\n",
        "app/m65.py": "target = 1\n",
        "app/m66.py": "target = 1\n",
        "app/m67.py": "target = 1\n",
        "app/m68.py": "target = 1\n",
        "app/m69.py": "target = 1\n",
        "app/m7.py": "target = 1\n",
        "app/m8.py": "target = 1\n",
        "app/m9.py": "target = 1\n",
        "tests/test_case.py": "from app import m0, m1, m2, m3, "
        "m4, m5, m6, m7, m8, m9, m10, "
        "m11, m12, m13, m14, m15, m16, "
        "m17, m18, m19, m20, m21, m22, "
        "m23, m24, m25, m26, m27, m28, "
        "m29, m30, m31, m32, m33, m34, "
        "m35, m36, m37, m38, m39, m40, "
        "m41, m42, m43, m44, m45, m46, "
        "m47, m48, m49, m50, m51, m52, "
        "m53, m54, m55, m56, m57, m58, "
        "m59, m60, m61, m62, m63, m64, "
        "m65, m66, m67, m68, m69\n"
        "def test_patch(monkeypatch):\n"
        "    table = {name: module for "
        "name in ('0_', '1_', '2_', '3_', "
        "'4_', '5_', '6_', '7_', '8_', "
        "'9_', '10_', '11_', '12_', "
        "'13_', '14_', '15_', '16_', "
        "'17_', '18_', '19_', '20_', "
        "'21_', '22_', '23_', '24_', "
        "'25_', '26_', '27_', '28_', "
        "'29_', '30_', '31_', '32_', "
        "'33_', '34_', '35_', '36_', "
        "'37_', '38_', '39_', '40_', "
        "'41_', '42_', '43_', '44_', "
        "'45_', '46_', '47_', '48_', "
        "'49_', '50_', '51_', '52_', "
        "'53_', '54_', '55_', '56_', "
        "'57_', '58_', '59_', '60_', "
        "'61_', '62_', '63_', '64_', "
        "'65_', '66_', '67_', '68_', "
        "'69_',) for module in (m0, m1, "
        "m2, m3, m4, m5, m6, m7, m8, m9, "
        "m10, m11, m12, m13, m14, m15, "
        "m16, m17, m18, m19, m20, m21, "
        "m22, m23, m24, m25, m26, m27, "
        "m28, m29, m30, m31, m32, m33, "
        "m34, m35, m36, m37, m38, m39, "
        "m40, m41, m42, m43, m44, m45, "
        "m46, m47, m48, m49, m50, m51, "
        "m52, m53, m54, m55, m56, m57, "
        "m58, m59, m60, m61, m62, m63, "
        "m64, m65, m66, m67, m68, m69,)}\n"
        "    for name, module in "
        "table.items():\n"
        "        "
        "monkeypatch.setattr(module, "
        "name, None)\n",
    },
    "expanded_patch_raising": {
        "tests/test_case.py": "\n"
        "from app import mod\n"
        "def test_patch(monkeypatch):\n"
        "    monkeypatch.setattr(mod, 'target', None, "
        "**{'raising': False})\n"
    },
    "generic_bounds": {
        "tools/use.py": "\n"
        "from app import mod\n"
        "type Alias[T: mod.MISSING] = list[T]\n"
        "def identity[T: mod.MISSING](value: T) -> T: return value\n"
        "class Box[T: mod.MISSING]: pass\n"
    },
    "helper_expanded_overrides_default": {
        "tests/test_case.py": "\n"
        "from app import mod, other\n"
        "def replace(patcher, module=mod, "
        "name='target'):\n"
        "    patcher.setattr(module, name, "
        "None)\n"
        "def test_patch(monkeypatch):\n"
        "    replace(monkeypatch, "
        "**{'module': other, 'name': "
        "'MISSING'})\n"
    },
    "helper_explicit_keywords_positive": {
        "tests/test_case.py": "\n"
        "from app import mod, other\n"
        "def replace(patcher, module=mod, "
        "name='target'):\n"
        "    patcher.setattr(module, name, "
        "None)\n"
        "def test_patch(monkeypatch):\n"
        "    replace(monkeypatch, "
        "module=other, name='other')\n"
    },
    "helper_unknown_expanded_overrides_default": {
        "tests/test_case.py": "\n"
        "from app import mod\n"
        "def replace(patcher, "
        "module=mod, name='target'):\n"
        "    patcher.setattr(module, "
        "name, None)\n"
        "def test_patch(monkeypatch, "
        "request):\n"
        "    replace(monkeypatch, "
        "**request.param)\n"
    },
    "mixed_callable_alias": {
        "tests/test_case.py": "\n"
        "from unittest.mock import patch\n"
        "from app import mod\n"
        "def test_patch():\n"
        "    for replace, target in ((patch, "
        "'app.mod.MISSING'), (patch.object, mod)):\n"
        "        with replace(target, 'target'):\n"
        "            pass\n"
    },
    "nested_scope_rebind": {
        "app/other.py": "def MISSING(): return 2\ndef read(): return MISSING()\n",
        "tests/test_case.py": "\n"
        "from app import mod, other\n"
        "def test_patch(monkeypatch):\n"
        "    module = mod\n"
        "    def replace():\n"
        "        monkeypatch.setattr(module, 'MISSING', "
        "None)\n"
        "    replace()\n"
        "    module = other\n",
    },
    "reload_after_return": {
        "app/mod.py": "def target(): return 1\n",
        "app/user.py": "from app.mod import target\ndef use(): return target()\n",
        "tests/test_case.py": "import importlib\n"
        "from app import mod, user\n"
        "def test_patch(monkeypatch):\n"
        "    monkeypatch.setattr(mod, 'target', None)\n"
        "    user.use()\n"
        "    return\n"
        "    importlib.reload(user)\n",
    },
    "reload_empty_loop": {
        "app/mod.py": "def target(): return 1\n",
        "app/user.py": "from app.mod import target\ndef use(): return target()\n",
        "tests/test_case.py": "import importlib\n"
        "from app import mod, user\n"
        "def test_patch(monkeypatch):\n"
        "    monkeypatch.setattr(mod, 'target', None)\n"
        "    for unused in ():\n"
        "        importlib.reload(user)\n"
        "    user.use()\n",
    },
    "reload_except_only": {
        "app/mod.py": "def target(): return 1\n",
        "app/user.py": "from app.mod import target\ndef use(): return target()\n",
        "tests/test_case.py": "import importlib\n"
        "from app import mod, user\n"
        "def test_patch(monkeypatch):\n"
        "    monkeypatch.setattr(mod, 'target', None)\n"
        "    try:\n"
        "        user.use()\n"
        "    except KeyError:\n"
        "        importlib.reload(user)\n",
    },
    "reload_positive": {
        "app/mod.py": "def target(): return 1\n",
        "app/user.py": "from app.mod import target\ndef use(): return target()\n",
        "tests/test_case.py": "import importlib\n"
        "from app import mod, user\n"
        "def test_patch(monkeypatch):\n"
        "    monkeypatch.setattr(mod, 'target', None)\n"
        "    importlib.reload(user)\n"
        "    user.use()\n",
    },
    "reload_while_false": {
        "app/mod.py": "def target(): return 1\n",
        "app/user.py": "from app.mod import target\ndef use(): return target()\n",
        "tests/test_case.py": "import importlib\n"
        "from app import mod, user\n"
        "def test_patch(monkeypatch):\n"
        "    monkeypatch.setattr(mod, 'target', None)\n"
        "    while False:\n"
        "        importlib.reload(user)\n"
        "    user.use()\n",
    },
    "resolve_typing_context": {
        "tools/use.py": "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from app import mod\n"
        "    Alias = mod.target\n"
        "def use(value: mod.target): pass\n"
    },
    "set_literal_order": {
        "tests/test_case.py": "\n"
        "from app import mod\n"
        "def test_patch(monkeypatch):\n"
        "    for number, name in zip({2, 1}, ('target', "
        "'MISSING')):\n"
        "        if number == 2:\n"
        "            monkeypatch.setattr(mod, name, None)\n"
    },
}


def _index(name: str):
    return _build(CASES[name])


def _targets(name: str):
    return {(t.status, t.module, t.name) for s in _index(name).patch_sites() for t in s.targets}


@pytest.mark.parametrize(
    "case", ["reload_empty_loop", "reload_while_false", "reload_after_return", "reload_except_only"]
)
def test_only_proven_reload_may_exempt_head_copy(case: str) -> None:
    findings = _index(case).patch_findings()
    assert findings["c"] and findings["d"]


def test_reload_positive_keeps_its_proof() -> None:
    findings = _index("reload_positive").patch_findings()
    assert not findings["c"] and not findings["d"]


def test_expanded_arguments_override_defaults() -> None:
    assert _targets("helper_expanded_overrides_default") == {("module", "app.other", "MISSING")}


def test_unknown_expansion_is_not_replaced_with_defaults() -> None:
    assert _index("helper_unknown_expanded_overrides_default").patch_findings()["e"]


def test_explicit_helper_keywords_keep_their_values() -> None:
    assert _targets("helper_explicit_keywords_positive") == {("module", "app.other", "other")}


def test_expanded_false_raising_is_a_rule_b_finding() -> None:
    assert _index("expanded_patch_raising").patch_findings()["b"]


def test_typing_context_reaches_comprehension_iterator() -> None:
    assert any(
        u.module == "app.mod" and u.name == "MISSING"
        for u in _index("checking_comprehension").unresolved()
    )


@pytest.mark.parametrize("position", [0, 1])
def test_public_resolve_matches_typing_references(position: int) -> None:
    index = _index("resolve_typing_context")
    nodes = [
        n
        for n in ast.walk(ast.parse(CASES["resolve_typing_context"]["tools/use.py"]))
        if isinstance(n, ast.Attribute)
    ]
    values = index.resolve("tools/use.py", nodes[position])
    assert {(v.kind, v.ref, v.data) for v in values} == {("def", "app.mod:target", None)}


def test_generic_bounds_are_checked_for_all_definitions() -> None:
    assert {u.line for u in _index("generic_bounds").unresolved() if u.name == "MISSING"} == {
        2,
        3,
        4,
    }


def test_enclosing_function_keeps_its_earlier_binding() -> None:
    assert ("module", "app.mod", "MISSING") in _targets("nested_scope_rebind")


def test_patch_callable_form_stays_paired_with_arguments() -> None:
    assert _targets("mixed_callable_alias") == {
        ("module", "app.mod", "MISSING"),
        ("module", "app.mod", "target"),
    }


@pytest.mark.parametrize(
    "case", ["dict_comprehension_whole_row_overflow", "dict_comprehension_overflow"]
)
def test_whole_row_and_key_overflow_remain_visible(case: str) -> None:
    assert _index(case).patch_findings()["e"]


def test_unordered_set_is_not_taken_as_source_order() -> None:
    findings = _index("set_literal_order").patch_findings()
    assert findings["a"] or findings["e"]


@pytest.mark.parametrize(
    "call",
    [
        "replace(monkeypatch, **{'module': other}, **{'name': 'MISSING'})",
        "replace(monkeypatch, **{'module': other, 'name': 'MISSING'}, unused=1)",
    ],
)
def test_multiple_expansions_keep_their_named_arguments(call: str) -> None:
    index = _build(
        {
            "tests/test_case.py": (
                "from app import mod, other\n"
                "def replace(patcher, module=mod, name='target', **rest):\n"
                "    patcher.setattr(module, name, None)\n"
                "def test_patch(monkeypatch):\n    " + call + "\n"
            )
        }
    )
    assert {(t.module, t.name) for s in index.patch_sites() for t in s.targets} == {
        ("app.other", "MISSING")
    }


@pytest.mark.parametrize(
    "call",
    [
        "monkeypatch.setattr(**{'target': mod, 'name': 'target', 'value': None, 'raising': False})",
        "monkeypatch.setattr(**{'target': 'app.mod.target', 'name': None, 'raising': False})",
        "monkeypatch.delattr(**{'target': 'app.mod.target', 'raising': False})",
    ],
)
def test_expanded_patch_signatures_preserve_false_raising(call: str) -> None:
    index = _build(
        {
            "tests/test_case.py": "from app import mod\ndef test_patch(monkeypatch):\n    "
            + call
            + "\n"
        }
    )
    (site,) = index.patch_sites()
    assert {(t.module, t.name) for t in site.false_targets} == {("app.mod", "target")}
    assert index.patch_findings()["b"]


def test_expanded_raising_stays_paired_with_its_target() -> None:
    index = _build(
        {
            "tests/test_case.py": """
from app import mod
import os
def test_patch(monkeypatch):
    for module, options in ((mod, {'raising': True}), (os, {'raising': False})):
        monkeypatch.setattr(module, 'target', None, **options)
"""
        }
    )
    assert not index.patch_findings()["b"]


@pytest.mark.parametrize(
    "expression", ["sorted({2, 1, 2})", "sorted(set([2, 1, 2]))", "sorted(list({2, 1, 2}))"]
)
def test_sorting_known_sets_establishes_exact_order(expression: str) -> None:
    index = _build(
        {
            "tests/test_case.py": (
                "from app import mod\ndef test_patch(monkeypatch):\n"
                f"    for number, name in zip({expression}, ('MISSING', 'target')):\n"
                "        if number == 2:\n            monkeypatch.setattr(mod, name, None)\n"
            )
        }
    )
    assert {(t.module, t.name) for s in index.patch_sites() for t in s.targets} == {
        ("app.mod", "target")
    }


def test_generic_constraints_defaults_and_parameter_shadowing() -> None:
    source = """from app import mod
type Alias[T: (mod.target, mod.MISSING) = mod.target] = list[T]
def identity[mod](value: mod.MISSING = mod.target) -> mod.MISSING: return value
class Box[T: mod.target = mod.MISSING]: pass
"""
    index = _build({"tools/use.py": source})
    assert {(u.line, u.name) for u in index.unresolved()} == {(2, "MISSING"), (4, "MISSING")}
    default = next(
        n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)
    ).args.defaults[0]
    assert {v.ref for v in index.resolve("tools/use.py", default)} == {"app.mod:target"}


def test_false_return_branch_does_not_block_a_proven_reload() -> None:
    source = CASES["reload_positive"]["tests/test_case.py"].replace(
        "    importlib.reload(user)", "    if False:\n        return\n    importlib.reload(user)"
    )
    index = _build(CASES["reload_positive"] | {"tests/test_case.py": source})
    assert not index.patch_findings()["c"] and not index.patch_findings()["d"]


def test_closure_binding_after_reassignment_is_also_retained() -> None:
    source = CASES["nested_scope_rebind"]["tests/test_case.py"] + "    replace()\n"
    index = _build(CASES["nested_scope_rebind"] | {"tests/test_case.py": source})
    assert {(t.module, t.name) for s in index.patch_sites() for t in s.targets} == {
        ("app.mod", "MISSING"),
        ("app.other", "MISSING"),
    }


def test_filtered_helper_keywords_have_a_complete_known_key_set() -> None:
    index = _build(
        {
            "tests/test_case.py": """from app import mod
def replace(patcher, **off):
    for name, value in off.items():
        patcher.setattr(mod, name, value)
def test_patch(monkeypatch, request):
    table = {'target': None, 'MISSING': None}
    selected = {name: value for name, value in table.items() if name != request.param}
    replace(monkeypatch, **selected)
"""
        }
    )
    assert {(t.module, t.name) for s in index.patch_sites() for t in s.targets} == {
        ("app.mod", "target"),
        ("app.mod", "MISSING"),
    }
    assert index.patch_findings()["a"]
    assert not index.patch_findings()["e"]


def test_optional_known_keyword_keeps_its_default_as_an_alternative() -> None:
    index = _build(
        {
            "tests/test_case.py": """from app import mod
def replace(patcher, name='MISSING'):
    patcher.setattr(mod, name, None)
def test_patch(monkeypatch, request):
    selected = {name: value for name, value in {'name': 'target'}.items() if request.param}
    replace(monkeypatch, **selected)
"""
        }
    )
    assert {(t.module, t.name) for s in index.patch_sites() for t in s.targets} == {
        ("app.mod", "target"),
        ("app.mod", "MISSING"),
    }
    assert index.patch_findings()["a"]


def test_irrelevant_helper_argument_does_not_expand_target_rows() -> None:
    source = """from app import mod
def replace(unused, patcher, name):
    patcher.setattr(mod, name, None)
def test_patch(monkeypatch):
    unused = [left + right for left in VALUES for right in VALUES]
    replace(unused, monkeypatch, 'MISSING')
"""
    source = source.replace("VALUES", repr(tuple(range(70))))
    index = _build({"tests/test_case.py": source})
    assert {(t.module, t.name) for s in index.patch_sites() for t in s.targets} == {
        ("app.mod", "MISSING")
    }
    assert index.patch_findings()["a"]
    assert not index.patch_findings()["e"]


@pytest.mark.parametrize(
    "body",
    [
        "    raise RuntimeError()\n    importlib.reload(user)",
        "    for item in (1,):\n        break\n        importlib.reload(user)",
        "    for item in (1,):\n        continue\n        importlib.reload(user)",
        "    try:\n        user.use()\n    except ValueError:\n"
        "        pass\n    else:\n        importlib.reload(user)",
        "    if request.param:\n        return\n    importlib.reload(user)",
    ],
)
def test_additional_unproven_reload_paths_keep_findings(body: str) -> None:
    source = (
        CASES["reload_positive"]["tests/test_case.py"]
        .replace("def test_patch(monkeypatch):", "def test_patch(monkeypatch, request):")
        .replace("    importlib.reload(user)", body)
    )
    index = _build(CASES["reload_positive"] | {"tests/test_case.py": source})
    assert index.patch_findings()["c"] and index.patch_findings()["d"]


def test_loop_break_does_not_hide_a_reload_after_the_loop() -> None:
    source = CASES["reload_positive"]["tests/test_case.py"].replace(
        "    importlib.reload(user)",
        "    for item in (1,):\n        break\n    importlib.reload(user)",
    )
    index = _build(CASES["reload_positive"] | {"tests/test_case.py": source})
    assert not index.patch_findings()["c"] and not index.patch_findings()["d"]
