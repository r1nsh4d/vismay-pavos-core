from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from uuid import UUID

from app.models import User, AuthToken

SECRET_KEY = "your-super-secret-key-change-in-prod"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthMgmt:

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(db: Session, user_id: UUID) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "type": "access",
            "exp": expire,
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def create_refresh_token(db: Session, user_id: UUID) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": expire,
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def store_refresh_token(db: Session, user_id: UUID, refresh_token: str):
        # Revoke old refresh token
        old_token = db.query(AuthToken).filter(
            AuthToken.user_id == user_id,
            AuthToken.is_active == True,
        ).first()
        if old_token:
            old_token.is_active = False

        # Store new refresh token
        new_token = AuthToken(
            user_id=user_id,
            refresh_token=refresh_token,
            is_active=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(new_token)
        db.commit()

    @staticmethod
    def validate_refresh_token(db: Session, refresh_token: str) -> UUID | None:
        try:
            token_obj = db.query(AuthToken).filter(
                AuthToken.refresh_token == refresh_token,
                AuthToken.is_active == True,
                AuthToken.expires_at > datetime.now(timezone.utc),
            ).first()
            if not token_obj:
                return None
            payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            token_type = payload.get("type")
            if token_type != "refresh":
                return None
            return UUID(payload["sub"])
        except (JWTError, KeyError, ValueError):
            return None

    @staticmethod
    def validate_access_token(db: Session, token: str) -> UUID | None:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            token_type = payload.get("type")
            if token_type != "access":
                return None
            user_id = payload.get("sub")
            if not user_id:
                return None
            # Optional: check user exists and is active
            user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
            if not user:
                return None
            return UUID(user_id)
        except (JWTError, KeyError, ValueError):
            return None

    @staticmethod
    def authenticate_user(db: Session, login: str, password: str) -> User | None:
        user = db.query(User).filter(
            (User.username == login) | (User.email == login)
        ).first()
        if not user or not user.is_active:
            return None
        if not AuthMgmt.verify_password(password, user.password_hash):
            return None
        return user