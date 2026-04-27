"""Load a dictConfig payload from JSON and apply it."""
import json
import logging.config
from pathlib import Path


def configure_logging(config_path: Path) -> None:
    """Load a strict JSON logging config file and apply it."""
    config_text: str = config_path.read_text(encoding="utf-8")
    config_data: dict[str, object] = json.loads(config_text)
    logging.config.dictConfig(config_data)