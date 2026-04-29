from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

class Database:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users = self.db.users

    async def add_user(self, user_id):
        if not await self.is_user_exist(user_id):
            await self.users.insert_one({'user_id': user_id, 'banned': False})

    async def is_user_exist(self, user_id):
        user = await self.users.find_one({'user_id': user_id})
        return bool(user)

    async def get_all_users(self):
        return await self.users.find().to_list(length=None)

    async def ban_user(self, user_id):
        await self.users.update_one({'user_id': user_id}, {'$set': {'banned': True}})

    async def unban_user(self, user_id):
        await self.users.update_one({'user_id': user_id}, {'$set': {'banned': False}})

    async def is_banned(self, user_id):
        user = await self.users.find_one({'user_id': user_id})
        return user.get('banned', False) if user else False

db = Database(Config.MONGO_URI, "ConverterBot")
