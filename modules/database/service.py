from . import async_session
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
                    )
                )
                if inserted_records is not None:
                    inserted_records.append(record)
                inserted += 1
            await session.commit()
            return inserted
