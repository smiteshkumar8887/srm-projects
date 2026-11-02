from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)


def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.query(models.User).filter(models.User.email == email.lower().strip()).first()


def create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    phone: str,
    password: str,
    address: str | None = None,
) -> models.User:
    user = models.User(
        full_name=full_name.strip(),
        email=email.lower().strip(),
        phone=phone.strip(),
        password_hash=hash_password(password),
        address=(address or "").strip() or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> models.User | None:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user
