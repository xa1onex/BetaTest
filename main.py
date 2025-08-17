import asyncio
import random
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

API_TOKEN = "7392209320:AAET1DAtfR64VmeYe186oWR_DsUwhAEWtms"
PROVIDER_TOKEN = ""  # Telegram Stars

# ==================== Инициализация бота ====================
bot = Bot(API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ==================== База данных ====================
conn = sqlite3.connect("casino.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 100
)
""")
conn.commit()

def add_user(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
    conn.commit()

def get_balance(user_id: int) -> int:
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    add_user(user_id)
    return 100

def update_balance(user_id: int, diff: int):
    bal = get_balance(user_id)
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (bal + diff, user_id))
    conn.commit()

# ==================== Активные игры ====================
active_games = {}  # user_id -> {type, bet, turn, results}

# ==================== Меню ====================
def main_menu(user_id: int):
    bal = get_balance(user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲", callback_data="game:dice"),
         InlineKeyboardButton(text="🎰", callback_data="game:slots"),
         InlineKeyboardButton(text="🏀", callback_data="game:basket"),
         InlineKeyboardButton(text="⚽", callback_data="game:football"),
         InlineKeyboardButton(text="🎯", callback_data="game:dart")],
        [InlineKeyboardButton(text="🆘 Помощь", callback_data="help"),
         InlineKeyboardButton(text="💵 Вывод средств", url="https://t.me/cloud_nnine")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit")]
    ])
    text = (
        f"🎮 Игры на звёзды\n"
        f"Сражайся с соперником 1 на 1!\n\n"
        f"🎲 Кубик — от 1 до 6 (больше число побеждает)\n"
        f"🎰 Слоты — 1-64 (64 = 777)\n"
        f"🏀 Баскетбол — 1-3 (3 = попадание)\n"
        f"⚽ Футбол — 1-5 (3 = гол)\n"
        f"🎯 Дротик — 1-6 (6 = bullseye)\n\n"
        f"💰 Баланс: <b>{bal}⭐</b>\n"
    )
    return text, kb

back_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])

deposit_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="50 ⭐", callback_data="pay:50"),
     InlineKeyboardButton(text="100 ⭐", callback_data="pay:100")],
    [InlineKeyboardButton(text="300 ⭐", callback_data="pay:300"),
     InlineKeyboardButton(text="500 ⭐", callback_data="pay:500")],
    [InlineKeyboardButton(text="1000 ⭐", callback_data="pay:1000")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])

# ==================== Состояния ====================
class PaymentStates(StatesGroup):
    choosing_amount = State()

# ==================== /start ====================
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    add_user(message.from_user.id)
    text, kb = main_menu(message.from_user.id)
    await message.answer(text, reply_markup=kb)

# ==================== Помощь ====================
@dp.callback_query(F.data == "help")
async def process_help(callback: CallbackQuery):
    await callback.message.edit_text(
        "📖 Здесь будет описание бота...\n\nНапиши сюда что хочешь.",
        reply_markup=back_kb
    )

# ==================== Назад ====================
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    text, kb = main_menu(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=kb)

# ==================== Пополнение ====================
@dp.callback_query(F.data == "deposit")
async def process_deposit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PaymentStates.choosing_amount)
    await callback.message.edit_text("💰 Выберите сумму пополнения:", reply_markup=deposit_kb)

@dp.callback_query(PaymentStates.choosing_amount, F.data.startswith("pay:"))
async def process_payment(callback: CallbackQuery, state: FSMContext):
    amount_stars = int(callback.data.split(":")[1])
    payload = f"deposit:{callback.from_user.id}:{amount_stars}"

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"Пополнение баланса",
        description=f"Пополнение баланса на {amount_stars}⭐",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Пополнение {amount_stars}⭐", amount=amount_stars * 1000)],  # *1000 для Stars
        payload=payload,
        start_parameter=f'deposit_{callback.from_user.id}_{amount_stars}',
        need_name=False,
        need_phone_number=False
    )
    await state.clear()

# ==================== Успешная оплата ====================
@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    if payload.startswith("deposit:"):
        _, user_id, amount_str = payload.split(":")
        user_id = int(user_id)
        amount = int(amount_str)
        update_balance(user_id, amount)
        await message.answer(
            f"✅ Платёж на {amount}⭐ успешно получен!\n"
            f"💰 Ваш новый баланс: {get_balance(user_id)}⭐"
        )

# ==================== Запуск игры ====================
@dp.callback_query(F.data.startswith("game:"))
async def choose_game(callback: CallbackQuery, from_retry: bool = False):
    user_id = callback.from_user.id
    game_type = callback.data.split(":")[1]
    bet = 10
    balance = get_balance(user_id)

    if balance < bet:
        await callback.answer("❌ Недостаточно звёзд для ставки!", show_alert=True)
        return

    update_balance(user_id, -bet)

    # сохраняем игру
    turn = random.choice(["user", "bot"])
    active_games[user_id] = {"type": game_type, "bet": bet, "turn": turn, "results": {}}

    # имитация поиска соперника
    if not from_retry:
        await callback.message.answer("⏳ Ищем противника...")
        await asyncio.sleep(2)
        await callback.message.answer("🎮 Противник найден!")
    else:
        await bot.send_message(user_id, "🔁 Новая игра началась!")

    if turn == "user":
        await bot.send_message(user_id, f"👉 Твой ход! Кидай {game_type} ({emoji_for(game_type)})")
    else:
        await bot.send_message(user_id, "🤖 Противник ходит первым...")
        await asyncio.sleep(2)
        opp_msg = await bot.send_dice(user_id, emoji=emoji_for(game_type))
        active_games[user_id]["results"]["bot"] = opp_msg.dice.value
        active_games[user_id]["turn"] = "user"
        await bot.send_message(user_id, f"👉 Твой ход! Кидай {game_type} ({emoji_for(game_type)})")



# ==================== Ходы ====================
@dp.message(F.dice)
async def handle_dice(message: Message):
    user_id = message.from_user.id
    if user_id not in active_games:
        return

    game = active_games[user_id]
    if game["turn"] != "user":
        return

    # сохраняем результат игрока
    game["results"]["user"] = message.dice.value

    # если бот ещё не ходил → ходит
    if "bot" not in game["results"]:
        await asyncio.sleep(2)
        bot_msg = await bot.send_dice(user_id, emoji=emoji_for(game["type"]))
        game["results"]["bot"] = bot_msg.dice.value

    # подводим итоги
    await asyncio.sleep(1)
    await finish_game(user_id)

async def finish_game(user_id: int):
    game = active_games[user_id]
    bet = game["bet"]
    res = game["results"]
    bank = bet * 2

    if res["user"] > res["bot"]:
        update_balance(user_id, bank)
        text = f"🏆 Ты выиграл! +{bet}⭐\n💰 Баланс: {get_balance(user_id)}⭐"
    elif res["user"] < res["bot"]:
        text = f"💀 Ты проиграл! -{bet}⭐\n💰 Баланс: {get_balance(user_id)}⭐"
    else:
        update_balance(user_id, bet)
        text = "🤝 Ничья! Баланс без изменений."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"retry:{game['type']}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

    await bot.send_message(user_id, text, reply_markup=kb)
    del active_games[user_id]

# ==================== Повтор игры ====================
@dp.callback_query(F.data.startswith("retry:"))
async def retry_game(callback: CallbackQuery):
    game_type = callback.data.split(":")[1]
    # вызываем choose_game, но помечаем, что это повтор
    fake_callback = CallbackQuery(
        id=callback.id,
        from_user=callback.from_user,
        chat_instance=callback.chat_instance,
        data=f"game:{game_type}",
        message=None  # теперь можно без message
    )
    await choose_game(fake_callback, from_retry=True)

# ==================== Утилиты ====================
def emoji_for(game_type: str) -> str:
    return {
        "dice": "🎲",
        "slots": "🎰",
        "basket": "🏀",
        "football": "⚽",
        "dart": "🎯"
    }[game_type]

# ==================== Запуск ====================
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))