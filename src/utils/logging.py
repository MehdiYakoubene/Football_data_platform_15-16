from __future__ import annotations

import logging
from pathlib import Path


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def _project_loggers() -> list[logging.Logger]:
    loggers = [logging.getLogger("__main__")]
    for name in logging.Logger.manager.loggerDict:
        if name.startswith("src.") or name.startswith("scripts."):
            loggers.append(logging.getLogger(name))
    return loggers


def get_logger(name: str) -> logging.Logger:
    """Return a project logger with a compact console format."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def configure_project_logging(quiet: bool = False, log_file: str | Path | None = None) -> None:
    """Route project logs to console, file, or both."""
    handlers: list[logging.Handler] = []

    if not quiet:
        handlers.append(logging.StreamHandler())

    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))

    if not handlers:
        handlers.append(logging.NullHandler())

    formatter = logging.Formatter(LOG_FORMAT)
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO)

    for logger in _project_loggers():
        logger.handlers.clear()
        for handler in handlers:
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
