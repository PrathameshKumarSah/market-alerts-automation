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
    """Uses Gemini API to synthesize high-quality, structured market analysis."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is missing!")

    ist_now = get_current_ist_time()
    date_str = ist_now.strftime("%A, %d %B %Y")
    time_str = ist_now.strftime("%I:%M %p IST")

    prompts = {
        "morning": f"""
You are an expert Indian stock market strategist. Provide the "Morning Pre-Market & Opening Setup" for today, {date_str} ({time_str}).
Include:
1. 🌐 Global Cues: GIFT Nifty, US markets close (Dow, S&P, Nasdaq), Asian markets (Nikkei, Hang Seng), Dollar Index (DXY), US 10Y Yields.
2. 📊 Indices Key Levels: Nifty 50 and Bank Nifty (Major Support, Pivot, Major Resistance, Expected Open).
3. 📰 Stocks & Sectors in Focus: Top 3-4 news-driven stocks (earnings, order wins, regulatory news).
4. 🎯 Day Trader Action Plan: Key opening strategy, risk management tips, and sectors to watch.
Format cleanly with emojis, bullet points, and concise insights suitable for quick reading on mobile. Keep it under 500 words.
""",
        "afternoon": f"""
You are an expert Indian stock market analyst. Provide the "Mid-Day Stock Market & European Open Review" for today, {date_str} ({time_str}).
Include:
1. ⚡ Market Pulse: Nifty & Bank Nifty mid-day status, breadth (Advances vs Declines), key sector gainers & losers.
2. 🌍 European Markets Open: FTSE, DAX, CAC open sentiment and its potential impact on the Indian afternoon session.
3. 📈 Second-Half Setups: Second-half momentum, VWAP levels, options open interest (OI) shifts, and trailing stop-loss guidance.
4. ⚠️ Key Traps & Risk Watch: Over-trading cautions and upcoming data triggers.
Format cleanly with emojis, bullet points, and high readability for mobile. Keep it under 500 words.
""",
        "evening": f"""
You are an expert commodity & derivatives market analyst specializing in Indian MCX trading.
Provide the "MCX Minerals, Metals & Commodities Evening Briefing" for today, {date_str} ({time_str}).
Focus specifically on the Indian MCX Evening Session (5:00 PM - 11:30 PM IST):
1. 🏭 Base Metals (Minerals/Metals):
   - Copper: Current LME cues, China demand sentiment, Key MCX Support & Resistance.
   - Zinc: LME warehouse inventory trends, Key MCX Support & Resistance.
   - Aluminium: Smelter & energy cost dynamics, Key MCX Support & Resistance.
2. 🪙 Bullion & Energy:
   - Gold & Silver: US Dollar Index impact, evening COMEX trend, key MCX pivot levels.
   - Crude Oil & Natural Gas: Inventory expectations and evening range.
3. 🚨 High-Impact US Macro Events Tonight: US CPI, PPI, Jobless claims, Fed speeches, or EIA reports scheduled between 6:30 PM and 9:30 PM IST.
4. 💡 Evening Session Trading Strategy: Clear risk-reward guidance, position sizing, and caution against illiquid contracts.
Format cleanly with emojis and organized sections for fast mobile reading. Keep it under 550 words.
"""
    }

    prompt = prompts.get(session, prompts["morning"])
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1000
        }
    }

    response = requests.post(api_url, json=payload, timeout=30)
    if response.status_code != 200:
        # Fallback to gemini-1.5-flash if 2.5 is not accessible
        fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        response = requests.post(fallback_url, json=payload, timeout=30)
        response.raise_for_status()

    result = response.json()
    try:
        report_text = result["candidates"][0]["content"]["parts"][0]["text"]
        return report_text.strip()
    except (KeyError, IndexError) as err:
        raise RuntimeError(f"Unexpected response structure from Gemini API: {result}") from err


def send_telegram_alert(text: str, session: str):
    """Sends formatted alert to Telegram."""
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
    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        res = requests.post(url, json=payload, timeout=15)
        if not res.ok:
            # Fallback to plain text if Markdown parsing fails
            payload.pop("parse_mode", None)
            res = requests.post(url, json=payload, timeout=15)

        if not res.ok:
            error_details = res.text
            try:
                error_details = res.json().get("description", res.text)
            except Exception:
                pass
            print(f"❌ Telegram API Error ({res.status_code}): {error_details}")
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

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, ALERT_RECIPIENT_EMAIL, msg.as_string())

    print(f"✅ Gmail alert sent to {ALERT_RECIPIENT_EMAIL}.")
    return True


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
