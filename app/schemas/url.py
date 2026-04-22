from pydantic import BaseModel,ConfigDict,HttpUrl
from datetime import datetime

class URLCreate(BaseModel):
    original_url:HttpUrl

class URLResponse(BaseModel):
    id:int
    original_url:HttpUrl
    short_code:str
    clicks:int
    is_active:bool
    created_at:datetime

    model_config=ConfigDict(from_attributes=True)
