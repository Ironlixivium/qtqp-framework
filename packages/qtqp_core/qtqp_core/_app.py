from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QGuiApplication
from q_signalkit import QSignal
from q_signalkit.qt_slot import QSlot

type GuiCapabilityLiteral = Literal["non-gui", "windowing", "widgets"]

class _GuiCapability(Enum):
    _value_: GuiCapabilityLiteral
    WINDOWING = "windowing"
    WIDGETS = "widgets"

_ERRORS = {
    "display_name": "Non-gui applications have no display name."
}

@dataclass(slots=True)
class AppConfig:
    gui_capability: GuiCapabilityLiteral
    display_name: str | None
    name: str
    owner_name: str | None
    version: str
    website: str | None

@dataclass(slots=True)
class _Signals:
    about_to_quit: QSignal[()] = field(default_factory=QSignal[()])
    display_name_changed: QSignal[(str)] = field(default_factory=QSignal[(str)])
    name_changed: QSignal[(str)] = field(default_factory=QSignal[(str)])

class QtQpApplicationController:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._capability = _GuiCapability(self._config.gui_capability)
        self._instance: QGuiApplication
        self.signals = _Signals()
        
    @property
    def display_name(self) -> str:
        return self._instance.applicationDisplayName()
    
    @property
    def gui_capability(self) -> _GuiCapability:
        return self._capability
    
    @property
    def name(self) -> str:
        return self._instance.applicationName()
    
    @property
    def owner_name(self) -> str:
        return self._instance.organizationName()
    
    @property
    def version(self) -> str:
        return self._instance.applicationVersion()
    
    @property
    def website(self) -> str:
        return self._instance.organizationDomain()

    @QSlot
    def set_display_name(self, display_name: str) -> None:
        self._config.display_name = display_name
        with QSignalBlocker(self._instance):
            self._instance.setApplicationDisplayName(display_name)
    @QSlot
    def set_name(self, name: str) -> None:
        self._config.name = name
        with QSignalBlocker(self._instance):
            self._instance.setApplicationName(name)
    
    @QSlot
    def set_owner_name(self, owner_name: str) -> None:
        self._config.owner_name = owner_name
        with QSignalBlocker(self._instance):
            self._instance.setOrganizationName(owner_name)

    @QSlot
    def set_version(self, version: str) -> None:
        self._config.version = version
        with QSignalBlocker(self._instance):
            self._instance.setApplicationVersion(version)

    @QSlot
    def set_website(self, website: str) -> None:
        self._config.website = website
        with QSignalBlocker(self._instance):
            self._instance.setOrganizationDomain(website)

    def run(self) -> None:
        self._instance.exec()

    def shutdown_request(self) -> None:
        self._instance.quit()
    
    def shutdown_force(self) -> None:
        self._instance.exit()

    def instantiate(self) -> None:
        bad = QGuiApplication.instance()
        if bad is not None:
            raise Exception("Do not instantiate any version of QCoreApplication outside of QtQpCore.")


        if self._capability == _GuiCapability.WINDOWING:
            app = QGuiApplication()
        else:
            from PySide6.QtWidgets import QApplication

            app = QApplication()

            # QApplication config
            # none so far!

        
        # Name
        app.setApplicationName(self._config.name)
        app.applicationNameChanged.connect(lambda: self.set_name(self._config.name))

        # Display name

        if self._config.display_name is not None:
            app.setApplicationDisplayName(self._config.display_name)
        app.applicationDisplayNameChanged.connect(lambda: self.set_display_name(self._config.display_name))

        # Version
        app.setApplicationVersion(self._config.version)
        app.applicationVersionChanged.connect(lambda: self.set_version(self._config.version))

        # Owner name
        if self._config.owner_name is not None:
            app.setOrganizationName(self._config.owner_name)
        app.organizationNameChanged.connect(lambda: self.set_owner_name(self._config.owner_name))

        # Website
        if self._config.website is not None:
            app.setOrganizationDomain(self._config.website)
        app.organizationDomainChanged.connect(lambda: self.set_website(self._config.website))

        # Quit locks
        app.setQuitLockEnabled(False)
        app.setQuitOnLastWindowClosed(False)

        self._instance = app

    def _connect_qt_signals(self) -> None:
        self._instance.aboutToQuit.connect(self.signals.about_to_quit.emit)
        self._instance.applicationDisplayNameChanged.connect(self.signals.display_name_changed.emit)
        self._instance.applicationNameChanged.connect(self.signals.name_changed.emit)






