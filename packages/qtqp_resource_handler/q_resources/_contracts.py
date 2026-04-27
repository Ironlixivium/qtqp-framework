from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject
from qtqp_path import QPath

from ._scopes import Scope


@dataclass(slots=True, frozen=True)
class LoadFilters:
    """Filtering rules applied when listing files across loading scopes.
    Attributes:
        extensions_whitelist: Empty shows files with any extension.
        extensions_blacklist:
        directory_whitelist: Empty shows files from directories regardless of name.
        directory_blacklist:
    """
    extensions_whitelist: tuple[str, ...]
    extensions_blacklist: tuple[str, ...] = ()
    directory_whitelist: tuple[str, ...] = ()
    directory_blacklist: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OpsProvider:
    """Keyring of contract-aware I/O callables injected into FileBrowserWidget."""
    list_files: Callable[[ClientContract], list[QPath]]
    list_dir_filtered: Callable[[ClientContract, QPath], list[tuple[QPath, bool]]]
    list_files_under: Callable[[ClientContract, QPath], list[QPath]]
    load: Callable[[ClientContract, QPath], bytes]
    save_as: Callable[[ClientContract, bytes, str], QPath]


@dataclass(slots=True, frozen=True)
class ClientContract:
    """Holds the resolved I/O configuration for a registered QObject.
    Attributes:
        load_filters: Filtering rules for listing appropriate files.
        load_scopes: Root directories to search. [Base-Dirs]
        load_paths:
        obj_id: Client's python id
        obj_type: Client's type, for verification.
        restricted_extensions: True = saving and loading is restricted to extensions in extensions_whitelist.
        restricted_path: True = saving and loading is restricted to the given path, inside the scope. \
            Overrides restricted_scope
        restricted_scope: True = Saving and loading is restricted to the scope.
        save_scope: Default site for save operations, or None if saving is disabled. [Base-Dir]
        save_subpath: Resolved destination for save operations.[Sub-Dir]
    """
    load_filters: LoadFilters
    load_subpaths: tuple[QPath, ...]
    load_scopes: tuple[Scope, ...]
    obj_id: int
    obj_type: type[QObject]
    restricted_extensions: bool
    restricted_path: bool
    restricted_scope: bool
    save_subpath: QPath | None
    save_scope: Scope | None

