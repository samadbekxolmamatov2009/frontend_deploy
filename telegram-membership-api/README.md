# Telegram guruh a'zoligi API

Foydalanuvchi (`telegram_id`) belgilangan Telegram guruh(lar)da borligini tekshiradi.
Baza kerak emas: javobni Telegram o'zi beradi (`getChatMember`).

    GET /check?telegram_id=123456789
    Header: X-API-Key: <dasturchiga berilgan kalit>

    200 {"telegram_id": 123456789, "in_course": true}
    401 kalit noto'g'ri | 422 telegram_id noto'g'ri | 429 limit oshdi
    502 Telegram'dan javob olinmadi (bu holda "false" QAYTARILMAYDI)

## Sozlash

1. @BotFather'da bot yarating (yoki mavjudidan foydalaning), tokenni oling.
2. Botni guruhga qo'shing va **admin** qiling (ishonchli ishlashi uchun).
3. Guruh ID'sini toping (odatda `-100...` bilan boshlanadi): guruhga botni qo'shgach
   `https://api.telegram.org/bot<TOKEN>/getUpdates` ni oching yoki @RawDataBot'dan foydalaning.
4. `.env.example` ni `.env` ga nusxalab to'ldiring. Har bir dasturchiga **alohida** API kalit
   yarating: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Ishga tushirish

    pip install -r requirements.txt
    python3 -m pytest -q                      # testlar
    set -a; source .env; set +a
    uvicorn app:create_app --factory --host 0.0.0.0 --port 8000

Ishga tushirgach: `curl -H "X-API-Key: <kalit>" "http://localhost:8000/check?telegram_id=123"`

## Xavfsizlik

- Bot tokenini hech kimga bermang; faqat serverdagi `.env`da tursin.
- Dasturchiga faqat API kalit va manzilni bering. Kalitni o'chirib qo'yish uchun `API_KEYS`dan olib tashlang.
- Internetga HTTPS orqali chiqaring (Nginx/Caddy yoki Render/Railway/Fly kabi xizmat).
- To'lovi tugagan odamni guruhdan chiqarib turing, aks holda u "kursda bor" deb ko'rinadi.
- Guruh havolasi ochiq tarqalmasin.
