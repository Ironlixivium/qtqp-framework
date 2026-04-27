"""QtQp replacement for Path. Unified path type for disk and Qt resource (QRC) paths."""
from __future__ import annotations

import fnmatch
import io
import os
import posixpath
import sys
from collections.abc import Callable, Iterator
from pathlib import Path, PurePosixPath
from stat import S_ISBLK, S_ISCHR, S_ISDIR, S_ISFIFO, S_ISREG, S_ISSOCK
from typing import IO, Any

from PySide6.QtCore import QFile, QIODevice, QLocale, QResource, QUrl

from ._globber import glob_qpath

_WIN32_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in "123456789"),
    *(f"LPT{i}" for i in "123456789"),
})
_WIN32_INVALID_CHARS = frozenset('<>:"/|?*')


def _validate_windows_path(s: str) -> None:
    import ntpath
    _, _, tail = ntpath.splitroot(s)
    for part in tail.replace("/", "\\").split("\\"):
        if not part or part in (".", ".."):
            continue
        name = part.rstrip(" .")
        if not name:
            raise ValueError(f"Invalid path component: {part!r}")
        if any(c in _WIN32_INVALID_CHARS for c in name):
            raise ValueError(f"Path component contains invalid character: {name!r}")
        if name.split(".")[0].upper() in _WIN32_RESERVED_NAMES:
            raise ValueError(f"Path component is a reserved Windows name: {name!r}")


class QPath(str):
    """QtQp replacement for Path. A path that is either a disk path or a QRC resource path.

    Subclasses str, so it is accepted anywhere a str is expected and passes
    isinstance(x, str) checks. QRC paths are detected by the ':/...' prefix;
    everything else is treated as a disk path.

    Construction raises ValueError for unsupported URL schemes (http, https, ftp, qrc)
    and TypeError for QUrl objects. QUrl and URL support are reserved for a future release.

    Attributes:
        is_qrc: True if this is a QRC path (':/...').
        is_disk: True if this is a disk path.
        drive: Drive letter or UNC prefix (disk only; '' for QRC).
        root: Root component ('/' for QRC and absolute disk paths).
        anchor: Concatenation of drive and root.
        name: Bare filename or final path component.
        suffix: File extension including the dot (e.g. '.pdf').
        suffixes: List of all extensions (e.g. ['.tar', '.gz']).
        stem: Filename without the last extension.
        parent: Parent directory as a QPath; self at the root.
        parents: Tuple of ancestor QPaths from immediate parent to root.
        parts: Path components as a tuple of strings.

    ## Methods (mirror pathlib.Path unless noted):
    >>> __truediv__ / __rtruediv__: Join with the / operator.
    >>> joinpath(*others): Join with one or more segments.
    >>> with_name(name): Replace the final path component.
        with_stem(stem): Replace the stem of the final component.
        with_suffix(suffix): Replace or remove the file extension.
        relative_to(other, *, walk_up=False): Compute a relative path.
        is_relative_to(other): Check if path is relative to other.
        is_absolute(): True if path has a root (always True for QRC).
        as_posix(): String with forward slashes.
        as_uri(): file:// URI (disk only).
        as_std_path(): Convert to pathlib.Path (disk only).
        match(pattern, *, case_sensitive=None): Glob-pattern match from the right.
        full_match(pattern, *, case_sensitive=None): Whole-path glob match.
        exists(*, follow_symlinks=True): Whether the path exists.
        is_file(*, follow_symlinks=True): Whether this is a regular file.
        is_dir(*, follow_symlinks=True): Whether this is a directory.
        compression_algorithm: QRC only; the compression used for this resource.
        size: QRC only; compressed byte size of the resource.
        uncompressed_size: QRC only; uncompressed byte size of the resource.
        locale: QRC only; the QLocale associated with this resource.
        read_uncompressed_bytes(): QRC only; raw uncompressed resource bytes.
        stat(*, follow_symlinks=True): Disk only; raises NotImplementedError for QRC.
        lstat(): Disk only.
        is_symlink() / is_mount() / is_junction(): Always False for QRC.
        is_block_device() / is_char_device() / is_fifo() / is_socket(): Always False for QRC.
        samefile(other): Disk only.
        open(mode, ...): QRC raises PermissionError.
        read_bytes(): Reads from QFile for QRC, open() for disk.
        read_text(encoding, errors, newline): Decodes read_bytes() for QRC.
        write_bytes(data) / write_text(data, ...): QRC raises PermissionError.
        touch(mode, exist_ok): QRC raises PermissionError.
        mkdir(mode, parents, exist_ok): QRC raises PermissionError.
        chmod(mode, *, follow_symlinks) / lchmod(mode): QRC raises PermissionError.
        unlink(missing_ok): QRC raises PermissionError.
        rmdir(): QRC raises PermissionError.
        rename(target) / replace(target): QRC raises PermissionError.
        symlink_to(target, target_is_directory): QRC raises PermissionError.
        hardlink_to(target): QRC raises PermissionError.
        iterdir(): Yields child QPaths (uses QResource.children() for QRC).
        glob(pattern, ...): QRC matches by name; disk delegates to pathlib.Path.
        rglob(pattern, ...): Recursive glob.
        walk(top_down, on_error, follow_symlinks): Disk only.
        absolute(): Make absolute without resolving symlinks.
        resolve(strict): Resolve to absolute canonical path; identity for QRC.
        expanduser(): Expand ~ (disk only).
        cwd(): Classmethod; current working directory.
        home(): Classmethod; home directory.
    """

    parser = os.path

    # ── construction ──────────────────────────────────────────────────────────

    def __new__(cls, value: str | Path | QUrl) -> QPath:
        """
        Raises:
            TypeError: If value is a QUrl instance.
            ValueError: If value uses an unsupported URL scheme (http, https, ftp, qrc).
        """
        if isinstance(value, QUrl):
            raise TypeError(
                "QPath does not accept QUrl; use QPath.from_qurl() when implemented"
            )
        s = str(value)
        lower = s.lower()
        if lower.startswith(("http://", "https://", "ftp://", "qrc:/")):
            raise ValueError(f"URL schemes are not yet supported by QPath: {s!r}")
        if s.startswith(":/"):
            return cls._new_qrc(s)
        return cls._new_disk(s)

    @classmethod
    def _new_qrc(cls, s: str) -> QPath:
        """
        Raises:
            ValueError: If s is shorter than 3 characters, contains backslashes, or contains null bytes.
        """
        if "\\" in s:
            raise ValueError(f"QRC path must not contain backslashes: {s!r}")
        if "\x00" in s:
            raise ValueError(f"QRC path must not contain null bytes: {s!r}")
        return super().__new__(cls, s)

    @classmethod
    def _new_disk(cls, s: str) -> QPath:
        """
        Raises:
            ValueError: If s contains null bytes, or on Windows, reserved names or invalid characters.
        """
        if "\x00" in s:
            raise ValueError(f"Disk path must not contain null bytes: {s!r}")
        if sys.platform == "win32":
            _validate_windows_path(s)
        return super().__new__(cls, s)

    # ── type detection ────────────────────────────────────────────────────────

    @property
    def is_qrc(self) -> bool:
        return self.startswith(":/")

    @property
    def is_disk(self) -> bool:
        return not self.is_qrc

    # ── pure path properties ──────────────────────────────────────────────────

    @property
    def drive(self) -> str:
        if self.is_qrc:
            return ""
        return self.parser.splitroot(str(self))[0]

    @property
    def root(self) -> str:
        if self.is_qrc:
            return "/"
        return self.parser.splitroot(str(self))[1]

    @property
    def anchor(self) -> str:
        if self.is_qrc:
            return "/"
        drv, root, _ = self.parser.splitroot(str(self))
        return drv + root

    @property
    def name(self) -> str:
        if self.is_qrc:
            return PurePosixPath(str(self)).name
        return self.parser.basename(str(self).rstrip(self.parser.sep))

    @property
    def suffix(self) -> str:
        name = self.name.lstrip(".")
        i = name.rfind(".")
        return name[i:] if i != -1 else ""

    @property
    def suffixes(self) -> list[str]:
        return ["." + ext for ext in self.name.lstrip(".").split(".")[1:]]

    @property
    def stem(self) -> str:
        name = self.name
        i = name.rfind(".")
        if i != -1:
            stem = name[:i]
            if stem.lstrip("."):
                return stem
        return name

    @property
    def parent(self) -> QPath:
        if self.is_qrc:
            s = self.rstrip("/")
            parent_s = s.rsplit("/", 1)[0]
            return QPath(parent_s if parent_s != ":" else ":/")
        s = self
        d = self.parser.dirname(s)
        if not d:
            d = "."
        return self if d == s else QPath(d)

    @property
    def parents(self) -> tuple[QPath, ...]:
        result: list[QPath] = []
        current: QPath = self
        while True:
            p = current.parent
            if p == current:
                break
            result.append(p)
            current = p
        return tuple(result)

    @property
    def parts(self) -> tuple[str, ...]:
        if self.is_qrc:
            segments = str(self).split("/")
            # segments[0] is always ":" — the anchor half; the rest are components
            components = [seg for seg in segments[1:] if seg]
            return (":/",) + tuple(components)
        drv, root, tail = self.parser.splitroot(str(self))
        anchor = drv + root
        tail_parts = [x for x in tail.split(self.parser.sep) if x and x != "."]
        return (anchor,) + tuple(tail_parts) if anchor else tuple(tail_parts)

    # ── pure path methods ─────────────────────────────────────────────────────

    def is_absolute(self) -> bool:
        if self.is_qrc:
            return True
        return self.parser.isabs(str(self))

    def as_posix(self) -> str:
        if self.is_qrc:
            return str(self)
        return str(self).replace(self.parser.sep, "/")

    def as_uri(self) -> str:
        """
        Raises:
            ValueError: If this is a QRC path, or if this is a relative disk path.
        """
        if self.is_qrc:
            raise ValueError(f"QRC paths cannot be expressed as file URIs: {self!r}")
        if not self.is_absolute():
            raise ValueError("relative paths can't be expressed as file URIs")
        from urllib.request import pathname2url
        return pathname2url(str(self), add_scheme=True)

    def as_std_path(self) -> Path:
        """Return a stdlib pathlib.Path for this disk path.

        Raises:
            ValueError: If this is a QRC path.
        """
        if self.is_qrc:
            raise ValueError(f"Cannot convert QRC path to pathlib.Path: {self!r}")
        return Path(str(self))

    def with_name(self, name: str) -> QPath:
        """
        Raises:
            ValueError: If name is empty, equals '.', contains separators, or self has no name.
        """
        if self.is_qrc:
            return QPath(str(PurePosixPath(str(self)).with_name(name)))
        sep = self.parser.sep
        altsep = getattr(self.parser, "altsep", None)
        if not name or sep in name or (altsep and altsep in name) or name == ".":
            raise ValueError(f"Invalid name {name!r}")
        if not self.name:
            raise ValueError(f"{self!r} has an empty name")
        d = self.parser.dirname(str(self).rstrip(sep))
        return QPath(self.parser.join(d, name) if d else name)

    def with_stem(self, stem: str) -> QPath:
        """
        Raises:
            ValueError: If stem is empty and the path has a non-empty suffix.
        """
        suffix = self.suffix
        if not suffix:
            return self.with_name(stem)
        if not stem:
            raise ValueError(f"{self!r} has a non-empty suffix")
        return self.with_name(stem + suffix)

    def with_suffix(self, suffix: str) -> QPath:
        """
        Raises:
            ValueError: If the path has an empty name, or suffix is non-empty and does not start with '.'.
        """
        stem = self.stem
        if not stem:
            raise ValueError(f"{self!r} has an empty name")
        if suffix and not suffix.startswith("."):
            raise ValueError(f"Invalid suffix {suffix!r}")
        return self.with_name(stem + suffix)

    def relative_to(self, other: str | QPath, *, walk_up: bool = False) -> QPath:
        """
        Raises:
            ValueError: If self is not under other, they have different anchors,
                or other contains '..' segments when walk_up=True.
        """
        other_q = QPath(other) if not isinstance(other, QPath) else other
        self_parts = self.parts
        other_parts = other_q.parts

        if not walk_up:
            if (len(self_parts) < len(other_parts)
                    or self_parts[:len(other_parts)] != other_parts):
                raise ValueError(
                    f"{str(self)!r} is not in the subpath of {str(other_q)!r}"
                )
            rel = self_parts[len(other_parts):]
        else:
            self_anchor = self_parts[0] if (self.drive or self.root) else None
            other_anchor = other_parts[0] if (other_q.drive or other_q.root) else None
            if self_anchor != other_anchor:
                raise ValueError(
                    f"{str(self)!r} and {str(other_q)!r} have different anchors"
                )
            s_tail = list(self_parts[1:] if self_anchor else self_parts)
            o_tail = list(other_parts[1:] if other_anchor else other_parts)
            i = 0
            while i < len(s_tail) and i < len(o_tail) and s_tail[i] == o_tail[i]:
                i += 1
            for part in o_tail[i:]:
                if part == "..":
                    raise ValueError(
                        f"'..' segment in {str(other_q)!r} cannot be walked"
                    )
            rel = tuple([".."] * (len(o_tail) - i) + s_tail[i:])

        if not rel:
            return QPath(".")
        sep = "/" if self.is_qrc else self.parser.sep
        return QPath(sep.join(rel))

    def is_relative_to(self, other: str | QPath) -> bool:
        other_q = QPath(other) if not isinstance(other, QPath) else other
        self_parts = self.parts
        other_parts = other_q.parts
        return (len(self_parts) >= len(other_parts)
                and self_parts[:len(other_parts)] == other_parts)

    def joinpath(self, *others: str | Path | QPath) -> QPath:
        result: QPath = self
        for other in others:
            result = result / other
        return result

    def __truediv__(self, other: str | Path | QPath) -> QPath:
        if self.is_qrc:
            return QPath(posixpath.join(str(self), str(other)))
        return QPath(self.parser.join(str(self), str(other)))

    def __rtruediv__(self, other: str | Path | QPath) -> QPath:
        return QPath(other) / self

    def match(self, pattern: str, *, case_sensitive: bool | None = None) -> bool:
        """
        Raises:
            ValueError: If pattern is empty.
        """
        pat = QPath(pattern) if not isinstance(pattern, QPath) else pattern
        if case_sensitive is None:
            case_sensitive = self.is_qrc or self.parser is posixpath
        path_parts = self.parts[::-1]
        pattern_parts = pat.parts[::-1]
        if not pattern_parts:
            raise ValueError("empty pattern")
        if len(path_parts) < len(pattern_parts):
            return False
        if len(path_parts) > len(pattern_parts) and pat.anchor:
            return False
        match_fn = fnmatch.fnmatchcase if case_sensitive else fnmatch.fnmatch
        return all(match_fn(pp, pap) for pp, pap in zip(path_parts, pattern_parts, strict=False))

    def full_match(self, pattern: str, *, case_sensitive: bool | None = None) -> bool:
        pat = QPath(pattern) if not isinstance(pattern, QPath) else pattern
        if case_sensitive is None:
            case_sensitive = self.is_qrc or self.parser is posixpath
        self_parts = self.parts
        pattern_parts = pat.parts
        if not pattern_parts:
            return not self_parts
        if len(self_parts) != len(pattern_parts) and "**" not in pattern_parts:
            return False
        match_fn = fnmatch.fnmatchcase if case_sensitive else fnmatch.fnmatch
        return all(
            match_fn(sp, pp) for sp, pp in zip(self_parts, pattern_parts, strict=False) if pp != "**"
        )

    # ── classmethod constructors ──────────────────────────────────────────────

    @classmethod
    def cwd(cls) -> QPath:
        return cls(os.getcwd())

    @classmethod
    def home(cls) -> QPath:
        """
        Raises:
            RuntimeError: If the home directory cannot be determined.
        """
        homedir = os.path.expanduser("~")
        if homedir == "~":
            raise RuntimeError("Could not determine home directory.")
        return cls(homedir)

    # ── filesystem introspection ──────────────────────────────────────────────

    def exists(self, *, follow_symlinks: bool = True) -> bool:
        if self.is_qrc:
            return QResource(str(self)).isValid()
        if follow_symlinks:
            return os.path.exists(str(self))
        return os.path.lexists(str(self))

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        if self.is_qrc:
            return QResource(str(self)).isFile()
        if follow_symlinks:
            return os.path.isfile(str(self))
        try:
            return S_ISREG(os.stat(str(self), follow_symlinks=False).st_mode)
        except (OSError, ValueError):
            return False

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        if self.is_qrc:
            return QResource(str(self)).isDir()
        if follow_symlinks:
            return os.path.isdir(str(self))
        try:
            return S_ISDIR(os.stat(str(self), follow_symlinks=False).st_mode)
        except (OSError, ValueError):
            return False

    def os_stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
        """
        Raises:
            NotImplementedError: If this is a QRC path.
        """
        if self.is_qrc:
            raise NotImplementedError("stat() is not supported for QRC paths")
        return os.stat(str(self), follow_symlinks=follow_symlinks)

    def os_lstat(self) -> os.stat_result:
        """
        Raises:
            NotImplementedError: If this is a QRC path.
        """
        if self.is_qrc:
            raise NotImplementedError("lstat() is not supported for QRC paths")
        return os.lstat(str(self))

    def is_symlink(self) -> bool:
        if self.is_qrc:
            return False
        return os.path.islink(str(self))

    def is_mount(self) -> bool:
        if self.is_qrc:
            return False
        return os.path.ismount(str(self))

    def is_junction(self) -> bool:
        if self.is_qrc:
            return False
        return os.path.isjunction(str(self))

    def is_block_device(self) -> bool:
        if self.is_qrc:
            return False
        try:
            return S_ISBLK(self.os_stat().st_mode)
        except (OSError, ValueError):
            return False

    def is_char_device(self) -> bool:
        if self.is_qrc:
            return False
        try:
            return S_ISCHR(self.os_stat().st_mode)
        except (OSError, ValueError):
            return False

    def is_fifo(self) -> bool:
        if self.is_qrc:
            return False
        try:
            return S_ISFIFO(self.os_stat().st_mode)
        except (OSError, ValueError):
            return False

    def is_socket(self) -> bool:
        if self.is_qrc:
            return False
        try:
            return S_ISSOCK(self.os_stat().st_mode)
        except (OSError, ValueError):
            return False

    def samefile(self, other: str | QPath) -> bool:
        """
        Raises:
            NotImplementedError: If this is a QRC path.
        """
        if self.is_qrc:
            raise NotImplementedError("samefile() is not supported for QRC paths")
        st = self.os_stat()
        other_st = (other if isinstance(other, QPath) else QPath(other)).os_stat()
        return st.st_ino == other_st.st_ino and st.st_dev == other_st.st_dev

    # ── filesystem I/O ────────────────────────────────────────────────────────

    def open(
        self,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> IO[Any]:
        """
        Raises:
            PermissionError: If this is a QRC path.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        if "b" not in mode:
            encoding = io.text_encoding(encoding)
        return open(str(self), mode, buffering, encoding, errors, newline)

    def read_bytes(self) -> bytes:
        """
        Raises:
            FileNotFoundError: If the QRC resource does not exist or cannot be opened.
        """
        if self.is_qrc:
            file = QFile(str(self))
            if not file.open(QIODevice.OpenModeFlag.ReadOnly):
                raise FileNotFoundError(
                    f"Resource not found or not readable: {self!r}"
                )
            try:
                return bytes(file.readAll().data())
            finally:
                file.close()
        with self.open(mode="rb", buffering=0) as f:
            return f.read()

    def read_text(self, encoding: str | None = None, errors: str | None = None, newline: str | None = None) -> str:
        if self.is_qrc:
            return self.read_bytes().decode(encoding or "utf-8", errors or "strict")
        encoding = io.text_encoding(encoding)
        with self.open(mode="r", encoding=encoding, errors=errors, newline=newline) as f:
            return f.read()

    def write_bytes(self, data: bytes) -> int:
        """
        Raises:
            PermissionError: If this is a QRC path.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        view = memoryview(data)
        with self.open(mode="wb") as f:
            return f.write(view)

    def write_text(
        self,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        """
        Raises:
            PermissionError: If this is a QRC path.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        encoding = io.text_encoding(encoding)
        with self.open(mode="w", encoding=encoding, errors=errors, newline=newline) as f:
            return f.write(data)

    def touch(self, mode: int = 0o666, exist_ok: bool = True) -> None:
        """
        Raises:
            PermissionError: If this is a QRC path.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        if exist_ok:
            try:
                os.utime(str(self), None)
                return
            except OSError:
                pass
        flags = os.O_CREAT | os.O_WRONLY
        if not exist_ok:
            flags |= os.O_EXCL
        fd = os.open(str(self), flags, mode)
        os.close(fd)

    def os_mkdir(self, mode: int = 0o777, parents: bool = False, exist_ok: bool = False) -> None:
        """
        Raises:
            PermissionError: If this is a QRC path.
            FileNotFoundError: If a parent directory is missing and parents=False.
            OSError: If the path already exists as a non-directory and exist_ok=False.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        try:
            os.mkdir(str(self), mode)
        except FileNotFoundError:
            if not parents or self.parent == self:
                raise
            self.parent.os_mkdir(parents=True, exist_ok=True)
            self.os_mkdir(mode, parents=False, exist_ok=exist_ok)
        except OSError:
            if not exist_ok or not self.is_dir():
                raise

    def os_chmod(self, mode: int, *, follow_symlinks: bool = True) -> None:
        """
        Raises:
            PermissionError: If this is a QRC path.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        os.chmod(str(self), mode, follow_symlinks=follow_symlinks)

    def os_lchmod(self, mode: int) -> None:
        """
        Raises:
            PermissionError: If this is a QRC path.
        """
        self.os_chmod(mode, follow_symlinks=False)

    def os_unlink(self, missing_ok: bool = False) -> None:
        """
        Raises:
            PermissionError: If this is a QRC path.
            FileNotFoundError: If the file does not exist and missing_ok=False.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        try:
            os.unlink(str(self))
        except FileNotFoundError:
            if not missing_ok:
                raise

    def os_rmdir(self) -> None:
        """
        Raises:
            PermissionError: If this is a QRC path.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        os.rmdir(str(self))

    def os_rename_to(self, target: str | QPath) -> QPath:
        """
        Raises:
            PermissionError: If this is a QRC path.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        os.rename(str(self), str(target))
        return target if isinstance(target, QPath) else QPath(target)

    def os_replace_at(self, target: str | QPath) -> QPath:
        """
        Raises:
            PermissionError: If this is a QRC path.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        os.replace(str(self), str(target))
        return target if isinstance(target, QPath) else QPath(target)

    def os_symlink_to(self, target: str | QPath, target_is_directory: bool = False) -> None:
        """
        Raises:
            PermissionError: If this is a QRC path.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        os.symlink(str(target), str(self), target_is_directory)

    def os_hardlink_to(self, target: str | QPath) -> None:
        """
        Raises:
            PermissionError: If this is a QRC path.
        """
        if self.is_qrc:
            raise PermissionError(f"Qt resource system is read-only: {self!r}")
        os.link(str(target), str(self))

    # ── iteration ─────────────────────────────────────────────────────────────

    def iterdir(self) -> Iterator[QPath]:
        """Yield immediate children as QPath objects."""
        if self.is_qrc:
            base = str(self).rstrip("/")
            for child_name in QResource(str(self)).children():
                yield QPath(f"{base}/{child_name}")
        else:
            with os.scandir(str(self)) as it:
                entries = list(it)
            for entry in entries:
                yield QPath(entry.path)

    def glob(
        self,
        pattern: str,
        *,
        case_sensitive: bool | None = None,
        recurse_symlinks: bool = False,
    ) -> Iterator[QPath]:
        """Yield all existing paths matching pattern under this path."""
        sys.audit("pathlib.Path.glob", self, pattern)
        sep = "/" if self.is_qrc else self.parser.sep
        if case_sensitive is None:
            case_sensitive = self.is_qrc or self.parser is posixpath
            case_pedantic = False
        else:
            case_pedantic = True
        for p in glob_qpath(
            str(self), pattern,
            sep=sep,
            case_sensitive=case_sensitive,
            case_pedantic=case_pedantic,
            recurse_symlinks=recurse_symlinks,
        ):
            yield QPath(p)

    def rglob(
        self,
        pattern: str,
        *,
        case_sensitive: bool | None = None,
        recurse_symlinks: bool = False,
    ) -> Iterator[QPath]:
        """Recursively yield all existing paths matching pattern under this path."""
        sys.audit("pathlib.Path.rglob", self, pattern)
        sep = "/" if self.is_qrc else self.parser.sep
        return self.glob(
            sep.join(["**", pattern]),
            case_sensitive=case_sensitive,
            recurse_symlinks=recurse_symlinks,
        )

    def walk(
        self,
        top_down: bool = True,
        on_error: Callable[[OSError], object] | None = None,
        follow_symlinks: bool = False,
    ) -> Iterator[tuple[QPath, list[str], list[str]]]:
        """Walk the directory tree (disk only).

        Raises:
            NotImplementedError: If this is a QRC path.
        """
        if self.is_qrc:
            raise NotImplementedError("walk() is not supported for QRC paths")
        sys.audit("pathlib.Path.walk", self, on_error, follow_symlinks)
        for dirpath, dirnames, filenames in os.walk(
            str(self), top_down, on_error, follow_symlinks
        ):
            yield QPath(dirpath), dirnames, filenames

    # ── resolve / expand ──────────────────────────────────────────────────────

    def absolute(self) -> QPath:
        if self.is_qrc or self.is_absolute():
            return self
        return QPath(os.path.abspath(str(self)))

    def resolve(self, strict: bool = False) -> QPath:
        if self.is_qrc:
            return self
        return QPath(os.path.realpath(str(self), strict=strict))

    def expanduser(self) -> QPath:
        """
        Raises:
            ValueError: If this is a QRC path.
            RuntimeError: If the home directory cannot be determined.
        """
        if self.is_qrc:
            raise ValueError(f"expanduser() is not supported for QRC paths: {self!r}")
        s = str(self)
        if not s.startswith("~"):
            return self
        expanded = os.path.expanduser(s)
        if expanded.startswith("~"):
            raise RuntimeError("Could not determine home directory.")
        return QPath(expanded)

    # ── QRC metadata ─────────────────────────────────────────────────────────

    @property
    def compression_algorithm(self) -> QResource.Compression:
        """Raises: NotImplementedError for disk paths."""
        if self.is_disk:
            raise NotImplementedError("compression_algorithm is only available for QRC paths")
        return QResource(str(self)).compressionAlgorithm()

    @property
    def size(self) -> int:
        """Compressed byte size of the resource. Raises: NotImplementedError for disk paths."""
        if self.is_disk:
            raise NotImplementedError("size is only available for QRC paths; use os.path.getsize() for disk")
        return QResource(str(self)).size()

    @property
    def uncompressed_size(self) -> int:
        """Raises: NotImplementedError for disk paths."""
        if self.is_disk:
            raise NotImplementedError("uncompressed_size is only available for QRC paths")
        return QResource(str(self)).uncompressedSize()

    @property
    def locale(self) -> QLocale:
        """Raises: NotImplementedError for disk paths."""
        if self.is_disk:
            raise NotImplementedError("locale is only available for QRC paths")
        return QResource(str(self)).locale()

    def read_uncompressed_bytes(self) -> bytes:
        """Read the raw uncompressed data from a QRC resource.

        Raises:
            NotImplementedError: If this is a disk path.
            FileNotFoundError: If the resource does not exist or is not a file.
        """
        if self.is_disk:
            raise NotImplementedError("read_uncompressed_bytes() is only available for QRC paths")
        resource = QResource(str(self))
        if not resource.isValid() or not resource.isFile():
            raise FileNotFoundError(f"Resource not found or not a file: {self!r}")
        return bytes(resource.uncompressedData().data())

    # ── Qt resource registration ──────────────────────────────────────────────

    def register_as_rcc(self, map_root: str = "") -> bool:
        """Register this compiled .rcc file into the Qt resource system.

        Args:
            map_root: Optional virtual root prefix (e.g. '/myapp').

        Returns:
            True if registration succeeded.
        """
        return QResource.registerResource(str(self), map_root)

    def unregister_as_rcc(self, map_root: str = "") -> bool:
        """Unregister this compiled .rcc file from the Qt resource system."""
        return QResource.unregisterResource(str(self), map_root)

    # ── dunder helpers ────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str(self)!r})"

    def __fspath__(self) -> str:
        return str(self)

    def __bytes__(self) -> bytes:
        return os.fsencode(str(self))
