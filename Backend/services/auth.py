"""
Auth Service
────────────
Password hashing, user registration, and authentication.
"""

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, FreelancerProfile
from models.pfi import PFIScore
from schemas.auth import UserRegister

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, data: UserRegister) -> User:
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise ValueError("Email already registered")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        name=data.name,
    )
    db.add(user)
    await db.flush()

    # Create freelancer profile if applicable
    if data.role == "freelancer":
        profile = FreelancerProfile(
            user_id=user.id,
            skills=data.skills or [],
            bio=data.bio,
        )
        db.add(profile)

        # Initialise PFI score
        pfi = PFIScore(user_id=user.id)
        db.add(pfi)

    await db.flush()
    # Refresh to load selectin relationships (freelancer_profile)
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid email or password")
    return user
