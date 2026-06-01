from __future__ import annotations

import logging

import pytest


@pytest.fixture(autouse=True)
def quiet_diplomat_logs():
    logger = logging.getLogger("diplomat")
    old_level = logger.level
    old_handlers = list(logger.handlers)
    old_propagate = logger.propagate
    logger.setLevel(logging.WARNING)
    logger.handlers = []
    logger.propagate = True
    try:
        yield
    finally:
        logger.setLevel(old_level)
        logger.handlers = old_handlers
        logger.propagate = old_propagate
