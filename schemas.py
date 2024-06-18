from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    username: str
    email: str
    # email: EmailStr
    password: str

class UserInDB(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        orm_mode = True

class Token(BaseModel):
    # access_token: str
    token: str
    # token_type: str

class RegistrationResponse(BaseModel):
    ok: bool = True

class UserResponse(BaseModel):
    data: UserInDB