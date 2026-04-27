"""QPath-specific glob engine."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any, Protocol

from PySide6.QtCore import QResource

from ._translate import (
    compile_pattern,
    magic_check,
    no_recurse_symlinks,
    special_parts,
)


class _DirEntry(Protocol):
    name: str
    def is_dir(self, *, follow_symlinks: bool = True) -> bool: ...


class _Selector(Protocol):
    def __call__(self, path: str, exists: bool = False) -> Iterator[str]: ...


class _GlobberBase(ABC):
    """Abstract class providing shell-style pattern matching and globbing."""

    def __init__(self, sep: str, case_sensitive: bool, case_pedantic: bool = False, recursive: object = False) -> None:
        self.sep = sep
        self.case_sensitive = case_sensitive
        self.case_pedantic = case_pedantic
        self.recursive = recursive

    @staticmethod
    @abstractmethod
    def lexists(path: str) -> bool: ...

    @staticmethod
    @abstractmethod
    def scandir(path: str) -> Iterator[tuple[_DirEntry, str, str]]: ...

    @staticmethod
    @abstractmethod
    def concat_path(path: str, text: str) -> str: ...

    def compile(self, pat: str, altsep: str | None = None) -> Any:
        seps: tuple[str, str] | str = (self.sep, altsep) if altsep else self.sep
        return compile_pattern(pat, seps, self.case_sensitive, self.recursive)

    def selector(self, parts: list[str]) -> _Selector:
        if not parts:
            return self.select_exists
        part = parts.pop()
        if self.recursive and part == '**':
            selector = self.recursive_selector
        elif part in special_parts:
            selector = self.special_selector
        elif not self.case_pedantic and magic_check.search(part) is None:
            selector = self.literal_selector
        else:
            selector = self.wildcard_selector
        return selector(part, parts)

    def special_selector(self, part: str, parts: list[str]) -> _Selector:
        if parts:
            part += self.sep
        select_next = self.selector(parts)

        def select_special(path: str, exists: bool = False) -> Iterator[str]:
            path = self.concat_path(path, part)
            return select_next(path, exists)
        return select_special

    def literal_selector(self, part: str, parts: list[str]) -> _Selector:
        while parts and magic_check.search(parts[-1]) is None:
            part += self.sep + parts.pop()
        if parts:
            part += self.sep
        select_next = self.selector(parts)

        def select_literal(path: str, exists: bool = False) -> Iterator[str]:
            path = self.concat_path(path, part)
            return select_next(path)
        return select_literal

    def wildcard_selector(self, part: str, parts: list[str]) -> _Selector:
        match = None if part == '*' else self.compile(part)
        dir_only = bool(parts)
        select_next: _Selector = self.selector(parts) if dir_only else self.select_exists

        def select_wildcard(path: str, exists: bool = False) -> Iterator[str]:
            try:
                entries = self.scandir(path)
            except OSError:
                pass
            else:
                for entry, entry_name, entry_path in entries:
                    if match is None or match(entry_name):
                        if dir_only:
                            try:
                                if not entry.is_dir():
                                    continue
                            except OSError:
                                continue
                            entry_path = self.concat_path(entry_path, self.sep)
                            yield from select_next(entry_path, exists=True)
                        else:
                            yield entry_path
        return select_wildcard

    def recursive_selector(self, part: str, parts: list[str]) -> _Selector:
        while parts and parts[-1] == '**':
            parts.pop()

        follow_symlinks = self.recursive is not no_recurse_symlinks
        if follow_symlinks:
            while parts and parts[-1] not in special_parts:
                part += self.sep + parts.pop()

        match = None if part == '**' else self.compile(part)
        dir_only = bool(parts)
        select_next = self.selector(parts)

        def select_recursive(path: str, exists: bool = False) -> Iterator[str]:
            match_pos = len(path)
            if match is None or match(path, match_pos):
                yield from select_next(path, exists)
            stack = [path]
            while stack:
                yield from select_recursive_step(stack, match_pos)

        def select_recursive_step(stack: list[str], match_pos: int) -> Iterator[str]:
            path = stack.pop()
            try:
                entries = self.scandir(path)
            except OSError:
                pass
            else:
                for entry, _entry_name, entry_path in entries:
                    is_dir = False
                    try:
                        if entry.is_dir(follow_symlinks=follow_symlinks):
                            is_dir = True
                    except OSError:
                        pass
                    if is_dir or not dir_only:
                        entry_path_str = str(entry_path)
                        if dir_only:
                            entry_path = self.concat_path(entry_path, self.sep)
                        if match is None or match(entry_path_str, match_pos):
                            if dir_only:
                                yield from select_next(entry_path, exists=True)
                            else:
                                yield entry_path
                        if is_dir:
                            stack.append(entry_path)

        return select_recursive

    def select_exists(self, path: str, exists: bool = False) -> Iterator[str]:
        if exists:
            yield path
        elif self.lexists(path):
            yield path


def _parse_pattern(pattern: str, sep: str) -> list[str]:
    """Split a relative glob pattern into parts for the selector chain."""
    if sep != "/" and "/" in pattern:
        pattern = pattern.replace("/", sep)
    parts = [x for x in pattern.split(sep) if x and x != "."]
    if not parts:
        raise ValueError(f"Unacceptable pattern: {pattern!r}")
    if pattern.endswith(sep):
        parts.append('')
    return parts


class _QRCEntry:
    """Minimal DirEntry-like wrapper for QRC resource children."""
    __slots__ = ("_path", "name")

    def __init__(self, path: str, name: str) -> None:
        self._path = path
        self.name = name

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        return QResource(self._path).isDir()


def glob_qpath(
    root: str,
    pattern: str,
    *,
    sep: str,
    case_sensitive: bool,
    case_pedantic: bool,
    recurse_symlinks: bool,
) -> Iterator[str]:
    """Run the glob engine over a QPath root, yielding matching path strings."""
    parts = _parse_pattern(pattern, sep)
    recursive = True if recurse_symlinks else no_recurse_symlinks
    globber = _QPathGlobber(sep, case_sensitive, case_pedantic, recursive)
    select = globber.selector(parts[::-1])
    for p in select(root + sep):
        yield p.rstrip(sep) if p.endswith(sep) and len(p) > len(sep) else p


class _QPathGlobber(_GlobberBase):
    """Glob engine for QPath — dispatches to os or QResource by path prefix."""

    @staticmethod
    def concat_path(path: str, text: str) -> str:
        return path + text

    @staticmethod
    def lexists(path: str) -> bool:
        if path.startswith(":/"):
            return QResource(path.rstrip("/")).isValid()
        return os.path.lexists(path)

    @staticmethod
    def scandir(path: str):  # type: ignore[override]
        if path.startswith(":/"):
            base = path.rstrip("/")
            children = QResource(base).children()
            return iter([
                (_QRCEntry(f"{base}/{name}", name), name, f"{base}/{name}")
                for name in children
            ])
        with os.scandir(path) as it:
            entries = list(it)
        return ((e, e.name, e.path) for e in entries)
