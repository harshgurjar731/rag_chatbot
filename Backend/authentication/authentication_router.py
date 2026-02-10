from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from database import get_session
from authentication.authentication_model import UserResponse, UserSignupRequest, UserLoginRequest
from models.User import User
from authentication.password_hashing import hash_password, verify_password
from authentication.jwt_utility import create_access_token

router = APIRouter()


@router.post("/signup", response_model=UserResponse)
def signup(
    payload: UserSignupRequest,
    session: Session = Depends(get_session),
):
    print("Signup payload", payload)
    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Passwords do not match"
        )

    existing_user = session.exec(
        select(User).where(User.username == payload.username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Username already exists"
        )

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        department=payload.department,
    )
    print("Signup hash password", hash_password(payload.password))

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


@router.post("/login")
def login(
    payload: UserLoginRequest,
    session: Session = Depends(get_session),
):
    user = session.exec(
        select(User).where(User.username == payload.username)
    ).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "department": user.department,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "department": user.department
        },
    }
