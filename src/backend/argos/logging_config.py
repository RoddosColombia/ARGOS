from __future__ import annotations

import logging
import sys

try:
    from pythonjsonlogger.json import JsonFormatter
except ImportError:  # python-json-logger < 3.x
    from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore[no-redef]


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    for noisy in ("uvicorn.access", "uvicorn.error", "uvicorn"):
        logging.getLogger(noisy).handlers = [handler]
        logging.getLogger(noisy).propagate = False
