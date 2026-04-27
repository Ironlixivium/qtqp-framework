"""Undoable command objects for annotation changes."""

from dataclasses import dataclass
from typing import Protocol

from .markups import Markup, MarkupStore


class Command(Protocol):
    """Undoable operation against a ``MarkupStore``."""

    def do(self, store: MarkupStore) -> None:
        """Apply the command."""
        ...

    def undo(self, store: MarkupStore) -> None:
        """Revert the command."""
        ...


@dataclass(frozen=True, slots=True)
class AddMarkupCommand:
    """Command that adds a markup to the store."""

    markup: Markup

    def do(self, store: MarkupStore) -> None:
        """Add the markup."""
        store.add(self.markup)

    def undo(self, store: MarkupStore) -> None:
        """Remove the markup by id."""
        store.remove(self.markup.id)


@dataclass(frozen=True, slots=True)
class RemoveMarkupCommand:
    """Command that removes a markup from the store."""

    markup: Markup

    def do(self, store: MarkupStore) -> None:
        """Remove the markup by id."""
        store.remove(self.markup.id)

    def undo(self, store: MarkupStore) -> None:
        """Re-add the markup."""
        store.add(self.markup)


@dataclass(frozen=True, slots=True)
class UpdateMarkupCommand:
    """Command that replaces one markup with another."""

    before: Markup
    after: Markup

    def do(self, store: MarkupStore) -> None:
        """Update to the new markup."""
        store.update(self.after)

    def undo(self, store: MarkupStore) -> None:
        """Restore the previous markup."""
        store.update(self.before)
