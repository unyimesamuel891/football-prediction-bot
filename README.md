# ⚽ Football Prediction Telegram Bot

Predicts football matches using **stats + Google Gemini AI** (free!).

**Markets:** 1X2 · BTTS · Over/Under · Correct Score · Expected Corners

---

## 🚀 Setup Guide

### 1. Get a Telegram Bot Token (free)
1. Open Telegram → search **@BotFather**
2. Send `/newbot` → follow prompts
3. Copy the token (e.g. `7123456789:AAFxyz...`)

### 2. Get a Google Gemini API Key (free, no credit card)
1. Go to → https://aistudio.google.com/apikey
2. Sign in with your Google account
3. Click **Create API Key**
4. Copy the key (starts with `AIza...`)

### 3. Upload to GitHub
1. Create a new repo at github.com
2. Upload: `bot.py`, `predictor.py`, `requirements.txt`, `Procfile`

### 4. Deploy on Railway (free hosting)
1. Go to → https://railway.app
2. Sign up with GitHub
3. **New Project → Deploy from GitHub repo** → select your repo
4. Go to **Variables** tab and add:
   - `TELEGRAM_BOT_TOKEN` = your Telegram token
   - `GEMINI_API_KEY` = your Gemini API key
5. Railway auto-deploys — your bot is live! ✅

---

## 🎮 How to Use the Bot

1. Find your bot on Telegram by its username
2. Send `/predict`
3. Enter home team → away team → stats (or skip) → pick markets
4. Tap **⚡ Get Prediction!**

### Optional Stats Format
```
Home form: W W D L W
Away form: L W W D L
Home avg goals scored: 1.8
Away avg goals scored: 1.2
Home avg goals conceded: 0.9
Away avg goals conceded: 1.5
Home avg corners: 5.5
Away avg corners: 4.2
```

---

## 📁 Files
| File | Purpose |
|---|---|
| `bot.py` | Telegram bot logic |
| `predictor.py` | Stats engine + Gemini AI |
| `requirements.txt` | Python dependencies |
| `Procfile` | Tells Railway how to start the bot |

---

## ⚠️ Disclaimer
For entertainment purposes only. Gamble responsibly.
