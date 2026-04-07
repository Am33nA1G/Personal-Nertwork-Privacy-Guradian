"""JWT auth endpoints and dependencies."""

import json
import logging
import os
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from pnpg.api.deps import get_config
from pnpg.api.models import LoginRequest, SetupRequest


warnings.filterwarnings("ignore", ".*error reading bcrypt version.*")

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)
router = APIRouter(tags=["auth"])


def hash_password(password: str) -> str:
    """Hash a password, falling back to direct bcrypt when passlib is incompatible."""
    try:
        return pwd_context.hash(password)
    except Exception:  # noqa: BLE001
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash with a direct fallback path."""
    try:
        return pwd_context.verify(password, password_hash)
    except Exception:  # noqa: BLE001
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )


def resolve_jwt_secret(config: dict) -> str:
    """Resolve and persist the JWT secret following the configured precedence."""
    existing = config.get("jwt_secret")
    if existing:
        return existing

    env_secret = os.getenv("PNPG_JWT_SECRET")
    if env_secret:
        config["jwt_secret"] = env_secret
        return env_secret

    secrets_path = Path("data/secrets.json")
    if secrets_path.exists():
        payload = json.loads(secrets_path.read_text(encoding="utf-8"))
        file_secret = payload.get("jwt_secret")
        if file_secret:
            config["jwt_secret"] = file_secret
            return file_secret

    generated = secrets.token_hex(32)
    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    secrets_path.write_text(
        json.dumps({"jwt_secret": generated}, indent=2),
        encoding="utf-8",
    )
    logger.warning("JWT secret auto-generated")
    config["jwt_secret"] = generated
    return generated


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    config: dict = Depends(get_config),
) -> str:
    """Validate the bearer token and return the current subject."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    secret = resolve_jwt_secret(config)
    try:
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
        )
        subject = payload.get("sub")
        if not subject:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return subject
    except (JWTError, ExpiredSignatureError) as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or expired token"
        ) from exc


@router.post("/auth/setup")
async def setup_auth(body: SetupRequest, request: Request) -> dict:
    """Create the initial password hash on first run."""
    if not request.app.state.needs_setup:
        raise HTTPException(status_code=409, detail="Already configured")

    hashed = hash_password(body.password)
    config = request.app.state.config
    auth_path = Path(config["auth_file"])
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(json.dumps({"hash": hashed}, indent=2), encoding="utf-8")

    request.app.state.password_hash = hashed
    request.app.state.needs_setup = False
    return {"data": {"message": "Password set successfully"}}


@router.post("/auth/login")
async def login(body: LoginRequest, request: Request) -> dict:
    """Issue access and refresh tokens for the single local user."""
    if request.app.state.needs_setup:
        raise HTTPException(status_code=503, detail="Run setup first")

    stored_hash = request.app.state.password_hash
    if not stored_hash or not verify_password(body.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid password")

    config = request.app.state.config
    secret = resolve_jwt_secret(config)
    now = datetime.now(timezone.utc)
    access_token = jwt.encode(
        {
            "sub": "pnpg-user",
            "iat": now,
            "exp": now + timedelta(hours=config["jwt_expiry_hours"]),
        },
        secret,
        algorithm="HS256",
    )
    refresh_token = jwt.encode(
        {
            "sub": "pnpg-user",
            "iat": now,
            "exp": now + timedelta(days=30),
            "type": "refresh",
        },
        secret,
        algorithm="HS256",
    )
    return {
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    }
