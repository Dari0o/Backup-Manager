import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent
LOG_FILE = LOG_DIR / "backup_manager.log"


def _build_formatter() -> logging.Formatter:
    return logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def setup_logger(name: str = "backup_manager", level: int = logging.DEBUG) -> logging.Logger:
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        return logger

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(_build_formatter())

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(_build_formatter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


setup_logger()
