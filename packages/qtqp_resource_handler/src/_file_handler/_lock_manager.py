import asyncio
from typing import cast

from qtqp.path import QPath


class _PathLock:
    def __init__(self, registry: asyncio.Lock, store: dict[QPath, asyncio.Lock], path: QPath) -> None:
        self._lock: asyncio.Lock = cast(asyncio.Lock, None)
        self._registry = registry
        self._store = store
        self._path = path

    async def __aenter__(self):
        async with self._registry:
            if self._path not in self._store:
                self._store[self._path] = asyncio.Lock()
            self._lock = self._store[self._path]
        await self._lock.acquire()

    async def __aexit__(self, *_):
        self._lock.release()
        async with self._registry:
            self._store.pop(self._path, None)


class LockManager:
    """Per-path asyncio.Lock registry with separate namespaces for disk and QRC paths.

    Locks are created lazily on entry and deleted on exit.
    Use as an async context manager via .disk(path) or .qrc(path).
    """

    def __init__(self) -> None:
        self._disk_locks: dict[QPath, asyncio.Lock] = {}
        self._qrc_locks: dict[QPath, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()

    def disk(self, path: QPath) -> _PathLock:
        return _PathLock(self._registry_lock, self._disk_locks, path)

    def qrc(self, path: QPath) -> _PathLock:
        return _PathLock(self._registry_lock, self._qrc_locks, path)
