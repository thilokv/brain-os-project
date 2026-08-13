"""Structured logging configuration for Brain OS."""

import logging
import sys


def configure_logging(log_level: str = "INFO") -> None:
    """Configure root logging once for the whole process."""
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g. re-imported under the test runner).
        root.setLevel(log_level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root.addHandler(handler)
    root.setLevel(log_level)

    # Quiet down noisy third-party loggers unless we're debugging.
    for noisy in ("httpx", "httpcore", "chromadb", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
