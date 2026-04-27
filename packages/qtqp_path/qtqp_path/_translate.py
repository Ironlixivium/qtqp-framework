"""Glob/fnmatch translation helpers — verbatim CPython copies.

_re_setops_sub, _re_escape, and _translate are copied from CPython fnmatch.py (Python 3.14).
magic_check, _special_parts, _no_recurse_symlinks, translate, and _compile_pattern are copied
from CPython glob.py (Python 3.14).

Inlined here so QPath rides Python's OS-layer updates without depending on private imports.
"""
from __future__ import annotations

import functools
import os
import re
from collections.abc import Callable
from typing import cast

# ── verbatim from CPython fnmatch.py ─────────────────────────────────────────

_re_setops_sub: Callable[[str | Callable[[re.Match[str]], str], str], str] = re.compile(r'([&~|])').sub
_re_escape: Callable[[str], str] = cast(Callable[[str], str], functools.lru_cache(maxsize=512)(re.escape))


def _translate(pat: str, star: str, question_mark: str) -> tuple[list[str], list[int]]:
    res: list[str] = []
    add: Callable[[str], None] = res.append
    star_indices: list[int] = []

    pos, pat_len = 0, len(pat)
    while pos < pat_len:
        char = pat[pos]
        pos += 1
        if char == '*':
            star_indices.append(len(res))
            add(star)
            while pos < pat_len and pat[pos] == '*':
                pos += 1
        elif char == '?':
            add(question_mark)
        elif char == '[':
            bracket_end = pos
            if bracket_end < pat_len and pat[bracket_end] == '!':
                bracket_end += 1
            if bracket_end < pat_len and pat[bracket_end] == ']':
                bracket_end += 1
            while bracket_end < pat_len and pat[bracket_end] != ']':
                bracket_end += 1
            if bracket_end >= pat_len:
                add('\\[')
            else:
                stuff = pat[pos:bracket_end]
                if '-' not in stuff:
                    stuff = stuff.replace('\\', r'\\')
                else:
                    chunks: list[str] = []
                    dash_pos = pos + 2 if pat[pos] == '!' else pos + 1
                    while True:
                        dash_pos = pat.find('-', dash_pos, bracket_end)
                        if dash_pos < 0:
                            break
                        chunks.append(pat[pos:dash_pos])
                        pos = dash_pos + 1
                        dash_pos += 3
                    chunk = pat[pos:bracket_end]
                    if chunk:
                        chunks.append(chunk)
                    else:
                        chunks[-1] += '-'
                    for chunk_idx in range(len(chunks) - 1, 0, -1):
                        if chunks[chunk_idx - 1][-1] > chunks[chunk_idx][0]:
                            chunks[chunk_idx - 1] = chunks[chunk_idx - 1][:-1] + chunks[chunk_idx][1:]
                            del chunks[chunk_idx]
                    stuff = '-'.join(
                        s.replace('\\', r'\\').replace('-', r'\-') for s in chunks
                    )
                pos = bracket_end + 1
                if not stuff:
                    add('(?!)')
                elif stuff == '!':
                    add('.')
                else:
                    stuff = _re_setops_sub(r'\\\1', stuff)
                    if stuff[0] == '!':
                        stuff = '^' + stuff[1:]
                    elif stuff[0] in ('^', '['):
                        stuff = '\\' + stuff
                    add(f'[{stuff}]')
        else:
            add(_re_escape(char))
    assert pos == pat_len
    return res, star_indices


# ── verbatim from CPython glob.py ────────────────────────────────────────────

magic_check: re.Pattern[str] = re.compile('([*?[])')
special_parts: tuple[str, str, str] = ('', '.', '..')
no_recurse_symlinks: object = object()


def translate(
    pat: str,
    *,
    recursive: bool = False,
    include_hidden: bool = False,
    seps: str | tuple[str, str] | None = None,
) -> str:
    """Translate a pathname with shell wildcards to a regular expression."""
    _seps: str | tuple[str, str]
    if not seps:
        if os.path.altsep:
            _seps = (os.path.sep, os.path.altsep)
        else:
            _seps = os.path.sep
    else:
        _seps = seps
    escaped_seps = ''.join(map(re.escape, _seps))
    any_sep = f'[{escaped_seps}]' if len(_seps) > 1 else escaped_seps
    not_sep = f'[^{escaped_seps}]'
    if include_hidden:
        one_last_segment = f'{not_sep}+'
        one_segment = f'{one_last_segment}{any_sep}'
        any_segments = f'(?:.+{any_sep})?'
        any_last_segments = '.*'
    else:
        one_last_segment = f'[^{escaped_seps}.]{not_sep}*'
        one_segment = f'{one_last_segment}{any_sep}'
        any_segments = f'(?:{one_segment})*'
        any_last_segments = f'{any_segments}(?:{one_last_segment})?'

    results: list[str] = []
    parts = re.split(any_sep, pat)
    last_part_idx = len(parts) - 1
    for idx, part in enumerate(parts):
        if part == '*':
            results.append(one_segment if idx < last_part_idx else one_last_segment)
        elif recursive and part == '**':
            if idx < last_part_idx:
                if parts[idx + 1] != '**':
                    results.append(any_segments)
            else:
                results.append(any_last_segments)
        else:
            if part:
                if not include_hidden and part[0] in '*?':
                    results.append(r'(?!\.)')
                results.extend(_translate(part, f'{not_sep}*', not_sep)[0])
            if idx < last_part_idx:
                results.append(any_sep)
    res = ''.join(results)
    return fr'(?s:{res})\z'


@functools.lru_cache(maxsize=512)
def compile_pattern(
    pat: str,
    seps: str | tuple[str, str],
    case_sensitive: bool,
    recursive: object = True,
) -> Callable[[str], re.Match[str] | None]:
    flags = re.NOFLAG if case_sensitive else re.IGNORECASE
    regex = translate(pat, recursive=bool(recursive), include_hidden=True, seps=seps)
    return re.compile(regex, flags=flags).match
