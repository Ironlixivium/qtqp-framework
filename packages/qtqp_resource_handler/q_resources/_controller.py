from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget
from qtqp_path import QPath

from ._contracts import ClientContract, LoadFilters, OpsProvider
from ._file_browser import FileBrowserWidget
from ._file_handler import ResourceBytesIO
from ._scopes import Scope, ScopeLiteral, create_dirs

logger = logging.getLogger(__name__)
class FileHandlerController(QObject):
    """Routes file I/O operations for registered QObjects according to their contracts.

    Each QObject registers a contract that specifies which scopes to search,
    which extensions to include or exclude, and where to save files. The
    controller then dispatches list, load, and save calls to the appropriate
    handler (disk or QRC) based on the path type.
    """

    def __init__(self, app_name: str) -> None:
        super().__init__(parent=None)
        self._contracts: dict[int, ClientContract] = {}
        self._loader = ResourceBytesIO()
        self._ops = OpsProvider(
            list_files=self._list_files_with_contract,
            list_dir_filtered=self._list_dir_filtered,
            list_files_under=self._list_files_under,
            load=self._load_with_contract,
            save_as=self._save_as_with_contract,
        )
        create_dirs(app_name)

    def register_new_contract(
        self,
        obj: QObject,
        *,
        directory_blacklist: tuple[str, ...] = (),
        directory_whitelist: tuple[str, ...] = (),
        extensions_blacklist: tuple[str, ...] = (),
        extensions_whitelist: tuple[str, ...] = (),
        load_subpaths: tuple[QPath, ...] = (),
        load_scopes: tuple[ScopeLiteral, ...] = ("cwd",),
        restricted_extensions: bool = False,
        restricted_path: bool = False,
        restricted_scope: bool = False,
        save_subpath: QPath | None = None,
        save_scope: ScopeLiteral | None = None,
    ) -> bool:
        """Create a new I/O contract for obj.

        Args:
            obj: The registering QObject. Its destroyed signal automatically
                removes the contract.
            load_scopes: Root scopes to search. 'Qt' resolves to a QRC path;
                all others resolve to disk paths.
            load_subpaths: Paths to search within each scope.
            extensions_whitelist: Suffix whitelist for list_files. Empty means all suffixes.
            extensions_blacklist: Suffix blacklist for list_files.
            directory_whitelist: Directory name whitelist for list_files. Empty means all directories.
            directory_blacklist: Directory name blacklist for list_files.
            restricted_extensions: Restrict saving and loading to extensions_whitelist.
            restricted_path: Restrict saving and loading to load_paths within the scope.
            restricted_scope: Restrict saving and loading to load_scopes.
            save_scope: Root scope for save operations. None disables saving.
            save_subpath: Resolved destination for save operations.

        Returns:
            True if the contract was registered successfully.
        """
        obj_id = id(obj)
        obj_type = type(obj)
        filters = LoadFilters(
            extensions_whitelist=extensions_whitelist,
            extensions_blacklist=extensions_blacklist,
            directory_whitelist=directory_whitelist,
            directory_blacklist=directory_blacklist,
        )
        contract = ClientContract(
            load_filters=filters,
            load_subpaths=load_subpaths,
            load_scopes=tuple(Scope(s) for s in load_scopes),
            obj_id=obj_id,
            obj_type=obj_type,
            restricted_extensions=restricted_extensions,
            restricted_path=restricted_path,
            restricted_scope=restricted_scope,
            save_subpath=save_subpath,
            save_scope=Scope(save_scope) if save_scope is not None else None,
        )
        self._contracts[obj_id] = contract
        obj.destroyed.connect(lambda: self._delete_contract(obj_id))

        return self._contracts[obj_id].obj_type == obj_type

    # ── Public by-obj API ────────────────────────────────────────────────────

    def list_files(
        self,
        obj: QObject,
        *,
        load_scopes: tuple[ScopeLiteral, ...] | None = None,
        load_subpaths: tuple[QPath, ...] | None = None,
        extensions_whitelist: tuple[str, ...] | None = None,
        extensions_blacklist: tuple[str, ...] | None = None,
        directory_whitelist: tuple[str, ...] | None = None,
        directory_blacklist: tuple[str, ...] | None = None,
    ) -> list[QPath]:
        """Return all files matching obj's contract filters across loading scopes.

        Results are concatenated in scope declaration order, sorted within each scope.

        Args:
            obj: QObject with a registered contract.
            load_scopes: Override root scopes. Subject to contract restriction.
            load_subpaths: Override search paths. Subject to contract restriction.
            extensions_whitelist: Override suffix whitelist. Subject to restricted_extensions.
            extensions_blacklist: Override suffix blacklist.
            directory_whitelist: Override directory name whitelist.
            directory_blacklist: Override directory name blacklist.
        """
        return self._list_files_with_contract(
            self._contracts[id(obj)],
            load_scopes=load_scopes,
            load_subpaths=load_subpaths,
            extensions_whitelist=extensions_whitelist,
            extensions_blacklist=extensions_blacklist,
            directory_whitelist=directory_whitelist,
            directory_blacklist=directory_blacklist,
        )

    def load(
        self,
        obj: QObject,
        path: QPath,
        *,
        load_scopes: tuple[ScopeLiteral, ...] | None = None,
        load_subpaths: tuple[QPath, ...] | None = None,
    ) -> bytes:
        """Read raw bytes from path, validating against the contract's extension whitelist.

        Args:
            obj: QObject with a registered contract.
            path: File to read.
            load_scopes: Override root scopes. Subject to contract restriction.
            load_subpaths: Override search paths. Subject to contract restriction.

        Raises:
            ValueError: If restricted and path is outside the allowed search roots.
        """
        return self._load_with_contract(
            self._contracts[id(obj)],
            path,
            load_scopes=load_scopes,
            load_subpaths=load_subpaths,
        )

    def save_as(
        self,
        obj: QObject,
        data: bytes,
        sub_path: str,
        *,
        overwrite: bool = False,
        save_scope: ScopeLiteral | None = None,
        save_subpath: QPath | None = None,
        extensions_whitelist: tuple[str, ...] | None = None,
    ) -> QPath:
        """Write data to sub_path under the contract's saving path.

        Args:
            obj: QObject with a registered contract.
            data: Bytes to write.
            sub_path: Destination filename within the save path.
            overwrite: Allow overwriting an existing file.
            save_scope: Override save scope. Subject to contract restriction.
            save_subpath: Override save path. Subject to contract restriction.
            extensions_whitelist: Override suffix whitelist. Subject to restricted_extensions.

        Raises:
            ValueError: If the resolved save path is None.
        """
        return self._save_as_with_contract(
            self._contracts[id(obj)],
            data,
            sub_path,
            overwrite=overwrite,
            save_scope=save_scope,
            save_subpath=save_subpath,
            extensions_whitelist=extensions_whitelist,
        )

    def browser_widget(
        self,
        obj: QObject,
        on_selection: Callable[[QPath], None],
        *,
        full_navigation: bool = False,
        modal: bool = True,
        parent: QWidget | None = None,
    ) -> FileBrowserWidget:
        """Create a FileBrowserWidget scoped to obj's contract.

        Args:
            obj: QObject with a registered contract.
            on_selection: Called with the QPath of the activated file.
            full_navigation: If True, returns a navigable directory browser.
            modal: Passed through to the widget; True = one-shot selection.
            parent: Qt parent widget.

        Raises:
            KeyError: If obj has no registered contract.
        """
        contract = self._contracts[id(obj)]
        if full_navigation:
            return FileBrowserWidget.navigating(
                contract, QPath.cwd(), on_selection,
                ops=self._ops, modal=modal, parent=parent,
            )
        return FileBrowserWidget.flat(
            contract, on_selection,
            ops=self._ops, modal=modal, parent=parent,
        )

    def bytes_from_browser(
        self,
        obj: QObject,
        *,
        full_navigation: bool = False,
        parent: QWidget | None = None,
    ) -> bytes | None:
        """Open a modal file browser scoped to obj's contract and return the loaded bytes.

        Blocks until the user selects a file or dismisses the dialog.

        Args:
            obj: QObject with a registered contract.
            full_navigation: If True, opens a navigable directory browser.
            parent: Qt parent widget for the dialog.

        Returns:
            Bytes of the selected file, or None if the user cancelled.

        Raises:
            KeyError: If obj has no registered contract.
        """
        contract = self._contracts[id(obj)]
        result: bytes | None = None
        dialog = QDialog(parent)

        def on_selection(path: QPath) -> None:
            nonlocal result
            result = self._load_with_contract(contract, path)
            dialog.accept()

        widget = (
            FileBrowserWidget.navigating(contract, QPath.cwd(), on_selection, ops=self._ops)
            if full_navigation else
            FileBrowserWidget.flat(contract, on_selection, ops=self._ops)
        )
        QVBoxLayout(dialog).addWidget(widget)
        dialog.exec()
        return result

    # ── Private by-contract helpers ──────────────────────────────────────────

    def _list_files_with_contract(
        self,
        contract: ClientContract,
        *,
        load_scopes: tuple[ScopeLiteral, ...] | None = None,
        load_subpaths: tuple[QPath, ...] | None = None,
        extensions_whitelist: tuple[str, ...] | None = None,
        extensions_blacklist: tuple[str, ...] | None = None,
        directory_whitelist: tuple[str, ...] | None = None,
        directory_blacklist: tuple[str, ...] | None = None,
    ) -> list[QPath]:
        resolved_scopes = tuple(Scope(s) for s in load_scopes) if load_scopes is not None else contract.load_scopes
        resolved_paths = load_subpaths if load_subpaths is not None else contract.load_subpaths
        filters = contract.load_filters
        resolved_whitelist = extensions_whitelist if extensions_whitelist is not None else filters.extensions_whitelist
        resolved_blacklist = extensions_blacklist if extensions_blacklist is not None else filters.extensions_blacklist
        resolved_dir_whitelist = directory_whitelist if directory_whitelist is not None else filters.directory_whitelist
        resolved_dir_blacklist = directory_blacklist if directory_blacklist is not None else filters.directory_blacklist

        if contract.restricted_path:
            resolved_scopes, resolved_paths = self._restrict_load_params(contract, resolved_scopes, resolved_paths)
        elif contract.restricted_scope:
            resolved_scopes, _ = self._restrict_load_params(contract, resolved_scopes, resolved_paths)

        if contract.restricted_extensions:
            resolved_whitelist = contract.load_filters.extensions_whitelist

        search_roots = resolved_paths if resolved_paths else tuple(scope.path for scope in resolved_scopes)

        results = self._loader.list_files(
            search_roots,
            extensions=resolved_whitelist,
            excluded_extensions=resolved_blacklist,
            excluded_directories=resolved_dir_blacklist,
        )

        if resolved_dir_whitelist:
            results = [path for path in results if any(part in resolved_dir_whitelist for part in path.parts[:-1])]

        return results

    def _list_files_under(self, contract: ClientContract, path: QPath) -> list[QPath]:
        return self._list_files_with_contract(contract, load_subpaths=(path,))

    def _list_dir_filtered(
        self, contract: ClientContract, path: QPath
    ) -> list[tuple[QPath, bool]]:
        filters = contract.load_filters
        result: list[tuple[QPath, bool]] = []
        for child, is_dir in self._loader.list_dir(path):
            if is_dir:
                result.append((child, True))
            else:
                ext = child.suffix.lower()
                if filters.extensions_whitelist and ext not in filters.extensions_whitelist:
                    continue
                if ext in filters.extensions_blacklist:
                    continue
                result.append((child, False))
        return result

    def _load_with_contract(
        self,
        contract: ClientContract,
        path: QPath,
        *,
        load_scopes: tuple[ScopeLiteral, ...] | None = None,
        load_subpaths: tuple[QPath, ...] | None = None,
    ) -> bytes:
        resolved_scopes = tuple(Scope(s) for s in load_scopes) if load_scopes is not None else contract.load_scopes
        resolved_paths = load_subpaths if load_subpaths is not None else contract.load_subpaths

        if contract.restricted_path:
            resolved_scopes, resolved_paths = self._restrict_load_params(contract, resolved_scopes, resolved_paths)
        elif contract.restricted_scope:
            resolved_scopes, _ = self._restrict_load_params(contract, resolved_scopes, resolved_paths)

        resolved_whitelist: tuple[str, ...] = ()
        if contract.restricted_extensions:
            resolved_whitelist = contract.load_filters.extensions_whitelist

        search_roots = resolved_paths if resolved_paths else tuple(scope.path for scope in resolved_scopes)

        if (contract.restricted_path or contract.restricted_scope) and not any(
            path.is_relative_to(root) for root in search_roots
        ):
            raise ValueError(f"{path} is outside allowed roots for {contract.obj_type.__name__}")

        if resolved_whitelist and path.suffix.lower() not in resolved_whitelist:
            raise ValueError(f"Suffix {path.suffix!r} not in allowed extensions {resolved_whitelist}")

        return self._loader.read_bytes(path)

    def _save_as_with_contract(
        self,
        contract: ClientContract,
        data: bytes,
        sub_path: str,
        *,
        overwrite: bool = False,
        save_scope: ScopeLiteral | None = None,
        save_subpath: QPath | None = None,
        extensions_whitelist: tuple[str, ...] | None = None,
    ) -> QPath:
        resolved_scope = Scope(save_scope) if save_scope is not None else contract.save_scope
        resolved_path = save_subpath if save_subpath is not None else contract.save_subpath
        resolved_whitelist = (
            extensions_whitelist if extensions_whitelist is not None
            else contract.load_filters.extensions_whitelist
        )

        if contract.restricted_path or contract.restricted_scope:
            resolved_scope, resolved_path = self._restrict_save_params(contract, resolved_scope, resolved_path)

        if contract.restricted_extensions:
            resolved_whitelist = contract.load_filters.extensions_whitelist

        if resolved_path is None:
            raise ValueError(f"{contract.obj_type.__name__} contract has no saving path")

        dest = resolved_path / sub_path

        if resolved_whitelist and dest.suffix.lower() not in resolved_whitelist:
            raise ValueError(f"Suffix {dest.suffix!r} not in allowed extensions {resolved_whitelist}")

        return QPath(self._loader.write_bytes(dest, data, overwrite=overwrite))

    # ── Restriction helpers ──────────────────────────────────────────────────

    def _restrict_load_params(
        self,
        contract: ClientContract,
        load_scopes: tuple[Scope, ...],
        load_subpaths: tuple[QPath, ...],
    ) -> tuple[tuple[Scope, ...], tuple[QPath, ...]]:
        restricted_scopes = tuple(scope for scope in load_scopes if scope in contract.load_scopes)
        restricted_paths = tuple(
            path for path in load_subpaths
            if any(path.is_relative_to(scope.path) for scope in contract.load_scopes)
        )
        return restricted_scopes, restricted_paths

    def _restrict_save_params(
        self,
        contract: ClientContract,
        save_scope: Scope | None,
        save_subpath: QPath | None,
    ) -> tuple[Scope | None, QPath | None]:
        restricted_scope = save_scope if save_scope == contract.save_scope else None
        restricted_path = (
            save_subpath
            if save_subpath is not None
            and contract.save_scope is not None
            and save_subpath.is_relative_to(contract.save_scope.path)
            else None
        )
        return restricted_scope, restricted_path

    def _delete_contract(self, id: int) -> None:
        self._contracts.pop(id)
