"""
This module provides the `get_current_user` dependency for Clerk-based authentication.
It replaces the previous email/password-based `get_current_user` from `routers/auth.py`.
"""
# core/clerk_auth.py
import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt, ExpiredSignatureError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from core.database import get_db
from models.user import User

logger = logging.getLogger(__name__)

# HTTPBearer extracts the token from "Authorization: Bearer <token>".
# auto_error=True means FastAPI returns 403 automatically if the header
# is missing, before our code even runs.
_bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Clerk JWT verification + find-or-create user dependency.

    Flow:
      1. Verify JWT signature using Clerk's RSA public key (RS256)
      2. Extract clerk_user_id and email from token claims
      3. Look up user by clerk_user_id → found: return user
      4. Fall back to email → found: backfill clerk_user_id, return user
      5. Neither found: create new User row, return it

    Steps 4 and 5 handle the migration window where existing users have
    a FlowDesk account but no clerk_user_id yet.
    """
    token = credentials.credentials

    # ── Step 1: verify and decode ─────────────────────────────────────────
    try:
        payload = jwt.decode(
            token,
            # Clerk's signing key is an RSA public key in PEM format.
            # Store it in .env as a single line with literal \n between sections,
            # or use a multiline env var. python-jose handles both.
            settings.CLERK_JWT_SIGNING_KEY,
            algorithms=["RS256"],
            # Clerk sets aud to your Frontend API URL in some templates.
            # If your JWT template sets no audience, pass options={"verify_aud": False}
            options={"verify_aud": False},
        )
    except ExpiredSignatureError as exc:
        logger.warning("Clerk JWT expired: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as exc:
        logger.warning("Clerk JWT verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Step 2: extract claims ────────────────────────────────────────────
    # "user_id" is the custom claim added in the Clerk JWT template.
    # "email" is typically in the top-level claims or inside "email_addresses".
    # Adjust the claim keys to match your exact Clerk JWT template output.
    clerk_user_id: str | None = payload.get("user_id")
    email: str | None = payload.get("email")

    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user_id claim — check your Clerk JWT template",
        )

    try:
        # ── Step 3: look up by clerk_user_id ─────────────────────────────────
        result = await db.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()
        if user is not None:
            return user

        # ── Step 4: fall back to email (migration path for existing users) ────
        if email:
            result = await db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()
            if user is not None:
                # Backfill clerk_user_id so future requests hit step 3 directly
                user.clerk_user_id = clerk_user_id
                await db.commit()
                await db.refresh(user)
                logger.info(
                    "Backfilled clerk_user_id for existing user %s", user.id
                )
                return user

        # ── Step 5: new Clerk user — provision a FlowDesk row ─────────────────
        # hashed_password is left as an empty string — the column stays in schema
        # but is never used for Clerk-authenticated users.
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing email claim — cannot provision user",
            )

        new_user = User(
            email=email,
            clerk_user_id=clerk_user_id,
            hashed_password="",   # intentionally blank — Clerk owns auth
            is_active=True,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info("Auto-provisioned new user for Clerk ID %s", clerk_user_id)
        return new_user
    except SQLAlchemyError as exc:
        logger.error("Database error during Clerk user find-or-create: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database error during user authentication"
        )