from loguru import logger
import sys
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def setup_logging(env: str = "dev"):
    """Configure logging settings for the application."""
    logger.remove()

    console_log_levels = {
        "dev": "DEBUG",
        "test": "INFO",
        "prod": "WARNING",
    }
    console_level = console_log_levels.get(env, "DEBUG")

    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "app.log",
        rotation="10 MB",
        retention="1 days",
        compression="zip",
        level="DEBUG",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    logger.add(
        sys.stderr,
        level=console_level,
        format="<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>",
        colorize=True,
    )

