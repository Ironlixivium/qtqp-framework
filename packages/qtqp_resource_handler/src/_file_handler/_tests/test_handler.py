"""Tests for ResourceBytesIO — sync I/O, filtering, path resolution, and Hypothesis completeness."""
from __future__ import annotations

import shutil
import string
import tempfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from PySide6.QtWidgets import QApplication
from qtqp.path import QPath

from qtqp.resource_handler._file_handler._handler import ResourceBytesIO

_FNAME = (
    st.text(alphabet=string.ascii_letters + string.digits + "_", min_size=1, max_size=20)
    .filter(lambda s: s not in (".", ".."))
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def handler(qt_app: QApplication, tmp_path: Path) -> ResourceBytesIO:
    h = ResourceBytesIO()
    h.app_dir = QPath(str(tmp_path)).resolve()
    h._read_dirs = (h.app_dir, h.cwd)  # type: ignore[reportPrivateUsage]
    return h


@pytest.fixture()
def file_tree(tmp_path: Path) -> Path:
    (tmp_path / "a.txt").write_bytes(b"a")
    (tmp_path / "b.pdf").write_bytes(b"b")
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "d.png").write_bytes(b"d")
    excl = tmp_path / "excluded"
    excl.mkdir()
    (excl / "c.txt").write_bytes(b"c")
    return tmp_path


# ── list_files ────────────────────────────────────────────────────────────────

class TestListFiles:
    def test_returns_all_files_by_default(
        self,
        handler: ResourceBytesIO,
        file_tree: Path,
        qt_app: QApplication,
    ) -> None:
        scope = QPath(str(file_tree))
        result = handler.list_files((scope,))
        names = {p.name for p in result}
        assert "a.txt" in names
        assert "b.pdf" in names
        assert "c.txt" in names
        assert "d.png" in names

    def test_extension_whitelist(self, handler: ResourceBytesIO, file_tree: Path, qt_app: QApplication) -> None:
        scope = QPath(str(file_tree))
        result = handler.list_files((scope,), extensions=(".txt",))
        names = {p.name for p in result}
        assert "a.txt" in names
        assert "c.txt" in names
        assert "b.pdf" not in names
        assert "d.png" not in names

    def test_extension_blacklist(self, handler: ResourceBytesIO, file_tree: Path, qt_app: QApplication) -> None:
        scope = QPath(str(file_tree))
        result = handler.list_files((scope,), excluded_extensions=(".pdf",))
        names = {p.name for p in result}
        assert "b.pdf" not in names
        assert "a.txt" in names

    def test_directory_blacklist(self, handler: ResourceBytesIO, file_tree: Path, qt_app: QApplication) -> None:
        scope = QPath(str(file_tree))
        result = handler.list_files((scope,), excluded_directories=("excluded",))
        paths_str = {str(p) for p in result}
        assert not any("excluded" in s for s in paths_str)
        assert any("a.txt" in s for s in paths_str)

    def test_directory_blacklist_also_skips_sub(
        self,
        handler: ResourceBytesIO,
        file_tree: Path,
        qt_app: QApplication,
    ) -> None:
        scope = QPath(str(file_tree))
        result = handler.list_files((scope,), excluded_directories=("sub",))
        names = {p.name for p in result}
        assert "d.png" not in names

    def test_mode_disk_skips_qrc_scopes(self, handler: ResourceBytesIO, file_tree: Path, qt_app: QApplication) -> None:
        disk_scope = QPath(str(file_tree))
        qrc_scope = QPath(":/res")
        result = handler.list_files((disk_scope, qrc_scope), mode="disk")
        assert all(p.is_disk for p in result)

    def test_mode_qrc_skips_disk_scopes(self, handler: ResourceBytesIO, file_tree: Path, qt_app: QApplication) -> None:
        disk_scope = QPath(str(file_tree))
        result = handler.list_files((disk_scope,), mode="qrc")
        assert result == []

    def test_empty_scopes_returns_empty(self, handler: ResourceBytesIO, qt_app: QApplication) -> None:
        assert handler.list_files(()) == []

    def test_result_sorted_by_posix_lower(
        self,
        handler: ResourceBytesIO,
        file_tree: Path,
        qt_app: QApplication,
    ) -> None:
        scope = QPath(str(file_tree))
        result = handler.list_files((scope,))
        posix_names = [p.as_posix().lower() for p in result]
        assert posix_names == sorted(posix_names)

    def test_whitelist_and_blacklist_combined(
        self,
        handler: ResourceBytesIO,
        file_tree: Path,
        qt_app: QApplication,
    ) -> None:
        scope = QPath(str(file_tree))
        result = handler.list_files((scope,), extensions=(".txt",), excluded_directories=("excluded",))
        names = {p.name for p in result}
        assert names == {"a.txt"}

    def test_multiple_scopes_concatenated(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "file_a.txt").write_bytes(b"")
        (dir_b / "file_b.txt").write_bytes(b"")
        scope_a = QPath(str(dir_a))
        scope_b = QPath(str(dir_b))
        result = handler.list_files((scope_a, scope_b))
        names = {p.name for p in result}
        assert "file_a.txt" in names
        assert "file_b.txt" in names


# ── read_bytes ────────────────────────────────────────────────────────────────

class TestReadBytes:
    def test_reads_absolute_file(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"\xde\xad\xbe\xef")
        result = handler.read_bytes(QPath(str(f)))
        assert result == b"\xde\xad\xbe\xef"

    def test_absolute_missing_raises_file_not_found(self, handler: ResourceBytesIO, qt_app: QApplication) -> None:
        with pytest.raises(FileNotFoundError):
            handler.read_bytes(QPath("/this/path/does/not/exist_xyz.txt"))

    def test_reads_relative_from_app_dir(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        (tmp_path / "config.txt").write_bytes(b"cfg-data")
        result = handler.read_bytes(QPath("config.txt"))
        assert result == b"cfg-data"

    def test_relative_missing_raises_file_not_found(self, handler: ResourceBytesIO, qt_app: QApplication) -> None:
        with pytest.raises(FileNotFoundError):
            handler.read_bytes(QPath("definitely_missing_xyzabc.txt"))

    def test_reads_empty_file(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        assert handler.read_bytes(QPath(str(f))) == b""

    def test_reads_large_file(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        data = b"x" * 100_000
        f = tmp_path / "large.bin"
        f.write_bytes(data)
        assert handler.read_bytes(QPath(str(f))) == data


# ── write_bytes ───────────────────────────────────────────────────────────────

class TestWriteBytes:
    def test_creates_file(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        dest = QPath(str(tmp_path / "output.txt"))
        out = handler.write_bytes(dest, b"hello")
        assert out.exists()
        assert out.read_bytes() == b"hello"

    def test_creates_parent_dirs(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        dest = QPath(str(tmp_path / "a" / "b" / "file.txt"))
        out = handler.write_bytes(dest, b"nested")
        assert out.read_bytes() == b"nested"

    def test_raises_file_exists_no_overwrite(
        self,
        handler: ResourceBytesIO,
        tmp_path: Path,
        qt_app: QApplication,
    ) -> None:
        dest = QPath(str(tmp_path / "existing.txt"))
        dest.write_bytes(b"original")
        with pytest.raises(FileExistsError):
            handler.write_bytes(dest, b"new", overwrite=False)

    def test_file_unchanged_after_failed_overwrite(
        self,
        handler: ResourceBytesIO,
        tmp_path: Path,
        qt_app: QApplication,
    ) -> None:
        dest = QPath(str(tmp_path / "original.txt"))
        dest.write_bytes(b"keep-me")
        try:
            handler.write_bytes(dest, b"discard", overwrite=False)
        except FileExistsError:
            pass
        assert dest.read_bytes() == b"keep-me"

    def test_overwrites_when_allowed(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        dest = QPath(str(tmp_path / "overwrite.txt"))
        dest.write_bytes(b"old")
        out = handler.write_bytes(dest, b"new", overwrite=True)
        assert out.read_bytes() == b"new"

    def test_relative_path_with_out_dir(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        out_dir = QPath(str(tmp_path / "output"))
        out_dir.os_mkdir()
        out = handler.write_bytes(QPath("result.txt"), b"data", out_dir=out_dir)
        assert out.is_relative_to(out_dir.resolve())
        assert out.read_bytes() == b"data"

    def test_returns_qpath(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        dest = QPath(str(tmp_path / "typed.txt"))
        out = handler.write_bytes(dest, b"")
        assert isinstance(out, QPath)


# ── _resolve_disk_path ────────────────────────────────────────────────────────

class TestResolveDiskPath:
    def test_existing_absolute_resolves(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        f = tmp_path / "exists.txt"
        f.write_bytes(b"")
        resolved = handler._resolve_disk_path(QPath(str(f)))  # type: ignore[reportPrivateUsage]
        assert resolved.exists()
        assert resolved.is_absolute()

    def test_nonexistent_absolute_raises(self, handler: ResourceBytesIO, qt_app: QApplication) -> None:
        with pytest.raises(FileNotFoundError):
            handler._resolve_disk_path(QPath("/this/cannot/possibly/exist_xyz.txt"))  # type: ignore[reportPrivateUsage]

    def test_relative_found_in_app_dir(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        (tmp_path / "found.txt").write_bytes(b"")
        result = handler._resolve_disk_path(QPath("found.txt"))  # type: ignore[reportPrivateUsage]
        assert result.name == "found.txt"
        assert result.is_absolute()

    def test_relative_missing_raises_with_tried_paths(self, handler: ResourceBytesIO, qt_app: QApplication) -> None:
        with pytest.raises(FileNotFoundError, match="Tried"):
            handler._resolve_disk_path(QPath("missing_file_xyzabc.txt"))  # type: ignore[reportPrivateUsage]


# ── _resolve_write_path ───────────────────────────────────────────────────────

class TestResolveWritePath:
    def test_absolute_path_resolves(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        p = QPath(str(tmp_path / "out.txt"))
        result = handler._resolve_write_path(p)  # type: ignore[reportPrivateUsage]
        assert result == p.resolve()

    def test_relative_with_out_dir(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        out_dir = QPath(str(tmp_path / "custom_out"))
        result = handler._resolve_write_path(QPath("file.txt"), out_dir=out_dir)  # type: ignore[reportPrivateUsage]
        assert result.is_relative_to(out_dir.resolve())

    def test_relative_without_out_dir_uses_app_dir(
        self,
        handler: ResourceBytesIO,
        tmp_path: Path,
        qt_app: QApplication,
    ) -> None:
        result = handler._resolve_write_path(QPath("file.txt"))  # type: ignore[reportPrivateUsage]
        assert result.is_relative_to(handler.app_dir)


# ── list_dir ──────────────────────────────────────────────────────────────────

class TestListDir:
    def test_lists_children(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        (tmp_path / "file.txt").write_bytes(b"")
        subdir = tmp_path / "sub"
        subdir.mkdir()
        entries = handler.list_dir(QPath(str(tmp_path)))
        names = [p.name for p, _ in entries]
        assert "file.txt" in names
        assert "sub" in names

    def test_dirs_come_first(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        (tmp_path / "z_file.txt").write_bytes(b"")
        (tmp_path / "a_dir").mkdir()
        entries = handler.list_dir(QPath(str(tmp_path)))
        is_dirs = [is_dir for _, is_dir in entries]
        # All Trues before all Falses
        assert is_dirs == sorted(is_dirs, reverse=True)

    def test_returns_qpath_instances(self, handler: ResourceBytesIO, tmp_path: Path, qt_app: QApplication) -> None:
        (tmp_path / "x.txt").write_bytes(b"")
        entries = handler.list_dir(QPath(str(tmp_path)))
        for p, _ in entries:
            assert isinstance(p, QPath)


# ── Hypothesis: list_files completeness ──────────────────────────────────────

@given(filenames=st.lists(_FNAME, min_size=1, max_size=10, unique=True))
def test_all_created_files_found_by_list_files(qt_app: QApplication, filenames: list[str]) -> None:
    tmp = tempfile.mkdtemp()
    try:
        for name in filenames:
            path = QPath(tmp) / (name + ".txt")
            path.write_bytes(b"content")
        h = ResourceBytesIO()
        h.app_dir = QPath(tmp).resolve()
        h._read_dirs = (h.app_dir,)  # type: ignore[reportPrivateUsage]
        result = h.list_files((QPath(tmp),))
        found = {p.name for p in result}
        for name in filenames:
            assert (name + ".txt") in found
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@given(
    kept=st.lists(_FNAME, min_size=1, max_size=5, unique=True),
    excluded_dir=_FNAME,
)
def test_directory_blacklist_excludes_completely(qt_app: QApplication, kept: list[str], excluded_dir: str) -> None:
    from hypothesis import assume
    assume(excluded_dir not in kept)
    tmp = tempfile.mkdtemp()
    try:
        for name in kept:
            path = QPath(tmp) / (name + ".txt")
            path.write_bytes(b"")
        excl = QPath(tmp) / excluded_dir
        excl.os_mkdir(exist_ok=True)
        (excl / "hidden.txt").write_bytes(b"")
        h = ResourceBytesIO()
        h.app_dir = QPath(tmp).resolve()
        h._read_dirs = (h.app_dir,)  # type: ignore[reportPrivateUsage]
        result = h.list_files((QPath(tmp),), excluded_directories=(excluded_dir,))
        # Check that no result path has excluded_dir as a directory component.
        for p in result:
            intermediate_parts = p.parts[1:-1]  # skip root "/" and filename
            assert excluded_dir not in intermediate_parts
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
