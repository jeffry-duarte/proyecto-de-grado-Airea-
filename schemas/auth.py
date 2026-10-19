from pydantic import BaseModel, ConfigDict, Field


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=False)


class RegisterRequest(RequestModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=1, max_length=300)
    password: str = Field(min_length=1, max_length=256)
    locality: str = Field(min_length=1, max_length=200)
    favoriteStationId: str = Field(min_length=1, max_length=160)
    healthProfile: str
    notificationsEnabled: bool = True
    inviteCode: str | None = None


class BootstrapAdminRequest(RegisterRequest):
    setupToken: str = ""


class LoginRequest(RequestModel):
    email: str
    password: str = Field(max_length=256)


class ProfileUpdateRequest(RequestModel):
    locality: str = Field(min_length=1, max_length=200)
    favoriteStationId: str = Field(min_length=1, max_length=160)
    healthProfile: str
    notificationsEnabled: bool


class AdminInviteRequest(RequestModel):
    email: str = Field(min_length=1, max_length=300)
