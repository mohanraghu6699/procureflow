import logging
import sys

from app.config import settings

APP_LOGGER = "procureflow"


def configure_logging() -> None:
    """Send application logs to stdout in one line per event. Safe to call more than once."""
    logger = logging.getLogger(APP_LOGGER)
    logger.setLevel(settings.log_level.upper())
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    logger.addHandler(handler)
    # Left propagating on purpose: nothing else attaches a root handler when running under uvicorn,
    # and it lets pytest's caplog see these records.
