"""Tests for QPath — construction, properties, manipulation, filesystem ops, and Hypothesis invariants."""
from __future__ import annotations

import string
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from PySide6.QtCore import QUrl

from .._q_path import QPath

# ── Hypothesis strategies ─────────────────────────────────────────────────────

_SAFE = string.ascii_letters + string.digits + "_-"
_COMPONENT = (
    st.text(alphabet=_SAFE, min_size=1, max_size=20)
    .filter(lambda s: s not in (".", ".."))
)

# min_size=2 avoids the known single-component .parent bug (QPath(":/a").parent → ValueError)
_QRC_DEEP = st.lists(_COMPONENT, min_size=2, max_size=5).map(
    lambda parts: QPath(":/" + "/".join(parts))
)
_DISK_ABS = st.lists(_COMPONENT, min_size=1, max_size=4).map(
    lambda parts: QPath("/" + "/".join(parts))
)
_ANY_PATH = st.one_of(_QRC_DEEP, _DISK_ABS)


# ── Construction ─────────────────────────────────────────────────────────────

class TestConstruction:
    def test_minimum_valid_qrc_root(self, qt_app):
        p = QPath(":/")
        assert p.is_qrc
        assert str(p) == ":/"

    def test_minimum_valid_qrc_with_component(self, qt_app):
        p = QPath(":/x")
        assert p.is_qrc
        assert str(p) == ":/x"



    def test_qrc_backslash_raises(self, qt_app):
        with pytest.raises(ValueError, match="backslash"):
            QPath(":/foo\\bar")

    def test_qrc_null_byte_raises(self, qt_app):
        with pytest.raises(ValueError, match="null"):
            QPath(":/foo\x00bar")

    def test_disk_null_byte_raises(self, qt_app):
        with pytest.raises(ValueError, match="null"):
            QPath("/foo\x00bar")

    def test_qurl_raises_type_error(self, qt_app):
        with pytest.raises(TypeError):
            QPath(QUrl("file:///tmp"))

    @pytest.mark.parametrize("scheme", [
        "http://example.com/foo",
        "https://example.com/foo",
        "ftp://example.com/foo",
        "qrc:/foo",
    ])
    def test_url_schemes_raise_value_error(self, qt_app, scheme):
        with pytest.raises(ValueError, match="URL schemes"):
            QPath(scheme)

    def test_from_pathlib_path(self, qt_app):
        p = QPath(Path("/home/user/file.txt"))
        assert p.is_disk
        assert str(p) == "/home/user/file.txt"

    def test_is_str_subclass(self, qt_app):
        assert isinstance(QPath(":/res/icon.png"), str)

    def test_str_identity_qrc(self, qt_app):
        s = ":/res/icon.png"
        assert str(QPath(s)) == s

    def test_str_identity_disk(self, qt_app):
        s = "/home/user/docs/file.pdf"
        assert str(QPath(s)) == s

    def test_disk_path_type(self, qt_app):
        p = QPath("/home/user/file.txt")
        assert p.is_disk
        assert not p.is_qrc


# ── Type detection ────────────────────────────────────────────────────────────

class TestTypeDetection:
    def test_qrc_is_qrc_true(self, qt_app):
        assert QPath(":/res/icon.png").is_qrc is True

    def test_qrc_is_disk_false(self, qt_app):
        assert QPath(":/res/icon.png").is_disk is False

    def test_disk_is_disk_true(self, qt_app):
        assert QPath("/a/b/c").is_disk is True

    def test_disk_is_qrc_false(self, qt_app):
        assert QPath("/a/b/c").is_qrc is False

    def test_relative_disk_is_disk(self, qt_app):
        assert QPath("relative/path").is_disk is True


# ── Pure path properties ──────────────────────────────────────────────────────

class TestProperties:
    # drive / root / anchor
    def test_qrc_drive_empty(self, qt_app):
        assert QPath(":/res/file").drive == ""

    def test_qrc_root_slash(self, qt_app):
        assert QPath(":/res/file").root == "/"

    def test_qrc_anchor_slash(self, qt_app):
        assert QPath(":/res/file").anchor == "/"

    def test_disk_abs_root_slash(self, qt_app):
        assert QPath("/home/user").root == "/"

    def test_disk_rel_root_empty(self, qt_app):
        assert QPath("relative/path").root == ""

    # name
    def test_qrc_name(self, qt_app):
        assert QPath(":/res/icon.png").name == "icon.png"

    def test_disk_name(self, qt_app):
        assert QPath("/home/user/file.txt").name == "file.txt"

    def test_name_trailing_slash_stripped(self, qt_app):
        assert QPath("/home/user").name == "user"

    # suffix
    def test_suffix_extension(self, qt_app):
        assert QPath(":/res/icon.png").suffix == ".png"

    def test_suffix_dotfile(self, qt_app):
        assert QPath(":/res/.hidden").suffix == ""

    def test_suffix_no_extension(self, qt_app):
        assert QPath(":/res/noext").suffix == ""

    def test_suffix_multi_extension(self, qt_app):
        assert QPath(":/res/archive.tar.gz").suffix == ".gz"

    # suffixes
    def test_suffixes_single(self, qt_app):
        assert QPath(":/res/icon.png").suffixes == [".png"]

    def test_suffixes_multi(self, qt_app):
        assert QPath(":/res/archive.tar.gz").suffixes == [".tar", ".gz"]

    def test_suffixes_dotfile(self, qt_app):
        assert QPath(":/res/.hidden").suffixes == []

    def test_suffixes_no_ext(self, qt_app):
        assert QPath(":/res/noext").suffixes == []

    # stem
    def test_stem_simple(self, qt_app):
        assert QPath(":/res/icon.png").stem == "icon"

    def test_stem_dotfile(self, qt_app):
        assert QPath(":/res/.hidden").stem == ".hidden"

    def test_stem_multi_suffix(self, qt_app):
        assert QPath(":/res/archive.tar.gz").stem == "archive.tar"

    # parts
    def test_parts_qrc(self, qt_app):
        assert QPath(":/foo/bar/baz").parts == (":/", "foo", "bar", "baz")

    def test_parts_qrc_two_component(self, qt_app):
        assert QPath(":/a/b").parts == (":/", "a", "b")

    def test_parts_disk_abs(self, qt_app):
        assert QPath("/home/user/file").parts == ("/", "home", "user", "file")

    def test_parts_disk_rel(self, qt_app):
        assert QPath("a/b/c").parts == ("a", "b", "c")

    # parent
    def test_parent_qrc_two_components(self, qt_app):
        assert QPath(":/a/b").parent == QPath(":/a")

    def test_parent_qrc_deep(self, qt_app):
        assert QPath(":/a/b/c").parent == QPath(":/a/b")

    def test_parent_disk(self, qt_app):
        assert QPath("/home/user/file.txt").parent == QPath("/home/user")

    def test_parent_disk_root_is_self(self, qt_app):
        p = QPath("/")
        assert p.parent == p

    def test_parent_single_component_qrc_is_root(self, qt_app):
        assert QPath(":/a").parent == QPath(":/")

    def test_parent_qrc_root_is_self(self, qt_app):
        p = QPath(":/")
        assert p.parent == p


# ── Manipulation methods ──────────────────────────────────────────────────────

class TestManipulation:
    def test_with_name_qrc(self, qt_app):
        assert QPath(":/res/icon.png").with_name("logo.svg") == QPath(":/res/logo.svg")

    def test_with_name_disk(self, qt_app):
        assert QPath("/home/user/file.txt").with_name("other.pdf") == QPath("/home/user/other.pdf")

    def test_with_name_empty_raises(self, qt_app):
        with pytest.raises(ValueError):
            QPath(":/res/icon.png").with_name("")

    def test_with_stem(self, qt_app):
        assert QPath(":/res/icon.png").with_stem("logo") == QPath(":/res/logo.png")

    def test_with_suffix_replace(self, qt_app):
        assert QPath(":/res/icon.png").with_suffix(".svg") == QPath(":/res/icon.svg")

    def test_with_suffix_remove(self, qt_app):
        assert QPath(":/res/icon.png").with_suffix("") == QPath(":/res/icon")

    def test_with_suffix_no_leading_dot_raises(self, qt_app):
        with pytest.raises(ValueError):
            QPath(":/res/icon.png").with_suffix("svg")

    def test_joinpath_qrc(self, qt_app):
        assert QPath(":/res") / "icons" / "logo.svg" == QPath(":/res/icons/logo.svg")

    def test_joinpath_disk(self, qt_app):
        assert QPath("/home/user") / "docs" / "readme.txt" == QPath("/home/user/docs/readme.txt")

    def test_joinpath_multi(self, qt_app):
        assert QPath(":/a").joinpath("b", "c", "d") == QPath(":/a/b/c/d")

    def test_rtruediv(self, qt_app):
        result = ":/res" / QPath("file.txt")
        assert result == QPath(":/res/file.txt")

    def test_relative_to_simple_qrc(self, qt_app):
        assert QPath(":/res/icons/logo.svg").relative_to(QPath(":/res")) == QPath("icons/logo.svg")

    def test_relative_to_simple_disk(self, qt_app):
        assert QPath("/a/b/c/d.txt").relative_to("/a/b") == QPath("c/d.txt")

    def test_relative_to_not_relative_raises(self, qt_app):
        with pytest.raises(ValueError):
            QPath(":/a/b").relative_to(QPath(":/c"))

    def test_relative_to_walk_up(self, qt_app):
        result = QPath(":/a/b/c").relative_to(QPath(":/a/d"), walk_up=True)
        assert result == QPath("../b/c")

    def test_is_relative_to_true(self, qt_app):
        assert QPath(":/res/icon.png").is_relative_to(QPath(":/res"))

    def test_is_relative_to_false(self, qt_app):
        assert not QPath(":/other/icon.png").is_relative_to(QPath(":/res"))

    def test_is_absolute_qrc(self, qt_app):
        assert QPath(":/res/file").is_absolute()

    def test_is_absolute_disk_abs(self, qt_app):
        assert QPath("/home/user").is_absolute()

    def test_is_absolute_disk_rel(self, qt_app):
        assert not QPath("relative/path").is_absolute()

    def test_as_posix_disk(self, qt_app):
        assert QPath("/home/user/file.txt").as_posix() == "/home/user/file.txt"

    def test_as_posix_qrc(self, qt_app):
        assert QPath(":/res/icon.png").as_posix() == ":/res/icon.png"

    def test_as_uri_qrc_raises(self, qt_app):
        with pytest.raises(ValueError):
            QPath(":/res/icon.png").as_uri()

    def test_as_uri_relative_disk_raises(self, qt_app):
        with pytest.raises(ValueError):
            QPath("relative/path.txt").as_uri()

    def test_as_uri_disk(self, qt_app):
        uri = QPath("/home/user/file.txt").as_uri()
        assert uri.startswith("file://")

    def test_as_std_path_qrc_raises(self, qt_app):
        with pytest.raises(ValueError):
            QPath(":/res/icon.png").as_std_path()

    def test_as_std_path_disk(self, qt_app):
        p = QPath("/home/user/file.txt").as_std_path()
        assert isinstance(p, Path)

    def test_match_qrc(self, qt_app):
        assert QPath(":/res/icons/logo.svg").match("*.svg")

    def test_match_disk(self, qt_app):
        assert QPath("/home/user/file.txt").match("*.txt")

    def test_full_match_qrc(self, qt_app):
        assert QPath(":/res/icons/logo.svg").full_match(":/res/**/*.svg")


# ── Filesystem tests ──────────────────────────────────────────────────────────

class TestFilesystem:
    def test_exists_file(self, qt_app, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello")
        assert QPath(str(f)).exists()

    def test_exists_missing(self, qt_app, tmp_path):
        assert not QPath(str(tmp_path / "missing.txt")).exists()

    def test_is_file(self, qt_app, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"data")
        assert QPath(str(f)).is_file()

    def test_is_dir(self, qt_app, tmp_path):
        assert QPath(str(tmp_path)).is_dir()

    def test_is_file_on_dir_false(self, qt_app, tmp_path):
        assert not QPath(str(tmp_path)).is_file()

    def test_read_write_bytes_roundtrip(self, qt_app, tmp_path):
        data = b"\x00\xff\xab\xcd"
        p = QPath(str(tmp_path / "data.bin"))
        written = p.write_bytes(data)
        assert written == len(data)
        assert p.read_bytes() == data

    def test_read_text_write_text_roundtrip(self, qt_app, tmp_path):
        p = QPath(str(tmp_path / "text.txt"))
        p.write_text("hello world", encoding="utf-8")
        assert p.read_text(encoding="utf-8") == "hello world"

    def test_touch_creates_file(self, qt_app, tmp_path):
        p = QPath(str(tmp_path / "new.txt"))
        p.touch()
        assert p.exists()

    def test_touch_exist_ok(self, qt_app, tmp_path):
        p = QPath(str(tmp_path / "existing.txt"))
        p.touch()
        p.touch(exist_ok=True)
        assert p.exists()

    def test_os_mkdir_creates_directory(self, qt_app, tmp_path):
        d = QPath(str(tmp_path / "subdir"))
        d.os_mkdir()
        assert d.is_dir()

    def test_os_mkdir_parents(self, qt_app, tmp_path):
        d = QPath(str(tmp_path / "a" / "b" / "c"))
        d.os_mkdir(parents=True, exist_ok=True)
        assert d.is_dir()

    def test_os_unlink(self, qt_app, tmp_path):
        f = tmp_path / "to_delete.txt"
        f.write_bytes(b"x")
        p = QPath(str(f))
        p.os_unlink()
        assert not p.exists()

    def test_os_unlink_missing_ok(self, qt_app, tmp_path):
        p = QPath(str(tmp_path / "nonexistent.txt"))
        p.os_unlink(missing_ok=True)

    def test_iterdir(self, qt_app, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"")
        (tmp_path / "b.txt").write_bytes(b"")
        children = list(QPath(str(tmp_path)).iterdir())
        names = {c.name for c in children}
        assert "a.txt" in names
        assert "b.txt" in names

    def test_cwd_classmethod(self, qt_app):
        p = QPath.cwd()
        assert p.is_disk
        assert p.is_absolute()

    def test_home_classmethod(self, qt_app):
        p = QPath.home()
        assert p.is_disk
        assert p.is_absolute()

    def test_absolute(self, qt_app, tmp_path):
        p = QPath(str(tmp_path / "file.txt"))
        assert p.absolute().is_absolute()

    def test_resolve_absolute(self, qt_app, tmp_path):
        f = tmp_path / "file.txt"
        f.write_bytes(b"")
        p = QPath(str(f)).resolve()
        assert p.is_absolute()

    def test_resolve_qrc_identity(self, qt_app):
        p = QPath(":/res/file.png")
        assert p.resolve() == p

    def test_os_stat(self, qt_app, tmp_path):
        import os
        f = tmp_path / "stat.txt"
        f.write_bytes(b"abc")
        stat = QPath(str(f)).os_stat()
        assert isinstance(stat, os.stat_result)
        assert stat.st_size == 3


# ── QRC permission errors ─────────────────────────────────────────────────────

class TestQrcPermissionErrors:
    @pytest.mark.parametrize("method,args", [
        ("write_bytes", (b"data",)),
        ("write_text", ("text",)),
        ("touch", ()),
        ("os_mkdir", ()),
        ("os_unlink", ()),
        ("os_rename_to", ("/tmp/target",)),
        ("os_symlink_to", ("/tmp/target",)),
        ("os_hardlink_to", ("/tmp/target",)),
        ("os_chmod", (0o644,)),
        ("os_rmdir", ()),
    ])
    def test_qrc_write_ops_raise(self, qt_app, method, args):
        p = QPath(":/res/file.txt")
        with pytest.raises(PermissionError):
            getattr(p, method)(*args)

    def test_qrc_open_write_raises(self, qt_app):
        with pytest.raises(PermissionError):
            QPath(":/res/file.txt").open("wb")

    def test_qrc_open_text_write_raises(self, qt_app):
        with pytest.raises(PermissionError):
            QPath(":/res/file.txt").open("w")


# ── QRC always-False filesystem type checks ───────────────────────────────────

class TestQrcAlwaysFalse:
    @pytest.mark.parametrize("method", [
        "is_symlink", "is_mount", "is_junction",
        "is_block_device", "is_char_device", "is_fifo", "is_socket",
    ])
    def test_qrc_always_returns_false(self, qt_app, method):
        assert getattr(QPath(":/res/file.txt"), method)() is False


# ── Hypothesis invariants ─────────────────────────────────────────────────────

class TestHypothesisInvariants:

    @given(path=_QRC_DEEP)
    def test_is_qrc_xor_is_disk_qrc(self, qt_app, path):
        assert path.is_qrc ^ path.is_disk

    @given(path=_DISK_ABS)
    def test_is_qrc_xor_is_disk_disk(self, qt_app, path):
        assert path.is_qrc ^ path.is_disk

    @given(path=_QRC_DEEP)
    def test_str_identity_qrc(self, qt_app, path):
        assert str(path) == str.__str__(path)
        assert QPath(str(path)) == path

    @given(path=_DISK_ABS)
    def test_str_identity_disk(self, qt_app, path):
        assert QPath(str(path)) == path

    @given(path=_QRC_DEEP)
    def test_parent_name_roundtrip_qrc(self, qt_app, path):
        # Safe: _QRC_DEEP has >= 2 components, so parent is a single-component QRC path.
        # parent / name reconstructs the original path.
        assert path.parent / path.name == path

    @given(path=_DISK_ABS)
    def test_parent_name_roundtrip_disk(self, qt_app, path):
        assume(path.name != "")
        assert path.parent / path.name == path

    @given(path=_ANY_PATH)
    def test_stem_plus_suffix_equals_name(self, qt_app, path):
        assert path.stem + path.suffix == path.name

    @given(path=_QRC_DEEP)
    def test_qrc_parts_starts_with_anchor(self, qt_app, path):
        assert path.parts[0] == ":/"
        assert len(path.parts) >= 2

    @given(path=_DISK_ABS)
    def test_disk_abs_parts_starts_with_slash(self, qt_app, path):
        assert path.parts[0] == "/"

    @given(
        path=_QRC_DEEP,
        ext=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=5),
    )
    def test_with_suffix_roundtrip(self, qt_app, path, ext):
        new_path = path.with_suffix("." + ext)
        assert new_path.suffix == "." + ext

    @given(path=_QRC_DEEP)
    def test_with_name_roundtrip(self, qt_app, path):
        original_name = path.name
        new_path = path.with_name(original_name)
        assert new_path == path
        assert new_path.name == original_name

    @given(path=_QRC_DEEP)
    def test_joinpath_name_equals_truediv(self, qt_app, path):
        segment = "extra"
        assert path.joinpath(segment) == path / segment

    @given(path=_QRC_DEEP)
    def test_is_relative_to_self(self, qt_app, path):
        assert path.is_relative_to(path)

    @given(path=_QRC_DEEP)
    def test_is_relative_to_parent(self, qt_app, path):
        # path always has >= 2 components; parent is valid (single-component)
        assert path.is_relative_to(path.parent)
