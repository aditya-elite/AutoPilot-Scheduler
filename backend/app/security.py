"""
Authentication and role-based authorization.

Design choices:
  * Passwords are hashed with bcrypt (passlib) — never stored or
    compared in plaintext.
  * Sessions are stateless JWTs signed with a server-side secret
    (app.config.settings.jwt_secret_key). The token carries the
    user's id and role so every request can be authorized without a
    DB round trip for role checks (a DB lookup still happens to
    confirm the account is still active).
  * `require_role(...)` is a dependency FACTORY — routers declare the
    minimum role required per-endpoint, e.g.
        Depends(require_role("factory_manager"))
    which keeps authorization logic out of business logic entirely.
"""
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Role hierarchy: admin > factory_manager > machine_operator.
# Used so `require_role("machine_operator")` still admits managers/admins.
_ROLE_RANK = {
    UserRole.machine_operator: 0,
    UserRole.factory_manager: 1,
    UserRole.admin: 2,
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_role(minimum_role: str):
    """Dependency factory: rejects any user below `minimum_role` in the hierarchy."""
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        required_rank = _ROLE_RANK[UserRole(minimum_role)]
        user_rank = _ROLE_RANK[UserRole(current_user.role)]
        if user_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{minimum_role}' or higher.",
            )
        return current_user
    return _dependency
