# Football Prediction Telegram Bot

> A Telegram bot that predicts football match outcomes using statistical analysis and Google Gemini AI.

---

## Overview

This bot accepts match data from the user via a Telegram conversation, runs it through a custom stats engine, and passes it to Google Gemini AI to generate structured match predictions across multiple betting markets.

Built with Python and deployed on Railway.

---

## Features

- **Multi-market predictions** — 1X2, Both Teams to Score (BTTS), Over/Under, Correct Score, Expected Corners
- **Stats-aware** — accepts optional team form, average goals, and corner data for more accurate predictions
- **AI-powered** — uses Google Gemini to reason over stats and generate predictions with confidence levels
- **Conversational flow** — step-by-step Telegram dialogue via python-telegram-bot
- **Fallback mode** — skips stats input and predicts on team names alone if no data is provided

---

## Tech Stack

| Tech | Purpose |
|---|---|
| Python | Core language |
| python-telegram-bot | Telegram bot framework |
| Google Gemini API | AI prediction engine |
| Railway | Deployment & hosting |

---

## How It Works

1. User sends `/predict` to the bot on Telegram
2. Bot prompts for home team and away team names
3. User optionally provides match stats (form, goals, corners)
4. User selects prediction markets (1X2, BTTS, Over/Under, etc.)
5. Stats engine processes the input and calls Gemini API
6. Bot returns a structured prediction with reasoning

### Optional Stats Format
Home form: W W D L W
Away form: L W W D L
Home avg goals scored: 1.8
Away avg goals scored: 1.2
Home avg goals conceded: 0.9
Away avg goals conceded: 1.5
Home avg corners: 5.5
Away avg corners: 4.2

---

## Project Structure

| File | Purpose |
|---|---|
| `bot.py` | Telegram bot logic and conversation handler |
| `predictor.py` | Stats engine + Gemini AI integration |
| `requirements.txt` | Python dependencies |
| `Procfile` | Railway deployment config |

---

## Local Setup

```bash
git clone https://github.com/unyimesamuel891/football-prediction-bot.git
cd football-prediction-bot
pip install -r requirements.txt
```

Create a `.env` file with your credentials:
TELEGRAM_BOT_TOKEN=your_token_here
GEMINI_API_KEY=your_key_here

Then run:

```bash
python bot.py
```

---

## Deployment

Deployed on **Railway** via the included `Procfile`. Connect your GitHub repo on [railway.app](https://railway.app) and set your environment variables in the Railway dashboard.

---

## Disclaimer

For educational and entertainment purposes only.
