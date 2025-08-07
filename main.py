from flask import Flask, request
import requests
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
VERIFY_CHANNELS = os.getenv("VERIFY_CHANNELS", "").split(",")
REWARD_AMOUNT = int(os.getenv("REWARD_AMOUNT", 2))
MONGO_URI = os.getenv("MONGO_URI")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

client = MongoClient(MONGO_URI)
db = client["actualearn"]
users = db["users"]

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

def is_user_in_channel(user_id, channel):
    url = f"{BASE_URL}/getChatMember"
    resp = requests.get(url, params={"chat_id": channel, "user_id": user_id})
    try:
        status = resp.json()["result"]["status"]
        return status in ["member", "administrator", "creator"]
    except:
        return False

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    # Message handler
    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        user = users.find_one({"user_id": user_id})
        if not user:
            users.insert_one({"user_id": user_id, "referred_by": None, "rewarded": False})

        if text.startswith("/start"):
            parts = text.split()
            if len(parts) > 1:
                ref_id = int(parts[1])
                if ref_id != user_id:
                    existing = users.find_one({"user_id": user_id})
                    if existing and not existing.get("referred_by"):
                        users.update_one({"user_id": user_id}, {"$set": {"referred_by": ref_id}})
                        send_message(chat_id, "✅ Referral code applied!")

            # Join buttons
            buttons = []
            for channel in VERIFY_CHANNELS:
                buttons.append([{
                    "text": f"Join {channel}",
                    "url": f"https://t.me/{channel.replace('@', '')}"
                }])
            # Add verify button
            buttons.append([{
                "text": "✅ I've Joined",
                "callback_data": "verify"
            }])
            send_message(
                chat_id,
                "👋 <b>Welcome to Actualearn!</b>\n\nPlease join all the required channels below to continue:",
                buttons=buttons
            )

    # Callback handler for "verify"
    if "callback_query" in data:
        query = data["callback_query"]
        user_id = query["from"]["id"]
        chat_id = query["message"]["chat"]["id"]
        data_id = query["id"]

        if query["data"] == "verify":
            all_joined = all(is_user_in_channel(user_id, channel) for channel in VERIFY_CHANNELS)
            if all_joined:
                user = users.find_one({"user_id": user_id})
                if user and not user.get("rewarded", False):
                    users.update_one({"user_id": user_id}, {"$set": {"rewarded": True}})
                    send_message(chat_id, f"🎉 <b>Success!</b> You’ve received ₹{REWARD_AMOUNT} reward!")

                    referrer_id = user.get("referred_by")
                    if referrer_id:
                        send_message(referrer_id, f"🎉 You got ₹{REWARD_AMOUNT} for referring a friend!")
                else:
                    send_message(chat_id, "✅ You’ve already verified and received your reward.")
            else:
                send_message(chat_id, "❌ Please join all the channels before verifying.")

    return "ok", 200
