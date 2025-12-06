from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import and_, func, or_, update
from sqlalchemy.orm import Session

from be.model.models import Inventory, Order, OrderItem


def create_order(
    session: Session,
    order_id: str,
    user_id: str,
    store_id: str,
    status: str,
    total_price: int,
    expires_at: Optional[datetime],
) -> Order:
    order = Order(
        order_id=order_id,
        user_id=user_id,
        store_id=store_id,
        status=status,
        total_price=total_price,
        expires_at=expires_at,
    )
    session.add(order)
    session.flush()
    return order


def add_order_items(
    session: Session,
    order_id: str,
    items: Iterable[Tuple[str, int, int]],
) -> None:
    order_items = [
        OrderItem(order_id=order_id, book_id=book_id, count=count, unit_price=price)
        for book_id, count, price in items
    ]
    session.add_all(order_items)
    session.flush()


def get_order(session: Session, order_id: str) -> Optional[Order]:
    return session.get(Order, order_id)


def get_order_items(session: Session, order_id: str) -> List[OrderItem]:
    return (
        session.query(OrderItem)
        .filter(OrderItem.order_id == order_id)
        .all()
    )


def update_order_status(
    session: Session,
    order_id: str,
    expected_status: str,
    new_status: str,
    **extra_fields,
) -> bool:
    stmt = (
        update(Order)
        .where(Order.order_id == order_id, Order.status == expected_status)
        .values(status=new_status, **extra_fields)
    )
    result = session.execute(stmt)
    return result.rowcount > 0


def list_orders(
    session: Session,
    user_id: str,
    status: Optional[str],
    created_from: Optional[datetime],
    created_to: Optional[datetime],
    sort_by: str,
    page: int,
    page_size: int,
) -> Tuple[int, List[Order]]:
    query = session.query(Order).filter(Order.user_id == user_id)
    if status:
        query = query.filter(Order.status == status)
    if created_from:
        query = query.filter(Order.created_at >= created_from)
    if created_to:
        query = query.filter(Order.created_at <= created_to)

    sort_column = Order.updated_at
    if sort_by == "created_at":
        sort_column = Order.created_at
    elif sort_by == "total_price":
        sort_column = Order.total_price

    total = query.with_entities(func.count()).scalar()
    orders = (
        query.order_by(sort_column.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total or 0, orders


def find_expired_pending_orders(
    session: Session, now: datetime, cutoff: Optional[datetime] = None
) -> List[Order]:
    query = session.query(Order).filter(Order.status == "pending")
    conditions = [Order.expires_at.isnot(None), Order.expires_at <= now]
    if cutoff is not None:
        query = query.filter(
            or_(
                and_(Order.expires_at.isnot(None), Order.expires_at <= now),
                and_(Order.expires_at.is_(None), Order.created_at <= cutoff),
            )
        )
    else:
        query = query.filter(
            and_(Order.expires_at.isnot(None), Order.expires_at <= now)
        )
    return query.all()


def adjust_inventory_for_items(
    session: Session,
    store_id: str,
    items: Iterable[Tuple[str, int]],
    decrease: bool = True,
) -> bool:
    for book_id, count in items:
        inv = (
            session.query(Inventory)
            .filter(
                Inventory.store_id == store_id,
                Inventory.book_id == book_id,
            )
            .with_for_update()
            .one_or_none()
        )
        if inv is None:
            return False
        delta = -count if decrease else count
        new_stock = inv.stock_level + delta
        if new_stock < 0:
            return False
        inv.stock_level = new_stock
    session.flush()
    return True
