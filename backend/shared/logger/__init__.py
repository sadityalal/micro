import logging
import sys
import os
import json
from datetime import datetime
from contextvars import ContextVar
from typing import Optional, Dict, Any
import uuid

request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)

# Log level mapping
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

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

def get_log_level(level_name: str) -> int:
    """Get log level from string, default to INFO if not found"""
    return LOG_LEVELS.get(level_name.upper(), logging.INFO)

def setup_logger(name: str, level: Optional[str] = None, level_int: Optional[int] = None) -> logging.Logger:
    """
    Setup logger with level from database configuration or default
    
    Args:
        name: Logger name
        level: Log level as string (from database)
        level_int: Log level as integer (fallback)
    """
    logger = logging.getLogger(name)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Determine log level
    if level_int is not None:
        log_level = level_int
    elif level is not None:
        log_level = get_log_level(level)
    else:
        log_level = logging.INFO  # Default fallback
        
    logger.setLevel(log_level)
    
    # Use /app/logs path (will be mounted to project logs directory)
    logs_dir = "/app/logs"
    
    # Console handler (always available)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    console_handler.addFilter(ContextFilter())
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)
    
    # File handler - will work when directory is mounted
    try:
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, f"{name}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        file_handler.addFilter(ContextFilter())
        file_handler.setLevel(log_level)
        logger.addHandler(file_handler)
    except Exception as e:
        # If file logging fails, we still have console logging
        print(f"Warning: File logging disabled: {e}")
    
    logger.propagate = False
    return logger

# Create loggers with default levels (will be updated by services)
api_gateway_logger = setup_logger("api-gateway")
auth_service_logger = setup_logger("auth-service")
rate_limiter_logger = setup_logger("rate-limiter")
session_manager_logger = setup_logger("session-manager")
