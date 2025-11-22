import logging
from contextvars import ContextVar
from typing import Optional, Dict, Any
import uuid

# Context variables for request-scoped data
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)


class ContextFilter(logging.Filter):
    """Add context information to log records"""

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
    """Set context for logging"""
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    if tenant_id:
        tenant_id_var.set(tenant_id)


def generate_request_id() -> str:
    """Generate a unique request ID"""
    return f"req_{uuid.uuid4().hex[:8]}"


def get_logging_context() -> Dict[str, Any]:
    """Get current logging context"""
    return {
        "request_id": request_id_var.get(),
        "user_id": user_id_var.get(),
        "tenant_id": tenant_id_var.get()
    }