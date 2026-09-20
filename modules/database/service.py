from . import async_session
from datetime import datetime, timedelta
from dataclasses import replace
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from .dal import AccountDAL, UserDAL
from .models import Account, FuelCard, FuelCardOperation, User


class DatabaseService:
    """Centralized service for database operations"""

    @staticmethod
    async def get_user(user_id: int) -> User | None:
        """Get user by Telegram user_id"""
        async with async_session() as session:
            user_dal = UserDAL(session)
            return await user_dal.get_by_user_id(user_id)

    @staticmethod
    async def create_user(user_id: int, mail: str | None = None) -> User:
        """Create new user"""
        async with async_session() as session:
            user_dal = UserDAL(session)
            user = await user_dal.create(user_id, mail)
            await session.commit()
            return user

    @staticmethod
    async def update_user(user_id: int, **kwargs) -> User | None:
        """Update user fields"""
        async with async_session() as session:
            user_dal = UserDAL(session)
            user = await user_dal.update(user_id, **kwargs)
            await session.commit()
            return user

    @staticmethod
    async def create_account(user_id: int, login: str, password_hash: str) -> Account:
        """Create new account for user"""
        async with async_session() as session:
            account_dal = AccountDAL(session)
            account = await account_dal.create(user_id, login, password_hash)
            await session.commit()
            return account

    @staticmethod
    async def get_account(user_id: int) -> Account | None:
        """Get account of user"""
        async with async_session() as session:
            account_dal = AccountDAL(session)
            return await account_dal.get_by_user_id(user_id)

    @staticmethod
    async def update_account(account_id: int, **kwargs) -> Account | None:
        """Update account fields"""
        async with async_session() as session:
            account_dal = AccountDAL(session)
            account = await account_dal.update(account_id, **kwargs)
            await session.commit()
            return account

    @staticmethod
    async def set_user_active(user_id: int) -> User | None:
        """Mark user as active"""
        return await DatabaseService.update_user(user_id)

    @staticmethod
    async def save_card_snapshot(card_record, operation_records, inserted_records=None) -> int:
        """Store a card and insert only operations not seen before."""
        async with async_session() as session:
            card = await session.scalar(select(FuelCard).where(FuelCard.external_id == card_record.external_id))
            if card is None:
                card = FuelCard(
                    external_id=card_record.external_id,
                    name=card_record.name,
                    detail_url=card_record.url,
                )
                session.add(card)
                await session.flush()
            else:
                card.name = card_record.name
                card.detail_url = card_record.url

            inserted = 0
            for record in operation_records:
                exists = await session.scalar(
                    select(FuelCardOperation.id).where(FuelCardOperation.external_id == record.external_id)
                )
                if exists is not None:
                    continue
                session.add(
                    FuelCardOperation(
                        card_id=card.id,
                        external_id=record.external_id,
                        occurred_at=record.occurred_at,
                        operation_type=record.operation_type,
                        amount=record.amount,
                        quantity=record.quantity,
                        station=record.station,
                        transaction_number=record.transaction_number,
                        dispenser=record.dispenser,
                        fuel=record.fuel,
                        unit_price=record.unit_price,
                        issuer=record.issuer,
                        card_number=record.card_number,
                        holder=record.holder,
                        contract=record.contract,
                        fuel_balance=record.fuel_balance,
                    )
                )
                if inserted_records is not None:
                    inserted_records.append(record)
                inserted += 1
            await session.commit()
            return inserted

    @staticmethod
    async def recalculate_fuel_balances(
        days: int = 60,
        operation_records: list | None = None,
    ) -> int:
        """Recalculate balances from the latest persisted balance per card."""
        since = datetime.now() - timedelta(days=days)
        async with async_session() as session:
            rows = (
                await session.execute(
                    select(FuelCard.external_id, FuelCardOperation)
                    .join(FuelCardOperation.card)
                )
            ).all()
            operations_by_card = {}
            for card_number, operation in rows:
                occurred_at = DatabaseService._operation_datetime(operation.occurred_at)
                if occurred_at is not None and occurred_at >= since:
                    operations_by_card.setdefault(card_number, []).append(operation)

            updated = 0
            for operations in operations_by_card.values():
                operations.sort(
                    key=lambda operation: DatabaseService._operation_datetime(operation.occurred_at)
                    or datetime.min
                )
                seeded_operations = [
                    operation for operation in operations if operation.fuel_balance is not None
                ]
                if not seeded_operations:
                    continue

                seed = seeded_operations[-1]
                try:
                    balance = Decimal(str(seed.fuel_balance).replace(",", "."))
                except InvalidOperation:
                    continue
                seed_index = operations.index(seed)

                for operation in operations[seed_index + 1:]:
                    balance += DatabaseService._signed_movement(operation)
                    operation.fuel_balance = DatabaseService._format_balance(balance)
                    updated += 1

                balance = Decimal(str(seed.fuel_balance).replace(",", "."))
                for operation in reversed(operations[:seed_index]):
                    balance -= DatabaseService._signed_movement(operation)
                    operation.fuel_balance = DatabaseService._format_balance(balance)
                    updated += 1

            if operation_records:
                balances = {
                    operation.external_id: operation.fuel_balance
                    for operations in operations_by_card.values()
                    for operation in operations
                }
                for index, record in enumerate(operation_records):
                    operation_records[index] = replace(
                        record,
                        fuel_balance=balances.get(record.external_id),
                    )

            await session.commit()
            return updated

    @staticmethod
    def _signed_movement(operation) -> Decimal:
        value = operation.quantity if operation.operation_type == "0" else operation.amount
        try:
            movement = Decimal(str(value).replace(",", "."))
        except (InvalidOperation, AttributeError):
            movement = Decimal("0")
        return -movement if operation.operation_type == "0" else movement

    @staticmethod
    def _format_balance(balance: Decimal) -> str:
        return format(balance.quantize(Decimal("0.01")), "f")

    @staticmethod
    def _operation_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        for pattern in ("%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value.strip(), pattern)
            except ValueError:
                continue
        return None
