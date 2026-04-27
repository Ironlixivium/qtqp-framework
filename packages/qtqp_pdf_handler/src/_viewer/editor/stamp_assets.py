"""Stamp asset registry for storing and caching images."""

import shutil
import uuid
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QPixmap


class StampRegistry:
    def __init__(self) -> None:
        self._assets: dict[str, Path] = {}
        self._full_pixmaps: dict[str, QPixmap] = {}
        self._preview_pixmaps: dict[str, QPixmap] = {}
        self._load_existing_assets()

    def _base_dir(self) -> Path:
        root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        if not root:
            root = str(Path.home() / ".local" / "share")
        return Path(root) / "stamps"

    def _load_existing_assets(self) -> None:
        base_dir = self._base_dir()
        if not base_dir.exists():
            return
        for path in base_dir.iterdir():
            if not path.is_file():
                continue
            stamp_id = path.stem
            if stamp_id:
                self._assets[stamp_id] = path

    def register_from_file(self, path: str) -> str:
        src = Path(path)
        if not src.exists():
            raise FileNotFoundError(str(src))
        dst_dir = self._base_dir()
        dst_dir.mkdir(parents=True, exist_ok=True)
        stamp_id = uuid.uuid4().hex
        ext = src.suffix or ".png"
        dst = dst_dir / f"{stamp_id}{ext}"
        shutil.copy2(src, dst)
        self._assets[stamp_id] = dst
        return stamp_id

    def resolve_path(self, stamp_asset_id: str) -> Path | None:
        return self._assets.get(stamp_asset_id)

    def get_pixmap(self, stamp_asset_id: str, *, preview: bool) -> QPixmap:
        path = self.resolve_path(stamp_asset_id)
        if path is None:
            return QPixmap()
        if not preview:
            cached = self._full_pixmaps.get(stamp_asset_id)
            if cached is not None:
                return cached
            pix = QPixmap(str(path))
            self._full_pixmaps[stamp_asset_id] = pix
            return pix

        cached = self._preview_pixmaps.get(stamp_asset_id)
        if cached is not None:
            return cached

        full = self._full_pixmaps.get(stamp_asset_id)
        if full is None:
            full = QPixmap(str(path))
            self._full_pixmaps[stamp_asset_id] = full
        if full.isNull():
            self._preview_pixmaps[stamp_asset_id] = full
            return full
        max_side = max(full.width(), full.height())
        max_dim = 1024
        if max_side > max_dim:
            scale = max_dim / max_side
            target_w = max(1, int(full.width() * scale))
            target_h = max(1, int(full.height() * scale))
            preview_pix = full.scaled(
                target_w,
                target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            preview_pix = full
        self._preview_pixmaps[stamp_asset_id] = preview_pix
        return preview_pix

    def pixmap(self, stamp_asset_id: str) -> QPixmap:
        return self.get_pixmap(stamp_asset_id, preview=False)
