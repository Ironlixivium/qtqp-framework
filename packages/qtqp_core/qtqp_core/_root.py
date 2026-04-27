import logging
import sys
import time
from types import TracebackType
from typing import Never

from ._app import GuiCapabilityLiteral
from ._overseer import OVERSEER

logger = logging.getLogger(__name__)

def _replace_excepthook() -> None:
    original_excepthook = sys.excepthook

    def logging_excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        
        logger.exception(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        original_excepthook(exc_type, exc_value, exc_traceback)
    
    sys.excepthook = logging_excepthook

class _AppFrame(type):
    def __enter__(self) -> None:
        OVERSEER.instantiate_application()
        _replace_excepthook()


    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None
    ) -> None:
        if OVERSEER.state.qt_application_started is False:
            raise Exception("Application was not run. Call run_application to run App.")
        
        if exc_type is None:
            time.sleep(3)
            if OVERSEER.state.qt_application_running is True:
                OVERSEER.shutdown_application(forced=True)


class QtQpRoot(metaclass=_AppFrame):
    def __new__(cls) -> Never:
        raise NotImplementedError

    def __init__(self) -> Never:
        raise NotImplementedError
    
    @staticmethod
    def setup_application(
        *,
        name: str,
        gui_capability: GuiCapabilityLiteral,
        version: str,
        display_name: str | None = None,
        owner_name: str | None = None,
        website: str | None = None,
    ) -> None:
        OVERSEER.configure_application(
            name=name,
            display_name=display_name,
            gui_capability=gui_capability,
            owner_name=owner_name,
            version=version,
            website=website,
        )

    def __enter__(self) -> None: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None
    ) -> None: ...

    @staticmethod
    def run_application() -> None:
        OVERSEER.run_application()
    
    @staticmethod
    def shutdown_application() -> None:
        OVERSEER.shutdown_application()