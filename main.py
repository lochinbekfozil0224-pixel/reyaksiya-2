#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@RiyaksiyaRobot — Kanal va Guruhlarga Reaksiya qo'shish boti
Yangilanishlar:
  • 300 ta botgacha
  • Tokenlarni birdan ko'p qo'shish (har birini yangi qatorga)
  • 12 ta bot har xil emoji bosadi (random tanlanadi),
    13-bot 1-ning, 14-bot 2-ning... va h.k. — hamma botlar reaksiya bosadi
  • Maxfiy kanallarda ham ishlaydi (-100... yoki https://t.me/c/...)
"""

import asyncio
import json
import os
import random
import logging
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot,
    ReactionTypeEmoji
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.error import TelegramError

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                  CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN = "8552227438:AAGHikxyoQKj2bYMHeoiU5IPFyulV4c9voo"
ADMIN_IDS = [8135915671]
DATA_FILE = "data.json"
MAX_BOTS  = 300

# Mavjud reaksiyalar (Telegramda ruxsat etilganlar)
REACTIONS = [
    "👍", "❤️", "🔥", "🥰", "👏", "😁", "🤩", "🙏", "👌", "🕊",
    "🤡", "🥱", "🥴", "😍", "🐳", "🌚", "🌭", "💯", "🤣",
    "⚡", "🍌", "🏆", "💔", "🤨", "😐", "🍓", "🍾", "💋",
    "😈", "😴", "😭", "🤓", "👻", "👀", "🎃", "🙈", "😇",
    "😨", "🤝", "✍", "🤗", "🫡", "🎅", "🎄", "☃", "💅", "🤪",
    "🗿", "🆒", "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾",
    "🤷", "😡",
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                DATA HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "users":            {},
        "channels":         {},
        "bot_tokens":       [],
        "admin_ids":        ADMIN_IDS,
        "required_channel": "",
        "stats": {
            "total_users":    0,
            "reactions_sent": 0,
            "daily_users":    {}
        },
        "gifts": [
            {"emoji":"🧸","name":"Ayiq",        "price":4000},
            {"emoji":"❤️","name":"Yurak",        "price":4000},
            {"emoji":"🌹","name":"Atirgul",      "price":7000},
            {"emoji":"🎁","name":"Sovg'a",       "price":7000},
            {"emoji":"🎄","name":"Archa",        "price":14000},
            {"emoji":"💖","name":'Yurak "Love"', "price":14000},
            {"emoji":"🍾","name":"Shampan",      "price":14000},
            {"emoji":"🚀","name":"Raketa",       "price":14000},
            {"emoji":"💐","name":"Gul",          "price":14000},
            {"emoji":"🎂","name":"Tort",         "price":14000},
            {"emoji":"💎","name":"Olmos",        "price":25000},
            {"emoji":"💍","name":"Uzuk",         "price":25000},
            {"emoji":"🏆","name":"Kubok",        "price":25000},
        ],
        "guide_video":      None,
        "reaction_counter": 0
    }

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user_id: int, data: dict) -> bool:
    return user_id in data.get("admin_ids", [])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  KANAL VA POST URL HELPER (maxfiy kanallar uchun)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def normalize_channel(text: str) -> str:
    """Foydalanuvchi yuborgan matnni @username yoki -100... formatga o'tkazadi."""
    s = text.strip()
    # Maxfiy kanal: https://t.me/c/1234567890/123 → -1001234567890
    if s.startswith("https://t.me/c/"):
        try:
            core = s.split("/c/")[1].split("/")[0]
            return f"-100{core}"
        except Exception:
            return s
    if s.startswith("https://t.me/"):
        return "@" + s.split("t.me/")[1].split("/")[0]
    if s.startswith("-100") and s[1:].lstrip("-").isdigit():
        return s
    if s.startswith("@"):
        return s
    if s.lstrip("-").isdigit():
        return s
    return "@" + s


def parse_post_url(url: str):
    """Post URL'dan (chat_id_or_@username, message_id) qaytaradi.
       https://t.me/channel/123       → ('@channel', 123)
       https://t.me/c/1234567890/123  → ('-1001234567890', 123)
    """
    url = url.strip()
    try:
        if "/c/" in url:
            parts = url.rstrip("/").split("/c/")[1].split("/")
            return f"-100{parts[0]}", int(parts[1])
        else:
            parts = url.rstrip("/").split("t.me/")[1].split("/")
            return f"@{parts[0]}", int(parts[1])
    except Exception:
        return None, None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#          SUBSCRIPTION HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def check_sub(bot: Bot, user_id: int, channel: str) -> bool:
    try:
        m = await bot.get_chat_member(channel, user_id)
        return m.status not in ["left", "kicked", "banned"]
    except TelegramError:
        return False

def sub_keyboard(channel: str) -> InlineKeyboardMarkup:
    slug = channel.lstrip("@")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{slug}")],
        [InlineKeyboardButton("✅ Obunani tekshirish",    callback_data="check_sub")]
    ])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#               KEYBOARDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 Reaksiyalar",      callback_data="react_menu"),
            InlineKeyboardButton("⚙️ Sozlamalar",       callback_data="react_menu"),
        ],
        [
            InlineKeyboardButton("🛍 Yangi xizmatlar",  callback_data="new_services"),
            InlineKeyboardButton("📖 Bot qo'llanmasi",  callback_data="bot_guide"),
        ],
        [
            InlineKeyboardButton("🎁 Sovg'alar olish",  callback_data="gifts"),
        ]
    ])

def react_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Kanal qo'shish",   callback_data="add_channel"),
            InlineKeyboardButton("🗑 Kanal o'chirish",  callback_data="del_channel"),
        ],
        [
            InlineKeyboardButton("📋 Kanallar ro'yxati",callback_data="ch_list"),
        ],
        [
            InlineKeyboardButton("🔙 Ortga qaytish",    callback_data="back_main"),
        ]
    ])

def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Bot qo'shish",      callback_data="adm_add_bot"),
            InlineKeyboardButton("📋 Botlar ro'yxati",  callback_data="adm_list_bots"),
        ],
        [
            InlineKeyboardButton("🗑 Bot o'chirish",     callback_data="adm_del_bot"),
            InlineKeyboardButton("📊 Statistika",        callback_data="adm_stats"),
        ],
        [
            InlineKeyboardButton("🎁 Sovg'alar",         callback_data="adm_gifts"),
            InlineKeyboardButton("📹 Qo'llanma video",  callback_data="adm_video"),
        ],
        [
            InlineKeyboardButton("📢 Majburiy kanal",   callback_data="adm_req_ch"),
            InlineKeyboardButton("👤 Admin qo'shish",   callback_data="adm_add_admin"),
        ]
    ])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#           WELCOME TEXT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WELCOME = (
    "Salom! 👋\n\n"
    "@RiyaksiyaRobot — Kanal va Guruhlarga Reaksiya qo'shish boti! 🎉\n\n"
    "✨ Endi siz ham o'z kanal yoki guruhingizdagi postlarga qulay va chiroyli "
    "Reaksiyalar qo'shishingiz mumkin.\n\n"
    "👍❤️🔥😮😂 — xohlagancha emojilarni tanlang va "
    "obunachilaringizni yanada faol qiling!"
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                 /start
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = update.effective_user
    uid  = user.id
    req  = data.get("required_channel", "")

    if req:
        if not await check_sub(context.bot, uid, req):
            await update.message.reply_text(
                f"⚠️ Botdan foydalanish uchun avval kanalga obuna bo'ling!\n\n"
                f"📢 Kanal: {req}",
                reply_markup=sub_keyboard(req)
            )
            return

    if str(uid) not in data["users"]:
        data["users"][str(uid)] = {
            "name":     user.full_name,
            "username": user.username,
            "joined":   datetime.now().isoformat(),
        }
        data["stats"]["total_users"] += 1
        today = datetime.now().strftime("%Y-%m-%d")
        data["stats"].setdefault("daily_users", {})
        data["stats"]["daily_users"][today] = \
            data["stats"]["daily_users"].get(today, 0) + 1
        save_data(data)

    await update.message.reply_text(WELCOME, reply_markup=main_menu_kb())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                 /panel
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid  = update.effective_user.id
    if not is_admin(uid, data):
        await update.message.reply_text("❌ Sizda admin huquqi yo'q!")
        return
    await update.message.reply_text(
        "🔐 <b>Admin Panel</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{data['stats']['total_users']}</b>\n"
        f"🤖 Botlar: <b>{len(data['bot_tokens'])}/{MAX_BOTS}</b>\n"
        f"📢 Kanallar: <b>{len(data['channels'])}</b>\n"
        f"⚡ Reaksiyalar: <b>{data['stats'].get('reactions_sent',0)}</b>",
        reply_markup=admin_kb(),
        parse_mode="HTML"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#          SUBSCRIPTION CHECK CALLBACK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cb_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    uid  = q.from_user.id
    req  = data.get("required_channel", "")
    await q.answer()

    if req and not await check_sub(context.bot, uid, req):
        await q.answer("❌ Siz hali obuna bo'lmadingiz!", show_alert=True)
        return

    user = q.from_user
    if str(uid) not in data["users"]:
        data["users"][str(uid)] = {
            "name":     user.full_name,
            "username": user.username,
            "joined":   datetime.now().isoformat(),
        }
        data["stats"]["total_users"] += 1
        save_data(data)

    await q.edit_message_text(WELCOME, reply_markup=main_menu_kb())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#             USER MENU CALLBACKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cb_back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data.clear()
    await q.edit_message_text(WELCOME, reply_markup=main_menu_kb())

async def cb_react_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = (
        "⚙️ <b>Reaksiyalar sozlamalari</b>\n\n"
        "📣 Reaksiyalarni ishlatish uchun avval botni kanal yoki guruhga qo'shishingiz kerak.\n\n"
        "👉 Quyidagi tugmalardan foydalanib, kerakli reaksiyalarni tanlang yoki ko'rish uchun bosing."
    )
    await q.edit_message_text(text, reply_markup=react_menu_kb(), parse_mode="HTML")

# ── Add channel ──
async def cb_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["state"] = "wait_ch"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data="react_menu")]])
    await q.edit_message_text(
        "📣 Reaksiya tizimini yoqish uchun kanal yuboring.\n\n"
        "Variantlar:\n"
        "• <code>@username</code>\n"
        "• <code>https://t.me/username</code>\n"
        "• <b>Maxfiy kanal:</b> <code>-1001234567890</code> yoki "
        "<code>https://t.me/c/1234567890/1</code>\n\n"
        "⚠️ Bot kanalga <b>admin</b> sifatida qo'shilgan bo'lishi shart "
        "(maxfiy kanallar uchun ham).\n\n"
        "Bot nomi: @RiyaksiyaRobot",
        reply_markup=kb, parse_mode="HTML"
    )

# ── Delete channel ──
async def cb_del_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    uid  = str(q.from_user.id)
    await q.answer()

    user_chs = [ch for ch, info in data["channels"].items()
                if str(info.get("owner_id")) == uid]
    if not user_chs:
        await q.answer("❌ Sizda hech qanday kanal yo'q!", show_alert=True)
        return

    btns = [[InlineKeyboardButton(f"🗑 {ch}", callback_data=f"do_del_{ch}")]
            for ch in user_chs]
    btns.append([InlineKeyboardButton("🔙 Ortga", callback_data="react_menu")])
    await q.edit_message_text(
        "🗑 O'chirish uchun kanalni tanlang:\n\nQuyidagi kanallardan birini o'chirish uchun ustiga bosing:",
        reply_markup=InlineKeyboardMarkup(btns)
    )

async def cb_do_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    uid  = str(q.from_user.id)
    ch   = q.data[len("do_del_"):]
    await q.answer()

    if ch in data["channels"] and str(data["channels"][ch].get("owner_id")) == uid:
        del data["channels"][ch]
        save_data(data)
        await q.answer(f"✅ {ch} o'chirildi!", show_alert=True)
    await cb_del_channel(update, context)

# ── Channel list ──
async def cb_ch_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    uid  = str(q.from_user.id)
    await q.answer()

    user_chs = [ch for ch, info in data["channels"].items()
                if str(info.get("owner_id")) == uid]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data="react_menu")]])
    if not user_chs:
        await q.edit_message_text(
            "📋 Sizda hali hech qanday kanal qo'shilmagan.\n\n➕ Kanal qo'shish tugmasini bosing.",
            reply_markup=kb
        )
        return

    btns = []
    for ch in user_chs:
        auto = "✅" if data["channels"][ch].get("auto_reaction") else "❌"
        btns.append([InlineKeyboardButton(f"📢 {ch}  |  Avto: {auto}", callback_data=f"ch_detail_{ch}")])
    btns.append([InlineKeyboardButton("🔙 Ortga", callback_data="react_menu")])
    await q.edit_message_text("📋 Sizning kanallaringiz:", reply_markup=InlineKeyboardMarkup(btns))

# ── Channel detail ──
async def cb_ch_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    ch   = q.data[len("ch_detail_"):]
    await q.answer()

    info     = data["channels"].get(ch, {})
    auto_on  = info.get("auto_reaction", False)
    auto_lbl = "✅ Yoqilgan" if auto_on else "❌ O'chirilgan"
    auto_btn = "🔴 Avtoni o'chirish" if auto_on else "🟢 Avtoni yoqish"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Reaksiya bosish",  callback_data=f"react_post_{ch}"),
            InlineKeyboardButton(auto_btn,              callback_data=f"toggle_auto_{ch}"),
        ],
        [InlineKeyboardButton("🔙 Ortga",               callback_data="ch_list")]
    ])
    await q.edit_message_text(
        f"📢 <b>Kanal:</b> {ch}\n\n🔄 <b>Avto reaksiya:</b> {auto_lbl}\n\nQuyidagi tugmalardan birini tanlang:",
        reply_markup=kb, parse_mode="HTML"
    )

async def cb_toggle_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    ch   = q.data[len("toggle_auto_"):]
    await q.answer()

    if ch in data["channels"]:
        cur = data["channels"][ch].get("auto_reaction", False)
        data["channels"][ch]["auto_reaction"] = not cur
        save_data(data)
        lbl = "✅ Yoqildi" if not cur else "❌ O'chirildi"
        await q.answer(f"Avto reaksiya {lbl}!", show_alert=True)

    q.data = f"ch_detail_{ch}"
    await cb_ch_detail(update, context)

async def cb_react_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q  = update.callback_query
    ch = q.data[len("react_post_"):]
    await q.answer()
    context.user_data["state"] = f"wait_post_url|{ch}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data=f"ch_detail_{ch}")]])
    await q.edit_message_text(
        "⚡ Qaysi postga reaksiya bosish kerak?\n\n"
        "Post URL-ini yuboring:\n"
        "• Ochiq kanal: <code>https://t.me/channel/123</code>\n"
        "• Maxfiy kanal: <code>https://t.me/c/1234567890/123</code>",
        reply_markup=kb, parse_mode="HTML"
    )

# ── New services ──
async def cb_new_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Telegram",  url="https://t.me/user_misr"),
            InlineKeyboardButton("📸 Instagram", url="https://instagram.com/user_misr"),
        ],
        [InlineKeyboardButton("🔙 Ortga", callback_data="back_main")]
    ])
    await q.edit_message_text(
        "🛍 Bizning xizmatlarimizni tanlaganingizdan xursandmiz!\n\n"
        "👇 Ijtimoiy tarmoqlardan birini tanlang:",
        reply_markup=kb
    )

# ── Bot guide ──
async def cb_bot_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data="back_main")]])

    if data.get("guide_video"):
        try:
            await q.message.reply_video(
                data["guide_video"],
                caption="📖 <b>Bot qo'llanmasi</b>",
                reply_markup=kb, parse_mode="HTML"
            )
            await q.message.delete()
            return
        except TelegramError:
            pass

    await q.edit_message_text(
        "📖 Bot qo'llanmasi hali yuklanmagan.\nAdmin tez orada qo'shadi.",
        reply_markup=kb
    )

# ── Gifts ──
async def cb_gifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()

    lines = ["🎁 <b>Sovg'alar ro'yxati:</b>\n"]
    for g in data["gifts"]:
        lines.append(f"{g['emoji']} {g['name']} — {g['price']:,} so'm".replace(",", " "))

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data="back_main")]])
    await q.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#           ADMIN PANEL CALLBACKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cb_adm_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()
    context.user_data.clear()
    await q.edit_message_text(
        "🔐 <b>Admin Panel</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{data['stats']['total_users']}</b>\n"
        f"🤖 Botlar: <b>{len(data['bot_tokens'])}/{MAX_BOTS}</b>\n"
        f"📢 Kanallar: <b>{len(data['channels'])}</b>\n"
        f"⚡ Reaksiyalar: <b>{data['stats'].get('reactions_sent',0)}</b>",
        reply_markup=admin_kb(), parse_mode="HTML"
    )

# ── Add bot ──
async def cb_adm_add_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()
    if not is_admin(q.from_user.id, data):
        await q.answer("❌ Ruxsat yo'q!", show_alert=True); return

    rem = MAX_BOTS - len(data["bot_tokens"])
    context.user_data["adm_state"] = "wait_bot_token"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data="adm_back")]])
    await q.edit_message_text(
        f"🤖 <b>Bot token qo'shish</b>\n\n"
        f"📊 Mavjud: {len(data['bot_tokens'])}/{MAX_BOTS}\n"
        f"➕ Yana qo'shish mumkin: {rem} ta\n\n"
        f"Bot tokenlarini yuboring (bir nechtasini birdan qo'shish uchun "
        f"har birini <b>yangi qatorga</b> yozing):\n"
        f"<code>123456789:ABCdefGHIjklmNOpqrSTUvwxyz\n"
        f"987654321:ZYXwvuTSRqponMLKjihgfedCBA</code>",
        reply_markup=kb, parse_mode="HTML"
    )

# ── List bots ──
async def cb_adm_list_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()
    if not is_admin(q.from_user.id, data):
        await q.answer("❌ Ruxsat yo'q!", show_alert=True); return

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data="adm_back")]])
    if not data["bot_tokens"]:
        await q.edit_message_text("🤖 Botlar ro'yxati bo'sh.", reply_markup=kb); return

    lines = [f"🤖 <b>Botlar ro'yxati ({len(data['bot_tokens'])}/{MAX_BOTS}):</b>\n"]
    for i, tok in enumerate(data["bot_tokens"], 1):
        short = tok[:10] + "..." + tok[-6:]
        lines.append(f"{i}. <code>{short}</code>")
    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n\n... (qisqartirildi)"
    await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

# ── Delete bot ──
async def cb_adm_del_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()
    if not is_admin(q.from_user.id, data):
        await q.answer("❌ Ruxsat yo'q!", show_alert=True); return

    if not data["bot_tokens"]:
        await q.answer("Bo'sh ro'yxat!", show_alert=True); return

    page = context.user_data.get("del_page", 0)
    PAGE = 20
    total = len(data["bot_tokens"])
    start = page * PAGE
    chunk = data["bot_tokens"][start:start+PAGE]

    btns = []
    for j, tok in enumerate(chunk):
        i = start + j
        short = tok[:10] + "..." + tok[-6:]
        btns.append([InlineKeyboardButton(f"🗑 #{i+1}: {short}", callback_data=f"do_del_bot_{i}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"adm_del_p_{page-1}"))
    if start + PAGE < total:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"adm_del_p_{page+1}"))
    if nav:
        btns.append(nav)

    btns.append([InlineKeyboardButton("🔙 Ortga", callback_data="adm_back")])
    await q.edit_message_text(
        f"🗑 O'chirish uchun botni tanlang ({start+1}-{min(start+PAGE,total)}/{total}):",
        reply_markup=InlineKeyboardMarkup(btns)
    )

async def cb_adm_del_p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    page = int(q.data.split("_")[-1])
    context.user_data["del_page"] = page
    await cb_adm_del_bot(update, context)

async def cb_do_del_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()
    idx  = int(q.data.split("_")[-1])
    if 0 <= idx < len(data["bot_tokens"]):
        data["bot_tokens"].pop(idx)
        save_data(data)
        await q.answer("✅ Bot o'chirildi!", show_alert=True)
    await cb_adm_del_bot(update, context)

# ── Stats ──
async def cb_adm_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()
    if not is_admin(q.from_user.id, data):
        await q.answer("❌ Ruxsat yo'q!", show_alert=True); return

    today      = datetime.now().strftime("%Y-%m-%d")
    today_cnt  = data["stats"].get("daily_users", {}).get(today, 0)
    total      = data["stats"]["total_users"]

    weekly = sum(
        v for d, v in data["stats"].get("daily_users", {}).items()
        if (datetime.now() - datetime.strptime(d, "%Y-%m-%d")).days <= 7
    )

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data="adm_back")]])
    await q.edit_message_text(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total}</b>\n"
        f"📅 Bugun kirganlar: <b>{today_cnt}</b>\n"
        f"📆 Haftalik: <b>{weekly}</b>\n"
        f"🤖 Botlar soni: <b>{len(data['bot_tokens'])}/{MAX_BOTS}</b>\n"
        f"📢 Kanallar soni: <b>{len(data['channels'])}</b>\n"
        f"⚡ Yuborilgan reaksiyalar: <b>{data['stats'].get('reactions_sent',0)}</b>",
        reply_markup=kb, parse_mode="HTML"
    )

# ── Required channel ──
async def cb_adm_req_ch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()
    if not is_admin(q.from_user.id, data):
        await q.answer("❌ Ruxsat yo'q!", show_alert=True); return

    context.user_data["adm_state"] = "wait_req_ch"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data="adm_back")]])
    cur_ch = data.get("required_channel") or "Yo'q"
    await q.edit_message_text(
        f"📢 <b>Majburiy obuna kanali</b>\n\n"
        f"Hozirgi: <b>{cur_ch}</b>\n\n"
        f"Yangi kanal @username yuboring (yoki <code>off</code> — o'chirish):",
        reply_markup=kb, parse_mode="HTML"
    )

# ── Guide video ──
async def cb_adm_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()
    if not is_admin(q.from_user.id, data):
        await q.answer("❌ Ruxsat yo'q!", show_alert=True); return

    context.user_data["adm_state"] = "wait_video"
    status = "✅ Bor" if data.get("guide_video") else "❌ Yo'q"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data="adm_back")]])
    await q.edit_message_text(
        f"📹 <b>Qo'llanma video</b>\n\nHolat: {status}\n\nYangi video yuboring:",
        reply_markup=kb, parse_mode="HTML"
    )

# ── Gifts admin ──
async def cb_adm_gifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()
    if not is_admin(q.from_user.id, data):
        await q.answer("❌ Ruxsat yo'q!", show_alert=True); return

    btns = []
    for i, g in enumerate(data["gifts"]):
        btns.append([InlineKeyboardButton(
            f"✏️ {g['emoji']} {g['name']} — {g['price']:,}".replace(",", " ") + " so'm",
            callback_data=f"adm_edit_gift_{i}"
        )])
    btns.append([InlineKeyboardButton("🔙 Ortga", callback_data="adm_back")])

    lines = ["🎁 <b>Sovg'alar boshqaruvi:</b>\n"]
    for i, g in enumerate(data["gifts"]):
        lines.append(f"{i+1}. {g['emoji']} {g['name']} — {g['price']:,} so'm".replace(",", " "))

    await q.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML"
    )

async def cb_adm_edit_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    idx  = int(q.data.split("_")[-1])
    g    = data["gifts"][idx]
    await q.answer()
    context.user_data["adm_state"] = f"wait_gift_{idx}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data="adm_gifts")]])
    await q.edit_message_text(
        f"✏️ <b>Sovg'ani tahrirlash</b>\n\n"
        f"Hozirgi: {g['emoji']} {g['name']} — {g['price']:,} so'm\n\n"
        f"Yangi ma'lumot yuboring:\n"
        f"<code>emoji|nom|narx</code>\n"
        f"Misol: <code>🧸|Ayiq|5000</code>".replace(",", " "),
        reply_markup=kb, parse_mode="HTML"
    )

# ── Add admin ──
async def cb_adm_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = load_data()
    await q.answer()
    if not is_admin(q.from_user.id, data):
        await q.answer("❌ Ruxsat yo'q!", show_alert=True); return

    context.user_data["adm_state"] = "wait_admin_id"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ortga", callback_data="adm_back")]])
    await q.edit_message_text(
        f"👤 <b>Admin qo'shish</b>\n\n"
        f"Hozirgi adminlar: {len(data.get('admin_ids',[]))} ta\n\n"
        f"Yangi admin Telegram ID sini yuboring:",
        reply_markup=kb, parse_mode="HTML"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#       REACTION DISTRIBUTION
#  12 ta har xil emojini random tanlaydi va botlar orasida tarqatadi:
#    bot 1  → emoji[0]
#    bot 2  → emoji[1]
#    ...
#    bot 12 → emoji[11]
#    bot 13 → emoji[0]   (bot 1 ni takrorlaydi)
#    bot 14 → emoji[1]   (bot 2 ni takrorlaydi)
#    ...
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_reaction_plan(bot_count: int) -> list:
    """Har bir botga emoji tayinlaydi. Birinchi 12 ta — har xil random,
    qolganlari shu 12 ta orasida aylanib takrorlanadi."""
    pool = REACTIONS[:]
    random.shuffle(pool)
    chosen = pool[:12]   # 12 ta har xil emoji
    plan = []
    for i in range(bot_count):
        plan.append(chosen[i % 12])
    return plan


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#         MESSAGE HANDLER (State machine)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    data = load_data()
    uid  = update.effective_user.id
    text = (update.message.text or "").strip()

    adm_state = context.user_data.get("adm_state", "")
    usr_state = context.user_data.get("state", "")

    # ── Admin states ──
    if is_admin(uid, data) and adm_state:

        if adm_state == "wait_bot_token":
            # Birdan ko'p tokenni qabul qilamiz (har biri yangi qatorda)
            tokens = [t.strip() for t in (text or "").splitlines() if t.strip()]
            if not tokens:
                await update.message.reply_text("❌ Token yuboring."); return

            added, skipped, bad = 0, 0, 0
            for tok in tokens:
                if ":" not in tok or len(tok) < 20:
                    bad += 1; continue
                if len(data["bot_tokens"]) >= MAX_BOTS:
                    break
                if tok in data["bot_tokens"]:
                    skipped += 1; continue
                try:
                    bot_obj  = Bot(tok)
                    await bot_obj.get_me()
                    data["bot_tokens"].append(tok)
                    added += 1
                except TelegramError:
                    bad += 1
            save_data(data)
            context.user_data.clear()
            await update.message.reply_text(
                f"✅ Qo'shildi: <b>{added}</b>\n"
                f"⚠️ Allaqachon bor: <b>{skipped}</b>\n"
                f"❌ Yaroqsiz: <b>{bad}</b>\n\n"
                f"📊 Jami: {len(data['bot_tokens'])}/{MAX_BOTS}",
                reply_markup=admin_kb(), parse_mode="HTML"
            )

        elif adm_state == "wait_req_ch":
            ch = text
            if ch.lower() == "off":
                data["required_channel"] = ""
                save_data(data); context.user_data.clear()
                await update.message.reply_text("✅ O'chirildi.", reply_markup=admin_kb()); return
            if ch.startswith("https://t.me/"):
                ch = "@" + ch.split("t.me/")[1].split("/")[0]
            if not ch.startswith("@"):
                ch = "@" + ch
            data["required_channel"] = ch
            save_data(data)
            context.user_data.clear()
            await update.message.reply_text(f"✅ Majburiy kanal: {ch}", reply_markup=admin_kb())

        elif adm_state == "wait_video":
            if update.message.video:
                data["guide_video"] = update.message.video.file_id
                save_data(data)
                context.user_data.clear()
                await update.message.reply_text("✅ Qo'llanma video saqlandi!", reply_markup=admin_kb())
            else:
                await update.message.reply_text("❌ Iltimos, video yuboring!")

        elif adm_state.startswith("wait_gift_"):
            idx = int(adm_state.split("_")[-1])
            try:
                parts = text.split("|")
                assert len(parts) == 3
                emoji, name, price = [p.strip() for p in parts]
                data["gifts"][idx] = {"emoji": emoji, "name": name, "price": int(price)}
                save_data(data)
                context.user_data.clear()
                await update.message.reply_text(
                    f"✅ Sovg'a yangilandi: {emoji} {name} — {price} so'm",
                    reply_markup=admin_kb()
                )
            except (AssertionError, ValueError):
                await update.message.reply_text("❌ Format: emoji|nom|narx")

        elif adm_state == "wait_admin_id":
            try:
                new_id = int(text)
                if new_id not in data["admin_ids"]:
                    data["admin_ids"].append(new_id)
                    save_data(data)
                    await update.message.reply_text(f"✅ Admin qo'shildi: {new_id}", reply_markup=admin_kb())
                else:
                    await update.message.reply_text("⚠️ Bu admin allaqachon bor!")
                context.user_data.clear()
            except ValueError:
                await update.message.reply_text("❌ Raqam kiriting!")
        return

    # ── User states ──
    if usr_state == "wait_ch":
        ch = normalize_channel(text)

        try:
            bot_mem = await context.bot.get_chat_member(ch, context.bot.id)
            if bot_mem.status not in ["administrator", "creator"]:
                await update.message.reply_text(
                    f"⚠️ Bot {ch} kanalida admin emas!\nAvval botni admin qilib qo'ying."
                ); return
        except TelegramError:
            await update.message.reply_text(
                f"❌ {ch} topilmadi yoki bot kanalga qo'shilmagan!\n"
                f"Botni kanalga (maxfiy bo'lsa ham) admin qilib qo'shing."
            ); return

        if ch in data["channels"] and str(data["channels"][ch].get("owner_id")) == str(uid):
            await update.message.reply_text(f"⚠️ {ch} allaqachon qo'shilgan!"); return

        data["channels"][ch] = {
            "owner_id":      uid,
            "auto_reaction": False,
            "added":         datetime.now().isoformat()
        }
        save_data(data)
        context.user_data.clear()
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚙️ Reaksiyalar menyusi", callback_data="react_menu")
        ]])
        await update.message.reply_text(
            f"✅ {ch} kanali qo'shildi!\nEndi reaksiyalarni boshqarishingiz mumkin.",
            reply_markup=kb
        )

    elif usr_state and usr_state.startswith("wait_post_url|"):
        ch  = usr_state.split("|", 1)[1]
        target, post_id = parse_post_url(text)
        if not target or not post_id:
            await update.message.reply_text(
                "❌ URL noto'g'ri!\nNamuna:\n"
                "• https://t.me/channel/123\n"
                "• https://t.me/c/1234567890/123"
            ); return

        context.user_data.clear()
        tokens = data.get("bot_tokens", [])
        if not tokens:
            await update.message.reply_text("❌ Hech qanday bot tokeni yo'q!"); return

        msg = await update.message.reply_text(f"⏳ {len(tokens)} ta bot reaksiya yubormoqda...")

        # 12 ta har xil reaksiya tanlanadi, botlar orasida sikl bilan tarqatiladi
        plan = build_reaction_plan(len(tokens))

        ok_count   = 0
        fail_count = 0
        errors     = []

        for i, tok in enumerate(tokens):
            emoji = plan[i]
            try:
                async with Bot(tok) as rb:
                    await rb.set_message_reaction(
                        chat_id=target,
                        message_id=post_id,
                        reaction=[ReactionTypeEmoji(emoji=emoji)]
                    )
                ok_count += 1
            except Exception as e:
                fail_count += 1
                err_short = str(e)[:60]
                errors.append(f"Bot#{i+1}: {err_short}")
                logger.warning(f"Bot #{i+1} reaksiya xatosi: {e}")
            await asyncio.sleep(0.4)

        data["stats"]["reactions_sent"] = data["stats"].get("reactions_sent", 0) + ok_count
        save_data(data)

        used_emojis = sorted(set(plan[:min(12, len(plan))]))
        used_text = "\n\n🎯 Bosilgan reaksiyalar: " + " ".join(used_emojis)

        err_text = ""
        if errors:
            err_text = "\n\n⚠️ Xatolar (birinchi 5):\n" + "\n".join(errors[:5])

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Ortga", callback_data=f"ch_detail_{ch}")
        ]])
        await msg.edit_text(
            f"{'✅' if ok_count else '❌'} Natija:\n\n"
            f"✅ Muvaffaqiyatli: {ok_count}/{len(tokens)}\n"
            f"❌ Xato: {fail_count}/{len(tokens)}"
            + used_text + err_text,
            reply_markup=kb
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#         AUTO REACTION (channel posts)
#  Ommaviy va maxfiy kanallarda ham ishlaydi
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def auto_react(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if not post:
        return

    data = load_data()

    # Kanal kalitini topamiz: ochiq → @username, maxfiy → -100... (chat.id)
    keys = []
    if post.chat.username:
        keys.append(f"@{post.chat.username}")
    keys.append(str(post.chat.id))
    # ham post.chat.id, ham unga -100 qo'shilgan ko'rinishi
    if post.chat.id < 0 and not str(post.chat.id).startswith("-100"):
        keys.append(f"-100{abs(post.chat.id)}")

    info = None
    for k in keys:
        if k in data["channels"]:
            info = data["channels"][k]
            break

    if not info or not info.get("auto_reaction"):
        return

    tokens = data.get("bot_tokens", [])
    if not tokens:
        return

    target  = post.chat.id
    post_id = post.message_id

    # 12 ta har xil emojini tarqatamiz
    plan = build_reaction_plan(len(tokens))

    sent = 0
    for i, tok in enumerate(tokens):
        emoji = plan[i]
        try:
            async with Bot(tok) as rb:
                await rb.set_message_reaction(
                    chat_id=target,
                    message_id=post_id,
                    reaction=[ReactionTypeEmoji(emoji=emoji)]
                )
            sent += 1
        except Exception as e:
            logger.warning(f"Auto-react bot#{i+1}: {e}")
        await asyncio.sleep(0.4)

    data["stats"]["reactions_sent"] = data["stats"].get("reactions_sent", 0) + sent
    save_data(data)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                   MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("panel",  cmd_panel))
    app.add_handler(CommandHandler("admin",  cmd_panel))

    # User callbacks
    app.add_handler(CallbackQueryHandler(cb_check_sub,    pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(cb_back_main,    pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(cb_react_menu,   pattern="^react_menu$"))
    app.add_handler(CallbackQueryHandler(cb_add_channel,  pattern="^add_channel$"))
    app.add_handler(CallbackQueryHandler(cb_del_channel,  pattern="^del_channel$"))
    app.add_handler(CallbackQueryHandler(cb_do_del,       pattern=r"^do_del_(?!bot_).+"))
    app.add_handler(CallbackQueryHandler(cb_ch_list,      pattern="^ch_list$"))
    app.add_handler(CallbackQueryHandler(cb_ch_detail,    pattern="^ch_detail_"))
    app.add_handler(CallbackQueryHandler(cb_toggle_auto,  pattern="^toggle_auto_"))
    app.add_handler(CallbackQueryHandler(cb_react_post,   pattern="^react_post_"))
    app.add_handler(CallbackQueryHandler(cb_new_services, pattern="^new_services$"))
    app.add_handler(CallbackQueryHandler(cb_bot_guide,    pattern="^bot_guide$"))
    app.add_handler(CallbackQueryHandler(cb_gifts,        pattern="^gifts$"))

    # Admin callbacks
    app.add_handler(CallbackQueryHandler(cb_adm_back,       pattern="^adm_back$"))
    app.add_handler(CallbackQueryHandler(cb_adm_add_bot,    pattern="^adm_add_bot$"))
    app.add_handler(CallbackQueryHandler(cb_adm_list_bots,  pattern="^adm_list_bots$"))
    app.add_handler(CallbackQueryHandler(cb_adm_del_p,      pattern=r"^adm_del_p_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_adm_del_bot,    pattern="^adm_del_bot$"))
    app.add_handler(CallbackQueryHandler(cb_do_del_bot,     pattern="^do_del_bot_"))
    app.add_handler(CallbackQueryHandler(cb_adm_stats,      pattern="^adm_stats$"))
    app.add_handler(CallbackQueryHandler(cb_adm_req_ch,     pattern="^adm_req_ch$"))
    app.add_handler(CallbackQueryHandler(cb_adm_video,      pattern="^adm_video$"))
    app.add_handler(CallbackQueryHandler(cb_adm_gifts,      pattern="^adm_gifts$"))
    app.add_handler(CallbackQueryHandler(cb_adm_edit_gift,  pattern="^adm_edit_gift_"))
    app.add_handler(CallbackQueryHandler(cb_adm_add_admin,  pattern="^adm_add_admin$"))

    # Messages
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.VIDEO) & ~filters.COMMAND,
        msg_handler
    ))

    # Auto reactions on channel posts
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, auto_react))

    print(f"🚀 @RiyaksiyaRobot ishga tushdi! (max {MAX_BOTS} bot)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()