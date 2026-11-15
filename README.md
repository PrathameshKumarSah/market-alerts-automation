# 📈 Automated Cloud Market Intelligence & Alerts

An automated, 100% free cloud pipeline that synthesizes Indian Stock Market & MCX Commodity briefings using **Google Gemini AI** and delivers real-time actionable alerts to your **Telegram** and **Gmail** on a fixed daily schedule (even when your laptop is turned off).

---

## ⏰ Daily Alert Schedule (Indian Standard Time - Mon to Fri)

| Session | Alert Time (IST) | Target Market | Content Highlights |
| :--- | :--- | :--- | :--- |
| **Morning** | **8:40 AM** | Indian Equities (Pre-Open) | GIFT Nifty, US/Asian market close, Nifty/BankNifty key support/resistance, top stocks in news, opening strategy. |
| **Afternoon** | **1:15 PM** | Mid-Day Equities & Europe | Mid-day market breadth, European opening sentiment, sector leaders/laggards, 2nd-half momentum setups. |
| **Evening** | **6:20 PM** | **MCX Metals & Commodities** | Copper, Zinc, Aluminium LME cues; Gold/Silver COMEX & DXY; Crude Oil; high-impact US macro events tonight. |

---

## 🚀 Setup Guide (Takes 3 Minutes)

### Step 1: Create a Free GitHub Repository
1. Go to [GitHub](https://github.com/) and create a new **Private** repository (e.g. `market-alerts`).
2. Push or upload all files from this directory to your new repository.

### Step 2: Add Secrets to GitHub (One-Time)
In your GitHub repository, go to:
**Settings** ➔ **Secrets and variables** ➔ **Actions** ➔ **New repository secret**

Add the following secrets:

1. `GEMINI_API_KEY`: Your Google AI Studio API key.
2. `TELEGRAM_BOT_TOKEN`: The token given by `@BotFather` when you created your bot.
3. `TELEGRAM_CHAT_ID`: Your numerical Telegram user/chat ID.
4. `GMAIL_USER` *(optional)*: Your Gmail address (e.g., `you@gmail.com`).
5. `GMAIL_APP_PASSWORD` *(optional)*: 16-character Google App Password (generated at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
6. `ALERT_RECIPIENT_EMAIL` *(optional)*: Where emails should be delivered.

---

### Step 3: Test Run on GitHub Actions
1. Go to the **Actions** tab in your GitHub repository.
2. Click on **Market Intelligence Cloud Automation** on the left menu.
3. Click **Run workflow** ➔ Select session (e.g., `evening` or `auto`) ➔ Click **Run workflow**.
4. Check your **Telegram** and **Gmail** — you will receive the alert within 15 seconds!

---

## 💻 Running & Testing Locally on Your PC

1. Create a `.env` file in this folder (copy from `.env.example`) and fill in your keys.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Test any session manually:
   ```bash
   python market_bot.py --session morning    # Morning stocks
   python market_bot.py --session afternoon  # Mid-day update
   python market_bot.py --session evening    # MCX Commodities & Metals (6:20 PM)
   python market_bot.py --session auto       # Auto-detects based on current IST time
   ```
