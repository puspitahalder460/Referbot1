from flask import Flask, request
import os
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Flask App
app = Flask(__name__)

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
VERIFY_CHANNELS = os.getenv("VERIFY_CHANNELS", "").split(",")
REWARD_AMOUNT = int(os.getenv("REWARD_AMOUNT", 2))

# Telegram API URL
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# MongoDB Setup
client = MongoClient(MONGO_URI)
db = client["actualearn"]
users = db["users"]

# Send message function
def send_message(chat_id, text, buttons=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    requests.post(url, json=payload)

# Check if user is in channel
def is_user_in_channel(user_id, channel):
    url = f"{BASE_URL}/getChatMember"
    response = requests.get(url, params={"chat_id": channel, "user_id": user_id})
    try:
        status = response.json().get("result", {}).get("status")
        return status in ["member", "administrator", "creator"]
    except:
        return False

# Telegram Webhook Handler
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        if not users.find_one({"user_id": user_id}):
            users.insert_one({"user_id": user_id, "referred_by": None, "rewarded": False})

        if text.startswith("/start"):
            parts = text.split()
            if len(parts) > 1:
                ref_id = int(parts[1])
                if ref_id != user_id:
                    user_data = users.find_one({"user_id": user_id})
                    if not user_data.get("referred_by"):
                        users.update_one({"user_id": user_id}, {"$set": {"referred_by": ref_id}})
                        send_message(chat_id, "✅ Referral code applied!")

            buttons = [[{"text": f"Join {ch}", "url": f"https://t.me/{ch.replace('@','')}"}] for ch in VERIFY_CHANNELS]
            buttons.append([{"text": "✅ I've Joined", "callback_data": "verify"}])
            send_message(chat_id, "👋 <b>Welcome to Actualearn!</b>\n\nPlease join all channels below and then verify:", buttons)

    elif "callback_query" in data:
        query = data["callback_query"]
        user_id = query["from"]["id"]
        chat_id = query["message"]["chat"]["id"]

        if query["data"] == "verify":
            all_joined = all(is_user_in_channel(user_id, ch) for ch in VERIFY_CHANNELS)

            if all_joined:
                user = users.find_one({"user_id": user_id})
                if user and not user.get("rewarded"):
                    users.update_one({"user_id": user_id}, {"$set": {"rewarded": True}})
                    send_message(chat_id, f"🎉 <b>Verified!</b> You’ve received ₹{REWARD_AMOUNT} reward!")

                    ref_id = user.get("referred_by")
                    if ref_id:
                        send_message(ref_id, f"🎉 Your friend joined! You’ve earned ₹{REWARD_AMOUNT} reward!")
                else:
                    send_message(chat_id, "✅ You are already verified and rewarded.")
            else:
                send_message(chat_id, "❌ Please join all the channels before verifying.")

    return "ok", 200

# Health Check Route
@app.route("/", methods=["GET"])
def home():
    return "✅ Actualearn Bot is Live", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
