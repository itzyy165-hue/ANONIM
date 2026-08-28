import asyncio
import logging
import os
import re
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import database

API_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Registration(StatesGroup):
    waiting_for_age = State()

def gender_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Парень", callback_data="gender_male")],
        [InlineKeyboardButton(text="👩 Девушка", callback_data="gender_female")]
    ])

def target_gender_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Парни", callback_data="target_male")],
        [InlineKeyboardButton(text="👩 Девушки", callback_data="target_female")],
        [InlineKeyboardButton(text="🏳️‍🌈 Все / Неважно", callback_data="target_any")]
    ])

def menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти собеседника", callback_data="search")]
    ])

def chat_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏹ Остановить диалог", callback_data="stop_chat")],
        [InlineKeyboardButton(text="🚨 Пожаловаться", callback_data="report_partner")]
    ])

def contains_link(text: str) -> bool:
    if not text:
        return False
    patterns = [
        r"https?://",
        r"t\.me/",
        r"www\.",
        r"\b[a-zA-Z0-9-]+\.(com|ru|org|net|me|io|info|xyz|cc|to)\b"
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    database.init_db()
    database.add_user(message.from_user.id, message.from_user.username)
    
    user = database.get_user(message.from_user.id)
    if user and user[6] == 1:
        await message.answer("❌ Ваш аккаунт заблокирован за нарушение правил.")
        return
        
    database.set_user_status(message.from_user.id, 'setup_gender')
    await state.clear()
    
    await message.answer(
        "👋 Привет! Добро пожаловать в анонимную чат-рулетку.\n\n"
        "Давай настроим твою анкету. Укажи свой пол:",
        reply_markup=gender_keyboard()
    )

@dp.message(Command("owner"))
async def cmd_owner(message: Message):
    await message.answer("👑 Создатель и владелец бота: <b>@GuddVes</b>", parse_mode="HTML")

@dp.callback_query(F.data.startswith("gender_"))
async def process_gender(callback: CallbackQuery):
    gender = "male" if callback.data == "gender_male" else "female"
    database.update_user_field(callback.from_user.id, "gender", gender)
    database.update_user_field(callback.from_user.id, "status", "setup_target")
    
    await callback.message.edit_text(
        "Отлично! Теперь выберите, чей пол вас интересует:",
        reply_markup=target_gender_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("target_"))
async def process_target(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split("_")[1]
    database.update_user_field(callback.from_user.id, "target_gender", target)
    
    database.update_user_field(callback.from_user.id, "status", "setup_age")
    await state.set_state(Registration.waiting_for_age)
    
    await callback.message.edit_text("Введите ваш возраст (цифрой):")
    await callback.answer()

@dp.message(Registration.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите возраст цифрами (например, 18):")
        return
        
    age = int(message.text)
    if age < 5 or age > 100:
        await message.answer("Пожалуйста, введите реальный возраст:")
        return
        
    database.update_user_field(message.from_user.id, "age", age)
    database.update_user_field(message.from_user.id, "status", "idle")
    await state.clear()
    
    await message.answer(
        "🎉 Регистрация успешно завершена!\n"
        "Теперь вы готовы к общению.",
        reply_markup=menu_keyboard()
    )

@dp.callback_query(F.data == "search")
async def start_search(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = database.get_user(user_id)
    
    if user and user[6] == 1:
        await callback.answer("Вы заблокированы.", show_alert=True)
        return
        
    partner_id = database.find_partner(user_id)
    
    if partner_id:
        database.set_user_status(user_id, 'chatting', partner_id)
        database.set_user_status(partner_id, 'chatting', user_id)
        
        await callback.message.edit_text("🎉 Собеседник найден! Можете общаться.", reply_markup=chat_keyboard())
        await bot.send_message(partner_id, "🎉 Собеседник найден! Можете общаться.", reply_markup=chat_keyboard())
    else:
        database.set_user_status(user_id, 'searching')
        await callback.message.edit_text(
            "🔍 Ищем подходящего собеседника...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить поиск", callback_data="stop_chat")]
            ])
        )
    await callback.answer()

@dp.callback_query(F.data == "stop_chat")
async def stop_chat(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = database.get_user(user_id)
    
    if user:
        partner_id = user[4]
        database.set_user_status(user_id, 'idle')
        await callback.message.edit_text("🛑 Диалог завершен.", reply_markup=menu_keyboard())
        
        if partner_id:
            database.set_user_status(partner_id, 'idle')
            await bot.send_message(partner_id, "🛑 Собеседник покинул чат.", reply_markup=menu_keyboard())
            
    await callback.answer()

@dp.callback_query(F.data == "report_partner")
async def report_partner(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = database.get_user(user_id)
    
    if user and user[4]:
        partner_id = user[4]
        database.increment_reports(partner_id)
        
        await callback.answer("🚨 Жалоба успешно отправлена администрации!", show_alert=True)
        
        database.set_user_status(user_id, 'idle')
        database.set_user_status(partner_id, 'idle')
        
        await callback.message.edit_text("🛑 Вы пожаловались на собеседника. Диалог завершен.", reply_markup=menu_keyboard())
        try:
            await bot.send_message(partner_id, "🛑 Собеседник завершил диалог.", reply_markup=menu_keyboard())
        except Exception:
            pass
    else:
        await callback.answer("Вы сейчас не в диалоге.", show_alert=True)

@dp.message()
async def handle_chat_messages(message: Message):
    if message.from_user.bot:
        return
        
    user_id = message.from_user.id
    user = database.get_user(user_id)
    
    if not user:
        return
        
    if user[6] == 1:
        return
        
    status, partner_id = user[3], user[4]
    
    if status != 'chatting' or not partner_id:
        await message.answer("Вы не в чате! Нажми «🔍 Найти собеседника».", reply_markup=menu_keyboard())
        return

    text_to_check = message.text or message.caption or ""
    if contains_link(text_to_check):
        database.increment_reports(user_id)
        await message.answer("❌ Ссылки запрещены! За отправку ссылок доступ к общению может быть ограничен.")
        return

    try:
        await message.copy_to(partner_id)
    except Exception:
        await message.answer("Не удалось доставить сообщение собеседнику.")

async def handle_ping(request):
    return web.Response(text="OK", status=200)

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    database.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    
    await web_server()
    print("ЛГБТ Чат-рулетка успешно запущена!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
