from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class IPCError(BaseModel):
    code: str
    message: str


class IPCRequest(BaseModel):
    version: int = Field(default=1, description="IPC protocol version")
    requestId: str = Field(..., description="Unique request tracing ID")
    operation: str = Field(..., description="Target operation name (e.g. systemd.service_status)")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Operation arguments")


class IPCResponse(BaseModel):
    version: int = Field(default=1, description="IPC protocol version")
    requestId: str = Field(..., description="Correlated request tracing ID")
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[IPCError] = None
