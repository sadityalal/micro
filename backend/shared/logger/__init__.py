import logging
import sys
import os
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

        # Add context if available
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        if hasattr(record, 'tenant_id'):
            log_entry["tenant_id"] = record.tenant_id

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def get_log_level_from_config() -> int:
    """Get log level from database configuration"""
    try:
        from shared.database.connection import get_db
        from shared.database.config_service import db_config_service

        db_gen = get_db()
        db_session = next(db_gen)
        try:
            config = db_config_service.get_tenant_config(db_session, 1)  # Default tenant
            log_level_str = config["logging"]["log_level"].upper()

            log_levels = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL
            }

            return log_levels.get(log_level_str, logging.INFO)

        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    except Exception as e:
        # Fallback if database not available
        print(f"Failed to get log level from database: {e}")
        return logging.INFO


def setup_logger(
        name: str,
        level: Optional[int] = None,
        format: str = "json",
        extra_handlers: Optional[list] = None
) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    # Get log level from database, fallback to INFO
    if level is None:
        level = get_log_level_from_config()

    logger.setLevel(level)

    # Log to root project directory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    logs_dir = os.path.join(project_root, "logs")

    # Use logger name for log file
    log_file = os.path.join(logs_dir, f"{name}.log")

    # Ensure log directory exists
    os.makedirs(logs_dir, exist_ok=True)

    # File handler for service-specific logs
    file_handler = logging.FileHandler(log_file)

    # Console handler for all logs
    console_handler = logging.StreamHandler(sys.stdout)

    if format == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    if extra_handlers:
        for handler in extra_handlers:
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    logger.propagate = False

    logger.info(f"Logger initialized with level: {logging.getLevelName(level)}")
    return logger


# Service-specific loggers
api_gateway_logger = setup_logger("api-gateway")
auth_service_logger = setup_logger("auth-service")