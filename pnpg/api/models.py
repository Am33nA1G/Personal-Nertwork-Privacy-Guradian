"""Pydantic request and response models for the API layer."""

from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int


class ListResponse(BaseModel, Generic[T]):
    data: list[T]
    pagination: Pagination


class SingleResponse(BaseModel, Generic[T]):
    data: T


class LoginRequest(BaseModel):
    password: str


class SetupRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AllowlistRuleCreate(BaseModel):
    process_name: Optional[str] = None
    dst_ip: Optional[str] = None
    dst_hostname: Optional[str] = None
    expires_at: Optional[datetime] = None
    reason: Optional[str] = None


class AlertAction(BaseModel):
    action: str = Field(..., pattern="^(suppress|resolve)$")
    reason: Optional[str] = None


class SuppressionCreate(BaseModel):
    rule_id: str
    process_name: Optional[str] = None
    scope: str = Field(..., pattern="^(single|rule)$")
    reason: Optional[str] = None


class ThreatEvent(BaseModel):
    threat_id: str
    detected_at: datetime
    severity: str
    threat_type: str
    process_name: str
    pid: int
    dst_ip: str
    dst_hostname: Optional[str] = None
    reason: str
    confidence: float
    status: str = "active"
    remediation_status: Optional[str] = None
    killed_at: Optional[datetime] = None
    block_ip_at: Optional[datetime] = None


class RemediationAction(BaseModel):
    action: str = Field(..., pattern="^(kill|block_ip)$")
    reason: Optional[str] = None
