import logging
import sys
import json
import time
from typing import Optional, Dict, Any
from contextvars import ContextVar
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

request_id_ctx: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
tenant_id_ctx: ContextVar[Optional[int]] = ContextVar('tenant_id', default=None)
user_id_ctx: ContextVar[Optional[int]] = ContextVar('user_id', default=None)
client_ip_ctx: ContextVar[Optional[str]] = ContextVar('client_ip', default=None)
user_agent_ctx: ContextVar[Optional[str]] = ContextVar('user_agent', default=None)


class JSONFormatter(logging.Formatter):
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

        request_id = request_id_ctx.get()
        tenant_id = tenant_id_ctx.get()
        user_id = user_id_ctx.get()
        client_ip = client_ip_ctx.get()
        user_agent = user_agent_ctx.get()

        if request_id:
            log_entry['request_id'] = request_id
        if tenant_id:
            log_entry['tenant_id'] = tenant_id
        if user_id:
            log_entry['user_id'] = user_id
        if client_ip:
            log_entry['client_ip'] = client_ip
        if user_agent:
            log_entry['user_agent'] = user_agent

        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        if hasattr(record, 'props'):
            log_entry.update(record.props)

        return json.dumps(log_entry, default=str)


class SecurityFilter(logging.Filter):
    SENSITIVE_FIELDS = {
        'password', 'token', 'secret', 'key', 'authorization',
        'jwt', 'bearer', 'credit_card', 'cvv', 'ssn'
    }

    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self._sanitize_message(record.msg)
        if hasattr(record, 'args') and record.args:
            record.args = tuple(
                self._sanitize_message(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True

    def _sanitize_message(self, message: str) -> str:
        import re
        patterns = [
            (r'("password"\s*:\s*)"[^"]*"', r'\1"***"'),
            (r'("token"\s*:\s*)"[^"]*"', r'\1"***"'),
            (r'("secret"\s*:\s*)"[^"]*"', r'\1"***"'),
            (r'("key"\s*:\s*)"[^"]*"', r'\1"***"'),
            (r'("authorization"\s*:\s*)"[^"]*"', r'\1"***"'),
            (r'(Bearer\s+)[^\s]+', r'\1***'),
            (r'(\b\d{16}\b)', '****************'),
            (r'(\b\d{3}-\d{2}-\d{4}\b)', '***-**-****'),
        ]
        for pattern, replacement in patterns:
            message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
        return message


class DatabaseLogLevelHandler:
    """Handler that dynamically gets log level from database"""

    def __init__(self):
        self._handlers_configured = False

    def setup_handlers(self, log_level: str = "INFO", json_format: bool = True):
        """Setup logging handlers with dynamic level"""
        if self._handlers_configured:
            return

        logger = logging.getLogger()

        # Clear existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Set level
        level = getattr(logging, log_level.upper(), logging.INFO)
        logger.setLevel(level)

        # Create handler
        handler = logging.StreamHandler(sys.stdout)

        # Set formatter
        if json_format:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - '
                '[tenant:%(tenant_id)s] [user:%(user_id)s] [req:%(request_id)s] - %(message)s'
            )
        handler.setFormatter(formatter)

        # Add security filter
        security_filter = SecurityFilter()
        handler.addFilter(security_filter)

        logger.addHandler(handler)

        # Set levels for noisy loggers
        logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

        self._handlers_configured = True

        logger.info(f"Logging configured from database", extra={
            "props": {
                "level": log_level,
                "json_format": json_format
            }
        })


# Global handler instance
_db_log_handler = DatabaseLogLevelHandler()


def setup_logging(log_level: str = "INFO", json_format: bool = True):
    """Setup logging with initial configuration"""
    _db_log_handler.setup_handlers(log_level, json_format)


async def update_log_level(log_level: str):
    """Update log level dynamically (call this when config changes)"""
    logger = logging.getLogger()
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Update all handlers
    for handler in logger.handlers:
        handler.setLevel(level)

    logging.info(f"Log level updated dynamically to {log_level}")


def get_logger(name: str) -> logging.Logger:
    """Get logger instance - this will use the dynamically configured level"""
    logger = logging.getLogger(name)
    return logger


class RequestContext:
    def __init__(self, request_id: str, tenant_id: int = None, user_id: int = None,
                 client_ip: str = None, user_agent: str = None):
        self.request_id = request_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.client_ip = client_ip
        self.user_agent = user_agent
        self.tokens = []

    def __enter__(self):
        self.tokens.append(request_id_ctx.set(self.request_id))
        if self.tenant_id is not None:
            self.tokens.append(tenant_id_ctx.set(self.tenant_id))
        if self.user_id is not None:
            self.tokens.append(user_id_ctx.set(self.user_id))
        if self.client_ip is not None:
            self.tokens.append(client_ip_ctx.set(self.client_ip))
        if self.user_agent is not None:
            self.tokens.append(user_agent_ctx.set(self.user_agent))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for token in self.tokens:
            token.var.set(token.old_value)


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.logger = get_logger(__name__)

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        tenant_id = request.headers.get('x-tenant-id')
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get('user-agent', '')

        with RequestContext(
                request_id=request_id,
                tenant_id=int(tenant_id) if tenant_id and tenant_id.isdigit() else None,
                client_ip=client_ip,
                user_agent=user_agent
        ):
            self.logger.info(
                "Request started",
                extra={
                    "props": {
                        "method": request.method,
                        "url": str(request.url),
                        "client_ip": client_ip,
                        "user_agent": user_agent
                    }
                }
            )

            start_time = time.time()
            try:
                response = await call_next(request)
                process_time = time.time() - start_time

                self.logger.info(
                    "Request completed",
                    extra={
                        "props": {
                            "method": request.method,
                            "url": str(request.url),
                            "status_code": response.status_code,
                            "process_time": round(process_time, 4)
                        }
                    }
                )

                response.headers["X-Request-ID"] = request_id
                response.headers["X-Process-Time"] = str(round(process_time, 4))
                return response

            except Exception as e:
                process_time = time.time() - start_time
                self.logger.error(
                    "Request failed",
                    extra={
                        "props": {
                            "method": request.method,
                            "url": str(request.url),
                            "process_time": round(process_time, 4),
                            "error": str(e)
                        }
                    },
                    exc_info=True
                )
                raise


# Initialize with default level - will be updated when database config is loaded
setup_logging()