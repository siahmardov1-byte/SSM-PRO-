import asyncio
import os
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup as Kb
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
CHANNEL = os.environ["CHANNEL"]
GROUP = os.environ["GROUP"]
YOUTUBE = os.getenv("YOUTUBE", "https://youtube.com")
DB_PATH = os.getenv("DB_PATH", "bot.db")

db = sqlite3.connect(DB_PATH)
db.executescript("""
CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, taken_by INTEGER);
""")
db.execute("INSERT OR IGNORE INTO settings VALUES ('open', '0')")
db.commit()

dp = Dispatcher()
link = lambda u: f"https://t.me/{u.lstrip('@')}"


def join_kb():
    return Kb(inline_keyboard=[
        [Btn(text="📢 КАНАЛ", url=link(CHANNEL))],
        [Btn(text="👥 ГРУППА", url=link(GROUP))],
        [Btn(text="✅ ПРОВЕРИТЬ ПОДПИСКУ", callback_data="verify")],
    ])


def menu_kb():
    return Kb(inline_keyboard=[
        [Btn(text="🎁 УЧАСТВОВАТЬ В РОЗЫГРЫШЕ", callback_data="join")],
        [Btn(text="▶️ YOUTUBE", url=YOUTUBE),
         Btn(text="👥 ГРУППА", url=link(GROUP)),
         Btn(text="📢 КАНАЛ", url=link(CHANNEL))],
    ])


async def is_member(bot: Bot, chat: str, uid: int) -> bool:
    try:
        m = await bot.get_chat_member(chat, uid)
    except Exception:
        return False
    return m.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)


async def verified(bot: Bot, uid: int) -> bool:
    return await is_member(bot, CHANNEL, uid) and await is_member(bot, GROUP, uid)


@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "⚡ <b>ПРОВЕРКА ДОСТУПА</b>\n\n"
        "Добро пожаловать! Чтобы продолжить, подпишитесь на канал и "
        "вступите в группу, затем нажмите <b>ПРОВЕРИТЬ ПОДПИСКУ</b>.",
        reply_markup=join_kb(), parse_mode="HTML")


@dp.callback_query(F.data == "verify")
async def verify(cb: CallbackQuery, bot: Bot):
    if await verified(bot, cb.from_user.id):
        await cb.answer("Проверка пройдена!", show_alert=True)
        await cb.message.answer(
            "✅ <b>ПРОВЕРКА ПРОЙДЕНА</b>\nМеню открыто.",
            reply_markup=menu_kb(), parse_mode="HTML")
    else:
        await cb.answer("Сначала подпишитесь на канал и группу!", show_alert=True)


@dp.callback_query(F.data == "join")
async def join(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    if not await verified(bot, uid):
        return await cb.answer("Сначала пройдите проверку через /start.", show_alert=True)

    is_open = db.execute("SELECT v FROM settings WHERE k='open'").fetchone()[0] == "1"
    if not is_open:
        return await cb.message.answer(
            "⏳ <b>РОЗЫГРЫШ ЕЩЁ НЕ НАЧАЛСЯ</b>\n"
            "Дождитесь официального анонса в канале.", parse_mode="HTML")

    if db.execute("SELECT 1 FROM accounts WHERE taken_by=?", (uid,)).fetchone():
        return await cb.answer("Вы уже получили свой приз (1/1).", show_alert=True)

    row = db.execute("SELECT id, data FROM accounts WHERE taken_by IS NULL LIMIT 1").fetchone()
    if not row:
        return await cb.message.answer("😔 Призы закончились.")

    db.execute("UPDATE accounts SET taken_by=? WHERE id=?", (uid, row[0]))
    db.commit()
    left = db.execute("SELECT COUNT(*) FROM accounts WHERE taken_by IS NULL").fetchone()[0]
    await cb.message.answer(
        f"🎉 <b>ПРИЗ ПОЛУЧЕН</b>\n\n🔐 <code>{row[1]}</code>\n"
        f"📦 Ваши получения: 1/1\n🎁 Осталось: {left}\n\n"
        "Не передавайте эти данные другим.", parse_mode="HTML")
    await cb.answer()


@dp.message(Command("open"), F.from_user.id == ADMIN_ID)
async def open_giveaway(msg: Message):
    db.execute("UPDATE settings SET v='1' WHERE k='open'"); db.commit()
    await msg.answer("Розыгрыш открыт ✅")


@dp.message(Command("close"), F.from_user.id == ADMIN_ID)
async def close_giveaway(msg: Message):
    db.execute("UPDATE settings SET v='0' WHERE k='open'"); db.commit()
    await msg.answer("Розыгрыш закрыт ⏸")


@dp.message(Command("add"), F.from_user.id == ADMIN_ID)
async def add_accounts(msg: Message, command: CommandObject):
    lines = [l.strip() for l in (command.args or "").splitlines() if l.strip()]
    db.executemany("INSERT INTO accounts (data) VALUES (?)", [(l,) for l in lines])
    db.commit()
    await msg.answer(f"Добавлено: {len(lines)}")


async def main():
    await dp.start_polling(Bot(TOKEN))


if __name__ == "__main__":
    asyncio.run(main())
