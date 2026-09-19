from . import async_session
from .dal import AccountDAL, UserDAL
from .models import Account, User


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
