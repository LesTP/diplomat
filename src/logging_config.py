from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml


DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(config_path: str | Path) -> None:
    config = _load_config(config_path)
    logging_config = config.get("logging", {})
    if not isinstance(logging_config, dict):
        logging_config = {}

    level_name = os.getenv(
        "DIPLOMAT_LOG_LEVEL",
        str(logging_config.get("level", "INFO")),
    )
    log_format = str(logging_config.get("format", DEFAULT_LOG_FORMAT))
    level = _level_from_name(level_name)

    logger = logging.getLogger("diplomat")
    logger.setLevel(level)
    logger.propagate = False

    handler = _existing_handler(logger)
    if handler is None:
        handler = logging.StreamHandler()
        setattr(handler, "_diplomat_handler", True)
        logger.addHandler(handler)
    handler.setLevel(logging.NOTSET)
    handler.setFormatter(logging.Formatter(log_format))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"diplomat.{name}")


def _load_config(config_path: str | Path) -> dict[str, Any]:
    try:
        config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    except OSError:
        return {}
    return config if isinstance(config, dict) else {}


def _level_from_name(level_name: str) -> int:
    level = logging.getLevelName(level_name.strip().upper())
    if isinstance(level, int):
        return level
    return logging.INFO


def _existing_handler(logger: logging.Logger) -> logging.Handler | None:
    for handler in logger.handlers:
        if getattr(handler, "_diplomat_handler", False):
            return handler
    return None
