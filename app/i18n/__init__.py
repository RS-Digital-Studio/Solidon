"""Translation without Qt.

Operations, parts and errors are declared at import time, long before a language
is chosen, so ``_()`` must not translate eagerly. It returns a lazy
:class:`TranslatableText` that resolves when the text is actually displayed
(Bauplan §4.1, AGENTS.md rule 20).

The core produces translatable texts; only the surface resolves them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Languages the application ships with. German is the source language.
SOURCE_LANGUAGE: Final = "de"
SUPPORTED_LANGUAGES: Final = ("de", "en")

_catalogs: dict[str, dict[str, str]] = {}
_language: str = SOURCE_LANGUAGE


@dataclass(frozen=True, slots=True)
class TranslatableText:
    """A text that carries its own translation key.

    Comparison and hashing use the message id, so registry consistency checks can
    treat these like strings without resolving them.
    """

    msgid: str
    context: str | None = None

    def translate(self, language: str | None = None) -> str:
        """Resolve against the active catalog, falling back to the message id."""
        catalog = _catalogs.get(language or _language, {})
        return catalog.get(self._key(), self.msgid)

    def _key(self) -> str:
        return f"{self.context}\x04{self.msgid}" if self.context else self.msgid

    def __str__(self) -> str:
        return self.translate()


def _(msgid: str, context: str | None = None) -> TranslatableText:
    """Mark a text for translation. The canonical name in declarations."""
    return TranslatableText(msgid, context)


def tr(msgid: str, context: str | None = None) -> str:
    """Translate immediately. For surfaces that need a plain string right now."""
    return TranslatableText(msgid, context).translate()


def set_language(language: str) -> None:
    """Switch the active language. Unknown languages fall back to the message id."""
    global _language
    _language = language


def get_language() -> str:
    return _language


def install_catalog(language: str, catalog: dict[str, str]) -> None:
    """Register (or extend) the catalog for one language."""
    _catalogs.setdefault(language, {}).update(catalog)


def known_languages() -> tuple[str, ...]:
    """Languages that have a catalog installed, plus the source language."""
    return tuple(dict.fromkeys((SOURCE_LANGUAGE, *sorted(_catalogs))))
