import logging
import sys
from typing import Optional

LOGGER_NAME = "webprobe"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
DEFAULT_LEVEL = logging.INFO

_CONFIGURED = False


def configure_logging(level: Optional[int] = None) -> None:
    """Configure the shared webprobe logger once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root_logger = logging.getLogger(LOGGER_NAME)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, "%Y-%m-%d %H:%M:%S"))
    root_logger.addHandler(handler)
    root_logger.setLevel(level or DEFAULT_LEVEL)
    root_logger.propagate = False
    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Return a namespaced logger prefixed with the webprobe package name.
    """
    configure_logging()
    if not name:
        return logging.getLogger(LOGGER_NAME)

    full_name = name
    if not name.startswith(LOGGER_NAME):
        full_name = f"{LOGGER_NAME}.{name}"
    return logging.getLogger(full_name)
