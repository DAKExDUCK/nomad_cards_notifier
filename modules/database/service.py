from dataclasses import replace
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from . import async_session
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
            card_statement = (
                insert(FuelCard)
                .values(
                    external_id=card_record.external_id,
                    name=card_record.name,
                    detail_url=card_record.url,
                )
                .on_conflict_do_update(
                    index_elements=[FuelCard.external_id],
                    set_={
                        "name": card_record.name,
                        "detail_url": card_record.url,
                    },
                )
                .returning(FuelCard.id)
            )
            card_id = (await session.execute(card_statement)).scalar_one()

            inserted = 0
            for record in operation_records:
                operation_statement = (
                    insert(FuelCardOperation)
                    .values(
                        card_id=card_id,
                        external_id=record.external_id,
                        occurred_at=record.occurred_at,
                        occurred_at_datetime=DatabaseService._operation_datetime(record.occurred_at),
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
                    .on_conflict_do_nothing(index_elements=[FuelCardOperation.external_id])
                    .returning(FuelCardOperation.id)
                )
                operation_id = (await session.execute(operation_statement)).scalar_one_or_none()
                if operation_id is not None:
                    if inserted_records is not None:
                        inserted_records.append(record)
                    inserted += 1
            await session.commit()
            return inserted

    @staticmethod
    async def get_fuel_cards() -> list[FuelCard]:
        async with async_session() as session:
            result = await session.execute(select(FuelCard).order_by(FuelCard.id))
            return list(result.scalars().all())

    @staticmethod
    async def get_fuel_cards_with_balances() -> list[tuple[FuelCard, str | None]]:
        async with async_session() as session:
            balance_subquery = (
                select(FuelCardOperation.fuel_balance)
                .where(
                    FuelCardOperation.card_id == FuelCard.id,
                    FuelCardOperation.fuel_balance.is_not(None),
                )
                .order_by(
                    FuelCardOperation.occurred_at_datetime.desc().nullslast(),
                    FuelCardOperation.created_at.desc().nullslast(),
                    FuelCardOperation.id.desc(),
                )
                .limit(1)
                .scalar_subquery()
            )
            result = await session.execute(
                select(FuelCard, balance_subquery.label("fuel_balance")).order_by(FuelCard.id)
            )
            return list(result.all())

    @staticmethod
    async def get_card_by_external_id(external_id: str) -> FuelCard | None:
        async with async_session() as session:
            result = await session.execute(select(FuelCard).where(FuelCard.external_id == external_id))
            return result.scalar_one_or_none()

    @staticmethod
    async def get_card_operations(card_id: int, limit: int = 10) -> list[FuelCardOperation]:
        async with async_session() as session:
            result = await session.execute(
                select(FuelCardOperation)
                .where(FuelCardOperation.card_id == card_id)
                .order_by(
                    FuelCardOperation.occurred_at_datetime.desc().nullslast(),
                    FuelCardOperation.created_at.desc().nullslast(),
                    FuelCardOperation.id.desc(),
                )
                .limit(limit)
            )
            return list(result.scalars().all())

    @staticmethod
    async def get_card_balance(card_id: int) -> str | None:
        async with async_session() as session:
            result = await session.execute(
                select(FuelCardOperation.fuel_balance)
                .where(
                    FuelCardOperation.card_id == card_id,
                    FuelCardOperation.fuel_balance.is_not(None),
                )
                .order_by(
                    FuelCardOperation.occurred_at_datetime.desc().nullslast(),
                    FuelCardOperation.created_at.desc().nullslast(),
                    FuelCardOperation.id.desc(),
                )
                .limit(1)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def set_card_balance(card_id: int, balance: str) -> bool:
        async with async_session() as session:
            result = await session.execute(
                select(FuelCardOperation)
                .where(FuelCardOperation.card_id == card_id)
                .order_by(
                    FuelCardOperation.occurred_at_datetime.desc().nullslast(),
                    FuelCardOperation.created_at.desc().nullslast(),
                    FuelCardOperation.id.desc(),
                )
                .limit(1)
            )
            operation = result.scalar_one_or_none()
            if operation is None:
                return False
            operation.fuel_balance = balance
            operation.fuel_balance_is_anchor = True
            operations_result = await session.execute(
                select(FuelCardOperation).where(FuelCardOperation.card_id == card_id)
            )
            operations = list(operations_result.scalars().all())
            DatabaseService._set_balance_anchor(operations, operation)
            DatabaseService._recalculate_operation_balances(operations)
            await session.commit()
            return True

    @staticmethod
    async def get_pending_notification_operations() -> list[FuelCardOperation]:
        async with async_session() as session:
            result = await session.execute(
                select(FuelCardOperation)
                .options(selectinload(FuelCardOperation.card))
                .where(FuelCardOperation.notification_sent_at.is_(None))
                .order_by(
                    FuelCardOperation.occurred_at_datetime.asc().nullslast(),
                    FuelCardOperation.created_at.asc().nullslast(),
                    FuelCardOperation.id.asc(),
                )
            )
            return list(result.scalars().all())

    @staticmethod
    async def get_sent_notification_operations() -> list[FuelCardOperation]:
        async with async_session() as session:
            result = await session.execute(
                select(FuelCardOperation)
                .options(selectinload(FuelCardOperation.card))
                .where(FuelCardOperation.notification_message_id.is_not(None))
                .order_by(FuelCardOperation.id)
            )
            return list(result.scalars().all())

    @staticmethod
    async def mark_notification_sent(operation_id: int, chat_id: int, message_id: int) -> None:
        async with async_session() as session:
            await session.execute(
                update(FuelCardOperation)
                .where(FuelCardOperation.id == operation_id)
                .values(
                    notification_sent_at=datetime.utcnow(),
                    notification_chat_id=str(chat_id),
                    notification_message_id=message_id,
                )
            )
            await session.commit()

    @staticmethod
    async def recalculate_fuel_balances(
        days: int = 60,
        operation_records: list | None = None,
    ) -> int:
        """Recalculate balances for the complete history; ``days`` is kept for compatibility."""
        async with async_session() as session:
            rows = (
                await session.execute(select(FuelCard.external_id, FuelCardOperation).join(FuelCardOperation.card))
            ).all()
            operations_by_card = {}
            for card_number, operation in rows:
                operations_by_card.setdefault(card_number, []).append(operation)

            updated = 0
            for operations in operations_by_card.values():
                updated += DatabaseService._recalculate_operation_balances(operations)

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
        value = operation.quantity or operation.amount
        try:
            normalized = str(value).replace("\u00a0", " ").replace(" ", "").replace(",", ".")
            movement = Decimal(normalized)
        except (InvalidOperation, AttributeError):
            movement = Decimal("0")
        return -movement if operation.operation_type == "0" else movement

    @staticmethod
    def _operation_sort_key(operation) -> tuple[datetime, datetime, int]:
        occurred_at = operation.occurred_at_datetime or DatabaseService._operation_datetime(operation.occurred_at)
        return (
            occurred_at or datetime.min,
            operation.created_at or datetime.min,
            operation.id,
        )

    @staticmethod
    def _recalculate_operation_balances(operations: list) -> int:
        operations.sort(key=DatabaseService._operation_sort_key)
        seeded_operations = [
            operation
            for operation in operations
            if operation.fuel_balance is not None and getattr(operation, "fuel_balance_is_anchor", False)
        ]
        if not seeded_operations:
            return 0

        seed = seeded_operations[-1]
        try:
            balance = Decimal(str(seed.fuel_balance).replace(",", "."))
        except InvalidOperation:
            return 0
        seed_index = operations.index(seed)
        updated = 0

        for operation in operations[seed_index + 1 :]:
            balance += DatabaseService._signed_movement(operation)
            operation.fuel_balance = DatabaseService._format_balance(balance)
            updated += 1

        balance = Decimal(str(seed.fuel_balance).replace(",", "."))
        for index in range(seed_index - 1, -1, -1):
            balance -= DatabaseService._signed_movement(operations[index + 1])
            operations[index].fuel_balance = DatabaseService._format_balance(balance)
            updated += 1

        return updated

    @staticmethod
    def _set_balance_anchor(operations: list, anchor) -> None:
        for operation in operations:
            operation.fuel_balance_is_anchor = operation is anchor

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
