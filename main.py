from flask import Flask, request
import requests
import os
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

client = MongoClient(MONGO_URL)
db = client["ActualearnBot"]
users = db["users"]

VERIFY_CHANNELS = ["@yourchannel1", "@yourchannel2"]
REWARD_AMOUNT = 2
MIN_WITHDRAW = 16

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def user_joined_all_channels(user_id):
    for channel in VERIFY_CHANNELS:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        res = requests.get(url, params={"chat_id": channel, "user_id": user_id})
        data = res.json()
        if data["result"]["status"] not in ["member", "administrator", "creator"]:
            return False
    return True

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        text = message.get("text", "")
        first_name = message["from"].get("first_name", "")

        user = users.find_one({"user_id": user_id})
        if not user:
            users.insert_one({
                "user_id": user_id,
                "balance": 0,
                "referrals": [],
                "withdraws": [],
                "last_withdraw": None
            })

        if text.startswith("/start"):
            args = text.split()
            if len(args) > 1:
                ref_id = int(args[1])
                if ref_id != user_id:
                    referrer = users.find_one({"user_id": ref_id})
                    if referrer and user_id not in referrer.get("referrals", []):
                        users.update_one({"user_id": ref_id}, {
                            "$inc": {"balance": REWARD_AMOUNT},
                            "$push": {"referrals": user_id}
                        })
                        send_message(ref_id, f"🎉 You earned ₹{REWARD_AMOUNT} for referring {first_name}!")
            send_message(chat_id, "👋 Welcome to Actualearn!\nUse /verify to get ₹2 for joining our channels.")

        elif text == "/verify":
            if user_joined_all_channels(user_id):
                user = users.find_one({"user_id": user_id})
                if not user.get("verified", False):
                    users.update_one({"user_id": user_id}, {
                        "$inc": {"balance": REWARD_AMOUNT},
                        "$set": {"verified": True}
                    })
                    send_message(chat_id, f"✅ Channels verified!\nYou received ₹{REWARD_AMOUNT}.")
                else:
                    send_message(chat_id, "✅ Already verified.")
            else:
                send_message(chat_id, "❌ Please join all the channels before verifying.")

        elif text == "/balance":
            user = users.find_one({"user_id": user_id})
            balance = user.get("balance", 0)
            send_message(chat_id, f"💰 Your balance: ₹{balance}")

        elif text == "/withdraw":
            user = users.find_one({"user_id": user_id})
            now = datetime.utcnow()
            last_withdraw = user.get("last_withdraw")
            if last_withdraw:
                diff = (now - last_withdraw).days
                if diff < 1:
                    send_message(chat_id, "⏳ You can withdraw only once per day.")
                    return "ok", 200

            if user["balance"] >= MIN_WITHDRAW:
                users.update_one({"user_id": user_id}, {
                    "$inc": {"balance": -MIN_WITHDRAW},
                    "$push": {"withdraws": {"amount": MIN_WITHDRAW, "time": now}},
                    "$set": {"last_withdraw": now}
                })
                send_message(chat_id, f"✅ ₹{MIN_WITHDRAW} withdrawal requested. You'll receive it soon.")
            else:
                send_message(chat_id, f"❌ Minimum ₹{MIN_WITHDRAW} required to withdraw.")

    return "ok", 200

@app.route("/")
def home():
    return "✅ Actualearn Bot is Live", 200

if __name__ == "__main__":
    app.run()
