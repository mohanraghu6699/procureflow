import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db
from app.dependencies import get_user_allowing_password_change, require_roles
from app.models import Delivery, PRStatusHistory, PurchaseOrder, PurchaseRequest, User, UserRole
from app.schemas import ChangePasswordRequest, LoginRequest, PasswordReset, TokenResponse, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("procureflow.auth")


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        department_id=user.department_id,
        department_name=user.department.name if user.department else None,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        logger.warning("Login failed for %s", payload.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        logger.warning("Login refused for inactive user %s", user.email)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    logger.info("Login succeeded for %s (%s)", user.email, user.role.value)
    token = create_access_token(subject=user.id, extra_claims={"role": user.role.value})
    return TokenResponse(access_token=token, user=_to_user_out(user))


# /me and the password change are the only endpoints open to a user who still has to choose a new password.
@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_user_allowing_password_change)):
    return _to_user_out(current_user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_allowing_password_change),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        logger.warning("Password change refused for %s: wrong current password", current_user.email)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different from the current one"
        )

    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    db.commit()
    logger.info("Password changed for %s", current_user.email)


# ---------- User administration (admin only) ----------


def _get_user_or_404(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _refuse_own_account(user: User, admin: User, action: str) -> None:
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"You can't {action} your own account")


def _activity_count(db: Session, user_id: str) -> int:
    """How many records in the system point at this user (requests, status changes, orders, deliveries)."""
    return (
        db.query(PurchaseRequest).filter(PurchaseRequest.requester_id == user_id).count()
        + db.query(PRStatusHistory).filter(PRStatusHistory.changed_by_id == user_id).count()
        + db.query(PurchaseOrder)
        .filter((PurchaseOrder.created_by_id == user_id) | (PurchaseOrder.cancelled_by_id == user_id))
        .count()
        + db.query(Delivery).filter(Delivery.updated_by_id == user_id).count()
    )


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        department_id=payload.department_id,
        must_change_password=True,  # the admin knows this password, so the user chooses their own at first sign-in
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("User %s (%s) created by %s", user.email, user.role.value, admin.email)
    return _to_user_out(user)


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    users = db.query(User).order_by(User.name).all()
    return [_to_user_out(u) for u in users]


@router.post("/users/{user_id}/reset-password", response_model=UserOut)
def reset_password(
    user_id: str,
    payload: PasswordReset,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Stands in for a forgot-password flow: the admin sets a temporary password, the user must replace it."""
    user = _get_user_or_404(db, user_id)
    _refuse_own_account(user, admin, "reset the password of")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = True
    db.commit()
    db.refresh(user)
    logger.info("Password of %s reset by %s (change required at next sign-in)", user.email, admin.email)
    return _to_user_out(user)


@router.post("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Blocks sign-in (existing sessions stop working immediately) and keeps the user's history."""
    user = _get_user_or_404(db, user_id)
    _refuse_own_account(user, admin, "deactivate")
    user.is_active = False
    db.commit()
    db.refresh(user)
    logger.info("User %s deactivated by %s", user.email, admin.email)
    return _to_user_out(user)


@router.post("/users/{user_id}/reactivate", response_model=UserOut)
def reactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    user = _get_user_or_404(db, user_id)
    user.is_active = True
    db.commit()
    db.refresh(user)
    logger.info("User %s reactivated by %s", user.email, admin.email)
    return _to_user_out(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Removes an account that has never done anything (for example one created by mistake)."""
    user = _get_user_or_404(db, user_id)
    _refuse_own_account(user, admin, "delete")
    records = _activity_count(db, user.id)
    if records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This user has {records} record{'s' if records != 1 else ''} in the system and can't be deleted; deactivate the account instead",
        )
    email = user.email
    db.delete(user)
    db.commit()
    logger.info("User %s deleted by %s", email, admin.email)
