"""
Admin-only user management. Restricted to the 'admin' role via
`require_role("admin")` on every endpoint here — a factory manager
can run the schedule, but only an admin can create/deactivate
accounts or change someone's role.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, AuditLog
from app.schemas import UserOut, UserCreateRequest, UserUpdateRequest
from app.security import require_role, hash_password

router = APIRouter(prefix="/admin/users", tags=["admin"])


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        user_id=str(user.user_id),
        username=user.username,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
    )


@router.get("", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), _admin=Depends(require_role("admin"))):
    users = db.query(User).order_by(User.username).all()
    return [_to_user_out(u) for u in users]


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    request: UserCreateRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_role("admin")),
):
    if request.role not in UserRole._value2member_map_:
        raise HTTPException(status_code=400, detail=f"Invalid role '{request.role}'")
    if db.query(User).filter(User.username == request.username).first():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        role=UserRole(request.role),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    db.add(AuditLog(
        entity_type="user",
        entity_id=0,  # user_id is a UUID, not a bigint; entity_type + new_value carries identity here
        action="create",
        new_value={"username": user.username, "role": user.role.value},
        changed_by=admin.user_id,
    ))
    db.commit()

    return _to_user_out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    request: UserUpdateRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_role("admin")),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if str(user.user_id) == str(admin.user_id) and request.is_active is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")

    old_value = {"full_name": user.full_name, "role": user.role.value, "is_active": user.is_active}

    if request.full_name is not None:
        user.full_name = request.full_name
    if request.role is not None:
        if request.role not in UserRole._value2member_map_:
            raise HTTPException(status_code=400, detail=f"Invalid role '{request.role}'")
        user.role = UserRole(request.role)
    if request.is_active is not None:
        user.is_active = request.is_active

    db.add(AuditLog(
        entity_type="user",
        entity_id=0,
        action="update",
        old_value=old_value,
        new_value={"full_name": user.full_name, "role": user.role.value, "is_active": user.is_active},
        changed_by=admin.user_id,
    ))
    db.commit()
    db.refresh(user)

    return _to_user_out(user)
