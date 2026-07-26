from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceRegistrationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    installation_id: str = Field(
        alias="installationId",
        min_length=36,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]{36,64}$",
    )


class ProfileResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    assistant_name: str = Field(alias="assistantName")
    updated_at: datetime = Field(alias="updatedAt")


class DeviceRegistrationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    expires_at: datetime = Field(alias="expiresAt")
    profile: ProfileResponse


class ProfilePatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assistant_name: str | None = Field(default=None, alias="assistantName")


class UsageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    daily_used: int = Field(alias="dailyUsed")
    daily_limit: int = Field(alias="dailyLimit")
    monthly_used: int = Field(alias="monthlyUsed")
    monthly_limit: int = Field(alias="monthlyLimit")
