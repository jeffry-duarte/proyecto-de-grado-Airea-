from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AdminRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AdminUserUpdateRequest(AdminRequest):
    name: str = Field(min_length=2, max_length=100)
    locality: str = Field(min_length=1, max_length=100)
    favoriteStationId: str = Field(min_length=1, max_length=80)
    healthProfile: Literal["general", "cyclist", "respiratory", "elderly"]
    notificationsEnabled: bool
    role: Literal["citizen", "admin"]


class NoticeRequest(AdminRequest):
    title: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=3, max_length=1000)
    severity: Literal["info", "warning", "critical"]
    published: bool


class StationOverrideRequest(AdminRequest):
    name: str = Field(min_length=2, max_length=100)
    zone: str = Field(min_length=2, max_length=160)
    active: bool


class AirQualityThresholdsRequest(AdminRequest):
    moderate: int = Field(ge=1, le=500)
    sensitive: int = Field(ge=1, le=500)
    high: int = Field(ge=1, le=500)

    @model_validator(mode="after")
    def thresholds_must_be_increasing(self):
        if not self.moderate < self.sensitive < self.high:
            raise ValueError("Los umbrales deben ir en orden ascendente.")
        return self
