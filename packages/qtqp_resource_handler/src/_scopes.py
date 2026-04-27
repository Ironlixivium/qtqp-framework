from enum import Enum
from typing import TYPE_CHECKING, Literal, assert_never, cast

from platformdirs import PlatformDirs
from qtqp.path import QPath


def create_dirs(app_name: str):
    """Must be called AFTER _q_app.ensure_qt_app"""
    global dirs
    dirs = PlatformDirs(app_name, "Quinn Plite", "1")

type ScopeLiteral = Literal[
    "config",
    "cwd",
    "home",
    "Qt",
    "root",
    "site_applications",
    "site_bin",
    "site_cache",
    "site_config",
    "site_data",
    "site_log",
    "site_runtime",
    "site_state",
    "user_applications",
    "user_bin",
    "user_cache",
    "user_config",
    "user_data",
    "user_desktop",
    "user_documents",
    "user_downloads",
    "user_log",
    "user_music",
    "user_pictures",
    "user_runtime",
    "user_state",
    "user_videos",
]

class Scope(Enum):
    CONFIG = "config"
    CWD = "cwd"
    HOME = "home"
    QT = "Qt"
    ROOT = "root"
    SITE_APPLICATIONS = "site_applications"
    SITE_BIN = "site_bin"
    SITE_CACHE = "site_cache"
    SITE_CONFIG = "site_config"
    SITE_DATA = "site_data"
    SITE_LOG = "site_log"
    SITE_RUNTIME = "site_runtime"
    SITE_STATE = "site_state"
    USER_APPLICATIONS = "user_applications"
    USER_BIN = "user_bin"
    USER_CACHE = "user_cache"
    USER_CONFIG = "user_config"
    USER_DATA = "user_data"
    USER_DESKTOP = "user_desktop"
    USER_DOCUMENTS = "user_documents"
    USER_DOWNLOADS = "user_downloads"
    USER_LOG = "user_log"
    USER_MUSIC = "user_music"
    USER_PICTURES = "user_pictures"
    USER_RUNTIME = "user_runtime"
    USER_STATE = "user_state"
    USER_VIDEOS = "user_videos"

    _value_: ScopeLiteral
    @property
    def path(self: Scope) -> QPath:
        match self:
            case Scope.CWD:
                return QPath.cwd()
            case Scope.HOME:
                return QPath.home()
            case Scope.QT:
                return QPath(f":/{dirs.appname}")
            case Scope.ROOT:
                return QPath(QPath.cwd().anchor)
            case _:
                return QPath(getattr(dirs, f"{self.value}_path")) # PlatformDirs

if TYPE_CHECKING:
    match cast(ScopeLiteral, None):
        case Scope.CONFIG.value: ...
        case Scope.CWD.value: ...
        case Scope.HOME.value: ...
        case Scope.QT.value: ...
        case Scope.ROOT.value: ...
        case Scope.SITE_APPLICATIONS.value: ...
        case Scope.SITE_BIN.value: ...
        case Scope.SITE_CACHE.value: ...
        case Scope.SITE_CONFIG.value: ...
        case Scope.SITE_DATA.value: ...
        case Scope.SITE_LOG.value: ...
        case Scope.SITE_RUNTIME.value: ...
        case Scope.SITE_STATE.value: ...
        case Scope.USER_APPLICATIONS.value: ...
        case Scope.USER_BIN.value: ...
        case Scope.USER_CACHE.value: ...
        case Scope.USER_CONFIG.value: ...
        case Scope.USER_DATA.value: ...
        case Scope.USER_DESKTOP.value: ...
        case Scope.USER_DOCUMENTS.value: ...
        case Scope.USER_DOWNLOADS.value: ...
        case Scope.USER_LOG.value: ...
        case Scope.USER_MUSIC.value: ...
        case Scope.USER_PICTURES.value: ...
        case Scope.USER_RUNTIME.value: ...
        case Scope.USER_STATE.value: ...
        case Scope.USER_VIDEOS.value: ...
        case _:
            assert_never()


