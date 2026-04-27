"""Undo/redo stack for editor commands."""

from collections import deque

from .commands import Command
from .markups import MarkupStore


class UndoStack:
    """Applies commands and provides undo/redo."""

    def __init__(self, store: MarkupStore) -> None:
        """Create an undo stack bound to a single ``MarkupStore``."""
        self._store = store
        self._done: deque[Command] = deque()
        self._undone: deque[Command] = deque()

    def push(self, cmd: Command) -> None:
        """Apply ``cmd`` and add it to the done stack."""
        cmd.do(self._store)
        self._done.append(cmd)
        self._undone.clear()

    def undo(self) -> None:
        """Undo the most recent command (if any)."""
        if not self._done:
            return
        cmd = self._done.pop()
        cmd.undo(self._store)
        self._undone.append(cmd)

    def redo(self) -> None:
        """Redo the most recently undone command (if any)."""
        if not self._undone:
            return
        cmd = self._undone.pop()
        cmd.do(self._store)
        self._done.append(cmd)
