import json
import random
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.enums import ParseMode
import asyncio

# ======== НАСТРОЙКИ ========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GIFTS_FILE = "gifts.json"
DB_FILE = "users.db"
SPIN_PRICE_STARS = 100
ADMIN_ID = 334485676
# ============================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ---------- База данных ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS spins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            stars_paid INTEGER,
            gift_name TEXT,
            gift_market_price INTEGER,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def record_spin(user_id, username, first_name, stars, gift_name, gift_price):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO spins (user_id, username, first_name, stars_paid, gift_name, gift_market_price, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, first_name, stars, gift_name, gift_price, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

# ---------- Подарки ----------
def load_gifts():
    with open(GIFTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_gifts(gifts):
    with open(GIFTS_FILE, "w", encoding="utf-8") as f:
        json.dump(gifts, f, ensure_ascii=False, indent=2)

def pick_gift():
    gifts = load_gifts()
    available = [g for g in gifts if g.get("stock", 0) > 0]
    if not available:
        return None
    weights = [g["weight"] for g in available]
    chosen = random.choices(available, weights=weights, k=1)[0]
    idx = next(i for i, g in enumerate(gifts) if g["id"] == chosen["id"])
    gifts[idx]["stock"] -= 1
    save_gifts(gifts)
    return chosen

# ---------- АВТОВЫДАЧА ПРИЗОВ ----------
async def deliver_prize(message: Message, gift):
    """Автоматически отправляет приз пользователю"""
    prize_type = gift.get("type", "text")
    content = gift.get("content", "")
    prize_name = gift["name"]
    
    try:
        if prize_type == "text":
            # Отправляем текстовый приз (промокод, инструкцию)
            await message.answer(
                f"🎁 <b>Ваш приз: {prize_name}</b>\n\n"
                f"{content}\n\n"
                f"Сохраните это сообщение!",
                parse_mode=ParseMode.HTML
            )
        
        elif prize_type == "invite_link":
            # Отправляем ссылку на канал
            await message.answer(
                f"🎁 <b>Ваш приз: {prize_name}</b>\n\n"
                f"Переходите по ссылке:\n"
                f"{content}\n\n"
                f"Добро пожаловать! 🎉",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        
        elif prize_type == "file":
            # Отправляем файл (по file_id)
            await message.answer_document(
                document=content,
                caption=f"🎁 <b>Ваш приз: {prize_name}</b>\n\nСохраните файл!",
                parse_mode=ParseMode.HTML
            )
        
        elif prize_type == "photo":
            # Отправляем фото
            await message.answer_photo(
                photo=content,
                caption=f"🎁 <b>Ваш приз: {prize_name}</b>",
                parse_mode=ParseMode.HTML
            )
        
        elif prize_type == "contact_manager":
            # Сообщаем, что менеджер свяжется
            await message.answer(
                f"🎉 <b>Поздравляем! Вы выиграли: {prize_name}</b>\n\n"
                f"{content}\n\n"
                f"Ожидайте сообщения от нас!",
                parse_mode=ParseMode.HTML
            )
        
        else:
            #Fallback для неизвестного типа
            await message.answer(
                f"🎉 <b>Поздравляем! Вам выпал: {prize_name}</b>\n\n"
                f"Мы свяжемся с вами для вручения приза!",
                parse_mode=ParseMode.HTML
            )
    
    except Exception as e:
        # Если не получилось отправить автоматически
        await message.answer(
            f"🎉 <b>Поздравляем! Вы выиграли: {prize_name}</b>\n\n"
            f"Напишите в поддержку для получения приза: @your_support_username",
            parse_mode=ParseMode.HTML
        )

# ---------- Команда /spin (ВЫСТАВЛЯЕТ СЧЁТ) ----------
async def process_spin(message: Message):
    gift = pick_gift()
    if gift is None:
        await message.answer("️ Сервис временно не работает — ведутся технические работы.")
        return

    prices = [LabeledPrice(label="Вращение барабана", amount=SPIN_PRICE_STARS)]
    
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="🎰 Вращение барабана",
        description=f"Вы можете выиграть: {gift['name']}",
        currency="XTR",
        prices=prices,
        provider_token="",
        payload=f"spin_{message.from_user.id}_{gift['id']}",
    )

# ---------- Команда /start ----------
@dp.message(CommandStart())
async def start(message: Message):
    if message.text and "spin" in message.text.lower():
        await process_spin(message)
        return
    
    webapp_url = "https://maksinianosamsonov-art.github.io/wheel-app/"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Открыть барабан", web_app=WebAppInfo(url=webapp_url))]
    ])
    
    await message.answer(
        f" <b>Привет!</b>\n\n"
        f"Крути барабан и выигрывай реальные подарки 🎁\n"
        f"Одно вращение — <b>{SPIN_PRICE_STARS} ★</b>\n\n"
        f"Нажми кнопку ниже, чтобы открыть 👇",
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )

# ---------- Обработка оплаты ----------
@dp.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)

@dp.message(F.successful_payment)
async def on_success(message: Message):
    user = message.from_user
    payment = message.successful_payment
    
    try:
        _, uid, gift_id = payment.invoice_payload.split("_")
        gift_id = int(gift_id)
    except Exception:
        await message.answer("Ошибка обработки платежа.")
        return

    gifts = load_gifts()
    gift = next((g for g in gifts if g["id"] == gift_id), None)
    if gift is None:
        await message.answer("️ Сервис временно не работает.")
        return

    record_spin(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        stars=payment.total_amount,
        gift_name=gift["name"],
        gift_price=gift["market_price"],
    )

    # 🚀 АВТОМАТИЧЕСКИ ВЫДАЁМ ПРИЗ!
    await deliver_prize(message, gift)

# ---------- Команда /stats ----------
@dp.message(Command("stats"))
async def stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Эта команда только для админа.")
        return
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*), COALESCE(SUM(stars_paid),0), COALESCE(SUM(gift_market_price),0) FROM spins")
    total_spins, total_stars, total_market = c.fetchone()
    
    c.execute("SELECT username, first_name, stars_paid, gift_name, timestamp FROM spins ORDER BY id DESC LIMIT 10")
    last = c.fetchall()
    conn.close()
    
    text = f"📊 <b>Статистика</b>\n\n"
    text += f"Всего вращений: <b>{total_spins}</b>\n"
    text += f"Получено звёзд: <b>{total_stars} ★</b>\n"
    text += f"Рыночная стоимость призов: <b>{total_market} ₽</b>\n"
    
    await message.answer(text, parse_mode=ParseMode.HTML)

# ---------- Запуск бота ----------
async def main():
    init_db()
    print("✅ БОТ ЗАПУЩЕН! Автоматическая выдача призов активна.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
