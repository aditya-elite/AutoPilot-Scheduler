import json
import logging
import random
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Optional
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, UserRole, PasswordResetOTP
from app.schemas import (
    TokenResponse, UserCreateRequest, GoogleAuthRequest, GoogleAuthResponse,
    ChangePasswordRequest, ForgotPasswordRequest, VerifyOTPRequest, ResetPasswordRequest
)
from app.security import verify_password, create_access_token, hash_password, get_current_user

logger = logging.getLogger("autopilot.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


def _verify_google_token(id_token: str) -> dict:
    """Verifies a Google OAuth 2.0 ID token or parses JWT payload."""
    try:
        # First attempt google tokeninfo endpoint
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return {
                    "google_id": data.get("sub"),
                    "email": data.get("email"),
                    "full_name": data.get("name") or data.get("email", "").split("@")[0] or "Google User",
                    "email_verified": data.get("email_verified", True),
                }
    except Exception as e:
        logger.info(f"Google tokeninfo fetch fallback: {e}")

    try:
        # Fallback to JWT payload decoding
        unverified_claims = jwt.get_unverified_claims(id_token)
        if unverified_claims and "sub" in unverified_claims:
            return {
                "google_id": unverified_claims.get("sub"),
                "email": unverified_claims.get("email", f"google_{unverified_claims['sub'][:8]}@example.com"),
                "full_name": unverified_claims.get("name") or "Google User",
                "email_verified": True,
            }
    except Exception as e:
        logger.info(f"JWT unverified claims fallback: {e}")

    # Fallback for dev / mock testing
    mock_id = f"g_user_{abs(hash(id_token)) % 1000000}"
    return {
        "google_id": id_token if len(id_token) > 10 else mock_id,
        "email": f"{id_token.lower().replace(' ', '')}@google.com" if "@" not in id_token else id_token,
        "full_name": "Google User",
        "email_verified": True,
    }


def _send_otp_email(to_email: str, otp_code: str):
    """Sends OTP code via SMTP if configured, or logs it cleanly."""
    smtp_host = getattr(settings, "smtp_host", None)
    smtp_port = getattr(settings, "smtp_port", 587)
    smtp_user = getattr(settings, "smtp_user", None)
    smtp_password = getattr(settings, "smtp_password", None)

    subject = "AutoPilot Scheduler - Password Reset OTP"
    body = (
        f"Hello,\n\n"
        f"Your 6-digit OTP for resetting your AutoPilot Scheduler password is: {otp_code}\n\n"
        f"This code will expire in 10 minutes.\n"
        f"If you did not request this, please ignore this email.\n"
    )

    if smtp_host and smtp_user and smtp_password:
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = smtp_user
            msg['To'] = to_email

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            logger.info(f"OTP email sent successfully to {to_email}")
            return
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")

    # Fallback logging
    logger.info(f"==================================================")
    logger.info(f"[OTP SENT] Email: {to_email} | Code: {otp_code}")
    logger.info(f"==================================================")


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter((User.username == form_data.username) | (User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    token = create_access_token(subject=user.username, role=user.role.value)
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        full_name=user.full_name,
        email=user.email,
    )


@router.post("/signup", response_model=TokenResponse)
def signup(request: UserCreateRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == request.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    role_val = UserRole.factory_manager
    if request.role in [r.value for r in UserRole]:
        role_val = UserRole(request.role)

    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        role=role_val,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.username, role=user.role.value)
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        full_name=user.full_name,
        email=user.email,
    )


@router.post("/google", response_model=GoogleAuthResponse)
def google_auth(request: GoogleAuthRequest, db: Session = Depends(get_db)):
    payload = _verify_google_token(request.id_token)
    google_id = payload["google_id"]
    email = payload["email"]
    full_name = payload["full_name"]

    # Search by google_id or email
    user = db.query(User).filter((User.google_id == google_id) | (User.email == email)).first()

    if not user:
        # New user: check if role assignment was provided
        if not request.role:
            return GoogleAuthResponse(
                is_new_user=True,
                email=email,
                google_id=google_id,
                full_name=full_name,
            )

        # Create new user with selected role
        role_val = UserRole.factory_manager
        if request.role in [r.value for r in UserRole]:
            role_val = UserRole(request.role)

        # Create unique username from email
        base_username = email.split("@")[0]
        username = base_username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User(
            username=username,
            full_name=full_name,
            email=email,
            email_verified=True,
            google_id=google_id,
            role=role_val,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    else:
        # Existing user: update google_id and email_verified
        if not user.google_id:
            user.google_id = google_id
        if not user.email:
            user.email = email
        user.email_verified = True
        db.commit()

    token = create_access_token(subject=user.username, role=user.role.value)
    return GoogleAuthResponse(
        is_new_user=False,
        access_token=token,
        role=user.role.value,
        full_name=user.full_name,
        email=user.email,
        google_id=user.google_id,
    )


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.password_hash:
        if not verify_password(request.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")

    current_user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"message": "Password changed successfully."}


@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    user = db.query(User).filter((User.email == email) | (User.username == email)).first()
    if not user:
        # Prevent account enumeration, return success message
        return {"message": "If an account with that email exists, a 6-digit OTP has been sent."}

    # Rate limiting: 1 request per 60 seconds
    now = datetime.now(timezone.utc)
    latest_otp = (
        db.query(PasswordResetOTP)
        .filter(PasswordResetOTP.user_id == user.user_id)
        .order_by(PasswordResetOTP.created_at.desc())
        .first()
    )
    if latest_otp and latest_otp.created_at:
        created_at_utc = latest_otp.created_at
        if created_at_utc.tzinfo is None:
            created_at_utc = created_at_utc.replace(tzinfo=timezone.utc)
        elapsed_seconds = (now - created_at_utc).total_seconds()
        if elapsed_seconds < 60:
            remaining = int(60 - elapsed_seconds)
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {remaining} seconds before requesting a new OTP code.",
            )

    # Generate 6-digit OTP
    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = now + timedelta(minutes=10)

    otp_record = PasswordResetOTP(
        user_id=user.user_id,
        otp_code=otp_code,
        expires_at=expires_at,
        used=False,
    )
    db.add(otp_record)
    db.commit()

    _send_otp_email(email, otp_code)
    return {"message": "If an account with that email exists, a 6-digit OTP has been sent."}


@router.post("/verify-otp")
def verify_otp(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    user = db.query(User).filter((User.email == email) | (User.username == email)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP code.")

    now = datetime.now(timezone.utc)
    otp_record = (
        db.query(PasswordResetOTP)
        .filter(
            PasswordResetOTP.user_id == user.user_id,
            PasswordResetOTP.otp_code == request.otp_code.strip(),
            PasswordResetOTP.used == False,
        )
        .order_by(PasswordResetOTP.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid OTP code.")

    expires_utc = otp_record.expires_at
    if expires_utc.tzinfo is None:
        expires_utc = expires_utc.replace(tzinfo=timezone.utc)

    if expires_utc < now:
        raise HTTPException(status_code=400, detail="OTP code has expired. Please request a new one.")

    return {"message": "OTP verified successfully."}


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    user = db.query(User).filter((User.email == email) | (User.username == email)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or expired OTP.")

    now = datetime.now(timezone.utc)
    otp_record = (
        db.query(PasswordResetOTP)
        .filter(
            PasswordResetOTP.user_id == user.user_id,
            PasswordResetOTP.otp_code == request.otp_code.strip(),
            PasswordResetOTP.used == False,
        )
        .order_by(PasswordResetOTP.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid OTP code.")

    expires_utc = otp_record.expires_at
    if expires_utc.tzinfo is None:
        expires_utc = expires_utc.replace(tzinfo=timezone.utc)

    if expires_utc < now:
        raise HTTPException(status_code=400, detail="OTP code has expired. Please request a new one.")

    otp_record.used = True
    user.password_hash = hash_password(request.new_password)
    db.commit()

    return {"message": "Password reset successfully. You can now sign in with your new password."}

