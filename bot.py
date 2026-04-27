"""
Football Prediction Telegram Bot - Clean 3-step flow
Home team -> Away team -> Pick markets -> Instant prediction
"""

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from predictor import FootballPredictor

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

predictor = FootballPredictor()
user_sessions = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Hey {update.effective_user.first_name}!\n\n"
        "⚽ *BoomDoom Football Predictor*\n"
        "I fetch real stats automatically and use AI to predict matches.\n\n"
        "Just type /predict to begin!",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Commands*\n\n"
        "/predict — New prediction\n"
        "/help — This message\n\n"
        "Supports: Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Champions League\n\n"
        "_Stats are fetched automatically — just type the team name!_",
        parse_mode="Markdown",
    )


async def predict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_sessions[uid] = {"step": "home_team"}
    await update.message.reply_text(
        "🏠 Enter the *Home Team* name:\n_e.g. Arsenal, Real Madrid, Bayern Munich_",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    if uid not in user_sessions:
        await update.message.reply_text("Use /predict to start.")
        return

    session = user_sessions[uid]
    step = session.get("step")

    if step == "home_team":
        session["home_team"] = text
        session["step"] = "away_team"
        await update.message.reply_text(
            f"✅ Home: *{text}*\n\n✈️ Enter the *Away Team* name:",
            parse_mode="Markdown",
        )

    elif step == "away_team":
        session["away_team"] = text
        session["step"] = "markets"
        session["markets"] = []

        keyboard = build_keyboard([])
        await update.message.reply_text(
            f"✅ Away: *{text}*\n\n"
            "🎯 Select markets then tap *⚡ Predict!*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("Use /predict to start a new prediction.")


def build_keyboard(markets):
    def btn(label, key):
        return InlineKeyboardButton(("✅ " if key in markets else "") + label, callback_data=key)
    return [
        [btn("1X2 Winner", "mkt_1x2"), btn("BTTS", "mkt_btts")],
        [btn("Over/Under Goals", "mkt_ou"), btn("Correct Score", "mkt_cs")],
        [btn("Expected Corners", "mkt_corners")],
        [InlineKeyboardButton("⚡ Predict!", callback_data="mkt_run")],
    ]


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
            await query.answer("⚠️ Pick at least one market!", show_alert=True)
            return

        await query.edit_message_text(
            f"⚙️ Fetching stats & predicting...\n"
            f"*{session['home_team']}* vs *{session['away_team']}*\n\n"
            "_This takes about 5 seconds..._",
            parse_mode="Markdown",
        )

        try:
            result = await predictor.predict(
                home_team=session["home_team"],
                away_team=session["away_team"],
                markets=markets,
            )
            await query.edit_message_text(result, parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}\n\nTry /predict again.")

        del user_sessions[uid]
        return

    markets = session.setdefault("markets", [])
    if data in markets:
        markets.remove(data)
    else:
        markets.append(data)
    await query.edit_message_reply_markup(InlineKeyboardMarkup(build_keyboard(markets)))


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("predict", predict_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
 
   
