from datetime import datetime, timedelta
from jose import jwt
import os

AUTH_TOKEN_SECRET_KEY = os.getenv("AUTH_TOKEN_SECRET_KEY", "CHANGE_THIS_SECRET")
AUTH_TOKEN_ALGORITHM = os.getenv("AUTH_TOKEN_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, AUTH_TOKEN_SECRET_KEY, algorithm=AUTH_TOKEN_ALGORITHM)
