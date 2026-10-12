"""
Telegram guruh a'zoligini tekshiruvchi kichik API.

GET /check?telegram_id=123  (header: X-API-Key)  ->  {"telegram_id": 123, "in_course": true}

Bot token va guruh ID'lari faqat serverda (muhit o'zgaruvchilarida) saqlanadi.
Ishga tushirish:  uvicorn app:create_app --factory --host 0.0.0.0 --port 8000
"""
import hmac
import logging
from contextlib import asynccontextmanager
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query

# httpx so'rov manzilini (ichida bot tokeni bor) log qilmasligi uchun
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

MEMBER_STATUSES = {"member", "administrator", "creator"}
UNKNOWN_USER_MARKERS = ("user not found", "PARTICIPANT_ID_INVALID", "USER_ID_INVALID")


@dataclass
class Settings:
    bot_token: str
    chat_ids: list
    api_keys: dict  # {nom: kalit}
    cache_ttl: int = 45
    rate_limit_per_min: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.environ.get("BOT_TOKEN", "").strip()
        chats = [c.strip() for c in os.environ.get("CHAT_IDS", "").split(",") if c.strip()]
        keys = {}
        for part in os.environ.get("API_KEYS", "").split(","):
            if ":" in part:
                name, key = part.split(":", 1)
                if name.strip() and key.strip():
                    keys[name.strip()] = key.strip()
        if not token or not chats or not keys:
            raise RuntimeError("BOT_TOKEN, CHAT_IDS va API_KEYS to'ldirilishi shart (.env.example'ga qarang)")
        return cls(token, chats, keys,
                   int(os.environ.get("CACHE_TTL", "45")),
                   int(os.environ.get("RATE_LIMIT_PER_MIN", "60")))


class TelegramError(Exception):
    pass


class MembershipChecker:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.s = settings
        self.client = client
        self._cache = {}  # user_id -> (expires_at, bool)

    async def _in_chat(self, chat_id: str, user_id: int) -> bool:
        url = f"https://api.telegram.org/bot{self.s.bot_token}/getChatMember"
        try:
            r = await self.client.get(url, params={"chat_id": chat_id, "user_id": user_id}, timeout=10)
            data = r.json()
        except (httpx.HTTPError, ValueError):
            raise TelegramError("Telegram bilan aloqa xatosi")
        if not data.get("ok"):
            desc = str(data.get("description", ""))
            if any(m.lower() in desc.lower() for m in UNKNOWN_USER_MARKERS):
                return False
            # bot guruhda emas, guruh ID noto'g'ri, token xato va h.k. -> "yo'q" demaymiz
            raise TelegramError("Telegram xatosi: " + desc[:120])
        res = data["result"]
        status = res.get("status")
        if status in MEMBER_STATUSES:
            return True
        if status == "restricted":
            return bool(res.get("is_member"))
        return False

    async def in_course(self, user_id: int) -> bool:
        now = time.monotonic()
        hit = self._cache.get(user_id)
        if hit and hit[0] > now:
            return hit[1]
        result = False
        for chat_id in self.s.chat_ids:
            if await self._in_chat(chat_id, user_id):
                result = True
                break
        # faqat muvaffaqiyatli natija keshlanadi (xato keshlanmaydi)
        self._cache[user_id] = (now + self.s.cache_ttl, result)
        if len(self._cache) > 50_000:
            self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
        return result


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits = defaultdict(deque)

    def allow(self, name: str) -> bool:
        now = time.monotonic()
        q = self.hits[name]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True


def create_app(settings: Optional[Settings] = None, client: Optional[httpx.AsyncClient] = None) -> FastAPI:
    settings = settings or Settings.from_env()
    client = client or httpx.AsyncClient()
    checker = MembershipChecker(settings, client)
    limiter = RateLimiter(settings.rate_limit_per_min)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        await client.aclose()

    app = FastAPI(title="Telegram guruh a'zoligi API", docs_url=None, redoc_url=None, lifespan=lifespan)

    def auth(x_api_key: Optional[str] = Header(default=None)) -> str:
        if x_api_key:
            for name, key in settings.api_keys.items():
                if hmac.compare_digest(x_api_key.encode(), key.encode()):
                    return name
        raise HTTPException(status_code=401, detail="API kalit noto'g'ri yoki yo'q")

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/check")
    async def check(telegram_id: int = Query(..., gt=0, lt=2**53), caller: str = Depends(auth)):
        if not limiter.allow(caller):
            raise HTTPException(status_code=429, detail="So'rovlar juda ko'p, keyinroq urinib ko'ring")
        try:
            member = await checker.in_course(telegram_id)
        except TelegramError:
            # Telegram ishlamasa "yo'q" deb javob bermaymiz, xato qaytaramiz
            raise HTTPException(status_code=502, detail="Tekshirib bo'lmadi, keyinroq urinib ko'ring")
        return {"telegram_id": telegram_id, "in_course": member}

    return app
