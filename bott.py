import os
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from aiohttp import web

# ======================
# TOKEN ИЗ ENV
# ======================

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

bathroom_status = {
    "occupied": False,
    "until": None,
    "user": None,
    "chat_id": None,
    "reserved": False
}


# ======================
# КНОПКИ
# ======================

def main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.add(
        InlineKeyboardButton(text="🛁 Занять ванну", callback_data="occupy"),
        InlineKeyboardButton(text="📊 Статус", callback_data="status"),
        InlineKeyboardButton(text="✅ Освободить", callback_data="free"),
    )
    kb.adjust(1)
    return kb.as_markup()


def time_keyboard():
    kb = InlineKeyboardBuilder()
    for t in [15, 30, 45, 60]:
        kb.add(InlineKeyboardButton(text=f"{t} минут", callback_data=f"time_{t}"))
    kb.adjust(2)
    return kb.as_markup()


# ======================
# ХЕНДЛЕРЫ
# ======================

@dp.message()
async def start(message: Message):
    await message.answer("🚿 Управление ванной комнатой", reply_markup=main_keyboard())


@dp.callback_query(F.data == "status")
async def status_handler(callback: CallbackQuery):
    if bathroom_status["occupied"]:
        remaining = bathroom_status["until"] - datetime.now()
        minutes = int(remaining.total_seconds() // 60)
        await callback.message.answer(
            f"🛁 Ванная занята пользователем {bathroom_status['user']}\n"
            f"⏳ Осталось примерно {minutes} минут"
        )
    elif bathroom_status["reserved"]:
        await callback.message.answer("⏳ Ванная скоро будет занята (через 10 минут)")
    else:
        await callback.message.answer("✅ Ванная свободна")
    await callback.answer()


@dp.callback_query(F.data == "occupy")
async def occupy_handler(callback: CallbackQuery):
    if bathroom_status["occupied"] or bathroom_status["reserved"]:
        await callback.message.answer("❌ Ванная уже занята или запланирована!")
    else:
        await callback.message.answer("⏰ Выберите время:", reply_markup=time_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("time_"))
async def time_selected(callback: CallbackQuery):
    if bathroom_status["occupied"] or bathroom_status["reserved"]:
        await callback.message.answer("❌ Ванная уже занята или запланирована!")
        await callback.answer()
        return

    minutes = int(callback.data.split("_")[1])

    bathroom_status["reserved"] = True
    bathroom_status["user"] = callback.from_user.full_name
    bathroom_status["chat_id"] = callback.message.chat.id

    await callback.message.answer(
        f"⏳ Ванная будет занята через 10 минут\n"
        f"⏱ Продолжительность: {minutes} минут"
    )

    asyncio.create_task(schedule_occupy(minutes))
    await callback.answer()


async def schedule_occupy(minutes: int):
    await asyncio.sleep(10 * 60)

    if not bathroom_status["reserved"]:
        return

    bathroom_status["reserved"] = False
    bathroom_status["occupied"] = True
    bathroom_status["until"] = datetime.now() + timedelta(minutes=minutes)

    await bot.send_message(
        bathroom_status["chat_id"],
        f"🛁 Ванная теперь занята пользователем {bathroom_status['user']}"
    )

    await asyncio.sleep(minutes * 60)

    if bathroom_status["occupied"]:
        await bot.send_message(
            bathroom_status["chat_id"],
            "✅ Время вышло! Ванная теперь свободна."
        )
        bathroom_status.update({
            "occupied": False,
            "until": None,
            "user": None,
            "chat_id": None
        })


@dp.callback_query(F.data == "free")
async def free_handler(callback: CallbackQuery):
    if bathroom_status["occupied"] or bathroom_status["reserved"]:
        bathroom_status.update({
            "occupied": False,
            "reserved": False,
            "until": None,
            "user": None,
            "chat_id": None
        })
        await callback.message.answer("✅ Ванная освобождена вручную")
    else:
        await callback.message.answer("ℹ️ Ванная уже свободна")
    await callback.answer()


# ======================
# HTTP СЕРВЕР ДЛЯ RENDER
# ======================

async def health(request):
    return web.Response(text="Bot is running")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)

    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# ======================
# MAIN
# ======================

async def main():
    await start_web_server()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
