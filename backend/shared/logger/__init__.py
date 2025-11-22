import logging
import sys
from typing import Optional
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add extra fields if present
        if hasattr(record, 'extra'):
            log_entry.update(record.extra)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logger(
        name: str,
        level: int = logging.INFO,
        format: str = "json",  # "json" or "text"
        extra_handlers: Optional[list] = None
) -> logging.Logger:
    """
    Setup and return a logger with consistent configuration

    Args:
        name: Logger name (usually __name__)
        level: Logging level
        format: "json" for structured logs, "text" for human-readable
        extra_handlers: Additional logging handlers
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)

    # Set formatter based on format type
    if format == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add extra handlers if provided
    if extra_handlers:
        for handler in extra_handlers:
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

    return logger


# Create default logger
default_logger = setup_logger("shared")