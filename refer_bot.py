import sqlite3
from telebot import TeleBot, types
import random

BOT_TOKEN = "8344213582:AAE1TOOATmLYXRu4tIm6Nvqv0UoI1axzvN0"
OWNER_ID = 8332280910

bot = TeleBot(BOT_TOKEN)

db = sqlite3.connect("referral.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users(
 user_id INTEGER PRIMARY KEY,
 referrals INTEGER DEFAULT 0,
 diamonds INTEGER DEFAULT 0
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS coupons(code TEXT)""")
cur.execute("""CREATE TABLE IF NOT EXISTS admins(
 user_id INTEGER PRIMARY KEY
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS channels(
 username TEXT PRIMARY KEY
)""")
db.commit()

cur.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)",(OWNER_ID,))
cur.execute("INSERT OR IGNORE INTO channels(username) VALUES(?)",("BOSSxNS",))

cur.execute("SELECT COUNT(*) FROM coupons")
if cur.fetchone()[0] == 0:
    test_coupon = str(random.randint(100000000, 999999999))
    cur.execute("INSERT INTO coupons(code) VALUES(?)",(test_coupon,))
    print("Test coupon added:", test_coupon)
db.commit()

def is_admin(uid):
    cur.execute("SELECT 1 FROM admins WHERE user_id=?",(uid,))
    return cur.fetchone() is not None

def ensure_admin(uid):
    cur.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)",(uid,))
    db.commit()

def get_channels():
    cur.execute("SELECT username FROM channels")
    return [r[0] for r in cur.fetchall()]

def add_channel(username):
    cur.execute("INSERT OR IGNORE INTO channels(username) VALUES(?)",(username,))
    db.commit()

def remove_channel(username):
    cur.execute("DELETE FROM channels WHERE username=?",(username,))
    db.commit()

def add_user(uid):
    cur.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)",(uid,))
    db.commit()

def add_referral(uid):
    cur.execute("UPDATE users SET referrals=referrals+1, diamonds=diamonds+1 WHERE user_id=?",(uid,))
    db.commit()

def get_user(uid):
    cur.execute("SELECT referrals, diamonds FROM users WHERE user_id=?",(uid,))
    return cur.fetchone()

def is_joined_all(uid):
    for ch in get_channels():
        try:
            m = bot.get_chat_member(f"@{ch}", uid)
            if m.status in ["left","kicked"]:
                return False
        except:
            return False
    return True

@bot.message_handler(commands=["start"])
def start(msg):
    uid = msg.from_user.id
    add_user(uid)
    ensure_admin(OWNER_ID)

    if len(msg.text.split())>1:
        ref = msg.text.split()[1]
        if ref.isdigit() and int(ref)!=uid:
            add_referral(int(ref))

    kb = types.InlineKeyboardMarkup()
    for ch in get_channels():
        kb.add(types.InlineKeyboardButton(f"Join @{ch}", url=f"https://t.me/{ch}"))
    kb.add(types.InlineKeyboardButton("✅ I Joined", callback_data="check"))

    bot.reply_to(msg,
        "🎁 *Referral Coupon Bot*\n"
        "1 Refer = 1 Diamond 💎\n"
        "Minimum Withdraw = 5 💎\n"
        "1 Coupon = 5 💎\n\n"
        "👉 Join all channels first",
        parse_mode="Markdown",
        reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data=="check")
def check(cb):
    if not is_joined_all(cb.from_user.id):
        bot.answer_callback_query(cb.id,"❌ Join all channels first")
        return

    r,d=get_user(cb.from_user.id)

    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💎 Withdraw",callback_data="withdraw"))
    kb.add(types.InlineKeyboardButton("🔗 Invite Link",callback_data="refer"))
    if is_admin(cb.from_user.id):
        kb.add(types.InlineKeyboardButton("🛠 Admin Panel",callback_data="admin"))

    bot.edit_message_text(
        f"👤 *Dashboard*\n🔗 Referrals: {r}\n💎 Diamonds: {d}",
        cb.message.chat.id,cb.message.message_id,
        parse_mode="Markdown",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data=="refer")
def refer(cb):
    uid=cb.from_user.id
    bot.send_message(cb.message.chat.id,
    f"📢 *Your link*\nhttps://t.me/{bot.get_me().username}?start={uid}",
    parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c:c.data=="withdraw")
def withdraw(cb):
    _,d=get_user(cb.from_user.id)
    if d<5:
        bot.answer_callback_query(cb.id,"❌ Need 5 diamonds minimum")
        return
    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("1 Coupon (5💎)",callback_data="w1"))
    kb.add(types.InlineKeyboardButton("2 Coupons (10💎)",callback_data="w2"))
    bot.send_message(cb.message.chat.id,"🎁 Select:",reply_markup=kb)

def send_coupon(count):
    cur.execute("SELECT rowid, code FROM coupons LIMIT ?",(count,))
    rows=cur.fetchall()
    if len(rows)<count: return None
    ids=[str(r[0]) for r in rows]
    cur.execute(f"DELETE FROM coupons WHERE rowid IN ({','.join(ids)})")
    db.commit()
    return "\n".join([r[1] for r in rows])

def update_diamonds(uid,amount):
    cur.execute("UPDATE users SET diamonds=diamonds-? WHERE user_id=?",(amount,uid))
    db.commit()

@bot.callback_query_handler(func=lambda c:c.data in ["w1","w2"])
def process_w(cb):
    uid=cb.from_user.id
    amount = 5 if cb.data=="w1" else 10
    count  = 1 if cb.data=="w1" else 2
    _,d=get_user(uid)
    if d<amount:
        bot.answer_callback_query(cb.id,"❌ Not enough diamonds"); return
    codes=send_coupon(count)
    if not codes:
        bot.send_message(uid,"⚠️ Coupons out of stock. Contact admin.")
        return
    update_diamonds(uid,amount)
    bot.send_message(uid,f"🎊 *Your Coupon(s)*\n\n{codes}",parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c:c.data=="admin")
def admin(cb):
    if not is_admin(cb.from_user.id): return
    kb=types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Add Coupon","📦 Coupon Stock")
    kb.add("👥 Users Count")
    kb.add("➕ Add Admin","➖ Remove Admin","👮 Admin List")
    kb.add("📌 Add Channel","❌ Remove Channel","📃 Channel List")
    bot.send_message(cb.message.chat.id,"🛠 Admin Panel",reply_markup=kb)

bot.infinity_polling()
