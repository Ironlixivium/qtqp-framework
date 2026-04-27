"""Unified I/O handler for disk and Qt resource (QRC) paths."""

import asyncio
import sys
from typing import Literal

from PySide6.QtCore import QFile, QIODevice, QResource
from qtqp.path import QPath

from ._lock_manager import LockManager


class ResourceBytesIO:
    """Reads and writes files from disk and Qt resource (QRC) paths.

    All operations dispatch on path.is_qrc. QRC async methods call Qt APIs
    directly on the main thread (safe under qasync). Disk async methods
    offload blocking I/O via asyncio.to_thread.

    Note on register_rcc_data lifetime: Qt holds a raw pointer into the bytes
    object passed to registerResourceData. The caller must keep that bytes
    reference alive for as long as the resource remains registered.
    """

    def __init__(self) -> None:
        self._locks = LockManager()
        self._init_runtime()

    def _init_runtime(self) -> None:
        self.frozen: bool = bool(getattr(sys, "frozen", False))
        self.cwd: QPath = QPath.cwd().resolve()
        self.app_dir: QPath = (
            QPath(sys.executable).resolve().parent
            if self.frozen
            else QPath(__file__).resolve().parent.parent
        )
        self._read_dirs: tuple[QPath, ...] = (self.app_dir, self.cwd)

    # -------- sync I/O --------

    def list_dir(self, path: QPath) -> list[tuple[QPath, bool]]:
        """List immediate children as (path, is_dir) pairs, dirs first then files."""
        entries = [(child, child.is_dir()) for child in path.iterdir()]
        return sorted(entries, key=lambda e: (not e[1], e[0].name.lower()))

    def list_files(
        self,
        scopes: tuple[QPath, ...],
        *,
        mode: Literal["all", "disk", "qrc"] = "all",
        extensions: tuple[str, ...] = (),
        excluded_extensions: tuple[str, ...] = (),
        excluded_directories: tuple[str, ...] = (),
    ) -> list[QPath]:
        """List files across scopes, routing each to disk or QRC by path type.

        Args:
            scopes: Root directories to search.
            mode: Restrict to "disk", "qrc", or "all" scopes.
            extensions: Suffix whitelist. Empty means all suffixes.
            excluded_extensions: Suffix blacklist.
            excluded_directories: Directory name blacklist.

        Returns:
            Concatenated, per-scope-sorted list of matching paths.
        """
        results: list[QPath] = []
        for scope in scopes:
            if mode == "disk" and scope.is_qrc:
                continue
            if mode == "qrc" and scope.is_disk:
                continue
            results.extend(self._list_files_under(
                scope,
                extensions=extensions,
                excluded_extensions=excluded_extensions,
                excluded_directories=excluded_directories,
            ))
        return results

    def read_bytes(self, path: QPath) -> bytes:
        """Read raw bytes from a QRC or disk path.

        Args:
            path: A QRC (':/...') or disk path. Relative disk paths are resolved
                  against app_dir then cwd.
        """
        if path.is_qrc:
            return path.read_bytes()
        return self._resolve_disk_path(path).read_bytes()

    def write_bytes(
        self,
        path: QPath,
        data: bytes,
        *,
        overwrite: bool = False,
        out_dir: QPath | None = None,
    ) -> QPath:
        """Write raw bytes to a QRC or disk path.

        Args:
            path: Destination QRC or disk path.
            data: Bytes to write.
            overwrite: Disk only — raises FileExistsError when False and file exists.
            out_dir: Disk only — base directory for relative paths (default: app_dir).

        Returns:
            The canonical path that was written.
        """
        if path.is_qrc:
            self._write_qrc_bytes(path, data)
            return path
        out_path = self._resolve_write_path(path, out_dir=out_dir)
        if out_path.exists() and not overwrite:
            raise FileExistsError(f"{out_path} already exists (set overwrite=True)")
        out_path.parent.os_mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        return out_path

    # -------- async I/O --------

    async def async_list_files(
        self,
        scopes: tuple[QPath, ...],
        *,
        mode: Literal["all", "disk", "qrc"] = "all",
        extensions: tuple[str, ...] = (),
        excluded_extensions: tuple[str, ...] = (),
        excluded_directories: tuple[str, ...] = (),
    ) -> list[QPath]:
        return self.list_files(
            scopes,
            mode=mode,
            extensions=extensions,
            excluded_extensions=excluded_extensions,
            excluded_directories=excluded_directories,
        )

    async def async_read_bytes(self, path: QPath) -> bytes:
        """Acquire per-path lock, then read. QRC: main thread. Disk: thread pool."""
        if path.is_qrc:
            async with self._locks.qrc(path):
                return self.read_bytes(path)
        async with self._locks.disk(path.resolve()):
            return await asyncio.to_thread(self.read_bytes, path)

    async def async_write_bytes(
        self,
        path: QPath,
        data: bytes,
        *,
        overwrite: bool = False,
        out_dir: QPath | None = None,
    ) -> QPath:
        """Acquire per-path lock, then write. QRC: main thread. Disk: thread pool."""
        if path.is_qrc:
            async with self._locks.qrc(path):
                return self.write_bytes(path, data)
        async with self._locks.disk(path.resolve()):
            return await asyncio.to_thread(
                self.write_bytes, path, data, overwrite=overwrite, out_dir=out_dir
            )

    def children(self, qrc_path: QPath) -> list[QPath]:
        """List immediate children of a QRC directory as full QPath objects."""
        return list(qrc_path.iterdir())

    async def async_children(self, qrc_path: QPath) -> list[QPath]:
        return self.children(qrc_path)

    # -------- RCC registration --------

    def register_rcc_file(self, rcc_file_path: QPath, map_root: str = "") -> bool:
        return rcc_file_path.register_as_rcc(map_root)

    def unregister_rcc_file(self, rcc_file_path: QPath, map_root: str = "") -> bool:
        return rcc_file_path.unregister_as_rcc(map_root)

    def register_rcc_data(self, rcc_data: bytes, map_root: str = "") -> bool:
        """Register compiled .rcc data from an in-memory bytes object.

        Warning: Qt holds a raw pointer into rcc_data. The caller must keep
        the bytes object alive for as long as the resource remains registered.

        Args:
            rcc_data: Raw bytes of a compiled .rcc resource file.
            map_root: Optional virtual root prefix.

        Returns:
            True if registration succeeded.
        """
        return QResource.registerResourceData(rcc_data, map_root)

    def unregister_rcc_data(self, rcc_data: bytes, map_root: str = "") -> bool:
        return QResource.unregisterResourceData(rcc_data, map_root)

    async def async_register_rcc_file(self, rcc_file_path: QPath, map_root: str = "") -> bool:
        return rcc_file_path.register_as_rcc(map_root)

    async def async_unregister_rcc_file(self, rcc_file_path: QPath, map_root: str = "") -> bool:
        return rcc_file_path.unregister_as_rcc(map_root)

    async def async_register_rcc_data(self, rcc_data: bytes, map_root: str = "") -> bool:
        return self.register_rcc_data(rcc_data, map_root)

    async def async_unregister_rcc_data(self, rcc_data: bytes, map_root: str = "") -> bool:
        return self.unregister_rcc_data(rcc_data, map_root)

    # -------- internals --------

    def _list_files_under(
        self,
        root: QPath,
        *,
        extensions: tuple[str, ...] = (),
        excluded_extensions: tuple[str, ...] = (),
        excluded_directories: tuple[str, ...] = (),
        recursive: bool = True,
    ) -> list[QPath]:
        pattern = "**/*" if recursive else "*"
        root_depth = len(root.parts)
        results: list[QPath] = []
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            if excluded_directories and any(
                part in excluded_directories for part in path.parts[root_depth:-1]
            ):
                continue
            suffix = path.suffix.lower()
            if suffix in excluded_extensions:
                continue
            if extensions and suffix not in extensions:
                continue
            results.append(path if root.is_qrc else path.resolve())
        return sorted(results, key=lambda p: p.as_posix().lower())

    def _resolve_disk_path(self, path: QPath) -> QPath:
        if path.is_absolute():
            if not path.exists():
                raise FileNotFoundError(path)
            return path.resolve()
        tried: list[QPath] = []
        for base in self._read_dirs:
            candidate = (base / path).resolve()
            tried.append(candidate)
            if candidate.exists():
                return candidate
        tried_s = "\n".join(f"  - {t}" for t in tried)
        raise FileNotFoundError(f"File not found. Tried:\n{tried_s}")

    def _resolve_write_path(self, path: QPath, *, out_dir: QPath | None = None) -> QPath:
        if path.is_absolute():
            return path.resolve()
        base = out_dir.resolve() if out_dir is not None else self.app_dir
        return (base / path).resolve()

    def _write_qrc_bytes(self, path: QPath, data: bytes) -> None:
        file = QFile(path)
        if not file.open(QIODevice.OpenModeFlag.WriteOnly):
            raise PermissionError(f"Qt resource not writable: {path}")
        try:
            file.write(data)
        finally:
            file.close()
