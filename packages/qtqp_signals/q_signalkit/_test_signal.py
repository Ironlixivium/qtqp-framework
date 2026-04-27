"""Tests for signalkit."""
from __future__ import annotations

import gc
from dataclasses import dataclass

from . import QSignal, QSignalInstance

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class Event:
    value: str


class Receiver:
    def __init__(self) -> None:
        self.received: list[str] = []

    def on_event(self, event: Event) -> None:
        self.received.append(event.value)


# ---------------------------------------------------------------------------
# Signal basics
# ---------------------------------------------------------------------------


def test_connect_and_emit() -> None:
    sig: QSignalInstance[Event] = QSignalInstance()
    rx = Receiver()
    sig.connect(rx.on_event)
    sig.emit(Event("hello"))
    assert rx.received == ["hello"]


def test_multiple_receivers() -> None:
    sig: QSignalInstance[Event] = QSignalInstance()
    rx1, rx2 = Receiver(), Receiver()
    sig.connect(rx1.on_event)
    sig.connect(rx2.on_event)
    sig.emit(Event("hi"))
    assert rx1.received == ["hi"]
    assert rx2.received == ["hi"]


def test_emission_order() -> None:
    order: list[int] = []
    sig: QSignalInstance[int] = QSignalInstance()
    sig.connect(lambda x: order.append(x * 1))
    sig.connect(lambda x: order.append(x * 2))
    sig.emit(3)
    assert order == [3, 6]


def test_disconnect_bound_method() -> None:
    sig: QSignalInstance[Event] = QSignalInstance()
    rx = Receiver()
    sig.connect(rx.on_event)
    sig.disconnect(rx.on_event)
    sig.emit(Event("nope"))
    assert rx.received == []


def test_disconnect_plain_callable() -> None:
    received: list[str] = []
    sig: QSignalInstance[str] = QSignalInstance()

    def handler(v: str) -> None:
        received.append(v)

    sig.connect(handler)
    sig.disconnect(handler)
    sig.emit("nope")
    assert received == []


def test_disconnect_all() -> None:
    sig: QSignalInstance[Event] = QSignalInstance()
    rx = Receiver()
    sig.connect(rx.on_event)
    sig.connect(lambda e: None)
    sig.disconnect_all()
    assert sig.receiver_count == 0


def test_disconnect_unknown_slot_is_silent() -> None:
    sig: QSignalInstance[str] = QSignalInstance()
    sig.disconnect(lambda x: None)  # should not raise


def test_double_connect_plain_callable_is_deduped() -> None:
    hits: list[int] = []
    sig: QSignalInstance[int] = QSignalInstance()
    def fn(x: int) -> None:
        hits.append(x)
    sig.connect(fn)
    sig.connect(fn)
    sig.emit(1)
    assert hits == [1]


# ---------------------------------------------------------------------------
# Weak reference behaviour
# ---------------------------------------------------------------------------


def test_dead_weak_ref_is_pruned_on_emit() -> None:
    sig: QSignalInstance[Event] = QSignalInstance()
    rx = Receiver()
    sig.connect(rx.on_event)
    assert sig.receiver_count == 1

    del rx
    gc.collect()

    sig.emit(Event("ghost"))  # should not raise
    assert sig.receiver_count == 0


def test_receiver_count_excludes_dead_refs() -> None:
    sig: QSignalInstance[Event] = QSignalInstance()
    rx = Receiver()
    sig.connect(rx.on_event)
    del rx
    gc.collect()
    assert sig.receiver_count == 0


# ---------------------------------------------------------------------------
# QSignal
# ---------------------------------------------------------------------------


class Producer:
    ready = QSignal[str]()
    error = QSignal[Exception]()

def test_descriptor_per_instance_isolation() -> None:
    p1, p2 = Producer(), Producer()
    hits: list[str] = []
    p1.ready.connect(hits.append)
    p2.ready.emit("from p2")
    assert hits == []
    p1.ready.emit("from p1")
    assert hits == ["from p1"]


def test_descriptor_class_access_returns_descriptor() -> None:
    assert isinstance(Producer.ready, QSignal)


def test_descriptor_multiple_signals_independent() -> None:
    p = Producer()
    strings: list[str] = []
    errors: list[Exception] = []
    p.ready.connect(strings.append)
    p.error.connect(errors.append)

    p.ready.emit("ok")
    err = ValueError("boom")
    p.error.emit(err)

    assert strings == ["ok"]
    assert errors == [err]
