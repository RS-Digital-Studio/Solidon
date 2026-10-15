"""Gegenbeispiele der ersten Durchsicht des statischen Auflösers (R-01 bis R-13)."""

from __future__ import annotations

import ast
import pickle
from pathlib import Path

import pytest

from tests.code_index_helpers import build_index as _build
from tools import code_facts
from tools.code_index import CACHE, Index

CASES: dict[str, dict[str, str]] = {}


def _case(name: str, sources: dict[str, str]) -> None:
    CASES[name] = sources


def _index(case: str) -> Index:
    return _build(CASES[case])


def _names(case: str) -> set[tuple[str, str, str | None]]:
    return {
        (target.status, target.module, target.name)
        for site in _index(case).patch_sites()
        for target in site.targets
    }


_case(
    "checking_alias",
    {
        "tools/use.py": """
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import mod
    Alias = mod.MISSING
"""
    },
)

_case(
    "checking_attribute",
    {
        "app/mod.py": (
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    class Hidden: pass\n"
        ),
        "tools/use.py": """
from typing import TYPE_CHECKING
from app import mod
if TYPE_CHECKING:
    Alias = mod.Hidden
""",
    },
)

_case(
    "annotations",
    {
        "tools/use.py": """
from app import mod
value: mod.MISSING = None
def use(item: mod.MISSING) -> mod.MISSING:
    pass
type Alias = mod.MISSING
"""
    },
)

_case(
    "type_only_reader",
    {
        "app/mod.py": """
from typing import TYPE_CHECKING
def target():
    return 1
if TYPE_CHECKING:
    def use():
        return target()
""",
        "tests/test_case.py": """
from app import mod
def test_use(monkeypatch):
    monkeypatch.setattr(mod, 'target', None)
""",
    },
)

_case(
    "lazy_same_name",
    {
        "app/lazy.py": "def install(*args): pass\n",
        "app/pkg/__init__.py": """
from app.lazy import install
_EXPORTS = {'target': ('target', 'target')}
install(__name__, _EXPORTS)
""",
        "app/pkg/target.py": "def target(): return 1\ndef own(): return target()\n",
        "app/user.py": "from app.pkg import target\ndef use(): return target()\n",
        "tests/test_case.py": """
import app.pkg.target as source
def test_patch(monkeypatch):
    monkeypatch.setattr(source, 'target', None)
""",
    },
)

_case(
    "reload_after_context",
    {
        "app/mod.py": "def target(): return 1\n",
        "app/user.py": "from app.mod import target\ndef use(): return target()\n",
        "tests/test_case.py": """
from unittest.mock import patch
import importlib
from app import mod, user
def test_patch():
    with patch.object(mod, 'target', None):
        user.use()
    importlib.reload(user)
""",
    },
)

_case(
    "reload_unrelated_branch",
    {
        "app/mod.py": "def target(): return 1\n",
        "app/user.py": "from app.mod import target\ndef use(): return target()\n",
        "tests/test_case.py": """
import importlib
from app import mod, user
def test_patch(monkeypatch):
    monkeypatch.setattr(mod, 'target', None)
    if False:
        importlib.reload(user)
    user.use()
""",
    },
)

_case(
    "raising_positional",
    {
        "tests/test_case.py": """
from app import mod
def test_patch(monkeypatch):
    monkeypatch.setattr(mod, 'target', None, False)
    monkeypatch.delattr(mod, 'target', False)
"""
    },
)

_case(
    "raising_folded",
    {
        "tests/test_case.py": """
from app import mod
def test_patch(monkeypatch):
    for raising in (True, False):
        monkeypatch.setattr(mod, 'target', None, raising=raising)
"""
    },
)

_case(
    "patch_alias",
    {
        "tests/test_case.py": """
from unittest.mock import patch as replace
from app import mod
def test_patch():
    with replace('app.mod.MISSING', None):
        pass
    with replace.object(mod, 'MISSING', None):
        pass
"""
    },
)

_case(
    "helper_defaults",
    {
        "tests/test_case.py": """
from app import mod, other
def replace(patcher, module=mod, name='target'):
    patcher.setattr(module, name, None)
def test_patch(monkeypatch):
    replace(monkeypatch, other, 'other')
"""
    },
)

_case(
    "helper_local_import",
    {
        "tests/helper.py": (
            "def replace(patcher, module, name):\n    patcher.setattr(module, name, None)\n"
        ),
        "tests/test_case.py": """
from app import mod
def test_patch(monkeypatch):
    from tests.helper import replace
    replace(monkeypatch, mod, 'target')
""",
    },
)

_case(
    "helper_named_kwargs",
    {
        "tests/test_case.py": """
from app import mod
def replace(patcher, module, name):
    patcher.setattr(module, name, None)
def test_patch(monkeypatch):
    replace(monkeypatch, **{'module': mod, 'name': 'target'})
"""
    },
)

_case(
    "late_delete",
    {
        "app/mod.py": "def target(): return 1\ndel target\n",
        "tools/use.py": "from app.mod import target\n",
        "tests/test_case.py": (
            "from app import mod\ndef test_patch(monkeypatch):\n"
            '    monkeypatch.setattr(mod, "target", None)\n'
        ),
    },
)

_case(
    "module_rebind",
    {
        "app/user.py": """
from app import other as module
from app import mod as module
def use():
    return module.target()
""",
        "tests/test_case.py": """
from app.user import module
def test_patch(monkeypatch):
    monkeypatch.setattr(module, 'target', None)
""",
    },
)

_case(
    "nonlocal_rebind",
    {
        "tools/use.py": """
from app import mod, other
def make():
    selected = mod
    def change():
        nonlocal selected
        selected = other
    def read():
        return selected.other()
    change()
    return read()
"""
    },
)

_case(
    "unknown_module_binding",
    {
        "app/config.py": """
import importlib
module = importlib.import_module('app.{}'.format('mod'))
""",
        "tests/test_case.py": """
from app.config import module
def test_patch(monkeypatch):
    monkeypatch.setattr(module, 'MISSING', None, raising=False)
""",
    },
)

_case(
    "numeric_sort",
    {
        "tests/test_case.py": """
from app import mod
def test_patch(monkeypatch):
    names = ['target', 'MISSING']
    for position, name in zip(sorted((2, 10)), names):
        if position == 2:
            monkeypatch.setattr(mod, name, None)
"""
    },
)

_case(
    "enumerate_start",
    {
        "tests/test_case.py": """
from app import mod
def test_patch(monkeypatch):
    for position, name in enumerate(('MISSING', 'target'), start=1):
        if position == 1:
            monkeypatch.setattr(mod, name, None)
"""
    },
)

items = ", ".join(repr("name_" + str(i)) for i in range(70))

_case(
    "open_zip_limit",
    {
        "app/mod.py": "\n".join(f"name_{i} = {i}" for i in range(69))
        + "\ndef read():\n    return ("
        + ", ".join(f"name_{i}" for i in range(69))
        + ")\n",
        "tests/test_case.py": f"""
from app import mod
def test_patch(monkeypatch):
    left = [name for name in ({items},)]
    right = [name for name in ({items},)]
    for first, second in zip(left, right):
        if first == 'name_69':
            monkeypatch.setattr(mod, first, None)
""",
    },
)


def test_mock_patch_aliases_count() -> None:
    assert len(_index("patch_alias").patch_sites()) == 2


def test_unknown_module_binding_stays_unresolved() -> None:
    assert _index("unknown_module_binding").patch_findings()["e"]


def test_lazy_export_wins_over_same_named_submodule_for_head_copies() -> None:
    assert any(copy.holder == "app.user" for copy in _index("lazy_same_name").head_copies())


@pytest.mark.parametrize("case", ["reload_after_context", "reload_unrelated_branch"])
def test_reload_must_act_while_the_patch_is_active(case: str) -> None:
    findings = _index(case).patch_findings()
    assert findings["c"] and findings["d"]


def test_type_checking_aliases_still_resolve_for_w5() -> None:
    assert _index("checking_alias").unresolved()


def test_type_checking_attribute_exists_for_the_type_checker() -> None:
    assert not _index("checking_attribute").unresolved()


def test_type_only_function_is_not_a_runtime_reader() -> None:
    assert _index("type_only_reader").patch_findings()["d"]


def test_annotation_and_type_alias_references_are_checked() -> None:
    assert len(_index("annotations").unresolved()) >= 3


@pytest.mark.parametrize("case", ["raising_positional", "raising_folded"])
def test_every_false_raising_value_is_rejected(case: str) -> None:
    assert _index(case).patch_findings()["b"]


def test_helper_defaults_only_apply_to_omitted_arguments() -> None:
    assert _names("helper_defaults") == {("module", "app.other", "other")}


def test_module_alias_rebinding_kills_the_previous_binding() -> None:
    assert _names("module_rebind") == {("module", "app.mod", "target")}


def test_deleted_module_name_does_not_exist() -> None:
    index = _index("late_delete")
    assert index.unresolved()
    assert index.patch_findings()["a"]


def test_sorted_numbers_keep_python_order() -> None:
    assert _names("numeric_sort") == {("module", "app.mod", "target")}


def test_enumerate_start_is_respected() -> None:
    assert _names("enumerate_start") == {("module", "app.mod", "MISSING")}


def test_row_limit_is_unknown_instead_of_truncated_targets() -> None:
    assert _index("open_zip_limit").patch_findings()["e"]


def test_resolve_can_fold_a_comprehension_like_its_bound_name() -> None:
    source = (
        "from app import mod, other\ndef use():\n"
        "    modules = [module for module in (mod, other)]\n    return modules\n"
    )
    index = _build({"tools/use.py": source})
    tree = ast.parse(source)
    comp = next(node for node in ast.walk(tree) if isinstance(node, ast.ListComp))
    use = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "modules" and isinstance(node.ctx, ast.Load)
    )
    assert index.resolve("tools/use.py", comp) == index.resolve("tools/use.py", use)


def _cache_root(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app/__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    cache = tmp_path / CACHE
    cache.parent.mkdir(parents=True)
    return cache


def test_stale_class_cache_does_not_prevent_rebuild(tmp_path: Path) -> None:
    cache = _cache_root(tmp_path)
    # Ein globaler Name des alten Pickle-Schemas existiert heute nicht mehr.
    cache.write_bytes(b"ctools.code_facts\nRetiredIR\n.")
    assert Index.build(tmp_path).exists("app", "VALUE")


class _CacheCallback:
    def __reduce__(self):
        return print, ("REVIEW_CACHE_CALLBACK_EXECUTED",)


def test_cache_from_an_analyzed_tree_cannot_execute_callbacks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = _cache_root(tmp_path)
    cache.write_bytes(pickle.dumps({"stamp": "old", "files": _CacheCallback()}))
    assert Index.build(tmp_path).exists("app", "VALUE")
    assert "REVIEW_CACHE_CALLBACK_EXECUTED" not in capsys.readouterr().out


def test_false_raising_targets_stay_paired_with_their_own_row() -> None:
    index = _build(
        {
            "tests/test_case.py": """
        import os
        from app import mod
        def test_patch(monkeypatch):
            for module, raising in ((mod, True), (os, False)):
                monkeypatch.setattr(module, "target", None, raising=raising)
    """
        }
    )
    assert not index.patch_findings()["b"]
    (site,) = index.patch_sites()
    assert {target.module for target in site.false_targets} == {"os"}


@pytest.mark.parametrize(
    "reload_code",
    [
        "importlib.reload(user)",
        "if True:\n        importlib.reload(user)",
    ],
)
def test_an_active_unconditional_reload_keeps_its_positive_proof(reload_code: str) -> None:
    source = (
        "import importlib\nfrom unittest.mock import patch\nfrom app import mod, user\n"
        "def test_patch():\n    with patch.object(mod, 'target', None):\n        "
        + reload_code.replace("\n", "\n    ")
        + "\n        user.use()\n"
    )
    extra = CASES["reload_after_context"] | {"tests/test_case.py": source}
    findings = _build(extra).patch_findings()
    assert not findings["c"] and not findings["d"]


@pytest.mark.parametrize(
    "reload_code",
    [
        "monkeypatch.undo()\n    importlib.reload(user)",
        "if unknown():\n        importlib.reload(user)",
        "def reload(module): pass\n    reload(user)",
    ],
)
def test_unproved_or_ended_reload_does_not_free_the_patch(reload_code: str) -> None:
    extra = CASES["reload_unrelated_branch"] | {
        "tests/test_case.py": (
            "import importlib\nfrom app import mod, user\ndef test_patch(monkeypatch):\n"
            "    monkeypatch.setattr(mod, 'target', None)\n    " + reload_code + "\n"
        )
    }
    findings = _build(extra).patch_findings()
    assert findings["c"] and findings["d"]


def test_constructing_a_patcher_does_not_activate_it_for_reload() -> None:
    extra = CASES["reload_after_context"] | {
        "tests/test_case.py": (
            "import importlib\nfrom unittest.mock import patch\nfrom app import mod, user\n"
            "def test_patch():\n    patch.object(mod, 'target', None)\n"
            "    importlib.reload(user)\n    user.use()\n"
        )
    }
    findings = _build(extra).patch_findings()
    assert findings["c"] and findings["d"]


def test_patch_aliases_can_be_bound_by_an_assignment() -> None:
    index = _build(
        {
            "tests/test_case.py": """
        from unittest import mock
        from app import mod
        def test_patch():
            replace = mock.patch
            with replace.object(mod, "MISSING", None):
                pass
    """
        }
    )
    assert len(index.patch_sites()) == 1
    assert index.patch_findings()["a"]


def test_valid_annotations_are_references_but_not_runtime_readers() -> None:
    index = _build(
        {
            "app/mod.py": "class Target: pass\n",
            "tools/use.py": """
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                from app import mod
            value: mod.Target = None
            def use(item: mod.Target) -> mod.Target:
                pass
            type Alias = mod.Target
        """,
        }
    )
    assert not index.unresolved()
    references = index.references("app.mod", "Target")
    assert len(references) == 4 and all(ref.checking for ref in references)
    assert not index.readers("app.mod", "Target")


def test_helper_defaults_are_bound_for_each_call_separately() -> None:
    index = _build(
        {
            "tests/test_case.py": """
        from app import mod, other
        def replace(patcher, module=mod, name="target"):
            patcher.setattr(module, name, None)
        def test_patch(monkeypatch):
            replace(monkeypatch)
            replace(monkeypatch, other, "other")
    """
        }
    )
    (site,) = index.patch_sites()
    assert {(target.module, target.name) for target in site.targets} == {
        ("app.mod", "target"),
        ("app.other", "other"),
    }
    assert not index.patch_findings()["a"]


def test_later_global_writers_remain_possible_after_import_rebinding() -> None:
    index = _build(
        {
            "app/user.py": """
            from app import mod, other
            module = other
            def change():
                global module
                module = other
            module = mod
        """,
            "tests/test_case.py": """
            from app.user import module
            def test_patch(monkeypatch):
                monkeypatch.setattr(module, "target", None)
        """,
        }
    )
    (site,) = index.patch_sites()
    assert {target.module for target in site.targets} == {"app.mod", "app.other"}


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("enumerate(('MISSING', 'target'), 1)", "MISSING"),
        ("zip(sorted((2, 10), reverse=True), ('MISSING', 'target'))", "target"),
    ],
)
def test_supported_sequence_signatures_keep_their_order(expression: str, expected: str) -> None:
    index = _build(
        {
            "tests/test_case.py": (
                "from app import mod\ndef test_patch(monkeypatch):\n"
                f"    for position, name in {expression}:\n"
                f"        if position == {1 if expression.startswith('enumerate') else 2}:\n"
                "            monkeypatch.setattr(mod, name, None)\n"
            )
        }
    )
    (site,) = index.patch_sites()
    assert {target.name for target in site.targets} == {expected}


@pytest.mark.parametrize(
    "expression",
    [
        "sorted(('target', 'MISSING'), key=unknown)",
        "enumerate(('target',), start=unknown)",
    ],
)
def test_unsupported_sequence_signatures_remain_unknown(expression: str) -> None:
    index = _build(
        {
            "tests/test_case.py": (
                "from app import mod\ndef test_patch(monkeypatch):\n"
                f"    for name in {expression}:\n"
                "        monkeypatch.setattr(mod, name, None)\n"
            )
        }
    )
    assert index.patch_findings()["e"]


def test_damaged_current_cache_is_rebuilt(tmp_path: Path) -> None:
    from tools.code_cache import MAGIC

    cache = _cache_root(tmp_path)
    cache.write_bytes(MAGIC + code_facts.stamp().encode("ascii") + b"\ninvalid-marshal")
    assert Index.build(tmp_path).exists("app", "VALUE")


def test_overwritten_imports_do_not_remain_head_copies() -> None:
    index = _build(
        {
            "app/user.py": (
                "from app.mod import target\nfrom app.other import other as target\n"
                "def use(): return target()\n"
            )
        }
    )
    copies = [copy for copy in index.head_copies() if copy.holder == "app.user"]
    assert [(copy.module, copy.name) for copy in copies] == [("app.other", "other")]
