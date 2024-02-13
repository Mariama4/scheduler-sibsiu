import config
from database import MongoDB
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

configuration = config.get_environment()

mongodb = MongoDB(
    username=configuration['MONGODB_USERNAME'],
    password=configuration['MONGODB_PASSWORD'],
    host=configuration['MONGODB_HOST'],
    port=configuration['MONGODB_PORT'],
    database=configuration['MONGODB_DATABASE']
)

dp = Dispatcher(storage=MemoryStorage())
