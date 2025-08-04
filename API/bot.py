import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Load environment variables from .env file
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SCOPES = ['https://www.googleapis.com/auth/business.manage']

if not TOKEN:
    raise ValueError("Telegram Bot Token is missing! Please set TELEGRAM_BOT_TOKEN in your .env file")

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


def authenticate():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=8080)
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())
    return creds


def get_all_locations(creds):
    service = build("mybusinessbusinessinformation", "v1", credentials=creds)
    accounts_response = service.accounts().list().execute()
    accounts = accounts_response.get('accounts', [])
    if not accounts:
        return []
    account_name = accounts[0]['name']
    locations_response = service.accounts().locations().list(parent=account_name).execute()
    locations = locations_response.get('locations', [])
    return [loc["name"] for loc in locations]


def post_update_to_location(location_name, text, creds):
    update_service = build("mybusiness", "v4", credentials=creds)
    body = {
        "summary": text,
        "languageCode": "en"
    }
    try:
        update_service.accounts().locations().localPosts().create(
            parent=location_name,
            body={"languageCode": "en", "summary": text}
        ).execute()
        return True
    except Exception as e:
        logging.error(f"Error posting to {location_name}: {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Use:\n\n/post <text> — post to the first business profile\n/allpost <text> — post to ALL profiles")


async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("❌ Usage: /post <your update text>")
        return

    creds = authenticate()
    locations = get_all_locations(creds)
    if not locations:
        await update.message.reply_text("❌ No business profiles found.")
        return

    success = post_update_to_location(locations[0], text, creds)
    if success:
        await update.message.reply_text("✅ Posted to 1st profile.")
    else:
        await update.message.reply_text("❌ Failed to post.")


async def allpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("❌ Usage: /allpost <your update text>")
        return

    creds = authenticate()
    locations = get_all_locations(creds)
    if not locations:
        await update.message.reply_text("❌ No business profiles found.")
        return

    count = 0
    for loc in locations:
        if post_update_to_location(loc, text, creds):
            count += 1

    await update.message.reply_text(f"✅ Posted to {count} profile(s).")


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CommandHandler("allpost", allpost))
    logging.info("🤖 Telegram bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
