from pydantic import BaseModel

class UserSignupRequest(BaseModel):
    username: str
    password: str
    confirm_password: str
    department: str


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    department: str