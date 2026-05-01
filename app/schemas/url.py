from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl, field_serializer


class URLCreate(BaseModel):
    original_url: HttpUrl


class URLResponse(BaseModel):
    id: int
    original_url: str
    short_code: str 
    short_url: str =""
    clicks: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("original_url")
    def serialize_original_url(self, v: str) -> str:
        return str(v)


class URLAnalytics(BaseModel):
    id: int
    short_code: str
    short_url: str=""
    original_url: str
    clicks: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)