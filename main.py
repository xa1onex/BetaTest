import asyncio
import random
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.client.default import DefaultBotProperties

API_TOKEN = "7392209320:AAET1DAtfR64VmeYe186oWR_DsUwhAEWtms"

# База
conn = sqlite3.connect("game_bot.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 100
)
""")
conn.commit()

# Очереди ожидания по типу игры
waiting_players = {
    "dice": [],
    "slots": [],
    "basket": [],
    "football": [],
    "dart": []
}
# Активные игры
active_games = {}

bot = Bot(
    API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, 100)", (user_id,))
    conn.commit()
    return 100


def update_balance(user_id, amount):
    bal = get_balance(user_id)
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (bal + amount, user_id))
    conn.commit()


class GameStates(StatesGroup):
    waiting = State()
    playing = State()


@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    balance = get_balance(message.from_user.id)
    text = (
        "🎮 <b>Игры на звёзды</b>\n"
        "Выбирай игру, ставь звёзды и сражайся 1 на 1!\n\n"
        "🎲 Кубик — от 1 до 6 (больше число побеждает)\n"
        "🎰 Слоты — 1-64 (64 = 777)\n"
        "🏀 Баскетбол — 1-3 (3 = попадание)\n"
        "⚽ Футбол — 1-5 (3 = гол)\n"
        "🎯 Дротик — 1-6 (6 = bullseye)\n\n"
        f"💰 Твой баланс: <b>{balance}⭐</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲", callback_data="game:dice"),
        InlineKeyboardButton(text="🎰", callback_data="game:slots"),
        InlineKeyboardButton(text="🏀", callback_data="game:basket"),
        InlineKeyboardButton(text="⚽", callback_data="game:football"),
        InlineKeyboardButton(text="🎯", callback_data="game:dart")],
        [InlineKeyboardButton(text="🆘 Помощь", callback_data=""),
         InlineKeyboardButton(text="💵 Вывод средств", callback_data="")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="")]
    ])
    await message.answer(text, reply_markup=kb)


@dp.callback_query(F.data.startswith("game:"))
async def choose_game(callback: CallbackQuery, state: FSMContext):
    game_type = callback.data.split(":")[1]
    user_id = callback.from_user.id
    balance = get_balance(user_id)

    if balance < 10:
        await callback.answer("Недостаточно звёзд для ставки!", show_alert=True)
        return

    if waiting_players[game_type]:
        opponent_id = waiting_players[game_type].pop(0)
        game_id = f"{user_id}_{opponent_id}"
        active_games[game_id] = {
            "type": game_type,
            "players": [opponent_id, user_id],
            "results": {}
        }
        await bot.send_message(opponent_id, "🎮 Противник найден! Ты ходишь первым, кидай стикер!")
        await bot.send_message(user_id, "🎮 Противник найден! Жди свой ход.")
    else:
        waiting_players[game_type].append(user_id)
        await callback.message.answer("⏳ Ожидаем противника...")


@dp.message(F.dice)
async def handle_dice(message: Message):
    user_id = message.from_user.id
    for game_id, game in list(active_games.items()):
        if user_id in game["players"]:
            game["results"][user_id] = message.dice.value
            players = game["players"]
            if len(game["results"]) == 2:
                p1, p2 = players
                res1, res2 = game["results"][p1], game["results"][p2]
                if res1 > res2:
                    winner, loser = p1, p2
                elif res2 > res1:
                    winner, loser = p2, p1
                else:
                    winner = loser = None

                if winner:
                    update_balance(winner, 10)
                    update_balance(loser, -10)
                    await bot.send_message(winner, f"🏆 Ты выиграл! +10⭐\n💰 Баланс: {get_balance(winner)}⭐")
                    await bot.send_message(loser, f"💀 Ты проиграл! -10⭐\n💰 Баланс: {get_balance(loser)}⭐")
                else:
                    await bot.send_message(p1, "🤝 Ничья! Баланс без изменений.")
                    await bot.send_message(p2, "🤝 Ничья! Баланс без изменений.")

                del active_games[game_id]
            else:
                # Передаём ход
                opponent = [p for p in game["players"] if p != user_id][0]
                await bot.send_message(opponent, "Твой ход! Кидай стикер.")
            break


if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))