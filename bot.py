"""
Football Prediction Telegram Bot
Main bot file — handles all Telegram interactions
"""

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from predictor import FootballPredictor

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

predictor = FootballPredictor()

# ─── State Storage (in-memory; use Redis/DB for production) ───────────────────
user_sessions = {}

# ─── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome = (
        f"👋 Hello {user.first_name}!\n\n"
        "⚽ *Football Prediction Bot*\n"
        "I combine real stats with AI reasoning to predict match outcomes.\n\n"
        "Use /predict to get started, or /help for all commands."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


# ─── /help ────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Available Commands*\n\n"
        "/predict — Start a new match prediction\n"
        "/help — Show this help message\n"
        "/about — About this bot\n\n"
        "*Prediction Markets Supported:*\n"
        "• 1X2 — Match winner\n"
        "• BTTS — Both teams to score\n"
        "• Over/Under goals\n"
        "• Correct score\n"
        "• Expected corners\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


# ─── /about ───────────────────────────────────────────────────────────────────
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *About This Bot*\n\n"
        "This bot uses a combination of:\n"
        "• 📊 Statistical models (form, goals, home/away advantage)\n"
        "• 🧠 Claude AI reasoning for contextual insight\n\n"
        "Enter team names, select your options, and receive a detailed prediction!\n\n"
        "_Predictions are for entertainment purposes only._"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /predict ────────────────────────────────────────────────────────────────
async def predict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_sessions[uid] = {"step": "home_team"}

    await update.message.reply_text(
        "🏠 *Step 1/4* — Enter the *Home Team* name:\n\n"
        "_Example: Arsenal, Real Madrid, Manchester City_",
        parse_mode="Markdown",
    )


# ─── Message Handler (collects team names + stats input) ─────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    if uid not in user_sessions:
        await update.message.reply_text(
            "Use /predict to start a new prediction."
        )
        return

    session = user_sessions[uid]
    step = session.get("step")

    # ── Step 1: Home team ──
    if step == "home_team":
        session["home_team"] = text
        session["step"] = "away_team"
        await update.message.reply_text(
            f"✅ Home team: *{text}*\n\n"
            "✈️ *Step 2/4* — Enter the *Away Team* name:",
            parse_mode="Markdown",
        )

    # ── Step 2: Away team ──
    elif step == "away_team":
        session["away_team"] = text
        session["step"] = "stats"
        await update.message.reply_text(
            f"✅ Away team: *{text}*\n\n"
            "📊 *Step 3/4* — Enter recent stats (optional but improves accuracy).\n\n"
            "Format (copy & fill in):\n"
            "```\n"
            "Home form: W W D L W\n"
            "Away form: L W W D L\n"
            "Home avg goals scored: 1.8\n"
            "Away avg goals scored: 1.2\n"
            "Home avg goals conceded: 0.9\n"
            "Away avg goals conceded: 1.5\n"
            "Home avg corners: 5.5\n"
            "Away avg corners: 4.2\n"
            "```\n"
            "_Or type *skip* to use AI estimation only._",
            parse_mode="Markdown",
        )

    # ── Step 3: Stats ──
    elif step == "stats":
        if text.lower() == "skip":
            session["stats_raw"] = None
        else:
            session["stats_raw"] = text
        session["step"] = "markets"

        keyboard = [
            [
                InlineKeyboardButton("1X2 (Match Winner)", callback_data="mkt_1x2"),
                InlineKeyboardButton("BTTS", callback_data="mkt_btts"),
            ],
            [
                InlineKeyboardButton("Over/Under Goals", callback_data="mkt_ou"),
                InlineKeyboardButton("Correct Score", callback_data="mkt_cs"),
            ],
            [
                InlineKeyboardButton("Expected Corners", callback_data="mkt_corners"),
            ],
            [
                InlineKeyboardButton("✅ Get Prediction!", callback_data="mkt_run"),
            ],
        ]
        session["markets"] = []
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🎯 *Step 4/4* — Select prediction markets:\n"
            "_(tap to toggle, then press ✅ Get Prediction!)_",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    else:
        await update.message.reply_text("Use /predict to start a new prediction.")


# ─── Callback: Market Selection ───────────────────────────────────────────────
MARKET_LABELS = {
    "mkt_1x2": "1X2 (Match Winner)",
    "mkt_btts": "BTTS",
    "mkt_ou": "Over/Under Goals",
    "mkt_cs": "Correct Score",
    "mkt_corners": "Expected Corners",
}

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if uid not in user_sessions:
        await query.edit_message_text("Session expired. Use /predict to start again.")
        return

    session = user_sessions[uid]

    if data == "mkt_run":
        markets = session.get("markets", [])
        if not markets:
            await query.answer("⚠️ Select at least one market!", show_alert=True)
            return

        await query.edit_message_text(
            f"⚙️ Analysing *{session['home_team']}* vs *{session['away_team']}*...\n"
            "🤖 Combining stats + AI — this takes a few seconds...",
            parse_mode="Markdown",
        )

        result = await predictor.predict(
            home_team=session["home_team"],
            away_team=session["away_team"],
            stats_raw=session.get("stats_raw"),
            markets=markets,
        )

        await query.edit_message_text(result, parse_mode="Markdown")
        del user_sessions[uid]
        return

    # Toggle market selection
    markets = session.setdefault("markets", [])
    if data in markets:
        markets.remove(data)
    else:
        markets.append(data)

    # Rebuild keyboard with ✅ indicators
    keyboard = [
        [
            InlineKeyboardButton(
                ("✅ " if "mkt_1x2" in markets else "") + "1X2 (Match Winner)",
                callback_data="mkt_1x2",
            ),
            InlineKeyboardButton(
                ("✅ " if "mkt_btts" in markets else "") + "BTTS",
                callback_data="mkt_btts",
            ),
        ],
        [
            InlineKeyboardButton(
                ("✅ " if "mkt_ou" in markets else "") + "Over/Under Goals",
                callback_data="mkt_ou",
            ),
            InlineKeyboardButton(
                ("✅ " if "mkt_cs" in markets else "") + "Correct Score",
                callback_data="mkt_cs",
            ),
        ],
        [
            InlineKeyboardButton(
                ("✅ " if "mkt_corners" in markets else "") + "Expected Corners",
                callback_data="mkt_corners",
            ),
        ],
        [
            InlineKeyboardButton("⚡ Get Prediction!", callback_data="mkt_run"),
        ],
    ]
    await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("Set the TELEGRAM_BOT_TOKEN environment variable.")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("predict", predict_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started. Polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
