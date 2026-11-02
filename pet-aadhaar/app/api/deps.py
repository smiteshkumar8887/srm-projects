from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_db


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> models.User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    user = db.get(models.User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> models.User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(models.User, user_id)
