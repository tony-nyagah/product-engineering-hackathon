from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models import User
from schemas import UserCreate, UserResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    exists = await db.execute(select(User).where(User.username == user_in.username))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(**user_in.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
