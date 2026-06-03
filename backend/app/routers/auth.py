from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, UserRole
from app.models.base_object import ObjectType
from app.services.object_service import create_object

router = APIRouter(prefix="/auth", tags=["auth"])


class UserProfileResponse(BaseModel):
    id: int
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    language: str
    avatar_url: str | None
    totp_enabled: bool

    class Config:
        from_attributes = True


class RegisterRequest(BaseModel):
    firebase_uid: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None


@router.post("/register", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def register_user(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.firebase_uid == data.firebase_uid))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already exists")

    obj_id = await create_object(db, ObjectType.user)
    user = User(
        id=obj_id,
        firebase_uid=data.firebase_uid,
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        avatar_url=data.avatar_url,
        role=UserRole.customer,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user=Depends(get_current_user)):
    return current_user
