import logging
import sys
import os
import json
from datetime import datetime
from contextvars import ContextVar
from typing import Optional, Dict, Any
import uuid

# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)


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

        # Add context information
        request_id = request_id_var.get()
        user_id = user_id_var.get()
        tenant_id = tenant_id_var.get()

        if request_id:
            log_entry["request_id"] = request_id
        if user_id:
            log_entry["user_id"] = user_id
        if tenant_id:
            log_entry["tenant_id"] = tenant_id

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class ContextFilter(logging.Filter):
    def filter(self, record):
        request_id = request_id_var.get()
        user_id = user_id_var.get()
        tenant_id = tenant_id_var.get()

        if request_id:
            record.request_id = request_id
        if user_id:
            record.user_id = user_id
        if tenant_id:
            record.tenant_id = tenant_id

        return True


def set_logging_context(
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None
):
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    if tenant_id:
        tenant_id_var.set(tenant_id)


def generate_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:8]}"


def get_logging_context() -> Dict[str, Any]:
    return {
        "request_id": request_id_var.get(),
        "user_id": user_id_var.get(),
        "tenant_id": tenant_id_var.get()
    }


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Create logs directory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    logs_dir = os.path.join(project_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_file = os.path.join(logs_dir, f"{name}.log")

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(JSONFormatter())
    file_handler.addFilter(ContextFilter())

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    console_handler.addFilter(ContextFilter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger


# Create loggers
api_gateway_logger = setup_logger("api-gateway")
auth_service_logger = setup_logger("auth-service")