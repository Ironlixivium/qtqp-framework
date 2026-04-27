"""Tests for _FileHandlerController — contracts, list/load/save, restriction logic, and Hypothesis."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from hypothesis import given
from hypothesis import strategies as st
from PySide6.QtCore import QObject

from qtqp.resource_handler._controller import (
    ClientContract,
    FileHandlerController,
    _LoadFilters,
)
from qtqp.resource_handler._scopes import Scope
from qtqp.path import QPath


class _TestObj(QObject):
    """Minimal QObject for contract registration; real type so destroyed signal fires."""


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def controller(qt_app):
    ctrl = FileHandlerController()
    mock = MagicMock()
    mock.list_files.return_value = []
    mock.read_bytes.return_value = b"content"
    mock.write_bytes.return_value = QPath.cwd() / "out.txt"
    ctrl._loader = mock
    return ctrl


@pytest.fixture()
def obj(qt_app, controller):
    o = _TestObj()
    controller.register_new_contract(o, load_scopes=("cwd",))
    return o


def _make_contract(
    scopes: list[str],
    *,
    save_scope: str | None = None,
    save_path: QPath | None = None,
    extensions_whitelist: tuple[str, ...] = (),
    restricted_extensions: bool = False,
    restricted_scope: bool = False,
    restricted_path: bool = False,
    load_subpaths: tuple[QPath, ...] = (),
) -> ClientContract:
    return ClientContract(
        load_filters=_LoadFilters(extensions_whitelist=extensions_whitelist),
        load_subpaths=load_subpaths,
        load_scopes=tuple(Scope(s) for s in scopes),
        obj_id=0,
        obj_type=_TestObj,
        restricted_extensions=restricted_extensions,
        restricted_path=restricted_path,
        restricted_scope=restricted_scope,
        save_subpath=save_path,
        save_scope=Scope(save_scope) if save_scope else None,
    )


# ── register_new_contract ─────────────────────────────────────────────────────

class TestRegisterContract:
    def test_returns_true_on_success(self, qt_app, controller):
        o = _TestObj()
        assert controller.register_new_contract(o) is True

    def test_contract_accessible_by_id(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(o)
        assert id(o) in controller._contracts

    def test_scope_strings_converted_to_enum(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(o, load_scopes=("cwd", "home"))
        contract = controller._contracts[id(o)]
        assert Scope.CWD in contract.load_scopes
        assert Scope.HOME in contract.load_scopes

    def test_contract_auto_removed_on_destruction(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(o)
        obj_id = id(o)
        assert obj_id in controller._contracts
        del o
        assert obj_id not in controller._contracts

    def test_two_objects_have_independent_contracts(self, qt_app, controller):
        o1 = _TestObj()
        o2 = _TestObj()
        controller.register_new_contract(o1, load_scopes=("cwd",))
        controller.register_new_contract(o2, load_scopes=("home",))
        assert controller._contracts[id(o1)].load_scopes == (Scope.CWD,)
        assert controller._contracts[id(o2)].load_scopes == (Scope.HOME,)

    def test_extension_whitelist_stored(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(o, extensions_whitelist=(".txt", ".pdf"))
        contract = controller._contracts[id(o)]
        assert ".txt" in contract.load_filters.extensions_whitelist
        assert ".pdf" in contract.load_filters.extensions_whitelist

    def test_save_scope_stored(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(o, save_scope="home")
        contract = controller._contracts[id(o)]
        assert contract.save_scope == Scope.HOME

    def test_save_scope_none_when_not_given(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(o)
        assert controller._contracts[id(o)].save_scope is None

    def test_restriction_flags_stored(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(
            o,
            restricted_extensions=True,
            restricted_scope=True,
            restricted_path=True,
        )
        c = controller._contracts[id(o)]
        assert c.restricted_extensions is True
        assert c.restricted_scope is True
        assert c.restricted_path is True


# ── list_files ────────────────────────────────────────────────────────────────

class TestListFiles:
    def test_delegates_to_loader(self, qt_app, controller, obj):
        controller.list_files(obj)
        assert controller._loader.list_files.called

    def test_no_contract_raises_key_error(self, qt_app, controller):
        unregistered = _TestObj()
        with pytest.raises(KeyError):
            controller.list_files(unregistered)

    def test_restricted_extensions_locks_whitelist(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(
            o,
            extensions_whitelist=(".txt",),
            restricted_extensions=True,
        )
        controller.list_files(o, extensions_whitelist=(".pdf",))
        call_kwargs = controller._loader.list_files.call_args[1]
        assert call_kwargs["extensions"] == (".txt",)

    def test_restricted_scope_filters_extra_scopes(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(o, load_scopes=("cwd",), restricted_scope=True)
        controller.list_files(o, load_scopes=("cwd", "home"))
        call_args = controller._loader.list_files.call_args[0][0]
        home_path = str(Scope.HOME.path)
        cwd_path = str(Scope.CWD.path)
        root_strs = [str(r) for r in call_args]
        assert home_path not in root_strs
        assert cwd_path in root_strs

    def test_unrestricted_scope_passes_override(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(o, load_scopes=("cwd",), restricted_scope=False)
        controller.list_files(o, load_scopes=("home",))
        call_args = controller._loader.list_files.call_args[0][0]
        home_path = Scope.HOME.path
        assert any(str(r) == str(home_path) for r in call_args)

    def test_directory_blacklist_passed_to_loader(self, qt_app, controller, obj):
        controller.list_files(obj, directory_blacklist=("node_modules",))
        call_kwargs = controller._loader.list_files.call_args[1]
        assert call_kwargs["excluded_directories"] == ("node_modules",)

    def test_directory_whitelist_filters_results(self, qt_app, controller):
        cwd = Scope.CWD.path
        mock_results = [
            cwd / "allowed" / "file.txt",
            cwd / "blocked" / "other.txt",
        ]
        controller._loader.list_files.return_value = mock_results
        o = _TestObj()
        controller.register_new_contract(o, load_scopes=("cwd",))
        result = controller.list_files(o, directory_whitelist=("allowed",))
        names = [p.name for p in result]
        assert "file.txt" in names
        assert "other.txt" not in names


# ── load ──────────────────────────────────────────────────────────────────────

class TestLoad:
    def test_delegates_to_read_bytes(self, qt_app, controller, obj):
        path = QPath.cwd() / "file.txt"
        controller.load(obj, path)
        controller._loader.read_bytes.assert_called_once_with(path)

    def test_no_contract_raises_key_error(self, qt_app, controller):
        unregistered = _TestObj()
        with pytest.raises(KeyError):
            controller.load(unregistered, QPath.cwd() / "x.txt")

    def test_restricted_scope_path_outside_raises(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(o, load_scopes=("cwd",), restricted_scope=True)
        with pytest.raises(ValueError, match="outside allowed roots"):
            controller.load(o, QPath("/etc/passwd"))

    def test_restricted_scope_path_inside_succeeds(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(o, load_scopes=("cwd",), restricted_scope=True)
        path = QPath.cwd() / "valid_file.txt"
        controller.load(o, path)
        controller._loader.read_bytes.assert_called_once_with(path)

    def test_restricted_extensions_forbidden_raises(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(
            o,
            extensions_whitelist=(".txt",),
            restricted_extensions=True,
        )
        with pytest.raises(ValueError, match="not in allowed extensions"):
            controller.load(o, QPath.cwd() / "secret.exe")

    def test_restricted_extensions_allowed_succeeds(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(
            o,
            extensions_whitelist=(".txt",),
            restricted_extensions=True,
        )
        path = QPath.cwd() / "readme.txt"
        controller.load(o, path)
        controller._loader.read_bytes.assert_called_once_with(path)

    def test_unrestricted_any_path_passes(self, qt_app, controller, obj):
        path = QPath("/some/arbitrary/path.xyz")
        controller.load(obj, path)
        controller._loader.read_bytes.assert_called_once_with(path)

    def test_returns_bytes_from_loader(self, qt_app, controller, obj):
        controller._loader.read_bytes.return_value = b"\xca\xfe"
        result = controller.load(obj, QPath.cwd() / "x.bin")
        assert result == b"\xca\xfe"


# ── save_as ───────────────────────────────────────────────────────────────────

class TestSaveAs:
    def test_no_save_path_raises(self, qt_app, controller):
        o = _TestObj()
        controller.register_new_contract(o, save_scope=None)
        with pytest.raises(ValueError, match="no saving path"):
            controller.save_as(o, b"data", "file.txt")

    def test_no_contract_raises_key_error(self, qt_app, controller):
        unregistered = _TestObj()
        with pytest.raises(KeyError):
            controller.save_as(unregistered, b"data", "file.txt")

    def test_restricted_extension_forbidden_raises(self, qt_app, controller, tmp_path):
        o = _TestObj()
        controller.register_new_contract(
            o,
            extensions_whitelist=(".txt",),
            restricted_extensions=True,
            save_scope="cwd",
            save_subpath=QPath(str(tmp_path)),
        )
        with pytest.raises(ValueError, match="not in allowed extensions"):
            controller.save_as(o, b"data", "output.pdf")

    def test_allowed_extension_calls_write_bytes(self, qt_app, controller, tmp_path):
        o = _TestObj()
        controller.register_new_contract(
            o,
            extensions_whitelist=(".txt",),
            restricted_extensions=True,
            save_scope="cwd",
            save_subpath=QPath(str(tmp_path)),
        )
        controller.save_as(o, b"hello", "output.txt")
        assert controller._loader.write_bytes.called

    def test_overwrite_flag_propagated(self, qt_app, controller, tmp_path):
        o = _TestObj()
        controller.register_new_contract(
            o,
            save_scope="cwd",
            save_subpath=QPath(str(tmp_path)),
        )
        controller.save_as(o, b"data", "file.txt", overwrite=True)
        call_kwargs = controller._loader.write_bytes.call_args[1]
        assert call_kwargs.get("overwrite") is True

    def test_overwrite_false_by_default(self, qt_app, controller, tmp_path):
        o = _TestObj()
        controller.register_new_contract(
            o,
            save_scope="cwd",
            save_subpath=QPath(str(tmp_path)),
        )
        controller.save_as(o, b"data", "file.txt")
        call_kwargs = controller._loader.write_bytes.call_args[1]
        assert call_kwargs.get("overwrite") is False

    def test_subpath_joined_with_filename(self, qt_app, controller, tmp_path):
        o = _TestObj()
        save_root = QPath(str(tmp_path))
        controller.register_new_contract(o, save_scope="cwd", save_subpath=save_root)
        controller.save_as(o, b"data", "report.txt")
        dest = controller._loader.write_bytes.call_args[0][0]
        assert dest.name == "report.txt"
        assert dest.is_relative_to(save_root)

    def test_returns_qpath_from_loader(self, qt_app, controller, tmp_path):
        o = _TestObj()
        expected = QPath(str(tmp_path / "out.txt"))
        controller._loader.write_bytes.return_value = expected
        controller.register_new_contract(o, save_scope="cwd", save_subpath=QPath(str(tmp_path)))
        result = controller.save_as(o, b"data", "out.txt")
        assert isinstance(result, QPath)


# ── _restrict_load_params ─────────────────────────────────────────────────────

class TestRestrictLoadParams:
    def test_keeps_in_contract_scopes(self, qt_app, controller):
        contract = _make_contract(["cwd"], restricted_scope=True)
        scopes, _ = controller._restrict_load_params(
            contract, (Scope.CWD, Scope.HOME), ()
        )
        assert Scope.CWD in scopes
        assert Scope.HOME not in scopes

    def test_all_out_of_contract_scopes_removed(self, qt_app, controller):
        contract = _make_contract(["cwd"], restricted_scope=True)
        scopes, _ = controller._restrict_load_params(
            contract, (Scope.HOME, Scope.USER_CONFIG), ()
        )
        assert scopes == ()

    def test_keeps_subpaths_under_contract_scope(self, qt_app, controller):
        contract = _make_contract(["cwd"], restricted_scope=True)
        cwd_path = Scope.CWD.path
        home_path = Scope.HOME.path
        in_scope = cwd_path / "docs" / "file.txt"
        out_scope = home_path / "docs" / "file.txt"
        _, paths = controller._restrict_load_params(
            contract, (Scope.CWD,), (in_scope, out_scope)
        )
        assert in_scope in paths
        assert out_scope not in paths

    def test_empty_request_scopes_returns_empty(self, qt_app, controller):
        contract = _make_contract(["cwd"], restricted_scope=True)
        scopes, _ = controller._restrict_load_params(contract, (), ())
        assert scopes == ()


# ── _restrict_save_params ─────────────────────────────────────────────────────

class TestRestrictSaveParams:
    def test_matching_scope_kept(self, qt_app, controller):
        contract = _make_contract(["cwd"], save_scope="cwd", save_path=Scope.CWD.path)
        scope, _ = controller._restrict_save_params(contract, Scope.CWD, None)
        assert scope == Scope.CWD

    def test_mismatched_scope_becomes_none(self, qt_app, controller):
        contract = _make_contract(["cwd"], save_scope="cwd", save_path=Scope.CWD.path)
        scope, _ = controller._restrict_save_params(contract, Scope.HOME, None)
        assert scope is None

    def test_path_within_save_scope_kept(self, qt_app, controller):
        contract = _make_contract(["cwd"], save_scope="cwd", save_path=Scope.CWD.path)
        valid_path = Scope.CWD.path / "output"
        _, path = controller._restrict_save_params(contract, Scope.CWD, valid_path)
        assert path == valid_path

    def test_path_outside_save_scope_becomes_none(self, qt_app, controller):
        contract = _make_contract(["cwd"], save_scope="cwd", save_path=Scope.CWD.path)
        invalid_path = Scope.HOME.path / "output"
        _, path = controller._restrict_save_params(contract, Scope.CWD, invalid_path)
        assert path is None

    def test_none_save_subpath_with_none_contract_save_scope(self, qt_app, controller):
        contract = _make_contract(["cwd"], save_scope=None, save_path=None)
        _, path = controller._restrict_save_params(contract, None, None)
        assert path is None


# ── Hypothesis: restriction invariants ───────────────────────────────────────

_SCOPE_LITERALS = ["cwd", "home", "user_config", "user_data", "user_documents"]
_SCOPE_STRAT = st.sampled_from(_SCOPE_LITERALS)


@given(
    contract_scopes=st.lists(_SCOPE_STRAT, min_size=1, max_size=3, unique=True),
    request_scopes=st.lists(_SCOPE_STRAT, min_size=0, max_size=5),
)
def test_restrict_load_never_returns_out_of_contract_scope(
    qt_app, contract_scopes, request_scopes
):
    ctrl = FileHandlerController()
    ctrl._loader = MagicMock()
    contract = _make_contract(contract_scopes, restricted_scope=True)
    request_enum = tuple(Scope(s) for s in request_scopes)
    restricted, _ = ctrl._restrict_load_params(contract, request_enum, ())
    for scope in restricted:
        assert scope in contract.load_scopes


@given(
    contract_scopes=st.lists(_SCOPE_STRAT, min_size=1, max_size=3, unique=True),
    request_scopes=st.lists(_SCOPE_STRAT, min_size=0, max_size=5),
)
def test_restrict_load_never_adds_new_scopes(
    qt_app, contract_scopes, request_scopes
):
    ctrl = FileHandlerController()
    ctrl._loader = MagicMock()
    contract = _make_contract(contract_scopes, restricted_scope=True)
    request_enum = tuple(Scope(s) for s in request_scopes)
    restricted, _ = ctrl._restrict_load_params(contract, request_enum, ())
    request_set = set(request_enum)
    for scope in restricted:
        assert scope in request_set or scope in contract.load_scopes


@given(
    contract_scope=_SCOPE_STRAT,
    request_scope=_SCOPE_STRAT,
)
def test_restrict_save_scope_is_none_or_matches_contract(
    qt_app, contract_scope, request_scope
):
    ctrl = FileHandlerController()
    ctrl._loader = MagicMock()
    contract = _make_contract(
        [contract_scope],
        save_scope=contract_scope,
        save_path=Scope(contract_scope).path,
    )
    result_scope, _ = ctrl._restrict_save_params(
        contract, Scope(request_scope), None
    )
    assert result_scope is None or result_scope == contract.save_scope
