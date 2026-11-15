import os
import sys
import argparse
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ALERT_RECIPIENT_EMAIL = os.getenv("ALERT_RECIPIENT_EMAIL", GMAIL_USER)


def get_current_ist_time():
    """Returns the current date and time in Indian Standard Time (UTC+5:30)."""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_offset = datetime.timedelta(hours=5, minutes=30)
    return utc_now + ist_offset


def detect_session_by_time():
    """Auto-detects session based on IST hour if not explicitly provided."""
    ist_now = get_current_ist_time()
    hour = ist_now.hour
    if hour < 11:
        return "morning"
    elif hour < 16:
        return "afternoon"
    else:
        return "evening"


def generate_market_report(session: str) -> str:
    """Uses Gemini API with Google Search Grounding to fetch live, real-time market data."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is missing!")

    ist_now = get_current_ist_time()
    date_str = ist_now.strftime("%A, %d %B %Y")
    time_str = ist_now.strftime("%I:%M %p IST")

    prompts = {
        "morning": f"""
You are an expert Indian financial analyst. Today is {date_str} ({time_str}).
Use Google Search to fetch today's real-time pre-market cues and synthesize the "Morning Stock Market Setup":
1. 🌐 Global Cues: Today's GIFT Nifty level, overnight closing of Dow Jones, S&P 500, Nasdaq, Asian markets (Nikkei, Hang Seng), Dollar Index (DXY), US 10Y Yields.
2. 📊 Indices Key Levels: Nifty 50 and Bank Nifty exact support and resistance levels, expected gap-up or gap-down open.
3. 📰 Top Stocks in News: 3-4 specific stocks making headlines today with clear catalysts (earnings, corporate actions, orders).
4. 🎯 Day Trader Action Plan: Key opening strategy, sector focus, and risk management guidelines.
Format with clean bullet points, emojis, and clear headings. Ensure the full report is complete and not truncated.
""",
        "afternoon": f"""
You are an expert Indian stock market analyst. Today is {date_str} ({time_str}).
Use Google Search to fetch today's live market updates and synthesize the "Mid-Day Stock Market & European Open Review":
1. ⚡ Market Pulse: Live Nifty & Bank Nifty status, market breadth (Advances vs Declines), top gaining and losing sectors today.
2. 🌍 European Markets Open: FTSE, DAX, CAC opening sentiment and its impact on the Indian afternoon session.
3. 📈 Second-Half Setups: Intraday momentum, VWAP levels, options OI trends, and trailing stop loss levels.
4. ⚠️ Key Risk Watch: Volatility risks, expiry dynamics, or afternoon events.
Format with clean bullet points, emojis, and clear headings. Ensure the full report is complete and not truncated.
""",
        "evening": f"""
You are an expert commodities analyst specializing in Indian MCX and global metals. Today is {date_str} ({time_str}).
Use Google Search to find today's latest real-time prices, London Metal Exchange (LME) warehouse data, COMEX, and MCX levels.
Synthesize the "MCX Minerals, Metals & Commodities Evening Briefing" for the 5:00 PM - 11:30 PM IST session:
1. 🏭 Base Metals (Minerals & Industrial Metals):
   - Copper: Today's LME trend, inventories, China demand factors, MCX support and resistance levels.
   - Zinc: LME warehouse trends, galvanizing demand, MCX support and resistance levels.
   - Aluminium: Smelter energy factors, supply updates, MCX support and resistance levels.
2. 🪙 Bullion & Energy:
   - Gold & Silver: Today's COMEX movements, USD/INR impact, MCX pivot levels.
   - Crude Oil & Natural Gas: Inventory news, OPEC updates, MCX evening range.
3. 🚨 High-Impact US Macro Data Tonight: US economic reports releasing tonight (CPI, PPI, Jobless Claims, Fed remarks, EIA crude data).
4. 💡 Evening Session Action Plan: Clear risk-reward setups, lot size risk management, and key price levels to watch.
Format with clean bullet points, emojis, and clear headings. Ensure the full report is complete and not truncated.
"""
    }

    prompt = prompts.get(session, prompts["evening"])

    # Enable Google Search Grounding for real-time live market figures
    # Increased maxOutputTokens to 3500 to prevent mid-sentence cutoff
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 3500
        }
    }

    models = ["gemini-2.5-flash", "gemini-1.5-flash"]
    last_err = None

    for model in models:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            response = requests.post(api_url, json=payload, timeout=45)
            if response.status_code == 200:
                result = response.json()
                candidate = result["candidates"][0]
                parts = candidate["content"]["parts"]
                text = "".join(part.get("text", "") for part in parts if "text" in part).strip()
                if text:
                    return text
            else:
                last_err = f"Model {model} returned HTTP {response.status_code}: {response.text}"
        except Exception as e:
            last_err = str(e)

    # Fallback without search grounding if tool is restricted
    fallback_payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 3500
        }
    }
    for model in models:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            response = requests.post(api_url, json=fallback_payload, timeout=35)
            if response.status_code == 200:
                result = response.json()
                parts = result["candidates"][0]["content"]["parts"]
                text = "".join(part.get("text", "") for part in parts if "text" in part).strip()
                if text:
                    return text
        except Exception:
            pass

    raise RuntimeError(f"Failed to generate report from Gemini API: {last_err}")


def send_telegram_alert(text: str, session: str):
    """Sends formatted alert to Telegram with chunking and error reporting."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials not configured. Skipping Telegram alert.")
        return False

    session_titles = {
        "morning": "🌅 *NIFTY & EQUITIES: MORNING SETUP*",
        "afternoon": "☀️ *NIFTY & MID-DAY MARKET REVIEW*",
        "evening": "🌙 *MCX METALS & COMMODITY BRIEFING*"
    }
    header = f"{session_titles.get(session, '📊 MARKET ALERT')}\n\n"
    full_message = header + text

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Telegram max message length is 4096 chars. Split if needed.
    chunks = [full_message[i:i + 4000] for i in range(0, len(full_message), 4000)]
    for idx, chunk in enumerate(chunks, 1):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        res = requests.post(url, json=payload, timeout=20)
        if not res.ok:
            # Fallback to plain text if Markdown parsing fails
            payload.pop("parse_mode", None)
            res = requests.post(url, json=payload, timeout=20)

        if not res.ok:
            error_details = res.text
            try:
                error_details = res.json().get("description", res.text)
            except Exception:
                pass
            print(f"❌ Telegram API Error on chunk {idx} ({res.status_code}): {error_details}")
            if "bot can't initiate conversation" in error_details.lower() or "forbidden" in error_details.lower():
                print("💡 FIX: You must open your bot in Telegram and tap 'START' (or send /start) so it has permission to message you!")
            return False

    print("✅ Telegram alert sent successfully.")
    return True


def send_gmail_alert(text: str, session: str):
    """Sends HTML email report via Gmail SMTP."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("⚠️ Gmail credentials not configured. Skipping Gmail alert.")
        return False

    ist_now = get_current_ist_time()
    date_str = ist_now.strftime("%d %b %Y")

    session_subjects = {
        "morning": f"🌅 Morning Stock Market Setup - {date_str}",
        "afternoon": f"☀️ Mid-Day Market & European Open - {date_str}",
        "evening": f"🌙 MCX Evening Metals & Commodities Brief - {date_str}"
    }

    subject = session_subjects.get(session, f"Market Alert - {date_str}")
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f7f9fa; color: #202124; padding: 20px; }}
            .container {{ max-width: 650px; margin: auto; background: #ffffff; border-radius: 8px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
            .header {{ border-bottom: 2px solid #1a73e8; padding-bottom: 12px; margin-bottom: 20px; }}
            .title {{ font-size: 20px; font-weight: bold; color: #1a73e8; margin: 0; }}
            .timestamp {{ font-size: 13px; color: #5f6368; margin-top: 4px; }}
            .content {{ line-height: 1.6; font-size: 14px; white-space: pre-wrap; }}
            .footer {{ margin-top: 24px; border-top: 1px solid #e0e0e0; padding-top: 12px; font-size: 12px; color: #70757a; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title">{subject}</div>
                <div class="timestamp">Generated for {GMAIL_USER} • {ist_now.strftime('%I:%M %p IST')}</div>
            </div>
            <div class="content">{text}</div>
            <div class="footer">
                Automated Market Intelligence • Powered by Gemini AI on Cloud
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Market Intelligence <{GMAIL_USER}>"
    msg["To"] = ALERT_RECIPIENT_EMAIL

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, ALERT_RECIPIENT_EMAIL, msg.as_string())
        print(f"✅ Gmail alert sent to {ALERT_RECIPIENT_EMAIL}.")
        return True
    except Exception as e:
        print(f"❌ Failed to send Gmail alert: {e}")
        return False


def save_local_log(text: str, session: str):
    """Saves a markdown archive of the briefing."""
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(log_dir, "market_reports_log.md")
    ist_now = get_current_ist_time()

    entry = f"\n\n---\n### {session.upper()} REPORT — {ist_now.strftime('%Y-%m-%d %H:%M:%S IST')}\n\n{text}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"📁 Log archived to {log_file}")


def main():
    parser = argparse.ArgumentParser(description="Market Intelligence & Alerts Bot")
    parser.add_argument(
        "--session",
        choices=["morning", "afternoon", "evening", "auto"],
        default="auto",
        help="Target session: morning (stocks), afternoon (midday), evening (MCX), or auto."
    )
    args = parser.parse_args()

    session = detect_session_by_time() if args.session == "auto" else args.session
    print(f"🚀 Starting Market Intelligence Bot for session: [{session.upper()}]...")

    report = generate_market_report(session)
    print("\n--- GENERATED REPORT ---")
    print(report[:300] + "...\n------------------------")

    save_local_log(report, session)
    send_telegram_alert(report, session)
    send_gmail_alert(report, session)

    print(f"🎯 Execution completed successfully for {session} session.")


if __name__ == "__main__":
    main()
