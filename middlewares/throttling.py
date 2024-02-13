from typing import Any, Awaitable, Callable, Dict
from aiogram.types import Message
from cachetools import TTLCache
from aiogram import BaseMiddleware
from datetime import timedelta


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, throttle_time: int, ignored_users: list[int] = None):
        self.throttle_time = timedelta(seconds=throttle_time)
        self.ignored_users = ignored_users or []
        self.caches = {
            "messages": TTLCache(maxsize=10_000, ttl=throttle_time)
        }

    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message,
            data: Dict[str, Any],
    ) -> Any:
        if event.chat.id in self.ignored_users:
            return await handler(event, data)

        key = f"message:{event.chat.id}:{event.text}"

        if key in self.caches['messages']:
            return await event.answer(
                f"Пожалуйста, подождите {self.throttle_time.seconds} секунд, прежде чем отправлять то же сообщение " +
                f"снова.")
        else:
            self.caches['messages'][key] = None

        return await handler(event, data)
