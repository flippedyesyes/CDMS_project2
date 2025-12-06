from typing import Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from be.model.models import User


def create_user(
    session: Session,
    user_id: str,
    password: str,
    token: str,
    terminal: str,
) -> User:
    user = User(
        user_id=user_id,
        password=password,
        balance=0,
        token=token,
        terminal=terminal,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise
    return user


def get_user(
    session: Session, user_id: str, include_inactive: bool = False
) -> Optional[User]:
    user = session.get(User, user_id)
    if user is None:
        return None
    if not include_inactive and user.status != "active":
        return None
    return user


def delete_user(session: Session, user_id: str) -> bool:
    user = session.get(User, user_id)
    if user is None:
        return False
    session.delete(user)
    return True


def soft_delete_user(session: Session, user_id: str) -> bool:
    user = session.get(User, user_id)
    if user is None:
        return False
    user.status = "deleted"
    user.token = None
    user.terminal = None
    session.flush()
    return True


def revive_user(
    session: Session,
    user: User,
    password: str,
    token: str,
    terminal: str,
) -> User:
    user.password = password
    user.balance = 0
    user.token = token
    user.terminal = terminal
    user.status = "active"
    session.flush()
    return user


def update_token(
    session: Session, user_id: str, token: str, terminal: str
) -> bool:
    stmt = (
        update(User)
        .where(User.user_id == user_id)
        .values(token=token, terminal=terminal)
    )
    result = session.execute(stmt)
    return result.rowcount > 0


def update_password(
    session: Session,
    user_id: str,
    new_password: str,
    token: str,
    terminal: str,
) -> bool:
    stmt = (
        update(User)
        .where(User.user_id == user_id)
        .values(password=new_password, token=token, terminal=terminal)
    )
    result = session.execute(stmt)
    return result.rowcount > 0


def change_balance(session: Session, user_id: str, delta: int) -> bool:
    user = session.get(User, user_id)
    if user is None:
        return False
    new_balance = user.balance + delta
    if new_balance < 0:
        return False
    user.balance = new_balance
    session.flush()
    return True
