import logging
import sys
import json
import time
from typing import Optional, Dict, Any
from contextvars import ContextVar
import uuid
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware

# Context variables for request-scoped data
request_id_ctx: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
tenant_id_ctx: ContextVar[Optional[int]] = ContextVar('tenant_id', default=None)
user_id_ctx: ContextVar[Optional[int]] = ContextVar('user_id', default=None)
client_ip_ctx: ContextVar[Optional[str]] = ContextVar('client_ip', default=None)
user_agent_ctx: ContextVar[Optional[str]] = ContextVar('user_agent', default=None)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

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

        # Add exception information
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, 'props'):
            log_entry.update(record.props)

        return json.dumps(log_entry, default=str)


class SecurityFilter(logging.Filter):
    """Filter to prevent logging of sensitive information"""

    SENSITIVE_FIELDS = {
        'password', 'token', 'secret', 'key', 'authorization',
        'jwt', 'bearer', 'credit_card', 'cvv', 'ssn'
    }

    def filter(self, record):
        # Sanitize message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self._sanitize_message(record.msg)

        # Sanitize args
        if hasattr(record, 'args') and record.args:
            record.args = tuple(
                self._sanitize_message(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )

        return True

    def _sanitize_message(self, message: str) -> str:
        """Sanitize sensitive information in log messages"""
        import re

        # Mask passwords and tokens
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


def setup_logging(level: str = "INFO", json_format: bool = True):
    """Setup logging configuration"""

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

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

    # Add handler to logger
    logger.addHandler(handler)

    # Set levels for noisy loggers
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    # Add startup message
    logger.info("Logging configured", extra={
        "props": {
            "level": level,
            "json_format": json_format,
            "environment": "production"
        }
    })


def get_logger(name: str) -> logging.Logger:
    """Get logger with context awareness"""
    logger = logging.getLogger(name)
    return logger


class RequestContext:
    """Context manager for request-scoped logging context"""

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
    """Middleware for request logging and context management"""

    def __init__(self, app):
        super().__init__(app)
        self.logger = get_logger(__name__)

    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())

        # Extract context information
        tenant_id = request.headers.get('x-tenant-id')
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get('user-agent', '')

        # Set up logging context
        with RequestContext(
                request_id=request_id,
                tenant_id=int(tenant_id) if tenant_id and tenant_id.isdigit() else None,
                client_ip=client_ip,
                user_agent=user_agent
        ):
            # Log request start
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

                # Log request completion
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

                # Add headers
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Process-Time"] = str(round(process_time, 4))

                return response

            except Exception as e:
                process_time = time.time() - start_time

                # Log request error
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


# Initialize logging
setup_logging()