from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase): ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)  # Telegram user_id
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")

    def has_account(self) -> bool:
        return len(self.accounts) > 0


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    login = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)  # Store hashed password
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="accounts")

    def is_active_account(self) -> bool:
        return bool(self.is_active)


class FuelCard(Base):
    __tablename__ = "fuel_cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    detail_url = Column(String(1000), nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    operations = relationship("FuelCardOperation", back_populates="card", cascade="all, delete-orphan")


class FuelCardOperation(Base):
    __tablename__ = "fuel_card_operations"
    __table_args__ = (UniqueConstraint("external_id", name="uq_fuel_card_operation_external_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(Integer, ForeignKey("fuel_cards.id"), nullable=False, index=True)
    external_id = Column(String(255), nullable=False)
    occurred_at = Column(String(100), nullable=True)
    operation_type = Column(String(255), nullable=False)
    amount = Column(String(100), nullable=True)
    quantity = Column(String(100), nullable=True)
    station = Column(String(255), nullable=True)
    transaction_number = Column(String(100), nullable=True)
    dispenser = Column(String(100), nullable=True)
    fuel = Column(String(100), nullable=True)
    unit_price = Column(String(100), nullable=True)
    issuer = Column(String(255), nullable=True)
    card_number = Column(String(100), nullable=True, index=True)
    holder = Column(String(255), nullable=True)
    contract = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    card = relationship("FuelCard", back_populates="operations")
