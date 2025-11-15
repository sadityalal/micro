from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import time

class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: float

class ServiceHealth(BaseModel):
    service: str
    status: str
    response_time: float
    timestamp: float

class GatewayResponse(BaseModel):
    message: str
    status: str
    available_services: List[str]
    timestamp: float

class ErrorResponse(BaseModel):
    error: str
    detail: str
    code: int
    timestamp: float

class ServiceStatus(BaseModel):
    name: str
    url: str
    status: str
    last_checked: float

class GatewayStats(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    services: Dict[str, ServiceStatus]

class ProxyRequest(BaseModel):
    service: str
    path: str
    method: str
    headers: Dict[str, str]
    body: Optional[Dict[str, Any]] = None

class ProxyResponse(BaseModel):
    status_code: int
    headers: Dict[str, str]
    body: Dict[str, Any]
    response_time: float

class UserContext(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    roles: List[str] = []
    tenant_id: int = 1

class RateLimitInfo(BaseModel):
    limit: int
    remaining: int
    reset_time: int

class RequestLog(BaseModel):
    request_id: str
    method: str
    path: str
    service: str
    user_id: Optional[int] = None
    tenant_id: int = 1
    status_code: int
    response_time: float
    timestamp: float
    user_agent: Optional[str] = None
    client_ip: Optional[str] = None