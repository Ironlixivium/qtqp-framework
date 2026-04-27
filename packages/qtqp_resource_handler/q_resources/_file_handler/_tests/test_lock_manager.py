"""Tests for LockManager — per-path async serialization, cleanup, and namespace isolation."""
from __future__ import annotations

import asyncio

from qtqp_path import QPath

from q_resources._file_handler._lock_manager import LockManager


def _run(coro):
    return asyncio.run(coro)


class TestSerialization:
    def test_same_disk_path_serializes(self, qt_app):
        lm = LockManager()
        p = QPath("/tmp/shared_lock_test")
        events: list[tuple[str, int]] = []

        async def task(n: int) -> None:
            async with lm.disk(p):
                events.append(("start", n))
                await asyncio.sleep(0.01)
                events.append(("end", n))

        async def run() -> None:
            await asyncio.gather(task(1), task(2))

        _run(run())

        # Each task must fully complete before the next starts.
        starts = [i for name, i in events if name == "start"]
        ends = [i for name, i in events if name == "end"]
        assert len(starts) == 2
        assert len(ends) == 2
        # The first task to start must also be the first to end.
        assert starts[0] == ends[0]

    def test_same_qrc_path_serializes(self, qt_app):
        lm = LockManager()
        p = QPath(":/res/locked_file.png")
        events: list[tuple[str, int]] = []

        async def task(n: int) -> None:
            async with lm.qrc(p):
                events.append(("start", n))
                await asyncio.sleep(0.01)
                events.append(("end", n))

        async def run() -> None:
            await asyncio.gather(task(1), task(2))

        _run(run())
        starts = [i for name, i in events if name == "start"]
        ends = [i for name, i in events if name == "end"]
        assert starts[0] == ends[0]

    def test_different_paths_run_concurrently(self, qt_app):
        lm = LockManager()
        p1 = QPath("/tmp/lock_path_a")
        p2 = QPath("/tmp/lock_path_b")
        events: list[tuple[str, int]] = []

        async def task(path: QPath, n: int) -> None:
            async with lm.disk(path):
                events.append(("start", n))
                await asyncio.sleep(0.05)
                events.append(("end", n))

        async def run() -> None:
            await asyncio.gather(task(p1, 1), task(p2, 2))

        _run(run())
        # Both tasks should have started before either ends.
        assert events[0][0] == "start"
        assert events[1][0] == "start"


class TestCleanup:
    def test_disk_lock_removed_after_exit(self, qt_app):
        lm = LockManager()
        p = QPath("/tmp/cleanup_disk")

        async def use() -> None:
            async with lm.disk(p):
                pass

        _run(use())
        assert p not in lm._disk_locks

    def test_qrc_lock_removed_after_exit(self, qt_app):
        lm = LockManager()
        p = QPath(":/res/cleanup.png")

        async def use() -> None:
            async with lm.qrc(p):
                pass

        _run(use())
        assert p not in lm._qrc_locks

    def test_same_path_reacquirable_after_release(self, qt_app):
        lm = LockManager()
        p = QPath("/tmp/reuse_lock")

        async def use_twice() -> None:
            async with lm.disk(p):
                pass
            async with lm.disk(p):
                pass

        _run(use_twice())
        assert p not in lm._disk_locks

    def test_no_leaked_locks_after_multiple_paths(self, qt_app):
        lm = LockManager()
        paths = [QPath(f"/tmp/multi_lock_{i}") for i in range(5)]

        async def use_all() -> None:
            for p in paths:
                async with lm.disk(p):
                    pass

        _run(use_all())
        assert len(lm._disk_locks) == 0


class TestNamespaceIsolation:
    def test_disk_and_qrc_are_independent(self, qt_app):
        lm = LockManager()
        p_disk = QPath("/tmp/isolated")
        p_qrc = QPath(":/isolated/path")
        events: list[tuple[str, str]] = []

        async def disk_task() -> None:
            async with lm.disk(p_disk):
                events.append(("start", "disk"))
                await asyncio.sleep(0.05)
                events.append(("end", "disk"))

        async def qrc_task() -> None:
            async with lm.qrc(p_qrc):
                events.append(("start", "qrc"))
                await asyncio.sleep(0.05)
                events.append(("end", "qrc"))

        async def run() -> None:
            await asyncio.gather(disk_task(), qrc_task())

        _run(run())
        # Both namespaces are independent — both tasks start before either ends.
        assert events[0][0] == "start"
        assert events[1][0] == "start"

    def test_disk_locks_stored_separately_from_qrc(self, qt_app):
        lm = LockManager()
        p = QPath("/tmp/same_string")

        async def use() -> None:
            async with lm.disk(p):
                async with lm.qrc(QPath(":/same_string/x")):
                    pass

        _run(use())
        assert p not in lm._disk_locks
        assert QPath(":/same_string/x") not in lm._qrc_locks


class TestExceptionSafety:
    def test_lock_released_on_exception(self, qt_app):
        lm = LockManager()
        p = QPath("/tmp/exception_test")

        async def failing_task() -> None:
            async with lm.disk(p):
                raise RuntimeError("boom")

        async def run() -> None:
            try:
                await failing_task()
            except RuntimeError:
                pass
            # Lock should be released; a second acquire must succeed.
            async with lm.disk(p):
                pass

        _run(run())
        assert p not in lm._disk_locks
