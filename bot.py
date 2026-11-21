import os, time, sqlite3, threading
import telebot
from telebot import types

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0") or 0)
CARD = os.environ.get("CARD_NUMBER", "0000 0000 0000 0000")
TRIAL_DAYS = 7
PLANS = {30: 29000, 90: 74000}

bot = telebot.TeleBot(TOKEN, parse_mode="HTML") if TOKEN else None
_lock = threading.Lock()
pending = {}  # user_id -> days


def db():
    c = sqlite3.connect("data.db", check_same_thread=False)
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, expires INTEGER)")
    return c


def get_expires(uid):
    with _lock, db() as c:
        r = c.execute("SELECT expires FROM users WHERE id=?", (uid,)).fetchone()
    return r[0] if r else None


def grant(uid, days, name=""):
    with _lock, db() as c:
        r = c.execute("SELECT expires FROM users WHERE id=?", (uid,)).fetchone()
        base = max(r[0], int(time.time())) if r else int(time.time())
        new = base + days * 86400
        c.execute("INSERT INTO users(id,name,expires) VALUES(?,?,?) "
                  "ON CONFLICT(id) DO UPDATE SET expires=?", (uid, name, new, new))
    return new


def has_access(uid):
    e = get_expires(uid)
    return bool(e and e > time.time())


def days_left(uid):
    e = get_expires(uid) or 0
    return max(0, int((e - time.time()) // 86400) + (1 if e > time.time() else 0))


def money(n):
    return f"{n:,}".replace(",", " ") + " so'm"


if bot:
    @bot.message_handler(commands=["start"])
    def start(m):
        uid = m.from_user.id
        if get_expires(uid) is None:
            grant(uid, TRIAL_DAYS, m.from_user.first_name or "")
            bot.send_message(m.chat.id, f"Salom, {m.from_user.first_name}! 🎉\n"
                             f"Sizga <b>{TRIAL_DAYS} kun bepul</b> berildi.\n\n"
                             "/status — obuna holati\n/buy — obuna sotib olish")
        else:
            bot.send_message(m.chat.id, "Xush kelibsiz! /status yoki /buy")

    @bot.message_handler(commands=["status"])
    def status(m):
        if has_access(m.from_user.id):
            bot.send_message(m.chat.id, f"✅ Obuna faol. Qolgan: <b>{days_left(m.from_user.id)} kun</b>")
        else:
            bot.send_message(m.chat.id, "❌ Obuna tugagan. /buy orqali yangilang.")

    @bot.message_handler(commands=["buy"])
    def buy(m):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(f"1 oy — {money(PLANS[30])}", callback_data="plan:30"))
        kb.add(types.InlineKeyboardButton(f"3 oy — {money(PLANS[90])}", callback_data="plan:90"))
        bot.send_message(m.chat.id, "Tarifni tanlang:", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("plan:"))
    def plan(c):
        days = int(c.data.split(":")[1])
        pending[c.from_user.id] = days
        bot.answer_callback_query(c.id)
        bot.send_message(c.message.chat.id,
                         f"💳 Karta: <code>{CARD}</code>\nSumma: <b>{money(PLANS[days])}</b>\n\n"
                         "To'lov qilgach, <b>chek rasmini</b> shu yerga yuboring.")

    @bot.message_handler(content_types=["photo"])
    def receipt(m):
        uid = m.from_user.id
        days = pending.get(uid, 30)
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"ok:{uid}:{days}"),
               types.InlineKeyboardButton("❌ Rad etish", callback_data=f"no:{uid}"))
        bot.forward_message(ADMIN_ID, m.chat.id, m.message_id)
        bot.send_message(ADMIN_ID, f"Yangi to'lov: {m.from_user.first_name} ({uid}) — {days} kun", reply_markup=kb)
        bot.reply_to(m, "Chek yuborildi. Admin tasdiqlashini kuting ⏳")

    @bot.callback_query_handler(func=lambda c: c.data.startswith(("ok:", "no:")))
    def admin_action(c):
        if c.from_user.id != ADMIN_ID:
            return
        p = c.data.split(":")
        uid = int(p[1])
        if p[0] == "ok":
            grant(uid, int(p[2]))
            bot.send_message(uid, f"✅ To'lov tasdiqlandi! Obuna {p[2]} kunga uzaytirildi.")
            bot.answer_callback_query(c.id, "Tasdiqlandi")
        else:
            bot.send_message(uid, "❌ To'lov rad etildi. Admin bilan bog'laning.")
            bot.answer_callback_query(c.id, "Rad etildi")

    # ======================================================
    # >>> SHU YERGA O'Z BOT KODINGNI (eski faylingni) QO'Y <<<
    # Har bir buyruq boshida tekshir:
    #     if not has_access(m.from_user.id):
    #         return bot.reply_to(m, "Obuna tugagan. /buy")
    # ======================================================
    @bot.message_handler(commands=["service"])
    def service(m):
        if not has_access(m.from_user.id):
            return bot.reply_to(m, "Obuna tugagan. /buy")
        bot.reply_to(m, "Xizmat ishlayapti ✅")


def run_bot():
    if not bot:
        print("BOT_TOKEN yo'q — bot ishga tushmadi")
        return
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
