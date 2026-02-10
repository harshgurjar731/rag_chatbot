from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlmodel import Session

from database import get_session
from models.User import User
from authentication.jwt_utility import AUTH_TOKEN_SECRET_KEY, AUTH_TOKEN_ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    try:
        payload = jwt.decode(token, AUTH_TOKEN_SECRET_KEY, algorithms=[AUTH_TOKEN_ALGORITHM])
        user_id: int | None = payload.get("user_id")

        if user_id is None:
            raise HTTPException(status_code=401)

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = session.get(User, user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user
