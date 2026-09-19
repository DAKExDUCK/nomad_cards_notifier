from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.database.models import Account, User


class UserDAL:
    """Data Access Layer for User"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_id(self, user_id: int) -> User | None:
        query = select(User).where(User.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, user_id: int, mail: str | None = None) -> User:
        user = User(user_id=user_id, mail=mail)
        self.session.add(user)
        await self.session.flush()
        return user

    async def update(self, user_id: int, **kwargs) -> User | None:
        user = await self.get_by_user_id(user_id)
        if not user:
            return None

        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        await self.session.flush()
        return user


class AccountDAL:
    """Data Access Layer for Account"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, account_id: int) -> Account | None:
        query = select(Account).where(Account.id == account_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int) -> Account | None:
        query = select(Account).where(Account.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, user_id: int, login: str, password_hash: str) -> Account:
        account = Account(user_id=user_id, login=login, password_hash=password_hash)
        self.session.add(account)
        await self.session.flush()
        return account

    async def update(self, account_id: int, **kwargs) -> Account | None:
        account = await self.get_by_id(account_id)
        if not account:
            return None

        for key, value in kwargs.items():
            if hasattr(account, key):
                setattr(account, key, value)

        await self.session.flush()
        return account
