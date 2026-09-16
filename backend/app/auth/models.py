from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128, description="Username or system identifier")
    password: str = Field(..., min_length=1, max_length=256, description="Plaintext password")


class PermissionRead(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    resource: str
    action: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class RoleRead(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_system: bool = False
    created_at: str
    updated_at: str
    permissions: List[str] = Field(default_factory=list, description="List of permission identifiers e.g. users.read")

    model_config = ConfigDict(from_attributes=True)


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    description: Optional[str] = Field(default=None, max_length=255)
    permissions: List[str] = Field(default_factory=list, description="List of permission identifiers to grant")


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    description: Optional[str] = Field(default=None, max_length=255)
    permissions: Optional[List[str]] = None


class UserRead(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    is_active: bool = True
    created_at: str
    updated_at: str
    last_login_at: Optional[str] = None
    roles: List[str] = Field(default_factory=list, description="Assigned role names")
    permissions: List[str] = Field(default_factory=list, description="Effective permission names")

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    password: str = Field(..., min_length=8, max_length=256)
    email: Optional[str] = Field(default=None, max_length=255, pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")
    roles: List[str] = Field(default_factory=list, description="Role names to assign, defaults to viewer if empty")
    is_active: bool = True


class UserUpdate(BaseModel):
    email: Optional[str] = Field(default=None, max_length=255, pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: Optional[str] = Field(default=None, min_length=8, max_length=256)
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AuthMeResponse(BaseModel):
    user: UserRead
    effective_permissions: List[str]


class LoginResponse(BaseModel):
    success: bool = True
    user: UserRead
    effective_permissions: List[str]
