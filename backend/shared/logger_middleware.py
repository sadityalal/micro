import logging
import sys
from typing import Optional
import json
import time
from contextvars import ContextVar

# Context variables for request-specific data
request_id_ctx: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
tenant_id_ctx: ContextVar[Optional[int]] = ContextVar('tenant_id', default=None)
user_id_ctx: ContextVar[Optional[int]] = ContextVar('user_id', default=None)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record):
        log_entry = {
            'timestamp': time.time(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add context information
        request_id = request_id_ctx.get()
        tenant_id = tenant_id_ctx.get()
        user_id = user_id_ctx.get()

        if request_id:
            log_entry['request_id'] = request_id
        if tenant_id:
            log_entry['tenant_id'] = tenant_id
        if user_id:
            log_entry['user_id'] = user_id

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(level: str = "INFO", json_format: bool = False):
    """Setup logging configuration"""

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)

    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [tenant:%(tenant_id)s] [user:%(user_id)s] - %(message)s'
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance with contextual information"""
    return logging.getLogger(name)


class RequestContext:
    """Context manager for request-specific logging context"""

    def __init__(self, request_id: str, tenant_id: int = None, user_id: int = None):
        self.request_id = request_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.token = None

    def __enter__(self):
        self.token = request_id_ctx.set(self.request_id)
        if self.tenant_id is not None:
            tenant_id_ctx.set(self.tenant_id)
        if self.user_id is not None:
            user_id_ctx.set(self.user_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            request_id_ctx.reset(self.token)
        tenant_id_ctx.set(None)
        user_id_ctx.set(None)


# Initialize logging on module import
setup_logging()