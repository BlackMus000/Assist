import os
import logging
import urllib.request
import urllib.error
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

user_data: dict = {}

def get_user(user_id: int) -> dict:
    if user_id not in user_data:
        user_data[user_id] = {
            "history": [],
            "tasks": [],
            "notes": [],
            "plan": [],
            "mode": "chat"
        }
    return user_data[user_id]

def ask_gemini(history: list, system: str) -> str:
    contents = []
    # Add system as first user message if history is empty
    full_history = [{"role": "user", "parts": [{"text": system + "\n\nПонял, буду следовать этим инструкциям."}]},
                    {"role": "model", "parts": [{"text": "Понял!"}]}]
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        full_history.append({"role": role, "parts": [{"text": msg["content"]}]})

    payload = json.dumps({"contents": full_history}).encode("utf-8")
    req = urllib.request.Request(GEMINI_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        logger.error(f"Gemini HTTP error {e.code}: {error_body}")
        return "Что-то пошло не так. Попробуй ещё раз."
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return "Что-то пошло не так. Попробуй ещё раз."

# ─── KEYBOARDS ───────────────────────────────────────────────

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Задачи", callback_data="menu_tasks"),
         InlineKeyboardButton("📝 Заметки", callback_data="menu_notes")],
        [InlineKeyboardButton("📅 План дня", callback_data="menu_plan"),
         InlineKeyboardButton("💬 Чат", callback_data="menu_chat")]
    ])

def tasks_keyboard(tasks):
    buttons = []
    active = [t for t in tasks if not t["done"]]
    for t in active[:8]:
        short = t["text"][:30] + ("…" if len(t["text"]) > 30 else "")
        buttons.append([InlineKeyboardButton(f"✓ {short}", callback_data=f"done_{t['id']}")])
    buttons.append([InlineKeyboardButton("➕ Добавить", callback_data="add_task"),
                    InlineKeyboardButton("🗑 Удалить", callback_data="del_task")])
    buttons.append([InlineKeyboardButton("« Назад", callback_data="menu_main")])
    return InlineKeyboardMarkup(buttons)

def notes_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Новая заметка", callback_data="add_note")],
        [InlineKeyboardButton("📋 Показать все", callback_data="show_notes")],
        [InlineKeyboardButton("« Назад", callback_data="menu_main")]
    ])

def plan_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить в план", callback_data="add_plan")],
        [InlineKeyboardButton("📋 Показать план", callback_data="show_plan")],
        [InlineKeyboardButton("🗑 Очистить план", callback_data="clear_plan")],
        [InlineKeyboardButton("« Назад", callback_data="menu_main")]
    ])

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="menu_main")]])

# ─── COMMANDS ────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"Привет, {name}! 👋 Я твой личный ассистент.\n\n"
        "Могу помочь с задачами, заметками, планированием дня и просто поговорить.\n\n"
        "Привет! Какие планы на сегодня? 😊",
        reply_markup=main_keyboard()
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Как пользоваться:\n\n"
        "• /start — главное меню\n"
        "• Просто пиши — отвечу как ИИ\n"
        "• Кнопки меню — задачи, заметки, план"
    )

# ─── CALLBACKS ───────────────────────────────────────────────

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = get_user(uid)
    cb = query.data

    if cb == "menu_main":
        data["mode"] = "chat"
        await query.edit_message_text("Главное меню:", reply_markup=main_keyboard())

    elif cb == "menu_chat":
        data["mode"] = "chat"
        await query.edit_message_text("💬 Просто пиши — я отвечу!", reply_markup=back_keyboard())

    elif cb == "menu_tasks":
        active = [t for t in data["tasks"] if not t["done"]]
        done_c = len([t for t in data["tasks"] if t["done"]])
        text = f"✅ Задачи\n\nАктивных: {len(active)} | Выполнено: {done_c}"
        if active:
            text += "\n\nАктивные:\n" + "\n".join(f"• {t['text']}" for t in active[:10])
        else:
            text += "\n\nНет активных задач."
        await query.edit_message_text(text, reply_markup=tasks_keyboard(data["tasks"]))

    elif cb == "add_task":
        data["mode"] = "add_task"
        await query.edit_message_text("✏️ Напиши задачу (можно несколько через Enter):", reply_markup=back_keyboard())

    elif cb == "del_task":
        active = [t for t in data["tasks"] if not t["done"]]
        if not active:
            await query.edit_message_text("Нет задач для удаления.", reply_markup=tasks_keyboard(data["tasks"]))
            return
        buttons = []
        for t in active[:8]:
            short = t["text"][:28] + ("…" if len(t["text"]) > 28 else "")
            buttons.append([InlineKeyboardButton(f"🗑 {short}", callback_data=f"deltask_{t['id']}")])
        buttons.append([InlineKeyboardButton("« Назад", callback_data="menu_tasks")])
        await query.edit_message_text("Выбери задачу для удаления:", reply_markup=InlineKeyboardMarkup(buttons))

    elif cb.startswith("done_"):
        tid = cb[5:]
        for t in data["tasks"]:
            if str(t["id"]) == tid:
                t["done"] = True
                break
        active = [t for t in data["tasks"] if not t["done"]]
        done_c = len([t for t in data["tasks"] if t["done"]])
        text = f"✅ Задачи\n\nАктивных: {len(active)} | Выполнено: {done_c}"
        if active:
            text += "\n\nАктивные:\n" + "\n".join(f"• {t['text']}" for t in active[:10])
        await query.edit_message_text(text, reply_markup=tasks_keyboard(data["tasks"]))

    elif cb.startswith("deltask_"):
        tid = cb[8:]
        data["tasks"] = [t for t in data["tasks"] if str(t["id"]) != tid]
        await query.edit_message_text("🗑 Задача удалена.", reply_markup=tasks_keyboard(data["tasks"]))

    elif cb == "menu_notes":
        await query.edit_message_text(f"📝 Заметки\n\nВсего: {len(data['notes'])}", reply_markup=notes_keyboard())

    elif cb == "add_note":
        data["mode"] = "add_note"
        await query.edit_message_text("✏️ Напиши заметку (первая строка — заголовок):", reply_markup=back_keyboard())

    elif cb == "show_notes":
        if not data["notes"]:
            await query.edit_message_text("Нет заметок.", reply_markup=notes_keyboard())
            return
        text = "📝 Твои заметки:\n\n"
        for i, n in enumerate(data["notes"][-10:], 1):
            text += f"{i}. {n['title']}\n{n['body'][:80]}{'…' if len(n['body']) > 80 else ''}\n\n"
        await query.edit_message_text(text, reply_markup=notes_keyboard())

    elif cb == "menu_plan":
        await query.edit_message_text(f"📅 План дня\n\nЗаписей: {len(data['plan'])}", reply_markup=plan_keyboard())

    elif cb == "add_plan":
        data["mode"] = "add_plan"
        await query.edit_message_text("✏️ Напиши в формате:\n10:00 Встреча с командой", reply_markup=back_keyboard())

    elif cb == "show_plan":
        if not data["plan"]:
            await query.edit_message_text("План дня пуст.", reply_markup=plan_keyboard())
            return
        sorted_plan = sorted(data["plan"], key=lambda x: x["time"])
        text = "📅 План дня:\n\n" + "\n".join(f"{p['time']} — {p['text']}" for p in sorted_plan)
        await query.edit_message_text(text, reply_markup=plan_keyboard())

    elif cb == "clear_plan":
        data["plan"] = []
        await query.edit_message_text("🗑 План дня очищен.", reply_markup=plan_keyboard())

# ─── MESSAGE HANDLER ─────────────────────────────────────────

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = get_user(uid)
    text = update.message.text.strip()
    mode = data.get("mode", "chat")

    if mode == "add_task":
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            data["tasks"].append({
                "id": str(len(data["tasks"]) + 1) + str(uid),
                "text": line, "done": False,
                "created": datetime.now().strftime("%d.%m %H:%M")
            })
        data["mode"] = "chat"
        await update.message.reply_text(
            f"✅ Добавлено задач: {len(lines)}\n" + "\n".join(f"• {l}" for l in lines),
            reply_markup=main_keyboard()
        )
        return

    if mode == "add_note":
        lines = text.split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        data["notes"].append({"id": len(data["notes"]) + 1, "title": title, "body": body,
                               "created": datetime.now().strftime("%d.%m %H:%M")})
        data["mode"] = "chat"
        await update.message.reply_text(f"📝 Заметка сохранена: {title}", reply_markup=main_keyboard())
        return

    if mode == "add_plan":
        parts = text.split(" ", 1)
        if len(parts) == 2 and ":" in parts[0]:
            data["plan"].append({"time": parts[0], "text": parts[1]})
            data["mode"] = "chat"
            await update.message.reply_text(f"📅 Добавлено: {parts[0]} — {parts[1]}", reply_markup=main_keyboard())
        else:
            await update.message.reply_text("⚠️ Формат: 10:00 Встреча с командой")
        return

    # CHAT
    await update.message.chat.send_action("typing")

    data["history"].append({"role": "user", "content": text})
    if len(data["history"]) > 20:
        data["history"] = data["history"][-20:]

    active_tasks = [t for t in data["tasks"] if not t["done"]]
    tasks_ctx = f"\nАктивные задачи: {', '.join(t['text'] for t in active_tasks[:5])}" if active_tasks else ""
    plan_ctx = ""
    if data["plan"]:
        sp = sorted(data["plan"], key=lambda x: x["time"])
        plan_ctx = f"\nПлан дня: {', '.join(p['time'] + ' ' + p['text'] for p in sp[:5])}"

    system = ("Ты — дружелюбный личный ассистент в Telegram. "
              "Отвечай по-русски, кратко и по делу. "
              "Только простой текст, без markdown. "
              "Будь тёплым и полезным." + tasks_ctx + plan_ctx)

    reply = ask_gemini(data["history"], system)
    data["history"].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)

# ─── MAIN ────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started with Gemini!")
    app.run_polling()

if __name__ == "__main__":
    main()
