from flask import Flask, request
import requests
import pymongo
import os
import time

app = Flask(__name__)

# ENV variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")
ADMIN_ID = os.environ.get("ADMIN_ID")  # Set your Telegram user ID as admin

# MongoDB setup
client = pymongo.MongoClient(MONGO_URL)
db = client["actualearn"]
users = db["users"]

# Telegram API URL
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Channel list for verification
REQUIRED_CHANNELS = [
    "https://t.me/YourChannel1",  # Replace with real channels
    "https://t.me/YourChannel2"
]

def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def is_joined(chat_id):
    for channel in REQUIRED_CHANNELS:
        username = channel.split("/")[-1]
        res = requests.get(f"{API_URL}/getChatMember?chat_id=@{username}&user_id={chat_id}")
        try:
            data = res.json()
            if data["result"]["status"] in ["left", "kicked"]:
                return False
        except:
            return False
    return True

def create_user(user_id, referrer=None):
    if users.find_one({"user_id": user_id}):
        return

    users.insert_one({
        "user_id": user_id,
        "referrer": referrer,
        "joined": False,
        "balance": 0,
        "referred_users": [],
        "withdrawals": 0,
        "last_withdraw": 0
    })

    if referrer and user_id != referrer:
        ref_user = users.find_one({"user_id": referrer})
        if ref_user and user_id not in ref_user.get("referred_users", []):
            users.update_one({"user_id": referrer}, {
                "$inc": {"balance": 2},
                "$push": {"referred_users": user_id}
            })
            send_message(referrer, f"✅ New referral joined! ₹2 added to your balance.")

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user = users.find_one({"user_id": chat_id})

        if text.startswith("/start"):
            ref = text.split(" ")[1] if " " in text else None
            create_user(chat_id, int(ref) if ref and ref.isdigit() else None)

            if not is_joined(chat_id):
                join_msg = "❌ Please join all the channels before verifying:\n"
                for ch in REQUIRED_CHANNELS:
                    join_msg += f"➡ {ch}\n"
                join_msg += "\nThen send /start again."
                send_message(chat_id, join_msg)
                return "ok"

            users.update_one({"user_id": chat_id}, {"$set": {"joined": True}})
            send_message(chat_id, "✅ You're verified and ready to earn ₹2 per referral!\nSend your link:\n" +
                         f"https://t.me/YourBotUsername?start={chat_id}")

        elif text == "/balance":
            if user:
                balance = user.get("balance", 0)
                send_message(chat_id, f"💰 Your balance: ₹{balance}")
            else:
                send_message(chat_id, "Please /start first.")

        elif text == "/withdraw":
            if user:
                balance = user.get("balance", 0)
                if balance < 16:
                    send_message(chat_id, "❌ Minimum withdraw amount is ₹16.")
                    return "ok"

                now = int(time.time())
                if now - user.get("last_withdraw", 0) < 86400:
                    send_message(chat_id, "❌ You can only withdraw once per day.")
                    return "ok"

                users.update_one({"user_id": chat_id}, {
                    "$inc": {"withdrawals": 1, "balance": -16},
                    "$set": {"last_withdraw": now}
                })
                send_message(chat_id, "✅ Withdrawal request sent. Admin will process it soon.")
                send_message(ADMIN_ID, f"⚠️ New withdrawal request from user {chat_id}")
            else:
                send_message(chat_id, "Please /start first.")

        else:
            send_message(chat_id, "❓ Unknown command. Use /start, /balance or /withdraw.")

    return "ok"

@app.route("/")
def home():
    return "Bot is running."

if __name__ == "__main__":
    app.run(debug=True)


# Health Check Route
@app.route("/", methods=["GET"])
def home():
    return "✅ Actualearn Bot is Live", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
