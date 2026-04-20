from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    timezone: str | None = "Asia/Kolkata"

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Schema for returning user data. Note: No password field included.
class UserOut(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime

    # Pydantic v2 equivalent of orm_mode = True
    # Tells Pydantic to read data even if it's not a dict, but an ORM model
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str