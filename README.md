# ⚽ Football Prediction Telegram Bot

Predicts football matches using **stats + Google Gemini AI**.

**Markets:** 1X2 · BTTS · Over/Under · Correct Score · Expected Corners


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
