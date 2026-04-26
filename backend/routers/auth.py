from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordBearer

from core.database import get_db
from core.security import hash_password, verify_password, create_access_token, decode_access_token
from models.user import User
from schemas.user import UserCreate, UserLogin, UserOut, Token
from core.clerk_auth import get_current_user as get_authenticated_user  # ← rename to avoid name clash

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Tells FastAPI where to extract the token from headers for protected routes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    """Dependency to retrieve the current user based on the provided JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
        
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
        
    # Async query to find user by email
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    return user


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,  # ← FastAPI marks this with a strikethrough in /docs
    summary="[DEPRECATED] Register with password — use Clerk instead",
)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # DEPRECATED: Clerk handles registration. This endpoint will be removed
    # once all clients have migrated. Do not use for new integrations.
    """Registers a new user."""
    # Check if user already exists
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create and persist new user
    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        timezone=user_data.timezone
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.post(
    "/login",
    response_model=Token,
    deprecated=True,
    summary="[DEPRECATED] Login with password — use Clerk instead",
)
async def login_user(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    # DEPRECATED: Clerk handles login. This endpoint will be removed
    # once all clients have migrated. Do not use for new integrations.
    """Authenticates a user and returns a JWT."""
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Payload 'sub' (subject) represents the user identifier
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
async def read_users_me(current_user: User = Depends(get_authenticated_user)):
    """Returns the currently authenticated user's profile."""
    return current_user